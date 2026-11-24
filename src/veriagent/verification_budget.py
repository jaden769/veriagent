"""Standalone logical verification admission; not wired into execution policies."""

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VerificationLimits:
    max_calls: int | None = None
    max_target_rows: int | None = None

    def __post_init__(self):
        for value in (self.max_calls, self.max_target_rows):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("Verification limits must be nonnegative integers or None")


@dataclass(frozen=True)
class VerificationReservation:
    target_rows: int


class VerificationBudgetExceeded(Exception):
    """Admission was denied before trusted verification work."""


class VerificationBudgetLedger:
    """One sequential run, one in-flight check, no refunds for attempted checks.

    Reservations bound logical calls and requested target rows only. The caller must
    reserve before invoking a verifier that reads at most those requested target rows.
    This does not bound database-internal work or enforce callers' tool authorization.
    """

    def __init__(self, limits: VerificationLimits):
        if not isinstance(limits, VerificationLimits):
            raise TypeError("Expected VerificationLimits")
        self.limits = limits
        self._calls = self._rows = self._completed = self._errors = self._known_rows = 0
        self._pending = None

    def reserve(self, target_rows: int) -> VerificationReservation:
        if type(target_rows) is not int or target_rows < 1:
            raise ValueError("Reserve a positive integer target-row count")
        if self._pending is not None:
            raise ValueError("A verification reservation is already pending")
        if self.limits.max_calls is not None and self._calls >= self.limits.max_calls:
            raise VerificationBudgetExceeded("verification_calls_exhausted")
        if (
            self.limits.max_target_rows is not None
            and self._rows + target_rows > self.limits.max_target_rows
        ):
            raise VerificationBudgetExceeded("verification_target_rows_exhausted")
        reservation = VerificationReservation(target_rows)
        self._calls += 1
        self._rows += target_rows
        self._pending = reservation
        return reservation

    def _check(self, reservation):
        if self._pending is None or reservation is not self._pending:
            raise ValueError("Unknown, stale or foreign verification reservation")

    def complete(self, reservation: VerificationReservation, *, observed_target_rows: int):
        self._check(reservation)
        if type(observed_target_rows) is not int or observed_target_rows != reservation.target_rows:
            raise ValueError("Completed verification must account for all reserved target rows")
        self._known_rows += observed_target_rows
        self._completed += 1
        self._pending = None

    def fail(self, reservation: VerificationReservation):
        self._check(reservation)
        self._errors += 1
        self._pending = None

    @property
    def state(self) -> dict:
        unknown = self._errors > 0 or self._pending is not None
        return {
            "schema_version": 1,
            "limits": asdict(self.limits),
            "reserved_calls": self._calls,
            "reserved_target_rows": self._rows,
            "completed_verification_calls": self._completed,
            "verification_errors": self._errors,
            "pending": self._pending is not None,
            "known_verified_target_rows": self._known_rows,
            "verified_target_rows": None if unknown else self._known_rows,
            "verification_work_complete": not unknown,
            "remaining_calls": None
            if self.limits.max_calls is None
            else self.limits.max_calls - self._calls,
            "remaining_target_rows": None
            if self.limits.max_target_rows is None
            else self.limits.max_target_rows - self._rows,
        }
