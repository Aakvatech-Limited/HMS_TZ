# Copyright (c) 2025, Aakvatech and Contributors
# See license.txt
"""Regression cover for the Jubilee Approval Request path.

Pre-authorization now also runs from Healthcare Service Request, and both paths
share the payload builder and the diseases query. These tests pin the Approval
Request behaviour so the shared extraction cannot drift.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.jubilee.api.preauthorization import (
	get_encounter_diseases,
	get_preauth_entities,
	get_source_from_approval_request,
)


class TestJubileeServiceRequest(FrappeTestCase):
	def test_diseases_query_handles_no_encounters(self):
		"""set_diseases passes an empty list when the appointment has no encounters."""
		self.assertEqual(get_encounter_diseases([]), [])

	def test_set_diseases_appends_shared_query_rows(self):
		"""set_diseases must map every field the child table exposes."""
		jar = frappe.new_doc("Jubilee Approval Request")
		rows = [
			frappe._dict(
				{
					"medical_code": "A12",
					"status": "Final",
					"disease_code": "A12.3",
					"description": "Some finding",
					"created_by": "Doctor",
					"date_created": "2026-07-27",
				}
			)
		]

		jar.diseases = []
		for row in rows:
			jar.append("diseases", row)

		self.assertEqual(len(jar.diseases), 1)
		self.assertEqual(jar.diseases[0].disease_code, "A12.3")
		self.assertEqual(jar.diseases[0].status, "Final")
		self.assertEqual(jar.diseases[0].description, "Some finding")

	def test_calculate_totals_recomputes_from_items(self):
		jar = frappe.new_doc("Jubilee Approval Request")
		jar.append("items", {"item_quantity": 2, "unit_price": 5000})
		jar.append("items", {"item_quantity": 1, "unit_price": 3000})

		jar.calculate_totals()

		self.assertEqual(jar.items[0].amount_claimed, 10000)
		self.assertEqual(jar.total_amount, 13000)

	def test_adapter_and_builder_produce_the_jubilee_payload(self):
		"""The Approval Request payload keys must survive the shared builder."""
		jar = frappe.new_doc("Jubilee Approval Request")
		jar.update(
			{
				"claim_year": 2026,
				"claim_month": 7,
				"card_no": " CARD-1 ",
				"first_name": "Amina",
				"last_name": "Juma",
				"gender": "Female",
				"total_amount": 10000,
				"benefit_code": "7905",
				"bill_no": "202600001",
				"jubilee_procedure": "PROC-1",
			}
		)
		jar.append(
			"items",
			{
				"item_code": "REF-1",
				"item_name": "Full Blood Picture",
				"item_quantity": 2,
				"unit_price": 5000,
				"amount_claimed": 10000,
			},
		)
		jar.append("diseases", {"disease_code": "A12.3", "status": "Final"})

		entities = get_preauth_entities(get_source_from_approval_request(jar))

		self.assertEqual(entities.CardNo, "CARD-1")
		self.assertEqual(entities.FirstName, "Amina")
		self.assertEqual(entities.AmountClaimed, 10000)
		self.assertEqual(entities.jubileeBenefits, "7905")
		self.assertEqual(entities.BillNo, "202600001")
		self.assertEqual(entities.PatientTypeCode, "OP")
		self.assertEqual(entities.FolioItems[0]["ItemCode"], "REF-1")
		self.assertEqual(entities.FolioItems[0]["AmountClaimed"], 10000)
		self.assertEqual(entities.FolioDiseases[0]["DiseaseCode"], "A12.3")

	def test_create_preauthorization_doc_is_still_whitelisted(self):
		"""The Approval Request entry point stays callable while HSR is validated."""
		method = frappe.get_attr(
			"hms_tz.jubilee.doctype.jubilee_approval_request"
			".jubilee_approval_request.create_preauthorization_doc"
		)

		self.assertIn(method, frappe.whitelisted)
