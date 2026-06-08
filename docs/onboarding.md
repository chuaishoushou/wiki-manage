# 团队成员 onboarding

> 按角色分轨。**大多数人是只读成员,先看下面第一节就够了。** 一致性主要靠 MCP 工具。
> 完整安装步骤见 [INSTALL.md](INSTALL.md);本页是分角色的最短路径。

---

## A. 只读成员最短路径(15 人里的多数)

你只想偶尔查知识,不写库。**约定:团队库 clone 到 `~/AI/team-wiki`。**

### A-1. Claude Code(最省事)

> 前置:python3 ≥3.8、git(路 B 还需 `claude` CLI),详见 [INSTALL.md 第 0 步](INSTALL.md)。

先 clone 两个仓并设好库位置(顺序不能反——先有库,再装):
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
git clone https://github.com/chuaishoushou/team-wiki.git   ~/AI/team-wiki
echo 'export WIKI_ROOT="$HOME/AI/team-wiki"' >> ~/.zshrc && export WIKI_ROOT="$HOME/AI/team-wiki"
# bash 用户把 ~/.zshrc 换成 ~/.bashrc
```

再装插件,二选一:
```bash
# 路 A(推荐,插件市场):在 Claude Code 里输入
#   /plugin marketplace add chuaishoushou/wiki-manage
#   /plugin install wiki-governance@wiki-governance-marketplace
# 路 B(不走市场,命令行):
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/AI/team-wiki --write
```
然后重启 Claude Code。

**验收**:新开会话问 AI「团队 wiki 有哪些 domain?」——答得出 = 成了。
会话开头若看到 `[wiki] 未连接…`,就是 `~/AI/team-wiki` 不存在或 `WIKI_ROOT` 没设对。

### A-2. Codex / Cursor
见下面 C 节(这两家没有插件机制,要用 wiki-init 写 MCP 配置)。

---

## B. 维护者 / 从零建库

### B-1. 全新团队,还没有 wiki
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
python3 ~/AI/wiki-manage/plugins/wiki-governance/tools/bin/wiki-cli \
    init ~/AI/team-wiki --domains backend,frontend,ops --owner 你的名字
export WIKI_ROOT="$HOME/AI/team-wiki"
```
一条命令建出合规空库(目录骨架 + AGENTS.md + _vocabulary.md + _routes.md + overview.md),并自检 lint=0。然后编辑 `_vocabulary.md` 填 domain 边界,用 `/wiki-ingest` 收录第一篇。详见 [migration-runbook](migration-runbook.md)。

### B-2. 从已有个人库迁团队
见 [migration-runbook](migration-runbook.md)(含安全审计 / 脱敏 / publish 流程)。

---

## C. Codex / Cursor 安装(用 wiki-init 写 MCP 配置)

> **预期管理**:这两家没有 Claude Code 那种插件机制。"装" = 写一个 MCP server 配置(+ 可选指针)。skill 自动触发在这两家不保证,**一致性靠 MCP 工具**。先按 A-1 顶部 clone 好两个仓、设好 `WIKI_ROOT`。

```bash
# 先 dry-run 看将写什么(不加 --write 只打印)
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki
# 确认后落地
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki --write
```

- **Codex**:写 `~/.codex/config.toml` 的 `[mcp_servers.wiki]`(stdio,指向 wiki_mcp.py + env WIKI_ROOT)+ `~/.codex/AGENTS.md` 用户级指针(跨工作区生效),然后**重启 Codex**。
- **Cursor**:`wiki-init --platform cursor --write --cursor-project <项目根> --wiki-root ~/AI/team-wiki` 写 `.cursor/mcp.json` + `.cursor/rules/wiki.mdc`。**每个新项目都要重跑一次**;`.cursor/rules` 不保证自动触发,靠 `@wiki` 提及或直接让 AI 调 MCP 工具。
- 先单独验证 server 能跑(隔离问题):
  ```bash
  echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{}}}' \
  | WIKI_ROOT=~/AI/team-wiki python3 ~/AI/wiki-manage/plugins/wiki-governance/tools/server/wiki_mcp.py
  ```
  打印含 `serverInfo` 的 JSON = server 没问题,之后出问题就是平台配置。

**验收**:让 AI「调用 wiki_get_protocol」——返回里 `root` 是你的库、`root_source` 为 `env`/`team-default`、`warnings` 为空 = 成了。

---

## 通用验收清单(任何平台)

- [ ] `WIKI_ROOT=~/AI/team-wiki wiki-cli protocol` 显示「连接来源: WIKI_ROOT 环境变量 ✅」(或「约定团队路径 ✅」)+「协议版本: … OK ✅」
- [ ] AI 能调 `wiki_get_protocol` 且 `warnings` 为空、`root_source` 为 `env`/`team-default`
- [ ] AI 能 `wiki_search` 检索到一条已知内容
- [ ] 探针:问 AI「团队 wiki 有哪些 domain?」答得出 = 协议已加载

## 常见卡点
| 现象 | 原因 / 解法 |
|---|---|
| `[wiki] 未连接团队 wiki` | `~/AI/team-wiki` 不存在,或 `WIKI_ROOT` 指向的不是 wiki 根 |
| protocol 显示 `root_source=personal-fallback` | 没设 `WIKI_ROOT` 且约定路径缺失 → 连到了个人库;clone team-wiki 到 `~/AI/team-wiki` 或 `export WIKI_ROOT` |
| GUI/Desktop 启动连不上,终端能连 | GUI 不继承 shell 的 `export`;把库放在约定路径 `~/AI/team-wiki` 即可兜底 |
| Codex 看不到 wiki 工具 | config.toml 的 `args` 路径是否存在;先跑上面的 server 单测看 serverInfo |
| Windows `python3` 找不到 | 装 Microsoft Store 版 Python(带 python3 别名),或给 `python` 建 `python3` 别名 |

## 我想贡献新知识(只读成员)
你不能直接写中心仓。把资料提 **PR 到 `staging/`** 或开 issue,由该 domain owner 审核晋升。被拒会归档到 `archive/rejected-*/` 并写明原因。
