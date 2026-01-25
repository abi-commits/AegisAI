"""Centralized logging configuration."""

import logging
from typing import Optional


def get_logger(name: str, level: str = "INFO") -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
