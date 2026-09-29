from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "setup", "public_action", "private_info", "phase_change", "resolve", "correction"
]
Visibility = Literal["private", "public"]


class Event(BaseModel):
    type: EventType
    raw_text: str
    parsed: dict[str, Any] = Field(default_factory=dict)
    visibility: Visibility = "public"
    conflict: bool = False


class Clarification(BaseModel):
    slot: str
    question: str


class RuleCard(BaseModel):
    game_name: str = ""
    phases: list[str] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)
    scoring_notes: list[str] = Field(default_factory=list)
    ambiguities: list[str] = Field(default_factory=list)
    critical_slots: list[str] = Field(
        default_factory=lambda: ["hand", "funds", "phase", "active_seat"]
    )
    raw_summary: str = ""


class GameState(BaseModel):
    phase: str | None = None
    active_seat: str | None = None
    me: dict[str, Any] = Field(default_factory=dict)
    public: dict[str, Any] = Field(default_factory=dict)
    last_events: list[str] = Field(default_factory=list)
    pending_clarifications: list[Clarification] = Field(default_factory=list)
    out_of_view_notes: list[str] = Field(default_factory=list)


class CandidateAction(BaseModel):
    action: str
    rationale: str
    assumptions: list[str] = Field(default_factory=list)


class LegalityReport(BaseModel):
    action: str
    legal: bool
    reason: str = ""


class AdviceResult(BaseModel):
    final_text: str
    candidates: list[CandidateAction] = Field(default_factory=list)
    legality: list[LegalityReport] = Field(default_factory=list)
    clarifications: list[Clarification] = Field(default_factory=list)
