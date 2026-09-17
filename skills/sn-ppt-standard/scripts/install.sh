#!/usr/bin/env bash
# ============================================================================
# sn-ppt-standard · 环境安装脚本(让 skill 自包含:一键装齐运行所需的全部依赖)
#
# 装什么(四块,缺一不可):
#   1) normalize venv  —— stage_materials.py 内部文本 worker 使用 markitdown/pdfminer/openpyxl
#   2) pymupdf(fitz)   —— 扫描 PDF rasterize 成页图(交 vision 兜底);装进渲染环境
#   3) OFL 字体包      —— 从官方项目获取中文/拉丁开源字体到 ~/.fonts
#   4) FontTools/Brotli/Pillow —— 裁剪 Deck 自带 WOFF2 + 生成 Review 联系表
#   5) Playwright Chromium —— render.py 无头渲染 HTML→PNG
#   (系统 .so 缺失时 render.py 会自动从 ~/pwdeps/lib 补,见 §5 提示)
#
# 用法:
#   bash scripts/install.sh                 # 全装
#   bash scripts/install.sh normalize       # 只装解析 venv
#   bash scripts/install.sh fonts chromium  # 只装字体+浏览器
#
# 产物路径(可用环境变量覆盖):
#   NORMALIZE_VENV   默认 ~/.cache/sn-ppt-standard/venv-normalize
#   FONTS_DIR        默认 ~/.fonts
#   PLAYWRIGHT_BROWSERS_PATH 默认 ~/.cache/ms-playwright
# 装完打印一行 `export NORMALIZE_PY=...`,供当前运行环境使用。
# ============================================================================
set -uo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUITE_FONTS_DIR="${SUITE_FONTS_DIR:-$HERE/../../../fonts}"
BUNDLED_FONTS_DIR="${BUNDLED_FONTS_DIR:-$HERE/../../../../fonts}"

NORMALIZE_VENV="${NORMALIZE_VENV:-$HOME/.cache/sn-ppt-standard/venv-normalize}"
FONTS_DIR="${FONTS_DIR:-$HOME/.fonts}"
export PLAYWRIGHT_BROWSERS_PATH="${PLAYWRIGHT_BROWSERS_PATH:-$HOME/.cache/ms-playwright}"
PYBIN="${PYBIN:-python3}"
PPT_FONT_DOWNLOADS="${PPT_FONT_DOWNLOADS:-1}"
GOOGLE_FONTS_REV="2796410152d4f9524b68ed46e69c1b60f8e0f7c3"
NORMALIZE_PACKAGES=(
  "markitdown==0.1.6"
  "pdfminer.six==20260107"
  "openpyxl==3.1.5"
  "python-docx>=1.1,<2"
  "python-pptx>=1.0,<2"
  "pypdf>=5,<7"
  "cairosvg>=2.7,<3"
  "pillow-heif>=0.22,<2"
  "lxml==6.1.1"
  "mammoth==1.11.0"
)

log(){ echo "[install] $*"; }

install_normalize(){
  log "1) normalize venv → $NORMALIZE_VENV"
  if command -v uv >/dev/null 2>&1; then
    uv venv "$NORMALIZE_VENV" >/dev/null 2>&1 || true
    uv pip install --python "$NORMALIZE_VENV/bin/python" "${NORMALIZE_PACKAGES[@]}"
  else
    "$PYBIN" -m venv "$NORMALIZE_VENV"
    "$NORMALIZE_VENV/bin/python" -m pip install -q --upgrade pip
    "$NORMALIZE_VENV/bin/python" -m pip install -q "${NORMALIZE_PACKAGES[@]}"
  fi
  # 冒烟:import 三个关键库
  "$NORMALIZE_VENV/bin/python" - <<'PY' && log "  normalize venv OK"
import markitdown, pdfminer, openpyxl
print("  imports ok:", markitdown.__name__, pdfminer.__name__, openpyxl.__name__)
PY
}

install_pymupdf(){
  log "2) pymupdf(fitz) → 当前渲染解释器 ($PYBIN)"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PYBIN" pymupdf >/dev/null 2>&1 || "$PYBIN" -m pip install -q pymupdf
  else
    "$PYBIN" -m pip install -q pymupdf
  fi
  "$PYBIN" -c "import fitz; print('  fitz ok', fitz.__doc__[:30])" 2>/dev/null && log "  pymupdf OK" || log "  ⚠️ pymupdf 装失败(扫描PDF rasterize 兜底不可用)"
}

install_fonts(){
  log "3) OFL 字体包 → $FONTS_DIR"
  mkdir -p "$FONTS_DIR"
  local packaged_count=0 packaged_dir packaged_font
  for packaged_dir in "$SUITE_FONTS_DIR" "$BUNDLED_FONTS_DIR"; do
    [ -d "$packaged_dir" ] || continue
    for packaged_font in "$packaged_dir"/*.ttf "$packaged_dir"/*.otf; do
      [ -f "$packaged_font" ] || continue
      cp -f "$packaged_font" "$FONTS_DIR/"
      packaged_count=$((packaged_count + 1))
    done
  done
  log "  已安装 $packaged_count 个随包开源字体"
  # 优先复用宿主已有 Noto SC；其余字体按官方 OFL 源补齐。
  local found=0 src f
  for src in "$HOME/.fonts" /usr/share/fonts /mnt/afs/*/.fonts; do
    for f in "$src"/*Noto*SC* "$src"/**/*Noto*SC*; do
      [ -f "$f" ] && { cp -n "$f" "$FONTS_DIR/" 2>/dev/null && found=1; }
    done
  done
  if [ "$PPT_FONT_DOWNLOADS" != "0" ]; then
    local base="https://raw.githubusercontent.com/google/fonts/$GOOGLE_FONTS_REV/ofl"
    local downloads=(
      "NotoSansSC.ttf|$base/notosanssc/NotoSansSC%5Bwght%5D.ttf"
      "NotoSerifSC.ttf|$base/notoserifsc/NotoSerifSC%5Bwght%5D.ttf"
      "IBMPlexMono-Regular.ttf|$base/ibmplexmono/IBMPlexMono-Regular.ttf"
      "IBMPlexMono-SemiBold.ttf|$base/ibmplexmono/IBMPlexMono-SemiBold.ttf"
      "Archivo.ttf|$base/archivo/Archivo%5Bwdth%2Cwght%5D.ttf"
      "Fraunces.ttf|$base/fraunces/Fraunces%5BSOFT%2CWONK%2Copsz%2Cwght%5D.ttf"
      "Spectral-Regular.ttf|$base/spectral/Spectral-Regular.ttf"
      "Spectral-Bold.ttf|$base/spectral/Spectral-Bold.ttf"
      "Xiaolai-Regular.ttf|https://github.com/lxgw/kose-font/releases/download/v3.126/Xiaolai-Regular.ttf"
      "MaShanZheng-Regular.ttf|$base/mashanzheng/MaShanZheng-Regular.ttf"
      "ZCOOLKuaiLe-Regular.ttf|$base/zcoolkuaile/ZCOOLKuaiLe-Regular.ttf"
      "ZCOOLQingKeHuangYou-Regular.ttf|$base/zcoolqingkehuangyou/ZCOOLQingKeHuangYou-Regular.ttf"
      "ZhiMangXing-Regular.ttf|$base/zhimangxing/ZhiMangXing-Regular.ttf"
      "LongCang-Regular.ttf|$base/longcang/LongCang-Regular.ttf"
      "LiuJianMaoCao-Regular.ttf|$base/liujianmaocao/LiuJianMaoCao-Regular.ttf"
      "PatrickHand-Regular.ttf|$base/patrickhand/PatrickHand-Regular.ttf"
      "Caveat.ttf|$base/caveat/Caveat%5Bwght%5D.ttf"
      "ArchitectsDaughter-Regular.ttf|$base/architectsdaughter/ArchitectsDaughter-Regular.ttf"
      "IndieFlower-Regular.ttf|$base/indieflower/IndieFlower-Regular.ttf"
      "DancingScript.ttf|$base/dancingscript/DancingScript%5Bwght%5D.ttf"
      "Kalam-Regular.ttf|$base/kalam/Kalam-Regular.ttf"
      "Kalam-Bold.ttf|$base/kalam/Kalam-Bold.ttf"
      "ShadowsIntoLight.ttf|$base/shadowsintolight/ShadowsIntoLight.ttf"
      "Sacramento-Regular.ttf|$base/sacramento/Sacramento-Regular.ttf"
      "Montserrat.ttf|$base/montserrat/Montserrat%5Bwght%5D.ttf"
      "Oswald.ttf|$base/oswald/Oswald%5Bwght%5D.ttf"
      "BebasNeue-Regular.ttf|$base/bebasneue/BebasNeue-Regular.ttf"
      "SpaceGrotesk.ttf|$base/spacegrotesk/SpaceGrotesk%5Bwght%5D.ttf"
      "BarlowCondensed-Regular.ttf|$base/barlowcondensed/BarlowCondensed-Regular.ttf"
      "BarlowCondensed-SemiBold.ttf|$base/barlowcondensed/BarlowCondensed-SemiBold.ttf"
      "BarlowCondensed-Bold.ttf|$base/barlowcondensed/BarlowCondensed-Bold.ttf"
      "PlayfairDisplay.ttf|$base/playfairdisplay/PlayfairDisplay%5Bwght%5D.ttf"
      "CormorantGaramond.ttf|$base/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf"
      "DMSans.ttf|$base/dmsans/DMSans%5Bopsz%2Cwght%5D.ttf"
      "Manrope.ttf|$base/manrope/Manrope%5Bwght%5D.ttf"
      "Unbounded.ttf|$base/unbounded/Unbounded%5Bwght%5D.ttf"
      "Bungee-Regular.ttf|$base/bungee/Bungee-Regular.ttf"
      "ZCOOLXiaoWei-Regular.ttf|$base/zcoolxiaowei/ZCOOLXiaoWei-Regular.ttf"
      "LeagueGothic.ttf|$base/leaguegothic/LeagueGothic%5Bwdth%5D.ttf"
      "Syne.ttf|$base/syne/Syne%5Bwght%5D.ttf"
      "Sora.ttf|$base/sora/Sora%5Bwght%5D.ttf"
      "LXGWWenKai-Regular.ttf|https://github.com/lxgw/LxgwWenKai/releases/download/v1.522/LXGWWenKai-Regular.ttf"
    )
    local spec name url tmp
    for spec in "${downloads[@]}"; do
      IFS='|' read -r name url <<< "$spec"
      [ -s "$FONTS_DIR/$name" ] && continue
      tmp="$FONTS_DIR/.${name}.download"
      if command -v curl >/dev/null 2>&1; then
        curl -fsSL --retry 2 --connect-timeout 15 "$url" -o "$tmp" || { rm -f "$tmp"; log "  ⚠️ 下载失败: $name"; continue; }
      elif command -v wget >/dev/null 2>&1; then
        wget -q --timeout=30 -O "$tmp" "$url" || { rm -f "$tmp"; log "  ⚠️ 下载失败: $name"; continue; }
      else
        log "  ⚠️ 缺少 curl/wget，跳过官方字体下载"
        break
      fi
      mv "$tmp" "$FONTS_DIR/$name"
    done
  fi
  if command -v fc-cache >/dev/null 2>&1; then fc-cache -f "$FONTS_DIR" >/dev/null 2>&1; fi
  if command -v fc-list >/dev/null 2>&1; then
    if fc-list 2>/dev/null | grep -qi "Noto Sans SC" && fc-list 2>/dev/null | grep -qi "Noto Serif SC"; then
      log "  核心中文字体 OK (Noto Sans/Serif SC)"
    else
      log "  ⛔ 未发现 Noto Sans/Serif SC；请检查网络或手动放入 $FONTS_DIR 后运行 fc-cache -f。"
      return 1
    fi
  elif [ -s "$FONTS_DIR/NotoSansSC.ttf" ] && [ -s "$FONTS_DIR/NotoSerifSC.ttf" ]; then
    # 极简 worker 常常没有 fontconfig；交付端由 font_bundle.py 直接读取字体文件，
    # 因此文件存在且可解析即可，不应把 fc-list 缺失误判为字体安装失败。
    "$PYBIN" - "$FONTS_DIR/NotoSansSC.ttf" "$FONTS_DIR/NotoSerifSC.ttf" <<'PY'
import sys
for path in sys.argv[1:]:
    with open(path, "rb") as source:
        signature = source.read(4)
    if signature not in {b"\x00\x01\x00\x00", b"OTTO", b"ttcf", b"true"}:
        raise SystemExit(f"invalid font signature: {path}")
PY
    log "  核心中文字体文件 OK (fontconfig 未安装，已校验字体文件签名)"
  else
    log "  ⛔ 未发现 Noto Sans/Serif SC 字体文件；请检查网络或手动放入 $FONTS_DIR。"
    return 1
  fi
}

install_chromium(){
  log "6) Playwright Chromium → $PLAYWRIGHT_BROWSERS_PATH"
  local PW="$NORMALIZE_VENV/bin/python"
  [ -x "$PW" ] || PW="$PYBIN"
  "$PYBIN" -m pip install -q playwright 2>/dev/null || true
  "$PYBIN" -m playwright install chromium 2>/dev/null && log "  Chromium OK" \
    || log "  ⚠️ playwright install chromium 失败;若宿主已有 chromium 设 PLAYWRIGHT_BROWSERS_PATH 复用。"
}

check_material_tools(){
  log "7) 可选附件转换器探测"
  if command -v libreoffice >/dev/null 2>&1 || command -v soffice >/dev/null 2>&1; then
    log "  LibreOffice OK（旧 Office/ODF 与页面外观渲染）"
  else
    log "  ⚠️ LibreOffice/soffice 未安装：现代 Office 仍可抽正文与内嵌图，但旧 Office 和页面外观可能需要 Material 返回 blocked。"
  fi
  if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
    log "  FFmpeg/ffprobe OK（音视频元数据与代表帧）"
  else
    log "  ⚠️ ffmpeg/ffprobe 未安装：音视频只能保留原件，依赖其内容的任务必须提供现有 ASR/媒体转换能力。"
  fi
}

install_fonttools(){
  log "4) FontTools/Brotli/Pillow → 当前渲染解释器 ($PYBIN)"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PYBIN" fonttools brotli pillow >/dev/null 2>&1 || "$PYBIN" -m pip install -q fonttools brotli pillow
  else
    "$PYBIN" -m pip install -q fonttools brotli pillow
  fi
  command -v pyftsubset >/dev/null 2>&1 && log "  pyftsubset OK" \
    || { log "  ⛔ pyftsubset 不可用，无法交付便携字体"; return 1; }
}

install_image_cutout(){
  log "5) NumPy/OpenCV → 主体透明抠图 ($PYBIN)"
  if command -v uv >/dev/null 2>&1; then
    uv pip install --python "$PYBIN" "numpy>=1.24,<2" "opencv-python-headless>=4.8,<4.11" >/dev/null 2>&1 \
      || "$PYBIN" -m pip install -q "numpy>=1.24,<2" "opencv-python-headless>=4.8,<4.11"
  else
    "$PYBIN" -m pip install -q "numpy>=1.24,<2" "opencv-python-headless>=4.8,<4.11"
  fi
  "$PYBIN" - <<'PY'
import site
from pathlib import Path
for root in map(Path, site.getsitepackages()):
    for name in ("numpy.libs", "opencv_python_headless.libs"):
        folder = root / name
        if folder.is_dir():
            for path in folder.iterdir():
                path.chmod(path.stat().st_mode | 0o444)
PY
  "$PYBIN" -c 'import cv2, numpy; print("  OpenCV", cv2.__version__, "NumPy", numpy.__version__)'
}

install_pptx_exporter(){
  local EXPORTER_DIR="$HERE/export_pptx"
  command -v node >/dev/null 2>&1 || { log "  ⛔ 未发现 node，PPTX exporter 不可用"; return 1; }
  command -v npm >/dev/null 2>&1 || { log "  ⛔ 未发现 npm，PPTX exporter 不可用"; return 1; }
  [ -f "$EXPORTER_DIR/package-lock.json" ] || { log "  ⛔ 缺少 $EXPORTER_DIR/package-lock.json"; return 1; }
  npm ci --prefix "$EXPORTER_DIR"
  npm test --prefix "$EXPORTER_DIR"
  log "  Standard PPTX exporter OK"
}

TARGETS=("$@"); [ ${#TARGETS[@]} -eq 0 ] && TARGETS=(normalize pymupdf fonts fonttools image-cutout chromium material-tools pptx-exporter)
for t in "${TARGETS[@]}"; do
  case "$t" in
    normalize) install_normalize ;;
    pymupdf)   install_pymupdf ;;
    fonts)     install_fonts ;;
    fonttools) install_fonttools ;;
    image-cutout) install_image_cutout ;;
    chromium)  install_chromium ;;
    material-tools) check_material_tools ;;
    pptx-exporter) install_pptx_exporter ;;
    *) log "未知目标: $t (可选 normalize|pymupdf|fonts|fonttools|image-cutout|chromium|material-tools|pptx-exporter)";;
  esac
done

echo
log "完成。运行附件解析前设置："
echo "  export NORMALIZE_PY=\"$NORMALIZE_VENV/bin/python\""
echo
log "系统 .so 缺失(headless chromium 报缺库)时:render.py 会自动从 ~/pwdeps/lib 补;"
log "若无 pwdeps,用 micromamba 免 root 装到 ~/pwdeps(见 SKILL.md 渲染依赖段)。"
