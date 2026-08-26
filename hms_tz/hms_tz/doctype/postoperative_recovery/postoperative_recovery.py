# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from hms_tz.nhif.api.medical_record import create_medical_record, delete_medical_record, update_medical_record


class PostoperativeRecovery(Document):
	def before_submit(self):
		self.validate_nurse()
		self.validate_discharge_criteria()

	def on_submit(self):
		create_medical_record(self)

	def on_cancel(self):
		delete_medical_record(self)

	def on_update_after_submit(self):
		update_medical_record(self)

	def validate_nurse(self):
		if not self.recovery_nurse:
			frappe.throw(_("Please select a recovery nurse."))

	def validate_discharge_criteria(self):
		"""Validate Aldrete score meets minimum before discharge."""
		if self.status == "Discharged to Ward":
			if not self.discharge_criteria_met:
				frappe.throw(
					_("Please confirm that discharge criteria have been met before discharging the patient.")
				)

			total_score = sum(flt(row.score) for row in (self.recovery_scores or []))
			total_max = sum(flt(row.max_score) for row in (self.recovery_scores or []))

			if total_max > 0 and total_score < (total_max * 0.7):
				frappe.msgprint(
					_(
						f"Warning: Total recovery score: <b>{total_score}/{total_max}</b> is below 70% threshold. "
						"Please confirm patient is safe for discharge."
					),
					alert=True,
					indicator="orange",
				)


@frappe.whitelist()
def create_surgical_handover(postoperative_recovery: str, **kwargs) -> str:
	"""Create a Surgical Handover record (Theater to Ward) from the
	Postoperative Recovery form."""
	pr = frappe.get_doc("Postoperative Recovery", postoperative_recovery)

	sh = frappe.new_doc("Surgical Handover")
	sh.patient = pr.patient
	sh.clinical_procedure = pr.clinical_procedure
	sh.company = pr.company
	sh.type = "Theater to Ward"
	sh.handover_time = frappe.utils.now_datetime()

	# Transfer details
	transfer_fields = ["from_location", "to_location", "handed_over_by", "received_by"]
	for field in transfer_fields:
		if kwargs.get(field):
			sh.set(field, kwargs[field])

	# Checklist items
	checklist_fields = [
		"patient_identity_verified",
		"consent_verified",
		"surgical_site_marked",
		"allergies_documented",
		"iv_lines_checked",
		"vitals_stable",
		"medications_documented",
		"blood_products_available",
		"specimens_handed_over",
		"drain_tubes_documented",
	]
	for field in checklist_fields:
		sh.set(field, 1 if kwargs.get(field) else 0)

	# Notes
	if kwargs.get("clinical_notes"):
		sh.clinical_notes = kwargs["clinical_notes"]

	sh.insert(ignore_permissions=True)

	return sh.name
