#!/usr/bin/env python3
"""
工作日报生成器 v2。

与 v1 的关键区别：
  1. 扫描 ~/.claude/projects/ 下**全部**项目目录（v1 只扫了 AI 一个目录，
     导致 2026-07 有 23/39 次运行报「近 24 小时没有任何会话记录」）
  2. 按**自然日**切（v1 是滑动 24h 窗口，跨天重复计算）
  3. 事实层（时间线 / 改动文件 / git 提交 / 知识库写入 / 卡点）由 daily_facts.py
     用代码硬抽，LLM 只负责把事实组织成人话——模型挂了也能降级出纯事实版日报
  4. 双输出：Markdown（归档、给月报消费）+ HTML（阅读版）
  5. 无会话的日子输出「今日无工作记录」而不是报错退出

用法：
  python3 run_daily_report_v2.py                     # 生成今天的日报
  python3 run_daily_report_v2.py --date 2026-07-31   # 生成指定日期
  python3 run_daily_report_v2.py --yesterday         # 生成昨天（定时任务用）
  python3 run_daily_report_v2.py --dry-run           # 只打印，不落盘
  python3 run_daily_report_v2.py --no-llm            # 跳过 LLM，只出事实版

API key：环境变量 DEEPSEEK_API_KEY → ~/.config/deepseek/api_key
"""
import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_facts import CN_TZ, collect_day, render_material  # noqa: E402

AGENT_LOGS = Path("/Users/chuaishoushou/AI/wiki/wiki/agent-logs")
REPORTS_DIR = AGENT_LOGS / "daily-reports"
HTML_DIR = REPORTS_DIR / "html"
# 给月报消费的精简版：完整日报太长，30 天会撑爆月报的原料上限
DIGEST_DIR = REPORTS_DIR / "digest"
RUN_REPORTS_DIR = AGENT_LOGS / "run-reports"
RUNS_JSONL = AGENT_LOGS / "runs.jsonl"
ARCHIVE_ROOT = Path("/Users/chuaishoushou/AI/wiki/wiki/archive")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
KEY_FILE = Path.home() / ".config" / "deepseek" / "api_key"

BRAND = "#D71920"      # 公司主红，只做点缀
INK = "#1f2328"        # 正文灰黑


def now_cn():
    return datetime.now(CN_TZ)


def load_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return None


# --------------------------------------------------------------------------
# LLM 叙事层
# --------------------------------------------------------------------------
SYSTEM_PROMPT = """你是工作日报撰写助手。用户是一名后端技术顾问（FLUX 物流 TMS 系统方向），\
每天通过 AI 助手完成开发、排障、代码迁移等工作。

下面给你的是**已经由程序从操作记录中抽取好的客观事实**（时间、文件、提交、报错都是真的）。
你的任务只是把这些事实组织成人能读的日报，**不要编造任何事实中没有的内容**。

输出严格的 JSON，结构如下：
{
  "summary": "一句话概括今天干了什么（40字以内）",
  "tasks": [
    {
      "title": "任务标题（15字内，动宾结构，如「修复 T1202 竞价弹窗空白」）",
      "time": "起止时间，如 02:15-04:12（多段用逗号分隔）",
      "modules": ["T1202"],
      "what": "具体做了什么，1-2句，说清楚改了什么、怎么解决的",
      "outcome": "**只在结果不是「顺利做完」时才填**，如「未完成，待测试反馈」「已验证通过」「暂时绕过，根因未定位」；正常完成一律留空字符串",
      "status": "done | partial | blocked"
    }
  ],
  "problems": [
    {
      "problem": "遇到的具体问题（不要写成任务，要写成「卡住的点」）",
      "cause": "根因（事实里能看出来才写，看不出写「未定位」）",
      "solution": "怎么解决的；没解决就写「未解决」",
      "hard": true/false
    }
  ],
  "highlights": ["今天真正有价值的成果，2-4条，要具体不要空话"],
  "followups": ["明确留到后面的事，没有就空数组"]
}

规则：
- **tasks 最多 9 条，这是硬要求**。工作块通常有几十个，必须按「同一模块 / 同一问题 / 同一目标」
  合并成任务：同一个模块号的多个块合并为一条；同一件事分散在几个时间段的合并为一条（时间写成
  "02:15-03:37, 13:40-14:20"）。绝对不要一个工作块输出一条任务。
  宁可合并得粗一些，也不要超过 9 条。
- 时间必须来自事实，不要瞎编。
- problems 只写真的卡住过的（事实里标了「疑似卡点」的、反复修改同一文件的、报错重试的）；
  顺利完成的不要写进 problems。没有就给空数组。
- hard=true 只给真正花了时间、绕了弯路的难点。
- 中文，语气平实，像给自己看的工作记录。技术名词、模块号、文件名保留原文。
- **不要写「已提交」「已推送」「已提交推送」这类过程动作**——提交推送是日常动作不是成果，
  日报另有独立的提交清单。outcome 只写真正需要提醒自己的状态。
- highlights 写「解决了什么、产生了什么价值」，不要写「改了几个文件」「提交了几次」。
- 只输出 JSON，不要 markdown 代码块包裹。"""


def call_deepseek(api_key, material, n_blocks=0, timeout=180, retries=2):
    hint = (f"\n\n注意：今天共 {n_blocks} 个工作块，请按主题合并后输出**不超过 9 条** tasks。"
            if n_blocks else "")
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": "===== 今日客观工作事实 =====\n" + material + hint},
        ],
        "temperature": 0.2,
        "max_tokens": 8000,
        "response_format": {"type": "json_object"},
    }
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                DEEPSEEK_URL,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {api_key}"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            return json.loads(data["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            # v1 只报「HTTP Error 400」，看不出原因；这里把响应体带出来
            detail = ""
            try:
                detail = e.read().decode("utf-8", "ignore")[:400]
            except Exception:
                pass
            last_err = RuntimeError(f"HTTP {e.code}: {detail}")
        except Exception as e:
            last_err = e
        if attempt < retries:
            time.sleep(3 * (attempt + 1))
    raise last_err


# --------------------------------------------------------------------------
# Markdown 渲染
# --------------------------------------------------------------------------
def fmt_hours(minutes):
    return f"{minutes // 60} 小时 {minutes % 60} 分" if minutes >= 60 else f"{minutes} 分钟"


STATUS_CN = {"done": "已完成", "partial": "部分完成", "blocked": "受阻"}

# 模型总爱在每条任务后面挂一句「已提交推送」，没有信息量，一律滤掉
NOISE_OUTCOME = ("已提交", "已推送", "提交推送", "已完成", "完成", "已修复", "已解决")


def is_noise_outcome(text):
    t = re.sub(r"[\s。，,、.]+", "", str(text))
    return (not t) or t in NOISE_OUTCOME or (len(t) <= 6 and t.startswith(("已提交", "已推送", "提交")))


def render_markdown(facts, story):
    d = facts
    L = [f"# 工作日报 {d['date']}（{d['weekday']}）", ""]
    if story and story.get("summary"):
        L += [f"> {story['summary']}", ""]

    L += ["## 一、今日概览", "",
          "| 指标 | 数值 |", "| --- | --- |",
          f"| 活跃区间 | {d['span_start']} – {d['span_end']} |",
          f"| 净投入时长 | {fmt_hours(d['active_minutes'])}（{len(d['work_spans'])} 个时段）|",
          f"| 会话 / 工作块 | {d.get('session_count', 0)} 个会话，切成 {len(d['blocks'])} 段 |",
          f"| 涉及工程 | {len(d['projects'])} 个 |",
          f"| 涉及模块 | {', '.join(d['task_codes'][:10]) or '—'} |",
          f"| 代码提交 | {len(d['commits'])} 次（触及 {d.get('files_total', 0)} 个文件）|",
          f"| 知识库沉淀 | {len(d['wiki_writes'])} 处 |", ""]

    # ---- 今日完成 ----
    L += ["## 二、今日完成", ""]
    if story and story.get("tasks"):
        for i, t in enumerate(story["tasks"], 1):
            tag = STATUS_CN.get(t.get("status", "done"), "")
            mods = "、".join(t.get("modules") or [])
            head = f"**{i}. {t.get('title', '')}**"
            meta = "　".join(x for x in [
                f"`{t.get('time', '')}`" if t.get("time") else "",
                f"模块 {mods}" if mods else "",
                f"[{tag}]" if tag else "",
            ] if x)
            L += [f"{head}　{meta}", "", f"   {t.get('what', '')}"]
            # 「已提交/已推送」是日常动作不是结果，别每条都挂一句
            if t.get("outcome") and not is_noise_outcome(t["outcome"]):
                L += [f"   　→ {t['outcome']}"]
            L += [""]
    else:
        L += ["_（LLM 叙事不可用，见下方时间线与成果清单）_", ""]

    # ---- 问题与难点 ----
    L += ["## 三、问题与难点", ""]
    probs = (story or {}).get("problems") or []
    if probs:
        for p in probs:
            mark = "🔴 " if p.get("hard") else ""
            L += [f"- {mark}**{p.get('problem', '')}**"]
            if p.get("cause"):
                L += [f"  - 原因：{p['cause']}"]
            if p.get("solution"):
                L += [f"  - 处理：{p['solution']}"]
        L += [""]
    else:
        L += ["无（当天未出现明显卡点）", ""]

    # ---- 时间线（纯事实） ----
    L += ["## 四、工作时间线", "",
          f"净投入 {fmt_hours(d['active_minutes'])}，分布在："
          + "、".join(f"{s['start']}–{s['end']}" for s in d["work_spans"]), ""]
    L += ["| 时间 | 时长 | 模块 | 做了什么 | 产出 |", "| --- | --- | --- | --- | --- |"]
    for t in d["timeline"]:
        out = []
        if t["files"]:
            out.append(f"{t['files']} 文件")
        if t["commits"]:
            out.append(f"{t['commits']} 提交")
        desc = (t["first_prompt"] or "—").replace("|", "／")[:60]
        L.append(f"| {t['start']}–{t['end']} | {t['minutes']}m | "
                 f"{'、'.join(t['modules']) or '—'} | {desc} | {'，'.join(out) or '—'} |")
    L += [""]

    # ---- 成果清单（纯事实）。只列提交，文件明细属于过程细节，不进日报 ----
    L += ["## 五、成果清单", ""]
    if story and story.get("highlights"):
        L += [f"- {h}" for h in story["highlights"]]
        L += [""]
    if d["commits"]:
        L += [f"### 代码提交（{len(d['commits'])} 次）", ""]
        for c in d["commits"]:
            L.append(f"- `{c['t']}` {c['msg']}")
        L += [""]

    # ---- 知识库 ----
    L += ["## 六、知识库记录情况", ""]
    if d["wiki_writes"]:
        L += [f"今日向知识库写入 {len(d['wiki_writes'])} 处：", ""]
        for w in d["wiki_writes"]:
            rel = w["file"].replace("/Users/chuaishoushou/AI/wiki/", "")
            L.append(f"- `{w['t']}` {rel}")
        L += [""]
    else:
        L += ["⚠️ **今日没有向知识库写入任何内容。**", ""]
    wiki_sk = [k for k in d["skills"] if k.startswith("wiki")]
    if wiki_sk:
        L += [f"触发的知识库 skill：{', '.join(wiki_sk)}", ""]
    # 值得沉淀但没沉淀的：有难点却没写 wiki
    if probs and not d["wiki_writes"]:
        L += ["建议沉淀（今日有卡点但未入库）：", ""]
        L += [f"- {p.get('problem', '')}" for p in probs if p.get("hard")]
        L += [""]

    # ---- 待跟进 ----
    L += ["## 七、待跟进", ""]
    fus = (story or {}).get("followups") or []
    L += ([f"- {f}" for f in fus] if fus else ["无"]) + [""]

    if d["skills"]:
        L += ["---", "", "<sub>触发 skill：" +
              "、".join(f"{k}×{v}" for k, v in list(d["skills"].items())[:8]) + "</sub>", ""]
    return "\n".join(L)


# --------------------------------------------------------------------------
# HTML 渲染（阅读版：红色点缀 + 灰黑正文）
# --------------------------------------------------------------------------
def render_html(facts, story):
    d = facts
    e = html.escape

    def card(label, value, sub=""):
        return (f'<div class="card"><div class="k">{e(label)}</div>'
                f'<div class="v">{value}</div>'
                f'<div class="s">{e(sub)}</div></div>')

    compact = (f"{d['active_minutes'] // 60}<span class='u'>小时</span>"
               f"{d['active_minutes'] % 60}<span class='u'>分</span>"
               if d["active_minutes"] >= 60 else
               f"{d['active_minutes']}<span class='u'>分</span>")
    cards = "".join([
        card("净投入", compact, f"{d['span_start']}–{d['span_end']}"),
        card("会话 / 块", f"{d.get('session_count', 0)} <span class='sep'>/</span> {len(d['blocks'])}",
             f"{len(d['work_spans'])} 个时段"),
        card("代码提交", str(len(d["commits"])), f"触及 {d.get('files_total', 0)} 个文件"),
        card("涉及模块", str(len(d["task_codes"])), "、".join(d["task_codes"][:4]) or "—"),
        card("涉及工程", str(len(d["projects"])), "个代码库"),
        card("知识库沉淀", str(len(d["wiki_writes"])), "处写入" if d["wiki_writes"] else "今日未沉淀"),
    ])

    # 任务
    tasks_html = ""
    for i, t in enumerate((story or {}).get("tasks") or [], 1):
        st = t.get("status", "done")
        mods = "".join(f'<span class="tag">{e(m)}</span>' for m in (t.get("modules") or []))
        tasks_html += f"""
        <div class="task st-{e(st)}">
          <div class="t-head"><span class="num">{i}</span>
            <span class="t-title">{e(t.get('title',''))}</span>
            <span class="t-time">{e(t.get('time',''))}</span>
            <span class="badge b-{e(st)}">{e(STATUS_CN.get(st, st))}</span></div>
          <div class="t-body">{e(t.get('what',''))}</div>
          <div class="t-foot">{mods}
            {'<span class="out">→ ' + e(t.get('outcome','')) + '</span>'
             if t.get('outcome') and not is_noise_outcome(t['outcome']) else ''}</div>
        </div>"""
    if not tasks_html:
        tasks_html = '<p class="muted">LLM 叙事不可用，请看下方时间线与成果清单。</p>'

    # 问题
    probs = (story or {}).get("problems") or []
    prob_html = "".join(f"""
        <div class="prob {'hard' if p.get('hard') else ''}">
          <div class="p-q">{'🔴 ' if p.get('hard') else ''}{e(p.get('problem',''))}</div>
          {'<div class="p-c"><b>原因</b>　' + e(p['cause']) + '</div>' if p.get('cause') else ''}
          {'<div class="p-s"><b>处理</b>　' + e(p['solution']) + '</div>' if p.get('solution') else ''}
        </div>""" for p in probs) or '<p class="muted">当天未出现明显卡点。</p>'

    # 时间线：按小时刻度定位，直观看出几点在干活
    tl = ""
    for t in d["timeline"]:
        sh, sm = int(t["start"][:2]), int(t["start"][3:])
        eh, em = int(t["end"][:2]), int(t["end"][3:])
        left = (sh * 60 + sm) / 1440 * 100
        width = max(0.7, ((eh * 60 + em) - (sh * 60 + sm)) / 1440 * 100)
        out = []
        if t["files"]:
            out.append(f"{t['files']}文件")
        if t["commits"]:
            out.append(f"{t['commits']}提交")
        tl += f"""
        <div class="tl-row">
          <div class="tl-time">{e(t['start'])}–{e(t['end'])}<span class="tl-min">{t['minutes']}m</span></div>
          <div class="tl-track"><div class="tl-bar" style="left:{left:.2f}%;width:{width:.2f}%"></div></div>
          <div class="tl-desc"><span class="tl-mod">{e('、'.join(t['modules'])) or ''}</span>
            {e(t['first_prompt'] or '—')}
            {'<span class="tl-out">' + e('·'.join(out)) + '</span>' if out else ''}</div>
        </div>"""

    hours_ruler = "".join(f'<span style="left:{h/24*100:.2f}%">{h:02d}</span>'
                          for h in range(0, 24, 3))

    commits_html = "".join(
        f'<li><code>{e(c["t"])}</code> {e(c["msg"])}</li>' for c in d["commits"]
    ) or '<li class="muted">今日无提交</li>'

    if d["wiki_writes"]:
        wiki_html = ('<ul class="plain">' + "".join(
            f'<li><code>{e(w["t"])}</code> {e(w["file"].replace("/Users/chuaishoushou/AI/wiki/", ""))}</li>'
            for w in d["wiki_writes"]) + "</ul>")
    else:
        wiki_html = ('<div class="warn">今日没有向知识库写入任何内容。'
                     + ("有卡点未沉淀，建议补记。" if any(p.get("hard") for p in probs) else "") + "</div>")

    hl = (story or {}).get("highlights") or []
    hl_html = ("<ul class='plain'>" + "".join(f"<li>{e(h)}</li>" for h in hl) + "</ul>") if hl else ""
    fus = (story or {}).get("followups") or []
    fu_html = ("<ul class='plain'>" + "".join(f"<li>{e(f)}</li>" for f in fus) + "</ul>") \
        if fus else '<p class="muted">无</p>'

    summary = e((story or {}).get("summary", "")) or f"{d['date']} 工作记录"

    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>工作日报 {e(d['date'])}</title>
<style>
:root{{--brand:{BRAND};--ink:{INK};--muted:#6b7280;--line:#e6e8eb;--bg:#f7f8fa;--card:#fff;}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);
 font:15px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",Arial,sans-serif;}}
.wrap{{max-width:1080px;margin:0 auto;padding:32px 24px 64px}}
header{{border-bottom:3px solid var(--brand);padding-bottom:16px;margin-bottom:28px}}
h1{{margin:0;font-size:26px;letter-spacing:.5px}}
h1 .date{{color:var(--brand)}}
.sub{{color:var(--muted);margin-top:6px;font-size:14px}}
h2{{font-size:17px;margin:36px 0 14px;padding-left:11px;border-left:4px solid var(--brand);line-height:1.2}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}}
.card .k{{font-size:12px;color:var(--muted)}}
.card .v{{font-size:23px;font-weight:600;margin:2px 0;letter-spacing:-.5px;white-space:nowrap}}
.card .v .sep{{color:var(--line);font-weight:300}}
.card .v .u{{font-size:14px;font-weight:400;color:#4b5158;margin:0 1px}}
.card .s{{font-size:12px;color:var(--muted)}}
.task{{background:var(--card);border:1px solid var(--line);border-left:3px solid var(--brand);
 border-radius:8px;padding:14px 16px;margin-bottom:10px}}
.task.st-partial{{border-left-color:#e8a33d}} .task.st-blocked{{border-left-color:#9aa0a6}}
.t-head{{display:flex;align-items:center;gap:10px;flex-wrap:wrap}}
.num{{background:var(--brand);color:#fff;width:20px;height:20px;border-radius:5px;
 display:inline-flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;flex:none}}
.t-title{{font-weight:600;font-size:16px}}
.t-time{{color:var(--muted);font-size:13px;font-family:ui-monospace,Menlo,monospace}}
.badge{{font-size:11px;padding:2px 8px;border-radius:20px;background:#eef0f2;color:var(--muted)}}
.b-done{{background:#fdecec;color:var(--brand)}} .b-partial{{background:#fdf3e3;color:#a86b12}}
.t-body{{margin:8px 0 6px;color:#3c4247}}
.t-foot{{display:flex;gap:8px;align-items:center;flex-wrap:wrap}}
.tag{{font-size:11px;border:1px solid var(--line);border-radius:4px;padding:1px 7px;color:var(--muted);
 font-family:ui-monospace,Menlo,monospace}}
.out{{font-size:13px;color:var(--brand)}}
.prob{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin-bottom:8px}}
.prob.hard{{background:#fffbfb;border-color:#f3d6d6}}
.p-q{{font-weight:600}} .p-c,.p-s{{font-size:14px;color:#4b5158;margin-top:4px}}
.p-c b,.p-s b{{color:var(--muted);font-weight:500;font-size:12px}}
.ruler{{position:relative;height:16px;margin:0 0 4px 150px;font-size:11px;color:var(--muted)}}
.ruler span{{position:absolute;transform:translateX(-50%)}}
.tl-row{{display:grid;grid-template-columns:150px 180px 1fr;gap:12px;align-items:center;
 padding:5px 0;border-bottom:1px dashed var(--line);font-size:13px}}
.tl-time{{font-family:ui-monospace,Menlo,monospace;color:#4b5158}}
.tl-min{{color:var(--muted);margin-left:6px;font-size:11px}}
.tl-track{{position:relative;height:8px;background:#eef0f2;border-radius:4px}}
.tl-bar{{position:absolute;top:0;height:8px;background:var(--brand);opacity:.75;border-radius:4px;min-width:5px}}
.tl-mod{{font-family:ui-monospace,Menlo,monospace;color:var(--brand);margin-right:6px}}
.tl-out{{color:var(--muted);margin-left:8px;font-size:12px}}
.tl-desc{{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
details{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin-bottom:8px}}
summary{{cursor:pointer;font-weight:600;font-size:14px}}
ul.files,ul.plain{{margin:10px 0 4px;padding-left:20px}}
ul.files li{{margin-bottom:7px;font-size:14px}}
.fp{{font-size:11px;color:var(--muted);font-family:ui-monospace,Menlo,monospace;word-break:break-all}}
ul.plain li{{margin-bottom:5px}}
code{{background:#f0f2f4;padding:1px 5px;border-radius:4px;font-size:12px;
 font-family:ui-monospace,Menlo,monospace;color:#4b5158}}
.muted{{color:var(--muted)}}
.warn{{background:#fffbeb;border:1px solid #f5e2b8;color:#8a6412;padding:10px 14px;border-radius:8px}}
.box{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 16px}}
.box.hl{{border-left:3px solid var(--brand)}}
.box.hl li{{margin-bottom:7px}}
footer{{margin-top:44px;padding-top:14px;border-top:1px solid var(--line);
 color:var(--muted);font-size:12px}}
@media(max-width:720px){{.tl-row{{grid-template-columns:110px 1fr}}.tl-track{{display:none}}
 .ruler{{display:none}}.wrap{{padding:20px 14px}}}}
@media print{{body{{background:#fff}}.wrap{{max-width:none}}details{{page-break-inside:avoid}}}}
</style></head><body><div class="wrap">
<header>
  <h1>工作日报　<span class="date">{e(d['date'])}</span> <span class="muted" style="font-size:16px">{e(d['weekday'])}</span></h1>
  <div class="sub">{summary}</div>
</header>

<h2>今日概览</h2>
<div class="cards">{cards}</div>

<h2>今日完成</h2>
{tasks_html}

<h2>问题与难点</h2>
{prob_html}

<h2>工作时间线</h2>
<div class="box">
<div class="ruler">{hours_ruler}</div>
{tl}
</div>

<h2>成果清单</h2>
{('<div class="box hl">' + hl_html + '</div>') if hl_html else ''}
<h3 style="font-size:14px;color:var(--muted);margin:18px 0 6px">代码提交（{len(d['commits'])} 次）</h3>
<div class="box"><ul class="plain">{commits_html}</ul></div>

<h2>知识库记录情况</h2>
{wiki_html}

<h2>待跟进</h2>
<div class="box">{fu_html}</div>

<footer>
 事实层由 daily_facts.py 从 {d['event_count']} 条会话事件中抽取（时间/文件/提交/知识库均为真实记录）；
 叙事由 {'DeepSeek' if story else '（未启用，纯事实版）'} 生成。
 生成于 {now_cn():%Y-%m-%d %H:%M}。
</footer>
</div></body></html>"""


def build_digest(facts, story):
    """月报只需要要点，不需要时间线和文件全清单。"""
    return {
        "date": facts["date"],
        "weekday": facts["weekday"],
        "summary": (story or {}).get("summary", ""),
        "active_minutes": facts["active_minutes"],
        "span": f"{facts['span_start']}-{facts['span_end']}" if facts["span_start"] else "",
        "modules": facts["task_codes"],
        "projects": list(facts["projects"].keys()),
        "files_total": facts.get("files_total", 0),
        "commits": [c["msg"] for c in facts["commits"]],
        "pushes": facts["pushes"],
        "wiki_writes": [w["file"].replace("/Users/chuaishoushou/AI/wiki/", "")
                        for w in facts["wiki_writes"]],
        "skills": facts["skills"],
        "tasks": (story or {}).get("tasks", []),
        "problems": (story or {}).get("problems", []),
        "highlights": (story or {}).get("highlights", []),
        "followups": (story or {}).get("followups", []),
    }


# --------------------------------------------------------------------------
def write_run_record(record):
    RUN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_LOGS.mkdir(parents=True, exist_ok=True)
    with open(RUNS_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    ts = record["started_at"].replace("-", "").replace(":", "").replace(" ", "-")[:15]
    path = RUN_REPORTS_DIR / f"daily-v2-{ts}.md"
    icon = {"ok": "✅ 成功", "degraded": "⚠️ 降级（纯事实版）",
            "empty": "⭕ 当日无记录", "error": "❌ 失败"}.get(record["status"], record["status"])
    lines = [
        "# 工作日报 v2 · 运行报告", "",
        f"- **目标日期**: {record['date']}",
        f"- **开始/结束**: {record['started_at']} → {record['finished_at']}，耗时 {record['duration_s']}s",
        f"- **触发方式**: {record['trigger']}" + ("（dry-run）" if record["dry_run"] else ""),
        f"- **状态**: {icon}",
        f"- **原料**: {record['event_count']} 条事件 / {record.get('session_count', 0)} 个会话 / "
        f"{record['block_count']} 个工作块 / "
        f"{record['project_count']} 个工程 / {record['material_chars']} 字符",
        f"- **抽取事实**: 改动 {record['files_total']} 文件、提交 {record['commit_count']} 次、"
        f"知识库写入 {record['wiki_writes']} 处",
        f"- **输出**: `{record.get('md_file', '—')}`",
        f"           `{record.get('html_file', '—')}`",
    ]
    if record.get("llm_error"):
        lines += ["", "## ⚠️ LLM 叙事失败（已降级为纯事实版）", "", "```", record["llm_error"], "```"]
    if record.get("error"):
        lines += ["", "## ❌ 错误", "", "```", record["error"], "```"]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="目标日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--yesterday", action="store_true", help="生成昨天的日报（定时任务用）")
    ap.add_argument("--dry-run", action="store_true", help="只打印不落盘")
    ap.add_argument("--no-llm", action="store_true", help="跳过 LLM，只出事实版")
    ap.add_argument("--trigger", default="manual", choices=["manual", "scheduled", "slash"])
    args = ap.parse_args()

    if args.date:
        day = args.date
    elif args.yesterday:
        day = (now_cn() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        day = now_cn().strftime("%Y-%m-%d")

    record = generate_day(day, trigger=args.trigger, dry_run=args.dry_run,
                          no_llm=args.no_llm, verbose=True)
    sys.exit(0 if record["status"] in ("ok", "degraded", "empty") else 1)


def generate_day(day, trigger="manual", dry_run=False, no_llm=False,
                 verbose=True, archive_existing=False, facts=None):
    """生成某一天的日报，返回本次运行的台账 record。

    批量回填（backfill_reports.py）与命令行都走这里，保证两条路产出完全一致。
    archive_existing=True 时，覆盖前先把已有的旧日报归档，不直接丢弃。
    facts 传入已采集好的事实层可跳过重复扫描（回填时用，扫一遍 500+ 会话文件不便宜）。
    """
    def say(*a, **kw):
        if verbose:
            print(*a, **kw)

    start, t0 = now_cn(), time.time()
    record = {
        "task": "daily-report", "version": "v2", "date": day,
        "started_at": start.strftime("%Y-%m-%d %H:%M:%S"),
        "trigger": trigger, "dry_run": dry_run, "status": "error",
        "event_count": 0, "block_count": 0, "project_count": 0, "material_chars": 0,
        "files_total": 0, "commit_count": 0, "wiki_writes": 0,
    }

    try:
        say(f"== Step 1: 采集 {day} 全部项目目录的工作事实 ==")
        if facts is None:
            facts = collect_day(day)
        record.update(
            event_count=facts["event_count"], block_count=len(facts["blocks"]),
            session_count=facts.get("session_count", 0),
            project_count=len(facts["projects"]), files_total=facts.get("files_total", 0),
            commit_count=len(facts["commits"]), wiki_writes=len(facts["wiki_writes"]),
        )
        say(f"   事件 {facts['event_count']}｜会话 {facts.get('session_count',0)}"
            f"｜工作块 {len(facts['blocks'])}"
            f"｜工程 {len(facts['projects'])}｜改动 {facts.get('files_total',0)} 文件"
            f"｜提交 {len(facts['commits'])}｜知识库 {len(facts['wiki_writes'])}")

        story = None
        if not facts["blocks"]:
            # 休息日不是故障，别再往失败率里记一笔
            record["status"] = "empty"
            md = (f"# 工作日报 {day}（{facts['weekday']}）\n\n"
                  f"当日没有检测到任何工作记录。\n")
            html_out = render_html(facts, None)
            say("   当日无工作记录")
        else:
            material = render_material(facts)
            record["material_chars"] = len(material)
            say(f"   原料 {len(material)} 字符")

            if no_llm:
                record["status"] = "degraded"
                say("== Step 2: 跳过 LLM（--no-llm）==")
            else:
                say("== Step 2: 调用 DeepSeek 生成叙事 ==")
                try:
                    api_key = load_api_key()
                    if not api_key:
                        raise RuntimeError("未找到 API key（DEEPSEEK_API_KEY 或 ~/.config/deepseek/api_key）")
                    story = call_deepseek(api_key, material, n_blocks=len(facts["blocks"]))
                    record["status"] = "ok"
                    say(f"   概括：{story.get('summary','')}")
                    say(f"   任务 {len(story.get('tasks',[]))} 条，"
                        f"问题 {len(story.get('problems',[]))} 条")
                except Exception as ex:
                    record["llm_error"] = f"{type(ex).__name__}: {ex}"
                    record["status"] = "degraded"
                    print(f"   [warn] {day} LLM 失败，降级为纯事实版：{record['llm_error']}",
                          file=sys.stderr)

            md = render_markdown(facts, story)
            html_out = render_html(facts, story)

        if dry_run:
            say("\n" + md)
            say("(--dry-run，未落盘)")
        else:
            for p in (REPORTS_DIR, HTML_DIR, DIGEST_DIR):
                p.mkdir(parents=True, exist_ok=True)
            md_file = REPORTS_DIR / f"{day}.md"
            html_file = HTML_DIR / f"{day}.html"
            digest_file = DIGEST_DIR / f"{day}.json"
            if archive_existing and md_file.exists():
                record["archived_to"] = str(archive_old_report(md_file, html_file))
                say(f"   旧日报已归档：{record['archived_to']}")
            md_file.write_text(
                md + f"\n---\n\n<sub>由日报 v2 生成于 {now_cn():%Y-%m-%d %H:%M}"
                     f"（{trigger}）。事实层来自会话记录，可手工修改。</sub>\n",
                encoding="utf-8")
            html_file.write_text(html_out, encoding="utf-8")
            digest_file.write_text(
                json.dumps(build_digest(facts, story), ensure_ascii=False, indent=1),
                encoding="utf-8")
            record["md_file"], record["html_file"] = str(md_file), str(html_file)
            record["digest_file"] = str(digest_file)
            say(f"== Step 3: 已写入 ==\n   {md_file}\n   {html_file}\n   {digest_file}")

    except Exception as ex:
        record["error"] = f"{type(ex).__name__}: {ex}"
        print(f"[error] {day} {record['error']}", file=sys.stderr)

    record["finished_at"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    record["duration_s"] = round(time.time() - t0, 1)
    rp = write_run_record(record)
    say(f"[runs] {rp}")
    return record


def archive_old_report(md_file, html_file):
    """覆盖前把旧日报挪进 archive——知识库红线：删除一律 mv 到 archive，不 rm。"""
    dest = ARCHIVE_ROOT / now_cn().strftime("%Y-%m-%d") / "replaced-daily-reports"
    dest.mkdir(parents=True, exist_ok=True)
    for src in (md_file, html_file):
        if src.exists():
            src.replace(dest / src.name)
    return dest


if __name__ == "__main__":
    main()
