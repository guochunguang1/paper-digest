#!/usr/bin/env python3
# =============================================================================
# paper-digest · PDF 提取脚本（文本 + 图注定位 + 图区域裁剪）
# 职责边界：本脚本只做确定性提取，不做任何"理解"；
#          题目/摘要/总结/逐图解读由 LLM 消费本脚本的产物完成（见 SKILL.md）。
# 出厂标准：灵活（参数全暴露 + 默认值）/ 高性能（block 级批量处理，无逐字符循环）
#          / 中间结果多保存（paper_text.md + figures/*.png + manifest.json 三落盘）
# 跨平台：pathlib 全程，Mac/Linux/Windows(Git Bash/WSL) 通用；仅依赖 pymupdf。
# =============================================================================
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("[paper-digest] 缺少 PyMuPDF：请先运行  python3 -m pip install --user PyMuPDF")

# ---- 参数块（集中可改；CLI 可覆盖；禁止把阈值散落进函数体）------------------
DEFAULT_ZOOM = 2.2          # 渲染倍率：1.0=72dpi，2.2≈158dpi，图解释够用且体积可控
DEFAULT_HEADER_MARGIN = 30.0  # 页顶跳过的 running header 高度（pt）
DEFAULT_CAPTION_PAD = 8.0     # 裁剪框在图注下缘多留的白边（pt）
MIN_CAPTION_WORDS = 4         # 图注块至少含这么多词，用于过滤正文交叉引用误匹配
FULL_WIDE_RATIO = 0.6         # 图注宽度超过页宽此比例 → 按整页宽裁剪，否则按图注列宽
MAIN_FIG_PAT = re.compile(
    r"^(Figure|Fig\.?|Scheme|Graphical abstract|图|图示)\s*(\d+)\s*[.．:：]", re.IGNORECASE
)
SUPP_FIG_PAT = re.compile(r"^(Figure|Fig\.?|图)\s*S(\d+)\s*[.．:：]", re.IGNORECASE)
MIN_TEXT_CHARS = 500          # 全文低于此字符数 → 判疑似扫描版（无文本层），告警


# ---- 图注识别 ----------------------------------------------------------------
def match_caption(block_text: str, include_supp: bool):
    """返回 (num, is_supp) 或 None。只认块首的编号样式，正文交叉引用不会命中。"""
    text = " ".join((block_text or "").split())
    m = MAIN_FIG_PAT.match(text)
    if m and len(text.split()) >= MIN_CAPTION_WORDS:
        return int(m.group(2)), False
    if include_supp:
        m = SUPP_FIG_PAT.match(text)
        if m and len(text.split()) >= MIN_CAPTION_WORDS:
            return int(m.group(2)), True
    return None


def find_captions(doc, include_supp: bool) -> list[dict]:
    """按页序扫描文本块，定位主图（可选补充图）图注；同名编号只保留首次出现。"""
    seen: set[tuple[bool, int]] = set()
    captions: list[dict] = []
    for pno in range(doc.page_count):
        for b in doc[pno].get_text("blocks"):
            hit = match_caption(b[4], include_supp)
            if hit is None:
                continue
            num, is_supp = hit
            key = (is_supp, num)
            if key in seen:
                continue
            seen.add(key)
            captions.append({
                "label": ("Figure S" if is_supp else "Figure ") + str(num),
                "num": num,
                "is_supp": is_supp,
                "page": pno,                      # 0-based
                "rect": [round(v, 1) for v in b[:4]],  # x0, y0, x1, y1（pt）
                "caption": " ".join((b[4] or "").split())[:500],
            })
    return captions


# ---- 图区域裁剪 --------------------------------------------------------------
def crop_region(doc, pno: int, rect: fitz.Rect, zoom: float) -> fitz.Pixmap:
    page = doc[pno]
    clip = fitz.Rect(
        max(page.rect.x0, rect.x0), max(page.rect.y0, rect.y0),
        min(page.rect.x1, rect.x1), min(page.rect.y1, rect.y1),
    )
    return page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip)


def figure_clip(doc, pno: int, cap_rect: list[float], header_margin: float,
                pad: float) -> fitz.Rect:
    """图注在图下方（主流期刊版式）→ 裁剪区域 = 页顶 header 以下到图注下缘。
    图注横跨整页宽 → 裁整页宽；否则按图注所在列宽裁。"""
    page = doc[pno]
    r = page.rect
    wide = (cap_rect[2] - cap_rect[0]) > FULL_WIDE_RATIO * r.width
    x0 = r.x0 if wide else max(r.x0, cap_rect[0] - pad)
    x1 = r.x1 if wide else min(r.x1, cap_rect[2] + pad)
    return fitz.Rect(x0, r.y0 + header_margin, x1, cap_rect[3] + pad)


def full_page_clip(doc, pno: int, header_margin: float) -> fitz.Rect:
    r = doc[pno].rect
    return fitz.Rect(r.x0, r.y0 + header_margin, r.x1, r.y1)


# ---- 主流程 ------------------------------------------------------------------
def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="paper-digest 提取：PDF → 文本 + 逐图 PNG + 清单")
    ap.add_argument("--pdf", required=True, type=Path, help="输入 PDF 路径（只读）")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="输出目录，默认 <PDF 同目录>/<PDF 名>_digest/")
    ap.add_argument("--zoom", type=float, default=DEFAULT_ZOOM, help="渲染倍率")
    ap.add_argument("--max-figs", type=int, default=0, help="最多裁前 N 张主图，0=全部")
    ap.add_argument("--include-supp", action="store_true", help="含补充图（Figure S*）")
    ap.add_argument("--pages", default="", help="手动指定图所在页（1-based 逗号分隔，如 4,6,8），整页裁剪，绕过图注检测")
    ap.add_argument("--header-margin", type=float, default=DEFAULT_HEADER_MARGIN)
    ap.add_argument("--caption-pad", type=float, default=DEFAULT_CAPTION_PAD)
    args = ap.parse_args(argv)

    pdf = args.pdf.resolve()
    if not pdf.is_file():
        sys.exit(f"[paper-digest] 找不到 PDF：{pdf}")
    outdir = (args.outdir or pdf.parent / (pdf.stem + "_digest")).resolve()
    extract_dir = outdir / "extract"
    fig_dir = extract_dir / "figures"
    fig_dir.mkdir(parents=True, exist_ok=True)

    doc = fitz.open(pdf)
    if doc.needs_pass:
        sys.exit("[paper-digest] PDF 已加密，无法读取；请先解密。")

    # -- Step 1: 全文文本（逐页标记，供 LLM 精读与页码回溯）--------------------
    text_file = extract_dir / "paper_text.md"
    with open(text_file, "w", encoding="utf-8") as f:
        for i in range(doc.page_count):
            f.write(f"\n\n<!-- ===== PAGE {i + 1} ===== -->\n\n")
            f.write(doc[i].get_text("text"))

    # -- Step 2: 逐图裁剪 -------------------------------------------------------
    figures: list[dict] = []
    if args.pages.strip():
        for p in (int(x) for x in args.pages.split(",") if x.strip()):
            pno = p - 1
            if not 0 <= pno < doc.page_count:
                print(f"[paper-digest] 跳过越界页 {p}")
                continue
            png = fig_dir / f"page{p:02d}.png"
            crop_region(doc, pno, full_page_clip(doc, pno, args.header_margin),
                        args.zoom).save(str(png))
            figures.append({"label": f"Page {p}", "num": p, "page": pno,
                            "png": str(png), "caption": ""})
    else:
        caps = find_captions(doc, args.include_supp)
        if args.max_figs > 0:
            caps = caps[:args.max_figs]
        for c in caps:
            png = fig_dir / f"fig{c['num']:02d}.png"
            clip = figure_clip(doc, c["page"], c["rect"], args.header_margin,
                               args.caption_pad)
            crop_region(doc, c["page"], clip, args.zoom).save(str(png))
            figures.append({k: c[k] for k in ("label", "num", "page", "caption")}
                           | {"png": str(png), "clip": [round(v, 1) for v in clip]})

    # -- Step 3: 清单落盘（checkpoint，供 LLM 对账与质检门复核）----------------
    manifest = {
        "pdf": str(pdf),
        "n_pages": doc.page_count,
        "text_file": str(text_file),
        "zoom": args.zoom,
        "figures": figures,
    }
    manifest_file = extract_dir / "manifest.json"
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                             encoding="utf-8")

    # -- Step 4: 摘要输出 --------------------------------------------------------
    n_chars = len(text_file.read_text(encoding="utf-8"))
    if n_chars < MIN_TEXT_CHARS:
        print(f"[paper-digest][警告] 全文仅 {n_chars} 字符，疑似扫描版 PDF（无文本层）。"
              "请先 OCR 或更换文字版 PDF，否则解读质量无保障。")
    print(f"[paper-digest] PDF：{pdf.name}（{doc.page_count} 页，{n_chars} 字符）")
    print(f"[paper-digest] 文本：{text_file}")
    print(f"[paper-digest] 图注定位：{len(figures)} 张 → {fig_dir}")
    for fig in figures:
        print(f"  - {fig['label']}（第 {fig['page'] + 1} 页）→ {Path(fig['png']).name}")
    print(f"[paper-digest] 清单：{manifest_file}")
    print(f"[paper-digest] 完成。产物见 {outdir}")


if __name__ == "__main__":
    main()
