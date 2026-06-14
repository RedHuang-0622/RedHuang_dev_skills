# 任务：从 PDF/扫描件 OCR 文本中提取资产条目

## 资产类型
{{ asset_type_name }}

## 字段定义
{{ fields_table }}

## OCR 文本（可能存在识别错误）
{{ raw_text }}

## 特殊注意事项（PDF/OCR）

1. **OCR 纠错**：
   - 常见 OCR 错误自动纠正（如 "0"↔"O", "1"↔"l", "元"↔"无"）
   - 表格识别错位时，尝试根据字段类型推断正确对应关系
   - 如果某行明显错位，标注 needs_review=true

2. **多页处理**：
   - 注意跨页表格的连续性
   - 页眉页脚内容忽略

3. **扫描质量**：
   - 如果某段文本 confidence 整体偏低（<0.7），整段标注 needs_review=true
   - 明显污损/遮挡区域标注为不可提取

4. **输出格式**：同通用模板的 JSON 数组格式

## 输出要求

```json
[
  {
    "fields": { "字段名": "值" },
    "confidence": 0.85,
    "field_confidences": { "字段名": 0.90 },
    "source_quote": "原文片段",
    "needs_review": false,
    "ocr_note": "OCR 质量描述（如有问题）"
  }
]
```
