"""market_size.py 測試。執行：在 pm-field-guide 資料夾下 `python -X utf8 -m unittest discover -s scripts/tests`。"""
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

import market_size as ms  # noqa: E402


def write_csv(text: str, bom: bool = True) -> str:
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        f.write(text)
    return path


def run_json(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        ms.run(argv + ["--json"])
    return json.loads(buf.getvalue())


# 手算基準（規格的驗算案例）：
#   TAM = 5000 × 12000            = 60,000,000
#   SAM = 60,000,000 × 60%        = 36,000,000（3000 家）
#   SOM = 36,000,000 × 5%         =  1,800,000（150 家）
#   滲透率 ×2 且年單價 ×2 → 1,800,000 × 4 = 7,200,000
#   目標 3,600,000 ÷ SAM 36,000,000 = 10%
BASE = ["--accounts", "5000", "--price", "12000", "--serviceable", "60%", "--penetration", "5%"]


class TestPureFunctions(unittest.TestCase):
    def test_ratio_formats(self):
        self.assertAlmostEqual(ms.parse_ratio("60"), 0.6)
        self.assertAlmostEqual(ms.parse_ratio("60%"), 0.6)
        self.assertAlmostEqual(ms.parse_ratio("0.6"), 0.6)
        self.assertAlmostEqual(ms.parse_ratio("100％"), 1.0)  # 全形百分號
        self.assertAlmostEqual(ms.parse_ratio("0.5%"), 0.005)
        self.assertAlmostEqual(ms.parse_ratio("0"), 0.0)
        for bad in ("150", "150%", "-5", "-5%", "abc", ""):
            with self.assertRaises(ValueError, msg=bad):
                ms.parse_ratio(bad)

    def test_market_size_reference_case(self):
        m = ms.market_size(5000, 12000, 0.6, 0.05)
        self.assertAlmostEqual(m["tam"], 60_000_000)
        self.assertAlmostEqual(m["sam"], 36_000_000)
        self.assertAlmostEqual(m["som"], 1_800_000)
        self.assertAlmostEqual(m["sam_accounts"], 3000)
        self.assertAlmostEqual(m["som_accounts"], 150)

    def test_required_penetration(self):
        self.assertAlmostEqual(ms.required_penetration(3_600_000, 36_000_000), 0.10)
        self.assertIsNone(ms.required_penetration(100, 0))

    def test_total_som_caps_penetration(self):
        seg = [{"accounts": 100, "price": 10, "serviceable": 1.0, "penetration": 0.6}]
        v, capped = ms.total_som(seg, 2.0, 1.0)   # 60% × 2 → 夾在 100%
        self.assertAlmostEqual(v, 1000)
        self.assertTrue(capped)
        v, capped = ms.total_som(seg, 0.5, 2.0)   # 100 × 20 × 30%
        self.assertAlmostEqual(v, 600)
        self.assertFalse(capped)


class TestSingleSegment(unittest.TestCase):
    def test_reference_case(self):
        res = run_json(BASE)
        seg = res["segments"][0]
        self.assertEqual((seg["tam"], seg["sam"], seg["som"]), (60_000_000, 36_000_000, 1_800_000))
        self.assertEqual((seg["sam_accounts"], seg["som_accounts"]), (3000, 150))
        tot = res["total"]
        self.assertEqual((tot["tam"], tot["sam"], tot["som"]), (60_000_000, 36_000_000, 1_800_000))
        self.assertAlmostEqual(tot["monthly_new_accounts"], 150 / 36, places=3)
        self.assertEqual(res["warnings"], [])
        self.assertIsNone(res["target"])

    def test_three_ratio_spellings_agree(self):
        a = run_json(BASE)["total"]
        b = run_json(["--accounts", "5000", "--price", "12000", "--serviceable", "60", "--penetration", "5"])["total"]
        c = run_json(["--accounts", "5,000", "--price", "12,000", "--serviceable", "0.6",
                      "--penetration", "0.05"])["total"]
        self.assertEqual(a, b)
        self.assertEqual(a, c)

    def test_sensitivity_grid(self):
        s = run_json(BASE)["sensitivity"]
        self.assertEqual(s["penetration_factors"], [0.5, 1, 2])
        self.assertEqual(s["price_factors"], [0.5, 1, 2])
        self.assertEqual(s["som"], [
            [450_000, 900_000, 1_800_000],
            [900_000, 1_800_000, 3_600_000],
            [1_800_000, 3_600_000, 7_200_000],
        ])
        self.assertEqual(s["som"][2][2], 7_200_000)  # 滲透率 ×2 且年單價 ×2
        self.assertFalse(any(any(r) for r in s["capped"]))

    def test_sensitivity_capped_at_100(self):
        res = run_json(["--accounts", "100", "--price", "10", "--serviceable", "100%", "--penetration", "60%"])
        s = res["sensitivity"]
        self.assertEqual(s["som"][2], [500, 1000, 2000])  # 滲透率夾在 100%
        self.assertEqual(s["capped"][2], [True, True, True])
        self.assertEqual(s["capped"][1], [False, False, False])

    def test_target(self):
        t = run_json(BASE + ["--target", "3600000"])["target"]
        self.assertAlmostEqual(t["required_penetration"], 0.10)
        self.assertTrue(t["reachable"])
        self.assertAlmostEqual(t["multiple_of_current"], 2)

    def test_target_unreachable(self):
        res = run_json(BASE + ["--target", "40000000"])
        self.assertFalse(res["target"]["reachable"])
        self.assertGreater(res["target"]["required_penetration"], 1)
        self.assertTrue(any("達不到" in o for o in res["interpretation"]))

    def test_warnings_are_reminders(self):
        res = run_json(["--accounts", "100", "--price", "10", "--serviceable", "100%", "--penetration", "31%"])
        w = "\n".join(res["warnings"])
        self.assertIn("很激進", w)
        self.assertIn("不是定律", w)
        self.assertIn("可服務比例為 100%", w)
        self.assertIn("地區、語言、產業、規模", w)
        # 剛好 30% 不算 > 30%
        res = run_json(["--accounts", "100", "--price", "10", "--serviceable", "50%", "--penetration", "30%"])
        self.assertEqual(res["warnings"], [])

    def test_bare_one_is_flagged(self):
        res = run_json(["--accounts", "100", "--price", "10", "--serviceable", "50", "--penetration", "1"])
        self.assertEqual(res["segments"][0]["penetration"], 1)
        self.assertTrue(any("已解讀為 100%" in w for w in res["warnings"]))

    def test_key_assumption(self):
        # 可服務比例 60% ×2 會被夾在 100%，擺幅較小；其餘三者擺幅相同 → 依順序先查滲透率。
        ka = run_json(BASE)["key_assumption"]
        self.assertEqual(ka["field"], "penetration")
        self.assertEqual((ka["som_at_half"], ka["som_at_double"]), (900_000, 3_600_000))
        # 滲透率 80% ×2 被夾住（擺幅變小），可服務比例 10% 沒被夾 → 改指向可服務比例。
        ka = run_json(["--accounts", "100", "--price", "10", "--serviceable", "10%",
                       "--penetration", "80%"])["key_assumption"]
        self.assertEqual(ka["field"], "serviceable")

    def test_json_structure_and_labels(self):
        res = run_json(BASE + ["--label", "獨立診所", "--unit", "人", "--years", "2"])
        for key in ("disclaimer", "formulas", "unit", "years", "segments", "total", "sensitivity",
                    "target", "key_assumption", "warnings", "interpretation"):
            self.assertIn(key, res)
        self.assertEqual(res["segments"][0]["segment"], "獨立診所")
        self.assertEqual((res["unit"], res["years"]), ("人", 2))
        self.assertAlmostEqual(res["total"]["monthly_new_accounts"], 6.25)
        self.assertIn("腳本只做乘法", res["disclaimer"])
        self.assertNotIn("source", res["segments"][0])


class TestCsv(unittest.TestCase):
    def test_example_file(self):
        # 西醫 1,800,000；牙醫 3000×18000×70%×8% = 3,024,000；中醫 2000×9000×50%×4% = 360,000
        res = run_json([str(EXAMPLES / "market_size.csv")])
        self.assertEqual([s["som"] for s in res["segments"]], [1_800_000, 3_024_000, 360_000])
        first = res["segments"][0]
        self.assertEqual((first["tam"], first["sam"], first["sam_accounts"], first["som_accounts"]),
                         (60_000_000, 36_000_000, 3000, 150))
        tot = res["total"]
        self.assertEqual(tot["tam"], 60_000_000 + 54_000_000 + 18_000_000)
        self.assertEqual(tot["sam"], 36_000_000 + 37_800_000 + 9_000_000)
        self.assertEqual(tot["som"], 5_184_000)
        self.assertEqual(tot["som_accounts"], 150 + 168 + 40)
        self.assertEqual([s["source_status"] for s in res["segments"]], ["已填", "來源待查證", "已填"])
        self.assertTrue(any("來源待查證" in w and "牙醫診所" in w for w in res["warnings"]))
        self.assertEqual(res["key_assumption"]["segment"], "牙醫診所")

    def test_english_headers_no_bom(self):
        p = write_csv("Segment,Accounts,Price,Serviceable,Penetration,Source\nA,5000,12000,0.6,0.05,統計\n", bom=False)
        try:
            res = run_json([p])
            self.assertEqual(res["total"]["som"], 1_800_000)
            self.assertEqual(res["warnings"], [])
        finally:
            os.remove(p)

    def test_chinese_aliases_with_parentheses(self):
        p = write_csv("客群,人數（人）,年營收（元）,可服務比例,滲透率\nA,5000,12000,60,5\n")
        try:
            res = run_json([p, "--unit", "人"])
            self.assertEqual(res["total"]["som"], 1_800_000)
            self.assertTrue(any("CSV 沒有來源欄" in w for w in res["warnings"]))
        finally:
            os.remove(p)

    def test_markdown_output(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ms.run([str(EXAMPLES / "market_size.csv"), "--target", "6000000"])
        md = buf.getvalue()
        for frag in ("# 市場規模試算（bottom-up）", "TAM = 目標客群數 × 年單價", "## 各客群", "## 合計",
                     "## 敏感度", "## 目標回推", "## 提醒", "## 解讀", "**來源待查證**",
                     "數字來自你提供的輸入，腳本只做乘法；每個輸入都要有來源", "最該先查證的假設"):
            self.assertIn(frag, md)

    def test_no_target_section_without_flag(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            ms.run(BASE)
        self.assertNotIn("目標回推", buf.getvalue())


class TestCliErrors(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "market_size.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def assertCleanError(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_cli_ok(self):
        proc = self._cli(*BASE, "--target", "3600000")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("1,800,000", proc.stdout)
        self.assertIn("7,200,000", proc.stdout)
        self.assertIn("需要滲透率 **10%**", proc.stdout)

    def test_missing_params(self):
        proc = self._cli("--accounts", "5000", "--price", "12000")
        self.assertCleanError(proc, "--serviceable")
        self.assertIn("--penetration", proc.stderr)

    def test_ratio_out_of_range(self):
        self.assertCleanError(
            self._cli("--accounts", "10", "--price", "10", "--serviceable", "150%", "--penetration", "5%"),
            "超過 100%")
        self.assertCleanError(
            self._cli("--accounts", "10", "--price", "10", "--serviceable", "50%", "--penetration=-5%"),
            "不能是負數")

    def test_bad_numbers(self):
        proc = self._cli("--accounts", "abc", "--price", "0", "--serviceable", "50%", "--penetration", "5%")
        self.assertCleanError(proc, "「abc」不是數字")
        self.assertIn("必須大於 0", proc.stderr)
        self.assertCleanError(self._cli(*BASE, "--target", "0"), "必須大於 0")
        self.assertCleanError(self._cli(*BASE, "--unit", "台"), "無效的選項")

    def test_csv_and_params_conflict(self):
        self.assertCleanError(self._cli(str(EXAMPLES / "market_size.csv"), "--accounts", "5"), "不能同時使用")

    def test_missing_file_and_column(self):
        self.assertCleanError(self._cli("no_such.csv"), "找不到檔案")
        p = write_csv("客群,家數,年單價,可服務比例\nA,1,1,50\n")
        try:
            self.assertCleanError(self._cli(p), "缺少必要欄位")
        finally:
            os.remove(p)

    def test_csv_bad_rows_all_reported(self):
        p = write_csv("客群,家數,年單價,可服務比例,滲透率\nA,abc,10,50,5\nB,10,10,120,5\nC,10,10,50,-3\n")
        try:
            proc = self._cli(p)
            self.assertCleanError(proc, "目標客群數「abc」不是數字")
            self.assertIn("可服務比例「120」無法解讀（超過 100%）", proc.stderr)
            self.assertIn("滲透率「-3」無法解讀（不能是負數）", proc.stderr)
        finally:
            os.remove(p)


if __name__ == "__main__":
    unittest.main()
