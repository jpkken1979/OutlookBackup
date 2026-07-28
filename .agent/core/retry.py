"""Utilidad centralizada de retry con exponential backoff y jitter.

Reemplaza las implementaciones ad-hoc de reintentos en el ecosistema con
un decorador ``@with_retry`` y una funcion ``retry_call()`` inline.

Uso::

    from core.retry import with_retry, retry_call

    @with_retry(max_retries=3, base_delay=1.0)
    async def fetch(url: str) -> dict: ...

    result = await retry_call(fetch, args=("https://...",), max_retries=3)
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
import random
import time
from collections.abc import Callable
from typing import Any, ParamSpec, TypeVar

logger = logging.getLogger(__name__)
P = ParamSpec("P")
T = TypeVar("T")

_MAX_RETRIES: int = 3
_BASE_DELAY: float = 1.0
_MAX_DELAY: float = 30.0
_RETRYABLE: tuple[type[BaseException], ...] = (Exception,)


def _delay(attempt: int, base: float, cap: float) -> float:
    """Calcula retraso con exponential backoff y full-jitter."""
    return random.uniform(0, min(base * (2**attempt), cap))


def _warn(name: str, attempt: int, total: int, exc: BaseException, d: float) -> None:
    logger.warning("Retry %d/%d for %s: %s — %.2fs", attempt + 1, total, name, exc, d)


def _fail(name: str, total: int, exc: BaseException) -> None:
    logger.error("All %d attempts exhausted for %s: %s", total, name, exc)


def _next_delay(
    name: str,
    attempt: int,
    total: int,
    max_retries: int,
    exc: BaseException,
    base_delay: float,
    max_delay: float,
) -> float | None:
    """Decide el retraso del proximo intento o senala agotamiento.

    Encapsula el if/else compartido por los wrappers sync/async: si quedan
    reintentos, calcula el backoff, loguea el warning y devuelve el delay;
    si se agotaron, loguea el fallo final y devuelve ``None``.

    Args:
        name: Nombre cualificado de la funcion reintentada.
        attempt: Indice del intento actual (0-based).
        total: Cantidad total de intentos permitidos.
        max_retries: Numero maximo de reintentos.
        exc: Excepcion capturada en el intento actual.
        base_delay: Retraso base en segundos.
        max_delay: Retraso maximo en segundos.

    Returns:
        El retraso en segundos a esperar antes de reintentar, o ``None`` si
        no quedan intentos.
    """
    if attempt < max_retries:
        d = _delay(attempt, base_delay, max_delay)
        _warn(name, attempt, total, exc, d)
        return d
    _fail(name, total, exc)
    return None


def _make_async_wrapper(
    func: Callable[P, T],
    total: int,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    retryable_exceptions: tuple[type[BaseException], ...],
) -> Callable[P, T]:
    """Construye el wrapper async con logica de reintento.

    Args:
        func: Corutina a envolver.
        total: Cantidad total de intentos permitidos.
        max_retries: Numero maximo de reintentos.
        base_delay: Retraso base en segundos.
        max_delay: Retraso maximo en segundos.
        retryable_exceptions: Excepciones que activan reintento.

    Returns:
        El wrapper async que aplica el reintento.
    """

    @functools.wraps(func)
    async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        last: BaseException | None = None
        for i in range(total):
            try:
                return await func(*args, **kwargs)  # type: ignore[misc]  # ParamSpec limitation
            except retryable_exceptions as exc:
                last = exc
                d = _next_delay(
                    func.__qualname__, i, total, max_retries, exc, base_delay, max_delay
                )
                if d is not None:
                    await asyncio.sleep(d)
        raise last  # type: ignore[misc]  # guaranteed non-None after loop

    return async_wrapper  # type: ignore[return-value]  # wrapper matches func signature


def _make_sync_wrapper(
    func: Callable[P, T],
    total: int,
    max_retries: int,
    base_delay: float,
    max_delay: float,
    retryable_exceptions: tuple[type[BaseException], ...],
) -> Callable[P, T]:
    """Construye el wrapper sync con logica de reintento.

    Args:
        func: Funcion sincrona a envolver.
        total: Cantidad total de intentos permitidos.
        max_retries: Numero maximo de reintentos.
        base_delay: Retraso base en segundos.
        max_delay: Retraso maximo en segundos.
        retryable_exceptions: Excepciones que activan reintento.

    Returns:
        El wrapper sincrono que aplica el reintento.
    """

    @functools.wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
        last: BaseException | None = None
        for i in range(total):
            try:
                return func(*args, **kwargs)
            except retryable_exceptions as exc:
                last = exc
                d = _next_delay(
                    func.__qualname__, i, total, max_retries, exc, base_delay, max_delay
                )
                if d is not None:
                    time.sleep(d)
        raise last  # type: ignore[misc]  # guaranteed non-None after loop

    return sync_wrapper  # type: ignore[return-value]  # wrapper matches func signature


def with_retry(
    fn: Callable[P, T] | None = None,
    /,
    *,
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BASE_DELAY,
    max_delay: float = _MAX_DELAY,
    retryable_exceptions: tuple[type[BaseException], ...] = _RETRYABLE,
) -> Callable[P, T] | Callable[[Callable[P, T]], Callable[P, T]]:
    """Decorador de reintentos para funciones sync y async.

    Uso con o sin argumentos: ``@with_retry`` o ``@with_retry(max_retries=5)``.

    Args:
        fn: Funcion a decorar (uso sin parentesis).
        max_retries: Numero maximo de reintentos.
        base_delay: Retraso base en segundos.
        max_delay: Retraso maximo en segundos.
        retryable_exceptions: Excepciones que activan reintento.

    Returns:
        Funcion decorada con logica de reintento.
    """
    total = max_retries + 1

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        if inspect.iscoroutinefunction(func):
            # iscoroutinefunction narrows func a Callable[P, Coroutine] via TypeGuard,
            # incompatible con el Callable[P, T] de _make_async_wrapper a ojos de mypy.
            return _make_async_wrapper(
                func,  # type: ignore[arg-type]
                total,
                max_retries,
                base_delay,
                max_delay,
                retryable_exceptions,
            )
        return _make_sync_wrapper(
            func, total, max_retries, base_delay, max_delay, retryable_exceptions
        )

    if fn is not None:
        return decorator(fn)
    return decorator  # type: ignore[return-value]  # overloaded decorator pattern


async def retry_call(
    fn: Callable[..., Any],
    *,
    args: tuple[Any, ...] = (),
    kwargs: dict[str, Any] | None = None,
    max_retries: int = _MAX_RETRIES,
    base_delay: float = _BASE_DELAY,
    max_delay: float = _MAX_DELAY,
    retryable_exceptions: tuple[type[BaseException], ...] = _RETRYABLE,
) -> Any:
    """Ejecuta una funcion (sync o async) con reintentos de forma inline.

    Args:
        fn: Funcion a ejecutar.
        args: Argumentos posicionales.
        kwargs: Argumentos con nombre.
        max_retries: Numero maximo de reintentos.
        base_delay: Retraso base en segundos.
        max_delay: Retraso maximo en segundos.
        retryable_exceptions: Excepciones que activan reintento.

    Returns:
        El resultado de ``fn(*args, **kwargs)``.

    Raises:
        La ultima excepcion si se agotan todos los intentos.
    """
    kw = kwargs or {}
    is_coro = inspect.iscoroutinefunction(fn)
    last: BaseException | None = None
    total = max_retries + 1
    for i in range(total):
        try:
            return (await fn(*args, **kw)) if is_coro else fn(*args, **kw)
        except retryable_exceptions as exc:
            last = exc
            if i < max_retries:
                d = _delay(i, base_delay, max_delay)
                _warn(fn.__qualname__, i, total, exc, d)
                await asyncio.sleep(d)
            else:
                _fail(fn.__qualname__, total, exc)
    raise last  # type: ignore[misc]  # guaranteed non-None after loop
