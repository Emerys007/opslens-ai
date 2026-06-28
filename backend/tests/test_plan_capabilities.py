from __future__ import annotations

import unittest
from unittest.mock import patch

from app.services.marketplace_billing import (
    normalize_plan,
    plan_from_price_id,
    price_id_for,
)
from app.services.plan_capabilities import (
    ALL_DETECTION_GROUPS,
    allowed_detection_groups,
    detection_group_for_category,
    plan_allows_category,
    plan_portal_limit,
    plan_portal_limit_reached,
)


class PlanNamingTests(unittest.TestCase):
    def test_normalize_accepts_marketing_tiers(self) -> None:
        self.assertEqual("starter", normalize_plan("Starter"))
        self.assertEqual("professional", normalize_plan(" professional "))
        self.assertEqual("agency", normalize_plan("AGENCY"))

    def test_normalize_accepts_legacy_business(self) -> None:
        self.assertEqual("business", normalize_plan("business"))

    def test_normalize_rejects_unknown_and_enterprise(self) -> None:
        # Enterprise is contact-sales, not a self-serve billable plan.
        with self.assertRaises(ValueError):
            normalize_plan("enterprise")
        with self.assertRaises(ValueError):
            normalize_plan("bogus")

    def test_price_id_for_new_tiers(self) -> None:
        with patch(
            "app.services.marketplace_billing.settings.stripe_price_starter_monthly",
            "price_starter_month",
        ), patch(
            "app.services.marketplace_billing.settings.stripe_price_agency_yearly",
            "price_agency_year",
        ):
            self.assertEqual("price_starter_month", price_id_for("starter", "monthly"))
            self.assertEqual("price_agency_year", price_id_for("agency", "yearly"))

    def test_price_id_for_raises_when_unconfigured(self) -> None:
        with patch(
            "app.services.marketplace_billing.settings.stripe_price_starter_yearly",
            "",
        ):
            with self.assertRaises(RuntimeError):
                price_id_for("starter", "yearly")

    def test_plan_from_price_id_round_trips_new_tiers(self) -> None:
        with patch(
            "app.services.marketplace_billing.settings.stripe_price_agency_monthly",
            "price_agency_month",
        ):
            self.assertEqual(("agency", "monthly"), plan_from_price_id("price_agency_month"))

    def test_plan_from_price_id_blank_is_empty(self) -> None:
        self.assertEqual(("", ""), plan_from_price_id(""))
        self.assertEqual(("", ""), plan_from_price_id(None))


class DetectionGroupMappingTests(unittest.TestCase):
    def test_prefix_mapping(self) -> None:
        self.assertEqual("property", detection_group_for_category("property_archived"))
        self.assertEqual("workflow", detection_group_for_category("workflow_disabled"))
        self.assertEqual("list", detection_group_for_category("list_criteria_changed"))
        self.assertEqual("template", detection_group_for_category("template_edited"))
        self.assertEqual("owner", detection_group_for_category("owner_deactivated"))

    def test_unrecognized_category_maps_to_empty(self) -> None:
        self.assertEqual("", detection_group_for_category("survey_created"))
        self.assertEqual("", detection_group_for_category(""))


class PlanCapabilityTests(unittest.TestCase):
    def test_starter_covers_property_and_workflow_only(self) -> None:
        groups = allowed_detection_groups("starter")
        self.assertIn("property", groups)
        self.assertIn("workflow", groups)
        self.assertNotIn("list", groups)
        self.assertNotIn("template", groups)
        self.assertNotIn("owner", groups)

    def test_professional_adds_list_and_template_not_owner(self) -> None:
        groups = allowed_detection_groups("professional")
        self.assertIn("list", groups)
        self.assertIn("template", groups)
        self.assertNotIn("owner", groups)

    def test_agency_and_business_cover_everything(self) -> None:
        self.assertEqual(ALL_DETECTION_GROUPS, allowed_detection_groups("agency"))
        self.assertEqual(ALL_DETECTION_GROUPS, allowed_detection_groups("business"))

    def test_unknown_plan_fails_open(self) -> None:
        self.assertEqual(ALL_DETECTION_GROUPS, allowed_detection_groups(""))
        self.assertEqual(ALL_DETECTION_GROUPS, allowed_detection_groups("mystery"))

    def test_plan_allows_category(self) -> None:
        self.assertFalse(plan_allows_category("starter", "list_criteria_changed"))
        self.assertTrue(plan_allows_category("starter", "property_archived"))
        self.assertFalse(plan_allows_category("professional", "owner_deactivated"))
        self.assertTrue(plan_allows_category("agency", "owner_deactivated"))
        # Fail open for unknown plan or unrecognized category.
        self.assertTrue(plan_allows_category("", "owner_deactivated"))
        self.assertTrue(plan_allows_category("starter", "survey_created"))

    def test_portal_limits(self) -> None:
        self.assertEqual(1, plan_portal_limit("starter"))
        self.assertEqual(3, plan_portal_limit("professional"))
        self.assertEqual(10, plan_portal_limit("agency"))
        self.assertEqual(10, plan_portal_limit("business"))
        self.assertIsNone(plan_portal_limit("enterprise"))
        self.assertIsNone(plan_portal_limit("unknown"))

    def test_portal_limit_reached(self) -> None:
        self.assertTrue(plan_portal_limit_reached("starter", 1))
        self.assertFalse(plan_portal_limit_reached("starter", 0))
        self.assertFalse(plan_portal_limit_reached("agency", 5))
        # Unlimited / unknown plans never block.
        self.assertFalse(plan_portal_limit_reached("enterprise", 999))
        self.assertFalse(plan_portal_limit_reached("unknown", 999))
