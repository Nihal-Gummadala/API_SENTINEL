import os
import re
import json
from datetime import datetime, timezone

from doc_fetcher import Load_Registry, Load_Endpoint_Index, Load_Index_File, Latest_Version, CACHE_DIR
from code_analyzer import Normalize_URL
from api_matcher import EndpointMatcher, Check_Call, Header_Value, SEVERITY_ORDER, _finding
from spec_diff import Diff_Indexes, Changes_For_Call


def _unverified(call, reason):
    return {"file": call["file"], "line": call["line"], "method": call["method"],
            "url": call["url"] or call["url_expression"], "reason": reason}


def Run_API_Checks(api_calls_by_file, repository, registry=None, load_index=None,
                   latest_version_for=None, state_dir=None, save_state=True):

    registry = registry or Load_Registry()
    load_index = load_index or (lambda api, version: Load_Endpoint_Index(api, version, registry))
    latest_version_for = latest_version_for or (lambda api: Latest_Version(api, registry))
    state_dir = state_dir or os.path.join(CACHE_DIR, "state")

    calls = [{**call, "file": file_name} for file_name, file_calls in api_calls_by_file.items() for call in file_calls]
    findings, errors = [], []
    summary = {
        "total_calls": len(calls),
        "checked_calls": 0,
        "untracked_hosts": {},  
        "unverified": [],      
        "apis": {},           
    }

    indexes, matchers, latest_versions = {}, {}, {}
    used_endpoints = {} 

    def get_index(api, version):
        key = (api, version)
        if key not in indexes:
            try:
                indexes[key] = load_index(api, version)
                matchers[key] = EndpointMatcher(indexes[key])
            except (RuntimeError, OSError, ValueError) as error:
                indexes[key] = None
                errors.append(f"{api} docs ({version or 'latest'}) unavailable: {error}")
        return indexes[key], matchers.get(key)


    for call in calls:
        api = call["api"]

        if call["url_status"] != "resolved":
            if call["url"] is None:
                reason = f"URL comes from `{call['url_expression']}`, which couldn't be traced in this file"
            else:
                reason = "the start of the URL (the host) couldn't be traced"
            summary["unverified"].append(_unverified(call, reason))
            continue

        if api not in registry:
            host = Normalize_URL(call["url"])[0]
            summary["untracked_hosts"][host] = summary["untracked_hosts"].get(host, 0) + 1
            continue

        if not call["method"]:
            summary["unverified"].append(_unverified(call, "the HTTP method couldn't be read"))
            continue

        api_info = registry[api]
        version, latest = None, None
        version_header = api_info.get("version_header")
        if version_header:
            if api not in latest_versions:
                latest_versions[api] = latest_version_for(api)
            latest = latest_versions[api]
            default = api_info.get("default_version")
            known = set(api_info.get("known_versions", [])) | {default} | ({latest} if latest else set())

            pinned = Header_Value(call["headers"], version_header)
            if pinned and "{" not in pinned:
                if pinned in known:
                    version = pinned
                else:
                    findings.append(_finding(call, "unknown_version", "high",
                        f"{call['method']} {call['url']}: {version_header}: {pinned} is not a version we know "
                        f"(known: {', '.join(sorted(v for v in known if v))}). Requests with an unsupported "
                        f"version are rejected."))
                    version = default
            else:
                version = default

        index, matcher = get_index(api, version)
        if index is None:
            summary["unverified"].append(_unverified(call, f"{api} docs could not be downloaded"))
            continue

        match = matcher.match(call["method"], Normalize_URL(call["url"])[1])
        if match["status"] == "ambiguous":
            summary["unverified"].append(_unverified(call, "parts of the URL path are unknown, so the endpoint can't be pinned down"))
            continue

        summary["checked_calls"] += 1
        findings.extend(Check_Call(call, match, index, api_info, version, latest))
        if match["status"] == "matched":
            used_endpoints.setdefault((api, version), []).append((call, match["endpoint"]))

        api_summary = summary["apis"].setdefault(api, {"versions_checked": [], "latest_version": latest,
                                                       "docs_fetched_at": index.get("fetched_at"), "calls_checked": 0})
        api_summary["calls_checked"] += 1
        if version and version not in api_summary["versions_checked"]:
            api_summary["versions_checked"].append(version)

    for (api, version), uses in used_endpoints.items():
        latest = latest_versions.get(api)
        if not (version and latest and version < latest):
            continue
        new_index, _ = get_index(api, latest)
        if new_index is None:
            continue
        old_index = indexes[(api, version)]
        changes = Diff_Indexes(old_index, new_index)
        upgrade = summary["apis"][api].setdefault("upgrades", {})
        upgrade[version] = {"to": latest, "calls": len(uses), "breaking_changes_in_docs": sum(len(c) for c in changes.values()),
                            "changes_affecting_calls": 0}
        for call, key in uses:
            for change in Changes_For_Call(changes, key, call):
                upgrade[version]["changes_affecting_calls"] += 1
                findings.append(_finding(call, change["kind"], change["severity"],
                    f"{call['method']} {call['url']}: in version {latest}, {change['message']}",
                    confidence=change["confidence"], endpoint=old_index["endpoints"][key],
                    source=f"upgrade {version} -> {latest}"))

    safe_name = re.sub(r"[^A-Za-z0-9_.-]", "_", repository) or "repo"
    state_path = os.path.join(state_dir, f"{safe_name}.json")
    state = {}
    if os.path.exists(state_path):
        with open(state_path) as file:
            state = json.load(file)
    new_state = dict(state)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    for (api, version), uses in used_endpoints.items():
        index = indexes[(api, version)]
        label = f"{api}@{version or 'latest'}"
        previous = state.get(label)
        if (previous and index.get("snapshot") and previous.get("snapshot") != index.get("snapshot")
                and previous.get("index_file") and os.path.exists(previous["index_file"])):
            old_index = Load_Index_File(previous["index_file"])
            changes = Diff_Indexes(old_index, index)
            for call, key in uses:
                for change in Changes_For_Call(changes, key, call):
                    findings.append(_finding(call, change["kind"], change["severity"],
                        f"{call['method']} {call['url']}: since the last check ({previous['checked_at'][:10]}), "
                        f"{change['message']}", confidence=change["confidence"],
                        endpoint=index["endpoints"].get(key), source="docs changed since last run"))
        if index.get("snapshot"):
            new_state[label] = {"snapshot": index["snapshot"], "index_file": index.get("index_file"), "checked_at": now}

    if save_state and new_state:
        os.makedirs(state_dir, exist_ok=True)
        with open(state_path, "w") as file:
            json.dump(new_state, file, indent=2)

    unique, seen = [], set()
    for finding in findings:
        key = (finding["file"], finding["line"], finding["kind"], finding["message"])
        if key not in seen:
            seen.add(key)
            unique.append(finding)
    unique.sort(key=lambda f: (SEVERITY_ORDER[f["severity"]], f["file"], f["line"]))

    return {"findings": unique, "summary": summary, "errors": errors}
