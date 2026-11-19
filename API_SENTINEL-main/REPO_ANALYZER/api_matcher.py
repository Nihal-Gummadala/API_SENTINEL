import re

BODY_METHODS = ("POST", "PUT", "PATCH", "DELETE")
SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def _tokenize(path, multi_segment):
    
    tokens = []
    for segment in path.split("/"):
        if not segment:
            continue
        whole_param = re.fullmatch(r"\{([^{}]+)\}", segment)
        if whole_param:
            name = whole_param.group(1)
            tokens.append(("multi" if name in multi_segment else "param", name))
        elif "{" in segment:
            pattern = "".join(".+" if piece.startswith("{") else re.escape(piece)
                              for piece in re.split(r"(\{[^{}]+\})", segment) if piece)
            tokens.append(("pattern", re.compile(pattern + r"\Z")))
        else:
            tokens.append(("literal", segment))
    return tokens


def _match_score(code_segments, tokens, placeholder_matches_literal=False):

    def match(i, j):
        if j == len(tokens):
            return 0 if i == len(code_segments) else -1
        if i >= len(code_segments):
            return -1
        kind, value = tokens[j]
        segment = code_segments[i]

        if kind == "literal":
            if segment != value and not (placeholder_matches_literal and segment == "{}"):
                return -1
            rest = match(i + 1, j + 1)
            return rest + 1 if rest >= 0 else -1

        if kind == "pattern":
            if segment != "{}" and not value.match(segment):
                return -1
            return match(i + 1, j + 1)

        if kind == "multi":
            for end in range(len(code_segments), i, -1):
                rest = match(end, j + 1)
                if rest >= 0:
                    return rest
            return -1

        return match(i + 1, j + 1)  

    return match(0, 0)


class EndpointMatcher:
    def __init__(self, index):
        self.index = index
        self.base_segments = [segment for segment in index.get("base_path", "").split("/") if segment]
        self.paths = {}  
        for key, endpoint in index["endpoints"].items():
            entry = self.paths.setdefault(endpoint["path"], {
                "tokens": _tokenize(endpoint["path"], set(endpoint.get("multi_segment", []))),
                "methods": {},
            })
            entry["methods"][endpoint["method"]] = key

    def match(self, method, code_segments):
        segments = list(code_segments)
        if self.base_segments and segments[:len(self.base_segments)] == self.base_segments:
            segments = segments[len(self.base_segments):]  

        candidates = []
        for path, entry in self.paths.items():
            score = _match_score(segments, entry["tokens"])
            if score >= 0:
                candidates.append((score, path, entry))
        if not candidates:
            if "{}" in segments and any(_match_score(segments, entry["tokens"], True) >= 0
                                        for entry in self.paths.values()):
                return {"status": "ambiguous", "endpoint": None, "path": None, "allowed": []}
            return {"status": "no_endpoint", "endpoint": None, "path": None, "allowed": []}

        candidates.sort(key=lambda candidate: -candidate[0])
        for score, path, entry in candidates:
            if method in entry["methods"]:
                return {"status": "matched", "endpoint": entry["methods"][method], "path": path,
                        "allowed": sorted(entry["methods"])}

        best_path, best_entry = candidates[0][1], candidates[0][2]
        return {"status": "method_not_allowed", "endpoint": None, "path": best_path,
                "allowed": sorted(best_entry["methods"])}


def _finding(call, kind, severity, message, confidence="verified", endpoint=None, source="current docs"):
    return {
        "file": call["file"],
        "line": call["line"],
        "api": call["api"],
        "method": call["method"],
        "url": call["url"],
        "endpoint": endpoint["method"] + " " + endpoint["path"] if endpoint else None,
        "kind": kind,
        "severity": severity,
        "confidence": confidence,
        "source": source,
        "message": message,
        "docs_url": endpoint.get("docs_url") if endpoint else None,
    }


def Header_Value(headers, name):
    if headers is None:
        return None
    for key, value in headers.items():
        if key.lower() == name.lower():
            return value if value is not None else "{unknown}"
    return None


def Check_Call(call, match, index, api_info, version_used=None, latest_version=None):
    """Compares one call with the docs it was matched against. Returns a list of findings."""
    findings = []
    label = f"{call['method']} {call['url']}"

    if match["status"] == "ambiguous":
        return findings  

    if match["status"] == "no_endpoint":
        findings.append(_finding(call, "no_endpoint", "high",
            f"{label}: no endpoint with this path exists in the {call['api']} docs. "
            f"It may have been removed, or the URL may be wrong."))
        return findings

    if match["status"] == "method_not_allowed":
        findings.append(_finding(call, "method_not_allowed", "high",
            f"{label}: {match['path']} exists but does not accept {call['method']} "
            f"(documented: {', '.join(match['allowed'])})."))
        return findings

    endpoint = index["endpoints"][match["endpoint"]]

    if endpoint["deprecated"]:
        findings.append(_finding(call, "deprecated_endpoint", "medium",
            f"{label}: this endpoint is marked deprecated in the docs.", endpoint=endpoint))


    query_params = {name: info for name, info in endpoint["params"].items() if info["in"] == "query"}
    if call["query_params"] is not None:
        for name in call["query_params"]:
            if "{" in name:
                continue
            if name not in query_params:
                findings.append(_finding(call, "unknown_query_param", "low",
                    f"{label}: query parameter '{name}' is not documented for this endpoint "
                    f"(it may have been renamed or removed).", confidence="likely", endpoint=endpoint))
            elif query_params[name]["deprecated"]:
                findings.append(_finding(call, "deprecated_param", "medium",
                    f"{label}: query parameter '{name}' is deprecated.", endpoint=endpoint))
        if "params" not in call["incomplete"]:
            for name, info in query_params.items():
                if info["required"] and name not in call["query_params"]:
                    findings.append(_finding(call, "missing_required_param", "high",
                        f"{label}: required query parameter '{name}' is not sent.", endpoint=endpoint))

    if call["method"] in BODY_METHODS and call["body_fields"] is not None:
        sent = set(call["body_fields"])
        body_complete = "json" not in call["incomplete"] and "data" not in call["incomplete"]
        if endpoint["body_known"]:
            for name in sorted(sent - set(endpoint["body_fields"])):
                findings.append(_finding(call, "unknown_body_field", "low",
                    f"{label}: body field '{name}' is not documented for this endpoint "
                    f"(it may have been renamed or removed).", confidence="likely", endpoint=endpoint))
        if body_complete:
            if endpoint["body_is_required"] and not sent:
                findings.append(_finding(call, "missing_body", "high",
                    f"{label}: this endpoint requires a request body, but none is sent.", endpoint=endpoint))
            elif sent:
                for name in endpoint["body_required"]:
                    if name not in sent:
                        findings.append(_finding(call, "missing_required_field", "high",
                            f"{label}: required body field '{name}' is not sent.", endpoint=endpoint))

    if call["headers"] is not None and "headers" not in call["incomplete"]:
        for name, info in endpoint["params"].items():
            if info["in"] == "header" and info["required"] and Header_Value(call["headers"], name) is None:
                findings.append(_finding(call, "missing_required_header", "medium",
                    f"{label}: required header '{name}' is not sent.", endpoint=endpoint))


    version_header = api_info.get("version_header")
    if version_header and call["headers"] is not None:
        pinned = Header_Value(call["headers"], version_header)
        if pinned is None and "headers" not in call["incomplete"]:
            message = (f"{label}: no {version_header} header, so this request uses the default version "
                       f"{api_info.get('default_version')}.")
            if latest_version and latest_version != api_info.get("default_version"):
                message += f" The newest version is {latest_version}; pin a version so upgrades are deliberate."
            findings.append(_finding(call, "version_not_pinned", "medium", message, endpoint=endpoint))


    return findings
