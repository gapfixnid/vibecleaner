import uuid
from dataclasses import dataclass, field
from typing import List, Optional, Any
import numpy as np
from PySide6.QtCore import QRectF


@dataclass
class TextBubble:
    id: int
    box: QRectF
    text: str = ""
    translated: str = ""
    text_box: Optional[QRectF] = None
    text_class: str = ""
    font_family: str = ""
    font_size: int = 0
    bold: bool = False
    italic: bool = False
    color: str = "#000000"
    alignment: str = "center"
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
            "style": {
                "font_family": self.font_family,
                "font_size": self.font_size,
                "bold": self.bold,
                "italic": self.italic,
                "color": self.color,
                "alignment": self.alignment,
            },
        }
        text_box = self._rect_to_project_list(self.text_box)
        if text_box is not None:
            data["text_box"] = text_box
        if self.text_class:
            data["text_class"] = self.text_class
        return data

    @classmethod
    def from_project_dict(cls, data: dict[str, Any]) -> "TextBubble":
        x, y, width, height = data["box"]
        style = data.get("style", {})
        return cls(
            id=data["id"],
            box=QRectF(x, y, width, height),
            text=data.get("text", ""),
            translated=data.get("translated", ""),
            text_box=cls._rect_from_project_list(data.get("text_box")),
            text_class=data.get("text_class", ""),
            font_family=style.get("font_family", data.get("font_family", "")),
            font_size=style.get("font_size", data.get("font_size", 0)),
            bold=style.get("bold", data.get("bold", False)),
            italic=style.get("italic", data.get("italic", False)),
            color=style.get("color", data.get("color", "#000000")),
            alignment=style.get("alignment", data.get("alignment", "center")),
        )

    def without_item(self) -> "TextBubble":
        return TextBubble(
            id=self.id,
            box=QRectF(self.box),
            text=self.text,
            translated=self.translated,
            text_box=QRectF(self.text_box) if self.text_box is not None else None,
            text_class=self.text_class,
            font_family=self.font_family,
            font_size=self.font_size,
            bold=self.bold,
            italic=self.italic,
            color=self.color,
            alignment=self.alignment,
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

    def to_project_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "page_id": self.page_id,
            "file_path": self.file_path,
            "bubble_counter": self.bubble_counter,
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
        )
