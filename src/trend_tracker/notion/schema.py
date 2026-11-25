"""Load, validate and document the Notion template schema."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DEFAULT_SCHEMA = Path(__file__).with_name("schema.json")

COLORS = {"default", "gray", "brown", "orange", "yellow", "green", "blue", "purple", "pink", "red"}
SCALAR_TYPES = {"title", "rich_text", "number", "select", "multi_select", "date", "url", "checkbox"}
OPTION_TYPES = {"select", "multi_select"}
ROLLUP_FUNCTIONS = {"count", "count_values", "unique", "show_unique", "show_original", "empty",
                    "not_empty", "sum", "average", "min", "max"}
VIEW_TYPES = {"table", "board", "list", "calendar", "timeline", "gallery"}
GROUPABLE = {"select", "multi_select", "relation", "checkbox"}


class SchemaError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("Invalid schema:\n  - " + "\n  - ".join(errors))
        self.errors = errors


@dataclass(frozen=True)
class Field:
    """A property as it will exist in Notion once everything is built."""

    name: str
    type: str
    options: tuple[str, ...] = ()
    help: str = ""


def load_schema(path: str | Path = DEFAULT_SCHEMA) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def fields_by_database(schema: dict[str, Any]) -> dict[str, dict[str, Field]]:
    """Every property per database, including relations, synced relations, rollups and formulas."""
    out: dict[str, dict[str, Field]] = {}
    for db in schema["databases"]:
        out[db["key"]] = {
            p["name"]: Field(p["name"], p["type"], tuple(o[0] for o in p.get("options", ())), p.get("help", ""))
            for p in db["properties"]
        }
    for rel in schema.get("relations", ()):
        out.setdefault(rel["from"], {})[rel["name"]] = Field(rel["name"], "relation", (), rel.get("help", ""))
        out.setdefault(rel["to"], {})[rel["synced_name"]] = Field(rel["synced_name"], "relation")
    for r in schema.get("rollups", ()):
        out.setdefault(r["database"], {})[r["name"]] = Field(r["name"], "rollup", (), r.get("help", ""))
    for f in schema.get("formulas", ()):
        out.setdefault(f["database"], {})[f["name"]] = Field(f["name"], "formula", (), f.get("help", ""))
    return out


def relation_target(schema: dict[str, Any], database: str, relation_name: str) -> str | None:
    for rel in schema.get("relations", ()):
        if rel["from"] == database and rel["name"] == relation_name:
            return rel["to"]
        if rel["to"] == database and rel["synced_name"] == relation_name:
            return rel["from"]
    return None


def validate(schema: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    keys = [db["key"] for db in schema.get("databases", ())]
    if len(keys) != len(set(keys)):
        errors.append("database keys must be unique")
    known = set(keys)

    for db in schema.get("databases", ()):
        where = f"{db['key']}"
        names = [p["name"] for p in db["properties"]]
        if len(names) != len(set(names)):
            errors.append(f"{where}: duplicate property names")
        titles = [p for p in db["properties"] if p["type"] == "title"]
        if len(titles) != 1:
            errors.append(f"{where}: needs exactly one title property, found {len(titles)}")
        for p in db["properties"]:
            if p["type"] not in SCALAR_TYPES:
                errors.append(f"{where}.{p['name']}: unsupported type {p['type']!r}")
            if p["type"] in OPTION_TYPES:
                opts = p.get("options") or []
                if not opts:
                    errors.append(f"{where}.{p['name']}: select needs options")
                opt_names = [o[0] for o in opts]
                if len(opt_names) != len(set(opt_names)):
                    errors.append(f"{where}.{p['name']}: duplicate options")
                for o in opts:
                    if "," in o[0]:
                        errors.append(f"{where}.{p['name']}: option {o[0]!r} contains a comma (Notion rejects it)")
                    if len(o) != 2 or o[1] not in COLORS:
                        errors.append(f"{where}.{p['name']}: bad option {o!r}")
            elif p.get("options"):
                errors.append(f"{where}.{p['name']}: only select/multi_select take options")

    for rel in schema.get("relations", ()):
        for end in ("from", "to"):
            if rel[end] not in known:
                errors.append(f"relation {rel['name']}: unknown database {rel[end]!r}")

    if errors:  # later checks rely on a structurally sound schema
        return errors

    # Name clashes once relations, rollups and formulas are added
    seen: dict[str, set[str]] = {db["key"]: {p["name"] for p in db["properties"]} for db in schema["databases"]}

    def add(db: str, name: str, what: str) -> None:
        if name in seen[db]:
            errors.append(f"{db}: {what} {name!r} clashes with an existing property")
        seen[db].add(name)

    for rel in schema.get("relations", ()):
        add(rel["from"], rel["name"], "relation")
        add(rel["to"], rel["synced_name"], "synced relation")
    for r in schema.get("rollups", ()):
        if r["database"] not in known:
            errors.append(f"rollup {r['name']}: unknown database {r['database']!r}")
            continue
        add(r["database"], r["name"], "rollup")
    for f in schema.get("formulas", ()):
        if f["database"] not in known:
            errors.append(f"formula {f['name']}: unknown database {f['database']!r}")
            continue
        add(f["database"], f["name"], "formula")
    if errors:
        return errors

    fields = fields_by_database(schema)

    for r in schema.get("rollups", ()):
        where = f"{r['database']}.{r['name']}"
        if r["function"] not in ROLLUP_FUNCTIONS:
            errors.append(f"{where}: unknown rollup function {r['function']!r}")
        target = relation_target(schema, r["database"], r["relation"])
        if target is None:
            errors.append(f"{where}: {r['relation']!r} is not a relation on {r['database']}")
        elif r["property"] not in fields[target]:
            errors.append(f"{where}: {target} has no property {r['property']!r}")

    for f in schema.get("formulas", ()):
        for ref in re.findall(r'prop\("([^"]+)"\)', f["expression"]):
            if ref not in fields[f["database"]]:
                errors.append(f"{f['database']}.{f['name']}: formula references unknown property {ref!r}")

    view_names: set[tuple[str, str]] = set()
    for v in schema.get("views", ()):
        db = v["database"]
        where = f"view {db}/{v['name']}"
        if db not in known:
            errors.append(f"{where}: unknown database")
            continue
        if (db, v["name"]) in view_names:
            errors.append(f"{where}: duplicate view name")
        view_names.add((db, v["name"]))
        if v["type"] not in VIEW_TYPES:
            errors.append(f"{where}: unsupported view type {v['type']!r}")
        if v["type"] == "board" and not v.get("group_by"):
            errors.append(f"{where}: board views need group_by")
        if gb := v.get("group_by"):
            field = fields[db].get(gb)
            if field is None:
                errors.append(f"{where}: group_by {gb!r} is not a property")
            elif field.type not in GROUPABLE:
                errors.append(f"{where}: cannot group by {field.type} property {gb!r}")
        for s in v.get("sorts", ()):
            if s["property"] not in fields[db]:
                errors.append(f"{where}: sort by unknown property {s['property']!r}")
            if s["direction"] not in ("ascending", "descending"):
                errors.append(f"{where}: bad sort direction {s['direction']!r}")
        if flt := v.get("filter"):
            errors.extend(_check_filter(flt, fields[db], where))
    return errors


def _check_filter(flt: dict[str, Any], fields: dict[str, Field], where: str) -> list[str]:
    errors = []
    for combinator in ("and", "or"):
        if combinator in flt:
            for sub in flt[combinator]:
                errors.extend(_check_filter(sub, fields, where))
            return errors
    name = flt.get("property")
    field = fields.get(name)
    if field is None:
        return [f"{where}: filter on unknown property {name!r}"]
    condition_type = next((k for k in flt if k != "property"), None)
    if condition_type != field.type:
        errors.append(f"{where}: filter uses {condition_type!r} but {name!r} is {field.type}")
    cond = flt.get(condition_type, {})
    for op in ("equals", "does_not_equal", "contains", "does_not_contain"):
        if op in cond and field.options and cond[op] not in field.options:
            errors.append(f"{where}: {cond[op]!r} is not an option of {name!r}")
    return errors


def check(schema: dict[str, Any]) -> None:
    errors = validate(schema)
    if errors:
        raise SchemaError(errors)


def glossary(schema: dict[str, Any]) -> str:
    """Markdown field reference generated from the schema."""
    fields = fields_by_database(schema)
    lines = [
        "# Notion template: field reference",
        "",
        "<!-- Generated by `python -m trend_tracker.notion glossary`. Do not edit by hand. -->",
        "",
        schema.get("notes", ""),
        "",
        "```mermaid",
        "erDiagram",
    ]
    titles = {db["key"]: db["title"] for db in schema["databases"]}
    for rel in schema.get("relations", ()):
        lines.append(f'    {titles[rel["from"]].upper()} }}o--o{{ {titles[rel["to"]].upper()} : "{rel["name"]} / {rel["synced_name"]}"')
    lines += ["```", ""]
    for db in schema["databases"]:
        lines += [f"## {db['title']}", "", db.get("description", ""), "", "| Property | Type | Notes |", "|---|---|---|"]
        for f in fields[db["key"]].values():
            notes = f.help
            if f.options:
                opts = ", ".join(f.options)
                notes = f"{notes} Options: {opts}." if notes else f"Options: {opts}."
            lines.append(f"| {f.name} | {f.type.replace('_', ' ')} | {notes} |")
        views = [v for v in schema.get("views", ()) if v["database"] == db["key"]]
        if views:
            lines += ["", "Views: " + "; ".join(_describe_view(v) for v in views) + "."]
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _describe_view(v: dict[str, Any]) -> str:
    parts = [f"**{v['name']}** ({v['type']}"]
    if v.get("group_by"):
        parts.append(f", grouped by {v['group_by']}")
    if v.get("filter"):
        f = v["filter"]
        cond_type = next(k for k in f if k != "property")
        cond = f[cond_type]
        if cond.get("is_empty"):
            parts.append(f", {f['property']} is empty")
        elif "equals" in cond:
            parts.append(f", {f['property']} = {cond['equals']}")
    if v.get("sorts"):
        s = v["sorts"][0]
        parts.append(f", newest {s['property']} first" if s["direction"] == "descending" and s["property"] in ("First seen", "Event date")
                     else f", sorted by {s['property']} {s['direction']}")
    return "".join(parts) + ")"
