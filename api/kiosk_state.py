"""In-memory kiosk / agent state shared by Admin and Agent screens."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any
from uuid import uuid4

_lock = Lock()


def _persist_session(event: dict[str, Any]) -> None:
    try:
        from backend.db import store

        store.save_kiosk_session(event)
    except Exception:
        pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class KioskSession:
    id: str
    started_at: str
    ended_at: str | None = None
    phase: str = "greeting"  # greeting | conversation | ended
    note: str = ""


@dataclass
class KioskState:
    running: bool = False
    phase: str = "stopped"  # stopped | idle | greeting | conversation
    started_at: str | None = None
    stopped_at: str | None = None
    current_session_id: str | None = None
    person_present: bool = False
    last_event: str = "Kiosk not started"
    updated_at: str = field(default_factory=_now)
    sessions: list[KioskSession] = field(default_factory=list)


_state = KioskState()


def get_status_lite() -> dict[str, Any]:
    """Lightweight status for frequent polling — omits session history."""
    with _lock:
        return {
            "running": _state.running,
            "phase": _state.phase,
            "started_at": _state.started_at,
            "stopped_at": _state.stopped_at,
            "current_session_id": _state.current_session_id,
            "person_present": _state.person_present,
            "last_event": _state.last_event,
            "updated_at": _state.updated_at,
            "demo_mode": True,
        }


def get_status() -> dict[str, Any]:
    with _lock:
        recent = [
            asdict(s) for s in reversed(_state.sessions[-20:])
        ]
        lite = {
            "running": _state.running,
            "phase": _state.phase,
            "started_at": _state.started_at,
            "stopped_at": _state.stopped_at,
            "current_session_id": _state.current_session_id,
            "person_present": _state.person_present,
            "last_event": _state.last_event,
            "updated_at": _state.updated_at,
            "demo_mode": True,
        }
        return {**lite, "sessions": recent}


def start_kiosk() -> dict[str, Any]:
    with _lock:
        _state.running = True
        _state.phase = "idle"
        _state.started_at = _now()
        _state.stopped_at = None
        _state.current_session_id = None
        _state.person_present = False
        _state.last_event = "Admin started agent kiosk"
        _state.updated_at = _now()
    _persist_session(
        {
            "session_id": _state.current_session_id or "kiosk",
            "event": "start_kiosk",
            "phase": _state.phase,
            "running": True,
            "started_at": _state.started_at,
        }
    )
    return get_status()


def stop_kiosk() -> dict[str, Any]:
    with _lock:
        ended_sid = _state.current_session_id
        if ended_sid:
            for s in _state.sessions:
                if s.id == ended_sid and s.ended_at is None:
                    s.ended_at = _now()
                    s.phase = "ended"
                    s.note = "Ended when admin stopped kiosk"
        _state.running = False
        _state.phase = "stopped"
        _state.stopped_at = _now()
        _state.current_session_id = None
        _state.person_present = False
        _state.last_event = "Admin stopped agent kiosk"
        _state.updated_at = _now()
    if ended_sid:
        _persist_session(
            {
                "session_id": ended_sid,
                "event": "stop_kiosk",
                "phase": "stopped",
                "running": False,
                "ended_at": _now(),
            }
        )
    return get_status()


def set_presence(present: bool) -> dict[str, Any]:
    with _lock:
        if not _state.running:
            return get_status()
        _state.person_present = present
        _state.updated_at = _now()
        if present and _state.phase == "idle":
            _state.last_event = "Person detected near kiosk"
        elif not present and _state.phase == "idle":
            _state.last_event = "Waiting for customer"
        else:
            _state.last_event = (
                "Person present" if present else "Person left detection zone"
            )
    return get_status()


def begin_session(note: str = "") -> dict[str, Any]:
    with _lock:
        if not _state.running:
            raise RuntimeError("Kiosk is not running. Start it from Admin first.")
        if _state.current_session_id:
            # Stale session from a previous customer — end and start fresh
            if _state.phase in ("conversation", "greeting"):
                for s in _state.sessions:
                    if s.id == _state.current_session_id and s.ended_at is None:
                        s.ended_at = _now()
                        s.phase = "ended"
                        s.note = note or "Auto-ended for new customer"
                _state.current_session_id = None
                _state.phase = "idle"
                _state.person_present = False
            else:
                return get_status()
        sid = uuid4().hex[:12]
        session = KioskSession(
            id=sid,
            started_at=_now(),
            phase="greeting",
            note=note or "Auto-started on presence",
        )
        _state.sessions.append(session)
        _state.current_session_id = sid
        _state.phase = "greeting"
        _state.last_event = "Greeting customer"
        _state.updated_at = _now()
        snap = {
            "session_id": sid,
            "event": "begin_session",
            "phase": "greeting",
            "started_at": session.started_at,
            "note": session.note,
        }
    _persist_session(snap)
    return get_status()


def set_phase(phase: str) -> dict[str, Any]:
    allowed = {"idle", "greeting", "conversation"}
    if phase not in allowed:
        raise ValueError(f"Invalid phase: {phase}")
    with _lock:
        if not _state.running:
            raise RuntimeError("Kiosk is not running")
        _state.phase = phase
        if phase == "idle":
            if _state.current_session_id:
                for s in _state.sessions:
                    if s.id == _state.current_session_id and s.ended_at is None:
                        s.ended_at = _now()
                        s.phase = "ended"
                        s.note = "Reset to idle"
                _state.current_session_id = None
                _state.person_present = False
        elif _state.current_session_id:
            for s in _state.sessions:
                if s.id == _state.current_session_id:
                    s.phase = phase
        labels = {
            "idle": "Ready for next customer",
            "greeting": "Greeting customer",
            "conversation": "In conversation",
        }
        _state.last_event = labels[phase]
        _state.updated_at = _now()
        sid = _state.current_session_id
        snap = {
            "session_id": sid,
            "event": "set_phase",
            "phase": phase,
            "last_event": _state.last_event,
        } if sid else None
    if snap:
        _persist_session(snap)
    return get_status()


def end_session(note: str = "") -> dict[str, Any]:
    with _lock:
        ended_sid = _state.current_session_id
        if ended_sid:
            for s in _state.sessions:
                if s.id == ended_sid and s.ended_at is None:
                    s.ended_at = _now()
                    s.phase = "ended"
                    s.note = note or "Session ended"
        _state.current_session_id = None
        _state.phase = "idle" if _state.running else "stopped"
        _state.person_present = False
        _state.last_event = "Session ended — waiting for next customer"
        _state.updated_at = _now()
    if ended_sid:
        _persist_session(
            {
                "session_id": ended_sid,
                "event": "end_session",
                "phase": "ended",
                "ended_at": _now(),
                "note": note or "Session ended",
            }
        )
    return get_status()
