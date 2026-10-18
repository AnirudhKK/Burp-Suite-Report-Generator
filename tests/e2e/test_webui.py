"""End-to-end tests of the web UI in Microsoft Edge. They run in order and share one page."""
import http.client
import json
import time
import zipfile
from urllib.parse import unquote

import pytest
from playwright.sync_api import expect

from ..conftest import SAMPLE, SESSION_COOKIE

pytestmark = pytest.mark.e2e


@pytest.fixture(scope="module")
def dl(tmp_path_factory):
    return tmp_path_factory.mktemp("downloads")


def wait_ready(page, timeout=20000):
    expect(page.locator("#status")).to_have_text("Up to date", timeout=timeout)


def preview(page):
    return page.frame_locator("#htmlFrame")


def preview_frame(page):
    return page.frame(url=lambda u: "/preview/" in u)


def bump(page, sel, value):
    page.locator(sel).fill(value)
    page.wait_for_timeout(50)
    wait_ready(page)


def open_panel(page, n):
    d = page.locator("details.panel").nth(n - 1)
    if d.get_attribute("open") is None:
        d.locator("summary").click()


def chips(page):
    return [" ".join(c.split()) for c in preview(page).locator(".toolbar .chip").all_inner_texts()]


def test_empty_state(page):
    expect(page.locator("#empty")).to_be_visible()
    for b in ("#exportHtml", "#exportPdf", "#exportDocx"):
        expect(page.locator(b)).to_be_disabled()
    expect(page.locator("#loadSample")).to_be_visible()


def test_load_sample_renders_preview_and_thumbnails(page):
    page.click("#loadSample")
    wait_ready(page)
    expect(preview(page).locator("h1").first).to_contain_text("Web Application Security Assessment")
    expect(page.locator(".tcard .thumb iframe")).to_have_count(3, timeout=15000)
    for i in range(3):
        doc = page.locator(".tcard .thumb iframe").nth(i).get_attribute("srcdoc") or ""
        assert len(doc) > 1000, "thumbnail empty"
        assert "<script" not in doc.lower(), "thumbnail contains script"


def test_toc_link_scrolls_inside_preview(page):
    url_before = preview_frame(page).url
    preview(page).locator(".toc a[href='#findings']").click()
    page.wait_for_timeout(600)
    fr = preview_frame(page)
    assert fr is not None, "preview frame navigated away"
    assert fr.url.split("#")[0] == url_before.split("#")[0], f"frame URL changed to {fr.url}"
    assert fr.evaluate("scrollY") > 300, "did not scroll"
    top = fr.evaluate("document.getElementById('findings').getBoundingClientRect().top")
    assert -5 < top < 200, f"#findings not at top of viewport (top={top})"
    assert "Burp Report Studio" not in fr.evaluate("document.title"), "app loaded inside preview"


def test_summary_table_link_jumps_to_finding(page):
    preview(page).locator(".summary-table a[href='#finding-2']").click()
    page.wait_for_timeout(500)
    top = preview_frame(page).evaluate("document.getElementById('finding-2').getBoundingClientRect().top")
    assert -5 < top < 200, f"finding-2 top={top}"


def test_every_anchor_has_a_target(page):
    missing = preview_frame(page).evaluate("""() => [...document.querySelectorAll('a[href^="#"]')]
        .map(a => a.getAttribute('href').slice(1)).filter(id => id && !document.getElementById(id))""")
    assert not missing, f"dangling anchors: {missing}"


def test_external_link_opens_new_tab(page):
    with page.context.expect_page() as pop:
        preview(page).locator(".refs a[href^='https://']").first.click()
    new = pop.value
    assert new.url.startswith("https://") or new.url == "about:blank", new.url
    new.close()
    assert preview_frame(page) is not None


def test_report_toolbar_filters(page):
    pv = preview(page)
    pv.locator(".chip[data-sev='High']").click()
    assert pv.locator("article.finding[data-severity='High']:visible").count() == 0
    pv.locator(".chip[data-sev='High']").click()
    pv.locator("#q").fill("sql")
    expect(pv.locator("article.finding:visible")).to_have_count(1)
    pv.locator("#q").fill("zzzz-nothing")
    expect(pv.locator(".no-results")).to_be_visible()
    pv.locator("#q").fill("")
    pv.locator("#collapse").click()
    assert pv.locator("details.instance[open]").count() == 0
    pv.locator("#expand").click()
    assert pv.locator("details.instance:not([open])").count() == 0


def test_scroll_position_kept_across_rerender(page):
    preview_frame(page).evaluate("scrollTo(0, 1800)")
    page.wait_for_timeout(300)
    open_panel(page, 2)
    bump(page, "[data-bind='subtitle']", "Scroll test")
    page.wait_for_timeout(700)
    y = preview_frame(page).evaluate("scrollY")
    assert abs(y - 1800) < 60, f"scrollY={y}"


def test_template_cards_switch_template(page):
    open_panel(page, 1)
    for key, marker in (("modern", "--accent-2"), ("minimal", "text-transform: uppercase; letter-spacing: .06em"),
                        ("corporate", "Georgia")):
        page.click(f".tcard[data-key='{key}']")
        wait_ready(page)
        assert marker in preview_frame(page).content(), f"{key}: marker missing"
        expect(page.locator(f".tcard[data-key='{key}']")).to_have_class("tcard sel")


def test_accent_colour_and_font(page):
    page.locator(".swatch[title='Teal']").click()
    wait_ready(page)
    assert "--accent: #0f766e" in preview_frame(page).content()
    page.locator(".swatch.custom input").evaluate(
        "e => { e.value = '#ff0088'; e.dispatchEvent(new Event('input', {bubbles:true})) }")
    wait_ready(page)
    assert "--accent: #ff0088" in preview_frame(page).content()
    page.select_option("#font", label="Georgia (serif)")
    wait_ready(page)
    assert "--font: Georgia" in preview_frame(page).content()
    page.select_option("#font", label="Source Serif 4 (formal serif)")
    wait_ready(page)
    fr = preview_frame(page)
    fr.evaluate("document.fonts.ready")
    loaded = fr.evaluate("[...document.fonts].filter(f => f.status === 'loaded').map(f => f.family)")
    assert "Source Serif 4" in loaded, f"bundled font not loaded in preview (CSP?): {loaded}"
    page.locator(".swatch.def").click()
    page.select_option("#font", index=0)
    wait_ready(page)


def test_html_typed_into_fields_is_shown_as_text(page, events):
    open_panel(page, 2)
    payload = "<img src=x onerror=alert(1)><script>alert(2)</script>\"'</style>"
    bump(page, "[data-bind='client']", payload)
    bump(page, "[data-bind='classification']", "</style><script>alert(3)</script>")
    open_panel(page, 8)
    bump(page, "[data-bind='executive_summary']", "Para one <b>x</b>\n\nPara two")
    fr = preview_frame(page)
    assert payload in fr.evaluate("document.body.innerText"), "payload not shown literally"
    assert fr.evaluate("document.querySelectorAll('img[src=x]').length") == 0
    expect(preview(page).locator("#executive-summary .prose p")).to_have_count(2)
    page.wait_for_timeout(500)
    assert not events["dialogs"], f"dialog fired: {events['dialogs']}"
    bump(page, "[data-bind='client']", "Acme")
    bump(page, "[data-bind='classification']", "CONFIDENTIAL")
    bump(page, "[data-bind='executive_summary']", "")


def test_section_and_field_toggles(page):
    open_panel(page, 3)
    cover = page.locator("#sectionsBox label[data-key='cover'] input")
    cover.click()
    wait_ready(page)
    assert preview(page).locator(".cover").count() == 0
    assert preview(page).locator(".doc-header").count() == 1
    cover.click()
    wait_ready(page)
    open_panel(page, 4)
    refs = page.locator("#fieldsBox label[data-key='references'] input")
    refs.click()
    wait_ready(page)
    assert preview(page).locator(".refs h4", has_text="References").count() == 0
    refs.click()
    wait_ready(page)


def test_severity_filters_keep_at_least_one(page):
    open_panel(page, 5)
    for s in ("Medium", "Low", "Information"):
        page.locator(f"#sevChips .chip:has-text('{s}')").click()
        wait_ready(page)
    page.locator("#sevChips .chip:has-text('High')").click()
    expect(page.locator("#toast")).to_contain_text("at least one")
    wait_ready(page)
    assert preview(page).locator("article.finding").count() == 2
    for s in ("Medium", "Low", "Information"):
        page.locator(f"#sevChips .chip:has-text('{s}')").click()
    wait_ready(page)
    assert preview(page).locator("article.finding").count() == 8


def test_unticking_every_host_is_refused(page):
    boxes = page.locator("#hostsBox input")
    boxes.nth(0).click()
    wait_ready(page)
    assert preview(page).locator("#hosts tbody tr").count() == 1
    boxes.nth(1).click()
    expect(page.locator("#toast")).to_contain_text("at least one host")
    assert page.locator("#hostsBox input:checked").count() == 1, "UI and config disagree"
    page.locator("#hostsWrap [data-all='hosts']").click()
    wait_ready(page)
    assert preview(page).locator("#hosts tbody tr").count() == 2


def test_issue_type_exclusion_and_search(page):
    page.fill("#typeSearch", "sql")
    assert page.locator("#typesBox label:visible").count() == 1
    page.locator("#typesBox label:visible input").click()
    wait_ready(page)
    assert preview(page).locator("article.finding h3", has_text="SQL injection").count() == 0
    page.locator("#typesWrap [data-all='types']").click()
    page.fill("#typeSearch", "")
    wait_ready(page)
    assert preview(page).locator("article.finding h3", has_text="SQL injection").count() == 1


def test_evidence_options(page):
    open_panel(page, 7)
    page.locator("[data-bind='response_headers_only']").check()
    wait_ready(page)
    assert "(headers only)" in preview_frame(page).content()
    page.locator("#evidenceOn").uncheck()
    wait_ready(page)
    assert preview(page).locator("pre.http").count() == 0
    page.locator("#evidenceOn").check()
    page.locator("[data-bind='response_headers_only']").uncheck()
    wait_ready(page)
    assert preview(page).locator("pre.http").count() > 0


def test_grouping_and_sorting(page):
    open_panel(page, 6)
    page.select_option("#grouping", "0")
    wait_ready(page)
    assert preview(page).locator("article.finding").count() == 11
    page.select_option("[data-bind='sort_by']", "name")
    wait_ready(page)
    names = preview(page).locator("article.finding h3").all_inner_texts()
    assert names == sorted(names, key=str.lower), names
    page.select_option("#grouping", "1")
    page.select_option("[data-bind='sort_by']", "severity")
    wait_ready(page)


def test_rapid_typing_shows_final_value(page):
    open_panel(page, 2)
    loc = page.locator("[data-bind='title']")
    loc.fill("")
    loc.press_sequentially("Rapid Title Final", delay=15)
    wait_ready(page)
    page.wait_for_timeout(400)
    expect(preview(page).locator(".cover h1")).to_have_text("Rapid Title Final")


def test_logo_upload_and_remove(page, fx):
    open_panel(page, 2)
    page.set_input_files("#logoFile", str(fx / "logo.png"))
    # The FileReader is async, so "Up to date" may still be the previous render; wait for the logo itself.
    expect(preview(page).locator("img.logo")).to_have_count(1, timeout=20000)
    wait_ready(page)
    page.click("#clearLogo")
    expect(preview(page).locator("img.logo")).to_have_count(0, timeout=20000)
    wait_ready(page)


def test_custom_template_bad_path(page):
    open_panel(page, 1)
    page.fill("#customTpl", "C:/definitely/not/here")
    page.click("#useCustomTpl")
    expect(page.locator("#toast")).to_contain_text("not found")
    expect(page.locator(".tcard.sel")).to_have_count(1)


def test_export_html(page, dl):
    open_panel(page, 2)
    bump(page, "[data-bind='client']", "Bücher 東京")
    with page.expect_download() as d:
        page.click("#exportHtml")
    path = dl / "report.html"
    d.value.save_as(path)
    name = unquote(d.value.suggested_filename)
    assert "Bücher" in name or name.endswith(".html"), name
    html = path.read_text(encoding="utf-8")
    assert html.lower().startswith("<!doctype html>") and "burpScroll" not in html, "export contains preview bridge"
    bump(page, "[data-bind='client']", "Acme")


def test_export_pdf(page, dl):
    with page.expect_download(timeout=90000) as d:
        page.click("#exportPdf")
    path = dl / "report.pdf"
    d.value.save_as(path)
    data = path.read_bytes()
    assert data[:5] == b"%PDF-" and len(data) > 20000, len(data)
    expect(page.locator("#exportPdf")).to_be_enabled()


def test_payload_highlighting(page):
    open_panel(page, 7)
    marks = preview(page).locator("pre.http mark.hl")
    expect(marks.first).to_be_attached()
    assert any("abc" in t and "xyz" in t for t in marks.all_inner_texts())
    page.locator("[data-bind='highlight_payloads']").uncheck()
    wait_ready(page)
    expect(preview(page).locator("pre.http mark.hl")).to_have_count(0)
    page.locator("[data-bind='highlight_payloads']").check()
    wait_ready(page)
    expect(preview(page).locator("pre.http mark.hl").first).to_be_attached()


def test_redaction(page):
    open_panel(page, 7)

    def evidence():
        return "\n".join(preview(page).locator("pre.http").all_inner_texts())

    text = evidence()
    assert "[REDACTED]" in text and SESSION_COOKIE not in text, "session cookie not redacted by default"
    page.locator("[data-bind='redact_secrets']").uncheck()
    wait_ready(page)
    assert f"session={SESSION_COOKIE}" in evidence(), "toggle off should show the raw cookie"
    page.locator("#redactCustom").fill("nginx\n/x-frame-options/i")
    wait_ready(page)
    text = evidence()
    assert "nginx" not in text and "X-Frame-Options" not in text and "[REDACTED]" in text, "custom redaction failed"
    assert f"session={SESSION_COOKIE}" in text, "built-in rules should stay off"
    page.locator("#redactCustom").fill("/([/")
    expect(page.locator("#toast")).to_contain_text("Invalid redaction pattern", timeout=20000)
    page.locator("#redactCustom").fill("")
    page.locator("[data-bind='redact_secrets']").check()
    wait_ready(page)
    assert SESSION_COOKIE not in evidence()
    expect(preview(page).locator("#scan-info")).to_contain_text("Evidence redaction")


def test_owasp_section(page):
    sec = preview(page).locator("#owasp")
    expect(sec).to_be_attached()
    expect(sec.locator("tbody tr")).to_have_count(11)   # A01-A10 + not mapped
    expect(sec.locator("h2")).to_have_text("OWASP Top 10:2025 mapping")
    expect(sec.locator("tr", has_text="A05").locator("a.fid")).to_have_count(2)
    expect(preview(page).locator(".toc a[href='#owasp']")).to_have_count(1)
    expect(preview(page).locator("#finding-1 .finding-meta")).to_contain_text("CWE-79")
    expect(preview(page).locator("#finding-1 .finding-meta")).to_contain_text("A05:2025")
    open_panel(page, 3)
    expect(page.locator("[data-bind='owasp_edition']")).to_have_value("2025")
    page.select_option("[data-bind='owasp_edition']", "2021")
    wait_ready(page)
    expect(sec.locator("h2")).to_have_text("OWASP Top 10:2021 mapping")
    expect(sec.locator("tr", has_text="A03").locator("a.fid")).to_have_count(2)
    expect(preview(page).locator("#finding-1 .finding-meta")).to_contain_text("A03:2021")
    expect(page.locator("#hintSections")).to_contain_text("OWASP 2021")
    page.select_option("[data-bind='owasp_edition']", "2025")
    wait_ready(page)
    expect(preview(page).locator("#finding-1 .finding-meta")).to_contain_text("A05:2025")
    page.locator("#sectionsBox label[data-key='owasp_table'] input").uncheck()
    wait_ready(page)
    expect(preview(page).locator("#owasp")).to_have_count(0)
    page.locator("#sectionsBox label[data-key='owasp_table'] input").check()
    open_panel(page, 4)
    page.locator("#fieldsBox label[data-key='cwe_owasp'] input").uncheck()
    wait_ready(page)
    expect(preview(page).locator(".finding-meta", has_text="OWASP Top 10")).to_have_count(0)
    page.locator("#fieldsBox label[data-key='cwe_owasp'] input").check()
    wait_ready(page)


def test_export_word(page, dl):
    with page.expect_download(timeout=90000) as d:
        page.click("#exportDocx")
    path = dl / "report.docx"
    d.value.save_as(path)
    assert d.value.suggested_filename.endswith(".docx"), d.value.suggested_filename
    with zipfile.ZipFile(path) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    for needle in ("OWASP Top 10:2025 mapping", "[REDACTED]", 'w:highlight w:val="yellow"', "CWE-79", "TOC \\o"):
        assert needle in xml, f"missing {needle!r} in document.xml"
    assert SESSION_COOKIE not in xml, "unredacted cookie in Word export"
    expect(page.locator("#exportDocx")).to_be_enabled()


def test_pdf_preview_mode(page):
    page.click(".seg [data-mode='pdf']")
    wait_ready(page, 90000)
    src = page.locator("#pdfFrame").get_attribute("src") or ""
    assert src.startswith("blob:"), src
    expect(page.locator("#widthSeg")).to_be_hidden()
    page.click(".seg [data-mode='html']")
    wait_ready(page)
    expect(page.locator("#htmlFrame")).to_be_visible()


def test_width_presets(page):
    page.click("#widthSeg [data-width='phone']")
    assert page.locator("#htmlFrame").bounding_box()["width"] <= 402
    page.click("#widthSeg [data-width='full']")
    assert page.locator("#htmlFrame").bounding_box()["width"] > 800


def test_profile_save_reset_load(page, dl):
    open_panel(page, 2)
    bump(page, "[data-bind='prepared_by']", "QA Tester")
    with page.expect_download() as d:
        page.click("#saveProfile")
    prof = dl / "profile.json"
    d.value.save_as(prof)
    assert json.loads(prof.read_text(encoding="utf-8"))["prepared_by"] == "QA Tester"
    page.once("dialog", lambda dlg: dlg.accept())
    page.click("#resetCfg")
    wait_ready(page)
    expect(page.locator("[data-bind='prepared_by']")).to_have_value("")
    page.set_input_files("#profileFile", str(prof))
    wait_ready(page)
    expect(page.locator("[data-bind='prepared_by']")).to_have_value("QA Tester")


def test_malformed_profile_is_handled(page, dl):
    bad = dl / "bad_profile.json"
    bad.write_text(json.dumps({"severities": "High", "max_evidence_chars": "lots", "sections": [1, 2],
                               "title": 42, "prepared_by": "Still Loaded"}), encoding="utf-8")
    page.set_input_files("#profileFile", str(bad))
    wait_ready(page)
    expect(page.locator("[data-bind='prepared_by']")).to_have_value("Still Loaded")
    assert page.locator("#sevChips .chip.on").count() == 4
    garbage = dl / "garbage.json"
    garbage.write_text("{not json", encoding="utf-8")
    page.set_input_files("#profileFile", str(garbage))
    expect(page.locator("#toast")).to_contain_text("Not a valid profile")


def test_settings_persist_across_reload(page):
    open_panel(page, 2)
    bump(page, "[data-bind='version']", "9.9")
    page.reload()
    expect(page.locator("[data-bind='version']")).to_have_value("9.9")
    wait_ready(page)


def test_invalid_xml_upload_keeps_previous_scan(page, dl):
    bad = dl / "not_burp.xml"
    bad.write_text("<foo/>", encoding="utf-8")
    page.set_input_files("#xmlFile", str(bad))
    expect(page.locator("#toast")).to_contain_text("Expected a Burp")
    expect(page.locator("#scanName")).to_have_text("sample_burp_export.xml")


def test_nasty_xml_upload(page, fx, events):
    page.set_input_files("#xmlFile", str(fx / "nasty.xml"))
    wait_ready(page, 30000)
    expect(page.locator("#scanName")).to_have_text("nasty.xml")
    assert chips(page) == ["High 2", "Medium 2", "Low 2", "Information 1"], "preview not for nasty.xml"
    text = preview_frame(page).evaluate("document.body.innerText")
    for s in ("[DOM-based]", "日本語", "<script>alert('n')</script>", "binary body omitted"):
        assert s in text, f"missing {s!r}"
    assert "(truncated)" in text.lower()
    page.wait_for_timeout(300)
    assert not events["dialogs"], events["dialogs"]


def test_drop_file_onto_window(page):
    page.evaluate("""async (bytes) => {
        const dt = new DataTransfer();
        dt.items.add(new File([new Uint8Array(bytes)], 'dropped.xml', {type: 'text/xml'}));
        window.dispatchEvent(new DragEvent('dragenter', {dataTransfer: dt}));
        window.dispatchEvent(new DragEvent('drop', {dataTransfer: dt, cancelable: true}));
    }""", list(SAMPLE.read_bytes()))
    expect(page.locator("#scanName")).to_have_text("dropped.xml", timeout=15000)
    wait_ready(page)
    assert "drag" not in (page.locator("body").get_attribute("class") or "")
    assert chips(page) == ["High 2", "Medium 1", "Low 2", "Information 3"], "stale preview"
    expect(page.locator(".tcard .thumb iframe")).to_have_count(3, timeout=15000)


def test_large_export_performance(page, fx):
    t0 = time.time()
    page.set_input_files("#xmlFile", str(fx / "large.xml"))
    expect(page.locator("#scanName")).to_have_text("large.xml", timeout=60000)
    wait_ready(page, 120000)
    load = time.time() - t0
    assert preview(page).locator("article.finding").count() == 40
    open_panel(page, 2)
    t1 = time.time()
    bump(page, "[data-bind='subtitle']", "perf edit")
    rerender = time.time() - t1
    print(f"perf: initial load+render {load:.1f}s, re-render after edit {rerender:.1f}s")
    # generous limits: shared CI runners are several times slower than a desktop
    assert load < 45, f"initial load {load:.1f}s"
    assert rerender < 15, f"re-render {rerender:.1f}s"


def test_app_layout_at_phone_width(browser, server, page):
    ctx = browser.new_context(viewport={"width": 390, "height": 844})
    p = ctx.new_page()
    p.goto(server["base"])
    wait_ready(p, 60000)   # the server already holds a scan, so the preview loads straight away
    sw = p.evaluate("document.documentElement.scrollWidth")
    ctx.close()
    assert sw <= 391, f"scrollWidth={sw}"


def test_api_rejects_untrusted_requests(server):
    def req(method, path, headers=None, body=None):
        c = http.client.HTTPConnection("127.0.0.1", server["port"])
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        r.read()
        return r.status

    assert req("POST", "/api/meta", body="{}") == 403
    assert req("GET", "/", {"Host": "attacker.example"}) == 403
    assert req("GET", "/preview/abc?t=wrong") == 403
    assert req("GET", "/favicon.ico") == 204


def test_no_unexpected_console_errors(events):
    # Rejected inputs above (bad profile, bad XML, bad regex) answer 400 on purpose.
    unexpected = [e for e in events["console"] if "status of 400" not in e and "kaspersky" not in e.lower()
                  and e != "Failed to load resource: net::ERR_FAILED"]
    assert not unexpected, unexpected
