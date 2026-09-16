---
name: sn-ppt-tools
description: Use when another PPT Skill needs web search, image search or download, or image generation and the host Agent's equivalent native capability is absent or has failed.
metadata:
  project: SenseNova-Skills
  tier: 0
  category: infrastructure
  user_visible: false
---

# sn-ppt-tools

这是 PPT Skill 整包自带的备用工具，不是独立内容生产流程。调用前先读
`references/capability-policy.md`。宿主 Agent 的等价原生工具始终优先；只有原生能力
不存在或一次实际调用确认不可用时，才调用这里的脚本。

## 持久配置

四个脚本每次启动都会自动加载一个用户级 `.env`：

1. 设置了 `SN_PPT_ENV_FILE` 时读取该文件；
2. OpenClaw 读取 `~/.openclaw/.env`；
3. 其他环境默认读取 `~/.hermes/.env`。

已有进程环境变量优先，`.env` 只补充缺失项。不要把 secret 写进 Skill 目录、workspace、
命令行、prompt 或 task pack。完整模板和缺失项检查通过 `sn-ppt-doctor` 查看。

## 普通搜索

```bash
python3 "$PPT_TOOLS_DIR/scripts/web_search.py" "QUERY" --num 10
```

配置：

- URL：`SN_PPT_WEB_SEARCH_URL`；否则
  `SN_PPT_SEARCH_BASE_URL` / `SERPER_BASE_URL` 加 `/search`。
- Key：`SN_PPT_WEB_SEARCH_API_KEY` -> `SN_PPT_SEARCH_API_KEY` ->
  `SERPER_API_KEY`。

## 图片搜索与下载

```bash
python3 "$PPT_TOOLS_DIR/scripts/image_search.py" "QUERY" --num 10

python3 "$PPT_TOOLS_DIR/scripts/fetch_image.py" \
  "https://example.com/image.png" \
  --deck-dir "$DECK_DIR" \
  --output "assets/image.png" \
  --referer "https://example.com/source-page"
```

图片搜索配置：

- URL：`SN_PPT_IMAGE_SEARCH_URL`；否则
  `SN_PPT_SEARCH_BASE_URL` / `SERPER_BASE_URL` 加 `/images`。
- Key：`SN_PPT_IMAGE_SEARCH_API_KEY` -> `SN_PPT_SEARCH_API_KEY` ->
  `SERPER_API_KEY`。

先根据搜索元数据选择候选，再下载选中的图片。不得把远程 URL 直接留在最终 deck。

## 图片生成

```bash
python3 "$PPT_TOOLS_DIR/scripts/image_generate.py" \
  --prompt-file "$DECK_DIR/pages/page_001.prompt.txt" \
  --deck-dir "$DECK_DIR" \
  --output "pages/page_001.png" \
  --size "2752x1536"
```

配置：

- URL：`SN_PPT_IMAGE_GEN_URL`；否则
  `SN_IMAGE_GEN_BASE_URL` / `SN_BASE_URL` 加 `/images/generations`。
- Key：`SN_PPT_IMAGE_GEN_API_KEY` -> `SN_IMAGE_GEN_API_KEY` ->
  `SN_API_KEY`。
- Model：`SN_PPT_IMAGE_GEN_MODEL` -> `SN_IMAGE_GEN_MODEL`。

只支持 OpenAI/SenseNova 兼容的同步 `POST /images/generations` 协议，响应可以是
`data[].url` 或 `data[].b64_json`。不在这里扩展其他 provider。

## 输出与失败

- 成功输出单行 JSON，`status` 为 `ok`。
- 缺少配置输出 `status=unavailable`，退出码为 2。
- 请求或落盘失败输出 `status=failed`，退出码为 1。
- 所有图片只能写入调用方给定的绝对 `DECK_DIR` 内。
- Key 不通过命令行传递，不写入输出、日志、task pack 或 deck 文件。
- 同一能力调用失败后不循环重试；由调用 Skill 按 policy 继续无工具路径。
