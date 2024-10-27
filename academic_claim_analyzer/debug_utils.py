import functools
import logging
import traceback
import asyncio
from datetime import datetime
import os
import sys
import codecs

# Configure a separate debug logger for file output only
debug_logger = logging.getLogger('debug_logger')
debug_logger.setLevel(logging.DEBUG)

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Create a new log file for each run
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
debug_handler = logging.FileHandler(f'logs/debug_{timestamp}.log', encoding='utf-8')
debug_handler.setLevel(logging.DEBUG)
debug_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
debug_handler.setFormatter(debug_formatter)
debug_logger.addHandler(debug_handler)

# Remove any existing console handlers
debug_logger.propagate = False  # Prevent propagation to root logger

def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max_length and add ellipsis if needed."""
    return f"{text[:max_length]}..." if len(text) > max_length else text

class UnicodeStreamHandler(logging.StreamHandler):
    """Custom StreamHandler that ensures Unicode compatibility."""
    def __init__(self, stream=None):
        super().__init__(stream)
        # Force UTF-8 encoding for Windows console
        if stream is None and sys.platform == 'win32':
            # Configure console to use utf-8
            try:
                import ctypes
                kernel32 = ctypes.windll.kernel32
                kernel32.SetConsoleOutputCP(65001)  # Set console to UTF-8
            except:
                pass
            sys.stdout.reconfigure(encoding='utf-8')
            stream = sys.stdout
        self.stream = stream or sys.stdout

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            # Write with proper encoding
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

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
    
    # Console handler with custom level and Unicode support
    console_handler = UnicodeStreamHandler()
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler with DEBUG level
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(getattr(logging, file_level.upper()))
    file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)