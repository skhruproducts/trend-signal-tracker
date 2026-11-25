import copy
from pathlib import Path

import pytest

from trend_tracker.notion import FakeClient, SchemaError, build, glossary, load_schema, validate
from trend_tracker.notion.__main__ import main, page_id
from trend_tracker.notion.builder import group_by_config, property_config

ROOT = Path(__file__).parent.parent


@pytest.fixture
def schema():
    return load_schema()


def test_shipped_schema_is_valid(schema):
    assert validate(schema) == []


def test_glossary_doc_is_up_to_date(schema):
    committed = (ROOT / "docs" / "NOTION_TEMPLATE.md").read_text(encoding="utf-8")
    assert committed == glossary(schema), "Run: python -m trend_tracker.notion glossary > docs/NOTION_TEMPLATE.md"


def test_methodology_labels_exist_in_schema(schema):
    """The rules engine and the Notion template must use the same vocabulary."""
    fields = {db["key"]: {p["name"]: p for p in db["properties"]} for db in schema["databases"]}
    opts = lambda db, prop: [o[0] for o in fields[db][prop]["options"]]
    assert opts("trends", "Status") == ["Watching", "Strengthening", "Confirmed", "Fading"]
    assert opts("trends", "Momentum") == ["Rising", "Below rising threshold", "Falling"]
    assert opts("signals", "Strength") == ["★" * n for n in range(1, 6)]


# --- build order and payloads ----------------------------------------------

def test_build_creates_everything_in_dependency_order(schema):
    fake = FakeClient()
    built = build(schema, fake, "PARENT", log=lambda _: None)
    methods = [(m, p.split("/")[1]) for m, p, _ in fake.calls]

    n_db = len(schema["databases"])
    n_patch = len(schema["relations"]) + len(schema["rollups"]) + len(schema["formulas"])
    assert methods[:n_db] == [("POST", "databases")] * n_db
    assert methods[n_db:n_db + n_patch] == [("PATCH", "data_sources")] * n_patch
    assert methods[-len(schema["views"]):] == [("POST", "views")] * len(schema["views"])
    assert set(built) == {"signals", "themes", "trends", "sources", "opportunities"}
    assert sum(len(b.views) for b in built.values()) == len(schema["views"])


def test_databases_are_created_under_the_parent_page(schema):
    fake = FakeClient()
    build(schema, fake, "PARENT", log=lambda _: None)
    for method, path, body in fake.calls:
        if path == "/databases":
            assert body["parent"] == {"type": "page_id", "page_id": "PARENT"}


def test_relations_point_at_the_right_data_source(schema):
    fake = FakeClient()
    built = build(schema, fake, "PARENT", log=lambda _: None)
    patches = [(p, b) for m, p, b in fake.calls if m == "PATCH"]
    path, body = patches[0]  # Signals.Theme -> Themes
    assert path == f"/data_sources/{built['signals'].data_source_id}"
    rel = body["properties"]["Theme"]["relation"]
    assert rel["data_source_id"] == built["themes"].data_source_id
    assert rel["dual_property"] == {"synced_property_name": "Signals"}


def test_views_group_by_resolved_property_ids(schema):
    fake = FakeClient()
    built = build(schema, fake, "PARENT", log=lambda _: None)
    view = next(b for m, p, b in fake.calls if p == "/views" and b["name"] == "Status board")
    group = view["configuration"]["group_by"]
    assert group["property_id"] == built["trends"].property_ids["Status"]["id"]
    assert group["type"] == "select"


def test_option_and_number_payloads():
    assert property_config({"type": "select", "options": [["A", "red"]]}) == {"select": {"options": [{"name": "A", "color": "red"}]}}
    assert property_config({"type": "number"}) == {"number": {"format": "number"}}
    assert property_config({"type": "rich_text"}) == {"rich_text": {}}


def test_group_by_rejects_unsupported_types():
    with pytest.raises(ValueError):
        group_by_config({"type": "date", "id": "x"})


# --- validation catches mistakes before any API call -------------------------

@pytest.mark.parametrize("mutate, message", [
    (lambda s: s["databases"][0]["properties"].append({"name": "Second", "type": "title"}), "exactly one title"),
    (lambda s: s["databases"][0]["properties"].append({"name": "X", "type": "select", "options": [["A", "teal"]]}), "bad option"),
    (lambda s: s["databases"][0]["properties"].append({"name": "X", "type": "select", "options": [["A, B", "red"]]}), "comma"),
    (lambda s: s["databases"][0]["properties"].append({"name": "X", "type": "people"}), "unsupported type"),
    (lambda s: s["relations"].append({"from": "signals", "name": "Ghost", "to": "nowhere", "synced_name": "S"}), "unknown database"),
    (lambda s: s["relations"].append({"from": "signals", "name": "Signal", "to": "themes", "synced_name": "Z"}), "clashes"),
    (lambda s: s["rollups"].append({"database": "themes", "name": "Bad", "relation": "Nope", "property": "Signal", "function": "count"}), "not a relation"),
    (lambda s: s["rollups"].append({"database": "themes", "name": "Bad", "relation": "Signals", "property": "Nope", "function": "count"}), "has no property"),
    (lambda s: s["formulas"].append({"database": "opportunities", "name": "F", "expression": "prop(\"Missing\")"}), "unknown property"),
    (lambda s: s["views"].append({"database": "signals", "name": "B", "type": "board"}), "need group_by"),
    (lambda s: s["views"].append({"database": "signals", "name": "B", "type": "board", "group_by": "First seen"}), "cannot group"),
    (lambda s: s["views"].append({"database": "signals", "name": "F", "type": "table", "filter": {"property": "Review", "select": {"equals": "Maybe"}}}), "not an option"),
    (lambda s: s["views"].append({"database": "signals", "name": "F", "type": "table", "filter": {"property": "Review", "relation": {"is_empty": True}}}), "is select"),
    (lambda s: s["views"].append({"database": "signals", "name": "All signals", "type": "table"}), "duplicate view"),
])
def test_validation_errors(schema, mutate, message):
    broken = copy.deepcopy(schema)
    mutate(broken)
    errors = validate(broken)
    assert any(message in e for e in errors), errors


def test_build_refuses_an_invalid_schema(schema):
    broken = copy.deepcopy(schema)
    broken["views"].append({"database": "signals", "name": "B", "type": "board"})
    fake = FakeClient()
    with pytest.raises(SchemaError):
        build(broken, fake, "PARENT", log=lambda _: None)
    assert fake.calls == []


# --- CLI -----------------------------------------------------------------------

def test_page_id_accepts_urls_and_ids():
    raw = "40f6d3a06abc8117b536face3fdff1fa"
    assert page_id(f"https://www.notion.so/My-Page-{raw}?pvs=4") == raw
    assert page_id(raw.upper()) == raw
    with pytest.raises(Exception):
        page_id("not-a-page")


def test_cli_validate_and_plan(capsys):
    assert main(["validate"]) == 0
    assert "ok: 5 databases" in capsys.readouterr().out
    assert main(["plan"]) == 0
    assert "POST  /views" in capsys.readouterr().out


def test_cli_build_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("NOTION_TOKEN", raising=False)
    assert main(["build", "--parent", "40f6d3a06abc8117b536face3fdff1fa"]) == 2
    assert "NOTION_TOKEN" in capsys.readouterr().err
