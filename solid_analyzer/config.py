"""Configuration management for the SOLID Analyzer framework."""

import os
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class RepoConfig:
    name: str
    url: str
    language: str
    branch: str
    test_command: str
    source_dirs: list[str]
    build_command: Optional[str] = None


@dataclass
class BudgetConfig:
    detections_per_repo: int = 60
    refactorings_per_repo: int = 60
    per_principle: int = 12


@dataclass
class GeminiConfig:
    model: str = "gemini-2.0-flash"
    temperature: float = 0.2
    max_output_tokens: int = 8192
    api_key: str = ""


@dataclass
class Config:
    repositories: list[RepoConfig] = field(default_factory=list)
    budget: BudgetConfig = field(default_factory=BudgetConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    output_dir: Path = Path("output")
    repos_dir: Path = Path("repos")

    SOLID_PRINCIPLES = ["SRP", "OCP", "LSP", "ISP", "DIP"]


def load_config(config_path: str = "data/repos.yaml") -> Config:
    """Load configuration from YAML file and environment variables."""
    config = Config()

    config_file = Path(config_path)
    if config_file.exists():
        with open(config_file) as f:
            raw = yaml.safe_load(f)

        if "repositories" in raw:
            for repo_data in raw["repositories"]:
                config.repositories.append(RepoConfig(**repo_data))

        if "budget" in raw:
            config.budget = BudgetConfig(**raw["budget"])

        if "gemini" in raw:
            gemini_data = raw["gemini"]
            config.gemini = GeminiConfig(**gemini_data)

    # Override API key from environment
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        config.gemini.api_key = api_key

    return config
