---
name: wiki-ingest
description: 把资料按统一规则 ingest 进团队 LLM Wiki。当用户要"记一下/入库/沉淀/收录"知识、给出外部资料(docx/pdf/md/链接)、或说"这次踩坑记到 wiki"时使用。先过敏感度闸与受控词表分类决策树,低置信入 staging。仅维护者写入。
disable-model-invocation: true
allowed-tools: Read, Grep, Glob, Write, Edit, Bash(git:*), Bash(wiki-cli:*), Bash(python3:*)
---

# wiki-ingest:统一规则入库(重流程)

> ⚠️ 写操作。规则真源是团队仓 `AGENTS.md` + `_vocabulary.md`,本 skill 只是把流程固化成步骤,**不复制规则正文**。任何分歧以 AGENTS.md / _vocabulary.md 为准。
> 跨平台:本工作流(正文)三家通用。检索/校验/分类用 `wiki-cli` 子命令,查知识也可直接 Read/Grep 库里的 `.md` 文件;三平台靠"规则指针"(CC: `~/.claude/CLAUDE.md`;Codex: `~/.codex/AGENTS.md`;Cursor: `.cursor/rules/wiki.mdc`)告诉 AI 库位置与这套流程。
>
> **这是"重流程",用于把新原始资料消化进团队仓(SSOT)。** 如果只是【归属已知的简单一页】(尤其个人库),走轻量路径即可:`wiki-cli new <type> <slug> --domain <d>` 一条命令生成合规页骨架,填正文即可,不必跑下面整套。仓库模型见 `docs/repos-model.md`。

## 第 0 步(强制):拉协议 + 自检新鲜度

跑 `wiki-cli protocol`。
- 若返回 `version_ok=false` → 工具落后于仓库协议,先升级工具仓再继续,**不要硬写**。
- 若 staleness 显示落后 origin → 提示用户先 `/wiki-sync` 或 `git pull`,避免基于旧库分类。

## 第 1 步(强制):敏感度闸 —— 先于分类

跑 `wiki-cli scan`(传资料文本)。命中**客户真名 / 凭证 / 攻击面关键词**时:
- frontmatter `sensitivity` 默认取建议值(通常 `maintainer-only`),需用户显式下调才放宽。
- 命中凭证/漏洞细节的:`maintainer-only` 或 `exclude`;**绝不让它进会 publish 的页**。
- `log.md` / revisions 摘要里**不要复述**凭证或注入细节。

## 第 2 步:落位建议(确定性)

跑 `wiki-cli suggest`(传摘要),拿到 `domain / page_type / slug / confidence`。这是确定性算法,任何机器同结果——把它当建议,最终由第 4 步校验闸拍板。

## 第 3 步:分类决策树

```
confidence = high 且命中某 domain → 落 wiki/domains/<domain>/<page_type>s/<slug>.md
                                     (module 类落 modules/<slug>/README.md)
跨 2+ domain 复用                  → 按 _vocabulary.md global_promotion 判 global/ 还是 domain-local
confidence = low / 歧义 / 平手     → 写 wiki/staging/domain-review/<slug>.md,停,等该 domain owner 裁决
                                     ★ 绝不擅自进 active 区
```
- page_type 取自闭集(source/entity/concept/query/module)。
- slug 用 kebab-case;模块用 `<module-id>-<英文名>`。
- 已存在相关页 → **优先重写整合**,不要新建重复(先 `wiki-cli search` 找相似,或直接 Grep 库文件)。

## 第 4 步(强制):写前校验

补齐 frontmatter 必填集(见 `_vocabulary.md` `required_frontmatter`):
`tags / page_type / domain / shared_scope / sensitivity / status / date_created`(低/中置信另需 `domain_reason`)。

落盘前跑 `wiki-cli validate <path>`。**有 error 不予落盘**,先补齐。
- tags 必须取自白名单,命中同义词先归并;禁止用 tag 表达状态。

## 第 5 步:落盘 + 连通 + 审计

1. `Write` 目标文件(直接用 file tools 写库里的 `.md`)。
2. 新页 → 在 `_routes.md` 追加关键词路由(否则检索不可达);更新所属 `overview.md` 使可达。
3. 追加 `log.md`:`## [YYYY-MM-DD] ingest | <标题>` + 改动摘要 + touched pages 链接。
4. 生成 `revisions/<YYYY-MM-DD>-<HHMMSS>-ingest.md`(含 domain/confidence/sensitivity/touched 页)。

## 第 6 步:staging 晋升(仅 owner)

staging 页晋升到 active **只能由该 domain 在 `_vocabulary.md` 登记的 owner 执行**;owner=UNASSIGNED 的 domain,新源滞留 staging。被拒的归档到 `archive/rejected-<date>/` 并写 `reject_reason`。

## 删除 = 归档

任何 `.md` 删除必须 `mv` 到 `archive/<分类>-<YYYY-MM-DD>/`,**绝不 `rm`**(敏感泄露除外,见 AGENTS.md)。
