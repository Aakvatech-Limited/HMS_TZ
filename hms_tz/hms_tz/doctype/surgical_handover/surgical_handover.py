# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class SurgicalHandover(Document):
	def before_insert(self):
		self.validate_handover_parties()

	def before_submit(self):
		self.validate_acknowledgement()
		self.validate_checklist_completeness()

	def validate_handover_parties(self):
		"""Ensure handover and receiving practitioners are different."""
		if self.handed_over_by and self.received_by:
			if self.handed_over_by == self.received_by:
				frappe.throw(_("Handed Over By and Received By cannot be the same practitioner."))

	def validate_acknowledgement(self):
		"""Ensure the handover has been acknowledged before submission."""
		if not self.acknowledgement:
			frappe.throw(
				_("The receiving practitioner must acknowledge the handover before it can be submitted.")
			)
		if not self.acknowledged_time:
			self.acknowledged_time = now_datetime()

	def validate_checklist_completeness(self):
		"""Warn if any checklist items are incomplete."""
		checklist_fields = [
			"patient_identity_verified",
			"consent_verified",
			"allergies_documented",
			"vitals_stable",
			"medications_documented",
		]

		incomplete = []
		for field in checklist_fields:
			if not self.get(field):
				incomplete.append(frappe.unscrub(field))

		if incomplete:
			frappe.msgprint(
				_("The following checklist items are incomplete: {0}").format(", ".join(incomplete)),
				alert=True,
				indicator="orange",
			)
