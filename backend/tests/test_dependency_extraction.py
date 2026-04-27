"""Pure-function tests for `dependency_extraction.extract_dependencies`.

No database access. Each test feeds a hand-crafted workflow definition
into the extractor and asserts on the resulting list of dependency
descriptors. Use this file as the canonical contract for what counts
as an "external dependency" of a HubSpot workflow.
"""

from __future__ import annotations

import unittest

from app.services.dependency_extraction import extract_dependencies


def _by_type(deps, dependency_type):
    return [d for d in deps if d["dependency_type"] == dependency_type]


def _by_id(deps, dependency_id):
    return [d for d in deps if d["dependency_id"] == dependency_id]


class ExtractDependenciesTests(unittest.TestCase):
    def test_empty_workflow_definition_returns_empty_list(self) -> None:
        self.assertEqual([], extract_dependencies({}))
        self.assertEqual([], extract_dependencies(None))
        self.assertEqual([], extract_dependencies({"actions": []}))

    def test_non_dict_input_returns_empty_list(self) -> None:
        self.assertEqual([], extract_dependencies("not a workflow"))
        self.assertEqual([], extract_dependencies([1, 2, 3]))

    def test_property_reference_in_enrollment_criteria(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "enrollmentCriteria": {
                "listFilterBranches": [
                    {
                        "filters": [
                            {
                                "property": "lifecyclestage",
                                "operator": "EQ",
                                "value": "lead",
                            }
                        ]
                    }
                ],
            },
        }

        deps = extract_dependencies(definition)
        properties = _by_type(deps, "property")
        self.assertEqual(1, len(properties))
        self.assertEqual("lifecyclestage", properties[0]["dependency_id"])
        self.assertEqual("0-1", properties[0]["dependency_object_type"])
        self.assertIn("enrollmentCriteria.listFilterBranches[0]", properties[0]["location"])
        self.assertTrue(properties[0]["location"].endswith(".property"))

    def test_property_reference_in_action(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-13",
                    "fields": {"property_name": "lifecyclestage", "value": "customer"},
                },
            ],
        }

        deps = extract_dependencies(definition)
        properties = _by_type(deps, "property")
        self.assertEqual(1, len(properties))
        self.assertEqual("lifecyclestage", properties[0]["dependency_id"])
        self.assertEqual("0-1", properties[0]["dependency_object_type"])
        self.assertEqual("actions[0].fields.property_name", properties[0]["location"])

    def test_copy_property_action_emits_value_property_dependency(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "actions": [
                {
                    "actionId": "2",
                    "actionTypeId": "0-22",
                    "fields": {
                        "property_name": "primary_email",
                        "value_property_name": "secondary_email",
                    },
                },
            ],
        }

        deps = extract_dependencies(definition)
        property_ids = sorted(d["dependency_id"] for d in _by_type(deps, "property"))
        self.assertEqual(["primary_email", "secondary_email"], property_ids)

    def test_email_template_reference(self) -> None:
        definition = {
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-13",
                    "fields": {"email_id": "12345"},
                },
                {
                    "actionId": "2",
                    "actionTypeId": "0-13",
                    "fields": {"email_content_id": "67890"},
                },
            ],
        }

        deps = extract_dependencies(definition)
        email_deps = _by_type(deps, "email_template")
        self.assertEqual(2, len(email_deps))
        self.assertEqual(
            {"12345", "67890"},
            {d["dependency_id"] for d in email_deps},
        )

    def test_list_reference(self) -> None:
        definition = {
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-99",
                    "fields": {"list_id": "42"},
                },
                {
                    "actionId": "2",
                    "actionTypeId": "0-99",
                    "fields": {"included_list_ids": ["1", "2"], "excluded_list_ids": ["3"]},
                },
            ],
        }

        deps = extract_dependencies(definition)
        lists = _by_type(deps, "list")
        list_ids = sorted(d["dependency_id"] for d in lists)
        self.assertEqual(["1", "2", "3", "42"], list_ids)

    def test_owner_reference(self) -> None:
        definition = {
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-77",
                    "fields": {"owner_id": "owner-99"},
                },
                {
                    "actionId": "2",
                    "actionTypeId": "0-77",
                    "fields": {"assignedOwnerId": "owner-100"},
                },
            ],
        }

        deps = extract_dependencies(definition)
        owners = _by_type(deps, "owner")
        self.assertEqual(2, len(owners))
        self.assertEqual(
            {"owner-99", "owner-100"},
            {owner["dependency_id"] for owner in owners},
        )

    def test_personalization_token_in_action_text(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-13",
                    "fields": {
                        "subject": "Hi {{ contact.firstname }}, welcome",
                        "body": "Your account manager is {{contact.sales_rep_email}}.",
                    },
                },
            ],
        }

        deps = extract_dependencies(definition)
        properties = _by_type(deps, "property")
        token_props = sorted(d["dependency_id"] for d in properties)
        self.assertIn("firstname", token_props)
        self.assertIn("sales_rep_email", token_props)
        # Tokens scoped to "contact" should be tagged with object type 0-1.
        firstname = next(d for d in properties if d["dependency_id"] == "firstname")
        self.assertEqual("0-1", firstname["dependency_object_type"])

    def test_personalization_token_with_company_scope_uses_company_object_type(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-13",
                    "fields": {"body": "Account: {{ company.name }}"},
                },
            ],
        }

        deps = extract_dependencies(definition)
        company_name = next(
            d for d in deps
            if d["dependency_type"] == "property" and d["dependency_id"] == "name"
        )
        self.assertEqual("0-2", company_name["dependency_object_type"])

    def test_malformed_definition_does_not_raise(self) -> None:
        # Mix of wrong types in places the extractor walks.
        definition = {
            "objectTypeId": "0-1",
            "enrollmentCriteria": "not-a-dict",
            "actions": [
                "not-an-action",
                {"actionTypeId": "0-13", "fields": "not-a-dict"},
                {"fields": {"property_name": ""}},  # empty value, should be skipped
                {"connection": "not-a-dict"},
            ],
        }

        deps = extract_dependencies(definition)
        # No exception — and nothing gets emitted from the malformed
        # branches. The empty `property_name` is skipped because of the
        # _normalise short-circuit.
        self.assertEqual([], deps)

    def test_same_property_referenced_three_times_emits_three_dependencies(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-13",
                    "fields": {"property_name": "lifecyclestage", "value": "lead"},
                },
                {
                    "actionId": "2",
                    "actionTypeId": "0-13",
                    "fields": {"property_name": "lifecyclestage", "value": "customer"},
                },
                {
                    "actionId": "3",
                    "actionTypeId": "0-13",
                    "fields": {"property_name": "lifecyclestage", "value": "champion"},
                },
            ],
        }

        deps = extract_dependencies(definition)
        lifecycle_refs = [
            d for d in deps
            if d["dependency_type"] == "property" and d["dependency_id"] == "lifecyclestage"
        ]
        self.assertEqual(3, len(lifecycle_refs))
        locations = sorted(d["location"] for d in lifecycle_refs)
        self.assertEqual(
            [
                "actions[0].fields.property_name",
                "actions[1].fields.property_name",
                "actions[2].fields.property_name",
            ],
            locations,
        )

    def test_unknown_external_id_emits_unknown_dependency(self) -> None:
        definition = {
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-99",
                    "fields": {"some_resource_id": "987654"},
                },
            ],
        }

        deps = extract_dependencies(definition)
        unknowns = _by_type(deps, "unknown")
        self.assertEqual(1, len(unknowns))
        self.assertEqual("987654", unknowns[0]["dependency_id"])
        self.assertIn("some_resource_id", unknowns[0]["location"])

    def test_default_object_type_id_is_used_when_definition_omits_it(self) -> None:
        definition = {
            "actions": [
                {
                    "actionTypeId": "0-13",
                    "fields": {"property_name": "industry"},
                },
            ],
        }

        deps = extract_dependencies(definition, default_object_type_id="0-2")
        self.assertEqual(1, len(deps))
        self.assertEqual("0-2", deps[0]["dependency_object_type"])

    def test_connection_filter_branches_walked(self) -> None:
        definition = {
            "objectTypeId": "0-1",
            "actions": [
                {
                    "actionId": "1",
                    "actionTypeId": "0-50",
                    "fields": {},
                    "connection": {
                        "filterBranches": [
                            {
                                "filters": [
                                    {"property": "country", "operator": "EQ"},
                                ],
                            },
                        ],
                    },
                },
            ],
        }

        deps = extract_dependencies(definition)
        country_refs = [
            d for d in deps
            if d["dependency_type"] == "property" and d["dependency_id"] == "country"
        ]
        self.assertEqual(1, len(country_refs))
        self.assertIn("connection.filterBranches", country_refs[0]["location"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
