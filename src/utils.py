"""
Utilities — logging, configuration, and common helpers.
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv


def setup_logging(level: str = "INFO", log_dir: str = "logs") -> logging.Logger:
    """
    Configure structured logging with both console and file handlers.

    Returns the root logger for the application.
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_path / f"etl_run_{timestamp}.log"

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    logger = logging.getLogger("financial_etl")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    logger.info("Logging initialised — file: %s", log_file)
    return logger


def load_config(config_path: str = "config/etl_config.yaml") -> dict:
    """
    Load pipeline configuration from YAML, with env-var interpolation.

    Environment variables in the form ``${VAR:-default}`` are resolved.
    """
    load_dotenv()

    with open(config_path, "r") as f:
        raw = f.read()

    # Simple env-var substitution: ${VAR:-default}
    import re

    def _replace_env(match: re.Match) -> str:
        var_name = match.group(1)
        default = match.group(2) if match.group(2) is not None else ""
        return os.getenv(var_name, default)

    resolved = re.sub(r"\$\{(\w+)(?::-([^}]*))?\}", _replace_env, raw)

    config = yaml.safe_load(resolved)
    return config


class PipelineContext:
    """
    Shared context for a single pipeline run.

    Holds configuration, logger, and run metadata.
    """

    def __init__(self, config: dict, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.stats: dict[str, int] = {
            "extracted": 0,
            "validated": 0,
            "validation_failures": 0,
            "transformed": 0,
            "loaded": 0,
        }

    def summary(self) -> str:
        """Return a human-readable run summary."""
        lines = [f"Pipeline Run {self.run_id}"]
        for key, value in self.stats.items():
            lines.append(f"  {key}: {value:,}")
        return "\n".join(lines)
