---
name: test-suite
description: 自动生成并执行 Go 测试套件 — 单元/集成/边界/性能/竞态/模糊/并发/内存/静态分析/泄漏检测，汇总测试报告
---

# 测试套件专家 (Test-Suite)

## 目标

为本次变更生成完整的多维测试套件，执行测试，汇总结果。

## 前置条件

以下任一存在即可：
- `docs/YYYY-MM-DD-{模块或功能名}/devgoal流程.md`（被 dev-goal 调用时）
- `docs/plan.md`（独立使用）

如果两者都不存在，从当前代码变更反推测试范围。

## 上下文获取

1. 优先读取工作目录下的 `devgoal流程.md`
   - G 阶段：目标拆解 + 成功标准（含质量阈值）
   - A 阶段：`code-changes.md` 的编码变更摘要
2. 回退读取 `docs/plan.md` 的测试策略章节
3. 再回退：用 `git diff` 或 Grep 定位变更文件，反推测试范围

---

## 测试维度（10 维）

### 1. 单元测试

**框架**: `testing` + `testify`（`go.mod` 已有则用，否则纯 `testing`）
**模式**: AAA（Arrange-Act-Assert），Table-Driven
**覆盖率目标**: 核心逻辑 ≥90%，整体 ≥80%

```go
func TestXxx(t *testing.T) {
    tests := []struct {
        name    string
        input   Input
        want    Output
        wantErr bool
    }{
        {"正常情况", validInput, expectedOutput, false},
        {"边界零值", zeroInput, zeroOutput, false},
        {"错误输入", badInput, Output{}, true},
    }
    for _, tt := range tests {
        t.Run(tt.name, func(t *testing.T) {
            got, err := DoXxx(tt.input)
            if (err != nil) != tt.wantErr {
                t.Fatalf("DoXxx() error = %v, wantErr %v", err, tt.wantErr)
            }
            if got != tt.want {
                t.Errorf("DoXxx() = %v, want %v", got, tt.want)
            }
        })
    }
}
```

**执行**:
```bash
go test ./pkg/xxx/... -v -count=1 -coverprofile=coverage.out
go tool cover -func=coverage.out | tail -1  # 总覆盖率
```

---

### 2. 集成测试

**原则**:
- 模块间通过接口协作的链路验证
- 优先真实依赖（内存版实现），外部服务用 mock
- 测试数据隔离（每个测试用例独立的 context/db 实例）
- 验证接口契约是否被正确实现

```go
func TestOrderCreation_Integration(t *testing.T) {
    // Arrange: 真实的内存仓储
    userRepo := memstore.NewUserRepo()
    orderSvc := order.NewService(userRepo)

    // Act
    err := orderSvc.Create(ctx, newOrder)

    // Assert
    assert.NoError(t, err)
    assert.Equal(t, StatusPending, newOrder.Status)
}
```

**执行**:
```bash
go test ./... -v -count=1 -tags=integration
```

---

### 3. 边界测试

| 边界类型 | 测试用例 |
|---------|---------|
| nil / 空指针 | `nil` 参数 → 返回明确错误或默认值 |
| 零值 | `0`, `""`, `false` → 行为明确 |
| 极端数值 | `math.MaxInt`, `math.MinInt`, `-1`, `0` |
| 空集合 | `nil slice`, `empty map`, `len=0` → 返回空集合不 panic |
| 超大输入 | 10,000+ 元素，极大字符串 |
| 溢出 | 加法/乘法溢出，`uint` 下溢 |

---

### 4. 性能测试（Benchmark）

```go
func BenchmarkXxx(b *testing.B) {
    data := setup(b)     // b.StopTimer / b.StartTimer 排除准备开销
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        DoXxx(data)
    }
}

// 并行版本
func BenchmarkXxx_Parallel(b *testing.B) {
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            DoXxx(input)
        }
    })
}
```

**执行**:
```bash
go test ./pkg/xxx/... -bench=. -benchmem -benchtime=1s -count=3
```

**benchmem 输出解读**: 关注 `allocs/op`（每次操作分配次数）和 `B/op`（每次操作分配字节数）。目标：热路径 0 allocs。

---

### 5. 竞态测试（Race Detection）🆕

**检测内容**: 并发读写同一内存地址未加锁、channel 竞态、WaitGroup 竞态。

```go
func TestXxx_Race(t *testing.T) {
    var (
        wg    sync.WaitGroup
        count int
        mu    sync.Mutex
    )
    n := 100

    // 并发写 — 必须有锁保护
    for i := 0; i < n; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            mu.Lock()
            count++
            mu.Unlock()
        }()
    }

    // 并发读 — 无锁读取（如读时不加锁 = race）
    for i := 0; i < n; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            mu.Lock()
            _ = count
            mu.Unlock()
        }()
    }
    wg.Wait()
    // 如果有未加锁的访问，-race 会报告
}
```

**执行**:
```bash
go test ./pkg/xxx/... -race -count=3
# 多跑几次：竞态不一定每次都触发，-count=3+ 提高检出率
```

**关键要求**：
- 所有涉及 `go func()` / goroutine 的新增代码，**必须**有对应的 `TestXxx_Race`
- 共享状态（全局变量、包级变量、struct 字段被多 goroutine 访问）的场景，**必须**跑 `-race`
- CI 中 `-race` 应作为独立 job（竞态检测会拖慢 5-10x，不适合与单元测试混跑）

---

### 6. 模糊测试（Fuzz）🆕

**Go 1.18+ 原生支持**。用于发现随机输入触发的 panic、死循环、逻辑错误。

```go
func FuzzXxx(f *testing.F) {
    // 种子语料
    f.Add("valid-seed-1")
    f.Add("")
    f.Add("\x00\xff")

    f.Fuzz(func(t *testing.T, input string) {
        // Fuzz 目标：不能 panic，不能死循环，不能 OOM
        result, err := DoXxx(input)
        if err != nil {
            t.Skip() // 预期内的错误，跳过
        }
        // 验证不变量
        if result.Field < 0 {
            t.Errorf("unexpected negative: %d", result.Field)
        }
    })
}
```

**执行**:
```bash
# 短时间（CI）
go test ./pkg/xxx/... -fuzz=FuzzXxx -fuzztime=10s

# 长时间（本地/夜间）
go test ./pkg/xxx/... -fuzz=. -fuzztime=5m
```

**适用场景**:
- 解析器（JSON/YAML/Proto/自定义格式）
- 输入校验函数
- 编解码逻辑
- 字符串/byte 处理
- 任何接收外部输入的函数

---

### 7. 并发压力测试 🆕

```go
func TestXxx_Concurrent(t *testing.T) {
    var (
        n      = 1000
        ctx    = context.Background()
        errs   = make(chan error, n)
    )

    for i := 0; i < n; i++ {
        go func(id int) {
            errs <- DoXxx(ctx, id)
        }(i)
    }

    for i := 0; i < n; i++ {
        if err := <-errs; err != nil {
            t.Errorf("goroutine %d: %v", i, err)
        }
    }
}

// 超时防护
func TestXxx_Timeout(t *testing.T) {
    ctx, cancel := context.WithTimeout(context.Background(), 100*time.Millisecond)
    defer cancel()

    done := make(chan struct{})
    go func() {
        DoXxx(ctx)
        close(done)
    }()

    select {
    case <-done:
    case <-ctx.Done():
        t.Fatal("operation timed out")
    }
}
```

**执行**:
```bash
go test ./pkg/xxx/... -run=Concurrent -race -count=3 -timeout=30s
```

---

### 8. 内存与逃逸分析 🆕

**逃逸分析**: 检测变量是否不必要地逃逸到堆上。

```bash
go build -gcflags="-m -m" ./pkg/xxx/... 2>&1 | grep "escapes to heap"
```

判断标准：
- 热路径变量逃逸到堆 → 性能隐患
- 小对象逃逸 → 检查是否可以传值而非传指针
- interface{} / any 装箱 → 隐式逃逸

**内存分析**:
```bash
go test ./pkg/xxx/... -bench=. -benchmem -memprofile=mem.out
go tool pprof -top mem.out
```

---

### 9. 静态分析 🆕

**内置（必须）**:
```bash
go vet ./...          # 标准 vet 检查
go vet -shadow ./...  # 变量遮蔽检查（Go 1.14+ 默认开启）
```

**可选（如已安装）**:
```bash
staticcheck ./...          # 更深入的静态分析
golangci-lint run ./...    # 全量 lint
go vet -copylocks ./...    # 检查 mutex 拷贝
```

**go vet 重点检查项**:
| 检查项 | 说明 |
|--------|------|
| `-atomic` | sync/atomic 误用 |
| `-copylocks` | 含 mutex 的 struct 被值拷贝 |
| `-loopclosure` | 循环变量被 goroutine 捕获 |
| `-lostcancel` | context cancel 未调用 |
| `-nilfunc` | nil 函数调用 |
| `-stdmethods` | 错误实现标准接口方法签名 |

---

### 10. 资源泄漏检测 🆕

**Goroutine 泄漏**:
```go
func TestXxx_NoGoroutineLeak(t *testing.T) {
    // 使用 uber/goleak（如项目已引入）
    // defer goleak.VerifyNone(t)

    // 或不依赖第三方库的手动检测
    initial := runtime.NumGoroutine()
    DoXxx(context.Background())
    runtime.Gosched() // 让出 CPU，给 goroutine 退出的机会
    time.Sleep(10 * time.Millisecond)

    if final := runtime.NumGoroutine(); final > initial+1 {
        t.Errorf("goroutine leak: %d -> %d", initial, final)
    }
}
```

**Channel 泄漏**: 确保每个创建的 channel 都有对应的 close 路径。

**资源清理检查清单**:
- [ ] `defer resp.Body.Close()` — HTTP 响应体
- [ ] `defer file.Close()` — 文件句柄
- [ ] `defer cancel()` — context
- [ ] `defer conn.Close()` — 网络连接
- [ ] channel close — 生产者 close channel

---

## 执行策略（按场景分层）

### 快速验证（每次代码变更后）
```bash
go vet ./...
go build ./...
go test ./pkg/xxx/... -v -count=1 -coverprofile=coverage.out
```

### 标准套件（提交前 / PR）
```bash
# 1. 静态分析
go vet ./...

# 2. 单元测试 + 覆盖率
go test ./... -v -count=1 -coverprofile=coverage.out

# 3. 竞态检测
go test ./... -race -count=3

# 4. 性能回归
go test ./... -bench=. -benchmem -benchtime=1s -count=3

# 5. 模糊测试（短时）
go test ./... -fuzz=. -fuzztime=10s
```

### 全面套件（合并前 / 发版前 / dev-goal 深度级）
```bash
# 全部标准套件 +
go build -gcflags="-m -m" ./... 2>&1 | grep "escapes to heap"  # 逃逸分析
go test ./... -race -count=10                                    # 加大竞态检出
go test ./... -fuzz=. -fuzztime=5m                               # 长时模糊
go test ./... -run=Concurrent -race -count=5 -timeout=60s       # 并发压力

# 可选工具
staticcheck ./...        # 如已安装
golangci-lint run ./...  # 如已安装
```

---

## 输出格式

```markdown
## A2: 测试报告

### 执行环境
- Go 版本: [go version 输出]
- 执行时间: [timestamp]
- 测试范围: [涉及的包路径]

### 结果汇总

| 测试维度 | 用例数 | 通过 | 失败 | 跳过 | 备注 |
|---------|-------|-----|-----|-----|------|
| 单元测试 | N | N | 0 | 0 | |
| 集成测试 | N | N | 0 | 0 | |
| 边界测试 | N | N | 0 | 0 | |
| 性能测试 | N | — | 0 | 0 | 见基准报告 |
| 竞态测试 | N | N | 0 | 0 | -race, count=3 |
| 模糊测试 | — | — | 0 | 0 | fuzztime=10s |
| 并发压力 | N | N | 0 | 0 | 1000 goroutines |
| 静态分析 | — | ✅ | 0 | — | go vet 通过 |

### 覆盖率

| 覆盖类型 | 覆盖率 | 目标 | 状态 |
|---------|-------|-----|-----|
| 语句 | XX% | ≥80% | ✅/⚠️ |
| 分支 | XX% | ≥80% | ✅/⚠️ |
| 函数 | XX% | ≥90% | ✅/⚠️ |

### 性能基线

| Benchmark | 耗时 (ns/op) | 内存 (B/op) | 分配 (allocs/op) | 对比基线 | 状态 |
|-----------|-------------|------------|-----------------|---------|-----|
| BenchmarkXxx | X | X | X | 首次/±X% | ✅/⚠️ |

### 竞态检测

| 测试 | Data Race | 位置 | 修复 |
|------|----------|------|------|
| TestXxx_Race | 无 / 发现 | [文件:行] | [修复说明] |

### 逃逸分析

| 变量 | 位置 | 逃逸？ | 影响 |
|------|------|--------|------|
| x | file.go:L45 | heap | 热路径，建议优化 |

### 未覆盖说明
- [无法覆盖的路径及原因]

### 资源泄漏检查
- [ ] Goroutine 泄漏: 通过 / 发现 N 个
- [ ] Channel 泄漏: 通过 / 发现 N 个
- [ ] 资源句柄: 通过 / 发现 N 处未关闭
```

---

## 输出目标

根据调用上下文选择：

**被 dev-goal 调用时**：写入工作目录 `docs/YYYY-MM-DD-{模块或功能名}/test-report.md`，并在同目录的 `devgoal流程.md` 的 `## A: Action` 章节追加测试摘要 + 文件引用 `详见 [test-report.md](./test-report.md)`。

**独立调用时**：生成 `docs/YYYY-MM-DD-功能变更摘要-test-{负责人姓名}.md`（保留兼容）。

---

## 暂停点

询问用户："测试完成。请确认测试报告后进入下一阶段。"

## 退出码与判定

| 情况 | 判定 | 处理 |
|------|------|------|
| 全部通过 | ✅ 通过 | 继续 |
| 覆盖率 < 80% | ⚠️ 警告 | 标注未覆盖区域，用户决定是否继续 |
| Benchmark 退化 > 20% | ⚠️ 警告 | 标注退化项，用户决定 |
| Data Race 发现 | 🚨 阻塞 | **必须修复**，不允许带 race 继续 |
| go vet 失败 | 🚨 阻塞 | **必须修复** |
| 单元测试失败 | 🚨 阻塞 | **必须修复** |
| Fuzz 发现 panic | 🚨 阻塞 | **必须修复** |

> 关键原则：竞态条件（data race）是**未定义行为**，Go 官方明确其为 bug，绝不允许"后续修复"。

---

## 禁止行为

- ❌ 跳过竞态检测（任何涉及并发的新增/修改代码）
- ❌ 模糊测试发现 panic 后只记录不修复
- ❌ Benchmark 不设 `-benchmem`（不知道是否 0 alloc）
- ❌ 覆盖率不达标不标注未覆盖区域只报数字
- ❌ 资源泄漏检测只跑不修
- ❌ 在未确认 test.md 的情况下直接进入最终审查
- ❌ 依赖外部服务但未提供 mock/内存版实现就声称"集成测试通过"
