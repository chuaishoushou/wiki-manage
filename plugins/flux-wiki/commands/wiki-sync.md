---
description: (任何人)同步团队 wiki 到最新(git pull),并报告协议版本与新鲜度
allowed-tools: Bash(git:*), Bash(python3:*)
---

**这是"手动应用更新"——不会自动发生。** 把本地团队 wiki 副本同步到最新,步骤:

1. 先 `wiki-cli changes` 展示团队仓有哪些待更新知识(只读),让用户**确认**要不要更新、哪些是大模块更新值得重读。
2. 用户确认后,`git -C "$WIKI_ROOT" pull --ff-only` 拉取应用(若 `$WIKI_ROOT` 未设,提示先设)。
3. 跑 `wiki-cli protocol` 报告:当前分支/版本、是否已与 origin 同步。
4. 若 `git pull --ff-only` 因有冲突 / 本地已偏离而失败,**不要强制覆盖**,把冲突文件列给用户人工处理(中心仓只读模型下本地不应有未推送改动,有则说明可能误改了本地副本)。
