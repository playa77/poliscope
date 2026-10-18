"""Shared structural contract primitives; authoritative semantics live elsewhere."""
from typing import Annotated
from pydantic import BaseModel, ConfigDict, Field

Identifier = Annotated[str, Field(min_length=1, max_length=256)]


class Contract(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, frozen=True)
