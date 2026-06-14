---
name: git-commit
description: 根据代码变更自动生成规范的 git commit message，适配 dev-goal 工作流
---

# Git 提交规范 (Git Commit)

## 目标

根据当前变更自动生成结构化 commit message，遵循约定式提交，与 dev-goal 子目标拆解对齐。

## 触发时机

在 dev-goal 工作流的 **A 阶段编码完成、测试通过后**调用。也可独立使用。

## 上下文获取

1. **dev-goal 模式**：读取工作目录下的文件
   - `devgoal流程.md` → G 阶段子目标拆解（commit 与子目标 1:1 对齐）
   - `code-changes.md` → 变更摘要
2. **独立模式**：从 `git diff --staged` 或 `git diff` 反推

## Commit Message 格式

```
<type>(<scope>): <subject>

<body>

Refs: <goal-id>
```

### type（变更性质）

| type | 适用场景 | 示例 |
|------|---------|------|
| `feat` | 新增功能、新增公开 API | `feat(payment): add Strategy-based payment dispatch` |
| `fix` | 修复 bug | `fix(order): prevent double-charge on timeout` |
| `refactor` | 重构，不改变外部行为 | `refactor(payment): extract if-else to Strategy pattern` |
| `perf` | 性能优化 | `perf(query): add index for order lookup` |
| `test` | 仅测试变更 | `test(payment): add race-condition coverage` |
| `docs` | 仅文档变更 | `docs(api): update payment flow diagram` |
| `chore` | 构建/工具/依赖 | `chore(deps): bump httpx to 0.27` |
| `revert` | 回滚 | `revert: rollback Strategy refactor` |

### scope（影响范围）

取**模块/包名**，小写，一个词。如 `payment`、`order`、`db`、`api`。

### subject（一句话摘要）

- 中文或英文，项目统一即可
- 祈使句（"修复重复扣款"而非"修复了重复扣款"）
- ≤ 50 字符
- 不以句号结尾

### body（变更详情）

用项目 `code-changes.md` 的子目标变更摘要，逐条列出：

```
- G1: 定义 PaymentStrategy Protocol
- G2: 实现 AlipayStrategy / WechatStrategy / BankcardStrategy
- G3: 重构 PaymentService 注入策略，消除 if-else 分支
- G4: 保持现有 API 不变，全部测试通过
```

### Refs（追溯）

关联 dev-goal 子目标编号：

```
Refs: G1, G2, G3, G4
```

---

## 执行步骤

### Step 1: 读取变更上下文

```
Read: docs/YYYY-MM-DD-{模块}/devgoal流程.md → G 阶段子目标表
Read: docs/YYYY-MM-DD-{模块}/code-changes.md → 变更摘要
```

### Step 2: 按子目标拆 commit

**原则**：一个子目标一个 commit。commit 与 G 阶段子目标 1:1 对齐。

```
子目标 G1: 定义接口        → commit 1: feat(payment): define PaymentStrategy Protocol
子目标 G2: 实现策略        → commit 2: feat(payment): implement Alipay/Wechat/Bankcard strategies
子目标 G3: 重构调用方      → commit 3: refactor(payment): inject Strategy, remove if-else
子目标 G4: 保持兼容        → commit 4: test(payment): verify existing API compatibility
```

**如果子目标之间有依赖**（后面的依赖前面的才能编译），可以合并为一个 commit，在 body 中逐条注明。

### Step 3: 确定 type

对照变更摘要中的"修改类型"列：

| 修改类型 | → type |
|---------|--------|
| 新增（新文件 / 新 API） | `feat` |
| 重构（行为不变） | `refactor` |
| 修复（行为修正） | `fix` |
| 仅测试 | `test` |

### Step 4: 生成并展示

输出完整的 commit message，让用户确认后执行 `git commit`。

**不直接提交**，只生成 message 文本，用户最后决定。

---

## 示例输出

```
git commit -m "refactor(payment): inject Strategy pattern, remove if-else dispatch

- G1: 定义 PaymentStrategy Protocol (protocols/payment.py)
- G2: 实现 AlipayStrategy / WechatStrategy / BankcardStrategy
- G3: 重构 PaymentService，策略通过 __init__ 注入
- G4: 保持 PaymentService 公开方法签名不变，全量测试通过

Refs: G1, G2, G3, G4"
```

---

## dev-goal 集成

在 `devgoal流程.md` 的 A 阶段执行记录中追加 commit 信息：

```markdown
### 执行记录
| 子目标 | 状态 | Commit | 偏离方案？ |
|-------|------|--------|----------|
| G1 | ✅ | `a1b2c3d feat(payment): define PaymentStrategy Protocol` | 无 |
| G2 | ✅ | `e4f5g6h feat(payment): implement payment strategies` | 无 |
| G3 | ✅ | `i7j8k9l refactor(payment): inject Strategy, remove if-else` | 无 |
| G4 | ✅ | `m0n1o2p test(payment): verify API compatibility` | 无 |
```

---

## 禁止行为

- ❌ **一个 commit 包含不相关的多个子目标**（违反 1:1 对齐）
- ❌ **commit message 写"改了点东西"/"fix"/"update"**（没有任何信息量）
- ❌ **type 与内容不符**（重构标 `feat`，修 bug 标 `refactor`）
- ❌ **不写 body**（涉及 >1 个文件的 commit 必须有 body 说明）
- ❌ **不写 Refs**（dev-goal 模式下必须追溯子目标）
- ❌ **跨子目标的回滚点合并为一个 commit**（深度级要求独立回滚，必须独立 commit）
- ❌ **不经用户确认直接 git commit**
