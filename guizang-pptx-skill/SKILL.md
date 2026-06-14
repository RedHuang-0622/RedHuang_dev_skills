---
name: guizang-pptx-skill
description: 生成原生 .pptx PowerPoint 演示文稿，融合歸藏设计系统（电子杂志风 + 瑞士国际主义风）的排版方法论。支持 12 种核心布局、9 套主题色，输出可编辑的 PPTX 文件。当用户需要制作 PPT、演示文稿、PowerPoint、slides 或提到"做PPT"、"生成PPT"、"杂志风PPT"、"瑞士风PPT"时使用。
---

# Guizang PPTX Skill

> 基于 guizang-ppt-skill 设计系统，扩展原生 PPTX 输出能力。
> 设计系统来源: 歸藏 (@op7418)，PPTX 引擎: python-pptx

## 这个 Skill 做什么

一句话：**用歸藏的设计方法论生成可编辑的原生 .pptx 文件**。

不只是"AI 生成 PPT"，而是把 guizang-ppt-skill 的 12 种核心布局 + 9 套精调主题色，通过 python-pptx 引擎直接输出为 PowerPoint 能打开、能编辑的 `.pptx` 文件。

### 与 guizang-ppt-skill 的关系

| | guizang-ppt-skill（原版） | guizang-pptx-skill（本 Skill） |
|---|---|---|
| **输出格式** | HTML 网页 | `.pptx` PowerPoint 文件 |
| **可编辑性** | 改源码 | Office/WPS 直接编辑 |
| **协作** | 静态文件 | 可多人协作 |
| **设计系统** | 32 种版式（10+22） | 12 种核心版式（覆盖 90% 场景） |
| **主题色** | 9 套（5+4） | 9 套（完整同步） |
| **适用场景** | 网页展示、私享会 | 办公交付、客户汇报、协作编辑 |

### 支持的设计系统

#### 风格 A · 电子杂志风（5 套主题色）

| # | 主题 | 适用场景 |
|---|------|---------|
| 1 | 🖋 墨水经典 | 通用/商业发布 |
| 2 | 🌊 靛蓝瓷 | 科技/数据/AI |
| 3 | 🌿 森林墨 | 自然/文化/非虚构 |
| 4 | 🍂 牛皮纸 | 怀旧/人文/文学 |
| 5 | 🌙 沙丘 | 艺术/设计/创意 |

#### 风格 B · 瑞士国际主义（4 套锚点色）

| # | 主题 | 锚点色 |
|---|------|--------|
| 1 | 🔵 克莱因蓝 IKB | `#002FA7` |
| 2 | 🟡 柠檬黄 | `#FFD500` |
| 3 | 🟢 柠檬绿 | `#C5E803` |
| 4 | 🟠 安全橙 | `#FF6B35` |

### 支持的 12 种布局

| # | 布局 | 适合场景 |
|---|------|---------|
| 1 | `hero_cover` | 封面/开场 |
| 2 | `act_divider` | 章节分隔 |
| 3 | `big_numbers` | 数据大字报（3-8 项 KPI） |
| 4 | `quote_image` | 左文右图 |
| 5 | `image_grid` | 多图对比/截图实证 |
| 6 | `pipeline` | 流程/步骤 |
| 7 | `hero_question` | 悬念问题页 |
| 8 | `big_quote` | 大引用/金句 |
| 9 | `compare` | Before/After 对比 |
| 10 | `mixed_text_image` | 图文混排 |
| 11 | `kpi_tower` | KPI 纵向柱状图 |
| 12 | `closing` | 结尾/致谢 |

---

## 工作流

### Step 1 · 需求澄清（动手前必做）

用以下问题对齐需求（如果用户已提供完整信息可跳过）：

1. **风格 A 还是 B？** — 电子杂志风 vs 瑞士国际主义风
2. **受众和场景？** — 内部汇报 / 客户提案 / 发布会 / 培训
3. **页数规模？** — 10页以内小 deck / 15-20页标准 / 30页+大型
4. **主题色？** — 风格 A 5 选 1 / 风格 B 4 选 1
5. **有没有素材？** — 文档/数据/图片链接
6. **有没有图片？** — 放 `ppt/images/` 文件夹下

#### 风格选择参考

| 用户说... | 推荐 |
|-----------|------|
| "杂志感" / "人文" / 不指定 | A · 电子杂志风 |
| "瑞士风" / "极简" / "数据驱动" / "科技" | B · 瑞士国际主义风 |
| 要交付给客户/领导（需要 .pptx） | 本 Skill |
| 需要做线上展示/网页版 | guizang-ppt-skill（原版 HTML） |

#### 大纲协助

用叙事弧模板搭骨架：

```
封面(Hook)      → hero_cover
背景(Context)   → quote_image / big_numbers
核心(Core)      → big_numbers / pipeline / compare / image_grid (3-6页)
转折(Shift)     → hero_question
收尾(Takeaway)  → big_quote / closing
```

---

### Step 2 · 组装 PPTX 规格 JSON

根据 Step 1 的结果，组装一个 JSON 规格文件。格式如下：

```json
{
  "title": "演示文稿标题",
  "author": "作者名",
  "style": "A",
  "theme": "ink-classic",
  "slides": [
    {
      "layout": "hero_cover",
      "theme_class": "hero dark",
      "kicker": "私享会 · 2026",
      "title": "一人公司",
      "subtitle": "被 AI 折叠的组织",
      "lead": "一段引人入胜的描述...",
      "meta": "作者名 · 职位"
    },
    {
      "layout": "big_numbers",
      "theme_class": "light",
      "kicker": "数据一览",
      "title": "过去 64 天",
      "lead": "从 0 到 1 的数据记录",
      "stats": [
        { "label": "Lines of Code", "number": "110K+", "note": "一行行写到 11 万+" },
        { "label": "GitHub Stars", "number": "5,166", "note": "一个开源仓库" },
        { "label": "Downloads", "number": "41K+", "note": "装到了几万台电脑里" }
      ]
    },
    {
      "layout": "quote_image",
      "theme_class": "light",
      "kicker": "BUT",
      "title": "我不是程序员。",
      "lead": "大学毕业后没写过一行代码",
      "callout": "这东西在三年前，需要一个十人团队做一年。",
      "callout_src": "— 一位观察者",
      "image": "images/screenshot.png"
    },
    {
      "layout": "pipeline",
      "theme_class": "light",
      "kicker": "Pipeline",
      "title": "工作流",
      "pipelines": [
        {
          "label": "文本侧",
          "steps": [
            { "nb": 1, "title": "Draft", "desc": "AI 起草初稿" },
            { "nb": 2, "title": "Polish", "desc": "AI 润色" },
            { "nb": 3, "title": "Morph", "desc": "AI 变形" }
          ]
        },
        {
          "label": "视觉侧",
          "steps": [
            { "nb": 4, "title": "Cut", "desc": "AI 剪辑" },
            { "nb": 5, "title": "Cover", "desc": "AI 封面" }
          ]
        }
      ]
    },
    {
      "layout": "hero_question",
      "theme_class": "hero dark",
      "kicker": "The Question",
      "question": "你的公司里，哪些岗位本来就不该由人来做？",
      "lead": "这不是技术问题，是架构问题。"
    },
    {
      "layout": "closing",
      "theme_class": "hero dark",
      "title": "Thank You",
      "lead": "让 AI 成为你的力量倍增器",
      "meta": "@author · 2026"
    }
  ]
}
```

#### 各布局的字段速查

**hero_cover / act_divider:**
`kicker`, `title`, `subtitle`(cover only), `lead`, `meta`

**big_numbers:**
`kicker`, `title`, `lead`, `stats: [{label, number, note}]` (支持 3-8 项)

**quote_image:**
`kicker`, `title`, `lead`, `callout`, `callout_src`, `image`

**image_grid:**
`kicker`, `title`, `images: ["path1", "path2", ...]` 或 `images: [{path, caption}]`

**pipeline:**
`kicker`, `title`, `pipelines: [{label, steps: [{nb, title, desc}]}]`

**hero_question:**
`kicker`, `question`, `lead`

**big_quote:**
`kicker`, `quote`, `source`, `source_meta`

**compare:**
`kicker`, `title`, `left: {kicker, title, items: [...]}`, `right: {kicker, title, items: [...]}`

**mixed_text_image:**
`kicker`, `title`, `body`, `callout`, `callout_src`, `image`

**kpi_tower:**
`kicker`, `title`, `kpis: [{label, value, unit, note}]`

**closing:**
`title`, `lead`, `meta`

style 可选值:
- `"A"` → 电子杂志风，theme 从 `ink-classic` / `indigo-porcelain` / `forest-ink` / `kraft-paper` / `dune` 中选
- `"B"` → 瑞士国际主义风，theme 从 `ikb` / `lemon` / `lemon-green` / `safety-orange` 中选

---

### Step 3 · 生成 PPTX

将 Step 2 组装的 JSON 保存为 `spec.json`，然后执行：

```bash
python <SKILL_ROOT>/scripts/generate_pptx.py spec.json output.pptx
```

**图片路径说明：**
- 支持相对路径（相对于 `spec.json` 所在目录）和绝对路径
- 如果图片文件不存在，引擎会自动生成带占位符的灰色矩形
- 图片会自动等比缩放填充到槽位中

---

### Step 4 · 预览与迭代

生成后告知用户：
- 文件路径和文件大小
- 幻灯片数量、使用的风格和主题
- 用户可以直接用 PowerPoint / WPS / Keynote 打开编辑

根据用户反馈调整 JSON spec，重新运行 Step 3 即可迭代。

---

## 设计原则

本 Skill 继承了 guizang-ppt-skill 的核心设计理念：

### 风格 A · 电子杂志风

1. **克制优于炫技** — 纯色底 + 大字号对比，不用渐变/阴影
2. **结构优于装饰** — 所有信息靠字号 + 字体对比 + 网格留白
3. **内容层级由字号和字体定义** — 最大衬线 = 主标题，大非衬线 = lead，等宽 = 元数据
4. **图片是内容支柱** — 16:10 / 4:3 / 3:2 / 1:1 标准比例
5. **节奏靠 hero 页** — light/dark/hero 页交替

### 风格 B · 瑞士国际主义风

1. **单一锚点色** — 一份 deck 只用 1 个 accent 色
2. **极致字号对比** — 主标题与正文比例 ≥ 8:1
3. **无衬线只此一家** — Inter / Helvetica / Microsoft YaHei UI
4. **直角纯色** — 不渐变、不阴影、不圆角
5. **网格至上** — 所有元素吸附到网格系统

---

## 不适合的场景

- 需要 WebGL 动态背景 → 用原版 guizang-ppt-skill（HTML）
- 需要 32 种完整版式中的冷门版式 → 用原版 guizang-ppt-skill（HTML）
- 需要交互式翻页动画 → 用原版 guizang-ppt-skill（HTML）

---

## 依赖

- Python 3.8+
- python-pptx (`pip install python-pptx`)

## 文件结构

```
guizang-pptx-skill/
├── SKILL.md                      ← 你正在读
├── scripts/
│   └── generate_pptx.py          ← PPTX 生成引擎
├── assets/
│   ├── template.html             ← 风格 A 参考模板
│   └── template-swiss.html       ← 风格 B 参考模板
└── references/                   ← 设计参考文档（同 guizang-ppt-skill）
    ├── themes.md
    ├── themes-swiss.md
    ├── layouts.md
    ├── layouts-swiss.md
    ├── components.md
    ├── checklist.md
    └── ...
```
