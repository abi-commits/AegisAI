#!/usr/bin/env python3
"""Main entry point for AegisAI."""

from aegis_ai.common.logging import get_logger
from aegis_ai.common.config import Config

logger = get_logger(__name__)


def main():
    """Main entry point."""
    config = Config()
    logger.info(f"AegisAI initialized in {config.environment} mode")
    logger.info(f"Project root: {config.project_root}")


if __name__ == "__main__":
    main()
