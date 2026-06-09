"""确定性的入库落位建议(domain / page_type / slug + confidence)。

刻意不使用 LLM 主观打分:同一输入在任何机器、任何平台返回完全一致的结果,
这是"跨平台分类一致"的前提。AI 只把它当建议,最终落位由 frontmatter 校验闸拍板。
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from . import routes as routes_mod
from .vocabulary import Vocabulary

# 模块号模式:T0119 / A0533 / S7 等
_MODULE_ID = re.compile(r"\b([TASW]\d{2,4}|S\d{1,2})\b", re.IGNORECASE)
_QUERY_HINT = ("怎么", "如何", "怎样", "为什么", "how ", "查询", "排查")
_ENTITY_HINT = ("客户", "公司", "组织", "customer", "供应商", "人员")


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[A-Za-z0-9_]+|[一-鿿]+", text.lower())


def _slugify(text: str) -> str:
    # 模块号优先
    m = _MODULE_ID.search(text)
    base = ""
    if m:
        base = m.group(1).lower()
    # 取若干英文 token 拼 kebab
    eng = re.findall(r"[a-z0-9]+", text.lower())
    eng = [e for e in eng if len(e) > 1][:3]
    parts = [p for p in ([base] + eng) if p]
    slug = "-".join(dict.fromkeys(parts))  # 去重保序
    return slug or "untitled"


def suggest_path(text: str, vocab: Vocabulary, root: str) -> Dict[str, Any]:
    """根据资料摘要建议落位。"""
    low = text.lower()
    reasons: List[str] = []

    # 1) domain 打分:slug token 命中 + boundary token 命中 + 路由关键词命中
    scores: Dict[str, int] = {d: 0 for d in vocab.domain_slugs}
    for d in vocab.data.get("domains", []):
        slug = d["slug"]
        for tok in _tokenize(slug + " " + d.get("boundary", "")):
            if len(tok) > 1 and tok in low:
                scores[slug] = scores.get(slug, 0) + 1

    # 路由关键词命中 → 该路由必加载路径所属 domain 加权
    rts = routes_mod.parse_routes(root)
    for r in rts:
        for kw in r.keywords:
            if kw.lower() in low:
                for p in r.required:
                    for slug in vocab.domain_slugs:
                        if f"/domains/{slug}/" in p.replace("\\", "/"):
                            scores[slug] = scores.get(slug, 0) + 2
                            reasons.append(f"路由关键词 `{kw}` 指向 {slug}")

    best_domain = ""
    best_score = 0
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    if ranked:
        best_domain, best_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    # 2) confidence:清晰优势 → high;有命中但不强 → medium;无命中或平手 → low
    if best_score >= 3 and best_score > second_score:
        confidence = "high"
    elif best_score >= 1 and best_score > second_score:
        confidence = "medium"
    else:
        confidence = "low"
        reasons.append("无明显 domain 命中或存在平手 → 应入 staging/domain-review/")

    # 3) page_type 启发
    if _MODULE_ID.search(text):
        page_type = "module"
        reasons.append("命中模块号模式 → module")
    elif any(h in low for h in _ENTITY_HINT):
        page_type = "entity"
    elif any(h in low for h in _QUERY_HINT):
        page_type = "query"
    else:
        page_type = "concept"

    slug = _slugify(text)

    # page_type → 目录名(避免 entitys/querys 这种错误复数,对齐 AGENTS.md 目录约定)
    type_dir = {"concept": "concepts", "entity": "entities", "query": "queries",
                "source": "sources", "module": "modules"}.get(page_type, page_type + "s")

    if confidence == "low":
        suggested_path = "wiki/staging/domain-review/" + slug + ".md"
    elif page_type == "module":
        suggested_path = f"wiki/domains/{best_domain}/modules/{slug}/README.md"
    else:
        suggested_path = f"wiki/domains/{best_domain}/{type_dir}/{slug}.md"

    return {
        "domain": best_domain if confidence != "low" else "",
        "page_type": page_type,
        "slug": slug,
        "confidence": confidence,
        "suggested_path": suggested_path,
        "scores": dict(ranked),
        "reasons": reasons,
    }
