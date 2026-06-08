#!/usr/bin/env python3
"""
一键生成工具
完整流程：tex → 解析 → PDF → PNG
"""

import argparse
import sys
from pathlib import Path

# 导入其他模块
from pdf_generator import PDFGenerator
from pdf_to_png import convert_all_pdfs


def generate_all(base_name: str, tex_dir: Path, image_width: str, dpi: int, output_dir: Path = None) -> bool:
    """
    一键生成完整流程
    
    Args:
        base_name: tex 文件名（不含扩展名）
        tex_dir: tex 文件所在目录
        image_width: 图片宽度（如 "1000pt"）
        dpi: PNG 分辨率
        output_dir: 输出目录，默认 output/{base_name}
    
    Returns:
        bool: 是否全部成功
    """
    project_root = Path(__file__).parent.parent
    
    # 确定 tex 文件路径
    if tex_dir is None:
        tex_dir = project_root
    else:
        tex_dir = Path(tex_dir)
    
    source_file = tex_dir / f"{base_name}.tex"
    if not source_file.exists():
        source_file = project_root / "examples" / f"{base_name}.tex"
    
    if not source_file.exists():
        print(f"❌ 找不到文件: {base_name}.tex")
        return False
    
    # 确定输出目录
    if output_dir is None:
        output_dir = project_root / "output" / base_name
    else:
        output_dir = Path(output_dir)
    
    pdf_dir = output_dir / "pdfs"
    png_dir = output_dir / "images"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    # Avoid mixing stale files from earlier versions of the same source.
    for directory, patterns in (
        (pdf_dir, ("*.pdf", "*.tex", "*.aux", "*.log")),
        (png_dir, ("*.png",)),
    ):
        for pattern in patterns:
            for path in directory.glob(pattern):
                path.unlink()
    
    print("=" * 60)
    print("  LaTeX 试卷图片生成工具 - 完整流程")
    print("=" * 60)
    print(f"\n📄 源文件: {source_file}")
    print(f"📐 图片宽度: {image_width}")
    print(f"🎯 PNG DPI: {dpi}")
    print(f"📁 输出目录: {output_dir}")
    print()
    
    # 步骤 1: 生成 PDF
    print("━" * 60)
    print("【步骤 1/2】生成 PDF 文件...")
    print("━" * 60)
    
    pdf_generator = PDFGenerator(image_width=image_width, output_dir=pdf_dir)
    success = pdf_generator.generate(base_name, tex_dir)
    
    if not success:
        print("\n❌ PDF 生成失败，流程终止")
        return False
    
    # 步骤 2: PDF 转 PNG
    print("\n" + "━" * 60)
    print("【步骤 2/2】PDF 转换为 PNG...")
    print("━" * 60)
    
    png_files = convert_all_pdfs(pdf_dir, png_dir, dpi)
    
    if not png_files:
        print("\n❌ PNG 转换失败")
        return False
    
    # 完成报告
    print("\n" + "=" * 60)
    print("  ✅ 全部完成！")
    print("=" * 60)
    print(f"\n📁 PDF 目录: {pdf_dir}")
    print(f"   共 {len(list(pdf_dir.glob('*.pdf')))} 个 PDF 文件")
    print(f"\n📁 PNG 目录: {png_dir}")
    print(f"   共 {len(png_files)} 个 PNG 文件")
    print()
    
    # 显示文件示例
    print("📋 生成的文件示例:")
    for png in png_files[:5]:
        print(f"   • {png.name}")
    if len(png_files) > 5:
        print(f"   ... 还有 {len(png_files) - 5} 个文件")
    
    print()
    return True


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="LaTeX 试卷图片一键生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
工作流程:
  1. 解析 tex 文件，提取题目
  2. 为每个题目组件生成独立 PDF
  3. 将 PDF 转换为 PNG 图片

示例:
  python generate_all.py                    # 交互式模式
  python generate_all.py -f demo            # 处理 demo.tex
  python generate_all.py -f demo -w 1200    # 指定宽度 1200px
  python generate_all.py -f demo --dpi 150  # 指定 150 DPI
        """
    )
    
    parser.add_argument(
        "-f", "--file",
        help="主文件名（不含 .tex 后缀）"
    )
    
    parser.add_argument(
        "-d", "--directory",
        help="tex 文件所在目录（默认为项目根目录）"
    )
    
    parser.add_argument(
        "-w", "--width",
        default="1000",
        help="图片宽度（像素，默认 1000）"
    )
    
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="PNG 分辨率（默认: 300）"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出目录（默认: output/{文件名}）"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # 命令行模式
        image_width = f"{args.width}pt"
        output_dir = Path(args.output) if args.output else None
        success = generate_all(args.file, args.directory, image_width, args.dpi, output_dir)
        sys.exit(0 if success else 1)
    else:
        # 交互式模式
        print("=" * 60)
        print("  LaTeX 试卷图片一键生成工具")
        print("=" * 60)
        
        project_root = Path(__file__).parent.parent
        tex_files = list(project_root.glob("*.tex")) + list((project_root / "examples").glob("*.tex"))
        
        if tex_files:
            print("\n📂 检测到以下 tex 文件:")
            for i, f in enumerate(tex_files, 1):
                rel_path = f.relative_to(project_root)
                print(f"   {i}. {rel_path}")
        
        print()
        base_name = input("请输入主文件名（不含 .tex 后缀）: ").strip()
        
        if not base_name:
            print("❌ 文件名不能为空")
            sys.exit(1)
        
        width_input = input("请输入图片宽度（像素，默认 1000）: ").strip()
        image_width = f"{width_input}pt" if width_input.isdigit() else "1000pt"
        
        dpi_input = input("请输入 PNG 分辨率（默认 300）: ").strip()
        dpi = int(dpi_input) if dpi_input.isdigit() else 300
        
        print()
        success = generate_all(base_name, None, image_width, dpi)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
