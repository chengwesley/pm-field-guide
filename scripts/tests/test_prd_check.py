"""prd_check.py 測試。執行：在 pm-field-guide 資料夾下 `python -X utf8 -m unittest discover -s scripts/tests`。"""
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
FIXTURES = Path(__file__).resolve().parent / "fixtures"
EXAMPLES = SCRIPTS.parent / "examples"
sys.path.insert(0, str(SCRIPTS))

import prd_check  # noqa: E402


def write_md(text: str, encoding: str = "utf-8") -> str:
    fd, path = tempfile.mkstemp(suffix=".md")
    with os.fdopen(fd, "wb") as f:
        f.write(text.encode(encoding))
    return path


def run_json(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        prd_check.run(argv + ["--json"])
    return json.loads(buf.getvalue())


def status(res):
    return {c["key"]: c["status"] for c in res["checks"]}


def analyze(text):
    return prd_check.analyze(text, "t.md")


ALL_KEYS = ["background", "goals", "non_goals", "scope", "requirements", "acceptance",
            "success_metric", "guardrail", "edge_cases", "open_questions", "changelog"]


class TestCompletePrd(unittest.TestCase):
    def test_all_pass(self):
        res = run_json([str(FIXTURES / "prd_complete.md")])
        self.assertEqual(list(status(res)), ALL_KEYS)
        self.assertEqual(set(status(res).values()), {"通過"})
        self.assertEqual(res["summary"], {"total": 11, "passed": 11, "partial": 0, "missing": 0, "advisory": 0})
        self.assertEqual(res["requirements"]["count"], 3)
        self.assertEqual(res["requirements"]["with_ac"], 3)
        self.assertEqual(res["requirements"]["without_ac"], [])
        self.assertEqual(res["issues"]["total"], 0)
        self.assertEqual(res["top_fixes"], [])
        self.assertEqual(res["exit_code"], 0)

    def test_evidence_has_line_numbers(self):
        res = run_json([str(FIXTURES / "prd_complete.md")])
        by = {c["key"]: c for c in res["checks"]}
        self.assertEqual(by["background"]["evidence"][0], {"line": 8, "text": "1. 背景與問題"})
        self.assertEqual(by["requirements"]["evidence"][0], {"line": 27, "text": "FR-01"})
        self.assertEqual(by["open_questions"]["evidence"][0]["line"], 54)

    def test_json_structure(self):
        res = run_json([str(FIXTURES / "prd_complete.md")])
        for k in ("file", "lines", "scope_note", "checks", "requirements", "issues",
                  "summary", "top_fixes", "strict", "exit_code"):
            self.assertIn(k, res)
        self.assertIn("不判斷內容寫得好不好", res["scope_note"])
        self.assertEqual(set(res["checks"][0]), {"key", "no", "name", "status", "evidence", "detail"})
        self.assertEqual(set(res["issues"]), {"total", "by_type", "items"})


class TestMissingPrd(unittest.TestCase):
    def setUp(self):
        self.res = run_json([str(FIXTURES / "prd_missing.md")])

    def test_missing_items(self):
        st = status(self.res)
        self.assertEqual(st["non_goals"], "缺少")
        self.assertEqual(st["acceptance"], "缺少")
        self.assertEqual([k for k, v in st.items() if v != "通過"], ["non_goals", "acceptance"])
        self.assertEqual(self.res["summary"]["missing"], 2)
        self.assertEqual(self.res["summary"]["passed"], 9)

    def test_requirements_without_ac(self):
        r = self.res["requirements"]
        self.assertEqual((r["count"], r["with_ac"]), (2, 0))
        self.assertEqual(r["without_ac"], ["FR-01", "FR-02"])

    def test_top_fixes_order(self):
        fixes = self.res["top_fixes"]
        self.assertEqual([f["rank"] for f in fixes], [1, 2])
        self.assertIn("補齊驗收條件", fixes[0]["item"])   # blocks RD/QA more than non-goals
        self.assertIn("FR-01", fixes[0]["item"])
        self.assertIn("補上非目標", fixes[1]["item"])


class TestEnglishPrd(unittest.TestCase):
    def test_english_headings_all_pass(self):
        res = run_json([str(FIXTURES / "prd_english.md")])
        self.assertEqual(set(status(res).values()), {"通過"}, status(res))
        self.assertEqual(res["requirements"]["ids"], ["US-01", "US-02"])
        self.assertEqual(res["requirements"]["with_ac"], 2)
        self.assertEqual(res["requirements"]["gwt_blocks"], 2)
        self.assertEqual(res["issues"]["total"], 0)


class TestStructureRules(unittest.TestCase):
    def test_goal_not_satisfied_by_non_goal_heading(self):
        st = status(analyze("## 非目標\n- 不做群發\n\n| 目標值 | 8% |\n|---|---|\n"))
        self.assertEqual(st["goals"], "缺少")
        self.assertEqual(st["non_goals"], "通過")

    def test_background_not_satisfied_by_open_questions(self):
        st = status(analyze("## 未決問題\n| 問題 | 負責人 | 期限 |\n|---|---|---|\n| A | 甲 | 3/1 |\n"))
        self.assertEqual(st["background"], "缺少")
        self.assertEqual(st["open_questions"], "通過")

    def test_non_goal_body_only_is_partial(self):
        st = status(analyze("## 範圍\n語音電話這版不做。\n"))
        self.assertEqual(st["non_goals"], "部分")
        self.assertEqual(st["scope"], "部分")  # scope heading without In / Out

    def test_scope_one_side_is_partial(self):
        res = analyze("| In | Later |\n|---|---|\n| A | B |\n")
        c = next(c for c in res["checks"] if c["key"] == "scope")
        self.assertEqual(c["status"], "部分")
        self.assertIn("沒有 Out", c["detail"])

    def test_requirement_heading_without_ids_is_partial(self):
        st = status(analyze("## 功能需求\n- 可以批次寄送\n"))
        self.assertEqual(st["requirements"], "部分")

    def test_ac_mapping_same_row_and_paragraph(self):
        text = (
            "## 需求\n"
            "| 編號 | 敘述 | 驗收 |\n|---|---|---|\n"
            "| FR-01 | 寄送 | AC-01 |\n"
            "| FR-02 | 結果頁 | |\n"
            "\n"
            "- REQ-3 匯出名單\n"
            "  - 假設已有 5 筆，當按下匯出，則下載 5 列的檔案\n"
            "- REQ-4 刪除名單\n"
            "\n"
            "### US-05 重寄\n"
            "說明文字。\n"
            "\n"
            "- Given 有 1 筆失敗\n- When 按下重寄\n- Then 該筆再寄 1 次\n"
        )
        res = analyze(text)
        self.assertEqual(res["requirements"]["ids"], ["FR-01", "FR-02", "REQ-3", "REQ-4", "US-05"])
        self.assertEqual(res["requirements"]["without_ac"], ["FR-02", "REQ-4"])
        c = next(c for c in res["checks"] if c["key"] == "acceptance")
        self.assertEqual(c["status"], "部分")
        self.assertIn("3／5", c["detail"])
        self.assertIn("FR-02、REQ-4", c["detail"])

    def test_metrics_reported_separately(self):
        st = status(analyze("## 成功指標\n主指標：爽約率，基準 12%，目標 8%，事件 no_show，觀察 8 週\n"))
        self.assertEqual(st["success_metric"], "通過")
        self.assertEqual(st["guardrail"], "缺少")
        res = analyze("## 成功指標\n| 類型 | 指標 | 基準值 | 目標值 |\n|---|---|---|---|\n| 主指標 | 爽約率 | 12% | 8% |\n| 護欄 | 退訂率 | 1% | 2% |\n")
        by = {c["key"]: c for c in res["checks"]}
        self.assertEqual(by["success_metric"]["status"], "部分")
        self.assertIn("量測方式、觀察期", by["success_metric"]["detail"])
        self.assertEqual(by["guardrail"]["status"], "通過")

    def test_edge_cases_three_kinds(self):
        res = analyze("## 異常路徑\n- 寄送失敗時顯示錯誤\n")
        c = next(c for c in res["checks"] if c["key"] == "edge_cases")
        self.assertEqual(c["status"], "部分")
        self.assertIn("無權限、取消", c["detail"])

    def test_open_questions_owner_and_date(self):
        st = status(analyze("## 未決事項\n- 簡訊費用誰出\n"))
        self.assertEqual(st["open_questions"], "部分")
        res = analyze("## Open questions\n| Q | Owner | Due |\n|---|---|---|\n| A | PM | 3/1 |\n| B | | ____ |\n")
        c = next(c for c in res["checks"] if c["key"] == "open_questions")
        self.assertEqual(c["status"], "部分")
        self.assertIn("2 條未決事項中有 1 條", c["detail"])

    def test_changelog_missing_is_advisory_only(self):
        res = analyze("## 背景\n內容\n")
        self.assertEqual(status(res)["changelog"], "建議")
        self.assertEqual(res["summary"]["advisory"], 1)
        self.assertEqual(res["summary"]["missing"], 9)

    def test_code_block_ignored(self):
        res = analyze("## 背景\n```\n## 非目標\nFR-01 TODO ____\n```\n")
        self.assertEqual(status(res)["non_goals"], "缺少")
        self.assertEqual(res["requirements"]["count"], 0)
        self.assertEqual(res["issues"]["total"], 0)


VAGUE = (
    "# PRD\n"                                        # 1
    "\n"                                             # 2
    "## 背景\n"                                      # 3
    "櫃檯希望可以快速完成提醒，流程要簡單。\n"       # 4  contextual words outside requirements: ignored
    "上線時間 TBD，細節之後補。\n"                   # 5
    "\n"                                             # 6
    "## 功能需求\n"                                  # 7
    "- FR-01 名單要能快速篩選，介面使用者友善\n"     # 8
    "- FR-02 匯出格式 ____，欄位 TODO\n"             # 9
    "- FR-03 密碼不正確時顯示「帳號或密碼錯誤」\n"   # 10 「不正確」 is not vague
    "\n"                                             # 11
    "## 目標\n"                                      # 12
    "- 降低爽約率\n"                                 # 13
    "- 爽約率由 12% 降低到 8%\n"                     # 14
    "- 提升回診率到 ____\n"                          # 15
    "- 支援簡訊、電子郵件 etc.\n"                    # 16
    "- 負責人 XXX\n"                                 # 17
)


class TestMechanicalIssues(unittest.TestCase):
    def setUp(self):
        self.items = analyze(VAGUE)["issues"]["items"]

    def _of(self, typ):
        return {i["line"]: i["terms"] for i in self.items if i["type"] == typ}

    def test_vague_line_numbers(self):
        self.assertEqual(self._of("模糊用語"), {
            5: ["TBD", "之後補"],
            8: ["使用者友善", "快速"],
            16: ["etc."],
        })

    def test_placeholder_line_numbers(self):
        self.assertEqual(self._of("未填佔位"), {9: ["____", "TODO"], 15: ["____"], 17: ["XXX"]})

    def test_metric_without_number(self):
        self.assertEqual(self._of("指標無數字"), {13: ["降低"]})

    def test_snippet_and_flags(self):
        i = next(i for i in self.items if i["line"] == 8)
        self.assertIn("FR-01 名單要能快速篩選", i["text"])
        self.assertTrue(i["in_requirement"])
        self.assertFalse(next(i for i in self.items if i["line"] == 5)["in_requirement"])

    def test_category_cell_not_flagged(self):
        text = "| 編號 | 類型 | Then |\n|---|---|---|\n| AC-01 | 正常 | 顯示 3 筆 |\n| AC-02 | 異常 | 顯示正確的姓名 |\n"
        got = {i["line"]: i["terms"] for i in analyze(text)["issues"]["items"]}
        self.assertEqual(got, {4: ["正確"]})

    def test_list_capped_at_30(self):
        text = "## 背景\n" + "".join(f"- 第 {n} 點 TBD\n" for n in range(35))
        res = analyze(text)
        self.assertEqual(res["issues"]["total"], 35)
        md = prd_check.render_markdown(res)
        self.assertEqual(md.count("| 模糊用語 |"), 30)
        self.assertIn("只列前 30 筆，共 35 筆", md)


class TestCli(unittest.TestCase):
    def _cli(self, *args):
        return subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / "prd_check.py"), *args],
                              capture_output=True, text=True, encoding="utf-8")

    def assertCleanError(self, proc, fragment):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertNotIn("Traceback", proc.stderr)
        self.assertIn(fragment, proc.stderr)

    def test_strict_exit_codes(self):
        missing, complete = str(FIXTURES / "prd_missing.md"), str(FIXTURES / "prd_complete.md")
        self.assertEqual(self._cli(missing).returncode, 0)             # default is always 0
        self.assertEqual(self._cli(missing, "--strict").returncode, 1)
        self.assertEqual(self._cli(complete, "--strict").returncode, 0)
        proc = self._cli(missing, "--strict", "--json")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(json.loads(proc.stdout)["exit_code"], 1)

    def test_strict_ignores_partial_and_advisory(self):
        p = write_md((FIXTURES / "prd_complete.md").read_text(encoding="utf-8")
                     .replace("| 版本 / 狀態 | v0.3 / 審閱中 |\n", "")
                     .split("## 10. 變更紀錄")[0].replace("AC-03 |\n| FR-03", "|\n| FR-03"))
        try:
            proc = self._cli(p, "--strict", "--json")
            res = json.loads(proc.stdout)
            self.assertEqual(status(res)["changelog"], "建議")
            self.assertEqual(status(res)["acceptance"], "部分")
            self.assertEqual(res["summary"]["missing"], 0)
            self.assertEqual(proc.returncode, 0)
        finally:
            os.remove(p)

    def test_markdown_output(self):
        proc = self._cli(str(EXAMPLES / "prd_sample.md"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = proc.stdout
        self.assertTrue(out.startswith("# PRD 結構檢查\n\n> 這份報告只檢查「結構與機械性問題」"))
        self.assertIn("品質檢查」逐條審", out.split("## 結構檢查")[0])
        for h in ("## 結構檢查", "## 機械性問題", "## 摘要", "## 解讀"):
            self.assertIn(h, out)
        self.assertIn("通過 4 項、部分 5 項、缺少 2 項", out)
        self.assertIn("缺：FR-03、FR-04", out)
        self.assertIn("1. 補齊驗收條件", out)
        self.assertIn("經驗排序，依團隊而異", out)

    def test_missing_file(self):
        self.assertCleanError(self._cli("no_such.md"), "找不到檔案")

    def test_empty_file(self):
        for content in ("", "\n  \n"):
            p = write_md(content)
            try:
                self.assertCleanError(self._cli(p), "檔案是空的")
            finally:
                os.remove(p)

    def test_non_utf8(self):
        p = write_md("## 背景\n內容\n", encoding="cp950")
        try:
            self.assertCleanError(self._cli(p), "不是 UTF-8")
        finally:
            os.remove(p)

    def test_bom_accepted(self):
        p = write_md("﻿## 背景\n內容\n")
        try:
            proc = self._cli(p, "--json")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(status(json.loads(proc.stdout))["background"], "通過")
        finally:
            os.remove(p)

    def test_no_argument(self):
        self.assertCleanError(self._cli(), "缺少必要參數")


if __name__ == "__main__":
    unittest.main()
