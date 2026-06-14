# 实现方案：通用资产数据处理 Skill 系统

## 设计目标

构建 9 个工具簇（TC1-TC9），覆盖 64 个文件，实现"配置驱动、Agent 原生、生命周期感知"的数据处理平台。核心约束：新增资产类型仅需添加 JSON 配置，无需代码变更。

## 设计模式全局选择

| 模式 | Python 实现 | 应用位置 | 理由 |
|------|-----------|---------|------|
| Strategy | Protocol + DI | TC4 处理模块（reader/cleaner/validator） | 不同资产类型可替换处理策略 |
| Factory Method | `@classmethod` / `match/case` | TC8 pipeline_builder | 按 Goal 创建流水线步骤序列 |
| Decorator | `@wraps` / Context Manager | TC7 安全（脱敏/权限校验） | 非侵入式注入安全控制 |
| Observer | `watchdog` + callback | TC1 ClusterRegistry | 文件变更热加载通知 |
| Chain of Resp. | callable 链 + Protocol | TC8 流水线步骤 | 步骤顺序执行，每步可短路 |
| Adapter | 包装类实现 Protocol | TC3 format_adapter / TC4 plugins | 异构格式统一适配 |
| Template Method | 基类 + 抽象方法 | TC2 条目化脚本 | 分块→提取→去重 算法骨架固定 |

---

## 方案 A: 严格分层架构 (Layered Architecture)

### 核心思路

按架构层组织目录：`clusters/` → `extraction/` → `normalizer/` → `processing/` → `cache/` → `lifecycle/` → `security/` → `orchestrator/`。每层只依赖下一层，横切关注点通过装饰器注入。**依赖方向单向不可逆**。

### 文件组织

```
asset-data-skill/
├── SKILL.md                          # Skill 入口
├── pyproject.toml                    # 项目配置（非交付范围）
│
├── clusters/                         # TC1: 索引与属性簇
│   ├── __init__.py                   # 导出 ClusterRegistry 单例
│   ├── registry.py                   # ClusterRegistry: 热加载 + 继承解析 + 通知
│   ├── validator_registry.py         # 校验器注册表
│   ├── index.json                    # 全局资产目录
│   ├── base/
│   │   ├── real_estate_base.json
│   │   ├── ship_base.json
│   │   └── equipment_base.json
│   └── real_estate/
│       └── mortgage.json
│
├── schemas/                          # JSON Schema 定义（跨层共享）
│   ├── goal.schema.json
│   ├── task_meta.schema.json
│   ├── raw_entries.schema.json
│   ├── normalized_ir.schema.json
│   └── agent_message.schema.json
│
├── prompts/                          # TC2 提示词模板
│   └── extraction/
│       ├── extract_entries_generic.md
│       ├── extract_from_pdf.md
│       └── extract_from_chat.md
│
├── extraction/                       # TC2: 条目化预处理
│   ├── __init__.py
│   ├── chunker.py                    # 文本分块器
│   ├── llm_extractor.py              # LLM 调用封装
│   └── deduplicator.py               # 条目去重
│
├── normalizer/                       # TC3: 标准化 IR
│   ├── __init__.py                   # 导出 normalize() 统一入口
│   ├── structural.py                 # 结构归一化
│   ├── numerical.py                  # 数值归一化
│   ├── schema_generator.py           # schema.json 生成
│   ├── summary_generator.py          # summary.md 生成
│   └── format_adapter.py             # 多 Agent 格式适配
│
├── processing/                       # TC4: 处理逻辑
│   ├── __init__.py
│   ├── reader.py                     # 格式检测 + 编码推断 + 别名映射
│   ├── cleaner.py                    # 缺失值 + 去重 + 异常检测
│   ├── validator.py                  # 模式校验 + 跨字段逻辑
│   ├── transformer.py                # 派生字段 + 透视 + 聚合
│   ├── analyzer.py                   # 描述统计 + 分布 + 相关性
│   └── step_executor.py              # 步骤执行 + 快照 + changelog
│
├── plugins/                          # TC4 插件
│   ├── __init__.py                   # 插件注册表
│   ├── ship_plugin.py
│   └── equipment_plugin.py
│
├── cache/                            # TC5: 任务缓存
│   ├── __init__.py
│   ├── task_manager.py               # 任务创建 + 状态机
│   ├── prompt_manager.py             # 提示词模板→实例
│   ├── state_recovery.py             # 中断恢复
│   └── changelog.py                  # 变更日志
│
├── lifecycle/                        # TC6: 生命周期
│   ├── __init__.py
│   ├── daemon.py                     # 后台守护进程
│   ├── policy_loader.py              # 策略加载
│   ├── archiver.py                   # 冷归档
│   ├── secure_delete.py              # 安全删除
│   └── audit_logger.py               # 审计日志
│
├── security/                         # TC7: 安全角色
│   ├── __init__.py
│   ├── rbac.py                       # RBAC 引擎
│   ├── masker.py                     # 数据脱敏
│   ├── sandbox.py                    # 操作沙箱
│   ├── approval.py                   # 审批工作流
│   └── intern_guard.py               # 实习生安全网
│
├── orchestrator/                     # TC8: Goal 编排
│   ├── __init__.py
│   ├── pipeline_builder.py           # 流水线构建
│   └── adaptive_trigger.py           # 自适应触发
│
├── configs/                          # 运行时配置
│   ├── goal_routing.json             # TC8: Goal → Steps 映射
│   ├── lifecycle_policies.json       # TC6: 生命周期策略
│   ├── role_permissions.json         # TC7: 角色-权限映射
│   ├── approval_rules.json           # TC7: 审批规则
│   └── agent_capabilities.json       # TC9: Agent 能力注册
│
└── protocols/                        # TC9: 协作协议
    └── agent_protocol.md             # Agent 间数据交换约定
```

### 关键接口契约

```python
# === TC1: ClusterRegistry ===
from typing import Protocol, runtime_checkable

@runtime_checkable
class ClusterProtocol(Protocol):
    """属性簇的数据契约 — 调用方定义"""
    cluster_id: str
    inherits_from: str | None
    sensitivity: str
    fields: dict[str, dict]
    computed_fields: dict[str, str]
    lifecycle: dict

class ClusterRegistry:
    """热加载注册中心 — 单例（模块级），禁止全局可变状态"""
    def __init__(self, clusters_dir: str, index_path: str): ...
    def get_cluster(self, asset_type: str) -> ClusterProtocol: ...
    def resolve_inheritance(self, cluster: dict) -> dict: ...
    def watch(self, callback: Callable[[str], None]) -> None: ...
    @property
    def version_hashes(self) -> dict[str, str]: ...

# === TC2: Extractor ===
@runtime_checkable
class EntryExtractor(Protocol):
    """条目提取器协议"""
    def extract(self, text: str, cluster: ClusterProtocol) -> list[dict]: ...

class Chunker:
    """文本分块器 — Strategy 可替换"""
    def __init__(self, strategy: ChunkStrategy): ...
    def chunk(self, text: str) -> list[str]: ...

class LLMExtractor:
    """LLM 提取器 — Adapter 模式封装 LLM 调用"""
    def __init__(self, prompt_dir: str, llm_backend: LLMBackendProtocol): ...
    def extract(self, chunks: list[str], cluster: ClusterProtocol) -> list[dict]: ...

class Deduplicator:
    """条目去重 — 基于相似度"""
    def deduplicate(self, entries: list[dict], threshold: float = 0.85) -> list[dict]: ...

# === TC3: Normalizer ===
class Normalizer:
    """标准化入口 — Facade 模式"""
    def __init__(self, cluster: ClusterProtocol): ...
    def normalize(self, data: pd.DataFrame) -> NormalizedPacket: ...

@dataclass
class NormalizedPacket:
    """标准化数据包 — DTO"""
    data_csv: pd.DataFrame
    schema_json: dict
    summary_md: str
    raw_entries: list[dict] | None = None
    documents_jsonl: str | None = None

# === TC4: Processing Modules ===
@runtime_checkable
class Reader(Protocol):
    def read(self, source: str | Path, cluster: ClusterProtocol) -> pd.DataFrame: ...

@runtime_checkable
class Cleaner(Protocol):
    def clean(self, df: pd.DataFrame, cluster: ClusterProtocol) -> tuple[pd.DataFrame, dict]: ...

@runtime_checkable
class Validator(Protocol):
    def validate(self, df: pd.DataFrame, cluster: ClusterProtocol) -> list[ValidationIssue]: ...

@runtime_checkable
class Transformer(Protocol):
    def transform(self, df: pd.DataFrame, cluster: ClusterProtocol) -> pd.DataFrame: ...

@runtime_checkable
class Analyzer(Protocol):
    def analyze(self, df: pd.DataFrame, cluster: ClusterProtocol) -> dict: ...

# === TC5: TaskManager ===
@dataclass
class TaskMeta:
    task_id: str
    asset_type: str
    operation: str
    role: str
    status: TaskStatus  # Enum: PENDING|RUNNING|AWAITING_APPROVAL|COMPLETED|FAILED
    current_step: int
    step_checksums: dict[int, str]
    created_at: str
    policy_override: dict | None = None

class TaskManager:
    """任务生命周期管理 — Builder 模式创建任务"""
    def create_task(self, goal: Goal, cluster: ClusterProtocol) -> TaskMeta: ...
    def advance_step(self, task_id: str) -> TaskMeta: ...
    def save_snapshot(self, task_id: str, step_name: str, data: pd.DataFrame) -> None: ...
    def get_checkpoint(self, task_id: str) -> tuple[int, pd.DataFrame | None]: ...

# === TC6: LifecyclePolicy ===
@dataclass
class LifecyclePolicy:
    name: str
    default_ttl_days: int
    backup_required: bool
    stages: dict[str, StagePolicy]  # {"raw_upload": StagePolicy, ...}

@dataclass
class StagePolicy:
    ttl_days: int
    backup: bool = False

class LifecycleDaemon:
    """后台守护 — Observer 模式"""
    def __init__(self, task_cache_dir: str, policy_loader: PolicyLoader): ...
    def scan_and_enforce(self) -> list[CleanupEvent]: ...

# === TC7: Security ===
class RBACEngine:
    """权限引擎 — Decorator 模式注入"""
    def check(self, role: str, operation: str, resource: str) -> bool: ...
    def require(self, operation: str, resource: str) -> Callable: ...  # 返回装饰器

class DataMasker:
    """数据脱敏 — Strategy 模式"""
    def mask(self, df: pd.DataFrame, cluster: ClusterProtocol, role: str) -> pd.DataFrame: ...

class InternGuard:
    """实习生安全网 — Decorator + Chain of Resp. 模式"""
    def wrap_pipeline(self, steps: list[PipelineStep]) -> list[PipelineStep]: ...
    def enforce_row_limit(self, df: pd.DataFrame, role: str) -> pd.DataFrame: ...

class ApprovalWorkflow:
    """审批工作流 — State 模式"""
    def request_approval(self, task_id: str, operation: str, reason: str) -> ApprovalTicket: ...
    def check_status(self, ticket_id: str) -> ApprovalStatus: ...

# === TC8: Orchestrator ===
@dataclass
class Goal:
    asset_type: str
    operation: str
    input_source: str
    role: str = "analyst"
    params: dict | None = None
    policy_override: dict | None = None

@dataclass
class PipelineStep:
    name: str
    handler: Callable[..., Any]
    confirm_before: list[str] | None = None
    required: bool = False
    condition: Callable[[dict], bool] | None = None

class PipelineBuilder:
    """流水线构建器 — Factory Method 模式"""
    def build(self, goal: Goal, cluster: ClusterProtocol) -> list[PipelineStep]: ...
    def inject_security(self, steps: list[PipelineStep], role: str) -> list[PipelineStep]: ...

class AdaptiveTrigger:
    """自适应处理 — Strategy 模式"""
    def analyze(self, data: pd.DataFrame) -> dict[str, bool]: ...  # → {"needs_extraction": True, ...}
    def adjust_pipeline(self, steps: list[PipelineStep], features: dict) -> list[PipelineStep]: ...

# === TC9: Agent Protocol (约定，非代码) ===
# agent_protocol.md 定义：
# - 数据交换格式：data.csv(列名=属性簇字段名) + schema.json(列级元数据) + summary.md(人类可读)
# - 目录约定：task_cache/{task_id}/normalized/ 为 Agent 间交换点
# - 错误码：AGENT_ERR_INPUT_FORMAT / AGENT_ERR_TIMEOUT / AGENT_ERR_PERMISSION
# - Agent 能力声明：agent_capabilities.json 声明支持的 input_formats / output_formats
```

### 模块依赖图

```
                    ┌──────────────┐
                    │  SKILL.md    │  ← 入口
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │orchestrator│ │ schemas/ │ │configs/  │  ← 横切
        │  (TC8)   │ │(共享)    │ │(共享)    │
        └─────┬────┘ └──────────┘ └──────────┘
              │
    ┌─────────┼─────────┬──────────┬──────────┐
    ▼         ▼         ▼          ▼          ▼
┌────────┐┌────────┐┌────────┐┌────────┐┌────────┐
│clusters││extract ││normaliz││process ││ cache  │
│ (TC1)  ││ (TC2)  ││ (TC3)  ││ (TC4)  ││ (TC5)  │
└───┬────┘└───┬────┘└───┬────┘└───┬────┘└───┬────┘
    │         │         │         │         │
    └─────────┴─────────┴─────────┴─────────┘
              │                        │
              ▼                        ▼
        ┌──────────┐            ┌──────────┐
        │ security │            │lifecycle │
        │  (TC7)   │            │  (TC6)   │
        │ [装饰器] │            │ [守护进程]│
        └──────────┘            └──────────┘
              │                        │
              └───────────┬────────────┘
                          ▼
                   ┌──────────────┐
                   │  protocols/  │
                   │    (TC9)     │
                   └──────────────┘

依赖规则：
  实线 → 编译时依赖（import）
  虚线 -→ 运行时依赖（通过 Protocol/配置文件）
  TC7 通过装饰器注入 TC2-TC5，不反向依赖
  TC6 通过文件系统读取 TC5 目录，不 import
```

### 方案 A 优劣

| 维度 | 评价 |
|------|------|
| **耦合度** | 🟢 低 — 层间通过 Protocol 通信，无具体类型依赖 |
| **内聚性** | 🟢 高 — 每层单一职责，模块内高度聚合 |
| **可测试性** | 🟢 高 — 每层可独立 mock 下层 Protocol |
| **实现成本** | 🟡 中 — 64 文件，需定义 10+ Protocol，工程量较大 |
| **改动面（扩展）** | 🟢 低 — 新增资产类型仅需 JSON，新增处理能力仅需新增模块注册 |
| **可回滚性** | 🟢 高 — 每层独立目录，git revert 精确到层 |
| **团队适配** | 🟢 高 — 经典分层架构，多数开发者熟悉 |

---

## 方案 B: 管道-过滤器架构 (Pipes & Filters)

### 核心思路

以**数据流**为第一公民组织代码。每个工具簇是一个 Filter（过滤器），通过 Pipe（文件系统目录）连接。`Pipeline` 对象管理 Filter 链的执行顺序和上下文传递。配置和安全是"Pipe Wrapper"——包裹在 Pipe 外层，不改变 Filter 内部逻辑。

### 文件组织

```
asset-data-skill/
├── SKILL.md
├── pyproject.toml
│
├── filters/                          # 所有 Filter 平铺在 filters/ 下
│   ├── __init__.py                   # 导出 Pipeline 类
│   ├── pipeline.py                   # Pipeline: Filter 链管理器
│   ├── context.py                    # PipelineContext: 数据流上下文（不可变）
│   │
│   ├── f01_index.py                  # TC1: 索引查找 Filter
│   ├── f02_chunk.py                  # TC2: 文本分块 Filter
│   ├── f03_extract.py                # TC2: LLM 条目化 Filter
│   ├── f04_deduplicate.py            # TC2: 去重 Filter
│   ├── f05_normalize_structure.py    # TC3: 结构归一化 Filter
│   ├── f06_normalize_numeric.py      # TC3: 数值归一化 Filter
│   ├── f07_generate_schema.py        # TC3: Schema 生成 Filter
│   ├── f08_generate_summary.py       # TC3: Summary 生成 Filter
│   ├── f09_read.py                   # TC4: 数据读取 Filter
│   ├── f10_clean.py                  # TC4: 清洗 Filter
│   ├── f11_validate.py               # TC4: 校验 Filter
│   ├── f12_transform.py              # TC4: 变换 Filter
│   ├── f13_analyze.py                # TC4: 分析 Filter
│   ├── f14_snapshot.py               # TC5: 快照保存 Filter
│   ├── f15_adapt_format.py           # TC3: 格式适配 Filter
│   └── f16_finalize.py               # TC5: 任务完成 Filter
│
├── wrappers/                         # 管道包装器（横切关注点）
│   ├── __init__.py
│   ├── security_wrapper.py           # TC7: 安全包装（脱敏/权限/沙箱）
│   ├── approval_wrapper.py           # TC7: 审批包装（需要确认的步骤）
│   ├── lifecycle_wrapper.py          # TC6: 生命周期包装（注入 TTL 策略）
│   └── adaptive_wrapper.py           # TC8: 自适应包装（数据特征检测→插入 Filter）
│
├── configs/                          # 配置（与方案 A 相同）
│   ├── index.json
│   ├── clusters/                     # 属性簇 JSON（与方案 A 相同结构）
│   ├── goal_routing.json
│   ├── lifecycle_policies.json
│   ├── role_permissions.json
│   ├── approval_rules.json
│   └── agent_capabilities.json
│
├── schemas/                          # JSON Schema（与方案 A 相同）
├── prompts/                          # 提示词模板（与方案 A 相同）
└── protocols/                        # TC9: Agent 协作协议
    └── agent_protocol.md
```

### 关键接口契约

```python
# === 核心：Filter 协议 ===
from typing import Protocol, runtime_checkable
from dataclasses import dataclass, field, replace

@dataclass(frozen=True)
class PipelineContext:
    """不可变上下文 — 在 Filter 间传递（通过 replace 创建新实例）"""
    task_id: str
    asset_type: str
    role: str
    cluster: dict                              # 属性簇快照
    data: pd.DataFrame | None = None           # 当前数据
    entries: list[dict] | None = None          # 条目化结果
    schema: dict | None = None                 # schema.json
    summary: str | None = None                 # summary.md
    artifacts: dict[str, str] = field(default_factory=dict)  # 产出物路径映射
    metrics: dict[str, float] = field(default_factory=dict)  # 处理指标

@runtime_checkable
class Filter(Protocol):
    """过滤器协议 — 单一职责：接收 Context，返回新 Context"""
    @property
    def name(self) -> str: ...
    def apply(self, ctx: PipelineContext) -> PipelineContext: ...
    def rollback(self, ctx: PipelineContext) -> PipelineContext: ...  # 回滚到本 Filter 前

@runtime_checkable
class Wrapper(Protocol):
    """包装器协议 — 装饰 Filter.apply()"""
    def wrap(self, filter_: Filter) -> Filter: ...

# === Pipeline ===
class Pipeline:
    """管道管理器 — Chain of Resp. 模式"""
    def __init__(self, filters: list[Filter], wrappers: list[Wrapper] | None = None): ...
    def execute(self, ctx: PipelineContext) -> PipelineContext: ...
    def resume(self, ctx: PipelineContext, from_filter: str) -> PipelineContext: ...  # 恢复

# === Pipeline 构建器（替代 TC8） ===
class PipelineFactory:
    """管道工厂 — Factory Method 模式，从 goal_routing.json 构建 Filter 链"""
    def __init__(self, routing_path: str): ...
    def create(self, goal: Goal, cluster: dict) -> Pipeline: ...
    def inject_wrappers(self, pipeline: Pipeline, role: str) -> Pipeline: ...

# === 示例 Filter 实现 ===
class StructureNormalizerFilter:
    """f05: 结构归一化 Filter"""
    name = "normalize_structure"
    def apply(self, ctx: PipelineContext) -> PipelineContext:
        data = structural_normalize(ctx.data, ctx.cluster)
        return replace(ctx, data=data)

class ApprovalWrapper:
    """审批包装器 — 对 confirm_before 中的操作插入确认步骤"""
    def __init__(self, approval: ApprovalWorkflow): ...
    def wrap(self, filter_: Filter) -> Filter:
        original = filter_.apply
        def wrapped_apply(ctx: PipelineContext) -> PipelineContext:
            if needs_approval(filter_.name, ctx.role):
                ticket = self.approval.request(...)
                if not ticket.approved:
                    raise ApprovalRequired(...)
            return original(ctx)
        return replace(filter_, apply=wrapped_apply)

class AdaptiveWrapper:
    """自适应包装器 — 根据数据特征动态插入/跳过 Filter"""
    def __init__(self, trigger: AdaptiveTrigger): ...
    def wrap(self, filter_: Filter) -> Filter:
        # 在上游 Filter 执行后检查，决定是否执行本 Filter
        ...
```

### 模块依赖图

```
                    ┌──────────────┐
                    │  SKILL.md    │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ configs/ │ │ schemas/ │ │protocols/│
        └────┬─────┘ └──────────┘ └──────────┘
             │
    ┌────────┴──────────────────────────────┐
    ▼                                        ▼
┌──────────────┐                    ┌──────────────┐
│  filters/    │ ←──────────────────│  wrappers/   │
│  pipeline.py │   wrappers 装饰     │  security/   │
│  context.py  │   filters.apply()   │  approval/   │
│  f01..f16.py │                    │  lifecycle/  │
└──────────────┘                    │  adaptive/   │
                                    └──────────────┘
依赖规则：
  filters/ 之间无 import 依赖，通过 PipelineContext 解耦
  wrappers/ 依赖 filters/ 的 Filter Protocol，不依赖具体 Filter
  filters/ 和 wrappers/ 都依赖 configs/ 读配置
  无循环依赖 — wrappers 装饰 filters，filters 不知道 wrappers 存在
```

### 方案 B 优劣

| 维度 | 评价 |
|------|------|
| **耦合度** | 🟢 极低 — Filter 间零 import 依赖，通过不可变 Context 通信 |
| **内聚性** | 🟢 高 — 每个 Filter 单一职责，可独立理解和测试 |
| **可测试性** | 🟢 极高 — Filter 是纯函数（ctx → ctx），最易测试 |
| **实现成本** | 🟡 中 — 16 个 Filter + 4 个 Wrapper + Pipeline 框架，初始架设成本较高 |
| **改动面（扩展）** | 🟢 极低 — 新增处理能力 = 新增一个 Filter 文件 + 注册到路由 |
| **可回滚性** | 🟢 高 — 每个 Filter 有自己的 rollback() 方法 |
| **团队适配** | 🟡 中 — 管道-过滤器模式需要理解不可变上下文和 Wrapper 概念 |

---

## 方案 C: 微内核-插件架构 (Microkernel + Plugin)

### 核心思路

**内核最小化**：只提供任务调度、文件系统约定、数据包格式定义。**一切业务逻辑都是插件**：每个资产类型是一个插件包，内含该资产类型的属性簇、处理脚本、校验器、提示词变体。新增资产类型 = 新增插件目录 = 零内核修改。

### 文件组织

```
asset-data-skill/
├── SKILL.md
├── pyproject.toml
│
├── kernel/                           # 微内核（最精简）
│   ├── __init__.py
│   ├── scheduler.py                  # 任务调度器：接收 Goal → 加载插件 → 执行
│   ├── filesystem.py                 # 文件系统约定：task_cache 目录结构
│   ├── packet.py                     # 数据包格式定义：NormalizedPacket
│   ├── errors.py                     # 错误体系
│   └── hooks.py                      # 插件钩子定义（见下方接口契约）
│
├── plugins/                          # 插件注册表 + 所有资产插件
│   ├── __init__.py                   # PluginRegistry: 扫描 + 注册 + 加载
│   ├── registry.py                   # 插件发现机制（setuptools entry_points）
│   │
│   ├── real_estate_mortgage/         # 房产-抵押 插件
│   │   ├── __init__.py
│   │   ├── plugin.toml               # 插件元数据（替代 index.json 条目）
│   │   ├── cluster.json              # 属性簇
│   │   ├── reader.py                 # 特定读取逻辑（如有）
│   │   ├── cleaner.py                # 特定清洗逻辑（如有）
│   │   ├── validator.py              # 特定校验器
│   │   ├── prompts/                  # 本插件提示词变体
│   │   │   └── extract_mortgage.md
│   │   └── tests/                    # 插件自带测试
│   │       └── test_mortgage.py
│   │
│   ├── ship_npl/                     # 船舶-不良债权 插件
│   │   ├── __init__.py
│   │   ├── plugin.toml
│   │   ├── cluster.json
│   │   ├── validator.py              # IMO 编号校验
│   │   └── transformer.py            # 吨位换算
│   │
│   ├── equipment/                    # 设备 插件
│   │   ├── __init__.py
│   │   ├── plugin.toml
│   │   ├── cluster.json
│   │   ├── transformer.py            # 折旧计算
│   │   └── analyzer.py               # 残值估算
│   │
│   └── _default/                     # 默认插件（兜底）
│       ├── __init__.py
│       ├── cluster.json
│       └── base_processor.py         # 通用处理器
│
├── services/                         # 内核服务（横切能力，以服务形式提供）
│   ├── __init__.py
│   ├── security_service.py           # TC7: RBAC + 脱敏 + 沙箱 + 审批 + 实习生安全网
│   ├── lifecycle_service.py          # TC6: 生命周期策略 + daemon + 归档 + 安全删除
│   ├── cache_service.py              # TC5: 任务缓存 + 状态恢复 + 提示词管理
│   └── orchestration_service.py      # TC8: Goal 路由 + 流水线构建 + 自适应触发
│
├── configs/                          # 全局配置（横切服务配置）
│   ├── goal_routing.json
│   ├── lifecycle_policies.json
│   ├── role_permissions.json
│   └── approval_rules.json
│
├── schemas/                          # JSON Schema（与方案 A 相同）
├── prompts/                          # 全局提示词模板（插件可覆盖）
│   └── extraction/
│       ├── extract_entries_generic.md
│       ├── extract_from_pdf.md
│       └── extract_from_chat.md
│
└── protocols/                        # TC9: Agent 协作协议
    ├── agent_protocol.md
    └── agent_capabilities.json
```

### 关键接口契约（钩子体系）

```python
# === 内核：插件钩子 ===
from abc import ABC, abstractmethod
from typing import Protocol, runtime_checkable

@runtime_checkable
class PluginProtocol(Protocol):
    """插件必须满足的协议 — 内核定义"""
    plugin_id: str
    asset_type: str
    version: str

    def get_cluster(self) -> dict: ...
    def get_reader(self) -> "ReaderProtocol | None": ...
    def get_cleaner(self) -> "CleanerProtocol | None": ...
    def get_validator(self) -> "ValidatorProtocol | None": ...
    def get_transformer(self) -> "TransformerProtocol | None": ...
    def get_analyzer(self) -> "AnalyzerProtocol | None": ...
    def get_prompts(self) -> dict[str, str]: ...  # {name: path}
    def get_lifecycle_policy(self) -> dict | None: ...

class PluginRegistry:
    """插件注册表 — 发现 + 加载 + 版本管理"""
    def __init__(self, plugins_dir: str): ...
    def discover(self) -> list[str]: ...                         # 扫描 plugin.toml
    def load(self, plugin_id: str) -> PluginProtocol: ...
    def get_for_asset(self, asset_type: str) -> PluginProtocol: ...
    def reload(self, plugin_id: str) -> None: ...               # 热更新单插件

# === 内核：调度器 ===
class KernelScheduler:
    """微内核调度器 — 最简逻辑"""
    def __init__(
        self,
        registry: PluginRegistry,
        security: "SecurityService",
        cache: "CacheService",
        orchestrator: "OrchestrationService",
        lifecycle: "LifecycleService",
    ): ...
    def execute(self, goal: Goal) -> TaskResult: ...
    # 内部流程：
    # 1. registry.get_for_asset(goal.asset_type) → plugin
    # 2. orchestrator.build_pipeline(goal, plugin) → steps
    # 3. security.wrap_pipeline(steps, goal.role) → secured_steps
    # 4. for step in secured_steps: step.execute() via cache
    # 5. lifecycle.attach_policy(task_id, plugin.get_lifecycle_policy())

# === 内核服务接口（全部通过 Protocol 依赖注入） ===
@runtime_checkable
class SecurityService(Protocol):
    """安全服务协议"""
    def check_permission(self, role: str, operation: str, resource: str) -> bool: ...
    def mask_data(self, df: pd.DataFrame, cluster: dict, role: str) -> pd.DataFrame: ...
    def wrap_for_role(self, steps: list, role: str) -> list: ...

@runtime_checkable
class CacheService(Protocol):
    """缓存服务协议"""
    def create_task(self, goal: Goal) -> str: ...
    def save_snapshot(self, task_id: str, step: str, data: pd.DataFrame) -> None: ...
    def get_checkpoint(self, task_id: str) -> dict: ...

@runtime_checkable
class OrchestrationService(Protocol):
    """编排服务协议"""
    def build_pipeline(self, goal: Goal, plugin: PluginProtocol) -> list[PipelineStep]: ...
    def adapt_pipeline(self, steps: list, data_sample: pd.DataFrame) -> list[PipelineStep]: ...

@runtime_checkable
class LifecycleService(Protocol):
    """生命周期服务协议"""
    def attach_policy(self, task_id: str, policy: dict) -> None: ...
    def start_daemon(self, interval_seconds: int = 3600) -> None: ...

# === 插件示例 ===
class RealEstateMortgagePlugin:
    """房产-抵押插件 — 通过组合使用内核服务和全局模块"""
    plugin_id = "real_estate_mortgage"
    asset_type = "RE_MORTGAGE"
    version = "1.0.0"

    def __init__(self, plugin_dir: str): ...
    def get_cluster(self) -> dict: ...        # 返回 cluster.json
    def get_reader(self) -> ReaderProtocol | None: ...    # None = 使用通用 reader
    def get_cleaner(self) -> CleanerProtocol | None: ...  # None = 使用通用 cleaner
    def get_validator(self) -> ValidatorProtocol | None: ...
    def get_transformer(self) -> TransformerProtocol | None: ...
    def get_analyzer(self) -> AnalyzerProtocol | None: ...
```

### 模块依赖图

```
                    ┌──────────────────┐
                    │    SKILL.md      │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  kernel/         │  ← 微内核（最小化）
                    │  scheduler.py    │
                    │  filesystem.py   │
                    │  packet.py       │
                    │  hooks.py        │
                    └──┬──────┬───────┘
                       │      │
              ┌────────▼─┐ ┌─▼────────────┐
              │ services/ │ │ plugins/      │  ← 平等关系
              │ (横切能力)│ │ (业务逻辑)    │     都依赖 kernel，互相不依赖
              └───────────┘ └──────────────┘
                    │            │
                    └─────┬──────┘
                          │
                   ┌──────▼──────┐
                   │  configs/   │  ← 配置驱动
                   │  schemas/   │
                   │  protocols/ │
                   └─────────────┘

依赖规则：
  kernel/ 不 import plugins/ 也不 import services/（通过 Protocol 反向依赖）
  plugins/ 依赖 kernel/ 的钩子 Protocol
  services/ 依赖 kernel/ 的钩子 Protocol
  plugins/ 和 services/ 之间无 import 依赖（通过 kernel 调度器协调）
  完美实现了依赖倒置原则（DIP）
```

### 方案 C 优劣

| 维度 | 评价 |
|------|------|
| **耦合度** | 🟢 极低 — 内核不依赖任何插件/服务，插件和服务通过 Protocol 通信 |
| **内聚性** | 🟢 极高 — 每个插件是独立的业务单元，包含该资产类型的全部知识 |
| **可测试性** | 🟢 极高 — 每个插件可独立测试，内核可 mock 插件 |
| **实现成本** | 🔴 高 — 需定义完整的钩子体系 + 插件注册机制 + 65+ 文件 |
| **改动面（扩展）** | 🟢 极低 — 新增资产类型 = 新增插件目录，零内核修改 |
| **可回滚性** | 🟢 极高 — 插件独立部署，回滚单插件不影响其他 |
| **团队适配** | 🟡 中 — 微内核架构需要团队理解 DIP 和插件发现机制 |

---

## 三方案定性对比

| 维度 | 方案 A（分层） | 方案 B（管道-过滤器） | 方案 C（微内核-插件） |
|------|:-----------:|:----------------:|:----------------:|
| **耦合度** | 🟢 低 — 层间 Protocol | 🟢 极低 — Filter 零 import 依赖 | 🟢 极低 — 内核零插件依赖 |
| **内聚性** | 🟢 高 — 层内高度聚合 | 🟢 高 — Filter 单一职责 | 🟢 极高 — 插件内含全部业务知识 |
| **可测试性** | 🟢 高 — 层独立 mock | 🟢 极高 — Filter 纯函数 | 🟢 极高 — 插件独立测试 |
| **实现成本** | 🟡 64 文件，10+ Protocol | 🟡 16 Filter + 4 Wrapper + 框架 | 🔴 钩子体系 + 注册机制 + 65+ 文件 |
| **改动面（扩展）** | 🟢 低 — JSON 或新模块 | 🟢 极低 — 新 Filter | 🟢 极低 — 新插件目录 |
| **可回滚性** | 🟢 高 — 目录级回滚 | 🟢 高 — Filter 级回滚 | 🟢 极高 — 插件级回滚 |
| **团队适配** | 🟢 高 — 经典模式 | 🟡 中 — 需理解不可变上下文 | 🟡 中 — 需理解 DIP + 钩子 |
| **未来 20+ 资产类型** | 🟡 Plugin 目录膨胀 | 🟢 Filter 总数可控 | 🟢 每个资产一个目录 |
| **数据处理直觉** | 🟡 层间关系不够直观 | 🟢 数据流动最直观 | 🟡 需要通过调度器理解 |
| **调试便利性** | 🟢 调用栈清晰 | 🟡 Context 替换链需追踪 | 🟡 钩子分发需理解 |

---

## 推荐：方案 B（管道-过滤器），融合方案 A 的配置结构和方案 C 的插件目录

### 推荐理由

1. **数据处理天然适配管道模式**：原始数据 → 条目化 → 标准化 → 清洗 → 校验 → 分析 → 交付，每一步都是对数据流的变换，Filter 模型最能表达这个本质。

2. **Filter 纯函数可测试性最强**：每个 Filter 是 `(PipelineContext) → PipelineContext`，测试只需构造输入 Context，断言输出 Context，无需 mock 任何依赖。这对数据处理逻辑的验证尤为关键。

3. **Wrapper 模式优雅解决横切关注点**：安全（脱敏/权限/审批）、生命周期（TTL 注入）、自适应（特征检测→插入 Filter）都通过 Wrapper 装饰 Filter 链，不侵入业务逻辑。

4. **采纳方案 A 的配置结构**：属性簇 JSON、Schemas、configs/ 保持方案 A 的清晰分层，因为配置天然适合归类管理。

5. **采纳方案 C 的插件目录**：`plugins/` 目录保留，但降级为"每个资产类型的 Filter 集合 + 属性簇 + 提示词"的组合包，而非完整的微内核插件。

### 最大风险

**Filter 链过长时，PipelineContext 膨胀导致不可变性开销**。随着 16+ Filter 执行，每次 `replace(ctx, ...)` 创建新 dataclass 实例有内存开销。

**缓解措施**：
- PipelineContext 只存储引用（DataFrame、dict 等），replace 复制的是引用而非深拷贝
- 对不关心的 Filter 间状态，不写入 Context（如中间统计量用局部变量）
- 基准测试：16 Filter × 10 万行数据，Context replace 开销应 < 50ms

### 备选切换策略

如果方案 B 的 Filter 链在执行中发现：
- **调试困难**（Context 变化不可视）→ 在 `pipeline.execute()` 中增加 `verbose=True` 模式，每个 Filter 执行后打印 Context 差异
- **Wrapper 太多层**（>5 层装饰）→ 合并相近 Wrapper 为组合 Wrapper
- **性能问题** → 部分 Filter 合并为批处理 Filter，减少 Context replace 次数

---

## 循环依赖检查

| 检查项 | 方案 A | 方案 B | 方案 C |
|--------|:------:|:------:|:------:|
| 业务层间循环依赖 | ✅ 单向 | ✅ Filter 零互依赖 | ✅ 插件不互依赖 |
| 横切关注点反向依赖 | ✅ 装饰器注入 | ✅ Wrapper 装饰 | ✅ 服务不依赖插件 |
| 配置层反向依赖 | ✅ 只读 | ✅ 只读 | ✅ 只读 |
| Plugin 与 Service 循环 | N/A | N/A | ✅ 无 import 关系 |

**结论：三种方案均零循环依赖。**

---

## 实现步骤（基于推荐方案 B + A/C 融合）

| # | 步骤 | 关键文件 | 设计模式 | 阶段 |
|---|------|---------|---------|------|
| 1 | 基础骨架：项目结构 + schemas + configs | SKILL.md, schemas/*, configs/* | — | Phase 1 |
| 2 | Pipeline 框架：PipelineContext + Filter Protocol + Pipeline | filters/pipeline.py, filters/context.py | Chain of Resp. | Phase 1 |
| 3 | TC1 属性簇：index.json + clusters JSON + Filter | filters/f01_index.py, configs/clusters/ | Registry | Phase 2 |
| 4 | TC3 标准化 Filter：structural + numerical + schema + summary | filters/f05-f08 | Strategy | Phase 2 |
| 5 | TC4 处理 Filter：reader + cleaner + validator + transformer + analyzer | filters/f09-f13, plugins/ | Strategy + Adapter | Phase 2 |
| 6 | TC5 缓存 Filter：snapshot + changelog + finalize | filters/f14, filters/f16 | Memento | Phase 2 |
| 7 | TC2 条目化 Filter：chunk + extract + deduplicate | filters/f02-f04, prompts/ | Template Method | Phase 3 |
| 8 | TC3 格式适配 Filter | filters/f15 | Adapter | Phase 3 |
| 9 | TC7 安全 Wrapper：security_wrapper + approval_wrapper | wrappers/security_wrapper.py | Decorator | Phase 4 |
| 10 | TC7 实习生 Wrapper | wrappers/security_wrapper.py（合并） | Decorator | Phase 4 |
| 11 | TC8 编排：PipelineFactory + AdaptiveWrapper | wrappers/adaptive_wrapper.py, filters/pipeline.py | Factory + Decorator | Phase 4 |
| 12 | TC6 生命周期 Wrapper + daemon | wrappers/lifecycle_wrapper.py | Decorator + Observer | Phase 5 |
| 13 | TC5 状态恢复 | filters/pipeline.py (resume 方法) | Memento | Phase 5 |
| 14 | TC9 Agent 协议 | protocols/agent_protocol.md | — | Phase 6 |
| 15 | 全链路集成 + 端到端测试 | — | — | Phase 6 |

## 测试策略

| 测试层 | 覆盖目标 | 方法 |
|--------|---------|------|
| 单元：Filter | 每个 Filter.apply(ctx) 的正确性 | 构造 PipelineContext → 断言新 Context |
| 单元：Wrapper | 每个 Wrapper.wrap(filter) 的装饰效果 | mock Filter → 断言行为变化 |
| 集成：Filter 链 | 2-3 个 Filter 串联执行 | 组合 Filter → 断言最终 Context |
| 集成：Wrapper + Filter | SecurityWrapper + CleanFilter 脱敏效果 | 构造含敏感数据的 Context → 断言脱敏后 |
| 端到端：全链路 | Goal → Pipeline → 最终交付物 | 准备测试数据 → 完整执行 → 断言 data.csv + schema.json + summary.md |
| 端到端：实习生 | role=intern 全链路 | 断言抽样 1000 行、脱敏生效、审批触发 |
| 性能：基准 | Filter 链吞吐量 | 16 Filter × 10 万行，目标 < 5s |

## 回滚方案

- 每阶段 git commit，阶段间可独立回滚
- Filter 有 rollback() 方法，单 Filter 异常时回滚到该 Filter 前状态
- 配置文件变更仅需替换 JSON 文件，无需回滚代码
