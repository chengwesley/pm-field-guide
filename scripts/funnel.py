#!/usr/bin/env python3
"""漏斗分析（pm-field-guide）。

讀入依漏斗順序排列的步驟人數 CSV，計算每一步的步驟轉換率、累計轉換率、流失人數與流失率，
找出「最大漏損」步驟；若有前期人數，計算轉換率變化（百分點）並對每一步做雙比例 z 檢定，
判斷差異是否可能只是隨機波動。數字由程式計算，不靠心算。

CSV 欄位（中英文皆可，大小寫不拘）：
  必要：step／步驟、count／人數／users
  選填：prev_count／前期人數（比較期間，要填就每一列都要填）
步驟順序 = 檔案中的列順序。

用法範例：
  python funnel.py funnel.csv
  python funnel.py funnel.csv --json
  python funnel.py funnel.csv --csv-out funnel_result.csv
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from statistics import NormalDist

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
    """讀 CSV（utf-8-sig），把中英文欄名對應到標準欄名。回傳 (records, present_columns, unused_headers)。"""
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
# 漏斗
# ---------------------------------------------------------------------------

ALIASES = {
    "step": ["step", "步驟"],
    "count": ["count", "人數", "users"],
    "prev_count": ["prev_count", "前期人數"],
}
REQUIRED = ["step", "count"]
ALPHA = 0.05
_INT_RE = re.compile(r"^-?\d+(\.0+)?$")


def parse_count(raw: str, label: str, zh: str) -> int:
    t = raw.replace(",", "").replace("，", "").strip()
    if not t:
        raise InputError(f"{label}：缺少{zh}。")
    if not _INT_RE.match(t):
        try:
            float(t)
        except ValueError:
            raise InputError(f"{label}：{zh}「{raw}」不是數字。")
        raise InputError(f"{label}：{zh}「{raw}」必須是整數（人數）。")
    v = int(float(t))
    if v < 0:
        raise InputError(f"{label}：{zh}「{raw}」不能是負數。")
    return v


def parse_steps(records: list[dict], present: set[str]):
    errors: list[str] = []
    steps: list[dict] = []
    has_prev = "prev_count" in present
    for rec in records:
        line = rec["_line"]
        name = rec.get("step", "")
        label = f"第 {line} 列「{name}」" if name else f"第 {line} 列"
        if not name:
            errors.append(f"第 {line} 列：步驟名稱是空的。")
            continue
        s = {"step": name, "line": line}
        try:
            s["count"] = parse_count(rec.get("count", ""), label, "人數")
        except InputError as e:
            errors.append(str(e))
        if has_prev:
            try:
                s["prev_count"] = parse_count(rec.get("prev_count", ""), label, "前期人數")
            except InputError as e:
                errors.append(str(e) + ("（有前期人數欄就每一步都要填，不會自動補值）" if "缺少" in str(e) else ""))
        steps.append(s)
    if errors:
        raise InputError("輸入資料有誤，請修正後重跑：\n" + "\n".join(f"  - {e}" for e in errors))
    if len(steps) < 2:
        raise InputError("漏斗至少要有 2 個步驟。")
    return steps, has_prev


def ratio(a: int, b: int) -> float | None:
    return a / b if b > 0 else None


def two_proportion_z(x1: int, n1: int, x2: int, n2: int) -> dict:
    """雙比例 z 檢定（合併比例），雙尾。回傳 z、p_value，無法檢定時帶 reason。"""
    if n1 <= 0 or n2 <= 0:
        return {"z": None, "p_value": None, "reason": "分母為 0，無法計算轉換率"}
    if x1 > n1 or x2 > n2:
        return {"z": None, "p_value": None, "reason": "本步人數大於上一步，轉換率超過 100%，不適用比例檢定"}
    p1, p2 = x1 / n1, x2 / n2
    pool = (x1 + x2) / (n1 + n2)
    se = math.sqrt(pool * (1 - pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return {"z": None, "p_value": None, "reason": "兩期轉換率都是 0% 或都是 100%，無變異可檢定"}
    z = (p1 - p2) / se
    p_value = 2 * (1 - NormalDist().cdf(abs(z)))
    small = min(n1 * pool, n1 * (1 - pool), n2 * pool, n2 * (1 - pool)) < 5
    return {"z": z, "p_value": p_value, "reason": None, "small_sample": small}


def analyze(steps: list[dict], has_prev: bool) -> dict:
    warnings: list[str] = []
    counts = [s["count"] for s in steps]
    first = counts[0]
    if first == 0:
        warnings.append("第一步人數為 0，無法計算累計轉換率。")
    rows = []
    for i, s in enumerate(steps):
        r = {"step": s["step"], "count": s["count"]}
        r["cumulative_conversion"] = ratio(s["count"], first)
        if i == 0:
            r.update(step_conversion=None, drop_off=None, drop_off_rate=None)
        else:
            prev = counts[i - 1]
            r["step_conversion"] = ratio(s["count"], prev)
            r["drop_off"] = prev - s["count"]
            r["drop_off_rate"] = ratio(prev - s["count"], prev)
            if s["count"] > prev:
                warnings.append(
                    f"「{s['step']}」人數（{s['count']:,}）比上一步「{steps[i - 1]['step']}」（{prev:,}）多。"
                    "漏斗的下一步不該比上一步大，通常是追蹤事件重複觸發、步驟定義不一致（例如有人可略過上一步）"
                    "或兩步的統計期間不同；請先查清楚，這一步的轉換率與流失數字不可信。"
                )
            if prev == 0:
                warnings.append(f"「{steps[i - 1]['step']}」人數為 0，「{s['step']}」的步驟轉換率無法計算。")
        rows.append(r)

    # 最大漏損
    cand = rows[1:]
    by_abs = max(cand, key=lambda r: r["drop_off"])
    rated = [r for r in cand if r["step_conversion"] is not None]
    by_rate = min(rated, key=lambda r: r["step_conversion"]) if rated else None
    biggest = {
        "by_users_lost": {"step": by_abs["step"], "drop_off": by_abs["drop_off"],
                          "step_conversion": by_abs["step_conversion"]},
        "by_step_conversion": None if by_rate is None else {
            "step": by_rate["step"], "drop_off": by_rate["drop_off"],
            "step_conversion": by_rate["step_conversion"]},
    }
    biggest["same_step"] = by_rate is not None and by_rate["step"] == by_abs["step"]

    comparison = None
    if has_prev:
        pcounts = [s["prev_count"] for s in steps]
        for i in range(1, len(steps)):
            if pcounts[i] > pcounts[i - 1]:
                warnings.append(
                    f"前期「{steps[i]['step']}」人數（{pcounts[i]:,}）比上一步（{pcounts[i - 1]:,}）多，"
                    "同樣可能是追蹤或定義問題。"
                )
        comparison = []
        for i in range(1, len(steps)):
            cur = ratio(counts[i], counts[i - 1])
            prv = ratio(pcounts[i], pcounts[i - 1])
            test = two_proportion_z(counts[i], counts[i - 1], pcounts[i], pcounts[i - 1])
            if test["p_value"] is None:
                verdict = f"無法檢定：{test['reason']}"
            elif test["p_value"] >= ALPHA:
                verdict = "差異可能只是隨機波動"
            else:
                verdict = "差異達統計顯著（p < 0.05）"
            if test.get("small_sample"):
                verdict += "；樣本小（期望次數 < 5），常態近似不可靠"
            comparison.append({
                "step": steps[i]["step"],
                "count": counts[i],
                "prev_count": pcounts[i],
                "step_conversion": cur,
                "prev_step_conversion": prv,
                "change_pp": None if cur is None or prv is None else (cur - prv) * 100,
                "z": test["z"],
                "p_value": test["p_value"],
                "random_fluctuation_likely": None if test["p_value"] is None else test["p_value"] >= ALPHA,
                "verdict": verdict,
            })
        overall_prev = ratio(pcounts[-1], pcounts[0])
    else:
        overall_prev = None

    res = {
        "steps": rows,
        "overall_conversion": ratio(counts[-1], first),
        "prev_overall_conversion": overall_prev,
        "biggest_drop": biggest,
        "comparison": comparison,
        "warnings": warnings,
    }
    res["interpretation"] = interpret(res)
    return res


def fmt_pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def fmt_pp(x: float | None) -> str:
    return "—" if x is None else f"{x:+.1f}"


def fmt_p(p: float | None) -> str:
    if p is None:
        return "—"
    return "< 0.0001" if p < 0.0001 else f"{p:.4f}"


def interpret(res: dict) -> list[str]:
    obs: list[str] = []
    steps = res["steps"]
    obs.append(
        f"整體轉換：「{steps[0]['step']}」{steps[0]['count']:,} 人走到「{steps[-1]['step']}」{steps[-1]['count']:,} 人，"
        f"整體轉換率 {fmt_pct(res['overall_conversion'])}。"
    )
    b = res["biggest_drop"]
    a = b["by_users_lost"]
    r = b["by_step_conversion"]
    if r is None:
        obs.append(f"流失人數最多的是「{a['step']}」（少了 {a['drop_off']:,} 人）。")
    elif b["same_step"]:
        obs.append(
            f"最大漏損在「{a['step']}」：流失人數最多（{a['drop_off']:,} 人），步驟轉換率也最低（{fmt_pct(a['step_conversion'])}），"
            "是最優先處理的一步。"
        )
    else:
        obs.append(
            f"兩種「最大漏損」指向不同步驟：流失人數最多是「{a['step']}」（{a['drop_off']:,} 人，轉換率 {fmt_pct(a['step_conversion'])}），"
            f"步驟轉換率最低是「{r['step']}」（{fmt_pct(r['step_conversion'])}，流失 {r['drop_off']:,} 人）。"
            "前段步驟人多，流失人數自然大；轉換率最低的那一步才是相對最弱的環節。"
            "要救回最多人看前者，要找體驗問題看後者。"
        )
    comp = res["comparison"]
    if comp is not None:
        if res["prev_overall_conversion"] is not None and res["overall_conversion"] is not None:
            d = (res["overall_conversion"] - res["prev_overall_conversion"]) * 100
            obs.append(
                f"整體轉換率由前期 {fmt_pct(res['prev_overall_conversion'])} 變為 {fmt_pct(res['overall_conversion'])}"
                f"（{fmt_pp(d)} 百分點）。"
            )
        sig_up = [c["step"] for c in comp if c["random_fluctuation_likely"] is False and c["change_pp"] > 0]
        sig_down = [c["step"] for c in comp if c["random_fluctuation_likely"] is False and c["change_pp"] < 0]
        noise = [c["step"] for c in comp if c["random_fluctuation_likely"] is True]
        if sig_up:
            obs.append(f"步驟轉換率顯著上升（p < 0.05）：{'、'.join(sig_up)}。")
        if sig_down:
            obs.append(f"步驟轉換率顯著下降（p < 0.05）：{'、'.join(sig_down)}，建議優先追原因。")
        if noise:
            obs.append(f"差異可能只是隨機波動（p ≥ 0.05）：{'、'.join(noise)}，不宜據此下結論。")
        obs.append(
            "z 檢定假設兩期是彼此獨立的使用者；若同一批人跨兩期重複出現，或步驟人數是事件次數而非人數，"
            "p 值會失準。同時檢定多個步驟時，偶爾出現一個 p < 0.05 也可能是巧合。"
        )
    if res["warnings"]:
        obs.append(f"有 {len(res['warnings'])} 則警告，見上方「警告」，處理後數字才可靠。")
    return obs


def render_markdown(res: dict) -> str:
    out = ["# 漏斗分析", "", "## 各步驟轉換", ""]
    out.append("| 步驟 | 人數 | 步驟轉換率 | 累計轉換率 | 流失人數 | 流失率 |")
    out.append("|---|---|---|---|---|---|")
    for r in res["steps"]:
        drop = "—" if r["drop_off"] is None else f"{r['drop_off']:,}"
        out.append(
            f"| {md_cell(r['step'])} | {r['count']:,} | {fmt_pct(r['step_conversion'])} | "
            f"{fmt_pct(r['cumulative_conversion'])} | {drop} | {fmt_pct(r['drop_off_rate'])} |"
        )
    out.append("")
    out.append("步驟轉換率 = 本步 ÷ 上一步；累計轉換率 = 本步 ÷ 第一步；流失率 = 1 − 步驟轉換率。")
    out.append("")
    b = res["biggest_drop"]
    out.append("## 最大漏損")
    out.append("")
    a = b["by_users_lost"]
    out.append(f"- 以流失人數看：「{md_cell(a['step'])}」，流失 {a['drop_off']:,} 人（步驟轉換率 {fmt_pct(a['step_conversion'])}）")
    if b["by_step_conversion"]:
        r = b["by_step_conversion"]
        out.append(f"- 以步驟轉換率看：「{md_cell(r['step'])}」，轉換率 {fmt_pct(r['step_conversion'])}（流失 {r['drop_off']:,} 人）")
        out.append(f"- 兩者{'相同' if b['same_step'] else '不同'}")
    out.append("")
    if res["comparison"] is not None:
        out.append("## 與前期比較")
        out.append("")
        out.append("| 步驟 | 本期人數 | 前期人數 | 本期轉換率 | 前期轉換率 | 變化（百分點） | z | p 值 | 判定 |")
        out.append("|---|---|---|---|---|---|---|---|---|")
        for c in res["comparison"]:
            z = "—" if c["z"] is None else f"{c['z']:.2f}"
            out.append(
                f"| {md_cell(c['step'])} | {c['count']:,} | {c['prev_count']:,} | {fmt_pct(c['step_conversion'])} | "
                f"{fmt_pct(c['prev_step_conversion'])} | {fmt_pp(c['change_pp'])} | {z} | {fmt_p(c['p_value'])} | {c['verdict']} |"
            )
        out.append("")
        out.append("檢定方法：雙比例 z 檢定（合併比例、雙尾），比較本期與前期的步驟轉換率，顯著水準 0.05。")
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


def _pct_num(x: float | None):
    return "" if x is None else round(x * 100, 2)


def write_result_csv(res: dict, path: str):
    header = ["步驟", "人數", "步驟轉換率(%)", "累計轉換率(%)", "流失人數", "流失率(%)"]
    comp = {c["step"]: c for c in (res["comparison"] or [])}
    if res["comparison"] is not None:
        header += ["前期人數", "前期步驟轉換率(%)", "變化(百分點)", "z", "p值", "判定"]
    rows = []
    for i, r in enumerate(res["steps"]):
        row = [r["step"], r["count"], _pct_num(r["step_conversion"]), _pct_num(r["cumulative_conversion"]),
               "" if r["drop_off"] is None else r["drop_off"], _pct_num(r["drop_off_rate"])]
        if res["comparison"] is not None:
            c = comp.get(r["step"]) if i > 0 else None
            if c is None:
                row += ["", "", "", "", "", ""]
            else:
                row += [c["prev_count"], _pct_num(c["prev_step_conversion"]),
                        "" if c["change_pp"] is None else round(c["change_pp"], 2),
                        "" if c["z"] is None else round(c["z"], 4),
                        "" if c["p_value"] is None else round(c["p_value"], 6), c["verdict"]]
        rows.append(row)
    write_csv_bom(path, header, rows)


def build_parser() -> argparse.ArgumentParser:
    p = _ZhArgumentParser(
        prog="funnel.py",
        description="漏斗分析：步驟轉換率、累計轉換率、流失與最大漏損；有前期人數時做雙比例 z 檢定。",
        epilog=(
            "CSV 欄位：step/步驟、count/人數/users；選填 prev_count/前期人數。\n"
            "步驟順序依檔案列順序；人數必須是非負整數。"
        ),
    )
    p.add_argument("csv", help="漏斗 CSV 檔路徑（UTF-8，Excel 匯出的 BOM 也可以）")
    p.add_argument("--json", action="store_true", help="輸出 JSON（給程式讀），不輸出 Markdown")
    p.add_argument("--csv-out", metavar="PATH", help="另存結果為 UTF-8-BOM CSV，可直接貼進 Excel／Google 試算表")
    return p


def run(argv: list[str] | None = None) -> dict:
    args = build_parser().parse_args(argv)
    records, present, unused = read_table(args.csv, ALIASES, REQUIRED)
    steps, has_prev = parse_steps(records, present)
    res = analyze(steps, has_prev)
    if unused:
        res["warnings"].append("以下欄位未使用（若是拼錯欄名請修正）：" + "、".join(unused))
        res["interpretation"] = interpret(res)
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
