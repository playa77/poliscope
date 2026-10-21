"""Noncontent references only; private payloads never enter immutable inputs."""
from typing import Annotated, Literal
from pydantic import Field
from .base import Contract, Identifier

class NoteReference(Contract):
    id: Identifier
    version: Identifier
    scope_id: Identifier
    classification: Literal['private']

class GoalScope(Contract):
    id: Identifier
    scope_id: Identifier
