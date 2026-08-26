import frappe
from erpnext.accounts.utils import get_balance_on
from frappe.model.document import Document
from frappe.utils import flt, get_url_to_form, nowdate, nowtime

from hms_tz.nhif.api.patient_encounter import create_service_request, validate_totals


class LimitChangeRequest(Document):
	def before_insert(self):
		self.posting_date = nowdate()
		self.posting_time = nowtime()
		self.requested_by = frappe.utils.get_fullname(frappe.session.user)

		self.validate_appointment_info()

	def validate(self):
		self.validate_draft_duplicate()
		self.set_missing_values()
		if self.is_cash_inpatient and self.is_non_nhif_patient:
			frappe.throw(
				"You can't change Cash/Daily limit for both inpatient and non-nhif patient at the same time"
			)
		if not self.is_cash_inpatient and not self.is_non_nhif_patient:
			frappe.throw(
				f"This patient: {self.patient} is not Non NHIF Patient or Not Inpatient, Limit Change Request is for Non NHIF Patients or Admitted patients"
			)

	def validate_appointment_info(self):
		if self.appointment_no:
			if "NHIF" in frappe.get_cached_value(
				"Patient Appointment", self.appointment_no, "insurance_company"
			):
				url = get_url_to_form("Patient Appointment", self.appointment_no)
				frappe.throw(
					f"This Appointment: <a href='{url}'><b>{self.appointment_no}</b></a> is for NHIF Patient, You can't change the Daily/Cash limit for this appointment"
				)

	def validate_draft_duplicate(self):
		exists_lcr = frappe.get_cached_value(
			"Limit Change Request",
			{
				"name": ["!=", self.name],
				"docstatus": 0,
				"patient": self.patient,
				"appointment_no": self.appointment_no,
			},
		)
		if exists_lcr:
			url = get_url_to_form(self.doctype, exists_lcr)
			frappe.throw(
				f"There is a draft Limit Change Request: <a href='{url}'><b>{exists_lcr}</b></a> for this patient: <b>{self.patient}</b>, Use it instead"
			)

	def validate_cash_daily_limit(self):
		if self.is_cash_inpatient:
			if not flt(self.cash_limit) or flt(self.cash_limit) == 0:
				frappe.throw("<b>Cash Limit is required</b>")

			if flt(self.previous_cash_limit) and flt(self.cash_limit) <= flt(self.previous_cash_limit):
				frappe.throw("New Cash Limit must be greater than the previous cash limit")
		if self.is_non_nhif_patient:
			if not flt(self.daily_limit) or flt(self.daily_limit) == 0:
				frappe.throw("<b>Daily Limit is required</b>")

			if flt(self.current_total_cost) and flt(self.daily_limit) <= flt(self.current_total_cost):
				frappe.throw("New Daily Limit must be greater than the current total cost")

	def before_submit(self):
		self.validate_cash_daily_limit()

		self.approved_by = frappe.utils.get_fullname(frappe.session.user)

		if self.is_cash_inpatient and self.inpatient_record:
			frappe.db.set_value(
				"Inpatient Record",
				self.inpatient_record,
				"cash_limit",
				self.cash_limit,
			)

			inpatient_record_doc = frappe.get_cached_doc("Inpatient Record", self.inpatient_record)

			if inpatient_record_doc.cash_limit == self.cash_limit:
				frappe.msgprint(
					f"Inpatient Record: {frappe.bold(self.inpatient_record)} of Patient {frappe.bold(self.patient)} - {frappe.bold(self.patient_name)} has been updated with new cash limit: {frappe.bold(self.cash_limit)}"
				)

		if self.is_non_nhif_patient and self.insurance_company and self.appointment_no:
			frappe.db.set_value(
				"Patient Appointment",
				self.appointment_no,
				"daily_limit",
				self.daily_limit,
			)
			frappe.msgprint(
				f"Daily Limit of: <b>{self.daily_limit}</b> was updated for Patient <b>{self.patient}</b>"
			)

	def on_submit(self):
		if self.is_non_nhif_patient and self.appointment_no:
			enc = frappe.qb.DocType("Patient Encounter")
			encounters = (
				frappe.qb.from_(enc)
				.select(enc.name, enc.duplicated)
				.where((enc.appointment == self.appointment_no) & (enc.docstatus == 1))
				.orderby(enc.creation)
			).run(as_dict=True)
			if len(encounters) == 0:
				return

			self.update_cash_limit_effect_to_encounters(encounters)

			self.create_insurance_items(encounters)

	def on_cancel(self):
		if self.is_cash_inpatient and self.inpatient_record:
			old_cash_limit = frappe.get_cached_value("Patient", {"name": self.patient}, "cash_limit")
			frappe.db.set_value(
				"Inpatient Record",
				self.inpatient_record,
				"cash_limit",
				old_cash_limit,
			)

		if self.is_non_nhif_patient and self.appointment_no:
			insurance_subscription = frappe.get_cached_value(
				"Patient Appointment",
				{"name": self.appointment_no},
				"insurance_subscription",
			)
			coverage_plan = frappe.get_cached_value(
				"Healthcare Insurance Subscription",
				insurance_subscription,
				"healthcare_insurance_coverage_plan",
			)
			old_daily_limit = frappe.get_cached_value(
				"Healthcare Insurance Coverage Plan",
				coverage_plan,
				"daily_limit",
			)
			frappe.db.set_value(
				"Patient Appointment",
				self.appointment_no,
				"daily_limit",
				old_daily_limit,
			)

	def set_missing_values(self):
		encounters = frappe.get_all(
			"Patient Encounter",
			filters={"appointment": self.appointment_no, "duplicated": 0},
			fields=[
				"name",
				"encounter_date",
				"inpatient_record",
				"mode_of_payment",
				"insurance_company",
				"current_total",
				"previous_total",
				"daily_limit",
			],
			order_by="encounter_date desc",
			page_length=1,
		)

		if len(encounters) > 0:
			if encounters[0]["mode_of_payment"] and encounters[0]["inpatient_record"]:
				self.inpatient_record = encounters[0]["inpatient_record"]
				self.is_cash_inpatient = 1
				self.previous_cash_limit = frappe.get_cached_value(
					"Inpatient Record", self.inpatient_record, "cash_limit"
				)
				self.current_total_deposit = -1 * (
					get_balance_on(
						party_type="Customer",
						party=self.patient_name,
						company=self.company,
					)
				)

			if encounters[0]["insurance_company"]:
				self.is_non_nhif_patient = 1
				self.insurance_company = encounters[0]["insurance_company"]
				self.previous_daily_limit = encounters[0]["daily_limit"]
				self.current_total_cost = encounters[0]["current_total"] + encounters[0]["previous_total"]

	def update_cash_limit_effect_to_encounters(self, encounters):
		"""Update the cash limit effect to all encounters related to the appointment"""

		table_map = [
			"lab_test_prescription",
			"radiology_procedure_prescription",
			"procedure_prescription",
			"drug_prescription",
			"therapies",
		]
		for encounter in encounters:
			encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter.name)
			for table_field in table_map:
				if encounter_doc.get(table_field):
					for item_row in encounter_doc.get(table_field):
						if item_row.hms_tz_is_limit_exceeded == 1:
							item_row.db_set("hms_tz_is_limit_exceeded", 0)
							item_row.db_set("is_cancelled", 0)

			encounter_doc.reload()
			if encounter.get("duplicated") == 0:
				encounter_doc.daily_limit = self.daily_limit
				validate_totals(encounter_doc, method="validate", show_alert=False)

				encounter_doc.db_update_all()
				encounter_doc.reload()

	def create_insurance_items(self, encounters):
		"""Create insurance items for all encounters related to the appointment"""

		for encounter in encounters:
			encounter_doc = frappe.get_doc("Patient Encounter", encounter.name)
			create_service_request(doc_obj=encounter_doc)
