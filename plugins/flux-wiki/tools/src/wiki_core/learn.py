"""learn:团队仓 → 个人库 增量学习的确定性数据层。

分工(轻量化边界):
- CLI(本模块)只做确定性部分:按 git 水位算增量、给出每页的来源/状态/历史落点、记录水位。
- 分类与改写是 AI 的活(/wiki-learn 命令):AI 读团队页原文,决定落进个人库哪个 domain,
  写盘时带溯源 frontmatter(learned_from / learned_commit)。
- 水位只有一个 commit 字段,存 <个人库>/.wiki/learn-state.json;不做定时、不做自动合并。

"上次学到哪"之外的状态不另造:已学页靠其 frontmatter 的 learned_from 字段逆查,
所以即使水位丢失,重学也只是多看几页,不会重复落盘到未知位置。

git 语义上的三个关键决定(都有 selftest 钉住):
- 首次学习用 git ls-files(已提交内容),不扫磁盘——与增量模式同一事实源,
  未提交文件两种模式都不可见,learned_commit 不会指向不含该内容的 commit。
- R(改名)保留旧路径:previous 用旧路径逆查,改名不再被误判成全新页。
- R 的新路径落在 archive/ 等非知识区(=协议规定的「归档」操作)时,降级为 D 呈现
  并附 archived_to——否则归档对成员完全不可见,个人库废弃知识永久残留。
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
    """写回学习水位(team_root 维度;支持多个团队仓互不干扰)。

    水位先经团队仓校验并展开为完整哈希:手滑/笔误的当下就报错,
    而不是静默写入、下次学习才以「全量重列」的形式爆出来。
    """
    team_key = os.path.abspath(os.path.expanduser(team_root))
    full = repo.git_rev_parse(team_key, commit)
    if not full:
        return {"ok": False,
                "reason": f"commit `{commit}` 在团队仓 {team_key} 不存在(或该路径不是 git 仓),"
                          "拒绝记录水位。请用 learn 输出里的 HEAD 哈希。"}
    state = load_state(personal_root)
    state[team_key] = {"last_commit": full,
                       "marked_at": datetime.now().isoformat(timespec="seconds")}
    p = _state_path(personal_root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return {"ok": True, "team_root": team_key, "last_commit": full}


def find_learned(personal_root: str) -> Dict[str, str]:
    """逆查已学页:团队仓内相对路径 -> 个人库内相对路径(读各页 frontmatter learned_from)。

    learned_from 支持字符串或列表(把多个团队页合并消化进同一个人页时逐一登记,
    否则未登记的来源页下次变更会被当全新页重复导入)。
    """
    out: Dict[str, str] = {}
    for path in repo.iter_pages(personal_root):
        try:
            meta, _, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        src = meta.get("learned_from") if has_fm else None
        sources = src if isinstance(src, list) else ([src] if isinstance(src, str) and src else [])
        for s in sources:
            out[str(s).replace("\\", "/")] = repo.rel_path(personal_root, path)
    return out


def _is_knowledge_page(rel: str) -> bool:
    """git 变更路径过滤:只关心知识页(.md,且不在排除目录/归档/模板里,非协议/导航文件)。

    overview.md 任何层级都是导航页(域内 overview 是域导航,学走后页内相对链接全断、
    内容只是链接列表),不算知识页;README.md 只在顶层算协议(模块目录的 README 是内容)。
    """
    if not rel.endswith(".md"):
        return False
    parts = rel.replace("\\", "/").split("/")
    if parts[-1] == "overview.md":
        return False
    # 顶层(库根或 wiki/ 内容层根)的协议/导航文件不算知识页;domain 内的 README 算
    if parts[-1] in repo.INFRA_FILES and len([p for p in parts if p != "wiki"]) == 1:
        return False
    skip = set(repo.EXCLUDE_DIRS) | {"archive", "templates"}
    return not any(p in skip for p in parts)


def _previous(learned: Dict[str, str], rel: str) -> Optional[str]:
    """按团队仓相对路径查已学落点;v2 嵌套团队仓兼容内容层相对写法(剥 wiki/ 前缀)。

    纯字符串运算,不依赖磁盘状态——D(已删)页文件已不在,且 git rm 最后一页时
    连 wiki/ 空目录都会被清掉(content_dir 探测会失效),所以前缀按布局约定硬剥。
    """
    rel = rel.replace("\\", "/")
    hit = learned.get(rel)
    if hit:
        return hit
    if rel.startswith("wiki/"):
        return learned.get(rel[len("wiki/"):])
    return None


def diff(personal_root: str, team_root: Optional[str], do_pull: bool = False) -> Dict[str, Any]:
    """算"自上次学习以来,团队仓有哪些知识页变了"(只读;--pull 例外,见下)。

    返回结构化报告:
      head/branch        团队仓当前位置
      since              本次比较的水位(None = 首次学习,列出全部已提交页)
      pages: [{status(A/M/D/R), team_rel, old_rel(R), archived_to(归档), abs, previous}]
      commits            水位以来的提交标题(供 AI 理解改动意图)
      watermark_stale    无增量但水位落后于 HEAD(建议 --mark 推进)
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
    state = load_state(personal_root).get(team_root, {})
    since = state.get("last_commit")
    note = ""
    if since and not repo.git_commit_exists(team_root, since):
        note = f"上次水位 {since[:9]} 已不在团队仓历史中(可能重建过),按首次学习处理"
        since = None
    elif since and repo.git_is_ancestor(team_root, since, head) is False:
        # 水位 commit 还在(未被 gc)但已不在当前分支历史上 = 团队仓 rebase/重建过。
        # 两点树差仍然给出正确的页面级净变更,但提交标题列表可能把已学内容再列一遍。
        note = (f"水位 {since[:9]} 不在当前分支历史上(团队仓可能 rebase/重建过):"
                "页面级变更仍准确,期间提交标题仅供参考;学习完成后 --mark 推进水位即可恢复正常")

    pages: List[Dict[str, Any]] = []
    if since:
        since_full = repo.git_rev_parse(team_root, since) or since
        if since_full == head:
            changes: List = []
        else:
            changes = repo.git_diff_name_status(team_root, since)
            if changes is None:
                return {"ok": False, "reason": f"git diff {since[:9]}..HEAD 失败,无法计算增量"}
        for status, rel, old_rel in changes:
            st = status[0]
            rel_norm = rel.replace("\\", "/")
            old_norm = old_rel.replace("\\", "/") if old_rel else None
            new_is_page = _is_knowledge_page(rel_norm)
            old_is_page = _is_knowledge_page(old_norm) if old_norm else False
            if st in ("R", "C"):
                if new_is_page and old_is_page:
                    pass  # 真改名:R,带 old_rel
                elif old_is_page and not new_is_page:
                    # 知识页被移出知识区(典型 = 协议规定的「归档」):对成员就是删除
                    pages.append({"status": "D", "team_rel": old_norm, "abs": None,
                                  "archived_to": rel_norm,
                                  "previous": _previous(learned, old_norm)})
                    continue
                elif new_is_page and not old_is_page:
                    st, old_norm = "A", None  # 从非知识区移入:对成员就是新增
                else:
                    continue
            elif not new_is_page:
                continue
            ab = os.path.join(team_root, rel)
            pages.append({
                "status": st,
                "team_rel": rel_norm,
                **({"old_rel": old_norm} if st == "R" and old_norm else {}),
                "abs": ab if os.path.isfile(ab) else None,
                "previous": _previous(learned,
                                      old_norm if st == "R" and old_norm else rel_norm),
            })
        commits = repo.git_log_subjects(team_root, since)
    else:
        # 首次学习(或水位失效):列团队仓已提交的全部知识页(git ls-files;
        # 极端情况拿不到 git 列表时退回磁盘遍历,行为与旧版一致)
        tracked = repo.git_ls_md(team_root)
        rels = tracked if tracked is not None else [
            os.path.relpath(ab, team_root) for ab in repo.iter_pages(team_root)]
        for rel in rels:
            rel_norm = rel.replace("\\", "/")
            if not _is_knowledge_page(rel_norm):
                continue
            ab = os.path.join(team_root, rel)
            pages.append({"status": "A", "team_rel": rel_norm,
                          "abs": ab if os.path.isfile(ab) else None,
                          "previous": _previous(learned, rel_norm)})
        commits = []

    pages.sort(key=lambda p: p["team_rel"])
    up_to_date = since is not None and not pages
    since_full = repo.git_rev_parse(team_root, since) if since else None
    return {
        "ok": True, "team_root": team_root, "branch": branch, "head": head,
        "since": since, "first_time": since is None, "note": note, "pull_note": pull_note,
        "pages": pages, "commits": commits, "up_to_date": up_to_date,
        "watermark_stale": bool(up_to_date and since_full != head),
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
        if res.get("watermark_stale"):
            n = len(res.get("commits") or [])
            lines.append(f"✅ 自水位 {res['since'][:9]} 以来无知识页变化"
                         f"(期间 {n} 个提交不涉及知识页)")
            for c in (res.get("commits") or [])[:5]:
                lines.append(f"  · {c}")
            lines.append(f"可推进水位省下次对比:wiki-cli learn --mark {res['head'][:12]}")
        else:
            lines.append(f"✅ 已学到最新(水位 {res['since'][:9]}),没有新增量")
        return "\n".join(lines)
    if res["first_time"]:
        lines.append(f"首次学习:团队仓现有 {len(res['pages'])} 个知识页")
    else:
        lines.append(f"自水位 {res['since'][:9]} 以来,{len(res['pages'])} 个知识页有变化:")
    mark_map = {"A": "新增", "M": "修改", "D": "删除", "R": "重命名"}
    for p in res["pages"]:
        prev = f"  (已学 → {p['previous']})" if p.get("previous") else ""
        if p["status"] == "R" and p.get("old_rel"):
            body = f"{p['old_rel']} → {p['team_rel']}"
        elif p["status"] == "D" and p.get("archived_to"):
            body = f"{p['team_rel']}  (团队仓已归档 → {p['archived_to']})"
        else:
            body = p["team_rel"]
        lines.append(f"  [{mark_map.get(p['status'], p['status'])}] {body}{prev}")
    if res["commits"]:
        lines.append("\n期间提交(新→旧):")
        for c in res["commits"][:20]:
            lines.append(f"  · {c}")
        if len(res["commits"]) > 20:
            lines.append(f"  … 共 {len(res['commits'])} 条")
    lines.append(f"\n学习完成后记录水位:wiki-cli learn --mark {res['head'][:12]}")
    return "\n".join(lines)
