#!/usr/bin/env python3
"""
LaTeX 试卷解析器
解析 problem、solution、note 环境，识别题目类型
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class ProblemType(Enum):
    """题目类型"""
    CHOICE = "choice"      # 选择题（有 pickout/options）
    FILLIN = "fillin"      # 填空题（有 fillin 命令）
    SOLUTION = "solution"  # 解答题（有 solution 环境）
    UNKNOWN = "unknown"    # 未知类型


@dataclass
class ChoiceOption:
    """选择题选项"""
    label: str      # A, B, C, D
    content: str    # 选项内容


@dataclass
class FillinAnswer:
    """填空题答案"""
    index: int      # 空格的序号
    content: str    # 答案内容


@dataclass
class Problem:
    """题目数据结构"""
    id: int                         # 题号
    type: ProblemType               # 题目类型
    body: str                       # problem 环境内容（原始）
    body_clean: str = ""            # 清理后的题干（无答案标记）
    
    # 选择题特有
    choice_answer: Optional[str] = None     # 选择题答案 A/B/C/D
    choice_options: List[ChoiceOption] = field(default_factory=list)
    
    # 填空题特有
    fillin_answers: List[FillinAnswer] = field(default_factory=list)
    
    # 解答题/所有题共有
    note: Optional[str] = None      # note 环境内容
    solution: Optional[str] = None  # solution 环境内容


class LaTeXParser:
    """LaTeX 试卷解析器"""
    
    def __init__(self, tex_content: str):
        self.content = tex_content
        self.problems: List[Problem] = []
        
    def parse(self) -> List[Problem]:
        """解析整个文档，返回所有题目"""
        self.problems = []
        
        # 提取导言区（用于 standalone 编译）
        self.preamble = self._extract_preamble()
        
        # 提取所有 problem 环境
        problem_blocks = self._extract_problems()
        
        for idx, (body, end_pos) in enumerate(problem_blocks, 1):
            problem = self._parse_single_problem(idx, body, end_pos)
            self.problems.append(problem)
        
        return self.problems
    
    def _extract_preamble(self) -> str:
        """提取导言区（从文档开头到 \begin{document}）"""
        match = re.search(r'(.*?)\\begin\{document\}', self.content, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""
    
    def _extract_problems(self) -> List[Tuple[str, int]]:
        """
        提取所有 problem 环境
        返回: [(problem_body, end_position), ...]
        """
        problems = []
        pattern = r'\\begin\{problem\}(.*?)\\end\{problem\}'
        
        for match in re.finditer(pattern, self.content, re.DOTALL):
            body = match.group(1).strip()
            end_pos = match.end()
            problems.append((body, end_pos))
        
        return problems
    
    def _parse_single_problem(self, idx: int, body: str, end_pos: int) -> Problem:
        """解析单个题目"""
        problem = Problem(id=idx, body=body, type=ProblemType.UNKNOWN)
        
        # 1. 检测题目类型
        problem.type = self._detect_type(body)
        
        # 2. 根据类型解析
        if problem.type == ProblemType.CHOICE:
            self._parse_choice_problem(problem)
        elif problem.type == ProblemType.FILLIN:
            self._parse_fillin_problem(problem)
        else:
            problem.body_clean = body
        
        # 3. 提取 note 环境（紧跟在 problem 之后）
        problem.note = self._extract_note(end_pos)
        
        # 4. 提取 solution 环境（紧跟在 problem/note 之后）
        problem.solution = self._extract_solution(end_pos)
        
        return problem
    
    def _detect_type(self, body: str) -> ProblemType:
        """检测题目类型"""
        # 检查是否有 pickout 或 pickin 命令
        if r'\pickout{' in body or r'\pickin{' in body:
            # 进一步检查是否有 options 命令（options 可能不带花括号）
            if r'\options' in body:
                return ProblemType.CHOICE
        
        # 检查是否有 fillin 命令
        if r'\fillin{' in body:
            return ProblemType.FILLIN
        
        # 默认是解答题
        return ProblemType.SOLUTION
    
    def _parse_choice_problem(self, problem: Problem):
        """解析选择题 - 处理嵌套大括号"""
        body = problem.body
        
        # 提取答案（pickout 或 pickin）
        pickout_matches = self._extract_nested_command(body, 'pickout')
        pickin_matches = self._extract_nested_command(body, 'pickin')
        
        if pickout_matches:
            problem.choice_answer = pickout_matches[0][2].strip()
        elif pickin_matches:
            problem.choice_answer = pickin_matches[0][2].strip()
        
        # 提取选项 - \options{optA}{optB}{optC}{optD}
        # 找到 \options 命令并提取4个参数
        options_match = re.search(r'\\options', body)
        if options_match:
            # 从 \options 后面开始解析4个参数
            pos = options_match.end()
            # 跳过空白
            while pos < len(body) and body[pos] in ' \t\n':
                pos += 1
            
            labels = ['A', 'B', 'C', 'D']
            for label in labels:
                if pos < len(body) and body[pos] == '{':
                    content, end_pos = self._extract_brace_content(body, pos)
                    problem.choice_options.append(ChoiceOption(label, content.strip()))
                    pos = end_pos
                    # 跳过空白
                    while pos < len(body) and body[pos] in ' \t\n':
                        pos += 1
        
        # 生成清理后的题干（移除 pickout/pickin 和 options）
        # 收集所有需要移除的区间，然后合并处理
        remove_intervals = []
        
        # pickout/pickin 区间
        for start, end, _ in pickout_matches + pickin_matches:
            remove_intervals.append((start, end))
        
        # options 区间
        if options_match:
            # 找到 \options 后4个参数的范围
            pos = options_match.end()
            end_pos = pos
            while end_pos < len(body) and body[end_pos] in ' \t\n':
                end_pos += 1
            
            for _ in range(4):  # 4个选项参数
                if end_pos < len(body) and body[end_pos] == '{':
                    _, end_pos = self._extract_brace_content(body, end_pos)
                    while end_pos < len(body) and body[end_pos] in ' \t\n':
                        end_pos += 1
            
            remove_intervals.append((options_match.start(), end_pos))
        
        # 合并重叠区间并移除
        remove_intervals.sort()
        body_clean = ""
        last_end = 0
        for start, end in remove_intervals:
            body_clean += body[last_end:start]
            last_end = end
        body_clean += body[last_end:]
        
        problem.body_clean = body_clean.strip()
    
    def _parse_fillin_problem(self, problem: Problem):
        """解析填空题 - 处理嵌套大括号"""
        body = problem.body
        
        # 提取所有 fillin 命令（处理嵌套大括号）
        fillin_matches = self._extract_nested_command(body, 'fillin')
        
        for idx, (start, end, content) in enumerate(fillin_matches, 1):
            answer_content = content.strip()
            problem.fillin_answers.append(FillinAnswer(idx, answer_content))
        
        # 生成清理后的题干（将 fillin 替换为下划线）
        # 从后往前替换，避免位置偏移
        body_clean = body
        for idx, (start, end, _) in enumerate(reversed(fillin_matches)):
            body_clean = body_clean[:start] + r'\underline{\hspace{3em}}' + body_clean[end:]
        
        problem.body_clean = body_clean.strip()
    
    def _extract_nested_command(self, text: str, cmd_name: str) -> list:
        """
        提取带有嵌套大括号的 LaTeX 命令
        返回: [(start_pos, end_pos, content), ...]
        """
        pattern = rf'\\{cmd_name}' + r'\{'
        matches = []
        
        for match in re.finditer(pattern, text):
            start = match.start()
            brace_start = match.end() - 1  # 指向 '{'
            
            # 从 '{' 开始找匹配的 '}'
            brace_count = 0
            content_start = brace_start + 1
            
            for i, char in enumerate(text[brace_start:], start=brace_start):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        content = text[content_start:i]
                        matches.append((start, i + 1, content))
                        break
        
        return matches
    
    def _extract_brace_content(self, text: str, start_pos: int) -> tuple:
        """
        从 start_pos（指向 '{'）提取匹配的大括号内容
        返回: (content, end_pos) 其中 end_pos 是 '}' 后的位置
        """
        if start_pos >= len(text) or text[start_pos] != '{':
            return ("", start_pos)
        
        brace_count = 0
        content_start = start_pos + 1
        
        for i, char in enumerate(text[start_pos:], start=start_pos):
            if char == '{':
                brace_count += 1
            elif char == '}':
                brace_count -= 1
                if brace_count == 0:
                    content = text[content_start:i]
                    return (content, i + 1)
        
        return ("", start_pos)
    
    def _extract_note(self, after_pos: int) -> Optional[str]:
        """提取 note 环境（紧跟在指定位置之后）"""
        # 从 after_pos 开始查找
        remaining = self.content[after_pos:]
        
        # 跳过空白字符和简单的命令（如 \bigskip, \vspace 等）
        remaining = self._skip_whitespace_and_commands(remaining)
        
        # 检查是否以 \begin{note} 开头
        note_match = re.match(
            r'\\begin\{note\}(.*?)\\end\{note\}',
            remaining,
            re.DOTALL
        )
        
        if note_match:
            return note_match.group(1).strip()
        
        return None
    
    def _extract_solution(self, after_pos: int) -> Optional[str]:
        """提取 solution 环境（在 note 之后）"""
        remaining = self.content[after_pos:]
        
        # 跳过空白字符和简单的命令
        remaining = self._skip_whitespace_and_commands(remaining)
        
        # 如果有 note 环境，从 note 之后开始
        note_match = re.match(
            r'\\begin\{note\}.*?\\end\{note\}',
            remaining,
            re.DOTALL
        )
        if note_match:
            remaining = remaining[note_match.end():]
            remaining = self._skip_whitespace_and_commands(remaining)
        
        # 检查是否以 \begin{solution} 开头
        solution_match = re.match(
            r'\\begin\{solution\}(.*?)\\end\{solution\}',
            remaining,
            re.DOTALL
        )
        
        if solution_match:
            return solution_match.group(1).strip()
        
        return None
    
    def get_preamble_for_standalone(self, image_width: str = "800pt") -> str:
        """
        生成适用于 standalone 文档类的导言区
        """
        # 提取关键包和设置
        lines = self.preamble.split('\n')
        
        new_preamble = [
            r'\documentclass[border=10pt]{standalone}',
            r'\usepackage[utf8]{inputenc}',
            r'\usepackage{amsmath,amssymb}',
            r'\usepackage{unicode-math}',
            r'\usepackage{xeCJK}',
            r'\usepackage{geometry}',
            r'\usepackage{xcolor}',
            r'\usepackage{ulem}',
            r'\usepackage{pifont}',
            r'\usepackage{tikz}',
            r'\usepackage{enumitem}',
            r'\usetikzlibrary{positioning, calc, shapes.geometric, arrows.meta}',
            '',
            r'% 中文字体支持',
            r'\setCJKmainfont{SimSun}',
            r'\setCJKsansfont{SimHei}',
            '',
            r'% 数学符号',
            r'\DeclareMathOperator{\dif}{\mathop{}\!\mathrm{d}}',
            r'\DeclareMathOperator{\upe}{\operatorname{e}}',
            r'\renewcommand{\le}{\leqslant}',
            r'\renewcommand{\leq}{\leqslant}',
            r'\renewcommand{\ge}{\geqslant}',
            r'\renewcommand{\geq}{\geqslant}',
            '',
            r'% 页面设置',
            rf'\geometry{{paperwidth={image_width},paperheight=100cm,margin=1cm}}',
            '',
            r'\begin{document}',
            r'\begin{minipage}{' + image_width + '}',
        ]
        
        return '\n'.join(new_preamble)
    
    def _skip_whitespace_and_commands(self, text: str) -> str:
        """
        跳过空白字符和简单的 LaTeX 命令（如 \bigskip, \vspace{} 等）
        注意：不跳过 \begin 和 \end 命令
        """
        text = text.lstrip()
        
        # 匹配简单命令的模式，但排除 \begin 和 \end
        while True:
            # 匹配无参数的命令（如 \bigskip, \smallskip）
            match = re.match(r'\\(?!begin|end)[a-zA-Z]+\*?(?![a-zA-Z])', text)
            if match:
                text = text[match.end():].lstrip()
                continue
            
            # 匹配带花括号参数的命令（如 \vspace{1em}）
            match = re.match(r'\\(?!begin|end)[a-zA-Z]+\*?\{', text)
            if match:
                # 提取大括号内容
                brace_start = match.end() - 1
                brace_count = 0
                for i, char in enumerate(text[brace_start:], start=brace_start):
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                        if brace_count == 0:
                            text = text[i+1:].lstrip()
                            break
                continue
            
            break
        
        return text
    
    @staticmethod
    def get_standalone_footer() -> str:
        """获取 standalone 文档的结尾"""
        return r'\end{minipage}' + '\n' + r'\end{document}'


if __name__ == "__main__":
    # 测试解析器
    sample = r'''
    \begin{problem}
    设函数 $f(x)$ 可导，则下列极限中等于 $f'(x_0)$ 的是\pickout{C}
    \options
    {$\lim_{h\to 0}\frac{f(x_0+2h)-f(x_0)}{h}$}
    {$\lim_{h\to 0}\frac{f(x_0+h)-f(x_0-h)}{h}$}
    {$\lim_{h\to 0}\frac{f(x_0+h)-f(x_0)}{h}$}
    {$\lim_{h\to 0}\frac{f(x_0)-f(x_0-h)}{2h}$}
    \end{problem}
    \begin{note}
    根据导数的定义...
    \end{note}
    '''
    
    parser = LaTeXParser(sample)
    problems = parser.parse()
    
    for p in problems:
        print(f"题目 {p.id}: {p.type.value}")
        print(f"  答案: {p.choice_answer}")
        print(f"  选项: {[(o.label, o.content[:30]) for o in p.choice_options]}")
        print(f"  笔记: {p.note[:50] if p.note else None}")
