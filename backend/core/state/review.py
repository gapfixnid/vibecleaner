from ..models import BubbleProblemCode, MangaPage, TextBubble


def derive_bubble_status(bubble: TextBubble) -> str:
    if bubble.status == "error":
        return "error"
    if bubble.edited:
        return "edited"
    if bubble.problems:
        codes = {problem.code for problem in bubble.problems}
        if BubbleProblemCode.TRANSLATION_EXPANDED in codes:
            return "translation_warning"
        if BubbleProblemCode.OCR_UNCERTAIN in codes:
            return "ocr_warning"
        if BubbleProblemCode.TEXT_OVERFLOW in codes:
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
