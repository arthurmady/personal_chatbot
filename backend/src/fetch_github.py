import base64
import json
import re
import unicodedata
from pathlib import Path

import httpx

from config import GITHUB_USER_URL


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    return text or "section"


def _make_detail_id(heading: str, used: set[str]) -> str:
    base = _slugify(heading)
    slug, n = base, 2
    while slug in used:
        slug = f"{base}_{n}"
        n += 1
    used.add(slug)
    return slug


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


def _parse_readme(readme: str) -> tuple[str, list[dict]]:
    lines = readme.strip().split("\n")

    pre_heading_lines = []
    details = []
    current_heading = None
    current_id = None
    current_content = []
    used_ids: set[str] = set()

    for line in lines:
        heading_match = re.match(r"^#{1,6}\s+(.+)$", line)
        if heading_match:
            if current_heading is not None:
                content = "\n".join(current_content).strip()
                if content:
                    details.append({
                        "id": current_id,
                        "content": content
                    })
            current_heading = heading_match.group(1).strip()
            current_id = _make_detail_id(current_heading, used_ids)
            current_content = []
        else:
            if current_heading is None:
                stripped = line.strip()
                if stripped:
                    pre_heading_lines.append(stripped)
            else:
                current_content.append(line)

    if current_heading is not None:
        content = "\n".join(current_content).strip()
        if content:
            details.append({
                "id": current_id,
                "content": content
            })

    if details:
        essential = details[0]["content"]
        details = details[1:]
    else:
        essential = " ".join(pre_heading_lines) if pre_heading_lines else None

    return essential, details


def fetch_github_readmes(data_dir: str | Path = "data") -> dict:
    data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    username = _extract_username(GITHUB_USER_URL)
    repos = _fetch_repos(username)

    facts = []
    for repo in repos:
        name = repo["name"]
        readme = _fetch_readme(username, name)
        if readme is None:
            continue

        essential, details = _parse_readme(readme)
        if not essential:
            essential = name
        # le suivi des détails donnés est global : l'id doit être unique d'un dépôt à l'autre
        prefix = _slugify(name)
        for detail in details:
            detail["id"] = f"{prefix}_{detail['id']}"

        fact = {
            "id": name,
            "tags": ["Projets"],
            "essential": essential,
            "details": details
        }
        facts.append(fact)

    output = data_dir / "github_projects.json"
    output.write_text(json.dumps({"facts": facts}, indent=2, ensure_ascii=False), encoding="utf-8")

    return {"status": "ok", "repos_count": len(facts), "file": str(output)}


if __name__ == "__main__":
    result = fetch_github_readmes()
    print(f"{result['repos_count']} repos récupérés → {result['file']}")
