# page_analysis_service.py
# Page-level analysis: panel detection, reading order, writing mode.
#
# Hierarchy:
#   Page -> Panels -> Bubbles -> Lines
#
# Reading order and writing mode are determined at the Page level,
# not within Bubble Analysis.

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class PanelDto:
    """A detected manga panel on the page."""
    x: float
    y: float
    width: float
    height: float
    index: int = 0  # Reading order index
    confidence: float = 0.0
    bubble_count: int = 0


@dataclass
class ReadingOrderDto:
    """Page-level reading order."""
    direction: str  # 'ltr' | 'rtl'
    orientation: str  # 'horizontal' | 'vertical'
    source: str  # 'language' | 'visual' | 'default'
    confidence: float = 0.0
    details: dict = field(default_factory=dict)


@dataclass
class PageAnalysisResult:
    """Result of page-level analysis."""
    panels: List[PanelDto] = field(default_factory=list)
    reading_order: ReadingOrderDto = None
    writing_mode: str = 'horizontal'  # 'horizontal' | 'vertical'
    page_width: int = 0
    page_height: int = 0

    def __post_init__(self):
        if self.reading_order is None:
            self.reading_order = ReadingOrderDto(
                direction='ltr',
                orientation='horizontal',
                source='default',
            )


# ---------------------------------------------------------------------------
# Panel detection
# ---------------------------------------------------------------------------

def detect_panels(
    image: np.ndarray,
    min_panel_area: float = 0.01,  # Min panel = 1% of page
    gap_threshold: int = 5,  # Min gap width between panels
) -> List[PanelDto]:
    """Detect manga panels using edge-based connected component analysis.

    Strategy:
    1. Threshold to find dark panel borders
    2. Dilate borders to connect gaps
    3. Invert and find connected components (white regions = panels)
    4. Filter by size and aspect ratio
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    # 1. Find dark regions (panel borders are typically black or dark)
    _, dark = cv2.threshold(gray, 40, 255, cv2.THRESH_BINARY_INV)

    # 2. Dilate to connect broken borders
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (gap_threshold, gap_threshold))
    dark_dilated = cv2.dilate(dark, kernel, iterations=2)

    # 3. Invert: now panel interiors are white, borders are black
    #    Actually we want the non-border regions as connected components
    #    So threshold the original: bright regions are panel interiors
    _, bright = cv2.threshold(gray, 180, 255, cv2.THRESH_BINARY)

    # 4. Combine: bright regions NOT touching dark borders = panel interiors
    #    Use the dark mask to erode bright regions at borders
    bright_masked = cv2.bitwise_and(bright, cv2.bitwise_not(dark_dilated))

    # 5. Morphological cleanup
    kernel_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    cleaned = cv2.morphologyEx(bright_masked, cv2.MORPH_OPEN, kernel_open, iterations=2)
    cleaned = cv2.morphologyEx(cleaned, cv2.MORPH_CLOSE, kernel_open, iterations=3)

    # 6. Connected components
    num_labels, labels, stats, centroids = cv2.connectedComponentsWithStats(cleaned, connectivity=8)

    min_area = min_panel_area * h * w
    panels = []

    for i in range(1, num_labels):  # Skip background
        area = stats[i, cv2.CC_STAT_AREA]
        if area < min_area:
            continue

        x, y, sw, sh = stats[i, :4]

        # Aspect ratio check — panels are usually rectangular
        aspect = sh / max(1, sw)
        if aspect < 0.15 or aspect > 8.0:
            continue

        panels.append(PanelDto(
            x=float(x),
            y=float(y),
            width=float(sw),
            height=float(sh),
            confidence=min(1.0, area / (min_area * 2)),
        ))

    # Sort panels by reading order (determined later, default top-to-bottom)
    panels.sort(key=lambda p: (p.y // 50, p.y), )  # Group by row
    for idx, panel in enumerate(panels):
        panel.index = idx

    return panels


def detect_panels_by_projection(
    image: np.ndarray,
    threshold: float = 0.3,  # Fraction of dark pixels to count as border
) -> List[PanelDto]:
    """Detect panels using horizontal and vertical projection profiles.

    Strategy:
    1. Compute horizontal projection (dark pixels per row)
    2. Compute vertical projection (dark pixels per column)
    3. Find gaps in projections = panel boundaries
    4. Intersect H and V gaps to get panel rectangles
    """
    h, w = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    # Threshold dark pixels
    _, dark = cv2.threshold(gray, 50, 1, cv2.THRESH_BINARY_INV)
    dark = dark.astype(np.uint8)

    # Horizontal projection: dark pixels per row
    h_proj = dark.sum(axis=1)
    # Vertical projection: dark pixels per column
    v_proj = dark.sum(axis=0)

    # Normalize
    h_max = h_proj.max() if h_proj.max() > 0 else 1
    v_max = v_proj.max() if v_proj.max() > 0 else 1
    h_norm = h_proj / h_max
    v_norm = v_proj / v_max

    # Find dark bands (panel borders)
    h_bands = h_norm > threshold
    v_bands = v_norm > threshold

    # Find transitions: where bands start/end
    h_transitions = _find_transitions(h_bands)
    v_transitions = _find_transitions(v_bands)

    if not h_transitions or not v_transitions:
        return []

    # Create panel rectangles from transitions
    panels = []
    min_area = 0.01 * h * w

    for yi, yj in h_transitions:
        for xi, xj in v_transitions:
            area = (yj - yi) * (xj - xi)
            if area < min_area:
                continue
            panels.append(PanelDto(
                x=float(xi),
                y=float(yi),
                width=float(xj - xi),
                height=float(yj - yi),
                confidence=0.7,
            ))

    return panels


def _find_transitions(band: np.ndarray) -> List[Tuple[int, int]]:
    """Find transitions in a 1D boolean array.

    Returns list of (start, end) tuples for True regions.
    """
    transitions = []
    in_region = False
    start = 0

    for i, val in enumerate(band):
        if val and not in_region:
            start = i
            in_region = True
        elif not val and in_region:
            transitions.append((start, i))
            in_region = False

    if in_region:
        transitions.append((start, len(band)))

    return transitions


# ---------------------------------------------------------------------------
# Reading order inference
# ---------------------------------------------------------------------------

# Source language -> default reading direction
_LANG_READING_ORDER = {
    'japanese': 'rtl',
    'chinese': 'ltr',  # Modern Chinese is LTR
    'korean': 'ltr',  # Modern Korean is LTR
    'english': 'ltr',
    'manhwa': 'ltr',
    'manhua': 'ltr',
}


def infer_reading_order(
    source_lang: str = 'japanese',
    text_blocks: Optional[list] = None,
    panels: Optional[List[PanelDto]] = None,
) -> ReadingOrderDto:
    """Infer page-level reading order.

    Uses a multi-signal approach:
    1. Language hint (strongest signal)
    2. Visual analysis of text block arrangement
    3. Panel arrangement
    """
    details = {}

    # 1. Language hint
    lang_lower = source_lang.lower().replace('_', '-')
    lang_direction = 'ltr'
    for key, direction in _LANG_READING_ORDER.items():
        if key in lang_lower:
            lang_direction = direction
            break

    details['language_hint'] = lang_direction

    # 2. Visual analysis from text blocks
    visual_direction = None
    if text_blocks and len(text_blocks) >= 2:
        visual_direction = _visual_reading_order(text_blocks)
        details['visual_analysis'] = visual_direction

    if panels and len(panels) >= 2:
        panel_direction = _panel_reading_order(panels)
        details['panel_analysis'] = panel_direction
        if visual_direction is None and panel_direction is not None:
            visual_direction = panel_direction

    # 3. Combine signals
    if visual_direction == lang_direction:
        direction = lang_direction
        source = 'language+visual'
        confidence = 0.95
    elif visual_direction is not None:
        # Visual contradicts language — trust language for known manga types
        direction = lang_direction
        source = 'language'
        confidence = 0.8
        details['note'] = f'Visual suggests {visual_direction}, using language hint'
    else:
        direction = lang_direction
        source = 'language'
        confidence = 0.7

    # Infer orientation from text blocks
    orientation = 'horizontal'
    if text_blocks and len(text_blocks) >= 2:
        orientation = _infer_orientation(text_blocks)

    return ReadingOrderDto(
        direction=direction,
        orientation=orientation,
        source=source,
        confidence=confidence,
        details=details,
    )


def _visual_reading_order(text_blocks: list) -> Optional[str]:
    """Infer reading order from text block positions.

    If text blocks flow right-to-left (higher X first), it's RTL.
    """
    centers = []
    for block in text_blocks:
        if hasattr(block, 'center'):
            c = block.center
            if isinstance(c, np.ndarray):
                c = c.tolist()
            if isinstance(c, (list, tuple)) and len(c) >= 2:
                centers.append([float(c[0]), float(c[1])])
        elif hasattr(block, 'xyxy') and block.xyxy is not None:
            xyxy = block.xyxy
            if hasattr(xyxy, 'x'):
                x1, y1, x2, y2 = xyxy.x(), xyxy.y(), xyxy.x() + xyxy.width(), xyxy.y() + xyxy.height()
            else:
                x1, y1, x2, y2 = xyxy
            centers.append([float(x1 + x2) / 2, float(y1 + y2) / 2])

    if len(centers) < 2:
        return None

    centers = np.array(centers, dtype=float)

    # Sort by Y (top to bottom)
    sorted_by_y = centers[centers[:, 1].argsort()]

    # Check if within horizontal bands, X decreases (RTL) or increases (LTR)
    y_coords = centers[:, 1]
    band_height = (y_coords.max() - y_coords.min()) * 0.3
    if band_height < 10:
        band_height = 30

    rtl_pairs = 0
    ltr_pairs = 0

    for i in range(len(sorted_by_y)):
        for j in range(i + 1, len(sorted_by_y)):
            dy = abs(sorted_by_y[i, 1] - sorted_by_y[j, 1])
            if dy <= band_height:
                # Same horizontal band
                if sorted_by_y[i, 0] > sorted_by_y[j, 0]:
                    rtl_pairs += 1
                else:
                    ltr_pairs += 1

    total = rtl_pairs + ltr_pairs
    if total < 2:
        return None

    if rtl_pairs > ltr_pairs * 1.3:
        return 'rtl'
    elif ltr_pairs > rtl_pairs * 1.3:
        return 'ltr'
    return None


def _panel_reading_order(panels: List[PanelDto]) -> Optional[str]:
    """Infer reading order from panel arrangement.

    In manga (RTL), the first panel is usually in the top-right.
    In manhwa/manhua (LTR), the first panel is usually in the top-left.
    """
    if len(panels) < 2:
        return None

    # Sort by Y, find top row
    sorted_by_y = sorted(panels, key=lambda p: p.y)
    top_band = sorted_by_y[0].y + 50

    top_panels = [p for p in panels if abs(p.y - sorted_by_y[0].y) < top_band]
    if len(top_panels) < 2:
        return None

    # Sort top panels by X
    top_panels.sort(key=lambda p: p.x)

    # In RTL, reading starts from right (higher X)
    # In LTR, reading starts from left (lower X)
    # Check if there's content in the rightmost panel that suggests it's first
    # For now, use the convention: if panels are evenly spaced, default to language hint
    return None


def _infer_orientation(text_blocks: list) -> str:
    """Infer text orientation (horizontal vs vertical)."""
    vertical_count = 0
    horizontal_count = 0

    for block in text_blocks:
        if hasattr(block, 'direction') and block.direction:
            if block.direction == 'vertical':
                vertical_count += 1
            else:
                horizontal_count += 1
        elif hasattr(block, 'xyxy') and block.xyxy is not None:
            x1, y1, x2, y2 = block.xyxy
            w = x2 - x1
            h = y2 - y1
            if h > w * 1.3:  # Tall text = vertical
                vertical_count += 1
            else:
                horizontal_count += 1

    return 'vertical' if vertical_count > horizontal_count else 'horizontal'


# ---------------------------------------------------------------------------
# Page Analysis Service
# ---------------------------------------------------------------------------

class PageAnalysisService:
    """Page-level analysis: panels, reading order, writing mode.

    Usage:
        service = PageAnalysisService()
        result = service.analyze(image, source_lang='japanese', text_blocks=blocks)
    """

    def __init__(self):
        pass

    def analyze(
        self,
        image: np.ndarray,
        source_lang: str = 'japanese',
        text_blocks: Optional[list] = None,
        detect_panels_flag: bool = True,
    ) -> PageAnalysisResult:
        """Perform full page analysis.

        Args:
            image: Page image (BGR or grayscale)
            source_lang: Source language for reading order hint
            text_blocks: Detected text blocks for visual analysis
            detect_panels_flag: Whether to run panel detection

        Returns:
            PageAnalysisResult with panels, reading order, writing mode
        """
        h, w = image.shape[:2]
        result = PageAnalysisResult(
            page_width=w,
            page_height=h,
        )

        # 1. Panel detection
        panels = []
        if detect_panels_flag:
            try:
                panels = detect_panels(image)
                if not panels:
                    panels = detect_panels_by_projection(image)
            except Exception:
                logger.debug("Panel detection failed, using full page", exc_info=True)

        result.panels = panels

        # 2. Reading order
        reading_order = infer_reading_order(source_lang, text_blocks, panels)
        result.reading_order = reading_order

        # 3. Writing mode (from orientation)
        result.writing_mode = reading_order.orientation

        # 4. Assign panel reading order indices
        self._assign_panel_order(result.panels, reading_order.direction)

        return result

    def _assign_panel_order(self, panels: List[PanelDto], direction: str):
        """Assign reading order indices to panels."""
        if not panels:
            return

        # Sort into rows first
        rows = self._group_into_rows(panels)

        idx = 0
        for row in rows:
            if direction == 'rtl':
                row.sort(key=lambda p: -p.x)  # Right to left
            else:
                row.sort(key=lambda p: p.x)  # Left to right

            for panel in row:
                panel.index = idx
                idx += 1

    def _group_into_rows(self, panels: List[PanelDto]) -> List[List[PanelDto]]:
        """Group panels into horizontal rows."""
        if not panels:
            return []

        # Sort by Y
        sorted_by_y = sorted(panels, key=lambda p: p.y)

        rows = [[sorted_by_y[0]]]
        for panel in sorted_by_y[1:]:
            last_row = rows[-1]
            ref_y = last_row[0].y
            ref_h = last_row[0].height

            if abs(panel.y - ref_y) < ref_h * 0.4:
                last_row.append(panel)
            else:
                rows.append([panel])

        return rows


# ---------------------------------------------------------------------------
# Singleton instance
# ---------------------------------------------------------------------------

service = PageAnalysisService()
