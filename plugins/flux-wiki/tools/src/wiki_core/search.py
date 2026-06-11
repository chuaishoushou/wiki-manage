"""全文 / 关键词检索(正文 + frontmatter;库根协议文件默认不参与)。"""
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


def _meta_text(meta: Dict[str, Any]) -> str:
    """frontmatter 值拼成可检索文本(summary/tags 里的词经常不在正文出现)。"""
    parts: List[str] = []
    for v in meta.values():
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
        elif v:
            parts.append(str(v))
    return " ".join(parts)


def search(root: str, query: str, limit: int = 10, include_archive: bool = False) -> List[Dict[str, Any]]:
    """检索页面,返回按相关度排序的命中列表。

    每条:{path(相对 root), title, score, snippet, page_type, domain, sensitivity}
    库根层的协议/台账文件(AGENTS/_routes/log 等)不参与——log.md 天然累积各种
    关键词,会与真正的知识页抢排名。
    """
    terms = [t.lower() for t in query.split() if t.strip()]
    if not terms:
        return []
    results: List[Dict[str, Any]] = []
    for path in repo.iter_pages(root, include_archive=include_archive):
        if repo.is_root_infra(root, path):
            continue
        try:
            meta, body, _ = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        title = _first_heading(body) or os.path.basename(path)
        meta_text = _meta_text(meta)
        full_lower = (body + "\n" + meta_text).lower()
        score = _score(full_lower, terms, title.lower())
        if score <= 0:
            continue
        results.append({
            "path": repo.rel_path(root, path),
            "title": title,
            "score": score,
            "snippet": _snippet(body, terms, fallback=meta_text),
            "page_type": meta.get("page_type", ""),
            "domain": meta.get("domain", ""),
            "sensitivity": meta.get("sensitivity", ""),
        })
    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:limit]


def has_knowledge_pages(root: str) -> bool:
    """库里是否存在知识页(排除库根协议文件——它们随 init 自带,不代表用户写过内容)。"""
    for p in repo.iter_pages(root):
        if not repo.is_root_infra(root, p):
            return True
    return False


def _first_heading(body: str) -> str:
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _snippet(body: str, terms: List[str], width: int = 120, fallback: str = "") -> str:
    low = body.lower()
    pos = -1
    for t in terms:
        p = low.find(t)
        if p != -1:
            pos = p
            break
    if pos == -1:
        # 正文没命中(命中在 frontmatter):截 frontmatter 文本,否则正文开头
        src = fallback if any(t in fallback.lower() for t in terms) else body
        return src.strip().replace("\n", " ")[:width]
    start = max(0, pos - width // 2)
    return body[start:start + width].strip().replace("\n", " ")
