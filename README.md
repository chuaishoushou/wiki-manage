# wiki-manage

让 AI 跨 Claude Code / Codex / Cursor 标准化管理 wiki 知识库的**本机服务 + Web 治理面板 + MCP**。

**Status**：Design phase（v1.0-design），尚无可运行代码。

## 跟 v0.1.x 的关系

v0.1.x 是 skill 形态插件，已停止演进，归档在 `~/AI/wiki-manage-legacy`（git history 完整保留）。v1.0 是**完全重写**——不再是 skill 插件，而是本机服务进程。

## 设计哲学

- **Markdown 是 SoT**：禁数据库（v1），索引在服务进程内存里
- **本机部署**：每个开发者本机跑一份服务，不需要中心服务器
- **双 wiki 模型**：个人仓本地 / 团队仓走 git
- **人标记 + AI 整理**：用户在 Web 上点标记，AI 工具通过 MCP 读清单后整理 markdown
- **跨 AI 工具走 MCP**：三平台原生支持，不再做三套 plugin manifest
- **沿用 Karpathy LLM Wiki 协议**：domains / global / staging / routes / revisions

## 完整设计

[docs/specs/2026-05-25-v1-design.md](docs/specs/2026-05-25-v1-design.md)

## 关键问答

- **要占端口吗？** 是，本机服务监听 `localhost:7081`（HTTP + MCP 共用）
- **要常驻 daemon 吗？** Docker container 跑着，按需启停
- **要数据库吗？** v1 不要。内存索引，崩了从 markdown 重建
- **多平台兼容怎么办？** 走 MCP 协议，三平台 10 行配置统一指向 `http://localhost:7081/mcp`

## License

TBD
