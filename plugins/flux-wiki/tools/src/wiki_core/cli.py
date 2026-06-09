"""wiki-cli:命令行入口(wiki_core 的唯一入口,纯 CLI)。

子命令:init / new / changes / sync-team / protocol / search / route / get / validate / lint / suggest / scan / publish。
读子命令(protocol/search/route/get/validate/lint/suggest/scan/changes)只读;
写子命令(init/new/sync-team/publish)含落盘副作用。lint 支持 --staged(供 git pre-commit hook)。
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from . import frontmatter, repo, routes as routes_mod, search as search_mod
from . import sensitivity as sens_mod, suggest as suggest_mod, validate as validate_mod
from . import lint as lint_mod, publish as publish_mod, scaffold as scaffold_mod
from . import changes as changes_mod, sync as sync_mod, SUPPORTED_PROTOCOL_VERSION
from .vocabulary import load as load_vocab


def _resolve_root_verbose(args):
    """解析 wiki 根,返回 (root, source);找不到则报错退出,personal 兜底发告警。"""
    root, source = repo.find_wiki_root_verbose(getattr(args, "root", None))
    if not root:
        if source == "start-invalid":
            sys.stderr.write("错误:--root 指向的路径不是有效 wiki 根(缺 AGENTS.md/_routes.md/_vocabulary.md)。下一步二选一:\n"
                             "  · 若这是个还没初始化的新库:wiki-cli init \"<该路径>\" 建一个(幂等,可重复跑)\n"
                             "  · 若指错了:修正 --root 指向真正的 wiki 根(已拒绝静默回退到默认库)\n")
        elif source == "env-invalid":
            sys.stderr.write("错误:WIKI_ROOT 指向的路径不是有效 wiki 根(缺 AGENTS.md/_routes.md/_vocabulary.md)。下一步二选一:\n"
                             "  · 若这是个还没初始化的新库:wiki-cli init \"<该路径>\" 建一个(幂等,可重复跑)\n"
                             "  · 若指错了:修正 WIKI_ROOT 指向真正的 wiki 根(已拒绝静默回退到默认库)\n")
        else:
            sys.stderr.write("错误:找不到 wiki 根。下一步二选一:\n"
                             "  · 还没有 wiki?新建一个:wiki-cli init <目录>\n"
                             "  · 已 clone 团队库?设 WIKI_ROOT 指向它:export WIKI_ROOT=/路径/到/team-wiki\n")
        sys.exit(2)
    if source == "personal-fallback":
        sys.stderr.write("⚠ 未设 WIKI_ROOT,已回退到个人库 ~/AI/wiki —— 若要用团队库,"
                         "请 export WIKI_ROOT 或把 team-wiki clone 到 ~/AI/team-wiki\n")
    return root, source


def _resolve_root(args) -> str:
    return _resolve_root_verbose(args)[0]


def _emit(obj: Any):
    print(json.dumps(obj, ensure_ascii=False, indent=2))


def cmd_init(args):
    domains = [d.strip() for d in (args.domains or "").split(",") if d.strip()] or None
    res = scaffold_mod.scaffold(args.dir, domains=domains, owner=args.owner or "UNASSIGNED",
                                profile=args.profile, check=args.check)
    if args.json:
        _emit({k: v for k, v in res.items() if k != "lint_report"})
        sys.exit(0 if res["ok"] else 1)

    # --check:结构健康检查(不写盘)
    if args.check:
        if res["already_complete"]:
            print(f"✅ {res['target']} 结构完整,无需修复")
            sys.exit(0)
        print(f"⚠ {res['target']} 结构不完整,缺 {len(res['missing'])} 项:")
        for m in res["missing"]:
            print(f"   - {m}")
        print(f"\n修复:wiki-cli init {args.dir}(幂等,只补缺失,不覆盖已有)")
        sys.exit(1)

    # 实际 ensure/repair
    if res["already_complete"]:
        print(f"✅ {res['target']} 已是合规库,无需改动(幂等 no-op)")
    else:
        print(f"✅ 已确保合规结构: {res['target']}")
        print(f"   新建 {len(res['created'])} 项,保留 {len(res['skipped'])} 项(已存在的绝不覆盖)")
        for c in res["created"][:12]:
            print(f"     + {c}")
        if len(res["created"]) > 12:
            print(f"     … 共 {len(res['created'])} 项")
    print(f"   domains={res['domains']}  profile={res['profile']}  "
          f"(lint: {res['lint_errors']} error / {res['lint_warns']} warn)")
    if res["lint_errors"]:
        print("   注:已有内容仍有 lint error(结构已就绪,内容质量另跑 /wiki-lint 处理)")
    print("\n下一步:")
    print(f"   1) export WIKI_ROOT={res['target']}")
    print("   2) 编辑 _vocabulary.md 填每个 domain 的边界与 owner")
    print("   3) 用 /wiki-ingest(或 wiki-cli suggest)收录第一篇")


def cmd_new(args):
    root = _resolve_root(args)
    vocab = load_vocab(root)
    if args.type not in vocab.page_types:
        sys.stderr.write(f"错误:page_type `{args.type}` 不在闭集 {vocab.page_types}\n")
        sys.exit(2)
    if vocab.domain_slugs and args.domain not in vocab.domain_slugs:
        sys.stderr.write(f"错误:domain `{args.domain}` 未在 _vocabulary.md 登记。\n"
                         f"  已登记:{', '.join(vocab.domain_slugs)}\n"
                         f"  不确定归属?先 wiki-cli suggest \"<摘要>\" 看建议,或走 /wiki-ingest 完整流程。\n")
        sys.exit(2)
    sens_levels = vocab.data.get("sensitivity_levels", [])
    if sens_levels and args.sensitivity not in sens_levels:
        sys.stderr.write(f"错误:sensitivity `{args.sensitivity}` 不在闭集 {sens_levels}(改 --sensitivity 或先在 _vocabulary.md 登记)\n")
        sys.exit(2)
    rel, content = scaffold_mod.new_page(root, args.type, args.slug, args.domain,
                                         title=args.title or "", sensitivity=args.sensitivity)
    full = repo.resolve_in_root(root, rel)
    if not full:
        sys.stderr.write(f"错误:路径越界 {rel}\n")
        sys.exit(2)
    if os.path.isfile(full):
        sys.stderr.write(f"错误:页已存在,拒绝覆盖 {rel}(改 slug 或直接编辑该文件)\n")
        sys.exit(1)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)
    # 写后即校验
    meta, _, has_fm = frontmatter.read_page(full)
    issues = validate_mod.validate_page(meta, has_fm, rel, vocab)
    errs = [i for i in issues if i["level"] == "error"]
    if args.json:
        _emit({"path": rel, "ok": not errs, "issues": issues})
        return
    print(f"✅ 已新建合规页: {rel}")
    if errs:
        print("⚠ 但 frontmatter 仍有 error(请补全):")
        _print_issues(errs)
    print("\n下一步:")
    print("   1) 编辑该文件填正文")
    print(f"   2) 在 _routes.md 给它登记一个关键词(否则检索不可达)")
    print("   3) 完成后 wiki-cli validate 自检")


def cmd_changes(args):
    root = _resolve_root(args)
    res = changes_mod.incoming(root, do_fetch=not args.no_fetch)
    if args.json:
        _emit(res)
        return
    print(changes_mod.format_text(res))


def cmd_protocol(args):
    root, source = _resolve_root_verbose(args)
    vocab = load_vocab(root)
    behind, why = repo.git_behind_count(root)
    branch, commit = repo.git_head_info(root)
    version_ok = vocab.protocol_version <= SUPPORTED_PROTOCOL_VERSION
    # 把"连接来源不可靠 / 版本落后 / 词表解析失败"等统一收成中文告警串,
    # 供调用方(如 wiki_get_protocol)直接展示;env/team-default 等正常路径为空列表。
    warnings: List[str] = []
    if source == "personal-fallback":
        warnings.append("未设 WIKI_ROOT,已兜底到个人库 ~/AI/wiki —— 这可能不是团队库,请 export WIKI_ROOT 或把 team-wiki clone 到 ~/AI/team-wiki")
    elif source == "cwd":
        warnings.append("未设 WIKI_ROOT,wiki 根是从当前目录上溯找到的 —— 请显式 export WIKI_ROOT 锁定连接的库")
    if not version_ok:
        warnings.append(f"工具协议版本落后:仓库 v{vocab.protocol_version} > 工具支持 v{SUPPORTED_PROTOCOL_VERSION},请升级工具")
    if vocab.parse_error:
        warnings.append(f"_vocabulary.md 的 JSON 块解析失败,分类闭集已失效:{vocab.parse_error}")
    payload = {
        "root": root,
        "root_source": source,
        "branch": branch,
        "commit": commit,
        "repo_protocol_version": vocab.protocol_version,
        "tool_supported_version": SUPPORTED_PROTOCOL_VERSION,
        "version_ok": version_ok,
        "behind_commits": behind,
        "behind_note": why,
        "domains": vocab.domain_slugs,
        "page_types": vocab.page_types,
        "sensitivity_levels": vocab.data.get("sensitivity_levels", []),
        "vocabulary_parse_error": vocab.parse_error,
        "warnings": warnings,
    }
    if args.json:
        _emit(payload)
        return
    print(f"wiki 根: {root}")
    src_label = {
        "env": "WIKI_ROOT 环境变量 ✅",
        "start": "--root 参数 ✅",
        "team-default": "约定团队路径 ~/AI/team-wiki ✅(你没设 WIKI_ROOT,已用约定团队库)",
        "cwd": "⚠ 从当前目录上溯找到(你没设 WIKI_ROOT)",
        "personal-fallback": "⚠ 默认兜底 ~/AI/wiki 个人库(你没设 WIKI_ROOT,这可能不是团队库!"
                             "请 export WIKI_ROOT 或把 team-wiki clone 到 ~/AI/team-wiki)",
    }.get(source, source)
    print(f"连接来源: {src_label}")
    if branch:
        print(f"当前版本: 分支 {branch} @ {commit}(内容版本由 git 记录,无需另存)")
    print(f"协议版本: 仓库 v{vocab.protocol_version} / 工具支持 v{SUPPORTED_PROTOCOL_VERSION} "
          f"({'OK ✅' if payload['version_ok'] else '⚠ 工具落后,请升级'})")
    if behind is None:
        print(f"新鲜度: 无法判定({why})")
    elif behind == 0:
        print("新鲜度: 本地与 origin 同步(基于上次 fetch;wiki-cli changes 可联网刷新)")
    else:
        print(f"新鲜度: ⚠ 落后 origin {behind} 个 commit(基于上次 fetch)。"
              f"wiki-cli changes 看具体变更,确认后 /wiki-sync 手动更新")
    print(f"合法 domain: {', '.join(vocab.domain_slugs) or '(无)'}")
    if vocab.parse_error:
        print("⚠ _vocabulary.md 的 JSON 块解析失败 → 分类闭集已失效,请检查该文件(不是空库问题)")
    elif not vocab.domain_slugs:
        print("提示: 词表暂无 domain(新库属正常)。编辑 _vocabulary.md 添加,或建库时用 wiki-cli init --domains")
    print(f"page_type 闭集: {', '.join(vocab.page_types)}")


def cmd_search(args):
    root = _resolve_root(args)
    results = search_mod.search(root, args.query, limit=args.limit, include_archive=args.archive)
    if args.json:
        _emit(results)
        return
    if not results:
        # 区分"内容区(wiki/)无任何页"和"有页但没命中",给新用户方向
        # (经 init 的库恒非空,此分支仅命中"仓骨架已建/已 clone 但尚未 ingest 任何页"等窄场景)
        has_any = next(repo.iter_pages(root), None) is not None
        if not has_any:
            print("库还是空的(还没有任何页)。先用 /wiki-ingest(或 wiki-cli suggest)收录第一篇。")
        else:
            print("(无命中)。换个关键词,或用 wiki-cli route <kw> 看路由表。")
        return
    for r in results:
        tag = f"[{r['page_type']}/{r['domain']}]" if r["page_type"] or r["domain"] else ""
        print(f"· {r['title']} {tag}  (score={r['score']})\n  {r['path']}\n  {r['snippet']}\n")


def cmd_route(args):
    root = _resolve_root(args)
    routes = routes_mod.parse_routes(root)
    if args.keyword:
        hits = routes_mod.resolve(routes, args.keyword)
        out = [{"keywords": h.keywords, "required": h.required, "optional": h.optional, "line": h.lineno} for h in hits]
        if args.json:
            _emit({"keyword": args.keyword, "hits": out})
            return
        if not hits:
            print(f"(关键词 `{args.keyword}` 未命中路由)")
            return
        if len(hits) > 1:
            print(f"⚠ 路由歧义:`{args.keyword}` 命中 {len(hits)} 行")
        for h in hits:
            print(f"必加载: {', '.join(h.required)}")
            if h.optional:
                print(f"可选: {', '.join(h.optional)}")
    else:
        # 无关键词 → 列总览 + 歧义
        amb = routes_mod.find_ambiguous(routes)
        payload = {"route_count": len(routes), "ambiguous": amb}
        if args.json:
            _emit(payload)
            return
        print(f"路由条数: {len(routes)}")
        if amb:
            print("⚠ 歧义关键词:")
            for k, v in amb.items():
                print(f"  `{k}` → 行 {v}")


def cmd_get(args):
    root = _resolve_root(args)
    full = repo.resolve_in_root(root, args.path)  # 路径围栏:拒绝 '../' 穿越与越界绝对路径
    if not full:
        sys.stderr.write(f"错误:路径越界或非法 {args.path}\n")
        sys.exit(2)
    if not os.path.isfile(full):
        sys.stderr.write(f"错误:文件不存在 {args.path}\n")
        sys.exit(1)
    meta, body, _ = frontmatter.read_page(full)
    if args.json:
        _emit({"path": args.path, "frontmatter": meta, "body": body})
        return
    print(f"--- {args.path} ---")
    for k, v in meta.items():
        print(f"{k}: {v}")
    print("---")
    print(body)


def cmd_validate(args):
    root = _resolve_root(args)
    vocab = load_vocab(root)
    full = repo.resolve_in_root(root, args.path)  # 路径围栏
    if not full:
        sys.stderr.write(f"错误:路径越界或非法 {args.path}\n")
        sys.exit(2)
    if not os.path.isfile(full):
        sys.stderr.write(f"错误:文件不存在 {args.path}\n")
        sys.exit(1)
    meta, _, has_fm = frontmatter.read_page(full)
    # full 已被 resolve_in_root 经 os.path.realpath 解析(macOS 下 /tmp→/private/tmp);
    # rel_path 的基准 root 也要 realpath,否则算出 ../../private/var 长串。
    issues = validate_mod.validate_page(meta, has_fm, repo.rel_path(os.path.realpath(root), full), vocab)
    if args.json:
        _emit({"path": args.path, "issues": issues})
    else:
        _print_issues(issues)
    sys.exit(1 if any(i["level"] == "error" for i in issues) else 0)


def cmd_lint(args):
    root = _resolve_root(args)
    vocab = load_vocab(root)
    if args.staged or args.files:
        files = args.files or _staged_md_files(root)
        report = lint_mod.lint_files(root, files, vocab)
    else:
        report = lint_mod.lint(root, vocab)
    if args.json:
        _emit(report)
    else:
        _print_report(report)
    if args.out:
        _write_report_md(report, args.out)
        if not args.json:
            print(f"\n报告已写入 {args.out}")
    sys.exit(1 if report["summary"]["errors"] > 0 else 0)


def cmd_suggest(args):
    root = _resolve_root(args)
    vocab = load_vocab(root)
    text = args.text or sys.stdin.read()
    res = suggest_mod.suggest_path(text, vocab, root)
    if args.json:
        _emit(res)
        return
    print(f"建议落位: {res['suggested_path']}")
    print(f"domain={res['domain'] or '(staging)'}  page_type={res['page_type']}  confidence={res['confidence']}")
    if res["reasons"]:
        print("依据:")
        for r in res["reasons"]:
            print(f"  - {r}")


def cmd_scan(args):
    root = _resolve_root(args)
    vocab = load_vocab(root)
    # 文本模式:对一段传入文本(--text 或 stdin)做敏感度扫描,不扫全库。
    # 入库前先过敏感闸常用此路径(配合 _vocabulary.md 的 sensitivity_rules)。
    text = getattr(args, "text", None)
    if text is not None:
        if text == "-" or text == "":
            text = sys.stdin.read()
        res = sens_mod.scan_text(text, vocab)
        if args.json:
            _emit(res)
        else:
            kinds = ",".join(k for k, v in res["hits"].items() if v) or "-"
            flag = "🔴" if res["any_hit"] else "·"
            print(f"{flag} any_hit={res['any_hit']}  建议={res['suggested']}  命中={kinds}")
            for k, v in res["hits"].items():
                if v:
                    print(f"   {k}: {', '.join(v)}")
        return
    # 安全审计【默认覆盖 archive/log/revisions】(spec §3.1 点名的永久固化泄密点);--no-archive 才退回 active
    include_archive = not args.no_archive
    report = sens_mod.scan_repo(root, vocab, include_archive=include_archive)
    cover = "全库(含 archive/根级)" if include_archive else "仅 active 区"
    if args.json:
        report["coverage"] = cover
        _emit(report)
    else:
        print(f"扫描范围:{cover}")
        print(f"扫描完成:{report['total_findings']} 条 finding,其中 {report['risky_count']} 条高风险(命中敏感且声明不足)\n")
        for f in report["findings"]:
            flag = "🔴" if (f["any_hit"] and (f["under_declared"] or not f["declared"])) else "·"
            kinds = ",".join(k for k, v in f["hits"].items() if v) or "-"
            print(f"{flag} {f['path']}  声明={f['declared'] or '无'} 建议={f['suggested']} 命中={kinds}")
    if args.out:
        _write_scan_md(report, args.out, root)
        if not args.json:
            print(f"\n审计报告已写入 {args.out}")


def cmd_publish(args):
    root = _resolve_root(args)
    vocab = load_vocab(root)
    if not args.out:
        # 仅规划(dry-run)
        p = publish_mod.plan(root, vocab, include_archive=True)
        if args.json:
            _emit(p)
            return
        print(f"将导出 {len(p['included'])} 页;排除 {len(p['excluded'])} 页;风险 {len(p['risky'])} 页")
        if p["risky"]:
            print("🔴 风险(命中敏感且声明不足,导出前必须裁定 sensitivity):")
            for r in p["risky"]:
                print(f"   - {r}")
        print("加 --out <目录> 执行导出(有风险页会被阻断,除非 --force)")
        return
    res = publish_mod.export(root, args.out, vocab, include_archive=True, force=args.force)
    if args.json:
        _emit(res)
        return
    if not res["ok"]:
        print(f"❌ 导出被阻断:{res['reason']}")
        for r in res["risky"]:
            print(f"   🔴 {r}")
        sys.exit(1)
    print(f"✅ 已导出 {res['copied']} 页 + {len(res['infra'])} 个协议文件 → {res['out']}")
    print(f"   排除 {len(res['excluded'])} 页(maintainer-only/exclude/无声明/publish:false 域)")


# ---------- 输出辅助 ----------

def _print_issues(issues: List[Dict[str, str]]):
    if not issues:
        print("✅ 无问题")
        return
    for i in issues:
        mark = "❌" if i["level"] == "error" else "⚠️"
        loc = f" [{i['path']}]" if i.get("path") else ""
        print(f"{mark} {i['code']}: {i['msg']}{loc}")


def _print_report(report: Dict[str, Any]):
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


def _write_report_md(report: Dict[str, Any], out: str):
    s = report["summary"]
    lines = [f"# wiki lint 报告", "",
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


def _write_scan_md(report: Dict[str, Any], out: str, root: str):
    lines = ["# wiki 安全审计报告(敏感度扫描)", "",
             f"- wiki 根: `{root}`",
             f"- finding 总数: {report['total_findings']}  高风险: {report['risky_count']}",
             "",
             "> 高风险 = 命中敏感关键词且声明不足。`git init` 前必须逐条裁定 sensitivity。", "",
             "| 风险 | 路径 | 声明 | 建议 | 命中 |", "|---|---|---|---|---|"]
    for f in report["findings"]:
        risky = f["any_hit"] and (f["under_declared"] or not f["declared"])
        flag = "🔴" if risky else "·"
        kinds = "<br>".join(f"{k}: {', '.join(v)}" for k, v in f["hits"].items() if v) or "-"
        lines.append(f"| {flag} | `{f['path']}` | {f['declared'] or '无'} | {f['suggested']} | {kinds} |")
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _staged_md_files(root: str) -> List[str]:
    import subprocess
    try:
        res = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only", "--diff-filter=ACM"],
                             capture_output=True, text=True, timeout=5)
        return [os.path.join(root, p) for p in res.stdout.splitlines() if p.endswith(".md")]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def cmd_sync_team(args):
    """sync-team:把团队仓知识镜像同步到个人库 team/ 区(写子命令,含写副作用)。"""
    root = _resolve_root(args)  # 个人库(同步目标)
    res = sync_mod.sync_team(root, args.team, do_pull=args.pull, dry_run=args.dry_run)
    if args.json:
        _emit(res)
        sys.exit(0 if res.get("ok") else 1)
    print(sync_mod.format_text(res))
    if not res.get("ok"):
        sys.exit(1)


# ---------- argparse ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki", description="LLM Wiki 治理工具(读写:检索/校验只读,init/new/sync-team/publish 写盘)")
    p.add_argument("--root", help="wiki 根路径(默认自动发现 / $WIKI_ROOT / ~/AI/wiki)")
    p.add_argument("--json", action="store_true", help="JSON 输出")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("init", help="建库 / 层级修复(幂等,可多次执行:缺啥补啥,不覆盖已有)")
    sp.add_argument("dir", help="目标目录(空=新建;已存在=补全缺失结构)")
    sp.add_argument("--domains", help="逗号分隔的初始 domain,如 backend,frontend,ops(仅新建 _vocabulary.md 时生效)")
    sp.add_argument("--owner", help="domain owner 名(默认 UNASSIGNED)")
    sp.add_argument("--profile", choices=["standard", "minimal"], default="standard",
                    help="minimal:sensitivity 不必填(团队还没敏感数据时更轻)")
    sp.add_argument("--check", action="store_true", help="只检查结构是否完整,不写盘(结构健康检查)")
    sp.set_defaults(func=cmd_init)

    sp = sub.add_parser("new", help="轻量新建一页合规骨架(已知归属时;含写副作用)")
    sp.add_argument("type", help="页面类型:concept/entity/query/source/module")
    sp.add_argument("slug", help="kebab-case 文件名(模块用 <id>-<名>)")
    sp.add_argument("--domain", required=True, help="所属 domain(须已在 _vocabulary.md 登记)")
    sp.add_argument("--title", help="页面标题(默认用 slug)")
    sp.add_argument("--sensitivity", default="team", help="敏感度,默认 team")
    sp.set_defaults(func=cmd_new)

    sp = sub.add_parser("changes", help="检查团队仓有哪些待更新知识(只读:git fetch+diff,不自动应用)")
    sp.add_argument("--no-fetch", action="store_true", help="不联网 fetch,基于上次同步比较")
    sp.set_defaults(func=cmd_changes)

    sp = sub.add_parser("sync-team", help="把团队仓知识镜像同步到个人库 team/ 区(增量;含写副作用)")
    sp.add_argument("--team", required=True, help="团队仓本地 clone 路径(独立 git 仓,知识源)")
    sp.add_argument("--pull", action="store_true", help="同步前先对团队仓 git pull --ff-only 拿最新")
    sp.add_argument("--dry-run", action="store_true", help="只预览将同步什么,不写盘")
    sp.set_defaults(func=cmd_sync_team)

    sp = sub.add_parser("protocol", help="协议版本 + 分支/版本 + 新鲜度 + 闭集")
    sp.set_defaults(func=cmd_protocol)

    sp = sub.add_parser("search", help="全文/关键词检索")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--archive", action="store_true")
    sp.set_defaults(func=cmd_search)

    sp = sub.add_parser("route", help="路由解析 / 歧义")
    sp.add_argument("keyword", nargs="?")
    sp.set_defaults(func=cmd_route)

    sp = sub.add_parser("get", help="取页内容 + frontmatter")
    sp.add_argument("path", help="相对 wiki 根的路径")
    sp.set_defaults(func=cmd_get)

    sp = sub.add_parser("validate", help="单页 frontmatter 校验")
    sp.add_argument("path")
    sp.set_defaults(func=cmd_validate)

    sp = sub.add_parser("lint", help="全库体检 / --staged 增量")
    sp.add_argument("--staged", action="store_true", help="只校验 git 暂存的 .md(供 pre-commit)")
    sp.add_argument("--files", nargs="*", help="指定文件")
    sp.add_argument("--out", help="把报告写到指定 md 路径(revisions/)")
    sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("suggest", help="入库落位建议(domain/type/slug)")
    sp.add_argument("text", nargs="?", help="资料摘要(省略则读 stdin)")
    sp.set_defaults(func=cmd_suggest)

    sp = sub.add_parser("scan", help="敏感度扫描(secret/客户名/攻击面;默认含 archive;--text 扫单段文本)")
    sp.add_argument("--no-archive", action="store_true", help="只扫 active 区(默认含 archive/log/revisions)")
    sp.add_argument("--text", help="只扫这段文本(入库前过敏感闸;传 '-' 或留空读 stdin),不扫全库")
    sp.add_argument("--out", help="把审计报告写到指定 md 路径")
    sp.set_defaults(func=cmd_scan)

    sp = sub.add_parser("publish", help="脱敏白名单导出团队仓(只导 sensitivity<=team;含写副作用)")
    sp.add_argument("--out", help="导出目标目录(省略=dry-run 仅规划)")
    sp.add_argument("--force", action="store_true", help="即使有风险页也强制导出(不建议)")
    sp.set_defaults(func=cmd_publish)

    return p


def main(argv: List[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0
