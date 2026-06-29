from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import timedelta

from app import db as db_module
from app.models.scheduler_lease import SchedulerLease
from app.services.scheduler_lease import _utc_now, try_acquire_lease
from app.services.workflow_polling_scheduler import run_polling_cycle

LEASE = "polling_cycle"


class _LeaseBase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'lease.sqlite')}"
        )
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

    def tearDown(self) -> None:
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        self._tempdir.cleanup()

    def _session(self):
        s = db_module.get_session()
        self.assertIsNotNone(s)
        return s


class SchedulerLeaseTests(_LeaseBase):
    def test_acquire_on_empty_table(self) -> None:
        s = self._session()
        try:
            self.assertTrue(try_acquire_lease(s, LEASE, "A", 120))
        finally:
            s.close()

    def test_second_holder_blocked_while_valid(self) -> None:
        s = self._session()
        try:
            self.assertTrue(try_acquire_lease(s, LEASE, "A", 120))
            self.assertFalse(try_acquire_lease(s, LEASE, "B", 120))
        finally:
            s.close()

    def test_same_holder_renews(self) -> None:
        s = self._session()
        try:
            self.assertTrue(try_acquire_lease(s, LEASE, "A", 120))
            self.assertTrue(try_acquire_lease(s, LEASE, "A", 120))
        finally:
            s.close()

    def test_expired_lease_is_taken_over(self) -> None:
        s = self._session()
        try:
            self.assertTrue(try_acquire_lease(s, LEASE, "A", 120))
            row = s.get(SchedulerLease, LEASE)
            row.expires_at = _utc_now() - timedelta(seconds=10)
            s.commit()
            # B takes the expired lease; A is now blocked.
            self.assertTrue(try_acquire_lease(s, LEASE, "B", 120))
            self.assertFalse(try_acquire_lease(s, LEASE, "A", 120))
        finally:
            s.close()


class RunPollingCycleOffloadTests(_LeaseBase):
    def test_async_wrapper_returns_summary(self) -> None:
        # No active installations -> a fast, no-op cycle, run in a worker thread.
        result = asyncio.run(run_polling_cycle(db_module.get_session))
        self.assertIsInstance(result, dict)
        self.assertEqual("ok", result.get("status"))
        self.assertEqual(0, result.get("portalsAttempted"))


if __name__ == "__main__":
    unittest.main()
