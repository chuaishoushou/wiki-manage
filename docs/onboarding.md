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
# 路 A(推荐,wiki-init,零中断):先 clone 工具仓,再跑一条命令
git clone https://github.com/chuaishoushou/wiki-manage.git ~/AI/wiki-manage
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/AI/team-wiki --write
# 路 B(备选,插件市场,有 trust/enable 提示):在 Claude Code 里输入
#   /plugin marketplace add chuaishoushou/wiki-manage
#   /plugin install flux-wiki@flux-wiki-marketplace
```
然后重启 Claude Code。**两条路二选一,勿同时用(会重复加载)。**

**验收**:新开会话问 AI「团队 wiki 有哪些 domain?」——答得出 = 成了。
会话开头若看到 `[wiki] 未连接…`,就是 `~/AI/team-wiki` 不存在或 `WIKI_ROOT` 没设对。

### A-2. Codex / Cursor
见下面 C 节(主推 wiki-init 写规则指针;Codex 另有插件市场备选,Cursor Pro 走 User Rules 粘贴)。

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

## C. Codex / Cursor 安装(主推 wiki-init,Codex 插件市场为备选)

> **预期管理**:统一主推 wiki-init(零中断)。先按 A-1 顶部准备好 team-wiki + 设好 `WIKI_ROOT`,并 `git clone wiki-manage`。Cursor Pro 无自托管市场、无可写全局规则文件,故走 User Rules 粘贴或项目级规则。

**Codex —— 路 A:wiki-init(推荐)**
```bash
# 先 dry-run 看将写什么(不加 --write 只打印),确认后加 --write 落地
python3 ~/AI/wiki-manage/bin/wiki-init --platform codex --wiki-root ~/AI/team-wiki --write
```
写 `~/.codex/AGENTS.md` 用户级规则指针(跨工作区:库位置 + 用 Read/Grep 查知识、用 wiki-cli 做协议/检索/校验),然后**重启 Codex**。
**Codex —— 路 B:插件市场(备选)**:`codex plugin marketplace add chuaishoushou/wiki-manage` → `codex plugin install flux-wiki` → 重启(命令以 `codex plugin --help` 为准)。装 skills + hooks。

**Cursor Pro —— 路 A:User Rules 全局(推荐,粘一次管所有项目)**
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform cursor --wiki-root ~/AI/team-wiki
```
复制打印出的「User Rules」纯文本块(已填好路径)→ Cursor 设置 → Rules → User Rules → 粘一次。
**Cursor Pro —— 路 B:项目级规则**:`wiki-init --platform cursor --write --cursor-project <项目根> --wiki-root ~/AI/team-wiki` 写 `.cursor/rules/wiki.mdc`,**每个项目重跑一次**,用 `@wiki` 触发。
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
