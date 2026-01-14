# Paper Storyteller

> 将 arXiv 上的深度学习相关的论文，转换为精美的故事化讲解网页，本工程基于Vibe Coding制作；Cursor + Opus 4.5 model;
> 有问题欢迎提issue；

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 功能特点

- 🎯 **智能架构图提取** - 使用 PaddleOCR PP-DocLayoutV2 自动识别论文中的网络结构图
- 🤖 **AI 故事化讲解** - Gemini 2.0 生成通俗易懂的论文解读
- 🎨 **精美网页输出** - 响应式设计，支持移动端
- 🌍 **中英文双语** - 支持中文和英文输出

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# Linux/Mac
export GOOGLE_API_KEY="your_gemini_api_key"

# Windows PowerShell
$env:GOOGLE_API_KEY="your_gemini_api_key"
```

或创建 `.env` 文件：
```
GOOGLE_API_KEY=your_gemini_api_key
```

### 3. 运行

```bash
# 使用 arXiv 链接
python paper_storyteller_skill.py https://arxiv.org/abs/2312.10035

# 使用 arXiv ID
python paper_storyteller_skill.py 2311.14405

# 指定语言（默认中文）
python paper_storyteller_skill.py 2311.14405 --lang en

# 指定输出目录
python paper_storyteller_skill.py 2311.14405 --output ./my_output
```

## 输出示例

生成的 HTML 网页包含：

| 内容 | 说明 |
|------|------|
| 📖 论文标题 | 标题、作者、发表时间 |
| 📝 原始摘要 | 论文的 Abstract |
| 🎯 网络架构图 | 自动从 PDF 提取的 Pipeline 图 |
| 💡 通俗解读 | AI 生成的 3 段故事化讲解 |
| ✨ 关键创新 | 5 个核心创新点 |
| 🌍 应用场景 | 潜在应用领域 |

## 项目结构

```
paper-storyteller/
├── paper_storyteller_skill.py  # 主入口
├── SKILL.md                    # Claude Code Skill 定义
├── requirements.txt            # Python 依赖
├── scripts/
│   ├── arxiv_fetcher.py        # arXiv API 封装
│   ├── doclayout_extractor.py  # 架构图提取（核心）
│   ├── html_builder.py         # HTML 页面生成
│   ├── image_generator.py      # AI 图片生成（可选）
│   ├── storyteller.py          # Gemini 故事生成
│   └── utils.py                # 工具函数
└── models/                     # PaddleOCR 模型（首次运行自动下载）
```

## 技术栈

| 组件 | 用途 |
|------|------|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 文档布局分析，架构图提取 |
| [Gemini 2.0](https://ai.google.dev/) | AI 内容生成 |
| [PyMuPDF](https://pymupdf.readthedocs.io/) | PDF 高质量渲染 |
| [arXiv API](https://arxiv.org/help/api) | 论文元数据获取 |

## 架构图提取原理

1. **PDF 渲染** - 使用 PyMuPDF 以 DPI 300 渲染 PDF 页面
2. **布局检测** - PP-DocLayoutV2 检测页面中的 `image` 区域
3. **智能评分** - 基于以下规则选择最佳架构图：
   - 位置：第 2-3 页的图优先（通常是方法图）
   - 面积：大图优先
   - 宽高比：宽图（>2:1）更可能是流程图
4. **高清裁剪** - 直接从高 DPI 渲染中裁剪

## 环境要求

- Python 3.8+
- CUDA（可选，GPU 加速）
- 约 500MB 磁盘空间（模型文件）

## 许可证

MIT License

## 致谢

- [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) - 优秀的文档分析工具
- [Google Gemini](https://ai.google.dev/) - 强大的 AI 模型
