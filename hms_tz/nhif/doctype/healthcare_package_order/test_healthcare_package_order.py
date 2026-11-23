# Copyright (c) 2023, Aakvatech and Contributors
# See license.txt

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase


class TestHealthcarePackageOrder(FrappeTestCase):
	def get_appointment_type(self, payment_type):
		return frappe.get_doc(
			{"doctype": "Healthcare Package Order", "payment_type": payment_type}
		).get_appointment_type()

	def test_cash_and_insurance_packages_use_normal_visit(self):
		with patch("frappe.db.exists", return_value=True):
			self.assertEqual(self.get_appointment_type("Cash"), "Normal Visit")
			self.assertEqual(self.get_appointment_type("Insurance"), "Normal Visit")

	def test_missing_visit_type_stops_the_order(self):
		with patch("frappe.db.exists", return_value=False):
			with self.assertRaises(frappe.ValidationError):
				self.get_appointment_type("Cash")
