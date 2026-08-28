---
name: pdf-recognition
description: >-
  理解任意 PDF（合同、论文、财报、报告、扫描件）。三级降级链——文字层直取 →
  多模态模型自己读图（若支持图像输入）→ 本地离线 OCR（RapidOCR，pip 库、零服务器部署）。
  全程本地运行，对模型能力自适应。触发词——理解PDF、读PDF、解析PDF、PDF总结、PDF转文字、
  扫描件识别、这份PDF讲了什么、帮我看看这个PDF。不适用场景——PDF 编辑/生成/合并拆分、
  PDF 密码破解、纯图片语义理解（本地 OCR 只能给图中文字）。
---

# pdf-recognition

不部署任何 OCR 服务器，理解所有 PDF。核心原则：**能走文本绝不走图，模型能看图就不用 OCR，OCR 是最后兜底**。

## 环境准备（首次使用前）

```bash
pip install -r scripts/requirements.txt
```

依赖只有两个：`pymupdf`（解析+渲染）、`rapidocr_onnxruntime`（本地 OCR，ONNX Runtime CPU 推理，模型文件约 15MB 首次自动下载，之后完全离线）。

## 执行流程

### 第 0 步：体检（永远先做）

```bash
python scripts/probe.py <file.pdf>
```

返回 JSON：页数、是否加密、文字层覆盖率、无文字层的页码列表、文档大纲。

- 加密 → 请用户提供密码，不要硬撞。
- 覆盖率 ≥ 70% → 走【通道 A】。
- 存在无文字层的页 → 这些页走【通道 B → C 瀑布】。

### 通道 A：文字层直取（首选，100% 准确）

```bash
python scripts/extract_text.py <file.pdf>                 # 全文
python scripts/extract_text.py <file.pdf> --pages 3-8     # 指定页
python scripts/extract_text.py <file.pdf> -o out.md       # 写文件
```

输出文本直接阅读理解。

### 通道 B：模型自己读图（仅当模型支持图像输入）

对无文字层的页先渲染：

```bash
python scripts/render_pages.py <file.pdf> --pages 3,5,7-9 --dpi 150 --outdir rendered/
```

然后用 `read_image` 逐页读图理解。

**判定"模型识别不了"的条件（任一命中即降级到通道 C）：**

1. `read_image` 调用直接报错（当前模型不接受图像输入）；
2. 模型返回内容自述"无法查看图片"或输出明显为空/乱码；
3. 先试 1 页，若失败则**该文档所有无文字层页整批走通道 C**，不要逐页重试浪费时间。

### 通道 C：本地 OCR 兜底（对模型零要求）

```bash
python scripts/ocr_pages.py <file.pdf> --pages 3,5,7-9 --dpi 200
python scripts/ocr_pages.py --images rendered/page-3.png rendered/page-5.png
```

RapidOCR 在进程内完成识别（不是服务、没有端口），脚本按坐标聚类还原文本行为近似段落，输出纯文本供阅读。置信度低于 0.6 的行会标注 `[低置信度]`——**不要盲信这些行，回答用户时注明不确定**。

**内存注意（小内存服务器必读）**：通道 C 是唯一吃内存的通道（ONNX Runtime + OpenCV 基线约 500MB~1GB）。通道 A/B 仅几十 MB。低内存环境下：

1. 优先走通道 A/B，**只有模型不支持图像时才用通道 C**；
2. OCR 时把 `--dpi` 降到 150（默认 200），像素量减少约 44%，中文印刷体识别率基本无损；
3. 按 `--pages` 分批处理（如每次 5 页），脚本已逐页释放位图并单线程运行；
4. 将 opencv 换成 headless 版（见 requirements.txt 注释），省 100MB+；
5. 若进程仍被杀，先用 `dmesg | grep -i oom` 确认是 OOM Killer，再考虑加 swap 或分批更细。

## 长文档策略（>50 页）

1. 先用 probe 输出的大纲向用户确认要看哪部分；
2. 用户无指定时，按大纲分块，逐块抽取后做 map-reduce 摘要；
3. 无大纲的长文档按 20 页一块处理，避免上下文溢出。

## 混合页（覆盖率 30%~70%）

文本层与 OCR 结果可能重叠。处理原则：以文本层为主，仅对 OCR 输出中**文本层缺失的区域**做补充，合并前去重。

## 能力边界（必须对用户诚实）

- 印刷体扫描件：中英文识别率 95%+，可放心理解。
- 手写体、复杂数学公式、嵌套表格：OCR 易错，结果标注低置信度并提示用户。
- 纯图表/示意图：通道 B 可用时由模型直接理解；只能用通道 C 时，输出中标注 `[本页含图形，本地 OCR 无法解析图形语义]`。
