"""
DocLayout Extractor - 基于 PaddleOCR-VL PP-DocLayoutV2 的论文图像提取器

功能：
- 使用 PP-DocLayoutV2 检测 PDF 中的 image 区域
- 智能选择网络架构图（基于位置、面积、宽高比打分）
- 优先选择第 2-3 页的大图（通常是架构图）

模型要求：
- 需要下载 PaddleOCR-VL 模型到 models/PaddleOCR-VL/
- 包含 PP-DocLayoutV2 子目录（inference.pdmodel / inference.pdiparams / inference.yml）
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import cv2
import numpy as np
import fitz  # PyMuPDF
from loguru import logger

# 避免 KMP 多实例报错
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

# 默认模型路径
DEFAULT_MODEL_DIR = "models/PaddleOCR-VL/PP-DocLayoutV2"


class DocLayoutExtractor:
    """基于 PP-DocLayoutV2 的论文 figure 提取器"""

    def __init__(
        self,
        output_dir: str = "output/figures",
        model_dir: Optional[str] = None,
        device: str = "cpu",
    ):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.model_dir = Path(
            model_dir or os.getenv("DOC_LAYOUT_MODEL_DIR", DEFAULT_MODEL_DIR)
        )
        self.device = device
        self._engine = None

    @property
    def engine(self):
        """延迟加载布局检测引擎"""
        if self._engine is None:
            from paddleocr import LayoutDetection

            # 检查模型文件
            required_files = ["inference.pdmodel", "inference.pdiparams", "inference.yml"]
            missing = [f for f in required_files if not (self.model_dir / f).exists()]
            if missing:
                raise FileNotFoundError(
                    f"模型文件缺失: {missing}\n"
                    f"请从 HuggingFace 下载 PaddleOCR-VL 到 {self.model_dir.parent}"
                )

            logger.info(f"初始化 LayoutDetection (本地 PP-DocLayoutV2)...")
            self._engine = LayoutDetection(
                model_name="PP-DocLayoutV2",
                model_dir=str(self.model_dir),
                device=self.device,
            )
            logger.success("LayoutDetection 初始化完成")
        return self._engine

    def _pdf_page_to_image(self, pdf_path: str, page_num: int, dpi: int = 300) -> np.ndarray:
        """将 PDF 页面渲染为 BGR 图像（高分辨率）"""
        doc = fitz.open(pdf_path)
        page = doc[page_num]
        zoom = dpi / 72
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        if pix.n == 4:
            img = cv2.cvtColor(img, cv2.COLOR_RGBA2BGR)
        elif pix.n == 3:
            img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        doc.close()
        return img

    def _detect_layout(self, image: np.ndarray) -> Dict:
        """
        检测图像中的布局元素
        返回: {"images": [...], "captions": [...]}
        """
        result = self.engine.predict(image)
        
        images = []
        captions = []
        
        if result and len(result) > 0:
            # 获取 JSON 格式结果
            json_result = result[0].json
            if isinstance(json_result, str):
                json_result = json.loads(json_result)
            
            boxes = json_result.get("res", {}).get("boxes", [])
            
            for box in boxes:
                label = box.get("label", "").lower()
                item = {
                    "label": label,
                    "score": box.get("score", 0),
                    "bbox": box.get("coordinate", []),
                }
                
                # 只提取 image 类型（不包括 figure_title）
                if label == "image":
                    images.append(item)
                elif "title" in label or "caption" in label:
                    captions.append(item)
        
        return {"images": images, "captions": captions}

    def _crop_region(self, image: np.ndarray, bbox: list, padding: int = 5) -> np.ndarray:
        """裁剪图像区域"""
        h, w = image.shape[:2]
        x0, y0, x1, y1 = [int(v) for v in bbox[:4]]
        x0 = max(0, x0 - padding)
        y0 = max(0, y0 - padding)
        x1 = min(w, x1 + padding)
        y1 = min(h, y1 + padding)
        return image[y0:y1, x0:x1]

    def _score_figure(self, page: int, area: int, width: int, height: int, det_score: float) -> float:
        """
        智能评分：选择最可能是网络架构图的图片
        
        规则：
        - 架构图通常在第 2-3 页（第1页多是概念图/结果图）
        - 架构图面积较大
        - 架构图通常较宽（宽高比 > 1.5）
        """
        aspect_ratio = width / height if height > 0 else 1
        
        # 位置分：第2-3页最高
        if page == 2 or page == 3:
            position_score = 50
        elif page == 1:
            position_score = 30
        elif page <= 5:
            position_score = 20
        else:
            position_score = 10
        
        # 面积分：大图优先
        area_score = min(area / 50000, 60)
        
        # 宽高比分：宽图更可能是流程图
        if aspect_ratio > 2.0:
            ratio_score = 30
        elif aspect_ratio > 1.5:
            ratio_score = 20
        elif aspect_ratio > 1.0:
            ratio_score = 10
        else:
            ratio_score = 5
        
        # 置信度分
        conf_score = det_score * 20
        
        # 小图惩罚
        size_penalty = -30 if area < 30000 else 0
        
        return position_score + area_score + ratio_score + conf_score + size_penalty

    def extract_from_pdf(
        self, pdf_path: str, max_pages: int = 8, dpi: int = 300
    ) -> Dict:
        """
        从 PDF 提取图片，并智能选择网络架构图
        
        Args:
            pdf_path: PDF 文件路径
            max_pages: 最多处理的页数
            dpi: 渲染分辨率
            
        Returns:
            {
                "figures": [...],
                "main_figure": Path,  # 最可能的架构图
                "secondary_figure": Path,  # 次选
                "total_figures": int
            }
        """
        pdf_path = Path(pdf_path)
        pdf_name = pdf_path.stem
        
        doc = fitz.open(str(pdf_path))
        total_pages = min(len(doc), max_pages)
        doc.close()
        
        all_figures = []
        
        logger.info(f"开始提取 PDF 图片: {pdf_path.name} ({total_pages} 页)")
        
        for page_idx in range(total_pages):
            logger.debug(f"   处理第 {page_idx + 1}/{total_pages} 页...")
            
            page_image = self._pdf_page_to_image(str(pdf_path), page_idx, dpi=dpi)
            layout = self._detect_layout(page_image)
            
            images = layout["images"]
            logger.debug(f"      检测到 {len(images)} 个 image")
            
            for img_idx, img_box in enumerate(images):
                bbox = img_box["bbox"]
                if len(bbox) < 4:
                    continue
                
                # 直接裁剪高 DPI 渲染的页面图像
                cropped = self._crop_region(page_image, bbox)
                h, w = cropped.shape[:2]
                area = w * h
                
                # 评分
                score = self._score_figure(
                    page=page_idx + 1,
                    area=area,
                    width=w,
                    height=h,
                    det_score=img_box["score"]
                )
                
                # 保存
                filename = f"{pdf_name}_p{page_idx+1}_img{img_idx+1}.png"
                save_path = self.output_dir / filename
                cv2.imwrite(str(save_path), cropped)
                
                all_figures.append({
                    "path": save_path,
                    "page": page_idx + 1,
                    "bbox": bbox,
                    "size": (w, h),
                    "area": area,
                    "detection_score": img_box["score"],
                    "total_score": score,
                })
                
                logger.debug(f"      保存: {filename} ({w}x{h}, score={score:.1f})")
        
        # 按分数排序选择
        all_figures.sort(key=lambda x: x["total_score"], reverse=True)
        
        main_figure = all_figures[0]["path"] if all_figures else None
        secondary = all_figures[1]["path"] if len(all_figures) > 1 else None
        
        logger.success(f"共提取 {len(all_figures)} 个图片")
        if main_figure:
            best = all_figures[0]
            logger.info(f"   主图: {main_figure.name} (p{best['page']}, {best['size'][0]}x{best['size'][1]}, score={best['total_score']:.1f})")
        
        return {
            "figures": all_figures,
            "main_figure": main_figure,
            "secondary_figure": secondary,
            "total_figures": len(all_figures),
        }


def extract_figures_doclayout(pdf_path: str, output_dir: str = "output/figures") -> Dict:
    """
    便捷函数：提取 PDF 中的图片
    
    Args:
        pdf_path: PDF 文件路径
        output_dir: 输出目录
        
    Returns:
        {
            "main_figure": Path,  # 最佳架构图
            "all_figures": [Path, ...],  # 所有图片
            "total": int
        }
    """
    extractor = DocLayoutExtractor(output_dir=output_dir)
    result = extractor.extract_from_pdf(pdf_path)
    return {
        "main_figure": result["main_figure"],
        "all_figures": [f["path"] for f in result["figures"]],
        "total": result["total_figures"],
    }


if __name__ == "__main__":
    import sys
    
    # 设置日志
    logger.remove()
    logger.add(sys.stderr, level="DEBUG")
    
    # 测试
    test_pdfs = list(Path("test_paper").glob("*.pdf"))
    if not test_pdfs:
        print("未找到测试 PDF，请将 PDF 放到 test_paper/ 目录")
        sys.exit(1)
    
    print(f"\n找到 {len(test_pdfs)} 个测试 PDF")
    
    for pdf in test_pdfs[:3]:
        print(f"\n{'='*60}")
        result = extract_figures_doclayout(str(pdf), output_dir="test_output")
        print(f"PDF: {pdf.name}")
        print(f"主图: {result['main_figure']}")
        print(f"总数: {result['total']}")
