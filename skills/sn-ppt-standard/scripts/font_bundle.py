#!/usr/bin/env python3
"""Build and validate a portable, deck-local WOFF2 font bundle.

Authoring renders can use fonts installed on the worker, but ``present.html``
must not depend on the viewer having those fonts. This script resolves the
font roles actually used by one deck to approved OFL families or explicitly
authorized user uploads, subsets the deck characters, writes ``assets/fonts/``,
and injects a bounded ``@font-face`` block into the deck's root ``base.css``.
"""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import glob
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


BUNDLE_START = "/* DECK_FONT_BUNDLE_START */"
BUNDLE_END = "/* DECK_FONT_BUNDLE_END */"
OFL_TEMPLATE = Path(__file__).resolve().parents[1] / "assets/licenses/OFL-1.1.txt"
GOOGLE_FONTS_REV = "2796410152d4f9524b68ed46e69c1b60f8e0f7c3"


@dataclass(frozen=True)
class Face:
    source_names: tuple[str, ...]
    weight: str
    style: str = "normal"


# Delivery is intentionally limited to families whose font files can be
# redistributed with the deck.  Local display fonts outside this list fall
# through to the next allowed family in their CSS stack.
FAMILY_FACES: dict[str, tuple[Face, ...]] = {
    "Noto Sans SC": (
        Face(("NotoSansSC[wght].ttf", "NotoSansSC.ttf"), "100 900"),
    ),
    "Noto Serif SC": (
        Face(("NotoSerifSC[wght].ttf", "NotoSerifSC.ttf"), "200 900"),
    ),
    "IBM Plex Mono": (
        Face(("IBMPlexMono-Regular.ttf",), "400"),
        Face(("IBMPlexMono-SemiBold.ttf",), "600"),
    ),
    "IBM Plex Sans": (
        Face(("IBMPlexSans_2.ttf",), "400"),
        Face(("IBMPlexSans_1.ttf",), "500"),
    ),
    "Archivo": (Face(("Archivo.ttf", "Archivo[wdth,wght].ttf"), "100 900"),),
    "Fraunces": (Face(("Fraunces.ttf", "Fraunces[SOFT,WONK,opsz,wght].ttf"), "100 900"),),
    "Spectral": (
        Face(("Spectral-Regular.ttf",), "400"),
        Face(("Spectral-Bold.ttf",), "700"),
    ),
    "Xiaolai": (Face(("Xiaolai-Regular.ttf",), "400"),),
    "LXGW WenKai": (
        Face(("LXGWWenKai-Regular.ttf",), "400"),
        # The official TTF release is a regular face; browsers may
        # synthesize bold while the portable bundle keeps the same glyph design.
        # Prefer the verified regular source here. Some historical authoring
        # images contain a malformed bold cmap; using it makes pyftsubset fail
        # even though the family passed a shallow availability check.
        Face(("LXGWWenKai-Regular.ttf", "LXGWWenKai-Bold.ttf"), "700"),
    ),
    "Smiley Sans": (Face(("SmileySans-Oblique.ttf",), "100 900", "oblique"),),
    "Ma Shan Zheng": (Face(("MaShanZheng-Regular.ttf",), "400"),),
    "ZCOOL KuaiLe": (Face(("ZCOOLKuaiLe-Regular.ttf",), "400"),),
    "ZCOOL QingKe HuangYou": (Face(("ZCOOLQingKeHuangYou-Regular.ttf",), "400"),),
    "Zhi Mang Xing": (Face(("ZhiMangXing-Regular.ttf",), "400"),),
    "Long Cang": (Face(("LongCang-Regular.ttf",), "400"),),
    "Liu Jian Mao Cao": (Face(("LiuJianMaoCao-Regular.ttf",), "400"),),
    "Patrick Hand": (Face(("PatrickHand-Regular.ttf",), "400"),),
    "Caveat": (Face(("Caveat.ttf", "Caveat[wght].ttf"), "400 700"),),
    "Architects Daughter": (Face(("ArchitectsDaughter-Regular.ttf",), "400"),),
    "Indie Flower": (Face(("IndieFlower-Regular.ttf",), "400"),),
    "Dancing Script": (Face(("DancingScript.ttf", "DancingScript[wght].ttf"), "400 700"),),
    "Kalam": (
        Face(("Kalam-Regular.ttf",), "400"),
        Face(("Kalam-Bold.ttf",), "700"),
    ),
    "Shadows Into Light": (Face(("ShadowsIntoLight.ttf",), "400"),),
    "Sacramento": (Face(("Sacramento-Regular.ttf",), "400"),),
    "Montserrat": (Face(("Montserrat.ttf", "Montserrat[wght].ttf"), "100 900"),),
    "Oswald": (Face(("Oswald.ttf", "Oswald[wght].ttf"), "200 700"),),
    "Bebas Neue": (Face(("BebasNeue-Regular.ttf",), "400"),),
    "Space Grotesk": (Face(("SpaceGrotesk.ttf", "SpaceGrotesk[wght].ttf"), "300 700"),),
    "Barlow Condensed": (
        Face(("BarlowCondensed-Regular.ttf",), "400"),
        Face(("BarlowCondensed-SemiBold.ttf",), "600"),
        Face(("BarlowCondensed-Bold.ttf",), "700"),
    ),
    "Playfair Display": (Face(("PlayfairDisplay.ttf", "PlayfairDisplay[wght].ttf"), "400 900"),),
    "Cormorant Garamond": (Face(("CormorantGaramond.ttf", "CormorantGaramond[wght].ttf"), "300 700"),),
    "DM Sans": (Face(("DMSans.ttf", "DMSans[opsz,wght].ttf"), "100 1000"),),
    "Manrope": (Face(("Manrope.ttf", "Manrope[wght].ttf"), "200 800"),),
    "Unbounded": (Face(("Unbounded.ttf", "Unbounded[wght].ttf"), "200 900"),),
    "Bungee": (Face(("Bungee-Regular.ttf",), "400"),),
    "ZCOOL XiaoWei": (Face(("ZCOOLXiaoWei-Regular.ttf",), "400"),),
    "League Gothic": (Face(("LeagueGothic.ttf", "LeagueGothic[wdth].ttf"), "400"),),
    "Syne": (Face(("Syne.ttf", "Syne[wght].ttf"), "400 800"),),
    "Sora": (Face(("Sora.ttf", "Sora[wght].ttf"), "100 800"),),
}


def _google_font_source(family: str) -> str:
    return f"https://github.com/google/fonts/tree/{GOOGLE_FONTS_REV}/ofl/{family}"


# A family cannot enter the delivery bundle without an explicit official source
# and SPDX-style license declaration.  This is deliberately narrower than
# "whatever happens to be installed on the authoring machine".
FONT_LICENSES: dict[str, dict[str, str]] = {
    "Noto Sans SC": {"license": "OFL-1.1", "source": _google_font_source("notosanssc")},
    "Noto Serif SC": {"license": "OFL-1.1", "source": _google_font_source("notoserifsc")},
    "IBM Plex Mono": {"license": "OFL-1.1", "source": _google_font_source("ibmplexmono")},
    "IBM Plex Sans": {"license": "OFL-1.1", "source": _google_font_source("ibmplexsans")},
    "Archivo": {"license": "OFL-1.1", "source": _google_font_source("archivo")},
    "Fraunces": {"license": "OFL-1.1", "source": _google_font_source("fraunces")},
    "Spectral": {"license": "OFL-1.1", "source": _google_font_source("spectral")},
    "Xiaolai": {"license": "OFL-1.1", "source": "https://github.com/lxgw/kose-font/tree/v3.126"},
    "LXGW WenKai": {"license": "OFL-1.1", "source": "https://github.com/lxgw/LxgwWenKai"},
    "Smiley Sans": {"license": "OFL-1.1", "source": "https://github.com/atelier-anchor/smiley-sans"},
    "Ma Shan Zheng": {"license": "OFL-1.1", "source": _google_font_source("mashanzheng")},
    "ZCOOL KuaiLe": {"license": "OFL-1.1", "source": _google_font_source("zcoolkuaile")},
    "ZCOOL QingKe HuangYou": {"license": "OFL-1.1", "source": _google_font_source("zcoolqingkehuangyou")},
    "Zhi Mang Xing": {"license": "OFL-1.1", "source": _google_font_source("zhimangxing")},
    "Long Cang": {"license": "OFL-1.1", "source": _google_font_source("longcang")},
    "Liu Jian Mao Cao": {"license": "OFL-1.1", "source": _google_font_source("liujianmaocao")},
    "Patrick Hand": {"license": "OFL-1.1", "source": _google_font_source("patrickhand")},
    "Caveat": {"license": "OFL-1.1", "source": _google_font_source("caveat")},
    "Architects Daughter": {"license": "OFL-1.1", "source": _google_font_source("architectsdaughter")},
    "Indie Flower": {"license": "OFL-1.1", "source": _google_font_source("indieflower")},
    "Dancing Script": {"license": "OFL-1.1", "source": _google_font_source("dancingscript")},
    "Kalam": {"license": "OFL-1.1", "source": _google_font_source("kalam")},
    "Shadows Into Light": {"license": "OFL-1.1", "source": _google_font_source("shadowsintolight")},
    "Sacramento": {"license": "OFL-1.1", "source": _google_font_source("sacramento")},
    "Montserrat": {"license": "OFL-1.1", "source": _google_font_source("montserrat")},
    "Oswald": {"license": "OFL-1.1", "source": _google_font_source("oswald")},
    "Bebas Neue": {"license": "OFL-1.1", "source": _google_font_source("bebasneue")},
    "Space Grotesk": {"license": "OFL-1.1", "source": _google_font_source("spacegrotesk")},
    "Barlow Condensed": {"license": "OFL-1.1", "source": _google_font_source("barlowcondensed")},
    "Playfair Display": {"license": "OFL-1.1", "source": _google_font_source("playfairdisplay")},
    "Cormorant Garamond": {"license": "OFL-1.1", "source": _google_font_source("cormorantgaramond")},
    "DM Sans": {"license": "OFL-1.1", "source": _google_font_source("dmsans")},
    "Manrope": {"license": "OFL-1.1", "source": _google_font_source("manrope")},
    "Unbounded": {"license": "OFL-1.1", "source": _google_font_source("unbounded")},
    "Bungee": {"license": "OFL-1.1", "source": _google_font_source("bungee")},
    "ZCOOL XiaoWei": {"license": "OFL-1.1", "source": _google_font_source("zcoolxiaowei")},
    "League Gothic": {"license": "OFL-1.1", "source": _google_font_source("leaguegothic")},
    "Syne": {"license": "OFL-1.1", "source": _google_font_source("syne")},
    "Sora": {"license": "OFL-1.1", "source": _google_font_source("sora")},
}

GENERIC_FAMILIES = {
    "serif", "sans-serif", "monospace", "cursive", "fantasy",
    "system-ui", "ui-sans-serif", "ui-serif", "ui-monospace",
}

DEFAULT_TOKENS = {
    "--font-sans", "--font-body", "--font-title", "--font-display",
    "--font-number", "--font-mono",
}

TOKEN_FALLBACKS = {
    "--font-kai": "Xiaolai",
    "--font-write": "Xiaolai",
    "--font-write-cursive": "Liu Jian Mao Cao",
    "--font-round": "ZCOOL QingKe HuangYou",
    "--font-jotter": "Xiaolai",
}

CUSTOM_CONFIG = Path("materials/font-config.json")
ROLE_TOKENS = {
    "title": ("--font-title", "--font-display"),
    "body": ("--font-body", "--font-sans"),
    "number": ("--font-number",),
    "annotation": ("--font-write", "--font-jotter"),
}


class _VisibleText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        if tag.lower() in {"style", "script", "template"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"style", "script", "template"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


def _atomic_write(path: Path, data: str | bytes) -> None:
    encoded = data if isinstance(data, bytes) else data.encode("utf-8")
    if path.is_file() and path.read_bytes() == encoded:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    kwargs = {} if isinstance(data, bytes) else {"encoding": "utf-8"}
    with tempfile.NamedTemporaryFile(mode=mode, dir=path.parent, delete=False, **kwargs) as handle:
        temporary = Path(handle.name)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _without_bundle(css: str) -> str:
    pattern = re.compile(
        re.escape(BUNDLE_START) + r".*?" + re.escape(BUNDLE_END) + r"\s*",
        flags=re.S,
    )
    return pattern.sub("", css).lstrip()


def _font_source_dirs() -> list[Path]:
    configured = os.environ.get("PPT_FONT_SOURCE_DIRS", "").strip()
    values = [Path(item).expanduser() for item in configured.split(os.pathsep) if item]
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "fonts"
        if candidate.is_dir():
            values.append(candidate)
    values.extend(
        (
            Path.home() / ".fonts",
            Path.home() / ".local/share/fonts",
            Path("/usr/share/fonts/opentype/noto"),
            Path("/usr/share/fonts/truetype/noto"),
        )
    )
    result: list[Path] = []
    for value in values:
        resolved = value.resolve()
        if resolved not in result:
            result.append(resolved)
    return result


def _declared_weight_range(weight: str) -> tuple[float, float] | None:
    values = weight.split()
    if len(values) != 2:
        return None
    return float(values[0]), float(values[1])


@lru_cache(maxsize=None)
def _variable_weight_range(path: str) -> tuple[float, float] | None:
    """Return the real ``wght`` axis bounds, never a filename/CSS guess."""
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(path, lazy=False)
        try:
            if "fvar" not in font:
                return None
            for axis in font["fvar"].axes:
                if axis.axisTag == "wght":
                    return float(axis.minValue), float(axis.maxValue)
        finally:
            font.close()
    except Exception:
        return None
    return None


def _font_supports_face(path: Path, face: Face) -> bool:
    if not _font_source_readable(str(path)):
        return False
    declared = _declared_weight_range(face.weight)
    if declared is None:
        return True
    actual = _variable_weight_range(str(path))
    return actual is not None and actual[0] <= declared[0] and actual[1] >= declared[1]


def _find_source(face: Face, source_dirs: list[Path]) -> Path:
    for directory in source_dirs:
        for name in face.source_names:
            candidate = directory / name
            if candidate.is_file() and candidate.stat().st_size and _font_supports_face(candidate, face):
                return candidate
    raise FileNotFoundError(
        f"missing compatible delivery font source {list(face.source_names)!r} "
        f"for weight {face.weight!r}; searched "
        + ", ".join(str(item) for item in source_dirs)
    )


def _family_available(family: str, source_dirs: list[Path]) -> bool:
    try:
        for face in FAMILY_FACES[family]:
            if not _font_source_readable(str(_find_source(face, source_dirs))):
                return False
        return True
    except FileNotFoundError:
        return False


@lru_cache(maxsize=None)
def _font_source_readable(path: str) -> bool:
    """Reject corrupt installed faces before pyftsubset turns them into a hard failure."""
    try:
        from fontTools.ttLib import TTFont

        font = TTFont(path, lazy=False)
        try:
            for table in font["cmap"].tables:
                _ = table.cmap
        finally:
            font.close()
        return True
    except Exception:
        return False


@lru_cache(maxsize=None)
def _font_source_metadata(path: str) -> dict[str, str]:
    """Read human-facing copyright/license fields retained in the source font."""
    from fontTools.ttLib import TTFont

    font = TTFont(path, lazy=False)
    try:
        names = font["name"]
        return {
            "copyright": names.getDebugName(0) or "",
            "license_description": names.getDebugName(13) or "",
            "license_url": names.getDebugName(14) or "",
        }
    finally:
        font.close()


def _load_custom_config(root: Path) -> tuple[dict[str, dict], dict[str, str]]:
    path = root / CUSTOM_CONFIG
    if not path.is_file():
        return {}, {}
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(f"custom font config is unreadable: {exc}") from exc
    fonts = config.get("fonts") or []
    if fonts and not config.get("license_acknowledged"):
        raise ValueError("custom font config lacks user embedding authorization")
    registry: dict[str, dict] = {}
    for item in fonts:
        if not isinstance(item, dict) or not item.get("id") or not item.get("source_path"):
            raise ValueError("custom font config contains an incomplete font record")
        font_id = str(item["id"])
        source = (root / str(item["source_path"])).resolve()
        try:
            source.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"custom font escapes workspace: {source}") from exc
        if not source.is_file() or not source.stat().st_size:
            raise FileNotFoundError(f"custom font source is missing: {item['source_path']}")
        digest = hashlib.sha256(source.read_bytes()).hexdigest()
        if digest != str(item.get("sha256") or ""):
            raise ValueError(f"custom font hash mismatch: {item['source_path']}")
        if not _font_source_readable(str(source)):
            raise ValueError(f"custom font is unreadable: {item['source_path']}")
        family_key = f"User::{font_id}"
        subfamily = str(item.get("subfamily") or "").lower()
        registry[family_key] = {
            **item,
            "source": source,
            "weight": str(int(item.get("weight") or 400)),
            "style": "italic" if "italic" in subfamily else "oblique" if "oblique" in subfamily else "normal",
        }
    role_overrides: dict[str, str] = {}
    for role, selection in (config.get("roles") or {}).items():
        if role not in ROLE_TOKENS or not isinstance(selection, dict):
            continue
        kind = selection.get("kind")
        if kind == "builtin":
            family = str(selection.get("family") or "")
            if family not in FAMILY_FACES:
                raise ValueError(f"custom font config references unapproved builtin family: {family}")
        elif kind == "custom":
            family = f"User::{selection.get('font_id') or ''}"
            if family not in registry:
                raise ValueError(f"custom font role {role} references a missing font")
        else:
            continue
        for token in ROLE_TOKENS[role]:
            role_overrides[token] = family
    return registry, role_overrides


def _validate_font_allowlist() -> None:
    missing = sorted(set(FAMILY_FACES) - set(FONT_LICENSES))
    extra = sorted(set(FONT_LICENSES) - set(FAMILY_FACES))
    if missing or extra:
        raise RuntimeError(f"font allowlist mismatch: missing={missing}, extra={extra}")
    unsupported = sorted(
        family for family, metadata in FONT_LICENSES.items()
        if metadata.get("license") != "OFL-1.1" or not metadata.get("source")
    )
    if unsupported:
        raise RuntimeError("font allowlist requires official OFL-1.1 sources: " + ", ".join(unsupported))
    if not OFL_TEMPLATE.is_file():
        raise FileNotFoundError(f"missing bundled license text: {OFL_TEMPLATE}")


def _token_definitions(css: str) -> dict[str, str]:
    return {
        name.lower(): value.strip()
        for name, value in re.findall(
            r"(?m)(--font-[a-z0-9-]+)\s*:\s*([^;{}]+);", css, flags=re.I
        )
    }


def _family_candidates(value: str) -> list[str]:
    result: list[str] = []
    for part in value.split(","):
        family = re.sub(r"^[\"']|[\"']$", "", part.strip())
        if not family or family.lower() in GENERIC_FAMILIES or family.startswith("var("):
            continue
        result.append(family)
    return result


def _resolve_token(
    token: str,
    definitions: dict[str, str],
    seen: set[str] | None = None,
) -> str:
    token = token.lower()
    seen = set(seen or ())
    if token in seen:
        raise ValueError(f"font token cycle includes {token}")
    seen.add(token)
    value = definitions.get(token, "")
    for family in _family_candidates(value):
        if family in FAMILY_FACES:
            return family
    for reference in re.findall(r"var\((--font-[a-z0-9-]+)", value, flags=re.I):
        family = _resolve_token(reference, definitions, seen)
        if family:
            return family
    if token in TOKEN_FALLBACKS:
        return TOKEN_FALLBACKS[token]
    if "mono" in token or "number" in token:
        return "IBM Plex Mono"
    if "serif" in token:
        return "Noto Serif SC"
    return "Noto Sans SC"


def _active_tokens(css: str, fragments: list[str]) -> dict[str, str]:
    markup = "\n".join(fragments)
    definitions = _token_definitions(css)
    tokens = set(DEFAULT_TOKENS)
    tokens.update(
        item.lower()
        for item in re.findall(r"(--font-[a-z0-9-]+)", markup, flags=re.I)
    )
    source_dirs = _font_source_dirs()
    fallback = "Noto Sans SC"
    if not _family_available(fallback, source_dirs):
        raise FileNotFoundError("Noto Sans SC is required as the portable font fallback")
    resolved = {token: _resolve_token(token, definitions) for token in sorted(tokens)}
    return {
        token: family if _family_available(family, source_dirs) else fallback
        for token, family in resolved.items()
    }


def _visible_characters(fragments: list[str]) -> str:
    parser = _VisibleText()
    for fragment in fragments:
        parser.feed(fragment)
    baseline = "".join(chr(code) for code in range(0x20, 0x7F))
    baseline += " ·—–→←≈≤≥℃°％：；，。！？（）【】《》“”‘’…"
    return "".join(sorted(set("".join(parser.parts) + baseline)))


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def _generic_for(family: str) -> str:
    if family.startswith("User::"):
        return "sans-serif"
    if family == "IBM Plex Mono":
        return "monospace"
    if family in {"Noto Serif SC", "Fraunces", "Spectral", "LXGW WenKai"}:
        return "serif"
    if family in {
        "Xiaolai", "Ma Shan Zheng", "Zhi Mang Xing", "Long Cang", "Liu Jian Mao Cao",
        "Patrick Hand", "Caveat", "Architects Daughter", "Indie Flower",
        "Dancing Script", "Kalam", "Shadows Into Light", "Sacramento",
    }:
        return "cursive"
    return "sans-serif"


# Families whose subset actually carries CJK glyphs.  Any other delivery family
# (Latin display / mono / English handwriting) must be followed by a bundled CJK
# fallback in the :root stack, otherwise stray Chinese falls back to whatever CJK
# font the viewer/worker happens to have (often a cartoon face) and the metric
# mismatch between authoring and delivery renders pushes content past the footer.
_CJK_COVERING = frozenset({
    "Noto Sans SC", "Noto Serif SC", "Smiley Sans",
    "Xiaolai", "LXGW WenKai", "Ma Shan Zheng",
    "Zhi Mang Xing", "Long Cang", "Liu Jian Mao Cao",
    "ZCOOL KuaiLe", "ZCOOL QingKe HuangYou", "ZCOOL XiaoWei",
})


def _covers_cjk(family: str) -> bool:
    # User uploads have unknown coverage → always append a CJK fallback.
    return family in _CJK_COVERING


def _rename_subset_font(target: Path, delivery_family: str, weight: str, style: str) -> None:
    """Rename a modified subset so OFL Reserved Font Names are not reused."""
    from fontTools.ttLib import TTFont

    font = TTFont(target, lazy=False)
    try:
        subfamily = "Oblique" if style == "oblique" else "Italic" if style == "italic" else "Regular"
        postscript = re.sub(
            r"[^A-Za-z0-9-]", "-", f"{delivery_family}-{weight.replace(' ', '-')}-{subfamily}"
        )[:63]
        full_name = f"{delivery_family} {subfamily}"
        name_table = font["name"]
        rewritten = {1: delivery_family, 2: subfamily, 3: postscript, 4: full_name,
                     6: postscript, 16: delivery_family, 17: subfamily}
        name_table.names = [record for record in name_table.names if record.nameID not in rewritten]
        for name_id, value in rewritten.items():
            name_table.setName(value, name_id, 3, 1, 0x409)
            name_table.setName(value, name_id, 1, 0, 0)
        renamed = target.with_name(target.stem + ".renamed.woff2")
        font.save(renamed)
    finally:
        font.close()
    os.replace(renamed, target)


def _subset(
    tool: str,
    source: Path,
    target: Path,
    characters_file: Path,
    delivery_family: str,
    weight: str,
    style: str,
) -> None:
    result = subprocess.run(
        [
            tool,
            str(source),
            f"--output-file={target}",
            "--flavor=woff2",
            f"--text-file={characters_file}",
            "--layout-features=*",
            "--name-IDs=*",
            "--name-legacy",
            "--name-languages=*",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )
    if result.returncode or not target.is_file() or not target.stat().st_size:
        detail = (result.stderr or result.stdout or "font subset failed")[-1000:]
        raise RuntimeError(f"pyftsubset failed for {source.name}: {detail}")
    _rename_subset_font(target, delivery_family, weight, style)
    declared = _declared_weight_range(weight)
    actual = _variable_weight_range(str(target)) if declared is not None else None
    if declared is not None and (
        actual is None or actual[0] > declared[0] or actual[1] < declared[1]
    ):
        raise RuntimeError(
            f"subset lost required variable weight range {weight} for {source.name}"
        )


def bundle_fonts(
    root: Path,
    css: str,
    fragments: list[str],
    scan_named_families: bool = True,
) -> str:
    root = root.resolve()
    _validate_font_allowlist()
    source_css = _without_bundle(css)
    token_families = _active_tokens(source_css, fragments)
    custom_fonts, role_overrides = _load_custom_config(root)
    token_families.update(role_overrides)
    markup = "\n".join(fragments)
    families = set(token_families.values())
    # A portable CJK/symbol fallback is always bundled, including when a user
    # font is assigned to body text but does not cover every deck character.
    families.add("Noto Sans SC")
    source_dirs = _font_source_dirs()
    if scan_named_families:
        for family in FAMILY_FACES:
            if _family_available(family, source_dirs) and re.search(
                rf"(?<![\w-]){re.escape(family)}(?![\w-])", markup, flags=re.I
            ):
                families.add(family)

    tool = shutil.which("pyftsubset")
    if not tool:
        raise FileNotFoundError("pyftsubset is required for portable deck fonts")
    characters = _visible_characters(fragments)
    deck_id = hashlib.sha256(
        (characters + json.dumps(token_families, sort_keys=True, ensure_ascii=False)).encode("utf-8")
    ).hexdigest()[:10]
    delivery_families = {
        family: f"Deck-{deck_id}-{_slug(family)}" for family in sorted(families)
    }

    fonts_dir = root / "assets/fonts"
    fonts_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, str]] = []
    rules: list[str] = []
    notices: dict[str, dict[str, object]] = {}
    with tempfile.TemporaryDirectory(prefix="deck-fonts-") as temporary:
        temporary_dir = Path(temporary)
        characters_file = temporary_dir / "characters.txt"
        characters_file.write_text(characters, encoding="utf-8")
        for family in sorted(families):
            custom = custom_fonts.get(family)
            faces = (
                (Face((str(custom["source"]),), custom["weight"], custom["style"]),)
                if custom else FAMILY_FACES[family]
            )
            for face in faces:
                source = Path(face.source_names[0]) if custom else _find_source(face, source_dirs)
                source_metadata = _font_source_metadata(str(source))
                license_metadata = (
                    {"license": "user-provided", "source": "user upload"}
                    if custom else FONT_LICENSES[family]
                )
                delivery = delivery_families[family]
                provisional = temporary_dir / f"{_slug(family)}-{face.weight.replace(' ', '-')}.woff2"
                _subset(
                    tool, source, provisional, characters_file,
                    delivery, face.weight, face.style,
                )
                data = provisional.read_bytes()
                digest = hashlib.sha256(data).hexdigest()
                filename = f"{_slug(family)}-{face.weight.replace(' ', '-')}-{digest[:12]}.woff2"
                target = fonts_dir / filename
                _atomic_write(target, data)
                records.append(
                    {
                        "source_family": family,
                        "delivery_family": delivery,
                        "weight": face.weight,
                        "style": face.style,
                        "source": source.name,
                        "source_url": license_metadata["source"],
                        "license": license_metadata["license"],
                        "license_file": (
                            "assets/fonts/USER-FONTS.txt" if custom
                            else "assets/fonts/OFL-1.1.txt"
                        ),
                        "copyright": source_metadata["copyright"],
                        "path": f"assets/fonts/{filename}",
                        "sha256": digest,
                        "user_authorized": bool(custom),
                        "original_sha256": str(custom.get("sha256") or "") if custom else "",
                        "source_path": str(custom.get("source_path") or "") if custom else "",
                    }
                )
                notice = notices.setdefault(
                    family,
                    {
                        "source_url": license_metadata["source"],
                        "license": license_metadata["license"],
                        "copyright": set(),
                        "files": [],
                    },
                )
                if source_metadata["copyright"]:
                    notice["copyright"].add(source_metadata["copyright"])
                notice["files"].append(source.name)
                rules.append(
                    "@font-face {\n"
                    f"  font-family: {json.dumps(delivery)};\n"
                    f"  src: url(\"./assets/fonts/{filename}\") format(\"woff2\");\n"
                    f"  font-style: {face.style};\n"
                    f"  font-weight: {face.weight};\n"
                    "  font-display: block;\n"
                    "}"
                )

    _atomic_write(fonts_dir / "OFL-1.1.txt", OFL_TEMPLATE.read_bytes())
    _atomic_write(
        fonts_dir / "USER-FONTS.txt",
        "USER-PROVIDED FONT NOTICE\n\n"
        "Fonts marked user-provided were uploaded for this presentation. "
        "The user affirmed that they hold the rights required for presentation "
        "use and embedding. They are internally renamed and subset for this deck.\n",
    )
    notice_lines = [
        "FONT LICENSE NOTICES",
        "",
        "Approved built-in subsets use SIL Open Font License 1.1; see OFL-1.1.txt.",
        "User-provided subsets rely on the user's authorization; see USER-FONTS.txt.",
    ]
    for family in sorted(notices):
        notice = notices[family]
        notice_lines.extend(
            [
                "",
                f"Family: {family}",
                f"License: {notice['license']}",
                f"Official source: {notice['source_url']}",
                "Source files: " + ", ".join(sorted(set(notice["files"]))),
            ]
        )
        for copyright_line in sorted(notice["copyright"]):
            notice_lines.append("Copyright: " + copyright_line)
    _atomic_write(fonts_dir / "LICENSES.txt", "\n".join(notice_lines).rstrip() + "\n")
    active_font_files = {Path(record["path"]).name for record in records}
    for stale in fonts_dir.glob("*.woff2"):
        if stale.name not in active_font_files:
            stale.unlink()

    fallback_delivery = delivery_families["Noto Sans SC"]
    overrides = "\n".join(
        f"  {token}: {json.dumps(delivery_families[family])}, "
        # Latin display / mono / English-handwriting / user subsets carry no CJK
        # glyphs → append the bundled Noto CJK fallback so stray Chinese never
        # falls through to a viewer/worker cartoon face (and both authoring and
        # delivery renders resolve CJK to the same metrics, killing the overflow).
        + (f"{json.dumps(fallback_delivery)}, " if not _covers_cjk(family) else "")
        + f"{_generic_for(family)};"
        for token, family in sorted(token_families.items())
    )
    rules.append(":root {\n" + overrides + "\n}")
    bundle = BUNDLE_START + "\n" + "\n\n".join(rules) + "\n" + BUNDLE_END
    manifest = {
        "version": 3,
        "deck_id": deck_id,
        "character_count": len(characters),
        "token_families": token_families,
        "delivery_families": delivery_families,
        "faces": records,
        "license_files": [
            "assets/fonts/LICENSES.txt", "assets/fonts/OFL-1.1.txt",
            "assets/fonts/USER-FONTS.txt",
        ],
    }
    _atomic_write(fonts_dir / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    # Keep role overrides last so the authoring :root declarations above cannot
    # overwrite the portable Deck family names in the CSS cascade.
    return source_css.rstrip() + "\n\n" + bundle + "\n"


def validate_font_bundle(root: Path) -> list[str]:
    root = root.resolve()
    manifest_path = root / "assets/fonts/manifest.json"
    css_path = root / "base.css"
    errors: list[str] = []
    if not manifest_path.is_file():
        return ["assets/fonts/manifest.json is missing"]
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"font manifest is unreadable: {exc}"]
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    if BUNDLE_START not in css or BUNDLE_END not in css:
        errors.append("base.css does not contain the deck font bundle")
    for relative in manifest.get("license_files", []):
        path = root / str(relative)
        if not path.is_file() or not path.stat().st_size:
            errors.append(f"bundled font license notice is missing or empty: {relative}")
    for record in manifest.get("faces", []):
        relative = str(record.get("path", ""))
        path = root / relative
        if not relative.startswith("assets/fonts/") or not path.is_file() or not path.stat().st_size:
            errors.append(f"bundled font is missing or empty: {relative or '<unset>'}")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != str(record.get("sha256", "")):
            errors.append(f"bundled font hash mismatch: {relative}")
        if str(record.get("delivery_family", "")) not in css:
            errors.append(f"delivery font family is absent from base.css: {record.get('delivery_family')}")
        license_kind = record.get("license")
        if license_kind == "OFL-1.1":
            if not record.get("source_url"):
                errors.append(f"bundled OFL font lacks official source metadata: {relative}")
        elif license_kind == "user-provided":
            if not record.get("user_authorized") or not record.get("original_sha256") or not record.get("source_path"):
                errors.append(f"user-provided font lacks authorization/provenance metadata: {relative}")
        else:
            errors.append(f"bundled font has unsupported license metadata: {relative}")
    declared = {Path(str(record.get("path", ""))).name for record in manifest.get("faces", [])}
    for stale in (root / "assets/fonts").glob("*.woff2"):
        if stale.name not in declared:
            errors.append(f"undeclared font file remains in bundle: assets/fonts/{stale.name}")
    return errors


def validate_render_freshness(root: Path) -> list[str]:
    """Reject PNGs rendered before their slide HTML or bundled base.css."""
    root = root.resolve()
    css_path = root / "base.css"
    errors: list[str] = []
    for slide in sorted(root.glob("slides/slide_*.html")):
        if ".bak." in slide.name:
            continue
        match = re.search(r"(\d+)", slide.stem)
        if not match:
            continue
        render = root / "renders" / f"slide_{int(match.group(1)):02d}.png"
        if not render.is_file() or not render.stat().st_size:
            errors.append(f"missing render for {slide.name}")
            continue
        newest_source = max(slide.stat().st_mtime, css_path.stat().st_mtime)
        if render.stat().st_mtime + 0.001 < newest_source:
            errors.append(f"stale render: {render.name} predates slide HTML or bundled base.css")
    return errors


def render_all(root: Path) -> None:
    """Re-render every slide with one shared Chromium process."""
    root = root.resolve()
    renderer = Path(__file__).resolve().with_name("render.py")
    result = subprocess.run(
        [sys.executable, str(renderer), "--batch", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout or "batch render failed")[-1600:]
        raise RuntimeError(f"portable-font batch render failed: {detail}")
    print((result.stdout or "batch renders refreshed").strip())


def _read_inputs(root: Path, from_plans: bool = False) -> tuple[str, list[str]]:
    css_path = root / "base.css"
    if not css_path.is_file():
        raise FileNotFoundError(f"missing {css_path}")
    pattern = "plan/slide_*.md" if from_plans else "slides/slide_*.html"
    files = sorted(Path(path) for path in glob.glob(str(root / pattern)) if ".bak." not in Path(path).name)
    if from_plans:
        files = [
            path for path in (root / "plan/design-brief.md", root / "plan/deck.md") if path.is_file()
        ] + files
    if not files:
        source = root / ("plan" if from_plans else "slides")
        raise FileNotFoundError(f"no {'plans' if from_plans else 'slides'} found under {source}")
    if from_plans:
        fragments = [_plan_font_fragment(path) for path in files]
    else:
        fragments = [path.read_text(encoding="utf-8") for path in files]
    return css_path.read_text(encoding="utf-8"), fragments


def _plan_font_fragment(path: Path) -> str:
    """Keep font tokens plus screen copy; exclude speech/source prose from subsets."""
    text = path.read_text(encoding="utf-8")
    tokens = " ".join(sorted(set(re.findall(r"--font-[a-z0-9-]+", text, flags=re.I))))
    if not path.name.startswith("slide_"):
        return tokens
    match = re.search(
        r"(?ms)^##\s+(?:最终屏显文案|屏显文案|On-screen copy|Final on-screen copy)\s*$"
        r"(.*?)(?=^##\s+|\Z)",
        text,
    )
    screen_copy = match.group(1) if match else text
    return tokens + "\n" + screen_copy


def bundle_workspace(root: Path, from_plans: bool = False) -> dict:
    """Bundle one workspace and return its validated manifest."""
    root = root.resolve()
    css, fragments = _read_inputs(root, from_plans=from_plans)
    _atomic_write(
        root / "base.css",
        bundle_fonts(root, css, fragments, scan_named_families=not from_plans),
    )
    errors = validate_font_bundle(root)
    if errors:
        raise RuntimeError("; ".join(errors))
    return json.loads((root / "assets/fonts/manifest.json").read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    root = Path(argv[0] if argv else ".").resolve()
    if len(argv) > 1 and argv[1] == "--validate":
        errors = validate_font_bundle(root)
        if errors:
            print("font bundle: FAIL", file=sys.stderr)
            for error in errors:
                print(f"- {error}", file=sys.stderr)
            return 1
        print("font bundle: PASS")
        return 0
    from_plans = "--from-plans" in argv[1:]
    manifest = bundle_workspace(root, from_plans=from_plans)
    if "--render" in argv[1:]:
        render_all(root)
        freshness_errors = validate_render_freshness(root)
        if freshness_errors:
            raise RuntimeError("; ".join(freshness_errors))
    print(
        f"font bundle: PASS ({len(manifest['faces'])} faces, "
        f"{manifest['character_count']} characters"
        + (", renders refreshed)" if "--render" in argv[1:] else ")")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
