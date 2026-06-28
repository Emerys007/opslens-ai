from __future__ import annotations

import unittest

from app.models.alert import (
    SOURCE_EVENT_LIST_ARCHIVED,
    SOURCE_EVENT_OWNER_DEACTIVATED,
    SOURCE_EVENT_PROPERTY_ARCHIVED,
    SOURCE_EVENT_PROPERTY_DELETED,
    SOURCE_EVENT_PROPERTY_RENAMED,
    SOURCE_EVENT_TEMPLATE_ARCHIVED,
    SOURCE_EVENT_WORKFLOW_DISABLED,
)
from app.services.remediation_guidance import fix_guidance_for

ALL_EVENT_TYPES = [
    "property_archived",
    "property_type_changed",
    "property_deleted",
    "property_renamed",
    "workflow_disabled",
    "workflow_edited",
    "workflow_deleted",
    "list_archived",
    "list_deleted",
    "list_criteria_changed",
    "template_archived",
    "template_deleted",
    "template_edited",
    "owner_deactivated",
    "owner_deleted",
]


class RemediationGuidanceTests(unittest.TestCase):
    def test_every_event_type_has_summary_and_steps(self) -> None:
        for event_type in ALL_EVENT_TYPES:
            guidance = fix_guidance_for(event_type)
            self.assertTrue(guidance["summary"].strip(), event_type)
            self.assertTrue(len(guidance["steps"]) >= 1, event_type)
            self.assertIsInstance(guidance["restorable"], bool)

    def test_restorable_flags(self) -> None:
        for restorable_type in (
            SOURCE_EVENT_PROPERTY_ARCHIVED,
            SOURCE_EVENT_WORKFLOW_DISABLED,
            SOURCE_EVENT_LIST_ARCHIVED,
            SOURCE_EVENT_TEMPLATE_ARCHIVED,
        ):
            self.assertTrue(fix_guidance_for(restorable_type)["restorable"], restorable_type)
        self.assertFalse(fix_guidance_for(SOURCE_EVENT_PROPERTY_DELETED)["restorable"])
        self.assertFalse(fix_guidance_for(SOURCE_EVENT_OWNER_DEACTIVATED)["restorable"])

    def test_rename_guidance_is_grounded_in_internal_name(self) -> None:
        guidance = fix_guidance_for(SOURCE_EVENT_PROPERTY_RENAMED)
        blob = (guidance["summary"] + " " + " ".join(guidance["steps"])).lower()
        self.assertIn("internal name", blob)
        self.assertFalse(guidance["restorable"])

    def test_unknown_type_returns_safe_default(self) -> None:
        guidance = fix_guidance_for("survey_created")
        self.assertTrue(guidance["summary"].strip())
        self.assertTrue(len(guidance["steps"]) >= 1)
        self.assertFalse(guidance["restorable"])
        self.assertEqual(fix_guidance_for(None)["restorable"], False)

    def test_returned_dict_is_a_copy(self) -> None:
        first = fix_guidance_for(SOURCE_EVENT_PROPERTY_ARCHIVED)
        first["steps"].append("mutated")
        first["summary"] = "mutated"
        second = fix_guidance_for(SOURCE_EVENT_PROPERTY_ARCHIVED)
        self.assertNotIn("mutated", second["steps"])
        self.assertNotEqual("mutated", second["summary"])
