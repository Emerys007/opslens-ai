from __future__ import annotations

import io
import os
import tempfile
import unittest
import urllib.error
from unittest.mock import patch

from app import db as db_module
from app.models.list_change_event import (
    LIST_EVENT_ARCHIVED,
    LIST_EVENT_CRITERIA_CHANGED,
    LIST_EVENT_DELETED,
    LIST_EVENT_UNARCHIVED,
    ListChangeEvent,
)
from app.models.list_snapshot import ListSnapshot
from app.services import list_polling


_STUB_ACCESS_TOKEN = "test-access-token"


def _list_payload(
    list_id: str,
    *,
    name: str | None = None,
    archived: bool = False,
    criteria_value: str = "initial",
) -> dict:
    return {
        "listId": list_id,
        "name": name or f"List {list_id}",
        "listType": "DYNAMIC",
        "processingType": "DYNAMIC",
        "archived": archived,
        "filterBranch": {
            "filters": [
                {
                    "property": "lifecyclestage",
                    "operator": "EQ",
                    "value": criteria_value,
                }
            ]
        },
    }


class ListPollingTests(unittest.TestCase):
    PORTAL_ID = "8675309"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'list-polling-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        self._token_patcher = patch.object(
            list_polling,
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

    def _all_events(self, session) -> list[ListChangeEvent]:
        return (
            session.query(ListChangeEvent)
            .filter(ListChangeEvent.portal_id == self.PORTAL_ID)
            .order_by(ListChangeEvent.id.asc())
            .all()
        )

    def _all_snapshots(self, session) -> list[ListSnapshot]:
        return (
            session.query(ListSnapshot)
            .filter(ListSnapshot.portal_id == self.PORTAL_ID)
            .order_by(ListSnapshot.list_id.asc())
            .all()
        )

    def _make_fake_http(self, state: list[dict]):
        def fake(_url: str, _token: str, _body: dict) -> dict:
            return {"results": list(state)}

        return fake

    def test_fresh_portal_emits_no_change_events_for_baseline_lists(self) -> None:
        state = [_list_payload("101"), _list_payload("102", name="Customers")]
        session = self._session()
        try:
            summary = list_polling.poll_portal_lists(
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

    def test_archive_flip_emits_archived_event(self) -> None:
        state = [_list_payload("101", archived=False)]
        session = self._session()
        try:
            list_polling.poll_portal_lists(session, self.PORTAL_ID, self._make_fake_http(state))
            state[0] = _list_payload("101", archived=True)

            summary = list_polling.poll_portal_lists(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["archivedEvents"])
            self.assertEqual(1, summary["events_emitted"])
            self.assertEqual([LIST_EVENT_ARCHIVED], [event.event_type for event in events])
        finally:
            session.close()

    def test_unarchive_flip_emits_unarchived_event_silent(self) -> None:
        state = [_list_payload("101", archived=True)]
        session = self._session()
        try:
            list_polling.poll_portal_lists(session, self.PORTAL_ID, self._make_fake_http(state))
            state[0] = _list_payload("101", archived=False)

            summary = list_polling.poll_portal_lists(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["unarchivedEvents"])
            self.assertEqual([LIST_EVENT_UNARCHIVED], [event.event_type for event in events])
        finally:
            session.close()

    def test_definition_hash_change_emits_criteria_changed_event(self) -> None:
        state = [_list_payload("101", criteria_value="subscriber")]
        session = self._session()
        try:
            list_polling.poll_portal_lists(session, self.PORTAL_ID, self._make_fake_http(state))
            state[0] = _list_payload("101", criteria_value="customer")

            summary = list_polling.poll_portal_lists(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["criteriaChangedEvents"])
            self.assertEqual(
                [LIST_EVENT_CRITERIA_CHANGED],
                [event.event_type for event in events],
            )
        finally:
            session.close()

    def test_disappeared_list_emits_deleted_event(self) -> None:
        state = [_list_payload("101"), _list_payload("102")]
        session = self._session()
        try:
            list_polling.poll_portal_lists(session, self.PORTAL_ID, self._make_fake_http(state))
            state = [_list_payload("101")]

            summary = list_polling.poll_portal_lists(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["deletedEvents"])
            self.assertEqual([LIST_EVENT_DELETED], [event.event_type for event in events])
            deleted = (
                session.query(ListSnapshot)
                .filter(
                    ListSnapshot.portal_id == self.PORTAL_ID,
                    ListSnapshot.list_id == "102",
                )
                .one()
            )
            self.assertIsNotNone(deleted.deleted_at)
        finally:
            session.close()

    def test_idempotent_poll_emits_no_events(self) -> None:
        state = [_list_payload("101")]
        session = self._session()
        try:
            list_polling.poll_portal_lists(session, self.PORTAL_ID, self._make_fake_http(state))
            summary = list_polling.poll_portal_lists(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            self.assertEqual(0, summary["events_emitted"])
            self.assertEqual([], self._all_events(session))
        finally:
            session.close()

    def test_401_skips_portal_gracefully(self) -> None:
        def fake_http(url: str, _token: str, _body: dict) -> dict:
            raise urllib.error.HTTPError(
                url=url,
                code=401,
                msg="Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        session = self._session()
        try:
            summary = list_polling.poll_portal_lists(session, self.PORTAL_ID, fake_http)

            self.assertEqual("skipped", summary["status"])
            self.assertEqual("hubspot_unauthorized", summary["reason"])
            self.assertEqual(0, summary["events_emitted"])
        finally:
            session.close()

    def test_429_aborts_portal_cycle(self) -> None:
        def fake_http(url: str, _token: str, _body: dict) -> dict:
            raise urllib.error.HTTPError(
                url=url,
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        session = self._session()
        try:
            summary = list_polling.poll_portal_lists(session, self.PORTAL_ID, fake_http)

            self.assertEqual("error", summary["status"])
            self.assertEqual("hubspot_rate_limited", summary["reason"])
            self.assertEqual(0, summary["events_emitted"])
        finally:
            session.close()


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
