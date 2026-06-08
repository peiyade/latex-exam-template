#!/usr/bin/env python3
"""
LaTeX 试卷自动编译脚本
生成带答案和无答案两个版本的 PDF
"""

import argparse
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional


class LaTeXCompiler:
    """LaTeX 试卷编译器"""
    
    def __init__(self, output_dir: Optional[Path] = None):
        self.project_root = Path(__file__).parent.parent
        if output_dir is not None:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = self.project_root / "output" / "pdf"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def check_xelatex(self) -> bool:
        """检查本地 xelatex 是否可用"""
        if shutil.which("xelatex"):
            return True
        print("❌ 未检测到本地 xelatex，请先安装 TeX Live / MacTeX，并确保 xelatex 在 PATH 中")
        return False
    
    def read_tex_file(self, filepath: Path) -> str:
        """读取 tex 文件内容"""
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read()
    
    def modify_document_class(self, content: str, answer: bool) -> str:
        r"""
        修改文档类选项
        - answer=True: \documentclass[answer]{THUExam}
        - answer=False: \documentclass[noanswer]{THUExam}
        """
        # 匹配 \documentclass[...]{THUExam} 或 \documentclass{THUExam}
        pattern = r'\\documentclass\[(.*?)\]\{THUExam\}|\\documentclass\{THUExam\}'
        
        def replacer(match):
            if match.group(1) is not None:
                # 有选项的情况
                existing_options = match.group(1)
                # 移除 answer/noanswer 选项
                options = re.sub(r'\banswer\b|\bnoanswer\b', '', existing_options)
                options = re.sub(r',\s*,', ',', options)  # 移除多余逗号
                options = options.strip(', ')
                
                new_option = "answer" if answer else "noanswer"
                if options:
                    return f"\\documentclass[{new_option},{options}]{{THUExam}}"
                else:
                    return f"\\documentclass[{new_option}]{{THUExam}}"
            else:
                # 无选项的情况
                new_option = "answer" if answer else "noanswer"
                return f"\\documentclass[{new_option}]{{THUExam}}"
        
        return re.sub(pattern, replacer, content, count=1)
    
    def compile_tex(self, tex_file: Path, output_name: str, work_dir: Optional[Path] = None) -> bool:
        """
        使用 xelatex 编译 tex 文件
        需要编译两次以解析交叉引用
        
        Args:
            tex_file: tex 文件路径
            output_name: 输出文件名（不含扩展名）
            work_dir: 编译工作目录，默认使用项目根目录
        """
        if work_dir is None:
            work_dir = self.project_root
        tex_name = tex_file.name
        
        print(f"📄 编译: {tex_name}")
        
        for i in range(1, 3):  # 编译两次
            print(f"  第 {i} 次编译...", end=" ")
            try:
                result = subprocess.run(
                    ["xelatex",
                     "-interaction=nonstopmode",  # 非交互模式
                     "-halt-on-error",             # 出错即停止
                     tex_name],
                    capture_output=True,
                    text=True,
                    cwd=work_dir,
                    timeout=120  # 2 分钟超时
                )
                
                if result.returncode != 0:
                    print(f"❌ 失败")
                    print("错误输出:")
                    output = (result.stderr + "\n" + result.stdout).strip()
                    print(output[-2000:] if len(output) > 2000 else output)
                    return False
                
                print("✅")
                
            except subprocess.TimeoutExpired:
                print(f"❌ 超时")
                return False
            except FileNotFoundError:
                print("❌ 未找到 xelatex")
                return False
            except Exception as e:
                print(f"❌ 错误: {e}")
                return False
        
        # 移动生成的 PDF 到输出目录
        pdf_file = tex_file.with_suffix('.pdf')
        if pdf_file.exists():
            output_path = self.output_dir / f"{output_name}.pdf"
            shutil.move(str(pdf_file), str(output_path))
            print(f"📦 已生成: {output_path}")
            return True
        else:
            print(f"❌ 未找到生成的 PDF 文件")
            return False
    
    def compile(self, base_name: str, tex_dir: Optional[Path] = None) -> bool:
        """
        编译主入口
        
        Args:
            base_name: 主文件名（不含 .tex 后缀）
            tex_dir: tex 文件所在目录，默认为项目根目录
        
        Returns:
            bool: 是否全部编译成功
        """
        if not self.check_xelatex():
            return False
        
        # 确定 tex 文件路径
        if tex_dir is None:
            tex_dir = self.project_root
        else:
            tex_dir = Path(tex_dir)
        
        source_file = tex_dir / f"{base_name}.tex"
        
        if not source_file.exists():
            print(f"❌ 找不到文件: {source_file}")
            return False
        
        print(f"📝 源文件: {source_file}")
        print("-" * 50)
        
        # 读取源文件
        content = self.read_tex_file(source_file)
        
        # 在项目根目录创建临时编译文件（确保能找到 .cls 文件）
        results = []
        
        # 1. 生成带答案版本
        print("\n🔓 生成带答案版本...")
        answer_content = self.modify_document_class(content, answer=True)
        answer_tex = self.project_root / f"{base_name}_answer.tex"
        with open(answer_tex, 'w', encoding='utf-8') as f:
            f.write(answer_content)
        
        success = self.compile_tex(answer_tex, f"{base_name}(带答案)", self.project_root)
        results.append(success)
        answer_tex.unlink()  # 删除临时文件
        
        # 2. 生成无答案版本
        print("\n🔒 生成无答案版本...")
        noanswer_content = self.modify_document_class(content, answer=False)
        noanswer_tex = self.project_root / f"{base_name}_noanswer.tex"
        with open(noanswer_tex, 'w', encoding='utf-8') as f:
            f.write(noanswer_content)
        
        success = self.compile_tex(noanswer_tex, f"{base_name}(无答案)", self.project_root)
        results.append(success)
        noanswer_tex.unlink()  # 删除临时文件
        
        # 清理中间文件（在项目根目录）
        self._cleanup(self.project_root, base_name)
        
        print("\n" + "=" * 50)
        if all(results):
            print("✅ 全部编译成功！")
            print(f"📁 输出目录: {self.output_dir}")
            return True
        else:
            print("⚠️ 部分编译失败")
            return False
    
    def _cleanup(self, tex_dir: Path, base_name: str):
        """清理编译产生的中间文件"""
        extensions = ['.aux', '.log', '.out', '.synctex.gz', '.bak*']
        for ext in extensions:
            for f in tex_dir.glob(f"{base_name}*{ext}"):
                try:
                    f.unlink()
                except:
                    pass


def interactive_compile():
    """交互式编译"""
    print("=" * 50)
    print("  LaTeX 试卷自动编译工具")
    print("=" * 50)
    
    compiler = LaTeXCompiler()
    
    # 显示可用的 tex 文件
    project_root = compiler.project_root
    tex_files = list(project_root.glob("*.tex"))
    
    if tex_files:
        print("\n📂 检测到以下 tex 文件:")
        for i, f in enumerate(tex_files, 1):
            print(f"   {i}. {f.name}")
    
    # 交互式输入
    print()
    base_name = input("请输入主文件名（不含 .tex 后缀）: ").strip()
    
    if not base_name:
        print("❌ 文件名不能为空")
        return
    
    print()
    compiler.compile(base_name)


def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="LaTeX 试卷自动编译工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python compiler.py                    # 交互式模式
  python compiler.py main               # 编译 main.tex
  python compiler.py homework1          # 编译 homework1.tex
        """
    )
    
    parser.add_argument(
        "filename",
        nargs="?",
        help="主文件名（不含 .tex 后缀）"
    )
    
    parser.add_argument(
        "-d", "--directory",
        help="tex 文件所在目录（默认为项目根目录）"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="输出目录"
    )
    
    args = parser.parse_args()
    
    if args.filename:
        output_dir = Path(args.output) if args.output else None
        compiler = LaTeXCompiler(output_dir=output_dir)
        compiler.compile(args.filename, args.directory)
    else:
        interactive_compile()


if __name__ == "__main__":
    main()
