# Error Handling Guide for OM1

This guide explains how to use the enhanced error handling utilities in the OM1 runtime for building robust and resilient robot applications.

## Overview

The `src/utils/error_handler.py` module provides:

- **Structured error types** for different failure scenarios
- **Automatic retry logic** with exponential backoff
- **Safe execution wrappers** for graceful degradation
- **Comprehensive logging** with context preservation

## Error Types

### Base Error Class

```python
from src.utils.error_handler import OM1Error, ErrorSeverity

# Create a custom error with context
error = OM1Error(
    message="Camera initialization failed",
    severity=ErrorSeverity.HIGH,
    context={"camera_id": "front_camera", "attempt": 3}
)
```

### Specialized Error Types

```python
from src.utils.error_handler import (
    HardwareConnectionError,  # Hardware/robot connection issues
    SensorError,              # Sensor input failures
    ActionExecutionError,     # Action execution problems
    LLMError                  # LLM API failures
)

# Example usage
raise HardwareConnectionError(
    "Failed to connect to robot",
    severity=ErrorSeverity.HIGH,
    context={"robot_ip": "192.168.1.100"}
)
```

## Retry Decorator

Use `@with_retry` for automatic retry logic on transient failures:

```python
from src.utils.error_handler import with_retry, HardwareConnectionError

@with_retry(
    max_attempts=5,
    delay=2.0,
    backoff=1.5,
    exceptions=(HardwareConnectionError, ConnectionError)
)
async def connect_to_robot(robot_ip: str):
    """
    Attempts to connect to robot with automatic retry.
    Will retry up to 5 times with exponential backoff.
    """
    # Connection logic here
    pass
```

### Parameters

- `max_attempts`: Maximum retry attempts (default: 3)
- `delay`: Initial delay between retries in seconds (default: 1.0)
- `backoff`: Multiplier for delay after each retry (default: 2.0)
- `exceptions`: Tuple of exception types to catch (default: (Exception,))
- `logger`: Optional logger instance

## Safe Execution

Use safe execution wrappers for non-critical operations where you want to continue on failure:

```python
from src.utils.error_handler import safe_execute, safe_execute_async

# Synchronous function
result = safe_execute(
    robot.get_battery_level,
    default=0.0,
    error_message="Failed to read battery level"
)

# Asynchronous function
face_expression = await safe_execute_async(
    robot.set_face,
    expression="happy",
    default="neutral",
    error_message="Failed to set face expression"
)
```

## Error Handling Best Practices

### 1. Use Appropriate Severity Levels

```python
from src.utils.error_handler import ErrorSeverity, handle_error, get_om1_logger

logger = get_om1_logger(__name__)

try:
    # Critical operation
    await robot.emergency_stop()
except Exception as e:
    handle_error(
        e, 
        logger, 
        severity=ErrorSeverity.FATAL,
        context={"operation": "emergency_stop"}
    )
```

### 2. Provide Rich Context

```python
try:
    await llm.generate_response(prompt)
except Exception as e:
    handle_error(
        e,
        logger,
        context={
            "model": "gpt-5-mini",
            "prompt_length": len(prompt),
            "timestamp": datetime.now().isoformat()
        }
    )
```

### 3. Combine Retry with Safe Execution

```python
@with_retry(max_attempts=3, exceptions=(SensorError,))
async def read_sensor_data(sensor_id: str):
    """Read sensor with automatic retry."""
    return await sensor.read(sensor_id)

# Use with safe execution for complete robustness
sensor_data = await safe_execute_async(
    read_sensor_data,
    sensor_id="lidar_front",
    default=None
)

if sensor_data is None:
    logger.warning("Using cached sensor data")
    sensor_data = get_cached_data()
```

## Integration Examples

### Example 1: Hardware Connection with Retry

```python
from src.utils.error_handler import with_retry, HardwareConnectionError, get_om1_logger

logger = get_om1_logger(__name__)

class RobotConnector:
    @with_retry(
        max_attempts=5,
        delay=3.0,
        exceptions=(HardwareConnectionError, ConnectionError),
        logger=logger
    )
    async def connect(self, robot_ip: str):
        """Connect to robot hardware with automatic retry."""
        try:
            # Your connection logic
            connection = await establish_connection(robot_ip)
            logger.info(f"Successfully connected to robot at {robot_ip}")
            return connection
        except ConnectionError as e:
            raise HardwareConnectionError(
                f"Connection to {robot_ip} failed",
                context={"robot_ip": robot_ip}
            ) from e
```

### Example 2: LLM with Graceful Degradation

```python
from src.utils.error_handler import safe_execute_async, LLMError, get_om1_logger

logger = get_om1_logger(__name__)

async def get_llm_response(prompt: str) -> str:
    """Get LLM response with fallback to cached responses."""
    
    async def call_llm():
        try:
            return await llm_client.generate(prompt)
        except Exception as e:
            raise LLMError(
                "LLM API call failed",
                context={"model": "gpt-5-mini", "prompt_preview": prompt[:100]}
            ) from e
    
    # Try LLM, fall back to cache on failure
    response = await safe_execute_async(
        call_llm,
        default=None,
        logger=logger
    )
    
    if response is None:
        logger.warning("LLM unavailable, using cached response")
        response = get_cached_response(prompt)
    
    return response
```

### Example 3: Sensor Input with Error Recovery

```python
from src.utils.error_handler import with_retry, safe_execute_async, SensorError

class CameraInput:
    def __init__(self):
        self.logger = get_om1_logger(__name__)
        self.last_valid_frame = None
    
    @with_retry(max_attempts=3, delay=0.5, exceptions=(SensorError,))
    async def capture_frame(self):
        """Capture camera frame with retry."""
        try:
            frame = await self.camera.read()
            if frame is None:
                raise SensorError("Camera returned null frame")
            self.last_valid_frame = frame
            return frame
        except Exception as e:
            raise SensorError(
                "Failed to capture frame",
                context={"camera_id": self.camera.id}
            ) from e
    
    async def get_frame(self):
        """Get frame with fallback to last valid frame."""
        frame = await safe_execute_async(
            self.capture_frame,
            default=None,
            logger=self.logger
        )
        
        if frame is None and self.last_valid_frame is not None:
            self.logger.warning("Using last valid frame")
            return self.last_valid_frame
        
        return frame
```

## Testing Error Handling

The module includes comprehensive tests in `tests/test_error_handler.py`:

```bash
# Run all error handler tests
pytest tests/test_error_handler.py -v

# Run specific test class
pytest tests/test_error_handler.py::TestRetryDecorator -v

# Run with coverage
pytest tests/test_error_handler.py --cov=src.utils.error_handler
```

## Migration Guide

To integrate error handling into existing OM1 code:

1. **Import the utilities:**
   ```python
   from src.utils.error_handler import (
       with_retry, safe_execute_async, 
       get_om1_logger, handle_error
   )
   ```

2. **Replace generic error handling:**
   ```python
   # Before
   try:
       result = await robot.move(x, y)
   except Exception as e:
       print(f"Error: {e}")
   
   # After
   result = await safe_execute_async(
       robot.move,
       x=x, y=y,
       default=False,
       logger=logger,
       error_message="Robot movement failed"
   )
   ```

3. **Add retry logic to critical operations:**
   ```python
   # Before
   async def connect():
       return await robot.connect()
   
   # After
   @with_retry(max_attempts=5, delay=2.0)
   async def connect():
       return await robot.connect()
   ```

## Contributing

When adding new error types or handling patterns:

1. Extend `OM1Error` for domain-specific errors
2. Add tests in `tests/test_error_handler.py`
3. Update this documentation with examples
4. Follow PEP 8 style guidelines

## Additional Resources

- [OM1 Documentation](https://docs.openmind.org/)
- [Python Exception Handling Best Practices](https://docs.python.org/3/tutorial/errors.html)
- [Asyncio Error Handling](https://docs.python.org/3/library/asyncio-exceptions.html)
