#!/usr/bin/env python3
"""
Deepseek 工作月报生成脚本（与 run_daily_report.py 同一套架构）。

流程：
  1. 采集目标月原料：
     - 当月全部日报 agent-logs/daily-reports/YYYY-MM-*.md
     - 平台真实数据 agent-logs/monthly-reports/data/YYYY-MM-platform.json（开发任务+客服记录，
       来自 FLUX 业务运营管理系统，可由浏览器会话抓取或 ServerAction 接口直连获取）
     - 补充材料 agent-logs/monthly-reports/data/YYYY-MM-notes.json（可选，如 AI 会话挖掘合成结果）
  2. 平台数据在本地做确定性聚合（类型/状态/客户/工时/日节奏），图表数据不经过 LLM，保证真实
  3. 调 Deepseek 生成叙事部分（总览/亮点/项目主题/问题攻坚），只允许基于原料写作；
     失败或 --no-llm 时降级：直接采用 notes.json 里的 synthesis 作为叙事
  4. 注入标准化模板 monthly_report_template.html，写出 agent-logs/monthly-reports/YYYY-MM.html
  5. 在 runs.jsonl（task=monthly-report）与 run-reports/ 记录执行情况

用法：
  python3 run_monthly_report.py                        # 生成上个月的月报（定时任务默认）
  python3 run_monthly_report.py --month 2026-06        # 生成指定月
  python3 run_monthly_report.py --month 2026-06 --no-llm   # 不调 LLM，直接用 notes.json 叙事
  python3 run_monthly_report.py --trigger scheduled    # 定时任务触发

API key 读取顺序：环境变量 DEEPSEEK_API_KEY → ~/.config/deepseek/api_key 文件
"""
import argparse
import calendar
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
AGENT_LOGS = Path("/Users/chuaishoushou/AI/wiki/wiki/agent-logs")
RUNS_DIR = AGENT_LOGS
RUN_REPORTS_DIR = AGENT_LOGS / "run-reports"
DAILY_DIR = AGENT_LOGS / "daily-reports"
MONTHLY_DIR = AGENT_LOGS / "monthly-reports"
DATA_DIR = MONTHLY_DIR / "data"
TEMPLATE = SCRIPT_DIR / "monthly_report_template.html"

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
KEY_FILE = Path.home() / ".config" / "deepseek" / "api_key"

CN_TZ = timezone(timedelta(hours=8))
PERSON = "许满意 (XUMY)"


def now_cn():
    return datetime.now(CN_TZ)


def load_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return None


def prev_month_str():
    first = now_cn().replace(day=1)
    prev_last = first - timedelta(days=1)
    return prev_last.strftime("%Y-%m")


# ---------- 原料采集 ----------

# 整月日报在月报原料里最多占这么多字符，剩余额度留给平台数据与补充材料
DAILY_MATERIAL_BUDGET = 40000


def slim_digest(d, budget):
    """把一天的 digest 压到预算内：先砍细节，再砍条数，保证每天都有代表进月报。"""
    out = {
        "date": d.get("date"), "weekday": d.get("weekday"),
        "summary": d.get("summary", ""),
        "minutes": d.get("active_minutes"),
        "modules": (d.get("modules") or [])[:8],
        "files": d.get("files_total"), "pushes": d.get("pushes"),
        "wiki": len(d.get("wiki_writes") or []),
        "tasks": [{"title": t.get("title", ""), "what": (t.get("what") or "")[:80],
                   "outcome": t.get("outcome", "")} for t in (d.get("tasks") or [])[:9]],
        "problems": [(p.get("problem") or "")[:70] for p in (d.get("problems") or [])[:4]],
        "highlights": [str(h)[:70] for h in (d.get("highlights") or [])[:4]],
        "commits": [str(c)[:70] for c in (d.get("commits") or [])[:8]],
    }
    s = json.dumps(out, ensure_ascii=False)
    if len(s) <= budget:
        return s
    out["commits"] = out["commits"][:3]
    out["tasks"] = [{"title": t["title"], "outcome": t["outcome"]} for t in out["tasks"]]
    s = json.dumps(out, ensure_ascii=False)
    return s if len(s) <= budget else s[:budget]


def collect_daily_reports(month):
    """采集当月日报作为叙事原料。

    优先读日报 v2 产出的 digest/<日期>.json（要点版）；没有 digest 的日子回退读
    完整 .md（v1 时代的老日报）。整月按天数均分字符预算——v2 日报比 v1 长得多，
    直接拼接会在 material[:60000] 处被截断，导致月底那些天完全进不了月报。
    """
    digest_dir = DAILY_DIR / "digest"
    days = sorted(DAILY_DIR.glob(f"{month}-*.md"))
    if not days:
        return []
    per_day = max(600, DAILY_MATERIAL_BUDGET // len(days))
    texts, n_digest, n_md = [], 0, 0
    for p in days:
        day = p.stem
        dj = digest_dir / f"{day}.json"
        if dj.exists():
            try:
                texts.append(f"----- 日报要点 {day} -----\n"
                             + slim_digest(json.loads(dj.read_text(encoding="utf-8")), per_day))
                n_digest += 1
                continue
            except Exception as e:
                print(f"[warn] digest {day} 解析失败，回退读 md: {e}", file=sys.stderr)
        texts.append(f"----- 日报 {day} -----\n"
                     + p.read_text(encoding="utf-8", errors="ignore")[:per_day])
        n_md += 1
    print(f"   日报原料：digest {n_digest} 份 + 完整 md {n_md} 份，"
          f"每天预算 {per_day} 字符")
    return texts


def load_json_if_exists(path):
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[warn] {path.name} 解析失败: {e}", file=sys.stderr)
    return None


# ---------- 确定性聚合（图表数据不经过 LLM） ----------

def aggregate(platform, month):
    dev = (platform or {}).get("dev_tasks", [])
    svc = (platform or {}).get("service_records", [])

    def count_by(rows, key):
        out = {}
        for r in rows:
            out[r.get(key, "未知")] = out.get(r.get(key, "未知"), 0) + 1
        return out

    customers = {}
    for r in dev:
        c = customers.setdefault(r.get("customer", "未知"), {"dev": 0, "svc": 0})
        c["dev"] += 1
    for r in svc:
        c = customers.setdefault(r.get("customer", "未知"), {"dev": 0, "svc": 0})
        c["svc"] += 1
    customer_counts = [
        {"name": k, "dev": v["dev"], "svc": v["svc"]}
        for k, v in sorted(customers.items(), key=lambda kv: -(kv[1]["dev"] + kv[1]["svc"]))
    ]

    year, mon = int(month[:4]), int(month[5:7])
    ndays = calendar.monthrange(year, mon)[1]
    daily = [{"day": d, "dev": 0, "svc": 0} for d in range(1, ndays + 1)]
    for rows, key in ((dev, "dev"), (svc, "svc")):
        for r in rows:
            cd = r.get("compDate", "")
            if cd.startswith(month):
                try:
                    daily[int(cd[8:10]) - 1][key] += 1
                except (ValueError, IndexError):
                    pass

    return {
        "devTypeCounts": count_by(dev, "type"),
        "devStatusCounts": count_by(dev, "status"),
        "svcTypeCounts": count_by(svc, "type"),
        "customerCounts": customer_counts,
        "dailyActivity": daily,
        "devHours": round(sum(float(r.get("hours") or 0) for r in dev), 1),
        "svcHours": round(sum(float(r.get("hours") or 0) for r in svc), 1),
    }


# ---------- 叙事生成 ----------

NARRATIVE_SCHEMA_HINT = """{
  "overview_short": "一句话月度总结（hero 副标题，30-50 字）",
  "overview": "总览段落（120-200 字：本月工作全貌、重点投入方向、总体结果）",
  "highlights": ["4-6 条月度亮点，每条一句话"],
  "themes": [{"name": "主题名", "category": "Vue迁移|任务修复|客户项目|基础设施|知识库|环境运维|AI工具链|其他",
              "detail": "3-6 句详述：做了什么、涉及模块/任务号/客户、解决了什么问题、结果",
              "dates": "如 06-10~06-18"}],
  "problems_solved": ["8-15 条：问题现象 → 最终解法，每条一句话"]
}"""


def call_deepseek_narrative(api_key, month, material):
    system_prompt = (
        "你是月度工作报告撰写助手。用户是 FLUX 公司技术顾问许满意（9 年后端），"
        "工作围绕 FLUX TMS 系统（老栈 tmsdevelop/tmsv6 与新栈 Vue sce-vtms）、客户项目支持、"
        "个人知识库与 AI 工具链建设。根据给定原料写月报的叙事部分，输出 JSON（不要 markdown 包裹），"
        "结构如下：\n" + NARRATIVE_SCHEMA_HINT + "\n"
        "要求：只根据原料写、不编造；主题 8-14 个、跨日期把同一件事串成一个主题；"
        "保留任务号/模块名/客户名等具体信息；中文，技术名词保留原文。"
    )
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"目标月份：{month}\n\n===== 原料 =====\n{material}"},
        ],
        "temperature": 0.3,
        "max_tokens": 6000,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        DEEPSEEK_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return json.loads(data["choices"][0]["message"]["content"])


def narrative_from_notes(notes):
    """降级路径：直接采用 notes.json 里的 synthesis（如 AI 会话挖掘合成结果）。"""
    syn = (notes or {}).get("synthesis") or {}
    if not syn:
        return None
    return {
        "overview_short": (notes or {}).get("overview_short", ""),
        "overview": (notes or {}).get("overview", ""),
        "highlights": syn.get("highlights", []),
        "themes": syn.get("themes", []),
        "problems_solved": syn.get("problems_solved", []),
    }


# ---------- 渲染 ----------

def render_html(month, platform, agg, narrative, meta):
    month_label = f"{int(month[:4])} 年 {int(month[5:7])} 月"
    dev = (platform or {}).get("dev_tasks", [])
    svc = (platform or {}).get("service_records", [])
    stats = [
        {"label": "开发任务完成", "value": len(dev), "suffix": " 项", "note": "开发任务平台 · 实际完成时间在本月"},
        {"label": "客户服务完成", "value": len(svc), "suffix": " 条", "note": "客户服务记录 · 处理完成"},
        {"label": "投入总工时", "value": round(agg["devHours"] + agg["svcHours"], 1), "suffix": " h", "note": f"开发 {agg['devHours']}h + 客服 {agg['svcHours']}h"},
        {"label": "服务客户数", "value": len([c for c in agg["customerCounts"] if c["name"] not in ("富勒科技(FLUX)", "未知")]), "suffix": " 家", "note": "外部客户（不含内部内测任务）"},
    ]
    data = {
        "month": month,
        "monthLabel": month_label,
        "person": PERSON,
        "stats": stats,
        "devTasks": dev,
        "svcRecords": svc,
        "agg": agg,
        "narrative": narrative,
        "meta": meta,
    }
    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.replace("{{TITLE}}", f"{month_label} 工作月报 · {PERSON}")
    payload = json.dumps(data, ensure_ascii=False)
    start = html.index("/*__DATA_START__*/")
    end = html.index("/*__DATA_END__*/") + len("/*__DATA_END__*/")
    html = html[:start] + payload + html[end:]
    return html


# ---------- 运行记录 ----------

def write_run_record(record):
    RUN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUNS_DIR / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    ts = record["started_at"].replace("-", "").replace(":", "").replace(" ", "-")[:15]
    report = RUN_REPORTS_DIR / f"monthly-{ts}.md"
    status_icon = "✅ 成功" if record["status"] == "ok" else "❌ 失败"
    lines = [
        "# Deepseek 工作月报 · 运行报告",
        "",
        f"- **目标月份**: {record['month']}",
        f"- **开始时间**: {record['started_at']}（北京时间），耗时 {record['duration_s']} 秒",
        f"- **触发方式**: {record['trigger']}",
        f"- **状态**: {status_icon}",
        f"- **原料**: 日报 {record['daily_count']} 份 · 平台数据 {'有' if record['has_platform'] else '无'}"
        f"（开发 {record['dev_count']} / 客服 {record['svc_count']}）· 补充材料 {'有' if record['has_notes'] else '无'}",
        f"- **叙事来源**: {record.get('narrative_source', '-')}",
        f"- **月报输出**: `{record.get('output_file', '未写入')}`",
    ]
    if record.get("error"):
        lines += ["", "## ❌ 错误", "", "```", record["error"], "```"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--month", default=prev_month_str(), help="目标月 YYYY-MM，默认上个月")
    ap.add_argument("--no-llm", action="store_true", help="不调 Deepseek，直接用 notes.json 的 synthesis 作叙事")
    ap.add_argument("--trigger", default="manual", choices=["manual", "scheduled", "slash"])
    args = ap.parse_args()
    month = args.month

    start = now_cn()
    t0 = time.time()
    record = {
        "task": "monthly-report", "month": month,
        "started_at": start.strftime("%Y-%m-%d %H:%M:%S"),
        "trigger": args.trigger, "status": "error",
        "daily_count": 0, "dev_count": 0, "svc_count": 0,
        "has_platform": False, "has_notes": False,
    }

    try:
        if not re.match(r"^\d{4}-\d{2}$", month):
            raise RuntimeError(f"月份格式不对: {month}")

        print(f"== Step 1: 采集 {month} 原料 ==")
        dailies = collect_daily_reports(month)
        platform = load_json_if_exists(DATA_DIR / f"{month}-platform.json")
        notes = load_json_if_exists(DATA_DIR / f"{month}-notes.json")
        # 统计口径：「完成待重测」= 测试打回，不计入当月完成（2026-07-06 与用户约定）
        dev_excluded = 0
        if platform:
            all_dev = platform.get("dev_tasks", [])
            kept = [t for t in all_dev if t.get("status") != "完成待重测"]
            dev_excluded = len(all_dev) - len(kept)
            platform["dev_tasks"] = kept
        record["daily_count"] = len(dailies)
        record["has_platform"] = platform is not None
        record["has_notes"] = notes is not None
        record["dev_count"] = len((platform or {}).get("dev_tasks", []))
        record["svc_count"] = len((platform or {}).get("service_records", []))
        print(f"(日报 {len(dailies)} 份 / 平台数据 {'有' if platform else '无'} / 补充材料 {'有' if notes else '无'})")
        if not dailies and not platform and not notes:
            raise RuntimeError(f"{month} 没有任何原料（日报/平台数据/补充材料都缺失），无法生成月报")

        print("== Step 2: 本地聚合平台数据（图表用，不经过 LLM） ==")
        agg = aggregate(platform, month)

        print("== Step 3: 生成叙事 ==")
        narrative, source = None, None
        material_parts = []
        if notes:
            material_parts.append("===== AI 会话挖掘合成结果（覆盖全月、最重要的叙事依据） =====\n" + json.dumps(notes, ensure_ascii=False))
        if dailies:
            material_parts.append("===== 当月日报 =====\n" + "\n\n".join(dailies))
        if platform:
            brief = [f"- [{r.get('type')}] {r.get('subject')}（{r.get('customer')}，{r.get('compDate')}）"
                     for r in (platform.get("dev_tasks", []) + platform.get("service_records", []))]
            material_parts.append("===== 平台完成清单 =====\n" + "\n".join(brief))
        material = "\n\n".join(material_parts)[:60000]

        if not args.no_llm:
            api_key = load_api_key()
            if api_key:
                try:
                    narrative = call_deepseek_narrative(api_key, month, material)
                    source = "deepseek"
                except Exception as e:
                    print(f"[warn] Deepseek 调用失败，降级用 notes: {e}", file=sys.stderr)
            else:
                print("[warn] 未找到 API key，降级用 notes", file=sys.stderr)
        if narrative is None:
            narrative = narrative_from_notes(notes)
            source = "notes-synthesis"
        if narrative is None:
            raise RuntimeError("叙事生成失败：Deepseek 不可用且 notes.json 无 synthesis")
        record["narrative_source"] = source
        print(f"(叙事来源: {source}，主题 {len(narrative.get('themes', []))} 个)")

        print("== Step 4: 注入模板渲染 ==")
        meta = {
            "generatedAt": now_cn().strftime("%Y-%m-%d %H:%M"),
            "trigger": args.trigger,
            "fetchedAt": (platform or {}).get("fetched_at", "-"),
            "dailyReportCount": len(dailies),
            "sessionCount": (notes or {}).get("session_count"),
            "devExcluded": dev_excluded,
        }
        html = render_html(month, platform, agg, narrative, meta)
        MONTHLY_DIR.mkdir(parents=True, exist_ok=True)
        out_file = MONTHLY_DIR / f"{month}.html"
        out_file.write_text(html, encoding="utf-8")
        record["output_file"] = str(out_file)
        print(f"== 月报已写入 {out_file} ==")
        record["status"] = "ok"
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
        print(f"[error] {record['error']}", file=sys.stderr)

    record["finished_at"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    record["duration_s"] = round(time.time() - t0, 1)
    report_path = write_run_record(record)
    print(f"[runs] 执行记录: {RUNS_DIR / 'runs.jsonl'}")
    print(f"[runs] 本次报告: {report_path}")
    sys.exit(0 if record["status"] == "ok" else 1)


if __name__ == "__main__":
    main()
