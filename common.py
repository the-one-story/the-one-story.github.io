"""Shared helpers: config loading, paths, small utilities.

Kept deliberately tiny so each stage can be read and run on its own.
"""
from __future__ import annotations

import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import yaml

ROOT = os.path.dirname(os.path.abspath(__file__))


def _path(*parts: str) -> str:
    return os.path.join(ROOT, *parts)


def load_settings() -> dict:
    with open(_path("config", "settings.yaml"), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_feeds() -> list[dict]:
    with open(_path("config", "feeds.yaml"), "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)["feeds"]


def tz_now(settings: dict) -> datetime:
    """Timezone-aware 'now' in the configured timezone."""
    return datetime.now(ZoneInfo(settings["timezone"]))


def read_json(rel_path: str, default=None):
    path = _path(rel_path)
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(rel_path: str, obj) -> str:
    path = _path(rel_path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
    return path


def rel(path: str) -> str:
    return _path(path)
