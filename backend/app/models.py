import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Any, Dict
import numpy as np
from PySide6.QtCore import QRectF


@dataclass
class TextBubble:
    id: int
    box: QRectF
    text: str = ""
    translated: str = ""
    text_box: Optional[QRectF] = None
    layout_box: Optional[QRectF] = None
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
    item: Any = None  # Reference to BubbleGraphicsItem

    @staticmethod
    def _rect_to_project_list(rect: Optional[QRectF]) -> Optional[list[float]]:
        if rect is None:
            return None
        return [rect.x(), rect.y(), rect.width(), rect.height()]

    @staticmethod
    def _rect_from_project_list(values: Optional[list[float]]) -> Optional[QRectF]:
        if not values:
            return None
        x, y, width, height = values
        return QRectF(x, y, width, height)

    def source_box(self) -> QRectF:
        """Return the original detected text area used for OCR/inpainting."""
        return self.text_box if self.text_box is not None else self.box

    def source_xyxy(self) -> list[float]:
        rect = self.source_box()
        return [rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height()]

    def to_project_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "box": [self.box.x(), self.box.y(), self.box.width(), self.box.height()],
            "text": self.text,
            "translated": self.translated,
            "status": self.status,
            "problems": list(self.problems),
            "edited": self.edited,
            "style": {
                "font_family": self.font_family,
                "font_size": self.font_size,
                "bold": self.bold,
                "italic": self.italic,
                "color": self.color,
                "alignment": self.alignment,
            },
            "layout_plan": {
                "writing_mode": self.writing_mode,
                "text_direction": self.text_direction,
                "justification": self.justification,
                "padding": dict(self.layout_padding),
                "margin": dict(self.layout_margin),
                "confidence": self.layout_confidence,
                "reasoning": self.layout_reasoning,
            },
        }
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
        return cls(
            id=data["id"],
            box=QRectF(x, y, width, height),
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
        )

    def without_item(self) -> "TextBubble":
        return TextBubble(
            id=self.id,
            box=QRectF(self.box),
            text=self.text,
            translated=self.translated,
            text_box=QRectF(self.text_box) if self.text_box is not None else None,
            layout_box=QRectF(self.layout_box) if self.layout_box is not None else None,
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
        )


@dataclass
class MangaPage:
    file_path: str
    cv_image: np.ndarray
    inpainted_image: Optional[np.ndarray] = None
    bubbles: List[TextBubble] = field(default_factory=list)
    bubble_counter: int = 0
    # User-assigned display name (incl. extension). Overrides basename(file_path)
    # for the sidebar/filtering. None = use the original file name.
    display_name: Optional[str] = None
    page_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "idle"
    problems: List[str] = field(default_factory=list)

    def to_project_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "page_id": self.page_id,
            "file_path": self.file_path,
            "bubble_counter": self.bubble_counter,
            "status": self.status,
            "problems": list(self.problems),
            "bubbles": [bubble.to_project_dict() for bubble in self.bubbles],
        }
        if self.display_name:
            data["display_name"] = self.display_name
        return data

    @classmethod
    def from_project_dict(cls, data: dict[str, Any], cv_image: np.ndarray) -> "MangaPage":
        bubbles = [TextBubble.from_project_dict(bubble_data) for bubble_data in data.get("bubbles", [])]
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
        )
