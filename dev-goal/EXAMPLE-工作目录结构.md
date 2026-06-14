# 工作目录示例: docs/2026-06-14-支付策略重构/

```
docs/2026-06-14-支付策略重构/
  devgoal流程.md          ← 下方内容（dev-goal 主流程 G+O+A+L）
  code-changes.md         ← [code-impl 输出]
  test-report.md          ← [test-suite 输出]
```

---

# Workflow: 支付模块策略模式重构
## 元信息
- 日期: 2026-06-14
- 规模: 标准
- 需求: 将支付模块的 if-else 分支重构为 Strategy 模式，支持支付宝/微信/银行卡三种支付方式可插拔

## G: Goal ───────────────────────────────────

### 目标拆解
**主目标**：支付模块从硬编码分支重构为 Strategy 策略模式

| # | 子目标 | 验收标准（可测量） | 优先级 |
|---|-------|------------------|-------|
| G1 | 定义 PaymentStrategy 接口 | 接口包含 Pay/Refund/Name 三个方法，编译通过 | P0 |
| G2 | 实现支付宝/微信/银行卡三种策略 | 每种策略通过单元测试，覆盖率 ≥ 90% | P0 |
| G3 | 重构 PaymentService 使用策略模式 | 原有 if-else 分支消除，注入策略即可切换 | P0 |
| G4 | 确保现有调用方不受影响 | 所有现有测试通过，无 API 变更 | P0 |

### 成功标准
- [ ] 功能：三种支付方式可插拔切换，行为不变
- [ ] 质量：
  - 单元测试通过，覆盖率 ≥ 80%
  - go vet 零告警
  - 竞态检测零 data race（涉及并发必跑）
  - 无 goroutine/channel/文件句柄泄漏
- [ ] 性能：关键路径无退化，benchmem 无异常分配
- [ ] 兼容：PaymentService 公开方法签名不变

### 非目标（明确不做）
- [不做的X] 新增第四种支付方式 — 原因：后续按需添加，本次只做重构
- [不做的Y] 改造订单模块 — 原因：订单模块通过 PaymentService 调用，接口不变即可

### 前置审查
| 文件 | 修改类型 | 关键位置 | 说明 |
|------|---------|---------|------|
| service/payment.go | 重构 | L45-L132 | 消除 if-else，注入策略 |
| service/payment_test.go | 修改 | L12-L89 | 适配策略模式测试 |
| strategy/alipay.go | 新增 | — | 支付宝策略实现 |
| strategy/wechat.go | 新增 | — | 微信策略实现 |
| strategy/bankcard.go | 新增 | — | 银行卡策略实现 |
| strategy/strategy.go | 新增 | — | PaymentStrategy 接口定义 |

**依赖关系**：
- 上游（谁依赖这些文件）：order/service.go → service/payment.go
- 下游（这些文件依赖谁）：strategy/* → 支付宝SDK / 微信SDK / 银行网关

**循环依赖检查**：✅ 无循环 — strategy 接口与实现分离，service 只依赖接口

### 风险预判
| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 支付宝SDK初始化在策略构建中遗漏 | 中 | 支付宝支付不可用 | 策略工厂统一管理依赖注入 |
| 接口方法不兼容现有调用 | 低 | 编译失败 | 接口先行定义，以现有调用方为基准 |

---

## O: Options ────────────────────────────────

### 历史经验参考
> 搜索范围: memory/ + docs/*/devgoal流程.md

| 来源 | 相关经验 | 对本次的启示 |
|------|---------|------------|
| — | 未找到相关历史经验 | 首次探索 — 本次 L 阶段将为此场景沉淀第一份经验 |

### 方案 A: 经典 Strategy — 接口 + 独立实现文件

**核心思路**：定义 PaymentStrategy 接口，每种支付方式一个 struct 实现，通过 PaymentService 的 SetStrategy 方法注入。

**设计模式**：Strategy（行为型）

**变更范围**：
- 新增 `strategy/` 包（4 个文件）
- 重构 `service/payment.go`（消除 if-else，约 80 行改动）
- `service/payment_test.go`（适配新结构）

**伪代码/接口草图**：
```go
// strategy/strategy.go
type PaymentStrategy interface {
    Pay(ctx context.Context, order *Order) (*PayResult, error)
    Refund(ctx context.Context, order *Order) (*RefundResult, error)
    Name() string
}

// service/payment.go
type PaymentService struct {
    strategies map[string]PaymentStrategy  // 注册表
}
func (s *PaymentService) Pay(ctx context.Context, order *Order, method string) (*PayResult, error) {
    st, ok := s.strategies[method]
    if !ok {
        return nil, ErrUnsupportedMethod
    }
    return st.Pay(ctx, order)
}
```

### 方案 B: 函数式 — 高阶函数代替接口

**核心思路**：不用接口，支付方式定义为 `func(ctx, order) (*PayResult, error)` 类型，通过 map 注册。

**设计模式**：无经典模式（函数式风格）

**变更范围**：类似方案 A，但无需 interface 定义，代码更少（约 50 行改动）

### 方案对比

| 维度 | 方案 A（Strategy 接口） | 方案 B（函数式） |
|------|----------------------|-----------------|
| **耦合度** | 低 — service 只依赖接口 | 低 — service 只依赖函数签名 |
| **内聚性** | 高 — 每种支付方式独立 struct，可持有自己的依赖 | 中 — 函数闭包持有状态，不够显式 |
| **可测试性** | 容易 — 可 mock 接口 | 一般 — mock 函数不如 mock 接口方便 |
| **实现成本** | 中 — 需要定义接口 + 3 个 struct | 低 — 无需接口，直接注册函数 |
| **改动面** | 新增 strategy 包，改动 payment.go | 改动 payment.go，不新增包 |
| **可回滚性** | 容易 — 删除 strategy 包，还原 payment.go | 容易 — 还原一个文件 |
| **团队适配** | 高 — Go 标准 Strategy 模式，团队熟悉 | 中 — 函数式在 Go 中不如接口普遍 |

### 风险对比

| 风险项 | 方案 A | 方案 B |
|--------|--------|--------|
| 循环依赖 | 无 | 无 |
| 破坏现有 API | 否（PaymentService 公开方法签名不变） | 否 |
| 性能影响 | 接口调用有微小 overhead（纳秒级，可忽略） | 函数调用无 overhead |
| 未知因素 | 无 | 函数闭包难以做依赖注入，未来扩展需重构 |

### 推荐：方案 A（Strategy 接口模式）

**推荐理由**：虽然方案 B 代码量更少，但方案 A 的 struct 可显式持有依赖（SDK 客户端、配置），可测试性更强，符合团队现有模式。长期来看扩展新支付方式只需新增一个 struct 实现接口，无需改动 service。

**最大风险**：接口方法设计上可能遗漏未来支付方式需要的参数 — 缓解：定义 context-heavy 的方法签名，通过 context 传递扩展参数。

**备选**：如果实现中发现接口过于僵化（3 种以上支付方式方法签名不统一），切换到方案 B。

---

## A: Action ─────────────────────────────────

### A1: 编码变更

> 详见 [code-changes.md](./code-changes.md)

**摘要**：
- 新增 `strategy/` 包（4 个文件）— 接口定义 + 三种支付策略实现（Strategy 模式）
- 重构 `service/payment.go` — 消除 if-else 分支，改为策略注册表注入
- 修改 `service/payment_test.go` — 适配策略模式测试
- API 无变更，现有调用方不受影响
- 循环依赖检查：✅ 无循环

### A1.5: Commit

按子目标 1:1 拆 commit：

| Commit | Type | Message |
|--------|------|---------|
| `a1b2c3d` | `feat(strategy)` | define PaymentStrategy interface |
| `e4f5g6h` | `feat(strategy)` | implement Alipay/Wechat/Bankcard strategies |
| `i7j8k9l` | `refactor(payment)` | inject Strategy, remove if-else dispatch |
| `m0n1o2p` | `test(payment)` | verify existing API compatibility |

Refs: G1, G2, G3, G4

### A2: 测试

> 详见 [test-report.md](./test-report.md)

**摘要**：
- 单元 15 | 集成 3 | 边界 6 | 性能 3 | 竞态 2 — 全部通过
- 覆盖率：语句 92% / 分支 88% / 函数 95%
- 竞态检测：✅ go test -race -count=3 零 data race
- go vet：✅ 零告警

### 执行记录
| 子目标 | 状态 | 关键变更 | 偏离方案？ |
|-------|------|---------|----------|
| G1 | ✅ | commit: a1b2c3d | 无 |
| G2 | ✅ | commit: e4f5g6h | 无 |
| G3 | ✅ | commit: i7j8k9l | 无 |
| G4 | ✅ | commit: m0n1o2p | 无 |

---

## L: Learning ───────────────────────────────

### 目标复核

| 子目标 | 验收标准 | 实际结果 | 达成？ | 偏差 |
|-------|---------|---------|-------|------|
| G1 | 接口编译通过 | ✅ 通过 | ✅ | 无 |
| G2 | 三种策略测试通过，覆盖率 ≥ 90% | ✅ 通过，92% | ✅ | 无 |
| G3 | if-else 分支消除 | ✅ 消除 | ✅ | 无 |
| G4 | 现有测试全部通过 | ✅ 通过 | ✅ | 无 |

### 方案实际效果 vs 预期

| 维度 | O 阶段预期 | 实际 | 差异分析 |
|------|----------|-----|---------|
| 实现成本 | 中（约 80 行改动） | 实际 95 行 | BankCard 策略需要额外的银行网关适配，多 15 行 |
| 改动面 | 6 个文件 | 6 个文件 | 一致 |
| 风险命中 | 无 | 支付宝 SDK 在测试环境初始化失败 | 通过依赖注入在测试中注入 mock 解决 |

### 经验存储

> 已写入 memory/strategy-pattern-payment.md
> MEMORY.md 索引已更新

关键经验：
- Strategy 接口方法使用 context 作为第一参数，为未来扩展（链路追踪、超时控制）留空间
- 策略注册表用 map[string]Strategy 而非 slice，O(1) 查找且支持运行时注册
- 测试中支付宝/微信 SDK 需要用 interface 再包一层（Adapter），否则集成测试无法 mock

### 改进建议
- **流程**：O1 阶段应要求写出关键接口的完整签名，而不只是草图 — 本次 Pay() 方法的 RefundResult 类型设计时不够细致
- **工具**：自动生成策略模式脚手架（接口 → struct 骨架）可节省 15 分钟
- **架构**：strategy 包的 SDK 依赖应考虑统一 Adapter 层，当前每个策略各自依赖不同 SDK
