---
name: asset-data-skill
description: 通用资产数据处理平台 — 元数据驱动、多 Agent 协作、完整生命周期管理的数据处理操作系统
---

# 通用资产数据处理 Skill (Asset Data Skill)

## 设计哲学

本 Skill 是一个**数据处理操作系统**：用声明式配置管理"数据是什么"，用标准化中间表示和提示词管理"如何理解数据"，用任务缓存和生命周期策略管理"数据如何安全流转"。

核心原则：
- **知识外置**：业务规则全部存储于 JSON 配置中，系统仅负责解释执行
- **统一中间表示**：所有数据最终转换为 `data.csv` + `schema.json` + `summary.md` 三件套
- **过程即资产**：每一步操作、提示词、LLM 回复、数据快照均留痕
- **安全内生**：权限、脱敏、审批、回滚机制贯穿各层
- **生命周期感知**：从数据进入系统即赋予生存周期策略
- **目标驱动自动化**：以 Goal 为入口，自动编排处理流水线

## 触发条件

当用户需要处理结构化/非结构化资产数据时使用本 Skill。典型触发词：
- "处理这批资产数据"
- "从这份 PDF 提取资产条目"
- "清洗并校验抵押资产表"
- "分析船舶不良债权数据"

## 架构

```
原始数据 → [条目化] → 标准化 IR → 清洗/校验/分析 → 最终交付
              ↑                           ↑
          TC2 Filter                 TC4 Filter 链
              │                           │
     ┌────────┴──────────┐    ┌──────────┴──────────┐
     │  Wrappers (横切)   │    │  PipelineContext     │
     │  TC7 安全/审批     │    │  (不可变数据流上下文)  │
     │  TC6 生命周期      │    │                      │
     │  TC8 自适应        │    └─────────────────────┘
     └───────────────────┘
```

## 快速开始

### 1. 声明 Goal

```json
{
  "goal": "clean_and_validate",
  "asset_type": "RE_MORTGAGE",
  "input": "upload/2024Q3_portfolio.xlsx",
  "role": "analyst",
  "params": {"interactive": true, "normalize": true}
}
```

### 2. 系统自动编排

系统解析 Goal → 加载属性簇 → 构建 Filter 链 → 注入 Wrapper → 执行流水线

### 3. 获取交付物

`task_cache/{task_id}/final/` 下包含处理后的数据和完整审计追踪。

## 文件组织

```
asset-data-skill/
├── SKILL.md                      # 本文件
├── filters/                       # 管道-过滤器核心 (16 Filter)
│   ├── context.py                 # PipelineContext 不可变上下文
│   └── pipeline.py                # Pipeline + Filter Protocol + PipelineFactory
├── configs/                       # 配置驱动 (全部 JSON)
│   ├── index.json                 # 全局资产目录
│   ├── clusters/                  # 属性簇 JSON (每资产类型一个)
│   ├── goal_routing.json          # Goal → Pipeline Steps 映射
│   ├── lifecycle_policies.json    # 生命周期策略定义
│   ├── role_permissions.json      # 角色-权限映射
│   ├── approval_rules.json        # 审批规则
│   └── agent_capabilities.json    # Agent 能力注册
├── schemas/                       # JSON Schema 校验
├── wrappers/                      # 横切关注点 Wrapper
├── plugins/                       # 资产类型插件
├── prompts/                       # LLM 提示词模板
├── protocols/                     # Agent 协作协议
└── kernel/                        # 微内核组件
```

## 角色与权限

| 角色 | 数据脱敏 | 行数限制 | 高风险操作 | 分步确认 |
|------|---------|---------|-----------|---------|
| admin | 无 | 无 | 直接执行 | 可选 |
| analyst | 按字段 access_level | 无 | 需确认 | 可选 |
| intern | 强制脱敏 | 默认 1000 行 | 需导师审批 | 强制 |
