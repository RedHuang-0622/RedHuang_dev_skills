---
name: dev-goal
description: GOAL 方法论调度层 — Goal(目标)→Options(方案)→Action(执行)→Learning(反思)，委托专业 Skill 执行各阶段
---

# Dev-GOAL: GOAL 方法论调度层

## 设计哲学

dev-goal 是**纯调度层**（orchestrator），不亲自执行分析/设计/编码/测试/审查。类比乐团：dev-goal 是**指挥**，专业 Skill 是**演奏者**。

| Claude Code 现实 | 本技能的对策 |
|------------------|-------------|
| Agent 无流程中止权，用户主权的权限模型 | Gate → **结构化用户确认**，用 AskUserQuestion 让用户决策 |
| Skill 间无共享状态，独立上下文 | **工作目录文件**作为 Skill 间交接协议 |
| LLM 数值评分不可靠 | 委托 devplan 做定性对比，不做数字评分 |
| 无内置知识库后端 | **memory/ 目录** + O0 历史经验检索（dev-goal 独有能力） |
| Context window 有限 | 每个 Skill 只接收其阶段所需的上下文，dev-goal 负责裁剪传递 |

**分工原则**：

| 阶段 | 委托 Skill | dev-goal 职责 |
|------|-----------|-------------|
| **G: Goal** | `front-review` | 传递需求 → 接收代码分析 → 提取目标摘要 → Gate 确认 |
| **O: Options** | `devplan` | O0 检索历史经验 → 传递上下文 → 接收多方案 → Gate 选择 |
| **A: Action** | `code-impl` + `git-commit` + `test-suite` | 传递选定方案 → 监督执行 → 生成 commit → 失败恢复 |
| **L: Learning** | `finish-review` | 目标复核 → 方案复盘 → 经验写入 memory/ → 改进建议 |

**一句话**：dev-goal 负责**怎么调度、怎么落盘、怎么沉淀**，不负责**怎么分析、怎么设计、怎么写代码**。

## 快速参考：单次执行流程

```
用户: /dev-goal 实现XXX功能

Agent: [AskUserQuestion] → 用户选规模 → 创建工作目录

Agent: [G-Phase: 委托 front-review]
       Skill(front-review) → 分析变更范围 → 写 front-review.md
       dev-goal 读 front-review.md → 提取目标摘要 → 追加到 devgoal流程.md
       → [AskUserQuestion] → 用户确认目标

Agent: [O-Phase: O0 检索 + 委托 devplan]
       ├── O0: bash search-knowledge.sh + Grep memory/ + docs/*/devgoal流程.md
       └── O1-O3: Skill(devplan) → 多方案 + 定性对比 + 推荐 → 写 plan.md
       dev-goal 读 plan.md → 追加摘要到 devgoal流程.md
       → [AskUserQuestion] → 用户选择方案

Agent: [A-Phase: 委托 code-impl + git-commit + test-suite]
       ├── Skill(code-impl) → 读 front-review.md + plan.md → 编码 → 写 code-changes.md
       ├── Skill(git-commit) → 读 G 阶段子目标 + code-changes.md → 生成 commit message
       └── Skill(test-suite) → 读 code-changes.md + G 阶段质量标准 → 分层测试 → 写 test-report.md

Agent: [L-Phase: 委托 finish-review + 经验沉淀]
       ├── Skill(finish-review) → 五轴审查 → 写 finish-review.md
       ├── L1-L2: dev-goal 目标复核 + 方案复盘（内联）
       ├── L3: Write memory/ 文件 + 更新 MEMORY.md（dev-goal 独有）
       └── L4: 改进建议（内联）

完成。
```

---

## 启动：复杂度声明（用户声明，不猜测）

执行任何阶段前，**先问用户**：

> 这次变更的规模是？
> - 🟢 **轻量**：局部修改，≤3 文件，不改 API — 精简流程，各 Skill 浅度执行
> - 🟡 **标准**（默认）：跨模块或新增功能 — 完整 G→O→A→L
> - 🔴 **深度**：架构变更 / 新增核心模块 — 各 Skill 深度执行 + 接口契约 + 依赖分析

用 `AskUserQuestion` 工具，header 设为 "变更规模"。

**根据用户选择**，向子 Skill 传递不同的深度参数：

| 阶段 | 轻量 | 标准 | 深度 |
|------|------|------|------|
| G: front-review | 快速扫描，≤3 文件 | 完整分析，含依赖图 | 同标准 + 架构影响评估 |
| O: devplan | 1-2 种思路简要对比 | 完整 O0-O3，≥2 方案定性对比 | ≥3 方案，含接口契约 + 依赖图 |
| A: code-impl | 快速实现 | 标准实现 + 回滚点 | 同标准 + 每子目标独立回滚点 |
| A: test-suite | go vet + build + test | + race -count=3 + benchmark | + 逃逸分析 + fuzz + 并发压力 + 泄漏检测 |
| L: finish-review | 快速审查 | 完整五轴审查 | 同标准 + 设计模式应用总结 |
| 输出 | 仅 memory（有价值时） | 1 个工作目录（5 个子 Skill 输出） | 1 个工作目录（含接口契约 + 依赖图） |

---

## 工作流目录

**每个任务一个目录**：`docs/YYYY-MM-DD-{模块或功能名}/`

```
docs/
  2026-06-14-支付策略重构/
    devgoal流程.md            ← dev-goal 主流程文件（G+O+A+L 摘要 + 子 Skill 输出引用）
    front-review.md           ← front-review 输出 — G 阶段
    plan.md                   ← devplan 输出 — O 阶段
    code-changes.md           ← code-impl 输出 — A1 阶段
    test-report.md            ← test-suite 输出 — A2 阶段
    finish-review.md          ← finish-review 输出 — L 阶段
```

**devgoal流程.md 结构**（dev-goal 在每个阶段结束时追加）：

```
# Workflow: {功能名}
## 元信息
- 日期: YYYY-MM-DD
- 规模: 标准/深度/轻量
- 需求: {一句话}
- 子 Skill 清单:
  - G: front-review → [front-review.md](./front-review.md)
  - O: devplan → [plan.md](./plan.md)
  - A1: code-impl → [code-changes.md](./code-changes.md)
  - A1.5: git-commit → commit message（子目标 1:1 对齐）
  - A2: test-suite → [test-report.md](./test-report.md)
  - L: finish-review → [finish-review.md](./finish-review.md)

## G: Goal ───────────────────────────────────
> 委托: front-review | 输出: [front-review.md](./front-review.md)
...（dev-goal 提取的目标摘要 + 成功标准 + 非目标）

## O: Options ────────────────────────────────
> O0: dev-goal 历史经验检索 | O1-O3 委托: devplan | 输出: [plan.md](./plan.md)
...（O0 经验汇总 + plan 方案摘要 + 选定方案）

## A: Action ─────────────────────────────────
> A1 委托: code-impl | A2 委托: test-suite
...（编码变更摘要 + 测试结果摘要 + 执行记录）

## L: Learning ───────────────────────────────
> 委托: finish-review | 输出: [finish-review.md](./finish-review.md)
...（目标复核 + 方案复盘 + 经验存储 + 改进建议）
```

---

## G-Phase: Goal 目标明确 — 委托 `front-review`

**目标**：委托专业代码分析 Skill 摸清变更范围，dev-goal 从分析结果中提炼可验证的目标。

### G1: 委托 front-review 分析变更范围

用 `Skill(front-review)` 执行代码分析。上下文传递模板：

```
请执行 front-review。
工作目录: docs/YYYY-MM-DD-{模块或功能名}/

需求: {用户原始需求描述}
规模: {轻量/标准/深度}

请分析：
- 需要修改的文件及关键位置
- 依赖关系（上游谁依赖这些文件 / 这些文件依赖谁）
- 循环依赖检查
- 风险点预判

将分析结果写入 工作目录/front-review.md。
```

### G2: 提取目标与验收标准

`front-review` 完成后，dev-goal 读取其输出，提炼为可验证的目标，追加到 `devgoal流程.md`：

```markdown
## G: Goal ───────────────────────────────────
> 委托: front-review | 输出: [front-review.md](./front-review.md)

### 目标拆解
**主目标**：[从 front-review 提炼的一句话]

| # | 子目标 | 验收标准（可测量） | 优先级 |
|---|-------|------------------|-------|
| G1 | ... | 具体到可测试 | P0/P1/P2 |

### 成功标准
- [ ] 功能：[用户可见的行为变化]
- [ ] 质量：
  - 单元测试通过，覆盖率 ≥ 80%
  - go vet 零告警
  - 竞态检测零 data race（涉及并发必跑）
  - 无 goroutine/channel/文件句柄泄漏
- [ ] 性能：[关键路径无退化，benchmem 无异常分配]
- [ ] 兼容：[不破坏现有 API/行为]

### 非目标（明确不做）
- [不做的X] — 原因：[为什么不在本次范围]
- [不做的Y] — 原因：[...]

### 前置审查摘要
> 详见 [front-review.md](./front-review.md)

| 文件 | 修改类型 | 说明 |
|------|---------|------|

**依赖关系**：[上游/下游]
**循环依赖检查**：[结果]
**风险预判**：[从 front-review 提取]
```

### ✅ Gate 1: 用户确认目标

追加完 G 阶段内容后，用 `AskUserQuestion` 确认：

> G 阶段完成（委托 front-review）。目标：[主目标]。涉及 [N] 个文件，[M] 个风险点。是否进入方案探索？

---

## O-Phase: Options 方案探索 — O0 自检 + 委托 `devplan`

**目标**：检索历史经验（dev-goal 独有能力），然后委托 devplan 设计多方案供用户选择。

### O0: 历史经验检索（dev-goal 独有，每次执行）

**快速方式**（推荐）：使用配套脚本一键检索

```bash
bash ~/.claude/skills/dev-goal/scripts/search-knowledge.sh "关键词1" "关键词2" "关键词3"
```

关键词来自 G2 的子目标描述 + front-review 涉及的文件/模块名。

**手动方式**（脚本不可用时）：

```
Read: memory/MEMORY.md（索引文件，快速定位相关条目）
Grep: memory/ 目录下所有 .md 文件，搜索关键词
Glob: docs/*/devgoal流程.md
Grep: 在这些文件中搜索 "## L: Learning" 段落下与当前模式/模块相关的经验
```

**汇总格式**（追加到 devgoal流程.md）：

```markdown
### O0: 历史经验参考
> 🔍 搜索范围: memory/ + docs/*/devgoal流程.md

| 来源 | 相关经验 | 对本次的启示 |
|------|---------|------------|
| memory/xxx.md | [经验摘要] | [如何应用] |
| docs/2026-01-01-xxx/devgoal流程.md (L-Phase) | [经验摘要] | [如何应用] |

_未找到相关经验则标注"首次探索 — 本次 L 阶段将为此场景沉淀第一份经验"_
```

### O1-O3: 委托 devplan 设计多方案

将 O0 检索结果和 front-review 分析一并传给 `devplan`：

```
请执行 devplan。
工作目录: docs/YYYY-MM-DD-{模块或功能名}/

需求: {用户原始需求描述}
规模: {轻量/标准/深度}

上下文文件:
- 变更范围分析: 工作目录/front-review.md
- 目标与验收标准: 工作目录/devgoal流程.md 的 G 阶段章节
- 历史经验参考: {O0 检索结果摘要}

请设计至少 {2/3} 种实现方案（深度级需 ≥3 种，建议至少 1 种来自不同设计范式）。
对每个方案说明：核心思路、设计模式、变更范围、关键接口草图。
做定性对比（耦合度/内聚性/可测试性/实现成本/改动面/可回滚性/团队适配）。
给出推荐方案及最大风险。

将结果写入 工作目录/plan.md。
```

`devplan` 完成后，dev-goal 读取 `plan.md`，追加摘要到 `devgoal流程.md`：

```markdown
## O: Options ────────────────────────────────
> O0: dev-goal 历史经验检索 | O1-O3 委托: devplan | 输出: [plan.md](./plan.md)

### O0: 历史经验参考
...（O0 检索结果）

### 方案摘要
> 详见 [plan.md](./plan.md)

| 方案 | 核心思路 | 设计模式 | 变更范围 | 主要风险 |
|------|---------|---------|---------|---------|
| A | ... | ... | ... | ... |
| B | ... | ... | ... | ... |

### 推荐：方案 {X}
**推荐理由**：[从 plan.md 提取]
**最大风险**：[从 plan.md 提取]
```

### ✅ Gate 2: 用户选择方案

用 `AskUserQuestion` 让用户选择方案：
- 推荐方案放在第一个，label 后加 "(Recommended)"
- 每个 option 的 description 写该方案的一句话核心思路 + 主要风险

---

## A-Phase: Action 执行 — 委托 `code-impl` + `git-commit` + `test-suite`

**目标**：严格按选定方案实现，增量验证。

### A1: 委托 code-impl 编码

```
请执行 code-impl。
工作目录: docs/YYYY-MM-DD-{模块或功能名}/

需求: {用户原始需求}
规模: {轻量/标准/深度}

上下文:
- 变更范围: 工作目录/front-review.md
- 选定方案: 工作目录/plan.md（方案 {X}）
- 目标与验收标准: 工作目录/devgoal流程.md 的 G 阶段章节

请按选定方案执行编码，增量提交。
将编码结果写入 工作目录/code-changes.md。
```

`code-impl` 完成后，dev-goal 追加摘要：

```markdown
### A1: 编码变更
> 委托: code-impl | 输出: [code-changes.md](./code-changes.md)

**摘要**：[变更文件数、行数、关键改动]
```

### A1.5: 委托 git-commit 生成提交

```
请执行 git-commit。
工作目录: docs/YYYY-MM-DD-{模块或功能名}/

上下文:
- 子目标拆解: 工作目录/devgoal流程.md 的 G 阶段章节
- 代码变更: 工作目录/code-changes.md

请按子目标 1:1 拆 commit，生成 message 后展示给我确认。
```

`git-commit` 完成后，dev-goal 将 commit 信息追加到执行记录表。

### A2: 委托 test-suite 测试

```
请执行 test-suite。
工作目录: docs/YYYY-MM-DD-{模块或功能名}/

上下文:
- 代码变更: 工作目录/code-changes.md
- 质量标准: 工作目录/devgoal流程.md 的 G 阶段"成功标准"章节
- 规模: {轻量/标准/深度} → 对应测试深度

请执行分层测试:
- 轻量: go vet + go build + go test -cover
- 标准: + go test -race -count=3 + go test -bench=. -benchmem
- 深度: + 逃逸分析 + -fuzz + 并发压力 + 资源泄漏检测

> ⚠️ 涉及 goroutine/channel/sync 原语的代码，必须跑 go test -race -count=3。

将结果写入 工作目录/test-report.md。
```

### 子 Skill 失败恢复路径

| 子 Skill | 失败场景 | 恢复方式 |
|--------|---------|---------|
| front-review | 分析遗漏关键文件 | 补充需求描述后重新调用 |
| devplan | 方案不可行（接口不兼容、依赖缺失） | 记录阻塞点 → 重新调用 devplan 调整方案 |
| code-impl | 编译/测试失败 | 修复后重试。同一错误 3 次 → 回 O 阶段 |
| test-suite | Data race 检出 | **阻塞**。修复后重跑全量 race。修复不了 → 回 O 阶段调整并发模型 |
| test-suite | 覆盖率不达标 | 标注未覆盖区域，用户决定。不阻塞 |
| test-suite | Benchmark 退化 > 20% | 标注退化项，用户决定。不阻塞 |

**回 O 阶段**：追加 `### O-补充：{阻塞原因}` 到 devgoal流程.md O 章节，调整方案后重新进入 A-Phase。

### A3: 执行记录（追加到 devgoal流程.md）

```markdown
### 执行记录
| 子目标 | 状态 | 关键变更 | 偏离方案？ |
|-------|------|---------|----------|
| G1 | ✅ | commit: abc123 | 无 |
| G2 | ✅ | commit: def456 | 有 — [说明原因和影响] |
```

---

## L-Phase: Learning 反思 — 委托 `finish-review` + 经验沉淀

**目标**：专业审查代码 + dev-goal 独有的目标复核和经验存储。

### L1: 委托 finish-review 五轴审查

```
请执行 finish-review。
工作目录: docs/YYYY-MM-DD-{模块或功能名}/

上下文:
- 需求: {用户原始需求}
- 代码变更: 工作目录/code-changes.md
- 测试报告: 工作目录/test-report.md
- 目标: 工作目录/devgoal流程.md 的 G 阶段章节

请执行五轴审查（正确性/可读性/架构/安全性/性能），标注发现问题的严重级别。
将结果写入 工作目录/finish-review.md。
```

### L2: 目标复核 + 方案效果评估（dev-goal 内联）

**第一步：目标复核** — 从 G 阶段提取验收标准，逐项核对：

```markdown
### 目标复核

| 子目标 | 验收标准 | 实际结果 | 达成？ | 偏差 |
|-------|---------|---------|-------|------|
| G1 | [从 G 阶段提取] | [实际] | ✅/❌ | [如有] |
```

**第二步：方案效果评估** — 对照 O 阶段定性对比逐维度复盘：

```markdown
### 方案实际效果 vs 预期

| 维度 | O 阶段预期 | 实际 | 差异分析 |
|------|----------|-----|---------|
| 耦合度 | [预期] | [实际] | [原因] |
| 内聚性 | [预期] | [实际] | [原因] |
| 可测试性 | [预期] | [实际] | [原因] |
| 实现成本 | [预期工时] | [实际工时] | [原因] |
| 改动面 | [预期范围] | [实际范围] | [原因] |
| 可回滚性 | [预期] | [实际] | [原因] |
| 团队适配 | [预期] | [实际] | [原因] |
| 风险命中 | [预期风险] | [是否发生] | [影响] |

> 💡 差异 > 1 档的维度 → 记录到 L3 经验存储。
```

### L3: 经验存储（dev-goal 独有，写入 memory/）

**必须写入** `memory/` 目录。文件名：`{主题关键词}.md`。

```markdown
---
name: {kebab-case-slug}
description: {一句话摘要，用于后续 Grep 检索匹配}
metadata:
  type: project
  tags: [{变更类型}, {涉及模块}, {设计模式}]
---

## 场景
{什么情况下做了这个变更}

## 方案
{选了什么方案，为什么}

## 关键经验
- {经验 1}
- {经验 2}

## 踩坑
- {坑 1}
- {坑 2}

## 工程约束违规（如有）
> 记录在编码或测试阶段发现的违反工程约束的情况，供后续 O0 按约束类别精准检索。

| 约束类别 | 具体问题 | 文件:行 | 修复方式 | 预防建议 |
|---------|---------|--------|---------|---------|
| 全局变量 | ... | ... | ... | ... |
| 野指针 | ... | ... | ... | ... |
| 硬编码 | ... | ... | ... | ... |
| 接口倒挂 | ... | ... | ... | ... |

## 可复用做法
- {做法 1}

## 结论
✅ 推荐 / ⚠️ 有条件推荐 / ❌ 不推荐
```

**重要**：写完 memory 文件后，更新 `memory/MEMORY.md` 索引：

```
- [{标题}]({filename}.md) — {一句话摘要}
```

### L4: 改进建议（dev-goal 内联）

```markdown
### 改进建议
- **流程**：[这次工作流哪里可以更顺]
- **工具**：[缺什么工具或脚本]
- **架构**：[是否暴露了架构层面的技术债]
```

---

## 输出规范

### 轻量级
```
（无 workflow 目录）
memory/{经验主题}.md      ← 仅当有值得沉淀的经验
```

### 标准级
```
docs/YYYY-MM-DD-{模块或功能名}/
  devgoal流程.md            ← dev-goal 主文件（G+O+A+L 摘要 + 子 Skill 输出引用）
  front-review.md           ← front-review 输出
  plan.md                   ← devplan 输出
  code-changes.md           ← code-impl 输出
  test-report.md            ← test-suite 输出
  finish-review.md          ← finish-review 输出
memory/{经验主题}.md         ← 至少 1 条
memory/MEMORY.md             ← 更新索引
```

### 深度级
```
docs/YYYY-MM-DD-{模块或功能名}/
  devgoal流程.md            ← 含接口契约 + 依赖图 + 设计模式总结
  front-review.md           ← 含架构影响评估
  plan.md                   ← ≥3 方案 + 接口契约 + 依赖图
  code-changes.md           ← 含每子目标回滚点
  test-report.md            ← 全面套件
  finish-review.md          ← 含设计模式应用总结
memory/{经验主题}.md         ← 至少 2 条（架构 + 工程）
memory/MEMORY.md             ← 更新索引
```

---

## 与其他 Skill 的集成协议

dev-goal 作为**纯调度层**，所有专业工作委托子 Skill 执行。交接通过工作目录下的文件：

```
dev-goal (调度层)
  │
  ├─ G: Skill(front-review) → front-review.md
  │     dev-goal 读取 → 提取目标摘要 → devgoal流程.md → Gate 1 确认
  │
  ├─ O: O0 自检（bash + Grep memory/）
  │     Skill(devplan) → plan.md
  │     dev-goal 读取 → 追加方案摘要 → devgoal流程.md → Gate 2 选择
  │
  ├─ A: Skill(code-impl) → code-changes.md
  │     Skill(git-commit) → commit message（子目标 1:1）
  │     Skill(test-suite) → test-report.md
  │     dev-goal 追加执行记录 → devgoal流程.md
  │
  └─ L: Skill(finish-review) → finish-review.md
        dev-goal 目标复核 + 方案复盘 → devgoal流程.md
        dev-goal 写 memory/ + 更新 MEMORY.md
```

**dev-goal 独有、不委托的能力**：
- 🔍 **O0 历史经验检索**：搜索 memory/ + docs/*/devgoal流程.md（其他 Skill 没有这个知识库）
- 🧠 **L3 经验存储**：写入 memory/ + 更新 MEMORY.md（dev-goal 是记忆系统的唯一写入者）
- 🚦 **Gate 确认**：每个阶段结束的结构化用户确认（AskUserQuestion）
- 🔄 **失败恢复**：子 Skill 失败时回退到上一阶段的决策逻辑

---

## 禁止行为

- ❌ **dev-goal 亲自做代码分析**（G 阶段应委托 front-review）
- ❌ **dev-goal 亲自做方案设计**（O 阶段应委托 devplan，O0 除外）
- ❌ **跳过 O0 历史经验检索**直接调 devplan（浪费过往踩坑经验）
- ❌ **跳过 Gate 确认直接进入下一阶段**（用户是最终决策者）
- ❌ **用数字评分替代定性对比**（委托 devplan 时明确要求定性对比）
- ❌ **并发代码不跑 race 检测**（data race = 未定义行为）
- ❌ **race 检出后不修复标记"后续处理"**（必须阻塞修复）
- ❌ **L 阶段不写 memory/**（后续工作流无法检索，经验流失）
- ❌ **写了 memory 不更新 MEMORY.md 索引**（写了也找不到）
- ❌ **给子 Skill 传递冗余上下文**（只传该阶段需要的文件，不传整个工作目录）
- ❌ **轻量级声明后强行走完整流程**（违背用户意图）
