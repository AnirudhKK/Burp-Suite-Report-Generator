import json

import pytest

from burp_report.config import FINDING_FIELDS, SECTIONS, ReportConfig


def test_round_trip(tmp_path, cfg):
    cfg.client = "Acme"
    cfg.output_formats = ["html", "docx"]
    cfg.redact_custom = ["/secret-\\d+/i"]
    cfg.save(tmp_path / "p.json")
    assert ReportConfig.load(tmp_path / "p.json") == cfg


def test_wrongly_typed_values_keep_defaults():
    cfg = ReportConfig.from_dict(
        {
            "severities": "High",
            "max_evidence_chars": "lots",
            "sections": [1, 2],
            "title": 42,
            "highlight_payloads": "yes",
            "prepared_by": "Still Loaded",
        }
    )
    default = ReportConfig()
    assert cfg.prepared_by == "Still Loaded"
    assert cfg.severities == default.severities
    assert cfg.max_evidence_chars == default.max_evidence_chars
    assert cfg.title == default.title and cfg.highlight_payloads is True


def test_unknown_formats_and_sort_are_dropped():
    cfg = ReportConfig.from_dict(
        {
            "output_formats": ["exe", "pdf"],
            "sort_by": "nonsense",
            "max_instances_per_finding": -5,
            "owasp_edition": "2017",
        }
    )
    assert cfg.output_formats == ["pdf"] and cfg.sort_by == "severity" and cfg.max_instances_per_finding == 0
    assert cfg.owasp_edition == "2025"


def test_owasp_edition():
    assert ReportConfig().owasp_edition == "2025"
    assert ReportConfig.from_dict({"owasp_edition": "2021"}).owasp_edition == "2021"
    assert ReportConfig.from_dict({}).owasp_edition == "2025", "profiles saved before the setting existed get 2025"


def test_old_profiles_gain_new_sections_and_fields():
    cfg = ReportConfig.from_dict({"sections": {"cover": False}, "fields": {}})
    assert cfg.sections == {k: k != "cover" for k in SECTIONS}
    assert cfg.fields == dict.fromkeys(FINDING_FIELDS, True)


def test_profile_must_be_an_object(tmp_path):
    (tmp_path / "bad.json").write_text(json.dumps([1, 2]), encoding="utf-8")
    with pytest.raises(ValueError):
        ReportConfig.load(tmp_path / "bad.json")
