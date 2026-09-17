# PPT 可选能力选择规则

普通搜索、图片搜索和图片生成都按同一顺序选择：

1. **Native**：查看当前 Agent 实际暴露的等价工具。工具注册只表示
   `present_unverified`；有 config/health 成功证据，或任务中的一次实际调用成功后，才算
   available 并优先使用。
2. **Bundled**：原生工具不存在，或一次实际调用已经确认不可用时，解析同级
   `sn-ppt-tools`，检查对应脚本和环境变量后调用。
3. **None**：内置工具未配置或调用失败时停止使用该能力，不伪造结果，不持续重试。

“原生可用”指当前 runtime 确实暴露了对应工具并能完成配置检查或实际调用，不根据工具
名称猜测。工具明确缺少配置时记为 `misconfigured`；没有检查手段时保持
`present_unverified`，实际任务需要该能力时可以尝试一次，失败后转 Bundled。
原生工具名称因 runtime 而异，例如普通/图片搜索可能是同一个带类型参数的工具。

## 路径

各 PPT Skill 从自己的 `SKILL_DIR` 取得同级 skills 目录：

```text
PPT_TOOLS_DIR = dirname(SKILL_DIR)/sn-ppt-tools
```

`sn-ppt-tools` 随 PPT 整包交付，不检查“是否安装”，也不扫描其他仓库位置。

## 状态记录

使用某项能力后，在已有 `task_pack.state.capabilities` 中更新对应小项：

```json
{
  "web_search": {
    "source": "native",
    "status": "available",
    "last_error": null,
    "updated_at": "ISO-8601"
  }
}
```

- `source` 只能是 `native`、`bundled` 或 `none`。
- `status` 使用 `available`、`unavailable` 或 `failed`。
- 只记录非敏感错误摘要；不得记录 key、Authorization header 或完整请求。
- 能力状态用于恢复和定位，不得反向改变 Story、输出出口或设计丰富度。

## 无能力路径

- 普通搜索不可用：PPT 流程跳过外部 Research，Story 基于用户材料继续，并明确事实覆盖
  边界。独立 Deep Research 仍按自己的前置条件处理。
- 图片搜索按 `native image search -> bundled image search -> none` 处理；两层都不可用或没有
  合格结果时，真实对象进入无图、CSS、SVG、Canvas 或原生图表回退，**不得自动改用生图仿真**。
- 图片生成按 `native generation -> bundled generation -> none` 处理；两层都不可用或失败时，
  使用无图版式继续，**不得自动改成搜图**。搜索与生成之间只有在输出 Skill 重新判断素材真实性
  类别、明确记录新的视觉方案仍合规时才能切换，不能作为能力失败后的隐式跨模态 fallback。
- Creative 的原生与内置图片生成都不可用：只停止 Creative 出口，保留
  `task_pack.json`、`info_pack.json`、`outline.md`、visual plan 和现有页面；状态写
  `partial`，不得自动切换出口。

无图片时必须重新组织版式，不保留空图片框、破图、占位图或“待生成”文字。
