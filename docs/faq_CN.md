# SenseNova Skills 常见问题

本页汇总了使用 SenseNova Skills 过程中常见的接入与运行问题及解决办法。English version: [`faq.md`](faq.md)。

## Q：报错 400 message[1]. role must be user or assistant 怎么解决？

这是 Claude Code v2.1.154+ 引入的兼容性问题。新版本在请求中加入了 system role，而部分第三方 Router 不支持该角色，导致 400 报错。

![Claude Code 中的 400 role 报错](images/faq/cc-400-role-error.png)

> **注意：** 必须按照你最初安装 Claude Code 的方式来执行回退操作。如果你使用 **cc-switch** 管理 Provider，请在 cc-switch 中为对应 Provider 的 env 字段添加 `DISABLE_AUTOUPDATER=1`，否则 cc-switch 可能会自动拉取最新版本覆盖回退。

1. 回退 Claude Code 至 v2.1.153：

   ```bash
   npm install -g @anthropic-ai/claude-code@2.1.153
   ```

2. 关闭 Claude Code 自动更新：

   ```bash
   export DISABLE_AUTOUPDATER=1
   ```

   ```json
   {
     "env": {
       "DISABLE_AUTOUPDATER": "1"
     }
   }
   ```

回退完成后，Claude Code 会以 v2.1.153 启动，请求恢复正常：

![回退到 v2.1.153 后正常运行的 Claude Code](images/faq/cc-downgrade-steps.png)

## Q：PPT 生成在复杂页面上超时怎么办？

`sn-ppt-standard` 会把每一页幻灯片生成为一份完整的 HTML 页面。对于内容较重的 PPT，例如 11 页且包含复杂布局、图表和细致样式的页面，默认的 LLM 超时时间可能不够。

运行 PPT 流程前，可以调大文本与视觉模型的超时时间：

```bash
export SN_TEXT_TIMEOUT=600
export SN_VISION_TIMEOUT=600
```

也可以设置共享兜底超时时间：

```bash
export SN_CHAT_TIMEOUT=600
```

如果同时设置了 `SN_TEXT_TIMEOUT` 和 `SN_CHAT_TIMEOUT`，文本 LLM 调用会优先使用 `SN_TEXT_TIMEOUT`。如果同时设置了 `SN_VISION_TIMEOUT` 和 `SN_CHAT_TIMEOUT`，视觉模型调用会优先使用 `SN_VISION_TIMEOUT`。

## Q：中文信息图中部分文字不够清晰怎么办？

使用 `sn-infographic` 时，可以增加生成轮数，让技能启用 VLM review 检查生成结果，并优先选择视觉问题更少的输出：

```text
生成一张关于<主题>的中文信息图 max_rounds=3 output_mode=verbose
```

当 `max_rounds=1` 时，VLM review 会被跳过。将 `max_rounds` 设置为 `2` 或更高，可以让流程有机会发现中文乱码、重复/重叠文字、文图排版不清晰等问题。

## Q：图片生成质量问题怎么解决？

图片生成质量问题（文字乱码/错别字、排版无美感、人物结构错误等）需等待新版模型上线，新版本将针对图片生成质量进行重点优化。

## Q：推理/代码能力与稳定性问题怎么解决？

SenseNova 6.7 Flash-Lite 参数量较小，在复杂推理、大规模代码任务和长上下文场景下能力有限，可能出现降智、死循环、重复输出、任务偷懒等情况。可以尝试切换使用 `deepseek-v4-pro`，该类场景下表现更稳定。

## Q：限流与额度问题怎么解决？

当前 SenseNova Token Plan 处于免费试用阶段，受限于免费额度和整体负载，高峰期可能出现以下情况：

- **429 限流：** 免费额度为 1,500 次 / 5 小时（滑动窗口），超出后自动限流，5 小时后自动恢复
- **FREE_QUOTA_EXHAUSTED：** 免费额度耗尽后 endpoint 暂时 inactive，等待窗口重置后恢复
- **延迟高 / 无响应：** 高峰期并发量大时可能出现排队

**后续提升预期：** 付费 Token Plan 正在筹备中，上线后将提供更高并发配额、更大调用量和更稳定的服务质量。

## Q：什么时候付费 Token Plan？

付费 Token Plan 正在筹备中，预计后续上线，具体时间请关注官方公告。

## Q：不支持 Anthropic 格式怎么办？

SenseNova 同时支持 Anthropic Messages 格式（通过 `https://token.sensenova.cn`）和 OpenAI 兼容格式（通过 `https://token.sensenova.cn/v1`）。Claude Code 可直接使用 Anthropic 格式接入，无需协议转换。具体配置方法请参阅 [SenseNova-Skills 接入 Agent 教程](https://sensetime.feishu.cn/wiki/EgmIwUnOpiXVPIkGUdVcAHTNnGd) 中的 Provider 配置章节。

## Q：模型名不识别怎么办？

如果遇到 `The supported API model names are ... but you passed ...` 类错误，请先确认模型名拼写是否正确。SenseNova 当前支持的模型名为：

- `sensenova-6.7-flash-lite` — SenseNova 6.7 Flash-Lite，轻量快速
- `sensenova-u1-fast` — SenseNova U1 Fast，推理增强

注意：模型名区分大小写，请确保与上述名称完全一致。

## Q：U1 Fast 接入报 404 怎么办？

`sensenova-u1-fast` 是图片生成模型，不通过 `/v1/chat/completions` 端点调用。如需使用 U1 Fast 生成图片，请通过 SenseNova Skills 中的 `sn-image-generate` 等工具调用，或使用专门的图片生成端点，而非标准的 Chat Completions 接口。

## Q：报错 401 怎么解决？

401 表示 API Key 无效或未正确设置。请检查：

- API Key 是否正确复制（确保无多余空格或换行）
- 是否在 [SenseNova 平台](https://www.sensenova.cn/token-plan) 已获取有效 Key
- Authorization 头格式是否为 `Bearer sk-xxx`

如确认 Key 无误仍报 401，建议重新生成 Key 后重试。

---

> **Provider 配置参考：** 如需了解 SenseNova 模型的 Provider 配置方法（cc-switch、Claude Code、Codex 等），请参阅 [SenseNova-Skills 接入 Agent 教程](https://sensetime.feishu.cn/wiki/EgmIwUnOpiXVPIkGUdVcAHTNnGd)。
