---
description: 把团队仓知识镜像同步到个人库 team/ 区(团队→个人,原样镜像,不重分类、不学习)
allowed-tools: Bash(python3:*), Bash(git:*)
---

把团队仓(独立 git 仓维护的公共知识)**原样镜像**到个人库的 `wiki/team/` 只读区,让你在个人库一处即可检索到团队知识。**不重新分类、不再 ingest**(那是反模式,见 docs/repos-model.md)。

适用场景:你的 `WIKI_ROOT` 指向**个人库**,团队仓是**另一个独立的 git 仓**(如公司 GitLab 的知识库 clone)。

步骤:
1. 确认两个路径:**团队仓本地 clone**(知识源,独立 git 仓)与**个人库**(= 当前 `WIKI_ROOT`,同步目标)。团队仓路径向用户要。
2. **先预览**(只读,不写盘):
   `wiki-cli sync-team --team <团队仓路径> --dry-run`
   看将新增 / 更新 / 删除哪些页,让用户确认。
3. 确认后**执行**:
   `wiki-cli sync-team --team <团队仓路径> [--pull]`
   - 加 `--pull`:同步前先对团队仓 `git pull --ff-only` 拿最新。
   - 团队页镜像到个人库 `wiki/team/` 区;增量幂等(再次同步只动变化的页)。
4. 报告结果(新增/更新/删除/未变 + 来源 commit)。提醒用户:
   - `team/` 区是**只读镜像**,可被 `wiki-cli search` / 直接 Read/Grep 检索,但**写操作走 CLI**:要改团队知识请到团队仓改、再 `sync-team`;别手改 `team/`(下次同步会覆盖)。
   - 若提示"团队仓不是合法 wiki 根",说明团队仓还没初始化,需先在团队仓 `wiki-cli init`。
