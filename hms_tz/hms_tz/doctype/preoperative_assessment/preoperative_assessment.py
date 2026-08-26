# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

from hms_tz.nhif.api.medical_record import create_medical_record, delete_medical_record, update_medical_record


class PreoperativeAssessment(Document):
	def before_save(self):
		self.set_missing_values()
		# self.fetch_patient_medical_history()
		self.validate_clearance_checks()

	def before_submit(self):
		if not self.practitioner:
			frappe.throw(_("Practitioner is required"))

	def on_submit(self):
		create_medical_record(self)

	def on_cancel(self):
		delete_medical_record(self)

	def on_update_after_submit(self):
		update_medical_record(self)

	def set_missing_values(self):
		"""Auto-set fields from OT Schedule → Clinical Procedure → Appointment chain."""
		# Set clinical_procedure and service_name from OT Schedule
		if self.ot_schedule:
			ot_details = frappe.db.get_value(
				"OT Schedule",
				self.ot_schedule,
				["clinical_procedure", "procedure_template", "patient", "company"],
				as_dict=True,
			)
			if ot_details:
				if not self.patient and ot_details.patient:
					self.patient = ot_details.patient
				if not self.company and ot_details.company:
					self.company = ot_details.company
				if not self.clinical_procedure and ot_details.clinical_procedure:
					self.clinical_procedure = ot_details.clinical_procedure
				if not self.service_name and ot_details.procedure_template:
					self.service_name = ot_details.procedure_template

		# Fetch appointment from Clinical Procedure (if available)
		if self.clinical_procedure and not self.appointment:
			appointment = frappe.db.get_value("Clinical Procedure", self.clinical_procedure, "appointment")
			if appointment:
				self.appointment = appointment

		# Set inpatient_record from patient
		if self.patient and not self.inpatient_record:
			self.inpatient_record = frappe.db.get_value("Patient", self.patient, "inpatient_record")

		# Set insurance fields from appointment
		if self.appointment and not self.payment_type:
			appt_details = frappe.db.get_value(
				"Patient Appointment",
				self.appointment,
				[
					"insurance_subscription",
					"coverage_plan_name",
					"insurance_company",
				],
				as_dict=True,
			)
			if appt_details and appt_details.insurance_company:
				self.payment_type = "Insurance"
				self.insurance_subscription = appt_details.insurance_subscription
				self.insurance_coverage_plan = appt_details.coverage_plan_name
				self.insurance_company = appt_details.insurance_company
			else:
				self.payment_type = "Cash"

		# Clear insurance fields for cash patients
		if self.payment_type == "Cash" and self.insurance_subscription:
			self.insurance_subscription = ""
			self.insurance_coverage_plan = ""
			self.insurance_company = ""

	def fetch_patient_medical_history(self):
		"""Fetch allergies, chronic medications, and surgical history from Patient."""

		if not self.patient:
			return

		patient_doc = frappe.get_cached_doc("Patient", self.patient)

		if not self.allergies and patient_doc.allergies:
			self.allergies = patient_doc.allergies

		if not self.surgical_history and patient_doc.surgical_history:
			self.surgical_history = patient_doc.surgical_history

		if len(self.chronic_medications) == 0:
			for row in patient_doc.chronic_medications:
				self.append(
					"chronic_medications",
					{
						"drug_code": row.drug_code,
						"drug_name": row.drug_name,
						"dosage": row.dosage,
						"period": row.period,
						"dosage_form": row.dosage_form,
						"quantity": row.quantity,
						"comment": row.comment,
						"patient_instruction": row.patient_instruction,
						"usage_interval": row.usage_interval,
						"interval": row.interval,
						"interval_uom": row.interval_uom,
					},
				)

	def validate_clearance_checks(self):
		"""Warn if marking as Cleared without all checks complete."""
		if self.status != "Cleared for Surgery":
			return

		required_checks = [
			"fasting_status_verified",
			"consent_signed",
			"site_marking_verified",
		]

		missing = []
		for check in required_checks:
			if not self.get(check):
				missing.append(frappe.unscrub(check))

		if missing:
			frappe.throw(
				_("Cannot mark as 'Cleared for Surgery'. The following checks are incomplete: {0}").format(
					", ".join(missing)
				)
			)
