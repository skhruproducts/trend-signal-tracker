from trend_tracker import Action, MatchKind, compare, normalize_url, triage
from trend_tracker.dedupe import normalize_title, title_similarity
from helpers import sig


def test_normalize_url_strips_tracking_www_slash_and_fragment():
    a = "http://WWW.Brand.example.com/coats/trench/?utm_source=ig&colour=beige&fbclid=x#top"
    b = "https://brand.example.com/coats/trench?colour=beige"
    assert normalize_url(a) == normalize_url(b)


def test_normalize_url_keeps_meaningful_params():
    assert normalize_url("https://a.example.com/p?id=1") != normalize_url("https://a.example.com/p?id=2")


def test_normalize_title_handles_accents_and_cyrillic():
    assert normalize_title("Manteau « Élégant » !") == "manteau elegant"
    assert normalize_title("Тренч, що носять ВЛІТКУ") == normalize_title("тренч що носять влітку")


def test_same_url_is_same_story():
    a = sig(url="https://brand.example.com/trench")
    b = sig(url="https://www.brand.example.com/trench/?utm_medium=email")
    assert compare(b, a).kind is MatchKind.SAME_STORY


def test_same_story_key_is_same_story():
    a, b = sig(key="brand-trench-launch"), sig(key="Brand-Trench-Launch ")
    assert compare(b, a).kind is MatchKind.SAME_STORY


def test_similar_title_shared_player_close_dates_is_possible():
    a = sig(day=3, title="Atelier Nord launches a lightweight unlined trench", players=["Atelier Nord"])
    b = sig(day=4, title="Atelier Nord launches lightweight unlined trench coat", players=["atelier nord"])
    m = compare(b, a)
    assert m.kind is MatchKind.POSSIBLE
    assert "shared players" in m.reasons[0]


def test_similar_title_but_far_apart_dates_is_different():
    a = sig(day=0, title="Atelier Nord launches a lightweight unlined trench", players=["Atelier Nord"])
    b = sig(day=30, title="Atelier Nord launches a lightweight wool trench", players=["Atelier Nord"])
    assert compare(b, a).kind is MatchKind.DIFFERENT


def test_near_identical_title_alone_is_possible():
    a = sig(title="Short trench coats sell out across Paris boutiques", players=["X"])
    b = sig(day=20, title="Short trench coats sell out across Paris boutiques!", players=["Y"])
    assert compare(b, a).kind is MatchKind.POSSIBLE


def test_unrelated_stories_are_different():
    a = sig(title="Brand A opens a store in Lyon", players=["Brand A"])
    b = sig(title="Denim searches fall in Poland", players=["Brand B"])
    assert compare(b, a).kind is MatchKind.DIFFERENT
    assert title_similarity(a.title, b.title) < 0.6


def test_triage_create_update_flag():
    existing = [
        sig(url="https://brand.example.com/trench", key="brand-trench"),
        sig(day=3, title="Atelier Nord launches a lightweight unlined trench", players=["Atelier Nord"]),
    ]
    update = triage(sig(url="https://brand.example.com/trench?utm_source=x"), existing)
    assert update.action is Action.UPDATE and update.target_id == existing[0].id

    flag = triage(sig(day=4, title="Atelier Nord launches lightweight unlined trench coat",
                      players=["Atelier Nord"]), existing)
    assert flag.action is Action.FLAG and flag.target_id is None

    create = triage(sig(title="Riva Concept opens in Lyon", players=["Riva"]), existing)
    assert create.action is Action.CREATE


def test_two_rows_claiming_the_same_story_are_flagged_not_merged():
    existing = [sig(key="dup-story"), sig(key="dup-story")]
    assert triage(sig(key="dup-story"), existing).action is Action.FLAG
