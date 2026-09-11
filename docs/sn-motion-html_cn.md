# Motion HTML 网页故事

简体中文 | [English](sn-motion-html.md)

[`sn-motion-html`](../skills/sn-motion-html/SKILL.md) 用于制作沉浸式、随滚动推进的网页故事，
适合品牌故事、产品展示、历史时间线、行业介绍和虚构世界等需要让镜头在同一空间中连续
移动的内容。不用于普通网页应用或单纯的自动播放视频页面。

## 产物

- 可复用的项目，而不是一次性的 HTML 文件。
- 以 `content/story.json` 为内容源的章节和文案结构。
- 连续媒体舞台：场景片段 → 连接片段 → 下一个场景。
- 风格一致的静帧、Seedance 场景 / 连接视频、海报和响应式界面。
- 视频不可用时仍可工作的 reduced-motion 静帧路径。

## 环境要求

- Python 和 FFmpeg，用于媒体标准化、校验和 contact sheet。
- 可用的图像生成能力，用于静帧一致性检查。
- 兼容 Ark 的 Seedance 视频生成账号。
- 项目本地 `.env`；静态托管时不得暴露该文件。

模板默认配置为：

```dotenv
ARK_API_KEY=
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
SEEDANCE_MODEL=doubao-seedance-2-5-260628
```

模型名和参数以服务商当前官方文档为准。

## 初始化项目

使用指定的视觉风格和界面预设初始化项目：

```bash
python scripts/init_project.py /absolute/output/path \
  --title "故事标题" \
  --style cinematic \
  --ui folio
```

可选风格为 `anime`、`cinematic`、`cgi`；界面预设为 `folio`、`caption`、`graphic`。
交付前需要替换模板中的示例故事和 manifest。

## 制作流程

1. 明确受众、事实范围、视觉语言、设备目标、声音策略和预算。
2. 对事实型内容先研究，并把来源笔记与展示文案分开。
3. 先产出章节蓝图、镜头计划、连接计划和角色 / 产品身份设定。
4. 分别取得视觉风格审批和内容 / 镜头计划审批。
5. 先生成少量静帧作为一致性检查，通过后再生成完整静帧集。
6. 先 dry-run 视频 manifest 和一段代表性片段。
7. 第一次付费视频请求前，单独取得明确授权。
8. 生成场景、提取真实边界帧、生成连接片段、标准化媒体并完成浏览器验收。

创意审批不等于付费视频生成授权。认证、权限、计费或模型未开通错误不应自动重试。

## 常用命令

以下命令在初始化后的项目根目录执行：

```bash
python scripts/seedance_pipeline.py . plan
python scripts/seedance_pipeline.py . all --workers 4
python scripts/verify_media.py .
python scripts/contact_sheet.py .
python scripts/serve_project.py . --port 8080
```

交付前检查媒体尺寸、帧率、编码、时长、浏览器导航、正向与反向滚动、视频缺失回退和
reduced-motion 行为，并提供预览地址、项目路径、媒体目录、服务商配置和剩余阻塞项。
