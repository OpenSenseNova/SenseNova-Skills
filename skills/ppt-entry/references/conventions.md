# PPT 系 skill 共用约定

所有 `ppt-*` skill 的 SKILL.md 在 shell 示例里使用以下占位符。**main agent 在
真正发 tool 调用前，负责按字面把它们替换成具体值**。不要依赖 shell 变量导出。

| 占位符 | 解析来源 | 示例值 |
|---|---|---|
| `<SKILL_DIR>` | 当前 skill 的安装目录（openclaw 已知） | `/absolute/path/to/skills/ppt-creative` |
| `<PPT_ENTRY_DIR>` | `ppt-entry` skill 的安装目录（openclaw 已知；**不要**用 `<U1_IMAGE_BASE>/..` 推导） | `/absolute/path/to/skills/ppt-entry` |
| `<deck_dir>` | `task_pack.json` 的 `deck_dir` 字段 | `/absolute/path/to/ppt_decks/AI产品发布会_20260318_154500` |
| `<deck_id>` | `task_pack.json` 的 `deck_id` 字段 | `AI产品发布会_20260318_154500` |
| `<U1_IMAGE_BASE>` | env `U1_IMAGE_BASE`（最高优先）→ openclaw skill 注册表 → 仓库相对 `skills/u1-image-base/`（**仅在 skills 都在本仓库同级时 work，分发安装时失效**，此时必须依赖前两级） | `/absolute/path/to/skills/u1-image-base` |
| `<NNN>` | 当前页号，三位补零 | `001`、`012`、`123` |

## 绝对路径原则

见 spec §16：所有落盘到 `deck_dir` 的工件里涉及 path 的字段一律绝对路径。
shell 示例里的路径也按绝对路径给出（main agent 替换后即绝对路径）。
**不要依赖 `cd <deck_dir>` 再用相对路径**，因为主 agent 在同一会话里可能
穿插其他工具调用，cwd 不可靠。

## `$U1_IMAGE_BASE` 解析

main agent 按以下顺序确定 u1-image-base 路径：

1. 环境变量 `U1_IMAGE_BASE`
2. openclaw 内部 skill 注册表返回的 u1-image-base 目录
3. 本仓库相对路径 `skills/u1-image-base/`（最后兜底）

解析完成后，替换所有 `<U1_IMAGE_BASE>` 占位符。不要 `export` 后依赖子进程继承。

## `timing.json` 写入契约

三个 mode skill 都要在每阶段进入 / 结束时调用 `timing_helper.py`，通过子进程调用，**不 import**（跨 skill 边界的 Python import 不稳定）。

工件位置：`<deck_dir>/timing.json`，绝对路径。

最小使用模式：

```bash
# entry 启动时初始化
python <PPT_ENTRY_DIR>/scripts/timing_helper.py init --path <deck_dir>/timing.json

# 记录一个阶段（entry / style / outline / asset_plan / image_generate / asset_qc / page_html / review / rewrite / pptx_export / review_summary）
python <PPT_ENTRY_DIR>/scripts/timing_helper.py record-stage --path <deck_dir>/timing.json --stage style --seconds 10.5

# 记录 per-page 粒度（prompt_seconds / image_gen_seconds / html_seconds / review_seconds / rewrite_seconds）
python <PPT_ENTRY_DIR>/scripts/timing_helper.py record-page --path <deck_dir>/timing.json --page-no 3 --field image_gen_seconds --seconds 14.2
```

**Resume 行为**：同一 stage 被多次写入 → 秒数累加，不重置（见 spec §15.3）。

## 内联注入占位符：`<<<INLINE: path>>>`

某些 prompt 文件里会出现字面量：

    <<<INLINE: references/html_constraints.md>>>

main agent 在发起 `u1-text-optimize` 调用**之前**，用该 prompt 文件**同 skill 目录**下对应路径的**文件全文**替换这条占位符。替换在内存里做，不改原 prompt 文件。

如果占位符指向的文件不存在或读取失败，**abort**（结构性依赖）。
