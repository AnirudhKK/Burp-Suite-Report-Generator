import pytest

from burp_report.redact import MASK, Redactor, compile_custom

REQUEST = """POST /login?next=/home&access_token=abc123&q=hello HTTP/1.1
Host: shop.example.com
Cookie: session=8f2a1c9e; lang=en; .AspNetCore.Identity=xyz
Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0In0.sig
X-Api-Key: k-123
X-Requested-With: XMLHttpRequest
Referer: https://shop.example.com/?sessionid=999&page=2

username=bob&password=hunter2&remember=1&csrf_token=tok"""

RESPONSE = """HTTP/1.1 200 OK
Set-Cookie: session=newvalue; Path=/; HttpOnly
WWW-Authenticate: Basic realm="x"
Content-Type: application/json

{"user":"bob","apiKey":"AKIAABCDEFGHIJKLMNOP","refresh_token":"r\\"t","items":[1,2]}
<input type="hidden" name="csrf" value="zzz"> <input name="q" value="keep">
key AKIAABCDEFGHIJKLMNOP and author=me"""


@pytest.fixture
def redactor():
    return Redactor.from_config(True, [])


def test_request_secrets_are_masked(redactor):
    out = redactor.message(REQUEST)
    for secret in ("abc123", "8f2a1c9e", "en;", "xyz", "eyJhbGci", "k-123", "999", "hunter2", "csrf_token=tok"):
        assert secret not in out, secret
    for kept in ("Host: shop.example.com", "X-Requested-With: XMLHttpRequest", "page=2", "username=bob",
                 "remember=1", "q=hello", "next=/home"):
        assert kept in out, kept
    assert "Authorization: Bearer " + MASK in out


def test_response_secrets_are_masked(redactor):
    out = redactor.message(RESPONSE)
    for secret in ("newvalue", "AKIAABCDEFGHIJKLMNOP", 'r\\"t', '"zzz"'):
        assert secret not in out, secret
    for kept in ('WWW-Authenticate: Basic realm="x"', '"user":"bob"', 'value="keep"', "author=me", "Path=/; HttpOnly"):
        assert kept in out, kept


def test_count_has_no_double_counting(redactor):
    once = redactor.message(REQUEST)
    n = redactor.count
    assert n > 0
    assert redactor.message(once) == once
    assert redactor.count == n, "already-masked values must not be counted again"


def test_custom_literal_and_regex():
    r = Redactor.from_config(False, ["hello", "/rem[a-z]+/i"])
    out = r.message(REQUEST)
    assert "hello" not in out and "remember" not in out and "REMEMBER" not in out
    assert "session=8f2a1c9e" in out, "built-in rules are off"


def test_disabled_redactor_changes_nothing():
    r = Redactor.from_config(False, [])
    assert not r.active
    assert r.message(REQUEST) == REQUEST and r.count == 0


def test_invalid_pattern_is_reported():
    with pytest.raises(ValueError, match="Invalid redaction pattern"):
        compile_custom(["/([/"])
