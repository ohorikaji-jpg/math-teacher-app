"""
教科書PDF からオレンジ色の公式欄を抽出するスクリプト
使用方法:
  python extract_formulas.py              # 全章
  python extract_formulas.py --chapter 1
  python extract_formulas.py --chapter 1 --chapter 2
  python extract_formulas.py --debug      # 色情報を確認
出力:
  output/formulas.md, output/formulas.json (既存)
  output/chapter1.html, output/chapter2.html ... (章ごとHTML)
"""

import fitz
import re
import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from html import escape

INPUT_PDF = Path("input/math2.pdf")
OUTPUT_DIR = Path("output")

# この教科書のオレンジ帯の2段階の色 (R, G, B 0.0-1.0)
# 濃いオレンジ: 公式名ヘッダー (1.00, 0.86, 0.74)
HEADER_COLOR = (0.99, 0.85, 0.73)
# 薄いオレンジ: 数式本体  (1.00, 0.93, 0.84)
BODY_COLOR   = (0.99, 0.91, 0.82)
COLOR_TOLERANCE = 0.05

# PUA文字 (このPDFのフォント固有の上付き文字マッピング)
PUA_MAP = {
    "\uea30": "⁰", "\uea31": "¹", "\uea32": "²", "\uea33": "³",
    "\uea34": "⁴", "\uea35": "⁵", "\uea36": "⁶", "\uea37": "⁷",
    "\uea38": "⁸", "\uea39": "⁹", "\uea6e": "ⁿ", "\uee12": "⁻",
}

# 数式本体にのみ適用する記号置換（タイトル中の漢字と衝突するため分離）
# このPDFでは ≧ のグリフが「加」(U+52A0) のコードポイントに割り当てられている
MATH_SYMBOL_MAP = {
    "\u52a0": "≧",   # 加 → ≧ (以上)
}


def fix_pua(text: str) -> str:
    """PUA文字を対応するUnicode上付き文字に置換 (タイトル・数式共通)"""
    for pua, replacement in PUA_MAP.items():
        text = text.replace(pua, replacement)
    return text


def fix_math_symbols(text: str) -> str:
    """数式本体にのみ適用する記号置換"""
    for orig, replacement in MATH_SYMBOL_MAP.items():
        text = text.replace(orig, replacement)
    return text


SUPERSCRIPT_CHARS = set("⁰¹²³⁴⁵⁶⁷⁸⁹ⁿ⁻")
MATH_CONTINUE_END = set("=+−-×÷(,")
MATH_CONTINUE_START = set("=+−-×÷),")

def join_expression_lines(lines: list[str]) -> list[str]:
    """
    数式の行分断を修正する。
    1. 行頭の上付き文字を前行末尾に結合
    2. 演算子で終わる行・始まる行を結合
    例: ['(a+b)', '³=a', '³+3a²b'] → ['(a+b)³=a³+3a²b']
    """
    if not lines:
        return lines

    result = [lines[0].strip()]
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue

        prev = result[-1] if result else ""

        # 行頭の上付き文字を抽出して前行に結合
        leading_supers = ""
        rest = stripped
        for ch in stripped:
            if ch in SUPERSCRIPT_CHARS:
                leading_supers += ch
                rest = rest[1:]
            else:
                break

        if leading_supers:
            result[-1] = prev.rstrip() + leading_supers
            prev = result[-1]
            stripped = rest
            if not stripped:
                continue

        # 箇条書き番号（数字1文字）は独立
        if re.fullmatch(r'\d', stripped):
            result.append(stripped)
            continue

        # 前行が演算子で終わるか、今行が演算子で始まる → 結合
        if (prev and prev[-1] in MATH_CONTINUE_END) or (stripped[0] in MATH_CONTINUE_START):
            result[-1] = prev.rstrip() + stripped
        else:
            result.append(stripped)

    return result


def color_matches(fill: tuple, target: tuple, tol: float = COLOR_TOLERANCE) -> bool:
    if not fill or len(fill) < 3:
        return False
    return all(abs(fill[i] - target[i]) <= tol for i in range(3))


@dataclass
class Formula:
    page: int
    chapter: str
    section: str
    title: str
    expressions: list[str] = field(default_factory=list)


def build_chapter_map(doc: fitz.Document) -> list[tuple[int, int, str]]:
    """
    全ページをスキャンして章の開始ページを検出する。
    各章番号の初出ページのみを章開始とみなす（ページヘッダーの重複を除外）。
    戻り値: [(start_page_0idx, end_page_0idx, chapter_title), ...]
    """
    chapter_starts = []
    seen_chapters: set[int] = set()
    pattern = re.compile(r'第\s*(\d+)\s*章\s*\n(.+)')

    for pn in range(doc.page_count):
        text = doc[pn].get_text()
        m = pattern.search(text)
        if m:
            ch_num = int(m.group(1))
            if ch_num in seen_chapters:
                continue  # ページヘッダーの重複をスキップ
            seen_chapters.add(ch_num)
            ch_name = m.group(2).strip()
            title = f"第{ch_num}章 {ch_name}"
            chapter_starts.append((pn, ch_num, title))

    result = []
    for i, (start, ch_num, title) in enumerate(chapter_starts):
        end = chapter_starts[i + 1][0] - 1 if i + 1 < len(chapter_starts) else doc.page_count - 1
        result.append((start, end, title))

    return result


def build_section_map(doc: fitz.Document, chapter_start: int, chapter_end: int) -> list[tuple[int, int, str]]:
    """章内の節ページ範囲を返す [(start, end, title), ...]"""
    section_starts = []
    seen: set[int] = set()
    pattern = re.compile(r'第\s*(\d+)\s*節\s*\n(.+)')

    for pn in range(chapter_start, chapter_end + 1):
        text = doc[pn].get_text()
        m = pattern.search(text)
        if m:
            sec_num = int(m.group(1))
            if sec_num in seen:
                continue
            seen.add(sec_num)
            title = f"第{sec_num}節 {m.group(2).strip()}"
            section_starts.append((pn, title))

    if not section_starts:
        return [(chapter_start, chapter_end, "")]

    result = []
    for i, (start, title) in enumerate(section_starts):
        end = section_starts[i + 1][0] - 1 if i + 1 < len(section_starts) else chapter_end
        result.append((start, end, title))
    return result


# ---- LaTeX変換 -------------------------------------------------------

SUPERSCRIPT_TO_LATEX = {
    "⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
    "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9",
    "ⁿ": "n", "⁻": "-",
}
SYMBOL_TO_LATEX = [
    ("≧", r"\geq "), ("≦", r"\leq "), ("×", r"\times "), ("÷", r"\div "),
    ("±", r"\pm "), ("∓", r"\mp "), ("∞", r"\infty"), ("π", r"\pi"),
    ("θ", r"\theta"), ("α", r"\alpha"), ("β", r"\beta"), ("γ", r"\gamma"),
    ("σ", r"\sigma"), ("φ", r"\phi"), ("ω", r"\omega"), ("Σ", r"\Sigma"),
    ("√", r"\sqrt"), ("−", "-"),
]


def text_to_latex(text: str) -> str:
    """Unicode数式テキストをLaTeXに変換（best-effort）"""
    result = ""
    i = 0
    while i < len(text):
        ch = text[i]
        if ch in SUPERSCRIPT_TO_LATEX:
            sup = ""
            while i < len(text) and text[i] in SUPERSCRIPT_TO_LATEX:
                sup += SUPERSCRIPT_TO_LATEX[text[i]]
                i += 1
            result += f"^{{{sup}}}" if len(sup) > 1 else f"^{sup}"
        else:
            result += ch
            i += 1
    for src, dst in SYMBOL_TO_LATEX:
        result = result.replace(src, dst)
    return result.strip()


def is_math_line(line: str) -> bool:
    """行が数式（LaTeX変換対象）か日本語説明文かを判定"""
    has_japanese = bool(re.search(r'[\u3040-\u30ff\u4e00-\u9fff]', line))
    if has_japanese and len(line) > 12:
        return False
    return bool(re.search(r'[=+\-×÷≧≦²³⁴⁵⁶⁷⁸⁹ⁿ√∞]|[a-zA-Z]\d|[a-zA-Z]\(', line))


# ---- HTML生成 --------------------------------------------------------

HTML_CSS = """
:root {
  --orange-dark: #e8885a;
  --orange-light: #fdf0e6;
  --orange-border: #e8a87c;
  --text: #2c2c2c;
  --section-bg: #f9f6f2;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: "Hiragino Kaku Gothic ProN", "Meiryo", sans-serif;
  color: var(--text);
  background: #fafaf8;
  line-height: 1.7;
}
.page-wrap { max-width: 900px; margin: 0 auto; padding: 2rem 1.5rem 4rem; }
h1.chapter-title {
  font-size: 1.8rem;
  border-left: 6px solid var(--orange-dark);
  padding: 0.4rem 0 0.4rem 0.8rem;
  margin-bottom: 2rem;
  color: #333;
}
h2.section-title {
  font-size: 1.2rem;
  color: #555;
  margin: 2.5rem 0 1rem;
  padding-bottom: 0.3rem;
  border-bottom: 2px solid var(--orange-border);
}
.formula-card {
  background: var(--orange-light);
  border: 1px solid var(--orange-border);
  border-radius: 6px;
  margin-bottom: 1.2rem;
  overflow: hidden;
}
.formula-header {
  background: var(--orange-dark);
  color: #fff;
  font-weight: bold;
  font-size: 0.95rem;
  padding: 0.4rem 0.9rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.formula-page { font-size: 0.78rem; font-weight: normal; opacity: 0.85; }
.formula-body { padding: 0.8rem 1.2rem; }
.expr-block {
  background: #fff;
  border-left: 3px solid var(--orange-border);
  padding: 0.5rem 1rem;
  margin: 0.4rem 0;
  border-radius: 0 4px 4px 0;
  font-size: 1.05rem;
  overflow-x: auto;
}
.expr-text {
  padding: 0.2rem 0;
  color: #444;
  font-size: 0.92rem;
}
.list-num {
  display: inline-block;
  width: 1.4em;
  height: 1.4em;
  line-height: 1.4em;
  text-align: center;
  background: var(--orange-dark);
  color: #fff;
  border-radius: 50%;
  font-size: 0.78rem;
  font-weight: bold;
  margin-right: 0.4rem;
  vertical-align: middle;
}
"""

MATHJAX_SCRIPT = """
<script>
MathJax = {
  tex: { inlineMath: [['\\\\(','\\\\)']], displayMath: [['\\\\[','\\\\]']] },
  options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] }
};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml.js" async></script>
"""


def render_expression(line: str) -> str:
    """1行を HTML に変換。数式なら MathJax ブロック、説明文なら <p>"""
    stripped = line.strip()
    if not stripped:
        return ""

    # 箇条書き番号（単独数字）
    if re.fullmatch(r'\d', stripped):
        return f'<span class="list-num">{escape(stripped)}</span>'

    if is_math_line(stripped):
        latex = text_to_latex(stripped)
        return f'<div class="expr-block">\\[ {escape(latex)} \\]</div>'
    else:
        return f'<p class="expr-text">{escape(stripped)}</p>'


def format_html_chapter(chapter_title: str, chapter_num: int,
                         formulas: list[Formula]) -> str:
    """1章分のHTMLを生成"""
    body_parts = []
    current_section = None

    for f in formulas:
        if f.section != current_section:
            current_section = f.section
            if current_section:
                body_parts.append(
                    f'<h2 class="section-title">{escape(current_section)}</h2>\n'
                )

        exprs_html = "\n".join(filter(None, [render_expression(e) for e in f.expressions]))
        card = (
            f'<div class="formula-card">\n'
            f'  <div class="formula-header">'
            f'{escape(f.title)}'
            f'<span class="formula-page">p.{f.page}</span>'
            f'</div>\n'
            f'  <div class="formula-body">\n{exprs_html}\n  </div>\n'
            f'</div>\n'
        )
        body_parts.append(card)

    body = "\n".join(body_parts)
    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(chapter_title)} 公式集</title>
<style>{HTML_CSS}</style>
{MATHJAX_SCRIPT}
</head>
<body>
<div class="page-wrap">
  <h1 class="chapter-title">{escape(chapter_title)} 公式集</h1>
{body}
</div>
</body>
</html>
"""


def extract_formulas_from_page(page: fitz.Page, page_num: int, chapter_title: str, section_title: str) -> list[Formula]:
    """1ページからオレンジ帯の公式を抽出"""
    # ヘッダー矩形とボディ矩形をそれぞれ収集
    headers: list[tuple[fitz.Rect, str]] = []
    bodies:  list[tuple[fitz.Rect, str]] = []

    for d in page.get_drawings():
        fill = d.get("fill")
        rect = d.get("rect")
        if not rect or rect.width < 100 or rect.height < 10:
            continue
        if color_matches(fill, HEADER_COLOR):
            raw = page.get_textbox(fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + 5))
            text = fix_pua(raw)  # タイトルは上付き文字のみ変換（漢字置換は行わない）
            headers.append((rect, text.strip()))
        elif color_matches(fill, BODY_COLOR):
            raw = page.get_textbox(fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + 5))
            text = fix_math_symbols(fix_pua(raw))  # 数式本体は記号置換も適用
            bodies.append((rect, text.strip()))

    # ヘッダーとボディをY座標で対応付け
    formulas = []
    used_bodies = set()

    for h_rect, h_text in headers:
        if not h_text:
            continue

        # 公式名: ヘッダーの最初の行
        lines = [l.strip() for l in h_text.splitlines() if l.strip()]
        title = lines[0] if lines else "公式"

        # 対応するボディ: ヘッダーの直下にある矩形
        body_text = ""
        best_dist = 999
        best_idx = -1
        for i, (b_rect, b_text) in enumerate(bodies):
            if i in used_bodies:
                continue
            dist = b_rect.y0 - h_rect.y1
            if -5 <= dist <= 30 and abs(b_rect.x0 - h_rect.x0) < 10:
                if dist < best_dist:
                    best_dist = dist
                    best_idx = i
                    body_text = b_text

        if best_idx >= 0:
            used_bodies.add(best_idx)

        raw_lines = [l for l in body_text.splitlines() if l.strip()]
        expressions = join_expression_lines(raw_lines)
        formulas.append(Formula(
            page=page_num + 1,
            chapter=chapter_title,
            section=section_title,
            title=title,
            expressions=expressions,
        ))

    # ボディのみ (ヘッダーなし) も拾う
    for i, (b_rect, b_text) in enumerate(bodies):
        if i in used_bodies or not b_text.strip():
            continue
        raw_lines = [l for l in b_text.splitlines() if l.strip()]
        expressions = join_expression_lines(raw_lines)
        formulas.append(Formula(
            page=page_num + 1,
            chapter=chapter_title,
            section=section_title,
            title="公式",
            expressions=expressions,
        ))

    return formulas


def format_markdown(all_formulas: list[Formula]) -> str:
    if not all_formulas:
        return "# 公式集\n\n公式が見つかりませんでした。\n"

    lines = ["# 公式集\n"]
    current_chapter = None
    current_section = None
    idx = 1

    for f in all_formulas:
        if f.chapter != current_chapter:
            current_chapter = f.chapter
            current_section = None
            lines.append(f"\n## {f.chapter}\n")
            idx = 1
        if f.section and f.section != current_section:
            current_section = f.section
            lines.append(f"\n### {f.section}\n")

        lines.append(f"#### {idx}. {f.title}  (p.{f.page})\n")
        for expr in f.expressions:
            lines.append(f"    {expr}")
        lines.append("")
        idx += 1

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="教科書PDFから公式を抽出")
    parser.add_argument("--chapter", type=int, action="append", dest="chapters",
                        help="対象章番号 (複数可、省略で全章)")
    parser.add_argument("--debug", action="store_true",
                        help="矩形の色情報をすべて出力")
    args = parser.parse_args()

    if not INPUT_PDF.exists():
        print(f"エラー: {INPUT_PDF} が見つかりません")
        return

    OUTPUT_DIR.mkdir(exist_ok=True)
    doc = fitz.open(str(INPUT_PDF))
    print(f"PDF読み込み完了: {doc.page_count}ページ")

    if args.debug:
        print("\n--- デバッグ: 各ページの大きな矩形のfill色 (上位20ページ) ---")
        for pn in range(min(20, doc.page_count)):
            page = doc[pn]
            for d in page.get_drawings():
                fill = d.get("fill")
                rect = d.get("rect")
                if fill and rect and rect.width > 80 and rect.height > 10:
                    print(f"  p.{pn+1}  fill=({fill[0]:.2f},{fill[1]:.2f},{fill[2]:.2f})  "
                          f"size={rect.width:.0f}x{rect.height:.0f}")
        print("---\n")

    chapter_map = build_chapter_map(doc)
    if not chapter_map:
        print("警告: 章見出しが見つかりません。全ページを対象にします。")
        chapter_map = [(0, doc.page_count - 1, "全体")]

    target = args.chapters or []
    if target:
        # 章番号でフィルタ: タイトルから番号を抽出して照合
        filtered = []
        for start, end, title in chapter_map:
            m = re.search(r'第(\d+)章', title)
            if m and int(m.group(1)) in target:
                filtered.append((start, end, title))
        chapter_map = filtered

    print(f"対象章: {[t for _, _, t in chapter_map]}")

    all_formulas: list[Formula] = []
    for start, end, ch_title in chapter_map:
        print(f"  処理中: {ch_title} (p.{start+1}〜{end+1})")
        section_map = build_section_map(doc, start, end)

        ch_formulas: list[Formula] = []
        for sec_start, sec_end, sec_title in section_map:
            for pn in range(sec_start, sec_end + 1):
                formulas = extract_formulas_from_page(doc[pn], pn, ch_title, sec_title)
                ch_formulas.extend(formulas)

        # 章HTMLを保存
        m = re.search(r'第(\d+)章', ch_title)
        ch_num = int(m.group(1)) if m else (chapter_map.index((start, end, ch_title)) + 1)
        html_path = OUTPUT_DIR / f"chapter{ch_num}.html"
        html_path.write_text(
            format_html_chapter(ch_title, ch_num, ch_formulas),
            encoding="utf-8"
        )
        print(f"    HTML保存: {html_path}  ({len(ch_formulas)}件)")
        all_formulas.extend(ch_formulas)

    print(f"\n抽出完了: {len(all_formulas)} 個の公式")

    md_path = OUTPUT_DIR / "formulas.md"
    md_path.write_text(format_markdown(all_formulas), encoding="utf-8")
    print(f"保存: {md_path}")

    json_data = [
        {"page": f.page, "chapter": f.chapter, "section": f.section,
         "title": f.title, "expressions": f.expressions}
        for f in all_formulas
    ]
    json_path = OUTPUT_DIR / "formulas.json"
    json_path.write_text(json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"保存: {json_path}")


if __name__ == "__main__":
    main()
