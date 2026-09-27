from typing import Literal

from pydantic import BaseModel

Provider = Literal["spotify", "apple", "youtube", "tidal", "deezer", "amazon"]


class StreamingLink(BaseModel):
    provider: Provider
    name: str
    url: str
    kind: Literal["exact", "search"]


class StreamingResponse(BaseModel):
    links: list[StreamingLink]
    mapping_status: Literal["available", "unavailable"]
