#!/usr/bin/env python3
"""工時三點估算計算器，PERT（pm-field-guide）。

每個工作項目給三個數字：樂觀（O）、最可能（M）、悲觀（P），計算
期望值 E = (O + 4M + P) ÷ 6、標準差 SD = (P − O) ÷ 6、不確定性比 P ÷ O，
再把各項目加總，算出「對外承諾用」的數字 = 合計期望值 + z × 合計標準差。
數字由程式計算，不靠心算。

輸入方式二擇一：
  (a) CSV 檔（欄名中英文皆可，大小寫不拘，括號內說明會被忽略，例如「樂觀（人天）」）：
      必要：item／項目、optimistic／樂觀／O、likely／最可能／M、pessimistic／悲觀／P
      選填：owner／負責人、note／備註
  (b) 可重複的 --item "名稱:O,M,P"

用法範例：
  python estimate.py estimate.csv
  python estimate.py estimate.csv --confidence 80 --unit 人週
  python estimate.py --item "字幕產生:20,35,60" --item "字幕編輯:10,15,26"
  python estimate.py estimate.csv --json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")


# ---------------------------------------------------------------------------
# 共用：錯誤、參數解析、CSV 讀取
# ---------------------------------------------------------------------------

class InputError(Exception):
    """使用者輸入有誤；main() 會印出繁中訊息並以 exit code 2 結束。"""


class _ZhHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage, actions, groups, prefix=None):
        return super().add_usage(usage, actions, groups, prefix or "用法：")


_ARGPARSE_ZH = [
    ("the following arguments are required", "缺少必要參數"),
    ("unrecognized arguments", "無法辨識的參數"),
    ("expected one argument", "需要提供一個值"),
    ("invalid choice", "無效的選項"),
    ("argument ", "參數 "),
]


class _ZhArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("formatter_class", _ZhHelpFormatter)
        kwargs["add_help"] = False
        super().__init__(*args, **kwargs)
        self._positionals.title = "必要參數"
        self._optionals.title = "選項"
        self.add_argument("-h", "--help", action="help", help="顯示這份說明後結束")

    def error(self, message):
        for en, zh in _ARGPARSE_ZH:
            message = message.replace(en, zh)
        self.print_usage(sys.stderr)
        self.exit(2, f"錯誤：{message}\n")


def _norm_header(h: str) -> str:
    raw = (h or "").strip()
    t = re.sub(r"[（(].*?[）)]", "", raw).strip()
    if not t:
        t = re.sub(r"[（()）]", "", raw)
    return t.lower().replace(" ", "").replace("_", "").replace("-", "")


def read_table(path: str, aliases: dict[str, list[str]], required: list[str]):
    """讀 CSV（utf-8-sig），把中英文欄名對應到標準欄名。

    回傳 (records, present_columns, unused_headers)。records 每筆含 "_line"（試算表列號，表頭為第 1 列）。
    """
    p = Path(path)
    if not p.is_file():
        raise InputError(f"找不到檔案：{path}")
    try:
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.reader(f))
    except UnicodeDecodeError:
        raise InputError(
            f"檔案不是 UTF-8 編碼：{path}。若從 Excel 匯出，請選「CSV UTF-8（逗號分隔）」；"
            "Google 試算表下載的 CSV 已是 UTF-8。"
        )
    except csv.Error as e:
        raise InputError(f"CSV 格式有誤：{e}")
    except OSError as e:
        raise InputError(f"無法讀取檔案：{path}（{e.strerror}）")

    while rows and not any(c.strip() for c in rows[0]):
        rows.pop(0)
    if not rows:
        raise InputError(f"CSV 是空的：{path}")

    lookup = {_norm_header(a): canon for canon, al in aliases.items() for a in al}
    header = rows[0]
    colmap: dict[str, int] = {}
    unused: list[str] = []
    for idx, h in enumerate(header):
        canon = lookup.get(_norm_header(h))
        if canon is None:
            if h.strip():
                unused.append(h.strip())
            continue
        if canon in colmap:
            raise InputError(
                f"欄位重複：「{header[colmap[canon]].strip()}」和「{h.strip()}」都代表 {canon}，請只留一欄。"
            )
        colmap[canon] = idx

    missing = [c for c in required if c not in colmap]
    if missing:
        names = "、".join(f"{c}（{'／'.join(aliases[c])}）" for c in missing)
        current = "、".join(h.strip() for h in header if h.strip()) or "（無）"
        raise InputError(f"缺少必要欄位：{names}。目前的欄位：{current}")

    records = []
    for lineno, r in enumerate(rows[1:], start=2):
        if not any(c.strip() for c in r):
            continue
        rec = {c: (r[i].strip() if i < len(r) else "") for c, i in colmap.items()}
        rec["_line"] = lineno
        records.append(rec)
    if not records:
        raise InputError(f"CSV 只有表頭，沒有資料列：{path}")
    return records, set(colmap), unused


def parse_number(s: str) -> float:
    t = s.replace(",", "").replace("，", "").strip()
    if not t:
        raise ValueError("空白")
    v = float(t)
    if not math.isfinite(v):
        raise ValueError("不是有限數字")
    return v


def fmt_num(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.{digits}f}".rstrip("0").rstrip(".")


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# 三點估算（PERT）
# ---------------------------------------------------------------------------

ALIASES = {
    "item": ["item", "項目"],
    "optimistic": ["optimistic", "樂觀", "O"],
    "likely": ["likely", "最可能", "M"],
    "pessimistic": ["pessimistic", "悲觀", "P"],
    "owner": ["owner", "負責人"],
    "note": ["note", "備註"],
}
REQUIRED = ["item", "optimistic", "likely", "pessimistic"]

# One-tailed z values of the standard normal distribution.
Z_VALUES = {80: 0.84, 90: 1.28, 95: 1.645}
HIGH_UNCERTAINTY_RATIO = 3.0
HIGH_UNCERTAINTY_FLAG = "不確定性高，先拆小或先做技術探索"

NOTE_HALF = "只報期望值時約有一半機率超時；對外承諾請用承諾值，不要用期望值。"
NOTE_NORMAL = (
    "承諾值 = 合計期望值 + z × 合計標準差，z 取單尾常態近似"
    "（80% → 0.84、90% → 1.28、95% → 1.645）；項目少或估值偏斜時只是近似，不是保證。"
)
NOTE_INDEPENDENT = (
    "合計標準差 = 各項變異數相加後開根號，假設各項目彼此獨立；"
    "若項目彼此相關（同一個人做、卡在同一個技術風險或同一個外部相依），實際風險會比這個數字大。"
)
NOTE_RATIO = (
    f"「悲觀 ÷ 樂觀 ≥ {fmt_num(HIGH_UNCERTAINTY_RATIO)} 視為不確定性高」是經驗值，依產業而異，不是定律。"
)


def parse_confidence(s: str) -> float:
    t = s.strip()
    pct = t.endswith("%") or t.endswith("％")
    if pct:
        t = t[:-1]
    v = parse_number(t)
    if pct or v > 1:
        v = v / 100
    if not 0 <= v <= 1:
        raise ValueError("超出 0–100%")
    return v


def parse_confidence_level(s: str) -> int:
    """把 90、90%、0.9 轉成 90；只接受 80、90、95。"""
    try:
        v = parse_confidence(s)
    except ValueError:
        raise InputError(f"信心水準「{s}」無法解讀，只接受 80、90、95（可寫成 90、90% 或 0.9）。")
    for level in Z_VALUES:
        if abs(v * 100 - level) < 1e-9:
            return level
    raise InputError(f"信心水準只接受 80、90、95（可寫成 90、90% 或 0.9），收到「{s}」。")


def pert(o: float, m: float, p: float) -> tuple[float, float, float]:
    """回傳 (期望值, 標準差, 不確定性比 P÷O)。"""
    return (o + 4 * m + p) / 6, (p - o) / 6, p / o


def combine(sds: list[float]) -> float:
    """各項獨立時的合計標準差：變異數相加後開根號。"""
    return math.sqrt(sum(sd * sd for sd in sds))


def commitment(total_expected: float, total_sd: float, level: int) -> float:
    return total_expected + Z_VALUES[level] * total_sd


def parse_item_arg(s: str) -> dict:
    """解析 --item "名稱:O,M,P"（冒號全形半形皆可，以最後一個冒號切開）。"""
    pos = max(s.rfind(":"), s.rfind("："))
    name = s[:pos].strip() if pos >= 0 else ""
    parts = [x.strip() for x in re.split(r"[,，]", s[pos + 1:])] if pos >= 0 else []
    if not name or len(parts) != 3:
        raise InputError(f"--item「{s}」格式有誤，請寫成 \"名稱:樂觀,最可能,悲觀\"，例如 \"字幕產生:20,35,60\"。")
    return {"item": name, "optimistic": parts[0], "likely": parts[1], "pessimistic": parts[2]}


def parse_items(records: list[dict]) -> list[dict]:
    """驗證並計算每個項目；有錯誤時一次列出全部並丟 InputError。"""
    errors: list[str] = []
    items: list[dict] = []
    for n, rec in enumerate(records, start=1):
        name = rec.get("item", "")
        where = f"第 {rec['_line']} 列" if "_line" in rec else f"第 {n} 個 --item"
        if not name:
            errors.append(f"{where}：項目名稱是空的。")
            continue
        label = f"{where}「{name}」"
        vals = {}
        row_errors = []
        for field, zh in (("optimistic", "樂觀"), ("likely", "最可能"), ("pessimistic", "悲觀")):
            raw = rec.get(field, "")
            try:
                v = parse_number(raw)
            except ValueError:
                row_errors.append(f"{label}：{zh}「{raw}」不是數字。" if raw else f"{label}：缺少{zh}。")
                continue
            if v <= 0:
                row_errors.append(f"{label}：{zh}「{raw}」必須大於 0。")
                continue
            vals[field] = v
        if not row_errors:
            o, m, p = vals["optimistic"], vals["likely"], vals["pessimistic"]
            if not o <= m <= p:
                row_errors.append(
                    f"{label}：必須符合 樂觀 ≤ 最可能 ≤ 悲觀，收到 {fmt_num(o)}／{fmt_num(m)}／{fmt_num(p)}。"
                )
        if row_errors:
            errors.extend(row_errors)
            continue
        e, sd, ratio = pert(o, m, p)
        high = ratio >= HIGH_UNCERTAINTY_RATIO - 1e-9
        items.append({
            "item": name,
            "owner": rec.get("owner", ""),
            "optimistic": o,
            "likely": m,
            "pessimistic": p,
            "expected": e,
            "sd": sd,
            "ratio": ratio,
            "high_uncertainty": high,
            "flag": HIGH_UNCERTAINTY_FLAG if high else "",
            "note": rec.get("note", ""),
        })
    if errors:
        raise InputError("輸入資料有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))
    if not items:
        raise InputError("沒有可計算的項目。")
    return items


def analyze(items: list[dict], level: int, unit: str, warnings: list[str] | None = None) -> dict:
    total_e = sum(it["expected"] for it in items)
    total_sd = combine([it["sd"] for it in items])
    variance = total_sd * total_sd
    value = commitment(total_e, total_sd, level)
    multi = len(items) > 1

    items_out = []
    for it in items:
        x = dict(it)
        for k in ("expected", "sd", "ratio"):
            x[k] = round(it[k], 4)
        x["variance_share"] = round(it["sd"] ** 2 / variance, 4) if variance > 0 else None
        items_out.append(x)

    notes = [NOTE_HALF, NOTE_NORMAL]
    if multi:
        notes.append(NOTE_INDEPENDENT)
    notes.append(NOTE_RATIO)

    res = {
        "unit": unit,
        "items": items_out,
        "total": {
            "count": len(items),
            "expected": round(total_e, 4),
            "sd": round(total_sd, 4),
            "independence_assumed": multi,
        },
        "commitment": {
            "confidence": level,
            "z": Z_VALUES[level],
            "buffer": round(value - total_e, 4),
            "value": round(value, 4),
        },
        "notes": notes,
        "warnings": list(warnings or []),
    }
    res["interpretation"] = interpret(res)
    return res


def interpret(res: dict) -> list[str]:
    unit = res["unit"]
    items = res["items"]
    tot = res["total"]
    com = res["commitment"]
    multi = tot["count"] > 1
    scope = f"{tot['count']} 個項目合計" if multi else f"「{items[0]['item']}」"
    obs = [
        f"{scope}的期望值是 {fmt_num(tot['expected'])} {unit}。這是「平均會落在哪」，"
        "不是安全的承諾：只報期望值時約有一半機率超時。",
        f"要有約 {com['confidence']}% 的把握，對外請報 {fmt_num(com['value'], 1)} {unit}"
        f"（期望值 {fmt_num(tot['expected'])} + {com['z']} × 標準差 {fmt_num(tot['sd'])}"
        f" = 多留 {fmt_num(com['buffer'], 1)} {unit} 的緩衝）。"
        "這是單尾常態近似，項目少或估值偏斜時只是概略值，不是保證。",
    ]
    if multi:
        obs.append(
            "合計標準差假設各項目彼此獨立；若多個項目由同一個人做、或卡在同一個技術風險，"
            "延誤會一起發生，實際風險會比這裡算的大，緩衝要再加。"
        )
        top = max(items, key=lambda x: x["variance_share"] or 0)
        if top["variance_share"] and top["variance_share"] >= 0.5:
            obs.append(
                f"整體的不確定性有 {fmt_num(top['variance_share'] * 100, 0)}% 來自「{top['item']}」"
                "（以變異數佔比計）；想縮小緩衝，先把這一項估準最有效。"
            )
    high = [x for x in items if x["high_uncertainty"]]
    if high:
        names = "、".join(f"{x['item']}（悲觀÷樂觀 = {fmt_num(x['ratio'])}）" for x in high)
        obs.append(
            f"不確定性高的項目：{names}。悲觀值是樂觀值的 {fmt_num(HIGH_UNCERTAINTY_RATIO)} 倍以上，"
            "代表團隊其實還不知道要做多久；建議先拆小，或先排一段有時間上限的技術探索再重估。"
            "（這個門檻是經驗值，依產業而異。）"
        )
    else:
        obs.append(
            f"沒有項目的 悲觀÷樂觀 達到 {fmt_num(HIGH_UNCERTAINTY_RATIO)}（經驗值，依產業而異），"
            "估值範圍相對收斂；仍請確認悲觀值有把已知風險算進去，而不是只比最可能多一點。"
        )
    if res["warnings"]:
        obs.append(f"有 {len(res['warnings'])} 則警告，見上方「警告」。")
    return obs


def render_markdown(res: dict) -> str:
    unit = res["unit"]
    items = res["items"]
    tot = res["total"]
    com = res["commitment"]
    multi = tot["count"] > 1
    has_owner = any(x["owner"] for x in items)

    out = ["# 工時三點估算結果（PERT）", ""]
    out.append(f"期望值 = (樂觀 + 4 × 最可能 + 悲觀) ÷ 6；標準差 = (悲觀 − 樂觀) ÷ 6。單位：{unit}")
    out.append("")
    out.append("## 各項目")
    out.append("")
    head = ["項目"] + (["負責人"] if has_owner else []) + ["樂觀 O", "最可能 M", "悲觀 P", "期望值", "標準差", "P÷O", "警示"]
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "|".join(["---"] * len(head)) + "|")
    for x in items:
        row = [md_cell(x["item"])] + ([md_cell(x["owner"]) or "—"] if has_owner else [])
        row += [fmt_num(x["optimistic"]), fmt_num(x["likely"]), fmt_num(x["pessimistic"]),
                fmt_num(x["expected"]), fmt_num(x["sd"]), fmt_num(x["ratio"]), x["flag"] or "—"]
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    out.append(f"- {NOTE_RATIO}")
    out.append("")

    out.append("## 合計")
    out.append("")
    out.append(f"- 項目數：{tot['count']}")
    out.append(f"- 合計期望值：{fmt_num(tot['expected'])} {unit}")
    out.append(f"- 合計標準差：{fmt_num(tot['sd'])} {unit}")
    if multi:
        out.append(f"- {NOTE_INDEPENDENT}")
    out.append("")

    out.append("## 承諾建議")
    out.append("")
    out.append(
        f"- {com['confidence']}% 信心的承諾值：**{fmt_num(com['value'], 1)} {unit}**"
        f"（{fmt_num(tot['expected'])} + {com['z']} × {fmt_num(tot['sd'])}，"
        f"比期望值多 {fmt_num(com['buffer'], 1)} {unit}）"
    )
    out.append(f"- {NOTE_HALF}")
    out.append(f"- {NOTE_NORMAL}")
    out.append("")

    if res["warnings"]:
        out.append("## 警告")
        out.append("")
        out.extend(f"- {md_cell(w)}" for w in res["warnings"])
        out.append("")

    out.append("## 解讀")
    out.append("")
    out.extend(f"- {o}" for o in res["interpretation"])
    return "\n".join(out) + "\n"


def build_parser() -> argparse.ArgumentParser:
    p = _ZhArgumentParser(
        prog="estimate.py",
        description="工時三點估算（PERT）：由樂觀／最可能／悲觀算出期望值、標準差與對外承諾值。",
        epilog=(
            "輸入二擇一：CSV 檔，或一到多個 --item。\n"
            "CSV 欄位：item/項目、optimistic/樂觀/O、likely/最可能/M、pessimistic/悲觀/P；\n"
            "選填 owner/負責人、note/備註。三個值都要大於 0，且 樂觀 ≤ 最可能 ≤ 悲觀。"
        ),
    )
    p.add_argument("csv", nargs="?", help="工作項目 CSV 檔路徑（UTF-8，Excel 匯出的 BOM 也可以）")
    p.add_argument("--item", action="append", default=[], metavar='"名稱:O,M,P"',
                   help="直接給一個項目，可重複，例如 --item \"字幕產生:20,35,60\"")
    p.add_argument("--unit", default="人天", metavar="單位", help="工時單位字樣，只影響顯示（預設：人天）")
    p.add_argument("--confidence", default="90", metavar="N",
                   help="承諾值的信心水準，只接受 80、90、95，可寫成 90、90%% 或 0.9（預設：90）")
    p.add_argument("--json", action="store_true", help="輸出 JSON（給程式讀），不輸出 Markdown")
    return p


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    level = parse_confidence_level(args.confidence)
    unit = args.unit.strip()
    if not unit:
        raise InputError("--unit 不能是空白。")
    if args.csv and args.item:
        raise InputError("CSV 檔和 --item 只能擇一，請不要同時提供。")
    if not args.csv and not args.item:
        raise InputError("請提供 CSV 檔路徑，或至少一個 --item \"名稱:樂觀,最可能,悲觀\"。")

    warnings: list[str] = []
    if args.csv:
        records, _, unused = read_table(args.csv, ALIASES, REQUIRED)
        if unused:
            warnings.append("以下欄位未使用（若是拼錯欄名請修正）：" + "、".join(unused))
    else:
        records = [parse_item_arg(s) for s in args.item]

    res = analyze(parse_items(records), level, unit, warnings)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(res), end="")
    return res


def main(argv: list[str] | None = None) -> int:
    try:
        run(argv)
    except InputError as e:
        print(f"錯誤：{e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
