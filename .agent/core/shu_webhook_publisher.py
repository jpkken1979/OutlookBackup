"""ShuWebhookPublisher — Real-time webhook broadcast for /shu improvements.

Publishes improvement suggestions to registered webhook endpoints with:
- Automatic retries with exponential backoff
- Robust error handling (logs but does not block)
- Persistent subscriber management
- Full type hints and Google docstrings
"""

import json
import logging
from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests  # type: ignore[import-untyped]
from requests.adapters import HTTPAdapter  # type: ignore[import-untyped]
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


@dataclass
class WebhookPayload:
    """Payload structure for webhook notifications.

    Attributes:
        event: Event type identifier.
        suggestions: List of improvement suggestions.
        affected_templates: List of affected template names.
        timestamp: ISO8601 timestamp of the event.
        version: Webhook payload version for compatibility.
    """

    event: str
    suggestions: list[str]
    affected_templates: list[str]
    timestamp: str
    version: str = "1.0"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization.

        Returns:
            Dictionary representation of the payload.
        """
        return asdict(self)


class ShuWebhookPublisher:
    """Manages webhook subscriptions and broadcasts improvements.

    Handles subscriber persistence, HTTP delivery with retries, and
    error logging without blocking the main flow.
    """

    def __init__(self, subscribers_dir: Path | None = None) -> None:
        """Initialize the webhook publisher.

        Args:
            subscribers_dir: Directory for subscriber storage.
                Defaults to ~/.antigravity/shu/.
        """
        if subscribers_dir is None:
            subscribers_dir = Path.home() / ".antigravity" / "shu"
        self.subscribers_dir = Path(subscribers_dir)
        self.subscribers_file = self.subscribers_dir / "subscribers.json"
        self.history_file = self.subscribers_dir / "broadcast_history.json"

        # Ensure directory exists
        self.subscribers_dir.mkdir(parents=True, exist_ok=True)

        # Initialize subscribers list if missing
        if not self.subscribers_file.exists():
            self.subscribers_file.write_text(json.dumps([]))

        self._session = self._create_session()

    def _create_session(self) -> requests.Session:
        """Create HTTP session with automatic retries.

        Returns:
            Configured requests Session with exponential backoff.
        """
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _load_subscribers(self) -> list[str]:
        """Load subscriber URLs from storage.

        Returns:
            List of subscriber endpoint URLs.
        """
        try:
            content = self.subscribers_file.read_text()
            subscribers = json.loads(content)
            return [s for s in subscribers if isinstance(s, str)]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to load subscribers: {e}")
            return []

    def _save_subscribers(self, subscribers: list[str]) -> None:
        """Persist subscriber list to storage.

        Args:
            subscribers: List of subscriber URLs.
        """
        try:
            self.subscribers_file.write_text(json.dumps(subscribers, indent=2))
        except OSError as e:
            logger.error(f"Failed to save subscribers: {e}")

    def _validate_url(self, url: str) -> bool:
        """Validate webhook endpoint URL.

        Args:
            url: URL to validate.

        Returns:
            True if URL is valid HTTP(S), False otherwise.
        """
        try:
            parsed = urlparse(url)
            return parsed.scheme in ("http", "https") and bool(parsed.netloc)
        except Exception:
            return False

    def _append_history(self, entry: dict) -> None:
        """Append broadcast result to history file.

        Args:
            entry: Broadcast result entry.
        """
        try:
            history: list[dict] = []
            if self.history_file.exists():
                history = json.loads(self.history_file.read_text())
            history.append(entry)
            # Keep last 100 entries
            history = history[-100:]
            self.history_file.write_text(json.dumps(history, indent=2))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to append broadcast history: {e}")

    def subscribe(self, endpoint_url: str) -> bool:
        """Register a new webhook subscriber.

        Args:
            endpoint_url: HTTPS/HTTP endpoint URL.

        Returns:
            True if subscription was added, False if already exists or invalid.

        Raises:
            ValueError: If URL is not valid HTTP(S).
        """
        if not self._validate_url(endpoint_url):
            raise ValueError(f"Invalid webhook URL: {endpoint_url}")

        subscribers = self._load_subscribers()
        if endpoint_url in subscribers:
            logger.info(f"Subscriber already exists: {endpoint_url}")
            return False

        subscribers.append(endpoint_url)
        self._save_subscribers(subscribers)
        logger.info(f"Subscriber added: {endpoint_url}")
        return True

    def unsubscribe(self, endpoint_url: str) -> bool:
        """Unregister a webhook subscriber.

        Args:
            endpoint_url: Endpoint URL to remove.

        Returns:
            True if subscriber was removed, False if not found.
        """
        subscribers = self._load_subscribers()
        if endpoint_url not in subscribers:
            logger.warning(f"Subscriber not found: {endpoint_url}")
            return False

        subscribers.remove(endpoint_url)
        self._save_subscribers(subscribers)
        logger.info(f"Subscriber removed: {endpoint_url}")
        return True

    def list_subscribers(self) -> list[str]:
        """Get list of registered subscribers.

        Returns:
            List of subscriber endpoint URLs.
        """
        return self._load_subscribers()

    def publish_improvement(self, suggestions: list[str], affected_templates: list[str]) -> dict:
        """Broadcast improvement suggestions to all subscribers.

        Sends HTTP POST to each subscriber with automatic retries and
        error logging. Does not block on failures.

        Args:
            suggestions: List of improvement suggestion strings.
            affected_templates: List of affected template names.

        Returns:
            Dictionary with broadcast statistics:
            - broadcast_count: Total subscribers notified
            - successful: Number of successful deliveries
            - failed: Number of failed deliveries
            - errors: List of error details for failed endpoints
        """
        subscribers = self._load_subscribers()
        payload = WebhookPayload(
            event="shu_improvement_available",
            suggestions=suggestions,
            affected_templates=affected_templates,
            timestamp=datetime.now(UTC).isoformat(),
        )
        payload_dict = payload.to_dict()

        successful = 0
        failed = 0
        errors: list[dict] = []

        for endpoint in subscribers:
            try:
                response = self._session.post(
                    endpoint,
                    json=payload_dict,
                    timeout=5.0,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                successful += 1
                logger.debug(f"Webhook delivered to {endpoint}: {response.status_code}")
            except requests.exceptions.Timeout:
                failed += 1
                error_msg = f"Timeout: {endpoint}"
                logger.warning(error_msg)
                errors.append({"endpoint": endpoint, "error": "Timeout"})
            except requests.exceptions.ConnectionError as e:
                failed += 1
                error_msg = f"Connection error: {endpoint}: {e}"
                logger.warning(error_msg)
                errors.append({"endpoint": endpoint, "error": "Connection error"})
            except requests.exceptions.HTTPError as e:
                failed += 1
                error_msg = f"HTTP error: {endpoint}: {e}"
                logger.warning(error_msg)
                status = e.response.status_code if e.response is not None else "?"
                errors.append({"endpoint": endpoint, "error": f"HTTP {status}"})
            except Exception as e:
                failed += 1
                error_msg = f"Unexpected error: {endpoint}: {e}"
                logger.error(error_msg)
                errors.append({"endpoint": endpoint, "error": str(e)})

        result = {
            "broadcast_count": len(subscribers),
            "successful": successful,
            "failed": failed,
            "errors": errors,
            "timestamp": datetime.now(UTC).isoformat(),
        }

        self._append_history(result)
        logger.info(f"Broadcast complete: {successful}/{len(subscribers)} successful")

        return result

    def get_broadcast_history(self, limit: int = 10) -> list[dict]:
        """Retrieve recent broadcast history.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of recent broadcast results.
        """
        try:
            if not self.history_file.exists():
                return []
            history = json.loads(self.history_file.read_text())
            return history[-limit:]
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(f"Failed to read broadcast history: {e}")
            return []

    def get_health_status(self) -> str:
        """Determine webhook health status based on recent broadcasts.

        Returns:
            Health status: "healthy" (🟢), "degraded" (🟡), or "critical" (🔴).
        """
        history = self.get_broadcast_history(limit=5)
        if not history:
            return "unknown"

        failed_count = sum(1 for entry in history if entry.get("failed", 0) > 0)

        if failed_count == 0:
            return "healthy"
        elif failed_count <= 1:
            return "degraded"
        else:
            return "critical"
