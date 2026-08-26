# Copyright (c) 2015, ESS LLP and Contributors
# See license.txt

import unittest

import frappe
from erpnext import get_default_company
from frappe.utils import getdate, nowtime
from healthcare.healthcare.doctype.healthcare_settings.healthcare_settings import (
	get_income_account,
	get_receivable_account,
)

from hms_tz.hms_tz.doctype.lab_test.lab_test import create_multiple
from hms_tz.hms_tz.doctype.patient_appointment.test_patient_appointment import create_patient


class TestLabTest(unittest.TestCase):
	def test_lab_test_item(self):
		lab_template = create_lab_test_template()
		self.assertTrue(frappe.db.exists("Item", lab_template.item))
		self.assertEqual(
			frappe.db.get_value(
				"Item Price",
				{"item_code": lab_template.item},
				"price_list_rate",
			),
			lab_template.lab_test_rate,
		)

		lab_template.disabled = 1
		lab_template.save()
		self.assertEqual(frappe.db.get_value("Item", lab_template.item, "disabled"), 1)

		lab_template.reload()

		lab_template.disabled = 0
		lab_template.save()

	def test_descriptive_lab_test(self):
		lab_template = create_lab_test_template()

		# blank result value not allowed as per template
		lab_test = create_lab_test(lab_template)
		lab_test.descriptive_test_items[0].result_value = 12
		lab_test.descriptive_test_items[2].result_value = 1
		lab_test.save()
		self.assertRaises(frappe.ValidationError, lab_test.submit)

	def test_sample_collection(self):
		lab_template = create_lab_test_template()

		lab_test = create_lab_test(lab_template)
		lab_test.descriptive_test_items[0].result_value = 12
		lab_test.descriptive_test_items[1].result_value = 1
		lab_test.descriptive_test_items[2].result_value = 2.3
		lab_test.save()

		# sample collection is always created when template has sample and sample_qty
		lab_test.reload()
		self.assertIsNotNone(lab_test.sample)
		self.assertTrue(frappe.db.exists("Sample Collection", {"sample": lab_template.sample}))

	def test_create_lab_tests_from_sales_invoice(self):
		sales_invoice = create_sales_invoice()
		create_multiple("Sales Invoice", sales_invoice.name)
		sales_invoice.reload()
		self.assertIsNotNone(sales_invoice.items[0].reference_dn)
		self.assertIsNotNone(sales_invoice.items[1].reference_dn)

	def test_create_lab_tests_from_patient_encounter(self):
		patient_encounter = create_patient_encounter()
		create_multiple("Patient Encounter", patient_encounter.name)
		patient_encounter.reload()
		self.assertTrue(patient_encounter.lab_test_prescription[0].lab_test_created)
		self.assertTrue(patient_encounter.lab_test_prescription[0].lab_test_created)


def _ensure_item_price(template):
	"""Ensure that the template's Item and Item Price exist (may have been rolled back by a prior test)."""
	from healthcare.healthcare.doctype.clinical_procedure_template.clinical_procedure_template import (
		make_item_price,
	)

	if not template.item:
		from healthcare.healthcare.doctype.lab_test_template.lab_test_template import (
			create_item_from_template,
		)

		create_item_from_template(template)
		template.reload()

	if not frappe.db.exists("Item", template.item):
		from healthcare.healthcare.doctype.lab_test_template.lab_test_template import (
			create_item_from_template,
		)

		template.db_set("item", "")
		create_item_from_template(template)
		template.reload()

	if template.is_billable and template.lab_test_rate:
		if not frappe.db.get_value("Item Price", {"item_code": template.item}):
			make_item_price(template.item, template.lab_test_rate)


def create_lab_test_template(test_sensitivity=0, sample_collection=1):
	medical_department = create_medical_department()
	if frappe.db.exists("Lab Test Template", "Insulin Resistance"):
		template = frappe.get_doc("Lab Test Template", "Insulin Resistance")
		_ensure_item_price(template)
		return template
	template = frappe.new_doc("Lab Test Template")
	template.lab_test_name = "Insulin Resistance"
	template.abbr = "IR"
	template.lab_test_template_type = "Descriptive"
	template.lab_test_code = "Insulin Resistance"
	template.lab_test_group = "Services"
	template.department = medical_department
	template.is_billable = 1
	template.lab_test_description = "Insulin Resistance"
	template.lab_test_rate = 2000
	template.points_of_care = "Laboratory"

	for entry in ["FBS", "Insulin", "IR"]:
		template.append(
			"descriptive_test_templates",
			{"particulars": entry, "allow_blank": 1 if entry == "IR" else 0},
		)

	if test_sensitivity:
		template.sensitivity = 1

	if sample_collection:
		template.sample = create_lab_test_sample()
		template.sample_qty = 5.0

	# company_options is mandatory
	company = get_default_company()
	service_unit = frappe.db.get_value(
		"Healthcare Service Unit", {"company": company}, "name"
	) or frappe.db.get_value("Healthcare Service Unit", {}, "name")
	template.append(
		"company_options",
		{
			"company": company,
			"service_unit": service_unit,
		},
	)

	template.save()
	return template


def create_blood_test_template(medical_department):
	"""Create a Blood Test lab test template with hms_tz-specific mandatory fields
	(abbr, company_options, points_of_care) set before saving."""
	if frappe.db.exists("Lab Test Template", "Blood Test"):
		template = frappe.get_doc("Lab Test Template", "Blood Test")
		needs_save = False
		if not template.get("abbr"):
			template.abbr = "BT"
			needs_save = True
		if not template.get("points_of_care"):
			template.points_of_care = "Laboratory"
			needs_save = True
		if not template.get("company_options"):
			company = get_default_company()
			service_unit = frappe.db.get_value(
				"Healthcare Service Unit", {"company": company}, "name"
			) or frappe.db.get_value("Healthcare Service Unit", {}, "name")
			template.append(
				"company_options",
				{"company": company, "service_unit": service_unit},
			)
			needs_save = True
		if needs_save:
			template.save(ignore_permissions=True)
		_ensure_item_price(template)
		return template

	template = frappe.new_doc("Lab Test Template")
	template.lab_test_name = "Blood Test"
	template.lab_test_code = "Blood Test"
	template.lab_test_group = "Services"
	template.department = medical_department
	template.is_billable = 1
	template.lab_test_rate = 2000
	template.abbr = "BT"
	template.points_of_care = "Laboratory"
	company = get_default_company()
	service_unit = frappe.db.get_value(
		"Healthcare Service Unit", {"company": company}, "name"
	) or frappe.db.get_value("Healthcare Service Unit", {}, "name")
	template.append(
		"company_options",
		{"company": company, "service_unit": service_unit},
	)
	template.save()
	return template


def create_medical_department():
	medical_department = frappe.db.exists("Medical Department", "_Test Medical Department")
	if not medical_department:
		medical_department = frappe.new_doc("Medical Department")
		medical_department.department = "_Test Medical Department"
		medical_department.save()
		medical_department = medical_department.name

	return medical_department


def create_lab_test(lab_template):
	patient = create_patient()
	lab_test = frappe.new_doc("Lab Test")
	lab_test.template = lab_template.name
	lab_test.patient = patient
	lab_test.patient_sex = "Female"
	lab_test.save()

	return lab_test


def create_lab_test_sample():
	blood_sample = frappe.db.exists("Lab Test Sample", "Blood Sample")
	if blood_sample:
		return blood_sample

	sample = frappe.new_doc("Lab Test Sample")
	sample.sample = "Blood Sample"
	sample.sample_uom = "U/ml"
	sample.save()

	return sample.name


def create_sales_invoice():
	patient = create_patient()
	medical_department = create_medical_department()
	insulin_resistance_template = create_lab_test_template()
	blood_test_template = create_blood_test_template(medical_department)

	company = get_default_company()
	sales_invoice = frappe.new_doc("Sales Invoice")
	sales_invoice.patient = patient
	sales_invoice.customer = frappe.get_cached_value("Patient", patient, "customer")
	sales_invoice.due_date = getdate()
	sales_invoice.company = company
	sales_invoice.debit_to = get_receivable_account(company)
	sales_invoice.is_pos = 0

	tests = [insulin_resistance_template, blood_test_template]
	for entry in tests:
		sales_invoice.append(
			"items",
			{
				"item_code": entry.item,
				"item_name": entry.lab_test_name,
				"description": entry.lab_test_description,
				"qty": 1,
				"uom": "Nos",
				"conversion_factor": 1,
				"income_account": get_income_account(None, company),
				"rate": entry.lab_test_rate,
				"amount": entry.lab_test_rate,
			},
		)

	sales_invoice.set_missing_values()

	sales_invoice.submit()
	return sales_invoice


def create_patient_encounter():
	patient = create_patient()
	medical_department = create_medical_department()
	insulin_resistance_template = create_lab_test_template()
	blood_test_template = create_blood_test_template(medical_department)

	company = get_default_company()
	patient_encounter = frappe.new_doc("Patient Encounter")
	patient_encounter.patient = patient
	patient_encounter.practitioner = create_practitioner()
	patient_encounter.encounter_date = getdate()
	patient_encounter.encounter_time = nowtime()
	patient_encounter.company = company
	patient_encounter.healthcare_service_unit = frappe.db.get_value(
		"Healthcare Service Unit",
		{"is_group": 0, "company": company},
		"name",
	) or frappe.db.get_value("Healthcare Service Unit", {"is_group": 0}, "name")

	tests = [insulin_resistance_template, blood_test_template]
	for entry in tests:
		patient_encounter.append(
			"lab_test_prescription",
			{
				"lab_test_code": entry.name,
				"lab_test_name": entry.lab_test_name,
				"amount": entry.lab_test_rate,
			},
		)

	patient_encounter.submit()
	return patient_encounter


def create_practitioner():
	practitioner = frappe.db.exists("Healthcare Practitioner", "_Test Healthcare Practitioner")

	if not practitioner:
		company = get_default_company()
		practitioner = frappe.new_doc("Healthcare Practitioner")
		practitioner.first_name = "_Test Healthcare Practitioner"
		practitioner.gender = "Female"
		practitioner.op_consulting_charge = 500
		practitioner.inpatient_visit_charge = 500
		practitioner.national_id = "19900101-00001-00001-01"
		practitioner.abbreviation = "THP"
		practitioner.hms_tz_company = company
		practitioner.save(ignore_permissions=True)
		practitioner = practitioner.name

	return practitioner
