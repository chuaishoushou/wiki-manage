"""scaffold:一条命令建出一个轻量个人知识库(v3 扁平结构),幂等可修复。

v3 结构(domains/ 直接在库根下,不再嵌套 wiki/ 层):
    AGENTS.md      协议(精简个人版)
    overview.md    顶层地图
    log.md         操作台账(追加)
    _routes.md     关键词路由(可选用)
    domains/       知识主体,按主题分目录,目录可自由扩展
    inbox/         待整理(归属不明先放这里)
    raw/           原始资料原件(只读)
    archive/       归档区(删除 = mv 到这里)
    .wiki/         工具产物(lint 报告 / learn 水位),不算知识

含写副作用 → 是独立写子命令;只读检查走 check=True。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from . import SUPPORTED_PROTOCOL_VERSION, repo


def _agents_md(date: str) -> str:
    return f"""---
protocol_version: {SUPPORTED_PROTOCOL_VERSION}
date_created: {date}
---

# 知识库协议(个人库)

> AI 操作本库前先读本文。本库以实用为先:目录可自由扩展,约定尽量少。

## 结构

| 位置 | 用途 |
|---|---|
| `domains/<主题>/` | 知识主体。按主题分目录,新主题**直接建目录**即可;主题内可自由组织(推荐 concepts/ queries/ sources/ modules/ 子目录,不强制) |
| `inbox/` | 待整理:归属不明的先放这里,定期清 |
| `raw/` | 原始资料原件,只读(AI 绝不修改) |
| `archive/` | 归档区:删除 = `mv` 到 `archive/<YYYY-MM-DD>/`,**绝不 `rm`** |
| `.wiki/` | 工具产物(lint 报告、团队学习水位),不算知识内容 |
| `overview.md` | 顶层地图(只放导航) |
| `log.md` | 操作台账(每次写入追加一行) |
| `_routes.md` | 关键词 → 文件 路由表(可选;重要页登记后 AI 检索更准) |

## 页面约定

- 文件名小写 kebab-case。
- frontmatter **推荐**(非强制):`tags / status / date_created`。
- 从团队仓学来的页**必须**带溯源字段:`learned_from`(团队仓内相对路径)与 `learned_commit`(学习时的 commit)。

## 操作

- **查询**:直接 Grep/Read 库内 .md,或 `wiki-cli search "<词>"`。
- **入库**:定主题 → 写入 `domains/<主题>/`(或 `wiki-cli new` 生成骨架)→ `log.md` 追加一行;拿不准放 `inbox/`。
- **学习团队知识**:`/wiki-learn` —— 读团队仓 git 增量 → 逐页分类写入 `domains/` → 记录水位(`wiki-cli learn --mark`)。
- **体检**:`wiki-cli lint`(只读报告;修复需用户确认)。
- **删除**:mv 到 `archive/<YYYY-MM-DD>/`,在 `log.md` 记一行。
"""


def _overview_md(domains: List[str], date: str) -> str:
    items = ("\n".join(f"- [{d}](domains/{d}/) — （一句话描述）" for d in domains)
             or "- （还没有主题。建第一个 `domains/<主题>/` 后,把本行替换成:`- [主题](domains/主题/) — 一句话描述`）")
    return f"""---
date_created: {date}
---

# 知识库总览

> 顶层导航地图,只放导航不堆知识。新主题目录建好后在这里加一行。

## 主题(domains)
{items}

## 入口
协议:`AGENTS.md` · 路由:`_routes.md` · 台账:`log.md`
"""


def _routes_md(date: str) -> str:
    return f"""---
date_created: {date}
---

# 关键词路由表(可选)

> 关键词 → 文件路径。重要页在此登记后,AI 命中关键词可精确加载。不登记也能全文检索到。

| 触发关键词(`\\|` 分隔) | 加载文件(相对库根) |
|---|---|
"""


def _safe_name(value: str, what: str) -> str:
    """slug/domain 必须是单层目录/文件名:含路径分隔符或 .. 一律拒绝。

    没有这道闸,`new concept ../../x --domain y` 会静默逃出 domains/ 落到库根
    (resolve_in_root 只防越出库,不防库内乱窜)。
    """
    v = (value or "").strip()
    if not v or v in (".", "..") or "/" in v or "\\" in v or v.startswith("."):
        raise ValueError(f"{what} 必须是单层名称(kebab-case),不能含路径分隔符或以点开头: {value!r}")
    return v


def new_page(root: str, page_type: str, slug: str, domain: str,
             title: str = "", date: str = "") -> tuple:
    """生成一页骨架的【相对内容根的路径 + 内容】(不写盘,由调用方写)。

    page_type 不设闭集:concept/query/source/module 等常见类型映射到约定子目录,
    其他类型按 `<type>s/` 建目录 —— 用户自由扩展不受限。
    """
    slug = _safe_name(slug, "slug")
    domain = _safe_name(domain, "--domain")
    page_type = _safe_name(page_type, "type")
    if not date:
        import datetime
        date = datetime.date.today().isoformat()
    type_dir = {"concept": "concepts", "entity": "entities", "query": "queries",
                "source": "sources", "module": "modules"}.get(page_type, page_type + "s")
    if page_type == "module":
        rel = os.path.join("domains", domain, "modules", slug, "README.md")
    else:
        rel = os.path.join("domains", domain, type_dir, slug + ".md")
    title = title or slug
    body = {
        "concept": "## Summary\n一句话概括。\n\n## Key Points\n- …\n",
        "query": "## 问题\n…\n\n## 结论\n…\n\n## 依据\n- …\n",
        "source": "## 来源\n…\n\n## 主要论点\n- …\n",
        "module": "## 业务定位\n…\n\n## Key Tables / APIs\n…\n\n## 踩坑 / Open Questions\n…\n",
    }.get(page_type, "## Summary\n…\n")
    content = (f"---\ntags: [{page_type}]\nstatus: active\ndate_created: {date}\n---\n"
               f"\n# {title}\n\n{body}")
    return rel, content


def scaffold(target: str, domains: Optional[List[str]] = None, date: str = "",
             check: bool = False) -> Dict[str, Any]:
    """幂等地确保 target 是一个 v3 个人库:缺啥补啥,【绝不覆盖已存在文件】。

    - 空目录/不存在 → 建全套骨架
    - 已存在但缺文件/缺目录 → 只补缺失的
    - 已完整 → no-op
    - v2 旧库(嵌套 wiki/ 布局)→ 不动它,只报告 legacy 提示(迁移由用户决定)
    check=True:只报告缺失,不写盘。
    """
    if not date:
        import datetime
        date = datetime.date.today().isoformat()
    target = os.path.abspath(os.path.expanduser(target))
    domains = domains or []

    # v2 旧库保护:嵌套布局不补 v3 骨架(避免两套结构混在一个库里)
    if repo.is_legacy_layout(target):
        return {
            "ok": True, "target": target, "legacy": True,
            "created": [], "skipped": [], "already_complete": True,
            "note": ("检测到 v2 旧布局(根下有 wiki/ 内容层)。库可继续使用;"
                     "建议迁移到 v3 扁平结构:把 wiki/ 下的 domains 等目录上移到库根,"
                     "详见 wiki-manage docs/INSTALL.md 的「v2 → v3 迁移」。"),
        }

    created: List[str] = []
    skipped: List[str] = []

    def ensure_file(rel: str, content: str):
        p = os.path.join(target, rel)
        if os.path.isfile(p):
            skipped.append(rel)
            return
        created.append(rel)
        if not check:
            os.makedirs(os.path.dirname(p) or target, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(content)

    def ensure_dir(rel: str):
        p = os.path.join(target, rel)
        if os.path.isdir(p):
            skipped.append(rel + "/")
            return
        created.append(rel + "/")
        if not check:
            os.makedirs(p, exist_ok=True)
            with open(os.path.join(p, ".gitkeep"), "w") as f:
                f.write("")

    for d in ["domains", "inbox", "raw", "archive", ".wiki"]:
        ensure_dir(d)
    for d in domains:
        ensure_dir(os.path.join("domains", d))

    ensure_file("AGENTS.md", _agents_md(date))
    ensure_file("overview.md", _overview_md(domains, date))
    ensure_file("_routes.md", _routes_md(date))
    ensure_file("log.md", f"# 操作台账\n\n## [{date}] init | 初始化/结构修复\n")
    ensure_file(".gitignore", ".obsidian/\n.idea/\n.DS_Store\n*.swp\n.wiki/\n")

    already_complete = len(created) == 0
    return {
        "ok": True, "target": target, "legacy": False,
        "created": created, "skipped": skipped,
        "already_complete": already_complete,
        "missing": created if check else [],
        "mode": "check" if check else "ensure",
    }
