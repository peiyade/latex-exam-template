#!/usr/bin/env python3
"""
LaTeX 题目 PDF 生成器
为每个题目组件生成独立的 PDF 文件，便于检查正则解析结果
"""

import argparse
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from parser import LaTeXParser, Problem, ProblemType


class PDFGenerator:
    """题目 PDF 生成器"""
    
    def __init__(
        self,
        image_width: str = "800pt",
        output_dir: Optional[Path] = None
    ):
        self.image_width = image_width
        
        self.project_root = Path(__file__).parent.parent
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.project_root / "output" / "pdfs"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def check_xelatex() -> bool:
        """检查本地 xelatex 是否可用"""
        if shutil.which("xelatex"):
            return True
        print("❌ 未检测到本地 xelatex，请先安装 TeX Live / MacTeX，并确保 xelatex 在 PATH 中")
        return False
    
    def generate_standalone_preamble(self) -> str:
        """生成 standalone 文档的导言区"""
        # 将 pt 转换为 cm（近似）用于 minipage
        width_cm = int(self.image_width.replace('pt', '')) / 28.35
        return f"""\\documentclass[border=10pt]{{standalone}}
\\usepackage[utf8]{{inputenc}}
\\usepackage{{amsmath,amssymb}}
\\usepackage{{unicode-math}}
\\usepackage[fontset=fandol]{{ctex}}
\\usepackage{{xcolor}}
\\usepackage{{ulem}}
\\usepackage{{pifont}}
\\usepackage{{tikz}}
\\usepackage{{enumitem}}
\\usepackage{{array}}
\\usepackage{{tabularx}}

\\usetikzlibrary{{positioning, calc, shapes.geometric, arrows.meta}}

\\DeclareMathOperator{{\\dif}}{{\\mathop{{}}\\!\\mathrm{{d}}}}
\\DeclareMathOperator{{\\upe}}{{\\operatorname{{e}}}}
\\renewcommand{{\\le}}{{\\leqslant}}
\\renewcommand{{\\leq}}{{\\leqslant}}
\\renewcommand{{\\ge}}{{\\geqslant}}
\\renewcommand{{\\geq}}{{\\geqslant}}

\\newcommand{{\\fillin}}[1]{{\\underline{{\\hspace{{0.5em}}#1\\hspace{{0.5em}}}}}}

\\begin{{document}}
\\begin{{minipage}}{{{width_cm:.1f}cm}}
"""
    
    @staticmethod
    def generate_standalone_footer() -> str:
        """生成 standalone 文档的结尾"""
        return "\\end{minipage}\n\\end{document}"
    
    def _create_standalone_tex(self, content: str) -> str:
        """创建完整的 standalone tex 文档"""
        preamble = self.generate_standalone_preamble()
        footer = self.generate_standalone_footer()
        
        # 清理内容
        content = self._clean_content(content)
        
        return f"{preamble}\n{content}\n{footer}"
    
    def _clean_content(self, content: str) -> str:
        """清理内容"""
        import re
        content = content.replace("\\answer{", "{")
        content = re.sub(r'\\pickout\{.*?\}', '', content)
        content = re.sub(r'\\pickin\{.*?\}', '', content)
        content = re.sub(r'\\options(?:\s*)\{.*?\}\s*\{.*?\}\s*\{.*?\}\s*\{.*?\}', '', content, flags=re.DOTALL)
        return content.strip()
    
    def _compile_tex(self, tex_content: str, basename: str) -> Optional[Path]:
        """使用本地 xelatex 编译 tex 文件为 PDF"""
        tex_file = self.output_dir / f"{basename}.tex"
        
        # 写入 tex 文件
        with open(tex_file, 'w', encoding='utf-8') as f:
            f.write(tex_content)
        
        pdf_file = self.output_dir / f"{basename}.pdf"
        
        try:
            result = subprocess.run(
                [
                    'xelatex',
                    '-interaction=nonstopmode',
                    '-halt-on-error',
                    '-output-directory',
                    str(self.output_dir),
                    str(tex_file)
                ],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if pdf_file.exists() and pdf_file.stat().st_size > 0:
                return pdf_file
            
            if result.returncode != 0:
                log_file = self.output_dir / f"{basename}.log"
                if log_file.exists():
                    print(f"    ⚠️  编译失败，查看日志: {log_file}")
                else:
                    output = (result.stderr + "\n" + result.stdout).strip()
                    print(f"    ⚠️  编译失败: {output[-1000:]}")
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
        
        return None
    
    def _build_choice_stem(self, problem: Problem) -> str:
        """构建选择题题干"""
        lines = [problem.body_clean, ""]
        for option in problem.choice_options:
            lines.append(f"({option.label}) {option.content}")
        return "\n".join(lines)
    
    def generate_choice_pdfs(self, problem: Problem) -> List[Path]:
        """生成选择题相关 PDF"""
        generated_files = []
        base_name = f"choice_{problem.id}"
        display_name = f"选择题{problem.id}"
        answer = problem.choice_answer or "X"
        
        # 1. 生成题干 PDF
        print(f"  📄 生成题干 PDF...")
        stem_content = self._build_choice_stem(problem)
        stem_tex = self._create_standalone_tex(stem_content)
        stem_pdf = self._compile_tex(stem_tex, f"{base_name}_题干_{answer}")
        
        if stem_pdf:
            final_name = self.output_dir / f"{display_name}题干_{answer}.pdf"
            shutil.move(str(stem_pdf), str(final_name))
            generated_files.append(final_name)
            print(f"     ✅ {final_name.name}")
        
        # 2. 生成每个选项的 PDF
        for option in problem.choice_options:
            print(f"  📄 生成选项 {option.label} PDF...")
            option_content = f"({option.label}) {option.content}"
            option_tex = self._create_standalone_tex(option_content)
            option_pdf = self._compile_tex(option_tex, f"{base_name}_选项_{option.label}")
            
            if option_pdf:
                final_name = self.output_dir / f"{display_name}选项_{option.label}.pdf"
                shutil.move(str(option_pdf), str(final_name))
                generated_files.append(final_name)
                print(f"     ✅ {final_name.name}")
        
        # 3. 生成笔记 PDF（如果有）
        if problem.note:
            print(f"  📄 生成笔记 PDF...")
            note_content = f"注\\quad {problem.note}"
            note_tex = self._create_standalone_tex(note_content)
            note_pdf = self._compile_tex(note_tex, f"{base_name}_笔记")
            
            if note_pdf:
                final_name = self.output_dir / f"{display_name}笔记.pdf"
                shutil.move(str(note_pdf), str(final_name))
                generated_files.append(final_name)
                print(f"     ✅ {final_name.name}")
        
        return generated_files
    
    def generate_fillin_pdfs(self, problem: Problem) -> List[Path]:
        """生成填空题相关 PDF"""
        generated_files = []
        base_name = f"fillin_{problem.id}"
        display_name = f"填空题{problem.id}"
        
        # 1. 生成题干 PDF
        print(f"  📄 生成题干 PDF...")
        stem_tex = self._create_standalone_tex(problem.body_clean)
        stem_pdf = self._compile_tex(stem_tex, f"{base_name}_题干")
        
        if stem_pdf:
            final_name = self.output_dir / f"{display_name}题干.pdf"
            shutil.move(str(stem_pdf), str(final_name))
            generated_files.append(final_name)
            print(f"     ✅ {final_name.name}")
        
        # 2. 生成每个答案的 PDF
        for answer in problem.fillin_answers:
            print(f"  📄 生成答案 {answer.index} PDF...")
            answer_tex = self._create_standalone_tex(answer.content)
            answer_pdf = self._compile_tex(answer_tex, f"{base_name}_答案_{answer.index}")
            
            if answer_pdf:
                final_name = self.output_dir / f"{display_name}答案{answer.index}.pdf"
                shutil.move(str(answer_pdf), str(final_name))
                generated_files.append(final_name)
                print(f"     ✅ {final_name.name}")
        
        # 3. 生成笔记 PDF（如果有）
        if problem.note:
            print(f"  📄 生成笔记 PDF...")
            note_content = f"注\\quad {problem.note}"
            note_tex = self._create_standalone_tex(note_content)
            note_pdf = self._compile_tex(note_tex, f"{base_name}_笔记")
            
            if note_pdf:
                final_name = self.output_dir / f"{display_name}笔记.pdf"
                shutil.move(str(note_pdf), str(final_name))
                generated_files.append(final_name)
                print(f"     ✅ {final_name.name}")
        
        return generated_files
    
    def generate_solution_pdfs(self, problem: Problem) -> List[Path]:
        """生成解答题相关 PDF"""
        generated_files = []
        base_name = f"solution_{problem.id}"
        display_name = f"计算题{problem.id}"
        
        # 1. 生成题干 PDF
        print(f"  📄 生成题干 PDF...")
        stem_tex = self._create_standalone_tex(problem.body)
        stem_pdf = self._compile_tex(stem_tex, f"{base_name}_题干")
        
        if stem_pdf:
            final_name = self.output_dir / f"{display_name}题干.pdf"
            shutil.move(str(stem_pdf), str(final_name))
            generated_files.append(final_name)
            print(f"     ✅ {final_name.name}")
        
        # 2. 生成答案 PDF（如果有）
        if problem.solution:
            print(f"  📄 生成答案 PDF...")
            solution_content = f"解\\quad {problem.solution}"
            solution_tex = self._create_standalone_tex(solution_content)
            solution_pdf = self._compile_tex(solution_tex, f"{base_name}_答案")
            
            if solution_pdf:
                final_name = self.output_dir / f"{display_name}答案.pdf"
                shutil.move(str(solution_pdf), str(final_name))
                generated_files.append(final_name)
                print(f"     ✅ {final_name.name}")
        
        # 3. 生成笔记 PDF（如果有）
        if problem.note:
            print(f"  📄 生成笔记 PDF...")
            note_content = f"注\\quad {problem.note}"
            note_tex = self._create_standalone_tex(note_content)
            note_pdf = self._compile_tex(note_tex, f"{base_name}_笔记")
            
            if note_pdf:
                final_name = self.output_dir / f"{display_name}笔记.pdf"
                shutil.move(str(note_pdf), str(final_name))
                generated_files.append(final_name)
                print(f"     ✅ {final_name.name}")
        
        return generated_files
    
    def generate(self, base_name: str, tex_dir: Optional[Path] = None) -> bool:
        """生成所有题目的 PDF"""
        if not self.check_xelatex():
            return False

        # 确定 tex 文件路径
        if tex_dir is None:
            tex_dir = self.project_root
        else:
            tex_dir = Path(tex_dir)
        
        source_file = tex_dir / f"{base_name}.tex"
        if not source_file.exists():
            source_file = self.project_root / "examples" / f"{base_name}.tex"
        
        if not source_file.exists():
            print(f"❌ 找不到文件: {base_name}.tex")
            return False
        
        print(f"📝 源文件: {source_file}")
        print("-" * 50)
        
        # 解析 tex 文件
        content = source_file.read_text(encoding='utf-8')
        parser = LaTeXParser(content)
        problems = parser.parse()
        
        print(f"✅ 解析完成，共 {len(problems)} 道题目\n")
        
        # 生成 PDF
        all_files = []
        
        for problem in problems:
            print(f"【题目 {problem.id}】{problem.type.value}")
            
            if problem.type == ProblemType.CHOICE:
                files = self.generate_choice_pdfs(problem)
            elif problem.type == ProblemType.FILLIN:
                files = self.generate_fillin_pdfs(problem)
            else:
                files = self.generate_solution_pdfs(problem)
            
            all_files.extend(files)
            print(f"  ✅ 生成 {len(files)} 个 PDF\n")
        
        # 清理临时文件
        for f in self.output_dir.glob("*.tex"):
            f.unlink()
        for f in self.output_dir.glob("*.aux"):
            f.unlink()
        for f in self.output_dir.glob("*.log"):
            f.unlink()
        
        print("=" * 50)
        print(f"✅ 全部完成！共生成 {len(all_files)} 个 PDF 文件")
        print(f"📁 输出目录: {self.output_dir}")
        print("=" * 50)
        
        return True


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="LaTeX 题目 PDF 生成器 - 用于检查正则解析结果",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python pdf_generator.py              # 交互式模式
  python pdf_generator.py -f demo      # 处理 demo.tex
  python pdf_generator.py -f demo -w 1000  # 指定宽度 1000pt
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
        help="PDF 宽度（像素，默认 800）"
    )
    
    args = parser.parse_args()
    
    if args.file:
        generator = PDFGenerator(
            image_width=f"{args.width}pt"
        )
        generator.generate(args.file, args.directory)
    else:
        # 交互式模式
        print("=" * 50)
        print("  LaTeX 题目 PDF 生成工具")
        print("  （用于检查正则解析结果）")
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
        
        width_input = input("请输入 PDF 宽度（像素，默认 800）: ").strip()
        image_width = f"{width_input}pt" if width_input.isdigit() else "800pt"
        
        print()
        generator = PDFGenerator(image_width=image_width)
        generator.generate(base_name)


if __name__ == "__main__":
    main()
