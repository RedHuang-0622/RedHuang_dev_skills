---
name: devplan
description: 根据上下文输出详细实现方案（Go/Python），遵循高内聚低耦合与设计模式，适配 dev-goal 工作流
---

# 方案设计专家 (Devplan)

## 目标

基于前置审查结论，设计技术方案：数据结构、接口、算法、步骤。至少 2 种方案，定性对比。

## 设计哲学（优先级从高到低）

1. **接口抽象 > 具体实现**：调用方定义接口，实现方满足接口。Go: `interface` 在调用方包；Python: `Protocol` 在调用方模块
2. **通用化 > 定制化**：提取共性逻辑，差异通过参数/策略注入。拒绝一次性专用代码
3. **工厂注入 > 单例**：所有依赖显式传入，杜绝全局状态
4. **组合 > 继承**：Go 用 struct 嵌入，Python 继承 ≤2 层
5. **高内聚低耦合**：模块单一职责，最少接口通信，零循环依赖

## 设计模式 → 语言映射

| 优先级 | 模式 | Go 惯用实现 | Python 惯用实现 | 场景 |
|--------|------|-----------|---------------|------|
| ⭐⭐⭐ | Strategy | interface + DI | Protocol + DI | 算法族可互换 |
| ⭐⭐⭐ | Adapter | struct 实现 interface | 包装类实现 Protocol | 第三方 SDK 适配 |
| ⭐⭐⭐ | Factory Method | `func NewXxx(cfg) (Xxx, error)` | `@classmethod` / `match/case` | 按配置创建实现 |
| ⭐⭐ | Decorator | 函数包装 + 中间件 | `@` 语法糖 / `wraps` | 日志/重试/鉴权 |
| ⭐⭐ | Builder | Functional Options | fluent + kwargs + dataclass | 复杂对象构造 |
| ⭐⭐ | Chain of Resp. | `http.Handler` 链 | ASGI middleware / callable 链 | 请求管道 |
| ⭐ | Template Method | 接口 + 组合 替代继承 | 基类 + 抽象方法（组合优先） | 算法骨架固定 |
| ❌ | Singleton | 禁止 — DI 替代 | 禁止 — module 即单例 | — |

> 完整 GoF 23 参考: [Refactoring.Guru](https://refactoring.guru/design-patterns)。Python 额外优先使用 Context Manager。

## 🛡️ 工程约束

### 配置硬度（设计时标注）

| 等级 | 适用 | 示例 |
|------|------|------|
| 🔴 常量 | 永不变的值 | `const MaxRetry = 3` / `MAX_RETRY: Final = 3` |
| 🟠 默认+覆盖 | 公认默认，少数覆盖 | `const defaultTimeout` + `WithTimeout()` |
| 🟡 环境变量 | 部署差异 | `DATABASE_URL` |
| 🟢 配置文件 | 复杂业务配置 | YAML / TOML |
| 🔵 构造注入 | 运行时依赖 | `func New(dep)` / `def __init__(self, dep)` |
| ⚪ 特性开关 | 热更新参数 | 远程配置中心 |

### 接口设计决策树

```
跨模块依赖 + 需要多实现/mock  → 定义 interface/Protocol（在调用方）
同一包/模块内单实现           → 用具体 struct/class
纯数据(DTO/dataclass)        → 不抽象，直接用
```

### 循环依赖 → 零容忍

```
Go:   pkg/A → pkg/B → pkg/A  ❌  → 提取 interface 到 pkg/contracts
Python: a.py → b.py → a.py   ❌  → 提取 Protocol 到 protocols/
```

### 异常体系（Python 专属）

方案必须明确异常层次。模块级基类 + ≤3 层子类。禁止 `raise Exception("...")`。

### async vs sync（Python 专属）

```
IO 在请求路径上 → async def + asyncio
IO 不在请求路径 → 同步 + 后台线程池
纯计算           → 同步
同步函数内调 asyncio.run()  → ❌ 绝对禁止
```

---

## 输出格式

写入工作目录 `plan.md`：

````markdown
# 实现方案

## 设计目标
## 设计模式选择
| 模式 | 语言实现 | 应用位置 | 理由 |

## 方案对比（≥2 种）
| 维度 | 方案 A | 方案 B |
|------|--------|--------|
| 耦合度 | 低 — ... | 低 — ... |
| 内聚性 | 高 — ... | 中 — ... |
| 可测试性 | ... | ... |
| 实现成本 | ... | ... |
| 改动面 | ... | ... |
| 可回滚性 | ... | ... |

## 推荐：方案 X
**理由** / **最大风险**

## 循环依赖检查
## 核心接口/Protocol 定义
```go / python
```
## 实现步骤
| # | 步骤 | 文件 | 设计模式 |
## 测试策略
## 回滚方案
````

---

## 禁止行为 (Top 5)

1. ❌ **接口定义在实现方**（interface/Protocol 属于使用方）
2. ❌ **循环依赖出现在设计图中**（设计阶段就必须消灭）
3. ❌ **模块级可变状态作为方案**（必须 DI）
4. ❌ **硬编码密钥/密码/URL 到方案中**
5. ❌ **只给一种方案**（轻量除外，必须 ≥2 种定性对比）

## 暂停点

询问用户："请确认 plan.md，确认后进入编码"

## 打断机制

- 用户拒绝 → 记录原因，返回修正
- 循环依赖无法解 → 停止，建议架构调整
