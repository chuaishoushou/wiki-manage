---
name: wiki-lint
description: 给团队 LLM Wiki 做体检/清理,并做 git init 前的安全审计。当用户说"检查 wiki/体检/清理/lint/安全扫描/发布前检查"时使用。跑确定性检查出结构化报告,修复需 owner 确认。
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Bash(git:*), Bash(python3:*), Write
---

# wiki-lint:体检 / 安全审计

> 调用约定:下文 `wiki-cli` 均指 `python3 "${CLAUDE_PLUGIN_ROOT}/tools/bin/wiki-cli"`(插件市场 / CC 装时该变量可用);命令正文沿用 wiki-cli 简写。

> 确定性检查(同一仓任何机器同结果),AI 只判读 + 给修复建议;**修复(删除/移动)需该 domain owner 确认**。检查全部走 `wiki-cli` 子命令。

## 体检(routine)

跑 `wiki-cli lint --out revisions/<YYYY-MM-DD>-lint.md`。覆盖:
1. frontmatter 必填/枚举闭集/page_type/domain 合法/tag 白名单/状态词禁用
2. `_routes.md` 路径存在 + 关键词歧义
3. 孤儿页(关键页未被路由覆盖 = 检索不可达)
4. 死链
5. 跨域同名重复
6. 敏感度声明不足
7. protocol_version(工具是否落后于仓库协议)

判读报告 → 提出修复 → **owner 确认后**再改 → 报告落 `revisions/<date>-lint.md`(不仅在对话答复)。

## 安全审计(git init 前 / 发布前,强制)

跑 `wiki-cli scan --out docs/security-audit-<date>.md`(全库)。逐条裁定每页 `sensitivity`:
- 命中**客户真名 / 凭证 / 攻击面** → 至少 `maintainer-only`;凭证/漏洞细节 → `exclude`。
- `personal` 等 `publish:false` 域 → 整体不进团队仓。
- **结论**:团队仓发布 = 白名单导出 `sensitivity <= team`,**绝不 `git push` 整库**;commit 0 用脱敏快照,不留单人旧历史。

## 写入时校验(pre-commit,约束 C 折中)

维护者本机可装 git pre-commit hook 跑 `wiki-cli lint --staged`(见 `adapters/git-hooks/`),校验不过不让 commit。本地、只对写入者、不影响只读成员,**不是团队级 CI**。
