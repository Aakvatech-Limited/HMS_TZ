import json

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.utils import date_diff, get_fullname, nowdate

from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import (
	create_revenue_entry,
	update_revenue_entry,
)
from hms_tz.nhif.api.healthcare_utils import update_dimensions
from hms_tz.nhif.api.medical_record import create_medical_record, update_medical_record
from hms_tz.nhif.utils import validate_issued_services, validate_point_of_care


def validate(doc, method):
	if doc.docstatus != 0:
		return
	set_prescribed(doc)
	set_missing_values(doc)
	check_item_for_out_of_stock(doc)
	update_dimensions(doc)


def after_insert(doc, method):
	set_original_item(doc)

	if doc.is_return == 0:
		create_revenue_entry(doc)


def set_original_item(doc):
	for item in doc.items:
		if item.item_code:
			item.original_item = item.item_code
			item.original_stock_uom_qty = item.stock_qty

		# SHM Rock: #168
		if doc.form_sales_invoice and doc.patient:
			update_dosage_details(item)

		new_row = item.as_dict()
		for fieldname in get_fields_to_clear():
			new_row[fieldname] = None

		new_row.update(
			{
				"parent": doc.name,
				"parentfield": "hms_tz_original_items",
				"parenttype": "Delivery Note",
				"doctype": "Original Delivery Note Item",
			}
		)
		doc.append("hms_tz_original_items", new_row)
	doc.save(ignore_permissions=True)


def update_dosage_details(item):
	"""Update dosage details for Cash Patient only if dosage is not set"""

	if item.si_detail:
		reference_dn = frappe.get_cached_value("Sales Invoice Item", item.si_detail, "reference_dn")
		if not reference_dn:
			return

		drug_doc = frappe.get_cached_doc("Drug Prescription", reference_dn)

		description = ", <br>".join(
			[
				"frequency: " + str(drug_doc.get("dosage") or "No Prescription Dosage"),
				"period: " + str(drug_doc.get("period") or "No Prescription Period"),
				"dosage_form: " + str(drug_doc.get("dosage_form") or ""),
				"interval: " + str(drug_doc.get("interval") or ""),
				"interval_uom: " + str(drug_doc.get("interval_uom") or ""),
				"medical_code: " + str(drug_doc.get("medical_code") or "No medical code"),
				"Doctor's comment: " + (drug_doc.get("comment") or "Take medication as per dosage."),
			]
		)

		item.description = description
		item.reference_doctype = drug_doc.doctype
		item.reference_name = drug_doc.name


def onload(doc, method):
	for item in doc.items:
		if item.last_qty_prescribed:
			frappe.msgprint(
				_(
					f"The item {item.item_code} was last prescribed on {item.last_date_prescribed} for {item.last_qty_prescribed} {item.stock_uom}"
				),
			)
		if doc.patient and doc.coverage_plan_name:
			check_for_medication_category(item)
			validate_medication_class(doc, item)

	check_cash_drugs_from_encounter(doc)


def set_prescribed(doc):
	for item in doc.items:
		items_list = frappe.db.sql(
			f"""
            SELECT dn.posting_date, dni.item_code, dni.stock_qty, dni.uom
            FROM `tabDelivery Note` dn
            INNER JOIN `tabDelivery Note Item` dni on dni.parent = dn.name
            WHERE dni.item_code = {frappe.db.escape(item.item_code)}
                AND dn.patient = {frappe.db.escape(doc.patient)}
                AND dn.name != {frappe.db.escape(doc.name)}
                AND dn.docstatus = 1
            ORDER BY posting_date desc
            LIMIT 1
        """,
			as_dict=1,
		)

		if len(items_list):
			item.last_qty_prescribed = items_list[0].get("stock_qty")
			item.last_date_prescribed = items_list[0].get("posting_date")

		# Check for medication category
		if doc.patient and doc.coverage_plan_name:
			check_for_medication_category(item)


def check_for_medication_category(item):
	is_category_s_medication = frappe.get_cached_value(
		"Medication", {"item": item.item_code}, "medication_category"
	)

	if is_category_s_medication == "Category S Medication":
		frappe.msgprint(
			f"Item: <b>{item.item_code}</b> is Category S Medication",
			alert=True,
		)


def validate_medication_class(doc, row):
	"""Validate medication class based on company settings

	Args:
	    doc (Document): Delivery Note
	    row (dict): Delivery Note Item
	"""

	validate_medication_class = frappe.get_cached_value(
		"HMS TZ Setting", doc.company, "validate_medication_class"
	)
	if int(validate_medication_class) == 0:
		return

	medication_class = frappe.get_cached_value("Medication", {"item": row.item_code}, "medication_class")
	if not medication_class:
		return

	medication_class_list = frappe.db.sql(
		f"""
        SELECT dn.posting_date, dni.item_code, mc.prescribed_after as valid_days
        FROM `tabDelivery Note` dn
        INNER JOIN `tabDelivery Note Item` dni on dni.parent = dn.name
        INNER JOIN `tabMedication` m on m.item = dni.item_code
        INNER JOIN `tabMedication Class` mc on mc.name = m.medication_class
        WHERE dn.docstatus = 1
            AND dn.patient = {frappe.db.escape(doc.patient)}
            AND dn.name != {frappe.db.escape(doc.name)}
            AND mc.name = {frappe.db.escape(medication_class)}
        ORDER BY posting_date desc
        LIMIT 1
    """,
		as_dict=1,
	)

	if len(medication_class_list) == 0:
		return

	prescribed_date = medication_class_list[0].posting_date
	item_code = medication_class_list[0].item_code
	valid_days = medication_class_list[0].valid_days
	if not int(valid_days):
		return

	if int(date_diff(nowdate(), prescribed_date)) < int(valid_days):
		frappe.msgprint(
			_(
				f"Item: <strong>{item_code}</strong> with same Medication Class: <strong>{medication_class}</strong>\
            was lastly prescribed on: <strong>{prescribed_date}</strong><br>\
            Therefore item with same <b>medication class</b> were supposed to be prescribed after: <strong>{valid_days}</strong> days"
			)
		)


def set_missing_values(doc):
	if doc.form_sales_invoice:
		if not doc.hms_tz_appointment_no or not doc.healthcare_practitioner:
			si_reference_dn = frappe.get_cached_value(
				"Sales Invoice Item", doc.items[0].si_detail, "reference_dn"
			)

			if si_reference_dn:
				parent_encounter = frappe.get_cached_value("Drug Prescription", si_reference_dn, "parent")
				doc.reference_name = parent_encounter
				doc.reference_doctype = "Patient Encounter"
				(
					doc.hms_tz_appointment_no,
					doc.healthcare_practitioner,
				) = frappe.get_cached_value(
					"Patient Encounter",
					parent_encounter,
					["appointment", "practitioner"],
				)
	if (
		not doc.patient
		and doc.reference_doctype
		and doc.reference_name
		and doc.reference_doctype == "Patient Encounter"
	):
		doc.patient = frappe.get_cached_value("Patient Encounter", doc.reference_name, "patient")

	if not doc.hms_tz_phone_no and doc.patient:
		doc.hms_tz_phone_no = frappe.get_cached_value("Patient", doc.patient, "mobile")


def before_submit(doc, method):
	if doc.hms_tz_all_items_out_of_stock == 1:
		frappe.throw(
			"<h4 class='font-weight-bold bg-warning text-center'>\
            This Delivery Note can't be submitted because all Items\
                are not available in stock</h4>"
		)

	for item in doc.items:
		if item.is_restricted and not item.approval_number:
			frappe.throw(
				_(
					f"Approval number required for {item.item_name}. Please open line {item.idx} and set the Approval Number."
				)
			)

		validate_issued_services(
			item.doctype, item.name, is_restricted=item.is_restricted, company=doc.company
		)

	validate_point_of_care(doc, "validate_poc_at_pharmacy")

	doc.hms_tz_submitted_by = get_fullname(frappe.session.user)
	doc.hms_tz_user_id = frappe.session.user
	doc.hms_tz_submitted_date = nowdate()


def on_submit(doc, method):
	update_drug_prescription(doc)
	check_cash_drugs_from_encounter(doc)
	create_medical_record(doc)


def update_drug_prescription(doc):
	if doc.patient and doc.is_return == 0:
		if doc.form_sales_invoice:
			sales_invoice_doc = frappe.get_doc("Sales Invoice", doc.form_sales_invoice)

			for item in sales_invoice_doc.items:
				if item.reference_dt == "Drug Prescription":
					for dni in doc.items:
						if (
							item.name == dni.si_detail
							and item.item_code == dni.item_code
							and item.parent == dni.against_sales_invoice
						):
							if item.qty != dni.stock_qty:
								quantity = dni.stock_qty
							else:
								quantity = item.qty

							frappe.db.set_value(
								"Drug Prescription",
								item.reference_dn,
								{
									"dn_detail": dni.name,
									"delivery_note": doc.name,
									"quantity": quantity,
									"delivered_quantity": quantity,
								},
								update_modified=False,
							)
							update_revenue_entry(
								"Delivery Note",
								doc.name,
								"Drug Prescription",
								item.reference_dn,
								lrpmt_status="Submitted",
							)

					for original_item in doc.hms_tz_original_items:
						if (
							original_item.hms_tz_is_out_of_stock == 1
							and item.name == original_item.si_detail
							and item.item_code == original_item.item_code
							and item.parent == original_item.against_sales_invoice
						):
							frappe.db.set_value(
								"Drug Prescription",
								item.reference_dn,
								{
									"is_not_available_inhouse": 1,
									"hms_tz_is_out_of_stock": 1,
									"is_cancelled": 1,
								},
								update_modified=False,
							)
							update_revenue_entry(
								"Delivery Note",
								doc.name,
								"Drug Prescription",
								item.reference_dn,
								lrpmt_status="Submitted",
								is_cancelled=1,
							)

		else:
			if doc.reference_doctype == "Patient Encounter":
				patient_encounter_doc = frappe.get_doc(doc.reference_doctype, doc.reference_name)

				for dni in doc.items:
					if dni.reference_doctype == "Drug Prescription":
						for item in patient_encounter_doc.drug_prescription:
							if (
								# commented to avoid mismatch of drug code of drug prescription and
								# item code of delivery note item
								# 2022-06-13
								# dni.item_code == item.drug_code and
								dni.reference_name == item.name and dni.reference_doctype == item.doctype
							):
								item.dn_detail = dni.name
								item.delivery_note = doc.name
								if item.quantity != dni.stock_qty:
									item.quantity = dni.stock_qty
								item.delivered_quantity = item.quantity - item.quantity_returned
								item.db_update()

								hsrp = DocType("Healthcare Service Request Payment")
								(
									frappe.qb.update(hsrp)
									.set(hsrp.lrpmt_doctype, doc.doctype)
									.set(hsrp.lrpmt_docname, doc.name)
									.set(hsrp.dn_detail, dni.name)
									.set(hsrp.lrpmt_status, "Submitted")
									.where(hsrp.ref_docname == dni.reference_name)
								).run()

								update_revenue_entry(
									"Delivery Note",
									doc.name,
									"Drug Prescription",
									dni.reference_name,
									lrpmt_status="Submitted",
								)

				for original_item in doc.hms_tz_original_items:
					if (
						original_item.hms_tz_is_out_of_stock == 1
						and original_item.reference_name
						and original_item.reference_doctype == "Drug Prescription"
					):
						for drug_item in patient_encounter_doc.drug_prescription:
							if (
								original_item.reference_name == drug_item.name
								and original_item.reference_doctype == drug_item.doctype
							):
								drug_item.is_not_available_inhouse = 1
								drug_item.hms_tz_is_out_of_stock = 1
								drug_item.is_cancelled = 1
								drug_item.db_update()

								hsrp = DocType("Healthcare Service Request Payment")
								(
									frappe.qb.update(hsrp)
									.set(hsrp.is_cancelled, 1)
									.set(hsrp.lrpmt_doctype, doc.doctype)
									.set(hsrp.lrpmt_docname, doc.name)
									.set(hsrp.lrpmt_status, "Submitted")
									.where(hsrp.ref_docname == original_item.reference_name)
								).run()

								update_revenue_entry(
									"Delivery Note",
									doc.name,
									"Drug Prescription",
									original_item.reference_name,
									lrpmt_status="Submitted",
									is_cancelled=1,
								)


def check_item_for_out_of_stock(doc):
	"""Mark an Item as out of stock if it is not available in stock"""

	if len(doc.items) > 0 and len(doc.hms_tz_original_items) > 0:
		items = []

		doc.total = 0
		doc.total_qty = 0
		for dni_row in doc.items:
			for original_item in doc.hms_tz_original_items:
				if (
					dni_row.hms_tz_is_out_of_stock == 1
					and dni_row.item_code == original_item.item_code
					and original_item.hms_tz_is_out_of_stock == 0
				):
					original_item.hms_tz_is_out_of_stock = 1

				if (
					dni_row.hms_tz_is_out_of_stock == 0
					and dni_row.item_code == original_item.item_code
					and original_item.hms_tz_is_out_of_stock == 1
				):
					original_item.hms_tz_is_out_of_stock = 0

			if not dni_row.hms_tz_is_out_of_stock:
				dni_row.name = None
				items.append(dni_row)

				doc.total += dni_row.amount
				doc.total_qty += dni_row.qty

		doc.items = items
		if len(doc.items) > 0:
			doc.hms_tz_all_items_out_of_stock = 0
		else:
			check_out_of_stock_for_original_item(doc)


def check_out_of_stock_for_original_item(doc):
	"""Copy items back to delivery note item table
	if all items marked as out of stock
	"""
	doc.total = 0
	doc.total_qty = 0
	for original_item in doc.hms_tz_original_items:
		if original_item.hms_tz_is_out_of_stock == 1:
			new_item = original_item.as_dict()

			for fieldname in get_fields_to_clear():
				new_item[fieldname] = None

			new_item.update(
				{
					"hms_tz_is_out_of_stock": 1,
					"parent": doc.name,
					"parentfield": "items",
					"parenttype": "Delivery Note",
					"doctype": "Delivery Note Item",
				}
			)
			doc.append("items", frappe.get_doc(new_item).as_dict())

			original_item.hms_tz_is_out_of_stock = 1

			doc.total += new_item.amount
			doc.total_qty += new_item.qty

	doc.hms_tz_all_items_out_of_stock = 1
	frappe.msgprint(
		"<h4 class='font-weight-bold bg-warning text-center'>All Items are marked as Out of Stock</h4>"
	)


@frappe.whitelist()
def convert_to_instock_item(name, row):
	"""Convert an item to be considered as it is available in stock

	:param name: Name of the current document.
	:param row: Original child row to be converted.
	"""
	new_row = json.loads(row)

	for fieldname in get_fields_to_clear():
		new_row[fieldname] = None

	new_row.update(
		{
			"hms_tz_is_out_of_stock": 0,
			"parent": name,
			"parentfield": "items",
			"parenttype": "Delivery Note",
			"doctype": "Delivery Note Item",
		}
	)
	doc = frappe.get_cached_doc("Delivery Note", name)
	prev_size = len(doc.items)
	doc.append("items", new_row)

	if len(doc.items) > prev_size:
		doc.total_qty += new_row.get("qty")
		doc.total += new_row.get("amount")

		for original_item in doc.hms_tz_original_items:
			if original_item.item_code == new_row.get("item_code"):
				original_item.hms_tz_is_out_of_stock = 0

		doc.save(ignore_permissions=True)
		doc.reload()
		return True


def get_fields_to_clear():
	return [
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
	]


def on_cancel(doc, method=None):
	delete_medical_record(doc)


def delete_medical_record(doc, method=None):
	update_medical_record(doc)


# SHM Rock: 205
def check_cash_drugs_from_encounter(doc):
	if not doc.form_sales_invoice and doc.reference_name and doc.reference_doctype == "Patient Encounter":
		encounter_doc = frappe.get_cached_doc(doc.reference_doctype, doc.reference_name)
		if encounter_doc.insurance_subscription:
			cash_drugs = [
				row.drug_code
				for row in encounter_doc.drug_prescription
				if (
					row.prescribe == 1
					and row.invoiced == 0
					and row.is_cancelled == 0
					and row.is_not_available_inhouse == 0
				)
			]
			if len(cash_drugs) > 0:
				drug_list = ", ".join(cash_drugs)
				msg = f"""<div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
                    <h4 style="font-weight: bold; color: #856404;"><i class="fa fa-exclamation-triangle" aria-hidden="true"></i> Payment Alert</h4>
                    <p style="font-size: 16px;">This patient: <strong>{doc.patient}</strong> has <strong>{len(cash_drugs)}</strong> more drugs to be paid in cash:</p>
                    <p style="font-style: italic; font-weight: bold; color: #856404;">{drug_list}</p>
                    <p style="font-size: 16px;">Please inform the patient to pay in cash for these drugs.</p>
                </div>"""

				frappe.msgprint(msg)
