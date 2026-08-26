# Copyright (c) 2023, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cstr, flt, get_fullname, nowdate, nowtime


class NHIFTrackingClaimChange(Document):
	pass


ref_docnames_list = []


def track_changes_of_claim_items(claim_doc):
	claim_no = reconcile_original_nhif_patient_claim_items(claim_doc)
	claim = frappe.get_cached_doc("NHIF Patient Claim", claim_no)
	claim.reload()

	for row in claim.original_nhif_patient_claim_item:
		for item in claim.nhif_patient_claim_item:
			if cstr(item.item_code) == cstr(row.item_code):
				if flt(item.amount_claimed) == flt(row.amount_claimed):
					ref_docnames_list.append(cstr(row.ref_docname))

				elif flt(item.amount_claimed) != flt(row.amount_claimed):
					ref_docnames_list.append(cstr(row.ref_docname))
					create_nhif_track_record(item, claim, row.amount_claimed, "Amount Changed")

	for row in claim.original_nhif_patient_claim_item:
		if cstr(row.ref_docname) not in ref_docnames_list:
			if row.ref_doctype == "Patient Appointment":
				create_nhif_track_record(row, claim, row.amount_claimed, "Item Removed")

			elif row.ref_doctype == "Drug Prescription":
				handle_drug_prescription_changes(row, claim, ref_docnames_list)

			elif row.ref_doctype in [
				"Lab Prescription",
				"Radiology Procedure Prescription",
				"Procedure Prescription",
				"Therapy Plan Detail",
			]:
				handle_lrpt_prescription_changes(row, claim, ref_docnames_list)

			elif row.ref_doctype in [
				"Inpatient Consultancy",
				"Inpatient Occupancy",
			]:
				handle_inpatient_changes(row, claim, ref_docnames_list)


def create_nhif_track_record(
	item,
	claim_doc,
	prev_amount,
	status,
	ref_name=None,
	encounter=None,
	lrpmt_return=None,
	med_change_request=None,
):
	amount_changed = abs(prev_amount - item.amount_claimed)
	new_item = frappe.get_doc(
		{
			"doctype": "NHIF Tracking Claim Change",
			"item_code": item.item_code,
			"item_name": item.item_name,
			"quantity": item.item_quantity,
			"claim_month": claim_doc.claim_month,
			"claim_year": claim_doc.claim_year,
			"company": claim_doc.company,
			"posting_date": nowdate(),
			"posting_time": nowtime(),
			"status": status,
			"previous_amount": prev_amount,
			"current_amount": item.amount_claimed,
			"amount_changed": abs(amount_changed),
			"nhif_patient_claim": item.parent,
			"patient_appointment": claim_doc.patient_appointment,
			"ref_docname": ref_name or item.ref_docname,
			"ref_doctype": item.ref_doctype,
			"patient_encounter": encounter or item.patient_encounter,
			"lrpmt_return": lrpmt_return,
			"medication_change_request": med_change_request,
			"user_email": frappe.session.user,
			"edited_by": get_fullname(),
		}
	).insert(ignore_permissions=True)


def handle_drug_prescription_changes(item, claim_doc, ref_docnames_list):
	def handle_drug_changes(item, ref_docname, is_cancelled, child_encounter, claim_row_encounter):
		if not is_cancelled and not child_encounter:
			med_change_request = get_medication_change_request_reference(item.item_name, claim_row_encounter)
			if med_change_request:
				create_nhif_track_record(
					item,
					claim_doc,
					item.amount_claimed,
					"Item Replaced",
					ref_name=ref_docname,
					encounter=child_encounter,
					med_change_request=med_change_request,
				)

		elif child_encounter and is_cancelled == 0:
			create_nhif_track_record(
				item,
				claim_doc,
				item.amount_claimed,
				"Item Removed",
				ref_name=ref_docname,
				encounter=child_encounter,
			)

		elif child_encounter and is_cancelled == 1:
			lrpmt_return = frappe.get_cached_value(
				"Medication Return",
				{
					"parentfield": "drug_items",
					"parenttype": "LRPMT Returns",
					"child_name": ref_docname,
					"encounter_no": child_encounter,
				},
				"parent",
			)
			if lrpmt_return:
				create_nhif_track_record(
					item,
					claim_doc,
					item.amount_claimed,
					"Item Cancelled",
					ref_name=ref_docname,
					encounter=child_encounter,
					lrpmt_return=lrpmt_return,
				)

	if "," not in item.ref_docname and item.ref_docname not in ref_docnames_list:
		is_cancelled = None
		child_encounter = None
		try:
			is_cancelled, child_encounter = frappe.get_cached_value(
				item.ref_doctype,
				item.ref_docname,
				["is_cancelled", "parent as encounter"],
			)
		except TypeError:
			pass

		handle_drug_changes(
			item,
			item.ref_docname,
			is_cancelled,
			child_encounter,
			item.patient_encounter,
		)
		ref_docnames_list.append(item.ref_docname)

	elif "," in item.ref_docname:
		for ref_name in item.ref_docname.split(","):
			if ref_name not in ref_docnames_list:
				is_cancelled = None
				child_encounter = None
				try:
					is_cancelled, child_encounter = frappe.get_cached_value(
						item.ref_doctype,
						ref_name,
						["is_cancelled", "parent as encounter"],
					)
				except TypeError:
					pass

				handle_drug_changes(
					item,
					ref_name,
					is_cancelled,
					child_encounter,
					item.patient_encounter,
				)
				ref_docnames_list.append(ref_name)


def handle_lrpt_prescription_changes(item, claim_doc, ref_docnames_list):
	def handle_lrpt_changes(item, ref_docname, is_cancelled, child_encounter):
		if child_encounter and is_cancelled == 0:
			create_nhif_track_record(
				item,
				claim_doc,
				item.amount_claimed,
				"Item Removed",
				ref_name=ref_docname,
				encounter=child_encounter,
			)

		elif child_encounter and is_cancelled == 1:
			lrpmt_return = frappe.get_cached_value(
				"Item Return",
				{
					"parentfield": "lrpt_items",
					"parenttype": "LRPMT Returns",
					"child_name": ref_docname,
					"encounter_no": child_encounter,
				},
				"parent",
			)
			if lrpmt_return:
				create_nhif_track_record(
					item,
					claim_doc,
					item.amount_claimed,
					"Item Cancelled",
					ref_name=ref_docname,
					encounter=child_encounter,
					lrpmt_return=lrpmt_return,
				)

	if "," not in item.ref_docname and item.ref_docname not in ref_docnames_list:
		is_cancelled, child_encounter = frappe.get_cached_value(
			item.ref_doctype,
			item.ref_docname,
			["is_cancelled", "parent as encounter"],
		)
		handle_lrpt_changes(item, item.ref_docname, is_cancelled, child_encounter)
		ref_docnames_list.append(item.ref_docname)

	elif "," in item.ref_docname:
		for ref_name in item.ref_docname.split(","):
			if ref_name not in ref_docnames_list:
				is_cancelled, child_encounter = frappe.get_cached_value(
					item.ref_doctype,
					ref_name,
					["is_cancelled", "parent as encounter"],
				)
				handle_lrpt_changes(item, ref_name, is_cancelled, child_encounter)
				ref_docnames_list.append(ref_name)


def handle_inpatient_changes(item, claim_doc, ref_docnames_list):
	def handle_beds_cons_changes(item, ref_docname, is_confirmed):
		if is_confirmed == 0:
			create_nhif_track_record(
				item,
				claim_doc,
				item.amount_claimed,
				"Item Unconfirmed",
				ref_name=ref_docname,
			)
		else:
			create_nhif_track_record(item, claim_doc, item.amount_claimed, "Item Removed")

	if "," not in item.ref_docname and item.ref_docname not in ref_docnames_list:
		is_confirmed = frappe.get_cached_value(item.ref_doctype, item.ref_docname, ["is_confirmed"])
		handle_beds_cons_changes(item, item.ref_docname, is_confirmed)
		ref_docnames_list.append(item.ref_docname)

	elif "," in item.ref_docname:
		for ref_name in item.ref_docname.split(","):
			if ref_name not in ref_docnames_list:
				is_confirmed = frappe.get_cached_value(item.ref_doctype, ref_name, ["is_confirmed"])
				handle_beds_cons_changes(item, ref_name, is_confirmed)
				ref_docnames_list.append(ref_name)


def get_medication_change_request_reference(item, encounter):
	dp = frappe.qb.DocType("Drug Prescription")
	md = frappe.qb.DocType("Medication Change Request")

	ref_name = (
		frappe.qb.from_(md)
		.inner_join(dp)
		.on(md.name == dp.parent)
		.select(md.name)
		.where(
			(dp.drug_name == item)
			& (md.patient_encounter == encounter)
			& (dp.parenttype == "Medication Change Request")
			& (dp.parentfield == "original_pharmacy_prescription")
		)
	).run(as_dict=1)

	return ref_name[0].name if ref_name else None


def reconcile_original_nhif_patient_claim_items(claim_doc):
	unique_items = []
	repeated_items = []
	unique_refcodes = []

	for row in claim_doc.original_nhif_patient_claim_item:
		if row.item_code not in unique_refcodes:
			unique_refcodes.append(row.item_code)
			unique_items.append(row)
		else:
			repeated_items.append(row)

	if len(repeated_items) > 0:
		claim_doc.original_nhif_patient_claim_item = []
		for item in unique_items:
			ref_docnames = []
			ref_encounters = []

			for d in repeated_items:
				if str(item.item_code) == str(d.item_code):
					item.item_quantity += d.item_quantity
					item.amount_claimed += d.amount_claimed

					if d.approval_ref_no:
						approval_ref_no = None
						if item.approval_ref_no:
							approval_ref_no = str(item.approval_ref_no) + "," + str(d.approval_ref_no)
						else:
							approval_ref_no = d.approval_ref_no

						item.approval_ref_no = approval_ref_no

					if d.patient_encounter:
						ref_encounters.append(d.patient_encounter)
					if d.ref_docname:
						ref_docnames.append(d.ref_docname)

					if item.status != "Submitted" and d.status == "Submitted":
						item.status = "Submitted"

			if item.patient_encounter:
				ref_encounters.append(item.patient_encounter)
			if item.ref_docname:
				ref_docnames.append(item.ref_docname)

			if len(ref_encounters) > 0:
				item.patient_encounter = ",".join(set(ref_encounters))

			if len(ref_docnames) > 0:
				item.ref_docname = ",".join(set(ref_docnames))

			item.name = None
			claim_doc.append("original_nhif_patient_claim_item", item)

		for record in repeated_items:
			if record.docstatus == 1:
				record.flags.ignore_permissions = True
				record.cancel()

			record.delete(ignore_permissions=True, force=True, delete_permanently=True)

		claim_doc.save(ignore_permissions=True)
		claim_doc.reload()
		return claim_doc.name

	return claim_doc.name
