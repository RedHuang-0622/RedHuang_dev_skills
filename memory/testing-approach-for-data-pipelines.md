---
name: testing-approach-for-data-pipelines
description: 数据处理流水线的分层测试策略 — 从单元到安全穿透，7 项新颖测试方法
metadata:
  type: project
  tags: [testing, data-pipeline, python, quality, security-testing]
---

## 场景

对"通用资产数据处理系统"（Pipes & Filters 架构，16 个 Filter + 3 个 Wrapper）编写测试套件。系统特点是：
- 每个 Filter 是 `(PipelineContext) → PipelineContext` 纯函数
- Wrapper 通过装饰器模式注入横切关注点
- 存在 SecurityWrapper（RBAC + intern 限制）、LifecycleWrapper（TTL 策略）
- 测试需要覆盖正常路径、异常路径、安全穿透、组合爆炸

## 关键经验

- **Filter 纯函数签名使测试零 mock**：只需构造一个 `PipelineContext(frozen dataclass)` 并填入 `data` 或 `entries`，即可测试任何 Filter。不需要 mock 数据库、文件系统或上游 Filter。
- **Wrapper 组合测试发现的 bug 最致命**：SecurityWrapper 的 `_check_permission` 对非 admin 角色永远返回 False——这个 bug 在单个 Wrapper 的单元测试中就被发现和修复了，但如果没测到，整个系统对 intern 和 analyst 角色就是"完全不可用"的。
- **Python 3.11 兼容性陷阱**：`object.__replace__()` 是 3.12+ 的功能，3.11 需要用 `dataclasses.replace()`。26 处代码全部需要修复——这个 bug 只有在实际运行 Python 3.11 时才会暴露，静态分析工具检测不到（因为类型检查器认为 `object` 确实有这个属性）。
- **314 个测试 1.97 秒跑完**——因为不需要启动服务、不需要 Docker、不需要数据库。纯函数架构的快反馈循环是产品级质量的基石。

## 踩坑

- **测试中 Filter 名称必须与 `role_permissions.json` 的 `allowed_operations` 匹配**：用 `MockFilter(name="test_filter")` 做 intern 测试会导致 PermissionError，因为 `test_filter` 不在允许列表中。必须用 `"read"` 或 `"clean"` 等在真实配置中存在的名称。
- **"read" Filter 被 SecurityWrapper 豁免脱敏**：在测试数据脱敏时不能使用 `name="read"` 的 MockFilter，因为 SecurityWrapper 明确跳过了 `"read"`, `"chunk"`, `"index_lookup"` 的脱敏逻辑。
- **IMOO 校验器对 `str(int(val))` 的假设**：`int("ABCDEFG")` 会崩溃。测试数据如果有非数字字符串，插件必须 try/except 保护。
- **SizeChunker 无限循环在测试中表现为 MemoryError**：这是因为 chunk size + overlap 的边界条件没处理好。修复前要先理解算法逻辑，不能简单调大 timeout。

## 7 项新颖测试方法

### 1. PipelineContext 不变性模糊测试
1000 次随机链式 `with_data()` / `with_entries()` / `with_artifact()` / `with_metric()` 调用后，原始 Context 必须完全不变。验证了 `frozen=True` + `dataclasses.replace()` 的正确性。

### 2. 属性簇继承攻击测试
验证循环继承/超深继承（>3 层）/字段覆盖冲突都在框架层面被安全处理，不会导致无限递归或静默数据损坏。

### 3. Intern 安全网穿透测试
逐个尝试绕过 intern 的每个限制：
- 行数限制（1000 行）→ 验证无法绕过
- 敏感字段脱敏 → 验证 `[RESTRICTED-X chars]` 已应用
- 强制确认 → 验证 `needs_confirmation: True`
- 公开字段 → 验证未被误脱敏

### 4. 生命周期策略冲突测试
模拟"intern 角色试图覆盖策略为 permanent"→ 验证框架强制 `supervised_short_term`（15天），intern 无法自行延长数据生命周期。

### 5. Wrapper 顺序交换性测试
3 个 Wrapper 的 6 种排列下 Pipeline 均成功执行。验证了 Wrapper 之间不存在隐式顺序依赖。

### 6. 快照回滚一致性测试
对每个 Filter 执行 `apply()` → `rollback()` → 验证回到 `apply` 之前的状态。10 次循环稳定性验证。

### 7. Pipeline 中断恢复测试
Pipeline 在中途失败后，可以从任意 Filter 位置恢复执行，跳过的 Filter 不会被重复执行。

## 可复用做法

- **10 维测试清单 × 3 级深度**：单元/集成/边界/性能/并发/模糊/内存/静态/安全/泄漏，每维都有轻量/标准/深度的明确验收标准
- **Mock 注入模式**：通过 Protocol 定义接口（`LLMBackend`, `ChunkStrategy`, `PluginProtocol`），测试用 Mock 实现注入，生产用真实实现
- **故障注入测试**：`MockFilter(should_fail=True)` 验证 `Pipeline.stop_on_error` 和 `resume()` 行为
- **临时文件系统**：`tempfile.TemporaryDirectory` 用于快照/完结的 IO 测试，测试完自动清理

## 结论

✅ 推荐 — 纯函数架构使测试成本极低（314 个测试 1.97 秒），但需要额外关注 Wrapper 组合和角色权限的集成测试，这些是单元测试覆盖不到的"缝隙"。
