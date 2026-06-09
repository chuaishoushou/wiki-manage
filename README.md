# wiki-manage

让一个团队(~15 人)共享**同一套规范化的 AI 知识库**:统一层级 / 分类 / 入库规则,跨 Claude Code / Codex / Cursor。

## 30 秒搞懂

涉及两个 git 仓,别混:

```
  team-wiki  (知识内容,你"读"它)            wiki-manage  (工具,你"装"它,= 本仓)
  ┌─────────────────────────────┐           ┌──────────────────────────────────┐
  │ wiki/domains/** 知识页        │  ◀─只读── │ plugin: flux-wiki           │
  │ AGENTS.md   协议(规则真源)    │ Read/Grep │   skills /wiki-ingest /query /lint │
  │ _vocabulary.md 受控词表        │  + CLI    │   CLI wiki-cli(含 init 建库)     │
  │ _routes.md  关键词路由         │           │   规则指针(三平台告诉 AI 库在哪) │
  └─────────────────────────────┘           └──────────────────────────────────┘
       1-2 名维护者写,15 人只读                成员装它来查/维护者用它来管
```

**术语速查**:`team-wiki`=知识内容仓 · `wiki-manage`=工具/插件仓(本仓) · `flux-wiki`=本仓里那个 Claude Code 插件 · `_vocabulary.md`=团队允许用的分类清单 · `AGENTS.md`=操作协议。

## 我是谁,从哪开始

| 你是… | 最短路径 |
|---|---|
| **全新团队(还没有 wiki)** | `wiki-cli init <目录>` 建一个合规空库 → 见 [迁移 runbook](docs/migration-runbook.md) |
| **只读成员(15 人里的多数)** | 只需查知识 → 见 [onboarding](docs/onboarding.md) 的「只读成员最短路径」 |
| **维护者(写/ingest/lint)** | 见 [迁移 runbook](docs/migration-runbook.md) + [spec](docs/specs/2026-06-07-v2-team-design.md) |

> 想深挖架构(为什么 plugin+skill+CLI、防漂移、风险)看 [spec](docs/specs/2026-06-07-v2-team-design.md);本 README 只带你上手。

## plugin 还是 skill?(一句话结论)

**做 plugin,plugin 里装的就是 skill;但内核是三家都能读的纯 markdown(`AGENTS.md`+`_vocabulary.md`+`SKILL.md`),查知识就是 AI 直接 Read/Grep 库文件 + Bash 调 `wiki-cli`,plugin 只是 Claude Code 侧的最佳投递。** 完整论证见 spec §1。

## 平台成熟度(重要预期管理)

**三平台都有插件市场、清单格式高度一致**,本仓同时备好三家清单,一键装。组件支持有差异:

| 平台 | 插件清单 | 安装 | 组件 |
|---|---|---|---|
| **Claude Code** | `.claude-plugin/plugin.json` | `/plugin marketplace add chuaishoushou/wiki-manage` → `/plugin install` | skills + commands + hooks |
| **Codex** | `.codex-plugin/plugin.json` | `codex plugin marketplace add chuaishoushou/wiki-manage` → `/plugin install`(命令名以 `codex plugin --help` 为准) | skills + hooks(**不支持 commands**) |
| **Cursor** | `.cursor-plugin/plugin.json` | 市场面板安装(官方暂无 CLI 装命令) | skills + commands + rules(.mdc) |

每家也都保留 `wiki-init`(不走市场、git 手动写规则指针)作备选。跨平台一致的内核靠**确定性的 `wiki-cli` + 库本地 .md**:AI 直接读本地 .md 查知识,用 CLI 做协议/检索/校验。skill 自动触发是 Claude Code 强项,Codex/Cursor 上以实测为准。

## 工具能力(只读;纯 CLI + 直接读文件)

| `wiki-cli <cmd>` | 作用 |
|---|---|
| `init <dir>` | **建库 / 层级修复(幂等,可多次跑:缺啥补啥、不覆盖已有;`--check` 只体检)** |
| `new <type> <slug> --domain` | **轻量新建一页合规骨架**(已知归属时,免手写 frontmatter) |
| `protocol` | 协议版本 + 连接来源 + 当前分支/版本 + 新鲜度 + 闭集 |
| `changes` | **检查团队仓有哪些待更新知识**(git fetch+diff,按模块/概念分组,区分大/小更新;只读不应用) |
| `search` / `route` / `get` | 检索 / 路由解析 / 取页(也可 AI 直接 Read/Grep 库 .md) |
| `validate` / `lint` | 单页校验 / 全库体检 |
| `suggest` | 入库落位建议(domain/type/slug) |
| `scan` `[进阶]` | 敏感度扫描(分享私库前用)— 写报告 |
| `publish` `[进阶]` | 脱敏白名单导出团队仓 — 含写副作用 |

## 快速开始

```bash
# 一键自测(unittest + CLI 端到端 + wiki-init + evals,自建临时 fixture)
python3 plugins/flux-wiki/tools/selftest.py

# 体验冷启动:30 秒建一个全新合规库看看长啥样
python3 plugins/flux-wiki/tools/bin/wiki-cli init /tmp/demo-wiki --domains backend,frontend
WIKI_ROOT=/tmp/demo-wiki python3 plugins/flux-wiki/tools/bin/wiki-cli protocol

# 三平台 onboarding 配置生成 + 自检(不加 --write 只打印)
python3 bin/wiki-init --platform all
```

## 位置可配置 / 多个库

库的位置由 `WIKI_ROOT` 环境变量(或每条命令的 `--root`)决定,可指向任意路径、可有多个:
```bash
wiki-cli --root ~/AI/wiki   protocol     # 库 A
wiki-cli --root ~/AI/wiki2  protocol     # 库 B(各自独立)
wiki-cli init ~/AI/wiki2 --domains kb    # 新库不存在?init 建出来(幂等,可重复跑)
wiki-cli init ~/AI/wiki2 --check         # 结构健康检查:缺层级会报并提示修复
```
- `init` 是**幂等**的:空目录建全套,已存在则只补缺失结构(层级修复),已完整则 no-op,**绝不覆盖你已有的页**。
- 多库切换:每条命令用 `--root` 指向不同库,或切换 `WIKI_ROOT` 环境变量即可,互不干扰。

## 文档

- [v2 团队设计 spec](docs/specs/2026-06-07-v2-team-design.md) — 架构、plugin/skill 结论、防漂移、风险(深读)
- [安装 INSTALL](docs/INSTALL.md) — 统一 git 安装(clone + wiki-init 写规则指针 + 设库路径)+ 更新/卸载/版本
- [成员 onboarding](docs/onboarding.md) — 三平台上手 + 验收清单
- [维护者迁移 runbook](docs/migration-runbook.md) — 从零建库 / 从个人库迁团队
- [仓库模型 repos-model](docs/repos-model.md) — 团队仓 vs 个人库、pull≠重 ingest、贡献走 PR(**防误用必读**)
- [skill 触发 evals](plugins/flux-wiki/evals/README.md)
- 团队仓 `.claude/` 模板:[examples/team-wiki-dotclaude/](examples/team-wiki-dotclaude/)

> 安全审计 / lint 基线报告是**针对你自己库的本地产物**(含具体内容,不随仓分发,已 gitignore)。
> 自己生成:`wiki-cli scan --out <file>` / `wiki-cli lint --out <file>`。

## ⚠️ 分享给团队前(若你迁移的是已有私库)

已有私库可能含客户名/凭证/攻击面描述。**`git init`/分享前**先 `wiki-cli scan` 裁定 `sensitivity`,用 `wiki-cli publish` 只导出 `sensitivity<=team`,**绝不 push 整库**。全新 `wiki-cli init` 建的空库无此问题。

## 路线图
v0 安全基线 → **v1 git+插件/skill+冷启动 scaffolder**(已实现)→ **v2 CLI + 规则指针**(已实现)→ v3 Web(后期)。

## License
TBD
