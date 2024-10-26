# academic_claim_analyzer/debug_utils.py

import functools
import logging
import traceback
import asyncio
from datetime import datetime
import os

__all__ = ['debug_decorator', 'configure_logging']  # Add this line to explicitly export the functions

# Configure a separate debug logger for file output only
debug_logger = logging.getLogger('debug_logger')
debug_logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Create a new log file for each run
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
debug_handler = logging.FileHandler(f'logs/debug_{timestamp}.log')
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
debug_handler.setFormatter(debug_formatter)
debug_logger.addHandler(debug_handler)

# Remove any existing console handlers
debug_logger.propagate = False  # Prevent propagation to root logger

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length and add ellipsis if needed."""
    return f"{text[:max_length]}..." if len(text) > max_length else text

def debug_decorator(func):
    """
    Decorator to log the entry, exit, arguments, and exceptions of functions.
    Supports both synchronous and asynchronous functions.
    """
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        func_name = func.__name__
        # Log full details to file
        debug_logger.debug(f"Entering async function: {func_name}")
        debug_logger.debug(f"Args: {args}")
        debug_logger.debug(f"Kwargs: {kwargs}")
        
        try:
            result = await func(*args, **kwargs)
            # Log full result to file
            debug_logger.debug(f"Full result from {func_name}: {result}")
            return result
        except Exception as e:
            debug_logger.error(f"Exception in async function {func_name}: {str(e)}")
            debug_logger.error(traceback.format_exc())
            raise

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        func_name = func.__name__
        # Log full details to file
        debug_logger.debug(f"Entering sync function: {func_name}")
        debug_logger.debug(f"Args: {args}")
        debug_logger.debug(f"Kwargs: {kwargs}")
        
        try:
            result = func(*args, **kwargs)
            # Log full result to file
            debug_logger.debug(f"Full result from {func_name}: {result}")
            return result
        except Exception as e:
            debug_logger.error(f"Exception in sync function {func_name}: {str(e)}")
            debug_logger.error(traceback.format_exc())
            raise

    if asyncio.iscoroutinefunction(func):
        return async_wrapper
    else:
        return sync_wrapper

# Add new logging configuration function
def configure_logging(log_file: str = 'debug.log', console_level: str = 'INFO', file_level: str = 'DEBUG'):
    """
    Configure logging with separate handlers for console and file output.
    
    Args:
        log_file: Path to log file
        console_level: Logging level for console output ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
        file_level: Logging level for file output
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Capture all levels
    
    # Remove existing handlers
    root_logger.handlers = []
    
    # Console handler with custom level
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with DEBUG level
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(getattr(logging, file_level.upper()))
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
