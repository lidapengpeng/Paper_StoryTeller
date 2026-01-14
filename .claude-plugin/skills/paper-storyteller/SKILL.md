---
name: paper-storyteller
description: |
  将 arXiv 神经网络论文转换为精美的故事化讲解网页。
  自动提取论文的网络架构图（Pipeline/Architecture），使用 Gemini AI 生成通俗易懂的中文讲解。
  适用于：解读 arXiv 论文、生成技术博客、制作学术分享页面。
triggers:
  - arxiv
  - 论文讲解
  - paper storyteller
  - 生成论文网页
  - 提取架构图
  - 解读论文
  - 讲解论文
---

# Paper Storyteller

将 arXiv 神经网络论文转换为带有 Pipeline 结构图的精美讲解网页。

## 使用方法

当用户提供 arXiv 论文链接或 ID 时，执行以下步骤：

### 1. 安装依赖（首次使用）

```bash
cd <plugin_directory>
pip install -r requirements.txt
```

### 2. 运行脚本生成讲解网页

```bash
python paper_storyteller_skill.py <arxiv_url_or_id> --lang zh --api-key $GOOGLE_API_KEY
```

参数说明：
- `<arxiv_url_or_id>`: arXiv 论文链接或 ID，例如 `https://arxiv.org/abs/2311.14405` 或 `2311.14405`
- `--lang`: 输出语言，`zh` 中文（默认），`en` 英文
- `--api-key`: Gemini API Key（或设置环境变量 `GOOGLE_API_KEY`）

### 3. 查看输出

脚本会在 `output/` 目录生成 HTML 文件，可以用浏览器打开查看。

## 输出内容

生成的 HTML 网页包含：
- 📖 论文标题和作者信息
- 🎯 网络架构图（自动从 PDF 提取，非 AI 生成）
- 💡 AI 生成的通俗解读
- ✨ 关键创新点
- 🌍 应用场景
- 📝 论文十问
- 🔍 审稿人视角
- 💡 潜在改进方向

## 环境要求

- Python 3.8+
- Gemini API Key
- 首次运行会自动下载 PaddleOCR 模型（约 200MB）
