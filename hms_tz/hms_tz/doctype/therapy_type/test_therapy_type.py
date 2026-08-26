# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import unittest

import frappe
from erpnext import get_default_company


class TestTherapyType(unittest.TestCase):
	def test_therapy_type_item(self):
		therapy_type = create_therapy_type()
		self.assertTrue(frappe.db.exists("Item", therapy_type.item))

		therapy_type.disabled = 1
		therapy_type.save()
		self.assertEqual(frappe.get_cached_value("Item", therapy_type.item, "disabled"), 1)


def create_therapy_type():
	exercise = create_exercise_type()

	# Ensure Healthcare Points of Care record exists for default value
	if not frappe.db.exists("Healthcare Points of Care", "Phisiotherapy"):
		frappe.get_doc(
			{
				"doctype": "Healthcare Points of Care",
				"point_of_care_name": "Phisiotherapy",
			}
		).insert(ignore_permissions=True)

	therapy_type = frappe.db.exists("Therapy Type", "Basic Rehab")
	if not therapy_type:
		# Get the first available company and service unit for company_options
		company = get_default_company()
		service_unit = frappe.db.get_value(
			"Healthcare Service Unit", {"company": company}, "name"
		) or frappe.db.get_value("Healthcare Service Unit", {}, "name")

		if not service_unit:
			parent = frappe.db.get_value(
				"Healthcare Service Unit",
				{"is_group": 1},
				"name",
			)
			su = frappe.new_doc("Healthcare Service Unit")
			su.healthcare_service_unit_name = "_Test Therapy Service Unit"
			su.company = company
			su.is_group = 0
			su.room_type = frappe.db.get_value("Healthcare Room Type", {}, "name") or "General Ward"
			if parent:
				su.parent_healthcare_service_unit = parent
			su.save(ignore_permissions=True)
			service_unit = su.name

		therapy_type = frappe.new_doc("Therapy Type")
		therapy_type.therapy_type = "Basic Rehab"
		therapy_type.default_duration = 30
		therapy_type.is_billable = 1
		therapy_type.rate = 5000
		therapy_type.item_code = "Basic Rehab"
		therapy_type.item_name = "Basic Rehab"
		therapy_type.item_group = "Services"
		therapy_type.points_of_care = "Phisiotherapy"
		therapy_type.append(
			"exercises",
			{
				"exercise_type": exercise.name,
				"counts_target": 10,
				"assistance_level": "Passive",
			},
		)
		therapy_type.append(
			"company_options",
			{
				"company": company,
				"service_unit": service_unit,
			},
		)
		therapy_type.save()
	else:
		therapy_type = frappe.get_cached_doc("Therapy Type", "Basic Rehab")
	return therapy_type


def create_exercise_type():
	exercise_type = frappe.db.exists("Exercise Type", "Sit to Stand")
	if not exercise_type:
		exercise_type = frappe.new_doc("Exercise Type")
		exercise_type.exercise_name = "Sit to Stand"
		exercise_type.append("steps_table", {"title": "Step 1", "description": "Squat and Rise"})
		exercise_type.save()
	return exercise_type
