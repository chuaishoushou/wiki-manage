#!/usr/bin/env python3
"""
日报事实层采集器：从 Claude Code 全部会话记录中抽取「某个自然日」的真实工作事实。

设计原则：**事实由代码抽，不经过 LLM**——时间、文件、提交、命令、知识库写入
这些都是确定性数据，交给模型只会引入编造。LLM 只在 run_daily_report_v2.py 里
负责把这些事实组织成人话。

产出一个 dict（可 json 序列化），结构见 collect_day() 返回值。

单独运行可自检：
    python3 daily_facts.py 2026-08-01          # 打印人类可读的事实摘要
    python3 daily_facts.py 2026-08-01 --json   # 输出原始 json
"""
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_ROOT = Path.home() / ".claude" / "projects"
WIKI_ROOT = Path("/Users/chuaishoushou/AI/wiki")
CN_TZ = timezone(timedelta(hours=8))

# 活动间隔超过这个分钟数就切成两个「工作时段」，用于算净工时和画时间线
IDLE_GAP_MIN = 30
# 单个工作块里最多保留多少条用户原话喂给 LLM
MAX_PROMPTS_PER_BLOCK = 12

# 用户表达「不对/没成」的信号词，用来定位当天的难点
TROUBLE_WORDS = [
    "不对", "还是不行", "不行", "报错", "失败", "没生效", "不生效", "有问题",
    "错了", "为什么", "怎么回事", "又出现", "还是", "重新", "回滚", "卡住",
    "打不开", "白屏", "超时", "异常", "崩", "丢失", "覆盖了",
]
# 知识库相关 skill，命中即视为「有沉淀动作」
WIKI_SKILLS = {"wiki-ingest", "wiki-learn", "wiki-query", "wiki-lint", "wiki-daily"}

# 任务号：FLUX 的模块/任务编号形如 T1202 / A0801 / E343
TASK_CODE_RE = re.compile(r"\b([TtAaEeDdMm]\d{3,4})\b")
# AI 自己的临时工作文件不是当天产出，别混进成果清单
TEMP_PATH_RE = re.compile(r"(^/private/tmp/|^/tmp/|/scratchpad/|/\.claude/(?!skills/)|"
                          r"/node_modules/|/\.git/|/__pycache__/)")
# commit message 里的中文方括号标题
BRACKET_RE = re.compile(r"【([^】]{2,30})】")
COMMIT_MSG_RE = re.compile(r"""commit\b[^\n]*?-m\s+(["'])(.+?)\1""", re.S)


def parse_ts(raw):
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(CN_TZ)
    except Exception:
        return None


def redact(text):
    """脱敏：API key、密码、token。日报会进知识库，别把凭据写进去。"""
    text = re.sub(r"sk-[A-Za-z0-9_\-]{16,}", "sk-***", text)
    text = re.sub(r"(?i)(password|passwd|pwd|secret|token|api[_-]?key)(\s*[=:]\s*)\S+", r"\1\2***", text)
    return text


def is_human_prompt(obj):
    """区分「用户真的敲进去的话」和 tool_result / 系统注入 / 子 agent 回传。"""
    if obj.get("type") != "user" or obj.get("isSidechain"):
        return False
    origin = obj.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    # 旧版记录没有 origin，用 promptSource 兜底
    return obj.get("promptSource") == "sdk"


def extract_text(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    return ""


def clean_prompt(text):
    """剥掉 skill 注入、system-reminder、附件等噪音，只留用户本意。"""
    text = re.sub(r"<system-reminder>.*?</system-reminder>", "", text, flags=re.S)
    text = re.sub(r"<[a-z-]+>.*?</[a-z-]+>", "", text, flags=re.S)
    if "Base directory for this skill" in text:
        return ""
    if text.strip().startswith(("[Request interrupted", "<", "Caveat:")):
        return ""
    return text.strip()


def repo_of(path):
    """把绝对路径归到一个可读的「仓库/工程」名上。"""
    p = str(path)
    for marker, depth in (("/v6_000_vue/", 1), ("/tmsv6/", 1), ("/scev6/", 1)):
        if marker in p:
            tail = p.split(marker, 1)[1].split("/")
            return (marker.strip("/") + "/" + tail[0]) if tail else marker.strip("/")
    parts = Path(p).parts
    for anchor in ("FLUX", "AI"):
        if anchor in parts:
            i = parts.index(anchor)
            return "/".join(parts[i:i + 3])
    return str(Path(p).parent)


def module_of(path):
    """从路径里提取模块号，如 .../modules/t1202/... -> T1202"""
    m = re.search(r"/modules/([a-zA-Z]\d{3,4})/", str(path))
    return m.group(1).upper() if m else None


def collect_day(day_str, projects_root=PROJECTS_ROOT):
    """采集某个自然日（北京时间 00:00~24:00）的全部工作事实。"""
    d0 = datetime.strptime(day_str, "%Y-%m-%d").replace(tzinfo=CN_TZ)
    d1 = d0 + timedelta(days=1)

    raw_events = []          # (ts, obj, project_dir)
    session_titles = {}      # sessionId -> 用户给会话起的标题（custom-title 行没有时间戳，单独收）
    files_listed = files_opened = files_hit = 0
    # 三层剪枝，保证「只解析目标日真正活跃的会话」，而不是全库扫描：
    #   ① mtime < 窗口起点 → 目标日之前就没再写过，直接跳过（不打开）
    #   ② 首个事件时间 >= 窗口末尾 → 会话在目标日之后才开始，读一行即弃
    #   ③ 已越过窗口末尾且连续多行 → 后面只会更晚，提前收工（截掉次日长尾）
    for path in projects_root.glob("*/*.jsonl"):
        files_listed += 1
        try:
            if datetime.fromtimestamp(path.stat().st_mtime, CN_TZ) < d0:
                continue
        except OSError:
            continue
        try:
            fh = path.open(errors="ignore")
        except OSError:
            continue
        files_opened += 1
        hit, seen_first, past_end = False, False, 0
        with fh:
            for line in fh:
                if not line.strip():
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                if obj.get("type") == "custom-title" and obj.get("customTitle"):
                    session_titles[obj.get("sessionId")] = str(obj["customTitle"])[:80]
                    continue
                ts = parse_ts(obj.get("timestamp"))
                if not ts:
                    continue
                if not seen_first:
                    seen_first = True
                    if ts >= d1:          # ② 整个会话都在目标日之后
                        break
                if ts >= d1:
                    past_end += 1
                    if past_end >= 30:    # ③ 稳定越界，剪掉尾巴（阈值防少量乱序误杀）
                        break
                    continue
                past_end = 0
                if ts >= d0:
                    raw_events.append((ts, obj, path.parent.name))
                    hit = True
        if hit:
            files_hit += 1

    raw_events.sort(key=lambda x: x[0])

    facts = {
        "date": day_str,
        "weekday": "周" + "一二三四五六日"[d0.weekday()],
        "event_count": len(raw_events),
        "session_count": 0,
        "files_listed": files_listed,
        "files_opened": files_opened,
        "files_hit": files_hit,
        "blocks": [],
        "timeline": [],
        "work_spans": [],
        "active_minutes": 0,
        "span_start": None,
        "span_end": None,
        "projects": {},
        "files_changed": [],
        "commits": [],
        "pushes": 0,
        "task_codes": [],
        "skills": {},
        "wiki_writes": [],
        "trouble_signals": [],
        "api_errors": 0,
        "tool_counts": {},
    }
    if not raw_events:
        return facts

    # ---------- 工作时段（净工时）：相邻事件间隔 > IDLE_GAP_MIN 就断开 ----------
    spans, cur_start, prev = [], raw_events[0][0], raw_events[0][0]
    for ts, _, _ in raw_events[1:]:
        if (ts - prev).total_seconds() > IDLE_GAP_MIN * 60:
            spans.append((cur_start, prev))
            cur_start = ts
        prev = ts
    spans.append((cur_start, prev))
    facts["work_spans"] = [
        {"start": s.strftime("%H:%M"), "end": e.strftime("%H:%M"),
         "minutes": max(1, round((e - s).total_seconds() / 60))}
        for s, e in spans
    ]
    facts["active_minutes"] = sum(x["minutes"] for x in facts["work_spans"])
    facts["span_start"] = raw_events[0][0].strftime("%H:%M")
    facts["span_end"] = raw_events[-1][0].strftime("%H:%M")

    # ---------- 按 session + 时间间隔切「工作块」 ----------
    by_session = defaultdict(list)
    for ts, obj, proj in raw_events:
        by_session[obj.get("sessionId") or proj].append((ts, obj, proj))
    facts["session_count"] = len(by_session)

    tool_counts = Counter()
    skills = Counter()
    all_files = Counter()
    file_first_seen = {}
    commits, pushes = [], 0
    task_codes = Counter()
    wiki_writes = []
    troubles = []
    api_errors = 0
    proj_events = Counter()
    blocks = []

    for sid, evts in by_session.items():
        chunks, cur = [], [evts[0]]
        for item in evts[1:]:
            if (item[0] - cur[-1][0]).total_seconds() > IDLE_GAP_MIN * 60:
                chunks.append(cur)
                cur = [item]
            else:
                cur.append(item)
        chunks.append(cur)

        for chunk in chunks:
            b = {
                "session": sid[:8] if sid else "?",
                "start": chunk[0][0].strftime("%H:%M"),
                "end": chunk[-1][0].strftime("%H:%M"),
                "minutes": max(1, round((chunk[-1][0] - chunk[0][0]).total_seconds() / 60)),
                "cwd": "", "branch": "",
                # custom-title 行没有时间戳进不了事件流，标题在读文件阶段单独收集
                "title": session_titles.get(sid, ""),
                "prompts": [], "files": [], "modules": [], "commits": [],
                "skills": [], "bash_highlights": [], "trouble": [], "wiki": [],
                "events": len(chunk),
            }
            b_files, b_modules, b_skills = Counter(), Counter(), Counter()
            for ts, obj, proj in chunk:
                proj_events[proj] += 1
                if obj.get("cwd") and not b["cwd"]:
                    b["cwd"] = obj["cwd"]
                if obj.get("gitBranch") and not b["branch"]:
                    b["branch"] = obj["gitBranch"]
                sk = obj.get("attributionSkill")
                if sk:
                    b_skills[sk] += 1
                    skills[sk] += 1
                if obj.get("type") == "system" and obj.get("level") == "error":
                    api_errors += 1

                if is_human_prompt(obj):
                    txt = clean_prompt(extract_text(obj.get("message", {}).get("content")))
                    if txt and len(txt) > 3:
                        b["prompts"].append({"t": ts.strftime("%H:%M"), "text": redact(txt[:400])})
                        for code in TASK_CODE_RE.findall(txt):
                            task_codes[code.upper()] += 1
                        low = txt[:200]
                        hit = [w for w in TROUBLE_WORDS if w in low]
                        if hit:
                            b["trouble"].append({"t": ts.strftime("%H:%M"), "text": redact(txt[:200])})

                content = (obj.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for blk in content:
                    if not (isinstance(blk, dict) and blk.get("type") == "tool_use"):
                        continue
                    name = blk.get("name")
                    tool_counts[name] += 1
                    inp = blk.get("input") or {}
                    if name in ("Edit", "Write", "NotebookEdit"):
                        fp = inp.get("file_path")
                        if fp and not TEMP_PATH_RE.search(str(fp)):
                            all_files[fp] += 1
                            b_files[fp] += 1
                            file_first_seen.setdefault(fp, ts)
                            mod = module_of(fp)
                            if mod:
                                b_modules[mod] += 1
                                task_codes[mod] += 1
                            # 必须是知识库目录本身；wiki-manage 是插件源码，不算沉淀
                            if str(fp).startswith(str(WIKI_ROOT) + os.sep):
                                wiki_writes.append({"t": ts.strftime("%H:%M"), "file": fp})
                                b["wiki"].append(fp)
                    elif name == "Bash":
                        cmd = (inp.get("command") or "").strip()
                        if not cmd:
                            continue
                        if re.search(r"\bgit\s+commit\b", cmd):
                            for _, msg in COMMIT_MSG_RE.findall(cmd):
                                msg = msg.strip().split("\n")[0][:160]
                                rec = {"t": ts.strftime("%H:%M"), "msg": redact(msg),
                                       "cwd": obj.get("cwd", "")}
                                commits.append(rec)
                                b["commits"].append(rec)
                                for code in TASK_CODE_RE.findall(msg):
                                    task_codes[code.upper()] += 1
                        if re.search(r"\bgit\s+push\b", cmd):
                            pushes += 1
                        if re.search(r"(lint|vue-tsc|tsc|npm run|mvn|pytest|test)", cmd):
                            b["bash_highlights"].append(redact(cmd[:120]))
                    elif name == "Skill":
                        s = inp.get("skill")
                        if s:
                            b_skills[s] += 1
                            skills[s] += 1

            b["files"] = [f for f, _ in b_files.most_common(15)]
            b["modules"] = [m for m, _ in b_modules.most_common(6)]
            b["skills"] = [s for s, _ in b_skills.most_common(6)]
            b["prompts"] = b["prompts"][:MAX_PROMPTS_PER_BLOCK]
            b["bash_highlights"] = b["bash_highlights"][:5]
            # 没有人类发言、也没有任何产出的块，是纯自动化噪音，丢掉
            if b["prompts"] or b["files"] or b["commits"]:
                blocks.append(b)
                troubles.extend(b["trouble"])

    blocks.sort(key=lambda x: x["start"])
    facts["blocks"] = blocks
    facts["projects"] = {k: v for k, v in proj_events.most_common()}
    facts["tool_counts"] = dict(tool_counts.most_common(12))
    facts["skills"] = dict(skills.most_common())
    # 同一条 commit 可能因命令重试被记录多次，按 message 去重后按时间排序
    seen_msg, uniq_commits = set(), []
    for c in sorted(commits, key=lambda x: x["t"]):
        key = c["msg"].strip()
        if key in seen_msg:
            continue
        seen_msg.add(key)
        uniq_commits.append(c)
    facts["commits"] = uniq_commits
    facts["commit_attempts"] = len(commits)
    facts["pushes"] = pushes
    facts["task_codes"] = [c for c, _ in task_codes.most_common(12)]
    # 同一篇知识页反复保存只算一处，保留首次写入时间
    seen_wiki, uniq_wiki = set(), []
    for w in sorted(wiki_writes, key=lambda x: x["t"]):
        if w["file"] in seen_wiki:
            continue
        seen_wiki.add(w["file"])
        uniq_wiki.append(w)
    facts["wiki_writes"] = uniq_wiki
    facts["trouble_signals"] = troubles[:20]
    facts["api_errors"] = api_errors

    # 文件按仓库分组，日报里按工程展示比一长串绝对路径可读得多
    grouped = defaultdict(list)
    for fp, n in all_files.most_common():
        grouped[repo_of(fp)].append({
            "path": fp,
            "name": Path(fp).name,
            "edits": n,
            "module": module_of(fp),
            "first": file_first_seen[fp].strftime("%H:%M"),
        })
    facts["files_changed"] = [{"repo": k, "files": v} for k, v in
                              sorted(grouped.items(), key=lambda x: -len(x[1]))]
    facts["files_total"] = sum(len(g["files"]) for g in facts["files_changed"])

    # 时间线：每个块一行，给 LLM 和 HTML 共用
    facts["timeline"] = [
        {"start": b["start"], "end": b["end"], "minutes": b["minutes"],
         "cwd": b["cwd"], "branch": b["branch"], "modules": b["modules"],
         # 块内全是代码/日志粘贴时退回用户给会话起的标题，别显示乱码
         "first_prompt": pick_headline(b["prompts"]) or b["title"],
         "files": len(b["files"]), "commits": len(b["commits"])}
        for b in blocks
    ]
    return facts


def pick_headline(prompts):
    """从一个工作块的用户原话里挑最像「任务指令」的一条做标题。

    用户经常直接粘贴报文/日志/URL 给 AI 看，那些当标题没有可读性，
    这里按「像不像人话」打分，挑最高的。
    """
    if not prompts:
        return ""
    best, best_score = "", -1e9
    for p in prompts:
        t = p["text"].strip()
        # 取第一段有实质内容的行，跳过 ``` 之类的包裹符
        first = next((ln.strip() for ln in t.split("\n")
                      if len(ln.strip()) > 3 and not ln.strip().startswith("```")), "")
        if not first:
            continue
        score = 0.0
        # 粘贴的代码/日志/报文特征，扣分
        if re.match(r"^(https?://|/|\{|\[|<|```|\w+[:.]\s*$)", first):
            score -= 40
        score -= t.count("\n") * 3
        score -= len(re.findall(r"[{}\[\]<>=;()]", first[:120])) * 3
        # 中文指令特征，加分；几乎没有中文的多半是贴进来的代码/日志
        cn = len(re.findall(r"[一-鿿]", first))
        if cn < 3:
            score -= 45
        score += cn * 0.6
        if re.search(r"(修复|优化|检查|实现|新增|删除|调整|排查|提交|合并|生成|分析|处理|改造|确认|验证)", first):
            score += 15
        # 长度适中最好
        score -= abs(len(first) - 40) * 0.25
        if score > best_score:
            best, best_score = first, score
    # 全是代码/日志粘贴时宁可留空，也别拿乱码当标题
    return best[:120] if best_score > -25 else ""


def render_material(facts, max_chars=32000):
    """把事实层压成喂给 LLM 的文本材料。保留结构，去掉冗余。"""
    L = []
    L.append(f"日期：{facts['date']}（{facts['weekday']}）")
    L.append(f"活跃区间：{facts['span_start']} ~ {facts['span_end']}，"
             f"净活跃约 {facts['active_minutes']} 分钟，工作块 {len(facts['blocks'])} 段")
    if facts["task_codes"]:
        L.append(f"涉及模块/任务号：{', '.join(facts['task_codes'])}")
    if facts["skills"]:
        L.append("触发的 skill：" + ", ".join(f"{k}({v})" for k, v in facts["skills"].items()))
    L.append("")

    for i, b in enumerate(facts["blocks"], 1):
        L.append(f"===== 工作块 {i}：{b['start']}-{b['end']}（{b['minutes']}分钟）=====")
        if b["cwd"]:
            L.append(f"工作目录：{b['cwd']}" + (f"  分支：{b['branch']}" if b["branch"] else ""))
        if b["modules"]:
            L.append(f"模块：{', '.join(b['modules'])}")
        if b["skills"]:
            L.append(f"skill：{', '.join(b['skills'])}")
        if b["prompts"]:
            L.append("用户原话（按时间）：")
            for p in b["prompts"]:
                L.append(f"  [{p['t']}] {p['text']}")
        if b["files"]:
            L.append("改动文件：")
            for f in b["files"][:10]:
                L.append(f"  - {f}")
        if b["commits"]:
            L.append("git 提交：")
            for c in b["commits"]:
                L.append(f"  [{c['t']}] {c['msg']}")
        if b["bash_highlights"]:
            L.append("校验/构建命令：" + " | ".join(b["bash_highlights"][:3]))
        if b["wiki"]:
            L.append("写入知识库：" + ", ".join(Path(w).name for w in b["wiki"]))
        L.append("")

    if facts["trouble_signals"]:
        L.append("===== 当天疑似卡点（用户表达不满/报错的原话）=====")
        for t in facts["trouble_signals"]:
            L.append(f"  [{t['t']}] {t['text']}")
        L.append("")
    if facts["api_errors"]:
        L.append(f"（当天有 {facts['api_errors']} 次 API 层重试/错误）")

    text = "\n".join(L)
    return text[:max_chars]


def _cli():
    day = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("-") \
        else datetime.now(CN_TZ).strftime("%Y-%m-%d")
    facts = collect_day(day)
    if "--json" in sys.argv:
        print(json.dumps(facts, ensure_ascii=False, indent=2))
        return
    if "--material" in sys.argv:
        print(render_material(facts))
        return
    print(f"日期 {facts['date']}（{facts['weekday']}）  事件 {facts['event_count']}"
          f"  会话 {facts.get('session_count', 0)}"
          f"  （库内 {facts.get('files_listed', 0)} 文件，打开 {facts.get('files_opened', 0)}，"
          f"命中 {facts.get('files_hit', 0)}）")
    print(f"活跃 {facts['span_start']}~{facts['span_end']}  净 {facts['active_minutes']} 分钟"
          f"  工作块 {len(facts['blocks'])}")
    print(f"项目 {len(facts['projects'])}  改动文件 {facts.get('files_total', 0)}"
          f"  提交 {len(facts['commits'])}  push {facts['pushes']}")
    print(f"任务号 {facts['task_codes']}")
    print(f"skill {facts['skills']}")
    print(f"知识库写入 {len(facts['wiki_writes'])}  卡点信号 {len(facts['trouble_signals'])}")
    print("\n--- 时间线 ---")
    for t in facts["timeline"]:
        print(f"  {t['start']}-{t['end']} ({t['minutes']}m) "
              f"mod={','.join(t['modules']) or '-'} files={t['files']} commits={t['commits']} "
              f"| {t['first_prompt'][:60]}")
    print("\n--- 提交 ---")
    for c in facts["commits"]:
        print(f"  [{c['t']}] {c['msg'][:100]}")


if __name__ == "__main__":
    _cli()
