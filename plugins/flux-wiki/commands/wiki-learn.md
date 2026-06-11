---
description: 把团队知识仓的增量知识学习并分类进个人知识库(按 git 提交水位,动态更新)
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(python3:*)
---

把团队知识仓(git 管理)自上次学习以来的**增量知识**,逐页消化分类进个人库。
约定:`wiki-cli` = `python3 "{{WIKI_CLI}}"`;个人库 = `{{WIKI_ROOT}}`(**知识写入层 = `{{WIKI_CONTENT}}`**);团队仓 = `{{TEAM_ROOT}}`。

## 步骤

1. **拿增量**(只读):
   `wiki-cli learn --pull`
   - 首次学习列团队仓**已提交**的全部知识页;之后只列水位(上次学到的 commit)以来变化的页,并附期间提交标题(理解改动意图)。
   - 每页字段:`status`(A 新增 / M 修改 / D 删除 / R 改名)、`abs`(原文路径)、`previous`(此前学进个人库的落点,靠页内 `learned_from` 溯源)、`old_rel`(仅 R:改名前路径)、`archived_to`(仅 D:团队仓归档去向)。
   - 报"未配置团队仓"→ 让用户给路径,本次用 `--team <路径>`,并提醒重跑安装可固化配置。
2. **向用户确认范围**:增量较多时先列清单让用户挑(全学 / 只学某些主题 / 跳过)。
3. **逐页学习**(这是你的活,CLI 不代劳)——按 status 分流:
   - **[A] 新页** → 定主题看三层:① 个人库 `_vocabulary.md` 里的 `team_domain_aliases` 映射(如 `tms → flux-tms`);② 同一团队域其他已学页 `learned_from` 的落点前缀;③ 都没有才新建 `{{WIKI_CONTENT}}/domains/<主题>/` 并向用户提一句。拿不准放 `{{WIKI_CONTENT}}/inbox/`。
   - **[M] 已学页有更新**(有 previous)→ **delta 合并,禁止整页覆盖**:先看团队侧改了什么——
     `git -C "{{TEAM_ROOT}}" diff <页内 learned_commit>..HEAD -- <team_rel>`
     只把增量合进个人页;个人页里团队版没有的私有内容(本机路径 / 工作区规则 / 标了 `personal-only` 的段落)**一律保留,不得删除或覆盖**。
   - **[R] 改名** → 不要当新页重学:把 previous 页 frontmatter 的 `learned_from` 改成新路径即可(若内容也改了再按 M 处理)。
   - **[D] 删除 / 归档** → 把对应已学页 `mv` 到 `archive/<YYYY-MM-DD>/`(不要 rm),或经用户确认保留;带 `archived_to` 说明团队只是归档,旧文可去团队仓 archive 翻。
   - **写盘纪律**:frontmatter **必须**带溯源 `learned_from: <团队仓内相对路径>` + `learned_commit: <本次团队仓 HEAD>`;**把多个团队页合并进同一个人页时,`learned_from` 写成列表逐一登记全部来源页**(漏登记的来源页下次变更会被当新页重复导入);其余字段按个人库自身 `AGENTS.md` 协议补齐。
   - **链接改写**:团队页内指向团队仓其它页的相对链接,落盘前必须处理——目标页已学过 → 改指个人库实际路径;未学 / 不学 → 降级为纯文本并保留团队路径作溯源,如「功能编号映射(team: domains/tms/concepts/function-module-mapping.md)」。
   - 域内 `overview.md` 是导航页,CLI 已自动过滤不会推送;模块目录的 `README.md` 是内容,正常学。
4. **收尾**:
   - `{{WIKI_ROOT}}/log.md` 追加一行:`## [YYYY-MM-DD] learn | 学习团队知识 N 页` + 简要清单。
   - 记录水位:`wiki-cli learn --mark <本次团队仓 HEAD>`(HEAD 在第 1 步输出里;无效哈希会被当场拒绝)。
   - learn 报"无知识页变化但水位停滞"时,直接按提示 `--mark` 推进即可,无需逐页学习。
5. **报告**:学了哪些页、落到哪、跳过了哪些及原因。
