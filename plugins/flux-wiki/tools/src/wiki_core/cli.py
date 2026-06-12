"""wiki-cli:命令行入口(wiki_core 的唯一入口)。

10 个子命令:
  init    建库 / 结构修复(幂等;--check 只体检结构)
  new     轻量新建一页骨架
  search  全文检索
  lint    体检(全库 / 指定文件 / --staged;全库文本模式自动落 revisions 审计)
  learn   团队仓增量学习数据(只读;--verify 核销;--mark 写水位,有核销门禁;--pull 先拉最新)
  status  当前库状态(根/布局/页数/主题/团队仓水位)  [别名 protocol]
  context 会话运行时入口:库位置/团队仓/约定速查(取代把路径烤死进部署物)
  doctor  环境巡检(死路径/孤儿水位/部署物缺失;error 退出非 0;--quick 供 hook,零打扰)
  guide   现读现发操作手册(learn/ingest/lint/query;三平台同一份流程)
  config  机器级配置读写(personal_root / 团队仓多仓登记)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List

from . import doctor as doctor_mod, guide as guide_mod, learn as learn_mod
from . import lint as lint_mod, repo
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


def _report_md_lines(report: Dict[str, Any]) -> List[str]:
    s = report["summary"]
    lines = [f"- 页数: {report.get('page_count', '?')}",
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
    return lines


def cmd_lint(args):
    root = _resolve_root(args)
    full_run = not (args.staged or args.paths)
    if full_run:
        report = lint_mod.lint(root)
    else:
        files = ([repo.resolve_in_root(root, p) or p for p in args.paths]
                 if args.paths else _staged_md_files(root))
        report = lint_mod.lint_files(root, [f for f in files if f])
    if args.json:
        _emit(report)
    else:
        _print_issues_sections(report)
    if args.out:
        _write_report_md(report, args.out)
        if not args.json:
            print(f"报告已写入 {args.out}")
    # 全库体检(文本模式)自动落审计:协议要求 lint 必生成 revisions,
    # 靠人自觉的时期审计链断过档,改由 CLI 在成功路径上代劳。
    # 只落到**配置的个人库**:--json 是程序化调用不落;--root 指向团队仓等
    # 外部库时也不落(团队 clone 约定只读,不能往人家工作树里写审计文件)。
    cfg_root = repo.load_config().get("personal_root")
    is_personal = bool(cfg_root and os.path.realpath(os.path.expanduser(cfg_root))
                       == os.path.realpath(root))
    if full_run and not args.json and is_personal:
        try:
            rev = repo.write_revision(root, "lint", _report_md_lines(report))
            print(f"审计已落 {repo.rel_path(root, rev)}")
        except OSError as e:
            sys.stderr.write(f"⚠ 审计文件写入失败: {e}\n")
    elif full_run and not args.json and cfg_root:
        print("(--root 非配置的个人库:按只读对待,不落审计文件)")
    sys.exit(1 if report["summary"]["errors"] > 0 else 0)


def _pick_team(args, teams_cfg: List[Dict[str, Any]], purpose: str) -> Dict[str, Any]:
    """--mark / 单仓操作的团队仓解析:--team 指定 > 唯一配置仓;多仓必须显式指定。"""
    team = repo.resolve_team(args.team, teams_cfg)
    if team:
        return team
    if len(teams_cfg) == 1:
        return teams_cfg[0]
    if not teams_cfg:
        sys.stderr.write(f"错误:{purpose} 需要团队仓。--team <路径> 指定,"
                         "或 wiki-cli config team <名> --path <路径> 登记。\n")
    else:
        names = ", ".join(t["name"] for t in teams_cfg)
        sys.stderr.write(f"错误:配置了多个团队仓({names}),{purpose} 必须 --team <名|路径> 指定。\n")
    sys.exit(2)


def cmd_learn(args):
    root = _resolve_root(args)
    teams_cfg = repo.get_teams()

    if args.mark:
        team = _pick_team(args, teams_cfg, "--mark")
        # 核销门禁:增量轮次里有未核销页(漏学/漏写溯源)时拒绝推水位——
        # 这是 learn 闭环唯一的机器强制点。首次学习是基线策展,允许选择性学,不阻塞。
        # verify 自身失败也拦(fail-closed):门禁验不了 ≠ 门禁通过,--force 可旁路。
        ver = learn_mod.verify(root, team["path"], exclude=team["exclude"],
                               branch_expect=team["branch"])
        gate_hit = (not args.force) and (
            not ver.get("ok")
            or (ver.get("unverified") and not ver.get("first_time")))
        if gate_hit:
            if args.json:
                _emit({"ok": False, "gate": "verify",
                       "reason": ver.get("reason") or "核销未过",
                       "unverified": ver.get("unverified", [])})
            else:
                print(learn_mod.format_verify(ver))
                sys.stderr.write("❌ 核销未过(或无法核销),拒绝 --mark"
                                 "(补学,或确认放弃后加 --force)。\n")
            sys.exit(1)
        res = learn_mod.mark(root, team["path"], args.mark)
        if not res.get("ok"):
            if args.json:
                _emit(res)
            else:
                sys.stderr.write(f"错误:{res['reason']}\n")
            sys.exit(2)
        # 审计:每次推水位强制落 revisions(verify 结果一并入档,可追溯学了什么/放弃了什么);
        # 审计失败不连累已成功的主操作,降级为警告。
        lines = [f"- 团队仓: [{team['name']}] {res['team_root']}",
                 f"- 水位: {ver.get('since') or '(首次)'} → {res['last_commit']}",
                 f"- 核销: ✅ {len(ver.get('verified') or [])} 页"
                 f" / ❌ {len(ver.get('unverified') or [])} 页"
                 f" / 分流 {ver.get('excluded_count', 0)} 页"]
        if ver.get("unverified"):
            lines.append("- ⚠ --force 放弃页(原因应记入 log.md):")
            lines.extend(f"  - [{p['status']}] {p['team_rel']}" for p in ver["unverified"])
        rev = None
        try:
            rev = repo.write_revision(root, "learn", lines)
        except OSError as e:
            sys.stderr.write(f"⚠ 审计文件写入失败(水位已记录): {e}\n")
        if args.json:
            _emit({**res, "revision": repo.rel_path(root, rev) if rev else None})
            return
        print(f"✅ 已记录学习水位: {res['last_commit'][:12]}(团队仓 {res['team_root']})")
        if rev:
            print(f"审计已落 {repo.rel_path(root, rev)}")
        return

    if args.verify:
        targets = [repo.resolve_team(args.team, teams_cfg)] if args.team else teams_cfg
        targets = [t for t in targets if t]
        if not targets:
            sys.stderr.write("错误:未配置团队仓(--team 或 config team 登记)。\n")
            sys.exit(2)
        results = [learn_mod.verify(root, t["path"], exclude=t["exclude"],
                                    branch_expect=t["branch"]) for t in targets]
        if args.json:
            _emit(results[0] if len(results) == 1 else
                  {"ok": all(r.get("ok") for r in results), "teams": results})
        else:
            print("\n\n".join(learn_mod.format_verify(r) for r in results))
        bad = any(r.get("ok") and r.get("unverified") and not r.get("first_time")
                  for r in results) or any(not r.get("ok") for r in results)
        sys.exit(1 if bad else 0)

    # 增量清单:--team 指定单仓;否则遍历全部配置仓
    targets = [repo.resolve_team(args.team, teams_cfg)] if args.team else teams_cfg
    targets = [t for t in targets if t]
    if not targets:
        res = learn_mod.diff(root, None)  # 复用统一报错文案
        if args.json:
            _emit(res)
        else:
            print(learn_mod.format_text(res))
        sys.exit(1)
    results = []
    for t in targets:
        results.append(learn_mod.diff(root, t["path"], do_pull=args.pull,
                                      exclude=t["exclude"], branch_expect=t["branch"],
                                      include_excluded=args.all))
    if args.json:
        _emit(results[0] if len(results) == 1 else
              {"ok": all(r.get("ok") for r in results), "teams": results})
        sys.exit(0 if all(r.get("ok") for r in results) else 1)
    print("\n\n".join(learn_mod.format_text(r) for r in results))
    if not all(r.get("ok") for r in results):
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
    teams = repo.get_teams(cfg)
    state = learn_mod.load_state(root)
    # 水位按团队仓多键存储(--team 学过的也在);全部列出,配置仓标注
    cfg_paths = {t["path"] for t in teams}
    learn_states = [{"team_root": k, "last_commit": v.get("last_commit"),
                     "marked_at": v.get("marked_at"), "is_default": (k in cfg_paths)}
                    for k, v in sorted(state.items()) if isinstance(v, dict)]
    first_state = state.get(teams[0]["path"], {}) if teams else {}
    payload = {
        "root": root,
        "root_source": source,
        "layout": "v2-nested" if legacy else "v3-flat",
        "tool_protocol_version": SUPPORTED_PROTOCOL_VERSION,
        "page_count": page_count,
        "domains": domains,
        "teams": [{**t, "exists": os.path.isdir(t["path"])} for t in teams],
        # v1 字段保留(单仓时等价;多仓取第一个),老调用方不破
        "team_root": teams[0]["path"] if teams else None,
        "team_root_exists": bool(teams and os.path.isdir(teams[0]["path"])),
        "learn_last_commit": first_state.get("last_commit"),
        "learn_marked_at": first_state.get("marked_at"),
        "learn_states": learn_states,
    }
    if args.json:
        _emit(payload)
        return
    src_label = {"start": "--root 参数", "env": "$WIKI_ROOT", "config": f"配置 {repo.CONFIG_PATH}",
                 "cwd": "从当前目录上溯"}.get(source, source)
    legacy_ack = legacy and os.path.isfile(os.path.join(root, ".wiki", "ack-legacy-layout"))
    layout_label = ("v2 嵌套(已确认保留)" if legacy_ack
                    else "⚠ v2 嵌套(建议迁 v3,见 docs/INSTALL.md)" if legacy else "v3 扁平 ✅")
    print(f"wiki 根 : {root}  (来源: {src_label})")
    print(f"布局    : {layout_label}")
    print(f"页数    : {page_count}  主题: {', '.join(domains) or '(无)'}")
    if teams:
        for t in payload["teams"]:
            mark = "✅" if t["exists"] else "❌ 路径不存在(doctor 看修复命令)"
            br = f" @ {t['branch']}" if t["branch"] else ""
            print(f"团队仓  : [{t['name']}] {t['path']}{br} {mark}")
    else:
        print("团队仓  : 未配置(wiki-cli config team <名> --path <路径> 登记)")
    shown = False
    for st in learn_states:
        wm = st["last_commit"] or "?"
        tag = "" if st["is_default"] else "(未登记仓)"
        print(f"学习水位: {wm[:12]}  @ {st['marked_at'] or ''}  {st['team_root']}{tag}")
        shown = True
    if teams and not shown:
        print("学习水位: (还没学习过;跑 /wiki-learn 或 wiki-cli guide learn)")


def cmd_context(args):
    ctx = doctor_mod.context_payload()
    if args.json:
        _emit(ctx)
    else:
        print(doctor_mod.format_context(ctx))
    sys.exit(0 if ctx["ok"] else 1)


def cmd_doctor(args):
    rep = doctor_mod.run(quick=args.quick)
    if args.json:
        _emit(rep)
        sys.exit(0 if args.quick else (1 if rep["errors"] else 0))
    out = doctor_mod.format_report(rep, quick=args.quick)
    if out:
        print(out)
    # --quick 是 hook 模式:永远 exit 0(环境问题不该卡住会话本身),全绿零输出
    sys.exit(0 if args.quick else (1 if rep["errors"] else 0))


def cmd_guide(args):
    # 库未配置/路径失效时必须硬失败:rc=0 渲染哨兵或死路径的手册,会让照手册
    # 写盘的 AI 在错误位置静默重建骨架,而 skill 的「手册拿不到→跑 doctor」
    # 安全网永远不会触发。让"拿不到"真的发生。
    root, source = repo.find_wiki_root_verbose(getattr(args, "root", None))
    if not root:
        sys.stderr.write("错误:个人库未配置或路径已失效(来源: %s)。\n"
                         "  先跑 wiki-cli doctor 看原因并按修复命令处理;"
                         "手册里的路径不可信,不要凭猜测写盘。\n" % source)
        sys.exit(2)
    text = guide_mod.render(args.op, root)
    if text is None:
        ops = ", ".join(guide_mod.available()) or "(playbooks 目录缺失)"
        sys.stderr.write(f"错误:没有 `{args.op}` 手册。可用: {ops}\n")
        sys.exit(2)
    print(text)


def cmd_config(args):
    if args.action == "get":
        cfg = repo.load_config()
        if args.key:
            val = cfg.get(args.key)
            print(json.dumps(val, ensure_ascii=False, indent=2) if isinstance(val, (dict, list))
                  else ("" if val is None else str(val)))
        else:
            _emit(cfg)
        return
    if args.action == "set":
        allowed = ("personal_root", "wiki_manage")
        if args.key not in allowed:
            sys.stderr.write(f"错误:config set 只支持 {allowed};团队仓用 config team。\n")
            sys.exit(2)
        val = os.path.abspath(os.path.expanduser(args.value))
        if args.key == "personal_root" and not any(
                os.path.isfile(os.path.join(val, m)) for m in repo.ROOT_MARKERS):
            sys.stderr.write(f"错误:{val} 不是有效 wiki 根(缺 AGENTS.md 等标记)。\n")
            sys.exit(2)
        repo.save_config({args.key: val})
        print(f"✅ {args.key} = {val}")
        return
    if args.action == "team":
        if args.remove:
            ok = repo.remove_team(args.name)
            print(f"✅ 已移除团队仓 {args.name}" if ok else f"⚠ 没有名为 {args.name} 的团队仓")
            sys.exit(0 if ok else 1)
        path = args.path
        if path:
            ab = os.path.abspath(os.path.expanduser(path))
            if not os.path.isdir(ab) or not repo.is_git_repo(ab):
                sys.stderr.write(f"错误:{ab} 不存在或不是 git 仓(团队仓必须是 git clone)。\n")
                sys.exit(2)
        exclude = ([e.strip() for e in args.exclude.split(",") if e.strip()]
                   if args.exclude is not None else None)
        try:
            hit = repo.upsert_team(args.name, path=path, branch=args.branch, exclude=exclude)
        except ValueError as e:
            sys.stderr.write(f"错误:{e}\n")
            sys.exit(2)
        print(f"✅ 团队仓 [{hit['name']}] {hit.get('path')}"
              + (f" @ {hit['branch']}" if hit.get("branch") else "")
              + (f"  exclude: {hit['exclude']}" if hit.get("exclude") else ""))


# ---------- 辅助 ----------

def _staged_md_files(root: str) -> List[str]:
    import subprocess
    try:
        # --relative:root 是大仓子目录时,输出路径相对 root(否则相对仓根,
        # join 后路径错位,--staged 静默检查不到任何文件恒通过)
        res = subprocess.run(["git", "-C", root, "diff", "--cached", "--name-only",
                              "--relative", "--diff-filter=ACM"],
                             capture_output=True, text=True, timeout=5)
        return [os.path.join(root, p) for p in res.stdout.splitlines() if p.endswith(".md")]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def _write_report_md(report: Dict[str, Any], out: str):
    lines = ["# wiki lint 报告", ""] + _report_md_lines(report)
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------- argparse ----------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="wiki-cli",
                                description="轻量个人知识库工具"
                                            "(init/new/search/lint/learn/status/context/doctor/guide/config)")
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

    sp = sub.add_parser("lint", help="体检(全库;或指定文件;--staged 检查 git 暂存页,可挂 pre-commit hook)")
    sp.add_argument("paths", nargs="*", help="只检查这些文件(相对库根)")
    sp.add_argument("--staged", action="store_true", help="只检查 git 暂存的 .md")
    sp.add_argument("--out", help="把报告写到指定 md 路径(建议 .wiki/reports/)")
    sp.set_defaults(func=cmd_lint)

    sp = sub.add_parser("learn", help="团队仓增量学习数据(按 git 水位;--verify 核销;--mark 记水位)")
    sp.add_argument("--team", help="团队仓(配置名或路径;默认遍历全部配置仓)")
    sp.add_argument("--pull", action="store_true",
                    help="先对团队仓 git pull --ff-only(唯一会动团队仓的操作,只快进不合并)")
    sp.add_argument("--all", action="store_true", help="连 exclude 分流掉的页一起列")
    sp.add_argument("--verify", action="store_true", help="核销检查:待学清单是否都已带 learned_from 落库")
    sp.add_argument("--mark", metavar="COMMIT", help="记录学习水位(学习完成后调用;有核销门禁)")
    sp.add_argument("--force", action="store_true", help="核销未过仍强制 --mark(放弃页记入审计)")
    sp.set_defaults(func=cmd_learn)

    sp = sub.add_parser("status", aliases=["protocol"], help="当前库状态(根/布局/页数/主题/团队仓水位)")
    sp.set_defaults(func=cmd_status)

    sp = sub.add_parser("context", help="会话运行时入口:库位置/团队仓/约定速查")
    sp.set_defaults(func=cmd_context)

    sp = sub.add_parser("doctor", help="环境巡检(死路径/孤儿水位/部署物;error 退出非 0)")
    sp.add_argument("--quick", action="store_true",
                    help="hook 模式:全绿零输出,有问题列出来;自身永远 exit 0")
    sp.set_defaults(func=cmd_doctor)

    sp = sub.add_parser("guide", help="打印操作手册(learn/ingest/lint/query),照做即可")
    sp.add_argument("op", help="learn / ingest / lint / query / help")
    sp.set_defaults(func=cmd_guide)

    sp = sub.add_parser("config", help="机器级配置(~/.flux-wiki.json)读写")
    csub = sp.add_subparsers(dest="action", required=True)
    g = csub.add_parser("get", parents=[common], help="读配置(全部或单键)")
    g.add_argument("key", nargs="?")
    s = csub.add_parser("set", parents=[common], help="改顶层路径键(personal_root / wiki_manage)")
    s.add_argument("key")
    s.add_argument("value")
    t = csub.add_parser("team", parents=[common], help="登记/更新/移除团队仓(多仓)")
    t.add_argument("name", help="团队仓名(自定,如 global / tm03)")
    t.add_argument("--path", help="本地 clone 路径(必须已存在且是 git 仓)")
    t.add_argument("--branch", help="工作分支(检出分支不一致时 learn/doctor 会警告)")
    t.add_argument("--exclude", help="逗号分隔 glob(如 knowledge/database/**,openspec/changes/archive/**)")
    t.add_argument("--remove", action="store_true", help="移除该团队仓登记")
    sp.set_defaults(func=cmd_config)

    return p


def main(argv: List[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)
    return 0
