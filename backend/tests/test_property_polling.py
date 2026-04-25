"""Tests for `app.services.property_polling.poll_portal_properties`.

Covers:

1. Fresh portal across 4 object types, 5 properties each → 20 ``created`` events.
2. Polling again with no underlying changes → 0 events, ``last_seen_at`` refreshed.
3. Property archived (``archived: false → true``) → 1 ``archived`` event.
4. Property unarchived → 1 ``unarchived`` event.
5. Property type changed → 1 ``type_changed`` event with old / new types.
6. Property label renamed (same internal name, new label) → 1 ``renamed`` event.
7. Property no longer in the API response (hard delete) → 1 ``deleted`` event.
8. HubSpot 401 on one object type → that type skipped, others poll normally,
   error recorded in ``summary["errors"]``.
9. HubSpot 429 on the first object type → poll aborts; remaining types are
   not polled (rate-limit on one endpoint usually means the rest will fail
   too — documented in the deliverable).
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from unittest.mock import patch
from urllib.parse import urlsplit

from app import db as db_module
from app.models.hubspot_installation import HubSpotInstallation
from app.models.property_change_event import (
    PROPERTY_EVENT_ARCHIVED,
    PROPERTY_EVENT_CREATED,
    PROPERTY_EVENT_DELETED,
    PROPERTY_EVENT_RENAMED,
    PROPERTY_EVENT_TYPE_CHANGED,
    PROPERTY_EVENT_UNARCHIVED,
    PropertyChangeEvent,
)
from app.models.property_snapshot import PropertySnapshot
from app.services import property_polling


_STUB_ACCESS_TOKEN = "test-access-token"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# Map HubSpot path segment → object_type_id (matches DEFAULT_OBJECT_TYPES).
PATH_TO_OBJECT_TYPE_ID = {
    "contacts": "0-1",
    "companies": "0-2",
    "deals": "0-3",
    "tickets": "0-5",
}


def _object_type_path_from_url(url: str) -> str:
    """Extract the path-segment object type (``contacts``, ``companies``,
    etc.) from a properties URL.
    """
    path = urlsplit(url).path
    # Path looks like /crm/v3/properties/{object_type}
    parts = [p for p in path.split("/") if p]
    if len(parts) >= 4 and parts[0] == "crm" and parts[2] == "properties":
        return parts[3]
    raise AssertionError(f"unexpected URL in test: {url}")


def _property_payload(
    name: str,
    *,
    label: str | None = None,
    type_: str = "string",
    field_type: str = "text",
    archived: bool = False,
) -> dict:
    return {
        "name": name,
        "label": label or name.replace("_", " ").title(),
        "type": type_,
        "fieldType": field_type,
        "description": f"Description for {name}",
        "archived": archived,
        "calculated": False,
        "displayOrder": 0,
        "groupName": "default",
        "createdAt": "2024-06-01T12:00:00.000Z",
        "updatedAt": "2026-04-01T12:00:00.000Z",
    }


def _list_response(properties: list[dict]) -> dict:
    return {"results": properties}


class PropertyPollingTests(unittest.TestCase):
    PORTAL_ID = "8675309"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'property-polling-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        session = db_module.get_session()
        assert session is not None
        try:
            session.add(
                HubSpotInstallation(
                    portal_id=self.PORTAL_ID,
                    access_token="seeded-access-token",
                    refresh_token="seeded-refresh-token",
                    is_active=True,
                )
            )
            session.commit()
        finally:
            session.close()

        # Bypass the SQLite tz-stripping path in get_portal_access_token.
        self._token_patcher = patch.object(
            property_polling,
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

    def _all_events(self, session) -> list[PropertyChangeEvent]:
        return (
            session.query(PropertyChangeEvent)
            .filter(PropertyChangeEvent.portal_id == self.PORTAL_ID)
            .order_by(PropertyChangeEvent.id.asc())
            .all()
        )

    def _all_snapshots(self, session) -> list[PropertySnapshot]:
        return (
            session.query(PropertySnapshot)
            .filter(PropertySnapshot.portal_id == self.PORTAL_ID)
            .order_by(
                PropertySnapshot.object_type_id.asc(),
                PropertySnapshot.property_name.asc(),
            )
            .all()
        )

    def _make_fake_http(self, state: dict[str, list[dict]]):
        """state: {"contacts": [...props...], "companies": [...], ...}.

        Mocks the JSON-fetch boundary so each object type's payload
        comes from the dict above.
        """

        def fake(url: str, _token: str) -> dict:
            object_type = _object_type_path_from_url(url)
            return _list_response(state.get(object_type, []))

        return fake

    # ------------------------------------------------------------------
    # 1. Fresh portal: 20 created events
    # ------------------------------------------------------------------

    def test_fresh_portal_emits_created_events_for_every_property(self) -> None:
        state = {
            object_type_path: [_property_payload(f"prop_{i}") for i in range(5)]
            for object_type_path in ("contacts", "companies", "deals", "tickets")
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual("ok", summary["status"])
        self.assertEqual(20, summary["polled"])
        self.assertEqual(20, summary["createdEvents"])
        self.assertEqual(0, summary["archivedEvents"])
        self.assertEqual(0, summary["deletedEvents"])

        session = self._session()
        try:
            events = self._all_events(session)
            self.assertEqual(20, len(events))
            self.assertEqual(
                {PROPERTY_EVENT_CREATED}, {event.event_type for event in events}
            )

            snapshots = self._all_snapshots(session)
            self.assertEqual(20, len(snapshots))
            object_types = {snap.object_type_id for snap in snapshots}
            self.assertEqual({"0-1", "0-2", "0-3", "0-5"}, object_types)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 2. Idempotent poll
    # ------------------------------------------------------------------

    def test_idempotent_poll_emits_no_events(self) -> None:
        state = {
            "contacts": [_property_payload("firstname"), _property_payload("email")],
            "companies": [],
            "deals": [],
            "tickets": [],
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

            session = self._session()
            try:
                before_seen_at = {
                    (s.object_type_id, s.property_name): s.last_seen_at
                    for s in self._all_snapshots(session)
                }
            finally:
                session.close()

            import time
            time.sleep(0.05)

            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        for key in ("createdEvents", "archivedEvents", "unarchivedEvents",
                    "typeChangedEvents", "renamedEvents", "deletedEvents"):
            self.assertEqual(0, summary[key], msg=f"{key} should be 0")

        session = self._session()
        try:
            events = self._all_events(session)
            self.assertEqual(2, len(events))  # only the originals

            after_seen_at = {
                (s.object_type_id, s.property_name): s.last_seen_at
                for s in self._all_snapshots(session)
            }
            for key, before in before_seen_at.items():
                self.assertGreaterEqual(after_seen_at[key], before)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 3. Archive flip
    # ------------------------------------------------------------------

    def test_archive_flip_emits_archived_event(self) -> None:
        state = {
            "contacts": [_property_payload("firstname", archived=False)],
            "companies": [],
            "deals": [],
            "tickets": [],
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

            state["contacts"] = [_property_payload("firstname", archived=True)]

            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["archivedEvents"])
        self.assertEqual(0, summary["unarchivedEvents"])

        session = self._session()
        try:
            archived_events = [
                e for e in self._all_events(session)
                if e.event_type == PROPERTY_EVENT_ARCHIVED
            ]
            self.assertEqual(1, len(archived_events))
            event = archived_events[0]
            self.assertEqual("firstname", event.property_name)
            self.assertEqual("0-1", event.object_type_id)
            self.assertFalse(event.previous_archived)
            self.assertTrue(event.new_archived)

            snapshot = (
                session.query(PropertySnapshot)
                .filter(
                    PropertySnapshot.portal_id == self.PORTAL_ID,
                    PropertySnapshot.object_type_id == "0-1",
                    PropertySnapshot.property_name == "firstname",
                )
                .one()
            )
            self.assertTrue(snapshot.archived)
        finally:
            session.close()

    def test_unarchive_flip_emits_unarchived_event(self) -> None:
        state = {
            "contacts": [_property_payload("firstname", archived=True)],
            "companies": [],
            "deals": [],
            "tickets": [],
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

            state["contacts"] = [_property_payload("firstname", archived=False)]

            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["unarchivedEvents"])
        self.assertEqual(0, summary["archivedEvents"])

    # ------------------------------------------------------------------
    # 4. Type change
    # ------------------------------------------------------------------

    def test_type_change_emits_type_changed_event(self) -> None:
        state = {
            "contacts": [_property_payload("score", type_="number")],
            "companies": [],
            "deals": [],
            "tickets": [],
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

            state["contacts"] = [_property_payload("score", type_="string")]

            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["typeChangedEvents"])

        session = self._session()
        try:
            type_events = [
                e for e in self._all_events(session)
                if e.event_type == PROPERTY_EVENT_TYPE_CHANGED
            ]
            self.assertEqual(1, len(type_events))
            self.assertEqual("number", type_events[0].previous_type)
            self.assertEqual("string", type_events[0].new_type)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 5. Label rename
    # ------------------------------------------------------------------

    def test_label_rename_emits_renamed_event(self) -> None:
        state = {
            "contacts": [_property_payload("score", label="Lead Score")],
            "companies": [],
            "deals": [],
            "tickets": [],
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

            state["contacts"] = [_property_payload("score", label="Engagement Score")]

            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["renamedEvents"])

        session = self._session()
        try:
            rename_events = [
                e for e in self._all_events(session)
                if e.event_type == PROPERTY_EVENT_RENAMED
            ]
            self.assertEqual(1, len(rename_events))
            self.assertEqual("Lead Score", rename_events[0].previous_label)
            self.assertEqual("Engagement Score", rename_events[0].new_label)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 6. Hard delete
    # ------------------------------------------------------------------

    def test_property_disappears_emits_deleted_event(self) -> None:
        state = {
            "contacts": [
                _property_payload("firstname"),
                _property_payload("email"),
            ],
            "companies": [],
            "deals": [],
            "tickets": [],
        }

        with patch.object(
            property_polling, "_http_get_json", side_effect=self._make_fake_http(state)
        ):
            session = self._session()
            try:
                property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

            # ``email`` disappears on the next poll without first being
            # archived — simulates a hard delete.
            state["contacts"] = [_property_payload("firstname")]

            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual(1, summary["deletedEvents"])

        session = self._session()
        try:
            deleted_events = [
                e for e in self._all_events(session)
                if e.event_type == PROPERTY_EVENT_DELETED
            ]
            self.assertEqual(1, len(deleted_events))
            self.assertEqual("email", deleted_events[0].property_name)

            snapshot = (
                session.query(PropertySnapshot)
                .filter(
                    PropertySnapshot.portal_id == self.PORTAL_ID,
                    PropertySnapshot.property_name == "email",
                )
                .one()
            )
            self.assertIsNotNone(snapshot.deleted_at)
        finally:
            session.close()

    # ------------------------------------------------------------------
    # 7. HubSpot 401 on one object type — partial failure
    # ------------------------------------------------------------------

    def test_401_on_one_object_type_records_error_and_polls_others(self) -> None:
        contacts_props = [_property_payload("firstname")]

        def fake_http_get_json(url: str, _token: str) -> dict:
            object_type = _object_type_path_from_url(url)
            if object_type == "companies":
                raise urllib.error.HTTPError(
                    url=url, code=401, msg="Unauthorized", hdrs=None,
                    fp=io.BytesIO(b'{"status":"error"}'),
                )
            if object_type == "contacts":
                return _list_response(contacts_props)
            return _list_response([])

        with patch.object(
            property_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        # The cycle did not abort: contacts was polled successfully.
        self.assertEqual("partial", summary["status"])
        self.assertEqual(1, summary["polled"])
        self.assertEqual(1, summary["createdEvents"])

        errors = summary["errors"]
        self.assertTrue(any(e["objectType"] == "companies" for e in errors))
        self.assertTrue(
            any(e["reason"] == "hubspot_unauthorized" for e in errors),
            f"errors did not contain unauthorized reason: {errors}",
        )

    # ------------------------------------------------------------------
    # 8. HubSpot 429 — abort the portal cycle
    # ------------------------------------------------------------------

    def test_429_aborts_portal_cycle(self) -> None:
        def fake_http_get_json(url: str, _token: str) -> dict:
            raise urllib.error.HTTPError(
                url=url, code=429, msg="Too Many Requests", hdrs=None,
                fp=io.BytesIO(b'{"status":"error"}'),
            )

        with patch.object(
            property_polling, "_http_get_json", side_effect=fake_http_get_json
        ):
            session = self._session()
            try:
                summary = property_polling.poll_portal_properties(session, self.PORTAL_ID)
            finally:
                session.close()

        self.assertEqual("error", summary["status"])
        self.assertEqual("hubspot_rate_limited", summary.get("reason"))
        self.assertEqual(0, summary["createdEvents"])

        # Only the first object type's error should be recorded —
        # subsequent types are not polled after a 429.
        self.assertEqual(1, len(summary["errors"]))


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
