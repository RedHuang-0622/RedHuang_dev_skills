---
name: code-impl
description: 根据方案执行编码，接口先行，增量验证，自动同步测试，遵循设计模式与工程约束
---

# 编码实现专家 (Code-Impl)

## 目标

严格按方案执行编码，每完成一步立即验证，自动更新相关测试文件。

## 上下文获取（按优先级尝试）

1. **dev-goal 模式**：工作目录 `docs/YYYY-MM-DD-{模块或功能名}/`
   - 从 `devgoal流程.md` 的 `## G: Goal` 获取目标拆解与验收标准
   - 从 `devgoal流程.md` 的 `## O: Options` 获取选定方案、接口草图、设计模式
2. **独立模式**：读取 `docs/plan.md` + `docs/front-review.md`（保留兼容）
3. **最小模式**：都不存在时，从当前代码库状态和用户需求反推

## 编码原则

- **接口先行**：先定义模块间接口，后写实现 — O 阶段有接口草图则严格遵循
- **垂直切片**：一个测试 → 一个实现 → 验证通过 → 下一个，不批量操作
- **类型优先**：充分利用类型系统，避免 `any` / `interface{}` 滥用
- **单一职责**：每个函数 ≤ 50 行，每个文件 ≤ 500 行
- **设计模式落地**：严格按方案中选定的设计模式编码
- **接口通信**：模块间通过接口而非具体实现通信
- **零循环依赖**：绝不引入循环依赖，如有必要即时重构为接口解耦
- **风格一致**：与现有代码风格保持一致（命名、注释、错误处理方式）

## 编码前检查清单

- [ ] 已读取 G 阶段目标拆解（知道要达成什么），或 plan.md
- [ ] 已读取 O 阶段选定方案与接口契约（知道怎么实现），或 plan.md
- [ ] 已检查 import 链，确认无循环依赖
- [ ] 已确认与现有代码风格一致

## 🛡️ 工程约束（编码时强制）

### 配置硬度：实施对照

| 值类型 | 必须用 | 检测方式 |
|--------|-------|---------|
| 密钥/Token/密码 | `os.Getenv` 或密钥服务 | Grep: `"sk-"`, `"password"`, `"token"` 不能出现在代码字面量 |
| 环境相关 URL | env / config.yaml | Grep: `"http://"` 或 `"https://"` 后跟具体 IP/域名 → 抽到 env |
| 不变常量 | `const` | 魔法数字/字符串出现在函数体中 → 提取为 named const |
| 业务阈值 | default const + option | 如 `const defaultPageSize = 20` 但提供 `WithPageSize(n)` |
| 外部依赖 | 构造函数注入 | 包级 `var client = http.Client{}` → 改为 `func New(cfg Config) *Svc` |

**编码后自检**：对整个 diff 跑一次 mental grep — 是否有任何硬编码的秘密、URL、或环境特定值？

### nil vs 空字符串：编码规则

```go
// ❌ 返回 nil string
func GetName(id int) *string {
    if id == 0 {
        return nil  // 调用方解引用必崩
    }
    name := "user_" + strconv.Itoa(id)
    return &name
}

// ✅ 返回零值 + error
func GetName(id int) (string, error) {
    if id == 0 {
        return "", ErrInvalidID
    }
    return "user_" + strconv.Itoa(id), nil
}

// ✅ 需要区分"未提供"和"空"时才用指针
type UpdateReq struct {
    Name *string `json:"name"`  // nil=不更新, ""=清空, "xxx"=更新
}
```

**规则**：
- 函数返回值：永远用 `(T, error)` 不用 `*T`
- JSON API：需要区分 null 和 "" 时用 `*string`，否则用 `string` + `omitempty`
- Map 写入前：必须 `make()` 或用字面量初始化。nil map 只允许只读场景
- Slice 返回给 JSON API：用 `[]T{}` 不是 `nil`，确保序列化为 `[]` 而非 `null`

### 野指针：三条铁律

```go
// 铁律 1: 构造函数不返回 nil + nil error
func NewSvc(dep Dep) (*Svc, error) {
    if dep == nil {
        return nil, errors.New("dep required")  // nil ptr + error = 合法
    }
    return &Svc{dep: dep}, nil
}
// 调用方: svc, err := NewSvc(dep);  if err != nil { return err }; svc.Do() ← 安全

// 铁律 2: 循环变量不取地址
// ❌
for _, item := range items {
    results = append(results, &item)  // 全都指向同一个地址！
}
// ✅
for i := range items {
    results = append(results, &items[i])  // 每个元素独立地址
}

// 铁律 3: interface nil ≠ 底层指针 nil
// ❌
var repo *mysqlRepo = nil
var iface Repo = repo
if iface == nil { ... }  // false! iface 有类型信息，不为 nil
// ✅
if repo == nil { ... }   // 直接判断底层指针
```

**提交前必查**：
- [ ] `grep "return nil, nil"` — 禁止（调用方无法区分正常和异常）
- [ ] `grep "return &.*\b(range\b|[A-Z])"` — 疑似返回 loop 变量地址
- [ ] 所有 `*T` 返回值的函数，检查 nil 路径是否都伴随 error

### 全局变量检测

```bash
# 提交前跑这个检查 — 发现包级 var 立即审视
grep -nE "^var [a-z]" pkg/**/*.go  # 包级 var（导出 var 大写除外）
grep -nE "^var [a-z]+ =" pkg/**/*.go  # 包级 + 初始化 = 最可疑
```

**处理**：
| 场景 | 改造方式 |
|------|---------|
| `var db *sql.DB` | → `main()` 中初始化 + 通过参数传递 |
| `var once sync.Once` + init | → 显式初始化函数，避免隐式 init 顺序依赖 |
| `var defaultTimeout = 30s` | → `const DefaultTimeout = 30 * time.Second` |
| `var logger = log.New(...)` | → 构造函数注入或用 `log.Default()` |
| `regexp.MustCompile` 包级 | ✅ 允许（官方推荐，不可变） |

### 高内聚低耦合：提交前过一遍

| 检查项 | 指标 |
|--------|------|
| 包级函数数 | > 10 个公开函数 → 职责可能太多 |
| 文件行数 | > 500 行 → 拆文件 |
| 函数行数 | > 50 行 → 拆函数（测试辅助除外） |
| import 数 | 一个包 import > 8 个其他包 → 耦合过高 |
| 循环依赖 | `go vet ./...` 零告警是底线 |
| util/common 包 | 不 import 任何业务包 ← **铁律** |

```go
// ❌ 高耦合：util 包 import 业务包
package util
import "project/pkg/order"  // util 引业务 → 架构倒挂

// ✅ 低耦合：util 零业务依赖
package util
import "encoding/json"  // 只引标准库或第三方基础库
```

## 执行步骤

### Step 1: 接口先行

在实现之前，先定义模块间接口：

```go
// 先定义接口契约
type IUserRepository interface {
    FindByID(ctx context.Context, id string) (*User, error)
    Save(ctx context.Context, user *User) error
}
```

### Step 2: 按方案顺序实现

按方案（devgoal流程.md O 阶段 或 plan.md）中的实现步骤顺序执行。每完成一个子目标：

```bash
# 1. 编译检查
go build ./...

# 2. 仅运行相关测试（快速反馈）
go test ./pkg/xxx/... -v -count=1

# 3. 静态检查
go vet ./...
```

**编译或测试失败 → 立即停止，修复后继续。**

### Step 3: 自动更新测试

当修改函数签名或行为时，同步更新对应测试文件：

- 识别被修改函数对应的测试文件（`*_test.go` 或 `*.test.ts`）
- 更新断言以匹配新行为
- 删除过时的测试

### Step 4: 输出变更摘要

**根据调用模式选择输出目标**：

| 模式 | 输出目标 |
|------|---------|
| dev-goal 模式 | 写入工作目录 `docs/YYYY-MM-DD-{模块或功能名}/code-changes.md` |
| 独立模式 | 生成 `docs/YYYY-MM-DD-功能变更摘要-code-changes-{负责人姓名}.md` |

## 输出格式

```markdown
# 代码变更摘要

## 新增文件
| 文件路径 | 用途 | 设计模式 |
|---------|------|---------|
| pkg/xxx/xxx.go | [简述] | [模式名] |

## 修改文件
| 文件路径 | 修改类型 | 具体位置 | 说明 |
|---------|---------|---------|------|
| pkg/xxx/xxx.go | 重构/新增逻辑 | L45-L78 | [改了什么] |

## 删除文件
| 文件路径 | 删除原因 |
|---------|---------|
| pkg/xxx/deprecated.go | 功能迁移到新模块 |

## API 变更
| API | 变更类型 | 兼容性 | 迁移说明 |
|-----|---------|-------|---------|
| OldFunc(a, b string) | 签名变更 → NewFunc(ctx, a, b) | ⚠️ 不兼容 | 调用方需添加 ctx 参数 |

## 设计模式使用
| 模式 | 文件 | 效果 |
|------|-----|------|
| Strategy | payment.go | 支付方式可插拔 |

## 接口抽象
| 接口 | 实现方 | 使用方 |
|------|-------|-------|
| IUserRepo | mysql/user_repo.go | order/service.go |

## 循环依赖检查
- [ ] 已确认无新增循环依赖
```

## 禁止行为

- ❌ 在没有测试覆盖的情况下重构
- ❌ 一次性修改超过 5 个不相关的文件
- ❌ 在未读取方案（devgoal流程.md 或 plan.md）的情况下开始编码
- ❌ 引入循环依赖（零容忍）
- ❌ 跳过接口直接依赖具体实现
- ❌ 使用全局变量做模块间通信
- ❌ **硬编码密钥/密码/Token/环境URL**（必须 env 或配置）
- ❌ **返回 nil 指针 + nil error**（调用方必崩，grep `return nil, nil` 自检）
- ❌ **取 loop 变量地址**（所有的 `&item` 在 for range 中都是 bug）
- ❌ **nil map 写入**（只读可以，写入必须 make）
- ❌ **包级 var 可变状态**（`var db *sql.DB`、`var cache map[string]T` → DI）
- ❌ **util/common 包 import 业务包**（架构倒挂）
- ❌ 构造函数无 error 返回值却可能失败（用 `func New(...) (*T, error)` 而非 `func New(...) *T`）

## 暂停点

询问用户："编码完成，请确认后我将运行完整测试"

## 打断机制

| 触发条件 | 处理方式 |
|---------|---------|
| 编译错误 | 停止，报告错误位置 |
| 测试失败 | 停止，报告失败用例 |
| 发现方案未覆盖的依赖 | 停止，描述依赖，建议回 O 阶段补充 |
| 发现潜在循环依赖 | 停止，先重构为接口解耦 |
