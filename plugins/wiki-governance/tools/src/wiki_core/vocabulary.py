"""加载 _vocabulary.md 的权威 JSON 块,提供受控词表访问。

_vocabulary.md 是机器可读规则源:合法 domain / page_type 闭集 / tag 白名单 /
敏感度规则 / frontmatter 必填集 / global 晋升判定。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from . import frontmatter

# 找不到 _vocabulary.md 时的最小兜底(保证工具不崩,但会在 lint 报缺失)
_FALLBACK: Dict[str, Any] = {
    "protocol_version": 0,
    "domains": [],
    "page_types": ["source", "entity", "concept", "query", "module"],
    "sensitivity_levels": ["public", "team", "maintainer-only", "exclude"],
    "required_frontmatter": ["tags", "page_type", "domain", "shared_scope", "sensitivity", "status", "date_created"],
    "required_frontmatter_conditional": {},
    "enum_fields": {},
    "tag_whitelist": [],
    "tag_synonyms": {},
    "status_in_tags_forbidden": [],
    "global_promotion": {"min_domains": 2},
    "sensitivity_rules": {"default_on_hit": "maintainer-only", "customer_names": [], "secret_keywords": [], "attack_surface_keywords": []},
    "publish": {"max_sensitivity": "team"},
}


class Vocabulary:
    """受控词表的薄封装。"""

    def __init__(self, data: Dict[str, Any], path: Optional[str] = None, parse_error: str = ""):
        self.data = data
        self.path = path
        self.parse_error = parse_error  # 非空 = _vocabulary.md 的 JSON 块解析失败(已回退兜底)

    @property
    def protocol_version(self) -> int:
        return int(self.data.get("protocol_version", 0))

    @property
    def domain_slugs(self) -> List[str]:
        return [d["slug"] for d in self.data.get("domains", [])]

    def domain(self, slug: str) -> Optional[Dict[str, Any]]:
        for d in self.data.get("domains", []):
            if d.get("slug") == slug:
                return d
        return None

    def owners(self, slug: str) -> List[str]:
        d = self.domain(slug)
        return list(d.get("owners", [])) if d else []

    @property
    def page_types(self) -> List[str]:
        return self.data.get("page_types", [])

    @property
    def required_fields(self) -> List[str]:
        return self.data.get("required_frontmatter", [])

    @property
    def conditional_fields(self) -> Dict[str, str]:
        return self.data.get("required_frontmatter_conditional", {})

    @property
    def enum_fields(self) -> Dict[str, List[str]]:
        return self.data.get("enum_fields", {})

    @property
    def tag_whitelist(self) -> List[str]:
        return self.data.get("tag_whitelist", [])

    @property
    def tag_synonyms(self) -> Dict[str, str]:
        return self.data.get("tag_synonyms", {})

    @property
    def status_in_tags_forbidden(self) -> List[str]:
        return self.data.get("status_in_tags_forbidden", [])

    @property
    def sensitivity_rules(self) -> Dict[str, Any]:
        return self.data.get("sensitivity_rules", {})

    @property
    def publish_max(self) -> str:
        return self.data.get("publish", {}).get("max_sensitivity", "team")

    @property
    def min_domains_for_global(self) -> int:
        return int(self.data.get("global_promotion", {}).get("min_domains", 2))


def load(root: str) -> Vocabulary:
    """从 wiki 根加载 _vocabulary.md。缺失或解析失败时返回兜底词表。"""
    path = os.path.join(root, "_vocabulary.md")
    if not os.path.isfile(path):
        return Vocabulary(dict(_FALLBACK), None)
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    block = frontmatter.extract_json_block(text)
    if not block:
        return Vocabulary(dict(_FALLBACK), path, parse_error="未找到 json 围栏块")
    try:
        data = json.loads(block)
    except json.JSONDecodeError as e:
        # 不再静默:记录解析错误,供 protocol/lint 显式报出
        return Vocabulary(dict(_FALLBACK), path, parse_error=f"JSON 解析失败: {e}")
    # 用兜底补齐缺失键,避免下游 KeyError
    merged = dict(_FALLBACK)
    merged.update(data)
    return Vocabulary(merged, path)
