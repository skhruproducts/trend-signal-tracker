import pytest

from trend_tracker import score_strength
from helpers import sig, src


def test_one_source_is_one_star():
    assert score_strength([src("Outlet A")]).stars == 1


def test_two_independent_sources_is_two_stars():
    assert score_strength([src("Outlet A"), src("Outlet B")]).stars == 2


def test_syndicated_copies_of_one_press_release_count_once():
    # Three articles, all rewriting Brand X's press release, plus one other outlet.
    sources = [src("Brand X", primary=True), src("Brand X"), src("Brand X"), src("Outlet B")]
    result = score_strength(sources)
    assert result.independent_sources == 2
    assert result.stars == 2


def test_origin_matching_ignores_case_and_spacing():
    assert score_strength([src("Outlet A"), src("  outlet   a ")]).stars == 1


def test_three_sources_without_primary_evidence_are_capped_at_two():
    result = score_strength([src("A"), src("B"), src("C")])
    assert result.stars == 2
    assert "no primary" in result.reason


def test_three_sources_with_primary_evidence_is_three_stars():
    assert score_strength([src("Brand", primary=True), src("B"), src("C")]).stars == 3


def test_quantitative_data_in_one_market_short_period_is_four_stars():
    sources = [src("Trends tool", quant=True, markets=["FR"], period_days=30), src("B"), src("C")]
    assert score_strength(sources).stars == 4


def test_quantitative_data_in_two_markets_is_five_stars():
    sources = [src("Trends tool", quant=True, markets=["FR", "PL"], period_days=7), src("B"), src("C")]
    assert score_strength(sources).stars == 5


def test_quantitative_data_over_a_sustained_period_is_five_stars():
    sources = [src("Trends tool", quant=True, markets=["FR"], period_days=90), src("B"), src("C")]
    assert score_strength(sources).stars == 5


def test_quantitative_data_alone_does_not_skip_corroboration():
    # Platform data with only one other source is still two independent sources.
    sources = [src("Trends tool", quant=True, markets=["FR", "PL"], period_days=90), src("B")]
    assert score_strength(sources).stars == 2


def test_accepts_a_signal():
    assert score_strength(sig(sources=[src("A"), src("B")])).stars == 2


def test_no_sources_is_an_error():
    with pytest.raises(ValueError):
        score_strength([])


def test_star_rendering():
    assert str(score_strength([src("A")])) == "★☆☆☆☆"
