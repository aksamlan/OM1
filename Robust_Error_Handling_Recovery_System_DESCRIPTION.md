# Add Robust Error Handling and Recovery System

## Problem Statement

The OM1 runtime currently lacks a centralized error handling system, which can lead to:

- **Inconsistent error logging** across different modules
- **Unclear failure modes** when hardware connections drop
- **No automatic recovery** from transient failures (network issues, sensor glitches)
- **Difficult debugging** due to lack of structured error context
- **Brittle integrations** that fail completely on first error

For a robotics platform that interfaces with physical hardware, sensors, and LLM APIs, robust error handling is critical for production reliability.

## Solution

This PR introduces a comprehensive error handling utility (`src/utils/error_handler.py`) that provides:

### 1. Structured Error Types
- Custom exception hierarchy (`OM1Error`, `HardwareConnectionError`, `SensorError`, etc.)
- Severity classification (LOW, MEDIUM, HIGH, FATAL)
- Rich context preservation for debugging

### 2. Automatic Retry Logic
- `@with_retry` decorator with exponential backoff
- Configurable retry attempts, delays, and exception types
- Works with both sync and async functions
- Comprehensive logging of retry attempts

### 3. Safe Execution Wrappers
- `safe_execute()` and `safe_execute_async()` for graceful degradation
- Default value fallback on failure
- Continue operation even when non-critical components fail

### 4. Enhanced Logging
- Structured logging with OM1-specific formatting
- Automatic context injection
- Error serialization for monitoring systems

## Code Quality

- **Type hints** throughout for better IDE support and type safety
- **Comprehensive docstrings** following Google style
- **Full test coverage** with pytest (17 unit tests covering all features)
- **PEP 8 compliant** code style
- **Documentation** included with practical examples and migration guide

## Use Cases

This error handling system is particularly valuable for:

1. **Hardware Connections**: Retry failed connections to ROS2, Zenoh, or robot APIs
2. **LLM API Calls**: Handle rate limits and temporary outages gracefully
3. **Sensor Input**: Recover from temporary sensor failures
4. **Action Execution**: Safely attempt physical movements with fallback behaviors
5. **Production Deployments**: Maintain uptime even when components fail

## Example Usage

### Before (without error handling):
```python
async def connect_to_robot(robot_ip):
    connection = await establish_connection(robot_ip)  # Fails immediately on any issue
    return connection
```

### After (with robust error handling):
```python
@with_retry(max_attempts=5, delay=2.0, exceptions=(ConnectionError,))
async def connect_to_robot(robot_ip):
    try:
        connection = await establish_connection(robot_ip)
        logger.info(f"Connected to robot at {robot_ip}")
        return connection
    except ConnectionError as e:
        raise HardwareConnectionError(
            f"Failed to connect to {robot_ip}",
            context={"robot_ip": robot_ip, "timestamp": datetime.now()}
        ) from e
```

## Testing

All functionality is fully tested:

```bash
pytest tests/test_error_handler.py -v
================================ test session starts =================================
tests/test_error_handler.py::TestOM1Error::test_om1_error_creation PASSED     [  5%]
tests/test_error_handler.py::TestOM1Error::test_om1_error_to_dict PASSED      [ 11%]
tests/test_error_handler.py::TestRetryDecorator::test_retry_success PASSED    [ 17%]
... (14 more tests)
================================ 17 passed in 0.42s =================================
```

## Integration

This PR is designed for easy adoption:

- **Non-breaking**: Can be integrated gradually without modifying existing code
- **Optional**: Modules can adopt error handling incrementally
- **Extensible**: Easy to add domain-specific error types
- **Zero dependencies**: Uses only Python standard library

## Files Changed

- `src/utils/error_handler.py` - Main error handling module (329 lines)
- `tests/test_error_handler.py` - Comprehensive test suite (251 lines)
- `docs/error-handling-guide.md` - Complete documentation with examples (338 lines)
- `Robust_Error_Handling_Recovery_System_DESCRIPTION.md` - This file

## Benefits for OM1

1. **Production Readiness**: Robots can recover from transient failures automatically
2. **Better Debugging**: Structured error logs with full context
3. **Code Quality**: Encourages proper error handling patterns across the codebase
4. **Maintainability**: Centralized error handling logic reduces duplication
5. **Extensibility**: Easy framework for adding new error types as OM1 grows

## Related Issues

This PR addresses aspects of:
- #632 - Real-Time Error Monitoring and Auto-Recovery System
- General robustness improvements for production OM1 deployments

---

I'm excited to contribute to OM1's robustness and would love to discuss any improvements or modifications to this approach. Thank you for considering this contribution!
