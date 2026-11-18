"""指南與模式說明的結構檢查：確保每份指南都有報告模板，且 SKILL.md 引用的檔案都存在。

執行：在 pm-field-guide 資料夾下 `python3 -X utf8 -m unittest discover -s scripts/tests`。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
REFS = ROOT / "references"
MODES = ROOT / "modes"

REQUIRED_SECTIONS = ["何時用", "動手前先問", "做法", "產出模板", "品質檢查", "常見錯誤", "情境範例", "相關指南"]
OPTIONAL_SECTIONS = {"工具"}
REPORT_SIZES = {"完整報告", "短版", "個人紀錄"}


def guides():
    return sorted(REFS.glob("*.md"))


def sections(text: str) -> list[str]:
    # 團隊客製版可能把範例段落加上前綴（例如「某公司 情境範例」），一律視為「情境範例」
    found = re.findall(r"^## (.+?)\s*$", text, re.M)
    return ["情境範例" if s.endswith("情境範例") else s for s in found]


def template_section(text: str) -> str:
    start = text.index("## 產出模板")
    end = text.index("\n## ", start + 5)
    return text[start:end]


class TestGuideStructure(unittest.TestCase):
    def test_there_are_50_guides_numbered_01_to_50(self):
        nums = [p.name[:2] for p in guides()]
        self.assertEqual(nums, [f"{i:02d}" for i in range(1, 51)])

    def test_every_guide_has_required_sections_in_order(self):
        for p in guides():
            with self.subTest(guide=p.name):
                found = sections(p.read_text(encoding="utf-8"))
                extra = set(found) - set(REQUIRED_SECTIONS) - OPTIONAL_SECTIONS
                self.assertFalse(extra, f"多出的段落：{extra}")
                core = [s for s in found if s in REQUIRED_SECTIONS]
                self.assertEqual(core, REQUIRED_SECTIONS)


class TestReportTemplates(unittest.TestCase):
    def test_every_guide_declares_report_format_title_and_conclusion(self):
        for p in guides():
            with self.subTest(guide=p.name):
                sec = template_section(p.read_text(encoding="utf-8"))
                m = re.search(r"^- \*\*報告格式：\*\* (\S+?)（外框見 `modes/report\.md`）$", sec, re.M)
                self.assertIsNotNone(m, "缺少「報告格式」行")
                self.assertIn(m.group(1), REPORT_SIZES)
                title = re.search(r"^- \*\*標題：\*\* (.+)$", sec, re.M)
                concl = re.search(r"^- \*\*結論先講：\*\* (.+)$", sec, re.M)
                self.assertIsNotNone(title, "缺少「標題」行")
                self.assertIsNotNone(concl, "缺少「結論先講」行")
                self.assertGreaterEqual(len(concl.group(1)), 10)

    def test_every_guide_template_has_a_body(self):
        for p in guides():
            with self.subTest(guide=p.name):
                sec = template_section(p.read_text(encoding="utf-8"))
                has_fence = sec.count("```") >= 2
                has_table = bool(re.search(r"^\|[-| :]+\|\s*$", sec, re.M))
                self.assertTrue(has_fence or has_table, "產出模板沒有可填寫的本文")
                self.assertIn("____", sec, "模板沒有任何待填空格")

    def test_title_names_a_document_that_exists_in_the_template(self):
        # 標題行寫的文件名稱，要對得上模板裡真的有的那一份（曾發生標題寫「報告」、模板卻是「計畫」）
        exempt = {"21": "PRD 的模板段落是編號章節", "50": "個人紀錄不需要標題"}
        for p in guides():
            if p.name[:2] in exempt:
                continue
            with self.subTest(guide=p.name):
                sec = template_section(p.read_text(encoding="utf-8"))
                title = re.search(r"^- \*\*標題：\*\* (.+)$", sec, re.M).group(1)
                names = [re.split(r"[：（｜/／ ]", h.strip())[0] for h in re.findall(r"^### (.+)$", sec, re.M)]
                names = [n for n in names if n and "_" not in n]
                # 模板第一行以空格開頭時（例如「____（專案名稱）週報」），補上第一行裡的關鍵字
                first = re.search(r"^### (.+)$", sec, re.M)
                if first:
                    names += re.findall(r"[\u4e00-\u9fff]{2,}", re.sub(r"（[^）]*）", "", first.group(1)))
                self.assertTrue(any(n in title for n in names), f"標題「{title}」對不上模板裡的文件：{names[:4]}")

    def test_full_reports_and_short_forms_are_both_used(self):
        sizes = [re.search(r"\*\*報告格式：\*\* (\S+?)（", template_section(p.read_text(encoding="utf-8"))).group(1)
                 for p in guides()]
        self.assertGreater(sizes.count("完整報告"), 0)
        self.assertGreater(sizes.count("短版"), 0)

    def test_report_shell_defines_every_format(self):
        text = (MODES / "report.md").read_text(encoding="utf-8")
        for heading in ["## 完整報告", "## 短版", "## 計算報告", "## 劇本進度報告", "## 填寫規則"]:
            self.assertIn(heading, text)
        for part in ["## 結論", "## 依據與信心", "## 需要你確認的事", "## 下一步"]:
            self.assertIn(part, text, f"完整報告缺少「{part}」")

    def test_mode_files_with_their_own_format_have_one(self):
        self.assertIn("## 審查結論", (MODES / "review.md").read_text(encoding="utf-8"))
        self.assertIn("## 演練回饋", (MODES / "rehearsal.md").read_text(encoding="utf-8"))
        self.assertIn("劇本進度報告", (MODES / "playbooks.md").read_text(encoding="utf-8"))


class TestReferencesResolve(unittest.TestCase):
    def test_skill_md_routes_to_every_guide(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        for p in guides():
            self.assertIn(p.name, skill, f"SKILL.md 路由表沒有 {p.name}")

    def test_referenced_files_exist(self):
        files = [ROOT / "SKILL.md", *MODES.glob("*.md"), *guides()]
        names = {p.name for p in guides()}
        for f in files:
            text = f.read_text(encoding="utf-8")
            with self.subTest(file=f.name):
                for g in re.findall(r"\b(\d\d-[a-z0-9-]+\.md)", text):
                    self.assertIn(g, names, f"指向不存在的指南 {g}")
                for m in re.findall(r"`(modes/[a-z]+\.md)`", text):
                    self.assertTrue((ROOT / m).exists(), f"指向不存在的 {m}")
                for s in re.findall(r"`(?:scripts/)?([a-z][a-z_]*\.py)\b", text):  # 模板裡的 ____.py 是佔位，不算
                    self.assertTrue((ROOT / "scripts" / s).exists(), f"指向不存在的腳本 {s}")


if __name__ == "__main__":
    unittest.main()
