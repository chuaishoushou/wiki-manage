#!/usr/bin/env python3
"""wiki-mcp:LLM Wiki 的只读 MCP server(stdio / JSON-RPC 2.0,纯标准库)。

与 wiki-cli 共享 wiki_core,确保 CLI↔MCP 行为一致。
只暴露只读 tool(无写 tool → 任何平台的 AI 都"看不见"写操作,这是只读纵深防御的一层)。
始终暴露 1 个 resource 占位(wiki://overview),规避 Codex 对 tools-only server 的判废。

部署:
  起步 = 本机 stdio(零常驻进程)。WIKI_ROOT 环境变量指定 wiki 根。
  各平台配置见 adapters/。
"""
import json
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, os.path.abspath(_SRC))

from wiki_core import frontmatter, repo, routes as routes_mod, search as search_mod  # noqa: E402
from wiki_core import sensitivity as sens_mod, suggest as suggest_mod, validate as validate_mod  # noqa: E402
from wiki_core import lint as lint_mod, changes as changes_mod, SUPPORTED_PROTOCOL_VERSION  # noqa: E402
from wiki_core.vocabulary import load as load_vocab  # noqa: E402

DEFAULT_PROTOCOL = "2024-11-05"
# 已知可协商的 MCP 协议版本(用于版本协商:不盲目回显客户端任意值)
KNOWN_PROTOCOLS = {"2024-11-05", "2025-03-26", "2025-06-18"}
SERVER_INFO = {"name": "wiki-governance", "version": "0.1.0"}

# .mcp.json 用 "${WIKI_ROOT:-}":WIKI_ROOT 未设时这里收到空串。
# 不把 env 值当 start 传(否则合法 env 会被如实报成 source='start');让 find_wiki_root_verbose
# 内部读 WIKI_ROOT 走 env 分支 —— 合法→'env'、空串→落 team-default(~/AI/team-wiki)兜底、
# 配错→'env-invalid' 硬失败,绝不静默连个人库。
ROOT, ROOT_SOURCE = repo.find_wiki_root_verbose()


def _vocab():
    return load_vocab(ROOT)


def _staleness_note():
    if not ROOT:
        return "wiki 根未找到"
    # root_source 下沉:让每个带 staleness 的工具返回都能暴露"连的不是团队库",
    # 无需 AI 主动调 get_protocol(GUI 丢 env 落到 cwd/个人库时尤其重要)。
    prefix = ""
    if ROOT_SOURCE not in ("env", "start", "team-default"):
        prefix = (f"⚠ root_source={ROOT_SOURCE}:当前连的可能不是团队库 —— "
                  "请设 WIKI_ROOT 或把 team-wiki clone 到 ~/AI/team-wiki · ")
    behind, why = repo.git_behind_count(ROOT)
    if behind is None:
        return prefix + f"新鲜度未知({why})"
    if behind == 0:
        return prefix + "本地与 origin 同步"
    return prefix + f"⚠ 本地落后 origin {behind} 个 commit,建议先 git pull / 用 /wiki-sync"


# ---------- tool 实现 ----------

def _agents_md_excerpt(limit=60):
    """返回团队仓 AGENTS.md 头部摘要,供跨工作区的 Codex/Cursor 拿到散文协议。"""
    if not ROOT:
        return ""
    p = os.path.join(ROOT, "AGENTS.md")
    if not os.path.isfile(p):
        return ""
    with open(p, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    return "\n".join(lines[:limit])


def t_get_protocol(_args):
    vocab = _vocab()
    warnings = []
    if ROOT_SOURCE in ("personal-fallback", "cwd"):
        warnings.append("你没设 WIKI_ROOT,当前连的是兜底/上溯库,可能不是团队 wiki —— 请显式设 WIKI_ROOT 或把 team-wiki clone 到 ~/AI/team-wiki")
    if vocab.parse_error:
        warnings.append(f"_vocabulary.md 解析失败({vocab.parse_error}),分类闭集已失效")
    return {
        "root": ROOT,
        "root_source": ROOT_SOURCE,  # env/start/team-default/cwd/personal-fallback/env-invalid:成员自查连到的是哪个库
        "warnings": warnings,
        "repo_protocol_version": vocab.protocol_version,
        "tool_supported_version": SUPPORTED_PROTOCOL_VERSION,
        "version_ok": vocab.protocol_version <= SUPPORTED_PROTOCOL_VERSION,
        "domains": vocab.domain_slugs,
        "page_types": vocab.page_types,
        "required_frontmatter": vocab.required_fields,
        "sensitivity_levels": vocab.data.get("sensitivity_levels", []),
        "staleness": _staleness_note(),
        "agents_md_excerpt": _agents_md_excerpt(),
        "note": "执行任何 wiki 写操作前先读 AGENTS.md + _vocabulary.md;写入走 file tools,不经本 MCP。",
    }


def t_search(args):
    results = search_mod.search(ROOT, args.get("query", ""), limit=int(args.get("limit", 10)))
    return {"staleness": _staleness_note(), "count": len(results), "results": results}


def t_resolve_route(args):
    routes = routes_mod.parse_routes(ROOT)
    hits = routes_mod.resolve(routes, args.get("keyword", ""))
    return {
        "keyword": args.get("keyword", ""),
        "ambiguous": len(hits) > 1,
        "hits": [{"keywords": h.keywords, "required": h.required, "optional": h.optional, "line": h.lineno} for h in hits],
    }


def t_get_page(args):
    rel = args.get("path", "")
    full = repo.resolve_in_root(ROOT, rel)  # 路径围栏:拒绝 '../' 穿越与越界绝对路径
    if not full:
        return {"error": f"路径越界或非法: {rel}"}
    if not os.path.isfile(full):
        return {"error": f"文件不存在: {rel}"}
    meta, body, _ = frontmatter.read_page(full)
    return {"path": rel, "frontmatter": meta, "body": body}


def t_validate(args):
    vocab = _vocab()
    rel = args.get("path", "")
    full = repo.resolve_in_root(ROOT, rel)  # 路径围栏
    if not full:
        return {"error": f"路径越界或非法: {rel}"}
    if not os.path.isfile(full):
        return {"error": f"文件不存在: {rel}"}
    meta, _, has_fm = frontmatter.read_page(full)
    issues = validate_mod.validate_page(meta, has_fm, repo.rel_path(ROOT, full), vocab)
    return {"path": rel, "ok": not any(i["level"] == "error" for i in issues), "issues": issues}


def t_lint(_args):
    return lint_mod.lint(ROOT, _vocab())


def t_suggest_path(args):
    return suggest_mod.suggest_path(args.get("text", ""), _vocab(), ROOT)


def t_sensitivity(args):
    vocab = _vocab()
    text = args.get("text")
    if text:
        return sens_mod.scan_text(text, vocab)
    return sens_mod.scan_repo(ROOT, vocab)


def t_changes(args):
    # 只读检查"团队仓有哪些待更新知识";fetch 只更新引用,不动工作区、不合并。
    do_fetch = args.get("fetch", True)
    return changes_mod.incoming(ROOT, do_fetch=bool(do_fetch))


TOOLS = [
    {
        "name": "wiki_get_protocol",
        "description": "返回 wiki 协议摘要(AGENTS.md/_vocabulary.md 闭集)+ 协议版本 + 本地新鲜度。任何 wiki 操作前先调它。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_get_protocol,
    },
    {
        "name": "wiki_search",
        "description": "全文/关键词检索 wiki(内容+frontmatter),按相关度排序。结果含新鲜度提示。",
        "inputSchema": {"type": "object", "properties": {
            "query": {"type": "string", "description": "检索词(空格分隔多词)"},
            "limit": {"type": "integer", "description": "返回条数,默认 10"}}, "required": ["query"]},
        "handler": t_search,
    },
    {
        "name": "wiki_resolve_route",
        "description": "按关键词解析 _routes.md,返回应加载的文件(必加载/可选加载),并标注路由歧义。",
        "inputSchema": {"type": "object", "properties": {
            "keyword": {"type": "string"}}, "required": ["keyword"]},
        "handler": t_resolve_route,
    },
    {
        "name": "wiki_get_page",
        "description": "按相对 wiki 根的路径取页内容 + frontmatter。",
        "inputSchema": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]},
        "handler": t_get_page,
    },
    {
        "name": "wiki_validate",
        "description": "校验单页 frontmatter 是否符合受控词表闭集与必填集(写入前自检)。",
        "inputSchema": {"type": "object", "properties": {
            "path": {"type": "string"}}, "required": ["path"]},
        "handler": t_validate,
    },
    {
        "name": "wiki_lint",
        "description": "全库体检:frontmatter/路由/孤儿/死链/重复/敏感度/协议版本,返回结构化报告。",
        "inputSchema": {"type": "object", "properties": {}},
        "handler": t_lint,
    },
    {
        "name": "wiki_suggest_path",
        "description": "确定性地建议新资料落位(domain/page_type/slug + confidence)。低 confidence 应入 staging。",
        "inputSchema": {"type": "object", "properties": {
            "text": {"type": "string", "description": "资料摘要"}}, "required": ["text"]},
        "handler": t_suggest_path,
    },
    {
        "name": "wiki_sensitivity",
        "description": "敏感度扫描(客户真名/凭证/攻击面)。给 text 则扫该段;不给则扫全库出审计。",
        "inputSchema": {"type": "object", "properties": {
            "text": {"type": "string"}}},
        "handler": t_sensitivity,
    },
    {
        "name": "wiki_changes",
        "description": "检查团队仓有哪些待更新知识(只读:git fetch+diff,按模块/概念分组,区分大更新/小更新)。不会自动应用,应用更新由用户手动 git pull。",
        "inputSchema": {"type": "object", "properties": {
            "fetch": {"type": "boolean", "description": "是否联网 fetch 最新引用,默认 true"}}},
        "handler": t_changes,
    },
]

TOOL_MAP = {t["name"]: t for t in TOOLS}

RESOURCES = [
    {"uri": "wiki://overview", "name": "wiki overview", "description": "wiki 顶层地图", "mimeType": "text/markdown"},
]


# ---------- JSON-RPC over stdio ----------

def _result(req_id, result):
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def _error(req_id, code, message):
    return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}


def handle(msg):
    # 非对象消息(标量 / 顶层数组 batch)→ 按 JSON-RPC 回 Invalid Request,不崩溃
    if not isinstance(msg, dict):
        return _error(None, -32600, "Invalid Request:消息必须是 JSON 对象(本 server 不支持 batch 数组)")
    method = msg.get("method")
    req_id = msg.get("id")
    params = msg.get("params")
    if not isinstance(params, dict):
        params = {}

    # 任何通知(无 id 的请求,如 notifications/initialized、notifications/cancelled)一律不回复
    if req_id is None and isinstance(method, str) and method.startswith("notifications/"):
        return None
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        # 版本协商:客户端请求的版本在已知集合内才回显,否则回服务端默认(不盲目照搬任意值)
        client_proto = params.get("protocolVersion")
        nego = client_proto if client_proto in KNOWN_PROTOCOLS else DEFAULT_PROTOCOL
        return _result(req_id, {
            "protocolVersion": nego,
            "capabilities": {"tools": {}, "resources": {}},
            "serverInfo": SERVER_INFO,
        })
    if method == "ping":
        return _result(req_id, {})
    if method == "tools/list":
        return _result(req_id, {"tools": [{"name": t["name"], "description": t["description"],
                                           "inputSchema": t["inputSchema"]} for t in TOOLS]})
    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOL_MAP.get(name)
        if not tool:
            return _error(req_id, -32602, f"未知 tool: {name}")
        if ROOT is None:
            return _result(req_id, {"content": [{"type": "text", "text": "错误:找不到 wiki 根(设 WIKI_ROOT)"}], "isError": True})
        try:
            out = tool["handler"](args)
            text = json.dumps(out, ensure_ascii=False, indent=2)
            return _result(req_id, {"content": [{"type": "text", "text": text}]})
        except Exception as e:  # noqa: BLE001  工具层兜底,避免单次调用崩溃整个 server
            return _result(req_id, {"content": [{"type": "text", "text": f"工具执行异常: {e}"}], "isError": True})
    if method == "resources/list":
        return _result(req_id, {"resources": RESOURCES})
    if method == "resources/read":
        uri = params.get("uri")
        if uri == "wiki://overview":
            ov = os.path.join(repo.content_dir(ROOT), "overview.md") if ROOT else None
            if not ov or not os.path.isfile(ov):
                ov = os.path.join(ROOT, "overview.md") if ROOT else None
            text = ""
            if ov and os.path.isfile(ov):
                with open(ov, "r", encoding="utf-8") as f:
                    text = f.read()
            return _result(req_id, {"contents": [{"uri": uri, "mimeType": "text/markdown", "text": text}]})
        return _error(req_id, -32602, f"未知 resource: {uri}")

    return _error(req_id, -32601, f"未知方法: {method}")


def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            # 畸形 JSON 无法取 id,按 JSON-RPC 回 parse error,但不退出循环
            _emit(_error(None, -32700, "Parse error"))
            continue
        # 顶层兜底:任何 handle 异常都转成 error 返回,绝不让一条消息杀死整个 stdio 循环
        try:
            resp = handle(msg)
        except Exception as e:  # noqa: BLE001
            rid = msg.get("id") if isinstance(msg, dict) else None
            resp = _error(rid, -32603, f"Internal error: {e}")
        if resp is not None:
            _emit(resp)


def _emit(resp):
    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()


if __name__ == "__main__":
    main()
