# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe

# from frappe import _
from hms_tz.nhif.api.patient import get_card_verifier, get_nhif_patient_info


def before_insert(doc, method):
	validate_card_no(doc)
	validate_national_id(doc)


def validate(doc, method):
	validate_card_no(doc)
	validate_national_id(doc)


def on_submit(doc, method):
	set_insurance_card_detail_in_patient(doc)


def on_update_after_submit(doc, method):
	if method != "on_submit" and doc.is_active == 1:
		set_insurance_card_detail_in_patient(doc)


def on_cancel(doc, method):
	set_insurance_card_detail_in_patient(doc)


def validate_card_no(doc):
	if not doc.coverage_plan_card_number:
		return

	if doc.is_dependant and doc.principal:
		# Dependants can use same card number as the principal member for Non NHIF patients
		return

	filters = {
		"is_active": 1,
		"docstatus": 1,
		"coverage_plan_card_number": doc.coverage_plan_card_number,
		"name": ["!=", doc.name or ""],
	}

	if doc.get("company"):
		filters["company"] = doc.company

	his = frappe.db.get_all(
		"Healthcare Insurance Subscription",
		filters=filters,
		fields=["name", "patient_name"],
	)
	if len(his) > 0:
		frappe.throw(
			f"Cardno: <b>{doc.coverage_plan_card_number}</b> used with HIS: {his[0].name} patient: <b>{his[0].patient_name}</b>, Please change Cardno to Proceed"
		)


def validate_national_id(doc):
	if not doc.national_id:
		return

	if doc.is_dependant and doc.principal:
		# Dependants can use same national ID number as the principal member for Non NHIF patients
		return

	filters = {
		"is_active": 1,
		"docstatus": 1,
		"national_id": doc.national_id,
		"name": ["!=", doc.name],
	}

	if doc.get("company"):
		filters["company"] = doc.company

	his = frappe.db.get_all(
		"Healthcare Insurance Subscription",
		filters=filters,
		fields=["name", "patient_name"],
	)
	if len(his) > 0:
		frappe.throw(
			f"NationalID: <b>{doc.national_id}</b> used with HIS: {his[0].name} Patient: <b>{his[0].patient_name}</b>, Please change NationalID to Proceed"
		)


def set_insurance_card_detail_in_patient(doc):
	if frappe.flags.auto_his:
		return

	if doc.is_dependant and doc.principal:
		return

	his_list = frappe.db.get_all(
		"Healthcare Insurance Subscription",
		filters={
			"patient": doc.patient,
			"docstatus": 1,
			"is_active": 1,
		},
		fields=["coverage_plan_card_number"],
		group_by="coverage_plan_card_number",
	)
	str_coverage_plan_card_number = ""
	for card in his_list:
		if card.coverage_plan_card_number:
			str_coverage_plan_card_number += card.coverage_plan_card_number + ", "

	frappe.db.set_value(
		"Patient",
		doc.patient,
		{
			"insurance_card_detail": str_coverage_plan_card_number[:-2],
			"card_no": doc.coverage_plan_card_number,
		},
	)


@frappe.whitelist()
def check_patient_info(
	patient,
	patient_name,
	card_no=None,
	national_id=None,
	ref_doctype=None,
	ref_docname=None,
):
	if not patient or (not card_no and not national_id):
		return

	patient_info = get_nhif_patient_info(
		card_no=card_no,
		national_id=national_id,
		ref_doctype=ref_doctype,
		ref_docname=ref_docname,
		check_patient_info_from_his=True,
	)

	if patient_info and patient_name != patient_info.get("FullName"):
		patient_doc = frappe.get_cached_doc("Patient", patient)
		patient_doc.patient_name = patient_info.get("FullName")
		patient_doc.first_name = patient_info.get("FirstName")
		patient_doc.middle_name = patient_info.get("MiddleName")
		patient_doc.last_name = patient_info.get("LastName")
		patient_doc.sex = patient_info.get("Gender")
		patient_doc.dob = patient_info.get("DateOfBirth")
		# patient_doc.product_code = patient_info.get("ProductCode")
		patient_doc.scheme_id = patient_info.get("SchemeID")
		patient_doc.nhif_employername = patient_info.get("EmployerName")
		patient_doc.membership_no = patient_info.get("membership_no")
		patient_doc.save(ignore_permissions=True)

		verifier_entry = get_card_verifier(patient_doc, card_no, national_id)
		verifier_entry["full_name"] = patient_info.get("FullName")

		return verifier_entry

	return None
