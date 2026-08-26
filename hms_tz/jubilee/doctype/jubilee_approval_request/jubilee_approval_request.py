# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import get_datetime, get_fullname, get_link_to_form, get_time, getdate, nowdate, nowtime

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_childs_map,
	get_item_rate,
	get_item_refcode,
)
from hms_tz.jubilee.api.api import send_preauthorization
from hms_tz.jubilee.api.preauthorization import get_encounter_diseases


class JubileeApprovalRequest(Document):
	def before_insert(self):
		"""Prevent duplicate Jubilee Approval Request for the same appointment."""

		if not self.appointment:
			frappe.throw(_("Appointment is required"))

		existing = frappe.db.get_value(
			"Jubilee Approval Request",
			{"appointment": self.appointment},
			"name",
		)
		if existing:
			link = get_link_to_form("Jubilee Approval Request", existing)
			frappe.throw(
				_(
					f"A Jubilee Approval Request: <b>{link}</b> "
					f"already exists for this appointment: <b>{self.appointment}</b>"
				)
			)

	def before_save(self):
		"""Auto-populate fields from Patient Encounter for manual creation (Path B)."""

		self.set_missing_values()

	def set_missing_values(self):
		"""Pull patient demographics, diseases, and items from the linked encounter."""
		if not self.appointment:
			frappe.throw(_("Appointment is required"))

		encounter_list = self.get_encounters()
		if not encounter_list:
			frappe.throw(_(f"No encounters found for appointment: {self.appointment}"))

		appointment_doc = frappe.get_doc("Patient Appointment", self.appointment)
		self.patient = appointment_doc.patient
		self.patient_name = appointment_doc.patient_name
		self.company = appointment_doc.company

		patient_doc = frappe.get_cached_doc("Patient", appointment_doc.patient)
		self.first_name = patient_doc.first_name
		self.last_name = patient_doc.last_name or ""
		self.gender = patient_doc.sex
		self.date_of_birth = patient_doc.dob
		self.telephone_no = patient_doc.mobile or ""
		self.inpatient_record = patient_doc.inpatient_record

		self.card_no = appointment_doc.coverage_plan_card_number or ""
		self.authorization_no = appointment_doc.authorization_number or ""
		self.attendance_date = (
			f"{appointment_doc.appointment_date} {appointment_doc.appointment_time or '00:00:00'}"
		)

		self.provider_id = (
			frappe.get_cached_value("HMS TZ Setting", self.company, "jubilee_provider_id") or ""
		)

		if not self.posting_date:
			self.posting_date = nowdate()
		if not self.posting_time:
			self.posting_time = nowtime()

		posting = getdate(self.posting_date)
		self.claim_year = posting.year
		self.claim_month = posting.month
		self.bill_no = "".join(self.name.split("-")[1:])

		self.practitioner = encounter_list[0].practitioner
		self.practitioner_no = (
			frappe.db.get_value("Healthcare Practitioner", self.practitioner, "tz_mct_code") or ""
		)
		self.jubilee_procedure = encounter_list[0].get("jubilee_procedure") or ""

		self.set_diseases(encounter_list)
		self.set_items(encounter_list)
		self.set_inpatient_values()

	def get_encounters(self):
		"""Get all encounters for the appointment excluding ipd encounters."""

		encounter_list = frappe.get_all(
			"Patient Encounter",
			{"appointment": self.appointment, "inpatient_record": ""},
			["name", "practitioner", "jubilee_procedure"],
			order_by="creation",
		)

		return encounter_list

	def set_diseases(self, encounters):
		"""Populate disease child table from encounter's preliminary and final diagnoses."""

		self.diseases = []
		for row in get_encounter_diseases([d.name for d in encounters]):
			self.append("diseases", row)

	def set_items(self, encounters):
		"""Populate item child table from encounter's service items."""

		self.items = []

		total_amount = 0
		for encounter in encounters:
			encounter_doc = frappe.get_doc("Patient Encounter", encounter.name)
			for child in get_childs_map():
				if not encounter_doc.get(child.get("table")):
					continue

				for row in encounter_doc.get(child.get("table")):
					if not row.get(child.get("item")):
						continue

					# Skip cancelled/prescribed/restricted items
					if row.get("prescribe") or row.get("is_not_available_inhouse") or row.get("is_cancelled"):
						continue

					ref_code = get_item_refcode(
						child.get("doctype"),
						row.get(child.get("item")),
						encounter_doc.company,
						encounter_doc.insurance_company,
					)

					item_code = frappe.get_cached_value(
						child.get("doctype"),
						row.get(child.get("item")),
						"item",
					)
					if not item_code:
						continue

					item_rate = get_item_rate(
						item_code,
						encounter_doc.company,
						encounter_doc.insurance_subscription,
						encounter_doc.insurance_company,
					)

					quantity = row.get("quantity") or 1
					amount = item_rate * quantity

					new_row = self.append("items", {})
					new_row.item_name = row.get(child.get("item"))
					new_row.item_code = str(ref_code) if ref_code else ""
					new_row.item_quantity = quantity
					new_row.unit_price = item_rate
					new_row.amount_claimed = amount
					new_row.ref_doctype = row.get("doctype")
					new_row.ref_docname = row.get("name")
					new_row.patient_encounter = encounter_doc.name
					new_row.created_by = get_fullname(frappe.session.user)
					new_row.date_created = nowdate()

					if row.get("preapproval_no") or (
						row.get("preapproval_status")
						and str(row.get("preapproval_status")).lower() not in ["error", "rejected"]
					):
						new_row.status = "Approved"
					else:
						new_row.status = "Pending"

					total_amount += amount

		self.total_amount = total_amount

	def set_inpatient_values(self):
		"""Set admitted/discharged dates from the encounter's inpatient record."""

		if not self.inpatient_record:
			return

		(
			discharge_date,
			scheduled_date,
			admitted_datetime,
			time_created,
		) = frappe.get_cached_value(
			"Inpatient Record",
			self.inpatient_record,
			[
				"discharge_date",
				"scheduled_date",
				"admitted_datetime",
				"creation",
			],
		)

		if not admitted_datetime:
			return

		if scheduled_date and getdate(scheduled_date) < getdate(admitted_datetime):
			self.admitted_date = f"{scheduled_date} {get_time(get_datetime(time_created))}"
		else:
			self.admitted_date = str(admitted_datetime)

		if discharge_date and getdate(self.admitted_date) == getdate(discharge_date):
			self.patient_type_code = "OP"
			self.admitted_date = None
			self.discharge_date = None
		elif discharge_date:
			self.patient_type_code = "IN"
			self.discharge_date = f"{discharge_date} {nowtime()}"

			# Override claim year/month from discharge date when inpatient
			d = getdate(discharge_date)
			self.claim_year = d.year
			self.claim_month = d.month

	def calculate_totals(self):
		"""Recalculate total_amount from items."""
		total = 0
		for row in self.items:
			row.amount_claimed = (row.unit_price or 0) * (row.item_quantity or 1)
			total += row.amount_claimed

		self.total_amount = total

	@frappe.whitelist()
	def send_to_jubilee(self):
		"""Send the pre-authorization request to Jubilee API on submit."""

		result = send_preauthorization(self.name)
		self.preauth_status = result.get("status") or ""
		self.preauth_description = result.get("description") or ""
		self.submission_id = result.get("submission_id") or ""

		self.db_update()

		self.add_comment(
			comment_type="Comment",
			text=f"""Jubilee Pre-Authorization request sent<br/>Status: {self.preauth_status}<br/>\
                Description: {self.preauth_description}<br/>Submission ID: {self.submission_id}""",
		)

		return {
			"status": self.preauth_status,
			"description": self.preauth_description,
			"submission_id": self.submission_id,
		}


@frappe.whitelist()
def create_preauthorization_doc(source_doctype, source_docname, benefit_code):
	"""Create or reuse a Jubilee Approval Request record and submit it."""

	if not source_docname:
		frappe.throw(_("Source document name is required"))

	source_doc = frappe.get_doc(source_doctype, source_docname)

	benefit_name = ""
	benefit_balance = 0
	if benefit_code:
		benefit_name, benefit_balance = frappe.get_cached_value(
			"Jubilee Benefit",
			{"appointment": source_doc.appointment, "benefit_code": benefit_code},
			["benefit_name", "benefit_balance"],
		) or ("", 0)

	existing_jar = frappe.db.get_value(
		"Jubilee Approval Request", {"appointment": source_doc.appointment}, "name"
	)

	jar_doc = None
	if existing_jar:
		jar_doc = frappe.get_doc("Jubilee Approval Request", existing_jar)
		jar_doc.benefit_code = benefit_code
		jar_doc.benefit_name = benefit_name
		jar_doc.benefit_balance = benefit_balance
		jar_doc.save(ignore_permissions=True)
	else:
		jar_doc = frappe.new_doc("Jubilee Approval Request")
		jar_doc.appointment = source_doc.appointment
		jar_doc.benefit_code = benefit_code
		jar_doc.benefit_name = benefit_name
		jar_doc.benefit_balance = benefit_balance
		jar_doc.save(ignore_permissions=True)

	result = jar_doc.send_to_jubilee()

	source_doc.add_comment(
		comment_type="Comment",
		text=(
			f"Jubilee Pre-Authorization request sent<br>"
			f"Approval Request: <b>{jar_doc.name}</b><br>"
			f"Status: <b>{result.get('status') or 'N/A'}</b><br>"
			f"Submission ID: <b>{result.get('submission_id') or 'N/A'}</b>"
		),
	)

	return {
		"status": result.get("status") or "ERROR",
		"submission_id": result.get("submission_id") or "",
		"description": result.get("description") or "",
		"service_request": jar_doc.name,
	}
