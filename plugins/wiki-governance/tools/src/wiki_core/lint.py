"""体检编排:把各项确定性检查汇总成结构化报告。

对应 AGENTS.md § Lint 的 11 步 + v2 新增的 sensitivity / protocol_version / page_type 检查。
全部确定性:同一仓库任何机器跑出同一报告。修复仍需 owner 确认(本工具只读)。
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List

from . import frontmatter, repo, routes as routes_mod, sensitivity, validate
from . import SUPPORTED_PROTOCOL_VERSION
from .vocabulary import Vocabulary, load as load_vocab

_MD_LINK = re.compile(r"\[[^\]]*\]\(([^)]+)\)")


def _check_dead_links(root: str) -> List[Dict[str, str]]:
    issues: List[Dict[str, str]] = []
    for path in repo.iter_pages(root):
        try:
            _, body, _ = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        rel = repo.rel_path(root, path)
        for target in _MD_LINK.findall(body):
            t = target.strip()
            if t.startswith(("http://", "https://", "#", "mailto:")):
                continue
            t = t.split("#")[0]
            if not t or not t.endswith(".md"):
                continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), t))
            if not os.path.isfile(resolved):
                issues.append(validate.issue("warn", "dead-link", f"死链 → `{target}`", rel))
    return issues


def _check_orphans(root: str, routes: List[routes_mod.Route]) -> List[Dict[str, str]]:
    """module README / concept 未被任何路由覆盖 → 检索不可达。

    overview.md 经顶层 overview 的导航链接(wikilink)可达,不按路由判孤儿。
    """
    covered = routes_mod.covered_paths(root, routes)
    issues: List[Dict[str, str]] = []
    for path in repo.iter_pages(root):
        base = os.path.basename(path)
        is_key = base == "README.md" or "/concepts/" in path.replace("\\", "/")
        if not is_key:
            continue
        if os.path.abspath(path) not in covered:
            issues.append(validate.issue("warn", "orphan", "关键页未被 _routes.md 覆盖(检索不可达)", repo.rel_path(root, path)))
    return issues


def _check_duplicates(root: str) -> List[Dict[str, str]]:
    """轻量跨域重复:同名 concept/entity/query 页出现在多个 domain。

    跳过 module 内标准文件(每个模块本就各有一份 product-spec.md/code-map.md 等,
    天然重名,不算重复)以及 README/overview。
    """
    seen: Dict[str, List[str]] = {}
    for path in repo.iter_pages(root):
        base = os.path.basename(path)
        norm = path.replace("\\", "/")
        if base in ("README.md", "overview.md") or "/modules/" in norm:
            continue
        seen.setdefault(base, []).append(repo.rel_path(root, path))
    issues = []
    for base, paths in seen.items():
        if len(paths) > 1:
            issues.append(validate.issue("warn", "possible-dup", f"同名页 `{base}` 出现 {len(paths)} 处: {paths}", ""))
    return issues


def _has_any_file(d: str) -> bool:
    """目录子树里是否存在任何文件(用于检测空目录)。"""
    for _, _, files in os.walk(d):
        if files:
            return True
    return False


def _check_structure(root: str) -> List[Dict[str, str]]:
    """目录结构卫生检查:游离/放错层级的内容目录、空目录(无任何文件的死目录)。

    这是文件级 lint 的补盲:它不依赖 .md 文件存在,专门抓"空壳目录"和"放错层级"。
    """
    issues: List[Dict[str, str]] = []
    content = repo.content_dir(root)
    nested = os.path.abspath(content) != os.path.abspath(root)

    # A. 内容类目录出现在【仓库根】,但内容其实在 wiki/ 之下 → 放错层级/迁移残留
    if nested:
        for name in ("domains", "global", "staging", "templates"):
            stray = os.path.join(root, name)
            if os.path.isdir(stray):
                kind = "空壳" if not _has_any_file(stray) else "含文件但放错层级"
                issues.append(validate.issue(
                    "error", "stray-content-dir",
                    f"`{name}/` 位于仓库根({kind}),内容应在 `wiki/{name}/` 之下 —— 疑似迁移残留",
                    name + "/"))

    # B. domains 下的【异常】空目录(无任何文件的死壳)。
    #    合法的空标准类型目录(空的 queries/concepts/... 占位)不报 —— 一个 domain 暂时没某类内容很正常。
    standard_type_dirs = {"sources", "entities", "concepts", "queries", "modules"}
    for dirpath, dirnames, _ in os.walk(content):
        dirnames[:] = [d for d in dirnames if d not in repo.EXCLUDE_DIRS]
        rel = os.path.relpath(dirpath, root)
        parts = rel.split(os.sep)
        if "archive" in parts or "templates" in parts:
            continue
        if os.path.basename(dirpath) in standard_type_dirs:
            continue  # 空的标准类型目录是合法占位
        if "domains" in parts and os.path.abspath(dirpath) != os.path.abspath(content):
            if not _has_any_file(dirpath):
                issues.append(validate.issue(
                    "warn", "empty-dir", f"异常空目录(无任何页,非标准类型): {rel}/ —— 该删或补内容", rel + "/"))
    return issues


def lint(root: str, vocab: Vocabulary = None) -> Dict[str, Any]:
    """跑全套体检,返回结构化报告。"""
    if vocab is None:
        vocab = load_vocab(root)

    sections: List[Dict[str, Any]] = []

    def add(name: str, issues: List[Dict[str, str]]):
        sections.append({"name": name, "issues": issues})

    # 1. 逐页 frontmatter 校验
    fm_issues: List[Dict[str, str]] = []
    page_count = 0
    for path in repo.iter_pages(root):
        page_count += 1
        try:
            meta, _, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        fm_issues.extend(validate.validate_page(meta, has_fm, repo.rel_path(root, path), vocab))
    add("frontmatter", fm_issues)

    # 2. 路由
    routes = routes_mod.parse_routes(root)
    route_issues: List[Dict[str, str]] = []
    for lineno, p in routes_mod.missing_targets(root, routes):
        route_issues.append(validate.issue("error", "route-missing", f"_routes.md 第 {lineno} 行指向不存在文件 `{p}`", "_routes.md"))
    for kw, linenos in routes_mod.find_ambiguous(routes).items():
        route_issues.append(validate.issue("error", "route-ambiguous", f"关键词 `{kw}` 在多行命中: {linenos}", "_routes.md"))
    add("routes", route_issues)

    # 3. 孤儿页
    add("orphans", _check_orphans(root, routes))

    # 4. 死链
    add("dead-links", _check_dead_links(root))

    # 5. 跨域重复(轻量)
    add("duplicates", _check_duplicates(root))

    # 5b. 目录结构卫生(补盲:空壳目录 / 放错层级的游离内容目录)
    add("structure", _check_structure(root))

    # 6. sensitivity(命中敏感但声明不足)
    scan = sensitivity.scan_repo(root, vocab)
    sens_issues = []
    for f in scan["findings"]:
        if f["any_hit"] and (f["under_declared"] or not f["declared"]):
            kinds = [k for k, v in f["hits"].items() if v]
            sens_issues.append(validate.issue(
                "error", "sensitivity-underdeclared",
                f"命中敏感({','.join(kinds)}),声明 `{f['declared'] or '无'}` < 建议 `{f['suggested']}`",
                f["path"]))
    add("sensitivity", sens_issues)

    # 7. protocol_version(工具是否落后于仓库协议)
    proto_issues = []
    if vocab.protocol_version > SUPPORTED_PROTOCOL_VERSION:
        proto_issues.append(validate.issue(
            "error", "protocol-mismatch",
            f"仓库 protocol_version={vocab.protocol_version} > 工具支持 {SUPPORTED_PROTOCOL_VERSION},请升级工具", "_vocabulary.md"))
    if vocab.path is None:
        proto_issues.append(validate.issue("error", "no-vocabulary", "缺少 _vocabulary.md(受控词表),分类闭集无法校验", ""))
    if vocab.parse_error:
        proto_issues.append(validate.issue(
            "error", "vocabulary-parse-error",
            f"_vocabulary.md 解析失败({vocab.parse_error}),已回退兜底,分类闭集失效", "_vocabulary.md"))
    add("protocol", proto_issues)

    # 汇总
    all_issues = [i for s in sections for i in s["issues"]]
    errors = sum(1 for i in all_issues if i["level"] == "error")
    warns = sum(1 for i in all_issues if i["level"] == "warn")
    return {
        "root": root,
        "page_count": page_count,
        "summary": {"errors": errors, "warns": warns, "total": len(all_issues)},
        "sections": sections,
    }


def lint_files(root: str, files: List[str], vocab: Vocabulary = None) -> Dict[str, Any]:
    """只校验指定文件的 frontmatter(供 pre-commit --staged 用)。"""
    if vocab is None:
        vocab = load_vocab(root)
    issues: List[Dict[str, str]] = []
    for path in files:
        if not path.endswith(".md") or not os.path.isfile(path):
            continue
        try:
            meta, _, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        rel = repo.rel_path(root, path)
        issues.extend(validate.validate_page(meta, has_fm, rel, vocab))
        # 敏感度逐文件也查
        f = sensitivity.scan_page(path, vocab, root)
        if f["any_hit"] and (f["under_declared"] or not f["declared"]):
            kinds = [k for k, v in f["hits"].items() if v]
            issues.append(validate.issue("error", "sensitivity-underdeclared",
                                         f"命中敏感({','.join(kinds)}),声明不足", rel))
    errors = sum(1 for i in issues if i["level"] == "error")
    warns = sum(1 for i in issues if i["level"] == "warn")
    return {"root": root, "summary": {"errors": errors, "warns": warns, "total": len(issues)},
            "sections": [{"name": "staged", "issues": issues}]}
