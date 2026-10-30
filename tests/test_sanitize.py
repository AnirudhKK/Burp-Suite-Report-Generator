from burp_report.sanitize import sanitize_html


def test_dangerous_markup_is_removed():
    out = sanitize_html(
        '<p onclick="x">a<script>alert(1)</script><a href="javascript:alert(1)">l</a>'
        '<img src=x onerror=1><iframe src="https://e.com"></iframe></p>'
    )
    for bad in ("onclick", "<script", "alert(1)", "javascript:", "<img", "onerror", "<iframe"):
        assert bad not in out


def test_safe_markup_is_kept():
    out = sanitize_html('<p>Text <b>bold</b> <code>x</code><a href="https://e.com/a">link</a></p><ul><li>i</li></ul>')
    assert "<b>bold</b>" in out and "<code>x</code>" in out and "<li>i</li>" in out
    assert 'href="https://e.com/a" target="_blank" rel="noopener noreferrer"' in out
