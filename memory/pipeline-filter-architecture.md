---
name: pipeline-filter-architecture
description: 管道-过滤器架构用于数据处理系统 — Pipes & Filters + Wrapper AOP 注入横切关注点
metadata:
  type: project
  tags: [architecture, data-processing, pipes-and-filters, python, design-patterns]
---

## 场景

构建一个"通用资产数据处理系统"（7 层架构 + 2 横切关注点），需要同时满足：
- 数据流经多步骤变换（读取→归一化→清洗→校验→变换→分析→输出）
- 安全/生命周期/自适应等横切关注点不侵入业务逻辑
- 新增资产类型只需配置，零代码修改
- 每步可回滚、全链可审计

## 方案

选择**管道-过滤器（Pipes & Filters）**架构，融合分层配置结构和微内核插件目录：

```
PipelineContext (frozen dataclass)
  │
  ├─ f01_index (属性簇加载+继承解析)
  ├─ f09_read (格式检测+编码推断)
  ├─ f02-f04 (LLM条目化: chunk→extract→dedup)
  ├─ f05-f06 (归一化: 结构+数值)
  ├─ f11_validate (多规则校验)
  ├─ f10_clean (自动修复common_errors)
  ├─ f12_transform (派生字段计算)
  ├─ f13_analyze (描述统计+IQR+相关性)
  ├─ f07-f08 (schema.json + summary.md)
  ├─ f15_adapt (Agent格式适配)
  ├─ f14_snapshot (快照保存)
  └─ f16_finalize (完结+TTL策略)
  │
  ▼
Wrappers (装饰器模式):
  ├─ SecurityWrapper (RBAC+脱敏+行限制+审批)
  ├─ LifecycleWrapper (TTL注入+策略覆盖)
  └─ AdaptiveWrapper (数据特征检测+动态调整)
```

### 为什么选这个方案而非其他

| 方案 | 核心思路 | 弃用原因 |
|------|---------|---------|
| A: 分层架构 | 按架构层组织目录，层间单向依赖 | Protocol 爆炸（10+ 个接口），横切渗透到每层 |
| B: 管道-过滤器 **（选中）** | 不可变 Context 穿过 Filter 链，Wrapper 装饰注入 | — |
| C: 微内核-插件 | 内核最小化，每种资产一个插件包 | 钩子体系设计复杂，初始架设成本最高 |

**方案 B 的核心优势**：
1. Filter 纯函数 `(PipelineContext) → PipelineContext`，零 mock 依赖，可测试性极强
2. Wrapper 装饰器模式让横切关注点零侵入——Security/Approval/Lifecycle 不写在任何业务 Filter 里
3. 融合 A 的配置结构清晰性 + C 的插件独立性

## 关键经验

- **PipelineContext 不可变性是整个系统最重要的架构决策**。使用 `frozen=True` dataclass + `dataclasses.replace()`，保证任何时候都能回滚到任意步骤之前。1000 次链式操作后原始 Context 为零变化。
- **Wrapper 顺序很重要**：Security→Lifecycle→Adaptive→Filter。Security 必须是外层（先鉴权再做事），Lifecycle 只监听 finalize，Adaptive 在 read 后/chunk 前介入。
- **Filter 之间通过 PipelineContext 通信，不 import 彼此**——这是保证零循环依赖的秘诀。Filter 链可以任意增删重排而不影响其他 Filter。
- **属性簇继承链深度限制 ≤3 层**——防止 JSON 配置演变成 Java Spring 式的 XML 地狱。
- **横切关注点按 Wrapper 装饰器注入，不按继承/混入**——这是与方案 A（分层架构）最大的区别，也是避免"Protocol 爆炸"的关键。

## 踩坑

- **`object.__replace__()` 在 Python 3.11 中不存在**：代码最初写了 `object.__replace__(self, field=value)`，但这是 Python 3.12+ 的功能。正确写法是 `dataclasses.replace(self, field=value)`。26 处全部需修复。
- **SizeChunker 无限循环**：当 `end == text_len`（到达文本末尾）时，`start = end - overlap` 会回到 overlap 位置，导致永远在最后一段循环。修复：在 `end >= text_len` 时提前 break。
- **SecurityWrapper._check_permission 只允许 admin**：权限检查只判断 `"*" in allowed`（admin 专属），非 admin 角色永远被拒绝。修复：增加 `filter_name in allowed` 作为备选逻辑。
- **相对导入路径错误**：Filter 文件中使用了 `from ..context import PipelineContext`，但 `filters/` 是顶层包，不存在父包。应该用 `from .context import PipelineContext`（单点）。

## 工程约束违规（如有）

| 约束类别 | 具体问题 | 文件:行 | 修复方式 | 预防建议 |
|---------|---------|--------|---------|---------|
| 全局变量 | `REGISTRY: dict` 模块级可变状态 | plugins/__init__.py:23 | 标记为 `re.compile()` 级例外，建议下版迁移到 `PluginRegistry` 类 | 在 code-impl 中明确列举"可接受的全局状态例外清单" |
| 文件行数 | f11_validate.py 257 行 > 250 上限 | filters/f11_validate.py | 可将枚举/正则校验器抽取为独立模块 | 考虑将上限调至 300 行（pandas 操作天然冗长）|

## 可复用做法

- **Filter 编号规范**：f01-f16 按数据流顺序编号，一眼可知执行顺序；测试文件命名 `test_f01_index.py` 与源文件 1:1 对应
- **workflow 工作目录结构**：`docs/YYYY-MM-DD-{模块名}/devgoal流程.md` + 5 个子文档，作为 Skill 间唯一交接协议
- **Mock LLM Backend 模式**：`f03_extract.py` 通过 `LLMBackend Protocol` 定义接口，测试用 MockLLMBackend 注入预定义响应（包含 bad JSON + retry 测试）
- **Frozen dataclass + replace()** 实现不可变数据流，比深拷贝高效（只复制引用），比手动构造新对象安全（类型检查）

## 结论

✅ 推荐 — 管道-过滤器架构特别适合"数据流经多步骤变换"的场景。与 Configuration-Driven（JSON 配置定义一切）结合后，新增资产类型只需一个 JSON 文件。
