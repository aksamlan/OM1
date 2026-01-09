"""
Enhanced error handling utility for OM1 runtime.

This module provides robust error handling, logging, and recovery mechanisms
for the OM1 modular AI runtime. It includes:
- Structured error logging with context
- Automatic retry logic for transient failures
- Graceful degradation strategies
- Error metrics and monitoring hooks
"""

import asyncio
import functools
import logging
import sys
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional, Type, TypeVar, Union

# Type variable for generic function returns
T = TypeVar('T')


class ErrorSeverity(Enum):
    """Classification of error severity levels."""
    LOW = "low"           # Non-critical, can be ignored
    MEDIUM = "medium"     # Important but system can continue
    HIGH = "high"         # Critical, requires immediate attention
    FATAL = "fatal"       # System cannot continue


class OM1Error(Exception):
    """Base exception class for OM1 runtime errors."""
    
    def __init__(
        self,
        message: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.context = context or {}
        self.original_exception = original_exception
        self.timestamp = datetime.now()
        
    def to_dict(self) -> dict[str, Any]:
        """Convert error to dictionary format for logging/monitoring."""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "severity": self.severity.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
            "original_exception": str(self.original_exception) if self.original_exception else None,
        }


class HardwareConnectionError(OM1Error):
    """Raised when hardware connection fails."""
    pass


class SensorError(OM1Error):
    """Raised when sensor input fails."""
    pass


class ActionExecutionError(OM1Error):
    """Raised when action execution fails."""
    pass


class LLMError(OM1Error):
    """Raised when LLM API call fails."""
    pass


def get_om1_logger(name: str) -> logging.Logger:
    """
    Get or create a logger with OM1-specific formatting.
    
    Args:
        name: Logger name (typically module name)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"om1.{name}")
    
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


def handle_error(
    error: Exception,
    logger: logging.Logger,
    context: Optional[dict[str, Any]] = None,
    severity: ErrorSeverity = ErrorSeverity.MEDIUM,
    reraise: bool = False
) -> None:
    """
    Centralized error handling with logging and context.
    
    Args:
        error: The exception that occurred
        logger: Logger instance for recording the error
        context: Additional context information
        severity: Error severity level
        reraise: Whether to re-raise the exception after logging
    """
    error_context = context or {}
    
    # If it's already an OM1Error, preserve its context
    if isinstance(error, OM1Error):
        error_context.update(error.context)
        severity = error.severity
    
    # Build comprehensive error message
    error_info = {
        "error_type": type(error).__name__,
        "message": str(error),
        "severity": severity.value,
        "context": error_context,
        "traceback": traceback.format_exc()
    }
    
    # Log based on severity
    if severity in (ErrorSeverity.FATAL, ErrorSeverity.HIGH):
        logger.error(f"[{severity.value.upper()}] {error_info['error_type']}: {error_info['message']}", 
                    extra={"error_info": error_info})
    elif severity == ErrorSeverity.MEDIUM:
        logger.warning(f"[{severity.value.upper()}] {error_info['error_type']}: {error_info['message']}", 
                      extra={"error_info": error_info})
    else:
        logger.info(f"[{severity.value.upper()}] {error_info['error_type']}: {error_info['message']}")
    
    if reraise:
        raise


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    logger: Optional[logging.Logger] = None
) -> Callable:
    """
    Decorator for automatic retry logic with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
        logger: Logger for recording retry attempts
        
    Returns:
        Decorated function with retry logic
        
    Example:
        @with_retry(max_attempts=3, delay=1.0, exceptions=(ConnectionError,))
        async def connect_to_robot():
            # Connection code that might fail transiently
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 1
            current_delay = delay
            _logger = logger or get_om1_logger(func.__module__)
            
            while attempt <= max_attempts:
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        _logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise
                    
                    _logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {current_delay:.1f}s: {str(e)}"
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
            
            raise RuntimeError("Unexpected end of retry loop")
        
        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            attempt = 1
            current_delay = delay
            _logger = logger or get_om1_logger(func.__module__)
            
            while attempt <= max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_attempts:
                        _logger.error(
                            f"Function {func.__name__} failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise
                    
                    _logger.warning(
                        f"Function {func.__name__} failed (attempt {attempt}/{max_attempts}), "
                        f"retrying in {current_delay:.1f}s: {str(e)}"
                    )
                    import time
                    time.sleep(current_delay)
                    current_delay *= backoff
                    attempt += 1
            
            raise RuntimeError("Unexpected end of retry loop")
        
        # Return appropriate wrapper based on whether function is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


def safe_execute(
    func: Callable[..., T],
    *args: Any,
    default: Optional[T] = None,
    logger: Optional[logging.Logger] = None,
    error_message: Optional[str] = None,
    **kwargs: Any
) -> Union[T, None]:
    """
    Execute a function safely with automatic error handling.
    
    Args:
        func: Function to execute
        *args: Positional arguments for function
        default: Default value to return on error
        logger: Logger for recording errors
        error_message: Custom error message prefix
        **kwargs: Keyword arguments for function
        
    Returns:
        Function result or default value on error
        
    Example:
        result = safe_execute(
            robot.move,
            x=1.0, y=0.0,
            default=False,
            error_message="Failed to move robot"
        )
    """
    _logger = logger or get_om1_logger(func.__module__ if hasattr(func, '__module__') else __name__)
    
    try:
        return func(*args, **kwargs)
    except Exception as e:
        prefix = error_message or f"Error executing {func.__name__}"
        handle_error(
            e,
            _logger,
            context={"args": args, "kwargs": kwargs},
            severity=ErrorSeverity.MEDIUM,
            reraise=False
        )
        return default


async def safe_execute_async(
    func: Callable[..., T],
    *args: Any,
    default: Optional[T] = None,
    logger: Optional[logging.Logger] = None,
    error_message: Optional[str] = None,
    **kwargs: Any
) -> Union[T, None]:
    """
    Async version of safe_execute.
    
    Args:
        func: Async function to execute
        *args: Positional arguments for function
        default: Default value to return on error
        logger: Logger for recording errors
        error_message: Custom error message prefix
        **kwargs: Keyword arguments for function
        
    Returns:
        Function result or default value on error
    """
    _logger = logger or get_om1_logger(func.__module__ if hasattr(func, '__module__') else __name__)
    
    try:
        return await func(*args, **kwargs)
    except Exception as e:
        prefix = error_message or f"Error executing {func.__name__}"
        handle_error(
            e,
            _logger,
            context={"args": args, "kwargs": kwargs},
            severity=ErrorSeverity.MEDIUM,
            reraise=False
        )
        return default
