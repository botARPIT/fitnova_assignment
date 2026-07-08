"""Shared async retry helper with exponential backoff and jitter."""

import asyncio
import logging
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

log = logging.getLogger("fitnova.retry")

T = TypeVar("T")


async def retry_async(
    operation: Callable[..., Awaitable[T]],
    is_retryable: Callable[[Exception], bool],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    jitter: float = 0.2,
    **log_context: str,
) -> T:
    """Execute an async operation with exponential backoff and retry.

    Args:
        operation: Async callable to invoke.
        is_retryable: Callable that returns True if the exception should be retried.
        max_attempts: Maximum number of attempts (including the first).
        base_delay: Base delay in seconds before the first retry.
        jitter: Max random jitter to add/subtract from delay (± fraction).
        **log_context: Key-value pairs included in every log message.

    Returns:
        The result of the operation.

    Raises:
        The final exception after all retries are exhausted.
    """
    last_exc: Exception | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except Exception as e:
            last_exc = e

            if not is_retryable(e):
                log.warning(
                    "Non-retryable exception — failing immediately",
                    extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_reason": type(e).__name__,
                        **log_context,
                    },
                )
                raise

            if attempt == max_attempts:
                log.error(
                    "Retry exhaustion — all attempts failed",
                    extra={
                        "attempt": attempt,
                        "max_attempts": max_attempts,
                        "retry_reason": type(e).__name__,
                        **log_context,
                    },
                )
                raise

            delay = base_delay * (2 ** (attempt - 1))
            if jitter > 0:
                delay += random.uniform(-jitter * delay, jitter * delay)
                delay = max(0.0, delay)

            log.info(
                "Retrying after transient failure",
                extra={
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "retry_reason": type(e).__name__,
                    "delay_ms": int(delay * 1000),
                    **log_context,
                },
            )
            await asyncio.sleep(delay)

    # Should never reach here — last attempt always raises
    raise last_exc  # type: ignore[misc]
