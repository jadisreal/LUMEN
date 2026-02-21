# skills/skill_registry.py - Centralized skill dispatch for LUMEN
#
# Each skill declares:
#   - intent   : the LLM intent string it handles
#   - handler  : callable(parameters, response, player, session_memory, **kw)
#   - name     : human-readable label (used in thread names / logs)
#   - description : one-liner for debugging / listing
#
# Register once at startup, dispatch with registry.get(intent).

from core.logger import get_logger

log = get_logger("skills")


class Skill:
    """A registered skill that handles a specific intent."""

    def __init__(self, intent: str, handler, name: str = None, description: str = ""):
        self.intent = intent
        self.handler = handler
        self.name = name or intent
        self.description = description

    def __repr__(self):
        return f"Skill({self.intent!r}, name={self.name!r})"


class SkillRegistry:
    """Maps LLM intent strings → Skill objects for clean dispatch."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}

    def register(self, intent: str, handler, name: str = None, description: str = ""):
        """Register a handler for an intent. Returns the created Skill."""
        skill = Skill(intent, handler, name, description)
        self._skills[intent] = skill
        log.debug(f"Registered skill: {skill}")
        return skill

    def get(self, intent: str) -> Skill | None:
        """Return the Skill for *intent*, or None."""
        return self._skills.get(intent)

    def has(self, intent: str) -> bool:
        """Check whether *intent* is registered."""
        return intent in self._skills

    def dispatch(self, intent: str, **kwargs):
        """Call the handler for *intent* with the given kwargs."""
        skill = self.get(intent)
        if skill:
            return skill.handler(**kwargs)
        return None

    def list_intents(self) -> list[str]:
        """Return all registered intent strings."""
        return list(self._skills.keys())

    def list_skills(self) -> list[Skill]:
        """Return all registered Skill objects."""
        return list(self._skills.values())
