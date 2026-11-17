#!/usr/bin/env python3
"""單位經濟計算器（pm-field-guide）。

用每帳號每月營收、毛利率、月流失率、獲客成本，算出每月毛利、預期壽命、LTV、
LTV/CAC 與回收期，並做敏感度檢查（流失率、CAC 差兩倍，毛利率差 10 個百分點），
讓 PM 知道哪個估值一變結論就翻盤、要先查證。數字由程式計算，不靠心算。

定義：
  每月毛利       = arpu × margin
  預期壽命（月） = min(1 ÷ churn, max_months)；churn 為 0 時取 max_months
  LTV            = 每月毛利 × 預期壽命
  LTV/CAC        = LTV ÷ cac
  回收期（月）   = cac ÷ 每月毛利

輸入方式擇一：
  1. 單一客群用參數：--arpu、--margin、--churn、--cac（必要），--max-months（預設 36）、--label（選填）
  2. 多客群用 CSV（中英文欄名皆可，大小寫不拘，括號內說明會被忽略，例如「月營收（元）」）：
     必要：segment／客群、arpu／月營收、margin／毛利率、churn／月流失率、cac／獲客成本
     選填：max_months／壽命上限（留空則用 --max-months）、note／備註／依據

毛利率與流失率可寫 55%、55 或 0.55（不帶 % 且不大於 1 的數字視為小數，例如 0.5 = 50%）。

用法範例：
  python unit_econ.py --arpu 499 --margin 55% --churn 6% --cac 1200
  python unit_econ.py --arpu 499 --margin 55 --churn 0.06 --cac 1200 --label 個人訂閱 --json
  python unit_econ.py segments.csv
  python unit_econ.py segments.csv --max-months 24 --json
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
        self._positionals.title = "位置參數"
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


def parse_percent(s: str) -> float:
    """接受 80%、80、0.8 三種寫法，回傳 0–1 的小數。帶 % 或大於 1 的數字除以 100。"""
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


def fmt_num(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.{digits}f}".rstrip("0").rstrip(".")


def fmt_pct(x: float) -> str:
    return f"{fmt_num(x * 100)}%"


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# 單位經濟
# ---------------------------------------------------------------------------

ALIASES = {
    "segment": ["segment", "客群"],
    "arpu": ["arpu", "月營收"],
    "margin": ["margin", "毛利率"],
    "churn": ["churn", "月流失率"],
    "cac": ["cac", "獲客成本"],
    "max_months": ["max_months", "壽命上限"],
    "note": ["note", "備註", "依據"],
}
REQUIRED = ["segment", "arpu", "margin", "churn", "cac"]
DEFAULT_MAX_MONTHS = 36.0
HEALTHY_RATIO = 3.0
BREAKEVEN_RATIO = 1.0
PAYBACK_WARN_MONTHS = 12.0
_EPS = 1e-9

FORMULAS = [
    "每月毛利 = 每帳號每月營收（ARPU）× 毛利率",
    "預期壽命（月）= min(1 ÷ 月流失率, 壽命上限)；月流失率為 0 時取壽命上限",
    "LTV = 每月毛利 × 預期壽命",
    "LTV/CAC = LTV ÷ 獲客成本",
    "回收期（月）= 獲客成本 ÷ 每月毛利",
]
RULES_OF_THUMB = (
    "判讀門檻為經驗值，依產業而異，不是定律：LTV/CAC 低於 1 視為虧損、1–3 偏低、3 以上健康；"
    "回收期超過 12 個月提醒現金壓力。"
)
MODEL_LIMITS = (
    "這是簡化模型：假設流失率每月固定、ARPU 與毛利率不變、沒有折現，也沒算升級加購；"
    "適合用來比較客群與找出關鍵假設，不適合當成財務預測。"
)

# (變動欄位, 方式, 數值, 標籤)
VARIANTS = (
    ("churn", "mul", 0.5, "流失率×0.5"),
    ("churn", "mul", 2.0, "流失率×2"),
    ("cac", "mul", 0.5, "CAC×0.5"),
    ("cac", "mul", 2.0, "CAC×2"),
    ("margin", "add", -0.10, "毛利率−10 個百分點"),
    ("margin", "add", 0.10, "毛利率+10 個百分點"),
)
FIELD_ZH = {"churn": "月流失率", "cac": "獲客成本", "margin": "毛利率"}


def expected_lifetime(churn: float, max_months: float) -> tuple[float, bool]:
    """回傳 (預期壽命月數, 是否被上限截斷)。churn 為 0 時取上限並視為截斷。"""
    if churn <= 0:
        return max_months, True
    raw = 1 / churn
    if raw > max_months + _EPS:
        return max_months, True
    return raw, False


def verdict(ltv_cac: float) -> str:
    if ltv_cac < BREAKEVEN_RATIO - _EPS:
        return "虧損"
    if ltv_cac < HEALTHY_RATIO - _EPS:
        return "偏低"
    return "健康"


def unit_economics(arpu: float, margin: float, churn: float, cac: float,
                   max_months: float = DEFAULT_MAX_MONTHS) -> dict:
    """純計算。margin、churn 為 0–1 小數。每月毛利為 0 時回收期為 None（無法回收）。"""
    monthly = arpu * margin
    lifetime, capped = expected_lifetime(churn, max_months)
    ltv = monthly * lifetime
    ratio = ltv / cac
    payback = cac / monthly if monthly > 0 else None
    return {
        "monthly_gross_profit": monthly,
        "lifetime_months": lifetime,
        "lifetime_capped": capped,
        "ltv": ltv,
        "ltv_cac": ratio,
        "payback_months": payback,
        "verdict": verdict(ratio),
    }


def crossed_thresholds(base_ratio: float, new_ratio: float) -> list[float]:
    """回傳從 base 變到 new 時跨過的 LTV/CAC 門檻（1、3）。"""
    return [t for t in (BREAKEVEN_RATIO, HEALTHY_RATIO)
            if (base_ratio >= t - _EPS) != (new_ratio >= t - _EPS)]


def sensitivity(arpu: float, margin: float, churn: float, cac: float, max_months: float) -> list[dict]:
    base = unit_economics(arpu, margin, churn, cac, max_months)
    out = []
    for field, how, amount, label in VARIANTS:
        vals = {"margin": margin, "churn": churn, "cac": cac}
        if how == "mul":
            vals[field] = vals[field] * amount
        else:
            vals[field] = vals[field] + amount
        if field in ("margin", "churn"):
            vals[field] = min(1.0, max(0.0, vals[field]))
        r = unit_economics(arpu, vals["margin"], vals["churn"], vals["cac"], max_months)
        crosses = crossed_thresholds(base["ltv_cac"], r["ltv_cac"])
        out.append({
            "variant": label,
            "field": field,
            "value": round(vals[field], 6),
            "ltv_cac": round(r["ltv_cac"], 4),
            "payback_months": None if r["payback_months"] is None else round(r["payback_months"], 4),
            "verdict": r["verdict"],
            "lifetime_capped": r["lifetime_capped"],
            "crosses": crosses,
            "changes_conclusion": bool(crosses),
        })
    return out


def analyze_segment(seg: dict) -> dict:
    """seg: {segment, arpu, margin, churn, cac, max_months, note}（已驗證）。"""
    r = unit_economics(seg["arpu"], seg["margin"], seg["churn"], seg["cac"], seg["max_months"])
    sens = sensitivity(seg["arpu"], seg["margin"], seg["churn"], seg["cac"], seg["max_months"])
    flags: list[str] = []
    if seg["churn"] <= 0:
        flags.append(
            f"月流失率為 0，預期壽命直接取上限 {fmt_num(seg['max_months'])} 個月；"
            "沒有客戶永遠不流失，請確認流失率是否量得到。"
        )
    elif r["lifetime_capped"]:
        flags.append(
            f"預期壽命被上限截斷：1 ÷ {fmt_pct(seg['churn'])} = {fmt_num(1 / seg['churn'])} 個月，"
            f"超過上限 {fmt_num(seg['max_months'])} 個月，LTV 以上限計算；調高上限前請確認有這麼長的留存資料。"
        )
    if r["payback_months"] is None:
        flags.append("每月毛利為 0，獲客成本永遠無法回收。")
    elif r["payback_months"] > PAYBACK_WARN_MONTHS + _EPS:
        flags.append(
            f"回收期 {fmt_num(r['payback_months'])} 個月，超過 {fmt_num(PAYBACK_WARN_MONTHS)} 個月（經驗值，依產業而異），"
            "成長越快、先墊出去的獲客現金越多，請留意現金壓力。"
        )
    return {
        "segment": seg["segment"],
        "arpu": seg["arpu"],
        "margin": round(seg["margin"], 6),
        "churn": round(seg["churn"], 6),
        "cac": seg["cac"],
        "max_months": seg["max_months"],
        "note": seg.get("note", ""),
        "monthly_gross_profit": round(r["monthly_gross_profit"], 4),
        "lifetime_months": round(r["lifetime_months"], 4),
        "lifetime_capped": r["lifetime_capped"],
        "ltv": round(r["ltv"], 4),
        "ltv_cac": round(r["ltv_cac"], 4),
        "payback_months": None if r["payback_months"] is None else round(r["payback_months"], 4),
        "verdict": r["verdict"],
        "flags": flags,
        "sensitive": any(s["changes_conclusion"] for s in sens),
        "sensitivity": sens,
    }


def validate_segment(raw: dict, label: str, default_max: float) -> tuple[dict | None, list[str], list[str]]:
    """把字串欄位轉成數字。回傳 (segment 或 None, errors, warnings)。"""
    errors: list[str] = []
    warnings: list[str] = []
    vals: dict = {}
    for field, zh in (("arpu", "月營收（ARPU）"), ("cac", "獲客成本（CAC）")):
        s = raw.get(field) or ""
        try:
            v = parse_number(s)
        except ValueError:
            errors.append(f"{label}：{zh}「{s}」不是數字。" if s else f"{label}：缺少{zh}。")
            continue
        if v <= 0:
            errors.append(f"{label}：{zh}必須大於 0，收到 {s}。")
        else:
            vals[field] = v
    for field, zh in (("margin", "毛利率"), ("churn", "月流失率")):
        s = raw.get(field) or ""
        try:
            vals[field] = parse_percent(s)
        except ValueError:
            errors.append(
                f"{label}：{zh}「{s}」無法解讀，請填 55%、55 或 0.55（0–100%）。" if s else f"{label}：缺少{zh}。"
            )
    s = raw.get("max_months") or ""
    if s:
        try:
            v = parse_number(s)
            if v <= 0:
                raise ValueError
            vals["max_months"] = v
        except ValueError:
            errors.append(f"{label}：壽命上限「{s}」必須是大於 0 的月數。")
    else:
        vals["max_months"] = default_max
    if errors:
        return None, errors, warnings

    churn_raw = (raw.get("churn") or "").strip()
    # A bare number <= 1 is read as a fraction; flag it only when the result is implausibly high.
    if not churn_raw.endswith(("%", "％")) and vals["churn"] >= 0.5 and parse_number(churn_raw) <= 1:
        warnings.append(
            f"{label}：月流失率「{churn_raw}」不帶 %，視為小數，即每月流失 {fmt_pct(vals['churn'])}；"
            f"若原意是 {churn_raw}%，請寫成「{churn_raw}%」。"
        )
    vals["segment"] = raw.get("segment") or ""
    vals["note"] = raw.get("note") or ""
    return vals, errors, warnings


def parse_segments(records: list[dict], default_max: float) -> tuple[list[dict], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    segs: list[dict] = []
    for rec in records:
        line = rec["_line"]
        name = rec.get("segment", "")
        if not name:
            errors.append(f"第 {line} 列：客群名稱是空的。")
            continue
        seg, errs, warns = validate_segment(rec, f"第 {line} 列「{name}」", default_max)
        errors.extend(errs)
        warnings.extend(warns)
        if seg:
            segs.append(seg)
    if errors:
        raise InputError("輸入資料有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))
    seen: dict[str, int] = {}
    for s in segs:
        seen[s["segment"]] = seen.get(s["segment"], 0) + 1
    dups = [n for n, c in seen.items() if c > 1]
    if dups:
        warnings.append("客群名稱重複：" + "、".join(f"「{d}」" for d in dups) + "，請確認是否重複列入。")
    return segs, warnings


def _seg_name(s: dict) -> str:
    return s["segment"] or "此客群"


def _cross_text(base_ratio: float, s: dict) -> str:
    parts = []
    for t in s["crosses"]:
        direction = "跌破" if s["ltv_cac"] < base_ratio else "站上"
        parts.append(f"{direction} {fmt_num(t)}")
    return "、".join(parts)


def interpret(res: dict) -> list[str]:
    obs: list[str] = []
    for x in res["segments"]:
        payback = ("獲客成本無法回收" if x["payback_months"] is None
                   else f"約 {fmt_num(x['payback_months'])} 個月回本")
        obs.append(
            f"「{_seg_name(x)}」：每帳號每月毛利 {fmt_num(x['monthly_gross_profit'])}，"
            f"預期留 {fmt_num(x['lifetime_months'])} 個月，一個客戶一生帶來毛利（LTV）{fmt_num(x['ltv'])}，"
            f"是獲客成本的 {fmt_num(x['ltv_cac'])} 倍（{x['verdict']}），{payback}。"
        )
        for f in x["flags"]:
            obs.append(f"「{_seg_name(x)}」注意：{f}")
        hits = [s for s in x["sensitivity"] if s["changes_conclusion"]]
        if hits:
            fields = []
            for s in hits:
                if FIELD_ZH[s["field"]] not in fields:
                    fields.append(FIELD_ZH[s["field"]])
            detail = "；".join(
                f"{s['variant']} 會讓 LTV/CAC {_cross_text(x['ltv_cac'], s)}（{fmt_num(x['ltv_cac'])} → {fmt_num(s['ltv_cac'])}）"
                for s in hits
            )
            obs.append(
                f"「{_seg_name(x)}」敏感度：{detail}。{'、'.join(fields)}{'這個' if len(fields) == 1 else '這幾個'}估值要先查證，"
                "再用這份結論做決定。"
            )
        else:
            obs.append(
                f"「{_seg_name(x)}」敏感度：流失率或 CAC 單獨差兩倍、毛利率差 10 個百分點，"
                f"LTV/CAC 都不會跨過 1 或 3 的門檻，「{x['verdict']}」的判讀相對穩定。"
            )
    if len(res["segments"]) > 1:
        best = max(res["segments"], key=lambda x: x["ltv_cac"])
        worst = min(res["segments"], key=lambda x: x["ltv_cac"])
        if best is not worst:
            obs.append(
                f"客群比較：LTV/CAC 最高的是「{_seg_name(best)}」（{fmt_num(best['ltv_cac'])}），"
                f"最低的是「{_seg_name(worst)}」（{fmt_num(worst['ltv_cac'])}）。"
                "比值高不等於該全押：還要看回收期（現金）與該客群的市場規模。"
            )
    obs.append(res["rules_of_thumb"])
    obs.append(res["model_limits"])
    if res["warnings"]:
        obs.append(f"有 {len(res['warnings'])} 則警告，見上方「警告」，處理後結論才可靠。")
    return obs


def analyze(segments: list[dict], warnings: list[str]) -> dict:
    res = {
        "formulas": list(FORMULAS),
        "rules_of_thumb": RULES_OF_THUMB,
        "model_limits": MODEL_LIMITS,
        "segments": [analyze_segment(s) for s in segments],
        "warnings": list(warnings),
    }
    res["interpretation"] = interpret(res)
    return res


def _payback_cell(v: float | None) -> str:
    return "無法回收" if v is None else fmt_num(v)


def render_markdown(res: dict) -> str:
    segs = res["segments"]
    out = ["# 單位經濟計算結果", "", "## 公式", ""]
    out.extend(f"- {f}" for f in res["formulas"])
    out.append("")
    out.append("## 各客群結果")
    out.append("")
    head = ["客群", "月營收", "毛利率", "月流失率", "獲客成本", "每月毛利", "預期壽命（月）", "LTV", "LTV/CAC",
            "回收期（月）", "判讀"]
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "|".join(["---"] * len(head)) + "|")
    for x in segs:
        life = fmt_num(x["lifetime_months"]) + ("（上限）" if x["lifetime_capped"] else "")
        out.append("| " + " | ".join([
            md_cell(_seg_name(x)), fmt_num(x["arpu"]), fmt_pct(x["margin"]), fmt_pct(x["churn"]), fmt_num(x["cac"]),
            fmt_num(x["monthly_gross_profit"]), life, fmt_num(x["ltv"]), fmt_num(x["ltv_cac"]),
            _payback_cell(x["payback_months"]), x["verdict"],
        ]) + " |")
    out.append("")
    out.append(f"判讀說明：{res['rules_of_thumb']}")
    out.append("")

    out.append("## 敏感度檢查")
    out.append("")
    out.append("每次只改一個估值、其他不動，重算 LTV/CAC 與回收期；**粗體** 表示 LTV/CAC 跨過 1 或 3 的門檻。")
    out.append("")
    for x in segs:
        if len(segs) > 1:
            out.append(f"### {md_cell(_seg_name(x))}")
            out.append("")
        out.append("| 情境 | LTV/CAC | 回收期（月） | 判讀 | 判定 |")
        out.append("|---|---|---|---|---|")
        out.append(f"| 目前 | {fmt_num(x['ltv_cac'])} | {_payback_cell(x['payback_months'])} | {x['verdict']} | — |")
        for s in x["sensitivity"]:
            ratio = fmt_num(s["ltv_cac"])
            if s["changes_conclusion"]:
                ratio = f"**{ratio}**"
                judge = f"{_cross_text(x['ltv_cac'], s)}：這個估值要先查證"
            else:
                judge = "穩定"
            if s["lifetime_capped"] and not x["lifetime_capped"]:
                judge += "（壽命被上限截斷）"
            out.append(f"| {s['variant']} | {ratio} | {_payback_cell(s['payback_months'])} | {s['verdict']} | {judge} |")
        out.append("")

    out.append("## 警告")
    out.append("")
    if res["warnings"]:
        out.extend(f"- {md_cell(w)}" for w in res["warnings"])
    else:
        out.append("- （無）")
    out.append("")
    out.append("## 解讀")
    out.append("")
    out.extend(f"- {o}" for o in res["interpretation"])
    return "\n".join(out) + "\n"


def _positive_float(s: str) -> float:
    try:
        v = parse_number(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"「{s}」不是數字")
    if v <= 0:
        raise argparse.ArgumentTypeError(f"壽命上限必須大於 0，收到 {s}")
    return v


def build_parser() -> argparse.ArgumentParser:
    p = _ZhArgumentParser(
        prog="unit_econ.py",
        description="單位經濟：每月毛利、預期壽命、LTV、LTV/CAC、回收期，含敏感度檢查。",
        epilog=(
            "輸入方式擇一：單一客群用 --arpu/--margin/--churn/--cac；多客群給 CSV。\n"
            "CSV 欄位：segment/客群、arpu/月營收、margin/毛利率、churn/月流失率、cac/獲客成本；\n"
            "選填 max_months/壽命上限、note/備註/依據。\n"
            "毛利率與流失率可填 55%、55 或 0.55。判讀門檻皆為經驗值，依產業而異。"
        ),
    )
    p.add_argument("csv", nargs="?", help="多客群 CSV 檔路徑（UTF-8，Excel 匯出的 BOM 也可以）；與 --arpu 等參數擇一")
    p.add_argument("--arpu", metavar="N", help="每帳號每月營收")
    p.add_argument("--margin", metavar="PCT", help="毛利率（55%%、55 或 0.55）")
    p.add_argument("--churn", metavar="PCT", help="月流失率（6%%、6 或 0.06）")
    p.add_argument("--cac", metavar="N", help="獲客成本（取得一個付費客戶的平均花費）")
    p.add_argument("--max-months", type=_positive_float, default=DEFAULT_MAX_MONTHS, metavar="N",
                   help="客戶壽命上限月數（預設 36）；CSV 模式下用於沒填壽命上限的列")
    p.add_argument("--label", metavar="NAME", help="客群名稱（選填，僅參數模式）")
    p.add_argument("--json", action="store_true", help="輸出 JSON（給程式讀），不輸出 Markdown")
    return p


_ARG_FIELDS = (("arpu", "--arpu"), ("margin", "--margin"), ("churn", "--churn"), ("cac", "--cac"))


def load_segments(args) -> tuple[list[dict], list[str]]:
    given = [flag for name, flag in _ARG_FIELDS if getattr(args, name) is not None]
    if args.csv is not None:
        extra = given + (["--label"] if args.label is not None else [])
        if extra:
            raise InputError(
                f"CSV 模式與參數模式請擇一：已提供 CSV 檔，請拿掉 {'、'.join(extra)}（或拿掉 CSV 檔路徑）。"
            )
        records, _present, unused = read_table(args.csv, ALIASES, REQUIRED)
        segs, warnings = parse_segments(records, args.max_months)
        if unused:
            warnings.append("以下欄位未使用（若是拼錯欄名請修正）：" + "、".join(unused))
        return segs, warnings
    if not given:
        raise InputError("請提供 CSV 檔路徑，或用 --arpu、--margin、--churn、--cac 輸入單一客群。")
    missing = [flag for name, flag in _ARG_FIELDS if getattr(args, name) is None]
    if missing:
        raise InputError(f"參數模式缺少：{'、'.join(missing)}。四個數字都要提供，程式不會代填預設值。")
    raw = {"segment": (args.label or "").strip(), "arpu": args.arpu, "margin": args.margin,
           "churn": args.churn, "cac": args.cac}
    seg, errors, warnings = validate_segment(raw, "參數", args.max_months)
    if errors:
        raise InputError("輸入資料有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))
    return [seg], warnings


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    segments, warnings = load_segments(args)
    res = analyze(segments, warnings)
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
