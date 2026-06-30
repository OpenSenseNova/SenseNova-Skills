---
name: sn-prepare-citations
description: 用于终稿完成且脚注需要后处理时：去重 [^key] 引用，转换为 [N] 编号，并追加参考文献。
---

# sn-prepare-citations（引用渲染）

处理 sn-deep-research 的 `stitched.md`：从 evidence.json 收集 `sources[]`，将正文中的 `[^source_id]` 转换为 `[N]` 编号引用，插入 L0/TOC，并追加参考文献。

## 推荐用法（sn-deep-research v2）

```bash
python3 scripts/prepare_citations.py \
  --report <report_dir>/stitched.md \
  --evidence <report_dir>/sub_reports/d1.evidence.json <report_dir>/sub_reports/d2.evidence.json \
  --outline <report_dir>/outline.json \
  --output <report_dir>/report.md
```

## 参数

| 参数 | 说明 |
|---|---|
| `--report` | 输入 markdown。sn-deep-research 中通常是 `stitched.md` |
| `--evidence` | 全部 `d*.evidence.json`，用于收集 source 元数据和修复 claim-id 泄漏 |
| `--outline` | 可选但推荐。提供 L0、TOC 和标题结构信息 |
| `--output` | 输出 markdown。sn-deep-research 中通常是 `report.md` |
| `--no-l0` | 关闭 L0 摘要层渲染 |
| `--no-toc` | 关闭 TOC 渲染 |

## 处理逻辑

1. 从所有 evidence.json 的 `sources[]` 收集引用元数据。
2. 按 URL 归一化去重，同 URL source 合并为同一编号。
3. 检测 `[^dN.cM]` claim-id 引用泄漏；能映射到 claim evidence 时替换为对应 `source_id`，不能映射则报告 unresolved。
4. 扫描正文中的 `[^source_id]`，按首次出现顺序分配编号。
5. 替换 `[^source_id]` → `[N]`，移除脚注定义行。
6. 根据 outline 插入或校准 L0 / TOC。
7. 追加 `## 参考文献`。
8. 写出 `report.md` 和同目录 `citations.json`。
9. stdout 输出结构化 JSON，包含 orphan citations、claim-id leakage、TOC 和 L0 状态。

## 控制器处理要求

- `orphan_citations` 非空：不要交付，回 writer/stitcher 修正引用或删除 unsupported 内容。
- `claim_id_leakage.unresolved` 非空：不要交付，回 writer 修正 `[^dN.cM]`。
- `claim_id_leakage.resolved` 非空但 unresolved 为空：可以继续，但记录为警告；writer 后续应直接输出 `[^source_id]`。

## 旧兼容模式

不传 `--outline` / `--output` 时，脚本会覆写 `--report` 指向的文件，仅做引用编号和参考文献追加。sn-deep-research 正常流程不使用该模式。