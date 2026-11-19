# Copyright (c) 2025, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


def setting_with_slot_duration(minutes):
	return frappe.get_doc({"doctype": "HMS TZ Setting", "appointment_slot_duration": minutes})


class TestHMSTZSetting(FrappeTestCase):
	def test_slot_duration_defaults_to_ten_minutes(self):
		self.assertEqual(frappe.new_doc("HMS TZ Setting").appointment_slot_duration, 10)

	def test_slot_durations_that_divide_an_hour_are_accepted(self):
		for minutes in (5, 10, 15, 20, 30, 60):
			setting_with_slot_duration(minutes).validate_appointment_slot_duration()

	def test_other_slot_durations_are_rejected(self):
		for minutes in (0, 4, 7, 25, 90):
			with self.subTest(minutes=minutes), self.assertRaises(frappe.ValidationError):
				setting_with_slot_duration(minutes).validate_appointment_slot_duration()
