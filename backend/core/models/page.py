from __future__ import annotations

import uuid
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .geometry import Box, Rect


@dataclass
class Bubble:
    """Minimal render-port DTO. The runtime domain model is TextBubble."""

    id: str
    box: Box
    text: str = ""
    translated: str = ""


@dataclass
class TextBubble:
    id: int
    box: Rect
    text: str = ""
    translated: str = ""
    text_box: Optional[Rect] = None
    layout_box: Optional[Rect] = None
    text_class: str = ""
    font_family: str = ""
    font_size: int = 0
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    alignment: str = "center"
    writing_mode: str = "horizontal"
    text_direction: str = "ltr"
    justification: str = "none"
    layout_padding: Dict[str, float] = field(default_factory=dict)
    layout_margin: Dict[str, float] = field(default_factory=dict)
    layout_confidence: float = 0.0
    layout_reasoning: str = ""
    status: str = "idle"
    problems: List[str] = field(default_factory=list)
    edited: bool = False
    project_extensions: Dict[str, Any] = field(default_factory=dict, repr=False)

    @staticmethod
    def _rect_to_project_list(rect: Optional[Rect]) -> Optional[list[float]]:
        if rect is None:
            return None
        return rect.to_xywh()

    @staticmethod
    def _rect_from_project_list(values: Optional[list[float]]) -> Optional[Rect]:
        if not values:
            return None
        x, y, width, height = values
        return Rect(x, y, width, height)

    def source_box(self) -> Rect:
        """Return the original detected text area used for OCR/inpainting."""
        return self.text_box if self.text_box is not None else self.box

    def source_xyxy(self) -> list[float]:
        return self.source_box().to_xyxy()

    def to_project_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = deepcopy(self.project_extensions)
        style = data.get("style") if isinstance(data.get("style"), dict) else {}
        style.update({
            "font_family": self.font_family,
            "font_size": self.font_size,
            "bold": self.bold,
            "italic": self.italic,
            "color": self.color,
            "alignment": self.alignment,
        })
        layout_plan = data.get("layout_plan") if isinstance(data.get("layout_plan"), dict) else {}
        layout_plan.update({
            "writing_mode": self.writing_mode,
            "text_direction": self.text_direction,
            "justification": self.justification,
            "padding": dict(self.layout_padding),
            "margin": dict(self.layout_margin),
            "confidence": self.layout_confidence,
            "reasoning": self.layout_reasoning,
        })
        data.update({
            "id": self.id,
            "box": self.box.to_xywh(),
            "text": self.text,
            "translated": self.translated,
            "status": self.status,
            "problems": list(self.problems),
            "edited": self.edited,
            "style": style,
            "layout_plan": layout_plan,
        })
        text_box = self._rect_to_project_list(self.text_box)
        if text_box is not None:
            data["text_box"] = text_box
        layout_box = self._rect_to_project_list(self.layout_box)
        if layout_box is not None:
            data["layout_box"] = layout_box
        if self.text_class:
            data["text_class"] = self.text_class
        return data

    @classmethod
    def from_project_dict(cls, data: dict[str, Any]) -> "TextBubble":
        x, y, width, height = data["box"]
        style = data.get("style", {})
        layout_plan = data.get("layout_plan", {})
        known_keys = {
            "id", "box", "text", "translated", "text_box", "layout_box", "text_class",
            "status", "problems", "edited", "style", "layout_plan", "font_family", "font_size",
            "bold", "italic", "color", "alignment", "writing_mode", "text_direction",
            "justification", "layout_padding", "layout_margin", "layout_confidence", "layout_reasoning",
        }
        extensions = {key: deepcopy(value) for key, value in data.items() if key not in known_keys}
        unknown_style = {
            key: deepcopy(value)
            for key, value in style.items()
            if key not in {"font_family", "font_size", "bold", "italic", "color", "alignment"}
        }
        unknown_layout = {
            key: deepcopy(value)
            for key, value in layout_plan.items()
            if key not in {"writing_mode", "text_direction", "justification", "padding", "margin", "confidence", "reasoning"}
        }
        if unknown_style:
            extensions["style"] = unknown_style
        if unknown_layout:
            extensions["layout_plan"] = unknown_layout
        return cls(
            id=data["id"],
            box=Rect(x, y, width, height),
            text=data.get("text", ""),
            translated=data.get("translated", ""),
            text_box=cls._rect_from_project_list(data.get("text_box")),
            layout_box=cls._rect_from_project_list(data.get("layout_box")),
            text_class=data.get("text_class", ""),
            font_family=style.get("font_family", data.get("font_family", "")),
            font_size=style.get("font_size", data.get("font_size", 0)),
            bold=style.get("bold", data.get("bold", False)),
            italic=style.get("italic", data.get("italic", False)),
            color=style.get("color", data.get("color", "#000000")),
            alignment=style.get("alignment", data.get("alignment", "center")),
            writing_mode=layout_plan.get("writing_mode", data.get("writing_mode", "horizontal")),
            text_direction=layout_plan.get("text_direction", data.get("text_direction", "ltr")),
            justification=layout_plan.get("justification", data.get("justification", "none")),
            layout_padding=dict(layout_plan.get("padding", data.get("layout_padding", {}))),
            layout_margin=dict(layout_plan.get("margin", data.get("layout_margin", {}))),
            layout_confidence=float(layout_plan.get("confidence", data.get("layout_confidence", 0.0)) or 0.0),
            layout_reasoning=layout_plan.get("reasoning", data.get("layout_reasoning", "")),
            status=data.get("status", "idle"),
            problems=list(data.get("problems", [])),
            edited=bool(data.get("edited", False)),
            project_extensions=extensions,
        )

    def clone(self) -> "TextBubble":
        """Deep-enough copy for cross-thread snapshots (rects are immutable)."""
        return TextBubble(
            id=self.id,
            box=self.box,
            text=self.text,
            translated=self.translated,
            text_box=self.text_box,
            layout_box=self.layout_box,
            text_class=self.text_class,
            font_family=self.font_family,
            font_size=self.font_size,
            bold=self.bold,
            italic=self.italic,
            color=self.color,
            alignment=self.alignment,
            writing_mode=self.writing_mode,
            text_direction=self.text_direction,
            justification=self.justification,
            layout_padding=dict(self.layout_padding),
            layout_margin=dict(self.layout_margin),
            layout_confidence=self.layout_confidence,
            layout_reasoning=self.layout_reasoning,
            status=self.status,
            problems=list(self.problems),
            edited=self.edited,
            project_extensions=deepcopy(self.project_extensions),
        )


@dataclass
class MangaPage:
    file_path: str
    cv_image: Any = None
    inpainted_image: Any = None
    bubbles: List[TextBubble] = field(default_factory=list)
    bubble_counter: int = 0
    # User-assigned display name (incl. extension). Overrides basename(file_path)
    # for the sidebar/filtering. None = use the original file name.
    display_name: Optional[str] = None
    page_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "idle"
    problems: List[str] = field(default_factory=list)
    project_extensions: Dict[str, Any] = field(default_factory=dict, repr=False)

    def to_project_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = deepcopy(self.project_extensions)
        data.update({
            "page_id": self.page_id,
            "file_path": self.file_path,
            "bubble_counter": self.bubble_counter,
            "status": self.status,
            "problems": list(self.problems),
            "bubbles": [bubble.to_project_dict() for bubble in self.bubbles],
        })
        if self.display_name:
            data["display_name"] = self.display_name
        return data

    @classmethod
    def from_project_dict(cls, data: dict[str, Any], cv_image: Any) -> "MangaPage":
        bubbles = [TextBubble.from_project_dict(bubble_data) for bubble_data in data.get("bubbles", [])]
        known_keys = {
            "page_id", "file_path", "original_file_path", "file_name", "inpaint_file_name",
            "bubble_counter", "display_name", "status", "problems", "bubbles",
        }
        extensions = {key: deepcopy(value) for key, value in data.items() if key not in known_keys}
        return cls(
            page_id=data.get("page_id") or uuid.uuid4().hex,
            file_path=data.get("file_path") or data.get("original_file_path", ""),
            cv_image=cv_image,
            inpainted_image=None,
            bubbles=bubbles,
            bubble_counter=data.get("bubble_counter", len(bubbles)),
            display_name=data.get("display_name"),
            status=data.get("status", "idle"),
            problems=list(data.get("problems", [])),
            project_extensions=extensions,
        )
