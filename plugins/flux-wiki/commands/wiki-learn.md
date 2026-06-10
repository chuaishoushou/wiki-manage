---
description: 把团队知识仓的增量知识学习并分类进个人知识库(按 git 提交水位,动态更新)
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*)
---

把团队知识仓(git 管理)自上次学习以来的**增量知识**,逐页消化分类进个人库。
约定:`wiki-cli` = `python3 "{{WIKI_CLI}}"`;个人库 = `{{WIKI_ROOT}}`;团队仓 = `{{TEAM_ROOT}}`。

## 步骤

1. **拿增量**(只读):
   `wiki-cli learn --pull`
   - 首次学习会列出团队仓全部知识页;之后只列水位(上次学到的 commit)以来变化的页,并附期间提交标题(理解改动意图)。
   - 列表里每页带 `previous` 字段 = 该团队页此前学进个人库的落点(靠页内 `learned_from` 溯源)。
   - 报"未配置团队仓"→ 让用户给路径,本次用 `--team <路径>`,并提醒重跑安装可固化配置。
2. **向用户确认范围**:增量较多时先列清单让用户挑(全学 / 只学某些主题 / 跳过)。
3. **逐页学习**(这是你的活,CLI 不代劳):对每个变化页
   - Read 团队页原文(列表里的 `abs` 路径)。
   - 判断它属于个人库哪个主题:已有 `previous` 落点 → **更新原页**;新页 → 选 `{{WIKI_ROOT}}/domains/<主题>/`(可建新主题目录),拿不准放 `inbox/`。
   - 写盘,frontmatter **必须**带溯源:`learned_from: <团队仓内相对路径>`、`learned_commit: <本次团队仓 HEAD>`;内容可原样收录或按个人库语境改写、合并进已有页。
   - 团队页被**删除**(status=D)→ 把对应已学页 `mv` 到 `archive/<YYYY-MM-DD>/`(不要 rm),或经用户确认保留。
4. **收尾**:
   - `{{WIKI_ROOT}}/log.md` 追加一行:`## [YYYY-MM-DD] learn | 学习团队知识 N 页` + 简要清单。
   - 记录水位:`wiki-cli learn --mark <本次团队仓 HEAD>`(HEAD 在第 1 步输出里)。
5. **报告**:学了哪些页、落到哪、跳过了哪些及原因。
