# 安装(统一 git 手动安装,不用插件市场)

> 设计决定:**不用插件市场,统一走 git + 手动安装**;**不做插件版本号,git 就是版本**(`git pull` 更新、`git checkout <tag/commit>` 钉版/回滚、`git log` 历史)。三平台同一套源码、同一个 MCP。

## 第 0 步(所有平台):clone 两个仓

```bash
git clone <wiki-manage 仓 url> ~/AI/wiki-manage      # 工具/插件(本仓)
git clone <team-wiki 仓 url>   ~/AI/team-wiki         # 团队知识内容
export WIKI_ROOT="$HOME/AI/team-wiki"                 # 写进 shell 配置
```

一键生成/落地各平台配置(不加 `--write` 只打印,先看再落):
```bash
python3 ~/AI/wiki-manage/bin/wiki-init --platform all --wiki-root ~/AI/team-wiki
python3 ~/AI/wiki-manage/bin/wiki-init --platform cc --wiki-root ~/AI/team-wiki --write   # 真正落地 CC
```

## 各平台机制(都不靠市场)

| 平台 | MCP(只读工具) | 规则/技能注册 |
|---|---|---|
| **Claude Code** | `claude mcp add -s user wiki -e WIKI_ROOT=... -- python3 <clone>/.../wiki_mcp.py` | skill 符号链接进 `~/.claude/skills/` + 规则指针写入 `~/.claude/CLAUDE.md` |
| **Codex** | `~/.codex/config.toml` 的 `[mcp_servers.wiki]` | `~/.codex/AGENTS.md` 用户级指针 |
| **Cursor** | `.cursor/mcp.json` | `.cursor/rules/wiki.mdc` |

> CC 的 skill 用**符号链接**指向 clone,所以 `git pull` 后 skill 内容即时更新;MCP 指向 clone 内的 `wiki_mcp.py`,`git pull` 后重启即用新版。

## 更新(统一,极简)

```bash
git -C ~/AI/wiki-manage pull     # 更新工具/插件(skill 经符号链接即时生效;MCP 重启 AI 后生效)
git -C ~/AI/team-wiki  pull     # 更新团队知识(= /wiki-sync)
```
- **不需要** `claude plugin update` / 版本号 / marketplace。
- 想钉到稳定版:`git -C ~/AI/wiki-manage checkout <tag>`;回滚:`git checkout <commit>`。

## 卸载(可逆)

```bash
claude mcp remove wiki
rm ~/.claude/skills/wiki-ingest ~/.claude/skills/wiki-query ~/.claude/skills/wiki-lint
rm ~/.claude/commands/wiki-sync.md ~/.claude/commands/wiki-help.md
# 删除 ~/.claude/CLAUDE.md 中 "wiki-init" 标记的那一段
```

## 三平台能装到什么程度(诚实)

- **跨平台一致的内核** = MCP(9 只读工具)+ 规则指针。三家都能装、能用,结果一致。
- **CC 额外**:skill(wiki-ingest/query/lint)+ slash 命令(/wiki-sync /wiki-help)自动加载。
- **Codex/Cursor**:没有 CC 那种 skill/命令自动加载,但 MCP 工具齐全;skill 自动触发能力请在你的实际版本上实测(spec §10)。
