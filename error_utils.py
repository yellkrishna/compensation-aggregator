"""
Error handling utilities for the Compensation Aggregator application.
Provides centralized error handling, logging, and recovery mechanisms.
"""

import logging
import traceback
import time
import functools
import random
from typing import Callable, TypeVar, Any, Optional, Dict, List, Union

# Type variable for generic function return type
T = TypeVar('T')

# Configure module logger
logger = logging.getLogger(__name__)

class ApplicationError(Exception):
    """Base exception class for application-specific errors."""
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)

class ScrapingError(ApplicationError):
    """Exception raised for errors during web scraping."""
    pass

class DataProcessingError(ApplicationError):
    """Exception raised for errors during data processing."""
    pass

class APIError(ApplicationError):
    """Exception raised for errors when interacting with external APIs."""
    pass

class ConfigurationError(ApplicationError):
    """Exception raised for errors in application configuration."""
    pass

def with_logging(func: Callable[..., T]) -> Callable[..., T]:
    """
    Decorator to add logging to any function.
    Logs function entry, exit, and any exceptions raised.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func_name = func.__name__
        logger.debug(f"Entering {func_name}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"Exiting {func_name}")
            return result
        except Exception as e:
            logger.error(f"Exception in {func_name}: {str(e)}")
            logger.debug(traceback.format_exc())
            raise
    return wrapper

def with_retry(
    max_attempts: int = 3, 
    backoff_factor: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator to retry a function on failure with exponential backoff.
    
    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Multiplier for exponential backoff
        jitter: Whether to add random jitter to backoff time
        exceptions: Tuple of exceptions to catch and retry on
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_attempts:
                        # Calculate backoff time with optional jitter
                        backoff_time = backoff_factor ** (attempt - 1)
                        if jitter:
                            backoff_time = backoff_time * (1 + random.random() * 0.1)
                            
                        logger.warning(
                            f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: "
                            f"{str(e)}. Retrying in {backoff_time:.2f}s"
                        )
                        time.sleep(backoff_time)
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )
            
            # If we get here, all attempts failed
            if last_exception:
                raise last_exception
            
            # This should never happen, but just in case
            raise RuntimeError(f"All {max_attempts} attempts failed for {func.__name__}")
            
        return wrapper
    return decorator

def safe_execute(
    func: Callable[..., T], 
    default_value: Any = None, 
    log_exception: bool = True,
    *args, **kwargs
) -> Union[T, Any]:
    """
    Safely execute a function, returning a default value on exception.
    
    Args:
        func: Function to execute
        default_value: Value to return if function raises an exception
        log_exception: Whether to log the exception
        *args, **kwargs: Arguments to pass to the function
        
    Returns:
        Function result or default value on exception
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_exception:
            logger.error(f"Error executing {func.__name__}: {str(e)}")
            logger.debug(traceback.format_exc())
        return default_value

def format_exception(e: Exception) -> str:
    """
    Format an exception into a user-friendly error message.
    
    Args:
        e: The exception to format
        
    Returns:
        Formatted error message
    """
    if isinstance(e, ApplicationError):
        if e.original_error:
            return f"{e.message} (Caused by: {str(e.original_error)})"
        return e.message
    return str(e)

def get_error_context(e: Exception) -> Dict[str, Any]:
    """
    Get additional context information about an exception.
    
    Args:
        e: The exception to get context for
        
    Returns:
        Dictionary with error context information
    """
    context = {
        'error_type': e.__class__.__name__,
        'error_message': str(e),
        'timestamp': time.time(),
    }
    
    # Add traceback information
    tb = traceback.format_exc()
    context['traceback'] = tb
    
    # Add original error for application errors
    if isinstance(e, ApplicationError) and e.original_error:
        context['original_error_type'] = e.original_error.__class__.__name__
        context['original_error_message'] = str(e.original_error)
    
    return context
