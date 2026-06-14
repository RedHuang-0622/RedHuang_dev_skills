---
name: devplan-python
description: 根据上下文输出详细的 Python 实现方案，遵循高内聚低耦合与设计模式，适配 dev-goal 工作流
---

# 方案设计专家 — Python (Devplan Python)

## 目标

基于前置审查的结论，设计 Python 技术实现方案，包括数据结构、接口变更、算法选择和执行顺序。

## 上下文获取（按优先级尝试）

1. **dev-goal 模式**：工作目录 `docs/YYYY-MM-DD-{模块或功能名}/`
   - 从 `devgoal流程.md` 的 `## G: Goal` 获取目标拆解
   - 从 `devgoal流程.md` 的 G4 前置审查获取影响文件和依赖关系
2. **独立模式**：读取 `docs/front-review.md`（保留兼容）
3. **最小模式**：都不存在时，从当前代码库状态和用户需求反推

## 核心设计原则

### 设计哲学（优先级从高到低）

1. **接口抽象 > 具体实现**：能用 Protocol/ABC 就绝不直接依赖具体类型。调用方定义接口，实现方满足接口
2. **通用化 > 定制化**：能写成通用组件就绝不写一次性定制代码。提取共性逻辑，差异通过参数/策略注入
3. **工厂注入 > 单例**：能用工厂/DI 就绝不依赖全局状态或单例模式。所有依赖显式传入
4. **组合 > 继承**：继承链 ≤2 层，深于 2 层 → 用组合 + Mixin 替代
5. **高内聚低耦合**：模块内高度聚合，模块间仅通过最窄 Protocol 通信

### 高内聚低耦合

- **单一职责**：每个模块/包/类只负责一个功能领域
- **接口隔离**：模块间通过 Protocol/ABC 通信，不暴露内部实现
- **依赖倒置**：高层模块不依赖低层模块，两者依赖 Protocol
- **最少知识**：一个对象应对其他对象有尽可能少的了解
- **组合优于继承**：继承链 ≤2 层，深于 2 层 → 用组合 + Mixin

### 23 种设计模式 → Python 惯用映射

在方案设计时，**必须**根据场景选择合适的设计模式：

| 优先级 | 模式 | Python 惯用实现 | 典型场景 |
|--------|------|---------------|---------|
| ⭐⭐⭐ | **Strategy** | Protocol + DI | 算法族可互换（支付方式、存储后端、压缩算法） |
| ⭐⭐⭐ | **Adapter** | 包装类实现 Protocol | 第三方 SDK 适配到内部接口 |
| ⭐⭐⭐ | **Factory Method** | `@classmethod` + 多态 / `match/case`（3.10+） | 根据配置创建不同实现 |
| ⭐⭐⭐ | **Decorator** | `@` 语法糖 / `functools.wraps` | 日志、计时、权限校验、重试 |
| ⭐⭐ | **Builder** | fluent API + named params + dataclass | Python 的 kwargs 常替代 Builder |
| ⭐⭐ | **Chain of Responsibility** | 中间件 callable 链 / ASGI middleware | 请求处理管道 |
| ⭐⭐ | **Observer** | `asyncio.Queue` / 信号/槽 / event bus | 事件驱动 |
| ⭐⭐ | **Template Method** | 基类 + 抽象方法 + 子类重写（组合优先） | 算法骨架固定，步骤可定制 |
| ⭐ | **Singleton** | ⚠️ 禁止 — module 本身就是单例，用 DI 替代 |

> Python 特有：**Context Manager** (`__enter__`/`__exit__` / `@contextmanager`) 是 Python 最优雅的资源管理模式，合适场景优先使用。

### 🔴 循环 import — 零容忍

**循环 import 绝对禁止**。如检测到潜在循环 import：

1. **提取 Protocol**：将依赖抽象为 `typing.Protocol`，放在独立的公共模块
2. **依赖倒置**：让双方都依赖 Protocol，而非互相 import 实现
3. **TYPE_CHECKING 守卫**：仅类型标注需要的 import，用 `if TYPE_CHECKING:`
4. **延迟 import**：函数内 import（最后手段，非首选）

```
❌ 循环 import:
  order.py → from .payment import process_payment
  payment.py → from .order import Order

✅ Protocol 解耦:
  protocols/payment.py → class PaymentProcessor(Protocol): ...
  order.py → from .protocols.payment import PaymentProcessor
  payment.py → from .protocols.payment import PaymentProcessor（实现）
  # payment.py 不需要 import Order，通过 order_id: str 解耦
```

### 依赖方向规则

```
高层策略 → 低层细节  ❌ 不允许
高层策略 → Protocol/ABC  ✅ 允许
低层细节 → 实现 Protocol  ✅ 允许
所有模块 → 领域模型/entity  ✅ 允许（单向）

具体层:
  entrypoints/ → services/ → protocols/  ← adapters/
       ↓             ↓                      ↓
       └─────────────┴──→ domain/ ←─────────┘
                           (entity)
```

## 🛡️ 工程约束（设计时必须遵守）

### 配置硬度等级

方案中涉及的任何可配置值，必须明确其硬度等级：

| 等级 | 形式 | 适用场景 | 示例 |
|------|------|---------|------|
| 🔴 **硬编码常量** | `typing.Final` / 模块级 `UPPER_CASE` | 数学恒量、协议常量、永不变的值 | `MAX_RETRY: Final = 3` |
| 🟠 **默认常量+覆盖** | 默认参数 + 显式传参覆盖 | 有公认默认值，少数场景需覆盖 | `def __init__(self, timeout: float = 30.0)` |
| 🟡 **环境变量** | `os.getenv` / `dynaconf` | 部署环境差异（DB URL、密钥、环境名） | `DATABASE_URL`, `API_KEY` |
| 🟢 **YAML/TOML 配置** | `pyproject.toml` + pydantic-settings | 复杂结构配置、业务参数、特性开关 | `server.port`, `feature.enable_new_flow` |
| 🔵 **构造函数注入** | `def __init__(self, dep: Dep)` | 运行时依赖、策略选择、外部服务 | `PaymentService(strategy=alipay_strategy)` |
| ⚪ **特性开关/动态** | 远程配置中心 / LaunchDarkly | 无需重启的热更新参数 | `A/B test ratio` |

**禁止**：
- ❌ 硬编码密钥/密码/Token（必须 env 或密钥管理服务）
- ❌ 硬编码环境相关 URL（必须 env 或配置）
- ❌ 硬编码业务阈值且无覆盖机制（至少是默认参数）

### Protocol vs ABC vs 具体类型（设计决策树）

```
需要跨模块依赖？ ──YES── 需要多种实现？ ──YES── ✅ 定义 Protocol
    │                           │
    NO                          NO
    │                           │
    dataclass/pydantic?        未来可能需要 mock？ ──YES── ✅ 定义 Protocol
    │                           │
    YES                         NO
    │                           │
    ✅ 用 dataclass            同一模块内单实现？ ──YES── ✅ 用具体类，不定义抽象
```

**原则**：Protocol 属于使用方（consumer），不属于实现方（producer）。

```python
# ✅ 正确：Protocol 在 order 模块（使用方）
# order/protocols.py
from typing import Protocol

class PaymentRepo(Protocol):
    async def pay(self, order_id: str, amount: Decimal) -> PaymentResult: ...

# ❌ 错误：Protocol 在 payment 模块（实现方），order 反向依赖
# payment/protocols.py
class PaymentService(Protocol): ...  # 实现方不应定义接口
```

### 模块设计：高内聚低耦合

| 原则 | 检查要点 |
|------|---------|
| **单一职责** | 一个模块只做一件事。模块 docstring 含"和"字 → 拆 |
| **最小接口** | Protocol 只包含调用方实际使用的方法。3 个方法以上 → 考虑拆分 |
| **依赖倒置** | 高层策略模块不 import 低层实现模块，双方都依赖 Protocol |
| **单向依赖** | 依赖图必须无环。`utils/`、`common/`、`helpers/` → 不应依赖业务模块 |
| **拒绝上帝模块** | 一个模块导出 >20 个公开符号 → 职责过多，考虑拆分 |

```python
# ❌ 上帝模块
# utils.py — 包含 DB helper、HTTP client、string util、date parser...
from app.utils import db_connect, http_get, slugify, parse_date  # 4 种职责

# ✅ 职责单一
# db/connection.py   — 只做 DB 连接池
# http/client.py     — 只做 HTTP 请求封装
# text/slug.py       — 只做字符串处理
# date/parser.py     — 只做日期解析
```

### 模块级状态禁令

| ❌ 禁止 | ✅ 替代 |
|--------|--------|
| `_cache: dict = {}` (模块级) | `class CacheService:` + DI |
| `_client = httpx.Client()` (模块级) | `__init__(self, client: httpx.Client)` |
| `settings = load_settings()` (模块级 IO) | `@lru_cache def get_settings()` 或 DI |
| `__init__.py` 复杂初始化 | 保持空或仅 import 公开 API |

**唯一例外**：`re.compile(...)` 模块级（不可变）、`logging.getLogger(__name__)` 模块级（官方惯例）、`Final` 常量模块级。

### None vs 默认值（设计决策）

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| "未提供"区别于"提供了空值" | `Optional[str]`，None = 未提供 | JSON `null` vs `""` 语义不同 |
| 一般字符串字段 | `str`，`""` 表示空/未提供 | 简单 |
| 函数返回值 | 返回 `T` + 异常，不返回 None | 调用方不需要 None 检查 |
| 可能找不到 | `Optional[T]` + 调用方显式检查 | `return None` 合法，但调用方必须感知 |
| JSON 序列化 | `pydantic` model + `exclude_none` | 控制 None 字段不输出 |

### 异常设计

方案中必须明确异常体系：

```python
# ✅ 模块级异常层次
class PaymentError(Exception):
    """payment 模块所有异常基类"""
    ...

class PaymentTimeoutError(PaymentError):
    """支付超时 — 可重试"""
    ...

class PaymentRefusedError(PaymentError):
    """支付被拒 — 不可重试"""
    ...

class PaymentConfigError(PaymentError):
    """配置错误 — 启动即失败"""
    ...

# ❌ 反模式
raise Exception("支付失败")  # 太宽，调用方无法针对性处理
```

### 异步 vs 同步（设计决策）

```
操作涉及 IO？ ──NO── ✅ 同步函数
    │
    YES
    │
    IO 发生在请求路径上？ ──NO── ✅ 同步 + 后台线程池
    │
    YES
    │
    ✅ async def + asyncio
```

**铁律**：同步函数中不调用 `asyncio.run()`（会导致嵌套事件循环错误）。异步函数不混用同步阻塞 IO。

## 执行步骤

1. 读取上下文（devgoal流程.md 的 G 阶段 或 front-review.md）
2. 分析现有代码模式，保持风格一致（ruff/black 配置）
3. 识别适用的设计模式（从 23 种中选取，优先 Python 惯用实现）
4. 检查循环 import，如有立即用 Protocol 解耦
5. 设计 Protocol 和数据结构，优先用 dataclass
6. 将方案拆解为可独立验证的小步骤
7. 生成方案文件并询问用户确认

## 输出格式

````markdown
# 实现方案（Python）

## 设计目标
[功能目标、非功能性要求]

## 设计模式选择
| 模式 | Python 惯用实现 | 应用位置 | 选择理由 |
|------|---------------|---------|---------|
| Strategy | Protocol + DI | payment 模块 | 多种支付方式可互换 |
| Adapter | 包装类实现 Protocol | alipay_adapter | 适配外部 SDK |

## 耦合度分析
| 模块对 | 耦合方式 | 耦合度 | 备注 |
|-------|---------|-------|------|
| order → payment | Protocol PaymentRepo | 低 | 通过 Protocol 解耦 ✅ |
| payment → alipay | 直接 import Adapter | 低 | 实现方依赖 ✅ |

## 循环 import 检查
- [ ] 已检查所有新增 import 关系
- [ ] 确认无循环 import
- [ ] `import-linter` 可验证
- [ ] 如有潜在循环已用 Protocol + TYPE_CHECKING 解耦（附方案）

## 架构设计
```python
# 核心 Protocol 定义
from typing import Protocol

class PaymentStrategy(Protocol):
    async def pay(self, order: Order) -> PaymentResult: ...
    async def refund(self, order: Order) -> RefundResult: ...

# 服务编排
@dataclass
class PaymentService:
    _strategy: PaymentStrategy  # 依赖注入

    async def process(self, order: Order) -> PaymentResult:
        return await self._strategy.pay(order)
```

## 实现步骤

1. [步骤1]：[预计修改文件] [预计耗时] [涉及设计模式]
   - 先写 Protocol → 写测试 → 写实现 → 验证通过
2. [步骤2]：[预计修改文件] [预计耗时] [涉及设计模式]
   ...

## 接口契约
```python
# 模块间通信 Protocol
class IModuleA(Protocol):
    async def method(self, *, input: Input) -> Result: ...
    # 注意: Protocol 方法签名只做文档用途，不强制运行时检查
```

## 测试策略

- 单元测试覆盖点：[列出]
- 集成测试场景：[列出]
- 边界条件：[列出]
- 性能指标：[阈值]
- 并发场景：[列出 async 路径]

## 回滚方案

[如修改失败如何恢复]

## 设计模式合规检查
- [ ] 每个 Protocol/类的职责是否单一
- [ ] 模块间是否通过 Protocol 通信
- [ ] 是否杜绝了循环 import
- [ ] 是否遵循了最少知识原则
- [ ] 继承链是否 ≤2 层
- [ ] 是否优先组合而非继承
````

## 禁止行为（设计层面）

- ❌ **硬编码密钥/密码/Token/URL** 到设计方案中
- ❌ **Protocol/ABC 定义在实现方模块中**（接口属于使用方）
- ❌ **模块级可变状态** 作为设计方案（必须 DI）
- ❌ **循环 import**（方案设计阶段就必须消灭）
- ❌ **上帝模块**（一个模块 >20 个公开符号、职责超过 2 个领域）
- ❌ **`utils/common` 模块 import 业务模块** 的依赖关系出现在设计图中
- ❌ **`__init__` 做 IO/网络调用**（必须显式初始化方法或工厂函数）
- ❌ **深继承链 ≥3 层**（组合替代）
- ❌ **混用同步阻塞 IO 和 asyncio**
- ❌ 只给一种方案（轻量级除外，必须至少 2 种方案对比）
- ❌ 方案中使用 `Any` 而非精确类型

## 暂停点

询问用户："请确认 plan.md，确认后我将开始编码"

## 打断机制

- 用户拒绝方案 → 记录拒绝原因，返回修正
- 发现循环 import 无法解决 → 停止，列出问题，建议架构调整
