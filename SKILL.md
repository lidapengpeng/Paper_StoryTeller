---
name: paper-storyteller
description: |
  将 arXiv 神经网络论文转换为精美的故事化讲解网页。
  自动提取论文的网络架构图（Pipeline/Architecture），使用 Gemini AI 生成通俗易懂的中文讲解。
  适用于：解读 arXiv 论文、生成技术博客、制作学术分享页面。
  触发词：arxiv、论文讲解、paper storyteller、生成论文网页、提取架构图
---

# Paper Storyteller

将 arXiv 神经网络论文转换为带有 Pipeline 结构图的精美讲解网页。

## 核心功能

1. **自动获取论文** - 从 arXiv 获取论文元数据和 PDF
2. **智能提取架构图** - 使用 PaddleOCR PP-DocLayoutV2 自动识别并提取论文中的网络结构图
3. **AI 生成讲解** - 使用 Gemini 2.0 生成通俗易懂的论文解读
4. **生成精美网页** - 响应式 HTML，支持中英文

## 使用方法

```bash
# 基本用法
python paper_storyteller_skill.py <arxiv_url_or_id>

# 指定语言（默认中文）
python paper_storyteller_skill.py https://arxiv.org/abs/2311.14405 --lang zh

# 指定 API Key
python paper_storyteller_skill.py 2311.14405 --api-key YOUR_GEMINI_KEY
```

## 环境要求

1. **Python 3.8+**
2. **Gemini API Key** - 设置环境变量 `GOOGLE_API_KEY`
3. **PaddleOCR 模型** - 首次运行会自动下载 PP-DocLayoutV2 模型（约 200MB）

## 安装依赖

```bash
pip install -r requirements.txt
```

## 输出内容

生成的 HTML 网页包含：
- 论文标题和作者信息
- 原始摘要
- **网络架构图**（自动从 PDF 提取）
- AI 生成的通俗解读（3段故事化讲解）
- 关键创新点（5个要点）
- 应用场景

## 文件结构

```
paper-storyteller/
├── SKILL.md                    # Skill 定义文件
├── paper_storyteller_skill.py  # 主入口
├── requirements.txt            # Python 依赖
├── scripts/                    # 核心模块
│   ├── arxiv_fetcher.py        # arXiv 论文获取
│   ├── doclayout_extractor.py  # 架构图提取（PaddleOCR）
│   ├── html_builder.py         # HTML 生成
│   ├── image_generator.py      # AI 图片生成（可选）
│   ├── storyteller.py          # Gemini 故事生成
│   └── utils.py                # 工具函数
└── models/                     # 模型文件（首次运行自动下载）
```

## 技术栈

- **PaddleOCR PP-DocLayoutV2** - 文档布局分析，精准提取架构图
- **Gemini 2.0 Flash** - AI 生成论文讲解
- **PyMuPDF** - PDF 高质量渲染（DPI 300）
- **arXiv API** - 论文元数据获取

## 特点

- ✅ 真实架构图提取（非 AI 生成）
- ✅ 智能选择最佳架构图（基于位置、面积、宽高比评分）
- ✅ 高清图片输出（DPI 300）
- ✅ Base64 图片嵌入，单文件 HTML
- ✅ 响应式设计，支持移动端
- ✅ 中英文双语支持
