from __future__ import annotations

import io
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

from app import db as db_module
from app.models.owner_change_event import (
    OWNER_EVENT_DEACTIVATED,
    OWNER_EVENT_DELETED,
    OWNER_EVENT_REACTIVATED,
    OwnerChangeEvent,
)
from app.models.owner_snapshot import OwnerSnapshot
from app.services import owner_polling


_STUB_ACCESS_TOKEN = "test-access-token"


def _owner_payload(
    owner_id: str,
    *,
    email: str | None = None,
    archived: bool = False,
) -> dict:
    return {
        "id": owner_id,
        "email": email or f"owner-{owner_id}@example.com",
        "firstName": "Test",
        "lastName": "Owner",
        "archived": archived,
    }


class OwnerPollingTests(unittest.TestCase):
    PORTAL_ID = "8675309"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'owner-polling-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        self._token_patcher = patch.object(
            owner_polling,
            "get_portal_access_token",
            return_value=_STUB_ACCESS_TOKEN,
        )
        self._token_patcher.start()

    def tearDown(self) -> None:
        self._token_patcher.stop()
        if db_module._engine is not None:
            db_module._engine.dispose()
        db_module._engine = None
        db_module._SessionLocal = None
        os.environ.pop("DATABASE_URL", None)
        self._tempdir.cleanup()

    def _session(self):
        session = db_module.get_session()
        self.assertIsNotNone(session)
        return session

    def _all_events(self, session) -> list[OwnerChangeEvent]:
        return (
            session.query(OwnerChangeEvent)
            .filter(OwnerChangeEvent.portal_id == self.PORTAL_ID)
            .order_by(OwnerChangeEvent.id.asc())
            .all()
        )

    def _all_snapshots(self, session) -> list[OwnerSnapshot]:
        return (
            session.query(OwnerSnapshot)
            .filter(OwnerSnapshot.portal_id == self.PORTAL_ID)
            .order_by(OwnerSnapshot.owner_id.asc())
            .all()
        )

    def _make_fake_http(
        self,
        active_state: list[dict],
        archived_state: list[dict] | None = None,
    ):
        archived_state = archived_state or []

        def fake(url: str, _token: str) -> dict:
            params = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            archived = params.get("archived", ["false"])[0] == "true"
            return {
                "results": list(archived_state if archived else active_state),
            }

        return fake

    def test_fresh_portal_emits_no_change_events_for_baseline_owners(self) -> None:
        state = [_owner_payload("101"), _owner_payload("102")]
        session = self._session()
        try:
            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            self.assertEqual("ok", summary["status"])
            self.assertEqual(2, summary["polled"])
            self.assertEqual(0, summary["events_emitted"])
            self.assertEqual([], self._all_events(session))
            self.assertEqual(2, len(self._all_snapshots(session)))
        finally:
            session.close()

    def test_active_to_archived_emits_deactivated_event(self) -> None:
        active = [_owner_payload("101", archived=False)]
        session = self._session()
        try:
            owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active),
            )
            active = []
            archived = [_owner_payload("101", archived=True)]

            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active, archived),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["deactivatedEvents"])
            self.assertEqual(1, summary["events_emitted"])
            self.assertEqual([OWNER_EVENT_DEACTIVATED], [event.event_type for event in events])
        finally:
            session.close()

    def test_archived_to_active_emits_reactivated_event(self) -> None:
        active: list[dict] = []
        archived = [_owner_payload("101", archived=True)]
        session = self._session()
        try:
            owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active, archived),
            )
            active = [_owner_payload("101", archived=False)]
            archived = []

            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active, archived),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["reactivatedEvents"])
            self.assertEqual([OWNER_EVENT_REACTIVATED], [event.event_type for event in events])
        finally:
            session.close()

    def test_disappeared_owner_emits_deleted_event(self) -> None:
        state = [_owner_payload("101"), _owner_payload("102")]
        session = self._session()
        try:
            owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )
            state = [_owner_payload("101")]

            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["deletedEvents"])
            self.assertEqual([OWNER_EVENT_DELETED], [event.event_type for event in events])
            deleted = (
                session.query(OwnerSnapshot)
                .filter(
                    OwnerSnapshot.portal_id == self.PORTAL_ID,
                    OwnerSnapshot.owner_id == "102",
                )
                .one()
            )
            self.assertIsNotNone(deleted.deleted_at)
        finally:
            session.close()

    def test_idempotent_poll_emits_no_events(self) -> None:
        state = [_owner_payload("101")]
        session = self._session()
        try:
            owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )
            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            self.assertEqual(0, summary["events_emitted"])
            self.assertEqual([], self._all_events(session))
        finally:
            session.close()

    def test_401_skips_portal_gracefully(self) -> None:
        def fake_http(url: str, _token: str) -> dict:
            raise urllib.error.HTTPError(
                url=url,
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        session = self._session()
        try:
            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                fake_http,
            )

            self.assertEqual("skipped", summary["status"])
            self.assertEqual("hubspot_unauthorized", summary["reason"])
            self.assertEqual(0, summary["events_emitted"])
        finally:
            session.close()

    def test_429_aborts_portal_cycle(self) -> None:
        def fake_http(url: str, _token: str) -> dict:
            raise urllib.error.HTTPError(
                url=url,
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        session = self._session()
        try:
            summary = owner_polling.poll_portal_owners(
                session,
                self.PORTAL_ID,
                fake_http,
            )

            self.assertEqual("error", summary["status"])
            self.assertEqual("hubspot_rate_limited", summary["reason"])
            self.assertEqual(0, summary["events_emitted"])
        finally:
            session.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
