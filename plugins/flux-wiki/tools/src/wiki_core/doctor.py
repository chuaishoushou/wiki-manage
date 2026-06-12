"""doctor / context:运行时巡检与会话入口(确定性,零 LLM)。

为什么存在:安装时校验挡不住安装后的漂移——团队仓被上游 reset 导致配置路径蒸发、
水位 commit 孤儿化、个人库被移动……这些都实际发生过,且一旦发生会污染所有平台的
指针。v4 的指针/skill 全部零路径,路径只活在 ~/.flux-wiki.json 一处,
doctor 负责在「用的时候」把漂移当场炸出来并给修复命令,而不是静默烂着。

- context:AI 会话首次涉及知识库时跑,拿当前路径/约定(取代把路径烤死进部署物)。
- doctor:逐项体检,error 退出非 0;--quick 供 SessionStart hook——
  全绿零输出零打扰,有问题才说话,自身永远 exit 0(hook 不能因此卡会话)。
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from . import learn as learn_mod, repo

MARK_BEGIN = "# === flux-wiki begin (auto by wiki-manage, 重装会整段替换) ==="

# 本文件位于 <wiki-manage>/plugins/flux-wiki/tools/src/wiki_core/doctor.py
SELF_MANAGE_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "..", "..", "..", "..", ".."))


def _item(level: str, code: str, msg: str, fix: str = "") -> Dict[str, str]:
    return {"level": level, "code": code, "msg": msg, "fix": fix}


def _pointer_stale(deployed_text: str) -> bool:
    """已装指针块正文是否落后于仓内 adapters/pointer-body.md(措辞改版检测)。
    比对失败(模板缺失等)按未过期处理——这是增强检测,不能自己制造误报。"""
    tpl = os.path.join(SELF_MANAGE_ROOT, "adapters", "pointer-body.md")
    try:
        with open(tpl, "r", encoding="utf-8") as f:
            expect = f.read().strip()
        _, _, rest = deployed_text.partition(MARK_BEGIN)
        block, _, _ = rest.partition("# === flux-wiki end ===")
        return block.strip() != expect
    except OSError:
        return False


def _check_personal(cfg: Dict[str, Any], items: List[Dict[str, str]]) -> Optional[str]:
    personal = cfg.get("personal_root")
    if not personal:
        items.append(_item("error", "no-personal-root",
                           "配置缺 personal_root(没装过或配置损坏)",
                           "重跑 wiki-manage 安装:cd <wiki-manage> && ./install.sh"))
        return None
    p = os.path.abspath(os.path.expanduser(personal))
    if not os.path.isdir(p) or not any(os.path.isfile(os.path.join(p, m))
                                       for m in repo.ROOT_MARKERS):
        items.append(_item("error", "personal-root-invalid",
                           f"个人库路径无效(缺 AGENTS.md 等标记): {p}",
                           "库被移动了?wiki-cli config set personal_root <新路径>;"
                           f"或重跑 {SELF_MANAGE_ROOT}/install.sh"))
        return None
    items.append(_item("ok", "personal-root", f"个人库: {p}"))
    return p


def _check_manage(cfg: Dict[str, Any], items: List[Dict[str, str]]):
    mng = cfg.get("wiki_manage")
    if not mng:
        items.append(_item("warn", "no-wiki-manage", "配置缺 wiki_manage(老版本配置?)",
                           "重跑安装可补齐"))
        return
    mng = os.path.abspath(os.path.expanduser(mng))
    cli = os.path.join(mng, "plugins", "flux-wiki", "tools", "bin", "wiki-cli")
    if not os.path.isfile(cli):
        items.append(_item("error", "wiki-manage-missing",
                           f"配置指向的 wiki-manage 不存在或不完整: {mng}",
                           f"仓被移动/删除?在新位置重跑 ./install.sh(当前运行的是 {SELF_MANAGE_ROOT})"))
        return
    if os.path.realpath(mng) != os.path.realpath(SELF_MANAGE_ROOT):
        items.append(_item("warn", "wiki-manage-drift",
                           f"当前运行的 wiki-cli 不在配置指向的仓里"
                           f"(配置: {mng},运行: {SELF_MANAGE_ROOT})",
                           "存在两份 clone?以哪份为准就在哪份里重跑 ./install.sh"))
    else:
        items.append(_item("ok", "wiki-manage", f"wiki-manage: {mng}"))


def _check_teams(cfg: Dict[str, Any], personal: Optional[str], items: List[Dict[str, str]]):
    teams = repo.get_teams(cfg)
    if not teams:
        items.append(_item("warn", "no-teams", "未配置任何团队仓(learn 不可用)",
                           "wiki-cli config team <名> --path <路径> [--branch <分支>] 登记"))
        return
    state = learn_mod.load_state(personal) if personal else {}
    for t in teams:
        name, path = t["name"], t["path"]
        if not os.path.isdir(path):
            items.append(_item("error", "team-path-dead",
                               f"团队仓 {name} 路径不存在: {path}",
                               f"仓被移动/重构了?wiki-cli config team {name} --path <新路径>"))
            continue
        if not repo.is_git_repo(path):
            items.append(_item("error", "team-not-git",
                               f"团队仓 {name} 不是 git 仓: {path}",
                               f"确认这是团队知识仓的 clone;wiki-cli config team {name} --path <正确路径>"))
            continue
        branch, head = repo.git_head_info(path)
        if t["branch"] and branch and branch != t["branch"]:
            items.append(_item("warn", "team-branch-mismatch",
                               f"团队仓 {name} 当前检出 {branch},配置工作分支是 {t['branch']}"
                               "(可能拉到错误内容)",
                               f"git -C \"{path}\" switch {t['branch']}"))
        st = state.get(path) or {}
        wm = st.get("last_commit")
        if wm:
            if not repo.git_commit_exists(path, wm):
                items.append(_item("warn", "watermark-gone",
                                   f"团队仓 {name} 的学习水位 {wm[:9]} 已不存在"
                                   "(仓重建/已 gc);下次 learn 自动降级为全量列+已学跳过",
                                   "学习一轮后重新 --mark 即恢复"))
            elif head and repo.git_is_ancestor(path, wm, head) is False:
                items.append(_item("warn", "watermark-orphan",
                                   f"团队仓 {name} 的学习水位 {wm[:9]} 不在当前分支历史上"
                                   "(仓被 reset/rebase 过)",
                                   f"若水位上有本地未保全提交先钉住:git -C \"{path}\" "
                                   f"branch rescue/{wm[:9]} {wm[:9]};学习一轮后重新 --mark"))
            else:
                items.append(_item("ok", "team",
                                   f"团队仓 {name}: {path} @ {branch or '?'} 水位 {wm[:9]} ✓"))
        else:
            items.append(_item("ok", "team",
                               f"团队仓 {name}: {path} @ {branch or '?'}(还没学习过)"))
    # learn-state 里有、配置里没有的仓:孤儿水位(仓被移除/换名),提示而非报错
    cfg_paths = {t["path"] for t in teams}
    for key in (state or {}):
        if isinstance(state.get(key), dict) and key not in cfg_paths:
            items.append(_item("warn", "state-orphan",
                               f"learn-state 里有未登记团队仓的水位: {key}",
                               f"还在用就登记:wiki-cli config team <名> --path \"{key}\";"
                               "不用了可忽略(不影响其他仓)"))


def _check_manifest(cfg: Dict[str, Any], items: List[Dict[str, str]]):
    manifest = cfg.get("installed_files") or []
    if not manifest:
        items.append(_item("warn", "no-manifest",
                           "配置里没有安装清单(v4 之前装的?)",
                           "重跑 ./install.sh 生成 manifest(卸载/巡检都靠它)"))
        return
    for ent in manifest:
        if not isinstance(ent, dict):
            continue
        typ, path = ent.get("type"), os.path.expanduser(ent.get("path", ""))
        if typ == "block":
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()
                ok = MARK_BEGIN in text
            except OSError:
                ok, text = False, ""
            if not ok:
                items.append(_item("error", "pointer-missing",
                                   f"指针块丢失: {path}",
                                   f"重跑 {SELF_MANAGE_ROOT}/install.sh 恢复"))
            elif _pointer_stale(text):
                # 「git pull 即更新」的唯一例外是指针正文措辞改版——没人帮用户发现
                # 这个例外的话,三平台会静默跑旧指令;在这里把例外变成报警闭环。
                items.append(_item("warn", "pointer-stale",
                                   f"指针块措辞已过期(仓内 pointer-body.md 已更新): {path}",
                                   f"重跑 {SELF_MANAGE_ROOT}/install.sh(幂等,整段替换)"))
            else:
                items.append(_item("ok", "pointer", f"指针块在场: {path}"))
        elif typ == "link":
            if os.path.islink(path):
                if os.path.exists(path):
                    items.append(_item("ok", "link", f"链接有效: {path}"))
                else:
                    items.append(_item("error", "link-broken",
                                       f"链接目标丢失: {path} → {os.readlink(path)}",
                                       "wiki-manage 仓被移动?在新位置重跑 ./install.sh"))
            elif os.path.exists(path):
                items.append(_item("ok", "link", f"在场(copy 降级): {path}"))
            else:
                items.append(_item("error", "link-missing", f"部署物丢失: {path}",
                                   "重跑 ./install.sh 恢复"))
        elif typ in ("file", "copy"):
            if os.path.exists(path):
                items.append(_item("ok", typ, f"在场: {path}"))
            else:
                items.append(_item("warn", f"{typ}-missing", f"部署物丢失: {path}",
                                   "重跑 ./install.sh 恢复"))
        elif typ == "hook":
            try:
                import json as _json
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    has_hook = "doctor --quick" in f.read()
            except OSError:
                has_hook = False
            if has_hook:
                items.append(_item("ok", "hook", f"巡检 hook 在场: {path}"))
            else:
                items.append(_item("warn", "hook-missing",
                                   f"巡检 hook 丢失: {path}", "重跑 ./install.sh 恢复"))


def run(quick: bool = False) -> Dict[str, Any]:
    """全套巡检。返回 {items, errors, warns};quick 模式行为相同,差异在 CLI 呈现层。"""
    items: List[Dict[str, str]] = []
    cfg = repo.load_config()
    if not cfg:
        items.append(_item("error", "no-config",
                           f"配置文件不存在或损坏: {repo.CONFIG_PATH}",
                           "重跑 wiki-manage 安装:cd <wiki-manage> && ./install.sh"))
    else:
        personal = _check_personal(cfg, items)
        _check_manage(cfg, items)
        _check_teams(cfg, personal, items)
        _check_manifest(cfg, items)
    errors = sum(1 for i in items if i["level"] == "error")
    warns = sum(1 for i in items if i["level"] == "warn")
    return {"items": items, "errors": errors, "warns": warns}


def format_report(rep: Dict[str, Any], quick: bool = False) -> str:
    """quick:全绿返回空串(hook 零打扰);有问题只列问题项。常规:全量列出。"""
    mark = {"ok": "✅", "warn": "⚠", "error": "❌"}
    lines: List[str] = []
    for i in rep["items"]:
        if quick and i["level"] == "ok":
            continue
        lines.append(f"{mark.get(i['level'], '·')} {i['msg']}")
        if i["fix"] and i["level"] != "ok":
            lines.append(f"   ↳ 修复: {i['fix']}")
    has_fix = any(i["fix"] and i["level"] != "ok" for i in rep["items"])
    if quick:
        if not lines:
            return ""
        out = ["[flux-wiki doctor] 知识库环境有问题(不影响本会话,但 wiki 操作可能失败):", *lines]
        if has_fix:
            out.append("(修复命令里的 wiki-cli 不在 PATH 时,用 ~/.local/bin/wiki-cli)")
        return "\n".join(out)
    if has_fix:
        lines.append("(修复命令里的 wiki-cli 不在 PATH 时,用 ~/.local/bin/wiki-cli)")
    lines.append(f"\ndoctor: {rep['errors']} 错误 / {rep['warns']} 警告")
    return "\n".join(lines)


# ---------- context(会话运行时入口) ----------

def context_payload() -> Dict[str, Any]:
    cfg = repo.load_config()
    personal = cfg.get("personal_root")
    personal = os.path.abspath(os.path.expanduser(personal)) if personal else None
    valid = bool(personal and os.path.isdir(personal)
                 and any(os.path.isfile(os.path.join(personal, m)) for m in repo.ROOT_MARKERS))
    teams = []
    state = learn_mod.load_state(personal) if valid else {}
    for t in repo.get_teams(cfg):
        alive = os.path.isdir(t["path"]) and repo.is_git_repo(t["path"])
        branch, _ = repo.git_head_info(t["path"]) if alive else (None, None)
        st = state.get(t["path"]) or {}
        teams.append({**t, "alive": alive, "current_branch": branch,
                      "watermark": (st.get("last_commit") or "")[:12],
                      "marked_at": st.get("marked_at") or ""})
    content = repo.content_dir(personal) if valid else None
    return {
        "ok": valid,
        "personal_root": personal,
        "content_dir": content,
        "layout": ("v2-nested" if valid and repo.is_legacy_layout(personal) else
                   "v3-flat" if valid else None),
        "teams": teams,
        "wiki_manage": cfg.get("wiki_manage"),
        "config_path": repo.CONFIG_PATH,
    }


def format_context(ctx: Dict[str, Any]) -> str:
    if not ctx["ok"]:
        return (f"❌ 个人库未配置或路径失效(配置: {ctx['config_path']});"
                "跑 wiki-cli doctor 看原因,或重跑 wiki-manage 安装。")
    lines = [f"个人库  : {ctx['personal_root']}"
             f"({'v2 嵌套,写入层 = ' + ctx['content_dir'] if ctx['layout'] == 'v2-nested' else 'v3 扁平'})"]
    for t in ctx["teams"]:
        flag = "✅" if t["alive"] else "❌ 路径失效(doctor 看修复命令)"
        wm = f" 水位 {t['watermark']}" if t["watermark"] else "(未学习过)"
        br = t["current_branch"] or "?"
        warn = ""
        if t["alive"] and t["branch"] and t["current_branch"] and t["branch"] != t["current_branch"]:
            warn = f" ⚠ 检出 {t['current_branch']} ≠ 配置分支 {t['branch']}"
        lines.append(f"团队仓  : [{t['name']}] {t['path']} @ {br}{wm} {flag}{warn}")
    if not ctx["teams"]:
        lines.append("团队仓  : 未配置(wiki-cli config team <名> --path <路径> 登记)")
    lines.append("约定    : 记知识 → <写入层>/domains/<主题>/ 并在库根 log.md 追加一行;"
                 "删除 = mv 进 archive/,绝不 rm;raw/ 只读;协议真源 = 库根 AGENTS.md")
    lines.append("手册    : wiki-cli guide <ingest|learn|lint|query|help>(操作前先拿手册照做)")
    cli = os.path.join(SELF_MANAGE_ROOT, "plugins", "flux-wiki", "tools", "bin", "wiki-cli")
    lines.append(f"工具    : wiki-cli = ~/.local/bin/wiki-cli(不在 PATH 时)= python3 \"{cli}\"")
    return "\n".join(lines)
