from backend.pipeline.page_translation_stages import _is_better_ocr_text, _is_suspicious_ocr_text


def test_short_ocr_text_is_marked_suspicious():
    assert _is_suspicious_ocr_text("")
    assert _is_suspicious_ocr_text("あ")
    assert _is_suspicious_ocr_text("OK")
    assert not _is_suspicious_ocr_text("hello")


def test_retry_only_replaces_with_non_empty_longer_text():
    assert _is_better_ocr_text("", "hello")
    assert _is_better_ocr_text("あ", "こんにちは")
    assert not _is_better_ocr_text("OK", "X")
    assert not _is_better_ocr_text("OK", "")
