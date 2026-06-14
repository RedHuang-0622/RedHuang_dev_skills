---
name: code-impl
description: 根据方案执行编码（Go/Python），接口先行，增量验证，自动生成 commit，遵循设计模式与工程约束
---

# 编码实现专家 (Code-Impl)

## 目标

严格按方案编码，接口先行，每步验证。自动生成规范 commit message。

## 编码原则（优先级从高到低）

1. **接口抽象 > 具体实现**：能用 interface/Protocol 绝不直接依赖具体类型。接口属于使用方
2. **通用化 > 定制化**：能写成通用组件绝不写一次性代码。提取共性，差异通过参数/策略注入
3. **工厂注入 > 单例**：能用工厂/DI 绝不依赖全局状态。所有依赖显式传入
4. **组合 > 继承**：继承链 ≤2 层（Go 用 struct 嵌入，Python 用 Mixin + 组合）
5. **高内聚低耦合**：模块内高度聚合，模块间仅通过最窄接口通信；util/common 不反向依赖业务
6. **零循环依赖**：编译/import 时发现 → 立即用接口解耦
7. **垂直切片**：一个子目标 → 测试 → 实现 → 验证 → 下一个，不批量操作
8. **风格一致**：遵循项目现有 formatter/linter 配置
9. **量化上限**：函数 ≤50 行，文件 ≤500 行，类 ≤250 行（Python）

## 编码前检查

- [ ] 已读取 G 阶段子目标与验收标准
- [ ] 已读取 O 阶段选定方案与接口契约
- [ ] 已检查 import 链无循环依赖
- [ ] 已确认语言（Go → `go.mod`，Python → `pyproject.toml`）

## 🛡️ 工程约束（语言共享）

### 配置硬度

| 等级 | Go | Python | 场景 |
|------|-----|--------|------|
| 🔴 硬编码常量 | `const` / `var` block | `Final` / `UPPER_CASE` | 数学恒量、协议常量 |
| 🟠 默认+覆盖 | `const defaultX` + `WithX()` | `def f(x: int = 30)` | 有公认默认值的参数 |
| 🟡 环境变量 | `os.Getenv("X")` | `os.getenv("X")` | DB URL、密钥 |
| 🟢 配置文件 | YAML + unmarshal | TOML + pydantic-settings | 复杂业务配置 |
| 🔵 构造注入 | `func New(dep Dep)` | `def __init__(self, dep: Dep)` | 运行时依赖 |
| ⚪ 特性开关 | 配置中心 | 配置中心 | 热更新参数 |

**绝对禁止**：硬编码密钥/Token/密码/环境URL。

### 依赖方向（铁律）

```
高层策略 → Protocol/interface  ✅
高层策略 → 低层实现           ❌
util/common → 业务模块        ❌ 架构倒挂
```

### 全局状态禁令

```
❌ 包级 var db *sql.DB         → main() 初始化 + 参数传递
❌ 模块级 _cache: dict = {}     → class CacheService + DI
❌ 模块级 _client = Client()    → __init__(self, client)
❌ init() 复杂初始化            → 显式 Initialize()
```

**唯一例外**：`sync.Pool`、`regexp.MustCompile`、`re.compile()` — 不可变/官方推荐。

### 空值安全

| | Go | Python |
|------|-----|--------|
| 可能为空 | `(T, error)` | `Optional[T]` + 调用方 `is not None` |
| 不应为空 | `return T{}, ErrXxx` | `raise SpecificError(...)` |
| 区分"未提供"和"空" | `*string` (nil vs "") | `Optional[str]` (None vs "") |
| 禁止模式 | `return nil, nil` | `except: pass` / 裸 `return None` |

---

## 执行步骤

### Step 1: 接口先行

实现前先定义模块间接口（Go: `interface`，Python: `Protocol`），写在调用方模块中。

### Step 2: 按方案顺序实现

按 O 阶段实现步骤逐一执行。每步完成：

**Go:**
```bash
go build ./... && go test ./pkg/xxx/... -v -count=1 && go vet ./...
```

**Python:**
```bash
mypy src/ --strict && ruff check src/ && pytest tests/ -v -x --tb=short
```

**编译/类型/测试失败 → 立即停止，修复后继续**

### Step 3: 同步更新测试

修改签名/行为时同步更新对应 `*_test.go` 或 `test_*.py`。删除过时用例，更新参数化 case。

### Step 4: 生成 commit message

编码完成、测试通过后，按 G 阶段子目标 1:1 生成 commit：

```
<type>(<scope>): <subject>          ← ≤50 字符，祈使句

<body>                               ← 子目标逐条列出

Refs: <G1, G2, G3...>
```

| type | 场景 |
|------|------|
| `feat` | 新增功能/API |
| `fix` | 修复 bug |
| `refactor` | 重构，行为不变 |
| `perf` | 性能优化 |
| `test` | 仅测试变更 |
| `docs` / `chore` / `revert` | 文档/构建/回滚 |

**展示 message 给用户确认，不直接提交。**

### Step 5: 输出变更摘要

写入工作目录 `code-changes.md`：

```markdown
# 代码变更摘要

## 新增/修改/删除文件
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|

## API 变更
| API | 变更 | 兼容性 |

## 设计模式使用
| 模式 | 文件 | 效果 |

## 接口抽象
| 接口 | 实现方 | 使用方 |

## 循环依赖检查
- [ ] 确认无新增

## Commit 记录
| Commit | Type | 子目标 | Message |
|--------|------|-------|---------|
```

---

## 语言附录

### Go 专项

**提交前 grep:**
```bash
grep -rnE "return nil, nil" --include="*.go"          # 零容忍
grep -rnE '^var [a-z]+ ' --include="*.go"              # 包级可变
grep -rnE '"sk-|"password|"token|"secret' --include="*.go"  # 硬编码密钥
```

**Go 独有 pitfall:**
- `for range` 取 `&item` → 全部指向同一地址 → 用 `&items[i]`
- interface nil ≠ 底层指针 nil → 判断底层指针
- nil map 只读安全，写入 panic → 写入前 `make()`

### Python 专项

**提交前 grep:**
```bash
grep -rnE 'except\s*:' --include="*.py"                # 裸 except 零容忍
grep -rnE 'except.*:\s*$' --include="*.py"             # 吞异常
grep -rnE 'def \w+\([^)]*=\s*\[\]' --include="*.py"   # 可变默认参数
grep -rnE '"sk-|"password|"token|"secret' --include="*.py"  # 硬编码密钥
grep -rnE "^_\w+\s*=\s*(httpx\.|requests\.|redis\.)" --include="*.py"  # 模块级连接
```

**Python 独有 pitfall:**
- `def f(x=[])` → 所有调用共享同一 list → `def f(x=None)`
- `except: pass` → 吞掉 KeyboardInterrupt → 指定异常类型
- `__init__` 不能 async → 需要异步初始化用工厂函数 `async def create()`
- 同步函数内调 `asyncio.run()` → 事件循环嵌套死锁
- `is` 比较字面量 (`x is 5`) → 用 `==`

---

## 禁止行为 (Top 5)

1. ❌ **硬编码密钥/密码/Token/环境URL**
2. ❌ **循环依赖 / 循环 import**（零容忍，必须当场解耦）
3. ❌ **模块级可变状态**（包级 var / 模块级 _cache / 模块级 Client）
4. ❌ **跳过接口直接依赖具体实现**（interface/Protocol 先行）
5. ❌ **不经验证批量提交**（每子目标 → 验证 → commit → 下一子目标）

## 暂停点

询问用户："编码完成，请确认后运行完整测试"

## 打断机制

| 触发 | 处理 |
|------|------|
| 编译/类型检查失败 | 停止，报告错误 |
| 测试失败 | 停止，报告失败用例 |
| 发现方案未覆盖的依赖 | 停止 → 回 O 阶段补充 |
| 发现循环依赖 | 停止 → 接口解耦后继续 |
