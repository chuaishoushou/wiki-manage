## 个人知识库(flux-wiki)

- 工具 `wiki-cli`:优先用 `~/.local/bin/wiki-cli`;不存在时读 `~/.flux-wiki.json` 的 `wiki_manage` 字段,用 `python3 <wiki_manage>/plugins/flux-wiki/tools/bin/wiki-cli`。
- **会话首次涉及知识库:先跑 `wiki-cli context`**,拿个人库位置/团队仓/约定速查(路径以它的输出为准,不要凭记忆,本段也不写死任何路径)。
- 查知识:直接 Grep/Read 个人库 `.md`,或 `wiki-cli search "<词>"`。
- 记知识 / 学团队知识 / 体检:先 `wiki-cli guide <ingest|learn|lint|query|help>` 拿手册,严格照做;guide 报错说明环境有问题,跑 `wiki-cli doctor` 按提示修,不要凭猜测写盘。
- 红线:删除任何页 = `mv` 到 `archive/<YYYY-MM-DD>/`,绝不 `rm`;`raw/` 只读;每次写入在库根 `log.md` 追加一行;协议真源 = 库根 `AGENTS.md`。
