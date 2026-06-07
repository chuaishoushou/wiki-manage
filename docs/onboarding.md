# 团队成员 onboarding

> 按角色分轨。**大多数人是只读成员,先看下面第一节就够了。** 一致性主要靠 MCP 工具。

---

## A. 只读成员最短路径(15 人里的多数)

你只想偶尔查知识,不写库。

### A-1. Claude Code(最省事)
```
git clone <wiki-manage 仓 url> ~/AI/wiki-manage
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/wiki --write   # 注册 MCP+skill+规则指针(不用市场)
```
然后设一次环境变量(指向团队知识库 clone 的位置),写进 shell 配置:
```bash
git clone <team-wiki 仓 url> ~/wiki    # 路径随你
export WIKI_ROOT="$HOME/wiki"
```
**就这两步。** 你**不需要** clone wiki-manage —— 装插件时工具已随插件带上。

**验收(对话式,最可靠)**:新开会话问 AI「团队 wiki 有哪些 domain?」——答得出 = 成了。
会话开头若看到 `[wiki] 未连接…` 提示,就是 `WIKI_ROOT` 没设对。

### A-2. Codex / Cursor
见下面 C 节(这两家没有一键安装,要手配 MCP)。

---

## B. 维护者 / 从零建库

### B-1. 全新团队,还没有 wiki
```bash
git clone <wiki-manage 仓 url> ~/AI/wiki-manage
python3 ~/AI/wiki-manage/plugins/wiki-governance/tools/bin/wiki-cli \
    init ~/team-wiki --domains backend,frontend,ops --owner 你的名字
export WIKI_ROOT=~/team-wiki
```
一条命令建出合规空库(目录骨架 + AGENTS.md + _vocabulary.md + _routes.md + overview.md),并自检 lint=0。然后编辑 `_vocabulary.md` 填 domain 边界,用 `/wiki-ingest` 收录第一篇。详见 [migration-runbook](migration-runbook.md)。

### B-2. 从已有个人库迁团队
见 [migration-runbook](migration-runbook.md)(含安全审计 / 脱敏 / publish 流程)。

---

## C. Codex / Cursor 安装(手配 MCP)

> **预期管理**:这两家没有 Claude Code 那种 plugin/marketplace 一键安装。"装" = 手配一个 MCP server(+ 可选指针)。skill 自动触发在这两家不保证,**一致性靠 MCP 工具**。

一键生成各平台配置 + 自检(不加 `--write` 只打印,你可对照后手动配):
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex   # 打印 ~/.codex 该写什么
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --write   # 直接写入
```

- **Codex**:写 `~/.codex/config.toml` 的 `[mcp_servers.wiki]`(stdio,指向 wiki_mcp.py + env WIKI_ROOT)+ `~/.codex/AGENTS.md` 用户级指针(跨工作区生效)。`skill-sidecar.openai.yaml` 是**可选/实验**,schema 需按你的 Codex 版本核对。
- **Cursor**:`wiki-init --platform cursor --write --cursor-project <项目根>` 写 `.cursor/mcp.json` + `.cursor/rules/wiki.mdc`。**每个新项目都要重跑一次**;`.cursor/rules` 不保证自动触发,靠 `@wiki` 提及或直接让 AI 调 MCP 工具。
- 先单独验证 server 能跑(隔离问题):
  ```bash
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' \
  | WIKI_ROOT=~/wiki python3 ~/AI/wiki-manage/plugins/wiki-governance/tools/server/wiki_mcp.py
  ```
  打印含 `serverInfo` 的 JSON = server 没问题,之后出问题就是平台配置。

**验收**:让 AI「调用 wiki_get_protocol」——返回里 `root` 是你的库、`warnings` 为空 = 成了。

---

## 通用验收清单(任何平台)

- [ ] `wiki-cli protocol` 显示「连接来源: WIKI_ROOT 环境变量 ✅」+「协议版本: … OK ✅」(若显示"兜底/上溯",说明没设 WIKI_ROOT,有连错库风险)
- [ ] AI 能调 `wiki_get_protocol` 且 `warnings` 为空
- [ ] AI 能 `wiki_search` 检索到一条已知内容
- [ ] 探针:问 AI「团队 wiki 有哪些 domain?」答得出 = 协议已加载

## 常见卡点
| 现象 | 原因 / 解法 |
|---|---|
| `[wiki] 未连接团队 wiki` | 没设 `WIKI_ROOT`,或指向的目录不是 wiki 根 |
| protocol 显示"兜底 ~/AI/wiki" | 你没 `export WIKI_ROOT` → 可能连错库,显式设它 |
| Codex 看不到 wiki 工具 | config.toml 的 `args` 路径是否存在;`python3` 是否在 PATH;先跑上面的 server 单测 |
| 私有仓 CC 后台 autoUpdate 卡住 | 环境预置 `GITHUB_TOKEN`/`GITLAB_TOKEN` |

## 我想贡献新知识(只读成员)
你不能直接写中心仓。把资料提 **PR 到 `staging/`** 或开 issue,由该 domain owner 审核晋升。被拒会归档到 `archive/rejected-*/` 并写明原因。
