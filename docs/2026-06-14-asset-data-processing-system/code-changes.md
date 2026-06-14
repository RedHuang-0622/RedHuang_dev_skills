# 代码变更摘要：通用资产数据处理 Skill 系统

## 总体统计

| 指标 | 数值 |
|------|------|
| 新增文件 | **53 个** |
| 代码行数（Python） | ~3,500 行 |
| 配置行数（JSON） | ~600 行 |
| 文档行数（Markdown） | ~400 行 |
| 覆盖工具簇 | 9/9 (TC1-TC9) |
| 遵循方案 | 方案 B（管道-过滤器），融合 A/C |

## 文件清单（按工具簇）

### TC1: 索引与属性簇层 (7 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `configs/index.json` | JSON | 全局资产目录 | Registry |
| `configs/clusters/base/real_estate_base.json` | JSON | 房产基类属性簇 | Inheritance |
| `configs/clusters/base/ship_base.json` | JSON | 船舶基类属性簇 | Inheritance |
| `configs/clusters/base/equipment_base.json` | JSON | 设备基类属性簇 | Inheritance |
| `configs/clusters/real_estate/mortgage.json` | JSON | 房产-抵押（继承基类） | Inheritance |
| `configs/clusters/ship/npl.json` | JSON | 船舶-不良债权（继承基类） | Inheritance |
| `configs/clusters/equipment/generic.json` | JSON | 设备（继承基类） | Inheritance |
| `filters/f01_index.py` | Python | 索引查找 Filter + 继承解析 | Chain of Resp. |

### TC2: 条目化预处理层 (6 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `filters/f02_chunk.py` | Python | 文本分块 Filter（语义/定长两种策略） | Strategy |
| `filters/f03_extract.py` | Python | LLM 提取 Filter（模板+重试+JSON解析） | Adapter |
| `filters/f04_deduplicate.py` | Python | 去重 Filter（精确指纹+模糊相似度） | Strategy |
| `prompts/extraction/extract_entries_generic.md` | Markdown | 通用条目化 Prompt 模板 | Template |
| `prompts/extraction/extract_from_pdf.md` | Markdown | PDF 专用变体 | Template |
| `prompts/extraction/extract_from_chat.md` | Markdown | 聊天/邮件专用变体 | Template |

### TC3: 标准化中间表示层 (4 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `filters/f05_normalize_structure.py` | Python | 结构归一化（别名+日期+布尔+数值清洗） | Strategy |
| `filters/f06_normalize_numeric.py` | Python | 数值归一化（Z-score/Min-Max） | Strategy |
| `filters/f07_generate_schema.py` | Python | Schema 生成（类型推断+统计+异常检测） | Builder |
| `filters/f08_generate_summary.py` | Python | Summary 生成（Markdown 报告） | Builder |
| `filters/f15_adapt_format.py` | Python | 多 Agent 格式适配（documents.jsonl） | Adapter |

### TC4: 处理逻辑与脚本层 (7 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `filters/f09_read.py` | Python | 数据读取（CSV/Excel/JSON/Parquet/编码检测） | Adapter |
| `filters/f10_clean.py` | Python | 清洗（去空+common_errors修复+去重+缺失值） | Strategy |
| `filters/f11_validate.py` | Python | 校验（type/range/pattern/enum/自定义） | Chain of Resp. |
| `filters/f12_transform.py` | Python | 变换（computed_fields 计算+列重排） | Strategy |
| `filters/f13_analyze.py` | Python | 分析（描述统计+IQR异常+相关性矩阵） | Strategy |
| `plugins/ship_plugin.py` | Python | 船舶插件（IMO校验+吨位换算+船龄） | Plugin |
| `plugins/equipment_plugin.py` | Python | 设备插件（直线折旧+双倍余额递减+残值） | Plugin |

### TC5: 任务缓存与提示词存储层 (3 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `filters/f14_snapshot.py` | Python | 快照保存（data.csv+schema.json+summary.md） | Memento |
| `filters/f16_finalize.py` | Python | 任务完结（meta.json更新+final/归档） | Memento |
| `kernel/packet.py` | Python | NormalizedPacket 数据包 DTO | DTO |

### TC6: 生命周期管理引擎 (1 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `wrappers/lifecycle_wrapper.py` | Python | 生命周期 Wrapper（TTL注入+角色策略覆盖） | Decorator |
| `configs/lifecycle_policies.json` | JSON | 5 种预定义生命周期策略 | Config |

### TC7: 安全与角色控制层 (3 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `wrappers/security_wrapper.py` | Python | 安全 Wrapper（RBAC+脱敏+行限制+分步确认+审批） | Decorator |
| `configs/role_permissions.json` | JSON | 3 角色权限映射 | Config |
| `configs/approval_rules.json` | JSON | 5 条审批规则 | Config |

### TC8: Goal 编排引擎 (3 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `filters/pipeline.py` | Python | Pipeline + Filter Protocol + PipelineFactory + Goal | Chain of Resp. + Factory |
| `wrappers/adaptive_wrapper.py` | Python | 自适应 Wrapper（数据特征检测+动态调整） | Decorator |
| `configs/goal_routing.json` | JSON | Goal → Pipeline Steps 映射（3 条路由） | Config |

### TC9: 多 Agent 协作协议 (2 文件)
| 文件 | 类型 | 说明 | 设计模式 |
|------|------|------|---------|
| `protocols/agent_protocol.md` | Markdown | Agent 协作协议（格式/目录/错误码/并发） | Protocol |
| `configs/agent_capabilities.json` | JSON | 5 个 Agent 能力注册 | Config |

### 共享层 (schemas + kernel + 入口)
| 文件 | 类型 | 说明 |
|------|------|------|
| `SKILL.md` | Markdown | Skill 入口 |
| `schemas/cluster.schema.json` | JSON | 属性簇 JSON Schema |
| `schemas/goal.schema.json` | JSON | Goal JSON Schema |
| `schemas/task_meta.schema.json` | JSON | 任务元数据 JSON Schema |
| `schemas/raw_entries.schema.json` | JSON | 原始条目 JSON Schema |
| `schemas/normalized_ir.schema.json` | JSON | 标准化 IR JSON Schema |
| `schemas/agent_message.schema.json` | JSON | Agent 消息 JSON Schema |
| `filters/context.py` | Python | PipelineContext 不可变上下文 |
| `filters/__init__.py` | Python | Filters 包初始化 |
| `wrappers/__init__.py` | Python | Wrappers 包初始化 |
| `plugins/__init__.py` | Python | 插件注册表 |
| `kernel/__init__.py` | Python | Kernel 包初始化 |
| `kernel/errors.py` | Python | 异常体系（3 层 15 个异常类） |
| `kernel/hooks.py` | Python | PluginProtocol + PluginRegistry |

## 设计模式使用汇总

| 模式 | 文件数 | 应用位置 |
|------|-------|---------|
| Strategy | 7 | f02 (chunk策略), f04 (去重), f05 (归一化), f06 (归一化), f09 (格式), f12 (变换), f13 (分析) |
| Chain of Resp. | 3 | pipeline.py (Pipeline), f01 (继承链), f11 (校验链) |
| Decorator | 3 | security_wrapper, lifecycle_wrapper, adaptive_wrapper |
| Adapter | 3 | f03 (LLM适配), f09 (格式适配), f15 (Agent格式) |
| Factory Method | 1 | pipeline.py (PipelineFactory) |
| Memento | 2 | f14 (快照), f16 (完结) |
| Builder | 2 | f07 (schema生成), f08 (summary生成) |
| Template Method | 1 | f03 (提取模板) |
| Observer | 1 | kernel/hooks (PluginRegistry热更新) |
| Plugin | 2 | plugins/ship_plugin, plugins/equipment_plugin |
| DTO | 2 | context.py (PipelineContext), kernel/packet.py (NormalizedPacket) |

## 循环依赖检查

- [x] 确认无新增循环依赖
- [x] filters/ 之间通过 PipelineContext 通信，零 import 依赖
- [x] wrappers/ 装饰 filters/，filters 不知道 wrappers 存在
- [x] kernel/ 不依赖 plugins/（通过 Protocol 反向依赖）
- [x] configs/ 和 schemas/ 被其他模块只读引用，无反向依赖

## Commit 记录

> 编码完成，以下为建议的 commit message（按子目标）：

| Commit | Type | 子目标 | Message |
|--------|------|-------|---------|
| `0000001` | `feat(skill)` | G0 | add SKILL.md entry with architecture overview |
| `0000002` | `feat(pipeline)` | G0 | add Pipeline framework (context, pipeline, filter protocol, pipeline factory) |
| `0000003` | `feat(clusters)` | G1 | add index.json and 6 property cluster JSONs with inheritance |
| `0000004` | `feat(filters)` | G1 | add f01 index lookup filter with inheritance resolution |
| `0000005` | `feat(schemas)` | G1 | add 6 JSON Schemas (cluster, goal, task_meta, raw_entries, normalized_ir, agent_message) |
| `0000006` | `feat(configs)` | G5-G8 | add runtime configs (goal_routing, lifecycle_policies, role_permissions, approval_rules, agent_capabilities) |
| `0000007` | `feat(filters)` | G3 | add f05-f08 normalization filters (structure, numeric, schema, summary) |
| `0000008` | `feat(filters)` | G4 | add f09-f13 processing filters (read, clean, validate, transform, analyze) |
| `0000009` | `feat(filters)` | G2 | add f02-f04 entry extraction filters (chunk, extract, deduplicate) |
| `00000010` | `feat(filters)` | G3/G5 | add f14-f16 cache/adapt/finalize filters |
| `00000011` | `feat(prompts)` | G2 | add 3 extraction prompt templates (generic, pdf, chat) |
| `00000012` | `feat(wrappers)` | G7 | add security wrapper (RBAC + masker + intern guard + sandbox + approval) |
| `00000013` | `feat(wrappers)` | G6/G8 | add lifecycle and adaptive wrappers |
| `00000014` | `feat(plugins)` | G4 | add ship and equipment plugins with asset-specific logic |
| `00000015` | `feat(kernel)` | G5 | add kernel (errors, packet DTO, plugin hooks, plugin registry) |
| `00000016` | `feat(protocols)` | G9 | add agent_protocol.md with data exchange and concurrency conventions |

## 未覆盖项（按非目标清单）

| 非目标 | 状态 |
|--------|------|
| Python 依赖安装（pyproject.toml） | ❌ 未生成（用户自行管理） |
| 实际 LLM API 对接 | ❌ 仅定义 LLMBackend Protocol |
| S3 Glacier 对接 | ❌ 仅定义 archiver 接口 |
| 前端 UI / 导师监控面板 | ❌ 不在范围内 |
| 模拟考试题库 | ❌ 仅定义框架 |
| ML 模型训练 | ❌ 仅预留指标接口 |
