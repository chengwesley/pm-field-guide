"""ab_test.py 的單元測試。

執行（在 pm-field-guide 資料夾）：python -X utf8 -m unittest discover -s scripts/tests
"""

import contextlib
import io
import json
import math
import os
import sys
import unittest
from statistics import NormalDist

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
FIX = os.path.join(HERE, "fixtures")

import ab_test  # noqa: E402


def run(argv):
    """執行 CLI，回傳 (exit code, stdout, stderr)。"""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = ab_test.main(argv)
        except SystemExit as e:  # argparse 的錯誤
            code = e.code
    return code, out.getvalue(), err.getvalue()


class TestSampleSize(unittest.TestCase):
    def test_baseline10_abs2pp(self):
        # 參考值：R `power.prop.test(p1=0.10, p2=0.12, power=0.8)` → n = 3840.847（每組）。
        # 手算：p̄=0.11；z.975=1.959964，z.80=0.841621
        #   [1.959964*sqrt(2*0.11*0.89) + 0.841621*sqrt(0.09+0.1056)]² / 0.02² = 3840.8
        n = ab_test.sample_size_per_group(0.10, 0.12, 0.05, 0.8)
        self.assertAlmostEqual(n, 3840.85, delta=0.5)
        self.assertTrue(3800 <= math.ceil(n) <= 3900)
        code, out, _ = run(["size", "--baseline", "10%", "--mde", "0.02", "--mde-type", "abs", "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["n_per_group"], 3841)

    def test_evan_miller_difference_is_formula_choice(self):
        # Evan Miller 計算機約 3,623：其 H0 項用 sqrt(2*p1*q1)（只用基準組變異數）。
        # 這裡用同樣假設獨立重算，證明差異來自公式選擇而非錯誤。
        za, zb = NormalDist().inv_cdf(0.975), NormalDist().inv_cdf(0.8)
        alt = (za * math.sqrt(2 * 0.1 * 0.9) + zb * math.sqrt(0.09 + 0.12 * 0.88)) ** 2 / 0.02 ** 2
        self.assertEqual(math.ceil(alt), 3623)
        self.assertGreater(ab_test.sample_size_per_group(0.10, 0.12, 0.05, 0.8), alt)

    def test_r_documentation_example(self):
        # R 說明文件範例：power.prop.test(p1 = .50, p2 = .75, power = .90) → n = 76.7
        n = ab_test.sample_size_per_group(0.50, 0.75, 0.05, 0.9)
        self.assertAlmostEqual(n, 76.65, delta=0.1)

    def test_relative_mde_equals_absolute(self):
        # 12% 相對提升 10% = 13.2%，等同絕對 +1.2pp
        _, o1, _ = run(["size", "--baseline", "0.12", "--mde", "10%", "--json"])
        _, o2, _ = run(["size", "--baseline", "0.12", "--mde", "0.012", "--mde-type", "abs", "--json"])
        self.assertEqual(json.loads(o1)["n_per_group"], json.loads(o2)["n_per_group"])

    def test_bonferroni_and_days(self):
        code, out, _ = run(["size", "--baseline", "10%", "--mde", "0.02", "--mde-type", "abs",
                            "--variants", "3", "--daily-traffic", "1000", "--json"])
        r = json.loads(out)
        self.assertEqual(code, 0)
        self.assertTrue(r["bonferroni"])
        self.assertAlmostEqual(r["alpha_adjusted"], 0.025)
        # 與直接用 α=0.025 算的結果一致
        self.assertEqual(r["n_per_group"], math.ceil(ab_test.sample_size_per_group(0.10, 0.12, 0.025, 0.8)))
        self.assertEqual(r["days"], math.ceil(r["n_per_group"] * 3 / 1000))
        _, md, _ = run(["size", "--baseline", "10%", "--mde", "0.02", "--mde-type", "abs", "--variants", "3"])
        self.assertIn("Bonferroni", md)

    def test_short_test_reminds_full_week(self):
        _, md, _ = run(["size", "--baseline", "10%", "--mde", "0.02", "--mde-type", "abs", "--daily-traffic", "100000"])
        self.assertIn("1 天", md)
        self.assertIn("至少跑滿一整週", md)

    def test_invalid_inputs_exit_2(self):
        cases = [
            ["size", "--baseline", "12", "--mde", "10%"],        # 12 不明確
            ["size", "--baseline", "abc", "--mde", "10%"],
            ["size", "--baseline", "0.95", "--mde", "0.1", "--mde-type", "abs"],  # 超過 100%
            ["size", "--baseline", "0.1", "--mde", "0"],
            ["size", "--baseline", "0.1", "--mde", "0.1", "--variants", "1"],
            ["size", "--baseline", "0.1", "--mde", "0.1", "--daily-traffic", "-5"],
            ["size", "--baseline", "0.1"],                       # 缺 --mde（argparse）
            ["size", "--baseline", "0.1", "--mde", "0.1", "--mde-type", "x"],
        ]
        for argv in cases:
            code, _, err = run(argv)
            self.assertEqual(code, 2, argv)
            self.assertNotIn("Traceback", err)
            self.assertTrue(any("一" <= ch <= "鿿" for ch in err), err)  # 錯誤訊息含中文


class TestChiSquare(unittest.TestCase):
    def test_table_critical_values(self):
        # 標準卡方分配臨界值表（如 NIST/SEMATECH e-Handbook 1.3.6.7.4）
        cases = [(3.841459, 1, 0.05), (6.634897, 1, 0.01), (10.827566, 1, 0.001),
                 (5.991465, 2, 0.05), (9.487729, 4, 0.05), (18.307038, 10, 0.05),
                 (43.772972, 30, 0.05)]
        for x, df, p in cases:
            self.assertAlmostEqual(ab_test.chi2_sf(x, df), p, delta=p * 1e-4, msg=(x, df))

    def test_closed_forms(self):
        # df=2：右尾 = exp(-x/2)；df=1：右尾 = erfc(sqrt(x/2))
        for x in (0.1, 1.0, 4.0, 15.0, 60.0):
            self.assertAlmostEqual(ab_test.chi2_sf(x, 2), math.exp(-x / 2), places=12)
            self.assertAlmostEqual(ab_test.chi2_sf(x, 1), math.erfc(math.sqrt(x / 2)), places=12)
        self.assertEqual(ab_test.chi2_sf(0, 3), 1.0)
        self.assertAlmostEqual(ab_test.chi2_cdf(3.841459, 1), 0.95, places=6)


class TestAnalyze(unittest.TestCase):
    def test_two_group_z_test(self):
        # 對照 1000/10000、實驗 1100/10000。手算：
        #   合併 p=0.105，SE=sqrt(0.105*0.895*(2/10000))=0.0043353，z=0.01/SE=2.3066
        #   p 值 = erfc(z/√2) = 0.02108（雙尾）
        #   未合併 SE=sqrt(0.09/1e4 + 0.0979/1e4)=0.0043347，95% CI = 0.01 ± 1.959964*SE
        code, out, _ = run(["analyze", os.path.join(FIX, "ab_results.csv"), "--json"])
        self.assertEqual(code, 0)
        r = json.loads(out)
        b = r["overall"]["groups"][1]
        z = 0.01 / math.sqrt(0.105 * 0.895 * 2 / 10000)
        self.assertAlmostEqual(b["z"], z, places=9)
        self.assertAlmostEqual(b["p_value"], math.erfc(z / math.sqrt(2)), places=9)
        self.assertAlmostEqual(b["p_value"], 0.02108, delta=0.0001)
        se = math.sqrt(0.09 / 1e4 + 0.11 * 0.89 / 1e4)
        self.assertAlmostEqual(b["ci_low"], 0.01 - 1.959964 * se, places=6)
        self.assertAlmostEqual(b["ci_high"], 0.01 + 1.959964 * se, places=6)
        self.assertAlmostEqual(b["rel_lift"], 0.10, places=12)
        self.assertTrue(b["significant"])
        self.assertEqual(r["overall"]["control"], "對照")
        self.assertFalse(r["srm"]["mismatch"])

    def test_srm_flag(self):
        # 10000 vs 10600，預期各 10300：卡方 = 2*300²/10300 = 17.476，df=1，p = erfc(sqrt(17.476/2)) ≈ 2.9e-5
        code, out, _ = run(["analyze", os.path.join(FIX, "ab_srm.csv"), "--json"])
        r = json.loads(out)
        self.assertAlmostEqual(r["srm"]["chi2"], 2 * 300 ** 2 / 10300, places=9)
        self.assertAlmostEqual(r["srm"]["p_value"], math.erfc(math.sqrt(r["srm"]["chi2"] / 2)), places=12)
        self.assertTrue(r["srm"]["mismatch"])
        _, md, _ = run(["analyze", os.path.join(FIX, "ab_srm.csv")])
        self.assertIn("樣本比例失衡，先查分流再看結果", md)
        # 若預期分流本來就是 10000:10600，則不應示警
        _, out2, _ = run(["analyze", os.path.join(FIX, "ab_srm.csv"), "--expected-split", "100,106", "--json"])
        self.assertFalse(json.loads(out2)["srm"]["mismatch"])

    def test_segments_and_peeking(self):
        code, md, _ = run(["analyze", os.path.join(FIX, "ab_segments.csv"), "--planned-n", "20000"])
        self.assertEqual(code, 0)
        self.assertIn("分群：桌機", md)
        self.assertIn("只能當作假設", md)
        self.assertIn("peeking", md)
        _, out, _ = run(["analyze", os.path.join(FIX, "ab_segments.csv"), "--json"])
        r = json.loads(out)
        # 整體 = 各分群加總：control 8000/740、B 8000/815
        g = r["overall"]["groups"]
        self.assertEqual((g[0]["visitors"], g[0]["conversions"]), (8000, 740))
        self.assertEqual((g[1]["visitors"], g[1]["conversions"]), (8000, 815))
        self.assertEqual(len(r["segments"]), 2)

    def test_bonferroni_three_groups(self):
        import tempfile
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("group,visitors,conversions\nA,1000,100\ncontrol,1000,100\nC,1000,130\n")
            path = f.name
        try:
            _, out, _ = run(["analyze", path, "--json"])
            r = json.loads(out)
            self.assertEqual(r["overall"]["control"], "control")  # 以名稱判斷，不是第一列
            self.assertAlmostEqual(r["overall"]["threshold"], 0.025)
            self.assertTrue(r["bonferroni"])
        finally:
            os.remove(path)

    def test_bad_csv_exit_2(self):
        for argv in (["analyze", os.path.join(FIX, "ab_bad.csv")],
                     ["analyze", os.path.join(FIX, "does_not_exist.csv")],
                     ["analyze", os.path.join(FIX, "ab_results.csv"), "--expected-split", "50,30,20"]):
            code, _, err = run(argv)
            self.assertEqual(code, 2, argv)
            self.assertNotIn("Traceback", err)


if __name__ == "__main__":
    unittest.main()
