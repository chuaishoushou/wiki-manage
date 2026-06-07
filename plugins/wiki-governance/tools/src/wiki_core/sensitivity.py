"""敏感度扫描:secret / 客户真名 / 攻击面关键词。

用于 v0 安全基线:git init 前全库扫描,给每页建议 sensitivity,
并标出"声明的 sensitivity 与扫描建议不符"的页。
扫描规则来自 _vocabulary.md 的 sensitivity_rules(团队可调,单一真源)。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List

from . import frontmatter, repo
from .vocabulary import Vocabulary

# 敏感度等级排序(越大越敏感),用于比较"声明 vs 建议"
_RANK = {"public": 0, "team": 1, "maintainer-only": 2, "exclude": 3}


def scan_text(text: str, vocab: Vocabulary) -> Dict[str, Any]:
    """扫描一段文本,返回命中详情与建议等级。"""
    rules = vocab.sensitivity_rules
    low = text.lower()
    hits: Dict[str, List[str]] = {"customer_names": [], "secret_keywords": [], "attack_surface": []}

    for name in rules.get("customer_names", []):
        if name.lower() in low:
            hits["customer_names"].append(name)
    for kw in rules.get("secret_keywords", []):
        if kw.lower() in low:
            hits["secret_keywords"].append(kw)
    for kw in rules.get("attack_surface_keywords", []):
        if kw.lower() in low:
            hits["attack_surface"].append(kw)

    any_hit = any(hits.values())
    suggested = rules.get("default_on_hit", "maintainer-only") if any_hit else "public"
    return {"hits": hits, "any_hit": any_hit, "suggested": suggested}


def scan_page(path: str, vocab: Vocabulary, root: str) -> Dict[str, Any]:
    # 扫【整页原文 + 路径】而非解析后的 body —— frontmatter 字段里的 secret/客户名
    # (如 title/tags/customer/clientSecret)必须一并命中,否则会被判 public 漏过。
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    meta, _, _ = frontmatter.parse(raw)
    rel = repo.rel_path(root, path)
    # _vocabulary.md 本身就是检测规则表(列举客户名/secret 关键词作为 pattern),
    # 不能把"规则定义"误判为"数据泄露"。它的真实敏感度由其 frontmatter sensitivity 声明决定。
    if os.path.basename(path) == "_vocabulary.md":
        res = {"hits": {"customer_names": [], "secret_keywords": [], "attack_surface": []},
               "any_hit": False, "suggested": "public"}
    else:
        res = scan_text(raw + "\n" + path, vocab)
    declared = meta.get("sensitivity", "")
    domain = meta.get("domain", "")
    dom = vocab.domain(domain) if domain else None
    publish_false = bool(dom and dom.get("publish") is False)

    # 是否"声明不足":建议比声明更敏感,或根本没声明
    declared_rank = _RANK.get(declared, -1)
    suggested_rank = _RANK.get(res["suggested"], 0)
    under_declared = declared_rank < suggested_rank

    return {
        "path": rel,
        "domain": domain,
        "declared": declared,
        "suggested": res["suggested"],
        "hits": res["hits"],
        "any_hit": res["any_hit"],
        "under_declared": under_declared,
        "publish_false_domain": publish_false,
    }


def scan_repo(root: str, vocab: Vocabulary, include_archive: bool = False) -> Dict[str, Any]:
    """全库扫描,汇总安全审计。"""
    findings: List[Dict[str, Any]] = []
    for path in repo.iter_pages(root, include_archive=include_archive):
        try:
            f = scan_page(path, vocab, root)
        except (OSError, UnicodeDecodeError):
            continue
        # 只收录有命中、或声明不足、或属 publish:false 域的页
        if f["any_hit"] or f["under_declared"] or f["publish_false_domain"] or not f["declared"]:
            findings.append(f)

    # 风险页 = 有命中且(声明不足 或 无声明)
    risky = [f for f in findings if f["any_hit"] and (f["under_declared"] or not f["declared"])]
    return {
        "total_findings": len(findings),
        "risky_count": len(risky),
        "findings": findings,
    }
