"""Command line for the Notion template.

    python -m trend_tracker.notion validate
    python -m trend_tracker.notion plan                      # dry run: list every API call
    python -m trend_tracker.notion build --parent PAGE_ID    # needs NOTION_TOKEN
    python -m trend_tracker.notion glossary > docs/NOTION_TEMPLATE.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict

from .builder import build
from .client import FakeClient, NotionClient, NotionError
from .schema import DEFAULT_SCHEMA, SchemaError, glossary, load_schema, validate


def page_id(value: str) -> str:
    """Accept a raw ID or a Notion page URL."""
    match = re.search(r"([0-9a-f]{32}|[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})", value.lower())
    if not match:
        raise argparse.ArgumentTypeError("expected a Notion page ID or URL")
    return match.group(1)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m trend_tracker.notion", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--schema", default=DEFAULT_SCHEMA, help="path to schema.json")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate", help="check the schema for errors")
    sub.add_parser("plan", help="print the API calls a build would make, without calling Notion")
    b = sub.add_parser("build", help="create the tracker under a Notion page")
    b.add_argument("--parent", required=True, type=page_id, help="ID or URL of the page to build under")
    b.add_argument("--out", help="write created IDs to this JSON file")
    sub.add_parser("glossary", help="print a Markdown field reference")
    args = parser.parse_args(argv)

    schema = load_schema(args.schema)

    if args.command == "validate":
        errors = validate(schema)
        for e in errors:
            print(f"error: {e}", file=sys.stderr)
        if not errors:
            n = sum(len(db["properties"]) for db in schema["databases"])
            print(f"ok: {len(schema['databases'])} databases, {n} properties, "
                  f"{len(schema.get('relations', ()))} relations, {len(schema.get('views', ()))} views")
        return 1 if errors else 0

    if args.command == "glossary":
        sys.stdout.write(glossary(schema))
        return 0

    if args.command == "plan":
        fake = FakeClient()
        try:
            build(schema, fake, "PARENT_PAGE_ID", log=lambda _: None)
        except SchemaError as e:
            print(e, file=sys.stderr)
            return 1
        for method, path, body in fake.calls:
            print(f"{method:<5} {path}")
            if body is not None:
                summary = {k: v for k, v in body.items() if k != "initial_data_source"}
                if "initial_data_source" in body:
                    summary["properties"] = list(body["initial_data_source"]["properties"])
                print("      " + json.dumps(summary, ensure_ascii=False)[:300])
        print(f"\n{len(fake.calls)} API calls", file=sys.stderr)
        return 0

    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        print("Set NOTION_TOKEN to an internal integration token that can edit the parent page.", file=sys.stderr)
        return 2
    try:
        built = build(schema, NotionClient(token), args.parent)
    except (SchemaError, NotionError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("\nDone:")
    for db in built.values():
        print(f"  {db.title:<14} {db.url}")
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({k: {kk: vv for kk, vv in asdict(v).items() if kk != "property_ids"} for k, v in built.items()},
                      fh, indent=2)
        print(f"IDs written to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
