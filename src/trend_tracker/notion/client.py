"""Minimal Notion API clients: a real one over HTTPS and a fake one for dry runs and tests."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
import uuid
from typing import Any, Protocol

API_BASE = "https://api.notion.com/v1"
API_VERSION = "2026-03-11"


class NotionError(RuntimeError):
    def __init__(self, status: int, code: str, message: str, method: str, path: str):
        super().__init__(f"{method} {path} -> {status} {code}: {message}")
        self.status, self.code = status, code


class Client(Protocol):
    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]: ...


class NotionClient:
    """Standard-library HTTP client. Retries rate limits and transient server errors."""

    def __init__(self, token: str, version: str = API_VERSION, base: str = API_BASE, max_retries: int = 4):
        if not token:
            raise ValueError("A Notion integration token is required (set NOTION_TOKEN).")
        self._token, self._version, self._base, self._max_retries = token, version, base, max_retries

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        for attempt in range(self._max_retries + 1):
            req = urllib.request.Request(
                self._base + path,
                data=data,
                method=method,
                headers={
                    "Authorization": f"Bearer {self._token}",
                    "Notion-Version": self._version,
                    "Content-Type": "application/json",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read() or b"{}")
            except urllib.error.HTTPError as e:
                payload = _json(e.read())
                retryable = e.code == 429 or e.code >= 500
                if retryable and attempt < self._max_retries:
                    time.sleep(float(e.headers.get("Retry-After") or 2 ** attempt))
                    continue
                raise NotionError(e.code, payload.get("code", ""), payload.get("message", str(e)), method, path) from None
        raise AssertionError("unreachable")


def _json(raw: bytes) -> dict[str, Any]:
    try:
        return json.loads(raw)
    except ValueError:
        return {}


class FakeClient:
    """Records calls and imitates the responses the builder relies on. Used by --dry-run and tests."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []
        self._data_sources: dict[str, dict[str, dict[str, Any]]] = {}

    @staticmethod
    def _id() -> str:
        return str(uuid.uuid4())

    def _add_props(self, ds_id: str, props: dict[str, Any]) -> None:
        store = self._data_sources.setdefault(ds_id, {})
        for name, config in props.items():
            ptype = next(iter(config))
            store[name] = {"id": self._id()[:8], "name": name, "type": ptype}
            if ptype == "relation":
                synced = config["relation"].get("dual_property", {}).get("synced_property_name")
                if synced:
                    target = self._data_sources.setdefault(config["relation"]["data_source_id"], {})
                    target[synced] = {"id": self._id()[:8], "name": synced, "type": "relation"}

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, path, body))
        if method == "POST" and path == "/databases":
            db_id, ds_id = self._id(), self._id()
            self._add_props(ds_id, body["initial_data_source"]["properties"])
            return {"object": "database", "id": db_id, "url": f"https://www.notion.so/{db_id.replace('-', '')}",
                    "data_sources": [{"id": ds_id, "name": body["title"][0]["text"]["content"]}]}
        if method == "PATCH" and path.startswith("/data_sources/"):
            ds_id = path.rsplit("/", 1)[1]
            self._add_props(ds_id, body.get("properties", {}))
            return {"object": "data_source", "id": ds_id}
        if method == "GET" and path.startswith("/data_sources/"):
            ds_id = path.rsplit("/", 1)[1]
            return {"object": "data_source", "id": ds_id, "properties": self._data_sources.get(ds_id, {})}
        if method == "POST" and path == "/views":
            return {"object": "view", "id": self._id(), "name": body["name"]}
        raise NotImplementedError(f"FakeClient does not handle {method} {path}")
