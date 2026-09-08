from typing import Literal

from pydantic import BaseModel

from app.core.enums import VisibilityScope


class HarmonyVisibilityRequest(BaseModel):
    visibility: VisibilityScope


class HarmonyHidden(BaseModel):
    kind: Literal["hidden"] = "hidden"


class HarmonyShared(BaseModel):
    kind: Literal["shared"] = "shared"
    summary: Literal["listeners", "sustained"] | None


class HarmonyOwn(BaseModel):
    kind: Literal["owner"] = "owner"
    visibility: VisibilityScope
    positive_count: int
    resolved_count: int
    acceptance_percent: int | None
    active_sending_months: int


HarmonyResponse = HarmonyHidden | HarmonyShared | HarmonyOwn
