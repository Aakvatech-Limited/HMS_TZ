# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

"""
Global Consumable API — reusable backend methods for the consumable dialog.
Can be called from any DocType's client script (Nurse Record, Clinical Procedure, etc.)
"""

import json

import frappe
from erpnext.accounts.utils import get_balance_on
from frappe import _
from frappe.utils import flt, nowdate, nowtime

from hms_tz.nhif.api.healthcare_utils import get_discount_percent, get_item_rate, get_mop_amount


@frappe.whitelist()
def get_consumable_item_details(
	item_code,
	company,
	payment_type,
	insurance_subscription=None,
	insurance_company=None,
	patient=None,
):
	"""
	Get item details including rate based on payment type.

	For Insurance: uses get_item_rate from healthcare_utils
	For Cash: uses get_mop_amount from healthcare_utils

	Returns: dict with rate, is_stock_item, item_name, uom, price_list
	"""
	if not item_code or not company:
		frappe.throw(_("Item Code and Company are required"))

	item_doc = frappe.get_cached_value(
		"Item",
		item_code,
		["item_name", "stock_uom", "is_stock_item"],
		as_dict=True,
	)
	if not item_doc:
		frappe.throw(_("Item {0} not found").format(item_code))

	result = {
		"item_name": item_doc.item_name,
		"uom": item_doc.stock_uom,
		"is_stock_item": item_doc.is_stock_item,
		"rate": 0,
		"price_list": "",
	}

	if payment_type == "Insurance" and insurance_subscription:
		try:
			# Apply discount for non-NHIF insurance
			discount_percent = 0
			if insurance_company and "NHIF" not in insurance_company:
				discount_percent = get_discount_percent(insurance_company)

			item_price_rate, price_list = get_item_rate(
				item_code,
				company,
				insurance_subscription,
				insurance_company,
				for_service_request=True,
			)

			rate = item_price_rate - (item_price_rate * (discount_percent / 100))
			result["rate"] = rate
			result["price_list"] = price_list

		except Exception as e:
			frappe.log_error(
				title="Consumable: get_item_rate error",
				message=str(e),
			)
			result["rate"] = 0
			result["error"] = str(e)

	elif payment_type == "Cash":
		try:
			rate = get_mop_amount(
				item_code,
				mop="",
				company=company,
				patient=patient,
			)
			result["rate"] = rate or 0

		except Exception as e:
			frappe.log_error(
				title="Consumable: get_mop_amount error",
				message=str(e),
			)
			result["rate"] = 0
			result["error"] = str(e)

	return result


@frappe.whitelist()
def get_nhif_coverage_percent(
	appointment, company, item_code, insurance_coverage_plan, insurance_company, payment_type
):
	"""
	Get NHIF Co-Payment percent covered for the given item.

	Returns percent_covered (default 100 if not found or non-NHIF).
	"""
	if not item_code:
		frappe.throw(_("Item Code is required"))

	if payment_type != "Insurance":
		return 100

	if not insurance_company or "NHIF" not in insurance_company:
		return 100

	if not insurance_coverage_plan:
		frappe.throw(_("Insurance Coverage Plan is required"))

	scheme_id = frappe.get_cached_value(
		"Healthcare Insurance Coverage Plan",
		insurance_coverage_plan,
		"nhif_scheme_id",
	)
	if not scheme_id:
		frappe.throw(_(f"Scheme ID not found for {insurance_coverage_plan}"))

	ref_code = ""
	code_list = frappe.db.get_all(
		"Item Customer Detail",
		filters={"parent": item_code, "customer_name": "NHIF"},
		fields=["ref_code"],
	)
	if len(code_list) > 0:
		ref_code = code_list[0].ref_code

	if not ref_code:
		frappe.throw(_(f"Item: {item_code} does not have an NHIF Reference Code"))

	is_covered = frappe.db.exists(
		"NHIF Price Package",
		{
			"company": company,
			"itemcode": ref_code,
			"schemeid": scheme_id,
		},
	)

	if not is_covered:
		frappe.throw(_(f"Item: {item_code} is not covered by NHIF"))

	years_of_insurance = frappe.get_cached_value(
		"Patient Appointment",
		appointment,
		"years_of_insurance",
	)

	percent_details = frappe.get_cached_value(
		"NHIF Co-Payment Item",
		{
			"itemcode": ref_code,
			"schemeid": scheme_id,
			"yearno": years_of_insurance,
		},
		["percentcovered", "name"],
		as_dict=True,
	)

	if not percent_details:
		return 100

	return percent_details.percentcovered or 0


@frappe.whitelist()
def validate_patient_deposit(patient, company, appointment, inpatient_record, total_amount):
	"""
	Validate patient deposit including all costs (encounter, IPD, consumables).

	Called from the consumable dialog before creating the record.
	Returns dict with has_sufficient_balance, current_balance, required_amount.
	"""
	total_amount = flt(total_amount)

	if not inpatient_record:
		inpatient_record = frappe.db.get_value("Patient", patient, "inpatient_record")

	customer = frappe.get_cached_value("Patient", patient, "customer")
	if not customer:
		return {
			"has_sufficient_balance": False,
			"current_balance": 0,
			"required_amount": total_amount,
			"error": _(f"Patient {patient} does not have a linked Customer"),
		}

	patient_name = frappe.get_cached_value("Patient", patient, "patient_name")

	if inpatient_record:
		# Use the consolidated function which includes encounter + IPD + consumable costs
		from hms_tz.nhif.api.patient_encounter import validate_patient_balance_vs_patient_costs

		validate_patient_balance_vs_patient_costs(
			patient=patient,
			patient_name=patient_name,
			appointment=appointment or "",
			inpatient_record=inpatient_record,
			company=company,
			caller="Consumable Dialog",
		)

	# Return deposit balance for the dialog UI
	deposit_balance = get_balance_on(party_type="Customer", party=customer, company=company)
	available_balance = -1 * deposit_balance

	return {
		"has_sufficient_balance": available_balance >= total_amount,
		"current_balance": available_balance,
		"required_amount": total_amount - available_balance if available_balance < total_amount else 0,
	}


@frappe.whitelist()
def create_consumable_record(args):
	"""
	Create, save, and submit a Consumable Record from the dialog.

	Args:
	    args: JSON string with:
	        - patient, company, appointment, encounter
	        - payment_type
	        - insurance_subscription, insurance_company, insurance_coverage_plan
	        - prescribed_by
	        - source_doctype, source_docname
	        - items: list of dicts with item_code, qty_requested, warehouse, rate,
	          payment_type, percent_covered, is_billable, insurance_subscription,
	          insurance_company, insurance_coverage_plan

	Returns: dict with name, delivery_note, has_pending_payment, message
	"""
	if isinstance(args, str):
		args = json.loads(args)

	args = frappe._dict(args)

	doc = frappe.new_doc("Consumable Record")
	doc.patient = args.patient
	doc.company = args.company
	doc.appointment = args.get("appointment")
	doc.encounter = args.get("encounter")
	doc.posting_date = nowdate()
	doc.posting_time = nowtime()
	doc.payment_type = args.payment_type
	doc.prescribed_by = args.get("prescribed_by")
	doc.source_doctype = args.get("source_doctype")
	doc.source_docname = args.get("source_docname")
	doc.insurance_subscription = args.get("insurance_subscription")
	doc.insurance_company = args.get("insurance_company")
	doc.insurance_coverage_plan = args.get("insurance_coverage_plan")

	for item_data in args.get("items", []):
		item_data = frappe._dict(item_data)
		row = doc.append("items", {})
		row.item_code = item_data.item_code
		row.qty_requested = flt(item_data.qty_requested) or 1
		row.warehouse = item_data.warehouse
		row.rate = flt(item_data.rate)
		row.price_list = item_data.get("price_list")
		row.payment_type = item_data.get("payment_type") or args.payment_type
		row.percent_covered = flt(item_data.get("percent_covered")) or 100
		row.is_billable = 1 if item_data.get("is_billable") in [1, True, "1"] else 0
		row.insurance_subscription = item_data.get("insurance_subscription") or args.get(
			"insurance_subscription"
		)
		row.insurance_company = item_data.get("insurance_company") or args.get("insurance_company")
		row.insurance_coverage_plan = item_data.get("insurance_coverage_plan") or args.get(
			"insurance_coverage_plan"
		)
		row.uom = item_data.get("uom")

	doc.insert(ignore_permissions=True)
	doc.reload()

	result = {
		"name": doc.name,
		"delivery_note": "",
		"has_pending_payment": 0,
		"message": _("Consumable Record {0} created successfully.").format(doc.name),
	}

	# Try to submit
	try:
		doc.submit()
		doc.reload()
		result["delivery_note"] = doc.delivery_note or ""
		result["has_pending_payment"] = doc.has_pending_payment
		if doc.has_pending_payment:
			result["message"] = _(
				"Consumable Record {0} created. Some items require cash payment before dispensing."
			).format(doc.name)
		elif doc.delivery_note:
			result["message"] = _("Consumable Record {0} created. Delivery Note {1} created (Draft).").format(
				doc.name, doc.delivery_note
			)
	except frappe.ValidationError as e:
		# Submission blocked (e.g., insufficient deposit)
		result["message"] = str(e)
		result["has_pending_payment"] = 1

	return result


@frappe.whitelist()
def submit_consumable_record(consumable_record: str):
	"""Submit a Consumable Record by loading a fresh copy from DB.
	This avoids 'Document Modified' errors when the doc was modified
	after the calling page was loaded.
	"""
	doc = frappe.get_doc("Consumable Record", consumable_record)
	doc.submit()

	return {
		"name": doc.name,
		"status": doc.status,
		"delivery_note": doc.delivery_note or "",
	}
