# A deliberately broken API client used to try out API Sentinel:
#   python Github_Repo_analyzer.py --local tests/fixtures/sample_repo
# Each call has a comment saying what the tool should flag.
import requests
import httpx
from requests import get

BASE = "https://api.github.com"
PINNED = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}


def create_issue(owner, repo):
    # 'assignee' is removed in GitHub API version 2026-03-10 -> upgrade warning
    url = f"{BASE}/repos/{owner}/{repo}/issues"
    return requests.post(url, json={"title": "Bug", "assignee": "octocat"}, headers=PINNED)


def list_issues_typo(owner, repo):
    # 'issuez' is not an endpoint -> no_endpoint
    return requests.get(f"{BASE}/repos/{owner}/{repo}/issuez", headers=PINNED)


def delete_file(owner, repo, path):
    # DELETE contents requires a body with 'message' and 'sha' -> missing_body
    return requests.delete(f"{BASE}/repos/{owner}/{repo}/contents/{path}", headers=PINNED)


def my_repos():
    # 'foo' is not a documented query parameter -> unknown_query_param
    session = requests.Session()
    return session.get(BASE + "/user/repos", params={"visibility": "all", "foo": 1})


def update_user():
    # /user accepts GET and PATCH, not PUT -> method_not_allowed
    return requests.put(BASE + "/user", json={"name": "x"}, headers=PINNED)


def classroom():
    # deprecated endpoint, and no version header -> deprecated_endpoint + version_not_pinned
    return get("https://api.github.com/classrooms")


def bogus_version():
    # this version doesn't exist -> unknown_version
    return requests.get(BASE + "/user", headers={"X-GitHub-Api-Version": "2023-01-01"})


def chat():
    # OpenAI requires 'messages' -> missing_required_field
    return httpx.post("https://api.openai.com/v1/chat/completions", json={"model": "gpt-4o-mini"})


def stripe():
    # not in api_registry.json -> listed under "APIs without docs"
    return requests.get("https://api.stripe.com/v1/charges")


def fine():
    # correct call -> no findings
    return requests.get(f"{BASE}/repos/octocat/hello-world/contents/README.md", params={"ref": "main"}, headers=PINNED)
