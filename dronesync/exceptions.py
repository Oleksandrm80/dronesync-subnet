"""
DroneSync - Custom Exceptions
"""


class DronesyncError(Exception):
    """Base exception for all DroneSync errors."""
    pass


class MissionValidationError(DronesyncError):
    """Invalid mission parameters."""
    pass


class TrajectoryError(DronesyncError):
    """Trajectory planning or validation failed."""
    pass


class SecurityViolationError(DronesyncError):
    """Security check failed — spoofing, hijacking, or invalid signature."""
    pass


class ReplayAttackError(DronesyncError):
    """Replay attack detected — mission already processed."""
    pass


class ConsensusError(DronesyncError):
    """Swarm consensus failed or Byzantine behavior detected."""
    pass


class PoPWError(DronesyncError):
    """PoPW record creation or verification failed."""
    pass


class StorageError(DronesyncError):
    """Persistent storage read/write error."""
    pass


class FirewallError(DronesyncError):
    """Command blocked by drone firewall."""
    pass


class WeatherError(DronesyncError):
    """Weather data unavailable or conditions unsafe."""
    pass
