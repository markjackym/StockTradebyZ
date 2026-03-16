"""
scheduler/state.py
共享状态读写工具 — Streamlit 与 Scheduler 通过 JSON 文件通信
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = _ROOT / "data" / "state"


def _ensure_dir() -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)


# ── 原子读写 ─────────────────────────────────────────────────────────────────

def read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default if default is not None else {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return default if default is not None else {}


def write_json(path: Path, data: Any) -> None:
    _ensure_dir()
    path.parent.mkdir(parents=True, exist_ok=True)
    # 原子写入：先写临时文件再 rename，防止读到半截 JSON
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows 上 rename 要求目标不存在
        if path.exists():
            path.unlink()
        Path(tmp).rename(path)
    except Exception:
        Path(tmp).unlink(missing_ok=True)
        raise


# ── Pipeline 运行状态 ────────────────────────────────────────────────────────

_STATUS_FILE = STATE_DIR / "pipeline_status.json"

_DEFAULT_STATUS = {
    "state": "idle",       # idle | running | success | failed
    "current_step": "",
    "progress": 0,         # 0-100
    "started_at": "",
    "finished_at": "",
    "error": "",
    "log_tail": [],        # 最近 200 行日志
}


def get_pipeline_status() -> dict:
    data = read_json(_STATUS_FILE, _DEFAULT_STATUS.copy())
    for k, v in _DEFAULT_STATUS.items():
        data.setdefault(k, v)
    return data


def set_pipeline_status(**kwargs: Any) -> None:
    data = get_pipeline_status()
    data.update(kwargs)
    write_json(_STATUS_FILE, data)


def append_log_line(line: str) -> None:
    data = get_pipeline_status()
    tail: list = data.get("log_tail", [])
    tail.append(line.rstrip())
    data["log_tail"] = tail[-200:]
    write_json(_STATUS_FILE, data)


# ── 定时任务配置 ──────────────────────────────────────────────────────────────

_SCHEDULE_FILE = STATE_DIR / "schedule_config.json"

_DEFAULT_SCHEDULE = {
    "enabled": False,
    "hour": 18,
    "minute": 0,
    "days": "mon-fri",   # mon-fri | daily | custom
    "custom_days": [],    # [0,1,2,3,4] (0=Mon)
    "skip_fetch": False,
    "start_from": 1,
}


def get_schedule_config() -> dict:
    data = read_json(_SCHEDULE_FILE, _DEFAULT_SCHEDULE.copy())
    for k, v in _DEFAULT_SCHEDULE.items():
        data.setdefault(k, v)
    return data


def set_schedule_config(config: dict) -> None:
    write_json(_SCHEDULE_FILE, config)


# ── 邮件配置 ──────────────────────────────────────────────────────────────────

_EMAIL_FILE = STATE_DIR / "email_config.json"

_DEFAULT_EMAIL = {
    "enabled": False,
    "smtp_host": os.environ.get("SMTP_HOST", ""),
    "smtp_port": int(os.environ.get("SMTP_PORT", "465")),
    "smtp_user": os.environ.get("SMTP_USER", ""),
    "smtp_pass": os.environ.get("SMTP_PASS", ""),
    "recipients": os.environ.get("SMTP_TO", ""),
}


def get_email_config() -> dict:
    data = read_json(_EMAIL_FILE, _DEFAULT_EMAIL.copy())
    for k, v in _DEFAULT_EMAIL.items():
        data.setdefault(k, v)
    return data


def set_email_config(config: dict) -> None:
    write_json(_EMAIL_FILE, config)


# ── 手动触发 ──────────────────────────────────────────────────────────────────

_TRIGGER_FILE = STATE_DIR / "trigger.json"


def create_trigger(skip_fetch: bool = False, start_from: int = 1) -> None:
    write_json(_TRIGGER_FILE, {
        "triggered_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "skip_fetch": skip_fetch,
        "start_from": start_from,
    })


def consume_trigger() -> dict | None:
    if not _TRIGGER_FILE.exists():
        return None
    data = read_json(_TRIGGER_FILE)
    if not data:
        return None
    try:
        _TRIGGER_FILE.unlink()
    except OSError:
        pass
    return data


# ── 运行历史 ──────────────────────────────────────────────────────────────────

_RUNS_FILE = STATE_DIR / "runs.json"


def append_run_log(entry: dict) -> None:
    runs = read_json(_RUNS_FILE, [])
    if not isinstance(runs, list):
        runs = []
    runs.insert(0, entry)
    runs = runs[:50]  # 保留最近 50 条
    write_json(_RUNS_FILE, runs)


def get_run_logs(limit: int = 20) -> list[dict]:
    runs = read_json(_RUNS_FILE, [])
    if not isinstance(runs, list):
        return []
    return runs[:limit]
