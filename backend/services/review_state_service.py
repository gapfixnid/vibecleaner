from app.models import MangaPage, TextBubble


def derive_bubble_status(bubble: TextBubble) -> str:
    if bubble.status == "error":
        return "error"
    if bubble.edited:
        return "edited"
    if bubble.problems:
        if any("translation" in p.lower() for p in bubble.problems):
            return "translation_warning"
        if any("ocr" in p.lower() for p in bubble.problems):
            return "ocr_warning"
        if any("overflow" in p.lower() for p in bubble.problems):
            return "layout_overflow"
        return "needs_review"
    if (bubble.translated or "").strip():
        return "ok"
    return "needs_review"


def derive_page_status(page: MangaPage) -> str:
    if page.status == "error":
        return "error"
    if page.problems:
        return "has_warnings"
    if any(derive_bubble_status(b) not in {"ok", "edited"} for b in page.bubbles):
        return "has_warnings" if page.bubbles else "idle"
    if page.inpainted_image is not None and page.bubbles:
        return "ready_for_review"
    return page.status if page.status not in {"processing", "reviewed", "exported"} else page.status


def refresh_bubble_status(bubble: TextBubble) -> None:
    bubble.status = derive_bubble_status(bubble)


def refresh_page_status(page: MangaPage) -> None:
    for bubble in page.bubbles:
        refresh_bubble_status(bubble)
    page.status = derive_page_status(page)
