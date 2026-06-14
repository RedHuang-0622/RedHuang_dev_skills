---
name: workplan
description: 长期定时工作规划器，管理周期性任务和长期工作计划
---

# 长期工作规划器 (Workplan)

## 目标

管理和调度长期、周期性的工作任务，确保工作按计划推进。

## 使用场景

- 创建周期性工作安排
- 追踪长期目标进度
- 日程规划和提醒
- 工作任务分解和时间线管理

## 核心功能

### 工作项定义
```go
type WorkItem struct {
    ID          string
    Title       string
    Description string
    Priority    Priority // P0-P3
    Status      Status   // Todo/Doing/Done/Blocked
    StartDate   time.Time
    DueDate     time.Time
    Recurrence  *Recurrence // 周期性任务
    Dependents  []string    // 依赖的其他工作项
}
```

### 周期类型
| 类型 | 说明 | 示例 |
|------|-----|------|
| Daily | 每日 | 每日站会 |
| Weekly | 每周 | 周报 |
| Monthly | 每月 | 月度复盘 |
| Custom | 自定义 | Cron 表达式 |

### 工作流

```
创建计划 → 任务分解 → 调度执行 → 进度追踪 → 完成复盘
```

### 进度追踪

```markdown
## 工作进度报告

### 本周完成
- [x] [任务1]
- [x] [任务2]

### 下周计划
- [ ] [任务3]
- [ ] [任务4]

### 风险项
- [风险描述] [影响] [应对措施]

### 阻塞项
- [阻塞描述] [依赖] [预计解决时间]
```

## 设计模式

- **Observer 模式**：工作项状态变更时通知相关人员
- **Command 模式**：工作项可撤销/重做
- **Strategy 模式**：不同周期的调度策略
