"""全文 / 关键词检索(内容 + frontmatter)。"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from . import frontmatter, repo


def _score(text_lower: str, terms: List[str], title_lower: str) -> int:
    score = 0
    for t in terms:
        score += text_lower.count(t)
        if t in title_lower:
            score += 5  # 标题命中加权
    return score


def search(root: str, query: str, limit: int = 10, include_archive: bool = False) -> List[Dict[str, Any]]:
    """检索页面,返回按相关度排序的命中列表。

    每条:{path(相对 root), title, score, snippet, page_type, domain, sensitivity}
    """
    terms = [t.lower() for t in query.split() if t.strip()]
    if not terms:
        return []
    results: List[Dict[str, Any]] = []
    for path in repo.iter_pages(root, include_archive=include_archive):
        try:
            meta, body, _ = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        title = _first_heading(body) or os.path.basename(path)
        full_lower = body.lower()
        score = _score(full_lower, terms, title.lower())
        if score <= 0:
            continue
        results.append({
            "path": repo.rel_path(root, path),
            "title": title,
            "score": score,
            "snippet": _snippet(body, terms),
            "page_type": meta.get("page_type", ""),
            "domain": meta.get("domain", ""),
            "sensitivity": meta.get("sensitivity", ""),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _snippet(body: str, terms: List[str], width: int = 120) -> str:
    low = body.lower()
    pos = -1
    for t in terms:
        p = low.find(t)
        if p != -1:
            pos = p
            break
    if pos == -1:
        return body.strip().replace("\n", " ")[:width]
    start = max(0, pos - width // 2)
    return body[start:start + width].strip().replace("\n", " ")
