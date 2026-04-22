---
name: generate-image
description: AI 图片生成（豆包 Seedream）。在研究报告中需要概念配图、场景示意图等非数据驱动的视觉内容时使用。通过 OpenAI 兼容接口调用，生成图片保存到本地并返回路径供 Markdown 引用。数据图表请用 Mermaid，不要用此 skill。
metadata:
  {
    "openclaw":
      {
        "emoji": "🎨",
        "primaryEnv": "ARK_API_KEY",
        "requires": { "bins": ["python3"], "env": ["ARK_API_KEY"] },
      },
  }
---

# generate-image - AI 图片生成

为研究报告生成概念性配图。适合：行业趋势示意图、技术架构概念图、场景展望图、封面图等**非数据驱动**的视觉内容。

**不适合**：数据图表（饼图、柱状图、折线图、时间线）→ 用 Mermaid 代码块直接写。

## API Key 配置

脚本通过环境变量 `ARK_API_KEY` 读取密钥。OpenClaw 会在每轮 agent 执行前把 `skills.entries.generate-image.apiKey` 注入到 `process.env.ARK_API_KEY`，结束后自动还原（见 [Skills Config](https://docs.openclaw.ai/tools/skills-config)）。

在 `~/.openclaw/openclaw.json` 中任选其一：

```json5
{
  skills: {
    entries: {
      "generate-image": {
        enabled: true,
        // 方式 A: 明文
        apiKey: "你的火山方舟 API Key",
        // 方式 B: 走 SecretRef（推荐，不落盘明文）
        // apiKey: { source: "env", provider: "default", id: "ARK_API_KEY" },
        // 可选：覆盖 base_url（走代理或其他兼容 /v1/images/generations 的服务）
        env: {
          ARK_BASE_URL: "https://ark.cn-beijing.volces.com/api/v3",
        },
      },
    },
  },
}
```

API Key 从火山方舟控制台 → API Key 管理 → 创建。未配置时 `python3 scripts/generate_image.py` 会以 `success: false` 退出并提示缺 `ARK_API_KEY`。

**沙箱场景**：若 agent 在 Docker sandbox 中执行（`agents.defaults.sandbox.*`），容器**不继承** host `process.env`。需同步配置：

```json5
{
  agents: {
    defaults: {
      sandbox: {
        docker: {
          env: { ARK_API_KEY: "...", ARK_BASE_URL: "..." },
        },
      },
    },
  },
}
```

或在自定义 sandbox 镜像里预置。

## 调用方式

```bash
python3 {baseDir}/scripts/generate_image.py "<prompt>" [选项]
```

## 参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `prompt` | 图片描述（必填，详见下方 Prompt 指南） | — |
| `--api-key` | API Key（可选，覆盖 `ARK_API_KEY`） | `$ARK_API_KEY` |
| `--base-url` | API 地址（可选，覆盖 `ARK_BASE_URL`） | `$ARK_BASE_URL` 或 `https://ark.cn-beijing.volces.com/api/v3` |
| `--model`, `-m` | 模型名称 | `doubao-seedream-5-0-260128` |
| `--size`, `-s` | 图片尺寸 | `2K` |
| `--output-dir`, `-o` | 保存目录 | 当前目录 |
| `--filename`, `-f` | 文件名 | `img_{timestamp}.png` |
| `--watermark` | 添加水印 | 不加 |

### 尺寸选项

| 值 | 说明 | 适用场景 |
|----|------|----------|
| `2K` | 默认，宽幅高清 | 报告正文配图（推荐） |
| `1024x1024` | 正方形 | 头像、图标 |
| `4K` | 超高清 | 需要放大查看的细节图 |

## 输出

```json
{
  "success": true,
  "file_path": "/absolute/path/to/img_1713200000000.png",
  "filename": "img_1713200000000.png",
  "revised_prompt": "模型优化后的 prompt",
  "model": "seedream-4-5-251128",
  "size": "2K"
}
```

生成后在报告中用 Markdown 引用：

```markdown
![图片描述](images/img_1713200000000.png)
```

## Prompt 指南

好的生图 prompt 应包含三个层次：

### 1. 内容（What）
描述画面中的主体和场景。要具体，不要抽象。

- 差：`"AI技术发展"`
- 好：`"一组互联的芯片节点从中央云服务器向边缘设备（手机、汽车、工厂传感器）辐射连接"`

### 2. 风格（How）
指定视觉风格、色调、渲染方式。

| 报告场景 | 推荐风格关键词 |
|----------|---------------|
| 行业趋势/宏观概览 | `科技感信息图风格, 蓝紫色调, 扁平化, 简洁线条` |
| 技术架构/方案 | `技术蓝图风格, 等距视角, 干净背景, 模块化布局` |
| 未来展望/愿景 | `未来概念艺术, 柔和光照, 开阔视野` |
| 商业/市场 | `商务插画风格, 专业配色, 现代设计` |
| 封面图 | `大气, 居中构图, 留白空间用于放标题` |

### 3. 构图（Where）
指定元素的空间关系和画面结构。

- `居中对称构图` / `从左到右流程` / `俯视角全景`
- `前景突出主体，背景虚化` / `留白在上方/下方`

### 完整示例

```
一幅科技感信息图，展示AI芯片产业链：左侧是芯片设计公司（ARM、NVIDIA的抽象logo），
中间是晶圆制造工厂的简化示意，右侧是终端应用场景（数据中心、自动驾驶、手机）。
整体采用深蓝色背景、浅蓝和白色线条连接，等距视角，扁平化风格，适合放在行业研究报告中。
```

## 使用原则

1. **一份报告 3-5 张为宜** — 不是每个章节都需要配图，选择最能增强理解的位置
2. **概念图，不是装饰** — 每张图都应该帮助读者理解一个具体概念，不是为了好看
3. **风格统一** — 同一份报告中的图片应使用相同的色调和风格关键词
4. **数据用 Mermaid** — 有具体数字的内容（市场份额、增长趋势、对比矩阵）用 Mermaid，不要用 AI 生图
