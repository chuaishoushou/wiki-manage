"""scaffolder:一条命令建出一个【合规空 wiki】(冷启动)。

解决头号产品缺口:此前工具只能管理已存在的 wiki,无法创建新库,
全新团队从第一步就被卡死。本模块是"合规库种子"的单一真源:
- AGENTS.md(通用协议,不含任何具体项目/客户内容)
- _vocabulary.md(受控词表,protocol_version 对齐工具)
- _routes.md / overview.md / log.md / .gitignore
- 目录骨架 wiki/{domains/<each>,global,staging/domain-review,templates} + archive/ revisions/ raw/
- 页面模板 wiki/templates/*

含写副作用 → 是独立写子命令;只读子命令不含写副作用。
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from . import SUPPORTED_PROTOCOL_VERSION

_PAGE_TYPES = ["source", "entity", "concept", "query", "module"]
_SENS_LEVELS = ["public", "team", "maintainer-only", "exclude"]


def build_vocab_dict(domains: List[str], owner: str, profile: str) -> Dict[str, Any]:
    """构造受控词表 dict。profile=minimal 时 sensitivity 不必填(适合还没敏感数据的新团队)。"""
    required = ["tags", "page_type", "domain", "shared_scope", "status", "date_created"]
    if profile != "minimal":
        required.insert(4, "sensitivity")
    owner = owner or "UNASSIGNED"
    return {
        "protocol_version": SUPPORTED_PROTOCOL_VERSION,
        "domains": [
            {"slug": d, "boundary": "（一句话填写本 domain 的边界）", "owners": [owner], "status": "active"}
            for d in domains
        ],
        "page_types": _PAGE_TYPES,
        "sensitivity_levels": _SENS_LEVELS,
        "required_frontmatter": required,
        "required_frontmatter_conditional": {
            "domain_reason": "当 domain_confidence 为 low 或 medium 时必填"
        },
        "enum_fields": {
            "page_type": _PAGE_TYPES,
            "shared_scope": ["domain", "global"],
            "sensitivity": _SENS_LEVELS,
            "status": ["active", "staged", "archived", "unresolved"],
            "domain_confidence": ["low", "medium", "high"],
        },
        "tag_whitelist": _PAGE_TYPES + list(domains) + [
            "overview", "reference", "operations",
            # 根级协议/导航文件(AGENTS/_vocabulary/_routes/overview)自带的基础设施类 tag,
            # 必须进白名单,否则对新建库根级文件 validate 会报 tag-not-whitelisted。
            "schema", "infrastructure", "protocol", "vocabulary", "routes", "navigation",
        ],
        "tag_synonyms": {},
        "status_in_tags_forbidden": ["稳定", "进行中", "stable", "in-progress"],
        "global_promotion": {
            "min_domains": 2,
            "note": "concept/entity 仅当被 2+ domain 复用才可晋升 global/,否则 domain-local",
        },
        "sensitivity_rules": {
            "default_on_hit": "maintainer-only",
            "customer_names": [],
            "secret_keywords": ["clientSecret", "client_secret", "password", "密码", "apiKey", "api_key", "token", "私钥"],
            "attack_surface_keywords": ["注入", "越权", "绕过", "硬编码", "明文", "漏洞"],
        },
        "publish": {
            "max_sensitivity": "team",
            "note": "发布团队仓时只导出 sensitivity <= max_sensitivity 的页;publish:false 的 domain 整体排除",
        },
    }


def _vocab_md(domains: List[str], owner: str, profile: str, date: str) -> str:
    data = build_vocab_dict(domains, owner, profile)
    block = json.dumps(data, ensure_ascii=False, indent=2)
    rows = "\n".join(
        f"| {d['slug']} | {d['boundary']} | {d['owners'][0]} | 是 |" for d in data["domains"]
    )
    sens_note = "(minimal:sensitivity 非必填)" if profile == "minimal" else "(standard:sensitivity 必填)"
    return f"""---
tags: [vocabulary, infrastructure, protocol]
domain: global
page_type: concept
shared_scope: global
sensitivity: team
status: active
date_created: {date}
---

# Wiki 受控词表(Controlled Vocabulary)

> 机器可读规则源。工具只解析下方唯一的 json 围栏;**请直接编辑该 JSON 块**,下方表格仅为渲染视图。
> 新增 domain / page_type / tag 必须先改这里;`wiki-cli lint` 会校验全库 frontmatter 落在闭集内。
> 当前 profile:{profile} {sens_note}

## 权威源(工具解析此块)

```json
{block}
```

## 渲染视图(人读,勿手改 —— 改上面 JSON)

### (a) 合法 domain + 边界 + owner
| domain | 边界 | owner | 进团队仓? |
|---|---|---|---|
{rows}

> owner=UNASSIGNED 的 domain,在指派前其 staging 不得晋升到 active。

### (b) page_type 闭集
`source` · `entity` · `concept` · `query` · `module`(独立必填字段)

### (c) sensitivity 四级
`public` · `team` · `maintainer-only` · `exclude`

### (d) global 晋升
concept/entity 被 2+ domain 复用才可晋 `global/`。
"""


def _agents_md(date: str) -> str:
    return f"""---
tags: [schema, infrastructure, protocol]
domain: global
page_type: concept
shared_scope: global
sensitivity: team
status: active
protocol_version: {SUPPORTED_PROTOCOL_VERSION}
date_created: {date}
extensions: [modules, routes, vocabulary, sensitivity]
forked_from: https://github.com/Programming-With-Maury/Karpathy-LLM-Wiki
---

# LLM Wiki 操作协议

> 本文件定义 AI 对本知识库的操作规则。任何操作前先读本文件 + `_vocabulary.md` + `_routes.md`。
> 机器可读闭集(合法 domain / page_type / tag 白名单 / 敏感度 / 必填集)的唯一真源是 `_vocabulary.md`;
> 本文是散文规则。冲突时:闭集以 `_vocabulary.md` 为准,流程以本文为准。

## Mission
为团队维护一个结构化知识库,优化"持久化合成 / 可追溯证据链 / 跨 domain 知识迁移"。
- `raw/` 只读源材料(AI 绝不修改);`wiki/` 是维护的合成层;`overview.md` 顶层地图;`log.md` 追加日志;`_routes.md` 关键词路由。

## 目录
- `wiki/domains/<domain>/{{overview,sources,entities,concepts,queries,modules}}/`
- `wiki/global/{{entities,concepts}}/` — 仅放 2+ domain 复用的页
- `wiki/staging/` 待审;`wiki/staging/domain-review/` 归属不明
- `wiki/templates/` 页面模板;`archive/` 归档(= 删除);`revisions/` 审计

## Frontmatter(必填集见 `_vocabulary.md` required_frontmatter)
`tags / page_type / domain / shared_scope / sensitivity / status / date_created`
(domain_confidence 为 low/medium 时另需 domain_reason)。
- `page_type` 独立必填,取闭集之一。
- `sensitivity` 与 `shared_scope` 正交:前者管"谁能看",后者管"复用范围"。

## 受控词表 & page_type
新增 domain/page_type/tag 必须先改 `_vocabulary.md`;tag 取自白名单,禁止用 tag 表达状态(状态只由 status 字段承载)。

## Sensitivity(敏感度,与分类正交)
- 四级见 `_vocabulary.md`。ingest 先过 sensitivity 闸再定 domain:命中客户真名/凭证/攻击面 → 默认 maintainer-only。
- 团队仓发布 = 白名单导出(`wiki-cli publish`),只导 sensitivity <= publish.max;**绝不 push 整库**。

## Operations
- **Ingest**:① 过 sensitivity 闸 ② `wiki-cli suggest` 定 domain/type/slug ③ 高置信落 domains/<x>/<type>s/,跨域判 global,低置信/歧义入 staging/domain-review ④ 落盘前 `wiki-cli validate` 不过不落 ⑤ 追加 log.md + revisions/ + 新页注册 _routes.md。
- **Query**:先 `wiki-cli route` 走路由表,未命中再 `wiki-cli search`;引用页面路径;有持久价值的答案存 queries/。
- **Lint(体检)**:跑 `wiki-cli lint` 出报告;修复需 owner 确认;报告落 revisions/。

## Staging owner 闸
staging 晋升到 active 只能由该 domain 在 `_vocabulary.md` 登记的 owner 执行;UNASSIGNED 的 domain 新源滞留 staging。

## 写入时校验(约束 C 折中)
不上团队级 CI;维护者本机 git pre-commit 跑 `wiki-cli lint --staged`(不过不让 commit)允许且推荐。

## Protocol version
`AGENTS.md`/`_vocabulary.md` 带 protocol_version;工具启动比对,落后则告警不静默。

## Deletion policy(强制)
任何 `.md` 删除必须 `mv` 到 `archive/<分类>-<YYYY-MM-DD>/`,**绝不 `rm`**(敏感泄露除外)。

## Naming
小写 kebab-case;模块 slug=`<module-id>-<英文名>`;歧义加 disambiguator。
"""


def _routes_md(date: str) -> str:
    return f"""---
tags: [routes, navigation, infrastructure]
domain: global
page_type: concept
shared_scope: global
sensitivity: team
status: active
date_created: {date}
---

# Wiki 路由表

> 关键词 → 文件路径。AI 命中关键词时按此表精确加载。新建关键页应在此注册,否则检索不可达。

| 触发关键词（\\| 分隔） | 必加载（相对 wiki 根） | 可选加载（按需 Read） |
|---|---|---|
"""


def _overview_md(domains: List[str], date: str) -> str:
    items = "\n".join(f"- [[wiki/domains/{d}/overview|{d}]] — （一句话描述）" for d in domains)
    return f"""---
tags: [overview, navigation]
domain: global
page_type: concept
shared_scope: global
sensitivity: team
status: active
date_created: {date}
---

# Wiki 总览

> 顶层导航地图。只放导航,不堆具体业务知识。

## 活跃 Domains
{items}

## 操作入口
- 协议:`AGENTS.md` · 受控词表:`_vocabulary.md` · 路由:`_routes.md` · 日志:`log.md`

## 入门
新会话先读:`AGENTS.md` → `_vocabulary.md` → `_routes.md` → 本页。
"""


_CONCEPT_TEMPLATE = """---
tags: [concept]
page_type: concept
domain: REPLACE_DOMAIN
shared_scope: domain
sensitivity: team
status: active
date_created: REPLACE_DATE
---

# 概念标题

## Summary
一句话。

## Key Points
- …

## Links
- [[…]]
"""

_MODULE_TEMPLATE = """---
tags: [module]
page_type: module
domain: REPLACE_DOMAIN
shared_scope: domain
sensitivity: team
status: active
module_id: REPLACE_ID
owners: { backend: UNASSIGNED }
date_created: REPLACE_DATE
---

# <module-id> 模块名

## 业务定位(5 分钟读完)
…

## Key Tables / APIs
…

## 踩坑 / Open Questions
…
"""


_TYPE_DIR = {"concept": "concepts", "entity": "entities", "query": "queries",
             "source": "sources", "module": "modules"}

_PAGE_BODY = {
    "concept": "## Summary\n一句话概括。\n\n## Key Points\n- …\n\n## Links\n- [[…]]\n",
    "entity": "## 是什么\n…\n\n## 关键属性\n- …\n\n## Links\n- [[…]]\n",
    "query": "## 问题\n…\n\n## 结论\n…\n\n## 依据\n- …\n",
    "source": "## 来源\n源路径见 frontmatter 的 source_paths。\n\n## 主要论点\n- …\n",
    "module": "## 业务定位(5 分钟读完)\n…\n\n## Key Tables / APIs\n…\n\n## 踩坑 / Open Questions\n…\n",
}


def new_page(root: str, page_type: str, slug: str, domain: str,
             title: str = "", sensitivity: str = "team", date: str = ""):
    """生成一页合规骨架的【相对路径 + 内容】(不写盘,由调用方写)。

    轻量添加路径:已知归属时,一条命令拿到带正确 frontmatter 的页骨架,填正文即可,
    不必走完整 ingest(入库消化)流程。
    """
    if not date:
        import datetime
        date = datetime.date.today().isoformat()
    if page_type == "module":
        rel = os.path.join("wiki", "domains", domain, "modules", slug, "README.md")
    else:
        rel = os.path.join("wiki", "domains", domain, _TYPE_DIR.get(page_type, page_type + "s"), slug + ".md")
    title = title or slug
    fm = (f"---\ntags: [{page_type}]\npage_type: {page_type}\ndomain: {domain}\n"
          f"shared_scope: domain\nsensitivity: {sensitivity}\nstatus: active\ndate_created: {date}\n")
    if page_type == "module":
        fm += "module_id: REPLACE_ID\nowners: { backend: UNASSIGNED }\n"
    fm += "---\n"
    content = fm + f"\n# {title}\n\n" + _PAGE_BODY.get(page_type, "")
    return rel, content


def _domain_overview(d: str, date: str) -> str:
    return (f"---\ntags: [overview]\npage_type: concept\ndomain: {d}\nshared_scope: domain\n"
            f"sensitivity: team\nstatus: active\ndate_created: {date}\n---\n\n# {d} 总览\n\n"
            "（这个 domain 的高层综合,随知识沉淀补充）\n")


def scaffold(target: str, domains: Optional[List[str]] = None, owner: str = "UNASSIGNED",
             profile: str = "standard", date: str = "", check: bool = False) -> Dict[str, Any]:
    """幂等地确保 target 是一个合规 wiki:缺啥补啥,【绝不覆盖已存在文件】,已完整则 no-op。

    可多次执行(ensure/repair):
    - 空目录/不存在 → 建全套骨架
    - 已存在但缺文件/缺层级 → 只补缺失的(层级修复)
    - 已完整 → 什么都不动
    check=True:只报告缺失,不写盘(结构健康检查)。
    """
    if not date:
        import datetime
        date = datetime.date.today().isoformat()
    target = os.path.abspath(os.path.expanduser(target))

    from . import lint as lint_mod
    from .vocabulary import load as load_vocab

    # 修复场景:若已有 _vocabulary.md,domain 以它为准;否则用入参(新建场景)
    if os.path.isfile(os.path.join(target, "_vocabulary.md")):
        existing = load_vocab(target)
        domains_eff = existing.domain_slugs or (domains or ["example"])
    else:
        domains_eff = domains or ["example"]

    created: List[str] = []   # 本次新建(check 模式下 = 缺失项)
    skipped: List[str] = []   # 已存在,保持不动

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

    # 空目录骨架
    for ed in [os.path.join("wiki", "global", "concepts"),
               os.path.join("wiki", "global", "entities"),
               os.path.join("wiki", "staging", "domain-review"),
               "archive", "revisions", "raw"]:
        ensure_dir(ed)

    # 协议/导航文件(缺则补)
    ensure_file("AGENTS.md", _agents_md(date))
    ensure_file("_vocabulary.md", _vocab_md(domains_eff, owner, profile, date))
    ensure_file("_routes.md", _routes_md(date))
    ensure_file("overview.md", _overview_md(domains_eff, date))
    ensure_file("log.md", f"# Activity Log\n\n## [{date}] init | 初始化/层级修复\n\n- scaffold ensure(domains: {', '.join(domains_eff)},profile: {profile})\n")
    ensure_file(os.path.join("wiki", "templates", "concept-template.md"), _CONCEPT_TEMPLATE)
    ensure_file(os.path.join("wiki", "templates", "module-template.md"), _MODULE_TEMPLATE)
    ensure_file(".gitignore", ".obsidian/\n.idea/\n.DS_Store\n*.swp\n")

    # 每个 domain 的 overview.md
    for d in domains_eff:
        ensure_file(os.path.join("wiki", "domains", d, "overview.md"), _domain_overview(d, date))

    already_complete = len(created) == 0

    if check:
        return {
            "ok": already_complete, "mode": "check", "target": target,
            "already_complete": already_complete, "missing": created, "present": len(skipped),
            "domains": domains_eff,
        }

    # 写盘后跑 lint(信息性:结构已就绪,但已有内容可能仍有 lint 债)
    report = lint_mod.lint(target, load_vocab(target))
    return {
        "ok": True,  # 结构 ensure 操作成功(只补不覆盖,不会失败);内容质量看 lint_errors
        "target": target,
        "domains": domains_eff,
        "profile": profile,
        "created": created,
        "skipped": skipped,
        "already_complete": already_complete,
        "lint_errors": report["summary"]["errors"],
        "lint_warns": report["summary"]["warns"],
        "lint_report": report,
    }
