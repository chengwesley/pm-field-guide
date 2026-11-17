"""產生 pm-field-guide 的三份填寫用 Excel 範本（RICE 排序表、風險登記表、UAT 測試案例表）。

用法：python build_templates.py
輸出：../assets/RICE排序表.xlsx、風險登記表.xlsx、UAT測試案例表.xlsx

欄位、量表與用詞依據：
- references/08-requirement-prioritization.md（RICE、B2B Reach）
- references/30-risk-management.md（機率×衝擊 1–3、等級門檻、緩解 vs 應變）
- references/31-uat.md（準入準出、缺陷分級 S1–S4、帶條件上線）
- references/44-qa-testing.md（QA 嚴重度定義）

公式只用 IF / COUNT / COUNTIF / COUNTIFS / SUMIF / SUMPRODUCT / RANK / ROUNDUP 等，
Excel 與 Google Sheets 都能用。資料列一律留空，不放範例資料。
"""

import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule, FormulaRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

sys.stdout.reconfigure(encoding="utf-8")

ASSETS = Path(__file__).resolve().parent.parent / "assets"
N_ROWS = 50  # 預先格式化的資料列數

def solid(color):
    """實心填色。前景與背景色都設：條件式格式（dxf）的實心填色 Excel 讀的是背景色。"""
    return PatternFill(fill_type="solid", start_color=color, end_color=color)


FONT = "Microsoft JhengHei"
HEADER_FILL = solid("1F4E78")
HEADER_FONT = Font(name=FONT, bold=True, color="FFFFFF", size=11)
TITLE_FONT = Font(name=FONT, bold=True, size=14, color="1F4E78")
LABEL_FONT = Font(name=FONT, bold=True, size=10, color="1F4E78")
BODY_FONT = Font(name=FONT, size=10)
NOTE_FONT = Font(name=FONT, size=9, italic=True, color="595959")
INPUT_FILL = solid("FFF2CC")   # 需手動填寫的參數格
CALC_FILL = solid("F2F2F2")    # 公式欄
SECTION_FILL = solid("DDEBF7")
WARN_FILL = solid("F8CBAD")
THIN = Side(style="thin", color="BFBFBF")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(wrap_text=True, vertical="top")
CENTER = Alignment(horizontal="center", vertical="center", wrap_text=True)


# ---------- 共用工具 ----------

def add_list_validation(ws, rng, options, prompt=None, allow_blank=True):
    dv = DataValidation(
        type="list",
        formula1='"' + ",".join(options) + '"',
        allow_blank=allow_blank,
        showDropDown=False,  # False = 顯示下拉箭頭（openpyxl 的命名相反）
    )
    dv.error = "請從下拉選單選擇：" + "／".join(options)
    dv.errorTitle = "輸入值不在選項內"
    dv.showErrorMessage = True
    if prompt:
        dv.prompt = prompt
        dv.showInputMessage = True
    ws.add_data_validation(dv)
    dv.add(rng)
    return dv


def add_number_validation(ws, rng, op, f1, f2=None, kind="decimal", msg="", prompt=None):
    dv = DataValidation(type=kind, operator=op, formula1=str(f1),
                        formula2=None if f2 is None else str(f2), allow_blank=True)
    dv.error = msg
    dv.errorTitle = "數值超出範圍"
    dv.showErrorMessage = True
    if prompt:
        dv.prompt = prompt
        dv.showInputMessage = True
    ws.add_data_validation(dv)
    dv.add(rng)
    return dv


def write_header(ws, row, headers):
    for col, (name, width) in enumerate(headers, start=1):
        c = ws.cell(row=row, column=col, value=name)
        c.font = HEADER_FONT
        c.fill = HEADER_FILL
        c.alignment = CENTER
        c.border = BORDER
        ws.column_dimensions[get_column_letter(col)].width = width
    ws.row_dimensions[row].height = 36


def style_data_rows(ws, first, last, ncols, wrap_cols=(), center_cols=(), calc_cols=()):
    for r in range(first, last + 1):
        for col in range(1, ncols + 1):
            c = ws.cell(row=r, column=col)
            c.font = BODY_FONT
            c.border = BORDER
            letter = get_column_letter(col)
            if letter in wrap_cols:
                c.alignment = WRAP
            elif letter in center_cols:
                c.alignment = Alignment(horizontal="center", vertical="top")
            else:
                c.alignment = Alignment(vertical="top")
            if letter in calc_cols:
                c.fill = CALC_FILL


def print_setup(ws, header_row=None):
    ws.page_setup.orientation = "landscape"
    ws.page_setup.paperSize = ws.PAPERSIZE_A4
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.print_options.horizontalCentered = True
    ws.page_margins.left = ws.page_margins.right = 0.4
    ws.page_margins.top = ws.page_margins.bottom = 0.5
    if header_row:
        ws.print_title_rows = f"{header_row}:{header_row}"


def write_guide_sheet(wb, title, sections):
    """說明分頁：sections = [(小標, [(欄位/項目, 說明), ...]), ...]"""
    ws = wb.create_sheet(title)
    ws.column_dimensions["A"].width = 24
    ws.column_dimensions["B"].width = 95
    r = 1
    for heading, rows in sections:
        c = ws.cell(row=r, column=1, value=heading)
        c.font = Font(name=FONT, bold=True, size=12, color="FFFFFF")
        c.fill = HEADER_FILL
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=2)
        ws.cell(row=r, column=2).fill = HEADER_FILL
        r += 1
        for key, text in rows:
            a = ws.cell(row=r, column=1, value=key)
            b = ws.cell(row=r, column=2, value=text)
            a.font = Font(name=FONT, bold=True, size=10)
            b.font = BODY_FONT
            a.alignment = WRAP
            b.alignment = WRAP
            a.border = b.border = BORDER
            a.fill = SECTION_FILL
            r += 1
        r += 1
    print_setup(ws)
    ws.page_setup.orientation = "portrait"
    return ws


# ---------- 1. RICE 排序表 ----------

def build_rice():
    wb = Workbook()
    ws = wb.active
    ws.title = "排序"
    HR, FIRST = 4, 5
    LAST = FIRST + N_ROWS - 1

    ws["A1"] = "需求排序：RICE 評分表"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:F1")
    ws["G1"] = "範圍／期間："
    ws["G1"].font = LABEL_FONT
    ws["G1"].alignment = Alignment(horizontal="right")
    ws.merge_cells("H1:I1")
    ws["J1"] = "本次排序依據的目標："
    ws["J1"].font = LABEL_FONT
    ws["J1"].alignment = Alignment(horizontal="right")
    ws.merge_cells("J1:K1")
    ws.merge_cells("L1:O1")
    for ref in ("H1", "L1"):
        ws[ref].fill = INPUT_FILL
        ws[ref].border = BORDER
        ws[ref].font = BODY_FONT

    # 產能參數列
    ws["A2"] = "本期產能（人月）"
    ws.merge_cells("A2:B2")
    ws["C2"].fill = INPUT_FILL
    ws["D2"] = "必做已佔用"
    ws.merge_cells("D2:E2")
    ws["F2"] = f'=SUMIF(C{FIRST}:C{LAST},"是",H{FIRST}:H{LAST})'
    ws["G2"] = "評分項目可用"
    ws["H2"] = '=IF(C2="","",C2-F2)'
    ws["I2"] = "觸及單位檢查"
    ws.merge_cells("I2:J2")
    ws["K2"] = (
        f'=IF(COUNTA(E{FIRST}:E{LAST})=0,"尚未選觸及單位",'
        f'IF(SUMPRODUCT((E{FIRST}:E{LAST}<>"")/COUNTIF(E{FIRST}:E{LAST},E{FIRST}:E{LAST}&""))>1,'
        f'"⚠ 混用多種觸及單位：分開排或換算成營收影響","OK：單一觸及單位"))'
    )
    ws.merge_cells("K2:O2")
    for ref in ("A2", "D2", "G2", "I2"):
        ws[ref].font = LABEL_FONT
        ws[ref].alignment = Alignment(horizontal="right", vertical="center")
    for ref in ("C2", "F2", "H2", "K2"):
        ws[ref].border = BORDER
        ws[ref].font = Font(name=FONT, bold=True, size=11)
        ws[ref].alignment = Alignment(horizontal="center", vertical="center")
    for ref in ("F2", "H2"):
        ws[ref].fill = CALC_FILL
        ws[ref].number_format = "0.0"
    ws["C2"].number_format = "0.0"
    add_number_validation(ws, "C2", "greaterThan", 0, msg="本期產能需大於 0（人月）",
                          prompt="填本期可投入的總人月，含必做項目")
    ws["A3"] = ("黃底＝手動填；灰底＝公式自動算，請勿覆蓋。必做項目不評分，但會先佔用產能。"
                "欄位說明見「說明」分頁。")
    ws["A3"].font = NOTE_FONT
    ws.merge_cells("A3:O3")

    headers = [
        ("#", 5),
        ("項目\n（寫成問題：誰／情境／痛點）", 42),
        ("必做\n（是／否）", 9),
        ("觸及\nReach", 11),
        ("觸及單位", 16),
        ("影響\nImpact", 9),
        ("信心\nConfidence", 11),
        ("工作量\n（人月）", 10),
        ("RICE 分數", 11),
        ("排名", 7),
        ("層級\n高／中／低", 9),
        ("累計工作量\n（人月）", 11),
        ("本期\n排入／不做", 13),
        ("依據\n（數據、訪談、客訴數、CRM）", 34),
        ("調整與原因", 30),
    ]
    write_header(ws, HR, headers)
    ncols = len(headers)

    for r in range(FIRST, LAST + 1):
        ws[f"A{r}"] = r - FIRST + 1
        # 影響（F）來自下拉選單，部分軟體可能存成文字，故不用 COUNT 檢查，乘法會自動轉數字
        ws[f"I{r}"] = (f'=IF(OR(C{r}="是",COUNT(D{r},G{r},H{r})<3,F{r}=""),"",'
                       f'IF(H{r}<=0,"",D{r}*F{r}*G{r}/H{r}))')
        ws[f"J{r}"] = f'=IF(I{r}="","",RANK(I{r},I${FIRST}:I${LAST},0))'
        ws[f"K{r}"] = (f'=IF(J{r}="","",IF(J{r}<=ROUNDUP(COUNT(I${FIRST}:I${LAST})/3,0),"高",'
                       f'IF(J{r}<=ROUNDUP(COUNT(I${FIRST}:I${LAST})*2/3,0),"中","低")))')
        ws[f"L{r}"] = (f'=IF(I{r}="","",SUMIF(C${FIRST}:C${LAST},"是",H${FIRST}:H${LAST})'
                       f'+SUMIF(I${FIRST}:I${LAST},">="&I{r},H${FIRST}:H${LAST}))')
        ws[f"M{r}"] = (f'=IF(C{r}="是","必做（排入）",IF(I{r}="","",'
                       f'IF(N($C$2)<=0,"請填本期產能",IF(L{r}<=$C$2,"排入","本期不做"))))')
        ws[f"G{r}"].number_format = "0%"
        ws[f"I{r}"].number_format = "#,##0.0"
        ws[f"L{r}"].number_format = "0.0"
        ws[f"H{r}"].number_format = "0.0"
        ws[f"D{r}"].number_format = "#,##0"
    style_data_rows(ws, FIRST, LAST, ncols, wrap_cols=("B", "N", "O"),
                    center_cols=("A", "C", "E", "F", "G", "H", "J", "K", "M"),
                    calc_cols=("I", "J", "K", "L", "M"))
    for r in range(FIRST, LAST + 1):
        ws[f"I{r}"].alignment = Alignment(horizontal="right", vertical="top")

    add_list_validation(ws, f"C{FIRST}:C{LAST}", ["是", "否"],
                        prompt="法規期限、資安漏洞、合約承諾＝是：不參與評分，直接排入")
    add_number_validation(ws, f"D{FIRST}:D{LAST}", "greaterThanOrEqual", 0,
                          msg="觸及需為 0 以上的數字", prompt="同一張表所有項目用同一種觸及單位")
    add_list_validation(ws, f"E{FIRST}:E{LAST}",
                        ["人/季", "客戶家數", "年度合約金額", "商機金額×成交機率"],
                        prompt="同一次排序只用一種單位；不要把家數和人數放在同一欄比大小")
    add_list_validation(ws, f"F{FIRST}:F{LAST}", ["3", "2", "1", "0.5", "0.25"],
                        prompt="3 巨大／2 高／1 中／0.5 低／0.25 極小")
    add_number_validation(ws, f"G{FIRST}:G{LAST}", "between", 0, 1,
                          msg="信心需介於 0% 到 100%（輸入 70% 或 0.7）",
                          prompt="輸入 70% 或 0.7。沒有數據或訪談支持的最高 50%")
    add_number_validation(ws, f"H{FIRST}:H{LAST}", "greaterThan", 0,
                          msg="工作量需大於 0（人月）")

    # 條件式格式：信心 > 50% 但依據空白
    ws.conditional_formatting.add(
        f"G{FIRST}:G{LAST}",
        FormulaRule(formula=[f'AND(ISNUMBER(G{FIRST}),G{FIRST}>0.5,LEN(TRIM(N{FIRST}))=0)'],
                    fill=WARN_FILL, font=Font(bold=True, color="9C0006")))
    ws.conditional_formatting.add(
        f"N{FIRST}:N{LAST}",
        FormulaRule(formula=[f'AND(ISNUMBER(G{FIRST}),G{FIRST}>0.5,LEN(TRIM(N{FIRST}))=0)'],
                    fill=WARN_FILL))
    # 層級與排入的顏色
    for val, color in (("高", "C6EFCE"), ("中", "FFEB9C"), ("低", "EDEDED")):
        ws.conditional_formatting.add(
            f"K{FIRST}:K{LAST}",
            FormulaRule(formula=[f'K{FIRST}="{val}"'], fill=solid(color)))
    ws.conditional_formatting.add(
        f"M{FIRST}:M{LAST}",
        FormulaRule(formula=[f'LEFT(M{FIRST},2)="本期"'], font=Font(color="9C0006", bold=True)))
    ws.conditional_formatting.add(
        f"M{FIRST}:M{LAST}",
        FormulaRule(formula=[f'OR(M{FIRST}="排入",M{FIRST}="必做（排入）")'],
                    font=Font(color="006100", bold=True)))
    ws.conditional_formatting.add(
        "K2", FormulaRule(formula=['LEFT(K2,1)="⚠"'], fill=WARN_FILL))

    ws.freeze_panes = f"C{FIRST}"
    ws.auto_filter.ref = f"A{HR}:{get_column_letter(ncols)}{LAST}"
    print_setup(ws, HR)

    write_guide_sheet(wb, "說明", [
        ("使用步驟", [
            ("1. 整理清單", "合併重複、拆掉過大的項目，把「解法」改寫成「問題」：誰、在什麼情境、遇到什麼問題。每一項都要能用一句話說出誰受益、受益什麼。"),
            ("2. 先拉出必做", "法規期限、資安漏洞、合約承諾等不可協商的項目，「必做」選「是」：不參與評分，但工作量會先佔用本期產能。"),
            ("3. 各自先打分再對齊", "評分者先獨立打分避免從眾，差距大的項目才討論。每個影響與信心分數都要能在「依據」欄寫出一句依據。"),
            ("4. 填本期產能", "在上方黃色格填本期可投入的總人月（含必做項目）。表格會依 RICE 分數由高到低累計工作量，標出「排入」或「本期不做」。"),
            ("5. 手動調整", "依賴關係（A 不做 B 做不了）、策略上的長期投資、技術債風險等公式外的考量，寫在「調整與原因」，並直接以此決定最終順序。"),
            ("6. 對外說明", "重點不是公布分數，而是說清楚依據、對方的需求排在哪裡、什麼條件會改變排序。「本期不做」的項目另外記下重新考慮的條件。"),
        ]),
        ("欄位說明", [
            ("項目", "寫成問題（誰／情境／痛點），不要寫成解法。"),
            ("必做", "是＝不參與評分，直接排入；否或空白＝參與 RICE 評分。"),
            ("觸及（Reach）", "依「觸及單位」填數字。同一張表所有評分項目用同一種單位，來源要一致（產品數據、CRM、合約清單）。"),
            ("觸及單位", "人/季（個人方案、自助訂閱）／客戶家數或年度合約金額（影響現有企業客戶）／商機金額×成交機率（業務新案、「不做會掉單」）。詳見下方 B2B 規則。"),
            ("影響（Impact）", "固定量表，見下方「影響量表」。"),
            ("信心（Confidence）", "百分比，輸入 70% 或 0.7。沒有數據或訪談支持的最高 50%。信心 > 50% 但「依據」空白時，該格會標成橘紅色。"),
            ("工作量（人月）", "估計投入的人月，需大於 0。"),
            ("RICE 分數", "＝觸及 × 影響 × 信心 ÷ 工作量。必做＝是，或觸及／影響／信心／工作量有任一未填時留空。"),
            ("排名", "在所有已算出分數的項目中，依 RICE 分數由高到低排名；同分同名次。"),
            ("層級", "依排名分三等份：前 1/3 為高、中間 1/3 為中、後 1/3 為低（每段人數無條件進位）。分數用來分群，不要拿 412 和 398 的差距吵架；群內用討論與策略決定先後。"),
            ("累計工作量", "必做項目的工作量 ＋ RICE 分數大於或等於本項的所有評分項目工作量。同分項目會一起計入。"),
            ("本期排入／不做", "累計工作量 ≤ 本期產能＝排入，否則＝本期不做；必做項目一律顯示「必做（排入）」。若必做已佔用超過產能，上方「評分項目可用」會變負數。公式結果是起點，手動調整後以「調整與原因」為準。"),
            ("依據", "數據、訪談、客訴數、CRM 紀錄。只有業務口頭說法時寫「業務回報，待 CRM 佐證」。"),
            ("調整與原因", "手動調整排序時，寫下調整內容與原因（依賴、策略、技術債）。"),
        ]),
        ("影響量表（Impact，固定五級）", [
            ("3", "巨大影響"),
            ("2", "高"),
            ("1", "中"),
            ("0.5", "低"),
            ("0.25", "極小"),
            ("怎麼選", "只能從這五個值選，不要自創中間值。文字描述為 RICE 原始定義的慣用說法；團隊可另外約定每一級對應的具體門檻（例如對留存或續約的預期影響），寫在依據欄。"),
        ]),
        ("B2B 觸及規則", [
            ("為什麼要換單位", "RICE 原本以「季度受影響人數」計，但企業客戶的人數不等於影響力：一家 50 人的企業客戶和 50 位個人用戶，對續約與營收的影響完全不同。"),
            ("影響現有企業客戶", "單位用「客戶家數」或「年度合約金額」，資料來源：CRM、合約清單。"),
            ("業務新案／不做會掉單", "單位用「商機金額×成交機率」，資料來源：CRM 商機，或請業務逐案填表。"),
            ("個人方案、自助訂閱", "單位用「人/季」（季度受影響使用者數），資料來源：產品數據。"),
            ("同一張表只用一種單位", "同一次排序裡所有項目用同一種觸及單位。不要把家數和人數放在同一欄比大小。上方「觸及單位檢查」偵測到混用時會顯示警示。"),
            ("B2B 與 B2C 同時存在", "分開成兩張表排序（複製「排序」分頁），或都換算成營收影響再比。"),
        ]),
        ("信心上限規則", [
            ("沒有證據最高 50%", "沒有數據或訪談支持的項目，信心最高填 50%，避免大家都填 80% 以上讓公式失去區分力。"),
            ("業務口頭說法", "只有業務口頭說法、沒有 CRM 佐證時，信心最高 50%，依據欄寫「業務回報，待 CRM 佐證」。"),
            ("自動提醒", "信心 > 50% 但依據欄空白時，信心與依據兩格都會標成橘紅色，補上依據或把信心降到 50% 以下即解除。"),
        ]),
        ("在 Google Sheets 使用", [
            ("匯入", "檔案 → 匯入 → 上傳本檔，下拉選單、公式與條件式格式都會保留。"),
            ("信心欄輸入", "建議直接輸入「70%」，避免不同軟體對純數字的百分比轉換方式不同。"),
        ]),
    ])
    return wb


# ---------- 2. 風險登記表 ----------

def build_risk():
    wb = Workbook()
    ws = wb.active
    ws.title = "風險登記表"
    HR, FIRST = 4, 5
    LAST = FIRST + N_ROWS - 1

    ws["A1"] = "風險登記表"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:C1")
    labels = [("D1", "專案名稱：", "E1:H1"), ("I1", "最後複審：", "J1:K1"),
              ("L1", "下次複審：", "M1:N1")]
    for ref, text, merge in labels:
        ws[ref] = text
        ws[ref].font = LABEL_FONT
        ws[ref].alignment = Alignment(horizontal="right", vertical="center")
        ws.merge_cells(merge)
        cell = ws[merge.split(":")[0]]
        cell.fill = INPUT_FILL
        cell.border = BORDER
        cell.font = BODY_FONT
    ws["J1"].number_format = ws["M1"].number_format = "yyyy-mm-dd"

    ws["A2"] = "高風險數："
    ws["B2"] = f'=COUNTIFS(G{FIRST}:G{LAST},"高",P{FIRST}:P{LAST},"<>已關閉")'
    ws["C2"] = "中風險數：（不含已關閉）"
    ws["D2"] = f'=COUNTIFS(G{FIRST}:G{LAST},"中",P{FIRST}:P{LAST},"<>已關閉")'
    ws["E2"] = "待補項目數："
    ws["F2"] = f'=COUNTIF(Q{FIRST}:Q{LAST},"?*")'
    for ref in ("A2", "C2", "E2"):
        ws[ref].font = LABEL_FONT
        ws[ref].alignment = Alignment(horizontal="right", vertical="center")
    for ref in ("B2", "D2", "F2"):
        ws[ref].font = Font(name=FONT, bold=True, size=11)
        ws[ref].fill = CALC_FILL
        ws[ref].border = BORDER
        ws[ref].alignment = Alignment(horizontal="center", vertical="center")
    ws["A3"] = ("機率與衝擊各 1–3 分；分數＝機率×衝擊；6–9 高、3–4 中、1–2 低。"
                "灰底欄為公式，請勿覆蓋。量表與寫法見「說明」分頁。")
    ws["A3"].font = NOTE_FONT
    ws.merge_cells("A3:R3")

    headers = [
        ("ID", 6),
        ("風險敘述\n（因為…可能…導致…）", 40),
        ("類別", 14),
        ("機率\n1–3", 7),
        ("衝擊\n1–3", 7),
        ("分數\n機率×衝擊", 9),
        ("等級", 7),
        ("早期指標與門檻", 28),
        ("應對策略", 10),
        ("緩解措施\n（現在做）", 28),
        ("觸發條件", 22),
        ("應變計畫\n（觸發後做）", 28),
        ("應變決策者", 11),
        ("負責人\n（Owner）", 11),
        ("檢視日期", 12),
        ("狀態", 10),
        ("待補提醒\n（自動）", 22),
        ("備註\n（關閉原因、轉議題編號）", 24),
    ]
    write_header(ws, HR, headers)
    ncols = len(headers)

    for r in range(FIRST, LAST + 1):
        ws[f"A{r}"] = f'=IF(B{r}="","","R"&(ROW()-{FIRST - 1}))'
        ws[f"F{r}"] = f'=IF(COUNT(D{r},E{r})<2,"",D{r}*E{r})'
        ws[f"G{r}"] = f'=IF(F{r}="","",IF(F{r}>=6,"高",IF(F{r}>=3,"中","低")))'
        ws[f"Q{r}"] = (
            f'=IF(OR(B{r}="",P{r}="已關閉"),"",'
            f'IF(AND(E{r}=3,LEN(TRIM(L{r}))=0),"衝擊 3：需有應變計畫",'
            f'IF(AND(OR(G{r}="高",G{r}="中"),LEN(TRIM(H{r}))=0),"中高風險：需有早期指標",'
            f'IF(AND(OR(G{r}="高",G{r}="中"),OR(LEN(TRIM(J{r}))=0,LEN(TRIM(L{r}))=0)),"中高風險：緩解與應變都要有",'
            f'IF(AND(LEN(TRIM(L{r}))>0,LEN(TRIM(K{r}))=0),"應變計畫需寫觸發條件",'
            f'IF(LEN(TRIM(N{r}))=0,"需指定負責人",""))))))'
        )
        ws[f"O{r}"].number_format = "yyyy-mm-dd"
    style_data_rows(ws, FIRST, LAST, ncols,
                    wrap_cols=("B", "H", "J", "K", "L", "Q", "R"),
                    center_cols=("A", "C", "D", "E", "F", "G", "I", "M", "N", "O", "P"),
                    calc_cols=("A", "F", "G", "Q"))

    add_list_validation(ws, f"C{FIRST}:C{LAST}",
                        ["外部依賴", "技術", "範圍", "人力", "法規與個資", "資安",
                         "營運與客服", "商業"])
    add_number_validation(ws, f"D{FIRST}:D{LAST}", "between", 1, 3, kind="whole",
                          msg="機率請填 1–3 的整數",
                          prompt="1 不太可能／2 有可能／3 很可能或已有跡象")
    add_number_validation(ws, f"E{FIRST}:E{LAST}", "between", 1, 3, kind="whole",
                          msg="衝擊請填 1–3 的整數",
                          prompt="1 小延誤可內部吸收／2 錯過一個里程碑／3 錯過上線日、客戶受影響、法規或資料問題")
    add_list_validation(ws, f"I{FIRST}:I{LAST}", ["避免", "減輕", "轉移", "接受"])
    add_list_validation(ws, f"P{FIRST}:P{LAST}", ["觀察中", "緩解中", "已觸發", "已關閉"])
    dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2000,1,1)",
                        allow_blank=True)
    dv.error = "請輸入日期，例如 2026-12-01"
    dv.showErrorMessage = True
    ws.add_data_validation(dv)
    dv.add(f"O{FIRST}:O{LAST}")
    dv.add("J1")
    dv.add("M1")

    ws.conditional_formatting.add(
        f"F{FIRST}:F{LAST}",
        ColorScaleRule(start_type="num", start_value=1, start_color="63BE7B",
                       mid_type="num", mid_value=4, mid_color="FFEB84",
                       end_type="num", end_value=9, end_color="F8696B"))
    for val, color in (("高", "F8CBAD"), ("中", "FFEB9C"), ("低", "C6EFCE")):
        ws.conditional_formatting.add(
            f"G{FIRST}:G{LAST}",
            FormulaRule(formula=[f'G{FIRST}="{val}"'], fill=solid(color)))
    ws.conditional_formatting.add(
        f"L{FIRST}:L{LAST}",
        FormulaRule(formula=[f'AND(E{FIRST}=3,LEN(TRIM(L{FIRST}))=0,P{FIRST}<>"已關閉")'],
                    fill=WARN_FILL))
    ws.conditional_formatting.add(
        f"Q{FIRST}:Q{LAST}",
        FormulaRule(formula=[f'LEN(Q{FIRST})>0'], font=Font(color="9C0006", bold=True)))
    ws.conditional_formatting.add(
        f"A{FIRST}:R{LAST}",
        FormulaRule(formula=[f'$P{FIRST}="已關閉"'], font=Font(color="A6A6A6")))

    ws.freeze_panes = f"C{FIRST}"
    ws.auto_filter.ref = f"A{HR}:{get_column_letter(ncols)}{LAST}"
    print_setup(ws, HR)

    write_guide_sheet(wb, "說明", [
        ("使用步驟", [
            ("1. 找風險", "三個來源：時程上悲觀估時差距大的項目、依賴清單上的外部項目、過去類似專案出過的事。跟 RD lead、QA、客服各問一次「這個專案你最擔心什麼」。至少檢查第三方服務、法務與合規審閱、平台審核、客戶提供資料、關鍵人員五類。"),
            ("2. 評估機率×衝擊", "各用 1–3 分（見下方量表），分數與等級自動計算。"),
            ("3. 設早期指標", "每個中高風險寫一個「在它真的發生前會先看到的訊號」並設門檻，要能在週報或站會時被觀察到。"),
            ("4. 分清緩解與應變", "中高風險兩者都要有；低風險只需記錄與觀察。應變計畫要寫觸發條件。"),
            ("5. 指定負責人", "一個風險一個人名，給最接近訊號的人（例如第三方串接的 RD），不要全部掛 PM。PM 負責複審與升級。"),
            ("6. 定期複審", "每週花 10 分鐘過一次中高風險：指標有沒有變化、緩解做了沒、分數要不要調、有沒有新風險。已發生的風險轉成議題（issue）處理，關閉的風險在「備註」欄寫原因。里程碑前做一次完整複審。"),
        ]),
        ("機率量表（1–3）", [
            ("1", "不太可能"),
            ("2", "有可能"),
            ("3", "很可能／已有跡象"),
        ]),
        ("衝擊量表（1–3）", [
            ("1", "小延誤、可內部吸收"),
            ("2", "錯過一個里程碑、部分功能受影響"),
            ("3", "錯過上線日、客戶受影響、法規或資料問題"),
        ]),
        ("分數與等級", [
            ("分數", "＝機率 × 衝擊，範圍 1–9，以紅黃綠色階顯示。"),
            ("高", "6–9"),
            ("中", "3–4"),
            ("低", "1–2"),
            ("衝擊 3 的特別規則", "衝擊為 3 的項目無論機率多低都要有應變計畫，因為代價承受不起。衝擊 3 但應變計畫空白時，該格會標成橘紅色。"),
            ("不可接受的風險", "若沒有另外約定，資料外洩、交易或文件的法律效力爭議、計費錯誤視為不可接受。"),
        ]),
        ("欄位說明", [
            ("ID", "填了風險敘述後自動產生 R1、R2…（依列號）。"),
            ("風險敘述", "寫成「因為 ____，可能發生 ____，導致 ____」，不能只寫「第三方風險」這類名詞。"),
            ("類別", "外部依賴、技術、範圍、人力、法規與個資、資安、營運與客服、商業（市場、合作夥伴）。"),
            ("早期指標與門檻", "例如「對方超過 ____ 天未回覆測試環境申請」「效能測試 ____ 秒以上的比例超過 ____%」。"),
            ("應對策略", "避免（改變計畫讓風險不存在）／減輕（降低機率或衝擊）／轉移（交給第三方承擔，如合約、保險）／接受（記錄並觀察）。此分類為通用風險管理用語，供篩選用；具體做法寫在緩解措施與應變計畫。"),
            ("緩解措施（現在做）", "現在就做，目的是降低機率或衝擊。例如提前申請測試環境、加做 spike。"),
            ("觸發條件", "達到什麼條件就啟動應變計畫，避免一直拖到太晚。"),
            ("應變計畫（觸發後做）", "觸發條件達到時才做，目的是發生後減少損失。例如改用備案服務、砍範圍、延後上線。"),
            ("應變決策者", "誰有權啟動應變。預設 PM 可啟動影響範圍在專案內的應變，影響客戶或對外承諾的需主管決定。"),
            ("負責人（Owner）", "一個人名，負責盯早期指標、執行緩解、在觸發時發起應變。"),
            ("檢視日期", "最近一次檢視此風險的日期。"),
            ("狀態", "觀察中／緩解中／已觸發／已關閉。已觸發的轉成議題處理；已關閉的整列變灰。"),
            ("待補提醒", "自動檢查：衝擊 3 缺應變計畫、中高風險缺早期指標或緩解／應變、有應變卻沒觸發條件、沒負責人。上方「待補項目數」統計全表待補列數。"),
            ("備註", "關閉原因、轉成議題後的議題編號、分數調整原因等。"),
        ]),
        ("提醒", [
            ("法務審閱", "涉及身分驗證、法律效力或個資處理（告知同意、最小蒐集、保存期限、跨境傳輸）的風險與應變，需交由法務審閱。"),
            ("對外使用", "對外使用前需經相關主管審閱。"),
        ]),
    ])
    return wb


# ---------- 3. UAT 測試案例表 ----------

SEVERITIES = ["S1 阻斷", "S2 嚴重", "S3 一般", "S4 建議"]


def build_uat():
    wb = Workbook()
    ws = wb.active
    ws.title = "測試案例"
    HR, FIRST = 4, 5
    LAST = FIRST + N_ROWS - 1
    rng = lambda col: f"{col}${FIRST}:{col}${LAST}"  # noqa: E731

    ws["A1"] = "UAT 測試案例"
    ws["A1"].font = TITLE_FONT
    ws.merge_cells("A1:B1")
    for ref, text, merge in (("C1", "功能／版本：", "D1:E1"), ("F1", "簽核人：", "G1:G1"),
                             ("H1", "期間：", "I1:J1")):
        ws[ref] = text
        ws[ref].font = LABEL_FONT
        ws[ref].alignment = Alignment(horizontal="right", vertical="center")
        if merge.split(":")[0] != merge.split(":")[1]:
            ws.merge_cells(merge)
        cell = ws[merge.split(":")[0]]
        cell.fill = INPUT_FILL
        cell.border = BORDER
        cell.font = BODY_FONT

    # 結果統計
    summary = [
        ("通過", f'=COUNTIF({rng("H")},"通過")'),
        ("失敗", f'=COUNTIF({rng("H")},"失敗")'),
        ("阻擋", f'=COUNTIF({rng("H")},"阻擋")'),
        ("未執行", f'=COUNTIF({rng("H")},"未執行")+COUNTIFS({rng("A")},"<>",{rng("H")},"")'),
        ("案例總數", f'=COUNTIF({rng("A")},"?*")+COUNT({rng("A")})'),
        ("通過率", '=IF(L2=0,"",B2/L2)'),
    ]
    # 標籤與數值交錯放在第 2 列：A 標籤 B 值、C 標籤 D 值…
    cols = [("A", "B"), ("C", "D"), ("E", "F"), ("G", "H"), ("K", "L"), ("M", "N")]
    # 案例總數放在 L2，供通過率引用
    for (label, formula), (lc, vc) in zip(summary, cols):
        ws[f"{lc}2"] = label
        ws[f"{lc}2"].font = LABEL_FONT
        ws[f"{lc}2"].alignment = Alignment(horizontal="right", vertical="center")
        ws[f"{vc}2"] = formula
        ws[f"{vc}2"].font = Font(name=FONT, bold=True, size=12)
        ws[f"{vc}2"].fill = CALC_FILL
        ws[f"{vc}2"].border = BORDER
        ws[f"{vc}2"].alignment = Alignment(horizontal="center", vertical="center")
    ws.merge_cells("I2:J2")
    ws["I2"] = "（案例編號已填、結果空白也算未執行）"
    ws["I2"].font = NOTE_FONT
    ws["N2"].number_format = "0%"
    ws["A3"] = ("每個情境寫成「某角色在某狀況下要完成某件事」，且能追溯到一個需求或 User Story。"
                "嚴重度定義見「缺陷分級」；準入準出見「準入準出」。")
    ws["A3"].font = NOTE_FONT
    ws.merge_cells("A3:M3")

    headers = [
        ("案例編號", 10),
        ("對應需求\n（FR／User Story）", 16),
        ("情境\n（角色＋狀況＋要完成的事）", 30),
        ("前置條件", 22),
        ("步驟", 34),
        ("預期結果", 28),
        ("實際結果", 28),
        ("結果", 10),
        ("缺陷編號", 11),
        ("嚴重度", 10),
        ("測試人員", 11),
        ("測試日期", 12),
        ("備註", 24),
    ]
    write_header(ws, HR, headers)
    ncols = len(headers)
    style_data_rows(ws, FIRST, LAST, ncols, wrap_cols=("B", "C", "D", "E", "F", "G", "M"),
                    center_cols=("A", "H", "I", "J", "K", "L"))
    for r in range(FIRST, LAST + 1):
        ws[f"L{r}"].number_format = "yyyy-mm-dd"

    add_list_validation(ws, f"H{FIRST}:H{LAST}", ["通過", "失敗", "阻擋", "未執行"])
    add_list_validation(ws, f"J{FIRST}:J{LAST}", SEVERITIES,
                        prompt="S1 阻斷／S2 嚴重／S3 一般／S4 建議（S4 不算缺陷，進 Backlog）")
    dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2000,1,1)",
                        allow_blank=True)
    dv.error = "請輸入日期，例如 2026-12-01"
    dv.showErrorMessage = True
    ws.add_data_validation(dv)
    dv.add(f"L{FIRST}:L{LAST}")

    result_colors = {"通過": "C6EFCE", "失敗": "F8CBAD", "阻擋": "FFEB9C", "未執行": "EDEDED"}
    for val, color in result_colors.items():
        ws.conditional_formatting.add(
            f"H{FIRST}:H{LAST}",
            FormulaRule(formula=[f'H{FIRST}="{val}"'], fill=solid(color)))
    ws.conditional_formatting.add(
        f"J{FIRST}:J{LAST}",
        FormulaRule(formula=[f'LEFT(J{FIRST},2)="S1"'],
                    fill=solid("F8696B"), font=Font(bold=True, color="FFFFFF")))
    ws.conditional_formatting.add(
        f"J{FIRST}:J{LAST}",
        FormulaRule(formula=[f'LEFT(J{FIRST},2)="S2"'], fill=WARN_FILL))
    # 失敗／阻擋但沒填缺陷編號
    ws.conditional_formatting.add(
        f"I{FIRST}:I{LAST}",
        FormulaRule(formula=[f'AND(OR(H{FIRST}="失敗",H{FIRST}="阻擋"),LEN(TRIM(I{FIRST}))=0)'],
                    fill=WARN_FILL))

    ws.freeze_panes = f"B{FIRST}"
    ws.auto_filter.ref = f"A{HR}:{get_column_letter(ncols)}{LAST}"
    print_setup(ws, HR)

    # ---- 準入準出 ----
    ec = wb.create_sheet("準入準出")
    ec["A1"] = "UAT 準入／準出條件檢核"
    ec["A1"].font = TITLE_FONT
    ec.merge_cells("A1:F1")
    ec["A2"] = ("準入條件缺任一項就延後開跑；準出條件在 UAT 開始前寫定，請簽核人確認，過程中不放寬。"
                "「目前數據」由「測試案例」分頁自動計算（計算未通過且標該嚴重度的案例數）。")
    ec["A2"].font = NOTE_FONT
    ec["A2"].alignment = WRAP
    ec.merge_cells("A2:G2")
    ec.row_dimensions[2].height = 30
    ehead = [("階段", 12), ("檢核項目", 52), ("是否達成", 10), ("目前數據（自動）", 16),
             ("證據／說明", 34), ("確認人", 11), ("確認日期", 12)]
    write_header(ec, 4, ehead)

    tc = "'測試案例'!"
    s1_open = f'=COUNTIFS({tc}$J${FIRST}:$J${LAST},"S1*",{tc}$H${FIRST}:$H${LAST},"<>通過")'
    s2_open = f'=COUNTIFS({tc}$J${FIRST}:$J${LAST},"S2*",{tc}$H${FIRST}:$H${LAST},"<>通過")'
    not_passed = (f'={tc}D2+{tc}F2+{tc}H2')  # 失敗＋阻擋＋未執行
    items = [
        ("準入", "QA 的 P0／P1 缺陷為 0", None),
        ("準入", "測試環境穩定可用，版本號 ____", None),
        ("準入", "測試帳號與資料備妥", None),
        ("準入", "參與者已確認時段（含需求提出者、一線使用者）", None),
        ("準入", "測試資料不用正式環境客戶資料；若必須用真實資料：已取得來源單位同意、只匯入必要欄位、姓名／Email／電話已去識別化", None),
        ("準入", "缺陷分級規則已事先公布，並寫清楚由誰判級", None),
        ("準入", "準出條件已寫定，並經簽核人確認", None),
        ("準出", "S1 = 0", s1_open),
        ("準出", "S2 ≤ ____ 且皆有繞道方案", s2_open),
        ("準出", "所有主要情境通過（目前數據＝失敗＋阻擋＋未執行案例數）", not_passed),
        ("帶條件上線", "無 S1", s1_open),
        ("帶條件上線", "S2 有可行的繞道方案，且已告知客服", s2_open),
        ("帶條件上線", "已知問題都有修復日期", None),
        ("帶條件上線", "簽核人書面同意", None),
        ("結束後", "UAT 測試資料已設定刪除日期，並確認執行", None),
    ]
    r = 5
    for stage, text, formula in items:
        ec.cell(row=r, column=1, value=stage)
        ec.cell(row=r, column=2, value=text)
        if formula:
            ec.cell(row=r, column=4, value=formula)
        for col in range(1, 8):
            c = ec.cell(row=r, column=col)
            c.font = BODY_FONT
            c.border = BORDER
            c.alignment = WRAP if col in (2, 5) else Alignment(horizontal="center", vertical="top")
        ec.cell(row=r, column=4).fill = CALC_FILL
        ec.cell(row=r, column=7).number_format = "yyyy-mm-dd"
        stage_fill = {"準入": "DDEBF7", "準出": "E2EFDA", "帶條件上線": "FFF2CC", "結束後": "EDEDED"}
        ec.cell(row=r, column=1).fill = solid(stage_fill[stage])
        r += 1
    last_item = r - 1
    add_list_validation(ec, f"C5:C{last_item}", ["是", "否", "不適用"])
    ec.conditional_formatting.add(
        f"C5:C{last_item}",
        FormulaRule(formula=['C5="是"'], fill=solid("C6EFCE")))
    ec.conditional_formatting.add(
        f"C5:C{last_item}",
        FormulaRule(formula=['C5="否"'], fill=WARN_FILL))
    dv = DataValidation(type="date", operator="greaterThan", formula1="DATE(2000,1,1)",
                        allow_blank=True)
    dv.showErrorMessage = True
    dv.error = "請輸入日期"
    ec.add_data_validation(dv)
    dv.add(f"G5:G{last_item}")

    r = last_item + 2
    ec.cell(row=r, column=1, value="決策紀錄").font = Font(name=FONT, bold=True, size=12,
                                                         color="FFFFFF")
    ec.cell(row=r, column=1).fill = HEADER_FILL
    ec.merge_cells(start_row=r, start_column=1, end_row=r, end_column=5)
    r += 1
    decision_start = r
    decisions = [
        ("決定", "只能三選一：通過上線／延期／帶條件上線（UAT 結束日當天必須做出決定）"),
        ("延期至", ""),
        ("版本號", ""),
        ("測試範圍", ""),
        ("已知問題與修復日期", "帶條件上線時必填；已知問題清單＋繞道方案＋修復日期，並同步給客服"),
        ("簽核人", "一個人名，且事前同意擔任"),
        ("簽核日期", ""),
    ]
    for label, hint in decisions:
        a = ec.cell(row=r, column=1, value=label)
        a.font = Font(name=FONT, bold=True, size=10)
        a.fill = SECTION_FILL
        a.border = BORDER
        a.alignment = WRAP
        b = ec.cell(row=r, column=2)
        b.fill = INPUT_FILL
        b.border = BORDER
        b.font = BODY_FONT
        b.alignment = WRAP
        h = ec.cell(row=r, column=3, value=hint)
        h.font = NOTE_FONT
        h.alignment = WRAP
        ec.merge_cells(start_row=r, start_column=3, end_row=r, end_column=7)
        r += 1
    add_list_validation(ec, f"B{decision_start}", ["通過上線", "延期", "帶條件上線"])
    ec.cell(row=decision_start + 1, column=2).number_format = "yyyy-mm-dd"
    ec.cell(row=decision_start + 6, column=2).number_format = "yyyy-mm-dd"
    r += 1
    note = ec.cell(row=r, column=1,
                   value=("提醒：涉及合約條款或法律效力的變更，簽核前請交由法務審閱。"
                          "對外使用前需經相關主管審閱。"))
    note.font = NOTE_FONT
    note.alignment = WRAP
    ec.merge_cells(start_row=r, start_column=1, end_row=r, end_column=7)
    ec.row_dimensions[r].height = 30
    ec.freeze_panes = "A5"
    print_setup(ec, 4)

    # ---- 缺陷分級 ----
    sv = wb.create_sheet("缺陷分級")
    sv["A1"] = "缺陷分級"
    sv["A1"].font = TITLE_FONT
    sv.merge_cells("A1:C1")
    sv.column_dimensions["A"].width = 14
    sv.column_dimensions["B"].width = 55
    sv.column_dimensions["C"].width = 55

    def table(start_row, title, head, rows):
        t = sv.cell(row=start_row, column=1, value=title)
        t.font = Font(name=FONT, bold=True, size=12, color="1F4E78")
        rr = start_row + 1
        for col, name in enumerate(head, start=1):
            c = sv.cell(row=rr, column=col, value=name)
            c.font = HEADER_FONT
            c.fill = HEADER_FILL
            c.alignment = CENTER
            c.border = BORDER
        for row in rows:
            rr += 1
            for col, val in enumerate(row, start=1):
                c = sv.cell(row=rr, column=col, value=val)
                c.font = BODY_FONT
                c.border = BORDER
                c.alignment = WRAP
            sv.cell(row=rr, column=1).font = Font(name=FONT, bold=True, size=10)
        return rr + 2

    nr = table(3, "UAT 缺陷分級與處理規則（本表「嚴重度」下拉選單依此）",
               ["級別", "定義", "處理規則"], [
                   ("S1 阻斷", "主要情境無法完成、資料錯誤或遺失、安全或法規風險", "必修，未修不可上線"),
                   ("S2 嚴重", "主要情境可完成但需繞道，或影響特定客群",
                    "原則必修；帶病上線需簽核人同意 + 繞道方案 + 修復日期"),
                   ("S3 一般", "次要功能異常、體驗不佳但不影響結果", "排入下一個迭代"),
                   ("S4 建議", "文案、樣式、新需求", "進 Backlog，不算缺陷"),
               ])
    nr = table(nr, "QA 測試嚴重度（Severity，供對照）", ["級別", "定義", "誰判斷"], [
        ("S1", "系統無法使用或資料遺失", "QA"),
        ("S2", "主要功能失效無替代做法", "QA"),
        ("S3", "功能異常但有替代做法", "QA"),
        ("S4", "外觀、文字", "QA"),
    ])
    nr = table(nr, "判級原則", ["項目", "說明", ""], [
        ("缺陷 vs 新需求", "「規格裡有寫，做出來不一樣」才是缺陷；「規格沒寫，但我覺得應該要有」是新需求，標 S4 進 Backlog。", "新需求偽裝成缺陷是 UAT 最常見的拖延來源。"),
        ("誰判級", "PM 主持判級，RD 與需求方各有發言權，爭議時由簽核人裁定。", "當天回報的缺陷，隔天站會前都要有級別與負責人。"),
        ("嚴重度 vs 優先級", "嚴重度＝缺陷對系統的技術衝擊（QA 判斷）；優先級＝什麼時候要修（PM 判斷）。兩者不一定一致。", "PM 調整優先級時寫一句理由（影響多少使用者、有沒有替代做法），可寫在「測試案例」的備註欄。"),
        ("UAT 與 QA 的差別", "QA 定義偏技術衝擊；UAT 定義偏「使用者能不能完成工作」。UAT 的 S4 含新需求，不算缺陷。", "UAT 開場就講清楚「這次只看能不能完成你的工作」，樣式問題一律標 S4。"),
    ])
    print_setup(sv)

    write_guide_sheet(wb, "說明", [
        ("使用步驟", [
            ("1. 確認準入", "到「準入準出」分頁逐項確認，缺任一項就延後開跑。"),
            ("2. 寫測試情境", "從需求反推，不從功能清單排。每個情境是「某角色在某狀況下要完成某件事」，例如「店長在手機上替三位客人一次完成預約」。每個 User Story 至少對應一個情境，涵蓋主要路徑、一條常見異常路徑、一條權限或邊界情境。"),
            ("3. 挑參與者", "選實際會用的人：1 位需求提出者、1–2 位一線使用者（業務／客服／客戶窗口），必要時 1 位對法規或財務敏感的人。"),
            ("4. 執行並每日收斂", "每天固定時間過一次新缺陷：判級、指派、預計修復日。"),
            ("5. 對照準出條件決定", "只有三個選項：通過上線、延期、帶條件上線，填在「準入準出」分頁下方的決策紀錄。"),
            ("6. 書面簽核並存檔", "簽核內容包含版本號、測試範圍、已知問題清單、修復承諾。"),
        ]),
        ("「測試案例」欄位說明", [
            ("案例編號", "自訂，例如 UAT-01。填了編號才會計入案例總數。"),
            ("對應需求", "FR 編號或 User Story，每個案例都要能追溯到一個需求。"),
            ("情境", "角色＋狀況＋要完成的事。"),
            ("前置條件", "帳號、權限、資料、環境狀態。"),
            ("步驟", "可照著做的操作步驟。"),
            ("預期結果／實際結果", "預期結果事先寫好；實際結果由測試人員填。"),
            ("結果", "通過／失敗／阻擋／未執行。阻擋＝因環境或其他缺陷無法執行。結果空白視同未執行。"),
            ("缺陷編號", "失敗或阻擋時填，沒填會標成橘紅色。"),
            ("嚴重度", "S1 阻斷／S2 嚴重／S3 一般／S4 建議，定義見「缺陷分級」。S4 不算缺陷。"),
            ("測試人員／測試日期", "實際執行的人與日期。"),
            ("上方統計", "通過、失敗、阻擋、未執行、案例總數、通過率，用 COUNTIF 自動計算。"),
        ]),
        ("帶條件上線（帶病上線）", [
            ("必須同時符合", "無 S1、S2 有可行的繞道方案且已告知客服、有修復日期、簽核人書面同意。三者（已知問題清單＋簽核人＋修復日期）缺一不上。"),
        ]),
        ("個資提醒", [
            ("測試資料", "UAT 不要直接用正式環境的客戶資料。必須用真實資料時：取得資料來源單位同意、只匯入測試必要的欄位、姓名／Email／電話做去識別化、UAT 結束後設定刪除日期並確認執行。符合台灣個資法、GDPR、CCPA 的最小蒐集與保存期限原則。"),
            ("本表內容", "實際結果、備註欄請勿貼上客戶個資或截圖中的個資。"),
        ]),
        ("法務提醒", [
            ("合約與法律效力", "涉及合約條款或法律效力的變更，簽核前提醒交由法務審閱。對外使用前需經相關主管審閱。"),
        ]),
    ])
    return wb


def main():
    ASSETS.mkdir(parents=True, exist_ok=True)
    outputs = {
        "RICE排序表.xlsx": build_rice,
        "風險登記表.xlsx": build_risk,
        "UAT測試案例表.xlsx": build_uat,
    }
    for name, builder in outputs.items():
        path = ASSETS / name
        builder().save(path)
        print(f"已產生：{path}")


if __name__ == "__main__":
    main()
