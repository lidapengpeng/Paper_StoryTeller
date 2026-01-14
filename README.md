# Paper Storyteller 📖✨

> **3 分钟读懂一篇 arXiv 论文** - 将深度学习论文转换为精美的故事化讲解网页
> 
> ⭐ 如果觉得有用，请给个 Star！

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ 功能特点

- 🎯 **智能架构图提取** - 使用 PaddleOCR PP-DocLayoutV2 自动识别论文中的网络结构图
- 🤖 **AI 故事化讲解** - Gemini 2.0 生成通俗易懂的论文解读
- 🎨 **精美网页输出** - 响应式设计，支持移动端
- 🌍 **中英文双语** - 支持中文和英文输出

## 🚀 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/lidapengpeng/Paper_StoryTeller.git
cd Paper_StoryTeller
```

### 2. 创建环境（推荐）

```bash
# 创建 conda 环境
conda create -n paper_storyteller python=3.10 -y
conda activate paper_storyteller

# 安装依赖
pip install -r requirements.txt
```

<details>
<summary>💡 不使用 conda？</summary>

直接安装依赖：
```bash
pip install -r requirements.txt
```
</details>

### 3. 下载模型（约 204MB）

```bash
# 创建模型目录
mkdir -p models/PaddleOCR-VL/PP-DocLayoutV2
cd models/PaddleOCR-VL/PP-DocLayoutV2

# 下载 3 个必需文件
wget https://huggingface.co/PaddlePaddle/PaddleOCR-VL/resolve/main/PP-DocLayoutV2/inference.pdiparams
wget https://huggingface.co/PaddlePaddle/PaddleOCR-VL/resolve/main/PP-DocLayoutV2/inference.pdmodel
wget https://huggingface.co/PaddlePaddle/PaddleOCR-VL/resolve/main/PP-DocLayoutV2/inference.yml

cd ../../..
```

<details>
<summary>💡 Windows 用户或下载慢？</summary>

直接浏览器下载这 3 个文件，放到 `models/PaddleOCR-VL/PP-DocLayoutV2/` 目录：
- [inference.pdiparams](https://huggingface.co/PaddlePaddle/PaddleOCR-VL/resolve/main/PP-DocLayoutV2/inference.pdiparams?download=true) (202MB)
- [inference.pdmodel](https://huggingface.co/PaddlePaddle/PaddleOCR-VL/resolve/main/PP-DocLayoutV2/inference.pdmodel?download=true) (1.4MB)
- [inference.yml](https://huggingface.co/PaddlePaddle/PaddleOCR-VL/resolve/main/PP-DocLayoutV2/inference.yml?download=true) (1.5KB) - 点击后 Ctrl+S 保存

</details>

### 4. 运行

```bash
# 直接传入 API Key
python paper_storyteller_skill.py https://arxiv.org/abs/2311.14405 --api-key YOUR_GEMINI_API_KEY

# 或使用 arXiv ID
python paper_storyteller_skill.py 2311.14405 --api-key YOUR_GEMINI_API_KEY

# 生成英文版本
python paper_storyteller_skill.py 2311.14405 --lang en --api-key YOUR_GEMINI_API_KEY
```

> 💡 **API Key 获取**：访问 https://ai.google.dev/ 获取免费的 Gemini API Key

## 📄 输出内容

生成的 HTML 网页包含：

| 内容 | 说明 |
|------|------|
| 📖 爆款标题 | AI 生成的吸引眼球的标题 |
| 💡 导读 | 引人入胜的开场白 |
| 🎯 网络架构图 | 自动从 PDF 提取的 Pipeline 图 |
| 🔧 方法详解 | 分层次的技术讲解 |
| ✨ 关键创新 | 核心创新点总结 |
| 📝 论文十问 | 深度理解论文的 10 个问题 |
| 🔍 审稿人视角 | 批判性分析 |
| 💡 改进方向 | 潜在的研究方向 |

## 📁 项目结构

```
Paper-Storyteller/
├── paper_storyteller_skill.py  # 主入口（2000+ 行，包含所有核心逻辑）
├── requirements.txt            # Python 依赖
├── README.md                   # 项目说明
├── LICENSE                     # MIT 许可证
└── scripts/                    # 核心模块
    ├── arxiv_fetcher.py        # arXiv API 封装
    ├── doclayout_extractor.py  # 架构图提取（PaddleOCR）
    └── utils.py                # 工具函数
```

## 🛠 技术栈

| 组件 | 用途 |
|------|------|
| [PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR) | 文档布局分析，架构图提取 |
| [Gemini 2.0](https://ai.google.dev/) | AI 内容生成 |
| [Nano Banana](https://ai.google.dev/) | AI 配图生成 |
| [PyMuPDF](https://pymupdf.readthedocs.io/) | PDF 高质量渲染 |

## 🔬 架构图提取原理

1. **PDF 渲染** - PyMuPDF 以 DPI 300 渲染页面
2. **布局检测** - PP-DocLayoutV2 检测 `image` 区域
3. **智能评分** - 基于位置、面积、宽高比选择最佳架构图
4. **高清裁剪** - 直接从高 DPI 渲染中裁剪

## ❓ 常见问题

<details>
<summary><b>报错"模型文件缺失"？</b></summary>

确保 `models/PaddleOCR-VL/PP-DocLayoutV2/` 目录下有这 3 个文件：
- `inference.pdiparams`
- `inference.pdmodel`
- `inference.yml`

参考上方"下载模型"步骤。
</details>

<details>
<summary><b>PaddlePaddle 安装失败？</b></summary>

参考官方安装指南：https://www.paddlepaddle.org.cn/install/quick

Mac M1/M2 用户：
```bash
conda install paddlepaddle -c paddle
```
</details>

<details>
<summary><b>API 调用报错？</b></summary>

1. 确认 API Key 正确设置
2. 确认 Gemini API 有访问权限
3. 检查 API 配额是否用尽
</details>

## 📜 许可证

MIT License

## 🙏 致谢

- [PaddlePaddle/PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)
- [Google Gemini](https://ai.google.dev/)

---

**作者**：Dapengpeng · **联系**：hellodapengya@gmail.com
