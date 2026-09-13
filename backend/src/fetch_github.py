import base64
import re
from pathlib import Path

import httpx

from config import GITHUB_USER_URL


def _extract_username(url: str) -> str:
    match = re.search(r"github\.com/([^/]+)", url)
    if not match:
        raise ValueError(f"URL GitHub invalide : {url}")
    return match.group(1)


def _fetch_repos(username: str) -> list[dict]:
    url = f"https://api.github.com/users/{username}/repos"
    params = {"per_page": 100, "sort": "updated"}
    repos = []
    with httpx.Client(timeout=30) as client:
        while url:
            resp = client.get(url, params=params)
            resp.raise_for_status()
            repos.extend(resp.json())
            url = resp.links.get("next", {}).get("url")
            params = {}
    return repos


def _fetch_readme(username: str, repo: str) -> str | None:
    url = f"https://api.github.com/repos/{username}/{repo}/readme"
    with httpx.Client(timeout=30) as client:
        resp = client.get(url)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        content_b64 = resp.json()["content"]
        return base64.b64decode(content_b64).decode("utf-8")


def fetch_github_readmes(data_dir: str | Path = "data") -> dict:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    username = _extract_username(GITHUB_USER_URL)
    repos = _fetch_repos(username)

    sections = []
    count = 0
    for repo in repos:
        name = repo["name"]
        readme = _fetch_readme(username, name)
        if readme is None:
            continue
        cleaned = re.sub(r"^#{1,6}\s+(.+)$", r"**\1**", readme, flags=re.MULTILINE)
        section = f"## (Projet Github) {name}\n\n{cleaned}"
        sections.append(section)
        count += 1

    markdown = "\n\n---\n\n".join(sections)
    output = data_dir / "github_projects.md"
    output.write_text(markdown, encoding="utf-8")

    return {"status": "ok", "repos_count": count, "file": str(output)}


if __name__ == "__main__":
    result = fetch_github_readmes()
    print(f"{result['repos_count']} repos récupérés → {result['file']}")
