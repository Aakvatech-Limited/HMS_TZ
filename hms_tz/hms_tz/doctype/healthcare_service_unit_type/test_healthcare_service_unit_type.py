# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe


class TestHealthcareServiceUnitType(unittest.TestCase):
	def test_item_creation(self):
		unit_type = get_unit_type()
		self.assertTrue(frappe.db.exists("Item", unit_type.item))

		# check item disabled
		unit_type.disabled = 1
		unit_type.save()
		self.assertEqual(frappe.get_cached_value("Item", unit_type.item, "disabled"), 1)


def get_unit_type():
	if frappe.db.exists("Healthcare Service Unit Type", "Inpatient Rooms"):
		return frappe.get_cached_doc("Healthcare Service Unit Type", "Inpatient Rooms")

	# Ensure Healthcare Ward Type exists
	if not frappe.db.exists("Healthcare Ward Type", "General Ward"):
		frappe.get_doc(
			{
				"doctype": "Healthcare Ward Type",
				"ward_type_name": "General Ward",
			}
		).insert(ignore_permissions=True)

	unit_type = frappe.new_doc("Healthcare Service Unit Type")
	unit_type.service_unit_type = "Inpatient Rooms"
	unit_type.inpatient_occupancy = 1
	unit_type.is_billable = 1
	unit_type.item_code = "Inpatient Rooms"
	unit_type.item_group = "Services"
	unit_type.uom = "Hour"
	unit_type.no_of_hours = 1
	unit_type.rate = 4000
	unit_type.ward_type = "General Ward"
	unit_type.save()
	return unit_type
