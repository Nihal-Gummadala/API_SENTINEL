def _location(info):
    return info.get("in") or "?"


def Diff_Indexes(old_index, new_index):
    changes = {}
    old_endpoints, new_endpoints = old_index["endpoints"], new_index["endpoints"]

    def add(key, kind, severity, message, name=None):
        changes.setdefault(key, []).append({"kind": kind, "severity": severity, "name": name, "message": message})

    for key, old in old_endpoints.items():
        new = new_endpoints.get(key)
        if new is None:
            add(key, "removed_endpoint", "high", f"{key} was removed.")
            continue

        if new["deprecated"] and not old["deprecated"]:
            add(key, "became_deprecated", "medium", f"{key} is now deprecated.")

        old_params, new_params = old["params"], new["params"]
        removed = [name for name in old_params if name not in new_params]
        added = [name for name in new_params if name not in old_params]
        for name in removed:
            location = _location(old_params[name])
            hint = ""
            same_place = [other for other in added if _location(new_params[other]) == location]
            if len(same_place) == 1:
                hint = f" (possibly renamed to '{same_place[0]}')"
            add(key, "removed_param", "high", f"{location} parameter '{name}' was removed{hint}.", name)
        for name in added:
            if new_params[name]["required"] and _location(new_params[name]) != "path":
                add(key, "new_required_param", "high",
                    f"new required {_location(new_params[name])} parameter '{name}'.", name)
        for name in old_params:
            if name in new_params:
                if new_params[name]["required"] and not old_params[name]["required"]:
                    add(key, "param_now_required", "high", f"parameter '{name}' is now required.", name)
                if new_params[name]["deprecated"] and not old_params[name]["deprecated"]:
                    add(key, "param_deprecated", "medium", f"parameter '{name}' is now deprecated.", name)

        if old["body_known"] and new["body_known"]:
            removed_fields = [name for name in old["body_fields"] if name not in new["body_fields"]]
            added_fields = [name for name in new["body_fields"] if name not in old["body_fields"]]
            for name in removed_fields:
                hint = f" (possibly renamed to '{added_fields[0]}')" if len(added_fields) == 1 and len(removed_fields) == 1 else ""
                add(key, "removed_body_field", "high", f"body field '{name}' was removed{hint}.", name)
        for name in new["body_required"]:
            if name not in old["body_required"]:
                kind = "field_now_required" if name in old["body_fields"] else "new_required_field"
                add(key, kind, "high", f"body field '{name}' is now required.", name)
        if new["body_is_required"] and not old["body_is_required"]:
            add(key, "body_now_required", "high", "a request body is now required.")

        if old["success_statuses"] and new["success_statuses"] and old["success_statuses"] != new["success_statuses"]:
            add(key, "success_status_changed", "low",
                f"success status changed from {', '.join(old['success_statuses'])} "
                f"to {', '.join(new['success_statuses'])}.")

    return changes


def Is_Relevant(change, call):
    """Does this change affect this particular call? Returns (relevant, confidence)."""
    name = change["name"]
    kind = change["kind"]

    if kind == "removed_param":
        sent = call["query_params"]
        if sent is None:
            return True, "possible"
        return name in sent, "verified"

    if kind == "removed_body_field":
        sent = call["body_fields"]
        if sent is None:
            return True, "possible"
        return name in sent, "verified"

    if kind in ("new_required_param", "param_now_required"):
        sent = call["query_params"]
        if sent is None:
            return True, "possible"
        return name not in sent, "verified"

    if kind in ("new_required_field", "field_now_required"):
        sent = call["body_fields"]
        if sent is None:
            return True, "possible"
        return name not in sent, "verified"

    if kind == "param_deprecated":
        sent = call["query_params"]
        if sent is None:
            return False, "possible" 
        return name in sent, "verified"

    return True, "verified" 


def Changes_For_Call(changes, endpoint_key, call):
    relevant = []
    for change in changes.get(endpoint_key, []):
        is_relevant, confidence = Is_Relevant(change, call)
        if not is_relevant:
            continue
        severity = change["severity"]
        if confidence == "possible" and severity == "high":
            severity = "medium"
        relevant.append({**change, "severity": severity, "confidence": confidence})
    return relevant
