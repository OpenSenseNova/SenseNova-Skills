#!/usr/bin/env bash
# openclaw-deep-research 安装脚本
#
# 步骤：
#   1. 在 plugin 根目录执行 npm install && npm run build
#   2. 5 个专家 agent workspace → ~/.openclaw/workspace-<id>/
#   3. skill 集（含 _search-common） → ~/.openclaw/skills/
#   4. 通过 merge_config.py 自动合并到 ~/.openclaw/openclaw.json（自动备份）
#
# 可选参数：
#   --force        覆写已存在的 agents.list 条目和 workspace AGENTS.md
#   --dry-run      仅打印合并 diff，不改 openclaw.json（workspace 和 skill 仍会复制）
#   --config PATH  openclaw.json 路径（覆盖 $OPENCLAW_CONFIG_PATH / 默认路径）

set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OC_HOME="${OPENCLAW_STATE_DIR:-$HOME/.openclaw}"
WORKSPACE_ROOT="$OC_HOME"
SKILLS_DIR="$OC_HOME/skills"

FORCE=0
DRY_RUN=0
CONFIG_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)    FORCE=1 ;;
    --dry-run)  DRY_RUN=1 ;;
    --config)   CONFIG_PATH="$2"; shift ;;
    -h|--help)
      sed -n '2,/^$/p' "$0" | sed 's/^# \{0,1\}//'
      exit 0 ;;
    *) echo "未知参数: $1" >&2; exit 2 ;;
  esac
  shift
done

echo "=> Plugin dir:    $PLUGIN_DIR"
echo "=> OpenClaw home: $OC_HOME"
echo

if ! command -v npm >/dev/null 2>&1; then
  echo "[err] 未找到 npm，无法构建 plugin" >&2
  exit 1
fi

echo "=> 构建 plugin..."
(cd "$PLUGIN_DIR" && npm install && npm run build)
echo

mkdir -p "$SKILLS_DIR"

# ------------------------------------------------------------------------
# 1. 专家 workspace
# ------------------------------------------------------------------------
for agent in scout-agent plan-agent research-agent review-agent report-agent; do
  target="$WORKSPACE_ROOT/workspace-$agent"
  mkdir -p "$target"
  src="$PLUGIN_DIR/workspaces/$agent/AGENTS.md"
  dst="$target/AGENTS.md"
  if [ -f "$dst" ] && [ "$FORCE" -eq 0 ]; then
    echo "[skip] $dst 已存在（--force 可覆写）"
  else
    cp "$src" "$dst"
    echo "[ok]   wrote $dst"
  fi
done

# ------------------------------------------------------------------------
# 2. Skills（controller skill + 8 辅助 skill + _search-common）
# ------------------------------------------------------------------------
SKILL_NAMES=(
  deep-research
  _search-common
  search-code
  search-academic
  search-social-cn
  search-social-en
  report-format-discovery
  research-report
  generate-image
)

SKIPPED_SKILLS=()
for skill in "${SKILL_NAMES[@]}"; do
  src="$PLUGIN_DIR/skills/$skill"
  dst="$SKILLS_DIR/$skill"
  if [ ! -d "$src" ]; then
    echo "[warn] skill $skill 不存在于 plugin 目录，跳过"
    continue
  fi
  if [ -d "$dst" ] && [ "$FORCE" -eq 0 ]; then
    echo "[skip] $dst 已存在（升级 plugin 时不会刷新文件，需 --force 才覆写）"
    SKIPPED_SKILLS+=("$skill")
  else
    rm -rf "$dst"
    cp -r "$src" "$dst"
    # 清理 python 缓存，避免旧 .pyc 残留
    find "$dst" -type d -name "__pycache__" -prune -exec rm -rf {} +
    echo "[ok]   copied $skill -> $dst"
  fi
done

if [ "${#SKIPPED_SKILLS[@]}" -gt 0 ]; then
  echo
  echo "[!!] 共跳过 ${#SKIPPED_SKILLS[@]} 个已存在的 skill：${SKIPPED_SKILLS[*]}"
  echo "     如这是升级安装，请重跑 ./scripts/install.sh --force 让 plugin 文件覆盖到最新版"
fi

# ------------------------------------------------------------------------
# 3. 合并 openclaw.json
# ------------------------------------------------------------------------
MERGE_ARGS=()
[ "$FORCE"   -eq 1 ] && MERGE_ARGS+=(--force)
[ "$DRY_RUN" -eq 1 ] && MERGE_ARGS+=(--dry-run)
[ -n "$CONFIG_PATH" ] && MERGE_ARGS+=(--config "$CONFIG_PATH")

if ! command -v python3 >/dev/null 2>&1; then
  echo "[err] 未找到 python3，无法自动合并 openclaw.json" >&2
  echo "      请手动执行：python3 $PLUGIN_DIR/scripts/merge_config.py" >&2
  exit 1
fi

echo
echo "=> 运行 merge_config.py..."
if [ "${#MERGE_ARGS[@]}" -gt 0 ]; then
  python3 "$PLUGIN_DIR/scripts/merge_config.py" "${MERGE_ARGS[@]}"
else
  python3 "$PLUGIN_DIR/scripts/merge_config.py"
fi

echo
echo "=> 完成。重启 openclaw：openclaw gateway restart"
echo "=> 验证：openclaw agents list   ；openclaw skills list | grep deep-research"
