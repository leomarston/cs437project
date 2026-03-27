"""Logging setup for the framework."""

import logging
import sys
from pathlib import Path
from rich.logging import RichHandler


def setup_logging(verbose: bool = False, log_file: str | None = None) -> logging.Logger:
    """Configure structured logging with rich console output."""
    level = logging.DEBUG if verbose else logging.INFO
    handlers: list[logging.Handler] = [
        RichHandler(
            level=level,
            show_time=True,
            show_path=False,
            markup=True,
        )
    ]

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
        handlers.append(file_handler)

    logging.basicConfig(
        level=level,
        format="%(message)s",
        handlers=handlers,
        force=True,
    )

    return logging.getLogger("solid_analyzer")
