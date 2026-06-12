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

import fnmatch
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from . import frontmatter, repo

STATE_REL = os.path.join(".wiki", "learn-state.json")


def match_exclude(rel: str, patterns: List[str]) -> bool:
    """rel(posix 相对路径)是否命中 exclude 规则。

    两种写法:`dir/**`(目录前缀,机械内容整树分流的主用法)与 fnmatch glob。
    机械生成内容(数据字典表卡、openspec 任务归档)靠它分流,
    避免一次「初版式」大批量提交把增量清单灌爆。
    """
    rel = rel.replace("\\", "/")
    for pat in patterns or []:
        pat = pat.replace("\\", "/")
        if pat.endswith("/**"):
            if rel.startswith(pat[:-2]):  # "dir/**" → 前缀 "dir/"
                return True
        elif fnmatch.fnmatch(rel, pat):
            return True
    return False


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
    水位记三元组 {commit, 日期, 分支}:团队仓 bootstrap 期 reset/rebase 是常态而非意外,
    commit 孤儿化后日期+分支仍能说明「当时学到哪」,供降级对比与人工排查。
    """
    team_key = os.path.abspath(os.path.expanduser(team_root))
    full = repo.git_rev_parse(team_key, commit)
    if not full:
        return {"ok": False,
                "reason": f"commit `{commit}` 在团队仓 {team_key} 不存在(或该路径不是 git 仓),"
                          "拒绝记录水位。请用 learn 输出里的 HEAD 哈希。"}
    branch, _ = repo.git_head_info(team_key)
    state = load_state(personal_root)
    state[team_key] = {"last_commit": full,
                       "marked_at": datetime.now().isoformat(timespec="seconds"),
                       "branch": branch or ""}
    p = _state_path(personal_root)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    repo.atomic_write_text(p, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    return {"ok": True, "team_root": team_key, "last_commit": full, "branch": branch}


def find_learned_full(personal_root: str) -> Dict[str, Dict[str, str]]:
    """逆查已学页:团队仓内相对路径 -> {path: 个人库内相对路径, commit: learned_commit}。

    learned_from 支持字符串或列表(把多个团队页合并消化进同一个人页时逐一登记,
    否则未登记的来源页下次变更会被当全新页重复导入)。
    commit 供 verify 判断 M 页是否真的重新消化过(learned_commit 仍停在旧水位 = 没学)。
    """
    out: Dict[str, Dict[str, str]] = {}
    for path in repo.iter_pages(personal_root):
        try:
            meta, _, has_fm = frontmatter.read_page(path)
        except (OSError, UnicodeDecodeError):
            continue
        src = meta.get("learned_from") if has_fm else None
        sources = src if isinstance(src, list) else ([src] if isinstance(src, str) and src else [])
        for s in sources:
            out[str(s).replace("\\", "/")] = {
                "path": repo.rel_path(personal_root, path),
                "commit": str(meta.get("learned_commit") or ""),
            }
    return out


def find_learned(personal_root: str) -> Dict[str, str]:
    """同 find_learned_full,只要落点路径(diff 的 previous 字段用)。"""
    return {k: v["path"] for k, v in find_learned_full(personal_root).items()}


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


def diff(personal_root: str, team_root: Optional[str], do_pull: bool = False,
         exclude: Optional[List[str]] = None, branch_expect: str = "",
         include_excluded: bool = False) -> Dict[str, Any]:
    """算"自上次学习以来,团队仓有哪些知识页变了"(只读;--pull 例外,见下)。

    返回结构化报告:
      head/branch        团队仓当前位置
      since              本次比较的水位(None = 首次学习,列出全部已提交页)
      pages: [{status(A/M/D/R), team_rel, old_rel(R), archived_to(归档), abs, previous}]
      commits            水位以来的提交标题(供 AI 理解改动意图)
      watermark_stale    无增量但水位落后于 HEAD(建议 --mark 推进)
      excluded_count     被 exclude 规则分流掉的页数(--all 可见全量)
      branch_note        当前检出分支与配置分支不一致时的警告
    """
    if not team_root:
        return {"ok": False, "reason": "未配置团队仓。安装时用 --team-root 指定,"
                                       "或本次显式传 --team <团队仓路径>,"
                                       "或 wiki-cli config team <名> --path <路径> 登记。"}
    team_root = os.path.abspath(os.path.expanduser(team_root))
    if not os.path.isdir(team_root):
        return {"ok": False, "reason": f"团队仓路径不存在: {team_root}"
                                       "(团队仓被移动/重构过?用 wiki-cli config team 改一行即可)"}

    pull_note = ""
    if do_pull:
        ok, msg = repo.git_pull(team_root)
        pull_note = f"git pull --ff-only: {'✅' if ok else '⚠'} {msg}"

    branch, head = repo.git_head_info(team_root)
    if head is None:
        return {"ok": False, "reason": f"团队仓不是 git 仓(无提交记录可读): {team_root}。"
                                       "学习依赖 git 提交记录,请确认这是团队知识仓的 clone。"}
    branch_note = ""
    if branch_expect and branch and branch != branch_expect:
        branch_note = (f"当前检出分支 {branch} ≠ 配置的工作分支 {branch_expect}"
                       f"(可能拉到错误内容;git -C \"{team_root}\" switch {branch_expect})")

    learned = find_learned(personal_root)
    state = load_state(personal_root).get(team_root, {})
    since = state.get("last_commit")
    note = ""
    if since and not repo.git_commit_exists(team_root, since):
        note = f"上次水位 {since[:9]} 已不在团队仓历史中(可能重建过),按首次学习处理"
        since = None
    elif since and repo.git_is_ancestor(team_root, since, head) is False:
        # 水位 commit 还在(未被 gc)但已不在当前分支历史上 = 团队仓 reset/rebase 过。
        # 两点树差仍然给出正确的页面级净变更,但提交标题列表可能把已学内容再列一遍。
        note = (f"水位 {since[:9]} 不在当前分支历史上(团队仓可能 reset/rebase 过):"
                "页面级变更仍准确,期间提交标题仅供参考;学习完成后 --mark 推进水位即可恢复正常。"
                f"若该水位上有未保全的本地提交,先钉住防 gc:"
                f"git -C \"{team_root}\" branch rescue/{since[:9]} {since[:9]}")

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

    # exclude 分流:机械内容(数据字典表卡/任务归档)不进清单,只报数量。
    # 两类页绝不分流:D(已学页的删除/归档必须呈现,否则个人库残留永久化)、
    # 有 previous 的页(已经学进个人库的内容,其更新被吞掉 = 个人页永久陈旧
    # 且 up_to_date 会假绿——分流规则只挡"从未学过"的机械内容)。
    excluded_count = 0
    excluded_sample: List[str] = []
    if exclude:
        kept: List[Dict[str, Any]] = []
        for p in pages:
            if (p["status"] != "D" and not p.get("previous")
                    and match_exclude(p["team_rel"], exclude)):
                excluded_count += 1
                if len(excluded_sample) < 5:
                    excluded_sample.append(p["team_rel"])
                if include_excluded:
                    p["excluded"] = True
                    kept.append(p)
                continue
            kept.append(p)
        pages = kept

    pages.sort(key=lambda p: p["team_rel"])
    up_to_date = since is not None and not pages
    since_full = repo.git_rev_parse(team_root, since) if since else None
    return {
        "ok": True, "team_root": team_root, "branch": branch, "head": head,
        "since": since, "first_time": since is None, "note": note, "pull_note": pull_note,
        "branch_note": branch_note, "pages": pages, "commits": commits,
        "up_to_date": up_to_date,
        "watermark_stale": bool(up_to_date and since_full != head),
        "excluded_count": excluded_count, "excluded_sample": excluded_sample,
    }


def verify(personal_root: str, team_root: str, exclude: Optional[List[str]] = None,
           branch_expect: str = "") -> Dict[str, Any]:
    """核销检查:当前待学清单里,哪些页已带 learned_from 真实落库(确定性,零 LLM)。

    这是 learn 闭环里唯一能机器强制的环节——AI 漏写 learned_from、或静默跳过页面,
    在 --mark 之前被拦下,而不是下次增量时以「重复导入」的形式爆出来。

    判定规则(只认 frontmatter 溯源,不做语义判断;判不了的一律算未核销,
    绝不 fail-open——核销门禁的意义就是宁可多拦一次,不放过一次漏学):
      A / R  → 个人库存在 learned_from 含该页(R 按新路径)的页 = 已核销
      M      → 已学页存在,且其 learned_commit 已覆盖该页在团队仓的**最后一次变更**
               (仅比水位新还不够:learned_commit 介于水位与最后变更之间 = 中间那次
               更新没学,纯水位比较会误判已核销)= 已核销
      D      → 不阻塞(删除/归档的处置协议上允许「确认保留」,无法确定性判定)
    首次学习(无水位)= 基线策展,允许选择性学习,核销只作提示不阻塞,
    由调用方(--mark 门禁)按 first_time 区分阻塞与提示。
    """
    res = diff(personal_root, team_root, exclude=exclude, branch_expect=branch_expect)
    if not res.get("ok"):
        return res
    learned = find_learned_full(personal_root)

    def _hit(rel: str) -> Optional[Dict[str, str]]:
        rel = rel.replace("\\", "/")
        h = learned.get(rel)
        if h:
            return h
        if rel.startswith("wiki/"):
            return learned.get(rel[len("wiki/"):])
        return None

    verified: List[Dict[str, Any]] = []
    unverified: List[Dict[str, Any]] = []
    info: List[Dict[str, Any]] = []
    for p in res["pages"]:
        st = p["status"]
        if st == "D":
            info.append({**p, "verify": "D 页不阻塞(按协议归档或确认保留)"})
            continue
        hit = _hit(p["team_rel"])
        if not hit:
            unverified.append({**p, "verify": "个人库无 learned_from 指向此页(未学或漏写溯源)"})
            continue
        if st == "M":
            lc = repo.git_rev_parse(res["team_root"], hit.get("commit") or "")
            if lc is None:
                unverified.append({**p, "verify":
                                   f"已学页 {hit['path']} 的 learned_commit 无效/缺失"
                                   "(无法对账,按未消化处理)"})
                continue
            last = repo.git_last_change(res["team_root"], p["team_rel"])
            covered = repo.git_is_ancestor(res["team_root"], last, lc) if last else None
            if covered is not True:  # False=没学到最新;None=git 失败,fail-closed
                unverified.append({**p, "verify":
                                   f"已学页 {hit['path']} 的 learned_commit 未覆盖该页"
                                   f"最后变更({(last or '?')[:9]})——团队侧更新未消化,"
                                   "或合并后忘了把 learned_commit 更新为本次 HEAD"})
                continue
        verified.append({**p, "learned_path": hit["path"]})
    return {"ok": True, "team_root": res["team_root"], "head": res["head"],
            "since": res["since"], "first_time": res["first_time"],
            "verified": verified, "unverified": unverified, "info": info,
            "excluded_count": res.get("excluded_count", 0),
            "all_clear": not unverified}


def format_verify(res: Dict[str, Any]) -> str:
    if not res.get("ok"):
        return f"❌ {res.get('reason')}"
    lines = [f"核销检查: 团队仓 {res['team_root']} @ {res['head'][:9]}"
             + ("(首次学习,核销仅提示不阻塞)" if res.get("first_time") else "")]
    for p in res.get("verified", []):
        lines.append(f"  ✅ [{p['status']}] {p['team_rel']} → {p['learned_path']}")
    for p in res.get("info", []):
        lines.append(f"  · [{p['status']}] {p['team_rel']}  {p['verify']}")
    for p in res.get("unverified", []):
        lines.append(f"  ❌ [{p['status']}] {p['team_rel']}  — {p['verify']}")
    if res.get("excluded_count"):
        lines.append(f"  (另有 {res['excluded_count']} 页被 exclude 规则分流,不参与核销)")
    if res.get("all_clear"):
        lines.append("✅ 全部核销,通过(可 --mark 推进水位)")
    else:
        lines.append(f"❌ {len(res['unverified'])} 页未核销:补学并写 learned_from/learned_commit,"
                     "或确认放弃后 --mark --force(放弃原因记入 log.md)")
    return "\n".join(lines)


def format_text(res: Dict[str, Any]) -> str:
    if not res.get("ok"):
        return f"❌ {res.get('reason')}"
    lines = [f"团队仓: {res['team_root']} @ {res.get('branch') or '?'}/{res['head'][:9]}"]
    if res.get("pull_note"):
        lines.append(res["pull_note"])
    if res.get("note"):
        lines.append(f"⚠ {res['note']}")
    if res.get("branch_note"):
        lines.append(f"⚠ {res['branch_note']}")
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
    if res.get("excluded_count"):
        sample = " ".join(res.get("excluded_sample", []))
        lines.append(f"\n(另有 {res['excluded_count']} 页命中 exclude 规则被分流"
                     f"——机械生成/任务归档类,原地引用即可不必学;--all 可见。示例: {sample})")
    if res["commits"]:
        lines.append("\n期间提交(新→旧):")
        for c in res["commits"][:20]:
            lines.append(f"  · {c}")
        if len(res["commits"]) > 20:
            lines.append(f"  … 共 {len(res['commits'])} 条")
    # 建议命令显式带 --team:多仓配置下不带 --team 的 --mark 会被要求指定,照抄即可用
    t = f" --team \"{res['team_root']}\""
    lines.append(f"\n学习完成后:wiki-cli learn{t} --verify 核销 → "
                 f"wiki-cli learn{t} --mark {res['head'][:12]}")
    return "\n".join(lines)
