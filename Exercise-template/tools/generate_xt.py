#!/usr/bin/env python3
"""
学习通图片生成脚本
───────────────────
使用优化参数生成适合手机屏幕（~600px 宽）的逐题拆分图片。

推荐场景：
  • 学习通、雨课堂等在线教育平台
  • 学生手机端查看
  • 需要逐题上传题库

参数说明：
  • 宽度 288pt × DPI 150 ≈ 600px（手机屏幕显示的黄金宽度）
  • 文件体积极小（通常 < 10KB/张），学生加载无感

用法：
  python3 tools/generate_xt.py 2025-2026-Exercise-3
  python3 tools/generate_xt.py demo -d examples
"""

import argparse
import sys
from pathlib import Path

# 将项目 tools 目录加入路径
_project_root = Path(__file__).parent.parent
sys.path.insert(0, str(_project_root / "tools"))

from generate_all import generate_all


# ───────────────────────────────
# 学习通优化参数（600px 宽度）
# ───────────────────────────────
XT_WIDTH = "288pt"   # 288 pt × 150 DPI / 72 ≈ 600 px
XT_DPI = 150


def main():
    parser = argparse.ArgumentParser(
        description="生成适合学习通/手机屏幕的试卷拆分图片（~600px 宽度优化）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python3 tools/generate_xt.py 2025-2026-Exercise-3
  python3 tools/generate_xt.py demo -d examples -o ../output/demo_xt
        """
    )

    parser.add_argument(
        "filename",
        help="tex 文件名（不含 .tex 后缀）"
    )

    parser.add_argument(
        "-d", "--directory",
        default="examples",
        help="tex 文件所在目录（默认: examples）"
    )

    parser.add_argument(
        "-o", "--output",
        help="输出目录（默认: output/{文件名}）"
    )

    args = parser.parse_args()

    tex_dir = _project_root / args.directory
    output_dir = Path(args.output) if args.output else None

    print("=" * 60)
    print("  学习通图片生成脚本")
    print(f"  宽度: {XT_WIDTH} | DPI: {XT_DPI} ≈ 600px")
    print("=" * 60)
    print()

    success = generate_all(
        base_name=args.filename,
        tex_dir=tex_dir,
        image_width=XT_WIDTH,
        dpi=XT_DPI,
        output_dir=output_dir
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
