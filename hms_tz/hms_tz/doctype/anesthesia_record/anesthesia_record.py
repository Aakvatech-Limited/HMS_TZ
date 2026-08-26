# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_time

from hms_tz.nhif.api.medical_record import create_medical_record, delete_medical_record, update_medical_record


class AnesthesiaRecord(Document):
	def before_save(self):
		self.validate_timing()

	def on_submit(self):
		create_medical_record(self)

	def on_cancel(self):
		delete_medical_record(self)

	def on_update_after_submit(self):
		update_medical_record(self)

	def validate_timing(self):
		"""Ensure end_time is after start_time if both are set."""
		if self.start_time and self.end_time:
			if get_time(self.end_time) < get_time(self.start_time):
				frappe.throw(_("End Time cannot be before Start Time"))
