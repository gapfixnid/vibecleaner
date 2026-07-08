# engines/rendering/typesetting.py
# DP-based line breaking and font fitting with cost functions.
#
# Replaces greedy wrapping with dynamic programming that minimizes:
#   Cost = overflow³ + raggedness² + widow_penalty + orphan_penalty
#         + hyphen_penalty + too_many_lines_penalty
#
# Font fitting uses binary search + cost function to find the
# most visually pleasing size, not just the largest that fits:
#   Cost = Overflow × 1000 + Unused_Area × 2 + Aspect_Penalty × 3
#         + Too_Many_Lines × 5

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class LineBreakResult:
    """Result of DP line breaking."""
    lines: List[str]
    cost: float


@dataclass
class FontFitResult:
    """Result of font fitting."""
    fontSize: int
    wrappedText: str
    cost: float
    overflow: bool
    contentWidth: float
    contentHeight: float


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Font size search range
FONT_SIZE_MIN = 6
FONT_SIZE_MAX = 300

# Cost function weights
WEIGHT_OVERFLOW = 1000.0      # overflow³ penalty (dominant)
WEIGHT_RAGGEDNESS = 1.0       # raggedness² penalty
WEIGHT_WIDOW = 500.0          # last line too short
WEIGHT_ORPHAN = 500.0         # first line too short (multi-line)
WEIGHT_HYPHEN = 50.0          # hyphenated line break
WEIGHT_TOO_MANY_LINES = 200.0 # exceeds preferred line count

WEIGHT_UNUSED_AREA = 2.0      # for font fitting
WEIGHT_ASPECT_PENALTY = 3.0   # for font fitting
WEIGHT_FIT_TOO_MANY_LINES = 5.0  # for font fitting

# Widow/orphan threshold (fraction of total lines)
WIDOW_ORPHAN_THRESHOLD = 0.3


# ---------------------------------------------------------------------------
# Text segmentation helpers
# ---------------------------------------------------------------------------

def _split_into_chunks(text: str, no_space: bool) -> List[str]:
    """Split text into indivisible chunks for line breaking.

    For space-separated languages: split on whitespace, keeping chunks
    as words (spaces are added between words on the same line).

    For no-space languages (CJK, etc.): each character is a chunk,
    but spaces are preserved as characters (not stripped).
    """
    if no_space:
        # Each character is a chunk; spaces are kept as regular chars
        paragraphs = text.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        chunks: List[str] = []
        for i, para in enumerate(paragraphs):
            chars = list(para)  # keep all characters including spaces
            chunks.extend(chars)
            if i < len(paragraphs) - 1:
                chunks.append('\n')  # mandatory break
        return chunks if chunks else ['']
    else:
        # Standard word splitting — spaces handled in line assembly
        words = text.split()
        return words if words else ['']


def _is_mandatory_break(chunk: str) -> bool:
    """Return True if this chunk forces a new line."""
    return chunk == '\n'


# ---------------------------------------------------------------------------
# DP line breaking
# ---------------------------------------------------------------------------

def _assemble_line(chunks: List[str], no_space: bool) -> str:
    """Assemble chunks into a line string.

    For no_space mode: concatenate directly (spaces are already in chunks).
    For space mode: join words with spaces.
    """
    if no_space:
        return ''.join(chunks)
    else:
        return ' '.join(chunks)


def _line_cost(
    chunks: List[str],
    start: int,
    end: int,
    max_width: float,
    measure: Callable[[str], float],
    no_space: bool,
) -> Tuple[float, float]:
    """Compute the cost of putting chunks[start:end] on one line.

    Returns (cost, line_width). cost is huge if the line overflows.
    """
    line_text = _assemble_line(chunks[start:end], no_space)
    width = measure(line_text)
    overflow = max(0.0, width - max_width)

    if overflow > 0:
        return (WEIGHT_OVERFLOW * (overflow ** 3), width)
    return (0.0, width)


def dp_wrap_text(
    text: str,
    measure: Callable[[str], float],
    max_width: float,
    max_height: float,
    no_space: bool = False,
    max_lines: int = 0,
    line_height: float | None = None,
) -> LineBreakResult:
    """DP-based line breaking with cost function.

    Finds the line break combination that minimizes total cost:
        Cost = overflow³ + raggedness² + widow + orphan + hyphen + too_many_lines

    Args:
        text: The text to wrap.
        measure: Function that returns the width (horizontal) or height
                 (vertical) of a given string.
        max_width: Maximum width of a single line.
        max_height: Maximum total height (sum of all line heights).
        no_space: True for CJK / no-space languages.
        max_lines: Preferred maximum line count (0 = unlimited).
        line_height: Height of a single line.

    Returns:
        LineBreakResult with the optimal list of lines and total cost.
    """
    if line_height is None:
        try:
            line_height = measure("가") * 1.2
            if line_height <= 0:
                line_height = 18.0
        except Exception:
            line_height = 18.0

    chunks = _split_into_chunks(text, no_space)
    n = len(chunks)

    # Group chunks into segments separated by mandatory breaks ('\n')
    segments: List[List[int]] = []  # lists of chunk indices
    current_seg: List[int] = []
    for i in range(n):
        if _is_mandatory_break(chunks[i]):
            segments.append(current_seg)
            current_seg = []
        else:
            current_seg.append(i)
    if current_seg:
        segments.append(current_seg)

    # DP for a single segment under exact target lines R
    def _dp_segment_with_target_lines(seg_indices: List[int], R: int) -> Tuple[List[str], float]:
        m = len(seg_indices)
        if m == 0:
            return ([''], 0.0)

        INF = float('inf')
        # dp[i][r] = min cost to break chunks[i:] starting at row r
        dp_cost = [[INF] * (R + 1) for _ in range(m + 1)]
        dp_break = [[-1] * (R + 1) for _ in range(m + 1)]
        dp_cost[m][R] = 0.0

        # Word-split penalty helper: penalize character-level breaks inside words
        def _get_break_penalty(idx1: int, idx2: int) -> float:
            if idx1 < 0 or idx2 >= m:
                return 0.0
            c1 = chunks[seg_indices[idx1]]
            c2 = chunks[seg_indices[idx2]]
            if c1 != ' ' and c2 != ' ' and len(c1.strip()) > 0 and len(c2.strip()) > 0:
                # Add word break penalty for Korean / CJK
                return 150.0
            return 0.0

        for r in range(R - 1, -1, -1):
            # Calculate elliptical limit width for row r
            y_r = (r + 0.5 - R / 2.0) * line_height
            half_h = max(30.0, max_height / 2.0)
            ratio = y_r / half_h
            ratio_clamped = max(-0.95, min(0.95, ratio))
            limit_w = max_width * math.sqrt(1.0 - ratio_clamped**2)
            limit_w = max(max_width * 0.3, limit_w)

            for i in range(m - 1, -1, -1):
                for j in range(i + 1, m + 1):
                    if r == R - 1 and j < m:
                        # Last row must consume all remaining chunks
                        continue

                    line_chunks = [chunks[idx] for idx in seg_indices[i:j]]
                    line_text = _assemble_line(line_chunks, no_space)
                    line_w = measure(line_text)
                    
                    overflow = max(0.0, line_w - limit_w)
                    line_cost = 0.0
                    if overflow > 0:
                        line_cost += WEIGHT_OVERFLOW * (overflow ** 3)
                    else:
                        rag = limit_w - line_w
                        line_cost += WEIGHT_RAGGEDNESS * (rag ** 2)

                    if j < m:
                        line_cost += _get_break_penalty(j - 1, j)

                    total = line_cost + dp_cost[j][r + 1]
                    if total < dp_cost[i][r]:
                        dp_cost[i][r] = total
                        dp_break[i][r] = j

        if dp_cost[0][0] == INF:
            return ([], INF)

        # Reconstruct optimal lines for target R
        lines: List[str] = []
        pos = 0
        r = 0
        while pos < m and r < R:
            nxt = dp_break[pos][r]
            if nxt <= pos or nxt > m:
                nxt = m
            line_chunks = [chunks[seg_indices[k]] for k in range(pos, nxt)]
            lines.append(_assemble_line(line_chunks, no_space))
            pos = nxt
            r += 1

        return (lines, dp_cost[0][0])

    # Try all reasonable target line counts and choose the best layout
    def _dp_segment(seg_indices: List[int]) -> Tuple[List[str], float]:
        m = len(seg_indices)
        if m == 0:
            return ([''], 0.0)

        best_lines: List[str] = []
        best_cost = float('inf')
        
        # Search from 1 up to a reasonable maximum line count
        max_lines_to_try = min(8, max(1, m // 2 + 1))
        
        for R in range(1, max_lines_to_try + 1):
            lines, cost = _dp_segment_with_target_lines(seg_indices, R)
            if cost < best_cost:
                best_cost = cost
                best_lines = lines

        if not best_lines:
            line_chunks = [chunks[idx] for idx in seg_indices]
            best_lines = [_assemble_line(line_chunks, no_space)]
            best_cost = 1000.0

        return (best_lines, best_cost)

    # Process each segment and combine
    all_lines: List[str] = []
    total_cost = 0.0
    for seg in segments:
        seg_lines, seg_cost = _dp_segment(seg)
        all_lines.extend(seg_lines)
        total_cost += seg_cost

    # Remove empty lines at the ends
    while all_lines and all_lines[0] == '':
        all_lines.pop(0)
    while all_lines and all_lines[-1] == '':
        all_lines.pop(0)

    # ---- Post-processing penalties ----
    num_lines = len(all_lines)

    # Widow penalty: last line is too short relative to max_width
    if num_lines > 1:
        last_line_w = measure(all_lines[-1])
        if last_line_w < max_width * (1 - 0.7):  # less than 30% of max
                total_cost += WEIGHT_WIDOW

    # Orphan penalty: first line is too short
    if num_lines > 1:
        first_line_w = measure(all_lines[0])
        if first_line_w < max_width * (1 - 0.7):
            total_cost += WEIGHT_ORPHAN

    # Too many lines penalty
    if max_lines > 0 and num_lines > max_lines:
        total_cost += WEIGHT_TOO_MANY_LINES * (num_lines - max_lines)

    # Hyphen penalty
    for line in all_lines:
        if line.endswith('-'):
            total_cost += WEIGHT_HYPHEN

    return LineBreakResult(lines=all_lines, cost=total_cost)


# ---------------------------------------------------------------------------
# Font fitting with cost function
# ---------------------------------------------------------------------------

def _font_fit_cost(
    content_width: float,
    content_height: float,
    roi_width: float,
    roi_height: float,
    num_lines: int,
    max_lines: int = 0,
) -> float:
    """Compute cost for a given font size layout.

    Lower cost = better visual fit.

    Cost = Overflow × 1000 + Unused_Area × 2 + Aspect_Penalty × 3
           + Too_Many_Lines × 5
    """
    # Overflow (dominant penalty)
    overflow_w = max(0.0, content_width - roi_width)
    overflow_h = max(0.0, content_height - roi_height)
    overflow = max(overflow_w, overflow_h)
    cost = WEIGHT_UNUSED_AREA * overflow * 1000

    # Unused area (how much empty space is left)
    used_area = content_width * content_height
    total_area = roi_width * roi_height
    if total_area > 0:
        unused_ratio = 1.0 - (used_area / total_area)
        cost += WEIGHT_UNUSED_AREA * unused_ratio * total_area

    # Aspect ratio penalty (prefer content that fills both dimensions evenly)
    if roi_width > 0 and roi_height > 0:
        content_aspect = content_width / content_height if content_height > 0 else 1.0
        roi_aspect = roi_width / roi_height
        aspect_diff = abs(content_aspect - roi_aspect)
        cost += WEIGHT_ASPECT_PENALTY * aspect_diff * 100

    # Too many lines
    if max_lines > 0 and num_lines > max_lines:
        cost += WEIGHT_FIT_TOO_MANY_LINES * (num_lines - max_lines) * 100

    return cost


def fit_font_size(
    text: str,
    measure: Callable[[str, int], Tuple[float, float]],
    roi_width: float,
    roi_height: float,
    no_space: bool = False,
    min_size: int = FONT_SIZE_MIN,
    max_size: int = FONT_SIZE_MAX,
    max_lines: int = 0,
    line_height_ratio: float = 1.2,
) -> FontFitResult:
    """Find the best font size using binary search + cost function.

    Unlike a simple "largest that fits" approach, this finds the font
    size that produces the most visually pleasing layout by minimizing
    a cost function that considers overflow, unused area, aspect ratio,
    and line count.

    Args:
        text: The text to fit.
        measure: Function(font_size) -> (content_width, content_height)
                 for the wrapped text at that font size.
        roi_width: Target width in pixels.
        roi_height: Target height in pixels.
        no_space: True for CJK / no-space languages.
        min_size: Minimum font size (default 6).
        max_size: Maximum font size (default 300).
        max_lines: Preferred maximum line count (0 = unlimited).
        line_height_ratio: Multiplier for line height (default 1.2).

    Returns:
        FontFitResult with the optimal font size and metrics.
    """
    def _evaluate(font_size: int) -> Tuple[float, str, float, float]:
        """Evaluate layout at a given font size. Returns (cost, wrapped, w, h)."""
        result = dp_wrap_text(
            text=text,
            measure=lambda s: measure(s, font_size)[0],  # width only for wrapping
            max_width=roi_width,
            max_height=roi_height,
            no_space=no_space,
            max_lines=max_lines,
            line_height=font_size * line_height_ratio,
        )
        wrapped = '\n'.join(result.lines)
        w, h = measure(wrapped, font_size)
        cost = _font_fit_cost(w, h, roi_width, roi_height, len(result.lines), max_lines)
        return cost, wrapped, w, h

    best_cost = float('inf')
    best_size = min_size
    best_wrapped = text
    best_w = 0.0
    best_h = 0.0

    # Binary search for the transition point (fits → doesn't fit)
    lo, hi = min_size, max_size
    while lo <= hi:
        mid = (lo + hi) // 2
        cost, wrapped, w, h = _evaluate(mid)
        overflow = max(0, w - roi_width, h - roi_height)

        if overflow == 0:
            # Fits — try larger
            if cost < best_cost:
                best_cost = cost
                best_size = mid
                best_wrapped = wrapped
                best_w = w
                best_h = h
            lo = mid + 1
        else:
            # Doesn't fit — try smaller
            hi = mid - 1

    # Check neighbors of the transition point for better cost
    for size_offset in range(-3, 4):
        size = best_size + size_offset
        if size < min_size or size > max_size:
            continue
        cost, wrapped, w, h = _evaluate(size)
        if cost < best_cost:
            best_cost = cost
            best_size = size
            best_wrapped = wrapped
            best_w = w
            best_h = h

    overflow = max(0.0, best_w - roi_width, best_h - roi_height)

    return FontFitResult(
        fontSize=best_size,
        wrappedText=best_wrapped,
        cost=best_cost,
        overflow=overflow > 0,
        contentWidth=best_w,
        contentHeight=best_h,
    )
