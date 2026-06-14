# 前置审查报告：通用资产数据处理 Skill 系统

## 需求摘要

基于详细系统设计文档，构建一个**可扩展、元数据驱动、多智能体协作、具备完整生命周期管理**的通用资产数据处理平台 Skill。本次交付为"工具簇"内容 — 即构成 7 层架构 + 2 个横切关注点的全部配置文件、脚本、提示词模板和交互协议。

## 架构总览：9 个工具簇

```
┌─────────────────────────────────────────────────────────────┐
│                    Skill 入口 (SKILL.md)                     │
├─────────────────────────────────────────────────────────────┤
│  TC8: Goal 编排引擎     │  TC9: 多 Agent 协作协议           │
│  goal_routing.json      │  agent_capabilities.json          │
│  pipeline_builder.py    │  protocol.md                      │
├─────────────────────────────────────────────────────────────┤
│  TC1: 索引与属性簇      │  TC2: 条目化预处理                │
│  index.json             │  prompts/extraction/              │
│  clusters/*.json        │  chunker.py + extractor.py        │
│  registry.py            │                                   │
├─────────────────────────────────────────────────────────────┤
│  TC3: 标准化 IR         │  TC4: 处理逻辑与脚本              │
│  normalizer.py          │  reader/cleaner/validator/        │
│  schema_generator.py    │  transformer/analyzer.py           │
│  format_adapter.py      │  plugins/ 目录                    │
├─────────────────────────────────────────────────────────────┤
│  TC5: 任务缓存与提示词  │  TC6: 生命周期管理                │
│  task_manager.py        │  lifecycle_daemon.py              │
│  prompt_manager.py      │  archive.py + secure_delete.py    │
├─────────────────────────────────────────────────────────────┤
│  TC7: 安全与角色控制                                        │
│  rbac.py + masker.py + sandbox.py + approval.py             │
└─────────────────────────────────────────────────────────────┘
```

## 影响文件清单（按工具簇分组）

### TC1: 索引与属性簇层 (index-cluster)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `clusters/index.json` | 新增 | 全局资产目录，按 asset_type 索引到属性簇文件 |
| `clusters/base/real_estate_base.json` | 新增 | 房产基类属性簇，定义通用字段（地址、面积、估值） |
| `clusters/base/ship_base.json` | 新增 | 船舶基类属性簇 |
| `clusters/base/equipment_base.json` | 新增 | 设备基类属性簇 |
| `clusters/real_estate/mortgage.json` | 新增 | 房产-抵押属性簇，继承 real_estate_base |
| `clusters/ship/npl.json` | 新增 | 船舶-不良债权属性簇，继承 ship_base |
| `clusters/registry.py` | 新增 | ClusterRegistry：热加载、版本哈希、继承解析、变更通知 |
| `clusters/__init__.py` | 新增 | 包初始化，导出注册中心单例 |
| `clusters/validator_registry.py` | 新增 | 校验器注册表（address_validator 等） |

### TC2: 条目化预处理层 (entry-extraction)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `prompts/extraction/extract_entries_generic.md` | 新增 | 通用条目化 Prompt 模板（Jinja2 变量注入） |
| `prompts/extraction/extract_from_pdf.md` | 新增 | PDF/扫描件专用变体 |
| `prompts/extraction/extract_from_chat.md` | 新增 | 聊天记录/邮件专用变体 |
| `scripts/extraction/chunker.py` | 新增 | 文本分块器：按语义/长度切分，支持滑动窗口重叠 |
| `scripts/extraction/llm_extractor.py` | 新增 | LLM 调用封装：模板填充、分块请求、结果聚合 |
| `scripts/extraction/deduplicator.py` | 新增 | 条目去重：基于地址/金额/名称的相似度匹配 |
| `scripts/extraction/__init__.py` | 新增 | 包初始化 |
| `schemas/raw_entries.schema.json` | 新增 | raw_entries.json 的 JSON Schema 定义 |

### TC3: 标准化中间表示层 (normalized-ir)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `scripts/normalizer/structural.py` | 新增 | 结构归一化：列名别名匹配、日期标准化、布尔统一、数值清洗 |
| `scripts/normalizer/numerical.py` | 新增 | 数值归一化：Z-score、Min-Max，按字段的 normalization_available 标记 |
| `scripts/normalizer/schema_generator.py` | 新增 | 生成 schema.json：类型推断、统计摘要、缺失值、归一化选项 |
| `scripts/normalizer/summary_generator.py` | 新增 | 生成 summary.md：行数、列列表、异常预览、建议操作 |
| `scripts/normalizer/format_adapter.py` | 新增 | 多 Agent 格式适配：documents.jsonl、report.md 生成 |
| `scripts/normalizer/__init__.py` | 新增 | 包初始化，导出 normalize() 统一入口 |
| `schemas/normalized_ir.schema.json` | 新增 | data.csv + schema.json 的数据契约定义 |

### TC4: 处理逻辑与脚本层 (processing-logic)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `scripts/processing/reader.py` | 新增 | 格式检测（csv/xlsx/json/parquet）、编码推断、别名映射 |
| `scripts/processing/cleaner.py` | 新增 | 缺失值处理、去重、异常检测、common_errors 自动修复 |
| `scripts/processing/validator.py` | 新增 | 模式校验、跨字段逻辑校验、校验失败建议生成 |
| `scripts/processing/transformer.py` | 新增 | 派生字段计算（computed_fields）、透视、聚合 |
| `scripts/processing/analyzer.py` | 新增 | 描述统计、分布分析、相关性、聚类、回归 |
| `scripts/processing/__init__.py` | 新增 | 包初始化 |
| `plugins/__init__.py` | 新增 | 插件注册表：load_plugin(asset_type) |
| `plugins/ship_plugin.py` | 新增 | 船舶特有逻辑：IMO编号校验、吨位换算 |
| `plugins/equipment_plugin.py` | 新增 | 设备特有逻辑：折旧计算、残值估算 |
| `scripts/step_executor.py` | 新增 | 步骤执行器：读 step 定义 → 执行 → 保存快照 + changelog → 确认 |

### TC5: 任务缓存与提示词存储层 (task-cache)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `scripts/cache/task_manager.py` | 新增 | 任务生命周期：创建 task_id、初始化目录、状态机管理 |
| `scripts/cache/prompt_manager.py` | 新增 | 提示词管理：模板加载 → 变量填充 → 复制到 task_cache → 审计 |
| `scripts/cache/state_recovery.py` | 新增 | 状态恢复：从 meta.json 读取当前步骤，校验和检查，续跑 |
| `scripts/cache/changelog.py` | 新增 | 变更日志：记录每步骤前后差异（行数变化、修改字段） |
| `scripts/cache/__init__.py` | 新增 | 包初始化 |
| `schemas/task_meta.schema.json` | 新增 | meta.json 的 JSON Schema 定义 |

### TC6: 生命周期管理引擎 (lifecycle-engine)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `scripts/lifecycle/daemon.py` | 新增 | 后台守护进程：定期扫描 task_cache/，按策略执行清理/备份/归档 |
| `scripts/lifecycle/policy_loader.py` | 新增 | 策略加载：从属性簇继承 → 任务级覆盖 → 角色级默认 |
| `scripts/lifecycle/archiver.py` | 新增 | 冷归档：打包加密 → 上传对象存储 → 记录存档 ID |
| `scripts/lifecycle/secure_delete.py` | 新增 | 安全删除：sensitive 级别覆写（DoD 5220.22-M）后删除 |
| `scripts/lifecycle/audit_logger.py` | 新增 | 审计日志：记录清理事件、归档事件至中心审计日志 |
| `scripts/lifecycle/__init__.py` | 新增 | 包初始化 |
| `configs/lifecycle_policies.json` | 新增 | 预定义策略定义（ephemeral/short_term/long_term/permanent/supervised） |

### TC7: 安全与角色控制层 (security-rbac)

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `scripts/security/rbac.py` | 新增 | RBAC 引擎：角色定义（intern/analyst/admin）、权限检查 |
| `scripts/security/masker.py` | 新增 | 数据脱敏：按字段 access_level 自动掩码/替换 |
| `scripts/security/sandbox.py` | 新增 | 操作沙箱：隔离高风险操作，限制文件系统访问范围 |
| `scripts/security/approval.py` | 新增 | 审批工作流：高风险操作生成审批请求，等待授权 |
| `scripts/security/intern_guard.py` | 新增 | 实习生安全网：抽样限制（默认 1000 行）、强制分步确认、高风险拦截 |
| `scripts/security/__init__.py` | 新增 | 包初始化 |
| `configs/role_permissions.json` | 新增 | 角色-权限映射表 |
| `configs/approval_rules.json` | 新增 | 审批规则：哪些操作需要审批、审批人、逐级规则 |

### TC8: Goal 编排引擎 (goal-orchestrator) — 横切

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `goal_routing.json` | 新增 | Goal → Pipeline Steps 映射表 |
| `scripts/orchestrator/pipeline_builder.py` | 新增 | 流水线构建：解析 Goal → 加载路由 → 注入角色策略 → 返回步骤序列 |
| `scripts/orchestrator/adaptive_trigger.py` | 新增 | 自适应处理：分析输入特征 → 动态插入/跳过步骤 |
| `scripts/orchestrator/__init__.py` | 新增 | 包初始化 |
| `schemas/goal.schema.json` | 新增 | Goal JSON 的 Schema 定义 |

### TC9: 多 Agent 协作协议 (agent-protocol) — 横切

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `protocols/agent_protocol.md` | 新增 | Agent 协作协议：数据交换格式、缓存目录约定、错误码 |
| `configs/agent_capabilities.json` | 新增 | Agent 能力注册表：各 Agent 支持的输入/输出格式 |
| `schemas/agent_message.schema.json` | 新增 | Agent 间消息的 Schema 定义 |

### 顶层入口

| 文件路径 | 类型 | 用途 |
|---------|------|------|
| `SKILL.md` | 新增 | Skill 入口文件：声明式描述、触发条件、使用方式 |

## 依赖分析

### 工具簇间依赖关系

```
TC1 (index-cluster) ──────────── 被 TC2/TC3/TC4/TC5/TC6/TC8 依赖
  │                                （所有层都需要属性簇提供字段定义）
  ├── TC2 (entry-extraction) ── 依赖 TC1（字段定义注入 Prompt）
  │     └── TC3 (normalized-ir) ── 依赖 TC2 产出 raw_entries.json
  │           ├── TC4 (processing-logic) ── 依赖 TC3 产出 data.csv + schema.json
  │           │     └── TC5 (task-cache) ── 被 TC4 各步骤调用，管理快照和状态
  │           └── TC9 (agent-protocol) ── 依赖 TC3 统一格式，定义 Agent 间约定
  ├── TC6 (lifecycle-engine) ── 依赖 TC1（lifecycle 策略）+ TC5（task_cache 目录）
  ├── TC7 (security-rbac) ── 贯穿 TC2/TC3/TC4/TC5（权限检查、脱敏、确认）
  └── TC8 (goal-orchestrator) ── 依赖 TC1（asset_type 路由）+ 调度 TC2→TC3→TC4→TC5
```

### 关键依赖链（最长路径）

```
Goal 输入 → TC8 解析 → TC1 加载属性簇 → TC2 条目化 → TC3 标准化
→ TC4 清洗/校验/分析 → TC5 保存快照 → TC3 格式适配 → 最终交付
（全程 TC7 权限/脱敏/确认介入，事后 TC6 生命周期清理）
```

### 循环依赖检查

- [x] 确认无新增循环依赖 — 依赖方向严格从上到下（TC1 → TC2 → TC3 → TC4 → TC5）
- [x] 横切关注点（TC7/TC8/TC9）按装饰器/拦截器模式注入，不反向依赖业务层
- [x] TC6 仅读取 TC5 目录，不写回，无循环

## 风险预估

| 风险 | 概率 | 严重程度 | 影响工具簇 | 缓解措施 |
|------|------|---------|-----------|---------|
| 属性簇继承链过于复杂导致解析死循环 | 中 | 高 — 整个系统启动失败 | TC1 | 继承深度限制 ≤3 层，注册中心启动时做 DAG 校验 |
| LLM 条目化输出格式不稳定，JSON 解析失败 | 高 | 中 — 条目化流程中断 | TC2 | Schema 校验 + 重试机制（最多 3 次）+ 结构化输出工具 |
| data.csv 列名与属性簇字段名不匹配（上游数据异构） | 高 | 中 — 标准化失败 | TC3 | 别名匹配（aliases）+ 模糊匹配回退 + 未匹配列人工确认 |
| 多 Agent 并发读写同一 task_cache 导致竞态 | 中 | 高 — 数据损坏 | TC5/TC9 | task_cache 目录级文件锁 + Agent 串行化同一任务 |
| 生命周期守护进程误删进行中任务 | 低 | 高 — 数据丢失 | TC6 | meta.json 状态检查：仅清理 completed/failed 状态任务 |
| 安全删除不彻底，敏感数据可恢复 | 低 | 高 — 合规风险 | TC6/TC7 | 覆写次数可配置（默认 3 次）+ 完成后校验 |
| 实习生脱敏不完整，敏感字段泄漏到前端 | 中 | 高 — 数据泄漏 | TC7 | 按字段 access_level 自动脱敏 + 导师预览双重校验 |
| 系统跨平台兼容性问题（Windows/文件锁差异） | 中 | 中 — Windows 部署失败 | TC5/TC6 | 使用跨平台库（portalocker），避免 Unix 专属调用 |

## 推荐的构建顺序（6 阶段）

```
Phase 1: 基础骨架（TC1 + TC5 基础）
  ├── clusters/ 目录 + index.json + 2 个示例属性簇
  ├── schemas/ 目录全部 JSON Schema
  ├── task_cache 目录结构 + meta.json 约定
  └── SKILL.md 入口

Phase 2: 数据核心（TC3 + TC4）
  ├── reader.py → cleaner.py → validator.py → transformer.py → analyzer.py
  ├── structural.py normalizer → schema_generator → summary_generator
  ├── step_executor.py（快照 + changelog）
  └── plugins/ 插件注册表 + 1 个示例插件

Phase 3: 智能输入（TC2）
  ├── prompts/extraction/ 3 个模板
  ├── chunker.py → llm_extractor.py → deduplicator.py
  └── format_adapter.py（documents.jsonl / report.md 生成）

Phase 4: 横切能力（TC7 + TC8）
  ├── rbac.py + masker.py + sandbox.py + approval.py + intern_guard.py
  ├── goal_routing.json + pipeline_builder.py + adaptive_trigger.py
  └── configs/ 权限/审批配置文件

Phase 5: 运维能力（TC6 + TC5 完善）
  ├── daemon.py + policy_loader.py + archiver.py + secure_delete.py
  ├── state_recovery.py + changelog.py 完善
  └── audit_logger.py

Phase 6: 集成与协议（TC9 + 全链路联调）
  ├── agent_capabilities.json + agent_protocol.md
  ├── 全链路集成测试：Goal → 条目化 → 标准化 → 清洗 → 分析 → 交付 → 清理
  └── 实习生安全网端到端测试
```

### 关键路径：Phase 1 → Phase 2 → Phase 4 → Phase 6
### 可并行：Phase 3 与 Phase 4 可部分重叠，Phase 5 独立于 Phase 3/4
