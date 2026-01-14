# Paper Storyteller

将 arXiv 论文转换为精美的故事化讲解网页。

## 使用方法

```
/paper-storyteller <arxiv_url_or_id> [--lang zh|en]
```

## 参数

- `arxiv_url_or_id`: arXiv 论文链接或 ID（必需）
  - 例如: `https://arxiv.org/abs/2311.14405` 或 `2311.14405`
- `--lang`: 输出语言，默认中文 `zh`，可选英文 `en`

## 示例

```bash
# 使用 arXiv 链接
/paper-storyteller https://arxiv.org/abs/2311.14405

# 使用 arXiv ID
/paper-storyteller 2103.00020

# 生成英文版本
/paper-storyteller 2311.14405 --lang en
```

## 执行步骤

1. 安装依赖（如果未安装）:
   ```bash
   pip install -r requirements.txt
   ```

2. 运行脚本:
   ```bash
   python paper_storyteller_skill.py <arxiv_url_or_id> --lang <language> --api-key $GOOGLE_API_KEY
   ```

## 输出

生成的 HTML 网页包含：
- 📖 论文标题和作者信息
- 🎯 网络架构图（自动从 PDF 提取）
- 💡 AI 生成的通俗解读
- ✨ 关键创新点
- 🌍 应用场景
- 📝 论文十问
- 🔍 审稿人视角
- 💡 潜在改进方向

## 环境要求

- Python 3.8+
- Gemini API Key（设置 `GOOGLE_API_KEY` 环境变量）
- 首次运行会自动下载 PaddleOCR 模型（约 200MB）
