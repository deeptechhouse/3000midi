"""Custom exceptions for sync bridge."""


class SyncDeviceError(Exception):
    """Exception for sync device errors."""

    def __init__(self, device_name: str, message: str, recoverable: bool = True):
        self.device_name = device_name
        self.message = message
        self.recoverable = recoverable
        super().__init__(f"[{device_name}] {message}")


class ConfigurationError(Exception):
    """Exception for configuration errors."""
    pass


class ProtocolError(Exception):
    """Exception for protocol parsing errors."""
    pass
