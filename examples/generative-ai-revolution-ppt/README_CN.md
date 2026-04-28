# 单技能示例：生成式 AI 革命 PPT 生成

[English version](README.md)

本示例演示如何使用 SenseNova-Skills 中的 **PPT 生成** 能力，仅凭一句指令、不提供任何输入文件，让智能体根据风格要求和受众场景，从零生成一份可直接打开的 PPTX。

## 输入

不附带输入文件。

## 操作说明

直接向智能体发起：

```text
制作一份 8 页中文 PPT，标题为“生成式AI革命：从聊天机器人到内容生产引擎”。
整体风格采用“科技展览 × 高端杂志”，要求色彩鲜明、视觉冲击力强、每页版式不同。
内容覆盖文本生成、图像生成、视频生成、代码生成、办公自动化、商业应用与未来趋势，
并以具有号召力的结尾页收束。
```

智能体依次产出：

1. 任务与风格元数据（`info-pack.json`、`style-spec.json`、`task-pack.json`、`storyboard.json`）
2. `pages/` 下的 8 页 HTML 源文件
3. `images/` 下的引用图片
4. `review.md` 中的审查记录

## 产物

- [`result/生成式AI革命_PPTX_20260416_2125.pptx`](result/生成式AI革命_PPTX_20260416_2125.pptx)：可直接打开的 PPTX
- [`result/生成式AI革命_PPTX_20260416_2125.zip`](result/生成式AI革命_PPTX_20260416_2125.zip)：便于二次编辑的源码压缩包

zip 解压后目录 `生成式AI革命_PPTX_20260416_2125/` 内含：

- `pages/page_01.html ~ page_08.html`：每一页的 HTML 源码
- `images/`：引用图片资源
- `info-pack.json` / `review.md` / `storyboard.json` / `style-spec.json` / `task-pack.json`：中间产物与审查说明

## 产物总览

```text
result/
├── 生成式AI革命_PPTX_20260416_2125.pptx   # 最终 PPT（可直接打开）
└── 生成式AI革命_PPTX_20260416_2125.zip    # HTML 源和中间产物集合压缩包
```
