"""Offline tests for API Sentinel's API checks (no network needed).
Run from the REPO_ANALYZER folder:   python -m unittest discover tests"""

import os
import sys
import copy
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from code_analyzer import Detect_API_Calls, Identify_API, Normalize_URL
from doc_fetcher import Build_Endpoint_Index
from api_matcher import EndpointMatcher
from spec_diff import Diff_Indexes
from api_checks import Run_API_Checks

REGISTRY = {
    "Demo": {"hosts": ["api.demo.com"], "version_header": "X-Demo-Version",
             "default_version": "2024-01-01", "known_versions": ["2024-01-01", "2025-01-01"]},
}

# A tiny OpenAPI document in the same shape as GitHub's.
SPEC_V1 = {
    "openapi": "3.0.3",
    "servers": [{"url": "https://api.demo.com"}],
    "components": {"parameters": {
        "owner": {"name": "owner", "in": "path", "required": True},
        "repo": {"name": "repo", "in": "path", "required": True},
    }},
    "paths": {
        "/repos/{owner}/{repo}/contents/{path}": {
            "get": {"operationId": "get-content",
                    "parameters": [{"$ref": "#/components/parameters/owner"}, {"$ref": "#/components/parameters/repo"},
                                   {"name": "path", "in": "path", "required": True, "x-multi-segment": True},
                                   {"name": "ref", "in": "query"}],
                    "responses": {"200": {}}},
        },
        "/repos/{owner}/{repo}/issues": {
            "get": {"parameters": [{"$ref": "#/components/parameters/owner"}, {"$ref": "#/components/parameters/repo"},
                                   {"name": "state", "in": "query"}],
                    "responses": {"200": {}}},
            "post": {"parameters": [{"$ref": "#/components/parameters/owner"}, {"$ref": "#/components/parameters/repo"}],
                     "requestBody": {"required": True, "content": {"application/json": {"schema": {
                         "type": "object", "required": ["title"],
                         "properties": {"title": {}, "body": {}, "assignee": {}}}}}},
                     "responses": {"201": {}}},
        },
        "/old": {"get": {"deprecated": True, "responses": {"200": {}}}},
    },
}

# Version 2: 'assignee' removed, 'state' renamed to 'status', /old removed.
SPEC_V2 = copy.deepcopy(SPEC_V1)
del SPEC_V2["paths"]["/repos/{owner}/{repo}/issues"]["post"]["requestBody"]["content"]["application/json"]["schema"]["properties"]["assignee"]
SPEC_V2["paths"]["/repos/{owner}/{repo}/issues"]["get"]["parameters"][2] = {"name": "status", "in": "query"}
del SPEC_V2["paths"]["/old"]

CLIENT = '''
import requests
from requests import get

BASE = "https://api.demo.com"
HEADERS = {"X-Demo-Version": "2024-01-01"}

def issues(owner, repo, url_from_caller, token=None):
    url = f"{BASE}/repos/{owner}/{repo}/issues"
    requests.post(url, json={"title": "t", "assignee": "me"}, headers=HEADERS)     # line 10
    requests.get(url, params={"state": "open"}, headers=HEADERS)                    # line 11
    requests.post(url, json={"body": "no title"}, headers=HEADERS)                  # line 12
    requests.get(url_from_caller)                                                   # line 13
    get(BASE + "/old")                                                              # line 14
    requests.request("PUT", BASE + "/repos/a/b/issues", headers=HEADERS)            # line 15
    requests.get(f"{BASE}/repos/a/b/contents/src/deep/file.py", headers=HEADERS)    # line 16
    requests.get(BASE + "/nope", headers=HEADERS)                                   # line 17
    requests.get("https://api.other.com/x")                                         # line 18
'''


def build_calls():
    calls = Identify_API(Detect_API_Calls("client.py", CLIENT), REGISTRY)
    return {"client.py": calls}


class DetectorTests(unittest.TestCase):
    def setUp(self):
        self.calls = {call["line"]: call for call in build_calls()["client.py"]}

    def test_finds_every_call_shape(self):
        self.assertEqual(sorted(self.calls), [10, 11, 12, 13, 14, 15, 16, 17, 18])

    def test_traces_url_through_variables(self):
        self.assertEqual(self.calls[10]["url"], "https://api.demo.com/repos/{owner}/{repo}/issues")
        self.assertEqual(self.calls[10]["api"], "Demo")

    def test_reads_body_params_and_headers(self):
        self.assertEqual(self.calls[10]["body_fields"], ["title", "assignee"])
        self.assertEqual(self.calls[11]["query_params"], ["state"])
        self.assertEqual(self.calls[10]["headers"], {"X-Demo-Version": "2024-01-01"})

    def test_parameter_url_is_unresolved(self):
        self.assertEqual(self.calls[13]["url_status"], "unresolved")
        self.assertEqual(self.calls[13]["url_expression"], "url_from_caller")

    def test_request_and_from_import(self):
        self.assertEqual(self.calls[15]["method"], "PUT")
        self.assertEqual(self.calls[14]["method"], "GET")

    def test_normalize(self):
        self.assertEqual(Normalize_URL("https://API.demo.com/a/{x}/b?y=1"), ("api.demo.com", ["a", "{}", "b"]))
        self.assertEqual(Normalize_URL("{base}/a")[0], None)


class MatcherTests(unittest.TestCase):
    def setUp(self):
        self.matcher = EndpointMatcher(Build_Endpoint_Index(SPEC_V1))

    def test_multi_segment_path(self):
        result = self.matcher.match("GET", ["repos", "a", "b", "contents", "src", "deep", "file.py"])
        self.assertEqual(result["endpoint"], "GET /repos/{owner}/{repo}/contents/{path}")

    def test_method_not_allowed(self):
        self.assertEqual(self.matcher.match("PUT", ["repos", "a", "b", "issues"])["status"], "method_not_allowed")

    def test_unknown_part_is_ambiguous_not_missing(self):
        self.assertEqual(self.matcher.match("GET", ["{}", "a", "b", "issues"])["status"], "ambiguous")
        self.assertEqual(self.matcher.match("GET", ["nope"])["status"], "no_endpoint")


class DiffTests(unittest.TestCase):
    def test_breaking_changes(self):
        changes = Diff_Indexes(Build_Endpoint_Index(SPEC_V1), Build_Endpoint_Index(SPEC_V2))
        kinds = {key: [change["kind"] for change in value] for key, value in changes.items()}
        self.assertIn("removed_endpoint", kinds["GET /old"])
        self.assertIn("removed_body_field", kinds["POST /repos/{owner}/{repo}/issues"])
        self.assertIn("possibly renamed to 'status'", changes["GET /repos/{owner}/{repo}/issues"][0]["message"])


class EndToEndTests(unittest.TestCase):
    def run_checks(self, specs, state_dir):
        def load_index(api, version):
            index = Build_Endpoint_Index(specs[version], api, version)
            index["snapshot"] = str(hash(str(specs[version])))
            path = os.path.join(state_dir, f"{version}-{index['snapshot']}.json")
            with open(path, "w") as file:
                import json
                json.dump(index, file)
            index["index_file"] = path
            return index

        return Run_API_Checks(build_calls(), "demo", registry=REGISTRY, load_index=load_index,
                              latest_version_for=lambda api: "2025-01-01", state_dir=state_dir)

    def test_findings(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_checks({"2024-01-01": SPEC_V1, "2025-01-01": SPEC_V2}, folder)
        found = {(f["line"], f["kind"]) for f in result["findings"]}

        self.assertIn((12, "missing_required_field"), found)      # no 'title'
        self.assertIn((14, "deprecated_endpoint"), found)
        self.assertIn((14, "version_not_pinned"), found)
        self.assertIn((15, "method_not_allowed"), found)
        self.assertIn((17, "no_endpoint"), found)
        self.assertIn((10, "removed_body_field"), found)          # upgrade: 'assignee' is gone
        self.assertIn((11, "removed_param"), found)               # upgrade: 'state' renamed
        self.assertNotIn((16, "no_endpoint"), found)              # deep path matched {path}
        self.assertFalse(any(line == 16 for line, _ in found))
        self.assertEqual(result["summary"]["untracked_hosts"], {"api.other.com": 1})
        self.assertEqual([item["line"] for item in result["summary"]["unverified"]], [13])

    def test_upgrade_only_flags_fields_actually_sent(self):
        with tempfile.TemporaryDirectory() as folder:
            result = self.run_checks({"2024-01-01": SPEC_V1, "2025-01-01": SPEC_V2}, folder)
        upgrade_lines = {f["line"] for f in result["findings"] if f["source"].startswith("upgrade")}
        self.assertNotIn(12, upgrade_lines)  # line 12 never sends 'assignee'

    def test_changes_since_last_run(self):
        with tempfile.TemporaryDirectory() as folder:
            self.run_checks({"2024-01-01": SPEC_V1, "2025-01-01": SPEC_V1}, folder)          # first run
            result = self.run_checks({"2024-01-01": SPEC_V2, "2025-01-01": SPEC_V2}, folder)  # docs changed
        since = {(f["line"], f["kind"]) for f in result["findings"] if f["source"] == "docs changed since last run"}
        self.assertIn((10, "removed_body_field"), since)


if __name__ == "__main__":
    unittest.main()
