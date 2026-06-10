"""learn:团队仓 → 个人库 增量学习的确定性数据层。

分工(轻量化边界):
- CLI(本模块)只做确定性部分:按 git 水位算增量、给出每页的来源/状态/历史落点、记录水位。
- 分类与改写是 AI 的活(/wiki-learn 命令):AI 读团队页原文,决定落进个人库哪个 domain,
  写盘时带溯源 frontmatter(learned_from / learned_commit)。
- 水位只有一个 commit 字段,存 <个人库>/.wiki/learn-state.json;不做定时、不做自动合并。

"上次学到哪"之外的状态不另造:已学页靠其 frontmatter 的 learned_from 字段逆查,
所以即使水位丢失,重学也只是多看几页,不会重复落盘到未知位置。
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import frontmatter, repo

STATE_REL = os.path.join(".wiki", "learn-state.json")


def _state_path(personal_root: str) -> str:
    return os.path.join(personal_root, STATE_REL)


def load_state(personal_root: str) -> Dict[str, Any]:
    try:
        with open(_state_path(personal_root), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def mark(personal_root: str, team_root: str, commit: str) -> Dict[str, Any]:
    """写回学习水位(team_root 维度;支持多个团队仓互不干扰)。"""
    team_key = os.path.abspath(os.path.expanduser(team_root))
    state = load_state(personal_root)
    state[team_key] = {"last_commit": commit,
                       "marked_at": datetime.now().isoformat(timespec="seconds")}
    p = _state_path(personal_root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"ok": True, "team_root": team_key, "last_commit": commit}


def find_learned(personal_root: str) -> Dict[str, str]:
    """逆查已学页:团队仓内相对路径 -> 个人库内相对路径(读各页 frontmatter learned_from)。"""
    out: Dict[str, str] = {}
    for path in repo.iter_pages(personal_root):
        try:
            meta, _, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        src = meta.get("learned_from") if has_fm else None
        if src and isinstance(src, str):
            out[src.replace("\\", "/")] = repo.rel_path(personal_root, path)
    return out


# 库的协议/导航/台账文件:是基础设施不是知识,学习时不列
_INFRA_FILES = {"AGENTS.md", "_routes.md", "_vocabulary.md", "overview.md", "log.md", "README.md"}


def _is_knowledge_page(rel: str) -> bool:
    """git 变更路径过滤:只关心知识页(.md,且不在排除目录/归档/模板里,非顶层协议文件)。"""
    if not rel.endswith(".md"):
        return False
    parts = rel.replace("\\", "/").split("/")
    # 顶层(库根或 wiki/ 内容层根)的协议/导航文件不算知识页;domain 内的 overview/README 算
    if parts[-1] in _INFRA_FILES and len([p for p in parts if p != "wiki"]) == 1:
        return False
    skip = set(repo.EXCLUDE_DIRS) | {"archive", "templates"}
    return not any(p in skip for p in parts)


def diff(personal_root: str, team_root: Optional[str], do_pull: bool = False) -> Dict[str, Any]:
    """算"自上次学习以来,团队仓有哪些知识页变了"(只读;--pull 例外,见下)。

    返回结构化报告:
      head/branch        团队仓当前位置
      since              本次比较的水位(None = 首次学习,列出全部现存页)
      pages: [{status(A/M/D/R), team_rel, abs(D 无), previous(个人库已学落点或 None)}]
      commits            水位以来的提交标题(供 AI 理解改动意图)
    """
    if not team_root:
        return {"ok": False, "reason": "未配置团队仓。安装时用 --team-root 指定,"
                                       "或本次显式传 --team <团队仓路径>。"}
    team_root = os.path.abspath(os.path.expanduser(team_root))
    if not os.path.isdir(team_root):
        return {"ok": False, "reason": f"团队仓路径不存在: {team_root}"}

    pull_note = ""
    if do_pull:
        ok, msg = repo.git_pull(team_root)
        pull_note = f"git pull --ff-only: {'✅' if ok else '⚠'} {msg}"

    branch, head = repo.git_head_info(team_root)
    if head is None:
        return {"ok": False, "reason": f"团队仓不是 git 仓(无提交记录可读): {team_root}。"
                                       "学习依赖 git 提交记录,请确认这是团队知识仓的 clone。"}

    learned = find_learned(personal_root)
    team_content = repo.content_dir(team_root)

    state = load_state(personal_root).get(team_root, {})
    since = state.get("last_commit")
    note = ""
    if since and not repo.git_commit_exists(team_root, since):
        note = f"上次水位 {since[:9]} 已不在团队仓历史中(可能重建过),按首次学习处理"
        since = None

    pages: List[Dict[str, Any]] = []
    if since:
        if since == head:
            changes: List = []
        else:
            changes = repo.git_diff_name_status(team_root, since)
            if changes is None:
                return {"ok": False, "reason": f"git diff {since[:9]}..HEAD 失败,无法计算增量"}
        for status, rel in changes:
            if not _is_knowledge_page(rel):
                continue
            rel_norm = rel.replace("\\", "/")
            ab = os.path.join(team_root, rel)
            pages.append({
                "status": status[0],
                "team_rel": rel_norm,
                "abs": ab if os.path.isfile(ab) else None,
                "previous": learned.get(rel_norm)
                            or learned.get(os.path.relpath(ab, team_content).replace("\\", "/")
                                           if os.path.isfile(ab) else rel_norm),
            })
        commits = repo.git_log_subjects(team_root, since)
    else:
        # 首次学习(或水位失效):列出团队仓现存全部知识页
        for ab in repo.iter_pages(team_root):
            rel_norm = os.path.relpath(ab, team_root).replace("\\", "/")
            if not _is_knowledge_page(rel_norm):
                continue
            pages.append({"status": "A", "team_rel": rel_norm, "abs": ab,
                          "previous": learned.get(rel_norm)})
        commits = []

    pages.sort(key=lambda p: p["team_rel"])
    return {
        "ok": True, "team_root": team_root, "branch": branch, "head": head,
        "since": since, "first_time": since is None, "note": note, "pull_note": pull_note,
        "pages": pages, "commits": commits, "up_to_date": (since is not None and not pages),
    }


def format_text(res: Dict[str, Any]) -> str:
    if not res.get("ok"):
        return f"❌ {res.get('reason')}"
    lines = [f"团队仓: {res['team_root']} @ {res.get('branch') or '?'}/{res['head'][:9]}"]
    if res.get("pull_note"):
        lines.append(res["pull_note"])
    if res.get("note"):
        lines.append(f"⚠ {res['note']}")
    if res["up_to_date"]:
        lines.append(f"✅ 已学到最新(水位 {res['since'][:9]}),没有新增量")
        return "\n".join(lines)
    if res["first_time"]:
        lines.append(f"首次学习:团队仓现有 {len(res['pages'])} 个知识页")
    else:
        lines.append(f"自水位 {res['since'][:9]} 以来,{len(res['pages'])} 个知识页有变化:")
    mark_map = {"A": "新增", "M": "修改", "D": "删除", "R": "重命名"}
    for p in res["pages"]:
        prev = f"  (已学 → {p['previous']})" if p.get("previous") else ""
        lines.append(f"  [{mark_map.get(p['status'], p['status'])}] {p['team_rel']}{prev}")
    if res["commits"]:
        lines.append("\n期间提交(新→旧):")
        for c in res["commits"][:20]:
            lines.append(f"  · {c}")
        if len(res["commits"]) > 20:
            lines.append(f"  … 共 {len(res['commits'])} 条")
    lines.append(f"\n学习完成后记录水位:wiki-cli learn --mark {res['head'][:12]}")
    return "\n".join(lines)
