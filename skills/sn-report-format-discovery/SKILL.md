---
name: sn-report-format-discovery
description: 用于用户希望推荐研究成品形式，或最终形式无法从需求中直接判断时。把需求解析为一个简短的 format 字符串，不创建格式文件或 schema。
---

# 最终形式推荐

根据用户需求确定一个请求级 `format` 字符串。该字符串和 `language` 一样只在本次运行上下文中传递，不写入文件。

## 输入

- 原始研究需求 `query`
- 请求级 `language`
- 用户明确提出的最终形式（如有）

## 规则

1. 用户明确指定最终形式时，优先使用用户的名称。
2. 用户未指定时，根据主要阅读任务选择一个简短名称；无法判断时使用 `report`。
3. 常见值包括 `report`、`paper`、`table`、`memo`、`timeline`、`faq`，但这不是封闭枚举。
4. `format` 只表示最终交付形式，不承载章节、摘要、目录、结构偏好或写作规则；这些要求继续保留在原始 query 中。
5. 不搜索外部格式规范，不生成候选对象，不创建 `format_proposal.json`、`format.json` 或任何格式 schema。
6. 不替用户修改研究问题、范围、语言或流程模式。

## 输出

只返回一行：

```text
format: <一个简短的非空字符串>
```
