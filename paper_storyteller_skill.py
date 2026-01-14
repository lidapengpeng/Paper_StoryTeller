#!/usr/bin/env python3
"""
Paper Storyteller - Claude Code Skill
将 arXiv 论文转换为带有论文图片（结构图、流程图、结果图）的网页

使用本地 PaddleOCR-VL PP-DocLayoutV2 提取论文图片
使用 Gemini 生成丰富的故事化内容
使用 Imagen 4.0 生成配图
"""

import os
import sys
import base64
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

# 添加 scripts 到路径
sys.path.insert(0, str(Path(__file__).parent / "scripts"))

import google.generativeai as genai
from google import genai as genai_client
from google.genai import types
from loguru import logger

import fitz  # PyMuPDF

from scripts.arxiv_fetcher import ArXivFetcher
from scripts.doclayout_extractor import DocLayoutExtractor as FigureExtractor
from scripts.utils import setup_logging, format_authors


class PaperStorytellerSkill:
    """
    Paper Storyteller Skill

    功能：
    1. 从 arXiv 获取论文
    2. 使用本地 PP-DocLayoutV2 提取论文中的图片（figure/chart）
    3. 使用 Gemini 生成简洁的论文解读
    4. 生成带图片的精美 HTML 网页
    """

    def __init__(self, gemini_api_key: str, output_dir: str = "output"):
        """
        初始化

        Args:
            gemini_api_key: Gemini API 密钥
            output_dir: 输出目录
        """
        self.gemini_api_key = gemini_api_key
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # 初始化 Gemini (文本生成)
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash-exp')
        
        # 初始化 Imagen (图片生成)
        self.imagen_client = genai_client.Client(api_key=gemini_api_key)

        # 初始化组件
        self.arxiv_fetcher = ArXivFetcher()
        self.figure_extractor = FigureExtractor(output_dir=str(self.output_dir / "figures"))
        
        # 图片输出目录
        self.images_dir = self.output_dir / "images"
        self.images_dir.mkdir(parents=True, exist_ok=True)

        logger.info("✅ Paper Storyteller Skill 初始化完成")

    def _extract_method_section(self, pdf_path: str) -> Optional[str]:
        """
        从 PDF 提取 Method/Approach/Methodology 章节的文本
        
        Args:
            pdf_path: PDF 文件路径
            
        Returns:
            Method 章节文本，如果未找到则返回 None
        """
        try:
            doc = fitz.open(pdf_path)
            full_text = ""
            
            # 提取所有页面文本
            for page in doc:
                full_text += page.get_text()
            
            doc.close()
            
            # 常见的 Method 章节标题模式
            method_patterns = [
                r'(?i)\n\s*(?:\d+\.?\s*)?(?:method|methodology|approach|proposed method|our method|framework|model|architecture)\s*\n',
                r'(?i)\n\s*(?:\d+\.?\s*)?(?:the proposed|our approach|technical approach)\s*\n',
                r'(?i)\n\s*III\.?\s*(?:method|methodology|approach)\s*\n',  # IEEE 格式
                r'(?i)\n\s*3\.?\s*(?:method|methodology|approach)\s*\n',    # 数字格式
            ]
            
            # 结束章节的模式
            end_patterns = [
                r'(?i)\n\s*(?:\d+\.?\s*)?(?:experiment|evaluation|result|implementation|conclusion|discussion|related work)\s*\n',
                r'(?i)\n\s*(?:IV|V|4|5)\.?\s*(?:experiment|evaluation|result)\s*\n',
            ]
            
            import re
            
            method_start = None
            method_end = None
            
            # 查找 Method 章节开始
            for pattern in method_patterns:
                match = re.search(pattern, full_text)
                if match:
                    method_start = match.end()
                    break
            
            if method_start is None:
                return None
            
            # 查找 Method 章节结束
            for pattern in end_patterns:
                match = re.search(pattern, full_text[method_start:])
                if match:
                    method_end = method_start + match.start()
                    break
            
            # 如果没找到结束，取接下来的 8000 字符
            if method_end is None:
                method_end = min(method_start + 8000, len(full_text))
            
            method_text = full_text[method_start:method_end].strip()
            
            # 清理文本
            method_text = re.sub(r'\s+', ' ', method_text)  # 合并多余空白
            method_text = method_text[:6000]  # 限制长度
            
            return method_text if len(method_text) > 200 else None
            
        except Exception as e:
            logger.warning(f"提取 Method 章节失败: {e}")
            return None

    def process_paper(self, arxiv_url_or_id: str, language: str = "zh") -> str:
        """
        处理论文：提取图片 + 生成丰富内容 + 生成网页

        Args:
            arxiv_url_or_id: arXiv URL 或 ID
            language: 语言 ("zh" 或 "en")

        Returns:
            生成的 HTML 文件路径
        """
        logger.info("="*70)
        logger.info("📖 Paper Storyteller - 开始处理")
        logger.info("="*70)

        # 1. 获取论文
        logger.info(f"\n📄 步骤 1/6: 获取论文 {arxiv_url_or_id}")
        metadata, pdf_path = self.arxiv_fetcher.fetch_and_download(arxiv_url_or_id)
        logger.success(f"   ✅ 论文: {metadata['title'][:50]}...")

        # 2. 提取 Pipeline 结构图
        logger.info(f"\n🎨 步骤 2/6: 使用 PaddleOCR 提取结构图")
        figures_result = self.figure_extractor.extract_from_pdf(pdf_path, max_pages=10)
        logger.success(f"   ✅ 提取了 {figures_result['total_figures']} 个图片")

        # 2.5. 提取 Method 章节文本
        logger.info(f"\n📝 步骤 2.5/6: 提取 Method 章节")
        method_text = self._extract_method_section(pdf_path)
        if method_text:
            logger.success(f"   ✅ 提取了 Method 章节 ({len(method_text)} 字符)")
        else:
            logger.warning("   ⚠️ 未找到 Method 章节，将使用摘要")

        # 3. 生成丰富内容（多次 API 调用）
        logger.info(f"\n✍️ 步骤 3/6: 生成论文解读 (语言: {language})")
        content = self._generate_rich_content(
            metadata, 
            language,
            method_text=method_text,
            pipeline_figure=figures_result.get('main_figure')
        )
        logger.success(f"   ✅ 内容生成完成")

        # 4. 生成配图（Hero + 导读 + 问题）
        logger.info(f"\n🖼️ 步骤 4/6: 生成 AI 配图")
        generated_images = self._generate_all_images(metadata, content, language)
        logger.success(f"   ✅ 生成了 {len(generated_images)} 张配图")

        # 5. 生成 HTML
        logger.info(f"\n🌐 步骤 5/6: 生成 HTML 网页")
        html_path = self._generate_html(
            metadata=metadata,
            content=content,
            figures=figures_result['figures'],
            main_figure=figures_result['main_figure'],
            generated_images=generated_images,
            language=language
        )
        logger.success(f"   ✅ 网页生成完成: {html_path}")

        logger.info("\n" + "="*70)
        logger.info("🎉 处理完成！")
        logger.info("="*70)

        return str(html_path)

    def _generate_rich_content(self, metadata: Dict, language: str, 
                                method_text: Optional[str] = None,
                                pipeline_figure: Optional[Path] = None) -> Dict[str, str]:
        """
        使用 Gemini 生成丰富内容（多次 API 调用）

        Args:
            metadata: 论文元数据
            language: 语言
            method_text: Method 章节文本（可选）
            pipeline_figure: Pipeline 结构图路径（可选）

        Returns:
            {
                'viral_title': 爆款标题,
                'hook_intro': 引人入胜的开头,
                'problem_statement': 问题陈述,
                'solution_overview': 解决方案概述,
                'architecture_description': 网络架构详细描述,
                'key_innovations': 关键创新点,
                'applications': 应用场景,
                'conclusion': 总结
            }
        """
        abstract = metadata['abstract']
        title = metadata['title']

        if language == "zh":
            # ===== 1. 爆款标题 =====
            logger.info("   [1/7] 生成爆款标题...")
            viral_title_prompt = f"""你是一位顶级科技自媒体编辑。请为这篇 AI 论文创作一个爆款标题。

## 严格要求
1. **长度**：15-25个中文字（必须严格遵守）
2. **格式**：必须包含一个核心英文术语（如模型名、技术名）
3. **禁止**：
   - 不要用"震惊"、"重磅"、"惊人"等陈词滥调
   - 不要用emoji
   - 不要用问号结尾的疑问句
   - 不要用"XX了解一下"句式

## 推荐技巧（选用1-2个）
- 对比反差："不用标注数据，也能超越监督学习"
- 数字冲击："4亿图文对训练出的视觉通才"
- 核心价值："让AI看懂任何图片的秘密武器"
- 悬念设置："OpenAI用自然语言重新定义计算机视觉"

## 论文信息
标题: {title}
摘要: {abstract[:400]}

直接输出一个标题（不要编号、不要解释）："""

            # ===== 2. 引人入胜的开头 =====
            logger.info("   [2/7] 生成引人入胜的开头...")
            hook_intro_prompt = f"""你是一位擅长讲故事的科技作者。请为这篇论文写一段引人入胜的导读。

## 内容要求
1. **开头**（第1段）：从一个具体场景或问题切入，让读者产生共鸣
2. **痛点**（第2段）：用生动语言描述当前技术的局限和困境
3. **解决方案**（第3段）：自然引出这篇论文的创新方案，让读者想继续往下读

## 格式要求
- 分成 2-3 个自然段落（每段用空行分隔）
- 每段 60-80 字，总共 150-200 字
- 保留关键英文术语
- 可以用类比、故事、数据等手法

论文标题: {title}
摘要: {abstract[:500]}

直接输出（用空行分段）："""

            # ===== 3. 问题陈述 =====
            logger.info("   [3/7] 生成问题陈述...")
            problem_prompt = f"""请用通俗易懂的语言解释这篇论文要解决的核心问题（100-150字）。

要求：
- 说明现有方法的不足之处
- 解释为什么这个问题重要
- 用生活化的例子帮助理解
- 保留关键英文术语

论文标题: {title}
摘要: {abstract[:600]}

直接输出问题陈述："""

            # ===== 4. 解决方案概述 =====
            logger.info("   [4/7] 生成解决方案概述...")
            solution_prompt = f"""请用通俗易懂的语言概述这篇论文的核心解决方案（150-200字）。

要求：
- 解释这个方法的核心思想是什么
- 用直白的语言，避免过多术语
- 如果有，用类比来帮助理解
- 保留关键英文术语（如模型名称、技术名词）
- 突出"巧妙之处"

论文标题: {title}
摘要: {abstract}

直接输出解决方案概述："""

            # ===== 5. 网络架构详细描述（结合 Method 章节 + Pipeline 图片）=====
            logger.info("   [5/7] 生成网络架构详细描述...")
            # 这部分将在后面使用多模态 API 单独生成
            arch_prompt = None  # 占位，后面会用多模态生成

            # ===== 6. 关键创新点 =====
            logger.info("   [6/7] 生成关键创新点...")
            innovations_prompt = f"""请列出这篇论文的 5 个关键创新点。

要求：
- 每个创新点用一个小标题（10字以内）+ 详细解释（50-80字）
- 突出"为什么这很重要"或"比以前好在哪里"
- 保留关键英文术语
- 用序号列出

论文标题: {title}
摘要: {abstract}

直接输出5个创新点："""

            # ===== 7. 应用场景 =====
            logger.info("   [7/8] 生成应用场景...")
            applications_prompt = f"""请列出这项技术的 4 个实际应用场景。

要求：
- 每个场景用一个标题（8字以内）+ 具体描述（60-80字）
- 描述要具体，说明如何应用、带来什么好处
- 涵盖不同领域（如工业、医疗、生活、娱乐等）
- 用序号列出

论文标题: {title}
摘要: {abstract}

直接输出4个应用场景："""

            # ===== 8. 论文十问 =====
            logger.info("   [8/10] 生成论文十问...")
            ten_questions_prompt = f"""你是一位资深的AI研究员和论文审稿人。请针对以下论文，回答"论文十问"——这是一套快速理解论文主旨的框架。

论文标题：{title}

论文摘要：{abstract}

请逐一回答以下10个问题，每个问题回答2-4句话，要求：
- 回答要具体、准确，基于论文内容
- 专业术语保留英文（如 CLIP, Transformer, zero-shot）
- 语言简洁有力，避免废话
- 如果某个问题在摘要中没有明确信息，请基于论文类型和领域做合理推断

**Q1. 论文试图解决什么问题？**
[核心问题是什么？为什么这个问题重要？]

**Q2. 这是否是一个新的问题？**
[是全新问题还是已有问题的新解法？与前人工作的关系？]

**Q3. 这篇文章要验证的科学假设是什么？**
[作者核心假设是什么？预期结论是什么？]

**Q4. 相关研究有哪些？如何归类？谁是该领域值得关注的研究者？**
[列出2-3个相关研究方向，提及1-2位领域专家]

**Q5. 论文的解决方案关键是什么？**
[核心方法/技术是什么？为什么这个方案能解决问题？]

**Q6. 论文的实验是如何设计的？**
[用了什么数据集？对比了哪些baseline？评估指标是什么？]

**Q7. 用于评估的数据集是什么？代码是否开源？**
[具体数据集名称，开源链接（如有）]

**Q8. 实验结果是否支持科学假设？**
[实验结果如何？是否达到预期？有什么局限性？]

**Q9. 这篇论文的主要贡献是什么？**
[列出2-3个核心贡献点]

**Q10. 下一步可以做什么？**
[有什么局限性？未来可以怎么改进或扩展？]

请按以下格式输出（保持Q1-Q10的结构）："""

            # ===== 9. 如果我是审稿人 =====
            logger.info("   [9/10] 生成审稿人视角...")
            reviewer_prompt = f"""你是一位顶级 AI 会议（如 NeurIPS、CVPR、ICML）的资深审稿人。请以审稿人的批判性视角审视这篇论文。

论文标题：{title}
论文摘要：{abstract}

请用**中文**从以下三个角度给出简洁有力的评价（每个角度 2-3 句话）：

**🔴 潜在的 Weakness**
- 用中文指出 1-2 个方法或实验设计上的潜在问题

**🟡 尖锐问题**
- 用中文列出 1-2 个审稿人可能提出的尖锐问题

**🟢 作者可能的回应**
- 用中文说明作者可能如何合理回应或辩护

要求：
- **必须全部使用中文撰写**
- 只有专业术语保留英文（如 Transformer、zero-shot）
- 总字数控制在 200 字以内

请用中文直接输出："""

            # ===== 10. 潜在改进方向 =====
            logger.info("   [10/10] 生成改进方向...")
            improvement_prompt = f"""你是一位 AI 研究者，正在阅读这篇论文并思考未来的研究方向。

论文标题：{title}
论文摘要：{abstract}

请用**中文**提出 2-3 个潜在的改进方向或未来研究思路，每个方向用 1-2 句话描述。

要求：
- **必须全部使用中文撰写**
- 思路要有启发性，引发读者深思
- 可以涉及：方法改进、新应用场景、与其他技术结合、解决现有局限等
- 只有专业术语保留英文（如 Transformer、GAN）
- 总字数控制在 100-150 字

请用中文直接输出（用数字编号）："""

        else:  # English
            logger.info("   [1/7] Generating viral title...")
            viral_title_prompt = f"""You are a top tech content editor. Create a viral, attention-grabbing title for this AI paper.

Requirements:
- Spark curiosity
- Highlight breakthrough or disruption
- Use techniques like questions, numbers, or comparisons
- 10-20 words
- No emoji

Paper: {title}
Abstract: {abstract[:500]}

Output title only:"""

            logger.info("   [2/7] Generating hook intro...")
            hook_intro_prompt = f"""Write an engaging opening paragraph (100-150 words) for this paper.

Requirements:
- Start with a concrete scenario or problem
- Describe current limitations vividly
- Naturally introduce "this paper proposes an innovative solution"
- Make readers want to continue

Paper: {title}
Abstract: {abstract[:600]}

Output opening paragraph:"""

            logger.info("   [3/7] Generating problem statement...")
            problem_prompt = f"""Explain the core problem this paper solves (80-100 words).

Requirements:
- Explain limitations of existing methods
- Why this problem matters
- Use relatable examples

Paper: {title}
Abstract: {abstract[:600]}

Output problem statement:"""

            logger.info("   [4/7] Generating solution overview...")
            solution_prompt = f"""Describe the core solution in simple terms (100-150 words).

Requirements:
- Explain the key idea
- Use analogies if helpful
- Highlight what's clever about it

Paper: {title}
Abstract: {abstract}

Output solution overview:"""

            logger.info("   [5/7] Generating architecture description...")
            arch_prompt = f"""Describe the network architecture workflow in detail (200-300 words).

Structure:
1. **Input**: What goes in, what format
2. **Processing**: Step-by-step through modules
   - What each module does
   - How data flows
   - Key operations (attention, convolution, etc.)
3. **Output**: Final result

Requirements:
- Use "First...Then...Next...Finally..." flow
- Keep technical terms
- Separate paragraphs for each step
- Suitable for explaining while looking at architecture diagram

Paper: {title}
Abstract: {abstract}

Output architecture description:"""

            logger.info("   [6/7] Generating key innovations...")
            innovations_prompt = f"""List 5 key innovations of this paper.

Format for each:
- Short title (5 words max) + detailed explanation (40-60 words)
- Highlight "why it matters" or "how it improves"
- Numbered list

Paper: {title}
Abstract: {abstract}

Output 5 innovations:"""

            logger.info("   [7/8] Generating applications...")
            applications_prompt = f"""List 4 real-world applications.

Format for each:
- Title (5 words max) + description (40-60 words)
- Be specific about how it's applied and benefits
- Cover different domains
- Numbered list

Paper: {title}
Abstract: {abstract}

Output 4 applications:"""

            # ===== 论文十问：一次性生成对论文的深度理解 =====
            logger.info("   [8/10] Generating 论文十问...")
            ten_questions_prompt = f"""你是一位资深的AI研究员和论文审稿人。请针对以下论文，回答"论文十问"——这是一套快速理解论文主旨的框架。

论文标题：{title}

论文摘要：{abstract}

请逐一回答以下10个问题，每个问题回答2-4句话，要求：
- 回答要具体、准确，基于论文内容
- 专业术语保留英文（如 CLIP, Transformer, zero-shot）
- 语言简洁有力，避免废话
- 如果某个问题在摘要中没有明确信息，请基于论文类型和领域做合理推断

**Q1. 论文试图解决什么问题？**
[核心问题是什么？为什么这个问题重要？]

**Q2. 这是否是一个新的问题？**
[是全新问题还是已有问题的新解法？与前人工作的关系？]

**Q3. 这篇文章要验证的科学假设是什么？**
[作者核心假设是什么？预期结论是什么？]

**Q4. 相关研究有哪些？如何归类？谁是该领域值得关注的研究者？**
[列出2-3个相关研究方向，提及1-2位领域专家]

**Q5. 论文的解决方案关键是什么？**
[核心方法/技术是什么？为什么这个方案能解决问题？]

**Q6. 论文的实验是如何设计的？**
[用了什么数据集？对比了哪些baseline？评估指标是什么？]

**Q7. 用于评估的数据集是什么？代码是否开源？**
[具体数据集名称，开源链接（如有）]

**Q8. 实验结果是否支持科学假设？**
[实验结果如何？是否达到预期？有什么局限性？]

**Q9. 这篇论文的主要贡献是什么？**
[列出2-3个核心贡献点]

**Q10. 下一步可以做什么？**
[有什么局限性？未来可以怎么改进或扩展？]

请按以下格式输出（保持Q1-Q10的结构）："""

            # ===== 9. 如果我是审稿人 =====
            logger.info("   [9/10] Generating reviewer perspective...")
            reviewer_prompt = f"""You are a senior reviewer for top AI conferences (NeurIPS, CVPR, ICML). Critically review this paper.

Title: {title}
Abstract: {abstract}

Provide brief comments from three perspectives (2-3 sentences each):

**🔴 Potential Weaknesses**
- Point out 1-2 potential issues in method or experimental design

**🟡 Sharp Questions**
- List 1-2 challenging questions a reviewer might ask

**🟢 Possible Author Response**
- How might authors reasonably respond to these concerns

Keep it concise, under 200 words total. Output directly:"""

            # ===== 10. 潜在改进方向 =====
            logger.info("   [10/10] Generating improvement directions...")
            improvement_prompt = f"""You are an AI researcher thinking about future research directions after reading this paper.

Title: {title}
Abstract: {abstract}

Propose 2-3 potential improvement directions or future research ideas. Each direction in 1-2 sentences.

Requirements:
- Ideas should be thought-provoking
- Can involve: method improvements, new applications, combining with other techniques, addressing limitations
- Keep it concise, 100-150 words total

Output directly (numbered):"""

        # ===== 执行 API 调用 =====
        viral_title = self._clean_response(self.model.generate_content(viral_title_prompt).text)
        hook_intro = self._clean_response(self.model.generate_content(hook_intro_prompt).text)
        problem = self._clean_response(self.model.generate_content(problem_prompt).text)
        solution = self._clean_response(self.model.generate_content(solution_prompt).text)
        
        # ===== 架构描述：使用多模态 API（Method 文本 + Pipeline 图片）=====
        architecture = self._generate_architecture_description(
            title=title,
            abstract=abstract,
            method_text=method_text,
            pipeline_figure=pipeline_figure,
            language=language
        )
        
        innovations = self._clean_response(self.model.generate_content(innovations_prompt).text)
        applications = self._clean_response(self.model.generate_content(applications_prompt).text)
        ten_questions = self._clean_response(self.model.generate_content(ten_questions_prompt).text)
        reviewer_perspective = self._clean_response(self.model.generate_content(reviewer_prompt).text)
        improvements = self._clean_response(self.model.generate_content(improvement_prompt).text)

        return {
            'viral_title': viral_title,
            'hook_intro': hook_intro,
            'problem_statement': problem,
            'solution_overview': solution,
            'architecture_description': architecture,
            'key_innovations': innovations,
            'applications': applications,
            'ten_questions': ten_questions,
            'reviewer_perspective': reviewer_perspective,
            'improvements': improvements
        }
    
    def _generate_architecture_description(self, title: str, abstract: str, 
                                           method_text: Optional[str],
                                           pipeline_figure: Optional[Path],
                                           language: str) -> str:
        """
        使用多模态 API 生成架构描述（结合 Method 章节 + Pipeline 图片）
        
        核心思路：
        1. 让 Gemini 先阅读 Method 章节文本
        2. 结合 Pipeline 结构图进行理解
        3. 专业视角讲解 + 统一的通俗比喻贯穿全文
        """
        import PIL.Image
        
        # 构建输入内容列表（多模态）
        content_parts = []
        
        # 基础 prompt
        if language == "zh":
            arch_prompt = f"""你是一位资深 AI 研究员，请讲解这篇论文的方法和网络架构。

## 论文信息
**标题**: {title}
**摘要**: {abstract[:600]}

"""
            if method_text:
                arch_prompt += f"""**Method 章节**:
{method_text[:3500]}

"""
            
            arch_prompt += """## 输出格式（严格按此结构）

### 一、整体流程概述

用 3-4 句话概括整个方法的核心思想。说明：这个方法的目标是什么？它是如何实现的？最终效果如何？请写成连贯的段落，不要用列表。

### 二、形象化理解

用一个统一的比喻来帮助理解核心思想（2-3 句话）。比喻要贴切、通俗易懂，不要展开细节。

### 三、技术细节

请详细讲解 Pipeline 中的每个关键步骤，每个步骤用独立的小标题。

#### 步骤 1: [中文步骤名称]

**输入**: 用中文描述输入数据的形式和维度。

**处理**: 用中文详细说明经过哪个模块，具体做了什么操作。

**输出**: 用中文说明输出结果和维度变化。

#### 步骤 2: [中文步骤名称]

同上格式，继续讲解下一个步骤...

（根据实际 Pipeline 的复杂度，可能有 3-5 个步骤）

### 四、最终输出

用中文说明模型最终输出是什么，如何用于实际任务。

## 写作要求（非常重要）
- **必须全部使用中文撰写**，包括步骤标题、输入/处理/输出描述
- 只有专业术语保留英文（如 Encoder、Transformer、Attention）
- 张量维度用数学格式（如 [B, 3, 224, 224] → [B, 512]）
- 每个部分要有实质内容，不要写空话
- 技术细节部分是重点，要写得充实详细
- 总字数 500-700 字

请直接用中文输出："""
        else:
            # English version
            arch_prompt = f"""You are a senior AI researcher. Explain this paper's method and architecture.

## Paper Info
**Title**: {title}
**Abstract**: {abstract[:600]}

"""
            if method_text:
                arch_prompt += f"""**Method Section**:
{method_text[:3500]}

"""
            
            arch_prompt += """## Output Format (Use Markdown headings)

### 1. Pipeline Overview
3-4 sentences summarizing what the method does, referencing the architecture diagram.

### 2. Intuitive Understanding  
ONE simple analogy (2-3 sentences) to build intuition. No details here.

### 3. Technical Details

For each key step in the pipeline:

**Step Name** (e.g., Image Encoding / Text Encoding / Contrastive Learning)
- **Input**: Data format and dimensions (e.g., image 224×224×3)
- **Process**: Which module, what operation
- **Output**: Output format and dimensions (e.g., feature vector 512-dim)

Repeat for all key steps.

### 4. Final Output
1-2 sentences on final output and usage.

## Requirements
- Include tensor dimensions (e.g., [B, 3, 224, 224] → [B, 512])
- Keep sections separate and clear
- 400-500 words total

Output directly:"""

        content_parts.append(arch_prompt)
        
        # 添加 Pipeline 图片（如果有）
        if pipeline_figure and pipeline_figure.exists():
            try:
                img = PIL.Image.open(pipeline_figure)
                content_parts.append(img)
                logger.info(f"      添加 Pipeline 图片: {pipeline_figure.name}")
            except Exception as e:
                logger.warning(f"      加载 Pipeline 图片失败: {e}")
        
        # 如果有图片，添加图片说明
        if pipeline_figure and pipeline_figure.exists():
            if language == "zh":
                content_parts.append("\n\n请仔细观察上面的网络架构图，结合 Method 章节的描述，给出准确且易懂的讲解。")
            else:
                content_parts.append("\n\nPlease carefully examine the architecture diagram above and provide accurate explanation.")
        
        # 调用 API
        try:
            response = self.model.generate_content(content_parts)
            return self._clean_response(response.text)
        except Exception as e:
            logger.warning(f"架构描述生成失败: {e}")
            # 降级：使用纯文本生成
            return self._clean_response(self.model.generate_content(arch_prompt).text)
    
    def _clean_response(self, text: str) -> str:
        """
        清理 AI 回复：
        1. 去除开场白（如"好的，以下是..."）
        2. 转换 Markdown 为 HTML
        """
        import re
        
        if not text:
            return ""
        
        text = text.strip()
        
        # 去除常见的 AI 开场白和多余说明
        prefixes_to_remove = [
            r'^好的[，,。\.]*\s*',
            r'^以下是.*?[：:]\s*',
            r'^根据.*?[，,]\s*',
            r'^这是.*?[：:]\s*',
            r'^当然[，,。\.]*\s*',
            r'^没问题[，,。\.]*\s*',
            r'^OK[，,。\.]*\s*',
            r'^Sure[，,。\.]*\s*',
            r'^Here\'s.*?[：:]\s*',
            r'^Here are.*?[：:]\s*',
            r'Here is the original image[：:.]?\s*',
            r'Based on the (?:image|diagram|figure).*?[：:,]\s*',
            r'Looking at the (?:image|diagram|figure).*?[：:,]\s*',
            r'From the (?:image|diagram|figure).*?[：:,]\s*',
        ]
        
        for prefix in prefixes_to_remove:
            text = re.sub(prefix, '', text, flags=re.IGNORECASE)
        
        # 转换 Markdown 标题为 HTML（按长度从长到短处理）
        text = re.sub(r'^#{5,}\s*(.+)$', r'<h6 class="step-title">\1</h6>', text, flags=re.MULTILINE)
        text = re.sub(r'^####\s*(.+)$', r'<h5 class="step-title">\1</h5>', text, flags=re.MULTILINE)
        text = re.sub(r'^###\s*(.+)$', r'<h4 class="arch-subtitle">\1</h4>', text, flags=re.MULTILINE)
        text = re.sub(r'^##\s*(.+)$', r'<h3>\1</h3>', text, flags=re.MULTILINE)
        
        # 转换 Markdown 粗体为 HTML
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        
        # 转换 Markdown 斜体为 HTML
        text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
        
        # 转换 Markdown 代码为 HTML
        text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
        
        # 转换 Markdown 列表为 HTML
        lines = text.split('\n')
        in_list = False
        result_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('- '):
                if not in_list:
                    result_lines.append('<ul class="detail-list">')
                    in_list = True
                result_lines.append(f'<li>{stripped[2:]}</li>')
            else:
                if in_list:
                    result_lines.append('</ul>')
                    in_list = False
                result_lines.append(line)
        if in_list:
            result_lines.append('</ul>')
        text = '\n'.join(result_lines)
        
        # 智能段落分隔：不要把 h3, h4, h5, ul 包在 <p> 里
        paragraphs = re.split(r'\n\n+', text)
        result_parts = []
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # 如果段落以 HTML 块级元素开头，不加 <p> 标签
            if re.match(r'^<(h[1-6]|ul|ol|div|section|blockquote)', para):
                result_parts.append(para)
            else:
                result_parts.append(f'<p>{para}</p>')
        
        text = '\n'.join(result_parts)
        
        # 清理可能产生的空 <p></p>
        text = re.sub(r'<p>\s*</p>', '', text)
        
        return text.strip()
    
    def _generate_all_images(self, metadata: Dict, content: Dict, language: str) -> Dict[str, Path]:
        """
        使用 Nano Banana (Gemini 2.5 Flash Image) 生成所有配图
        """
        images = {}
        arxiv_id = metadata['arxiv_id']
        title = metadata['title']
        
        # 1. Hero 配图 - 宽幅横幅
        logger.info("   [1/3] 生成 Hero 配图 (Nano Banana)...")
        hero_prompt = f"""A stunning wide cinematic banner image for an AI research breakthrough.

Theme: "{title[:60]}"

Visual style:
- Dreamlike, ethereal atmosphere with soft glowing particles
- Deep space blue and violet gradient background
- Abstract flowing data streams and neural pathways made of light
- Crystalline geometric structures floating in space
- Soft bokeh effects and lens flares
- Photorealistic 3D render quality
- Extremely wide aspect ratio (21:9)
- No text, no letters, no words, no labels"""

        hero_path = self._generate_nano_banana(hero_prompt, f"hero_{arxiv_id}.png", "16:9")
        if hero_path:
            images['hero'] = hero_path
        
        # 2. 导读配图 - 精准表达核心概念
        logger.info("   [2/3] 生成导读配图 (Nano Banana)...")
        hook_text = content.get('hook_intro', '')[:400]
        
        # 让 Gemini 分析导读核心内容，生成精准的可视化场景
        scene_prompt = f"""你是一位资深插画师，需要为下面这段导读文字设计一幅插图。

导读内容：
"{hook_text}"

请分析这段文字的核心含义，然后设计一个能够直观表达这个含义的具体场景。

要求：
1. 场景必须能让人一眼就理解导读在说什么
2. 用具体的人物/物体/动作来表达抽象概念
3. 场景要有故事感，让人想了解更多
4. 输出格式：一句话描述场景（50字以内），要具体到人物在做什么、环境是什么样的

示例（仅供参考格式）：
- 如果导读讲的是"AI学习图文对应"：一个孩子坐在地上，左手拿着一张狗的照片，右手指着书上"狗"这个字，脸上露出恍然大悟的表情
- 如果导读讲的是"突破传统限制"：一个人打破了一个写满标签的玻璃罩，从里面飞出五颜六色的图像

直接输出你设计的场景描述："""
        
        try:
            scene = self._clean_response(self.model.generate_content(scene_prompt).text)[:150]
            logger.info(f"      场景: {scene[:60]}...")
        except:
            scene = "A person connecting images and words with glowing threads of light"
        
        intro_prompt = f"""Create a vivid illustration of this exact scene:

{scene}

Art direction:
- Modern, clean digital illustration style
- Warm, inviting color palette with good contrast
- Clear visual storytelling - the action should be immediately obvious
- Expressive characters with clear emotions
- Dynamic composition that draws the eye
- Professional quality, suitable for a tech article
- Square format (1:1)
- CRITICAL: Absolutely NO text, NO letters, NO words, NO labels in the image"""

        intro_path = self._generate_nano_banana(intro_prompt, f"intro_{arxiv_id}.png", "1:1")
        if intro_path:
            images['intro'] = intro_path
        
        # 3. 问题背景配图 - 精准表达问题/挑战
        logger.info("   [3/3] 生成问题配图 (Nano Banana)...")
        problem_text = content.get('problem_statement', '')[:400]
        
        # 让 Gemini 分析问题核心，生成精准的可视化场景
        problem_scene_prompt = f"""你是一位资深插画师，需要为下面这段"问题背景"文字设计一幅插图。

问题背景：
"{problem_text}"

请设计一个能够直观表达这个问题的具体场景（50字以内）。

要求：
1. 场景必须能让人一眼就理解"问题出在哪里"
2. 用具体的人物/物体/动作来表达技术困难
3. 要有戏剧张力，让人感受到问题的严重性

示例格式：
- 问题"只能识别预定义类别"：一个机器人面前放着奇怪的动物，它困惑地翻着只有猫狗鸟三个选项的手册
- 问题"需要大量标注"：一个人被堆积如山的照片淹没，每张都要贴标签

直接输出场景描述："""
        
        try:
            problem_scene = self._clean_response(self.model.generate_content(problem_scene_prompt).text)[:150]
            logger.info(f"      问题场景: {problem_scene[:50]}...")
        except:
            problem_scene = "A robot confused by an unfamiliar object it cannot classify"
        
        problem_prompt = f"""Create a vivid illustration of this scene showing a problem:

{problem_scene}

Art direction:
- Modern digital illustration style
- Colors that convey difficulty: muted blues, grays, accent of orange
- Clear visual storytelling - the problem should be immediately obvious
- Show confusion, frustration, or being overwhelmed
- Professional quality for a tech article
- Square format (1:1)
- CRITICAL: NO text, NO letters, NO words in the image"""

        problem_path = self._generate_nano_banana(problem_prompt, f"problem_{arxiv_id}.png", "1:1")
        if problem_path:
            images['problem'] = problem_path
        
        return images
    
    def _generate_nano_banana(self, prompt: str, filename: str, aspect_ratio: str = "1:1") -> Optional[Path]:
        """使用 Nano Banana (Gemini 2.5 Flash Image) 生成图片"""
        try:
            response = self.imagen_client.models.generate_content(
                model='gemini-2.5-flash-image',
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_modalities=['IMAGE'],
                    image_config=types.ImageConfig(
                        aspect_ratio=aspect_ratio
                    )
                )
            )
            
            # 从响应中提取图片
            for part in response.candidates[0].content.parts:
                if part.inline_data is not None:
                    img_path = self.images_dir / filename
                    # 保存图片
                    with open(img_path, 'wb') as f:
                        f.write(part.inline_data.data)
                    return img_path
            
            return None
        except Exception as e:
            logger.warning(f"   Nano Banana 生成失败 ({filename}): {e}")
            # 回退到 Imagen
            return self._generate_imagen_fallback(prompt, filename)
    
    def _generate_imagen_fallback(self, prompt: str, filename: str) -> Optional[Path]:
        """回退到 Imagen 4.0"""
        try:
            response = self.imagen_client.models.generate_images(
                model='imagen-4.0-generate-001',
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    output_mime_type='image/png',
                ),
            )
            
            if response.generated_images:
                img = response.generated_images[0].image
                img_path = self.images_dir / filename
                img.save(str(img_path))
                return img_path
            return None
        except Exception as e:
            logger.warning(f"   Imagen fallback 也失败 ({filename}): {e}")
            return None

    def _image_to_base64(self, image_path: Path) -> str:
        """将图片转换为 base64 编码"""
        with open(image_path, 'rb') as f:
            encoded = base64.b64encode(f.read()).decode('utf-8')
        return f"data:image/png;base64,{encoded}"

    def _generate_html(self,
                       metadata: Dict,
                       content: Dict,
                       figures: List[Dict],
                       main_figure: Optional[Path],
                       generated_images: Dict[str, Path],
                       language: str) -> Path:
        """
        生成丰富内容的 HTML 网页
        """
        # Hero 配图
        hero_img_html = ""
        if generated_images.get('hero') and generated_images['hero'].exists():
            hero_base64 = self._image_to_base64(generated_images['hero'])
            hero_img_html = f'<img src="{hero_base64}" alt="Hero" class="hero-image">'
        
        # 导读配图
        intro_img_html = ""
        if generated_images.get('intro') and generated_images['intro'].exists():
            intro_base64 = self._image_to_base64(generated_images['intro'])
            intro_img_html = f'<img src="{intro_base64}" alt="Introduction" class="section-image">'
        
        # 问题配图
        problem_img_html = ""
        if generated_images.get('problem') and generated_images['problem'].exists():
            problem_base64 = self._image_to_base64(generated_images['problem'])
            problem_img_html = f'<img src="{problem_base64}" alt="Problem" class="section-image">'
        
        # 准备架构图
        arch_figure_html = ""
        if main_figure and main_figure.exists():
            img_base64 = self._image_to_base64(main_figure)
            arch_figure_html = f'''
            <div class="arch-figure">
                <img src="{img_base64}" alt="Network Architecture">
            </div>'''

        # 其他图片（已移除，只展示主图）

        # 格式化创新点（转换为HTML列表）
        innovations_html = self._format_list_to_html(content.get('key_innovations', ''))
        
        # 格式化应用场景
        applications_html = self._format_list_to_html(content.get('applications', ''))

        # 语言相关标签
        labels = {
            'zh': {
                'intro': '导读',
                'problem': '问题背景',
                'solution': '解决方案',
                'architecture': '网络架构详解',
                'innovations': '核心创新',
                'applications': '应用场景',
                'ten_questions': '论文十问',
                'ten_questions_desc': '快速理解论文主旨的框架',
                'reviewer': '如果我是审稿人',
                'reviewer_desc': '以批判性视角审视这篇论文',
                'improvements': '潜在改进方向',
                'improvements_desc': '未来研究的可能路径',
                'readmore': '阅读原文',
                'readmore_desc': '想深入了解？点击阅读完整论文',
                'footer': '由 Paper Storyteller 生成 · 基于 PaddleOCR + Gemini + Nano Banana',
                'designer': '设计：Dapengpeng',
                'contact': '联系：hellodapengya@gmail.com',
            },
            'en': {
                'intro': 'Introduction',
                'problem': 'Problem Background',
                'solution': 'Solution Overview',
                'architecture': 'Architecture Deep Dive',
                'innovations': 'Key Innovations',
                'applications': 'Applications',
                'ten_questions': '10 Questions',
                'ten_questions_desc': 'A framework for quickly understanding papers',
                'reviewer': 'If I Were a Reviewer',
                'reviewer_desc': 'Critical perspective on this paper',
                'improvements': 'Future Directions',
                'improvements_desc': 'Potential paths for future research',
                'readmore': 'Read More',
                'readmore_desc': 'Want to learn more? Read the full paper',
                'footer': 'Generated by Paper Storyteller · Powered by PaddleOCR + Gemini + Nano Banana',
                'designer': 'Design: Dapengpeng',
                'contact': 'Contact: hellodapengya@gmail.com',
            }
        }
        L = labels.get(language, labels['en'])

        # HTML 模板
        html = f'''<!DOCTYPE html>
<html lang="{'zh-CN' if language == 'zh' else 'en'}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{content.get('viral_title', metadata['title'])}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            /* 页面背景 */
            --bg: #F6F3EE;
            /* 内容区背景 */
            --bg-card: #FFFFFF;
            --bg-card-light: #FAFAFA;
            /* 分割线/边框 */
            --border: #E7E1D8;
            /* 标题色 */
            --text-heading: #121417;
            /* 正文段落 */
            --text: #2B2F36;
            /* 次要文字 */
            --text-muted: #6B7280;
            /* 重点强调 */
            --text-bright: #0F172A;
            /* 链接色 */
            --primary: #0F766E;
            --primary-dark: #115E59;
            /* 强调色 */
            --accent: #0F766E;
            /* 代码块 */
            --code-bg: #0B1220;
            --code-text: #E5E7EB;
            /* 渐变 - Hero 区域保持视觉吸引力 */
            --gradient-1: linear-gradient(135deg, #0F766E 0%, #115E59 50%, #134E4A 100%);
            --gradient-2: linear-gradient(135deg, #F6F3EE 0%, #FFFFFF 100%);
        }}
        
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Noto Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 2;
            font-size: 16px;
            letter-spacing: 0.02em;
            text-align: justify;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }}
        
        /* 基础段落样式 */
        p {{
            margin-bottom: 1em;
            line-height: 1.9;
            word-break: break-word;
            text-align: justify;
        }}

        .container {{
            max-width: 750px;
            margin: 0 auto;
            padding: 24px 20px;
        }}
        
        /* 移动端适配 */
        @media (max-width: 768px) {{
            body {{
                font-size: 15px;
                line-height: 1.9;
            }}
            .container {{
                padding: 16px 16px;
            }}
            p {{
                margin-bottom: 1em;
            }}
        }}
        
        /* ===== Hero Section ===== */
        .hero {{
            position: relative;
            background: var(--gradient-1);
            border-radius: 16px;
            padding: 50px 45px;
            margin-bottom: 32px;
            overflow: hidden;
            box-shadow: 0 8px 30px rgba(15, 118, 110, 0.15);
        }}
        
        .hero::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            background: url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.08'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E");
            opacity: 0.4;
        }}
        
        .hero-image {{
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            width: 100%; height: 100%;
            object-fit: cover;
            opacity: 0.15;
            mix-blend-mode: overlay;
        }}
        
        .hero-content {{
            position: relative;
            z-index: 1;
        }}

        .hero h1 {{
            font-size: 2.8em;
            font-weight: 700;
            color: white;
            line-height: 1.2;
            margin-bottom: 25px;
            text-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }}

        .hero .meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            color: rgba(255,255,255,0.9);
            font-size: 0.95em;
        }}
        
        .hero .meta-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        
        .hero .meta-item a {{
            color: white;
            text-decoration: underline;
        }}
        
        /* ===== Sections ===== */
        .section {{
            background: var(--bg-card);
            border-radius: 16px;
            padding: 36px 40px;
            margin-bottom: 24px;
            box-shadow: 0 2px 12px rgba(0,0,0,0.06);
            border: 1px solid var(--border);
        }}
        
        /* 正文段落样式 - 只有正文内容需要首行缩进 */
        .content-text > p {{
            text-indent: 2em;
            margin-bottom: 1.1em;
            line-height: 1.95;
            color: var(--text);
        }}
        
        /* 标题类元素绝对不缩进 */
        h1, h2, h3, h4, h5, h6 {{
            text-indent: 0 !important;
        }}
        
        /* 引用块样式 */
        .section blockquote {{
            border-left: 4px solid var(--primary);
            padding: 15px 20px;
            margin: 20px 0;
            background: rgba(99, 102, 241, 0.1);
            border-radius: 0 8px 8px 0;
        }}
        
        .section blockquote p {{
            text-indent: 0;
            margin-bottom: 0;
        }}

        .section h2 {{
            font-size: 1.4em;
            font-weight: 600;
            color: var(--text-heading);
            margin-bottom: 24px;
            padding-bottom: 12px;
            border-bottom: 2px solid var(--primary);
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        
        .section h2::before {{
            content: '';
            width: 6px;
            height: 28px;
            background: var(--primary);
            border-radius: 3px;
        }}

        .section p {{
            color: var(--text);
            font-size: 1.05em;
            line-height: 2;
            margin-bottom: 15px;
        }}
        
        /* ===== Section with Image (图上文下) ===== */
        .section-image-wrapper {{
            display: flex;
            justify-content: center;
            margin-bottom: 30px;
        }}
        
        .section-image {{
            width: 100%;
            max-width: 500px;
            height: auto;
            border-radius: 16px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.4);
            transition: transform 0.3s ease;
        }}
        
        .section-image:hover {{
            transform: scale(1.02);
        }}
        
        /* ===== Hook Intro ===== */
        .hook-intro {{
            padding: 20px 24px;
            font-size: 1.02em;
            color: var(--text);
            line-height: 1.9;
            border-left: 3px solid var(--primary);
            background: transparent;
        }}
        
        .hook-intro p {{
            text-indent: 2em;
            margin-bottom: 1em;
            text-align: justify;
        }}
        
        .hook-intro p:last-child {{
            margin-bottom: 0;
        }}
        
        /* ===== Problem & Solution ===== */
        .problem-box {{
            padding: 20px 24px;
            border-left: 3px solid #E74C3C;
            background: transparent;
        }}
        
        .problem-box p {{
            text-indent: 2em;
            margin-bottom: 1em;
            line-height: 1.9;
            text-align: justify;
        }}
        
        .problem-box p:last-child {{
            margin-bottom: 0;
        }}
        
        .solution-box {{
            padding: 20px 24px;
            border-left: 3px solid var(--primary);
            background: transparent;
        }}
        
        .solution-box p {{
            text-indent: 2em;
            margin-bottom: 1em;
            line-height: 1.9;
            text-align: justify;
        }}
        
        .solution-box p:last-child {{
            margin-bottom: 0;
        }}
        
        /* ===== Architecture Section ===== */
        .arch-figure {{
            margin: 30px 0;
            text-align: center;
        }}

        .arch-figure img {{
            max-width: 100%;
            height: auto;
            border-radius: 16px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.4);
            background: white;
            padding: 20px;
        }}

        .arch-description {{
            background: var(--bg-card-light);
            border-radius: 12px;
            padding: 28px 32px;
            margin-top: 24px;
            border: 1px solid var(--border);
        }}
        
        /* 架构描述 - 小标题后的第一段不缩进，后续段落缩进 */
        .arch-description > p {{
            margin-bottom: 1em;
            line-height: 1.9;
            text-align: justify;
        }}
        
        /* 架构描述中，普通段落（非紧跟标题的）才缩进 */
        .arch-description > p + p {{
            text-indent: 2em;
        }}
        
        /* 小标题后紧跟的段落不缩进 */
        .arch-description h4 + p {{
            text-indent: 0;
        }}
        
        .arch-description h4.arch-subtitle {{
            color: var(--text-heading);
            font-size: 1.1em;
            font-weight: 600;
            margin: 24px 0 12px 0;
            padding-bottom: 6px;
            border-bottom: 2px solid var(--primary);
            display: inline-block;
        }}
        
        .arch-description h4.arch-subtitle:first-of-type {{
            margin-top: 0;
        }}
        
        /* 技术步骤小标题 */
        .arch-description h5.step-title,
        .arch-description h6.step-title {{
            color: var(--primary);
            font-size: 1em;
            font-weight: 600;
            margin: 18px 0 8px 0;
        }}
        
        .arch-description .detail-list {{
            list-style: none;
            margin: 10px 0 15px 0;
            padding: 0;
        }}
        
        .arch-description .detail-list li {{
            padding: 8px 0 8px 20px;
            position: relative;
            color: var(--text);
            line-height: 1.6;
        }}
        
        .arch-description .detail-list li::before {{
            content: "→";
            position: absolute;
            left: 0;
            color: var(--accent);
            font-weight: bold;
        }}
        
        .arch-description .detail-list li strong {{
            color: var(--text-bright);
        }}
        
        /* ===== Innovations List ===== */
        .innovations-list {{
            list-style: none;
        }}
        
        .innovations-list li {{
            background: var(--bg-card-light);
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 10px;
            border-left: 3px solid var(--primary);
            border: 1px solid var(--border);
            border-left: 3px solid var(--primary);
            transition: transform 0.2s, box-shadow 0.2s;
            line-height: 1.75;
        }}
        
        /* 列表项内容不缩进 */
        .innovations-list li p {{
            text-indent: 0;
            margin-bottom: 0;
        }}
        
        .innovations-list li:hover {{
            transform: translateX(5px);
            box-shadow: 0 4px 15px rgba(99, 102, 241, 0.2);
        }}
        
        .innovations-list li strong {{
            color: var(--primary);
            font-size: 1.05em;
        }}
        
        /* ===== 论文十问 Ten Questions ===== */
        .ten-questions .section-desc {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border);
            text-indent: 0;
        }}
        
        .questions-content {{
            display: flex;
            flex-direction: column;
            gap: 0;
        }}
        
        .qa-item {{
            padding: 20px 0;
            border-bottom: 1px solid var(--border);
        }}
        
        .qa-item:last-child {{
            border-bottom: none;
        }}
        
        .qa-question {{
            display: flex;
            align-items: baseline;
            gap: 10px;
            margin-bottom: 10px;
        }}
        
        .qa-num {{
            color: var(--primary);
            font-weight: 700;
            font-size: 0.95em;
            flex-shrink: 0;
        }}
        
        .qa-title {{
            font-weight: 600;
            color: var(--text-heading);
            font-size: 1.05em;
            line-height: 1.5;
        }}
        
        .qa-answer {{
            color: var(--text);
            line-height: 1.85;
            padding-left: 36px;
        }}
        
        /* 问答答案不需要首行缩进 */
        .qa-answer p {{
            text-indent: 0;
            margin-bottom: 0.5em;
            text-align: justify;
        }}
        
        .qa-answer p:last-child {{
            margin-bottom: 0;
        }}
        
        .qa-answer strong {{
            color: var(--primary);
        }}
        
        @media (max-width: 600px) {{
            .qa-answer {{
                padding-left: 0;
                margin-top: 8px;
            }}
            .qa-question {{
                flex-wrap: wrap;
            }}
        }}
        
        /* ===== Applications Grid ===== */
        .applications-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 20px;
        }}
        
        .app-card {{
            background: var(--bg-card-light);
            border-radius: 16px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .app-card:hover {{
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
        }}
        
        .app-card h4 {{
            color: var(--accent);
            font-size: 1.1em;
            margin-bottom: 10px;
        }}
        
        /* ===== Abstract ===== */
        .abstract {{
            background: var(--bg-card-light);
            border-radius: 12px;
            padding: 25px 30px;
            font-style: italic;
            color: var(--text-muted);
            border-left: 4px solid var(--text-muted);
        }}

        /* ===== Gallery ===== */
        .gallery {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}

        .gallery-item {{
            text-align: center;
        }}

        .gallery-item img {{
            width: 100%;
            height: auto;
            border-radius: 12px;
            background: white;
            padding: 10px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.3);
        }}

        .gallery-item p {{
            margin-top: 10px;
            font-size: 0.9em;
            color: var(--text-muted);
        }}
        
        /* ===== 审稿人视角 Reviewer Section ===== */
        .reviewer-section .section-desc {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-bottom: 20px;
            text-indent: 0;
        }}
        
        .reviewer-content {{
            padding: 20px 24px;
            border-left: 3px solid #E74C3C;
            background: transparent;
        }}
        
        .reviewer-content p {{
            margin-bottom: 1em;
            line-height: 1.85;
            text-align: justify;
            text-indent: 0;
        }}
        
        .reviewer-content p:last-child {{
            margin-bottom: 0;
        }}
        
        /* ===== 改进方向 Improvements Section ===== */
        .improvements-section .section-desc {{
            color: var(--text-muted);
            font-size: 0.9em;
            margin-bottom: 20px;
            text-indent: 0;
        }}
        
        .improvements-content {{
            padding: 20px 24px;
            border-left: 3px solid var(--primary);
            background: transparent;
        }}
        
        .improvements-content p {{
            margin-bottom: 0.8em;
            line-height: 1.85;
            text-align: justify;
            text-indent: 0;
        }}
        
        .improvements-content p:last-child {{
            margin-bottom: 0;
        }}
        
        /* ===== Read More ===== */
        .read-more {{
            text-align: center;
            padding: 36px;
        }}
        
        .read-more a {{
            display: inline-block;
            background: var(--primary);
            color: white;
            padding: 14px 36px;
            border-radius: 8px;
            font-weight: 600;
            text-decoration: none;
            transition: background 0.2s, transform 0.2s;
            box-shadow: 0 2px 8px rgba(15, 118, 110, 0.25);
        }}
        
        .read-more a:hover {{
            background: var(--primary-dark);
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(15, 118, 110, 0.3);
        }}
        
        /* ===== Footer ===== */
        .footer {{
            text-align: center;
            padding: 40px 20px;
            color: var(--text-muted);
            font-size: 0.9em;
        }}
        
        .footer-designer {{
            margin-top: 8px;
            font-size: 0.85em;
        }}

        .footer-designer a {{
            color: var(--primary);
            text-decoration: none;
        }}

        .footer-designer a:hover {{
            text-decoration: underline;
        }}

        .footer-date {{
            margin-top: 5px;
            font-size: 0.8em;
            opacity: 0.7;
        }}
        
        .footer .badges {{
            margin-top: 15px;
        }}

        .badge {{
            display: inline-block;
            background: var(--bg-card-light);
            color: var(--text-muted);
            border: 1px solid var(--border);
            padding: 6px 16px;
            border-radius: 20px;
            font-size: 0.85em;
            margin: 5px;
            border: 1px solid rgba(255,255,255,0.1);
        }}
        
        /* ===== Responsive ===== */
        @media (max-width: 768px) {{
            .hero {{ padding: 35px 20px; }}
            .hero h1 {{ font-size: 1.6em; line-height: 1.4; }}
            .section {{ 
                padding: 28px 20px; 
                margin-bottom: 20px;
                border-radius: 16px;
            }}
            .section h2 {{
                font-size: 1.3em;
                margin-bottom: 20px;
            }}
            .content-text > p {{
                text-indent: 2em;
                line-height: 1.85;
                margin-bottom: 0.9em;
            }}
            .applications-grid {{ grid-template-columns: 1fr; }}
            .section-image {{ max-width: 100%; }}
            .arch-description {{
                padding: 20px;
            }}
            .arch-description h4.arch-subtitle {{
                font-size: 1.05em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <!-- Hero -->
        <header class="hero">
            {hero_img_html}
            <div class="hero-content">
                <h1>{content.get('viral_title', metadata['title'])}</h1>
            <div class="meta">
                    <span class="meta-item"><strong>Authors:</strong> {format_authors(metadata['authors'])}</span>
                    <span class="meta-item"><strong>Published:</strong> {metadata['published'].strftime('%Y-%m-%d')}</span>
                    <span class="meta-item"><strong>arXiv:</strong> <a href="https://arxiv.org/abs/{metadata['arxiv_id']}">{metadata['arxiv_id']}</a></span>
            </div>
        </div>
        </header>

        <!-- Hook Intro -->
        <section class="section">
            <h2>{L['intro']}</h2>
            <div class="section-image-wrapper">
                {intro_img_html}
            </div>
            <div class="hook-intro">
                {content.get('hook_intro', '')}
        </div>
        </section>

        <!-- Problem -->
        <section class="section">
            <h2>{L['problem']}</h2>
            <div class="section-image-wrapper">
                {problem_img_html}
        </div>
            <div class="problem-box">
                <p>{content.get('problem_statement', '')}</p>
            </div>
        </section>

        <!-- Solution -->
        <section class="section">
            <h2>{L['solution']}</h2>
            <div class="solution-box">
                <p>{content.get('solution_overview', '')}</p>
            </div>
        </section>

        <!-- Architecture -->
        <section class="section">
            <h2>{L['architecture']}</h2>
            {arch_figure_html}
            <div class="arch-description">
                {self._format_paragraphs(content.get('architecture_description', ''))}
            </div>
        </section>

        <!-- Innovations -->
        <section class="section">
            <h2>{L['innovations']}</h2>
            {innovations_html}
        </section>

        <!-- Applications -->
        <section class="section">
            <h2>{L['applications']}</h2>
            {applications_html}
        </section>

        <!-- 论文十问 -->
        <section class="section ten-questions">
            <h2>{L['ten_questions']}</h2>
            <p class="section-desc">{L['ten_questions_desc']}</p>
            <div class="questions-content">
                {self._format_ten_questions(content.get('ten_questions', ''))}
        </div>
        </section>

        <!-- 如果我是审稿人 -->
        <section class="section reviewer-section">
            <h2>{L['reviewer']}</h2>
            <p class="section-desc">{L['reviewer_desc']}</p>
            <div class="reviewer-content">
                {self._format_reviewer_content(content.get('reviewer_perspective', ''))}
            </div>
        </section>

        <!-- 潜在改进方向 -->
        <section class="section improvements-section">
            <h2>{L['improvements']}</h2>
            <p class="section-desc">{L['improvements_desc']}</p>
            <div class="improvements-content">
                {self._format_improvements(content.get('improvements', ''))}
        </div>
        </section>

        <!-- Read More -->
        <section class="section read-more">
            <p style="margin-bottom: 20px; color: var(--text-muted);">{L['readmore_desc']}</p>
            <a href="https://arxiv.org/abs/{metadata['arxiv_id']}" target="_blank">
                {L['readmore']} &rarr;
            </a>
        </section>

        <!-- Footer -->
        <footer class="footer">
            <p>{L['footer']}</p>
            <p class="footer-designer">{L['designer']} · <a href="mailto:hellodapengya@gmail.com">{L['contact']}</a></p>
            <p class="footer-date">{datetime.now().strftime('%Y-%m-%d')}</p>
            <div class="badges">
                <span class="badge">PaddleOCR</span>
                <span class="badge">Gemini 2.0</span>
                <span class="badge">Nano Banana</span>
        </div>
        </footer>
    </div>
</body>
</html>'''

        # 保存
        filename = f"{metadata['arxiv_id']}_{language}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        output_path = self.output_dir / filename

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)

        return output_path
    
    def _format_paragraphs(self, text: str) -> str:
        """将文本格式化为HTML段落"""
        if not text:
            return ""
        paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        return '\n'.join(f'<p>{p}</p>' for p in paragraphs)
    
    def _format_list_to_html(self, text: str) -> str:
        """将列表文本转换为HTML格式"""
        if not text:
            return ""
        
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        items = []
        current_item = ""
        
        for line in lines:
            # 检测是否是新的列表项（数字开头或 - 开头）
            if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
                if current_item:
                    items.append(current_item)
                # 清理前缀
                current_item = line.lstrip('0123456789.-•) ').strip()
            else:
                current_item += ' ' + line if current_item else line
        
        if current_item:
            items.append(current_item)
        
        if not items:
            return f'<p>{text}</p>'
        
        # 生成 HTML
        html_items = []
        for item in items:
            # 尝试分离标题和描述
            if '：' in item:
                title, desc = item.split('：', 1)
                html_items.append(f'<li><strong>{title}</strong>：{desc}</li>')
            elif ':' in item:
                title, desc = item.split(':', 1)
                html_items.append(f'<li><strong>{title}</strong>: {desc}</li>')
            else:
                html_items.append(f'<li>{item}</li>')
        
        return f'<ul class="innovations-list">{"".join(html_items)}</ul>'

    def _format_ten_questions(self, text: str) -> str:
        """将论文十问内容格式化为HTML"""
        import re
        
        if not text:
            return "<p>暂无内容</p>"
        
        # 先清理所有的 ** 标记
        text = re.sub(r'\*\*', '', text)
        
        # 使用正则匹配每个问题及其答案
        # 匹配格式: Q1. 问题标题？ 答案内容...
        pattern = r'Q(\d+)[\.。\s]*([^Q\n]+?[？?])\s*(.*?)(?=Q\d+[\.。\s]|$)'
        matches = re.findall(pattern, text, re.DOTALL)
        
        if not matches:
            # 备用方案：简单按 Q1, Q2... 分割
            parts = re.split(r'Q(\d+)[\.。]?\s*', text)
            questions = []
            i = 1
            while i < len(parts):
                if i + 1 < len(parts):
                    q_num = parts[i].strip()
                    q_content = parts[i + 1].strip()
                    # 尝试分离问题和答案
                    lines = q_content.split('\n', 1)
                    if len(lines) > 1:
                        q_title = lines[0].strip().rstrip('：:？?').strip()
                        q_answer = lines[1].strip()
                    else:
                        q_title = "问题 " + q_num
                        q_answer = q_content
                    questions.append({'num': q_num, 'title': q_title, 'answer': q_answer})
                i += 2
        else:
            questions = []
            for match in matches:
                q_num = match[0].strip()
                q_title = match[1].strip().rstrip('？?').strip()
                q_answer = match[2].strip()
                questions.append({'num': q_num, 'title': q_title, 'answer': q_answer})
        
        if not questions:
            return f'<div class="qa-item"><p>{text}</p></div>'
        
        # 生成 HTML
        html_parts = []
        for q in questions:
            # 清理答案中可能残留的格式问题
            answer = q['answer'].strip()
            # 移除答案开头可能的冒号
            answer = re.sub(r'^[：:]\s*', '', answer)
            # 将换行转为 <br>
            answer = answer.replace('\n\n', '</p><p>').replace('\n', '<br>')
            
            html_parts.append(f'''
            <div class="qa-item">
                <div class="qa-question">
                    <span class="qa-num">Q{q['num']}</span>
                    <span class="qa-title">{q['title']}</span>
                </div>
                <div class="qa-answer"><p>{answer}</p></div>
            </div>''')
        
        return '\n'.join(html_parts)

    def _format_reviewer_content(self, text: str) -> str:
        """格式化审稿人视角内容为HTML"""
        import re
        
        if not text:
            return "<p>暂无内容</p>"
        
        # 清理 Markdown 格式
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        
        # 处理 emoji 标题行（🔴 🟡 🟢）
        text = re.sub(r'(🔴|🟡|🟢)\s*(.+?)(?=\n|$)', r'<p><strong>\1 \2</strong></p>', text)
        
        # 处理列表项
        text = re.sub(r'^[-•]\s*(.+)$', r'<p>• \1</p>', text, flags=re.MULTILINE)
        
        # 将连续换行转为段落
        paragraphs = text.strip().split('\n\n')
        formatted = []
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith('<p>'):
                # 单行换行转为 <br>
                p = p.replace('\n', '<br>')
                formatted.append(f'<p>{p}</p>')
            elif p:
                formatted.append(p.replace('\n', '<br>'))
        
        return '\n'.join(formatted)

    def _format_improvements(self, text: str) -> str:
        """格式化改进方向内容为HTML"""
        import re
        
        if not text:
            return "<p>暂无内容</p>"
        
        # 清理 Markdown 格式
        text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'\*([^*]+)\*', r'<em>\1</em>', text)
        
        # 处理编号列表 (1. 2. 3.)
        text = re.sub(r'^(\d+)[\.。]\s*', r'<strong>\1.</strong> ', text, flags=re.MULTILINE)
        
        # 将每行转为段落
        lines = text.strip().split('\n')
        formatted = []
        for line in lines:
            line = line.strip()
            if line:
                if not line.startswith('<p>'):
                    formatted.append(f'<p>{line}</p>')
                else:
                    formatted.append(line)
        
        return '\n'.join(formatted)


# =============================================================================
# CLI Interface
# =============================================================================
def main():
    """命令行接口"""
    import argparse

    parser = argparse.ArgumentParser(description='Paper Storyteller - Claude Code Skill')
    parser.add_argument('arxiv_url', help='arXiv URL or ID')
    parser.add_argument('--lang', default='zh', choices=['zh', 'en'], help='Language (zh or en)')
    parser.add_argument('--api-key', help='Gemini API key (or set GOOGLE_API_KEY env var)')
    parser.add_argument('--output', default='output', help='Output directory')

    args = parser.parse_args()

    # Setup logging
    setup_logging("INFO")

    # Get API key
    api_key = args.api_key or os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logger.error("❌ 请提供 Gemini API key (--api-key 或 GOOGLE_API_KEY 环境变量)")
        sys.exit(1)

    # Process paper
    skill = PaperStorytellerSkill(gemini_api_key=api_key, output_dir=args.output)
    html_path = skill.process_paper(args.arxiv_url, language=args.lang)

    print(f"\n✅ 完成！网页已生成: {html_path}")
    print(f"   在浏览器中打开查看")


if __name__ == "__main__":
    main()
