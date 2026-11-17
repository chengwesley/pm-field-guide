#!/usr/bin/env python3
"""RICE 優先排序計算器（pm-field-guide）。

讀入一份需求清單 CSV，計算 RICE 分數 = 觸及 × 影響 × 信心 ÷ 工作量，
依分數排序、切成 高／中／低 三層，可畫出產能線，並做「估值差兩倍」敏感度檢查，
讓 PM 知道哪些估值要先查證。分數由程式計算，不靠心算。

CSV 欄位（中英文皆可，大小寫不拘，括號內說明會被忽略，例如「工作量（人月）」）：
  必要：item／項目、reach／觸及、impact／影響、confidence／信心、effort／工作量／人月
  選填：reach_unit／觸及單位、must／必做（是/Y/yes/true/1）、note／依據／備註

用法範例：
  python rice.py backlog.csv
  python rice.py backlog.csv --capacity 6
  python rice.py backlog.csv --capacity 6 --json
  python rice.py backlog.csv --csv-out rice_result.csv
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


def write_csv_bom(path: str, header: list[str], rows: list[list]):
    try:
        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    except OSError as e:
        raise InputError(f"無法寫入 CSV：{path}（{e.strerror}）")


# ---------------------------------------------------------------------------
# RICE
# ---------------------------------------------------------------------------

ALIASES = {
    "item": ["item", "項目"],
    "reach": ["reach", "觸及"],
    "impact": ["impact", "影響"],
    "confidence": ["confidence", "信心"],
    "effort": ["effort", "工作量", "人月"],
    "reach_unit": ["reach_unit", "觸及單位"],
    "must": ["must", "必做"],
    "note": ["note", "依據", "備註"],
}
REQUIRED = ["item", "reach", "impact", "confidence", "effort"]
STANDARD_IMPACTS = (3.0, 2.0, 1.0, 0.5, 0.25)
TRUTHY = {"是", "y", "yes", "true", "1"}
TIER_NAMES = ("高", "中", "低")
VARIANTS = (
    ("reach", 0.5, "觸及×0.5"),
    ("reach", 2.0, "觸及×2"),
    ("effort", 0.5, "工作量×0.5"),
    ("effort", 2.0, "工作量×2"),
)
TIER_RULE = (
    "依排名把評分項目切成三等份：前三分之一為「高」、中間為「中」、後三分之一為「低」；"
    "無法整除時，多出的名額依序給「高」、再給「中」。同分項目歸入同一層。"
    "分數差距小的項目排名先後沒有意義，請以分層而非精確名次討論。"
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


def rice_score(reach: float, impact: float, confidence: float, effort: float) -> float:
    return reach * impact * confidence / effort


def parse_items(records: list[dict], present: set[str]):
    """驗證並轉換資料列。回傳 (scored, musts, warnings)；有錯誤時一次列出全部並丟 InputError。"""
    errors: list[str] = []
    warnings: list[str] = []
    scored: list[dict] = []
    musts: list[dict] = []
    for rec in records:
        line = rec["_line"]
        name = rec.get("item", "")
        label = f"第 {line} 列「{name}」" if name else f"第 {line} 列"
        if not name:
            errors.append(f"第 {line} 列：項目名稱是空的。")
            continue
        is_must = rec.get("must", "").strip().lower() in TRUTHY
        note = rec.get("note", "")
        if is_must:
            effort = None
            if rec.get("effort", ""):
                try:
                    effort = parse_number(rec["effort"])
                    if effort <= 0:
                        raise ValueError
                except ValueError:
                    errors.append(f"{label}：工作量「{rec['effort']}」必須是大於 0 的數字。")
                    continue
            musts.append({"item": name, "effort": effort, "note": note, "line": line})
            continue

        row_errors = []
        vals = {}
        for field, zh in (("reach", "觸及"), ("effort", "工作量")):
            raw = rec.get(field, "")
            try:
                vals[field] = parse_number(raw)
            except ValueError:
                row_errors.append(f"{label}：{zh}「{raw}」不是數字。" if raw else f"{label}：缺少{zh}。")
        if "reach" in vals and vals["reach"] < 0:
            row_errors.append(f"{label}：觸及不能是負數。")
        if "effort" in vals and vals["effort"] <= 0:
            row_errors.append(f"{label}：工作量必須大於 0（人月）。")

        raw = rec.get("impact", "")
        try:
            imp = parse_number(raw)
            if imp <= 0:
                row_errors.append(f"{label}：影響「{raw}」必須是正數（建議 3、2、1、0.5、0.25）。")
            else:
                vals["impact"] = imp
                if not any(abs(imp - s) < 1e-9 for s in STANDARD_IMPACTS):
                    warnings.append(
                        f"{label}：影響值 {fmt_num(imp)} 不在標準刻度（3、2、1、0.5、0.25）內，仍照原值計算；"
                        "建議改回標準刻度，跨項目才可比。"
                    )
        except ValueError:
            row_errors.append(f"{label}：影響「{raw}」不是數字。" if raw else f"{label}：缺少影響。")

        raw = rec.get("confidence", "")
        try:
            vals["confidence"] = parse_confidence(raw)
        except ValueError:
            row_errors.append(
                f"{label}：信心「{raw}」無法解讀，請填 80、80% 或 0.8（0–100%）。" if raw else f"{label}：缺少信心。"
            )

        if row_errors:
            errors.extend(row_errors)
            continue
        scored.append({
            "idx": len(scored),
            "item": name,
            "reach": vals["reach"],
            "reach_unit": rec.get("reach_unit", ""),
            "impact": vals["impact"],
            "confidence": vals["confidence"],
            "effort": vals["effort"],
            "note": note,
            "line": line,
            "score": rice_score(vals["reach"], vals["impact"], vals["confidence"], vals["effort"]),
        })

    if errors:
        raise InputError("輸入資料有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))
    if not scored and not musts:
        raise InputError("沒有可計算的項目。")

    # 名稱重複
    seen: dict[str, int] = {}
    for it in [*scored, *musts]:
        seen[it["item"]] = seen.get(it["item"], 0) + 1
    dups = [n for n, c in seen.items() if c > 1]
    if dups:
        warnings.append("項目名稱重複：" + "、".join(f"「{d}」" for d in dups) + "，請確認是否重複列入。")

    # 觸及單位
    units = sorted({it["reach_unit"] for it in scored if it["reach_unit"]})
    if len(units) > 1:
        warnings.append(
            "觸及單位混用：" + "、".join(f"「{u}」" for u in units)
            + "。B2B 的客戶家數和使用者人數不能放在同一欄比較，分數會失真；請統一單位，或把不同單位的項目分開排序。"
        )
    elif units and any(not it["reach_unit"] for it in scored):
        blanks = [it["item"] for it in scored if not it["reach_unit"]]
        warnings.append(
            f"部分項目沒填觸及單位（{'、'.join(blanks)}），無法確認是否都用「{units[0]}」計算。"
        )

    # 沒有依據的高信心
    no_basis = [it for it in scored if it["confidence"] > 0.5 + 1e-9 and not it["note"]]
    if no_basis:
        names = "、".join(f"{it['item']}（{fmt_num(it['confidence'] * 100)}%）" for it in no_basis)
        extra = "" if "note" in present else "（CSV 沒有依據／備註欄）"
        warnings.append(f"沒有依據的信心值建議最高 50%{extra}：{names}。請補上資料來源，或把信心調到 50% 以下。")

    return scored, musts, warnings


def tier_sizes(n: int) -> list[int]:
    k, r = divmod(n, 3)
    return [k + (r >= 1), k + (r >= 2), k]


def evaluate(entries: list[dict], capacity: float | None):
    """entries: [{idx, score, effort}]。回傳排序、名次、分層、是否在產能線內、累計工作量。"""
    order = sorted(entries, key=lambda e: (-e["score"], e["idx"]))
    sizes = tier_sizes(len(order))
    ranks: dict[int, int] = {}
    tiers: dict[int, int] = {}
    for pos, e in enumerate(order):
        ranks[e["idx"]] = pos + 1
        t = 0 if pos < sizes[0] else (1 if pos < sizes[0] + sizes[1] else 2)
        if pos > 0 and math.isclose(e["score"], order[pos - 1]["score"], rel_tol=1e-9, abs_tol=1e-12):
            t = tiers[order[pos - 1]["idx"]]
        tiers[e["idx"]] = t
    in_plan: set[int] | None = None
    cum: dict[int, float] = {}
    if capacity is not None:
        in_plan = set()
        total = 0.0
        line_open = True
        for e in order:
            total += e["effort"]
            cum[e["idx"]] = total
            if line_open and total <= capacity + 1e-9:
                in_plan.add(e["idx"])
            else:
                line_open = False
    return order, ranks, tiers, in_plan, cum


def analyze(scored: list[dict], musts: list[dict], capacity: float | None, warnings: list[str]) -> dict:
    base_entries = [{"idx": it["idx"], "score": it["score"], "effort": it["effort"]} for it in scored]
    order, ranks, tiers, in_plan, cum = evaluate(base_entries, capacity)
    by_idx = {it["idx"]: it for it in scored}

    items_out = []
    for e in order:
        it = by_idx[e["idx"]]
        sens = []
        for field, factor, label in VARIANTS:
            reach = it["reach"] * factor if field == "reach" else it["reach"]
            effort = it["effort"] * factor if field == "effort" else it["effort"]
            new_score = rice_score(reach, it["impact"], it["confidence"], effort)
            mod = [
                {"idx": x["idx"], "score": new_score, "effort": effort} if x["idx"] == it["idx"] else x
                for x in base_entries
            ]
            _, r2, t2, p2, _ = evaluate(mod, capacity)
            if capacity is not None:
                changed = (it["idx"] in p2) != (it["idx"] in in_plan)
            else:
                changed = t2[it["idx"]] != tiers[it["idx"]]
            sens.append({
                "variant": label,
                "score": round(new_score, 4),
                "rank": r2[it["idx"]],
                "tier": TIER_NAMES[t2[it["idx"]]],
                "in_plan": (it["idx"] in p2) if capacity is not None else None,
                "changes_conclusion": changed,
            })
        items_out.append({
            "rank": ranks[it["idx"]],
            "item": it["item"],
            "tier": TIER_NAMES[tiers[it["idx"]]],
            "score": round(it["score"], 4),
            "reach": it["reach"],
            "reach_unit": it["reach_unit"],
            "impact": it["impact"],
            "confidence": round(it["confidence"], 4),
            "effort": it["effort"],
            "cumulative_effort": round(cum[it["idx"]], 4) if capacity is not None else None,
            "in_plan": (it["idx"] in in_plan) if capacity is not None else None,
            "note": it["note"],
            "sensitive": any(s["changes_conclusion"] for s in sens),
            "sensitivity": sens,
        })

    result = {
        "tier_rule": TIER_RULE,
        "capacity": capacity,
        "items": items_out,
        "must_items": [{"item": m["item"], "effort": m["effort"], "note": m["note"]} for m in musts],
        "warnings": list(warnings),
    }
    if capacity is not None:
        used = sum(x["effort"] for x in items_out if x["in_plan"])
        result["capacity_used"] = round(used, 4)
        result["capacity_remaining"] = round(capacity - used, 4)
        result["not_in_plan"] = [x["item"] for x in items_out if not x["in_plan"]]
    result["interpretation"] = interpret(result)
    return result


def interpret(res: dict) -> list[str]:
    obs: list[str] = []
    items = res["items"]
    cap = res["capacity"]
    if items:
        obs.append("分層依排名切三等份（規則見上方表格下方）；分數差距小時名次先後沒有意義，請以分層討論。")
        high =[x["item"] for x in items if x["tier"] == "高"]
        obs.append(f"高優先層共 {len(high)} 項：{'、'.join(high)}。")
        if len(items) >= 2:
            a, b = items[0], items[1]
            if a["score"] > 0 and (a["score"] - b["score"]) / a["score"] < 0.10:
                obs.append(
                    f"第 1 名「{a['item']}」（{fmt_num(a['score'])}）和第 2 名「{b['item']}」（{fmt_num(b['score'])}）"
                    "分數相差不到 10%，在估值誤差範圍內，視為同一級。"
                )
    else:
        obs.append("所有項目都標為必做，沒有需要評分的項目。")

    if cap is not None and items:
        planned = [x for x in items if x["in_plan"]]
        if planned:
            obs.append(
                f"產能 {fmt_num(cap)} 人月，本期排入 {len(planned)} 項，共 {fmt_num(res['capacity_used'])} 人月，"
                f"剩 {fmt_num(res['capacity_remaining'])} 人月。"
            )
        else:
            obs.append(f"產能 {fmt_num(cap)} 人月放不下排名第 1 的項目（{fmt_num(items[0]['effort'])} 人月），本期沒有項目在產能線內。")
        rem = res["capacity_remaining"]
        fits = [x for x in items if not x["in_plan"] and x["effort"] <= rem + 1e-9]
        if fits and rem > 0:
            obs.append(
                "產能線依排名由上往下切、遇到放不下的項目就停；不過以下排名較後的項目放得進剩餘產能，"
                "可視情況討論是否補進：" + "、".join(f"{x['item']}（{fmt_num(x['effort'])} 人月）" for x in fits) + "。"
            )

    sensitive = [x for x in items if x["sensitive"]]
    basis = "是否跨過產能線" if cap is not None else "是否換層"
    if sensitive:
        parts = []
        for x in sensitive:
            fields = []
            if any(s["changes_conclusion"] for s in x["sensitivity"] if s["variant"].startswith("觸及")):
                fields.append("觸及")
            if any(s["changes_conclusion"] for s in x["sensitivity"] if s["variant"].startswith("工作量")):
                fields.append("工作量")
            parts.append(f"{x['item']}（{'、'.join(fields)}）")
        obs.append(
            f"敏感度檢查（以{basis}判斷）：{len(sensitive)} 項的估值差兩倍就會改變結論，請優先查證括號內的估值："
            + "、".join(parts) + "。"
        )
    elif items:
        obs.append(f"敏感度檢查（以{basis}判斷）：觸及或工作量單獨差兩倍，都不會改變任何項目的結論。")

    musts = res["must_items"]
    if musts:
        total = sum(m["effort"] for m in musts if m["effort"] is not None)
        missing = [m["item"] for m in musts if m["effort"] is None]
        msg = f"必做項目 {len(musts)} 項不參與評分"
        if cap is not None:
            msg += f"，也沒有從產能扣除：--capacity 應填扣掉必做之後的剩餘產能（已填工作量的必做合計 {fmt_num(total)} 人月）"
        else:
            msg += f"（已填工作量的必做合計 {fmt_num(total)} 人月）"
        if missing:
            msg += f"；未填工作量：{'、'.join(missing)}"
        obs.append(msg + "。")
    if res["warnings"]:
        obs.append(f"有 {len(res['warnings'])} 則警告，見上方「警告」，處理後結論才可靠。")
    return obs


def render_markdown(res: dict) -> str:
    cap = res["capacity"]
    items = res["items"]
    out = ["# RICE 優先排序結果", ""]
    out.append("分數 = 觸及 × 影響 × 信心 ÷ 工作量（人月）")
    out.append("")
    if items:
        out.append("## 排序與分層")
        out.append("")
        head = ["排名", "項目", "分層", "分數", "觸及", "影響", "信心", "工作量"]
        if cap is not None:
            head += ["累計工作量", "本期"]
        out.append("| " + " | ".join(head) + " |")
        out.append("|" + "|".join(["---"] * len(head)) + "|")
        line_drawn = False
        for x in items:
            if cap is not None and not x["in_plan"] and not line_drawn:
                cells = [f"**── 產能線：{fmt_num(cap)} 人月 ──**"] + [""] * (len(head) - 1)
                out.append("| " + " | ".join(cells) + " |")
                line_drawn = True
            reach = fmt_num(x["reach"]) + (f" {x['reach_unit']}" if x["reach_unit"] else "")
            row = [str(x["rank"]), md_cell(x["item"]), x["tier"], fmt_num(x["score"]), md_cell(reach),
                   fmt_num(x["impact"]), f"{fmt_num(x['confidence'] * 100, 1)}%", fmt_num(x["effort"])]
            if cap is not None:
                row += [fmt_num(x["cumulative_effort"]), "做" if x["in_plan"] else "不做"]
            out.append("| " + " | ".join(row) + " |")
        if cap is not None and not line_drawn:
            cells = [f"**── 產能線：{fmt_num(cap)} 人月 ──**"] + [""] * (len(head) - 1)
            out.append("| " + " | ".join(cells) + " |")
        out.append("")
        out.append(f"分層規則：{res['tier_rule']}")
        out.append("")
        if cap is not None:
            out.append("## 本期不做")
            out.append("")
            if res["not_in_plan"]:
                for x in items:
                    if not x["in_plan"]:
                        out.append(f"- {md_cell(x['item'])}（排名 {x['rank']}，{fmt_num(x['effort'])} 人月）")
            else:
                out.append("- （無，全部項目都在產能內）")
            out.append("")

    out.append("## 不參與評分的必做項目")
    out.append("")
    if res["must_items"]:
        out.append("| 項目 | 工作量 | 依據 |")
        out.append("|---|---|---|")
        for m in res["must_items"]:
            out.append(f"| {md_cell(m['item'])} | {fmt_num(m['effort']) if m['effort'] is not None else '未填'} | {md_cell(m['note']) or '—'} |")
    else:
        out.append("- （無）")
    out.append("")

    if items:
        basis = "跨過產能線（做↔不做）" if cap is not None else "換層"
        out.append("## 敏感度檢查")
        out.append("")
        out.append(f"每次只改一個估值、其他項目不動，重新排序；**粗體** 表示會{basis}。")
        out.append("")
        head = ["項目", "目前"] + [v[2] for v in VARIANTS] + ["判定"]
        out.append("| " + " | ".join(head) + " |")
        out.append("|" + "|".join(["---"] * len(head)) + "|")

        def cell(rank, tier, in_plan, changed):
            status = ("做" if in_plan else "不做") if cap is not None else f"{tier}層"
            txt = f"#{rank} {status}"
            return f"**{txt}**" if changed else txt

        for x in items:
            row = [md_cell(x["item"]), cell(x["rank"], x["tier"], x["in_plan"], False)]
            row += [cell(s["rank"], s["tier"], s["in_plan"], s["changes_conclusion"]) for s in x["sensitivity"]]
            row.append("敏感：估值差兩倍就會改變結論" if x["sensitive"] else "穩定")
            out.append("| " + " | ".join(row) + " |")
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


def write_result_csv(res: dict, path: str):
    header = ["排名", "項目", "分層", "分數", "觸及", "觸及單位", "影響", "信心(%)", "工作量(人月)",
              "累計工作量", "本期", "敏感度", "依據"]
    rows = []
    for x in res["items"]:
        rows.append([
            x["rank"], x["item"], x["tier"], round(x["score"], 2), x["reach"], x["reach_unit"], x["impact"],
            round(x["confidence"] * 100, 2), x["effort"],
            "" if x["cumulative_effort"] is None else x["cumulative_effort"],
            "" if x["in_plan"] is None else ("做" if x["in_plan"] else "不做"),
            "敏感" if x["sensitive"] else "穩定", x["note"],
        ])
    for m in res["must_items"]:
        rows.append(["", m["item"], "必做", "", "", "", "", "", "" if m["effort"] is None else m["effort"],
                     "", "必做", "", m["note"]])
    write_csv_bom(path, header, rows)


def _positive_float(s: str) -> float:
    try:
        v = parse_number(s)
    except ValueError:
        raise argparse.ArgumentTypeError(f"「{s}」不是數字")
    if v <= 0:
        raise argparse.ArgumentTypeError(f"產能必須大於 0，收到 {s}")
    return v


def build_parser() -> argparse.ArgumentParser:
    p = _ZhArgumentParser(
        prog="rice.py",
        description="RICE 優先排序：分數 = 觸及 × 影響 × 信心 ÷ 工作量，含分層、產能線與敏感度檢查。",
        epilog=(
            "CSV 欄位：item/項目、reach/觸及、impact/影響、confidence/信心、effort/工作量/人月；\n"
            "選填 reach_unit/觸及單位、must/必做（是/Y/yes/true/1）、note/依據/備註。\n"
            "影響建議用 3、2、1、0.5、0.25；信心可填 80、80% 或 0.8。"
        ),
    )
    p.add_argument("csv", help="需求清單 CSV 檔路徑（UTF-8，Excel 匯出的 BOM 也可以）")
    p.add_argument("--capacity", type=_positive_float, metavar="N",
                   help="本期產能（人月）。依排名累加工作量，畫出產能線")
    p.add_argument("--json", action="store_true", help="輸出 JSON（給程式讀），不輸出 Markdown")
    p.add_argument("--csv-out", metavar="PATH", help="另存結果為 UTF-8-BOM CSV，可直接貼進 Excel／Google 試算表")
    return p


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    records, present, unused = read_table(args.csv, ALIASES, REQUIRED)
    scored, musts, warnings = parse_items(records, present)
    if unused:
        warnings.append("以下欄位未使用（若是拼錯欄名請修正）：" + "、".join(unused))
    res = analyze(scored, musts, args.capacity, warnings)
    if args.csv_out:
        write_result_csv(res, args.csv_out)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(render_markdown(res), end="")
        if args.csv_out:
            print(f"\n（結果已另存：{args.csv_out}）")
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
