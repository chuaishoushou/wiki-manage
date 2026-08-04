#!/usr/bin/env python3
"""
Deepseek 接入 flux-wiki 的自主维护脚本（会议演示用骨架）。

流程：
  1. 读取今天的 Claude Code 会话记录，抽取用户消息作为"今天遇到的问题"原料（敏感串打码）
  2. 调 Deepseek Chat API：
     a) 生成今日知识摘要 → 追加写入 domains/personal/ai-digest.md
     b) 体检一份现有 wiki 页面 → 指出问题并给出改写全文
  3. 落盘：摘要走追加；改写走"先归档旧版到 archive/，再覆盖"（wiki 红线：不 rm）
  4. 记录：wiki 库根 log.md 追加一行；本目录 runs/ 写入结构化执行记录
     - runs/runs.jsonl              每次运行一行 JSON（机器可读）
     - runs/run-YYYYMMDD-HHMMSS.md  单次运行报告（人可读，演示用）

用法：
  python3 run_daily_agent.py                        # 完整跑一次（trigger=manual）
  python3 run_daily_agent.py --dry-run              # 只看 Deepseek 输出，不落盘
  python3 run_daily_agent.py --trigger scheduled    # 定时任务触发（记录触发来源）
  python3 run_daily_agent.py --target domains/personal/preferences.md  # 指定体检页面

API key 读取顺序：环境变量 DEEPSEEK_API_KEY → ~/.config/deepseek/api_key 文件
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
# 采集层与日报共用一套事实抽取：原先这里自己抓 user 消息，
# 分不清真人输入和 tool_result，经常「读到 3 个会话、0 字符原料」。
from daily_facts import collect_day, render_material  # noqa: E402

WIKI_ROOT = Path("/Users/chuaishoushou/AI/wiki")
WRITE_LAYER = WIKI_ROOT / "wiki"
# 执行历史统一放 wiki 知识库的 agent-logs 区（台账 + 单次报告）
RUNS_DIR = WRITE_LAYER / "agent-logs"
RUN_REPORTS_DIR = RUNS_DIR / "run-reports"
DOMAINS = WRITE_LAYER / "domains"
LOG_MD = WRITE_LAYER / "log.md"
DIGEST_FILE = DOMAINS / "personal" / "ai-digest.md"
# 全部项目目录。早先这里只写了 -Users-chuaishoushou-AI 一个目录，而实际工作分散在
# FLUX-V10 / FLUX-tmsdevelop 等二十多个目录里，导致绝大多数会话根本没被读到。
PROJECTS_ROOT = Path("/Users/chuaishoushou/.claude/projects")

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"
KEY_FILE = Path.home() / ".config" / "deepseek" / "api_key"

# 固定使用北京时间 (UTC+8) 判定"今天"，避免运行环境时区差异导致漏采集
CN_TZ = timezone(timedelta(hours=8))

# 体检目标白名单外规则：这些内容绝不发给外部 API
EXCLUDE_DIRS = {"flux-credentials"}
EXCLUDE_FILES = {"ai-digest.md"}
MIN_TARGET_BYTES = 800      # 太小的页面没体检价值
MAX_TARGET_BYTES = 15000    # 太大的页面改写全文容易被 max_tokens 截断


def now_cn():
    return datetime.now(CN_TZ)


def today_str():
    return now_cn().strftime("%Y-%m-%d")


def redact(text):
    """把 API key / 密码类字样打码后再外发，降低泄密面。"""
    text = re.sub(r"sk-[A-Za-z0-9]{16,}", "sk-***REDACTED***", text)
    text = re.sub(r"(?i)(password|passwd|pwd|secret|token)(\s*[=:]\s*)\S+", r"\1\2***", text)
    return text


def load_api_key():
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if KEY_FILE.exists():
        return KEY_FILE.read_text().strip()
    return None


def collect_day_material(day, max_chars=24000):
    """采集目标自然日的工作原料，返回 (原料文本, 事实层, 工作块数)。

    直接复用 daily_facts 的事实抽取——它扫全部项目目录、按自然日切片，
    并且把改动文件、git 提交、卡点信号都结构化出来了，比原先只抓聊天文本
    能提炼出多得多的知识点。如果当天日报已经跑过，再把日报提炼好的
    problems/highlights 附上，知识点质量更高。
    """
    facts = collect_day(day)
    parts = [render_material(facts, max_chars=max_chars - 4000)]

    digest_file = (RUNS_DIR / "daily-reports" / "digest" / f"{day}.json")
    if digest_file.exists():
        try:
            d = json.loads(digest_file.read_text(encoding="utf-8"))
            brief = {
                "当天概括": d.get("summary", ""),
                "已归纳的任务": [t.get("title") for t in (d.get("tasks") or [])],
                "已识别的问题": d.get("problems") or [],
                "已识别的产出": d.get("highlights") or [],
            }
            parts.append("===== 当天日报已提炼的要点（可作为知识点线索）=====\n"
                         + json.dumps(brief, ensure_ascii=False))
        except Exception as e:
            print(f"[warn] 读取日报 digest 失败，忽略: {e}", file=sys.stderr)

    raw = "\n\n".join(parts)
    return redact(raw[:max_chars]), facts, len(facts["blocks"])


def build_kb_index(max_chars=9000):
    """知识库已有页面的一行式索引（路径 + summary/标题），喂给 LLM 判重用。

    只给索引不给正文：101 个页面全文太大，而判「这条知识是否已经有专门页面」
    靠标题与 summary 已经足够；真要补充正文，走 update_suggestions 人工确认。
    """
    lines = []
    for p in sorted(DOMAINS.rglob("*.md")):
        rel_parts = set(p.relative_to(DOMAINS).parts)
        if rel_parts & EXCLUDE_DIRS or p.name in EXCLUDE_FILES:
            continue
        summary = ""
        try:
            head = p.read_text(encoding="utf-8", errors="ignore")[:2000]
        except OSError:
            continue
        m = re.search(r"^summary:\s*(.+)$", head, re.M)
        if m:
            summary = m.group(1).strip()
        else:
            m = re.search(r"^#\s+(.+)$", head, re.M)
            summary = m.group(1).strip() if m else ""
        lines.append(f"- {p.relative_to(WRITE_LAYER)} — {summary[:80]}")
    text = "\n".join(lines)
    return text[:max_chars]


def existing_digest_items(max_chars=36000):
    """ai-digest.md 里已经沉淀过的全部条目（新日期优先），喂给 LLM 判重用。"""
    if not DIGEST_FILE.exists():
        return ""
    _, sections = parse_digest_sections(DIGEST_FILE.read_text(encoding="utf-8"))
    out, total = [], 0
    for day in sorted(sections, reverse=True):
        body = sections[day].strip()
        if total + len(body) > max_chars:
            break
        out.append(body)
        total += len(body)
    return "\n".join(out)


def recent_review_targets(n=8):
    """读台账里最近体检过的页面，用于避免短期内反复体检同几页。"""
    path = RUNS_DIR / "runs.jsonl"
    if not path.exists():
        return set()
    seen = []
    try:
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("review_target"):
                seen.append(r["review_target"])
    except OSError:
        return set()
    return set(seen[-n:])


def pick_review_target(override=None, day=None):
    """挑一份现有 wiki 页面做体检。

    按目标日期确定性轮换（同一天选同一份，便于复现），并跳过最近刚体检过的页面；
    凭证域(flux-credentials)与自动生成文件永不入选——不把敏感内容发给外部 API。
    """
    if override:
        p = (WRITE_LAYER / override) if not override.startswith("/") else Path(override)
        if p.exists():
            return p
        print(f"[warn] 指定的体检目标不存在: {override}，回退到自动轮换", file=sys.stderr)

    pool = []
    for p in sorted(DOMAINS.rglob("*.md")):
        rel_parts = set(p.relative_to(DOMAINS).parts)
        if rel_parts & EXCLUDE_DIRS or p.name in EXCLUDE_FILES:
            continue
        size = p.stat().st_size
        if MIN_TARGET_BYTES <= size <= MAX_TARGET_BYTES:
            pool.append(p)
    if not pool:
        return None

    recent = recent_review_targets()
    fresh = [p for p in pool if str(p.relative_to(WRITE_LAYER)) not in recent]
    candidates = fresh or pool          # 全都体检过了就允许重来
    seed = (day or today_str()).encode()
    idx = int(hashlib.sha256(seed).hexdigest(), 16) % len(candidates)
    return candidates[idx]


def call_deepseek(api_key, problems_text, review_path, review_content, day,
                  timeout=180, retries=2):
    system_prompt = (
        "你是公司内部知识库(flux-wiki)的自主维护助手。用户是 FLUX 物流 TMS 方向的后端技术顾问。\n"
        "给你的原料是程序从当天操作记录中抽取的**客观事实**（时间、改动文件、git 提交、"
        "报错、卡点都是真的），不要编造原料里没有的内容。\n\n"
        "必须严格按 JSON 输出：\n"
        "1) digest_markdown: 提炼当天**知识库里还没有的、有复用价值的新知识**，"
        "用 markdown 列表写，每条前缀 `- [目标日期] `，条数按当天内容多少定，"
        "通常 2-5 条，内容特别丰富时可到 8 条。\n"
        "   什么算有复用价值：踩过的坑与根因、技术决策与选型理由、某个模块/接口/配置的运作机制、"
        "排查手法、环境与部署的固定套路、用户明确表达的偏好或流程规范。\n"
        "   什么不算：今天完成了什么任务（那是日报的事）、提交推送等过程动作、"
        "一次性的琐碎操作、没有结论的尝试。\n"
        "   **判重（最重要的规则）**：材料里给了「知识库已有页面索引」和「已沉淀条目全集」。"
        "每提炼一条前先对照这两份清单——同一结论换个说法也算重复，一律不要输出；"
        "只有新的坑、新的机制、新的结论才能进 digest_markdown。\n"
        "   每条要写清「结论/机制」本身，让半年后的自己不看上下文也能读懂；"
        "带上模块号、文件名、配置项等关键标识。没有新知识就返回空字符串——"
        "**宁可空着，也不要为了凑数复述旧知识**。\n"
        "2) update_suggestions: 数组，可为空。当某条知识**已有专门页面**（见索引），"
        "但当天出现了值得补进该页面的新细节/新结论/更正时，不要写进 digest_markdown，"
        "放到这里：[{\"page\": \"索引里的页面路径\", \"point\": \"建议补充的要点，一句话\"}]。"
        "拿不准是重复还是补充时放这里，不要进 digest。\n"
        "3) lint_issue: 简要指出'待体检页面'中一个具体问题（内容过时、表述重复、"
        "结构混乱、条目冲突等）。没发现问题返回空字符串。\n"
        "4) lint_fixed_content: lint_issue 非空时给出该页面修正后的完整 markdown 全文"
        "（必须以 --- 开头保留原有 frontmatter，只修正指出的问题，不要删减无关内容）。否则返回空字符串。\n"
        "只输出 JSON，不要任何多余文字。"
    )
    user_prompt = (
        f"目标日期：{day}\n\n"
        f"===== 当天工作事实（敏感串已打码） =====\n{problems_text or '(当天没有可读取的工作记录)'}\n\n"
        f"===== 知识库已有页面索引（判重用） =====\n{build_kb_index() or '(空)'}\n\n"
        f"===== 已沉淀条目全集（判重用，来自 ai-digest.md） =====\n"
        f"{existing_digest_items() or '(空)'}\n\n"
        f"===== 待体检页面 {review_path} =====\n{review_content}\n"
    )

    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.3,
        "max_tokens": 8000,
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
            # 原先只报「HTTP Error 400」，看不出到底哪里不合法
            detail = ""
            try:
                detail = e.read().decode("utf-8", "ignore")[:400]
            except Exception:
                pass
            last_err = RuntimeError(f"HTTP {e.code}: {detail}")
        except Exception as e:
            # 7 月出现过多次 SSL UNEXPECTED_EOF，重试一般就过去了
            last_err = e
        if attempt < retries:
            time.sleep(3 * (attempt + 1))
    raise last_err


def append_log(line):
    with open(LOG_MD, "a", encoding="utf-8") as f:
        f.write(line.rstrip("\n") + "\n")


def _bigrams(text):
    text = re.sub(r"[\s\-\[\]（）()【】`*，。；：、,.;:]+", "", text)
    return {text[i:i + 2] for i in range(len(text) - 1)}


def is_similar(a, b, threshold=0.55):
    """字符 bigram Jaccard 相似度，用于挡「几乎同一句话换个说法」的重复条目。

    同一模块的不同知识重合度一般 <0.4（只有模块号和通用词相同），
    同一结论的复述通常 >0.6，0.55 取中间偏保守。
    """
    A, B = _bigrams(a), _bigrams(b)
    if not A or not B:
        return False
    return len(A & B) / len(A | B) >= threshold


def drop_semantic_duplicates(digest_markdown):
    """代码级判重兜底：新条目与库内全部已有条目比相似度，高相似的丢弃。

    LLM 判重（提示词里已要求对照已有知识）能挡大部分，但实测它偶尔会把
    「和已有条目几乎逐字相同」的结论当成新知识放出来——最后一道闸在这里。
    返回 (保留的 markdown, 被丢弃的条目列表)。
    """
    fresh = [l.strip() for l in digest_markdown.splitlines() if l.strip().startswith("- ")]
    if not fresh:
        return "", []
    existing = []
    if DIGEST_FILE.exists():
        _, sections = parse_digest_sections(DIGEST_FILE.read_text(encoding="utf-8"))
        for body in sections.values():
            existing += [l.strip() for l in body.splitlines() if l.strip().startswith("- ")]
    kept, dropped = [], []
    for item in fresh:
        dup = next((e for e in existing if is_similar(item, e)), None)
        # 新条目之间也可能互相重复
        if dup is None:
            dup = next((k for k in kept if is_similar(item, k)), None)
        if dup:
            dropped.append(item)
        else:
            kept.append(item)
    return "\n".join(kept), dropped


DIGEST_HEADER = (
    "---\nsummary: Deepseek 每日知识摘要（自动生成，人工可编辑）\n"
    "tags: [自动摘要, deepseek]\ndomain: personal\ndomain_confidence: medium\n"
    "shared_scope: domain\nsource_paths: []\nstatus: active\n"
    "date_created: {d}\ndate_updated: {d}\n---\n\n# 每日知识摘要\n"
)
_SEC_RE = re.compile(r"^## +(\d{4}-\d{2}-\d{2})", re.M)


def parse_digest_sections(text):
    """把 ai-digest.md 拆成 (前言, {日期: 正文})。

    历史段落标题有 `## 2026-07-05 00:09` 和 `## 2026-07-05` 两种写法，
    统一按日期归并；同一天多次运行的内容合并保留，不丢历史。
    """
    marks = list(_SEC_RE.finditer(text))
    if not marks:
        return text.rstrip() + "\n", {}
    preamble = text[:marks[0].start()].rstrip() + "\n"
    sections = {}
    for i, m in enumerate(marks):
        day = m.group(1)
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end]
        body = body.split("\n", 1)[1] if "\n" in body else ""   # 去掉标题行残留
        body = body.strip()
        if not body:
            continue
        sections[day] = (sections[day] + "\n" + body) if day in sections else body
    return preamble, sections


def render_digest(preamble, sections):
    out = [preamble.rstrip(), ""]
    for day in sorted(sections):
        out += [f"## {day}", sections[day].strip(), ""]
    return "\n".join(out) + "\n"


def apply_digest(digest_markdown, day):
    """写入某天的知识摘要，段落按日期排序落盘（不用运行时间戳当标题）。

    与该日期已有条目**去重合并**，从不整段覆盖——重跑同一天时既不会产生重复条目，
    也不会把之前沉淀的（可能人工编辑过的）判断顶掉。
    """
    if not digest_markdown.strip():
        return False
    DIGEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    text = DIGEST_FILE.read_text(encoding="utf-8") if DIGEST_FILE.exists() \
        else DIGEST_HEADER.format(d=day)
    preamble, sections = parse_digest_sections(text)

    def bullets(body):
        return [l.strip() for l in body.splitlines() if l.strip().startswith("- ")]

    have = bullets(sections.get(day, ""))
    fresh = [l for l in bullets(digest_markdown) if l not in have]
    if not fresh and have:
        return False                      # 全是已有内容，无需改动文件
    sections[day] = "\n".join(have + fresh) if (have or fresh) else digest_markdown.strip()
    DIGEST_FILE.write_text(render_digest(preamble, sections), encoding="utf-8")
    return True


SUGGESTIONS_FILE = RUNS_DIR / "wiki-update-suggestions.md"


def apply_suggestions(suggestions, day):
    """把「建议补充到已有页面」的要点记入待办清单（字面查重，重复不追加）。

    不直接改正式页面——补充是否成立要人工判断，自动改只留给带防护的 lint 通道。
    """
    if not suggestions:
        return 0
    if SUGGESTIONS_FILE.exists():
        existing = SUGGESTIONS_FILE.read_text(encoding="utf-8")
    else:
        existing = ("# Wiki 补充建议清单（自动生成）\n\n"
                    "wiki-daily 判定「知识库已有专门页面，但当天出现了新细节」时记在这里，"
                    "由人工确认后补进对应页面；处理完的行手动删掉即可。\n\n")
    added = 0
    lines = []
    for s in suggestions:
        line = f"- [{day}] `{s['page']}` — {s['point']}"
        if line not in existing:
            lines.append(line)
            added += 1
    if added:
        SUGGESTIONS_FILE.write_text(existing.rstrip() + "\n" + "\n".join(lines) + "\n",
                                    encoding="utf-8")
    return added


def apply_lint_fix(review_path, lint_issue, lint_fixed_content, record):
    """带防护的体检改写：截断/格式异常一律拒绝，宁可不改不能改坏。"""
    if not lint_issue.strip() or not lint_fixed_content.strip():
        return False
    original = review_path.read_text(encoding="utf-8")
    fixed = lint_fixed_content
    if not fixed.lstrip().startswith("---"):
        record["lint_rejected"] = "改写结果缺失 frontmatter（不以 --- 开头），拒绝写入"
        return False
    if len(fixed) < len(original) * 0.6:
        record["lint_rejected"] = (
            f"改写结果长度 {len(fixed)} 不足原文 {len(original)} 的 60%，疑似被截断，拒绝写入"
        )
        return False
    archive_dir = WRITE_LAYER / "archive" / today_str()
    archive_dir.mkdir(parents=True, exist_ok=True)
    backup_path = archive_dir / (review_path.name + ".bak")
    shutil.copy2(review_path, backup_path)
    review_path.write_text(fixed, encoding="utf-8")
    record["archive_path"] = str(backup_path)
    return True


def write_run_record(record):
    """执行记录双写：runs.jsonl（机器可读） + run-reports/run-<ts>.md（人可读报告）。"""
    RUN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RUNS_DIR / "runs.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    ts = record["started_at"].replace("-", "").replace(":", "").replace(" ", "-")[:15]
    report = RUN_REPORTS_DIR / f"run-{ts}.md"
    status_icon = {
        "ok": "✅ 成功",
        "partial": "⚠️ 部分完成（体检改写被拒）",
        "degraded": "⚠️ 无产出（有工作记录但没提炼出可沉淀知识）",
        "empty": "⭕ 当日无工作记录",
        "error": "❌ 失败",
    }.get(record["status"], record["status"])
    lines = [
        "# Deepseek Wiki 自主维护 · 运行报告",
        "",
        f"- **目标日期**: {record.get('date', '—')}",
        f"- **开始时间**: {record['started_at']}（北京时间）",
        f"- **结束时间**: {record['finished_at']}，耗时 {record['duration_s']} 秒",
        f"- **触发方式**: {record['trigger']}" + ("（dry-run，未落盘）" if record["dry_run"] else ""),
        f"- **状态**: {status_icon}",
        f"- **原料**: {record['raw_chars']} 字符｜工作块 {record.get('block_count', 0)} 段"
        f"｜会话 {record.get('session_count', 0)} 个"
        f"｜涉及工程 {record.get('project_count', 0)} 个",
        f"- **提炼知识点**: {record.get('digest_points', 0)} 条",
        "",
        "## ① 知识摘要",
        "",
    ]
    if record.get("digest_written"):
        lines += [f"已追加到 `{DIGEST_FILE}`：", "", record.get("digest_markdown", "").strip()]
    elif record.get("digest_markdown", "").strip():
        lines += ["（dry-run 未写入）", "", record["digest_markdown"].strip()]
    else:
        lines += ["对照已有知识判重后，当天没有需要新增的知识点。"]
    sugg = record.get("update_suggestions") or []
    if sugg:
        lines += ["", "## ①½ 建议补充到已有页面（人工确认后处理）", ""]
        lines += [f"- `{s['page']}` — {s['point']}" for s in sugg]
        lines += ["", ("（dry-run 未落盘）" if record["dry_run"]
                       else f"（已记入 `{SUGGESTIONS_FILE}`）")]
    dropped = record.get("dropped_duplicates") or []
    if dropped:
        lines += ["", "## ①¾ 相似度闸拦下的重复条目（未写入，供抽查）", ""]
        lines += [f"- {d}" for d in dropped]
    lines += ["", f"## ② 知识库体检（目标: `{record.get('review_target', '无')}`）", ""]
    if record.get("lint_issue", "").strip():
        lines += [f"**发现问题**: {record['lint_issue']}", ""]
        if record.get("lint_applied"):
            lines += [f"**处理**: 已自动改写，旧版本归档至 `{record.get('archive_path')}`"]
        elif record.get("lint_rejected"):
            lines += [f"**处理**: 未写入 —— {record['lint_rejected']}"]
        else:
            lines += ["**处理**: dry-run 未写入"]
    else:
        lines += ["未发现需要修正的问题。"]
    if record.get("error"):
        lines += ["", "## ❌ 错误", "", "```", record["error"], "```"]
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", help="目标日期 YYYY-MM-DD，默认今天")
    ap.add_argument("--yesterday", action="store_true", help="处理昨天（定时任务用）")
    ap.add_argument("--dry-run", action="store_true", help="只调用 Deepseek 展示结果，不落盘")
    ap.add_argument("--trigger", default="manual",
                    choices=["manual", "scheduled", "slash", "backfill"],
                    help="触发来源，写入执行记录")
    ap.add_argument("--target", default=None, help="指定体检页面（相对写入层或绝对路径），默认按日期轮换")
    ap.add_argument("--no-lint", action="store_true", help="只做知识摘要，跳过页面体检")
    args = ap.parse_args()

    if args.date:
        day = args.date
    elif args.yesterday:
        day = (now_cn() - timedelta(days=1)).strftime("%Y-%m-%d")
    else:
        day = today_str()

    record = run_once(day, trigger=args.trigger, dry_run=args.dry_run,
                      target=args.target, no_lint=args.no_lint,
                      verbose=True)
    sys.exit(0 if record["status"] in ("ok", "partial", "empty", "degraded") else 1)


def run_once(day, trigger="manual", dry_run=False, target=None, no_lint=False,
             verbose=True):
    """跑一天的知识沉淀 + 页面体检，返回台账 record。命令行与回填共用。"""
    def say(*a, **kw):
        if verbose:
            print(*a, **kw)

    start = now_cn()
    t0 = time.time()
    record = {
        "task": "wiki-daily",
        "date": day,
        "started_at": start.strftime("%Y-%m-%d %H:%M:%S"),
        "trigger": trigger,
        "dry_run": dry_run,
        "status": "error",
        "raw_chars": 0,
        "session_count": 0,
        "project_count": 0,
        "block_count": 0,
    }

    try:
        api_key = load_api_key()
        if not api_key:
            raise RuntimeError("未找到 API key：请设置 DEEPSEEK_API_KEY 或写入 ~/.config/deepseek/api_key")

        say(f"== Step 1: 采集 {day} 的工作原料 ==")
        problems_text, facts, n_blocks = collect_day_material(day)
        record["raw_chars"] = len(problems_text)
        record["block_count"] = n_blocks
        record["session_count"] = facts.get("session_count", 0)
        record["project_count"] = len(facts["projects"])
        say(f"   原料 {len(problems_text)} 字符｜会话 {record['session_count']}"
            f"｜工作块 {n_blocks}｜工程 {record['project_count']}")

        if n_blocks == 0:
            # 当天没干活就不是故障，也别硬编知识点
            record["status"] = "empty"
            say("   当天无工作记录，跳过（不写入摘要）")
            record["finished_at"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
            record["duration_s"] = round(time.time() - t0, 1)
            rp = write_run_record(record)
            say(f"[runs] 本次报告: {rp}")
            return record

        review_path, review_content = None, ""
        if no_lint:
            say("== Step 2: 跳过页面体检（--no-lint）==")
        else:
            say("== Step 2: 选取体检目标页面 ==")
            review_path = pick_review_target(target, day)
            if review_path is None:
                say("   [warn] 没有符合条件的可体检页面，本次只做知识摘要")
            else:
                review_content = review_path.read_text(encoding="utf-8")
                record["review_target"] = str(review_path.relative_to(WRITE_LAYER))
                say(f"   目标: {review_path}")

        say("== Step 3: 调用 Deepseek ==")
        result = call_deepseek(api_key, problems_text,
                               review_path or "(本次不体检)", review_content, day)
        # LLM 判重之上再过一道代码级相似度闸：几乎逐字重复的条目直接丢弃
        kept_md, dropped = drop_semantic_duplicates(result.get("digest_markdown", ""))
        record["digest_markdown"] = kept_md
        record["dropped_duplicates"] = dropped
        record["lint_issue"] = result.get("lint_issue", "") if review_path else ""
        sugg = result.get("update_suggestions") or []
        record["update_suggestions"] = [
            {"page": str(s.get("page", ""))[:200], "point": str(s.get("point", ""))[:300]}
            for s in sugg if isinstance(s, dict) and s.get("point")
        ]
        n_points = len([l for l in record["digest_markdown"].splitlines() if l.strip().startswith("-")])
        record["digest_points"] = n_points
        say(f"   新知识 {n_points} 条｜建议补充已有页面 {len(record['update_suggestions'])} 条"
            + (f"｜相似度闸拦下 {len(dropped)} 条" if dropped else "")
            + (f"；体检发现问题：{record['lint_issue'][:60]}" if record["lint_issue"] else ""))

        if dry_run:
            say("\n" + record["digest_markdown"])
            say("(--dry-run，不落盘)")
            record["status"] = "ok" if n_points else "empty"
        else:
            say("== Step 4: 落盘 ==")
            did_digest = apply_digest(record["digest_markdown"], day)
            record["digest_written"] = did_digest
            say(f"   [digest] {'已写入 ' + str(DIGEST_FILE) if did_digest else '无新知识，跳过'}")

            n_sugg = apply_suggestions(record.get("update_suggestions") or [], day)
            if n_sugg:
                say(f"   [suggest] {n_sugg} 条补充建议已记入 {SUGGESTIONS_FILE.name}")

            did_lint = False
            if review_path:
                did_lint = apply_lint_fix(review_path, record["lint_issue"],
                                          result.get("lint_fixed_content", ""), record)
            record["lint_applied"] = did_lint
            if did_lint:
                say(f"   [lint] 已改写 {review_path.name}，旧版归档 {record['archive_path']}")
            elif record.get("lint_rejected"):
                say(f"   [lint] 未写入 —— {record['lint_rejected']}")

            if did_digest or did_lint:
                parts = []
                if did_digest:
                    parts.append(f"ai-digest.md 写入 {day} 摘要 {n_points} 条")
                if did_lint:
                    parts.append(f"{review_path.name} 体检改写(旧版已归档)")
                append_log(f"- [{today_str()}] Deepseek 自主维护({trigger})：{'；'.join(parts)}")
                say("   [log] 已写入 wiki log.md")

            # 状态要如实反映产出：什么都没沉淀就不能记 ok，否则连着二十天空转也没人发现。
            # 判重生效后「无新知识」会更常见，有补充建议同样算有效产出。
            if record.get("lint_rejected"):
                record["status"] = "partial"
            elif did_digest or did_lint or n_sugg:
                record["status"] = "ok"
            else:
                record["status"] = "degraded"
                record["note"] = ("当天有工作记录，但判重后无新知识、无补充建议、"
                                  "也未改写任何页面")
                say("   [warn] 本次没有任何产出，标记 degraded")
    except Exception as e:
        record["error"] = f"{type(e).__name__}: {e}"
        print(f"[error] {day} {record['error']}", file=sys.stderr)

    record["finished_at"] = now_cn().strftime("%Y-%m-%d %H:%M:%S")
    record["duration_s"] = round(time.time() - t0, 1)
    report_path = write_run_record(record)
    say(f"[runs] 执行记录: {RUNS_DIR / 'runs.jsonl'}")
    say(f"[runs] 本次报告: {report_path}")
    return record


if __name__ == "__main__":
    main()
