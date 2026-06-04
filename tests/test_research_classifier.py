"""Tests for opportunity classification parsing + service rendering."""

from src.config import ServiceCatalog, Service
from src.research.classifier import parse_classification
from src.research.services import (
    format_services_block,
    pitches_for,
    valid_service_ids,
)


KNOWN = {"technical_seo", "geo_aeo"}


def _catalog() -> ServiceCatalog:
    return ServiceCatalog(
        company_name="ReachLLM",
        company_url="reachllm.com",
        company_one_liner="AI visibility agency",
        services=[
            Service("technical_seo", "Technical SEO", ["traffic drops"], ["indexed"], "We audit."),
            Service("geo_aeo", "GEO/AEO", ["not cited by AI"], ["llms.txt"], "We optimize."),
        ],
        audiences=["SMBs", "agencies"],
    )


class TestParseClassification:
    def test_clean_json(self):
        text = '{"is_opportunity": true, "priority": 8, "confidence": 0.9, "matched_services": ["technical_seo"], "problem_summary": "traffic crash", "suggested_angle": "audit"}'
        opp = parse_classification(text, KNOWN)
        assert opp.is_opportunity
        assert opp.priority == 8
        assert opp.confidence == 0.9
        assert opp.matched_services == ["technical_seo"]

    def test_fenced_json(self):
        text = "Here you go:\n```json\n{\"is_opportunity\": true, \"priority\": 6, \"matched_services\": [\"geo_aeo\"]}\n```"
        opp = parse_classification(text, KNOWN)
        assert opp.is_opportunity
        assert opp.matched_services == ["geo_aeo"]

    def test_drops_hallucinated_service(self):
        text = '{"is_opportunity": true, "priority": 7, "matched_services": ["made_up", "geo_aeo"]}'
        opp = parse_classification(text, KNOWN)
        assert opp.matched_services == ["geo_aeo"]

    def test_priority_clamped(self):
        text = '{"is_opportunity": true, "priority": 99, "matched_services": ["geo_aeo"]}'
        assert parse_classification(text, KNOWN).priority == 10

    def test_confidence_clamped(self):
        text = '{"is_opportunity": true, "priority": 5, "confidence": 5, "matched_services": ["geo_aeo"]}'
        assert parse_classification(text, KNOWN).confidence == 1.0

    def test_not_opportunity(self):
        text = '{"is_opportunity": false, "priority": 0, "matched_services": []}'
        assert parse_classification(text, KNOWN).is_opportunity is False

    def test_opportunity_without_service_or_priority_is_rejected(self):
        text = '{"is_opportunity": true, "priority": 0, "matched_services": []}'
        assert parse_classification(text, KNOWN).is_opportunity is False

    def test_garbage_fails_closed(self):
        assert parse_classification("not json at all", KNOWN).is_opportunity is False
        assert parse_classification("", KNOWN).is_opportunity is False


class TestServicesRendering:
    def test_block_includes_ids_and_pitch(self):
        block = format_services_block(_catalog())
        assert "technical_seo" in block
        assert "We optimize." in block

    def test_valid_ids(self):
        assert valid_service_ids(_catalog()) == {"technical_seo", "geo_aeo"}

    def test_pitches_for(self):
        pitches = pitches_for(_catalog(), ["geo_aeo", "nope"])
        assert len(pitches) == 1
        assert "We optimize." in pitches[0]
