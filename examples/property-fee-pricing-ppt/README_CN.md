# 单技能示例：物业费定价体系 PPT 生成

[English version](README.md)

本示例演示如何使用 SenseNova-Skills 中的 **PPT 生成** 能力，仅凭一句指令、不提供任何输入文件，让智能体根据风格要求和受众场景，从零生成一份可直接打开的 PPTX。

> 主线：给定主题 / 页数 / 配色 / 风格 / 受众 → 自动产出大纲与素材计划 → 渲染分页 HTML → 截图合成 PPTX。

## 输入

无。所有内容由智能体根据 prompt 中的主题（物业费定价体系）和风格要求生成。

## 涉及技能

| 步骤 | 技能 | 作用 |
|------|------|------|
| 1️⃣ 入口分派 | [`sn-ppt-entry`](../../skills/sn-ppt-entry/SKILL.md) | 根据用户需求分派到具体的 PPT 生成模式 |
| 2️⃣ PPT 生成 | [`sn-ppt-standard`](../../skills/sn-ppt-standard/SKILL.md) | 标准模式：生成大纲、素材、分页 HTML，并合成 PPTX |

## 操作流程

直接向智能体发起：

```text
制作一个关于物业费定价体系的PPT，共26页，配色使用黑白配色，要求温馨柔和风格，物业管理人员用，物业委员会看
```

智能体经由 `sn-ppt-entry` 进入 `sn-ppt-standard`，依次产出：

1. 大纲与素材计划（`outline.json` / `asset_plan.json` / `info_pack.json` / `style_spec.json` / `task_pack.json`）
2. 26 页分页 HTML（含图片、图标与样式资源）
3. 截图合成的 PPTX

## 产物

- [`result/物业费定价体系_20260425_104934.pptx`](result/物业费定价体系_20260425_104934.pptx)：可直接打开的 PPTX 文件（由每页 HTML 截图合成）
- [`result/物业费定价体系_20260425_104934.zip`](result/物业费定价体系_20260425_104934.zip)：PPT 对应的原始分页 HTML 集合，便于二次编辑或直接网页预览

zip 解压后目录 `物业费定价体系_20260425_104934/` 内含：

- `pages/page_001.html ~ page_026.html`：每一页的 HTML 源码
- `assets/`：引用的样式与脚本（如 echarts.min.js）
- `images/`：引用的图片（jpg）
- `outline.json` / `asset_plan.json` / `info_pack.json` / `style_spec.json` / `task_pack.json`：生成过程中的中间产物（大纲、素材计划、样式规范等）

## 产物总览

```
result/
├── 物业费定价体系_20260425_104934.pptx   # 最终 PPT（可直接打开）
└── 物业费定价体系_20260425_104934.zip    # HTML 源集合压缩包
```
