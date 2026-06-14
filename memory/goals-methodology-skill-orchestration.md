---
name: goals-methodology-skill-orchestration
description: dev-goal GOAL 方法论的实际执行经验 — 5 阶段调度、文件交接协议、Skill 集群的优缺点
metadata:
  type: project
  tags: [methodology, orchestration, skill-design, workflow, dev-goal]
---

## 场景

首次使用 dev-goal 完成一个**深度级**项目：从一份 12 节的系统设计文档出发，构建一个包含 53 个文件、6000+ 行代码的通用资产数据处理系统。完整走过 G→O→A→L 四阶段。

## 关键经验

- **GOAL 的四阶段命名是精心设计的钩子**：G(Goal)→O(Options)→A(Action)→L(Learning) 的字母序列提供了自然的阶段分割，让每个阶段有明确的"边界感"。
- **"深度"级别的产出物数量大约是标准级的 10 倍**：53 个文件 vs 预期的 10-15 个。如果未来跑"轻量"级，需要明确约束上限（如 ≤3 文件）。
- **文件交接协议是唯一正确的 Skill 间通信方式**：每个 Skill 有独立上下文，只能通过工作目录的 Markdown 文件交接。这避免了 Skill 间的隐式依赖。
- **Gate 确认是防止"假阳性进度"的关键**：G 阶段完成后用户确认目标，O 阶段完成后用户选择方案——如果跳过 Gate，后续可能基于错误前提执行。
- **O0 历史经验检索的价值在第一次使用时为零**（memory/ 为空），但随着每次 L 阶段积累，这个环节的价值会指数增长。

## 踩坑

- **深度级项目的 A 阶段耗时远超预期**：生成 53 个文件需要 50+ 次 Write 调用。在批量生成模式下，"一次调用并行写多个文件"可以大幅缩短时间。
- **Skill 定义中的工程约束存在大量重复**：`设计哲学`、`配置硬度`、`依赖方向` 在 4-6 个 Skill 的 SKILL.md 中逐字重复。修改一处需要同步多处。
- **Memory 系统需要刻意执行 L 阶段才能填充**——如果因为时间原因跳过 L 阶段，所有经验都会丢失。
- **测试阶段（A2）发现了源代码阶段（A1）的 bug**：7 个运行时 bug 在 A1 阶段未被发现，到 A2 才暴露。code-impl 需要内置"至少跑一次基本测试"的检查点。

## 可复用做法

- **工作目录命名规范**：`docs/YYYY-MM-DD-{功能名}/` 提供天然的按时间排序和检索
- **5 文档体系**：`front-review.md` → `plan.md` → `code-changes.md` → `test-report.md` → `finish-review.md` 形成完整项目档案
- **子目标 1:1 commit**：每个子目标（G1-G9）对应一个 commit，回溯清晰
- **Gate 确认用 AskUserQuestion**：结构化选项（含 Recommended 标记）让用户决策效率高

## 结论

✅ 推荐 — GOAL 方法论在处理"从需求文档到完整代码"的转化任务中表现出色。但"轻量"级路径尚未验证，且 memory 系统需要持续积累才能发挥 O0 检索的真正价值。
