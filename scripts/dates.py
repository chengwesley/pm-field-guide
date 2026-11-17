#!/usr/bin/env python3
"""日期與工作天工具：查星期、檢查文件中的星期標註、加減工作天、排時程。只用 Python 標準函式庫。

讓 Claude 寫時程時「算出」星期幾與工作天，避免把星期標錯（例如每個日期都差一天）。

用法範例：
    # 1) 查星期（短日期的年份依 --today 推算）
    python dates.py weekday 2026-11-17 11/20 2026/12/25

    # 2) 交付前檢查文件裡「日期（星期）」是否標對；有錯 exit code = 1
    python dates.py check schedule.md --today 2026-11-13

    # 3) 從 11/13 往後加 10 個工作天，跳過假日檔裡的日期、補班日照常上班
    python dates.py add 2026-11-13 10 --holidays holidays.txt --makeup-workdays makeup.txt

    # 4) 依 CSV（工作項目,工作天,緩衝天,前置）排出起訖日
    python dates.py plan tasks.csv --start 2026-11-16 --holidays holidays.txt

假日說明：本工具不內建任何國定假日。假日與補班日只來自使用者提供的檔案，
請以行政院人事行政總處公布的「政府行政機關辦公日曆表」為準。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import date, timedelta

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# argparse 繁中化
# ---------------------------------------------------------------------------

_ZH_MESSAGES = {
    "usage: ": "用法：",
    "positional arguments": "位置參數",
    "options": "選項",
    "subcommands": "子命令",
    "show this help message and exit": "顯示說明後離開",
    " (default: %(default)s)": "（預設：%(default)s）",
    "argument %(argument_name)s: %(message)s": "參數 %(argument_name)s：%(message)s",
    "unrecognized arguments: %s": "無法辨識的參數：%s",
    "the following arguments are required: %s": "缺少必要參數：%s",
    "expected one argument": "需要一個值",
    "expected at most one argument": "最多只能有一個值",
    "expected at least one argument": "至少需要一個值",
    "invalid %(type)s value: %(value)r": "%(value)r 不是有效的值",
    "invalid choice: %(value)r (choose from %(choices)s)": "無效的選項 %(value)r（可選：%(choices)s）",
    "ambiguous option: %(option)s could match %(matches)s": "選項 %(option)s 不明確，可能是 %(matches)s",
    "%(prog)s: error: %(message)s\n": "%(prog)s：錯誤：%(message)s\n",
    "%(heading)s:": "%(heading)s：",
}
argparse._ = lambda s: _ZH_MESSAGES.get(s, s)  # argparse 在執行期查詢模組層級的 _()


class InputError(Exception):
    """使用者輸入錯誤：以繁中訊息、exit code 2 結束，不顯示 traceback。"""


def fail(msg: str) -> None:
    raise InputError(msg)


# ---------------------------------------------------------------------------
# 日期解析與年份推算
# ---------------------------------------------------------------------------

WEEKDAY_ZH = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
LABEL_CHAR_TO_INDEX = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

# 短日期（只有月/日）比 today 早超過這麼多天，就推定為明年
ROLLOVER_DAYS = 183

YEAR_RULE_HELP = (
    "只寫月/日（如 11/17）時，年份取 --today 的年份；若該月日比 --today 早超過約 6 個月"
    f"（{ROLLOVER_DAYS} 天），則視為明年。例：today=2026-11-13 時，11/17→2026-11-17、"
    "1/5→2027-01-05、6/1→2026-06-01。"
)

FULL_RE = re.compile(r"^\s*(\d{4})\s*[-/.年]\s*(\d{1,2})\s*[-/.月]\s*(\d{1,2})\s*日?\s*$")
SHORT_RE = re.compile(r"^\s*(\d{1,2})\s*[-/月]\s*(\d{1,2})\s*日?\s*$")


def zh_weekday(d: date) -> str:
    return WEEKDAY_ZH[d.weekday()]


def fmt(d: date) -> str:
    return f"{d.isoformat()}（{zh_weekday(d)}）"


def make_date(y: int, m: int, d: int, original: str) -> date:
    try:
        return date(y, m, d)
    except ValueError:
        fail(f"{original!r} 不是有效的日期（{y} 年沒有 {m} 月 {d} 日）")


def infer_year(m: int, d: int, today: date, original: str) -> date:
    """月/日 → 完整日期。規則見 YEAR_RULE_HELP。"""
    if not (1 <= m <= 12 and 1 <= d <= 31):
        fail(f"{original!r} 不是有效的月/日")
    try:
        cand = date(today.year, m, d)
    except ValueError:
        cand = None  # 例如今年沒有 2/29
    if cand is not None and (today - cand).days <= ROLLOVER_DAYS:
        return cand
    if cand is None:
        # 今年不存在該日（2/29）：依同一規則判斷是今年還是明年，今年不存在則報錯
        probe = date(today.year, m, 28)
        if (today - probe).days <= ROLLOVER_DAYS:
            fail(f"{original!r}：{today.year} 年沒有 {m} 月 {d} 日，請寫完整年份")
    return make_date(today.year + 1, m, d, original)


def parse_date(text: str, today: date | None, allow_short: bool = True) -> date:
    raw = str(text).strip()
    mt = FULL_RE.match(raw)
    if mt:
        return make_date(int(mt.group(1)), int(mt.group(2)), int(mt.group(3)), raw)
    ms = SHORT_RE.match(raw)
    if ms:
        if not allow_short or today is None:
            fail(f"{raw!r} 缺少年份，這裡請寫完整日期，例如 2026-11-17")
        return infer_year(int(ms.group(1)), int(ms.group(2)), today, raw)
    fail(f"無法辨識日期 {raw!r}，請用 2026-11-17、2026/11/17 或 11/17 的格式")


def parse_today(text: str | None) -> date:
    if text is None:
        return date.today()
    return parse_date(text, None, allow_short=False)


# ---------------------------------------------------------------------------
# 工作天日曆
# ---------------------------------------------------------------------------

def read_date_list(path: str, what: str) -> set[date]:
    """讀取一行一個日期的檔案；# 之後為註解；日期後可接說明文字（以空白分隔）。必須寫完整年份。"""
    dates: set[date] = set()
    try:
        with open(path, encoding="utf-8-sig") as f:
            for no, line in enumerate(f, 1):
                content = line.split("#", 1)[0].strip()
                if not content:
                    continue
                token = content.split()[0].rstrip(",")
                if not FULL_RE.match(token):
                    fail(f"{what}檔 {path} 第 {no} 行：{token!r} 不是完整日期（請寫 2026-10-10 這種含年份的格式）")
                dates.add(parse_date(token, None, allow_short=False))
    except FileNotFoundError:
        fail(f"找不到{what}檔：{path}")
    except UnicodeDecodeError:
        fail(f"無法以 UTF-8 讀取{what}檔：{path}")
    return dates


class WorkCalendar:
    def __init__(self, holidays: set[date] | None = None, makeup: set[date] | None = None):
        self.holidays = holidays or set()
        self.makeup = makeup or set()
        both = self.holidays & self.makeup
        if both:
            fail("下列日期同時出現在假日檔與補班日檔，請確認：" + "、".join(sorted(d.isoformat() for d in both)))
        self.has_holiday_file = holidays is not None
        self.has_makeup_file = makeup is not None

    def is_workday(self, d: date) -> bool:
        if d in self.makeup:
            return True
        if d in self.holidays:
            return False
        return d.weekday() < 5

    def why_off(self, d: date) -> str:
        if d in self.holidays:
            return "假日檔所列"
        if d.weekday() >= 5:
            return "週末"
        return ""

    def add_workdays(self, start: date, n: int) -> date:
        """從 start 起移動 n 個工作天（不含 start 當天）；n=0 回傳 start 本身。"""
        step = 1 if n >= 0 else -1
        d = start
        remaining = abs(n)
        guard = 0
        while remaining > 0:
            d += timedelta(days=step)
            guard += 1
            if guard > 366 * 50:
                fail("超過 50 年仍找不到足夠的工作天，請檢查假日檔")
            if self.is_workday(d):
                remaining -= 1
        return d

    def next_workday_on_or_after(self, d: date) -> date:
        guard = 0
        while not self.is_workday(d):
            d += timedelta(days=1)
            guard += 1
            if guard > 366 * 50:
                fail("超過 50 年仍找不到工作天，請檢查假日檔")
        return d

    def coverage_notes(self, *days: date) -> list[str]:
        notes = []
        if not self.has_holiday_file:
            notes.append("未提供假日檔：只跳過週六、週日，沒有扣除國定假日。請依當地政府公布的辦公日曆建立假日檔（--holidays）。")
        else:
            covered = {d.year for d in self.holidays} | {d.year for d in self.makeup}
            years = sorted({d.year for d in days})
            missing = [y for y in years if y not in covered]
            if missing:
                notes.append("假日檔沒有下列年份的任何日期，這些年份的國定假日可能沒扣到："
                             + "、".join(str(y) for y in missing))
        return notes


def build_calendar(args: argparse.Namespace) -> WorkCalendar:
    hol = read_date_list(args.holidays, "假日") if getattr(args, "holidays", None) else None
    mk = read_date_list(args.makeup_workdays, "補班日") if getattr(args, "makeup_workdays", None) else None
    return WorkCalendar(hol, mk)


# ---------------------------------------------------------------------------
# weekday
# ---------------------------------------------------------------------------

def cmd_weekday(args: argparse.Namespace) -> dict:
    today = parse_today(args.today)
    items = []
    for text in args.dates:
        d = parse_date(text, today)
        items.append({"input": text, "date": d.isoformat(), "weekday": zh_weekday(d)})
    return {"today": today.isoformat(), "dates": items}


def render_weekday(r: dict) -> str:
    lines = ["| 輸入 | 日期 | 星期 |", "|---|---|---|"]
    for it in r["dates"]:
        lines.append(f"| {it['input']} | {it['date']} | {it['weekday']} |")
    if any(not FULL_RE.match(it["input"]) for it in r["dates"]):
        lines += ["", f"（短日期的年份依 today = {r['today']} 推算：{YEAR_RULE_HELP}）"]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# check
# ---------------------------------------------------------------------------

# 英文星期：Mon／Monday、Tue／Tues／Tuesday…，首字大寫，可帶句點
_EN_DAY = (r"(?:Mon(?:day)?|Tue(?:s(?:day)?)?|Wed(?:nesday)?|Thu(?:r(?:s(?:day)?)?)?"
           r"|Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)")
EN_DAY_TO_INDEX = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}
_LABEL = (
    r"(?P<label>\s*(?:[（(]\s*(?:週|周|星期|禮拜)?\s*(?P<l1>[一二三四五六日天])\s*[）)]"
    r"|(?:週|周|星期|禮拜)\s*(?P<l2>[一二三四五六日天])"
    r"|[（(]\s*(?P<l3>" + _EN_DAY + r")\.?\s*[）)]"
    r"|,?\s*(?P<l4>" + _EN_DAY + r")\b(?![a-z])))"
)
# 日期本體：完整日期（含年份）、或月/日、月-日、M月D日
_DATE = (
    r"(?<![\d/.\-])(?:"
    r"(?P<y>\d{4})\s*(?P<ysep>[-/.])\s*(?P<ym>\d{1,2})\s*(?P=ysep)\s*(?P<yd>\d{1,2})(?![\d/])"
    r"|(?P<cy>\d{4})\s*年\s*(?P<cm>\d{1,2})\s*月\s*(?P<cd>\d{1,2})\s*日"
    r"|(?P<zm>\d{1,2})\s*月\s*(?P<zd>\d{1,2})\s*日"
    r"|(?P<m>\d{1,2})(?P<sep>[/\-])(?P<d>\d{1,2})(?![\d/\-.])"
    r")"
)
DATE_WITH_OPTIONAL_LABEL = re.compile(_DATE + r"(?:" + _LABEL + r")?")
URL_RE = re.compile(r"https?://\S+|www\.\S+")


def _resolve(m: re.Match, today: date) -> tuple[date | None, str, bool]:
    """回傳（日期或 None, 錯誤說明, 是否為不明確的「月-日」寫法）。"""
    g = m.groupdict()
    try:
        if g["y"]:
            return date(int(g["y"]), int(g["ym"]), int(g["yd"])), "", False
        if g["cy"]:
            return date(int(g["cy"]), int(g["cm"]), int(g["cd"])), "", False
        mm, dd = (g["zm"], g["zd"]) if g["zm"] else (g["m"], g["d"])
        return infer_year(int(mm), int(dd), today, f"{mm}/{dd}"), "", bool(g["sep"] == "-")
    except (ValueError, InputError):
        return None, "無效日期", bool(g.get("sep") == "-")


def cmd_check(args: argparse.Namespace) -> dict:
    today = parse_today(args.today)
    try:
        with open(args.file, encoding="utf-8-sig") as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        fail(f"找不到檔案：{args.file}")
    except UnicodeDecodeError:
        fail(f"無法以 UTF-8 讀取 {args.file}，請另存為 UTF-8")
    checked, unlabeled = [], []
    for no, line in enumerate(lines, 1):
        scan = URL_RE.sub(lambda mo: " " * len(mo.group(0)), line)  # 網址內的數字不算日期
        for m in DATE_WITH_OPTIONAL_LABEL.finditer(scan):
            text = line[m.start():m.end()].strip()
            d, err, dash_short = _resolve(m, today)
            label_ch = m.group("l1") or m.group("l2")
            label_en = m.group("l3") or m.group("l4")
            if label_ch or label_en:
                labeled = (LABEL_CHAR_TO_INDEX[label_ch] if label_ch
                           else EN_DAY_TO_INDEX[label_en[:3].lower()])
                entry = {"line": no, "text": text, "date": d.isoformat() if d else None,
                         "labeled": WEEKDAY_ZH[labeled],
                         "actual": zh_weekday(d) if d else None}
                if d is None:
                    entry["status"] = "錯誤"
                    entry["note"] = err
                else:
                    entry["status"] = "OK" if d.weekday() == labeled else "錯誤"
                checked.append(entry)
            else:
                # 「3-5 天」這類範圍很常見，未標星期的「月-日」寫法不列為日期警告
                if d is None or dash_short:
                    continue
                unlabeled.append({"line": no, "text": text, "date": d.isoformat(), "weekday": zh_weekday(d)})
    errors = sum(1 for c in checked if c["status"] != "OK")
    return {"file": args.file, "today": today.isoformat(), "checked": checked,
            "errors": errors, "unlabeled": unlabeled}


def render_check(r: dict) -> str:
    out = [f"# 星期標註檢查：{r['file']}", ""]
    if r["checked"]:
        out += ["| 行號 | 找到的文字 | 推算日期 | 標註星期 | 實際星期 | 結果 |", "|---:|---|---|---|---|---|"]
        for c in r["checked"]:
            actual = c["actual"] or c.get("note", "—")
            status = "OK" if c["status"] == "OK" else "**錯誤**"
            out.append(f"| {c['line']} | {c['text']} | {c['date'] or '—'} | {c['labeled']} | {actual} | {status} |")
    else:
        out.append("（沒有找到「日期＋星期」的標註）")
    out += ["", "## 未標星期的日期（警告）", ""]
    if r["unlabeled"]:
        out += ["| 行號 | 找到的文字 | 推算日期 | 實際星期 |", "|---:|---|---|---|"]
        for u in r["unlabeled"]:
            out.append(f"| {u['line']} | {u['text']} | {u['date']} | {u['weekday']} |")
    else:
        out.append("（無）")
    out += ["", "## 解讀", ""]
    total = len(r["checked"])
    if r["errors"]:
        out.append(f"- 共檢查 {total} 個星期標註，**{r['errors']} 個錯誤**，請依「實際星期」修正後再交付。")
    else:
        out.append(f"- 共檢查 {total} 個星期標註，全部正確。")
    if r["unlabeled"]:
        out.append(f"- 有 {len(r['unlabeled'])} 個日期沒有標星期；若是時程上的關鍵日期，建議補上，並再跑一次本檢查。"
                   "（分數如 1/3 也可能被列入，屬正常誤報）")
    out.append(f"- 只寫月/日的日期，年份依 today = {r['today']} 推算：{YEAR_RULE_HELP}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# add
# ---------------------------------------------------------------------------

def parse_int(text: str, name: str) -> int:
    raw = str(text).strip().replace("＋", "+").replace("－", "-").replace("−", "-")
    if not re.fullmatch(r"[+-]?\d+", raw):
        fail(f"{name} 必須是整數（可為負數），收到：{text!r}")
    return int(raw)


def cmd_add(args: argparse.Namespace) -> dict:
    today = parse_today(args.today)
    start = parse_date(args.start, today)
    n = parse_int(args.n, "N")
    cal = build_calendar(args)
    result = cal.add_workdays(start, n)
    notes = cal.coverage_notes(start, result)
    if n == 0 and not cal.is_workday(start):
        notes.append(f"起始日 {fmt(start)} 本身不是工作天（{cal.why_off(start)}），N=0 時照原樣回傳。")
    skipped = []
    lo, hi = (start, result) if result >= start else (result, start)
    d = lo
    while d <= hi:
        if d != start and not cal.is_workday(d):
            skipped.append({"date": d.isoformat(), "weekday": zh_weekday(d), "reason": cal.why_off(d)})
        d += timedelta(days=1)
    makeup_used = [x.isoformat() for x in sorted(cal.makeup) if lo <= x <= hi and x != start]
    return {"start": start.isoformat(), "start_weekday": zh_weekday(start), "n": n,
            "result": result.isoformat(), "result_weekday": zh_weekday(result),
            "calendar_days": (result - start).days, "skipped_non_workdays": skipped,
            "makeup_workdays_used": makeup_used, "notes": notes}


def render_add(r: dict) -> str:
    start = date.fromisoformat(r["start"])
    result = date.fromisoformat(r["result"])
    direction = "往後" if r["n"] >= 0 else "往前"
    out = ["| 項目 | 值 |", "|---|---|",
           f"| 起始日 | {fmt(start)} |",
           f"| 工作天 | {direction} {abs(r['n'])} 個工作天（不含起始日當天） |",
           f"| **結果** | **{fmt(result)}** |",
           f"| 跨越日曆天 | {abs(r['calendar_days'])} 天 |"]
    holi = [s for s in r["skipped_non_workdays"] if s["reason"] == "假日檔所列"]
    out += ["", "## 解讀", ""]
    out.append(f"- 期間跳過 {len(r['skipped_non_workdays'])} 個非工作天"
               + (f"，其中假日檔所列 {len(holi)} 天：" + "、".join(f"{h['date']}（{h['weekday']}）" for h in holi) if holi else "")
               + "。")
    if r["makeup_workdays_used"]:
        out.append("- 期間包含補班日（照常上班）：" + "、".join(r["makeup_workdays_used"]))
    for n in r["notes"]:
        out.append(f"- {n}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

PLAN_ALIASES = {
    "task": {"task", "工作項目", "項目", "任務"},
    "workdays": {"workdays", "工作天", "工作天數"},
    "buffer": {"buffer", "緩衝天", "緩衝", "緩衝天數"},
    "depends_on": {"depends_on", "前置", "前置項目", "depends"},
}
NO_DEP_TOKENS = {"-", "無", "none", "（無）", "(無)"}
DEP_SPLIT_RE = re.compile(r"[;；、]")


def _int_cell(text: str, col: str, line: int, minimum: int) -> int:
    raw = (text or "").strip()
    if raw == "" and col == "緩衝天":
        return 0
    if not re.fullmatch(r"\d+", raw):
        fail(f"第 {line} 行的「{col}」必須是整數（收到：{text!r}）；半天請先換算成整天")
    v = int(raw)
    if v < minimum:
        fail(f"第 {line} 行的「{col}」至少要 {minimum}")
    return v


def read_plan_csv(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                fail(f"CSV 是空的：{path}")
            mapping = {}
            for raw in reader.fieldnames:
                key = (raw or "").strip().lower()
                for canon, aliases in PLAN_ALIASES.items():
                    if key in {a.lower() for a in aliases}:
                        mapping[canon] = raw
            missing = [c for c in ("task", "workdays") if c not in mapping]
            if missing:
                names = {"task": "task／工作項目", "workdays": "workdays／工作天"}
                fail("CSV 缺少必要欄位：" + "、".join(names[c] for c in missing)
                     + f"（目前欄位：{', '.join(reader.fieldnames)}）")
            tasks = []
            for row in reader:
                line = reader.line_num
                if not any((v or "").strip() for v in row.values() if isinstance(v, str)):
                    continue
                name = (row.get(mapping["task"]) or "").strip()
                if not name:
                    fail(f"第 {line} 行缺少工作項目名稱")
                tasks.append({
                    "task": name,
                    "workdays": _int_cell(row.get(mapping["workdays"]), "工作天", line, 1),
                    "buffer": _int_cell(row.get(mapping["buffer"]) if "buffer" in mapping else "", "緩衝天", line, 0),
                    "depends_raw": (row.get(mapping["depends_on"]) or "").strip() if "depends_on" in mapping else "",
                    "line": line,
                })
    except FileNotFoundError:
        fail(f"找不到檔案：{path}")
    except UnicodeDecodeError:
        fail(f"無法以 UTF-8 讀取 {path}，請另存為 UTF-8 編碼的 CSV")
    except csv.Error as e:
        fail(f"CSV 格式錯誤：{e}")
    if not tasks:
        fail("CSV 沒有任何工作項目")
    seen = {}
    for t in tasks:
        if t["task"] in seen:
            fail(f"工作項目 {t['task']!r} 重複（第 {seen[t['task']]} 行與第 {t['line']} 行），名稱必須唯一")
        seen[t["task"]] = t["line"]
    for i, t in enumerate(tasks):
        raw = t["depends_raw"]
        if raw == "":
            t["depends"] = [tasks[i - 1]["task"]] if i > 0 else []
        elif raw.lower() in NO_DEP_TOKENS:
            t["depends"] = []
        else:
            deps = [x.strip() for x in DEP_SPLIT_RE.split(raw) if x.strip()]
            for dname in deps:
                if dname not in seen:
                    fail(f"第 {t['line']} 行的前置項目 {dname!r} 不存在於工作項目清單中")
                if dname == t["task"]:
                    fail(f"第 {t['line']} 行的工作項目不能以自己為前置")
            t["depends"] = deps
    return tasks


def cmd_plan(args: argparse.Namespace) -> dict:
    today = parse_today(args.today)
    project_start = parse_date(args.start, today)
    cal = build_calendar(args)
    tasks = read_plan_csv(args.file)
    by_name = {t["task"]: t for t in tasks}
    state: dict[str, str] = {}

    def schedule(t: dict) -> None:
        if state.get(t["task"]) == "done":
            return
        if state.get(t["task"]) == "visiting":
            fail(f"前置關係出現循環（涉及 {t['task']!r}），請檢查「前置」欄")
        state[t["task"]] = "visiting"
        if t["depends"]:
            for dname in t["depends"]:
                schedule(by_name[dname])
            latest_end = max(by_name[d]["end"] for d in t["depends"])
            start = cal.add_workdays(latest_end, 1)
        else:
            start = cal.next_workday_on_or_after(project_start)
        work_end = cal.add_workdays(start, t["workdays"] - 1)
        end = cal.add_workdays(work_end, t["buffer"]) if t["buffer"] else work_end
        t.update({"start": start, "work_end": work_end, "end": end})
        state[t["task"]] = "done"

    for t in tasks:
        schedule(t)

    first_start = min(t["start"] for t in tasks)
    final_end = max(t["end"] for t in tasks)
    span_workdays = sum(1 for k in range((final_end - first_start).days + 1)
                        if cal.is_workday(first_start + timedelta(days=k)))
    total_work = sum(t["workdays"] for t in tasks)
    total_buffer = sum(t["buffer"] for t in tasks)
    scheduled = total_work + total_buffer
    notes = cal.coverage_notes(first_start, final_end)
    if not cal.is_workday(project_start):
        notes.append(f"--start {fmt(project_start)} 不是工作天，第一個工作項目順延到 {fmt(first_start)}。")
    parallel = span_workdays < scheduled

    return {
        "project_start": project_start.isoformat(),
        "first_start": first_start.isoformat(),
        "final_end": final_end.isoformat(),
        "final_end_weekday": zh_weekday(final_end),
        "span_workdays": span_workdays,
        "span_calendar_days": (final_end - first_start).days + 1,
        "total_workdays": total_work,
        "total_buffer": total_buffer,
        "buffer_share": total_buffer / scheduled if scheduled else 0.0,
        "has_parallel_tasks": parallel,
        "tasks": [{
            "task": t["task"], "depends_on": t["depends"], "workdays": t["workdays"], "buffer": t["buffer"],
            "start": t["start"].isoformat(), "start_weekday": zh_weekday(t["start"]),
            "work_end": t["work_end"].isoformat(), "work_end_weekday": zh_weekday(t["work_end"]),
            "end": t["end"].isoformat(), "end_weekday": zh_weekday(t["end"]),
        } for t in tasks],
        "notes": notes,
    }


def render_plan(r: dict) -> str:
    out = ["# 時程表", "",
           "| 工作項目 | 前置 | 工作天 | 緩衝天 | 開始 | 工作完成 | 結束（含緩衝） |",
           "|---|---|---:|---:|---|---|---|"]
    for t in r["tasks"]:
        dep = "、".join(t["depends_on"]) if t["depends_on"] else "—"
        out.append(f"| {t['task']} | {dep} | {t['workdays']} | {t['buffer']} | "
                   f"{t['start']}（{t['start_weekday']}） | {t['work_end']}（{t['work_end_weekday']}） | "
                   f"{t['end']}（{t['end_weekday']}） |")
    out += ["", f"**最終完成日：{r['final_end']}（{r['final_end_weekday']}）**", "", "## 解讀", ""]
    out.append(f"- 從 {r['first_start']} 開始，到 {r['final_end']}（{r['final_end_weekday']}）結束，"
               f"共 {r['span_workdays']} 個工作天、{r['span_calendar_days']} 個日曆天。")
    out.append(f"- 所有工作項目合計：工作 {r['total_workdays']} 天＋緩衝 {r['total_buffer']} 天，"
               f"緩衝佔排定天數的 {r['buffer_share']:.1%}。")
    if r["total_buffer"] == 0:
        out.append("- 目前沒有任何緩衝天，任何一項延誤都會直接推遲完成日。")
    if r["has_parallel_tasks"]:
        out.append("- 有工作項目平行進行，所以各項天數加總大於整體工作天數。")
    out.append("- 每個項目的開始日是前置項目「結束（含緩衝）」後的下一個工作天；未填前置時預設接在上一列之後，填「-」或「無」則從專案開始日起算。")
    for n in r["notes"]:
        out.append(f"- {n}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

HOLIDAY_HELP = ("假日檔：一行一個完整日期（如 2026-10-10），# 後為註解，日期後可接說明。"
                "本工具不內建任何假日，請以行政院人事行政總處公布的辦公日曆表為準")
MAKEUP_HELP = "補班日檔（例如需上班的週六）：格式同假日檔，列出的日期一律視為工作天"
TODAY_HELP = "今天日期（推算短日期年份用），預設為系統今天。" + YEAR_RULE_HELP


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="dates.py",
        description="日期與工作天工具：查星期、檢查星期標註、加減工作天、排時程。"
                    "不內建國定假日；假日與補班日請依行政院人事行政總處辦公日曆表自行提供檔案。",
    )
    sub = parser.add_subparsers(dest="command", title="子命令", metavar="{weekday,check,add,plan}")
    sub.required = True

    pw = sub.add_parser("weekday", help="列出日期的星期（週一…週日）",
                        description="列出每個日期的中文星期。接受 2026-11-17、2026/11/17、11/17。" + YEAR_RULE_HELP)
    pw.add_argument("dates", nargs="+", metavar="DATE", help="一個或多個日期")
    pw.add_argument("--today", help=TODAY_HELP)
    pw.add_argument("--json", action="store_true", help="輸出 JSON")

    pc = sub.add_parser("check", help="檢查文件中「日期（星期）」的標註是否正確；有錯時 exit code 為 1",
                        description="掃描 Markdown／文字檔，找出 11/14（五）、11/14(五)、2026-11-17（週二）、"
                                    "11-17（一）、11/14 週五、11/14（星期五）、11月14日（五）、2026-11-17 (Tue)、11/17 (Tuesday) 等寫法並核對真實星期。"
                                    "另列出未標星期的日期（警告；不含「11-17」這種易與數字範圍混淆的寫法）。"
                                    "有任何標錯時 exit code = 1，全對為 0。" + YEAR_RULE_HELP)
    pc.add_argument("file", help="要檢查的 Markdown 或文字檔（UTF-8）")
    pc.add_argument("--today", help=TODAY_HELP)
    pc.add_argument("--json", action="store_true", help="輸出 JSON")

    pa = sub.add_parser("add", help="加減 N 個工作天（跳過週末與假日檔日期）",
                        description="從 START 起往後（N 為負數則往前）移動 N 個工作天，不含 START 當天。"
                                    "週六日與假日檔日期不算工作天；補班日檔的日期算工作天。")
    pa.add_argument("start", metavar="START", help="起始日期")
    pa.add_argument("n", metavar="N", help="工作天數，可為負數")
    pa.add_argument("--holidays", metavar="FILE", help=HOLIDAY_HELP)
    pa.add_argument("--makeup-workdays", metavar="FILE", help=MAKEUP_HELP)
    pa.add_argument("--today", help=TODAY_HELP)
    pa.add_argument("--json", action="store_true", help="輸出 JSON")

    pp = sub.add_parser("plan", help="依工作項目 CSV 排出每項起訖日",
                        description="CSV 欄位：task/工作項目、workdays/工作天，可選 buffer/緩衝天、depends_on/前置。"
                                    "前置留空＝接在上一列之後；填「-」或「無」＝從 --start 起算；"
                                    "多個前置以「;」或「、」分隔，取最晚結束者。每項佔用（工作天＋緩衝天）個工作天。")
    pp.add_argument("file", help="工作項目 CSV（UTF-8，可含 BOM）")
    pp.add_argument("--start", required=True, help="專案開始日（非工作天時順延到下一個工作天）")
    pp.add_argument("--holidays", metavar="FILE", help=HOLIDAY_HELP)
    pp.add_argument("--makeup-workdays", metavar="FILE", help=MAKEUP_HELP)
    pp.add_argument("--today", help=TODAY_HELP)
    pp.add_argument("--json", action="store_true", help="輸出 JSON")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    handlers = {
        "weekday": (cmd_weekday, render_weekday),
        "check": (cmd_check, render_check),
        "add": (cmd_add, render_add),
        "plan": (cmd_plan, render_plan),
    }
    compute, render = handlers[args.command]
    try:
        result = compute(args)
    except InputError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else render(result))
    if args.command == "check" and result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
