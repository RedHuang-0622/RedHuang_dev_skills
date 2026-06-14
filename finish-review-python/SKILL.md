---
name: finish-review-python
description: 完成 Python 代码变更后的全面审查，输出最终 review 文档，五轴检查（含 Python 专项）
---

# 最终审查专家 — Python (Finish-Review Python)

## 目标

对所有 Python 代码变更进行最后的全面审查，输出结构化的 review 报告。

## 上下文获取（按优先级尝试）

1. **dev-goal 模式**：工作目录 `docs/YYYY-MM-DD-{模块或功能名}/`
   - 从 `devgoal流程.md` 的 G 阶段获取目标与前置审查
   - 从 `devgoal流程.md` 的 O 阶段获取选定方案
   - 从 `code-changes.md` 获取编码变更
   - 从 `test-report.md` 获取测试结果
2. **独立模式**：需存在 `docs/front-review.md` + `docs/plan.md` + `docs/test.md`
3. **最小模式**：仅需实际代码变更，从 git diff 反推

## 审查维度（五轴 + Python 专项）

### 1. 正确性 ✅

- [ ] 功能是否符合 plan.md 预期？
- [ ] 边界情况是否都在测试中覆盖？
- [ ] 异常处理是否完善且具体（无裸 except）？
- [ ] Protocol/ABC 是否被正确实现？
- [ ] 类型标注是否准确（mypy strict 通过）？

### 2. 可读性 📖

- [ ] 命名是否符合 PEP 8？（`snake_case` 变量/函数，`PascalCase` 类，`UPPER_CASE` 常量）
- [ ] 函数是否过长（>50行需要拆分）？
- [ ] 类是否过大（>250行需要拆分）？
- [ ] docstring 是否为 Google / NumPy / Sphinx 风格之一且一致？
- [ ] 魔法数字是否已提取为命名常量？
- [ ] f-string 是否一致使用（而非 `%` 或 `.format()`）？

### 3. 架构 🏗️

- [ ] 是否遵循 Protocol/ABC 解耦？
- [ ] 有无循环 import？
- [ ] 组合是否优先于继承（继承链 ≤2）？
- [ ] 模块职责是否单一（一个模块 ≤20 公开符号）？
- [ ] `utils/common` 是否零业务依赖？
- [ ] 通用化程度：是否有可抽取为通用组件的一次性代码？

### 4. 安全性 🔒

- [ ] 输入是否经过验证（pydantic / marshmallow）？
- [ ] 有无硬编码密钥/密码/Token？
- [ ] SQL 注入风险？（参数化查询）
- [ ] 命令注入风险？（`subprocess` 的 `shell=True`）
- [ ] 敏感数据是否在日志中脱敏？
- [ ] bandit 扫描是否通过？

### 5. 性能 ⚡

- [ ] 有无 N+1 查询？
- [ ] 循环内是否有不必要的 IO/计算？
- [ ] 大结果集是否分页？
- [ ] async IO 路径是否被同步阻塞破坏？
- [ ] 有无不必要的深拷贝 / 大对象创建？

### 6. Python 专项 🔍

- [ ] 无可变默认参数（`def f(x=[])`)
- [ ] 无模块级可变状态（`_cache = {}`）
- [ ] `is None` 而非 `== None`
- [ ] `is` 不用于比较字面量（`x is 5` → `x == 5`）
- [ ] 无 `from module import *`
- [ ] 无 `except: pass`
- [ ] `__init__` 无 IO/网络调用
- [ ] 无同步函数内调用 `asyncio.run()`
- [ ] Context Manager 用于资源管理（非 `try-finally`）
- [ ] `async def` 函数命名是否清晰（非 `async` 的不加 `async_` 前缀）

## 输出格式

```markdown
# 最终代码审查报告（Python）

## 变更概览
- 提交数：[x]
- 修改文件数：[x]
- 新增代码行：[+x]
- 删除代码行：[-x]
- 涉及设计模式：[列出]
- Python 版本：[3.11 / 3.12]

## 审查结论
| 维度 | 状态 | 评分 | 备注 |
|-----|------|-----|-----|
| 正确性 | ✅/⚠️/🚨 | A/B/C | |
| 可读性 | ✅/⚠️/🚨 | A/B/C | |
| 架构 | ✅/⚠️/🚨 | A/B/C | |
| 安全性 | ✅/⚠️/🚨 | A/B/C | |
| 性能 | ✅/⚠️/🚨 | A/B/C | |
| Python 专项 | ✅/⚠️/🚨 | A/B/C | |

## 类型检查
```
mypy src/ --strict
```
- [ ] mypy strict 零错误

## 设计模式合规
| 模式 | 文件 | Python 惯用实现 | 合规状态 |
|------|-----|---------------|---------|
| Strategy | payment.py | Protocol + DI | ✅ |
| Adapter | alipay_adapter.py | 包装类实现 Protocol | ✅ |

## 循环 import 检查
```
import-linter 输出或手动分析
```
- [ ] 确认无循环 import
- [ ] 所有模块间通过 Protocol 通信

## Protocol 抽象审核
| Protocol | 实现方 | 使用方 | 耦合度 |
|---------|-------|-------|-------|
| PaymentRepo | adapters/alipay.py | services/order.py | 低 ✅ |

## 异常体系审核
| 模块 | 是否有自定义异常 | 是否层次合理 | 是否被调用方捕获 |
|------|----------------|------------|----------------|
| payment | ✅ PaymentError | ✅ 3 层 | ✅ |

## 发现的问题

### 🚨 严重问题（0 个）
_无_

### ⚠️ 警告（N 个）
1. `services/payment.py:L45` - 函数 `process()` 51 行，超过 50 行阈值
   - 建议：提取 `_validate_order()` 和 `_build_result()` 方法

### 💡 建议（N 个）
1. `adapters/alipay.py:L12` - `Any` 类型可用 `TypedDict` 精确化
2. `tests/unit/test_payment.py:L89` - 可增加 `hypothesis` 属性测试补充边界覆盖

## ✅ 亮点
- [亮点1]：[描述]
- [亮点2]：[描述]

## Python 专项检查清单
- [ ] 无可变默认参数
- [ ] 无模块级可变状态
- [ ] `is None` 正确使用
- [ ] 无裸 except
- [ ] 无 `__init__` IO
- [ ] Context Manager 覆盖所有资源
- [ ] 无 `asyncio.run()` 嵌套

## 对比前置审查的差异
| 原计划（front-review） | 实际实现 | 差异原因 |
|----------------------|---------|---------|
| 修改 A 文件 | 新增 B 文件 | 重构发现更优解 |

## 最终判断
- [ ] ✅ 通过，可合并
- [ ] ⚠️ 有条件通过（需处理警告）
- [ ] 🚨 不通过，需修改
```

## 终止点

输出最终判断和合并建议。

## 打断机制

- 发现严重问题（安全漏洞、数据丢失风险）→ 立即停止，列出问题，等待处理
- 发现循环 import → 停止，要求先重构
- bandit 检出 HIGH → 停止
- mypy strict 不通过 → 警告，用户决定
- 评分低于 B → 警告，用户决定是否接受
