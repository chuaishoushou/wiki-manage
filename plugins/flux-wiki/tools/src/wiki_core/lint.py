"""体检:确定性检查 → 结构化报告(同一库任何机器同结果)。

v3 体检哲学:**lint 是服务,不是管教**。
- error 只留"会让 AI 操作失败"的硬伤:_routes.md 指向不存在的文件。
- 其余(死链/重名/路由歧义/溯源残缺/旧布局)一律 warn。
- 用户自建目录、自由组织、无 frontmatter 的页:**不报任何问题**。
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List
from urllib.parse import unquote

from . import frontmatter, repo, routes as routes_mod

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
# Obsidian 风格 [[target]] / [[target|别名]](排除 ![[嵌入]] 也按链接处理无妨)
_WIKI_LINK = re.compile(r"\[\[([^\]\[|#]+)(?:#[^\]\[|]*)?(?:\|[^\]\[]*)?\]\]")


def issue(level: str, code: str, msg: str, path: str = "") -> Dict[str, str]:
    return {"level": level, "code": code, "msg": msg, "path": path}


def _check_routes(root: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    routes = routes_mod.parse_routes(root)
    for lineno, p in routes_mod.missing_targets(root, routes):
        issues.append(issue("error", "route-missing",
                            f"_routes.md 第 {lineno} 行指向不存在文件 `{p}`", "_routes.md"))
    for lineno, p in routes_mod.missing_optional(root, routes):
        issues.append(issue("warn", "route-optional-missing",
                            f"_routes.md 第 {lineno} 行可选加载解析不到 `{p}`"
                            "(基准:必加载页所在目录,或库根)", "_routes.md"))
    for kw, linenos in routes_mod.find_ambiguous(routes).items():
        issues.append(issue("warn", "route-ambiguous",
                            f"关键词 `{kw}` 在多行命中: {linenos}", "_routes.md"))
    return issues


def _md_link_dead(path: str, target: str) -> bool:
    """[text](target) 形式的目标是否解析不到(URL 编码如 %20 先解码再找文件)。"""
    t = unquote(target.strip())
    if t.startswith(("http://", "https://", "#", "mailto:")):
        return False
    t = t.split("#")[0]
    if not t or not t.endswith(".md"):
        return False
    return not os.path.isfile(os.path.normpath(os.path.join(os.path.dirname(path), t)))


def _basename_index(root: str) -> Dict[str, int]:
    """全库 basename(不含 .md)→ 出现次数,用于 [[wikilink]] 的全库唯一名解析。"""
    idx: Dict[str, int] = {}
    for p in repo.iter_pages(root, include_archive=True):
        name = os.path.basename(p)[:-3]
        idx[name] = idx.get(name, 0) + 1
    return idx


def _wikilink_dead(root: str, path: str, target: str, names: Dict[str, int]) -> bool:
    """[[target]] 按 Obsidian 语义解析:相对当前页 → 相对库根/内容根 → 全库唯一 basename。"""
    t = target.strip()
    if not t:
        return False
    cand = t if t.endswith(".md") else t + ".md"
    for base in (os.path.dirname(path), root, repo.content_dir(root)):
        if os.path.isfile(os.path.normpath(os.path.join(base, cand))):
            return False
    return names.get(os.path.basename(cand)[:-3], 0) == 0


def _check_dead_links(root: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    names = _basename_index(root)
    for path in repo.iter_pages(root):
        try:
            _, body, _ = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        rel = repo.rel_path(root, path)
        for target in _MD_LINK.findall(body):
            if _md_link_dead(path, target):
                issues.append(issue("warn", "dead-link", f"死链 → `{target}`", rel))
        for target in _WIKI_LINK.findall(body):
            if _wikilink_dead(root, path, target, names):
                issues.append(issue("warn", "dead-wikilink", f"死链 → `[[{target}]]`", rel))
    return issues


def _check_duplicates(root: str) -> List[Dict[str, str]]:
    """同名页出现在多个主题下(可能是重复沉淀)。README/overview 天然重名,跳过;
    modules/ 目录是命名空间(协议规定每个模块放同名骨架页 task-history/code-map 等),
    其内的页不参与重名检查——否则每个模块库都固定产出一串不可操作的警告。"""
    seen: Dict[str, List[str]] = {}
    for path in repo.iter_pages(root):
        base = os.path.basename(path)
        if base in ("README.md", "overview.md"):
            continue
        rel = repo.rel_path(root, path)
        if "modules" in rel.replace("\\", "/").split("/"):
            continue
        seen.setdefault(base, []).append(rel)
    issues = []
    for base, paths in seen.items():
        if len(paths) > 1:
            issues.append(issue("warn", "possible-dup",
                                f"同名页 `{base}` 出现 {len(paths)} 处: {paths}", ""))
    return issues


def _check_provenance(root: str) -> List[Dict[str, str]]:
    """从团队仓学来的页(有 learned_from)应带 learned_commit,否则增量更新对不上。"""
    issues: List[Dict[str, str]] = []
    for path in repo.iter_pages(root):
        try:
            meta, _, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        if has_fm and meta.get("learned_from") and not meta.get("learned_commit"):
            issues.append(issue("warn", "provenance-incomplete",
                                "有 learned_from 但缺 learned_commit(团队增量更新将无法对账)",
                                repo.rel_path(root, path)))
    return issues


def _check_layout(root: str) -> List[Dict[str, str]]:
    if repo.is_legacy_layout(root):
        # 用户已明确拍板保留 v2 时放置确认标记,避免每次体检的永久噪音
        if os.path.isfile(os.path.join(root, ".wiki", "ack-legacy-layout")):
            return []
        return [issue("warn", "legacy-layout",
                      "v2 嵌套布局(根下有 wiki/ 内容层)。可继续用;"
                      "建议迁到 v3 扁平结构(见 wiki-manage README「v2 → v3 迁移」);"
                      "确定保留 v2 可建空文件 .wiki/ack-legacy-layout 静默本提示", "wiki/")]
    return []


def lint(root: str) -> Dict[str, Any]:
    """跑全套体检,返回结构化报告。"""
    sections: List[Dict[str, Any]] = [
        {"name": "routes", "issues": _check_routes(root)},
        {"name": "dead-links", "issues": _check_dead_links(root)},
        {"name": "duplicates", "issues": _check_duplicates(root)},
        {"name": "provenance", "issues": _check_provenance(root)},
        {"name": "layout", "issues": _check_layout(root)},
    ]
    page_count = sum(1 for _ in repo.iter_pages(root))
    all_issues = [i for s in sections for i in s["issues"]]
    errors = sum(1 for i in all_issues if i["level"] == "error")
    warns = sum(1 for i in all_issues if i["level"] == "warn")
    return {
        "root": root,
        "page_count": page_count,
        "summary": {"errors": errors, "warns": warns, "total": len(all_issues)},
        "sections": sections,
    }


def lint_files(root: str, files: List[str]) -> Dict[str, Any]:
    """只检查指定文件(供 --staged / 指定路径):死链 + 溯源完整性。"""
    issues: List[Dict[str, str]] = []
    for path in files:
        if not path.endswith(".md") or not os.path.isfile(path):
            continue
        rel = repo.rel_path(root, path)
        try:
            meta, body, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError) as e:
            issues.append(issue("warn", "unreadable", f"无法读取: {e}", rel))
            continue
        if has_fm and meta.get("learned_from") and not meta.get("learned_commit"):
            issues.append(issue("warn", "provenance-incomplete",
                                "有 learned_from 但缺 learned_commit", rel))
        for target in _MD_LINK.findall(body):
            if _md_link_dead(path, target):
                issues.append(issue("warn", "dead-link", f"死链 → `{target}`", rel))
    errors = sum(1 for i in issues if i["level"] == "error")
    warns = sum(1 for i in issues if i["level"] == "warn")
    return {"root": root, "summary": {"errors": errors, "warns": warns, "total": len(issues)},
            "sections": [{"name": "files", "issues": issues}]}
