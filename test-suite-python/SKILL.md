---
name: test-suite-python
description: 自动生成并执行 Python 测试套件 — 单元/集成/边界/性能/并发/模糊/内存/静态分析/安全/泄漏检测，汇总测试报告
---

# 测试套件专家 — Python (Test-Suite Python)

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

**框架**: `pytest` + `pytest-asyncio`（异步代码必装）
**模式**: Arrange-Act-Assert，`@pytest.mark.parametrize`（Table-Driven）
**覆盖率目标**: 核心逻辑 ≥90%，整体 ≥80%

```python
import pytest
from decimal import Decimal

class TestPaymentService:
    @pytest.mark.parametrize(
        "amount,method,expected",
        [
            (Decimal("100"), "alipay", True),      # 正常场景
            (Decimal("0.01"), "alipay", True),      # 最小金额
            (Decimal("0"), "alipay", False),         # 零值边界
            (Decimal("-1"), "alipay", False),        # 负数边界
            (Decimal("100"), "unknown", False),      # 未知支付方式
        ],
        ids=["正常", "最小金额", "零值", "负数", "未知方式"],
    )
    async def test_pay(self, payment_service, amount, method, expected):
        result = await payment_service.pay(amount, method)
        assert result.success == expected
```

### 2. 集成测试

**框架**: `pytest` + `pytest-docker`（需要真实依赖时）/ `responses` / `aioresponses`
**范围**: 模块间合约、数据库读写、外部 API mock、消息队列

```python
@pytest.fixture
async def payment_service(test_db):
    """集成测试 fixture：注入真实 DB + mock 外部 API"""
    client = httpx.AsyncClient()
    service = PaymentService(db=test_db, client=client)
    yield service
    await client.aclose()

@pytest.mark.integration
async def test_full_payment_flow(payment_service, sample_order):
    # Arrange
    order = await sample_order()
    # Act
    result = await payment_service.process(order)
    # Assert
    assert result.status == "paid"
    # 验证 DB 写入
    saved = await payment_service.db.orders.get(order.id)
    assert saved.status == "paid"
```

### 3. 边界测试

**关注**: 类型边界、容器边界、业务边界

```python
class TestBoundary:
    def test_empty_list_input(self):
        assert process([]) == []  # 空输入

    def test_single_element(self):
        assert len(process([1])) == 1  # 单元素

    @pytest.mark.parametrize("n", [0, 1, 999, 1000])
    def test_page_size_bounds(self, n):
        assert 0 <= len(fetch_page(size=n)) <= n

    def test_none_vs_empty_string(self):
        """None = 不更新, '' = 清空 的语义区分"""
        req1 = UpdateRequest(name=None)
        req2 = UpdateRequest(name="")
        assert req1.should_skip_name()
        assert not req2.should_skip_name()

    def test_max_recursion_depth(self):
        with pytest.raises(RecursionError):
            infinite_recursion(1)
```

### 4. 性能测试

**框架**: `pytest-benchmark`
**重点**: 关键路径无退化

```python
def test_payment_benchmark(benchmark):
    service = create_service()
    order = sample_order()

    result = benchmark(service.process, order)
    assert result.status == "paid"

# 或手动对比基准
def test_no_n_plus_1_queries():
    with assert_queries_count(1):  # 自定义 context manager
        service.get_orders_with_items(batch_size=10)
```

### 5. 并发测试（async 代码必须）

**框架**: `pytest-asyncio` + `asyncio.gather`
**重点**: 竞态条件、死锁、数据一致性

```python
import asyncio

@pytest.mark.asyncio
async def test_concurrent_payments_not_over_charge(payment_service):
    """并发支付不应重复扣款"""
    initial_balance = await payment_service.get_balance(user_id=1)

    # 并发发起 10 次支付，总额超过余额
    tasks = [
        payment_service.pay(user_id=1, amount=Decimal("10"))
        for _ in range(10)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 成功的次数不应超过余额允许
    success_count = sum(1 for r in results if not isinstance(r, Exception))
    final_balance = await payment_service.get_balance(user_id=1)

    assert success_count <= initial_balance // 10
    assert final_balance >= 0

@pytest.mark.asyncio
async def test_no_deadlock():
    """两个资源互相等待不应死锁"""
    async with asyncio.timeout(5):  # 5 秒超时 → 防止死锁挂起
        await transfer_deadlock_prone(a=1, b=2)
```

### 6. 模糊测试

**框架**: `hypothesis`
**重点**: 随机输入不崩溃

```python
from hypothesis import given, strategies as st

@given(
    amount=st.decimals(min_value=0, max_value=1_000_000),
    method=st.sampled_from(["alipay", "wechat", "bankcard"]),
)
def test_pay_never_crashes(amount, method):
    service = create_service()
    # 任何合法输入都不应崩溃
    result = service.pay(amount=str(amount), method=method)
    assert result.status in ("paid", "failed")
```

### 7. 内存测试

**框架**: `tracemalloc`（内置）/ `memray`（深度分析）
**重点**: 无内存泄漏、无意外大对象

```python
import tracemalloc

def test_no_memory_leak():
    service = create_service()
    tracemalloc.start()

    snapshot1 = tracemalloc.take_snapshot()
    for _ in range(1000):
        service.process(sample_order())
    snapshot2 = tracemalloc.take_snapshot()

    stats = snapshot2.compare_to(snapshot1, "lineno")
    # 持续增长 > 1MB → 泄漏嫌疑
    for stat in stats[:5]:
        assert stat.size_diff < 1024 * 1024, f"Leak at {stat.traceback}"

def test_large_result_pagination():
    """大批量结果应分页返回，不应全部加载到内存"""
    import sys
    result = fetch_large_dataset()
    size = sys.getsizeof(result)
    assert size < 50 * 1024 * 1024, f"Result too large: {size // 1024 // 1024}MB"
```

### 8. 静态分析

| 工具 | 检查内容 | 命令 |
|------|---------|------|
| `mypy` | 类型正确性 | `mypy src/ --strict` |
| `ruff` | Lint + 格式 | `ruff check src/ && ruff format --check src/` |
| `bandit` | 安全漏洞 | `bandit -c pyproject.toml src/` |
| `pip-audit` | 依赖漏洞 | `pip-audit` |
| `import-linter` | 循环 import + 层次违规 | `lint-imports` |

**必须全部零告警**（已配置的允许列表除外）。

### 9. 安全测试

**框架**: `bandit` + 手动测试用例
**重点**: SQL 注入、XSS、权限绕过、敏感数据泄露

```python
class TestSecurity:
    def test_sql_injection_prevention(self):
        malicious = "1; DROP TABLE users; --"
        result = get_user(user_id=malicious)
        assert result is None  # 不应执行注入

    def test_no_sensitive_data_in_logs(self, caplog):
        process_payment(user_id=1, card_number="1234-5678-9012-3456")
        assert "1234-5678" not in caplog.text  # 卡号不应出现在日志

    def test_no_secret_in_error_response(self):
        with pytest.raises(ValueError) as exc:
            connect_to_db(password="wrong")
        assert "password" not in str(exc.value).lower()

    def test_authorization_bypass_attempt(self):
        # 普通用户不应访问管理员端点
        response = client.get("/admin/users", headers={"Authorization": f"Bearer {user_token}"})
        assert response.status_code == 403
```

### 10. 资源泄漏检测

**框架**: `pytest-leaks` / 手动 fixture
**重点**: 文件句柄、网络连接、async task 未取消

```python
class TestResourceLeaks:
    def test_file_handle_leak(self, tmp_path):
        import psutil
        proc = psutil.Process()
        initial_fds = proc.num_fds()

        for _ in range(100):
            with leaky_file_reader(tmp_path / "test.txt"):
                pass

        final_fds = proc.num_fds()
        assert final_fds - initial_fds < 5, f"FD leak: {final_fds - initial_fds}"

    @pytest.mark.asyncio
    async def test_async_task_cleanup(self, event_loop):
        initial_tasks = len(asyncio.all_tasks(event_loop))

        async with create_worker() as worker:
            await worker.process(sample_job())

        # 给事件循环一点时间清理
        await asyncio.sleep(0.1)
        final_tasks = len(asyncio.all_tasks(event_loop))
        assert final_tasks <= initial_tasks, f"Task leak: {final_tasks - initial_tasks}"

    def test_connection_pool_exhaustion(self):
        """连接池不应耗尽"""
        import httpx
        async with httpx.AsyncClient(limits=httpx.Limits(max_connections=10)) as client:
            tasks = [client.get("http://localhost:8000/health") for _ in range(50)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            errors = [r for r in results if isinstance(r, Exception)]
            assert len(errors) == 0
```

---

## 测试深度（对应 dev-goal 规模分层）

| 维度 | 轻量 | 标准 | 深度 |
|------|------|------|------|
| 单元测试 | ✅ | ✅ | ✅ |
| 集成测试 | — | ✅（关键路径） | ✅（全路径） |
| 边界测试 | ✅（基础） | ✅ | ✅ + property-based |
| 性能测试 | — | `pytest-benchmark` 关键路径 | + 对比基线 + 火焰图 |
| 并发测试 | — | `asyncio.gather` 基本竞态 | + 长时间 soak + chaos 注入 |
| 模糊测试 | — | — | `hypothesis` 全量 |
| 内存测试 | — | — | `tracemalloc` + `memray` |
| 静态分析 | `ruff` | `ruff` + `mypy --strict` | + `bandit` + `import-linter` |
| 安全测试 | — | `bandit` 扫描 | + 手动安全用例 |
| 泄漏检测 | — | — | FD + 连接池 + task |
| 覆盖率 | ≥80% | ≥85% | ≥90%（核心 ≥95%） |

---

## 执行流程

```bash
# === 轻量级 ===
# 1. 静态检查
ruff check src/ tests/

# 2. 类型检查
mypy src/ --strict

# 3. 单元测试 + 覆盖率
pytest tests/ -v --tb=short --cov=src --cov-report=term --cov-fail-under=80

# === 标准级（含以上全部 + 以下） ===
# 4. 集成测试
pytest tests/ -v -m "integration" --tb=short

# 5. 性能基准测试
pytest tests/ -v -m "benchmark" --benchmark-only

# 6. 安全扫描
bandit -c pyproject.toml src/

# 7. 依赖漏洞
pip-audit

# === 深度级（含以上全部 + 以下） ===
# 8. 模糊测试（长时间运行）
pytest tests/ -v -m "fuzz" --hypothesis-max-examples=5000

# 9. 并发压力测试
pytest tests/ -v -m "stress" --duration=30

# 10. 内存分析
python -m memray run -o output.bin -m pytest tests/ -m "memory"
python -m memray flamegraph output.bin

# 11. 循环 import 检查
lint-imports
```

---

## 输出格式

```markdown
# 测试报告

## 测试概览
| 项目 | 数值 |
|------|------|
| 总用例数 | 45 |
| 通过 | 45 |
| 失败 | 0 |
| 跳过 | 0 |
| 耗时 | 12.3s |

## 各维度结果

### 1. 单元测试 ✅
| 模块 | 用例数 | 通过 | 覆盖率 |
|------|-------|------|--------|
| services/payment.py | 15 | 15 | 92% |
| adapters/alipay.py | 8 | 8 | 88% |

### 2. 集成测试 ✅
| 场景 | 结果 | 耗时 |
|------|------|------|
| 完整支付流程 | ✅ | 0.8s |
| 退款流程 | ✅ | 0.6s |
| 支付失败回滚 | ✅ | 0.5s |

### 3. 边界测试 ✅
| 边界 | 输入 | 预期 | 结果 |
|------|------|------|------|
| 最小金额 | 0.01 | 成功 | ✅ |
| 零值金额 | 0 | 拒绝 | ✅ |
| 负数金额 | -1 | 拒绝 | ✅ |

### 4. 性能测试 ✅
| 操作 | 基准（上次） | 本次 | 变化 |
|------|-----------|------|------|
| pay() | 12ms | 11.8ms | -1.7% ✅ |
| refund() | 8ms | 9.2ms | +15% ⚠️ |

### 5. 并发测试 ✅
| 场景 | 并发数 | 结果 |
|------|-------|------|
| 并发支付 | 50 | 零 data corruption ✅ |
| 余额竞态 | 30 | 无超额扣款 ✅ |
| 死锁检测 | — | 零死锁 ✅ |

### 6. 模糊测试 ✅
| 目标 | 用例数 | 发现缺陷 |
|------|-------|---------|
| pay() | 5000 | 0 |

### 7. 内存测试 ✅
| 操作 | 分配量 | 判断 |
|------|-------|------|
| pay() | 2.3KB | 正常 ✅ |

### 8. 静态分析 ✅
| 工具 | 结果 |
|------|------|
| mypy --strict | ✅ 零错误 |
| ruff check | ✅ 零告警 |
| bandit | ✅ 零告警 |
| pip-audit | ✅ 无已知漏洞 |

### 9. 安全测试 ✅
| 检查项 | 结果 |
|--------|------|
| SQL 注入 | ✅ |
| XSS | ✅ |
| 密钥泄露 | ✅ |

### 10. 资源泄漏检测 ✅
| 资源 | Before | After | 判断 |
|------|--------|-------|------|
| 文件句柄 | 12 | 13 | ✅ |
| Async tasks | 3 | 3 | ✅ |

## 综合判断
- [x] ✅ 通过 — 所有维度达标
- [ ] ⚠️ 有条件通过 — {具体条件和理由}
- [ ] 🚨 不通过 — {阻塞项}
```

---

## 失败恢复路径

| 失败场景 | 严重程度 | 处理 |
|---------|---------|------|
| 单元测试失败 | 🚨 阻塞 | 修复代码 → 重跑 |
| 覆盖率不达标 | ⚠️ 警告 | 标注未覆盖区域，用户决定 |
| 集成测试失败 | 🚨 阻塞 | 检查环境 → 修复 → 重跑 |
| 性能退化 >20% | ⚠️ 警告 | 标注退化项，用户决定 |
| 并发 data corruption | 🚨 阻塞 | **必须修复** → 重跑全量并发 |
| hypothesis 发现缺陷 | 🚨 阻塞 | 修复 → 重跑 fuzz |
| bandit 检出 HIGH | 🚨 阻塞 | **必须修复** |
| pip-audit 有 CVE | 🚨 阻塞 | 升级有漏洞依赖 |
| 内存泄漏 | 🚨 阻塞 | 定位泄漏点 → 修复 → 重跑 |
| 文件句柄泄漏 | 🚨 阻塞 | 检查 context manager 使用 |

> ⚠️ 涉及 `asyncio` / `threading` / `multiprocessing` 的代码，并发测试**不可跳过**。

---

## 禁止行为

- ❌ **跳过涉及并发的代码的并发测试**（必须跑 `asyncio.gather` 竞态测试）
- ❌ **裸 except 出现在测试代码中**（会吞掉测试失败）
- ❌ **测试依赖外部真实服务**（必须 mock 或用 test container）
- ❌ **测试间有隐式顺序依赖**（每个测试必须独立可运行）
- ❌ **硬编码 sleep 等待**（用 `asyncio.wait_for` 或 `pytest-timeout`）
- ❌ **mypy strict 告警跳过**（必须修复或显式 `# type: ignore[rule]` + 注释理由）
- ❌ **bandit HIGH 告警标记为"已知"不修复**
- ❌ **覆盖率阈值手动下调以"通过"**（下降必须解释原因）
- ❌ **`async def test_*` 不用 `@pytest.mark.asyncio`**
