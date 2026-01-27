"""Event bus implementing pub/sub pattern functionally."""
from typing import Callable, Dict, List, Any
from collections import defaultdict
import threading
import logging

logger = logging.getLogger(__name__)

EventHandler = Callable[[Any], None]


def create_event_bus():
    """
    Create an event bus using closures for encapsulation.
    Returns a tuple of (subscribe, emit, unsubscribe) functions.
    """
    subscribers: Dict[str, List[EventHandler]] = defaultdict(list)
    lock = threading.Lock()

    def subscribe(event_type: str, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to an event type. Returns unsubscribe function."""
        with lock:
            subscribers[event_type].append(handler)

        def unsubscribe():
            with lock:
                if handler in subscribers[event_type]:
                    subscribers[event_type].remove(handler)

        return unsubscribe

    def emit(event_type: str, payload: Any = None) -> None:
        """Emit an event to all subscribers."""
        with lock:
            handlers = subscribers[event_type].copy()

        for handler in handlers:
            try:
                handler(payload)
            except Exception as e:
                logger.error(f"Handler error for {event_type}: {e}")

    def get_subscriber_count(event_type: str) -> int:
        """Get number of subscribers for event type."""
        with lock:
            return len(subscribers[event_type])

    return subscribe, emit, get_subscriber_count


class EventBus:
    """Alternative class-based event bus for easier testing."""

    def __init__(self):
        self._subscribe, self._emit, self._count = create_event_bus()

    def on(self, event_type: str, handler: EventHandler) -> Callable[[], None]:
        """Subscribe to event type."""
        return self._subscribe(event_type, handler)

    def emit(self, event_type: str, payload: Any = None) -> None:
        """Emit event."""
        self._emit(event_type, payload)

    def subscriber_count(self, event_type: str) -> int:
        """Get subscriber count."""
        return self._count(event_type)
