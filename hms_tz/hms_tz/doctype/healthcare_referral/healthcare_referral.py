# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.core.utils import html2text
from frappe.model.document import Document
from frappe.utils import now_datetime

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_childs_map,
	get_item_refcode,
)
from hms_tz.nhif.nhif_api.referral import create_referral


class HealthcareReferral(Document):
	def before_insert(self):
		self.get_clinical_notes()

	def before_save(self):
		self.posting_date = now_datetime()
		self.patient_type_code = (
			"IN" if frappe.get_cached_value("Patient", self.patient, "inpatient_record") else "OUT"
		)

	def before_submit(self):
		self.validate_required_fields()
		self.posting_date = now_datetime()

		if "NHIF" in self.insurance_company:
			create_referral(self)

	def validate_required_fields(self):
		"""Validate required fields"""

		if not self.referred_to_facility_code:
			frappe.throw("Referred To Facility Code is required")

		if not self.practitioner_no:
			frappe.throw("Practitioner No is required")

		if not self.patient:
			frappe.throw("Patient is required")

		if not self.attendance_date:
			frappe.throw("Attendance Date is required")

		if not self.reason_for_referral:
			frappe.throw("Reason for Referral is required")

		if len(self.diagnosis) == 0:
			frappe.throw("Diagnosis are required")

		if self.referral_type == "Form 2C/2E" and len(self.services) == 0:
			frappe.throw("Services are required")

	def get_clinical_notes(self):
		"""Get clinical notes from encounter"""

		if not self.encounter:
			return

		notes_html = frappe.get_cached_value("Patient Encounter", self.encounter, "examination_detail") or ""
		clinical_notes = html2text(notes_html).lstrip("\n")
		self.reason_for_referral = clinical_notes

	@frappe.whitelist()
	def get_diagnosis(self):
		"""Get diagnosis from encounter"""

		if not self.encounter:
			return

		diagnosis = []
		unique_diagnosis = []
		encounter_doc = frappe.get_cached_doc("Patient Encounter", self.encounter)
		for d in encounter_doc.patient_encounter_final_diagnosis:
			diagnosis.append(
				{
					"status": "Final",
					"disease_code": d.code,
					"description": d.definition,
				}
			)
			unique_diagnosis.append(d.code)

		for d in encounter_doc.patient_encounter_preliminary_diagnosis:
			if d.code not in unique_diagnosis:
				diagnosis.append(
					{
						"status": "Provisional",
						"disease_code": d.code,
						"description": d.definition,
					}
				)
				unique_diagnosis.append(d.code)

		return reversed(diagnosis)

	@frappe.whitelist()
	def get_services(self):
		"""Get services from encounter"""

		if not self.encounter:
			return

		services = []
		childs_map = get_childs_map()
		encounter_doc = frappe.get_cached_doc("Patient Encounter", self.encounter)

		for child in childs_map:
			if len(encounter_doc.get(child["table"])) == 0:
				continue

			for row in encounter_doc.get(child["table"]):
				if row.is_cancelled == 1 or row.is_not_available_inhouse == 1:
					continue

				if self.insurance_company and row.prescribe == 1:
					continue

				ref_code = get_item_refcode(
					child["doctype"],
					row.get(child["item"]),
					self.company,
					self.insurance_company,
				)

				service = {
					"service_type": child["doctype"],
					"service_name": row.get(child["item"]),
					"qty": row.get("quantity") or 1,
					"item_code": ref_code,
				}

				if child["lrpmt_doctype"] != "Therapy Session":
					if row.get(child["lrpmt_docname"]):
						service["approval_ref_no"] = frappe.get_cached_value(
							child["lrpmt_doctype"], row.get(child["lrpmt_docname"]), "approval_number"
						)
				else:
					service["approval_ref_no"] = frappe.get_cached_value(
						"Therapy Session",
						{"hms_tz_ref_childname": row.name},
						"approval_number",
					)

				services.append(service)

		return services

	@frappe.whitelist()
	def get_source_facility(self):
		"""Get source facility code"""

		if not self.company or self.referral_type == "AcknowledgeServiceReferral":
			return

		facility_code = frappe.get_cached_value("HMS TZ Setting", self.company, "facility_code")

		if not facility_code:
			frappe.throw(f"Source Facility Code is not set for the HMS TZ Setting: <b>{self.company}</b>")

		source_facility = frappe.get_cached_value(
			"Healthcare Facility", {"facility_code": facility_code}, "name"
		)

		return {"source_facility": source_facility, "source_facility_code": facility_code}
