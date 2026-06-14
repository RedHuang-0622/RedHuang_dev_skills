---
name: devplan
description: 根据上下文输出详细的实现方案，遵循高内聚低耦合与设计模式，适配 dev-goal 工作流
---

# 方案设计专家 (Devplan)

## 目标

基于前置审查的结论，设计技术实现方案，包括数据结构、接口变更、算法选择和执行顺序。

## 上下文获取（按优先级尝试）

1. **dev-goal 模式**：工作目录 `docs/YYYY-MM-DD-{模块或功能名}/`
   - 从 `devgoal流程.md` 的 `## G: Goal` 获取目标拆解
   - 从 `devgoal流程.md` 的 G4 前置审查获取影响文件和依赖关系
2. **独立模式**：读取 `docs/front-review.md`（保留兼容）
3. **最小模式**：都不存在时，从当前代码库状态和用户需求反推

## 核心设计原则

### 高内聚低耦合

- **单一职责**：每个模块/包/类只负责一个功能领域
- **接口隔离**：模块间通过最小接口通信，不暴露内部实现
- **依赖倒置**：高层模块不依赖低层模块，两者都依赖抽象
- **最少知识**：一个对象应对其他对象有尽可能少的了解

### 23 种设计模式作为编码规范

在方案设计时，**必须**根据场景选择合适的设计模式。Go 项目优先使用：

| 优先级 | 模式 | 典型 Go 场景 |
|--------|------|------------|
| ⭐⭐⭐ | **Strategy** | 算法族可互换（支付方式、排序策略、压缩算法） |
| ⭐⭐⭐ | **Adapter** | 第三方 SDK 适配到内部接口 |
| ⭐⭐⭐ | **Factory Method** | 根据配置创建不同实现 |
| ⭐⭐ | **Decorator** | 中间件链、Wrapper 模式（HTTP middleware、日志包装） |
| ⭐⭐ | **Builder** | 构造复杂 struct（Functional Options 是 Go 惯用替代） |
| ⭐⭐ | **Chain of Responsibility** | 拦截器链、校验管道 |
| ⭐ | **Singleton** | ⚠️ 用 DI 替代，避免包级全局状态 |
| ⭐ | **Observer** | channel / event bus 通常是更 Go 的选择 |

> 完整 GoF 23 种模式参考：[Refactoring.Guru](https://refactoring.guru/design-patterns)。Go 项目特别关注 **组合优于继承**，结构型模式中 Bridge/Composite 通常不如接口 + 组合自然。行为型模式中 Template Method 在 Go 中通常用接口 + 组合替代继承。

### 🔴 循环依赖 — 零容忍

**循环依赖绝对禁止**。如检测到潜在的循环依赖：

1. **提取接口（Interface/Protocol）**：将被依赖方抽象为接口，放在独立的公共包/模块中
2. **依赖倒置**：让双方都依赖接口，而非互相依赖实现
3. **引入中介者**：通过中间层解耦两个模块
4. **重组包结构**：将有循环关系的类型提取到同一个包或第三个共享包

```
❌ 循环依赖:
  pkg/A ➜ pkg/B ➜ pkg/A

✅ 接口解耦:
  pkg/A ➜ pkg/contracts (IUserService interface)
  pkg/B ➜ pkg/contracts (IUserService interface)
  pkg/B 实现 IUserService
  pkg/A 使用 IUserService（不依赖 pkg/B 的实现）
```

### 依赖方向规则

```
高层策略 ➜ 低层细节  ❌ 不允许
高层策略 ➜ 抽象接口  ✅ 允许
低层细节 → 实现接口  ✅ 允许
所有模块 ➜ 领域模型/实体  ✅ 允许（单向）
```

## 🛡️ 工程约束（设计时必须遵守）

### 配置硬度等级

方案中涉及的任何可配置值，必须明确其硬度等级。**按硬度从高到低**：

| 等级 | 形式 | 适用场景 | 示例 |
|------|------|---------|------|
| 🔴 **硬编码常量** | `const` / `const` block | 数学恒量、协议常量、永不变的值 | `const MaxRetry = 3` |
| 🟠 **默认常量+覆盖** | `const defaultX` + `WithX()` option | 有公认默认值，少数场景需覆盖 | `const DefaultTimeout = 30s` |
| 🟡 **环境变量** | `os.Getenv` / `envconfig` | 部署环境差异（DB URL、密钥、环境名） | `DATABASE_URL`, `API_KEY` |
| 🟢 **YAML/JSON 配置** | `config.yaml` + struct unmarshal | 复杂结构配置、业务参数、特性开关 | `server.port`, `feature.enable_new_flow` |
| 🔵 **构造函数注入** | `func New(dep Dep) *Svc` | 运行时依赖、策略选择、外部服务 | `NewPaymentService(strategy)` |
| ⚪ **特性开关/动态** | 远程配置中心 | 无需重启的热更新参数 | `A/B test ratio` |

**禁止**：
- ❌ 硬编码密钥/密码/Token（必须 env 或密钥管理服务）
- ❌ 硬编码环境相关 URL（必须 env 或 config.yaml）
- ❌ 硬编码业务阈值且无覆盖机制（至少是 default const + option）

### 接口 vs 具体类型（设计决策树）

```
需要跨包依赖？ ──YES── 需要多种实现？ ──YES── ✅ 定义 interface
    │                           │
    NO                          NO
    │                           │
    是纯数据结构(DTO)？         未来可能需要 mock？ ──YES── ✅ 定义 interface
    │                           │
    YES                         NO
    │                           │
    ✅ 用 struct                同一包内单实现？ ──YES── ✅ 用 struct，不定义 interface
```

**原则**：接口属于使用方（consumer），不属于实现方（producer）。在调用方包中定义接口，实现方只需返回 struct。

```go
// ✅ 正确：接口在 order 包（使用方）
package order
type PaymentRepo interface {
    Pay(ctx context.Context, order *Order) error
}

// ❌ 错误：接口在 payment 包（实现方），order 反向依赖
package payment
type PaymentService interface { ... }  // 实现方不应定义接口
```

### 包设计：高内聚低耦合

| 原则 | 检查要点 |
|------|---------|
| **单一职责** | 一个包只做一件事。如果描述包需要"和"字 → 拆包 |
| **最小接口** | 接口只包含调用方实际使用的方法。3 个方法以上的接口 → 考虑拆分 |
| **依赖倒置** | 高层策略包不 import 低层实现包，双方都依赖接口 |
| **单向依赖** | 依赖图必须无环。util/ common/ base/ → 这些包不应依赖业务包 |
| **拒绝上帝包** | 一个包导出 >20 个公开符号 → 职责过多，考虑拆分 |

```go
// ❌ 上帝包
package utils  // 包含 DB helper、HTTP client、string util、date parser...

// ✅ 职责单一
package dbhelper    // 只做 DB 连接池和重试
package httputil   // 只做 HTTP 请求封装
package strutil     // 只做字符串处理
```

### 全局变量与单例禁令

| ❌ 禁止 | ✅ 替代 |
|--------|--------|
| `var db *sql.DB` (包级) | `func NewDB(cfg Config) *sql.DB` + DI |
| `var once sync.Once; once.Do(...)` | 在 `main()` 或 `NewApp()` 中显式初始化 |
| `func GetInstance() *Svc` (Singleton) | `func NewSvc(deps...) *Svc` + 调用方注入 |
| `func init()` 中复杂初始化 | `main()` 或显式的 `Initialize()` 方法 |
| 包级 `var config = loadConfig()` | `func LoadConfig(path string) Config` + 传参 |

**唯一例外**：`sync.Pool`、`regexp.MustCompile` 等标准库推荐包级变量的场景，且变量为不可变或无状态。

### nil vs 空值（设计决策）

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| "未提供"区别于"提供了空值" | `*string` 指针，nil = 未提供 | JSON `null` vs `""` 语义不同 |
| 一般字符串字段 | `string`，`""` 表示空/未提供 | 简单，避免指针解引用 |
| 函数返回值 | 返回零值 + error，不返回 nil | `return "", ErrNotFound` 而非 `return nil, nil` |
| Map 只读 | `nil map` — 读取返回零值 | 不需要初始化空 map |
| Map 读写 | 必须 `make()` 初始化 | nil map 写入会 panic |
| Slice 序列化 | `[]T{}` 而非 `nil` | `nil` slice → JSON `null`，`[]` → JSON `[]` |

### 野指针预防（设计层面）

方案中涉及指针的地方，明确以下约定：

```go
// ✅ 构造函数永远不返回 nil 指针 — 返回零值 struct + error
func NewSvc(dep Dep) (*Svc, error) {
    if dep == nil {
        return nil, errors.New("dep is nil")  // nil 指针 + error = 合法
    }
    return &Svc{dep: dep}, nil  // 永远返回有效指针
}

// ❌ 返回 nil 指针不返回 error — 调用方必崩
func NewSvc() *Svc {
    return nil  // 调用方不知情，必然 nil pointer deref
}
```

**设计清单**：
- [ ] 所有公开函数入参中是否包含可能为 nil 的指针？→ 文档注明 nil 行为
- [ ] 返回值是指针的函数，是否所有路径都保证非 nil 或返回 error？
- [ ] 是否有存 loop 变量指针的场景？→ 必须 copy
- [ ] interface 变量是否会为 nil？→ `if x == nil` 不等于 `x.(*T) == nil`

## 执行步骤

1. 读取上下文（devgoal流程.md 的 G 阶段 或 front-review.md）
2. 分析现有代码模式，保持风格一致
3. 识别适用的设计模式（从 23 种中选取）
4. 检查循环依赖，如有立即用接口解耦
5. 设计接口和数据结构，优先复用现有类型
6. 将方案拆解为可独立验证的小步骤
7. 生成 `docs/plan.md` 并询问用户确认

## 输出格式

````markdown
# 实现方案

## 设计目标
[功能目标、非功能性要求]

## 设计模式选择
| 模式 | 应用位置 | 选择理由 |
|------|---------|---------|
| Strategy | 支付模块 | 多种支付方式可互换 |
| Adapter | 第三方API | 适配外部接口到内部规范 |

## 耦合度分析
| 模块对 | 耦合方式 | 耦合度 | 备注 |
|-------|---------|-------|------|
| order→user | interface IUserRepo | 低 | 通过接口解耦 ✅ |
| order→product | 直接 import 实体 | 低 | 单向依赖 ✅ |

## 循环依赖检查
- [ ] 已检查所有新增依赖关系
- [ ] 确认无循环依赖
- [ ] 如有潜在循环已用接口替代（附方案）

## 架构设计
```go
// 核心接口/类型定义
type NewFeature interface {
    // ...
}
```

## 实现步骤

1. [步骤1]：[预计修改文件] [预计耗时] [涉及设计模式]
2. [步骤2]：[预计修改文件] [预计耗时] [涉及设计模式]
  ...

## 接口契约
```go
// 模块间通信接口，优先定义
type IModuleA interface {
    Method(ctx context.Context, input Input) (Result, error)
}
```

## 测试策略

- 单元测试覆盖点：[列出]
- 集成测试场景：[列出]
- 边界条件：[列出]
- 性能指标：[阈值]

## 回滚方案

[如修改失败如何恢复]

## 设计模式合规检查
- [ ] 每个类的职责是否单一
- [ ] 模块间是否通过接口通信
- [ ] 是否杜绝了循环依赖
- [ ] 是否遵循了最少知识原则
````

## 禁止行为（设计层面）

- ❌ **硬编码密钥/密码/Token/URL** 到设计方案中（必须标注为 env 或密钥服务）
- ❌ **接口定义在实现方包中**（接口属于使用方，如 `package payment` 定义 `type PaymentService interface`）
- ❌ **包级可变全局变量** 作为设计方案（必须用 DI 或显式初始化）
- ❌ **循环依赖**（方案设计阶段就必须消灭，不允许"后续解决"）
- ❌ **上帝包**（一个包 > 20 个公开符号、职责超过 2 个领域）
- ❌ **util/common 包 import 业务包** 的依赖关系出现在设计图中
- ❌ **返回 nil 指针不返回 error** 的函数签名设计（调用方无法防御）
- ❌ **init() 做复杂初始化**（必须显式 `New()` 或 `Initialize()`）
- ❌ 只给一种方案（轻量级除外，必须至少 2 种方案对比）

## 暂停点

询问用户："请确认 plan.md，确认后我将开始编码"

## 打断机制

- 用户拒绝方案 → 记录拒绝原因，返回修正
- 发现循环依赖无法解决 → 停止，列出问题，建议架构调整
