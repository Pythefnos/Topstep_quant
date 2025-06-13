"""
Logger configuration for structured logging with UTC timestamps and service context.
"""
import logging
import sys
import time
from typing import Optional, Union

# Global variable to store configured service name for logging
_SERVICE_NAME: Optional[str] = None

def configure_logger(service_name: str,
                     level: Union[int, str] = logging.INFO,
                     log_file: Optional[str] = None) -> logging.Logger:
    """
    Configure and return a structured logger with given service name and log level.

    Logs are output to stdout and optionally to a file, with UTC timestamps and service name.
    This should be called once at application startup.

    Parameters:
        service_name (str): Name of the service or bot (included in log records).
        level (int or str): Logging level (e.g. logging.INFO or "DEBUG").
        log_file (str, optional): File path to write logs to.
            If provided, logs will be written to this file in addition to stdout.

    Returns:
        logging.Logger: Configured logger instance.
    """
    global _SERVICE_NAME
    _SERVICE_NAME = service_name

    # Convert level to numeric if given as string
    log_level = level
    if isinstance(level, str):
        log_level = logging.getLevelName(level.upper())
        if not isinstance(log_level, int):
            # If level name is invalid, default to INFO
            log_level = logging.INFO

    # Create logger with service name
    logger = logging.getLogger(service_name)
    logger.setLevel(log_level)
    logger.propagate = False  # avoid duplicate logs on root handlers

    # Remove existing handlers if already configured
    if logger.handlers:
        for h in logger.handlers:
            logger.removeHandler(h)

    # Ensure UTC timestamps in logs
    logging.Formatter.converter = time.gmtime

    # Define log format to include
    # timestamp (UTC), level, service name, and message
    log_format = "%(asctime)sZ | %(levelname)s | [%(name)s] %(message)s"
    date_format = "%Y-%m-%dT%H:%M:%SZ"
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)

    # Stream handler for stdout
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    # File handler if log_file is specified
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            # If file handler cannot be created, log an error to stdout
            logger.error("Failed to set up file logging at %s: %s", log_file, e)

    return logger

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Retrieve a logger by name. If name is None, returns the logger for the configured service.

    Parameters:
        name (str, optional): The name of the logger to retrieve. Defaults to the configured service name.

    Returns:
        logging.Logger: The logger instance.
    """
    if name is None:
        if _SERVICE_NAME is None:
            # If service logger not configured, default to root logger
            return logging.getLogger()
        return logging.getLogger(_SERVICE_NAME)
    return logging.getLogger(name)
