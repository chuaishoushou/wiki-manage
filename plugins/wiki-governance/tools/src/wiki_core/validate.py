"""单页 frontmatter 校验(对照受控词表的闭集与必填集)。"""
from __future__ import annotations

from typing import Any, Dict, List

from .vocabulary import Vocabulary


def issue(level: str, code: str, msg: str, path: str = "") -> Dict[str, str]:
    return {"level": level, "code": code, "msg": msg, "path": path}


def validate_page(meta: Dict[str, Any], has_fm: bool, rel: str, vocab: Vocabulary) -> List[Dict[str, str]]:
    """校验一页的 frontmatter,返回 issue 列表(error/warn)。"""
    issues: List[Dict[str, str]] = []

    if not has_fm:
        issues.append(issue("error", "no-frontmatter", "缺少 YAML frontmatter", rel))
        return issues

    # 必填字段
    for field in vocab.required_fields:
        if field not in meta or meta.get(field) in ("", [], None):
            issues.append(issue("error", "missing-field", f"缺少必填字段 `{field}`", rel))

    # 条件必填:domain_reason
    dc = meta.get("domain_confidence")
    if dc in ("low", "medium") and not meta.get("domain_reason"):
        issues.append(issue("error", "missing-conditional", "domain_confidence 为 low/medium 时必须填 domain_reason", rel))

    # 枚举闭集
    for field, allowed in vocab.enum_fields.items():
        if field in meta and meta.get(field) not in ("", [], None):
            val = meta.get(field)
            if isinstance(val, list):
                # 枚举字段写成列表本身就是错(如 status: [active, ...])
                issues.append(issue("error", "enum-is-list", f"枚举字段 `{field}` 不应是列表: {val}", rel))
                continue
            if val not in allowed:
                issues.append(issue("error", "bad-enum", f"字段 `{field}` 取值 `{val}` 不在闭集 {allowed}", rel))

    # page_type 必须存在且合法(单列强调,因为它是 v2 新增的机器分类锚)
    pt = meta.get("page_type")
    if pt and pt not in vocab.page_types:
        issues.append(issue("error", "bad-page-type", f"page_type `{pt}` 不在 {vocab.page_types}", rel))

    # domain 必须是已登记 domain
    dom = meta.get("domain")
    if dom and vocab.domain_slugs and dom not in vocab.domain_slugs:
        issues.append(issue("error", "unknown-domain", f"domain `{dom}` 未在 _vocabulary.md 登记", rel))

    # tags 校验:白名单 + 同义归并 + 禁止用 tag 表达状态
    tags = meta.get("tags")
    if tags not in (None, "", []) and not isinstance(tags, list):
        issues.append(issue("error", "tags-not-list", f"tags 必须是列表,实为 `{tags}`", rel))
    if isinstance(tags, list):
        whitelist = set(vocab.tag_whitelist)
        synonyms = vocab.tag_synonyms
        forbidden = set(vocab.status_in_tags_forbidden)
        for t in tags:
            if t in forbidden:
                issues.append(issue("error", "status-in-tags", f"tag `{t}` 是状态词,禁止用 tag 表达状态(用 status 字段)", rel))
            elif t in synonyms:
                issues.append(issue("warn", "tag-synonym", f"tag `{t}` 应归并为 `{synonyms[t]}`", rel))
            elif whitelist and t not in whitelist:
                issues.append(issue("warn", "tag-not-whitelisted", f"tag `{t}` 不在白名单(需 owner 批准入表)", rel))

    return issues
