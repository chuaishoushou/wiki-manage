---
description: 把团队知识仓的增量知识学习并分类进个人知识库(按 git 提交水位,核销后记水位)
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*), Bash(wiki-cli:*)
---

把团队知识仓自上次学习以来的增量知识,逐页消化分类进个人库。

> 工具 `wiki-cli`:shim 已装在 `~/.local/bin`(在 PATH 时直接 `wiki-cli`,否则用全路径 `~/.local/bin/wiki-cli`);都不行就读 `~/.flux-wiki.json` 的 `wiki_manage` 字段,用 `python3 <wiki_manage>/plugins/flux-wiki/tools/bin/wiki-cli`。

跑 `wiki-cli guide learn` 拿当前手册(已注入本机真实路径与团队仓清单),**严格按手册五步执行**:拿增量 → 确认范围 → 逐页学习(溯源/链接改写/delta 合并纪律都在手册里)→ 核销+记水位 → 报告。
