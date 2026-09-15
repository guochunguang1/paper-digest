# Example · Circulation TRIM31–LOX-1 动脉粥样硬化论文全流程解读

> 真实跑通的运行 trace（2026-09-15，ZCode，macOS arm64，python 3.9.6 + PyMuPDF 1.26.5）。

## 任务

解读用户文献目录下的一篇 Circulation 研究论文，产出中文深度解读 HTML。

## 输入

`Macrophage Specific E3 Ubiquitin Lig Source Circulation SO 2025.pdf`（21 页，英文，Circulation 2025;153，DOI 10.1161/CIRCULATIONAHA.125.076514）

## 所选路径与关键决策

1. **Step 1 提取**：默认参数跑 `script-skeleton.py`。21 页、91882 字符；图注定位 **8 张主图**（Figure 1–8，均在偶数页，图注在图下方），全部按"页顶 header 以下 → 图注下缘"裁剪成功，宽图注走整页宽分支。无扫描版告警。
2. **Step 2 精读**：该刊首页无字面 "Abstract" 标题，但结构化摘要（BACKGROUND/METHODS/RESULTS/CONCLUSIONS）在首页——LLM 按语义识别，验证了"不依赖关键词匹配"的设计。
3. **Step 3 逐图看图**：8 张裁剪图逐一视觉核验，裁剪全部干净（面板完整、图注在框内）；解读结合正文引用段落写"做了什么/怎么做/说明什么"，引用图中真实 P 值（如 Fig2H P=0.0002、Fig6E LC-MS/MS 定位 K12）。
4. **Step 4 组装**：按 report-template.html 版式生成，标题/摘要中英对照，图片 base64 内嵌。
5. **Step 5 质检门**：6 章节、无占位符、8==8==8 图数一致、双语在场 → PASS。产物 10 MB。

## 输出

- `<PDF>_digest/Macrophage Specific E3 Ubiquitin Lig Source Circulation SO 2025_digest.html`（10 MB，单文件自包含）
- `extract/`：paper_text.md（92k 字符）+ manifest.json（8 图清单）+ figures/fig01–08.png（0.3–1.3 MB/张）

## 遇到的问题

- 大图的图注带 "(Continued)"，正文跨页续写；manifest 截取的是首页图注块前 500 字，续文在下一页——不影响裁图（图主体在一页内），解读时用正文对应段落补全语义。已记入 errorbook。
- 8 张 158dpi PNG 内嵌后 HTML 达 10 MB；分享带宽受限时可用 `--zoom 1.5` 重跑，体积约降一半。
