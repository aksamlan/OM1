"""
Unit tests for error_handler module.

Tests cover:
- Error classification and logging
- Retry mechanisms with backoff
- Safe execution wrappers
- Custom OM1 exception types
"""

import asyncio
import logging
import pytest
from unittest.mock import Mock, patch

from src.utils.error_handler import (
    ErrorSeverity,
    OM1Error,
    HardwareConnectionError,
    SensorError,
    ActionExecutionError,
    LLMError,
    get_om1_logger,
    handle_error,
    with_retry,
    safe_execute,
    safe_execute_async,
)


class TestOM1Error:
    """Test suite for OM1Error exception class."""
    
    def test_om1_error_creation(self):
        """Test basic OM1Error instantiation."""
        error = OM1Error(
            "Test error",
            severity=ErrorSeverity.HIGH,
            context={"module": "test"}
        )
        
        assert error.message == "Test error"
        assert error.severity == ErrorSeverity.HIGH
        assert error.context["module"] == "test"
        assert error.timestamp is not None
    
    def test_om1_error_to_dict(self):
        """Test error serialization to dictionary."""
        error = OM1Error("Test error", context={"key": "value"})
        error_dict = error.to_dict()
        
        assert error_dict["error_type"] == "OM1Error"
        assert error_dict["message"] == "Test error"
        assert error_dict["severity"] == ErrorSeverity.MEDIUM.value
        assert error_dict["context"]["key"] == "value"
    
    def test_custom_error_types(self):
        """Test custom OM1 error subclasses."""
        hw_error = HardwareConnectionError("Hardware failed")
        sensor_error = SensorError("Sensor failed")
        action_error = ActionExecutionError("Action failed")
        llm_error = LLMError("LLM failed")
        
        assert isinstance(hw_error, OM1Error)
        assert isinstance(sensor_error, OM1Error)
        assert isinstance(action_error, OM1Error)
        assert isinstance(llm_error, OM1Error)


class TestErrorHandling:
    """Test suite for error handling utilities."""
    
    def test_handle_error_logging(self, caplog):
        """Test error handling logs correctly."""
        logger = get_om1_logger("test")
        
        with caplog.at_level(logging.WARNING):
            try:
                raise ValueError("Test error")
            except ValueError as e:
                handle_error(e, logger, context={"test": "context"})
        
        assert "Test error" in caplog.text
        assert "MEDIUM" in caplog.text
    
    def test_handle_error_with_om1_error(self, caplog):
        """Test handling of OM1Error preserves context."""
        logger = get_om1_logger("test")
        om1_error = OM1Error(
            "Custom error",
            severity=ErrorSeverity.HIGH,
            context={"original": "context"}
        )
        
        with caplog.at_level(logging.ERROR):
            handle_error(om1_error, logger, context={"additional": "data"})
        
        assert "Custom error" in caplog.text
        assert "HIGH" in caplog.text


class TestRetryDecorator:
    """Test suite for retry decorator."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_attempt(self):
        """Test function succeeds on first attempt."""
        call_count = 0
        
        @with_retry(max_attempts=3, delay=0.01)
        async def succeeds_immediately():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await succeeds_immediately()
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_success_after_failures(self):
        """Test function succeeds after transient failures."""
        call_count = 0
        
        @with_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def fails_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Transient error")
            return "success"
        
        result = await fails_twice()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_exhausts_attempts(self):
        """Test function fails after max attempts."""
        call_count = 0
        
        @with_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise ValueError("Permanent error")
        
        with pytest.raises(ValueError, match="Permanent error"):
            await always_fails()
        
        assert call_count == 3
    
    def test_retry_sync_function(self):
        """Test retry decorator with synchronous functions."""
        call_count = 0
        
        @with_retry(max_attempts=3, delay=0.01, exceptions=(ValueError,))
        def fails_once():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("Transient error")
            return "success"
        
        result = fails_once()
        assert result == "success"
        assert call_count == 2


class TestSafeExecution:
    """Test suite for safe execution wrappers."""
    
    def test_safe_execute_success(self):
        """Test safe_execute with successful function."""
        def succeeds():
            return 42
        
        result = safe_execute(succeeds)
        assert result == 42
    
    def test_safe_execute_with_error(self, caplog):
        """Test safe_execute returns default on error."""
        def fails():
            raise RuntimeError("Test error")
        
        with caplog.at_level(logging.WARNING):
            result = safe_execute(fails, default=None)
        
        assert result is None
        assert "Test error" in caplog.text
    
    @pytest.mark.asyncio
    async def test_safe_execute_async_success(self):
        """Test safe_execute_async with successful function."""
        async def succeeds():
            return 42
        
        result = await safe_execute_async(succeeds)
        assert result == 42
    
    @pytest.mark.asyncio
    async def test_safe_execute_async_with_error(self, caplog):
        """Test safe_execute_async returns default on error."""
        async def fails():
            raise RuntimeError("Test error")
        
        with caplog.at_level(logging.WARNING):
            result = await safe_execute_async(fails, default="fallback")
        
        assert result == "fallback"
        assert "Test error" in caplog.text


class TestLogger:
    """Test suite for logger utilities."""
    
    def test_get_om1_logger(self):
        """Test logger creation with OM1 naming."""
        logger = get_om1_logger("test_module")
        
        assert logger.name == "om1.test_module"
        assert len(logger.handlers) > 0
    
    def test_logger_singleton_behavior(self):
        """Test same logger instance is returned for same name."""
        logger1 = get_om1_logger("same_module")
        logger2 = get_om1_logger("same_module")
        
        assert logger1 is logger2
