# skill 触发 evals

两层:

## 1. 确定性代理回归(可自动跑,已并入自测)
```bash
python3 plugins/wiki-governance/evals/check_descriptions.py
```
校验每个 SKILL.md 的 `description` 覆盖 `triggers.json` 里的 `must_cover` 触发词 —— 防止改 description 时漏掉关键词导致 skill 不再被自动选中。这是确定性的,不依赖 LLM。

## 2. LLM 触发命中率(需 Claude Code eval 工具 / 人工)
`triggers.json` 列了每个 skill 的 `should_trigger` / `should_not_trigger` 自然语句。
在团队实际 Claude Code 版本上:
- 用 `should_trigger` 语句确认对应 skill 被自动调用;
- 用 `should_not_trigger` 确认不误触发(尤其 ingest 这类写操作)。

⚠ 注意 skill description 列表预算(约上下文 1%):本机已有 ~17 个 FLUX skill,
wiki 三个 skill 的 description 可能被挤占截断而触发不稳。用 `/doctor` 检查触发预算,
必要时调 `skillListingBudgetFraction` 或给低频 skill 设 name-only(spec §10)。
