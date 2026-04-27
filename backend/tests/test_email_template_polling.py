from __future__ import annotations

import io
import os
import tempfile
import unittest
import urllib.error
import urllib.parse
from unittest.mock import patch

from app import db as db_module
from app.models.email_template_change_event import (
    TEMPLATE_EVENT_ARCHIVED,
    TEMPLATE_EVENT_DELETED,
    TEMPLATE_EVENT_EDITED,
    TEMPLATE_EVENT_UNARCHIVED,
    EmailTemplateChangeEvent,
)
from app.models.email_template_snapshot import EmailTemplateSnapshot
from app.services import email_template_polling


_STUB_ACCESS_TOKEN = "test-access-token"


def _template_payload(
    template_id: str,
    *,
    name: str | None = None,
    archived: bool = False,
    subject: str = "Welcome",
    body_text: str = "Initial body",
) -> dict:
    return {
        "id": template_id,
        "name": name or f"Email {template_id}",
        "type": "AUTOMATED_EMAIL",
        "archived": archived,
        "subject": subject,
        "content": {
            "widgets": {
                "main": {
                    "body": {
                        "html": f"<p>{body_text}</p>",
                    }
                }
            }
        },
        "templatePath": "@hubspot/email/dnd/welcome.html",
    }


class EmailTemplatePollingTests(unittest.TestCase):
    PORTAL_ID = "8675309"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        self._database_url = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'template-polling-test.sqlite')}"
        )
        os.environ["DATABASE_URL"] = self._database_url
        db_module._engine = None
        db_module._SessionLocal = None
        db_module.init_db()

        self._token_patcher = patch.object(
            email_template_polling,
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

    def _all_events(self, session) -> list[EmailTemplateChangeEvent]:
        return (
            session.query(EmailTemplateChangeEvent)
            .filter(EmailTemplateChangeEvent.portal_id == self.PORTAL_ID)
            .order_by(EmailTemplateChangeEvent.id.asc())
            .all()
        )

    def _all_snapshots(self, session) -> list[EmailTemplateSnapshot]:
        return (
            session.query(EmailTemplateSnapshot)
            .filter(EmailTemplateSnapshot.portal_id == self.PORTAL_ID)
            .order_by(EmailTemplateSnapshot.template_id.asc())
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

    def test_fresh_portal_emits_no_change_events_for_baseline_templates(self) -> None:
        state = [_template_payload("101"), _template_payload("102", name="Nurture")]
        session = self._session()
        try:
            summary = email_template_polling.poll_portal_email_templates(
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
        active = [_template_payload("101", archived=False)]
        session = self._session()
        try:
            email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active),
            )
            active = []
            archived = [_template_payload("101", archived=True)]

            summary = email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active, archived),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["archivedEvents"])
            self.assertEqual(1, summary["events_emitted"])
            self.assertEqual([TEMPLATE_EVENT_ARCHIVED], [event.event_type for event in events])
        finally:
            session.close()

    def test_unarchive_flip_emits_unarchived_event_silent(self) -> None:
        active: list[dict] = []
        archived = [_template_payload("101", archived=True)]
        session = self._session()
        try:
            email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active, archived),
            )
            active = [_template_payload("101", archived=False)]
            archived = []

            summary = email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(active, archived),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["unarchivedEvents"])
            self.assertEqual([TEMPLATE_EVENT_UNARCHIVED], [event.event_type for event in events])
        finally:
            session.close()

    def test_definition_hash_change_emits_template_edited_event(self) -> None:
        state = [_template_payload("101", body_text="first")]
        session = self._session()
        try:
            email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )
            state = [_template_payload("101", body_text="second")]

            summary = email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["editedEvents"])
            self.assertEqual([TEMPLATE_EVENT_EDITED], [event.event_type for event in events])
        finally:
            session.close()

    def test_disappeared_template_emits_deleted_event(self) -> None:
        state = [_template_payload("101"), _template_payload("102")]
        session = self._session()
        try:
            email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )
            state = [_template_payload("101")]

            summary = email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )

            events = self._all_events(session)
            self.assertEqual(1, summary["deletedEvents"])
            self.assertEqual([TEMPLATE_EVENT_DELETED], [event.event_type for event in events])
            deleted = (
                session.query(EmailTemplateSnapshot)
                .filter(
                    EmailTemplateSnapshot.portal_id == self.PORTAL_ID,
                    EmailTemplateSnapshot.template_id == "102",
                )
                .one()
            )
            self.assertIsNotNone(deleted.deleted_at)
        finally:
            session.close()

    def test_idempotent_poll_emits_no_events(self) -> None:
        state = [_template_payload("101")]
        session = self._session()
        try:
            email_template_polling.poll_portal_email_templates(
                session,
                self.PORTAL_ID,
                self._make_fake_http(state),
            )
            summary = email_template_polling.poll_portal_email_templates(
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
            summary = email_template_polling.poll_portal_email_templates(
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
            summary = email_template_polling.poll_portal_email_templates(
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
