from __future__ import annotations

import os
import tempfile
import unittest

from app import db as db_module
from app.models.portal_entitlement import PortalEntitlement
from app.models.portal_setting import PortalSetting
from app.services.portal_settings import load_portal_settings, save_portal_settings
from app.services.slack_delivery import _resolve_brand_name


class WhiteLabelTests(unittest.TestCase):
    PORTAL_ID = "51300126"

    def setUp(self) -> None:
        self._tempdir = tempfile.TemporaryDirectory()
        os.environ["DATABASE_URL"] = (
            f"sqlite:///{os.path.join(self._tempdir.name, 'white-label.sqlite')}"
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

    def _seed(self, *, white_label: str = "", plan: str = "agency") -> None:
        session = db_module.get_session()
        try:
            session.add(
                PortalSetting(portal_id=self.PORTAL_ID, white_label_name=white_label)
            )
            session.add(
                PortalEntitlement(
                    portal_id=self.PORTAL_ID,
                    plan=plan,
                    billing_interval="monthly",
                    subscription_status="active",
                    trial_approved=False,
                )
            )
            session.commit()
        finally:
            session.close()

    def test_agency_with_name_uses_brand(self) -> None:
        self._seed(white_label="Acme Ops", plan="agency")
        session = db_module.get_session()
        try:
            self.assertEqual("Acme Ops", _resolve_brand_name(session, self.PORTAL_ID))
        finally:
            session.close()

    def test_non_agency_plan_falls_back_to_opslens(self) -> None:
        self._seed(white_label="Acme Ops", plan="professional")
        session = db_module.get_session()
        try:
            self.assertEqual("OpsLens", _resolve_brand_name(session, self.PORTAL_ID))
        finally:
            session.close()

    def test_no_name_falls_back_to_opslens(self) -> None:
        self._seed(white_label="", plan="agency")
        session = db_module.get_session()
        try:
            self.assertEqual("OpsLens", _resolve_brand_name(session, self.PORTAL_ID))
        finally:
            session.close()

    def test_settings_round_trip_white_label(self) -> None:
        session = db_module.get_session()
        try:
            save_portal_settings(
                session,
                self.PORTAL_ID,
                {
                    "slackWebhookUrl": "",
                    "alertThreshold": "medium",
                    "whiteLabelName": "Acme Ops",
                },
            )
            loaded = load_portal_settings(session, self.PORTAL_ID)
            self.assertEqual("Acme Ops", loaded["whiteLabelName"])
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
