from burp_report.highlight import candidates, compile_candidates, spans, to_markup


def test_payload_named_in_issue_detail(sample_scan):
    xss = sample_scan.issues[0]
    assert candidates(xss.issue_detail, xss.detail_items) == ["abc<script>alert(1)</script>xyz"]


def test_detail_items_are_candidates(sample_scan):
    emails = next(i for i in sample_scan.issues if i.name == "Email addresses disclosed")
    assert candidates(emails.issue_detail, emails.detail_items) == ["support@example.com", "admin@example.com"]


def test_plain_bold_words_are_ignored():
    assert candidates("<p>The <b>q</b> parameter is <b>vulnerable</b>.</p>") == []


def test_matches_raw_url_and_html_encoded():
    pats = compile_candidates(["a<b>'c"])
    text = "raw a<b>'c | url a%3Cb%3E%27c | html a&lt;b&gt;&#39;c | other abc"
    found = [text[s:e] for s, e in spans(text, pats)]
    assert found == ["a<b>'c", "a%3Cb%3E%27c", "a&lt;b&gt;&#39;c"]


def test_markup_escapes_text_and_marks():
    out = str(to_markup("x<script>y", [(1, 9)]))
    assert out == 'x<mark class="hl">&lt;script&gt;</mark>y'
