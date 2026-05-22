"""Core ChatKit application class — a thin convenience layer over FastAPI."""
from dataclasses import dataclass, field
from typing import Optional

from fastapi import FastAPI


@dataclass
class Persona:
    """One chat persona: a system prompt + optional tool definitions."""
    slug: str
    name: str
    system_prompt: str
    description: str = ""
    tools: list = field(default_factory=list)
    visible: bool = True
    intro_message: str = ""


class ChatKit:
    """Multi-persona chat application built on FastAPI.

    Typical usage:

        kit = ChatKit(title="My App")
        kit.register(Persona(slug="support", name="Support",
                             system_prompt="You are helpful."))
        app = kit.app
    """

    def __init__(self, title: str = "Chat Console") -> None:
        self.app = FastAPI(title=title)
        self.personas: dict[str, Persona] = {}

    def register(self, persona: Persona) -> None:
        if persona.slug in self.personas:
            raise ValueError(f"Persona {persona.slug!r} already registered")
        self.personas[persona.slug] = persona

    def get(self, slug: str) -> Optional[Persona]:
        return self.personas.get(slug)

    def visible(self) -> list[Persona]:
        return [p for p in self.personas.values() if p.visible]

    def __call__(self, *args, **kwargs):
        return self.app(*args, **kwargs)
