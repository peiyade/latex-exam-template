#!/usr/bin/env python3
"""
LaTeX 题目图片生成器
将试卷中的题目拆分为独立的 PNG 图片
"""

import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

from parser import LaTeXParser, Problem, ProblemType


class ImageGenerator:
    """题目图片生成器"""
    
    # 中文字体备选列表
    CJK_FONTS = [
        "SimSun",           # Windows 宋体
        "Noto Serif CJK SC", # Linux 默认
        "Source Han Serif SC",
        "Adobe Song Std",
        "STSong",           # macOS
    ]
    
    def __init__(
        self,
        dpi: int = 300,
        image_width: str = "800pt"
    ):
        self.dpi = dpi
        self.image_width = image_width
        
        self.project_root = Path(__file__).parent.parent
        self.output_dir = self.project_root / "output" / "2025-2026-Exercise-2"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.temp_dir: Optional[Path] = None
    
    def __enter__(self):
        """上下文管理器入口 - 创建临时目录"""
        self.temp_dir = self.project_root / ".temp" / f"latex_img_{int(time.time())}"
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口 - 清理临时目录"""
        if self.temp_dir and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def check_xelatex(self) -> bool:
        """检查本地 xelatex 是否可用"""
        if shutil.which("xelatex"):
            return True
        print("❌ 未检测到本地 xelatex，请先安装 TeX Live / MacTeX，并确保 xelatex 在 PATH 中")
        return False
    
    def check_poppler(self) -> bool:
        """检查是否安装了 poppler (pdftoppm)"""
        try:
            subprocess.run(
                ["pdftoppm", "-v"],
                capture_output=True,
                check=True
            )
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            return False
    
    def generate_standalone_preamble(self) -> str:
        """生成 standalone 文档的导言区"""
        # 将 pt 转换为 cm（近似）用于 minipage
        width_cm = int(self.image_width.replace('pt', '')) / 28.35
        return f"""\\documentclass[border=10pt]{{standalone}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath,amssymb}}
\\usepackage{{unicode-math}}
% 中文支持 - 使用 ctex 包自动配置字体
\\usepackage[fontset=fandol]{{ctex}}
\\usepackage{{xcolor}}
\\usepackage{{ulem}}
\\usepackage{{pifont}}
\\usepackage{{tikz}}
\\usepackage{{enumitem}}
\\usepackage{{array}}
\\usepackage{{tabularx}}

\\usetikzlibrary{{positioning, calc, shapes.geometric, arrows.meta}}

% 数学符号
\\DeclareMathOperator{{\\dif}}{{\\mathop{{}}\\!\\mathrm{{d}}}}
\\DeclareMathOperator{{\\upe}}{{\\operatorname{{e}}}}
\\DeclareMathOperator{{\\upi}}{{\\operatorname{{i}}}}
\\renewcommand{{\\le}}{{\\leqslant}}
\\renewcommand{{\\leq}}{{\\leqslant}}
\\renewcommand{{\\ge}}{{\\geqslant}}
\\renewcommand{{\\geq}}{{\\geqslant}}

% 文档类模拟
\\newcommand{{\\fillin}}[1]{{\\underline{{\\hspace{{0.5em}}#1\\hspace{{0.5em}}}}}}
\\definecolor{{answerred}}{{RGB}}{{255,0,0}}

\\begin{{document}}
\\begin{{minipage}}{{{width_cm:.1f}cm}}
"""
    
    def _generate_font_setup(self) -> str:
        """生成字体设置代码，尝试多个备选字体"""
        font_code = "% 中文字体设置\n"
        
        # 构建字体测试代码
        font_tests = []
        for font in self.CJK_FONTS:
            font_tests.append(f"    \\setCJKmainfont{{{font}}}")
        
        # 使用 try 块尝试每个字体
        font_code += "\\IfFontExistsTF{SimSun}{\n"
        font_code += "    \\setCJKmainfont{SimSun}\n"
        font_code += "}{\\IfFontExistsTF{Noto Serif CJK SC}{\n"
        font_code += "    \\setCJKmainfont{Noto Serif CJK SC}\n"
        font_code += "}{\\IfFontExistsTF{Source Han Serif SC}{\n"
        font_code += "    \\setCJKmainfont{Source Han Serif SC}\n"
        font_code += "}{\\IfFontExistsTF{STSong}{\n"
        font_code += "    \\setCJKmainfont{STSong}\n"
        font_code += "}{\n"
        font_code += "    \\setCJKmainfont{FandolSong}\n"
        font_code += "}}}}"
        
        return font_code
    
    @staticmethod
    def generate_standalone_footer() -> str:
        """生成 standalone 文档的结尾"""
        return "\\end{minipage}\n\\end{document}"
    
    def generate_choice_images(self, problem: Problem) -> List[Path]:
        """
        生成选择题相关图片
        返回生成的所有图片路径列表
        """
        generated_files = []
        base_name = f"choice_{problem.id}"
        display_name = f"选择题{problem.id}"
        answer = problem.choice_answer or "X"
        
        # 1. 生成题干图片（含选项列表，不显示答案）
        print(f"  📄 生成题干...")
        stem_content = self._build_choice_stem(problem)
        stem_tex = self._create_standalone_tex(stem_content)
        stem_pdf = self._compile_tex(stem_tex, f"{base_name}_stem")
        
        if stem_pdf:
            stem_png = self._convert_pdf_to_png(
                stem_pdf, 
                f"{display_name}题干:{answer}.png"
            )
            if stem_png:
                generated_files.append(stem_png)
        
        # 2. 生成每个选项的图片
        for option in problem.choice_options:
            print(f"  📄 生成选项 {option.label}...")
            option_content = f"({option.label}) {option.content}"
            option_tex = self._create_standalone_tex(option_content)
            option_pdf = self._compile_tex(option_tex, f"{base_name}_opt_{option.label}")
            
            if option_pdf:
                option_png = self._convert_pdf_to_png(
                    option_pdf,
                    f"{display_name}选项:{option.label}.png"
                )
                if option_png:
                    generated_files.append(option_png)
        
        return generated_files
    
    def generate_fillin_images(self, problem: Problem) -> List[Path]:
        """生成填空题相关图片"""
        generated_files = []
        base_name = f"fillin_{problem.id}"
        display_name = f"填空题{problem.id}"
        
        # 1. 生成题干图片（fillin 显示为下划线空白）
        print(f"  📄 生成题干...")
        stem_content = problem.body_clean
        stem_tex = self._create_standalone_tex(stem_content)
        stem_pdf = self._compile_tex(stem_tex, f"{base_name}_stem")
        
        if stem_pdf:
            stem_png = self._convert_pdf_to_png(stem_pdf, f"{display_name}题干.png")
            if stem_png:
                generated_files.append(stem_png)
        
        # 2. 生成每个答案的图片
        for answer in problem.fillin_answers:
            print(f"  📄 生成答案 {answer.index}...")
            answer_content = answer.content
            answer_tex = self._create_standalone_tex(answer_content)
            answer_pdf = self._compile_tex(answer_tex, f"{base_name}_ans_{answer.index}")
            
            if answer_pdf:
                answer_png = self._convert_pdf_to_png(
                    answer_pdf,
                    f"{display_name}答案{answer.index}.png"
                )
                if answer_png:
                    generated_files.append(answer_png)
        
        return generated_files
    
    def generate_solution_images(self, problem: Problem) -> List[Path]:
        """生成解答题相关图片"""
        generated_files = []
        base_name = f"solution_{problem.id}"
        display_name = f"计算题{problem.id}"
        
        # 1. 生成题干图片
        print(f"  📄 生成题干...")
        stem_content = problem.body
        stem_tex = self._create_standalone_tex(stem_content)
        stem_pdf = self._compile_tex(stem_tex, f"{base_name}_stem")
        
        if stem_pdf:
            stem_png = self._convert_pdf_to_png(stem_pdf, f"{display_name}题干.png")
            if stem_png:
                generated_files.append(stem_png)
        
        # 2. 生成答案图片（如果有 solution）
        if problem.solution:
            print(f"  📄 生成答案...")
            solution_content = f"解\\quad {problem.solution}"
            solution_tex = self._create_standalone_tex(solution_content)
            solution_pdf = self._compile_tex(solution_tex, f"{base_name}_solution")
            
            if solution_pdf:
                solution_png = self._convert_pdf_to_png(
                    solution_pdf,
                    f"{display_name}答案.png"
                )
                if solution_png:
                    generated_files.append(solution_png)
        
        return generated_files
    
    def generate_note_image(self, problem: Problem, problem_type_str: str) -> Optional[Path]:
        """生成笔记图片（如果有 note）"""
        if not problem.note:
            return None
        
        print(f"  📄 生成笔记...")
        base_name = f"note_{problem.id}"
        display_name = f"{problem_type_str}{problem.id}"
        
        note_content = f"注\\quad {problem.note}"
        note_tex = self._create_standalone_tex(note_content)
        note_pdf = self._compile_tex(note_tex, f"{base_name}_note")
        
        if note_pdf:
            note_png = self._convert_pdf_to_png(note_pdf, f"{display_name}笔记.png")
            return note_png
        
        return None
    
    def _build_choice_stem(self, problem: Problem) -> str:
        """构建选择题题干（含选项，不含答案）"""
        lines = [problem.body_clean, ""]
        
        # 添加选项
        for option in problem.choice_options:
            lines.append(f"({option.label}) {option.content}")
        
        return "\n".join(lines)
    
    def _create_standalone_tex(self, content: str) -> str:
        """创建完整的 standalone tex 文档"""
        preamble = self.generate_standalone_preamble()
        footer = self.generate_standalone_footer()
        
        # 清理内容中的特殊标记
        content = self._clean_content(content)
        
        return f"{preamble}\n{content}\n{footer}"
    
    def _clean_content(self, content: str) -> str:
        """清理内容，移除或替换不支持的命令"""
        # 移除 answer 命令（如果有）
        content = content.replace("\\answer{", "{")
        
        # 处理 \pickout 和 \pickin（应该已经被移除，但以防万一）
        import re
        content = re.sub(r'\\pickout\{.*?\}', '', content)
        content = re.sub(r'\\pickin\{.*?\}', '', content)
        
        # 处理 \options 命令（选择题选项已单独处理，这里应该没有）
        content = re.sub(r'\\options\{.*?\}\{.*?\}\{.*?\}\{.*?\}', '', content, flags=re.DOTALL)
        
        return content.strip()
    
    def _compile_tex(self, tex_content: str, basename: str) -> Optional[Path]:
        """
        编译 tex 文件为 PDF（standalone 文档只需编译一次）
        返回生成的 PDF 路径，失败返回 None
        """
        if not self.temp_dir:
            raise RuntimeError("必须在上下文管理器中使用")
        
        tex_file = self.temp_dir / f"{basename}.tex"
        
        # 写入 tex 文件
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(tex_content)
        
        # 编译（standalone 文档只需编译一次）
        try:
            result = subprocess.run(
                [
                    "xelatex",
                    "-interaction=nonstopmode",
                    "-halt-on-error",
                    "-output-directory",
                    str(self.temp_dir),
                    str(tex_file),
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            # 检查 PDF 是否生成（即使返回码非零，PDF 可能已生成）
            pdf_file = self.temp_dir / f"{basename}.pdf"
            if pdf_file.exists() and pdf_file.stat().st_size > 0:
                return pdf_file
            
            # 如果没有生成 PDF，则报错
            if result.returncode != 0:
                log_file = self.temp_dir / f"{basename}.log"
                if log_file.exists():
                    error_log = self.output_dir / f"{basename}_error.log"
                    shutil.copy(log_file, error_log)
                    print(f"    ⚠️  编译失败，日志保存至: {error_log}")
                return None
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"    ⚠️  编译超时")
            return None
        except FileNotFoundError:
            print("    ⚠️  未找到 xelatex")
            return None
        except Exception as e:
            print(f"    ⚠️  编译错误: {e}")
            return None
    
    def _convert_pdf_to_png(self, pdf_path: Path, output_name: str) -> Optional[Path]:
        """
        将 PDF 转换为 PNG
        使用 pdftoppm (poppler)
        """
        try:
            # 使用唯一的临时前缀避免冲突
            import uuid
            output_prefix = self.temp_dir / f"img_{uuid.uuid4().hex[:8]}"
            
            result = subprocess.run(
                [
                    "pdftoppm",
                    "-png",
                    "-r", str(self.dpi),
                    "-singlefile",
                    str(pdf_path),
                    str(output_prefix)
                ],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                print(f"    ⚠️  PDF 转换失败: {result.stderr}")
                return None
            
            # pdftoppm 使用 -singlefile 时不会添加 -1 后缀
            generated_png = Path(f"{output_prefix}.png")
            
            if generated_png.exists():
                # 移动到输出目录
                final_path = self.output_dir / output_name
                try:
                    shutil.move(str(generated_png), str(final_path))
                    return final_path
                except Exception as e:
                    print(f"    ⚠️  移动文件失败: {e}")
                    return None
            
            return None
            
        except subprocess.TimeoutExpired:
            print(f"    ⚠️  PDF 转换超时")
            return None
        except Exception as e:
            print(f"    ⚠️  PDF 转换错误: {e}")
            return None
    
    def generate_report(self, problems: List[Problem], generated_files: dict) -> str:
        """生成处理报告"""
        lines = [
            "=" * 50,
            "            图片生成报告",
            "=" * 50,
            "",
            f"题目总数: {len(problems)}",
            "",
            "题目分类统计:",
        ]
        
        # 统计各类题目数量
        type_count = {"choice": 0, "fillin": 0, "solution": 0, "unknown": 0}
        for p in problems:
            type_count[p.type.value] += 1
        
        lines.append(f"  选择题: {type_count['choice']} 道")
        lines.append(f"  填空题: {type_count['fillin']} 道")
        lines.append(f"  解答题: {type_count['solution']} 道")
        lines.append("")
        lines.append(f"生成图片总数: {sum(len(files) for files in generated_files.values())}")
        lines.append("")
        lines.append("输出目录:")
        lines.append(f"  {self.output_dir}")
        lines.append("")
        lines.append("=" * 50)
        
        return "\n".join(lines)


def interactive_generate():
    """交互式生成图片"""
    print("=" * 50)
    print("  LaTeX 题目图片生成工具")
    print("=" * 50)
    
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
        return
    
    # 查找文件
    tex_file = project_root / f"{base_name}.tex"
    if not tex_file.exists():
        tex_file = project_root / "examples" / f"{base_name}.tex"
    
    if not tex_file.exists():
        print(f"❌ 找不到文件: {base_name}.tex")
        return
    
    # 输入图片宽度
    width_input = input("请输入图片宽度（像素，默认 800）: ").strip()
    image_width = f"{width_input}pt" if width_input.isdigit() else "800pt"
    
    print()
    
    # 开始处理
    with ImageGenerator(image_width=image_width) as generator:
        # 检查依赖
        if not generator.check_xelatex():
            return
        
        if not generator.check_poppler():
            print("❌ 未检测到 poppler (pdftoppm)")
            print("请安装:")
            print("  macOS: brew install poppler")
            print("  Ubuntu: sudo apt-get install poppler-utils")
            return
        
        # 读取并解析 tex 文件
        print(f"📝 正在解析: {tex_file}")
        content = tex_file.read_text(encoding='utf-8')
        parser = LaTeXParser(content)
        problems = parser.parse()
        
        print(f"✅ 解析完成，共 {len(problems)} 道题目\n")
        
        # 生成图片
        generated_files = {}
        
        for problem in problems:
            print(f"【题目 {problem.id}】{problem.type.value}")
            
            files = []
            
            if problem.type == ProblemType.CHOICE:
                files = generator.generate_choice_images(problem)
                type_str = "选择题"
            elif problem.type == ProblemType.FILLIN:
                files = generator.generate_fillin_images(problem)
                type_str = "填空题"
            else:
                files = generator.generate_solution_images(problem)
                type_str = "计算题"
            
            # 生成笔记图片
            note_file = generator.generate_note_image(problem, type_str)
            if note_file:
                files.append(note_file)
            
            generated_files[problem.id] = files
            print(f"  ✅ 生成 {len(files)} 张图片\n")
        
        # 输出报告
        report = generator.generate_report(problems, generated_files)
        print(report)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="LaTeX 题目图片生成工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python image_generator.py              # 交互式模式
  python image_generator.py -f demo      # 处理 demo.tex
  python image_generator.py -f demo -w 1000  # 指定宽度 1000px
        """
    )
    
    parser.add_argument(
        "-f", "--file",
        help="主文件名（不含 .tex 后缀）"
    )
    
    parser.add_argument(
        "-d", "--directory",
        help="tex 文件所在目录"
    )
    
    parser.add_argument(
        "-w", "--width",
        default="800",
        help="图片宽度（像素，默认 800）"
    )
    
    parser.add_argument(
        "--dpi",
        type=int,
        default=300,
        help="图片 DPI（默认 300）"
    )
    
    args = parser.parse_args()
    
    if args.file:
        # 命令行模式
        project_root = Path(__file__).parent.parent
        tex_dir = Path(args.directory) if args.directory else project_root
        tex_file = tex_dir / f"{args.file}.tex"
        
        if not tex_file.exists():
            tex_file = project_root / "examples" / f"{args.file}.tex"
        
        if not tex_file.exists():
            print(f"❌ 找不到文件: {args.file}.tex")
            sys.exit(1)
        
        image_width = f"{args.width}pt"
        
        with ImageGenerator(
            dpi=args.dpi,
            image_width=image_width
        ) as generator:
            
            if not generator.check_xelatex():
                sys.exit(1)
            
            if not generator.check_poppler():
                print("❌ 未检测到 poppler")
                sys.exit(1)
            
            print(f"📝 正在解析: {tex_file}")
            content = tex_file.read_text(encoding='utf-8')
            parser = LaTeXParser(content)
            problems = parser.parse()
            
            print(f"✅ 解析完成，共 {len(problems)} 道题目\n")
            
            generated_files = {}
            
            for problem in problems:
                print(f"【题目 {problem.id}】{problem.type.value}")
                
                files = []
                
                if problem.type == ProblemType.CHOICE:
                    files = generator.generate_choice_images(problem)
                    type_str = "选择题"
                elif problem.type == ProblemType.FILLIN:
                    files = generator.generate_fillin_images(problem)
                    type_str = "填空题"
                else:
                    files = generator.generate_solution_images(problem)
                    type_str = "计算题"
                
                note_file = generator.generate_note_image(problem, type_str)
                if note_file:
                    files.append(note_file)
                
                generated_files[problem.id] = files
                print(f"  ✅ 生成 {len(files)} 张图片\n")
            
            report = generator.generate_report(problems, generated_files)
            print(report)
    else:
        # 交互式模式
        interactive_generate()


if __name__ == "__main__":
    main()
