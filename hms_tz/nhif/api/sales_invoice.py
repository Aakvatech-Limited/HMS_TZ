# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


from collections import defaultdict

import frappe
from frappe import _
from frappe.query_builder import DocType

from hms_tz.hms_tz.doctype.hms_tz_setting.hms_tz_setting import is_cash_inpatient_deposit_allowed
from hms_tz.nhif.api.healthcare_utils import (
	INVOICED_FIELDS,
	create_individual_lab_test,
	create_individual_procedure_prescription,
	create_individual_radiology_examination,
	create_therapy_plan,
	get_healthcare_docs_job_id,
	update_dimensions,
	update_invoice_reference_in_lrpmt_childs,
)
from hms_tz.nhif.api.sales_order import validate_stock_item

# billed rows without an LRPMT document, so their invoice item is complete at submit
NO_SERVICE_DOCTYPES = ("Inpatient Occupancy", "Inpatient Consultancy", "Consumable Item")


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
		if not insurance_subscription and is_cash_inpatient_deposit_allowed(doc.company):
			if hasattr(doc, "enabled_auto_create_delivery_notes"):
				doc.enabled_auto_create_delivery_notes = 0


@frappe.whitelist()
def create_pending_healthcare_docs(doc_name: str):
	frappe.has_permission("Sales Invoice", "write", doc_name, throw=True)
	enqueue_healthcare_docs(doc_name)
	frappe.msgprint(_("Pending healthcare services are being created in the background."))


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

	# healthcare's on_submit rejects rows still marked invoiced, then marks them again, so on_submit resets too
	if doc.is_return == 1:
		reset_invoiced_status(doc)


def on_submit(doc, method):
	if doc.is_return == 1:
		reset_invoiced_status(doc)
		return

	set_invoiced_references(doc, doc.name)
	mark_items_without_services(doc)
	update_drug_prescription(doc)
	enqueue_healthcare_docs(doc.name)


def set_invoiced_references(doc, invoice: str):
	"""Set the invoice on the rows the invoice bills, with one update per doctype."""
	references = defaultdict(list)
	for item in doc.items:
		if item.get("service_request"):
			references["Healthcare Service Request Payment"].append(item.service_request)

		if item.reference_dt in INVOICED_FIELDS and item.reference_dn:
			references[item.reference_dt].append(item.reference_dn)

	for doctype, names in references.items():
		set_references_invoiced(doctype, names, invoice)


def set_references_invoiced(doctype: str, names: list[str], invoice: str):
	"""An empty invoice marks the rows as not invoiced."""
	table = DocType(doctype)
	(
		frappe.qb.update(table)
		.set(table[INVOICED_FIELDS.get(doctype, "invoiced")], 1 if invoice else 0)
		.set(table.sales_invoice_number, invoice)
		.where(table.name.isin(names))
	).run()


def mark_items_without_services(doc):
	item_names = [item.name for item in doc.items if item.reference_dt in NO_SERVICE_DOCTYPES]
	if not item_names:
		return

	invoice_item = DocType("Sales Invoice Item")
	(
		frappe.qb.update(invoice_item)
		.set(invoice_item.hms_tz_is_lrp_item_created, 1)
		.where(invoice_item.name.isin(item_names))
	).run()


def enqueue_healthcare_docs(invoice: str):
	frappe.enqueue(
		"hms_tz.nhif.api.sales_invoice.create_invoice_healthcare_docs",
		queue="short",
		timeout=300,
		job_id=get_healthcare_docs_job_id(invoice),
		deduplicate=True,
		enqueue_after_commit=True,
		invoice=invoice,
	)


def create_invoice_healthcare_docs(invoice: str):
	create_healthcare_docs(frappe.get_doc("Sales Invoice", invoice))


def create_healthcare_docs(doc):
	"""Create the services the invoice paid for, committing after each item so a rerun resumes."""
	if doc.docstatus != 1:
		return

	therapy_items = []
	service_request_ids = []
	consumable_item_ids = []
	if doc.get("items"):
		for item in doc.items:
			if not item.reference_dt or not item.reference_dn:
				continue

			# its service document will be created from the Healthcare Service Request
			if item.get("service_request"):
				service_request_ids.append(item.get("service_request"))
				continue

			if item.reference_dt == "Consumable Item":
				consumable_item_ids.append(item.reference_dn)
				continue

			if item.hms_tz_is_lrp_item_created:
				continue

			if item.reference_dt in [
				"Lab Prescription",
				"Radiology Procedure Prescription",
				"Procedure Prescription",
			]:
				child = frappe.get_doc(item.reference_dt, item.reference_dn)
				patient_encounter_doc = frappe.get_doc("Patient Encounter", child.parent)
				if child.doctype == "Lab Prescription":
					create_individual_lab_test(patient_encounter_doc, child)
				elif child.doctype == "Radiology Procedure Prescription":
					create_individual_radiology_examination(patient_encounter_doc, child)
				elif child.doctype == "Procedure Prescription":
					create_individual_procedure_prescription(patient_encounter_doc, child)

				update_invoice_reference_in_lrpmt_childs(child, item)
				frappe.db.commit()  # nosemgrep

			elif item.reference_dt == "Therapy Plan Detail":
				therapy_items.append(item)

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
					hsr_doc = frappe.get_doc("Healthcare Service Request", row.service_request_no)
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


def update_drug_prescription(doc):
	if not doc.patient:
		return

	drug_names = [
		item.reference_dn
		for item in doc.items
		if item.reference_dt == "Drug Prescription" and item.reference_dn
	]
	if not drug_names:
		return

	drug = DocType("Drug Prescription")
	query = frappe.qb.update(drug).set(drug.drug_prescription_created, 1).where(drug.name.isin(drug_names))

	delivery_note = frappe.db.get_value("Delivery Note", {"form_sales_invoice": doc.name}, "name")
	if delivery_note:
		query = query.set(drug.delivery_note, delivery_note)

	query.run()


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
	set_invoiced_references(doc, "")

	appointments = [row.reference_dn for row in doc.items if row.reference_dt == "Patient Appointment"]
	if appointments:
		appointment = DocType("Patient Appointment")
		(
			frappe.qb.update(appointment)
			.set(appointment.invoiced, 0)
			.set(appointment.ref_sales_invoice, "")
			.where(appointment.name.isin(appointments))
		).run()


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
