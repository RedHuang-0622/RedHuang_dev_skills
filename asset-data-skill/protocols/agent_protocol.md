# Agent 协作协议 (Agent Protocol)

## 概述

本协议定义多个 Agent 之间通过 `task_cache` 文件系统协作的约定。Agent 之间**无实时通信**，通过读写约定的目录和文件交换数据，天然支持异步和重试。

## 数据交换格式

### 标准数据包（三件套）

| 格式 | 文件 | 内容 | 消费者 |
|------|------|------|--------|
| 结构化数据 | `data.csv` | 列名为属性簇标准字段名的 CSV | cleaner, analyzer, auditor |
| 列级元数据 | `schema.json` | 每列的类型、统计摘要、缺失值 | analyzer, auditor |
| 人类可读报告 | `summary.md` | 行数、列列表、异常预览 | human, orchestrator |

### 扩展格式

| 格式 | 文件 | 用途 |
|------|------|------|
| 条目化结果 | `raw_entries.json` | LLM 提取的结构化条目 |
| 向量嵌入文本 | `documents.jsonl` | 每行一个自然语言描述的 JSON |
| 归一化数据 | `data_normalized.csv` | Z-score / Min-Max 归一化副本 |
| 变更日志 | `changelog_{step}.json` | 每步骤前后差异 |

## 目录约定

```
task_cache/{task_id}/
├── meta.json              ← 任务元数据
├── inputs/                ← 原始文件快照（只读）
├── normalized/            ← Agent 间交换点
│   ├── data.csv
│   ├── schema.json
│   └── summary.md
├── steps/                 ← 处理步骤快照
├── logs/                  ← 操作日志
└── final/                 ← 最终交付物
```

## Agent 角色与能力

| Agent 角色 | 输入 | 输出 | 写目录 |
|-----------|------|------|--------|
| `extractor` | `inputs/` 原始文件 | `normalized/raw_entries.json` | — |
| `cleaner` | `normalized/data.csv` | `steps/after_clean.csv` + changelog | — |
| `analyzer` | `normalized/data.csv` + `schema.json` | `normalized/report.md` | — |
| `auditor` | `normalized/` + `steps/` + `logs/` | `final/audit_report.md` | — |
| `orchestrator` | `goal.json` | `meta.json` | task_cache 目录 |

## 错误码

| 错误码 | 含义 | 处理方式 |
|--------|------|---------|
| `AGENT_ERR_INPUT_FORMAT` | 输入格式不符合预期 | 检查上游输出，重新生成 |
| `AGENT_ERR_TIMEOUT` | LLM 调用超时 | 重试（最多 3 次），降级到规则模式 |
| `AGENT_ERR_PERMISSION` | 权限不足 | 提升角色或跳过该步骤 |
| `AGENT_ERR_DATA_CORRUPTION` | 数据损坏 | 从上一个 checkpoint 恢复 |
| `AGENT_ERR_CLUSTER_MISSING` | 属性簇未找到 | 检查 index.json 注册情况 |

## 并发控制

同一 `task_id` 同时最多一个 Agent 写入：
- **文件锁**：写入前获取 `{task_id}.lock`（跨平台：portalocker）
- **状态检查**：写入前检查 `meta.json` 的 `status` 字段
- **幂等写入**：所有 Agent 写入应是幂等的（相同输入 → 相同输出）

## 版本兼容

- 协议版本通过 `meta.json` 中的 `protocol_version` 字段声明
- 向后兼容：新 Agent 必须能读取旧格式
- 向前不兼容时，Agent 返回 `AGENT_ERR_INPUT_FORMAT` 并注明所需版本
