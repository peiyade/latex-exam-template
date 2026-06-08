# LaTeX 试卷图片生成工具 - 逻辑说明

## 一、解析器 (parser.py) 逻辑

### 1. 题目类型判定
```
检测顺序：
1. 如果 body 包含 \pickout{ 或 \pickin{ 且包含 \options → 选择题 (CHOICE)
2. 如果 body 包含 \fillin{ → 填空题 (FILLIN)  
3. 否则 → 解答题 (SOLUTION)
```

### 2. 题目结构提取

#### 选择题提取：
- **答案**: 从 `\pickout{X}` 或 `\pickin{X}` 提取
- **选项**: 从 `\options{A}{B}{C}{D}` 提取4个参数
- **题干清理**: 
  - 移除 `\pickout{X}` 和 `\pickin{X}`
  - 移除 `\options{...}{...}{...}{...}`
  - 保留题干纯文本

#### 填空题提取：
- **答案**: 从 `\fillin{内容}` 提取（支持嵌套大括号）
- **题干清理**: 
  - 将 `\fillin{...}` 替换为 `\underline{\hspace{3em}}`
  - 显示为下划线空白

#### 解答题提取：
- **题干**: `problem` 环境内容
- **答案**: `solution` 环境内容
- **笔记**: `note` 环境内容（紧跟在 problem 后）

### 3. 嵌套大括号处理
使用栈计数法匹配大括号：
```python
def _extract_brace_content(text, start_pos):
    brace_count = 0
    for i, char in enumerate(text[start_pos:], start=start_pos):
        if char == '{': brace_count += 1
        elif char == '}': 
            brace_count -= 1
            if brace_count == 0: return content
```

---

## 二、图片生成器 (image_generator.py) 逻辑

### 1. 文件命名规则

#### 选择题：
| 文件类型 | 命名格式 | 内容说明 |
|---------|---------|---------|
| 题干 | `选择题{编号}题干:{答案}.png` | 题干 + 4个选项（不显示答案） |
| 选项A | `选择题{编号}选项:A.png` | 仅选项A内容 |
| 选项B | `选择题{编号}选项:B.png` | 仅选项B内容 |
| 选项C | `选择题{编号}选项:C.png` | 仅选项C内容 |
| 选项D | `选择题{编号}选项:D.png` | 仅选项D内容 |
| 笔记 | `选择题{编号}笔记.png` | note环境内容 |

#### 填空题：
| 文件类型 | 命名格式 | 内容说明 |
|---------|---------|---------|
| 题干 | `填空题{编号}题干.png` | 题干（fillin→下划线） |
| 答案1 | `填空题{编号}答案1.png` | 第1个空的答案 |
| 答案n | `填空题{编号}答案n.png` | 第n个空的答案 |
| 笔记 | `填空题{编号}笔记.png` | note环境内容 |

#### 计算题（解答题）：
| 文件类型 | 命名格式 | 内容说明 |
|---------|---------|---------|
| 题干 | `计算题{编号}题干.png` | problem环境内容 |
| 答案 | `计算题{编号}答案.png` | solution环境内容 |
| 笔记 | `计算题{编号}笔记.png` | note环境内容 |

### 2. 图片生成流程

```
对于每个题目:
    1. 根据类型调用对应生成函数
    2. 构建 LaTeX 内容
    3. 包裹 standalone 模板
    4. 写入 .tex 文件（ASCII文件名，避免命令行工具处理中文路径时出错）
    5. 本地编译: xelatex → PDF
    6. PDF 转 PNG: pdftoppm -png -r 300
    7. 移动到输出目录（中文文件名）
```

### 3. Standalone 模板结构
```latex
\documentclass[border=10pt]{standalone}
\usepackage[fontset=fandol]{ctex}  % 中文支持
\usepackage{amsmath,amssymb,unicode-math}
\usepackage{tikz,enumitem}
\geometry{paperwidth={width}pt,paperheight=100cm,margin=1cm}

\begin{document}
\begin{minipage}{{width}pt}
% 题目内容
\end{minipage}
\end{document}
```

### 4. 关键技术点

#### 本地编译：
- 直接调用 PATH 中的 `xelatex`
- 编译失败时保留 `.log` 便于定位 LaTeX 错误

#### 文件名处理：
- 临时文件：使用 ASCII 名（如 `choice_1_stem.tex`）
- 输出文件：使用中文名（如 `选择题1题干:C.png`）
- 避免 pdftoppm 中文字符问题

#### 图片尺寸：
- 宽度：用户指定（默认 800pt）
- DPI：300
- 高度：自适应（paperheight=100cm足够大）

---

## 三、潜在问题

### 问题1：选择题3没有 note 但生成了笔记图片
检查 `generate_note_image` 逻辑：当 note 为 None 时应该跳过。

### 问题2：计算题答案图片过大
solution 内容可能包含大量数学公式，导致 PDF 较大。

### 问题3：图片高度自适应
standalone 的 paperheight=100cm 是固定的，可能导致图片有大量空白。

---

## 四、待检查项

1. **选择题题干**: 是否正确显示题干 + 4个选项，无答案标记？
2. **填空题题干**: fillin 是否正确显示为下划线？
3. **笔记图片**: 无 note 的题目是否还生成笔记图片？
4. **计算题答案**: solution 内容是否完整？
