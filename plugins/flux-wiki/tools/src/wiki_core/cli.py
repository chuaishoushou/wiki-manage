"""wiki-cli:命令行入口(wiki_core 的唯一入口)。

6 个子命令:
  init    建库 / 结构修复(幂等;--check 只体检结构)
  new     轻量新建一页骨架
  search  全文检索
  lint    体检(全库 / 指定文件 / --staged)
  learn   团队仓增量学习数据(只读;--mark 写水位;--pull 先拉最新)
  status  当前库状态(根/布局/页数/主题/团队仓水位)  [别名 protocol]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from . import learn as learn_mod, lint as lint_mod, repo
from . import scaffold as scaffold_mod, search as search_mod, SUPPORTED_PROTOCOL_VERSION


def _resolve_root(args) -> str:
    """解析 wiki 根;找不到则给修复指引后退出(绝不静默猜库)。"""
    root, source = repo.find_wiki_root_verbose(getattr(args, "root", None))
    if not root:
        hints = {
            "start-invalid": "--root 指向的路径不是有效 wiki 根(缺 AGENTS.md)。",
            "env-invalid": "$WIKI_ROOT 指向的路径不是有效 wiki 根(缺 AGENTS.md)。",
            "config-invalid": f"配置文件 {repo.CONFIG_PATH} 里的 personal_root 已失效。",
            "none": "找不到 wiki 根。",
        }
        sys.stderr.write(f"错误:{hints.get(source, source)}\n"
                         "  · 新库:wiki-cli init <目录> 建一个(幂等,可重复跑)\n"
                         "  · 已有库:用 --root <路径> 显式指定,或重跑 wiki-manage 安装写入配置\n")
        sys.exit(2)
    return root


def _emit(obj: Any):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def _print_issues_sections(report: Dict[str, Any]):
    s = report["summary"]
    print(f"体检完成:{report.get('page_count', '?')} 页,{s['errors']} 错误 / {s['warns']} 警告\n")
    for sec in report["sections"]:
        if not sec["issues"]:
            continue
        print(f"## {sec['name']} ({len(sec['issues'])})")
        for i in sec["issues"]:
            mark = "❌" if i["level"] == "error" else "⚠️"
            loc = f" [{i['path']}]" if i.get("path") else ""
            print(f"  {mark} {i['msg']}{loc}")
        print()


# ---------- 子命令 ----------

def cmd_init(args):
    domains = [d.strip() for d in (args.domains or "").split(",") if d.strip()]
    res = scaffold_mod.scaffold(args.dir, domains=domains, check=args.check)
    if args.json:
        _emit(res)
        sys.exit(0 if res["ok"] and (not args.check or res["already_complete"]) else 1)
    if res.get("legacy"):
        print(f"⚠ {res['target']}:{res['note']}")
        sys.exit(0)
    if args.check:
        if res["already_complete"]:
            print(f"✅ {res['target']} 结构完整")
            sys.exit(0)
        print(f"⚠ {res['target']} 结构不完整,缺 {len(res['missing'])} 项:")
        for m in res["missing"]:
            print(f"   - {m}")
        print(f"\n修复:wiki-cli init \"{args.dir}\"(幂等,只补缺失,不覆盖已有)")
        sys.exit(1)
    if res["already_complete"]:
        print(f"✅ {res['target']} 已是完整结构,无需改动")
    else:
        print(f"✅ 已就绪: {res['target']}(新建 {len(res['created'])} 项,已有的绝不覆盖)")
        for c in res["created"]:
            print(f"   + {c}")


def cmd_new(args):
    root = _resolve_root(args)
    try:
        rel, content = scaffold_mod.new_page(root, args.type, args.slug, args.domain,
                                             title=args.title or "")
    except ValueError as e:
        sys.stderr.write(f"错误:{e}\n")
        sys.exit(2)
    # v2 旧库兼容:内容层在 wiki/ 下时落到 wiki/domains/...
    base = repo.content_dir(root)
    full = repo.resolve_in_root(base, rel)
    if not full:
        sys.stderr.write(f"错误:路径越界 {rel}\n")
        sys.exit(2)
    if os.path.isfile(full):
        sys.stderr.write(f"错误:页已存在,拒绝覆盖 {repo.rel_path(root, full)}(改 slug 或直接编辑)\n")
        sys.exit(1)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    out_rel = repo.rel_path(root, full)
    if args.json:
        _emit({"ok": True, "path": out_rel})
        return
    print(f"✅ 已新建: {out_rel}")
    print("   填正文即可;重要页可在 _routes.md 登记一个关键词,并在 log.md 记一行。")


def cmd_search(args):
    root = _resolve_root(args)
    results = search_mod.search(root, args.query, limit=args.limit, include_archive=args.archive)
    if args.json:
        _emit(results)
        return
    if not results:
        print("库还是空的,先写第一页(直接建文件或 wiki-cli new)。"
              if not search_mod.has_knowledge_pages(root)
              else "(无命中)。换个关键词,或直接 Grep 库目录。")
        return
    for r in results:
        print(f"· {r['title']}  (score={r['score']})\n  {r['path']}\n  {r['snippet']}\n")


def cmd_lint(args):
    root = _resolve_root(args)
    if args.staged or args.paths:
        files = ([repo.resolve_in_root(root, p) or p for p in args.paths]
                 if args.paths else _staged_md_files(root))
        report = lint_mod.lint_files(root, [f for f in files if f])
    else:
        report = lint_mod.lint(root)
    if args.json:
        _emit(report)
    else:
        _print_issues_sections(report)
    if args.out:
        _write_report_md(report, args.out)
        if not args.json:
            print(f"报告已写入 {args.out}")
    sys.exit(1 if report["summary"]["errors"] > 0 else 0)


def cmd_learn(args):
    root = _resolve_root(args)
    team = args.team or repo.load_config().get("team_root")
    if args.mark:
        if not team:
            sys.stderr.write("错误:--mark 需要知道团队仓(--team 或安装时配置 team_root)。\n")
            sys.exit(2)
        res = learn_mod.mark(root, team, args.mark)
        if args.json:
            _emit(res)
            sys.exit(0 if res.get("ok") else 2)
        if not res.get("ok"):
            sys.stderr.write(f"错误:{res['reason']}\n")
            sys.exit(2)
        print(f"✅ 已记录学习水位: {res['last_commit'][:12]}(团队仓 {res['team_root']})")
        return
    res = learn_mod.diff(root, team, do_pull=args.pull)
    if args.json:
        _emit(res)
        sys.exit(0 if res.get("ok") else 1)
    print(learn_mod.format_text(res))
    if not res.get("ok"):
        sys.exit(1)


def cmd_status(args):
    root, source = repo.find_wiki_root_verbose(getattr(args, "root", None))
    if not root:
        _resolve_root(args)  # 复用统一报错与退出
        return
    cfg = repo.load_config()
    legacy = repo.is_legacy_layout(root)
    content = repo.content_dir(root)
    domains_dir = os.path.join(content, "domains")
    domains = sorted(d for d in os.listdir(domains_dir)
                     if os.path.isdir(os.path.join(domains_dir, d))) if os.path.isdir(domains_dir) else []
    page_count = sum(1 for _ in repo.iter_pages(root))
    team = cfg.get("team_root")
    team_key = os.path.abspath(os.path.expanduser(team)) if team else None
    state = learn_mod.load_state(root)
    # 水位按团队仓多键存储(--team 学过的也在);全部列出,配置仓标注默认
    learn_states = [{"team_root": k, "last_commit": v.get("last_commit"),
                     "marked_at": v.get("marked_at"), "is_default": (k == team_key)}
                    for k, v in sorted(state.items()) if isinstance(v, dict)]
    team_state = state.get(team_key, {}) if team_key else {}
    payload = {
        "root": root,
        "root_source": source,
        "layout": "v2-nested" if legacy else "v3-flat",
        "tool_protocol_version": SUPPORTED_PROTOCOL_VERSION,
        "page_count": page_count,
        "domains": domains,
        "team_root": team,
        "team_root_exists": bool(team and os.path.isdir(os.path.expanduser(team))),
        "learn_last_commit": team_state.get("last_commit"),
        "learn_marked_at": team_state.get("marked_at"),
        "learn_states": learn_states,
    }
    if args.json:
        _emit(payload)
        return
    src_label = {"start": "--root 参数", "env": "$WIKI_ROOT", "config": f"配置 {repo.CONFIG_PATH}",
                 "cwd": "从当前目录上溯"}.get(source, source)
    legacy_ack = legacy and os.path.isfile(os.path.join(root, ".wiki", "ack-legacy-layout"))
    layout_label = ("v2 嵌套(已确认保留)" if legacy_ack
                    else "⚠ v2 嵌套(建议迁 v3,见 README)" if legacy else "v3 扁平 ✅")
    print(f"wiki 根 : {root}  (来源: {src_label})")
    print(f"布局    : {layout_label}")
    print(f"页数    : {page_count}  主题: {', '.join(domains) or '(无)'}")
    if team:
        ok = payload["team_root_exists"]
        print(f"团队仓  : {team} {'✅' if ok else '❌ 路径不存在'}")
    else:
        print("团队仓  : 未配置(需要时重跑安装加 --team-root,或 learn 时显式 --team)")
    shown = False
    for st in learn_states:
        wm = st["last_commit"] or "?"
        tag = "(默认)" if st["is_default"] else ""
        print(f"学习水位: {wm[:12]}  @ {st['marked_at'] or ''}  {st['team_root']}{tag}")
        shown = True
    if team and not shown:
        print("学习水位: (还没学习过;跑 /wiki-learn)")


# ---------- 辅助 ----------

def _staged_md_files(root: str) -> List[str]:
    import subprocess
    try:
        res = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                             capture_output=True, text=True, timeout=5)
        return [os.path.join(root, p) for p in res.stdout.splitlines() if p.endswith(".md")]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _write_report_md(report: Dict[str, Any], out: str):
    s = report["summary"]
    lines = ["# wiki lint 报告", "",
             f"- 页数: {report.get('page_count', '?')}",
             f"- 错误: {s['errors']}  警告: {s['warns']}", ""]
    for sec in report["sections"]:
        if not sec["issues"]:
            continue
        lines.append(f"## {sec['name']} ({len(sec['issues'])})")
        for i in sec["issues"]:
            mark = "❌" if i["level"] == "error" else "⚠️"
            loc = f" `{i['path']}`" if i.get("path") else ""
            lines.append(f"- {mark} **{i['code']}**: {i['msg']}{loc}")
        lines.append("")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------- argparse ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki-cli", description="轻量个人知识库工具(init/new/search/lint/learn/status)")
    p.add_argument("--root", help="wiki 根路径(默认: $WIKI_ROOT → ~/.flux-wiki.json 配置 → 当前目录上溯)")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    # --root/--json 写在子命令前后都接受(`search x --json` 与 `--json search x` 等价)。
    # 子命令侧用 SUPPRESS 默认值:不传时不覆盖主解析器已解析的值。
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", default=argparse.SUPPRESS,
                        help="wiki 根路径(同全局 --root,两个位置均可)")
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS,
                        help="JSON 输出(同全局 --json)")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=lambda **kw: argparse.ArgumentParser(parents=[common], **kw))

    sp = sub.add_parser("init", help="建库 / 结构修复(幂等:缺啥补啥,不覆盖已有)")
    sp.add_argument("dir", help="目标目录(空=新建;已存在=补全缺失结构)")
    sp.add_argument("--domains", help="逗号分隔的初始主题目录,如 backend,notes(可不填,之后随建)")
    sp.add_argument("--check", action="store_true", help="只检查结构是否完整,不写盘")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("new", help="轻量新建一页骨架")
    sp.add_argument("type", help="页面类型(concept/query/source/module/任意自定义)")
    sp.add_argument("slug", help="kebab-case 文件名")
    sp.add_argument("--domain", required=True, help="所属主题目录(不存在会自动建)")
    sp.add_argument("--title", help="页面标题(默认用 slug)")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("search", help="全文检索")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--archive", action="store_true", help="连归档区一起搜")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("lint", help="体检(全库;或指定文件;--staged 供 pre-commit)")
    sp.add_argument("paths", nargs="*", help="只检查这些文件(相对库根)")
    sp.add_argument("--staged", action="store_true", help="只检查 git 暂存的 .md")
    sp.add_argument("--out", help="把报告写到指定 md 路径(建议 .wiki/reports/)")
    sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("learn", help="团队仓增量学习数据(按 git 水位;--mark 记录学到哪)")
    sp.add_argument("--team", help="团队仓本地 clone 路径(默认用安装时配置的 team_root)")
    sp.add_argument("--pull", action="store_true", help="先对团队仓 git pull --ff-only 拿最新")
    sp.add_argument("--mark", metavar="COMMIT", help="记录学习水位(学习完成后调用)")
    sp.set_defaults(func=cmd_learn)

    sp = sub.add_parser("status", aliases=["protocol"], help="当前库状态(根/布局/页数/主题/团队仓水位)")
    sp.set_defaults(func=cmd_status)

    return p


def main(argv: List[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0
