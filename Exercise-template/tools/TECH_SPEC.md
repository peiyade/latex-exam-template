# LaTeX 试卷自动化工具 - 技术规格书

## 技术选型确认

| 组件 | 选型 | 理由 |
|-----|------|-----|
| 图片生成 | **LaTeX standalone** | 公式渲染完美，符合学术场景需求 |
| 解析器 | **正则表达式** | 模板结构规范，正则足够且轻量 |
| LaTeX 编译 | **本地 xelatex** | 依赖简单，直接使用 PATH 中的本地 TeX Live / MacTeX |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                     用户输入层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │  compiler   │  │   image_gen │  │   interactive CLI   │ │
│  │   编译脚本   │  │   图片生成  │  │    交互式命令行      │ │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘ │
└─────────┼────────────────┼────────────────────┼────────────┘
          │                │                    │
          ▼                ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│                     核心处理层                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│  │   parser    │  │  generator  │  │      xelatex        │ │
│  │  LaTeX解析器 │  │  PNG生成器  │  │    本地编译器        │ │
│  └─────────────┘  └─────────────┘  └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                     输出层                                   │
│     output/pdf/              output/images/                  │
│  ├─ 练习(带答案).pdf      ├─ 选择题1题干:A.png              │
│  └─ 练习(无答案).pdf      ├─ 选择题1选项:A.png              │
│                             ├─ 填空题1题干.png               │
│                             ├─ 填空题1答案1.png              │
│                             ├─ 计算题1题干.png               │
│                             ├─ 计算题1答案.png               │
│                             └─ 计算题1笔记.png               │
└─────────────────────────────────────────────────────────────┘
```

---

## 阶段一：自动编译脚本 (compiler.py)

### 功能
- 交互式输入文件名
- 自动生成带答案/无答案两个版本
- 使用本地 `xelatex` 编译

### 输入
```bash
python compiler.py
# 或
python compiler.py demo
```

### 输出
```
output/pdf/
├── demo(带答案).pdf
└── demo(无答案).pdf
```

### 核心算法
```python
1. 读取 source.tex
2. 修改 \documentclass[answer]{THUExam}
3. 写入 temp_answer.tex → 编译 → demo(带答案).pdf
4. 修改 \documentclass[noanswer]{THUExam}  
5. 写入 temp_noanswer.tex → 编译 → demo(无答案).pdf
6. 清理临时文件
```

---

## 阶段二：图片生成器 (image_generator.py)

### 功能
- 解析 tex 文件，识别题目类型
- 为每个题目组件生成独立图片
- 支持自定义图片宽度
- 300 DPI 输出

### 输入
```bash
python image_generator.py
# 交互式输入: demo
# 交互式输入: 宽度(默认800px)
```

### 输出规范

#### 选择题 (Choice)
```
选择题{编号}题干:{答案}.png      # 题干（含选项列表，不显示答案）
选择题{编号}选项:A.png           # 选项 A
选择题{编号}选项:B.png           # 选项 B
选择题{编号}选项:C.png           # 选项 C
选择题{编号}选项:D.png           # 选项 D
选择题{编号}笔记.png             # note 环境（如有）
```

#### 填空题 (Fill-in)
```
填空题{编号}题干.png             # 题干（fillin 显示为下划线）
填空题{编号}答案1.png            # 第1个空的答案
填空题{编号}答案2.png            # 第2个空的答案（如有）
填空题{编号}笔记.png             # note 环境（如有）
```

#### 解答题 (Solution)
```
计算题{编号}题干.png             # problem 环境内容
计算题{编号}答案.png             # solution 环境内容
计算题{编号}笔记.png             # note 环境内容（如有）
```

### 核心算法
```python
1. 解析 tex 文件
   for each problem:
     - 检测类型 (choice/fillin/solution)
     - 提取 body/note/solution

2. 选择题处理:
   - 提取 \pickout{X} 作为答案
   - 提取 \options{A}{B}{C}{D}
   - 生成题干.tex（移除 pickout/options）
   - 为每个选项生成独立 .tex

3. 填空题处理:
   - 提取所有 \fillin{答案}
   - 生成题干.tex（fillin → 下划线）
   - 为每个答案生成独立 .tex

4. 解答题处理:
   - 直接生成题干.tex
   - 生成答案.tex（solution 内容）
   - 生成笔记.tex（如有）

5. 编译所有 .tex → PDF → PNG (300 DPI)
```

### standalone 模板
```latex
\documentclass[border=10pt]{standalone}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb,unicode-math}
\usepackage{xeCJK}
\usepackage{xcolor,ulem}
\usepackage{tikz}
\usepackage{enumitem}

% 字体设置
\setCJKmainfont{SimSun}

% 数学宏
\DeclareMathOperator{\dif}{\mathop{}\!\mathrm{d}}
\renewcommand{\le}{\leqslant}
\renewcommand{\ge}{\geqslant}

% 页面尺寸 (用户自定义宽度)
\geometry{paperwidth=800pt,paperheight=100cm,margin=1cm}

\begin{document}
\begin{minipage}{800pt}
% 题目内容
\end{minipage}
\end{document}
```

---

## 数据结构设计

```python
class ProblemType(Enum):
    CHOICE = "choice"
    FILLIN = "fillin"
    SOLUTION = "solution"

@dataclass
class Problem:
    id: int
    type: ProblemType
    body: str                    # 原始内容
    body_clean: str              # 清理后的题干
    
    # 选择题
    choice_answer: Optional[str] = None
    choice_options: List[ChoiceOption] = field(default_factory=list)
    
    # 填空题  
    fillin_answers: List[FillinAnswer] = field(default_factory=list)
    
    # 所有题
    note: Optional[str] = None
    solution: Optional[str] = None
```

---

## 依赖清单

### Python 包
```
click>=8.0          # CLI 框架
pdf2image>=1.16     # PDF 转图片 (poppler 后端)
Pillow>=9.0         # 图像处理
```

### 系统依赖
```
python3             # 运行工具脚本
xelatex             # LaTeX 编译器（TeX Live / MacTeX）
poppler             # pdftoppm 命令 (PDF 转 PNG)
                    # macOS: brew install poppler
                    # Ubuntu: apt-get install poppler-utils
```

---

## 执行流程

```
用户输入
   │
   ▼
┌──────────────┐
│ 检查 xelatex │◄──── 需要本地 PATH 可访问
│ 本地命令      │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 解析 LaTeX   │◄──── 提取所有 problem
│ 识别题目类型  │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 生成 standalone│◄──── 每个题目组件一个 .tex
│ 临时 tex 文件 │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ xelatex 编译 │◄──── 本地执行
│ 生成 PDF     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ pdftoppm 转换│◄──── PDF → PNG (300 DPI)
│ 生成 PNG     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 按规范重命名 │◄──── 选择题1题干:A.png
│ 移动到输出目录│
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ 生成报告     │◄──── 题目数量统计等
│ 清理临时文件  │
└──────────────┘
```

---

## 风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|-----|------|-----|---------|
| xelatex 未安装或不在 PATH | 中 | 高 | 脚本检查依赖，提示安装 TeX Live / MacTeX |
| LaTeX 编译错误 | 低 | 中 | 捕获错误日志，显示给用户 |
| 中文显示异常 | 低 | 高 | standalone 模板中强制指定中文字体 |
| poppler 未安装 | 中 | 高 | 脚本检查依赖，提供安装指引 |
| 题目解析错误 | 低 | 中 | 提供调试模式，输出解析中间结果 |

---

## 图片生成最佳实践（常用配置速查）

> **日常最常用：学习通/手机端配置。详见 `tools/generate_xt.py` 一键脚本。**

### 平台适配参数

| 使用场景 | 宽度参数 | DPI | 实际像素 | 特点 |
|---------|---------|-----|---------|-----|
| **学习通 / 手机端** ⭐ | `-w 288pt` | `150` | **~600 px** | 字体清晰、文件极小、适合手机 |
| 通用网页展示 | `-w 600pt` | `150` | ~1250 px | 适中，兼顾手机和电脑 |
| 高清打印 | `-w 1000pt` | `300` | ~4167 px | 印刷级别，文件较大 |

### 快速使用

```bash
# 学习通专用（推荐）
python3 tools/generate_xt.py 2025-2026-Exercise-3

# 通用流程（自定义参数）
python3 tools/generate_all.py -f 2025-2026-Exercise-3 -w 600 --dpi 150
```

### 生成文件结构

```
output/2025-2026-Exercise-3/
├── pdfs/
│   ├── 2025-2026-Exercise-3(带答案).pdf
│   ├── 2025-2026-Exercise-3(无答案).pdf
│   └── ...（逐题拆分 PDF）
└── images/
    ├── 选择题1题干_A.png        # 题干（含选项，~600px 宽）
    ├── 选择题1选项_A.png        # 单独选项
    ├── 选择题1笔记.png          # 解析/备注
    ├── 填空题12题干.png
    ├── 填空题12答案1.png
    └── ...
```

---

## 下一步行动

确认技术方案后，将依次实现：

1. ✅ `compiler.py` - 自动编译脚本（30分钟）
2. ✅ `parser.py` - LaTeX 解析器（已完成）
3. ✅ `image_generator.py` - 图片生成器核心（1-2小时）
4. ✅ `utils.py` - 通用工具函数（30分钟）
5. ✅ `generate_xt.py` - 学习通优化脚本（已完成）
6. 🔄 整合测试与示例验证（30分钟）

**预计总用时：3-4 小时**
