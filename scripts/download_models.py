"""
下载 PaddleOCR-VL 模型文件

首次运行 Paper Storyteller 时会自动调用此脚本下载必需的模型。
也可以手动运行：python scripts/download_models.py
"""

import os
from pathlib import Path


def download_paddleocr_models(model_dir: str = "models/PaddleOCR-VL") -> bool:
    """
    下载 PaddleOCR-VL 的 PP-DocLayoutV2 模型
    
    Args:
        model_dir: 模型保存目录
        
    Returns:
        bool: 是否下载成功
    """
    from huggingface_hub import snapshot_download
    
    model_path = Path(model_dir)
    layout_model_path = model_path / "PP-DocLayoutV2"
    
    # 检查是否已存在
    required_files = ["inference.pdmodel", "inference.pdiparams", "inference.yml"]
    if layout_model_path.exists():
        existing = [f for f in required_files if (layout_model_path / f).exists()]
        if len(existing) == len(required_files):
            print(f"✅ 模型已存在: {layout_model_path}")
            return True
    
    print("📥 开始下载 PaddleOCR-VL 模型...")
    print("   仓库: PaddlePaddle/PaddleOCR-VL")
    print("   目标: PP-DocLayoutV2 (约 200MB)")
    print()
    
    try:
        # 只下载 PP-DocLayoutV2 子目录（节省空间）
        from huggingface_hub import hf_hub_download
        
        model_path.mkdir(parents=True, exist_ok=True)
        layout_model_path.mkdir(parents=True, exist_ok=True)
        
        files_to_download = [
            "PP-DocLayoutV2/config.json",
            "PP-DocLayoutV2/inference.yml",
            "PP-DocLayoutV2/inference.pdmodel",
            "PP-DocLayoutV2/inference.pdiparams",
        ]
        
        for file_path in files_to_download:
            filename = file_path.split("/")[-1]
            print(f"   下载: {filename}...")
            hf_hub_download(
                repo_id="PaddlePaddle/PaddleOCR-VL",
                filename=file_path,
                local_dir=str(model_path),
                local_dir_use_symlinks=False,
            )
        
        print()
        print(f"✅ 模型下载完成: {layout_model_path}")
        return True
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
        print()
        print("请手动下载模型:")
        print("  1. 访问 https://huggingface.co/PaddlePaddle/PaddleOCR-VL")
        print("  2. 下载 PP-DocLayoutV2 文件夹")
        print(f"  3. 放到 {layout_model_path}")
        return False


def check_models() -> bool:
    """检查模型是否存在"""
    model_dir = os.getenv("DOC_LAYOUT_MODEL_DIR", "models/PaddleOCR-VL/PP-DocLayoutV2")
    model_path = Path(model_dir)
    
    required_files = ["inference.pdmodel", "inference.pdiparams", "inference.yml"]
    missing = [f for f in required_files if not (model_path / f).exists()]
    
    if missing:
        print(f"⚠️ 缺少模型文件: {missing}")
        return False
    return True


if __name__ == "__main__":
    import sys
    
    print("=" * 50)
    print("  PaddleOCR-VL 模型下载工具")
    print("=" * 50)
    print()
    
    success = download_paddleocr_models()
    sys.exit(0 if success else 1)
