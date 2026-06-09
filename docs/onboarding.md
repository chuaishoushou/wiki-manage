# 团队成员 onboarding

> 按角色分轨。**大多数人是只读成员,先看下面第一节就够了。** 一致性靠规则指针 + wiki-cli(AI 直接 Read/Grep 库文件 + CLI 检索/校验)。
> 完整安装步骤见 [INSTALL.md](INSTALL.md);本页是分角色的最短路径。

---

## A. 只读成员最短路径(15 人里的多数)

你只想偶尔查知识,不写库。**约定:团队库 clone 到 `~/AI/team-wiki`。**

### A-1. Claude Code(最省事)

> 前置:python3 ≥3.8、git(路 B 还需 `claude` CLI),详见 [INSTALL.md 第 0 步](INSTALL.md)。

先准备团队知识库 + 设库位置(先有库,再装):
```bash
git clone https://github.com/chuaishoushou/team-wiki.git ~/AI/team-wiki   # 团队知识(约定路径)
echo 'export WIKI_ROOT="$HOME/AI/team-wiki"' >> ~/.zshrc && export WIKI_ROOT="$HOME/AI/team-wiki"
# bash 用户把 ~/.zshrc 换成 ~/.bashrc
```

再装插件,二选一:
```bash
# 路 A(推荐,插件市场,无需 clone 工具仓——插件自带 wiki-cli):在 Claude Code 里输入
#   /plugin marketplace add chuaishoushou/wiki-manage
#   /plugin install flux-wiki@flux-wiki-marketplace
# 路 B(不走市场,命令行,需先 clone 工具仓):
#   git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/AI/team-wiki --write
```
然后重启 Claude Code。

**验收**:新开会话问 AI「团队 wiki 有哪些 domain?」——答得出 = 成了。
会话开头若看到 `[wiki] 未连接…`,就是 `~/AI/team-wiki` 不存在或 `WIKI_ROOT` 没设对。

### A-2. Codex / Cursor
见下面 C 节(这两家也有插件市场,可一键装;或用 wiki-init 写规则指针作备选)。

---

## B. 维护者 / 从零建库

### B-1. 全新团队,还没有 wiki
```bash
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli \
    init ~/AI/team-wiki --domains backend,frontend,ops --owner 你的名字
export WIKI_ROOT="$HOME/AI/team-wiki"
```
一条命令建出合规空库(目录骨架 + AGENTS.md + _vocabulary.md + _routes.md + overview.md),并自检 lint=0。然后编辑 `_vocabulary.md` 填 domain 边界,用 `/wiki-ingest` 收录第一篇。详见 [migration-runbook](migration-runbook.md)。

### B-2. 从已有个人库迁团队
见 [migration-runbook](migration-runbook.md)(含安全审计 / 脱敏 / publish 流程)。

---

## C. Codex / Cursor 安装(插件市场为主,wiki-init 备选)

> **预期管理**:这两家也有插件市场、清单格式与 CC 高度一致,本仓已备好三家清单。先按 A-1 顶部准备好 team-wiki + 设好 `WIKI_ROOT`(路 A 插件市场无需 clone 工具仓;路 B/wiki-init 才需 `git clone wiki-manage`)。

**路 A:插件市场(推荐)**
- **Codex**:`codex plugin marketplace add chuaishoushou/wiki-manage`(命令名以 `codex plugin --help` 为准)→ 在 Codex 里 `/plugin install flux-wiki` → 重启。装 skills + hooks(不支持 slash command)。
- **Cursor**:经市场面板安装(官方暂无 CLI 装命令);装好后用 `@wiki` 触发规则。装 skills + commands + rules(.mdc)。

**路 B:wiki-init(不走市场)**
```bash
# 先 dry-run 看将写什么(不加 --write 只打印)
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki
# 确认后落地
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki --write
```

- **Codex**:写 `~/.codex/AGENTS.md` 用户级规则指针(跨工作区生效:库位置 + 用 Read/Grep 查知识、用 wiki-cli 做协议/检索/校验),然后**重启 Codex**。
- **Cursor**:`wiki-init --platform cursor --write --cursor-project <项目根> --wiki-root ~/AI/team-wiki` 写 `.cursor/rules/wiki.mdc` 规则指针。**每个新项目都要重跑一次**;靠 `@wiki` 提及或直接让 AI Read/Grep 库文件并调 wiki-cli。
- 先单独验证库与工具就绪(隔离问题):
  ```bash
  WIKI_ROOT=~/AI/team-wiki python3 ~/AI/wiki-manage/plugins/flux-wiki/tools/bin/wiki-cli protocol
  ```
  打印「连接来源 … ✅」+「协议版本 … OK ✅」= 库与 CLI 没问题,之后出问题就是平台配置。

**验收**:让 AI 跑 `wiki-cli protocol`——输出里 `root` 是你的库、`root_source` 为 `env`/`team-default`、`warnings` 为空 = 成了。

---

## 通用验收清单(任何平台)

- [ ] `WIKI_ROOT=~/AI/team-wiki wiki-cli protocol` 显示「连接来源: WIKI_ROOT 环境变量 ✅」(或「约定团队路径 ✅」)+「协议版本: … OK ✅」
- [ ] AI 能跑 `wiki-cli protocol` 且 `warnings` 为空、`root_source` 为 `env`/`team-default`
- [ ] AI 能 `wiki-cli search`(或直接 Grep 库 .md)检索到一条已知内容
- [ ] 探针:问 AI「团队 wiki 有哪些 domain?」答得出 = 规则指针已加载

## 常见卡点
| 现象 | 原因 / 解法 |
|---|---|
| `[wiki] 未连接团队 wiki` | `~/AI/team-wiki` 不存在,或 `WIKI_ROOT` 指向的不是 wiki 根 |
| protocol 显示 `root_source=personal-fallback` | 没设 `WIKI_ROOT` 且约定路径缺失 → 连到了个人库;clone team-wiki 到 `~/AI/team-wiki` 或 `export WIKI_ROOT` |
| GUI/Desktop 启动连不上,终端能连 | GUI 不继承 shell 的 `export`;把库放在约定路径 `~/AI/team-wiki` 即可兜底 |
| Codex 查不到团队知识 | 插件是否装上(`/plugin` 看列表)或 `~/.codex/AGENTS.md` 规则指针是否写入;`~/AI/team-wiki` 是否存在;先跑上面的 `wiki-cli protocol` 看连接来源 |
| Windows `python3` 找不到 | 装 Microsoft Store 版 Python(带 python3 别名),或给 `python` 建 `python3` 别名 |

## 我想贡献新知识(只读成员)
你不能直接写中心仓。把资料提 **PR 到 `staging/`** 或开 issue,由该 domain owner 审核晋升。被拒会归档到 `archive/rejected-*/` 并写明原因。
