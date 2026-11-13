# Image Studio 图片工作台

简体中文 | [English](sn-image-studio.md)

[`sn-image-studio`](../skills/sn-image-studio/SKILL.md) 是本地双语网页工作台，支持浏览风格案例、
编辑提示词、上传输入图片，以及使用 SenseNova U1.5 生图或改图。它自带独立图片客户端，无需安装 `sn-image-base`。

## 选择工作方式

| 工作方式 | 执行流程 |
| --- | --- |
| 直接生图或改图 | 网页提交当前提示词与有序输入图，Studio 直接调用图片客户端，无需 Agent。 |
| 按需求改写提示词 | 选择 Codex、Claude Code 或 Hermes，在独立 ACP 会话中改写提示词，并可选择通过 Studio 继续生图。 |
| 发布已有案例 | 将提示词、效果图和案例元数据导入本地案例库。 |

Agent 的登录与模型配置和 SenseNova 生图 Key 是两套配置。只配好对话模型不会自动获得生图权限。
当前 ACP 选项为 `codex`、`claude` 和 `hermes`；OpenClaw 不是 Studio 的 ACP 选项。

## 安装

使用 Python 3.10+，安装完整的 `skills/sn-image-studio/` 目录，保留 `assets/`、`references/`、
`scripts/` 和 `requirements.txt`，也可直接在本仓库中运行。以下示例使用 macOS/Linux/WSL Shell，
从仓库根目录开始；若已安装到 Agent 的技能目录，将 `SKILL_DIR` 替换为对应绝对路径。

```bash
export SKILL_DIR="$PWD/skills/sn-image-studio"
export STUDIO_ENV="$PWD/.env"
python3 -m venv .venv-image-studio
. .venv-image-studio/bin/activate
python -m pip install -r "$SKILL_DIR/requirements.txt"
python "$SKILL_DIR/scripts/catalog.py" validate
```

后续使用同一个 Python 环境运行 Studio。新开 Shell 时重新设置两个路径变量。
`STUDIO_ENV` 是本指南使用的 Shell 变量，不是 Studio 会自动读取的配置变量。

## 配置生图服务

通过网页配置表单或编辑选定的 `.env` 配置服务。缺少凭据时，网页打开后会显示配置表单。
Key 只填写到表单或配置文件中，不需要发送到聊天里。

根据签发生图 Key 的账号地区选择对应地址：

| 账号地区 | Base URL | 平台文档 |
| --- | --- | --- |
| 海外 | `https://token.sensenova.ai/v1` | [海外平台文档](https://platform.sensenova.ai/docs) |
| 中国内地 | `https://token.sensenova.cn/v1` | [内地平台文档](https://platform.sensenova.cn/docs) |

以下为中国内地账号的图片专属配置示例，海外账号请替换 Base URL：

```dotenv
SN_IMAGE_GEN_BASE_URL="https://token.sensenova.cn/v1"
SN_IMAGE_GEN_API_KEY="your-image-api-key"
SN_IMAGE_GEN_MODEL="sensenova-u1.5-lite"
SN_IMAGE_GEN_MODEL_TYPE="sensenova"
```

账号须具备所选 U1.5 模型的调用权限。Studio 按以下顺序解析配置：

| 配置项 | 回退顺序 |
| --- | --- |
| API Key | `SN_IMAGE_GEN_API_KEY` → `SN_API_KEY`；没有内置 Key |
| Base URL | `SN_IMAGE_GEN_BASE_URL` → `SN_BASE_URL` → `https://token.sensenova.cn/v1` |
| 模型 | `SN_IMAGE_GEN_MODEL` → `sensenova-u1.5-lite` |
| 协议 | `SN_IMAGE_GEN_MODEL_TYPE` → `sensenova` |

默认读取命令当前目录的 `.env`，不会自动读取启动它的 Agent 主目录配置。为各命令传入同一
`--env-file` 绝对路径。文件中的同名值先覆盖进程环境，再按上述回退顺序解析；网页保存图片专属覆盖值，保留其他设置。

## 打开工作台

不使用 ACP Agent、只直接生图时：

```bash
python "$SKILL_DIR/scripts/studio.py" doctor --env-file "$STUDIO_ENV"
python "$SKILL_DIR/scripts/studio.py" serve --background --language zh-CN --env-file "$STUDIO_ENV"
```

`doctor` 会报告缺少的配置或依赖，但不验证服务商登录，也不发起生图请求。缺少 Key 时仍可打开网页完成配置。
未指定 `--harness` 时不能提交改写需求，完成图片配置后可直接生成。

需要 Agent 按需求改写时，先按 [ACP 接入说明](../skills/sn-image-studio/references/acp.md)
安装并认证**一种**选定的 ACP 服务：

| 选项 | ACP 服务准备 |
| --- | --- |
| `codex` | `npm install -g @agentclientprotocol/codex-acp@2.5.0` |
| `claude` | `npm install -g @agentclientprotocol/claude-agent-acp@0.100.0` |
| `hermes` | 安装 Hermes 及其 ACP 依赖，执行 `hermes acp --check` 检查。 |

npm 适配器还需要兼容的 Node.js/npm 环境；认证步骤见接入说明中对应适配器的文档。
以下以 Hermes 为例：

```bash
python "$SKILL_DIR/scripts/studio.py" doctor --harness hermes --env-file "$STUDIO_ENV"
python "$SKILL_DIR/scripts/studio.py" serve --background --harness hermes --language zh-CN --env-file "$STUDIO_ENV"
```

使用其他 Agent 时，一致替换两条命令中的 `hermes`。若 4318 端口已运行仅直接生图或配置不同的 Studio，
使用 `--port 4319` 选择空闲端口，或先停止该实例再切换。Studio 不会因为其他 Agent 已安装就自动选择或切换过去。

打开返回的完整 `url`，包括语言参数；默认地址为 `http://127.0.0.1:4318/`。
英文使用 `--language en`，`auto` 按已保存偏好或浏览器语言选择。网页也提供语言切换，两种语言各自保存独立提示词草稿。

## 使用与验收

1. 选择风格案例，查看效果图、提示词及必需输入。案例示例图仅用于展示，不会自动作为模型输入。
2. 按顺序上传所需图片并确认各自角色。无输入图时走文生图，有输入图时走图片编辑。
3. 直接编辑提示词，或提交“保留纸雕风格，把场景换成桂林，标题文字保持原样”等需求，并选择改写后是否生图。
4. 检查任务结果与图片预览。仅改写成功不等于生图成功；后续手动修改会被保留，过期改写会作为候选结果。

默认分辨率为 2K；本客户端的 4K 选项仅适用于 `sensenova-u1.5-lite`，图片编辑使用 `size=auto`。
详见[图片 API 说明](../skills/sn-image-studio/references/image-api.md)。按案例改写不保证与示例图完全一致。

任务由后端执行，关闭网页或启动它的对话不会停止任务，重新打开网页可恢复结果展示。
服务重启则不同：未完成任务会标记失败并提示结果可能未确认，不会自动重放付费请求。
结果不确定或超时时，先检查原任务，再决定是否重新提交。

运行文件默认位于 `~/.cache/sn-image-studio/<port>/`，可用 `--data-dir` 更改。
前台模式（不传 `--background`）可用 Ctrl+C 停止；后台模式记录启动返回的 `pid`，
确认没有活动任务后仅停止该进程。关闭浏览器不会停止服务。

发布已有提示词和效果图时，按[案例编写指南](../skills/sn-image-studio/references/case-authoring.md)
使用 `catalog.py add`，再执行 `catalog.py validate`。保留原始提示词和公开署名，
不要把私有来源链接或内部备注放入发布的案例库。
