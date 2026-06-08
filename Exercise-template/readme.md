## 清华大学试卷 LaTeX 模板

改编自 [北京科技大学试卷 LaTeX 模板](https://github.com/htharoldht/USTBExam), 完全支持overleaf，并做了一些功能上的改进。不过也有一些功能没有很好的支持（比如AB卷打乱试题），欢迎PR！

#### 注意事项

- Overleaf 上请选择 `xeLaTeX` 为编译器
- `\documentclass[answer]{THUExam}`和`\documentclass[]{THUExam}` 决定是否渲染答案

#### 效果展示

![Exam](exam.jpg)

![Exam](ans.jpg)

## 自动化工具

本项目附带一套 Python 工具链，可将 `.tex` 试卷**自动拆分为逐题图片**（题干、答案、笔记分别输出），便于上传至在线教学平台。

### 学习通 / 手机端专用配置 ⭐（常用）

这是**最常用**的生成配置，针对学生手机屏幕优化：

| 参数 | 值 | 说明 |
|------|-----|------|
| 宽度 | `288pt` | 约 **600px**，手机屏幕黄金宽度 |
| DPI | `150` | 字体清晰，文件体积极小 |
| 输出 | 逐题拆分 | 每道题单独成图，方便手机滑动做题 |

**一键生成命令：**

```bash
python3 tools/generate_xt.py 2025-2026-Exercise-3
```

- 源文件默认在 `examples/` 目录
- 输出到 `output/2025-2026-Exercise-3/images/`
- 每张图片通常 **< 10KB**，学生加载无感
- 依赖本地命令：`python3`、`xelatex`、`pdftoppm`

### 自定义参数生成

如需其他宽度，可使用通用脚本：

```bash
# 通用网页展示（~1250px，兼顾手机电脑）
python3 tools/generate_all.py -f 2025-2026-Exercise-3 -w 600 --dpi 150

# 高清打印（~4167px）
python3 tools/generate_all.py -f 2025-2026-Exercise-3 -w 1000 --dpi 300
```

### 输出文件示例

```
output/2025-2026-Exercise-3/
├── pdfs/
│   ├── 2025-2026-Exercise-3(带答案).pdf
│   └── 2025-2026-Exercise-3(无答案).pdf
└── images/
    ├── 选择题1题干_A.png       # 题干（含选项）
    ├── 选择题1选项_A.png       # 选项 A（单独）
    ├── 填空题2题干.png         # 题干（填空处显示下划线）
    ├── 填空题2答案1.png        # 第1个空的答案
    ├── 计算题3题干.png         # 解答题题干
    ├── 计算题3答案.png         # 解答题答案
    └── ...
```

## TODO

- [ ] **考虑使用 pylatexenc 替代正则解析**
  - 当前 `tools/parser.py` 使用正则表达式解析 LaTeX，在嵌套结构和边界情况处理上存在局限
  - 建议调研 `pylatexenc.latexwalker` 作为备选方案，提供更准确的语法树解析
  - 迁移时机：当解析逻辑过于复杂或出现无法解决的边界情况时
