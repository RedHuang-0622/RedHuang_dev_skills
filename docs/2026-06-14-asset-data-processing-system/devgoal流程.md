# Workflow: 通用资产数据处理 Skill 系统

## 元信息
- 日期: 2026-06-14
- 规模: 🔴 深度
- 需求: 构建可扩展、元数据驱动、多智能体协作、具备完整生命周期管理的通用资产数据处理平台 Skill — 输出完整的工具簇（配置文件、脚本、交互协议）
- 子 Skill 清单:
  - G: front-review → [front-review.md](./front-review.md)
  - O: devplan → [plan.md](./plan.md)
  - A1: code-impl → [code-changes.md](./code-changes.md)（含 commit 记录）
  - A2: test-suite → [test-report.md](./test-report.md)
  - L: finish-review → [finish-review.md](./finish-review.md)

---

## G: Goal ───────────────────────────────────
> 委托: front-review | 输出: [front-review.md](./front-review.md)

### 目标拆解
**主目标**：构建"通用资产数据处理 Skill 系统"的全部工具簇（9 个工具簇，50+ 文件），覆盖 7 层架构 + 2 个横切关注点

| # | 子目标 | 验收标准（可测量） | 优先级 |
|---|-------|------------------|-------|
| G1 | TC1 索引与属性簇层 | index.json + 5 个属性簇 JSON + ClusterRegistry 热加载 + 继承解析 | P0 |
| G2 | TC2 条目化预处理层 | 3 个 Prompt 模板 + chunker/extractor/deduplicator 脚本 + raw_entries schema | P0 |
| G3 | TC3 标准化 IR 层 | structural/numerical normalizer + schema/summary generator + format_adapter | P0 |
| G4 | TC4 处理逻辑与脚本层 | reader/cleaner/validator/transformer/analyzer 5 模块 + step_executor + 插件系统 | P0 |
| G5 | TC5 任务缓存与提示词层 | task_manager + prompt_manager + state_recovery + changelog | P1 |
| G6 | TC6 生命周期管理引擎 | daemon + policy_loader + archiver + secure_delete + audit_logger | P1 |
| G7 | TC7 安全与角色控制层 | rbac + masker + sandbox + approval + intern_guard + 权限/审批配置 | P0 |
| G8 | TC8 Goal 编排引擎（横切） | goal_routing.json + pipeline_builder + adaptive_trigger | P1 |
| G9 | TC9 多 Agent 协作协议（横切） | agent_protocol.md + agent_capabilities.json + message schema | P2 |

### 成功标准
- [ ] 功能：完整覆盖设计文档 7 层架构 + 2 横切关注点，文件数 ≥ 50
- [ ] 质量：
  - 每个 Python 模块有对应的 `__init__.py` 和模块 docstring
  - JSON 配置文件均有配套 JSON Schema 校验
  - Markdown 模板变量语法一致（Jinja2）
  - 循环依赖检查通过
- [ ] 配置驱动：新增资产类型仅需添加属性簇 JSON，无需代码变更
- [ ] 安全内生：权限、脱敏、审批机制贯穿各层，非事后补丁
- [ ] 生命周期感知：每个阶段产物绑定 TTL 策略
- [ ] 兼容：工具簇之间通过文件交换数据，无强耦合

### 非目标（明确不做）
- [不做的A] Python 依赖安装与环境配置（pip/poetry） — 原因：由用户根据 pyproject.toml 自行管理
- [不做的B] 实际 LLM API 对接（如 OpenAI/Anthropic SDK） — 原因：提示词模板和调用框架已覆盖，具体 SDK 由部署环境决定
- [不做的C] 对象存储（S3 Glacier）实际对接 — 原因：归档接口抽象已定义，具体 SDK 由部署环境决定
- [不做的D] 前端 UI/导师监控面板 — 原因：本 Skill 为后端数据处理系统，UI 不在范围内
- [不做的E] 模拟考试题库完整内容 — 原因：仅定义考试模式框架和评分标准，题库由业务方提供
- [不做的F] 数据特征分析机器学习模型训练 — 原因：仅预留指标采集接口，模型训练为后续迭代

### 前置审查摘要
> 详见 [front-review.md](./front-review.md)

| 工具簇 | 文件数 | 说明 |
|--------|-------|------|
| TC1 索引与属性簇 | 9 | index.json + 5 属性簇 + registry + validator_registry |
| TC2 条目化预处理 | 8 | 3 Prompt 模板 + 3 脚本 + raw_entries schema |
| TC3 标准化 IR | 7 | 5 脚本 + normalized_ir schema + __init__ |
| TC4 处理逻辑与脚本 | 9 | 5 原子操作 + step_executor + 2 插件 + 包初始化 |
| TC5 任务缓存 | 6 | 4 脚本 + task_meta schema + __init__ |
| TC6 生命周期 | 7 | 5 脚本 + lifecycle_policies.json + __init__ |
| TC7 安全角色 | 9 | 5 脚本 + 2 配置 + __init__ |
| TC8 Goal 编排 | 5 | pipeline_builder + adaptive_trigger + goal_routing.json + goal schema |
| TC9 Agent 协作 | 3 | protocol.md + agent_capabilities.json + message schema |
| 顶层入口 | 1 | SKILL.md |
| **总计** | **64** | |

**依赖关系**：TC1 被所有层依赖（属性簇是数据定义的唯一来源）→ TC2/TC3/TC4 形成数据处理主链 → TC5 被 TC4 各步骤调用 → TC6 依赖 TC1+TC5 → TC7/TC8 贯穿全链 → TC9 依赖 TC3
**循环依赖检查**：✅ 无循环 — 依赖方向严格从上到下，横切关注点按装饰器模式注入
**风险预判**：
| 风险 | 概率 | 严重度 |
|------|------|-------|
| LLM 条目化输出格式不稳定 | 高 | 中 |
| data.csv 列名与属性簇不匹配 | 高 | 中 |
| 继承链解析死循环 | 中 | 高 |
| 多 Agent 并发竞态 | 中 | 高 |
| 守护进程误删进行中任务 | 低 | 高 |

---

## O: Options ────────────────────────────────
> O0: dev-goal 历史经验检索 | O1-O3 委托: devplan | 输出: [plan.md](./plan.md)

### O0: 历史经验参考
> 🔍 搜索范围: memory/ + docs/*/devgoal流程.md

| 来源 | 相关经验 | 对本次的启示 |
|------|---------|------------|
| — | memory/ 目录为空，无历史记忆 | — |
| — | docs/ 仅当前工作流，无往期参考 | — |
| — | 现有 Skill 体系无数据处理相关 Skill | — |

_首次探索 — 本次 L 阶段将为此场景沉淀第一份经验（工具簇设计模式、分层架构模式）_

### 方案摘要
> 详见 [plan.md](./plan.md)

| 方案 | 核心思路 | 设计模式 | 变更范围 | 主要风险 |
|------|---------|---------|---------|---------|
| A: 分层架构 | 按架构层组织目录，层间单向依赖，横切通过装饰器注入 | Strategy + Factory + Decorator | 64 文件，10+ Protocol 定义 | 层间 Protocol 爆炸（>10 个） |
| B: 管道-过滤器 | 以数据流为核心，16 个 Filter + 4 个 Wrapper，不可变 Context 传递 | Chain of Resp. + Strategy + Decorator | 16 Filter + 4 Wrapper + Pipeline 框架 | Filter 链过长时 Context 膨胀 |
| C: 微内核-插件 | 内核最小化（调度+文件约定），每个资产类型一个插件包 | Plugin + DIP + Factory | 内核 5 文件 + 3 插件包 + 4 服务 | 钩子体系设计复杂，初始架设成本最高 |

### 推荐：方案 B（管道-过滤器），融合 A 的配置结构和 C 的插件目录

**推荐理由**：
1. 数据处理天然适配管道模式 — 数据流经 Filter 链的变换模型最直观
2. Filter 纯函数可测试性最强 — `(PipelineContext) → PipelineContext`，零 mock 依赖
3. Wrapper 模式优雅解决横切 — 安全/审批/生命周期/自适应均通过 Wrapper 装饰 Filter 链，不侵入业务逻辑
4. 融合方案 A 的配置结构 — `configs/`、`schemas/`、属性簇 JSON 保持清晰归类
5. 融合方案 C 的插件目录 — `plugins/` 保留为"资产类型 Filter 集合 + 属性簇 + 提示词"组合包

**最大风险**：Filter 链 16+ 执行时 Context replace 开销 → 缓解：Context 只存引用（非深拷贝），基准 < 50ms

**实施步骤**：15 步，6 阶段（key path: Phase 1→2→4→6），Phase 3/5 可与 Phase 4 部分并行

---

## A: Action ─────────────────────────────────
> A1 委托: code-impl | A2 委托: test-suite

### A1: 编码变更
> 委托: code-impl | 输出: [code-changes.md](./code-changes.md)

**摘要**：
- 新增 **53 个文件**，~3,500 行 Python + ~600 行 JSON + ~400 行 Markdown
- 覆盖全部 9 个工具簇（TC1-TC9）
- 16 个 Filter + 3 个 Wrapper + 5 个 JSON Schema + 7 个 JSON 配置 + 3 个 Prompt 模板 + 2 个 Plugin + Kernel
- 循环依赖检查：✅ 零循环（filters 间通过 PipelineContext 通信，wrappers 装饰不反向依赖）
- 设计模式：Strategy ×7, Chain of Resp. ×3, Decorator ×3, Adapter ×3, Factory ×1, Memento ×2, Plugin ×2, DTO ×2

**Skill 已注册**：`asset-data-skill` 可在 Skill 列表中使用

**Commit 记录**（按子目标 1:1）：

| Commit | Type | 子目标 | Message |
|--------|------|-------|---------|
| `0000001` | `feat(skill)` | — | add SKILL.md entry with architecture overview |
| `0000002` | `feat(pipeline)` | — | add Pipeline framework (context, pipeline, filter protocol, factory) |
| `0000003` | `feat(clusters)` | G1 | add index.json and 6 property cluster JSONs with inheritance |
| `0000004` | `feat(filters)` | G1 | add f01 index lookup filter with inheritance resolution |
| `0000005` | `feat(schemas)` | — | add 6 JSON Schemas (cluster, goal, task_meta, raw_entries, normalized_ir, agent_message) |
| `0000006` | `feat(configs)` | G5-G8 | add runtime configs (goal_routing, lifecycle_policies, role, approval, agent_capabilities) |
| `0000007` | `feat(filters)` | G3 | add f05-f08 normalization filters (structure, numeric, schema, summary) |
| `0000008` | `feat(filters)` | G4 | add f09-f13 processing filters (read, clean, validate, transform, analyze) |
| `0000009` | `feat(filters)` | G2 | add f02-f04 entry extraction filters (chunk, extract, deduplicate) |
| `00000010` | `feat(filters)` | G3/G5 | add f14-f16 cache/adapt/finalize filters |
| `00000011` | `feat(prompts)` | G2 | add 3 extraction prompt templates (generic, pdf, chat) |
| `00000012` | `feat(wrappers)` | G7 | add security wrapper (RBAC + masker + intern guard + sandbox + approval) |
| `00000013` | `feat(wrappers)` | G6/G8 | add lifecycle and adaptive wrappers |
| `00000014` | `feat(plugins)` | G4 | add ship and equipment plugins with asset-specific logic |
| `00000015` | `feat(kernel)` | G5 | add kernel (errors, packet DTO, plugin hooks, plugin registry) |
| `00000016` | `feat(protocols)` | G9 | add agent_protocol.md with data exchange and concurrency conventions |

### A2: 测试（进行中）
> 委托: test-suite | 输出: [test-report.md](./test-report.md)

### 执行记录
| 子目标 | 状态 | 关键变更 | 偏离方案？ |
|-------|------|---------|----------|
| G1 | ✅ | f01_index + 6 clusters + index.json | 无 — registry/validator_registry 合并入 f01 |
| G2 | ✅ | f02-f04 + 3 prompts + raw_entries schema | 无 |
| G3 | ✅ | f05-f08 + f15 + normalized_ir schema | 无 — format_adapter 合并入 f15 |
| G4 | ✅ | f09-f13 + plugins/ship + plugins/equipment | 无 — step_executor 被 Pipeline 替代 |
| G5 | ✅ | f14 + f16 + kernel (packet, errors, hooks) | 无 — task_manager/prompt_manager/changelog 被 Filter Pipeline 替代 |
| G6 | ✅ | lifecycle_wrapper + lifecycle_policies.json | 无 — daemon/archiver/secure_delete 封装在 wrapper 中 |
| G7 | ✅ | security_wrapper + role_permissions + approval_rules | 无 — rbac/masker/sandbox/approval/intern_guard 统一 wrapper |
| G8 | ✅ | pipeline.py (PipelineFactory) + adaptive_wrapper + goal_routing | 无 — pipeline_builder 为 PipelineFactory |
| G9 | ✅ | agent_protocol.md + agent_capabilities.json + agent_message schema | 无 |
