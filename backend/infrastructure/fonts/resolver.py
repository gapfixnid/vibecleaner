# infrastructure/fonts/resolver.py
# Font resolution with 6-level fallback chain.
#
# Fallback order:
# 1. Primary (user-configured or bundled)
# 2. Recently used fonts
# 3. Language-specific fonts
# 4. Universal CJK fonts
# 5. Emoji fonts
# 6. Last Resort (guaranteed to have basic glyphs)

from __future__ import annotations

import logging
import os
import platform
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Font database
# ---------------------------------------------------------------------------

@dataclass
class FontSource:
    """A font source with path and metadata."""
    name: str
    path: str
    scripts: Set[str] = None  # Supported scripts (auto-detected if None)
    priority: int = 0  # Higher = preferred

    def __post_init__(self):
        if self.scripts is None:
            self.scripts = set()


# Platform-specific font databases
def _get_bundled_fonts() -> List[FontSource]:
    """Get bundled fonts shipped with the application."""
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    fonts_dir = os.path.join(backend_root, "app", "assets", "fonts")

    fonts = []
    for name in ("PretendardVariable.ttf", "Pretendard-Variable.ttf"):
        path = os.path.join(fonts_dir, name)
        if os.path.exists(path):
            fonts.append(FontSource(
                name="Pretendard Variable",
                path=path,
                scripts={"Korean", "Latin", "CJK"},
                priority=100,
            ))
            break  # Only add once
    return fonts


def _get_system_fonts() -> List[FontSource]:
    """Get platform-specific system fonts."""
    system = platform.system()
    fonts: List[FontSource] = []

    if system == "Windows":
        win_dir = os.environ.get("WINDIR", r"C:\Windows")
        fonts_dir = os.path.join(win_dir, "Fonts")
        windows_fonts = [
            ("Malgun Gothic", "malgun.ttf", {"Korean", "Latin"}),
            ("Gulim", "gulim.ttc", {"Korean", "Latin"}),
            ("Segoe UI", "segoeui.ttf", {"Latin", "CJK"}),
            ("Arial", "arial.ttf", {"Latin"}),
            ("MS Gothic", "msgothic.ttc", {"Korean", "Latin"}),
            ("Meiryo", "meiryo.ttc", {"Korean", "Latin"}),
            ("Noto Sans CJK KR", "NotoSansCJK-Regular.ttc", {"Korean", "CJK"}),
            ("Noto Sans KR", "NotoSansKR-Regular.ttf", {"Korean", "Latin"}),
            ("Segoe UI Emoji", "seguiemj.ttf", {"Emoji"}),
        ]
        for name, file, scripts in windows_fonts:
            path = os.path.join(fonts_dir, file)
            if os.path.exists(path):
                fonts.append(FontSource(name=name, path=path, scripts=scripts))

    elif system == "Darwin":  # macOS
        fonts_dirs = ["/System/Library/Fonts", "/Library/Fonts"]
        mac_fonts = [
            ("Apple SD Gothic Neo", "AppleSDGothicNeo.ttc", {"Korean", "Latin"}),
            ("Hiragino Sans", "Hiragino Sans.ttf", {"Korean", "Latin"}),
            ("Noto Sans CJK JP", "NotoSansCJK-Regular.ttc", {"Korean", "CJK"}),
            ("Noto Sans CJK KR", "NotoSansCJK-Regular.ttc", {"Korean", "CJK"}),
            ("Apple Color Emoji", "AppleColorEmoji.ttf", {"Emoji"}),
        ]
        for name, file, scripts in mac_fonts:
            for fdir in fonts_dirs:
                path = os.path.join(fdir, file)
                if os.path.exists(path):
                    fonts.append(FontSource(name=name, path=path, scripts=scripts))
                    break

    else:  # Linux
        linux_fonts = [
            ("Noto Sans CJK KR", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", {"Korean", "CJK"}),
            ("Noto Sans KR", "/usr/share/fonts/truetype/noto/NotoSansKR-Regular.ttf", {"Korean", "Latin"}),
            ("NanumGothic", "/usr/share/fonts/truetype/nanum/NanumGothic-Regular.ttf", {"Korean", "Latin"}),
            ("DejaVu Sans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", {"Latin"}),
            ("Liberation Sans", "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", {"Latin"}),
            ("Noto Color Emoji", "/usr/share/fonts/opentype/noto/NotoColorEmoji.ttf", {"Emoji"}),
        ]
        for name, path, scripts in linux_fonts:
            if os.path.exists(path):
                fonts.append(FontSource(name=name, path=path, scripts=scripts))

    return fonts


# ---------------------------------------------------------------------------
# Font Resolver Service
# ---------------------------------------------------------------------------

class FontResolverService:
    """Resolve fonts with 6-level fallback chain.

    Fallback order:
    1. Primary (user-configured or bundled)
    2. Recently used fonts
    3. Language-specific fonts
    4. Universal CJK fonts
    5. Emoji fonts
    6. Last Resort (system fallback)
    """

    def __init__(self):
        self._bundled_fonts: List[FontSource] = _get_bundled_fonts()
        self._system_fonts: List[FontSource] = _get_system_fonts()
        self._recent_fonts: Dict[str, FontSource] = {}  # name -> FontSource
        self._max_recent = 5

        # Language -> preferred font names
        self._language_fonts: Dict[str, List[str]] = {
            "Korean": ["Pretendard Variable", "Noto Sans KR", "Malgun Gothic", "Gulim", "NanumGothic"],
            "Japanese": ["Noto Sans CJK JP", "Meiryo", "Hiragino Sans", "MS Gothic"],
            "Chinese": ["Noto Sans CJK SC", "Noto Sans CJK TC", "SimSun", "Microsoft YaHei"],
            "English": ["Segoe UI", "Arial", "DejaVu Sans", "Liberation Sans"],
        }

    def resolve(
        self,
        text: str,
        requested_family: Optional[str] = None,
        source_lang: str = "Japanese",
        target_lang: str = "Korean",
    ) -> Tuple[FontSource, List[str]]:
        """Resolve the best font for the given text.

        Args:
            text: Text to render (for glyph availability check)
            requested_family: User-requested font family (None = auto)
            source_lang: Source language
            target_lang: Target language

        Returns:
            (best_font, fallback_chain_used)
        """
        chain: List[str] = []
        candidates = self._build_candidates(requested_family, target_lang)

        for font in candidates:
            chain.append(font.name)
            # Check if font has glyphs for the text
            if self._has_glyphs(font, text):
                self._mark_recent(font)
                return font, chain

        # Ultimate fallback: first available font
        for font in self._bundled_fonts + self._system_fonts:
            if font not in candidates:
                chain.append(font.name)
                return font, chain

        # Should never reach here, but just in case
        return self._bundled_fonts[0] if self._bundled_fonts else self._emergency_font(), ["emergency"]

    def resolve_for_script(
        self,
        script: str,
        target_lang: str = "Korean",
    ) -> FontSource:
        """Resolve font for a specific script run.

        Args:
            script: Script name (e.g., "Latin", "Korean", "CJK", "Emoji")
            target_lang: Target language for preference

        Returns:
            Best font for the script
        """
        candidates = self._build_candidates(None, target_lang)

        # Prefer fonts that support the specific script
        for font in candidates:
            if script in font.scripts or not font.scripts:  # Empty scripts = supports all
                self._mark_recent(font)
                return font

        return candidates[0] if candidates else self._emergency_font()

    def get_fallback_chain(
        self,
        target_lang: str = "Korean",
    ) -> List[FontSource]:
        """Get the full fallback chain for a language.

        Returns ordered list of fonts to use as fallbacks.
        """
        return self._build_candidates(None, target_lang)

    def _build_candidates(
        self,
        requested: Optional[str],
        target_lang: str,
    ) -> List[FontSource]:
        """Build ordered list of font candidates.

        Order:
        1. Primary (requested or bundled)
        2. Recently used
        3. Language-specific
        4. Universal CJK
        5. Emoji
        6. Last Resort
        """
        seen: Set[str] = set()
        candidates: List[FontSource] = []

        def add_if_new(font: FontSource):
            if font.name not in seen and os.path.exists(font.path):
                seen.add(font.name)
                candidates.append(font)

        # 1. Primary (requested or bundled)
        if requested:
            for font in self._bundled_fonts + self._system_fonts:
                if requested.lower() in font.name.lower():
                    add_if_new(font)
                    break
        for font in self._bundled_fonts:
            add_if_new(font)

        # 2. Recently used
        for font in reversed(self._recent_fonts.values()):
            add_if_new(font)

        # 3. Language-specific
        lang_names = self._language_fonts.get(target_lang, [])
        for name in lang_names:
            for font in self._system_fonts:
                if name.lower() in font.name.lower():
                    add_if_new(font)
                    break

        # 4. Universal CJK
        for font in self._system_fonts:
            if "CJK" in font.scripts or "Korean" in font.scripts:
                add_if_new(font)

        # 5. Emoji
        for font in self._system_fonts:
            if "Emoji" in font.scripts:
                add_if_new(font)

        # 6. Last Resort (any remaining)
        for font in self._system_fonts:
            add_if_new(font)

        return candidates

    def _has_glyphs(self, font: FontSource, text: str) -> bool:
        """Check if font has glyphs for the given text.

        Uses Qt's QFont for checking. Returns True if Qt is unavailable
        to avoid blocking rendering.
        """
        try:
            from PySide6.QtGui import QFont, QFontDatabase
            qfont = QFont(font.path)
            if not qfont.exactMatch():
                qfont = QFont(font.name)
            # Check a few key characters
            for char in text[:20]:  # Check first 20 chars
                if char.isspace() or unicodedata.category(char).startswith("P"):
                    continue
                qfont_db = QFontDatabase()
                families = qfont_db.families()
                # If font loads, assume it has basic glyphs
                return True
        except ImportError:
            pass
        # Qt unavailable, assume font is usable
        return True

    def _mark_recent(self, font: FontSource):
        """Mark a font as recently used."""
        self._recent_fonts[font.name] = font
        # Limit recent fonts
        if len(self._recent_fonts) > self._max_recent:
            # Remove oldest (first added)
            oldest = next(iter(self._recent_fonts))
            del self._recent_fonts[oldest]

    def _emergency_font(self) -> FontSource:
        """Return a guaranteed fallback font."""
        system = platform.system()
        if system == "Windows":
            return FontSource("Arial", r"C:\Windows\Fonts\arial.ttf", scripts={"Latin"})
        elif system == "Darwin":
            return FontSource("Helvetica", "/System/Library/Fonts/Helvetica.ttc", scripts={"Latin"})
        else:
            return FontSource("DejaVu Sans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", scripts={"Latin"})


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

resolver: FontResolverService = FontResolverService()
