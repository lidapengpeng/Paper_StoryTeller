#!/usr/bin/env python3
"""
Paper Storyteller 环境检查与安装脚本
运行此脚本检查环境是否正确配置
"""

import sys
import os
import subprocess
from pathlib import Path

def print_step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print('='*60)

def print_ok(msg):
    print(f"  ✅ {msg}")

def print_warn(msg):
    print(f"  ⚠️  {msg}")

def print_err(msg):
    print(f"  ❌ {msg}")

def check_python():
    print_step("检查 Python 版本")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print_ok(f"Python {version.major}.{version.minor}.{version.micro}")
        return True
    else:
        print_err(f"需要 Python 3.8+，当前版本: {version.major}.{version.minor}")
        return False

def check_dependencies():
    print_step("检查核心依赖")
    
    dependencies = [
        ("paddleocr", "PaddleOCR (图像提取)"),
        ("paddlepaddle", "PaddlePaddle (深度学习框架)"),
        ("fitz", "PyMuPDF (PDF 处理)"),
        ("google.generativeai", "Google Generative AI"),
        ("cv2", "OpenCV (图像处理)"),
        ("PIL", "Pillow (图像处理)"),
    ]
    
    all_ok = True
    for module, name in dependencies:
        try:
            __import__(module.replace(".", "_") if "." in module else module)
            print_ok(name)
        except ImportError:
            print_err(f"{name} - 未安装")
            all_ok = False
    
    return all_ok

def check_model():
    print_step("检查 PaddleOCR 模型")
    
    model_dir = Path("models/PaddleOCR-VL/PP-DocLayoutV2")
    required_files = ["inference.pdmodel", "inference.pdiparams", "inference.yml"]
    
    if not model_dir.exists():
        print_warn(f"模型目录不存在: {model_dir}")
        print("  首次运行时会自动下载模型（约 200MB）")
        print("  或者手动下载：")
        print("  git clone https://huggingface.co/PaddlePaddle/PaddleOCR-VL models/PaddleOCR-VL")
        return False
    
    missing = [f for f in required_files if not (model_dir / f).exists()]
    if missing:
        print_warn(f"模型文件缺失: {missing}")
        return False
    
    print_ok("PP-DocLayoutV2 模型已就绪")
    return True

def check_api_key():
    print_step("检查 API Key")
    
    api_key = os.getenv("GOOGLE_API_KEY")
    if api_key:
        print_ok(f"GOOGLE_API_KEY 已设置 ({api_key[:10]}...)")
        return True
    else:
        print_warn("GOOGLE_API_KEY 未设置")
        print("  请设置环境变量：")
        print("    Windows: $env:GOOGLE_API_KEY='your_key'")
        print("    Linux/Mac: export GOOGLE_API_KEY='your_key'")
        print("  或者运行时传入: python paper_storyteller_skill.py --api-key YOUR_KEY")
        return False

def main():
    print("\n" + "="*60)
    print("  Paper Storyteller 环境检查")
    print("="*60)
    
    results = []
    results.append(("Python 版本", check_python()))
    results.append(("核心依赖", check_dependencies()))
    results.append(("PaddleOCR 模型", check_model()))
    results.append(("API Key", check_api_key()))
    
    print_step("检查结果")
    
    all_ok = True
    for name, ok in results:
        if ok:
            print_ok(name)
        else:
            print_warn(name)
            all_ok = False
    
    if all_ok:
        print("\n🎉 环境配置完成！可以开始使用：")
        print("   python paper_storyteller_skill.py https://arxiv.org/abs/2311.14405")
    else:
        print("\n⚠️  部分配置未完成，请按照上述提示修复。")
        print("   安装依赖: pip install -r requirements.txt")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
