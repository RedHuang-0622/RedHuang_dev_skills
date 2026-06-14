---
name: dev_full_workflow
description: 执行完整代码变更工作流：front-review → devplan → code-impl → test-suite → finish-review
---

# 完整开发工作流 (Dev Full Workflow)

## 概述

执行从需求到交付的完整代码变更工作流，每个阶段需用户确认后才进入下一阶段。

```
front-review → devplan → code-impl → test-suite → finish-review
     ↓          ↓         ↓           ↓           ↓
  用户确认    用户确认   用户确认    用户确认     完成交付
```

## 触发方式

- 直接说：「按照完整工作流处理这个需求：XXX」
- 或使用 `/dev_full_workflow`

## 工作流阶段

### 阶段 1: 前置审查 (front-review)

**调用**：`/front-review`

**输入**：用户的功能需求或 bug 描述

**操作**：
1. 搜索并定位相关代码
2. 分析依赖和影响范围
3. 检查潜在循环依赖
4. 生成 `docs/YYYY-MM-DD-功能变更摘要-front-review-（负责人姓名）.md`

**确认点**：用户确认 front-review 报告后进入下一阶段

### 阶段 2: 方案设计 (devplan)

**调用**：`/devplan`

**前置**：`docs/front-review.md` 必须存在

**操作**：
1. 读取 front-review 报告
2. 从 23 种设计模式中选择合适的
3. 设计接口契约，杜绝循环依赖
4. 生成 `docs/YYYY-MM-DD-功能变更摘要-plan-（负责人姓名）.md`

**确认点**：用户确认 plan 后进入编码

### 阶段 3: 编码实现 (code-impl)

**调用**：`/code-impl`

**前置**：`docs/plan.md` 必须存在

**操作**：
1. 严格按 plan 实现
2. 接口先行，设计模式落地
3. 每步验证编译 + 测试
4. 同步更新测试文件
5. 生成 `docs/YYYY-MM-DD-功能变更摘要-code-changes-（负责人姓名）.md`

**确认点**：编码完成，用户确认后运行完整测试

### 阶段 4: 测试套件 (test-suite)

**调用**：`/test-suite`

**前置**：代码变更完成

**操作**：
1. 生成/运行单元测试
2. 生成/运行集成测试
3. 生成/运行边界测试
4. 生成/运行性能测试
5. 生成 `docs/YYYY-MM-DD-功能变更摘要-test-（负责人姓名）.md`

**确认点**：测试通过，用户确认后进入最终审查

### 阶段 5: 最终审查 (finish-review)

**调用**：`/finish-review`

**前置**：所有前置文档和代码变更

**操作**：
1. 五轴审查（正确性/可读性/架构/安全性/性能）
2. 设计模式合规检查
3. 循环依赖检查
4. 生成 `docs/YYYY-MM-DD-功能变更摘要-finish-review-（负责人姓名）.md`

**终止点**：输出最终合并建议

## 工作流输出文件清单

完成后 `docs/` 目录下新增：

```
docs/YYYY-MM-DD-功能变更摘要-front-review-（负责人姓名）.md
docs/YYYY-MM-DD-功能变更摘要-plan-（负责人姓名）.md
docs/YYYY-MM-DD-功能变更摘要-code-changes-（负责人姓名）.md
docs/YYYY-MM-DD-功能变更摘要-test-（负责人姓名）.md
docs/YYYY-MM-DD-功能变更摘要-finish-review-（负责人姓名）.md
```

## 各阶段打断机制

| 阶段 | 触发条件 | 处理方式 |
|------|---------|---------|
| front-review | 用户拒绝方案 | 记录拒绝原因，返回修正 |
| devplan | 用户拒绝方案 | 记录拒绝原因，返回修正 |
| devplan | 发现无法解决的循环依赖 | 停止，建议架构调整 |
| code-impl | 编译错误 | 停止，报告错误位置 |
| code-impl | 测试失败 | 停止，报告失败用例 |
| code-impl | 发现潜在循环依赖 | 停止，重构为接口解耦 |
| test-suite | 覆盖率低于 80% | 警告，用户决定是否继续 |
| finish-review | 发现严重问题 | 停止，列出问题，等待处理 |

## 禁止行为

- ❌ 跳过任何阶段
- ❌ 在用户未确认的情况下进入下一阶段
- ❌ 批量修改超过 5 个不相关的文件
- ❌ 不经验证直接提交
- ❌ 引入循环依赖
- ❌ 跳过接口抽象直接依赖具体实现
