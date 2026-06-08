#!/usr/bin/env python3
"""
PDF 转 PNG 工具
将 pdf_generator.py 生成的 PDF 转换为 PNG 图片
"""

import argparse
import subprocess
from pathlib import Path
from typing import List, Optional


def pdf_to_png(pdf_path: Path, output_path: Path, dpi: int = 300) -> bool:
    """
    将单个 PDF 转换为 PNG
    
    Args:
        pdf_path: PDF 文件路径
        output_path: 输出 PNG 路径
        dpi: 分辨率
    
    Returns:
        bool: 是否成功
    """
    try:
        # 使用 pdftoppm 转换
        # 输出路径不包含扩展名，pdftoppm 会自动添加 -1.png
        result = subprocess.run(
            [
                "pdftoppm",
                "-png",
                "-r", str(dpi),
                "-singlefile",
                str(pdf_path),
                str(output_path.with_suffix(""))  # 去掉 .png，pdftoppm 会添加
            ],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            print(f"    ⚠️  转换失败: {result.stderr}")
            return False
        
        # pdftoppm 使用 -singlefile 时不添加 -1 后缀
        generated = output_path.with_suffix(".png")
        if generated.exists():
            return True
        
        # 如果上面的路径不存在，尝试带 -1 后缀的
        generated_with_number = output_path.parent / f"{output_path.stem}-1.png"
        if generated_with_number.exists():
            # 重命名为目标名称
            generated_with_number.rename(generated)
            return True
        
        return False
        
    except Exception as e:
        print(f"    ⚠️  转换错误: {e}")
        return False


def convert_all_pdfs(pdf_dir: Path, output_dir: Path, dpi: int = 300) -> List[Path]:
    """
    转换目录下所有 PDF 为 PNG
    
    Args:
        pdf_dir: PDF 文件所在目录
        output_dir: PNG 输出目录
        dpi: 分辨率
    
    Returns:
        List[Path]: 生成的 PNG 文件列表
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    
    pdf_files = sorted(pdf_dir.glob("*.pdf"))
    generated_files = []
    
    print(f"📝 找到 {len(pdf_files)} 个 PDF 文件")
    print(f"🎯 输出目录: {output_dir}")
    print(f"📐 DPI: {dpi}")
    print("-" * 50)
    
    for i, pdf_file in enumerate(pdf_files, 1):
        # 保持文件名一致，只改扩展名
        png_name = pdf_file.name.replace(".pdf", ".png")
        output_path = output_dir / png_name
        
        print(f"[{i}/{len(pdf_files)}] {pdf_file.name} → {png_name}")
        
        if pdf_to_png(pdf_file, output_path, dpi):
            generated_files.append(output_path)
            print(f"     ✅ 成功")
        else:
            print(f"     ❌ 失败")
    
    print("-" * 50)
    print(f"✅ 共生成 {len(generated_files)} 个 PNG 文件")
    
    return generated_files


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="PDF 转 PNG 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pdf_to_png.py                    # 转换 output/pdfs/ 下所有 PDF
  python pdf_to_png.py -i output/pdfs     # 指定输入目录
  python pdf_to_png.py -o output/images   # 指定输出目录
  python pdf_to_png.py --dpi 150          # 设置 150 DPI
        """
    )
    
    parser.add_argument(
        "-i", "--input",
        default="output/pdfs",
        help="PDF 输入目录 (默认: output/pdfs)"
    )
    
    parser.add_argument(
        "-o", "--output",
        default="output/images",
        help="PNG 输出目录 (默认: output/images)"
    )
    
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="图片 DPI (默认: 300)"
    )
    
    args = parser.parse_args()
    
    pdf_dir = Path(args.input)
    output_dir = Path(args.output)
    
    if not pdf_dir.exists():
        print(f"❌ 输入目录不存在: {pdf_dir}")
        return
    
    convert_all_pdfs(pdf_dir, output_dir, args.dpi)


if __name__ == "__main__":
    main()
