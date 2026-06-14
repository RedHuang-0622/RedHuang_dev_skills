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
