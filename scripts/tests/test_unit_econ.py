"""unit_econ.py 測試。執行：在 pm-field-guide 資料夾下 `python -X utf8 -m unittest discover -s scripts/tests`。"""
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent
EXAMPLES = SCRIPTS.parent / "examples"
sys.path.insert(0, str(SCRIPTS))

import unit_econ  # noqa: E402


def write_csv(text: str, bom: bool = True) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)
    return path


def run_json(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        unit_econ.run(argv + ["--json"])
    return json.loads(buf.getvalue())


# 手算基準：
#   案例 A：arpu 499、margin 55%、churn 6%、cac 1200
#     每月毛利 = 499 × 0.55 = 274.45
#     壽命     = 1 ÷ 0.06 = 16.6667 月（< 36，未截斷）
#     LTV      = 274.45 × 16.6667 = 4,574.17
#     LTV/CAC  = 4574.17 ÷ 1200 = 3.8118
#     回收期   = 1200 ÷ 274.45 = 4.3724 月
#   案例 B：arpu 1500、margin 80%、churn 3%、cac 12000
#     每月毛利 = 1200；壽命 = 33.3333 月；LTV = 40,000；LTV/CAC = 3.3333；回收期 = 10 月
CASE_A = ["--arpu", "499", "--margin", "55%", "--churn", "6%", "--cac", "1200"]
CASE_B = ["--arpu", "1500", "--margin", "80%", "--churn", "3%", "--cac", "12000"]


class TestParsing(unittest.TestCase):
    def test_percent_formats(self):
        self.assertAlmostEqual(unit_econ.parse_percent("80"), 0.8)
        self.assertAlmostEqual(unit_econ.parse_percent("80%"), 0.8)
        self.assertAlmostEqual(unit_econ.parse_percent("0.8"), 0.8)
        self.assertAlmostEqual(unit_econ.parse_percent("100％"), 1.0)  # 全形百分號
        self.assertAlmostEqual(unit_econ.parse_percent("0.5%"), 0.005)
        self.assertAlmostEqual(unit_econ.parse_percent("0"), 0.0)
        for bad in ("150", "-5", "abc", ""):
            with self.assertRaises(ValueError):
                unit_econ.parse_percent(bad)

    def test_three_percent_spellings_give_same_result(self):
        results = []
        for margin, churn in (("55%", "6%"), ("55", "6"), ("0.55", "0.06")):
            res = run_json(["--arpu", "499", "--margin", margin, "--churn", churn, "--cac", "1200"])
            results.append(res["segments"][0]["ltv_cac"])
        self.assertEqual(results[0], results[1])
        self.assertEqual(results[1], results[2])


class TestPureFunctions(unittest.TestCase):
    def test_case_a(self):
        r = unit_econ.unit_economics(499, 0.55, 0.06, 1200)
        self.assertAlmostEqual(r["monthly_gross_profit"], 274.45, places=6)
        self.assertAlmostEqual(r["lifetime_months"], 16.67, places=2)
        self.assertAlmostEqual(r["ltv"], 4574.17, places=2)
        self.assertAlmostEqual(r["ltv_cac"], 3.81, places=2)
        self.assertAlmostEqual(r["payback_months"], 4.37, places=2)
        self.assertFalse(r["lifetime_capped"])
        self.assertEqual(r["verdict"], "健康")

    def test_case_b(self):
        r = unit_econ.unit_economics(1500, 0.80, 0.03, 12000)
        self.assertAlmostEqual(r["monthly_gross_profit"], 1200)
        self.assertAlmostEqual(r["ltv"], 40000, places=6)
        self.assertAlmostEqual(r["ltv_cac"], 3.33, places=2)
        self.assertAlmostEqual(r["payback_months"], 10)
        self.assertEqual(r["verdict"], "健康")

    def test_lifetime_cap_and_zero_churn(self):
        self.assertEqual(unit_econ.expected_lifetime(0.02, 36), (36, True))    # 1/0.02 = 50 > 36
        self.assertEqual(unit_econ.expected_lifetime(0.0, 36), (36, True))     # churn 0 → 上限
        life, capped = unit_econ.expected_lifetime(0.05, 36)                   # 20 < 36
        self.assertAlmostEqual(life, 20)
        self.assertFalse(capped)
        life, capped = unit_econ.expected_lifetime(0.25, 4)                    # 剛好等於上限，不算截斷
        self.assertAlmostEqual(life, 4)
        self.assertFalse(capped)
        self.assertEqual(unit_econ.expected_lifetime(1.0, 36), (1.0, False))   # 100% 流失 → 1 個月

    def test_verdict_boundaries(self):
        self.assertEqual(unit_econ.verdict(0.99), "虧損")
        self.assertEqual(unit_econ.verdict(1.0), "偏低")
        self.assertEqual(unit_econ.verdict(2.99), "偏低")
        self.assertEqual(unit_econ.verdict(3.0), "健康")
        # 100 × 0.5 × 6 月 = 300；CAC 100 → 剛好 3
        self.assertEqual(unit_econ.unit_economics(100, 0.5, 1 / 6, 100)["verdict"], "健康")

    def test_zero_margin_has_no_payback(self):
        r = unit_econ.unit_economics(100, 0.0, 0.1, 500)
        self.assertEqual(r["ltv"], 0)
        self.assertIsNone(r["payback_months"])
        self.assertEqual(r["verdict"], "虧損")

    def test_crossed_thresholds(self):
        self.assertEqual(unit_econ.crossed_thresholds(3.8, 1.9), [3.0])
        self.assertEqual(unit_econ.crossed_thresholds(3.8, 0.5), [1.0, 3.0])
        self.assertEqual(unit_econ.crossed_thresholds(0.8, 1.6), [1.0])
        self.assertEqual(unit_econ.crossed_thresholds(3.8, 7.6), [])

    def test_sensitivity_case_a(self):
        # 流失率×0.5 → 3% → 壽命 33.33 → LTV 9148.33 → 7.6236；回收期不變 4.3724
        # 流失率×2   → 12% → 壽命 8.33 → LTV 2287.08 → 1.9059 → 跌破 3
        # CAC×0.5    → 600 → 7.6236；回收期 2.1862
        # CAC×2      → 2400 → 1.9059 → 跌破 3；回收期 8.7448
        # 毛利率−10  → 45% → 224.55 × 16.6667 = 3742.5 → 3.1188；回收期 5.3440
        # 毛利率+10  → 65% → 324.35 × 16.6667 = 5405.83 → 4.5049；回收期 3.6997
        s = {x["variant"]: x for x in unit_econ.sensitivity(499, 0.55, 0.06, 1200, 36)}
        self.assertEqual(list(s), ["流失率×0.5", "流失率×2", "CAC×0.5", "CAC×2",
                                   "毛利率−10 個百分點", "毛利率+10 個百分點"])
        self.assertAlmostEqual(s["流失率×0.5"]["ltv_cac"], 7.6236, places=4)
        self.assertAlmostEqual(s["流失率×0.5"]["payback_months"], 4.3724, places=4)
        self.assertAlmostEqual(s["流失率×2"]["ltv_cac"], 1.9059, places=4)
        self.assertEqual(s["流失率×2"]["crosses"], [3.0])
        self.assertAlmostEqual(s["CAC×0.5"]["payback_months"], 2.1862, places=4)
        self.assertAlmostEqual(s["CAC×2"]["ltv_cac"], 1.9059, places=4)
        self.assertAlmostEqual(s["CAC×2"]["payback_months"], 8.7448, places=4)
        self.assertTrue(s["CAC×2"]["changes_conclusion"])
        self.assertAlmostEqual(s["毛利率−10 個百分點"]["ltv_cac"], 3.1188, places=4)
        self.assertFalse(s["毛利率−10 個百分點"]["changes_conclusion"])
        self.assertAlmostEqual(s["毛利率+10 個百分點"]["ltv_cac"], 4.5049, places=4)
        self.assertEqual([k for k, v in s.items() if v["changes_conclusion"]], ["流失率×2", "CAC×2"])

    def test_sensitivity_clamps(self):
        # 毛利率 5% − 10pp → 夾在 0%；95% + 10pp → 夾在 100%；流失率 60% × 2 → 夾在 100%
        low = {x["variant"]: x for x in unit_econ.sensitivity(100, 0.05, 0.6, 50, 36)}
        self.assertEqual(low["毛利率−10 個百分點"]["value"], 0)
        self.assertIsNone(low["毛利率−10 個百分點"]["payback_months"])
        self.assertEqual(low["流失率×2"]["value"], 1)
        high = {x["variant"]: x for x in unit_econ.sensitivity(100, 0.95, 0.1, 50, 36)}
        self.assertEqual(high["毛利率+10 個百分點"]["value"], 1)

    def test_sensitivity_case_b_cap(self):
        # 流失率×0.5 → 1.5% → 66.67 月 > 36 → 截斷；LTV = 1200 × 36 = 43200 → 3.6
        s = {x["variant"]: x for x in unit_econ.sensitivity(1500, 0.8, 0.03, 12000, 36)}
        self.assertTrue(s["流失率×0.5"]["lifetime_capped"])
        self.assertAlmostEqual(s["流失率×0.5"]["ltv_cac"], 3.6, places=4)
        # 流失率×2 → 6% → 16.67 月 → LTV 20000 → 1.6667 → 跌破 3
        self.assertEqual(s["流失率×2"]["crosses"], [3.0])
        # 毛利率−10 → 70% → 1050 × 33.33 = 35000 → 2.9167 → 跌破 3
        self.assertEqual(s["毛利率−10 個百分點"]["crosses"], [3.0])


class TestRunArgsMode(unittest.TestCase):
    def test_case_a_json_structure(self):
        res = run_json(CASE_A + ["--label", "個人訂閱"])
        self.assertEqual(set(res), {"formulas", "rules_of_thumb", "model_limits", "segments",
                                    "warnings", "interpretation"})
        self.assertEqual(len(res["segments"]), 1)
        x = res["segments"][0]
        self.assertEqual(x["segment"], "個人訂閱")
        self.assertEqual(x["monthly_gross_profit"], 274.45)
        self.assertEqual(x["lifetime_months"], 16.6667)
        self.assertEqual(x["ltv"], 4574.1667)
        self.assertEqual(x["ltv_cac"], 3.8118)
        self.assertEqual(x["payback_months"], 4.3724)
        self.assertEqual(x["max_months"], 36)
        self.assertEqual(x["verdict"], "健康")
        self.assertTrue(x["sensitive"])
        self.assertEqual(len(x["sensitivity"]), 6)
        self.assertEqual(x["flags"], [])
        self.assertEqual(res["warnings"], [])
        self.assertIn("經驗值，依產業而異", res["rules_of_thumb"])
        self.assertTrue(any("這幾個估值要先查證" in o for o in res["interpretation"]))

    def test_case_b(self):
        x = run_json(CASE_B)["segments"][0]
        self.assertEqual(x["ltv"], 40000)
        self.assertEqual(x["ltv_cac"], 3.3333)
        self.assertEqual(x["payback_months"], 10)
        self.assertEqual(x["segment"], "")

    def test_zero_churn_noted(self):
        res = run_json(["--arpu", "100", "--margin", "50", "--churn", "0", "--cac", "600", "--max-months", "24"])
        x = res["segments"][0]
        self.assertEqual(x["lifetime_months"], 24)
        self.assertTrue(x["lifetime_capped"])
        self.assertEqual(x["ltv"], 1200)       # 50 × 24
        self.assertEqual(x["ltv_cac"], 2)
        self.assertEqual(x["verdict"], "偏低")
        self.assertTrue(any("月流失率為 0" in f for f in x["flags"]))

    def test_cap_and_payback_flags(self):
        # 每月毛利 100；churn 1% → 100 月 → 截斷 36；LTV 3600；CAC 1800 → 2.0；回收期 18 月 > 12
        res = run_json(["--arpu", "200", "--margin", "50%", "--churn", "1%", "--cac", "1800"])
        x = res["segments"][0]
        self.assertEqual(x["ltv"], 3600)
        self.assertEqual(x["payback_months"], 18)
        flags = "\n".join(x["flags"])
        self.assertIn("被上限截斷", flags)
        self.assertIn("現金壓力", flags)
        self.assertIn("經驗值", flags)

    def test_loss_verdict(self):
        # 每月毛利 50；壽命 5 月；LTV 250；CAC 500 → 0.5
        x = run_json(["--arpu", "100", "--margin", "50", "--churn", "20", "--cac", "500"])["segments"][0]
        self.assertEqual(x["ltv_cac"], 0.5)
        self.assertEqual(x["verdict"], "虧損")
        s = {v["variant"]: v for v in x["sensitivity"]}
        self.assertEqual(s["CAC×0.5"]["crosses"], [1.0])   # 0.5 → 1.0 站上 1

    def test_decimal_churn_warns_about_ambiguity(self):
        res = run_json(["--arpu", "100", "--margin", "50%", "--churn", "0.5", "--cac", "100"])
        self.assertEqual(res["segments"][0]["churn"], 0.5)
        self.assertTrue(any("視為小數" in w for w in res["warnings"]))
        self.assertEqual(run_json(CASE_A)["warnings"], [])
        # 0.06 → 6% 是合理讀法，不警告；「1」→ 100% 要警告
        self.assertEqual(run_json(["--arpu", "100", "--margin", "0.5", "--churn", "0.06", "--cac", "100"])["warnings"], [])
        res = run_json(["--arpu", "100", "--margin", "50%", "--churn", "1", "--cac", "100"])
        self.assertEqual(res["segments"][0]["lifetime_months"], 1)
        self.assertTrue(any("請寫成「1%」" in w for w in res["warnings"]))

    def test_markdown_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            unit_econ.run(CASE_A)
        md = buf.getvalue()
        for fragment in ("# 單位經濟計算結果", "## 公式", "LTV = 每月毛利 × 預期壽命", "回收期（月）= 獲客成本 ÷ 每月毛利",
                         "274.45", "16.67", "4,574.17", "3.81", "4.37", "## 敏感度檢查", "**1.91**",
                         "這個估值要先查證", "經驗值，依產業而異", "## 解讀"):
            self.assertIn(fragment, md)


class TestCsvMode(unittest.TestCase):
    def test_example_file(self):
        res = run_json([str(EXAMPLES / "unit_econ.csv")])
        segs = res["segments"]
        self.assertEqual([x["segment"] for x in segs], ["個人訂閱", "企業方案", "學生方案"])
        self.assertEqual(segs[0]["ltv_cac"], 3.8118)
        self.assertEqual(segs[1]["ltv"], 40000)
        # 學生方案：249 × 0.5 = 124.5；壽命 8.3333；LTV 1037.5；÷ 900 = 1.1528；回收期 7.2289
        self.assertEqual(segs[2]["ltv"], 1037.5)
        self.assertEqual(segs[2]["ltv_cac"], 1.1528)
        self.assertEqual(segs[2]["verdict"], "偏低")
        self.assertEqual(res["warnings"], [])
        self.assertTrue(any(o.startswith("客群比較") for o in res["interpretation"]))

    def test_english_headers_no_bom(self):
        p = write_csv("Segment,ARPU,Margin,Churn,CAC,Max_Months\nA,499,0.55,0.06,1200,\nB,200,50,1%,1800,48\n",
                      bom=False)
        try:
            res = run_json([p, "--max-months", "24"])
            a, b = res["segments"]
            self.assertEqual(a["ltv_cac"], 3.8118)
            self.assertEqual(a["max_months"], 24)     # 留空 → 用 --max-months
            self.assertEqual(b["max_months"], 48)     # 列內指定優先
            self.assertEqual(b["lifetime_months"], 48)  # churn 1% → 100 月 → 截斷 48
        finally:
            os.remove(p)

    def test_chinese_headers_with_parens_and_bom(self):
        p = write_csv("客群,月營收（元）,毛利率(%),月流失率,獲客成本,壽命上限（月）,依據\n甲,499,55,6%,1200,,後台報表\n")
        try:
            res = run_json([p])
            self.assertEqual(res["segments"][0]["ltv_cac"], 3.8118)
            self.assertEqual(res["segments"][0]["note"], "後台報表")
        finally:
            os.remove(p)

    def test_unused_column_and_duplicate_names_warn(self):
        p = write_csv("客群,月營收,毛利率,月流失率,獲客成本,通路\n甲,499,55%,6%,1200,x\n甲,499,55%,6%,1200,y\n")
        try:
            w = "\n".join(run_json([p])["warnings"])
            self.assertIn("以下欄位未使用", w)
            self.assertIn("通路", w)
            self.assertIn("客群名稱重複", w)
        finally:
            os.remove(p)

    def test_markdown_has_per_segment_tables(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            unit_econ.run([str(EXAMPLES / "unit_econ.csv")])
        md = buf.getvalue()
        self.assertIn("### 個人訂閱", md)
        self.assertIn("### 企業方案", md)
        self.assertIn("| 企業方案 | 1,500 | 80% | 3% | 12,000 | 1,200 | 33.33 | 40,000 | 3.33 | 10 | 健康 |", md)


class TestCliErrors(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "unit_econ.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def assertCleanError(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_success_exit_code(self):
        proc = self._cli(*CASE_A)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("## 解讀", proc.stdout)
        proc = self._cli(str(EXAMPLES / "unit_econ.csv"), "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(len(json.loads(proc.stdout)["segments"]), 3)

    def test_no_input(self):
        self.assertCleanError(self._cli(), "請提供 CSV 檔路徑")

    def test_missing_args(self):
        proc = self._cli("--arpu", "499", "--margin", "55%")
        self.assertCleanError(proc, "參數模式缺少：--churn、--cac")

    def test_both_modes(self):
        proc = self._cli(str(EXAMPLES / "unit_econ.csv"), "--arpu", "499")
        self.assertCleanError(proc, "請擇一")

    def test_missing_file(self):
        self.assertCleanError(self._cli("no_such.csv"), "找不到檔案")

    def test_bad_arg_values_all_reported(self):
        proc = self._cli("--arpu", "abc", "--margin", "150", "--churn", "-3%", "--cac", "0")
        self.assertCleanError(proc, "月營收（ARPU）「abc」不是數字")
        self.assertIn("毛利率「150」無法解讀", proc.stderr)
        self.assertIn("月流失率「-3%」無法解讀", proc.stderr)
        self.assertIn("獲客成本（CAC）必須大於 0", proc.stderr)

    def test_bad_max_months(self):
        self.assertCleanError(self._cli(*CASE_A, "--max-months", "0"), "壽命上限必須大於 0")
        self.assertCleanError(self._cli(*CASE_A, "--max-months", "abc"), "不是數字")

    def test_csv_missing_column(self):
        p = write_csv("客群,月營收,毛利率,月流失率\n甲,499,55%,6%\n")
        try:
            self.assertCleanError(self._cli(p), "缺少必要欄位")
        finally:
            os.remove(p)

    def test_csv_bad_rows_all_reported(self):
        p = write_csv("客群,月營收,毛利率,月流失率,獲客成本,壽命上限\n"
                      "甲,abc,55%,6%,1200,\n乙,499,,6%,1200,-1\n,499,55%,6%,1200,\n")
        try:
            proc = self._cli(p)
            self.assertCleanError(proc, "第 2 列「甲」：月營收（ARPU）「abc」不是數字")
            self.assertIn("第 3 列「乙」：缺少毛利率", proc.stderr)
            self.assertIn("壽命上限「-1」必須是大於 0 的月數", proc.stderr)
            self.assertIn("第 4 列：客群名稱是空的", proc.stderr)
        finally:
            os.remove(p)

    def test_non_utf8(self):
        fd, p = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "wb") as f:
            f.write("客群,月營收,毛利率,月流失率,獲客成本\n甲,499,55,6,1200\n".encode("cp950"))
        try:
            self.assertCleanError(self._cli(p), "不是 UTF-8")
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
