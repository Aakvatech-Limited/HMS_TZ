# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import time

import frappe
from frappe.model.document import Document
from frappe.utils import nowdate, nowtime

from hms_tz.nhif.api.patient_appointment import make_encounter

try:
	from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
		get_income_account,
		get_receivable_account,
	)
except ImportError:
	from erpnext.healthcare.doctype.healthcare_settings.healthcare_settings import (
		get_income_account,
		get_receivable_account,
	)


class HealthcarePackageOrder(Document):
	def before_insert(self):
		self.set_missing_values()

	def validate(self):
		self.set_total_price()

	def before_submit(self):
		self.validate_consultaion_details()
		self.validate_payment()
		self.create_appointemnts()

	def on_submit(self):
		self.create_encounters()

	def set_missing_values(self):
		self.posting_date = nowdate()
		self.posting_time = nowtime()

	def set_total_price(self):
		price_of_services, price_package = frappe.get_cached_value(
			"Healthcare Package",
			self.healthcare_package,
			["total_price_of_services", "price_of_package"],
		)
		self.total_price = price_package if price_package > 0 else price_of_services

	def validate_consultaion_details(self):
		if len(self.consultations) == 0:
			frappe.throw("Please add consultation details")

		for row in self.consultations:
			if not row.consultation_item:
				frappe.throw(
					f"Please select a consultation item on RowNo: \
                        <b>{row.idx}</b>"
				)

			if not row.practitioner:
				frappe.throw(
					f"Please select a practitioner for consultation on \
                        RowNo: <b>{row.idx}</b>"
				)

	def validate_payment(self):
		if self.payment_type == "Insurance" and not self.insurance_subscription:
			frappe.throw("Please select an insurance subscription")

		if self.payment_type == "Cash":
			if not self.mode_of_payment:
				frappe.throw("Please select a mode of payment")

			if self.paid == 0 and not self.sales_invoice:
				frappe.throw("Please make payment for this order")

	def create_appointemnts(self):
		appointment_type = frappe.get_cached_value(
			"Appointment Type", {"visit_type_id": "1-Normal Visit"}, "name"
		)

		# create appointment with no consultation fee
		non_consultation_appointment = create_single_appointment(
			self, self.consultations[0], appointment_type
		)
		self.non_consultation_appointment = non_consultation_appointment

		# create appointment with consultation fee
		for row in self.consultations:
			consultation_appointment = create_single_appointment(self, row, appointment_type, True)
			row.appointment = consultation_appointment

	def create_encounters(self):
		if self.non_consultation_appointment:
			appointment_doc = frappe.get_cached_doc("Patient Appointment", self.non_consultation_appointment)
			encounter = make_encounter(appointment_doc, "patient_encounter")
			self.db_set("non_consultation_encounter", encounter, update_modified=False)
			self.update_encounter_details(encounter, True)

		for row in self.consultations:
			if row.appointment:
				appointment_doc = frappe.get_cached_doc("Patient Appointment", row.appointment)
				encounter = make_encounter(appointment_doc, "patient_encounter")
				row.db_set("encounter", encounter, update_modified=False)
				self.update_encounter_details(encounter)

	def update_encounter_details(self, encounter, has_items=False):
		package_doc = frappe.get_cached_doc("Healthcare Package", self.healthcare_package)
		encounter_doc = frappe.get_cached_doc("Patient Encounter", encounter)
		update_encounter_items(encounter_doc, package_doc, has_items)
		encounter_doc.save(ignore_permissions=True)

		if has_items:
			encounter_doc.submit()
			time.sleep(10)
			frappe.db.set_value(
				encounter_doc.doctype,
				encounter_doc.name,
				{"finalized": 1, "encounter_type": "Final"},
			)

	@frappe.whitelist()
	def create_sales_invoice(self):
		self = frappe.parse_json(self)
		invoice = frappe.new_doc("Sales Invoice")
		invoice.patient = self.patient
		invoice.customer = frappe.get_cached_value("Patient", self.patient, "customer")
		invoice.due_date = nowdate()
		invoice.company = self.company
		invoice.debit_to = get_receivable_account(self.company)
		invoice.healthcare_practitioner = "Healthcare Package"

		item = invoice.append("items", {})
		item.item_code = "Healthcare Package"
		item.description = "Healthcare Package: " + self.healthcare_package
		item.rate = self.total_price
		item.amount = self.total_price
		item.qty = 1
		item.cost_center = frappe.get_cached_value("Company", self.company, "cost_center")
		item.reference_dt = "Healthcare Package Order"
		item.reference_dn = self.name
		item.income_account = get_income_account("Healthcare Package", self.company)

		if self.mode_of_payment and self.total_price > 0:
			invoice.is_pos = 1
			payment = invoice.append("payments", {})
			payment.mode_of_payment = self.mode_of_payment
			payment.amount = self.total_price

		invoice.set_taxes()
		invoice.set_missing_values(for_validate=True)
		invoice.flags.ignore_mandatory = True
		invoice.save()
		invoice.calculate_taxes_and_totals()
		invoice.submit()
		self.paid = 1
		self.sales_invoice = invoice.name
		self.save(ignore_permissions=True)
		frappe.msgprint(f"Sales Invoice {invoice.name} created")
		return True


def create_single_appointment(doc, row, appointment_type, is_pratictioner_consultation=False):
	appointment = frappe.new_doc("Patient Appointment")
	appointment.company = doc.company
	appointment.patient = doc.patient
	appointment.patient_name = doc.patient_name
	appointment.appointment_date = nowdate()
	appointment.appointment_time = nowtime()
	appointment.appointment_type = appointment_type
	if doc.payment_type == "Insurance":
		appointment.insurance_subscription = doc.insurance_subscription
		appointment.authorization_number = doc.authorization_number
	if doc.payment_type == "Cash":
		appointment.mode_of_payment = doc.mode_of_payment
		appointment.invoiced = 1
	appointment.department = row.department
	appointment.billing_item = row.consultation_item
	if is_pratictioner_consultation:
		appointment.paid_amount = row.consultation_fee
		appointment.practitioner = row.practitioner
		appointment.practitioner_name = row.practitioner_name
	else:
		appointment.practitioner = "Healthcare Package"
		appointment.practitioner_name = "Healthcare Package"
		appointment.paid_amount = 0
	appointment.healthcare_package_order = doc.name
	appointment.save(ignore_permissions=True)

	return appointment.name


def update_encounter_items(encounter_doc, package_doc, has_items):
	item_table = "<p>"
	template_map = {
		"Lab Test Template": "Lab Item",
		"Radiology Examination Template": "Radiology Item",
		"Clinical Procedure Template": "Procedure Item",
		"Therapy Type": "Therapy Item",
		"Medication": "Drug Item",
	}
	if has_items:
		for field_name in [
			"patient_encounter_preliminary_diagnosis",
			"patient_encounter_final_diagnosis",
		]:
			encounter_doc.append(
				field_name,
				{
					"code_value": "ICD-10 R69",
					"code": "R69",
					"description": "Unknown and unspecified causes of morbidity",
					"mtuha": "Other",
				},
			)

	for row in package_doc.services:
		item_table += f"{template_map[row.healthcare_service_type]}: {row.healthcare_service}<br>"
		if has_items:
			for d in get_table_field_map():
				if row.healthcare_service_type == d["template"]:
					new_row = {
						d["field"]: row.healthcare_service,
						"prescribe": 1 if encounter_doc.mode_of_payment else 0,
						"medical_code": "ICD-10 R69" + "\n " + "Unknown and unspecified causes of morbidity",
						"amount": row.service_price,
					}

					if row.healthcare_service_type == "Radiology Examination Template":
						new_row["radiology_test_comment"] = "Healthcare Package"

					if row.healthcare_service_type == "Medication":
						new_row["quantity"] = row.quantity
						new_row["dosage"] = row.dosage
						new_row["period"] = row.period
						new_row["healthcare_service_unit"] = encounter_doc.default_healthcare_service_unit

					if row.healthcare_service_type == "Therapy Type":
						new_row["no_of_sessions"] = 1

					encounter_doc.append(d["table"], new_row)
	item_table += "</p>"
	encounter_doc.examination_detail = item_table


def get_table_field_map():
	field_table_map = [
		{
			"template": "Lab Test Template",
			"table": "lab_test_prescription",
			"field": "lab_test_code",
		},
		{
			"template": "Radiology Examination Template",
			"table": "radiology_procedure_prescription",
			"field": "radiology_examination_template",
		},
		{
			"template": "Clinical Procedure Template",
			"table": "procedure_prescription",
			"field": "procedure",
		},
		{
			"template": "Therapy Type",
			"table": "therapies",
			"field": "therapy_type",
		},
		{
			"template": "Medication",
			"table": "drug_prescription",
			"field": "drug_code",
		},
	]
	return field_table_map
