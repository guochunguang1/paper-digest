# paper-digest 错题本

> 运行中发现的问题、坑、修复，只追加不删改。随 PR 提交作为变更说明。
> 查历史用 grep 关键词，不全读。
> **仅记本 skill 局部坑**；跨 skill/跨包的共享坑（包 bug、环境/编译/依赖、API 误用、平台差异）登记到全局 `skills/sogen-skill-dev/PITFALLS.md`（判据见 `references/pitfalls-policy.md`）。

## 条目格式

```
### YYYY-MM-DD · <一句话现象>
- 现象：<报错/异常行为/数据问题>
- 根因：<定位到的真实原因>
- 修复：<在 skill 哪一层改了什么>
- 需改底层包？：是 / 否
- 状态：resolved / resolved-in-source / 已转交包维护 / 待包发布后同步
```

## 记录

### 2026-09-15 · 目标机 Python 无 PyMuPDF，需装包
- 现象：`import fitz` 失败，macOS 系统 Python 3.9.6 默认无 PyMuPDF。
- 根因：非标准库，各机器需自行安装。
- 修复：SKILL.md「前置依赖」写明安装命令 `python3 -m pip install --user PyMuPDF`；脚本对 ImportError 给出带安装命令的明确退出提示，而不是裸 traceback。
- 需改底层包？：否
- 状态：resolved

### 2026-09-15 · 大图图注 "(Continued)" 跨页，manifest 图注文本不完整
- 现象：Circulation 大图的图注以 "(Continued)" 结束、续文在下一页；manifest 的 `caption` 只含首页图注块前 500 字符，缺续文。
- 根因：PyMuPDF 文本块按页切分，跨页图注定然断裂；这是版式事实而非 bug。
- 修复：不影响裁图（图主体在单页内，裁剪框按首页图注定位）。解读语义由 LLM 用正文引用该图的段落补全；SKILL.md Step 2 已规定"按语义而非关键词识别摘要"，同理适用于图注。
- 需改底层包？：否
- 状态：resolved

### 2026-09-15 · 8 张图内嵌后 HTML 体积达 10 MB
- 现象：默认 `--zoom 2.2`（≈158dpi）下 8 张主图 PNG 共约 8 MB，base64 膨胀 1/3 后 HTML 达 10 MB。
- 根因：base64 编码体积 +33%；组学类期刊多面板图本身信息密度大。
- 修复：接受为默认（质量优先）；分享带宽受限时以 `--zoom 1.5` 重跑提取即可，模板与流程无需改动。
- 需改底层包？：否
- 状态：resolved（参数化解决）

### 2026-09-15 · 开发期误答：ZCode 技能显式调用前缀是 `$` 不是 `/`
- 现象：用户敲 `/paper-digest` 无补全；截图显示技能列表均以 `$` 前缀呈现（`$patent-writing` 等）。
- 根因：ZCode 客户端中 `$` = 技能（skill）调用，`/` = slash 命令；开发 assist 误按通用惯例把 `$` 当模板变量。另一叠加因素：技能列表会话启动时扫描，会话中新建的 skill 当轮不可见。
- 修复：无 skill 文件改动。使用文档/沟通口径修正——新会话中用 `$paper-digest` 显式调用，或自然语言自动触发。
- 需改底层包？：否
- 状态：resolved
