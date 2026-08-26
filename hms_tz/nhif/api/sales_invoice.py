# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.query_builder import DocType

from hms_tz.nhif.api.healthcare_utils import (
	create_individual_lab_test,
	create_individual_procedure_prescription,
	create_individual_radiology_examination,
	create_therapy_plan,
	update_dimensions,
	update_invoice_reference_in_lrpmt_childs,
)
from hms_tz.nhif.api.sales_order import validate_stock_item


def validate(doc, method):
	for item in doc.items:
		if not item.is_free_item and item.amount == 0:
			frappe.throw(
				_(
					f"Amount of the healthcare service <b>'{item.item_name}'</b> \
                    cannot be ZERO. Please do not select this item and request \
                    Pricing team to resolve this."
				)
			)

		# do not validate stock for cash inpatient sales invoice
		if doc.get("enabled_auto_create_delivery_notes") == 0:
			continue

		validate_stock_item(item, item.warehouse, method)

	update_dimensions(doc)
	validate_create_delivery_note(doc)


def validate_create_delivery_note(doc):
	if not doc.patient:
		return
	if doc.get("enabled_auto_create_delivery_notes") == 0:
		return

	inpatient_record = frappe.get_cached_value("Patient", doc.patient, "inpatient_record")
	if inpatient_record:
		insurance_subscription = frappe.get_cached_value(
			"Inpatient Record", inpatient_record, "insurance_subscription"
		)
		if not insurance_subscription:
			if hasattr(doc, "enabled_auto_create_delivery_notes"):
				doc.enabled_auto_create_delivery_notes = 0


@frappe.whitelist()
def create_pending_healthcare_docs(doc_name):
	doc = frappe.get_cached_doc("Sales Invoice", doc_name)
	create_healthcare_docs(doc, "From Front End")


def before_submit(doc, method):
	if doc.is_pos and doc.outstanding_amount != 0:
		frappe.throw(
			_(
				"Sales invoice not paid in full.<BR><BR>Make sure that full paid amount is entered in <b>Mode of Payments table.</b>"
			)
		)

	if doc.hms_tz_discount_requested == 1 and doc.hms_tz_discount_status == "Pending":
		frappe.throw(
			_(
				"Patient Discount Request is still pending. Please wait for approval before submitting this invoice."
			)
		)

	# do not validate stock for cash inpatient sales invoice
	if getattr(doc, "enabled_auto_create_delivery_notes", 0) == 1:
		for row in doc.items:
			if frappe.get_cached_value("Item", row.item_code, "is_stock_item") == 1:
				validate_stock_item(row, row.warehouse, method)

	if doc.is_return == 1:
		reset_invoiced_status(doc)


def on_submit(doc, method):
	if doc.is_return == 1:
		reset_invoiced_status(doc)
		return

	create_healthcare_docs(doc, method)
	update_drug_prescription(doc)


def create_healthcare_docs(doc, method):
	if doc.docstatus != 1 or method not in ["on_submit", "From Front End"]:
		frappe.msgprint(
			_(
				f"No LRPMTs were created. Alert the IT Team!<b><br>DOCSTATUS = {doc.docstatus}<br>METHOD {method}</b>"
			)
		)
		return

	therapy_items = []
	service_request_ids = []
	consumable_item_ids = []
	if doc.get("items"):
		for item in doc.items:
			if not item.reference_dt or not item.reference_dn:
				continue

			# check if item is from Service Request
			# its service document will be created from Healthcare Service
			# Request
			if item.get("service_request"):
				frappe.db.set_value(
					"Healthcare Service Request Payment",
					item.get("service_request"),
					{
						"sales_invoice_number": doc.name,
						"invoiced": 1,
					},
				)
				service_request_ids.append(item.get("service_request"))
				continue

			child = frappe.get_doc(item.reference_dt, item.reference_dn)

			if item.reference_dt and item.reference_dt in [
				"Lab Prescription",
				"Radiology Procedure Prescription",
				"Procedure Prescription",
			]:
				patient_encounter_doc = frappe.get_doc("Patient Encounter", child.parent)
				if child.doctype == "Lab Prescription":
					create_individual_lab_test(patient_encounter_doc, child)
				elif child.doctype == "Radiology Procedure Prescription":
					create_individual_radiology_examination(patient_encounter_doc, child)
				elif child.doctype == "Procedure Prescription":
					create_individual_procedure_prescription(patient_encounter_doc, child)

				update_invoice_reference_in_lrpmt_childs(child, item)

			elif item.reference_dt and item.reference_dt == "Therapy Plan Detail":
				therapy_items.append(item)

			elif item.reference_dt and item.reference_dt in [
				"Inpatient Occupancy",
				"Inpatient Consultancy",
				"Consumable Item",
			]:
				update_invoice_reference_in_lrpmt_childs(child, item)

				if item.reference_dt == "Consumable Item":
					consumable_item_ids.append(item.reference_dn)

		create_therapy_plan(invoice_therapy_dict=therapy_items)

		if len(service_request_ids) > 0:
			hsrp = DocType("Healthcare Service Request Payment")
			healthcare_service_parents = (
				frappe.qb.from_(hsrp)
				.select(
					hsrp.parent.as_("service_request_no"),
				)
				.distinct()
				.where(hsrp.name.isin(service_request_ids))
			).run(as_dict=True)

			if len(healthcare_service_parents) > 0:
				for row in healthcare_service_parents:
					hsr_doc = frappe.get_cached_doc("Healthcare Service Request", row.service_request_no)
					hsr_doc.create_healthcare_service_docs()

		if len(consumable_item_ids) > 0:
			ci = DocType("Consumable Item")
			consumable_item_parents = (
				frappe.qb.from_(ci)
				.select(
					ci.parent.as_("consumable_record_no"),
				)
				.distinct()
				.where(ci.name.isin(consumable_item_ids))
			).run(as_dict=True)

			if len(consumable_item_parents) > 0:
				for row in consumable_item_parents:
					cons_doc = frappe.get_doc("Consumable Record", row.consumable_record_no)
					cons_doc.try_create_delivery_note()

	if method == "From Front End":
		frappe.db.commit()


def update_drug_prescription(doc):
	if not doc.patient:
		return

	for item in doc.items:
		if item.reference_dn and item.reference_dt and item.reference_dt == "Drug Prescription":
			frappe.db.set_value(
				"Drug Prescription",
				item.reference_dn,
				{
					"sales_invoice_number": doc.name,
					"drug_prescription_created": 1,
					"invoiced": 1,
				},
				update_modified=False,
			)

			dn_name = frappe.get_cached_value("Delivery Note", {"form_sales_invoice": doc.name}, "name")
			if dn_name:
				frappe.db.set_value(
					"Drug Prescription",
					item.reference_dn,
					"delivery_note",
					dn_name,
					update_modified=False,
				)


@frappe.whitelist()
def get_discount_items(invoice_no):
	items = frappe.get_all(
		"Sales Invoice Item",
		filters={"parent": invoice_no},
		fields=["item_code", "item_name", "amount", "reference_dt", "name"],
		order_by="reference_dt desc",
	)
	return items


def reset_invoiced_status(doc):
	"""Remove invoiced status on items because a return invoice is created"""

	for row in doc.items:
		if row.reference_dt and row.reference_dn:
			if row.reference_dt == "Patient Appointment":
				appointment = frappe.qb.DocType("Patient Appointment")
				(
					frappe.qb.update(appointment)
					.set(appointment.invoiced, 0)
					.set(appointment.ref_sales_invoice, "")
					.where(appointment.name == row.reference_dn)
				).run()

			elif row.reference_dt in [
				"Lab Prescription",
				"Radiology Procedure Prescription",
				"Procedure Prescription",
				"Drug Prescription",
				"Therapy Plan Detail",
				"Inpatient Occupancy",
			]:
				frappe.db.set_value(
					row.reference_dt,
					row.reference_dn,
					{
						"invoiced": 0,
						"sales_invoice_number": "",
					},
				)
				if row.get("service_request") and row.reference_dt != "Inpatient Occupancy":
					frappe.db.set_value(
						"Healthcare Service Request Payment",
						row.get("service_request"),
						{
							"invoiced": 0,
							"sales_invoice_number": "",
						},
					)

			elif row.reference_dt == "Inpatient Consultancy":
				frappe.db.set_value(
					row.reference_dt,
					row.reference_dn,
					{
						"hms_tz_invoiced": 0,
						"sales_invoice_number": "",
					},
				)


@frappe.whitelist()
def get_pos_profile(current_user):
	pos = frappe.get_cached_value("POS Profile User", {"user": current_user}, "parent")
	if pos:
		modes = frappe.db.get_all(
			"POS Payment Method",
			filters={"parent": pos},
			fields=["mode_of_payment"],
		)

		return modes
