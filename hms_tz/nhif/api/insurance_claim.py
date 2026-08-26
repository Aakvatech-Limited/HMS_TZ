# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe import _

from hms_tz.nhif.api.healthcare_utils import get_item_rate
from hms_tz.nhif.api.patient_appointment import get_item_price


def set_patient_encounter(doc, method):
	if doc.reference_dn:
		reference_doc = frappe.get_cached_doc(doc.reference_dt, doc.reference_dn)
		if reference_doc.parenttype and reference_doc.parenttype == "Patient Encounter":
			doc.order_encounter = reference_doc.parent
		elif doc.reference_dt == "Healthcare Service Order":
			doc.order_encounter = reference_doc.order_group


def set_price(doc, method):
	if not doc.insurance_subscription:
		return
	price_list = None
	price_list_rate = None
	if doc.reference_dt == "Healthcare Service Order":
		company, hso_prescribed = frappe.get_cached_value(
			doc.reference_dt, doc.reference_dn, ["company", "prescribed"]
		)
		if hso_prescribed:
			return
	elif doc.reference_dt in [
		"Patient Appointment",
		"Patient Encounter",
		"Lab Test",
		"Radiology Examination",
		"Clinical Procedure",
	]:
		company = frappe.get_cached_value(doc.reference_dt, doc.reference_dn, "company")
	else:
		company = frappe.defaults.get_user_default("Company")
		if not company:
			frappe.msgprint(_("Default company not found for this user"), alert=True)
			return
	if doc.insurance_subscription:
		if price_list:
			price_list_rate = get_item_rate(
				doc.service_item,
				company,
				doc.insurance_subscription,
				doc.insurance_company,
			)
			if price_list_rate and price_list_rate != 0:
				price_list_rate = get_item_price(doc.service_item, price_list, company)
				doc.price_list_rate = price_list_rate
				return
			if price_list_rate == 0:
				frappe.throw(_(f"Please set Price List for item: {doc.service_item}"))
