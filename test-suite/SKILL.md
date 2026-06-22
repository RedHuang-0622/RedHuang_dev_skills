---
name: test-suite
description: 执行 Go/Python 分层测试套件 — 单元/集成/边界/性能/并发/模糊/内存/静态/安全/泄漏，汇总报告
---

# 测试套件专家 (Test-Suite)

## 目标

为本次变更执行分层测试，汇总结果。语言自动检测。

## 上下文获取

优先读 `devgoal流程.md`（G 阶段质量标准 + code-changes.md），回退读 `plan.md` 测试策略。

---

## 测试维度（10 维清单）

| # | 维度 | 轻量 | 标准 | 深度 |
|---|------|:---:|:---:|:---:|
| 1 | 单元测试 | ✅ | ✅ | ✅ |
| 2 | 集成测试 | — | ✅ 关键路径 | ✅ 全路径 |
| 3 | 边界测试 | ✅ 基础 | ✅ | ✅ + property-based |
| 4 | 性能测试 | — | ✅ benchmark 关键路径 | + 基线对比 + 火焰图 |
| 5 | 并发测试 | — | ✅ 基本竞态 | + soak + chaos |
| 6 | 模糊测试 | — | — | ✅ |
| 7 | 内存测试 | — | — | ✅ |
| 8 | 静态分析 | ✅ lint | + 类型检查 strict | + 安全 + 依赖审计 |
| 9 | 安全测试 | — | ✅ 自动扫描 | + 手动用例 |
| 10 | 泄漏检测 | — | — | ✅ FD/连接池/task |

**覆盖率阈值**：轻量 ≥80%，标准 ≥85%，深度 ≥90%（核心 ≥95%）

---

## 执行命令（按深度分层）

### 轻量

**Go:**
```bash
go vet ./... && go build ./... && go test ./... -cover -coverprofile=coverage.out
```

**Python:**
```bash
ruff check src/ tests/ && mypy src/ --strict && pytest tests/ -v --tb=short --cov=src --cov-report=term --cov-fail-under=80
```

### 标准（含轻量 + 以下）

**Go:**
```bash
go test ./... -race -count=3 -coverprofile=coverage.out
go test ./... -bench=. -benchmem -benchtime=1s
```

**Python:**
```bash
pytest tests/ -v -m "integration" --tb=short
pytest tests/ -v -m "benchmark" --benchmark-only
bandit -c pyproject.toml src/
pip-audit
```

### 深度（含标准 + 以下）

**Go:**
```bash
go test -fuzz=. -fuzztime=30s ./pkg/xxx/...
go test -race -count=10 -timeout=5m ./pkg/xxx/...       # 并发压力
go build -gcflags="-m" ./... 2>&1 | grep "escapes"      # 逃逸分析
```

**Python:**
```bash
pytest tests/ -v -m "fuzz" --hypothesis-max-examples=5000
pytest tests/ -v -m "stress" --duration=30
python -m memray run -o out.bin -m pytest tests/ -m "memory"
lint-imports                                              # 循环 import
```

---

## 失败恢复

| 失败 | 严重程度 | 处理 |
|------|:---:|------|
| 单元/集成测试失败 | 🚨 | 修复 → 重跑 |
| 覆盖率不达标 | ⚠️ | 标注未覆盖区，用户决定 |
| 并发 data race / corruption | 🚨 | **阻塞**，修复后重跑全量 race |
| 性能退化 >20% | ⚠️ | 标注退化项，用户决定 |
| fuzz/hypothesis 发现缺陷 | 🚨 | 修复 → 重跑 |
| bandit HIGH / govulncheck CVE | 🚨 | **阻塞**，必须修复 |
| 内存/资源泄漏 | 🚨 | 定位 → 修复 → 重跑 |

> ⚠️ 涉及 goroutine / channel / asyncio / threading 的变更，并发测试**不可跳过**。

---

## CI 生成模式

当用户请求"写 CI"时，将上述测试维度映射为 GitHub Actions workflow。

### 分层映射

| 测试层 | CI Job 名 | 阻塞 | 关键动作 |
|--------|-----------|:---:|----------|
| 轻量 | `lightweight` | ✅ | `go vet` + `go build` + `go test -cover -covermode=atomic`，覆盖阈值 80% |
| 标准 | `standard` | ✅ race | `-race -count=3`，多 Go 版本矩阵（`strategy.matrix.go-version`），benchmark 信息性 |
| 深度 | `deep` | — | fuzz 30s（自动发现 targets: `go test -list 'Fuzz.*'`），extended stress，逃逸分析 |
| 静态 | `static-analysis` | ✅ vuln | `govulncheck`（BLOCKING），`staticcheck`，`gofmt`，`go mod tidy` |
| 汇总 | `summary` | — | `needs: [以上全部]`，生成 `test-report.md` artifact（30 天 retention） |

### Go 项目 CI 模板骨架

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
  workflow_dispatch:  # 手动触发入口

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true   # 新 push 自动取消旧 run

permissions:
  contents: read
  actions: read
```

### Job 依赖链

```
push/PR → lightweight ──┬── standard ─── deep
                         ├── static-analysis
                         └── summary (if: always())
```

- `standard` 依赖 `lightweight`：不过 vet/build 就不浪费资源跑 race
- `static-analysis` 依赖 `lightweight`：相同原因
- `summary` 用 `if: always()` 确保前面失败也能汇总

### 关键决策点

| 决策 | 做法 | 原因 |
|------|------|------|
| **Race 阻塞** | `-race -count=3`，失败必须修 | 并发库 data race = 未定义行为，不可放过 |
| **多版本矩阵** | Go 1.23 + 1.24 | Go 泛型在不同版本的行为差异（类型别名、逃逸分析） |
| **fail-fast: false** | 矩阵内不互相取消 | 一个版本挂不影响另一个版本的结果收集 |
| **覆盖率模式** | `-covermode=atomic` | 并发代码必须用 atomic 模式，count 模式会有竞态漏报 |
| **Fuzz 自动发现** | `go test -list 'Fuzz.*'` → 循环跑 | 不硬编码 target 列表，新增 fuzz test 自动纳入 |
| **Benchmark 非阻塞** | `continue-on-error: true` | benchmark 受 CI runner 噪声影响大，信息性参考不阻塞 |
| **逃逸分析** | `-gcflags="-m"` 收集 `escapes to heap` | 连接池热路径不该有意外堆分配 |
| **Vulncheck 阻塞** | `govulncheck` 发现 CVE → 必须修 | 第三方依赖漏洞可达远程利用 |
| **gofmt 阻塞** | `gofmt -l .` 有输出则失败 | 格式不一致污染 git blame |
| **go mod tidy 阻塞** | `go mod tidy` 后 `git diff --exit-code` | go.sum 不一致导致可重现构建失败 |

### 时长保护

| 层 | timeout-minutes | 理由 |
|----|:---:|------|
| lightweight | 5 | vet/build/test 正常 ≤2m |
| standard | 10 | race ×3 次 + bench，约 6-8m |
| deep | 30 | fuzz 30s × N targets + stress |
| static-analysis | 5 | govulncheck 下载 DB 可能慢 |

### Artifact 策略

- **coverage.out**: 每个 job 上传一份，带 Go 版本标签，7 天 retention
- **benchmark 文本**: 同上，用于性能退化对比
- **test-report.md**: summary job 生成，30 天 retention，用作历史基线
- **逃逸分析**: 辅助调试堆分配，7 天

### README Badge

```markdown
[![CI](https://github.com/{owner}/{repo}/actions/workflows/ci.yml/badge.svg)](https://github.com/{owner}/{repo}/actions/workflows/ci.yml)
```

### 并发库专项检查清单

当被测项目涉及 `goroutine` / `channel` / `sync` / `atomic` / `lock-free` 时，额外确保：

1. `-race` 至少 `-count=3`（单次可能漏检）
2. `-covermode=atomic`（不用 count）
3. `golangci-lint` 启用 `copylocks`、`gocritic:rangeValCopy`
4. stress test 跑 `-race -count=3`（CI 核数少可能暴露本地不出的 race）
5. fuzz 覆盖 channel/queue 的并发入口（如 `Enqueue`/`Dequeue` 交错）

---

## 输出格式

写入工作目录 `test-report.md`：

```markdown
# 测试报告

## 概览
| 总数 | 通过 | 失败 | 跳过 | 耗时 | 覆盖率 |
|------|------|------|------|------|--------|

## 各维度
| 维度 | 结果 | 关键指标 |
|------|:---:|---------|

## 失败详情（如有）
| 用例 | 错误 | 位置 |

## 性能对比（如有）
| 操作 | 基线 | 本次 | 变化 |

## 综合判断
- [ ] ✅ 通过
- [ ] ⚠️ 有条件通过 — {条件}
- [ ] 🚨 不通过 — {阻塞项}
```

---

## 禁止行为 (Top 5)

1. ❌ **跳过并发代码的 race/竞态测试**（data race = 未定义行为，必须阻塞）
2. ❌ **测试依赖外部真实服务**（必须 mock 或用 test container）
3. ❌ **测试间有隐式顺序依赖**（每个测试独立可运行）
4. ❌ **bandit HIGH / race 检出后标记"已知"不修复**
5. ❌ **硬编码 sleep 等待**（用 timeout / wait_for）
