---
name: code-impl-python
description: 根据方案执行 Python 编码，接口先行，增量验证，自动同步测试，遵循设计模式与 Python 工程约束
---

# 编码实现专家 — Python (Code-Impl Python)

## 目标

严格按方案执行 Python 编码，每完成一步立即验证，自动更新相关测试文件。

## 上下文获取（按优先级尝试）

1. **dev-goal 模式**：工作目录 `docs/YYYY-MM-DD-{模块或功能名}/`
   - 从 `devgoal流程.md` 的 `## G: Goal` 获取目标拆解与验收标准
   - 从 `devgoal流程.md` 的 `## O: Options` 获取选定方案、接口草图、设计模式
2. **独立模式**：读取 `docs/plan.md` + `docs/front-review.md`（保留兼容）
3. **最小模式**：都不存在时，从当前代码库状态和用户需求反推

## 编码原则（核心思想）

- **接口抽象 > 具体实现**：能用 Protocol/ABC 的就绝不当场指定调用方。依赖抽象不依赖具体
- **通用化 > 定制化**：能写成通用组件就绝不写一次性的定制代码。提取共性，参数化差异
- **工厂注入 > 单例**：能用工厂/DI 就绝不依赖全局状态或单例。一切依赖显式传入
- **组合优于继承**：优先用依赖注入 + 组合，深继承链（≥3 层）禁止
- **高内聚低耦合**：一个模块只做一件事，模块间仅通过最窄接口通信 — 实现细节不泄露
- **零循环依赖**：绝不引入循环 import，如有必要即时抽取 Protocol 解耦
- **垂直切片**：一个测试 → 一个实现 → 验证通过 → 下一个，不批量操作
- **类型优先**：所有公开函数必须有类型标注（mypy strict），禁止裸露 `Any`
- **风格一致**：遵循项目现有 `pyproject.toml` 的 ruff/black 配置
- **单一职责（量化）**：每个函数 ≤ 50 行，每个文件 ≤ 500 行，每个类 ≤ 250 行

## 编码前检查清单

- [ ] 已读取 G 阶段目标拆解（知道要达成什么），或 plan.md
- [ ] 已读取 O 阶段选定方案与接口契约（知道怎么实现），或 plan.md
- [ ] 已检查 import 链，确认无循环 import
- [ ] 已确认项目 Python 版本（3.10+ / 3.11+ / 3.12+）
- [ ] 已确认类型检查器版本和严格程度

## 🛡️ 工程约束（编码时强制）

### 配置硬度：实施对照

| 值类型 | 必须用 | 检测方式 |
|--------|-------|---------|
| 密钥/Token/密码 | `os.getenv` / `dotenv` / Secret Manager | Grep: `"sk-"`, `"password"`, `"token"`, `"secret"` 不能出现在代码字面量 |
| 环境相关 URL | env / `.env` / `pyproject.toml` | Grep: `"http://"` 或 `"https://"` 后跟具体 IP/域名 → 抽到 env |
| 不变常量 | `typing.Final` / 模块级 `UPPER_CASE` | 魔法数字/字符串出现在函数体中 → 提取为 `Final` 常量 |
| 业务阈值 | 默认参数 + 显式覆盖 | 如 `def __init__(self, page_size: int = 20)` |
| 外部依赖 | 构造函数注入 | 模块级 `client = httpx.Client()` → 改为 `def __init__(self, client: httpx.Client)` |
| 特性开关 | `os.getenv("FEATURE_X")` 或配置中心 | 条件逻辑依赖环境变量而非代码分支 |

```python
# ❌ 硬编码密钥
API_KEY = "sk-abc123..."                # 致命
DATABASE_URL = "postgresql://..."       # 致命

# ✅ 运行时注入
import os
API_KEY = os.getenv("API_KEY")          # 环境变量
# 或
from dynaconf import settings
DATABASE_URL = settings.DATABASE_URL    # 配置中心
```

**编码后自检**：对整个 diff 跑一次 mental grep — 是否有任何硬编码的秘密、URL、或环境特定值？

### None 安全：Python 版 nil 防御

```python
# ❌ 返回 None 且无文档说明 — 调用方必崩
def get_user(user_id: int) -> User:
    if user_id == 0:
        return None  # 调用方不知情，AttributeError
    return User(id=user_id)

# ✅ 返回 Optional + 调用方显式处理
from typing import Optional

def get_user(user_id: int) -> Optional[User]:
    if user_id == 0:
        return None
    return User(id=user_id)

# 调用方:
user = get_user(0)
if user is not None:    # 显式检查
    user.do_something()

# ✅ 业务上不应为 None 时，抛异常而非返回 None
def get_user(user_id: int) -> User:
    if user_id == 0:
        raise ValueError(f"Invalid user_id: {user_id}")
    return User(id=user_id)
```

**规则**：
- 函数可能返回 None → 返回类型标注为 `Optional[T]`，调用方必须检查
- 函数不应返回 None → 标注 `T`，异常时 `raise`，不返回 None
- `is None` 不用 `== None`（后者可被重载 `__eq__`）
- JSON API：需要区分 null 和空串时用 `Optional[str]`，否则用 `str | None` + `omit_none`

### 可变默认参数（铁律）

```python
# ❌ 绝不允许 — Python 经典陷阱
def add_item(item: str, items: list[str] = []) -> list[str]:
    items.append(item)  # 所有调用共享同一个 list！
    return items

# ✅ 正确
def add_item(item: str, items: list[str] | None = None) -> list[str]:
    if items is None:
        items = []
    items.append(item)
    return items
```

**提交前必查**：`grep "=\[\]"` 或 `grep "=\{\}"` 出现在函数签名中 → 必须修复。

### 模块级可变状态禁令

```python
# ❌ 绝不允许
_cache: dict[str, Any] = {}           # 模块级可变全局
_client = httpx.Client()              # 模块级外部连接
_counter = 0                          # 模块级可变计数
_settings = load_settings()           # 模块级初始化 IO

# ✅ 替代方案
# 方案 1: 依赖注入
class UserService:
    def __init__(self, client: httpx.Client, cache: Cache) -> None:
        self._client = client
        self._cache = cache

# 方案 2: 工厂函数（无状态模块）
from functools import lru_cache

@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return load_settings()

# 方案 3: 不可变常量（允许）
DEFAULT_TIMEOUT: Final = 30.0
ALLOWED_METHODS: Final[tuple[str, ...]] = ("GET", "POST", "PUT")
```

**例外**：`re.compile(...)` 模块级（不可变）、`logging.getLogger(__name__)` 模块级（官方惯例）。

### 异常处理

```python
# ❌ 绝不允许：裸 except / 吞异常
try:
    do_something()
except:
    pass  # 键盘中断都被吞了！

# ❌ 绝不允许：异常宽度过大
try:
    do_something()
except Exception:  # 太宽，吞掉所有
    pass

# ✅ 捕获具体异常
try:
    do_something()
except (ValueError, KeyError) as e:
    logger.warning("Expected error: %s", e)
    raise  # 或做具体处理

# ✅ 资源管理用 context manager，不用 try-finally
with open("file.txt") as f:
    data = f.read()
# 自动关闭，不需要 finally

# ✅ 自定义异常层次
class PaymentError(Exception):
    """支付模块基础异常"""
    ...

class PaymentTimeoutError(PaymentError):
    """支付超时"""
    ...

class PaymentRefusedError(PaymentError):
    """支付被拒"""
    ...
```

**提交前必查**：
- `grep "except:"` — 裸 except 零容忍
- `grep "except Exception:"` — 确认是否有意，大部分应更具体
- `grep "except.*pass"` — 吞异常必须写注释说明原因

### 接口与抽象：Protocol > ABC

```python
# ✅ 首选：typing.Protocol（结构化子类型，类似 Go interface）
from typing import Protocol

class PaymentStrategy(Protocol):
    """支付策略接口 — 属于使用方，非实现方"""
    async def pay(self, order: Order) -> PaymentResult: ...
    async def refund(self, order: Order) -> RefundResult: ...
    @property
    def name(self) -> str: ...

# 实现方不需要显式继承 — 满足结构即可
class AlipayStrategy:  # 不继承 PaymentStrategy
    async def pay(self, order: Order) -> PaymentResult:
        ...
    async def refund(self, order: Order) -> RefundResult:
        ...

# ⚠️ 需要运行时检查时用 ABC
from abc import ABC, abstractmethod

class PaymentStrategy(ABC):
    @abstractmethod
    async def pay(self, order: Order) -> PaymentResult: ...

# ❌ 禁止：接口定义在实现方模块中
# payment/alipay.py
class PaymentStrategy(Protocol):  # 错误！接口属于使用方
    ...

# ✅ 接口定义在使用方模块中
# order/payment_repo.py
class PaymentStrategy(Protocol):  # 正确！order 定义自己需要的接口
    ...
```

### 依赖方向规则

```
高层策略 → 低层细节  ❌ 不允许
高层策略 → Protocol/ABC  ✅ 允许
低层细节 → 实现 Protocol  ✅ 允许
所有模块 → 领域模型/entity  ✅ 允许（单向）
```

```python
# ❌ 架构倒挂：utils 模块 import 业务模块
# utils/common.py
from app.models import User  # utils 引业务 → 架构倒挂

# ✅ 正确：utils 零业务依赖
# utils/datetime.py
from datetime import datetime, timezone  # 只引标准库或第三方基础库
```

### 高内聚低耦合：提交前过一遍

| 检查项 | 指标 |
|--------|------|
| 模块级公开符号数 | > 20 个公开函数/类 → 职责可能太多 |
| 文件行数 | > 500 行 → 拆文件 |
| 函数行数 | > 50 行 → 拆函数（测试辅助除外） |
| 类行数 | > 250 行 → 拆类 / 提取 Mixin 或组合 |
| import 数 | 一个模块 import > 10 个其他模块 → 耦合过高 |
| 循环 import | `ruff check` + `import-linter` 零告警是底线 |
| utils/common 模块 | 不 import 任何业务模块 ← **铁律** |

### 模块设计原则（框架无关）

**不规定具体目录结构**——不同项目/团队有自己的组织方式。但以下原则跨结构适用：

| 原则 | 检查要点 |
|------|---------|
| **单一职责** | 一个模块只做一件事。描述模块需要"和"字 → 拆 |
| **最小接口** | Protocol 只包含调用方实际使用的方法，不提前"预留" |
| **依赖倒置** | 高层策略不 import 低层实现，双方依赖 Protocol |
| **单向依赖** | 依赖图无环。通用工具层不反向依赖业务层 |
| **拒绝上帝模块** | 一个模块 >20 个公开符号 → 职责过多，考虑拆分 |

**反模式**（任何结构下都禁止）：
- `utils.py` / `helpers.py` / `common.py` 汇集 DB、HTTP、字符串、日期等无关职责
- 通用模块反向 import 业务模块（架构倒挂）

### 循环 import：零容忍

```python
# ❌ 循环 import: order.py → payment.py → order.py
# order.py
from .payment import PaymentService  # order 引 payment

# payment.py
from .order import Order  # payment 引 order → 循环！

# ✅ 解耦方案 1: 提取 Protocol
# protocols/payment.py
from typing import Protocol
class PaymentRepo(Protocol):
    async def pay(self, order_id: str) -> None: ...

# order.py
from .protocols.payment import PaymentRepo  # 只依赖协议

# payment.py
from .protocols.payment import PaymentRepo  # 实现协议
# 不需要 import Order 具体类型，通过 order_id str 解耦
```

## 编码即检查（每步验证）

```bash
# 1. 类型检查（替代 go vet）
mypy src/ --strict

# 2. Lint 检查
ruff check src/

# 3. 格式化检查
ruff format --check src/

# 4. 仅运行相关测试（快速反馈）
pytest tests/ -v -x --tb=short

# 5. 安全扫描
bandit -c pyproject.toml src/
```

**代码检查失败 → 立即停止，修复后继续。**

## 执行步骤

### Step 1: 接口先行

在实现之前，先定义模块间协议：

```python
# protocols/payment.py  ← 使用方定义的协议
from typing import Protocol, runtime_checkable

@runtime_checkable
class PaymentStrategy(Protocol):
    """支付策略 — order 模块定义的契约"""
    async def pay(self, order_id: str, amount: Decimal) -> PaymentResult: ...
    async def refund(self, transaction_id: str) -> RefundResult: ...
```

### Step 2: 按方案顺序实现

按方案中的实现步骤顺序执行。每完成一个子目标 → 立即验证。

### Step 3: 自动更新测试

修改函数签名或行为时，同步更新对应测试文件：
- 识别 `tests/` 下对应的 `test_*.py` 文件
- 更新参数化测试 `@pytest.mark.parametrize` 的 case
- 删除过时的测试

### Step 4: 输出变更摘要

**根据调用模式选择输出目标**：

| 模式 | 输出目标 |
|------|---------|
| dev-goal 模式 | 写入工作目录 `docs/YYYY-MM-DD-{模块或功能名}/code-changes.md` |
| 独立模式 | 生成 `docs/YYYY-MM-DD-功能变更摘要-code-changes.md` |

## 输出格式

```markdown
# 代码变更摘要

## 新增文件
| 文件路径 | 用途 | 设计模式 |
|---------|------|---------|
| protocols/payment.py | 支付策略 Protocol | Strategy |

## 修改文件
| 文件路径 | 修改类型 | 具体位置 | 说明 |
|---------|---------|---------|------|
| services/payment.py | 重构 | L45-L132 | 消除 if-else，注入策略 |

## 删除文件
| 文件路径 | 删除原因 |
|---------|---------|
| old_payment.py | 功能迁移到新模块 |

## API 变更
| API | 变更类型 | 兼容性 | 迁移说明 |
|-----|---------|-------|---------|
| `process(order_id)` | 签名变更 → `async process(order_id, strategy)` | ⚠️ 不兼容 | 调用方需注入策略参数 |

## 设计模式使用
| 模式 | 文件 | 效果 |
|------|-----|------|
| Strategy | payment.py | 支付方式可插拔 |
| Adapter | alipay_adapter.py | 适配支付宝 SDK 到内部 Protocol |

## 接口抽象
| Protocol/ABC | 实现方 | 使用方 |
|-------------|-------|-------|
| PaymentStrategy | alipay_adapter.py | order/service.py |

## 循环 import 检查
- [ ] 已确认无新增循环 import
- [ ] `ruff check` 通过
```

## Python 特有设计模式映射

| GoF 模式 | Python 惯用实现 | 说明 |
|----------|---------------|------|
| Strategy | Protocol + DI | duck typing 天然支持 |
| Adapter | 包装类实现 Protocol | 比 Go 更简洁 |
| Factory Method | `@classmethod` + 多态 | 或直接用 `match/case`（3.10+） |
| Builder | fluent API + `@dataclass` | Python 的 named param 常替代 Builder |
| Decorator | `@` 语法糖 / `functools.wraps` | Python 内置一等支持 |
| Observer | `asyncio.Queue` / 事件总线 | 语言级信号/槽 |
| Chain of Responsibility | 中间件 callable 链 | 类似 Go net/http middleware |
| Singleton | ❌ 禁止 — 用 DI 容器或模块级不可变常量 | Python 模块本身就是单例，不再额外套 |
| Template Method | 基类 + 抽象方法 + 子类重写 | 可用但组合优先 |

## 禁止行为

- ❌ **硬编码密钥/密码/Token/环境URL**（必须 env 或配置中心）
- ❌ **可变默认参数**（`def f(x=[])` → 必须 `def f(x=None)`）
- ❌ **裸 except / 吞异常**（`except: pass` 零容忍）
- ❌ **模块级可变状态**（`_cache = {}`、`_client = Client()` → DI）
- ❌ **循环 import**（必须设计阶段消灭）
- ❌ **`utils/common` 模块 import 业务模块**（架构倒挂）
- ❌ **返回 `None` 不标注 `Optional`**（调用方无感知）
- ❌ **`is` 比较字面量**（`x is 5` → CPython 有小整数缓存，实现细节不可依赖）
- ❌ **类型标注使用 `Any` 偷懒**（必须用 `Protocol` 或 `TypeVar` 精确化）
- ❌ **`__init__` 做 IO/网络调用**（必须显式 `async def initialize()`）
- ❌ **深继承链 ≥3 层**（组合替代）
- ❌ **`from module import *`**（污染命名空间）
- ❌ 一次性修改超过 5 个不相关的文件
- ❌ 在未读取方案的情况下开始编码
- ❌ 跳过 Protocol/ABC 直接依赖具体实现
- ❌ 构造函数做可能失败的操作时不用工厂函数（`def __init__` 不能是 async，也用不了 `await`）

## 暂停点

询问用户："编码完成，请确认后我将运行完整测试"

## 打断机制

| 触发条件 | 处理方式 |
|---------|---------|
| mypy strict 报错 | 停止，报告错误位置和类型 |
| ruff check 不通过 | 停止，报告违规项 |
| 测试失败 | 停止，报告失败用例 |
| bandit 检出安全问题 | **阻塞**，必须修复 |
| 发现方案未覆盖的依赖 | 停止，描述依赖，建议回 O 阶段补充 |
| 发现潜在循环 import | 停止，先抽取 Protocol 解耦 |
