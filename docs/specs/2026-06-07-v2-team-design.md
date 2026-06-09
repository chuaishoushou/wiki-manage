# wiki-manage v2.0 设计 —— 团队 LLM Wiki 管理架构

**版本**:v2.0 (team)
**日期**:2026-06-07
**状态**:Active design,v1 阶段已开始实现(本仓 `plugins/` + `tools/`)
**取代**:[v1.0-skeleton](2026-05-25-v1-design.md)(本机 Web 服务 + 砍团队仓 + 只服务个人 —— 与团队共享目标根本冲突,已标记 superseded)
**来源**:14 智能体工作流(5 研究 + 3 方案合成 + 5 维对抗验证)+ 人工核验

---

## 0. 为什么推倒 v1

v1 明确"砍团队仓、只服务个人、不要 enforcement、做本机 Web 服务",而本轮目标是**给约 15 人团队共享同一套规范化知识库 + 统一入库分类**。两者根本冲突,且 v1 的 README(讲双 wiki/MCP)与 spec(讲砍团队仓/plugin manifest)自相矛盾。故重新设计。

### 已锁定的 4 条约束(用户拍板,本设计的第一性约束)

| | 约束 | 含义 |
|---|---|---|
| **A** | 平台:混用 Claude Code + Codex + Cursor | 规范层必须可移植(纯 markdown 最大公约数);跨平台主动能力走 wiki-cli(纯 CLI),知识库本地文件 AI 直接读;CC 侧叠 plugin 走最佳路径 |
| **B** | 仓库:中心团队仓 + 成员只读 | 1-2 名维护者写入/ingest,15 名成员主要查询/消费 |
| **C** | 治理:AI 自律 + 人工抽查,不上重 CI | 靠协议/词表让 AI 一致分类 + 定期 lint;**但维护者本机 pre-commit 校验不算"重 CI"** |
| **D** | 运行:方案1+方向2,Web 后期 | 纯 git + 插件/skill 为零额外进程底座 + 轻量 wiki-cli(纯 CLI);Web 暂不做 |

---

## 1. 核心结论:plugin vs skill

> **做一个 Claude Code plugin,plugin 里捆绑的就是 skill —— 但两者都不是内核。内核是三家 AI 都能读的纯 markdown(`AGENTS.md` 协议 + `_vocabulary.md` 受控词表 + `SKILL.md` 工作流);因为团队是"在别的代码仓里干活、wiki 是独立仓"的用法,统一规范的实际主通道是 wiki-cli(纯 CLI)+ 规则指针,知识库本地文件 AI 直接读;plugin 只是 Claude Code 这一侧的最佳投递外壳。**

| 角色 | 谁来当 | 真源? |
|---|---|---|
| 规则真源(法律) | 团队仓根 `AGENTS.md` + `_vocabulary.md` | ✅ 唯一 |
| 工作流内核(可移植) | 3 个 `SKILL.md`(ingest/query/lint) | 引用 AGENTS.md,不抄正文 |
| 入口 | 4 个 slash command | = skill 手动触发面 |
| 主动能力(跨平台承重墙) | 1 个轻量 wiki-cli(纯 CLI) | 确定性逻辑唯一实现处 |
| CC 投递外壳 | plugin + marketplace | 仅 CC 侧增强 |

**为什么 plugin 不是内核**:Cursor 无 plugin 体系;Codex 的 plugin 与 CC **格式不兼容**(两套 manifest,要发两条流水线)。规则若只活在 plugin 里 → Codex/Cursor 拿不到 → 违反约束 A。

---

## 2. 分层架构(两仓 + 六层)

```
┌─ L0 内容仓  team-wiki.git (= 现 ~/AI/wiki 纳入 git) ──────── 真源 = markdown 内容
│   wiki/domains/** · wiki/global/** · wiki/staging/** · wiki/templates/**
│   raw/(只读) · log.md · revisions/** · archive/**
│
├─ L1 协议 SSOT  team-wiki 根 ───────────────────────────── 唯一规范事实源(三家原生读)
│   AGENTS.md       ← ingest/query/lint/staging/删除即归档/frontmatter/sensitivity/protocol_version
│   _vocabulary.md  ← 受控词表(新增):domain+owner / page_type 闭集 / tag 白名单 / global 晋升
│   _routes.md · overview.md
│
├─ L2 工作流内核  wiki-manage/plugins/wiki-governance/skills/ ─ 可移植 markdown(name+desc 跨平台)
│   wiki-ingest/SKILL.md · wiki-query/SKILL.md · wiki-lint/SKILL.md
│
├─ L3 入口(slash) /wiki-ingest /wiki-query /wiki-lint /wiki-sync
│
├─ L4 主动能力  wiki-manage/plugins/wiki-governance/tools/ ──── 确定性逻辑唯一实现处(纯 stdlib)
│   (注:tools 物理上放在插件目录内,因为 plugin 安装只拷贝插件目录;这样 hook 才能引用到)
│   src/wiki_core/  ← frontmatter / vocabulary / routes / search / suggest / sensitivity / validate / lint / publish / repo / cli
│   bin/wiki-cli    ← 唯一入口(纯 CLI;AI 直接调,也供 CI/手动/离线/pre-commit 用)
│
├─ L5 CC 投递外壳  wiki-manage 根 .claude-plugin/marketplace.json ─ Claude Code 专属
│   plugins/wiki-governance/{.claude-plugin/plugin.json, hooks/hooks.json}
│
└─ L6 各平台适配层(薄,只"指向"不"复制") wiki-manage/adapters/ + bin/wiki-init
    CC:     plugin(L5) 一键装 + ~/.claude/CLAUDE.md 规则指针
    Codex:  ~/.codex/AGENTS.md(用户级规则指针)
    Cursor: .cursor/rules/wiki.mdc(Apply Manually,规则指针)
```

**两仓拆分**:`team-wiki.git`(内容+协议)与 `wiki-manage.git`(工具+plugin)分开 —— 规范升级不污染内容历史,内容 diff 干净便于人工抽查。

### 防 `CLAUDE.md ↔ plugin` 漂移铁律

1. 规则正文**只允许活在 `AGENTS.md` + `_vocabulary.md`**;其他一切(CLAUDE.md/skill/适配层/wiki-cli 文案)只放指针。
2. **`CLAUDE.md` 去规则化**:协议正文全抽进 AGENTS.md;团队仓 `.claude/CLAUDE.md` 与个人 `~/.claude/CLAUDE.md` 只留指针。
3. SKILL.md 正文 = 触发器 + 极简步骤 + 决策树骨架 + "先 Read AGENTS.md" 指针,目标 < 200 行。
4. wiki-cli 是确定性逻辑的**唯一实现**(同一 `src/`),绝不各处再写一份逻辑。
5. 适配层只允许"指针",不允许协议正文副本。
6. lint 把"协议正文重复"与"工具逻辑落后于协议(protocol_version 不匹配)"都列为一等检查项。

---

## 3. 对抗验证的关键修正(v1 合成版的 4 个硬伤)

本设计相对"朴素合成"做了 4 处结构性修正,均来自对抗验证 + 人工核验:

### 3.1 🔴 安全:`sensitivity` 作为正交维度(否则首次 push 即泄密)

`shared_scope` 是"复用范围"不是"可见权限"。已核验现库 active 区含:3 个客户真名映射内部细节、凭证/密钥 schema(`a05-email-alert/data-and-config.md` 等)、18 个文件含攻击面描述、`personal/` 私有域。

- frontmatter 增独立必填字段 `sensitivity: public | team | maintainer-only | exclude`。
- ingest 决策树**先过 sensitivity 闸再定 domain**:命中客户专名/凭证/漏洞特征默认 `maintainer-only` 或 `exclude`。
- 团队仓用 **publish 白名单脚本只导出 `sensitivity <= team`**,而非 push 整库。
- `git init` 前先 secret-scan + 人工裁定,**以脱敏快照作为 commit 0,不保留单人旧历史**(否则 git 历史 + log + revisions + archive 四处永久固化)。
- `personal/` 一律 `exclude`。

### 3.2 🔴 跨工作区:被动注入在三家全失效 → 规则指针 + wiki-cli 是主通道

成员日常在**别的代码仓**里干活,工作区根不是 wiki 仓,wiki 的 `AGENTS.md`/`SKILL.md`/`.cursor/rules` 不会被自动加载。修正:

- 协议指针放**用户级**(`~/.claude/CLAUDE.md`、`~/.codex/AGENTS.md`、`.cursor/rules/wiki.mdc`),跨工作区生效,告诉 AI 库位置 + 两件事(直接读库文件查知识、用 wiki-cli 做 protocol/检索/校验/分类/同步)。
- 统一规范的可靠送达靠规则指针 + wiki-cli:AI 跨工作区被指针唤醒后,用 `wiki-cli protocol` 拿协议摘要 + 版本(也可直接 Read 库根 `AGENTS.md`);skill 第一步、写操作前强制先拉。
- 跨平台一致性承重墙 = **规则指针 + 纯 CLI 的 wiki-cli + AI 直接读本地库文件**,而非常驻服务。

### 3.3 🔴 一致性在 N=1 已失守 → 写入时校验闸(非重 CI)

现库(单人/57 页)强制规则已大面积不达标:type-in-tags 仅 1.8%、`domain_reason` 0/57、77 个乱 tag、`scripts/lint.py` 根本不存在。纯事后 lint = 错误先入库先传播。修正:

- `page_type` 升为独立必填字段,闭集校验。
- 校验前移到"写入即拒绝":**维护者本机 git pre-commit hook** 跑 lint(不过不让 commit)。本地、只对 1-2 写入者、不影响只读成员、零团队 CI —— **与约束 C 兼容**。
- `lint.py`(纯标准库)是 **v1 硬前置**,不是 v2 交付物。

### 3.4 🟠 维护者瓶颈 + 静默陈旧

- 晋升权**按 domain 绑定 owner**(写进 `_vocabulary.md`),弱域指给真正懂的人。
- 两段式 ingest:成员 AI 产"近可晋升的 staging 候选页",维护者只审+晋升。
- wiki-cli 检索结果**附带"本地落后 N 个 commit"警告**,陈旧可见。
- staging 给可见 SLA + 状态字段;被拒归档留 `reject_reason`。

---

## 4. 统一入库分类机制(方案心脏)

一致性来自**流程**,工具只让它更快、可复现。四件套:

1. **受控词表 `_vocabulary.md`**:① 合法 domain + 边界 + owner;② page_type 闭集;③ tag 白名单 + 同义归并;④ global 晋升判定(≥2 域)。
2. **ingest 分类决策树**(固化进 `wiki-ingest` SKILL.md):
   ```
   新料 → wiki-cli validate(frontmatter 闭集校验,不过不落盘)
        → wiki-cli scan(命中敏感 → maintainer-only/exclude)
        → wiki-cli suggest(确定性算法,非 LLM 打分)
          ├ 高置信命中词表某 domain → 落 domains/<x>/<type>/<slug>.md
          ├ 跨 2+ domain → 判 global / domain-local
          └ 歧义/低置信 → 强制 staging/domain-review/,停,等 owner 裁决
   ```
3. **staging 复核闸**:只有该 domain owner 能晋升到 active。
4. **定期 lint + pre-commit gate**:确定性脚本出客观结果,AI 判读,修复需 owner 确认。

**诚实代价**:最终一致而非强一致;owner 是判断单点;词表需持续喂养。

---

## 5. wiki-cli 工具面(约束 D)

wiki-cli = **只读检索 + 计算 + 建议**;写入永远走 file 操作 + skill(人可审、git diff 可见)。纯 CLI 单一入口,AI 直接 Bash 调用;查知识也可绕过 CLI 直接 Read/Grep 库文件:

| wiki-cli 子命令 | 作用 | 副作用 |
|---|---|---|
| `wiki-cli protocol` | 返回 AGENTS.md+_vocabulary.md 摘要 + protocol_version + 本地落后 commit 数 | 无 |
| `wiki-cli search` | 全文/关键词检索(内容 + frontmatter) | 无 |
| `wiki-cli route` | 解析 `_routes.md` 关键词→文件 + 孤儿页逆查 | 无 |
| `wiki-cli get` | 按路径取页内容 + frontmatter | 无 |
| `wiki-cli validate` | frontmatter 必填/枚举闭集/命名/tag 白名单校验 | 无 |
| `wiki-cli lint` | 跑 12 步体检,结构化报告 | 无(落盘由 CLI 选项控制) |
| `wiki-cli suggest` | 读 `_vocabulary.md` 给 domain/type/slug + confidence | 无 |
| `wiki-cli scan` | secret/PII/攻击面扫描,给 sensitivity 建议 | 无 |

**部署形态**(贴死约束 D):纯 CLI,零常驻进程 —— AI 每次 Bash 调用拉起一次即退出,无服务、无端口、无 bearer token。若未来要团队级 http 集中共享/索引,再单独引入服务端(见 v2.5),届时仍复用同一 `src/`。

**CLI 作为 bundled script**:既给 AI 直接调,也可被 pre-commit hook 调用;纯 Python 标准库(纯 API 环境无网络不能装包)。

---

## 6. 各平台分发(约束 A)

| | Claude Code(最佳) | Codex(第二) | Cursor(降级) |
|---|---|---|---|
| 规范层 | 用户级 CLAUDE.md 指针 + clone 读 AGENTS.md | `~/.codex/AGENTS.md` 用户级指针 | `.cursor/rules/wiki.mdc`(Apply Manually,@-mention) |
| 工作流 skill | plugin 捆绑(命名空间隔离) | SKILL.md 复制到 `.agents/skills`(实测定论)+ `openai.yaml` sidecar | 无原生 skill,靠规则指针 + @-mention |
| 主动能力 | plugin 一并装好 wiki-cli + 规则指针 | `wiki-init` 写 `~/.codex/AGENTS.md` 指针 + 设库路径 | `wiki-init` 写 `.cursor/rules/wiki.mdc` 指针 + 设库路径 |
| 分发/更新 | marketplace 一键 + tag 发版 | git pull 工具仓(plugin 第二通道,需独立 manifest) | git pull,无版本化 UI |
| 一致性保证 | skill+wiki-cli+plugin | AGENTS.md+wiki-cli(skill 行为字段不可移植) | **规则指针 + wiki-cli**(三家共用同一 CLI 与库文件) |

**跨平台"结果一致"靠确定性的 wiki-cli + 规则指针兜底**:三家跑同一 wiki-cli、读同一份本地库文件,检索/校验/lint/分类建议**计算结果一致**,平台差异退化为"触发体验"差异。

**版本策略**:`plugin.json` 省略 version → 每 commit 算新版;成员 pin 到 release tag(`wiki-2026.06`)而非裸追 main,给评审/灰度窗口;规则正文变更走 PR + 第二 owner review。私有仓后台 autoUpdate 需环境预置 `GITHUB_TOKEN`(交互式凭证会阻塞启动)。

**注意**:Claude Code plugin 与 Codex plugin 是两套独立分发物,需各自 manifest,不存在"一份 plugin 两家装"。

---

## 7. 从现状迁移(安全优先排序)

| # | 步骤 | 说明 | 阻塞 |
|---|---|---|---|
| 0 | **安全审计 + 切分** | secret-scan 全库 → 标 sensitivity → 脱敏/剥离 personal 与攻击面 → 定 .gitignore + raw/ 决策 | 阻塞一切 git 操作 |
| 1 | 内容仓 git 化 | 以脱敏快照 `git init`(不留旧历史)→ protected branch + 成员只读 role | 依赖步 0 |
| 2 | 协议从个人 CLAUDE.md 抽进 AGENTS.md | 团队通用进 SSOT;CLAUDE.md 只留指针(放用户级);补 `_vocabulary.md` | — |
| 3 | 抽 3 个 skill + 写 lint.py + 接 pre-commit | 先本机 `~/.claude/skills/` 跑通 | — |
| 4 | wiki-manage 重生为 marketplace 仓 | plugin + wiki-cli(纯 CLI,bundled script) | 依赖步 3 |
| 5 | 团队装载 | CC marketplace 一键;Codex/Cursor 用 `wiki-init` 写规则指针 + 设库路径 + 自检 | 依赖步 4 |

**已核实**:`~/AI/wiki` 无 `.git`(硬阻塞);`~/AI/wiki-manage` 已是 git 仓。

---

## 8. 分阶段路线图

| 阶段 | 目标 | 关键交付 |
|---|---|---|
| **v0 安全基线** | 不泄密 | secret-scan 工具(`wiki scan`)+ sensitivity 字段 + publish 白名单脚本 + 审计报告 |
| **v1 git+插件/skill 底座** | 15 人拿到统一规则、只读消费、能 ingest/query/lint | 内容仓 git 化 + AGENTS.md SSOT + `_vocabulary.md` + 3 skill + `lint.py`+pre-commit + plugin/marketplace + Codex/Cursor 薄适配 |
| **v2 wiki-cli 主动能力** | 三家检索/校验/分类建议结果一致 | `src/` + 纯 CLI `wiki-cli`(8 子命令)+ `protocol`/`changes`/落后警告 + 规则指针 + `wiki-init` |
| **v2.5(可选)团队 http 共享** | 统一索引/集中审计/零安装 | 引入服务端(复用同一 `src/`)+ streamable-http + 定时 git pull + bearer token + 内网 + 健康检查 |
| **v3(后期)Web 面板** | 可视化抽查/审计 | 只读看板(lint 趋势/staging 待审/漂移热点) |

---

## 9. 最大风险(诚实,含缓解)

1. **最终一致 + owner 单点**:错误有窗口期,会先传播再被抓;owner 休假/离职是真实瓶颈。缓解:词表+决策树+staging 闸收敛判断;pre-commit 把"最终一致"前移成"写入时一致";owner ≥2 互备 + 月度词表 review。强一致只能上 v3 managed-settings(对 15 人暂不划算)。
2. **跨平台不对等(Cursor 二等公民)**:plugin/hook/autoUpdate 是 CC 专属。缓解:核心治理只沉淀在 AGENTS.md(文本)+ wiki-cli(纯 CLI 工具)两层(三家都吃,且 AI 还能直接 Read 库文件);Cursor 明确为"规则指针 + wiki-cli"。
3. **工程坑**:plugin.json version 陷阱、skill description 预算被既有 ~17 个 FLUX skill 挤占。缓解:v1 落地前在团队实际客户端版本逐项实测;version 选"省略靠 SHA"。wiki-cli 是纯 CLI,无常驻进程,不存在 server 挂掉问题;团队 http 共享留到 v2.5 再单独评估。

---

## 10. 待团队实测定论的项(v1 立项前)

- Codex skills 目录路径(`.agents/skills` 已基本定论,仍需团队实际版本验证)。
- Cursor 是否原生读 SKILL.md / `.cursorrules` 与 AGENTS.md 优先级冲突。
- 团队实际 CC/Codex/Cursor 版本上:plugin 自动安装提示、`wiki-init` 写规则指针后三家是否稳定加载、skill description 触发预算。
