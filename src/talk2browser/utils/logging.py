"""Logging configuration for talk2browser."""
import logging
import sys
from typing import Optional, cast


class ColoredFormatter(logging.Formatter):
    """Custom formatter that adds colors to log levels."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',     # Cyan
        'INFO': '\033[32m',      # Green
        'WARNING': '\033[33m',   # Yellow
        'ERROR': '\033[31m',     # Red
        'CRITICAL': '\033[31;1m', # Bright Red
        'RESET': '\033[0m'       # Reset to default
    }
    
    def format(self, record):
        # Get the original format
        log_fmt = self._style._fmt
        
        # Add color to the levelname
        if record.levelname in self.COLORS:
            record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{self.COLORS['RESET']}"
        
        # Call the original formatter
        result = super().format(record)
        
        # Restore the original format for other handlers
        self._style._fmt = log_fmt
        
        return result


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a configured logger instance.
    
    Args:
        name: Logger name (usually __name__)
        level: Optional log level (default: INFO)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    # Only configure if this is the root logger or has no handlers
    if not logger.handlers and (logger.level == logging.NOTSET or level is not None):
        if level is None:
            level = logging.INFO
            
        logger.setLevel(level)
        
        # Create console handler with colored output
        console = logging.StreamHandler(sys.stdout)
        console.setLevel(level)
        
        # Create formatter and add it to the handler
        formatter = ColoredFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console.setFormatter(formatter)
        
        # Add the handler to the logger
        logger.addHandler(console)
    
    return logger


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None) -> None:
    """Configure logging for the application.
    
    Args:
        level: Logging level (default: INFO)
        log_file: Optional file to log to
    """
    # Remove all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set up console handler with colored output
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    
    # Create formatter
    formatter = ColoredFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console.setFormatter(formatter)
    
    # Add console handler to root logger
    root_logger.setLevel(level)
    root_logger.addHandler(console)
    
    # Optionally add file handler
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Set log level for external libraries
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
