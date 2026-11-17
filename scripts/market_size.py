#!/usr/bin/env python3
"""市場規模 bottom-up 試算（pm-field-guide）。

用「目標客群數 × 每家每年平均營收」由下往上算 TAM／SAM／SOM，
附滲透率 × 年單價的敏感度表，並指出最該先查證的假設。
數字全部來自你提供的輸入，腳本只做乘法；每個輸入都要有來源。

定義：
  TAM = 目標客群數 × 年單價
  SAM = TAM × 可服務比例（產品形態、地區、語言、通路搆得到的部分）
  SOM = SAM × 滲透率（期間內實際可能取得的份額）

單一客群：用參數
  --accounts 目標客群總家數或人數、--price 每家每年平均營收、
  --serviceable 可服務比例、--penetration 滲透率（比例可填 60%、60 或 0.6）

多個客群：用 CSV（中英文欄名皆可，大小寫不拘，括號內說明會被忽略，例如「年單價（元）」）
  必要：segment／客群、accounts／家數／人數、price／年單價／年營收、
        serviceable／可服務比例、penetration／滲透率
  選填：source／來源（空白會標「來源待查證」）

用法範例：
  python market_size.py --accounts 5000 --price 12000 --serviceable 60% --penetration 5%
  python market_size.py --accounts 5000 --price 12000 --serviceable 60 --penetration 5 --target 3600000
  python market_size.py segments.csv
  python market_size.py segments.csv --years 3 --target 5000000 --json
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
    if abs(x - round(x)) < 1e-6:
        return f"{int(round(x)):,}"
    return f"{x:,.{digits}f}".rstrip("0").rstrip(".")


def fmt_pct(x: float) -> str:
    return f"{fmt_num(x * 100, 2)}%"


def md_cell(s) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# 市場規模
# ---------------------------------------------------------------------------

ALIASES = {
    "segment": ["segment", "客群"],
    "accounts": ["accounts", "家數", "人數"],
    "price": ["price", "年單價", "年營收"],
    "serviceable": ["serviceable", "可服務比例"],
    "penetration": ["penetration", "滲透率"],
    "source": ["source", "來源"],
}
REQUIRED = ["segment", "accounts", "price", "serviceable", "penetration"]
FACTORS = (0.5, 1.0, 2.0)
AGGRESSIVE_PENETRATION = 0.30
SOURCE_PENDING = "來源待查證"
DISCLAIMER = "數字來自你提供的輸入，腳本只做乘法；每個輸入都要有來源。"
FORMULAS = {
    "TAM": "目標客群數 × 年單價",
    "SAM": "TAM × 可服務比例",
    "SOM": "SAM × 滲透率",
    "SAM 客群數": "目標客群數 × 可服務比例",
    "SOM 客群數": "SAM 客群數 × 滲透率",
}
FIELD_ZH = {"accounts": "目標客群數", "price": "年單價", "serviceable": "可服務比例", "penetration": "滲透率"}
# Tie-break order when several inputs move SOM equally: least observable first.
FIELD_PRIORITY = ("penetration", "serviceable", "price", "accounts")
FIELD_HOW = {
    "penetration": "它是對未來的預估，查不到現成統計，要靠試賣、訪談或同類產品的實績佐證",
    "serviceable": "它取決於產品形態、地區、語言、通路的限制，請逐項列出扣掉了哪些客群",
    "price": "請用實際報價、成交紀錄或願付價格訪談佐證",
    "accounts": "請用政府統計、公開登記資料或產業名錄佐證，並確認定義與你的目標客群一致",
}


def parse_ratio(s: str) -> float:
    """比例：接受 60%、60、0.6。有 % 或數值大於 1 視為百分比；結果需在 0–100%。"""
    t = s.strip()
    pct = t.endswith("%") or t.endswith("％")
    if pct:
        t = t[:-1]
    v = parse_number(t)
    if pct or v > 1:
        v = v / 100
    if v < 0:
        raise ValueError("不能是負數")
    if v > 1 + 1e-12:
        raise ValueError("超過 100%")
    return min(v, 1.0)


def _is_bare_one(s: str) -> bool:
    t = s.strip()
    if t.endswith("%") or t.endswith("％"):
        return False
    try:
        return parse_number(t) == 1
    except ValueError:
        return False


def market_size(accounts: float, price: float, serviceable: float, penetration: float) -> dict:
    """純計算：回傳 tam／sam／som 與對應客群數。比例為 0–1 的小數。"""
    tam = accounts * price
    sam_accounts = accounts * serviceable
    som_accounts = sam_accounts * penetration
    return {
        "tam": tam,
        "sam": sam_accounts * price,
        "som": som_accounts * price,
        "sam_accounts": sam_accounts,
        "som_accounts": som_accounts,
    }


def total_som(segments: list[dict], pen_factor: float = 1.0, price_factor: float = 1.0) -> tuple[float, bool]:
    """各客群滲透率、年單價同乘倍數後的合計 SOM；滲透率夾在 100% 以內。回傳 (SOM, 是否有被夾住)。"""
    total = 0.0
    capped = False
    for s in segments:
        pen = s["penetration"] * pen_factor
        if pen > 1:
            pen = 1.0
            capped = True
        total += s["accounts"] * s["price"] * price_factor * s["serviceable"] * pen
    return total, capped


def sensitivity_table(segments: list[dict]) -> dict:
    som, capped = [], []
    for pf in FACTORS:
        row, crow = [], []
        for prf in FACTORS:
            v, c = total_som(segments, pf, prf)
            row.append(round(v, 4))
            crow.append(c)
        som.append(row)
        capped.append(crow)
    return {"penetration_factors": list(FACTORS), "price_factors": list(FACTORS), "som": som, "capped": capped}


def required_penetration(target: float, sam: float) -> float | None:
    """SOM 要達到 target 需要的滲透率（= target ÷ SAM）；SAM 為 0 時回傳 None。"""
    if sam <= 0:
        return None
    return target / sam


def key_assumption(segments: list[dict]) -> dict | None:
    """找出對合計 SOM 影響最大的輸入：逐一把單一輸入 ×0.5 與 ×2（比例夾在 100% 以內），比較 SOM 擺幅。

    四個輸入相乘，擺幅常常相同；相同時依「越難直接查到越先查」排序：滲透率 > 可服務比例 > 年單價 > 目標客群數。
    """
    best = None
    for i, s in enumerate(segments):
        for rank, field in enumerate(FIELD_PRIORITY):
            vals = []
            for f in (0.5, 2.0):
                v = dict(s)
                v[field] = s[field] * f
                if field in ("serviceable", "penetration"):
                    v[field] = min(v[field], 1.0)
                vals.append(v["accounts"] * v["price"] * v["serviceable"] * v["penetration"])
            swing = vals[1] - vals[0]
            if swing <= 0:
                continue
            key = (-round(swing, 6), rank, i)
            if best is None or key < best[0]:
                best = (key, {
                    "segment": s["segment"], "field": field, "field_label": FIELD_ZH[field],
                    "value": s[field], "som_at_half": round(vals[0], 4), "som_at_double": round(vals[1], 4),
                    "swing": round(swing, 4),
                })
    return best[1] if best else None


def parse_segments(records: list[dict], present: set[str]):
    """驗證並轉換 CSV 資料列。回傳 (segments, warnings)；有錯誤時一次列出全部並丟 InputError。"""
    errors: list[str] = []
    warnings: list[str] = []
    segments: list[dict] = []
    for rec in records:
        line = rec["_line"]
        name = rec.get("segment", "")
        if not name:
            errors.append(f"第 {line} 列：客群名稱是空的。")
            continue
        label = f"第 {line} 列「{name}」"
        vals: dict = {}
        row_errors = []
        for field in ("accounts", "price"):
            raw = rec.get(field, "")
            zh = FIELD_ZH[field]
            try:
                v = parse_number(raw)
                if v <= 0:
                    row_errors.append(f"{label}：{zh}「{raw}」必須大於 0。")
                else:
                    vals[field] = v
            except ValueError:
                row_errors.append(f"{label}：{zh}「{raw}」不是數字。" if raw else f"{label}：缺少{zh}。")
        for field in ("serviceable", "penetration"):
            raw = rec.get(field, "")
            zh = FIELD_ZH[field]
            try:
                vals[field] = parse_ratio(raw)
                if _is_bare_one(raw):
                    warnings.append(f"{label}：{zh}填「{raw}」，已解讀為 100%；若原意是 1%，請寫成 1%。")
            except ValueError as e:
                if raw:
                    row_errors.append(
                        f"{label}：{zh}「{raw}」無法解讀（{e}），請填 60、60% 或 0.6，範圍 0–100%。"
                    )
                else:
                    row_errors.append(f"{label}：缺少{zh}。")
        if row_errors:
            errors.extend(row_errors)
            continue
        segments.append({"segment": name, **vals, "source": rec.get("source", "")})

    if errors:
        raise InputError("輸入資料有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))

    seen: dict[str, int] = {}
    for s in segments:
        seen[s["segment"]] = seen.get(s["segment"], 0) + 1
    dups = [n for n, c in seen.items() if c > 1]
    if dups:
        warnings.append(
            "客群名稱重複：" + "、".join(f"「{d}」" for d in dups) + "，請確認是否重複計算（客群重疊會讓合計灌水）。"
        )

    no_source = [s["segment"] for s in segments if not s["source"]]
    if no_source:
        extra = "" if "source" in present else "（CSV 沒有來源欄）"
        warnings.append(f"{SOURCE_PENDING}{extra}：{'、'.join(no_source)}。沒有來源的數字只能當假設值，請補上出處。")
    return segments, warnings


def analyze(segments: list[dict], unit: str, years: int, target: float | None,
            warnings: list[str], from_csv: bool) -> dict:
    warnings = list(warnings)
    seg_out = []
    for s in segments:
        m = market_size(s["accounts"], s["price"], s["serviceable"], s["penetration"])
        row = {
            "segment": s["segment"],
            "accounts": s["accounts"],
            "price": s["price"],
            "serviceable": round(s["serviceable"], 6),
            "penetration": round(s["penetration"], 6),
            **{k: round(v, 4) for k, v in m.items()},
        }
        if from_csv:
            row["source"] = s["source"]
            row["source_status"] = "已填" if s["source"] else SOURCE_PENDING
        seg_out.append(row)

    aggressive = [s for s in segments if s["penetration"] > AGGRESSIVE_PENETRATION + 1e-12]
    if aggressive:
        names = "、".join(f"{s['segment']}（{fmt_pct(s['penetration'])}）" for s in aggressive)
        warnings.append(
            f"滲透率超過 {fmt_pct(AGGRESSIVE_PENETRATION)}：{names}。這在多數市場很激進，請附依據"
            "（同類產品實績、已簽意向書等）。此門檻是經驗值，依產業而異，是提醒、不是定律。"
        )
    full = [s["segment"] for s in segments if s["serviceable"] >= 1 - 1e-12]
    if full:
        warnings.append(
            f"可服務比例為 100%：{'、'.join(full)}。通常會有地區、語言、產業、規模的限制，"
            "請確認真的每一家都服務得到。這是提醒、不是定律。"
        )

    tot = {k: sum(x[k] for x in seg_out) for k in ("accounts", "tam", "sam", "som", "sam_accounts", "som_accounts")}
    total = {k: round(v, 4) for k, v in tot.items()}
    total["blended_serviceable"] = round(tot["sam"] / tot["tam"], 6) if tot["tam"] else None
    total["blended_penetration"] = round(tot["som"] / tot["sam"], 6) if tot["sam"] else None
    months = years * 12
    total["monthly_new_accounts"] = round(tot["som_accounts"] / months, 4)

    target_out = None
    if target is not None:
        need = required_penetration(target, tot["sam"])
        target_out = {
            "target": target,
            "sam": total["sam"],
            "required_penetration": None if need is None else round(need, 6),
            "current_penetration": total["blended_penetration"],
            "reachable": need is not None and need <= 1 + 1e-12,
            "multiple_of_current": (
                round(need / (tot["som"] / tot["sam"]), 4) if need is not None and tot["som"] > 0 else None
            ),
        }

    res = {
        "disclaimer": DISCLAIMER,
        "formulas": FORMULAS,
        "unit": unit,
        "years": years,
        "segments": seg_out,
        "total": total,
        "sensitivity": sensitivity_table(segments),
        "target": target_out,
        "key_assumption": key_assumption(segments),
        "warnings": warnings,
    }
    res["interpretation"] = interpret(res)
    return res


def interpret(res: dict) -> list[str]:
    unit, years, tot = res["unit"], res["years"], res["total"]
    segs = res["segments"]
    obs = [
        f"TAM {fmt_num(tot['tam'])} 是「所有目標客群都買單」的上限；SAM {fmt_num(tot['sam'])} 是我們服務得到的部分；"
        f"SOM {fmt_num(tot['som'])} 才是 {years} 年內實際可能拿到的年營收，規劃請以 SOM 為準。",
        f"SOM 換算成客戶數是 {fmt_num(tot['som_accounts'])} {unit}，平均每月要新增約 "
        f"{fmt_num(tot['monthly_new_accounts'], 1)} {unit}（{fmt_num(tot['som_accounts'])} ÷ {years * 12} 個月）。"
        "請拿這個數字問業務或行銷：以現有人力與通路做不做得到。",
    ]
    if len(segs) > 1 and tot["som"] > 0:
        top = max(segs, key=lambda x: x["som"])
        obs.append(
            f"SOM 最大的客群是「{top['segment']}」（{fmt_num(top['som'])}，占合計 {fmt_pct(top['som'] / tot['som'])}）。"
            "合計的前提是客群之間不重疊，重疊的部分要先扣掉。"
        )
    ka = res["key_assumption"]
    if ka:
        val = fmt_pct(ka["value"]) if ka["field"] in ("serviceable", "penetration") else fmt_num(ka["value"])
        where = f"「{ka['segment']}」的" if len(segs) > 1 else ""
        obs.append(
            f"最該先查證的假設：{where}{ka['field_label']}（目前 {val}）。它從 ×0.5 到 ×2，合計 SOM 會在 "
            f"{fmt_num(ka['som_at_half'])} 到 {fmt_num(ka['som_at_double'])} 之間擺動，是所有輸入裡擺幅最大的。"
            "四個輸入是相乘關係，擺幅相同時依「越難直接查到越先查」排序（滲透率 > 可服務比例 > 年單價 > 目標客群數）。"
            f"{ka['field_label']}要先查，因為{FIELD_HOW[ka['field']]}。"
        )
    else:
        obs.append("SOM 為 0（滲透率或可服務比例是 0），請先確認這兩個比例。")
    t = res["target"]
    if t:
        if t["required_penetration"] is None:
            obs.append(f"目標年營收 {fmt_num(t['target'])}：SAM 為 0，無法換算所需滲透率。")
        elif not t["reachable"]:
            obs.append(
                f"目標年營收 {fmt_num(t['target'])} 超過 SAM（{fmt_num(t['sam'])}），滲透率到 100% 也達不到；"
                "要達標得提高年單價、擴大可服務範圍或增加客群。"
            )
        else:
            msg = f"目標年營收 {fmt_num(t['target'])} 需要滲透率 {fmt_pct(t['required_penetration'])}"
            if t["multiple_of_current"] is not None:
                msg += f"，是目前假設（{fmt_pct(t['current_penetration'])}）的 {fmt_num(t['multiple_of_current'])} 倍"
            if t["required_penetration"] > AGGRESSIVE_PENETRATION + 1e-12:
                msg += f"；超過 {fmt_pct(AGGRESSIVE_PENETRATION)}，在多數市場很激進（經驗值，依產業而異）"
            obs.append(msg + "。")
    if res["warnings"]:
        obs.append(f"有 {len(res['warnings'])} 則提醒，見上方「提醒」，處理後數字才站得住。")
    obs.append("bottom-up 的結果建議再用 top-down（產業報告的整體市場數字）交叉驗證，兩者差距過大時回頭檢查客群定義。")
    return obs


def render_markdown(res: dict) -> str:
    unit, years, tot = res["unit"], res["years"], res["total"]
    segs = res["segments"]
    has_source = any("source" in s for s in segs)
    out = ["# 市場規模試算（bottom-up）", ""]
    out.append(f"> {res['disclaimer']}")
    out.append("")
    out.append("公式：")
    out.append("")
    out.append("- TAM = 目標客群數 × 年單價")
    out.append("- SAM = TAM × 可服務比例；SAM 客群數 = 目標客群數 × 可服務比例")
    out.append(f"- SOM = SAM × 滲透率（{years} 年內可取得）；SOM 客群數 = SAM 客群數 × 滲透率")
    out.append("")
    out.append("## 各客群")
    out.append("")
    head = ["客群", f"目標客群數（{unit}）", "年單價", "可服務比例", "滲透率", "TAM", "SAM", f"SOM（{years} 年）",
            f"SAM {unit}數", f"SOM {unit}數"]
    if has_source:
        head.append("來源")
    out.append("| " + " | ".join(head) + " |")
    out.append("|" + "|".join(["---"] * len(head)) + "|")
    for s in segs:
        row = [md_cell(s["segment"]), fmt_num(s["accounts"]), fmt_num(s["price"]), fmt_pct(s["serviceable"]),
               fmt_pct(s["penetration"]), fmt_num(s["tam"]), fmt_num(s["sam"]), fmt_num(s["som"]),
               fmt_num(s["sam_accounts"]), fmt_num(s["som_accounts"])]
        if has_source:
            row.append(md_cell(s["source"]) if s["source"] else f"**{SOURCE_PENDING}**")
        out.append("| " + " | ".join(row) + " |")
    out.append("")
    out.append("## 合計")
    out.append("")
    out.append("| 層級 | 計算式 | 金額（年營收） | 客群數 |")
    out.append("|---|---|---|---|")
    out.append(f"| TAM | 目標客群數 × 年單價 | {fmt_num(tot['tam'])} | {fmt_num(tot['accounts'])} {unit} |")
    sv = "—" if tot["blended_serviceable"] is None else fmt_pct(tot["blended_serviceable"])
    pn = "—" if tot["blended_penetration"] is None else fmt_pct(tot["blended_penetration"])
    out.append(f"| SAM | TAM × {sv}（可服務比例） | {fmt_num(tot['sam'])} | {fmt_num(tot['sam_accounts'])} {unit} |")
    out.append(f"| SOM（{years} 年） | SAM × {pn}（滲透率） | {fmt_num(tot['som'])} | {fmt_num(tot['som_accounts'])} {unit} |")
    out.append(f"| 換算 | SOM {unit}數 ÷ {years * 12} 個月 | — | 每月約 {fmt_num(tot['monthly_new_accounts'], 1)} {unit}新客戶 |")
    if len(segs) > 1:
        out.append("")
        out.append("合計列的比例是各客群加權後的結果（SAM ÷ TAM、SOM ÷ SAM）。")
    out.append("")

    sens = res["sensitivity"]
    out.append("## 敏感度：SOM 對滲透率與年單價")
    out.append("")
    out.append("| 滲透率＼年單價 | " + " | ".join(f"年單價 ×{fmt_num(f)}" for f in sens["price_factors"]) + " |")
    out.append("|" + "|".join(["---"] * (len(sens["price_factors"]) + 1)) + "|")
    any_cap = False
    for i, pf in enumerate(sens["penetration_factors"]):
        cells = []
        for j in range(len(sens["price_factors"])):
            txt = fmt_num(sens["som"][i][j])
            if sens["capped"][i][j]:
                txt += " ＊"
                any_cap = True
            if pf == 1 and sens["price_factors"][j] == 1:
                txt = f"**{txt}**"
            cells.append(txt)
        out.append(f"| 滲透率 ×{fmt_num(pf)} | " + " | ".join(cells) + " |")
    out.append("")
    out.append("**粗體** 是目前的假設。" + ("＊ 表示滲透率乘上倍數後超過 100%，已夾在 100%。" if any_cap else ""))
    out.append("")

    t = res["target"]
    if t:
        out.append("## 目標回推")
        out.append("")
        if t["required_penetration"] is None:
            out.append(f"- 目標年營收 {fmt_num(t['target'])}：SAM 為 0，無法換算。")
        else:
            out.append(
                f"- 目標年營收 {fmt_num(t['target'])} ÷ SAM {fmt_num(t['sam'])} = 需要滲透率 "
                f"**{fmt_pct(t['required_penetration'])}**"
                + ("" if t["reachable"] else "（超過 100%，在目前的 SAM 內達不到）")
            )
            if t["current_penetration"] is not None:
                out.append(f"- 目前假設的滲透率：{fmt_pct(t['current_penetration'])}")
        out.append("")

    out.append("## 提醒")
    out.append("")
    if res["warnings"]:
        out.extend(f"- {md_cell(w)}" for w in res["warnings"])
    else:
        out.append("- （無）")
    out.append("")
    out.append("## 解讀")
    out.append("")
    out.extend(f"- {o}" for o in res["interpretation"])
    out.append(f"- {res['disclaimer']}")
    return "\n".join(out) + "\n"


def _positive_float(s: str) -> float:
    try:
        v = parse_number(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"「{s}」不是數字")
    if v <= 0:
        raise argparse.ArgumentTypeError(f"必須大於 0，收到 {s}")
    return v


def _positive_int(s: str) -> int:
    try:
        v = int(s.strip())
    except ValueError:
        raise argparse.ArgumentTypeError(f"「{s}」不是整數")
    if v <= 0:
        raise argparse.ArgumentTypeError(f"必須大於 0，收到 {s}")
    return v


def build_parser() -> argparse.ArgumentParser:
    p = _ZhArgumentParser(
        prog="market_size.py",
        description=(
            "市場規模 bottom-up 試算：TAM = 目標客群數 × 年單價；SAM = TAM × 可服務比例；SOM = SAM × 滲透率。\n"
            "含滲透率 × 年單價的敏感度表。" + DISCLAIMER
        ),
        epilog=(
            "單一客群：--accounts、--price、--serviceable、--penetration 四個都要給。\n"
            "多個客群：給 CSV，欄位 segment/客群、accounts/家數/人數、price/年單價/年營收、\n"
            "serviceable/可服務比例、penetration/滲透率；選填 source/來源。\n"
            "比例可填 60%、60 或 0.6（沒有 % 且不大於 1 的數字視為小數，例如 0.6 = 60%、1 = 100%）。"
        ),
    )
    p.add_argument("csv", nargs="?", help="多客群 CSV 檔路徑（UTF-8，Excel 匯出的 BOM 也可以）；單一客群請改用下方參數")
    p.add_argument("--accounts", metavar="N", help="目標客群總家數或人數")
    p.add_argument("--price", metavar="N", help="每家（每人）每年平均營收")
    p.add_argument("--serviceable", metavar="PCT", help="我們服務得到的比例，用來算 SAM，例如 60%%")
    p.add_argument("--penetration", metavar="PCT", help="期間內可取得的滲透率，用來算 SOM，例如 5%%")
    p.add_argument("--years", type=_positive_int, default=3, metavar="N",
                   help="滲透率對應的年數，用於輸出文字與每月新客戶換算（預設 3）")
    p.add_argument("--unit", choices=["家", "人"], default="家", help="客群單位：家 或 人（預設 家）")
    p.add_argument("--label", metavar="TEXT", help="單一客群的名稱（預設「目標客群」）")
    p.add_argument("--target", type=_positive_float, metavar="N",
                   help="目標年營收；有給才會回推「SOM 要達標需要多少滲透率」")
    p.add_argument("--json", action="store_true", help="輸出 JSON（給程式讀），不輸出 Markdown")
    return p


def _single_segment(args) -> tuple[list[dict], list[str]]:
    names = ("accounts", "price", "serviceable", "penetration")
    missing = [f"--{n}" for n in names if getattr(args, n) is None]
    if missing:
        raise InputError(
            "請給 CSV 檔，或提供單一客群的四個參數。缺少：" + "、".join(missing) + "。腳本不會替你補預設數字。"
        )
    errors, warnings, vals = [], [], {}
    for field in ("accounts", "price"):
        raw = getattr(args, field)
        try:
            v = parse_number(raw)
            if v <= 0:
                errors.append(f"--{field}（{FIELD_ZH[field]}）「{raw}」必須大於 0。")
            else:
                vals[field] = v
        except ValueError:
            errors.append(f"--{field}（{FIELD_ZH[field]}）「{raw}」不是數字。")
    for field in ("serviceable", "penetration"):
        raw = getattr(args, field)
        try:
            vals[field] = parse_ratio(raw)
            if _is_bare_one(raw):
                warnings.append(f"--{field}（{FIELD_ZH[field]}）填「{raw}」，已解讀為 100%；若原意是 1%，請寫成 1%。")
        except ValueError as e:
            errors.append(
                f"--{field}（{FIELD_ZH[field]}）「{raw}」無法解讀（{e}），請填 60、60% 或 0.6，範圍 0–100%。"
            )
    if errors:
        raise InputError("輸入有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))
    return [{"segment": args.label or "目標客群", **vals, "source": ""}], warnings


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    if args.csv:
        given = [f"--{n}" for n in ("accounts", "price", "serviceable", "penetration", "label")
                 if getattr(args, n) is not None]
        if given:
            raise InputError(
                "CSV 與單一客群參數不能同時使用（收到 " + "、".join(given) + "）。多客群請把數字都寫進 CSV。"
            )
        records, present, unused = read_table(args.csv, ALIASES, REQUIRED)
        segments, warnings = parse_segments(records, present)
        if unused:
            warnings.append("以下欄位未使用（若是拼錯欄名請修正）：" + "、".join(unused))
        from_csv = True
    else:
        segments, warnings = _single_segment(args)
        from_csv = False
    res = analyze(segments, args.unit, args.years, args.target, warnings, from_csv)
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
