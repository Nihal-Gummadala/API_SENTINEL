import os
import json
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
REGISTRY_PATH = os.path.join(HERE, "api_registry.json")
CACHE_DIR = os.environ.get("API_SENTINEL_CACHE") or os.path.join(os.path.expanduser("~"), ".cache", "api_sentinel")
SNAPSHOTS_TO_KEEP = 10
MAX_AGE_HOURS = 24
HTTP_METHODS = ("get", "post", "put", "delete", "patch", "head", "options")


def Load_Registry(path=REGISTRY_PATH):
    with open(path) as file:
        registry = json.load(file)
    return {name: info for name, info in registry.items() if not name.startswith("_")}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hours_since(timestamp):
    then = datetime.fromisoformat(timestamp)
    return (datetime.now(timezone.utc) - then).total_seconds() / 3600


def Spec_URL(api_info, version=None):
    if version and api_info.get("versioned_spec_url"):
        return api_info["versioned_spec_url"].format(version=version)
    return api_info["spec_url"]


def Fetch_Spec(api_name, version=None, registry=None, cache_dir=CACHE_DIR, max_age_hours=MAX_AGE_HOURS, force=False):

    registry = registry or Load_Registry()
    api_info = registry[api_name]
    label = version or "latest"
    url = Spec_URL(api_info, version)
    extension = "yaml" if api_info.get("format") == "yaml" else "json"

    folder = os.path.join(cache_dir, "specs", api_name)
    os.makedirs(folder, exist_ok=True)
    spec_path = os.path.join(folder, f"{label}.{extension}")
    meta_path = os.path.join(folder, f"{label}.meta.json")

    meta = {}
    if os.path.exists(meta_path) and os.path.exists(spec_path):
        with open(meta_path) as file:
            meta = json.load(file)
        if not force and meta.get("url") == url and _hours_since(meta["checked_at"]) < max_age_hours:
            return spec_path, meta

    request_headers = {}
    if meta.get("etag") and meta.get("url") == url and not force:
        request_headers["If-None-Match"] = meta["etag"]

    try:
        response = requests.get(url, headers=request_headers, timeout=120)
    except requests.RequestException as error:
        if meta:
            print(f"Warning: could not refresh {api_name} docs ({error}); using cached copy from {meta['fetched_at']}")
            return spec_path, meta
        raise RuntimeError(f"Could not download {api_name} docs from {url}: {error}")

    if response.status_code == 304:
        meta["checked_at"] = _now()
    elif response.status_code == 200:
        content = response.content
        with open(spec_path, "wb") as file:
            file.write(content)
        meta = {
            "url": url,
            "fetched_at": _now(),
            "checked_at": _now(),
            "etag": response.headers.get("ETag"),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    elif meta:
        print(f"Warning: {api_name} docs returned HTTP {response.status_code}; using cached copy")
        return spec_path, meta
    else:
        raise RuntimeError(f"Could not download {api_name} docs from {url}: HTTP {response.status_code}")

    with open(meta_path, "w") as file:
        json.dump(meta, file, indent=2)
    return spec_path, meta


def Parse_Spec(spec_path):
    with open(spec_path, "rb") as file:
        raw = file.read()
    if spec_path.endswith((".yaml", ".yml")):
        import yaml  
        loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)  
        return yaml.load(raw, Loader=loader)
    return json.loads(raw)


def Load_Endpoint_Index(api_name, version=None, registry=None, cache_dir=CACHE_DIR, force=False):
    registry = registry or Load_Registry()
    label = version or "latest"
    spec_path, meta = Fetch_Spec(api_name, version, registry, cache_dir, force=force)
    snapshot = meta["sha256"][:12]

    index_folder = os.path.join(cache_dir, "index", api_name, label)
    os.makedirs(index_folder, exist_ok=True)
    index_path = os.path.join(index_folder, f"{snapshot}.json")

    if os.path.exists(index_path):
        with open(index_path) as file:
            index = json.load(file)
    else:
        spec = Parse_Spec(spec_path)
        index = Build_Endpoint_Index(spec, api_name, label)
        index["snapshot"] = snapshot
        index["fetched_at"] = meta["fetched_at"]
        index["source_url"] = meta["url"]
        with open(index_path, "w") as file:
            json.dump(index, file)
        _prune_snapshots(index_folder)

    index["index_file"] = index_path
    return index


def _prune_snapshots(folder, keep=SNAPSHOTS_TO_KEEP):
    snapshots = sorted((os.path.join(folder, name) for name in os.listdir(folder) if name.endswith(".json")),
                       key=os.path.getmtime, reverse=True)
    for old in snapshots[keep:]:
        os.remove(old)


def Load_Index_File(path):
    with open(path) as file:
        return json.load(file)


def _resolve(spec, node, depth=0):
    """Follows "$ref": "#/components/..." pointers."""
    while isinstance(node, dict) and "$ref" in node and depth < 50:
        reference = node["$ref"]
        if not reference.startswith("#/"):
            return {}  # references to other files aren't supported
        target = spec
        for key in reference[2:].split("/"):
            key = key.replace("~1", "/").replace("~0", "~")
            target = target.get(key, {}) if isinstance(target, dict) else {}
        node = target
        depth += 1
    return node if isinstance(node, dict) else {}


def _schema_fields(spec, schema, depth=0):

    schema = _resolve(spec, schema)
    if depth > 8 or not schema:
        return set(), set(), False

    properties = set(schema.get("properties", {}))
    required = set(schema.get("required", []))
    known = bool(properties)

    for part in schema.get("allOf", []):
        sub_properties, sub_required, sub_known = _schema_fields(spec, part, depth + 1)
        properties |= sub_properties
        required |= sub_required
        known = known or sub_known

    options = schema.get("oneOf", []) + schema.get("anyOf", [])
    if options:
        option_fields = [_schema_fields(spec, option, depth + 1) for option in options]
        for sub_properties, _, sub_known in option_fields:
            properties |= sub_properties
            known = known or sub_known
        
        required |= set.intersection(*(sub_required for _, sub_required, _ in option_fields))

    if schema.get("additionalProperties") not in (None, False):
        known = False  
    return properties, required, known


def _request_body(spec, operation):
    body = _resolve(spec, operation.get("requestBody", {}))
    if not body:
        return {"body_fields": [], "body_required": [], "body_known": True, "body_is_required": False}

    content = body.get("content", {})
    media = content.get("application/json")
    if media is None:
        media = next((value for value in content.values() if isinstance(value, dict) and "schema" in value), {})
    properties, required, known = _schema_fields(spec, media.get("schema", {}))
    return {
        "body_fields": sorted(properties),
        "body_required": sorted(required),
        "body_known": known,
        "body_is_required": bool(body.get("required", False)),
    }


def Build_Endpoint_Index(spec, api_name="", version=""):
    servers = spec.get("servers") or [{"url": ""}]
    base_path = urlparse(servers[0].get("url", "")).path.rstrip("/")

    endpoints = {}
    mentioned_versions = set()

    for path, path_item in spec.get("paths", {}).items():
        path_item = _resolve(spec, path_item)
        shared_parameters = path_item.get("parameters", [])

        for method in HTTP_METHODS:
            operation = path_item.get(method)
            if not isinstance(operation, dict):
                continue

            params, multi_segment = {}, []
            for parameter in shared_parameters + operation.get("parameters", []):
                parameter = _resolve(spec, parameter)
                if "name" not in parameter:
                    continue
                params[parameter["name"]] = {
                    "in": parameter.get("in"),
                    "required": bool(parameter.get("required", False)),
                    "deprecated": bool(parameter.get("deprecated", False)),
                }
                if parameter.get("x-multi-segment"):
                    multi_segment.append(parameter["name"])

            for change in operation.get("x-github-breaking-changes", []):
                if change.get("version"):
                    mentioned_versions.add(change["version"])

            key = f"{method.upper()} {path}"
            endpoints[key] = {
                "method": method.upper(),
                "path": path,
                "operation_id": operation.get("operationId"),
                "summary": operation.get("summary"),
                "deprecated": bool(operation.get("deprecated", False)),
                "docs_url": (operation.get("externalDocs") or {}).get("url"),
                "params": params,
                "multi_segment": multi_segment,
                "success_statuses": sorted(code for code in operation.get("responses", {}) if str(code).startswith("2")),
                **_request_body(spec, operation),
            }

    return {
        "api": api_name,
        "version": version,
        "base_path": base_path,
        "mentioned_versions": sorted(mentioned_versions),
        "endpoints": endpoints,
    }


def Latest_Version(api_name, registry=None, cache_dir=CACHE_DIR):
    """Newest version we know of: the registry's list plus any versions the
    unversioned spec mentions in its breaking-change notes."""
    registry = registry or Load_Registry()
    api_info = registry[api_name]
    versions = set(api_info.get("known_versions", []))
    if api_info.get("default_version"):
        versions.add(api_info["default_version"])
    try:
        versions |= set(Load_Endpoint_Index(api_name, None, registry, cache_dir)["mentioned_versions"])
    except RuntimeError as error:
        print(f"Warning: could not check for new {api_name} versions: {error}")
    return max(versions) if versions else None


if __name__ == "__main__":
    import sys
    name = sys.argv[1] if len(sys.argv) > 1 else "GitHub"
    version = sys.argv[2] if len(sys.argv) > 2 else None
    index = Load_Endpoint_Index(name, version)
    print(f"{name} {index['version']}: {len(index['endpoints'])} endpoints, snapshot {index['snapshot']}")
