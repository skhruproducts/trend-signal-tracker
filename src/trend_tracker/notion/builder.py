"""Build the tracker in a Notion workspace from schema.json.

Order matters: relations need both data sources to exist, rollups need the
relation, and views need property IDs. So the build runs in five steps:

    1. create one database per entry (title, scalar properties)
    2. add two-way relations
    3. add rollups and formulas
    4. read back property IDs
    5. create saved views
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .client import Client
from .schema import check


@dataclass
class BuiltDatabase:
    key: str
    title: str
    database_id: str
    data_source_id: str
    url: str = ""
    property_ids: dict[str, dict[str, str]] = field(default_factory=dict)
    views: list[str] = field(default_factory=list)


def _text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content}}] if content else []


def property_config(prop: dict[str, Any]) -> dict[str, Any]:
    ptype = prop["type"]
    if ptype in ("select", "multi_select"):
        return {ptype: {"options": [{"name": n, "color": c} for n, c in prop["options"]]}}
    if ptype == "number":
        return {"number": {"format": "number"}}
    return {ptype: {}}


def group_by_config(prop: dict[str, str]) -> dict[str, Any]:
    ptype, pid = prop["type"], prop["id"]
    if ptype in ("select", "multi_select"):
        return {"type": ptype, "property_id": pid, "sort": {"type": "manual"}, "hide_empty_groups": False}
    if ptype in ("relation", "checkbox"):
        return {"type": ptype, "property_id": pid, "sort": {"type": "ascending"}}
    raise ValueError(f"Grouping by {ptype} properties is not supported by this template")


def build(
    schema: dict[str, Any],
    client: Client,
    parent_page_id: str,
    log: Callable[[str], None] = print,
) -> dict[str, BuiltDatabase]:
    check(schema)
    built: dict[str, BuiltDatabase] = {}

    # 1. Databases
    for db in schema["databases"]:
        resp = client.request("POST", "/databases", {
            "parent": {"type": "page_id", "page_id": parent_page_id},
            "title": _text(db["title"]),
            "description": _text(db.get("description", "")),
            "initial_data_source": {"properties": {p["name"]: property_config(p) for p in db["properties"]}},
        })
        built[db["key"]] = BuiltDatabase(
            key=db["key"], title=db["title"], database_id=resp["id"],
            data_source_id=resp["data_sources"][0]["id"], url=resp.get("url", ""),
        )
        log(f"created database  {db['title']}")

    def patch(key: str, properties: dict[str, Any]) -> None:
        client.request("PATCH", f"/data_sources/{built[key].data_source_id}", {"properties": properties})

    # 2. Two-way relations
    for rel in schema.get("relations", ()):
        patch(rel["from"], {rel["name"]: {"relation": {
            "data_source_id": built[rel["to"]].data_source_id,
            "dual_property": {"synced_property_name": rel["synced_name"]},
        }}})
        log(f"linked            {built[rel['from']].title}.{rel['name']} <-> {built[rel['to']].title}.{rel['synced_name']}")

    # 3. Rollups and formulas
    for r in schema.get("rollups", ()):
        patch(r["database"], {r["name"]: {"rollup": {
            "function": r["function"],
            "relation_property_name": r["relation"],
            "rollup_property_name": r["property"],
        }}})
        log(f"rollup            {built[r['database']].title}.{r['name']}")
    for f in schema.get("formulas", ()):
        patch(f["database"], {f["name"]: {"formula": {"expression": f["expression"]}}})
        log(f"formula           {built[f['database']].title}.{f['name']}")

    # 4. Property IDs (needed for grouping)
    for b in built.values():
        ds = client.request("GET", f"/data_sources/{b.data_source_id}")
        b.property_ids = {name: {"id": p["id"], "type": p["type"]} for name, p in ds["properties"].items()}

    # 5. Views
    for v in schema.get("views", ()):
        b = built[v["database"]]
        body: dict[str, Any] = {
            "database_id": b.database_id,
            "data_source_id": b.data_source_id,
            "name": v["name"],
            "type": v["type"],
        }
        if v.get("filter"):
            body["filter"] = v["filter"]
        if v.get("sorts"):
            body["sorts"] = v["sorts"]
        if v.get("group_by"):
            body["configuration"] = {"type": v["type"], "group_by": group_by_config(b.property_ids[v["group_by"]])}
        client.request("POST", "/views", body)
        b.views.append(v["name"])
        log(f"view              {b.title} / {v['name']}")

    return built
