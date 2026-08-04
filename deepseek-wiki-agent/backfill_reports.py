#!/usr/bin/env python3
"""
历史日报回填：用当前规则重新生成指定日期范围的日报。

背景：2026-07 期间日报采集只扫了一个项目目录，导致 23/39 次运行失败、少数
"成功"的也只抓到零星会话。会话原始记录还在 ~/.claude/projects/，所以这些
日子的日报可以按真实数据重建。

保留策略（重要）：
  - runs.jsonl 执行台账**只追加不清理**，历史执行记录原样保留，回填记录以
    trigger=backfill 追加在后面，能看出哪天是什么时候重建的
  - 已存在的旧日报**先归档**到 wiki/archive/<今天>/replaced-daily-reports/
    再覆盖，不直接丢弃（知识库红线：删除一律 mv 到 archive）
  - 当天确实没有工作记录的日子直接跳过，不生成空日报文件

用法：
  python3 backfill_reports.py --from 2026-07-05 --to 2026-08-01
  python3 backfill_reports.py --from 2026-07-05 --to 2026-08-01 --dry-run    # 只看计划
  python3 backfill_reports.py --from 2026-07-05 --to 2026-08-01 --skip-existing
  python3 backfill_reports.py --from 2026-07-05 --to 2026-08-01 --no-llm     # 不花 API，纯事实版
  python3 backfill_reports.py --from 2026-07-05 --to 2026-08-01 --workers 1  # 串行
"""
import argparse
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from daily_facts import CN_TZ, collect_day  # noqa: E402
import run_daily_report as rdr  # noqa: E402
import run_daily_agent as rda  # noqa: E402

# runs.jsonl 与 run-reports 是并发写入点，串行化避免交错
_write_lock = threading.Lock()


def _serialize(module, fname):
    orig = getattr(module, fname)

    def wrapped(*a, **kw):
        with _write_lock:
            return orig(*a, **kw)

    setattr(module, fname, wrapped)


_serialize(rdr, "write_run_record")
_serialize(rda, "write_run_record")
# ai-digest.md 是整文件「读-改-写」，并发跑会互相覆盖，必须串行
_serialize(rda, "apply_digest")
_serialize(rda, "append_log")


def daterange(d0, d1):
    cur = d0
    while cur <= d1:
        yield cur
        cur += timedelta(days=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="d_from", required=True, help="起始日期 YYYY-MM-DD")
    ap.add_argument("--to", dest="d_to", required=True, help="结束日期 YYYY-MM-DD（含）")
    ap.add_argument("--task", default="daily", choices=["daily", "wiki", "both"],
                    help="回填哪一类：daily=工作日报，wiki=知识库摘要，both=两个都补")
    ap.add_argument("--dry-run", action="store_true", help="只列出将要处理的日期，不生成")
    ap.add_argument("--skip-existing", action="store_true", help="已有日报的日子也跳过（daily）")
    ap.add_argument("--force", action="store_true",
                    help="连已有摘要的日期也重跑 wiki。慎用：模型换个说法就绕过字面去重，"
                         "同一天重刷会堆出语义重复的条目")
    ap.add_argument("--no-llm", action="store_true", help="跳过 DeepSeek，只出纯事实版（仅 daily）")
    ap.add_argument("--workers", type=int, default=3, help="并发数，默认 3")
    args = ap.parse_args()

    d0 = datetime.strptime(args.d_from, "%Y-%m-%d").date()
    d1 = datetime.strptime(args.d_to, "%Y-%m-%d").date()
    if d1 < d0:
        sys.exit("结束日期早于起始日期")
    today = datetime.now(CN_TZ).date()
    if d1 > today:
        d1 = today
        print(f"[info] 结束日期收敛到今天 {d1}")

    days = [d.strftime("%Y-%m-%d") for d in daterange(d0, d1)]
    print(f"== 扫描 {len(days)} 天的会话记录 ==")

    # wiki 摘要已有哪些日期，用于 --skip-existing 判断
    digest_days = set()
    if args.task in ("wiki", "both") and rda.DIGEST_FILE.exists():
        _, secs = rda.parse_digest_sections(rda.DIGEST_FILE.read_text(encoding="utf-8"))
        digest_days = set(secs)

    plan = []
    for i, day in enumerate(days, 1):
        facts = collect_day(day)
        n = len(facts["blocks"])
        has_daily = (rdr.REPORTS_DIR / f"{day}.md").exists()
        has_wiki = day in digest_days
        todo = []
        if n:
            # 日报默认重建（旧的本来就是错的），wiki 摘要默认只补缺失
            if args.task in ("daily", "both") and not (has_daily and args.skip_existing):
                todo.append("daily")
            if args.task in ("wiki", "both") and not (has_wiki and not args.force):
                todo.append("wiki")
        if n == 0:
            state = "跳过（当日无工作记录）"
        elif not todo:
            state = "跳过（已有产出）"
        else:
            marks = {"daily": "日报" + ("(重建)" if has_daily else "(新建)"),
                     "wiki": "摘要" + ("(补充)" if has_wiki else "(新增)")}
            state = " + ".join(marks[t] for t in todo)
            plan.append((day, facts, todo))
        print(f"  [{i:>2}/{len(days)}] {day}  事件 {facts['event_count']:>6}"
              f"  块 {n:>3}  提交 {len(facts['commits']):>3}   {state}")

    print(f"\n== 待处理 {len(plan)} 天 ==")
    if args.dry_run:
        print("(--dry-run，未执行)")
        return
    if not plan:
        print("没有需要处理的日期。")
        return

    t0 = time.time()
    done, failed = [], []
    counter = {"n": 0}

    ICON = {"ok": "✅", "partial": "⚠️ ", "degraded": "⚠️ ", "empty": "⭕", "error": "❌"}

    def work(item):
        day, facts, todo = item
        recs = []
        if "daily" in todo:
            recs.append(rdr.generate_day(day, trigger="backfill", no_llm=args.no_llm,
                                         verbose=False, archive_existing=True, facts=facts))
        if "wiki" in todo:
            # 只补知识摘要，不重做页面体检——历史体检已经改过页面，
            # 回填时再改一遍既无意义又有风险
            recs.append(rda.run_once(day, trigger="backfill", no_lint=True,
                                     verbose=False))
        with _write_lock:
            counter["n"] += 1
            i = counter["n"]
        bits = []
        for r in recs:
            tag = ICON.get(r["status"], "?")
            if r.get("task") == "wiki-daily":
                bits.append(f"{tag}摘要{r.get('digest_points', 0)}条")
            else:
                bits.append(f"{tag}日报(块{r['block_count']}/提交{r['commit_count']})")
        err = next((r.get("error") or r.get("llm_error") for r in recs
                    if r.get("error") or r.get("llm_error")), "")
        print(f"  [{i:>2}/{len(plan)}] {day}  " + "  ".join(bits)
              + (f"  ({err[:60]})" if err else ""), flush=True)
        return recs

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as ex:
        for recs in ex.map(work, plan):
            for rec in recs:
                (done if rec["status"] in ("ok", "partial", "degraded", "empty")
                 else failed).append(rec)

    dur = round(time.time() - t0)
    ok = sum(1 for r in done if r["status"] == "ok")
    deg = sum(1 for r in done if r["status"] in ("degraded", "partial"))
    pts = sum(r.get("digest_points", 0) for r in done if r.get("task") == "wiki-daily")
    print(f"\n== 回填完成，耗时 {dur // 60} 分 {dur % 60} 秒 ==")
    print(f"   成功 {ok} 项，降级/部分 {deg} 项，失败 {len(failed)} 项"
          + (f"；新增知识点 {pts} 条" if pts else ""))
    if failed:
        print("   失败日期（可单独重跑）：")
        for r in failed:
            print(f"     {r['date']}  {r.get('error', '')[:80]}")
        print(f"   重跑命令：python3 backfill_reports.py --from <日期> --to <日期>")
    print(f"   日报目录：{rdr.REPORTS_DIR}")
    print(f"   台账（历史记录已保留，回填以 trigger=backfill 追加）：{rdr.RUNS_JSONL}")


if __name__ == "__main__":
    main()
