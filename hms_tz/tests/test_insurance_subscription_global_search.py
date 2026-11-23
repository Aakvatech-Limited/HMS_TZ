from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.patches import add_insurance_subscription_to_global_search as search_patch

DOCTYPE = search_patch.DOCTYPE


class TestInsuranceSubscriptionGlobalSearch(FrappeTestCase):
	def tearDown(self):
		frappe.db.rollback()
		frappe.clear_cache(doctype=DOCTYPE)

	@patch.object(search_patch, "rebuild_for_doctype")
	def test_patch_lists_subscription_once_and_indexes_it(self, rebuild_for_doctype):
		frappe.db.delete("Global Search DocType", {"document_type": DOCTYPE})

		search_patch.execute()
		search_patch.execute()

		self.assertEqual(frappe.db.count("Global Search DocType", {"document_type": DOCTYPE}), 1)
		rebuild_for_doctype.assert_called_with(DOCTYPE)

	@patch.object(search_patch, "rebuild_for_doctype")
	def test_subscription_is_found_by_patient_name_mobile_and_card_no(self, rebuild_for_doctype):
		search_patch.execute()

		fields = {field.fieldname for field in frappe.get_meta(DOCTYPE).get_global_search_fields()}
		self.assertTrue({"patient_name", "mobile_number", "coverage_plan_card_number"} <= fields)
