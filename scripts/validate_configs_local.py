"""Validate the prepared local and GitHub Actions configs without using secrets."""

import json
from pathlib import Path

from src.models import Config


for config_path in (Path("data/config.json"), Path("data/config.github.json")):
    config = Config.model_validate(json.loads(config_path.read_text(encoding="utf-8")))
    print(f"{config_path}: OK ({config.ai.provider.value}/{config.ai.model})")
