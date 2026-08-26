# Copyright (c) 2013, Aakvatech and contributors
# For license information, please see license.txt

import calendar

import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters):
	data = []
	columns = get_columns()

	nhif_summary = get_data(filters)
	if nhif_summary:
		company_info = frappe.get_all(
			"Company",
			filters={"name": nhif_summary[0]["facility_name"]},
			fields=["p_o_box", "city"],
		)

		nhif_summary[0]["address"] = company_info[0]["p_o_box"]
		nhif_summary[0]["region"] = company_info[0]["city"]
		nhif_summary[0]["district"] = "Ilala"

		data += nhif_summary

	return columns, data


def get_columns():
	columns = [
		{"fieldname": "male", "label": _("Male"), "fieldtype": "Data"},
		{"fieldname": "female", "label": _("Female"), "fieldtype": "Data"},
		{
			"fieldname": "amount_claimed",
			"label": _("Total Amount Claimed"),
			"fieldtype": "Currency",
		},
		{
			"fieldname": "consultation",
			"label": _("Consultation"),
			"fieldtype": "Currency",
		},
		{
			"fieldname": "diagnostic_examination",
			"label": _("Diagnostic Examination"),
			"fieldtype": "Currency",
		},
		{
			"fieldname": "surgical_produceral_charge",
			"label": _("Surgical and Procedural Charges"),
			"fieldtype": "Currency",
		},
		{
			"fieldname": "medicine",
			"label": _("Medication and Consumables"),
			"fieldtype": "Currency",
		},
		{
			"fieldname": "inpatient_charges",
			"label": _("Inpatient/Bed Charges"),
			"fieldtype": "Currency",
		},
	]
	return columns


def get_data(filters):
	details = []
	parent_list = []

	male_count = female_count = total_amount = total_amount_for_out_patient = total_amount_for_inpatient = 0
	consultation = diagnostic_examination = surgical_produceral_charge = medicine = inpatient_charges = 0

	claims = frappe.get_all(
		"NHIF Patient Claim",
		filters=[
			["docstatus", "=", 1],
			["company", "=", filters.get("company")],
			["claim_month", "=", filters.get("submit_claim_month")],
			["claim_year", "=", filters.get("submit_claim_year")],
		],
		fields=["name", "company", "facility_code", "gender", "total_amount"],
	)
	if not claims:
		return []

	facility_code = claims[0]["facility_code"]
	facility_name = claims[0]["company"]

	for claim_doc in claims:
		parent_list.append(claim_doc.name)

		if claim_doc.gender == "Male":
			male_count += 1
		else:
			female_count += 1

	items = frappe.get_all(
		"NHIF Patient Claim Item",
		filters={"parent": ["in", parent_list]},
		fields=["ref_doctype", "amount_claimed"],
	)

	for item in items:
		if item.ref_doctype == "Patient Appointment":
			consultation += item.amount_claimed
		elif item.ref_doctype == "Drug Prescription":
			medicine += item.amount_claimed
		elif (item.ref_doctype == "Lab Prescription") | (
			item.ref_doctype == "Radiology Procedure Prescription"
		):
			diagnostic_examination += item.amount_claimed
		elif (item.ref_doctype == "Procedure Prescription") | (item.ref_doctype == "Therapy Plan Detail"):
			surgical_produceral_charge += item.amount_claimed
		else:
			inpatient_charges += item.amount_claimed

	total_amount = (
		consultation + medicine + diagnostic_examination + surgical_produceral_charge + inpatient_charges
	)

	first_day_of_month = getdate(
		str(filters.get("submit_claim_year")) + "-" + str(filters.get("submit_claim_month")) + "-1"
	)

	last_day_of_month = first_day_of_month.replace(
		day=calendar.monthrange(first_day_of_month.year, first_day_of_month.month)[1]
	)

	details.append(
		{
			"from_date": first_day_of_month,
			"to_date": last_day_of_month,
			"accreditation_no": "01440",
			"ownership": "Religious/NGO",
			"facility_name": facility_name,
			"facility_code": facility_code,
			"male": male_count,
			"female": female_count,
			"total_patient": male_count + female_count,
			"amount_claimed": total_amount,
			"consultation": consultation,
			"diagnostic_examination": diagnostic_examination,
			"surgical_produceral_charge": surgical_produceral_charge,
			"medicine": medicine,
			"inpatient_charges": inpatient_charges,
			"total_amount_for_out_patient": total_amount_for_out_patient,
			"total_amount_for_inpatient": total_amount_for_inpatient,
		}
	)

	return details
