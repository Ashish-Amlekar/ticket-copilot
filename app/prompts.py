"""Load versioned prompt files from prompts/<name>/<version>.yaml."""

from dataclasses import dataclass

import yaml

from app.config import PROMPT_NAME, PROMPT_VERSION, ROOT


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    system: str
    user: str

    @property
    def label(self) -> str:
        return f"{self.name}@{self.version}"

    def render(self, **values: str) -> list[dict]:
        # str.replace instead of str.format so braces in the JSON schema or in
        # ticket text can never break rendering.
        user = self.user
        for key, value in values.items():
            user = user.replace("{" + key + "}", value)
        return [
            {"role": "system", "content": self.system},
            {"role": "user", "content": user},
        ]


def load_prompt(name: str = PROMPT_NAME, version: str = PROMPT_VERSION) -> Prompt:
    path = ROOT / "prompts" / name / f"{version}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return Prompt(name=data["name"], version=data["version"], system=data["system"], user=data["user"])