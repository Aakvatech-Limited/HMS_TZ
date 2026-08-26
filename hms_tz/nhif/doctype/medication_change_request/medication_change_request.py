# Copyright (c) 2021, Aakvatech and contributors
# For license information, please see license.txt


from time import sleep

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.workflow import apply_workflow
from frappe.query_builder import DocType
from frappe.utils import get_fullname, get_url_to_form, nowdate

from hms_tz.hms_tz.doctype.healthcare_service_request.healthcare_service_request import (
	get_discount_percent,
	get_drug_quantity,
	get_item_rate,
	get_item_refcode,
	get_mop_amount,
	get_template_company_option,
	get_warehouse_from_service_unit,
	msgThrow,
	set_service_amounts,
	validate_nhif_patient_claim_status,
	validate_stock_item,
)
from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import (
	create_revenue_entry_from_inpatient_cash_mcr,
	create_revenue_entry_from_insurance_mcr,
	update_returned_or_cancelled_revenue_entry,
)
from hms_tz.nhif.api.delivery_note import update_drug_prescription


class MedicationChangeRequest(Document):
	def before_insert(self):
		encounter_doc = self.validate_initial_values()
		self.set_missing_values(encounter_doc)

	def after_insert(self):
		if self.delivery_note:
			self.update_delivery_note_workflow("Changes Requested", "Request Changes")

		if self.sales_order:
			url = get_url_to_form("Medication Change Request", self.name)
			comment = frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"comment_email": frappe.session.user,
					"reference_doctype": "Sales Order",
					"reference_name": self.sales_order,
					"content": f"Medication Change Request: <a href='{url}'>{frappe.bold(self.name)}</a> is created",
				}
			).insert(ignore_permissions=True)

			frappe.db.set_value(
				"Sales Order",
				self.sales_order,
				"med_change_request_status",
				"Pending",
			)

	def validate(self):
		self.validate_duplicate_medication_change_request()

		self.title = f"{self.patient_encounter}/{self.delivery_note or self.sales_order}"

		items = []
		if len(self.drug_prescription) > 0:
			for drug in self.drug_prescription:
				if drug.drug_code not in items:
					items.append(drug.drug_code)
				else:
					frappe.throw(
						_(
							f"Drug '{frappe.bold(drug.drug_code)}' is duplicated in line '{frappe.bold(drug.idx)}' in Drug Prescription"
						)
					)

				self.validate_drug_quantity(drug)
				self.validate_item_available_in_house(drug)

				if not self.sales_order:
					self.validate_item_insurance_coverage(drug, "validate")
					self.validate_copayment_added_item(drug)
					self.validate_insurance_pre_approval(drug, "validate")
					validate_healthcare_service_unit(self.warehouse, drug, method="validate")

	def before_submit(self):
		if not self.sales_order:
			validate_nhif_patient_claim_status("Medication Change Request", self.company, self.appointment)

		self.posting_date = nowdate()

		mop = ""
		if not self.insurance_subscription:
			mop = frappe.get_cached_value(
				"Patient Appointment",
				self.appointment,
				"mode_of_payment",
			)

		for item in self.drug_prescription:
			if not self.sales_order:
				self.validate_item_insurance_coverage(item, "throw")
				self.validate_copayment_added_item(item)
				self.validate_insurance_pre_approval(item, "throw")
				validate_healthcare_service_unit(self.warehouse, item, method="throw")

			set_amount(self, item, mop)

	def on_submit(self):
		if not self.sales_order:
			validate_nhif_patient_claim_status("Medication Change Request", self.company, self.appointment)

		has_updated = self.update_encounter()

		if not has_updated:
			frappe.throw(
				title="Failed to Update Encounter",
				msg="Failed to update Patient Encounter. Please try again.",
			)

		encounter_doc = get_patient_encounter_doc(self.patient_encounter)

		if self.delivery_note:
			self.update_delivery_note(encounter_doc)
			self.update_hsr_and_hre()

		if self.sales_order:
			self.update_sales_order(encounter_doc)

	def on_trash(self):
		if self.sales_order:
			url = get_url_to_form("Medication Change Request", self.name)
			comment = frappe.get_doc(
				{
					"doctype": "Comment",
					"comment_type": "Comment",
					"comment_email": frappe.session.user,
					"reference_doctype": "Sales Order",
					"reference_name": self.sales_order,
					"content": f"Medication Change Request: <a href='{url}'>{frappe.bold(self.name)}</a> is deleted",
				}
			).insert(ignore_permissions=True)

			frappe.db.set_value(
				"Sales Order",
				self.sales_order,
				"med_change_request_status",
				"",
			)

	def validate_initial_values(self):
		if not self.sales_order and not self.delivery_note:
			frappe.throw(
				"Please select either Sales Order or Delivery Note to create Medication Change Request"
			)

		if not self.sales_order and self.delivery_note:
			validate_nhif_patient_claim_status("Medication Change Request", self.company, self.appointment)

		if not self.patient_encounter:
			frappe.throw("Please select Patient Encounter to create Medication Change Request.")

		encounter_doc = get_patient_encounter_doc(self.patient_encounter)
		if (
			not encounter_doc.insurance_coverage_plan
			and not encounter_doc.inpatient_record
			and not self.sales_order
		):
			frappe.throw(
				frappe.bold(
					"Cannot create medication change request for Cash Patient OPD via delivery note,<br>\
                        Please create medication change request for Cash Patient OPD via Sales Order"
				)
			)

		return encounter_doc

	def set_missing_values(self, encounter_doc):
		self.posting_date = nowdate()
		if not self.warehouse:
			self.warehouse = self.get_warehouse_per_dn_or_so()

		if self.delivery_note:
			self.insurance_subscription = encounter_doc.insurance_subscription
			self.insurance_coverage_plan = encounter_doc.insurance_coverage_plan
			self.insurance_company = encounter_doc.insurance_company

		for row in encounter_doc.drug_prescription:
			if self.delivery_note and self.warehouse != get_warehouse_from_service_unit(
				row.healthcare_service_unit
			):
				continue

			self.set_drugs(
				row,
				inpatient_record=encounter_doc.inpatient_record,
			)

		if not self.patient_encounter_final_diagnosis:
			for d in encounter_doc.patient_encounter_final_diagnosis:
				if not isinstance(d, dict):
					d = d.as_dict()

				d["name"] = None

				self.append("patient_encounter_final_diagnosis", d)

	def set_drugs(self, row, inpatient_record=None):
		is_so_from_encounter = frappe.get_cached_value(
			"HMS TZ Setting", self.company, "auto_create_sales_order_from_encounter"
		)
		if self.insurance_subscription:
			# add only covered items unser insurance coverage, means items that
			# reached to delivery note
			if self.delivery_note and row.prescribe == 0:
				new_row = row.as_dict()
				new_row["name"] = None
				new_row["parent"] = None
				new_row["parentfield"] = None
				new_row["parenttype"] = None

				self.append("original_pharmacy_prescription", new_row)
				self.append("drug_prescription", new_row)

			# add only uncovered items that are prescribed, means items that
			# reached to sales order
			if is_so_from_encounter == 1 and self.sales_order and row.prescribe == 1:
				new_row = row.as_dict()
				new_row["name"] = None
				new_row["parent"] = None
				new_row["parentfield"] = None
				new_row["parenttype"] = None

				self.append("original_pharmacy_prescription", new_row)
				self.append("drug_prescription", new_row)

		elif not self.insurance_subscription:
			# add all cash items from sales order for OPD patient
			if is_so_from_encounter == 1 and self.sales_order and row.prescribe == 1:
				new_row = row.as_dict()
				new_row["name"] = None
				new_row["parent"] = None
				new_row["parentfield"] = None
				new_row["parenttype"] = None

				self.append("original_pharmacy_prescription", new_row)
				self.append("drug_prescription", new_row)

			# add all cash items from pe for ipd patient
			if inpatient_record and row.prescribe == 1 and not self.sales_order:
				new_row = row.as_dict()
				new_row["name"] = None
				new_row["parent"] = None
				new_row["parentfield"] = None
				new_row["parenttype"] = None

				self.append("original_pharmacy_prescription", new_row)
				self.append("drug_prescription", new_row)

	def validate_drug_quantity(self, row):
		# auto calculating quantity
		if not row.quantity:
			row.quantity = get_drug_quantity(row)

		if not row.quantity:
			frappe.throw(
				f"Please keep quantity for item: {frappe.bold(row.drug_code)}, Row#: {frappe.bold(row.idx)}"
			)

		row.delivered_quantity = row.quantity - (row.quantity_returned or 0)

		validate_stock_item(
			row.drug_code,
			row.quantity,
			self.company,
			row.doctype,
			row.healthcare_service_unit,
			caller="unknown",
			method="validate",
		)

	def validate_item_available_in_house(self, row):
		template_doc = get_template_company_option(row.drug_code, self.company)
		row.is_not_available_inhouse = template_doc.is_not_available
		if row.is_not_available_inhouse == 1:
			frappe.msgprint(
				f"NOTE: This healthcare service item, <b> {frappe.bold(row.drug_code)} </b>, is not available inhouse"
			)

	def validate_duplicate_medication_change_request(self):
		if not self.patient_encounter:
			return

		if self.delivery_note:
			meds = frappe.db.get_all(
				"Medication Change Request",
				filters={
					"patient_encounter": self.patient_encounter,
					"delivery_note": self.delivery_note,
					"docstatus": 0,
					"name": ["!=", self.name],
				},
			)
			if len(meds) > 0:
				url = get_url_to_form("Medication Change Request", meds[0].name)
				msg = f"""<div style="border: 1px solid #ccc; background-color: #f9f9f9; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin: 10px;">
                    <p style="font-weight: normal; font-size: 15px;">Draft Medication Change Request: <span style="font-weight: bold;"><a href='{url}'>{frappe.bold(meds[0].name)}</a></span>\
                        for delivery note: <span style="font-weight: bold;">{frappe.bold(self.delivery_note)}</span>\
                            and patient encounter: <span style="font-weight: bold;">{frappe.bold(self.patient_encounter)}</span> is already created</p>
                    <p style="font-style: italic; font-weight: bold; font-size: 15px;"></p>
                    <p style="font-size: 15px;">Please update the existing Medication Change Request or delete it and try again.</p>
                </div>"""

				frappe.throw(msg)

		if self.sales_order:
			meds = frappe.db.get_all(
				"Medication Change Request",
				filters={
					"patient_encounter": self.patient_encounter,
					"sales_order": self.sales_order,
					"docstatus": 0,
					"name": ["!=", self.name],
				},
			)
			if len(meds) > 0:
				url = get_url_to_form("Medication Change Request", meds[0].name)
				msg = f"""<div style="border: 1px solid #ccc; background-color: #f9f9f9; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin: 10px;">
                    <p style="font-weight: normal; font-size: 15px;">Draft Medication Change Request: <span style="font-weight: bold;"><a href='{url}'>{frappe.bold(meds[0].name)}</a></span>\
                        for sales order: <span style="font-weight: bold;">{frappe.bold(self.sales_order)}</span>\
                            and patient encounter: <span style="font-weight: bold;">{frappe.bold(self.patient_encounter)}</span> is already created</p>
                    <p style="font-style: italic; font-weight: bold; font-size: 15px;"></p>
                    <p style="font-size: 15px;">Please update the existing Medication Change Request or delete it and try again.</p>
                </div>"""

				frappe.throw(msg)

	def get_warehouse_per_dn_or_so(self):
		if self.sales_order:
			return frappe.get_cached_value("Sales Order", self.sales_order, "set_warehouse")

		if self.delivery_note:
			return frappe.get_cached_value("Delivery Note", self.delivery_note, "set_warehouse")

	def validate_item_insurance_coverage(self, row, method):
		"""Validate if the Item is covered with the insurance coverage plan of a patient"""

		if not self.insurance_subscription or row.prescribe:
			return

		is_exclusions = frappe.get_cached_value(
			"Healthcare Insurance Coverage Plan",
			self.insurance_coverage_plan,
			"is_exclusions",
		)

		today = frappe.utils.nowdate()
		service_coverage = frappe.get_all(
			"Healthcare Service Insurance Coverage",
			filters={
				"is_active": 1,
				"start_date": ["<=", today],
				"end_date": [">=", today],
				"healthcare_service_template": row.drug_code,
				"healthcare_insurance_coverage_plan": self.insurance_coverage_plan,
			},
			fields=[
				"name",
				"has_copayment",
				"approval_mandatory_for_claim",
				"healthcare_service_template",
			],
		)
		if len(service_coverage) > 0:
			row.is_restricted = service_coverage[0].approval_mandatory_for_claim
			row.has_copayment = service_coverage[0].has_copayment

			if is_exclusions:
				msgThrow(
					_(
						f"{frappe.bold(row.drug_code)} not covered in Healthcare Insurance Coverage Plan: {self.insurance_coverage_plan}"
					),
					method,
				)

		else:
			if not is_exclusions:
				msgThrow(
					_(
						f"{frappe.bold(row.drug_code)} not covered in Healthcare Insurance Coverage Plan: {self.insurance_coverage_plan}"
					),
					method,
				)

	def validate_copayment_added_item(self, row):
		"""Validate a co-payment item is newly added to the Medication Change Request"""

		if not self.insurance_company or "NHIF" not in self.insurance_company or row.prescribe:
			return

		if row.has_copayment == 0:
			return

		original_items = [d.drug_code for d in self.original_pharmacy_prescription if d.has_copayment == 1]

		if row.drug_code not in original_items:
			msg = f"""<div style="border-left: 4px solid red; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">
                    <p class="text-center"><i>Row#: <b>{row.idx}</b> Item: <b>${row.drug_code}</b> is a co-payment item, and it should not be added via Medication Change Request.</i></p>
                </div>
                <br>
                <p class="text-center"><i><b>Please select a different item to proceed..</b></i></p>
            """

			frappe.throw(title="Co-Payment Item not Allowed", msg=msg)

	def validate_insurance_pre_approval(self, row, method):
		"""Validate if the Item requires pre-approval from insurance company"""

		if not self.insurance_company or "NHIF" not in self.insurance_company:
			return

		if (
			row.get("prescribe")
			or row.get("is_not_available_inhouse")
			or row.get("is_cancelled")
			or row.get("is_restricted")
			or row.get("preapproval_status") in ["Accepted", "REJECTED"]
		):
			return

		if not row.get("preapproval_status"):
			msgThrow(
				_(f"{frappe.bold(row.drug_code)} requires pre-approval."),
				method,
			)

	def update_encounter(self):
		"""Update Patient Encounter with new Drug Prescription"""

		doc = get_patient_encounter_doc(self.patient_encounter)
		for line in self.original_pharmacy_prescription:
			for row in doc.drug_prescription:
				if (
					line.drug_code == row.drug_code
					and line.healthcare_service_unit == row.healthcare_service_unit
				):
					frappe.delete_doc(
						row.doctype,
						row.name,
						force=1,
						ignore_permissions=True,
						for_reload=True,
					)
		doc.reload()
		fields_to_clear = [
			"name",
			"owner",
			"creation",
			"modified",
			"modified_by",
			"docstatus",
			"amended_from",
			"amendment_date",
			"parentfield",
			"parenttype",
		]
		for row in self.drug_prescription:
			if row.is_not_available_inhouse == 1:
				continue

			new_row = frappe.copy_doc(row).as_dict()
			for fieldname in fields_to_clear:
				new_row[fieldname] = None

			new_row["drug_prescription_created"] = 1
			doc.append("drug_prescription", new_row)

		doc.db_update_all()
		frappe.clear_document_cache("Patient Encounter", self.patient_encounter)
		frappe.msgprint(
			_("Patient Encounter " + self.patient_encounter + " has been updated!"),
			alert=True,
		)
		return True

	def update_sales_order(self, encounter_doc):
		so_doc = frappe.get_cached_doc("Sales Order", self.sales_order)
		so_doc.items = []
		for row in encounter_doc.get("drug_prescription"):
			if row.prescribe == 0 or row.is_not_available_inhouse == 1 or row.is_cancelled == 1:
				continue

			item_code = frappe.get_cached_value("Medication", row.get("drug_code"), "item")
			if not item_code:
				frappe.throw(
					_(
						f"""The Item Code for {row.get("drug_code")} is not found!<br>\
                            Please request administrator to set item code in {row.get("drug_code")}."""
					)
				)

			item_name, item_description = frappe.get_cached_value(
				"Item", item_code, ["item_name", "description"]
			)

			dosage_info = ", <br>".join(
				[
					"frequency: " + str(row.get("dosage") or "No Prescription Dosage"),
					"period: " + str(row.get("period") or "No Prescription Period"),
					"dosage_form: " + str(row.get("dosage_form") or ""),
					"interval: " + str(row.get("interval") or ""),
					"interval_uom: " + str(row.get("interval_uom") or ""),
					"medical_code: " + str(row.get("medical_code") or "No medical code"),
					"Doctor's comment: " + (row.get("comment") or "Take medication as per dosage."),
				]
			)

			new_row = {
				"item_code": item_code,
				"item_name": item_name,
				"description": item_description,
				"dosage_info": dosage_info,
				"qty": row.quantity - row.quantity_returned,
				"delivery_date": nowdate(),
				"warehouse": so_doc.set_warehouse,
				"reference_dt": row.get("doctype"),
				"reference_dn": row.get("name"),
				"healthcare_practitioner": encounter_doc.get("practitioner"),
				"healthcare_service_unit": encounter_doc.get("healthcare_service_unit"),
			}

			so_doc.append("items", new_row)

		so_doc.med_change_request_status = "Approved"
		so_doc.save(ignore_permissions=True)
		so_doc.add_comment(
			comment_type="Comment",
			text=f"Medication Change Request: {frappe.bold(self.name)} is Approved",
		)
		so_doc.reload()

	def update_delivery_note(self, encounter_doc):
		dn_doc = frappe.get_cached_doc("Delivery Note", self.delivery_note)
		dn_doc.items = []
		dn_doc.hms_tz_original_items = []

		for row in encounter_doc.drug_prescription:
			warehouse = get_warehouse_from_service_unit(row.healthcare_service_unit)
			if warehouse != dn_doc.set_warehouse:
				continue

			if row.prescribe and (
				encounter_doc.insurance_subscription
				or (not encounter_doc.inpatient_record and not encounter_doc.insurance_subscription)
			):
				continue

			if row.is_not_available_inhouse or row.is_cancelled:
				continue

			item_code, uom = frappe.get_cached_value("Medication", row.drug_code, ["item", "stock_uom"])
			is_stock, item_name = frappe.get_cached_value("Item", item_code, ["is_stock_item", "item_name"])
			if not is_stock:
				continue

			item = frappe.new_doc("Delivery Note Item")
			item.item_code = item_code
			item.item_name = item_name
			item.warehouse = warehouse
			item.qty = row.delivered_quantity or 1
			item.medical_code = row.medical_code
			item.rate = row.amount
			item.amount = row.amount * row.delivered_quantity
			item.reference_doctype = row.doctype
			item.reference_name = row.name
			item.is_restricted = row.is_restricted
			item.discount_percentage = row.hms_tz_is_discount_percent
			item.hms_tz_is_discount_applied = row.hms_tz_is_discount_applied
			item.description = ", <br>".join(
				[
					"frequency: " + str(row.get("dosage") or "No Prescription Dosage"),
					"period: " + str(row.get("period") or "No Prescription Period"),
					"dosage_form: " + str(row.get("dosage_form") or ""),
					"interval: " + str(row.get("interval") or ""),
					"interval_uom: " + str(row.get("interval_uom") or ""),
					"medical_code: " + str(row.get("medical_code") or "No medical code"),
					"Doctor's comment: " + (row.get("comment") or "Take medication as per dosage."),
				]
			)
			dn_doc.append("items", item)

			new_original_item = set_original_items(dn_doc.name, item)
			new_original_item.stock_uom = uom
			new_original_item.uom = uom
			dn_doc.append("hms_tz_original_items", new_original_item)

		dn_doc.save(ignore_permissions=True)
		dn_doc.reload()

		self.update_delivery_note_workflow("Changes Made", "Make Changes", dn_doc=dn_doc)

		self.update_drug_prescription(encounter_doc, dn_doc)

	def update_delivery_note_workflow(self, state, action, dn_doc=None):
		if not dn_doc:
			dn_doc = frappe.get_cached_doc("Delivery Note", self.delivery_note)

		if dn_doc.form_sales_invoice:
			url = get_url_to_form("sales Invoice", dn_doc.form_sales_invoice)
			frappe.throw(
				f"Cannot create medication change request for items paid in cash,<br>\
                please refer sales invoice: <a href='{url}'>{frappe.bold(dn_doc.form_sales_invoice)}</a>"
			)

		try:
			if dn_doc.workflow_state != state:
				apply_workflow(dn_doc, action)
				dn_doc.reload()

				if dn_doc.workflow_state == "Changes Made":
					frappe.msgprint(
						_("Delivery Note " + self.delivery_note + " has been updated!"),
						alert=True,
					)

		except Exception:
			if state == "Changes Made":
				frappe.log_error(
					title=f"{self.doctype}: {self.name}",
					message=frappe.get_traceback(),
				)
				frappe.throw(f"Apply workflow error for delivery note: {frappe.bold(dn_doc.name)}")

			else:
				frappe.log_error(
					title=f"{self.doctype}: {self.name}",
					message=frappe.get_traceback(),
				)
				frappe.msgprint(f"Apply workflow error for delivery note: {frappe.bold(dn_doc.name)}")
				frappe.throw("Medication Change Request was not created, try again")

	def update_drug_prescription(self, patient_encounter_doc, dn_doc):
		for d in patient_encounter_doc.drug_prescription:
			for item in dn_doc.items:
				if d.name == item.reference_name:
					frappe.db.set_value(
						"Drug Prescription",
						item.reference_name,
						{
							"dn_detail": item.name,
							"delivery_note": dn_doc.name,
						},
						update_modified=False,
					)

	def update_hsr_and_hre(self):
		"""Update Healthcare Service Request and Hospital Revenue Entry after Medication Change Request is submitted"""

		frappe.enqueue(
			"hms_tz.nhif.doctype.medication_change_request.medication_change_request.update_hsr_hre_for_mcr",
			timeout=300,
			queue="short",
			mcr_name=self.name,
		)


@frappe.whitelist()
def get_delivery_note(patient, patient_encounter):
	d_list = frappe.get_all(
		"Delivery Note",
		filters={"reference_name": patient_encounter, "docstatus": 0},
		fields=["name", "set_warehouse"],
	)
	if len(d_list) > 1:
		frappe.throw(
			f"""There is {frappe.bold(len(d_list))} delivery note of IPD and OPD warehouses, for patient: {frappe.bold(patient)}, and encounter: {frappe.bold(patient_encounter)}, \
            Please choose one delivery note between {frappe.bold(d_list[0].name + ": warehouse: " + d_list[0].set_warehouse)} and {frappe.bold(d_list[1].name + ": warehouse: " + d_list[1].set_warehouse)}"""
		)

	if len(d_list) == 0:
		return ""

	if len(d_list) == 1:
		return d_list[0].name


@frappe.whitelist()
def get_patient_encounter_name(delivery_note, sales_order):
	if delivery_note:
		return frappe.get_cached_value("Delivery Note", delivery_note, "reference_name")

	elif sales_order:
		return frappe.get_cached_value("Sales Order", sales_order, "patient_encounter")

	return ""


@frappe.whitelist()
def get_patient_encounter_doc(patient_encounter: str):
	doc = frappe.get_doc("Patient Encounter", patient_encounter)
	return doc


def set_amount(self, row, mop=""):
	item_code = frappe.get_cached_value("Medication", row.drug_code, "item")

	# apply discount if it is available on Heathcare Insurance Company
	discount_percent = 0
	if self.insurance_company and "NHIF" not in self.insurance_company:
		discount_percent = get_discount_percent(self.insurance_company)

	if self.insurance_subscription and not row.prescribe:
		amount = get_item_rate(item_code, self.company, self.insurance_subscription, self.insurance_company)
		row.amount = amount - (amount * (discount_percent / 100))
		if discount_percent > 0:
			row.hms_tz_is_discount_applied = 1
			row.hms_tz_is_discount_percent = discount_percent

	elif not self.insurance_subscription:
		if not row.prescribe:
			row.prescribe = 1

		row.amount = get_mop_amount(item_code, mop, self.company, self.patient)


@frappe.whitelist()
def validate_healthcare_service_unit(warehouse, item, method):
	if warehouse != get_warehouse_from_service_unit(item.healthcare_service_unit):
		msgThrow(
			_(
				f"Please change healthcare service unit: {frappe.bold(item.healthcare_service_unit)}, \
                for drug: {frappe.bold(item.drug_code)} row: {frappe.bold(item.idx)}\
                as it is of different warehouse"
			),
			method,
		)


@frappe.whitelist()
def get_items_on_change_of_delivery_note(name, encounter, delivery_note):
	doc = frappe.get_cached_doc("Medication Change Request", name)

	if not doc or not encounter or not delivery_note:
		return

	patient_encounter_doc = get_patient_encounter_doc(encounter)
	delivery_note_doc = frappe.get_cached_doc("Delivery Note", delivery_note)

	doc.drug_prescription = []
	doc.original_pharmacy_prescription = []
	for item_line in patient_encounter_doc.drug_prescription:
		if delivery_note_doc.set_warehouse != get_warehouse_from_service_unit(
			item_line.healthcare_service_unit
		):
			continue

		doc.set_drugs(
			item_line,
			inpatient_record=patient_encounter_doc.inpatient_record,
		)

	doc.delivery_note = delivery_note
	doc.warehouse = delivery_note_doc.set_warehouse
	doc.save(ignore_permissions=True)
	doc.reload()
	return doc


@frappe.whitelist()
def get_items_on_change_of_sales_order(name, encounter, sales_order):
	doc = frappe.get_cached_doc("Medication Change Request", name)

	if not doc or not encounter or not sales_order:
		return

	patient_encounter_doc = get_patient_encounter_doc(encounter)

	doc.drug_prescription = []
	doc.original_pharmacy_prescription = []
	for item_line in patient_encounter_doc.drug_prescription:
		doc.set_drugs(item_line)

	doc.sales_order = sales_order
	doc.warehouse = frappe.get_cached_value("Sales Order", sales_order, "set_warehouse")
	doc.save(ignore_permissions=True)
	doc.reload()
	return doc


def get_fields_to_clear():
	return [
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
	]


def set_original_items(name, item):
	new_row = item.as_dict()
	for fieldname in get_fields_to_clear():
		new_row[fieldname] = None

	new_row.update(
		{
			"parent": name,
			"parentfield": "hms_tz_original_items",
			"parenttype": "Delivery Note",
			"doctype": "Original Delivery Note Item",
		}
	)

	return new_row


@frappe.whitelist()
def create_medication_change_request_from_dn(doctype, name):
	source_doc = frappe.get_cached_doc(doctype, name)

	if source_doc.form_sales_invoice:
		url = get_url_to_form("sales Ivoice", source_doc.form_sales_invoice)
		frappe.throw(
			f"Cannot create medicaton change request for items paid in cash,<br>\
            please refer sales invoice: <a href='{url}'>{frappe.bold(source_doc.form_sales_invoice)}</a>"
		)

	if not source_doc.hms_tz_comment:
		frappe.throw(
			"<b>No comment found on the delivery note, Please keep a comment and save the delivery note, before creating med change request</b>"
		)

	doc = frappe.new_doc("Medication Change Request")
	doc.patient = source_doc.patient
	doc.patient_name = source_doc.patient_name
	doc.appointment = source_doc.hms_tz_appointment_no
	doc.company = source_doc.company
	doc.patient_encounter = source_doc.reference_name
	doc.delivery_note = source_doc.name
	doc.healthcare_practitioner = source_doc.healthcare_practitioner
	doc.hms_tz_comment = source_doc.hms_tz_comment
	doc.warehouse = source_doc.set_warehouse

	validate_nhif_patient_claim_status("Medication Change Request", doc.company, doc.appointment)

	doc.save(ignore_permissions=True)
	url = get_url_to_form(doc.doctype, doc.name)
	frappe.msgprint(
		f"Draft Medication Change Request: <a href='{url}'>{frappe.bold(doc.name)}</a> is created"
	)
	return doc.name


@frappe.whitelist()
def create_medication_change_request_from_so(doctype, name):
	source_doc = frappe.get_cached_doc(doctype, name)

	if not source_doc.med_change_request_comment:
		frappe.throw(
			"<b>No comment found on the sales order,\
                Please keep a comment and save the sales order, before creating med change request</b>"
		)

	appointment, practitioner = frappe.get_cached_value(
		"Patient Encounter",
		source_doc.patient_encounter,
		["appointment", "practitioner"],
	)
	doc = frappe.new_doc("Medication Change Request")
	doc.patient = source_doc.patient
	doc.patient_name = source_doc.patient_name
	doc.appointment = appointment
	doc.company = source_doc.company
	doc.patient_encounter = source_doc.patient_encounter
	doc.sales_order = source_doc.name
	doc.healthcare_practitioner = practitioner
	doc.hms_tz_comment = source_doc.med_change_request_comment
	doc.warehouse = source_doc.set_warehouse

	doc.save(ignore_permissions=True)
	url = get_url_to_form(doc.doctype, doc.name)
	frappe.msgprint(
		f"Draft Medication Change Request: <a href='{url}'>{frappe.bold(doc.name)}</a> is created"
	)
	return doc.name


@frappe.whitelist()
def get_service_unit(warehouse, company, service_unit_type):
	service_units = frappe.get_all(
		"Healthcare Service Unit",
		filters={
			"warehouse": warehouse,
			"company": company,
			"service_unit_type": service_unit_type,
		},
		fields=["name"],
		limit=1,
	)

	if service_units:
		return service_units[0].name

	return None


def update_hsr_hre_for_mcr(mcr_name):
	"""Update Healthcare Service Request with new Drug Prescription

	This function is called via enqueue after MCR submission.
	It compares original vs current drugs in MCR to determine:
	- Which drugs were removed (need to delete from HSR)
	- Which drugs were added (need to add to HSR)
	- Which drugs remain (need to update in HSR)

	Args:
	    mcr_name: Medication Change Request name
	"""

	sleep(60)

	# Reload MCR document fresh from database
	mcr_doc = frappe.get_doc("Medication Change Request", mcr_name)

	# Original items = items that were in MCR before user made changes
	original_drug_codes = set()
	for d in mcr_doc.original_pharmacy_prescription:
		original_drug_codes.add(d.drug_code)

	# Current items = items in MCR after user made changes (excluding cancelled/not available)
	current_drug_codes = set()
	for d in mcr_doc.drug_prescription:
		if d.is_not_available_inhouse == 1 or d.is_cancelled == 1:
			continue

		current_drug_codes.add(d.drug_code)

	# Calculate what changed
	removed_drug_codes = original_drug_codes - current_drug_codes  # Items removed by user
	added_drug_codes = current_drug_codes - original_drug_codes  # Items added by user
	unchanged_drug_codes = (
		original_drug_codes & current_drug_codes
	)  # Items that remain (may have qty changes)

	try:
		update_insurance_hsr_hre(mcr_doc, removed_drug_codes, added_drug_codes, unchanged_drug_codes)

		update_cash_inpatient_hre(mcr_doc, removed_drug_codes, added_drug_codes, unchanged_drug_codes)

		re_update_drug_prescription(mcr_doc.delivery_note)
	except Exception:
		frappe.log_error(
			title=f"Error: MCR: {mcr_doc.name} updating HSR and HRE",
			message=frappe.get_traceback(),
		)


def update_insurance_hsr_hre(mcr_doc, removed_drug_codes, added_drug_codes, unchanged_drug_codes):
	"""Update Healthcare Service Request and Hospital Revenue Entry for insurance Medication Change Request
	Args:
	    mcr_doc: Medication Change Request document
	    removed_drug_codes: Set of drug codes that were removed in MCR
	    added_drug_codes: Set of drug codes that were newly added in MCR
	    unchanged_drug_codes: Set of drug codes that existed before and still exist
	"""

	if not mcr_doc.insurance_subscription:
		return

	# For insurance patients or non-inpatients, proceed with HSR updates
	hsr_id = frappe.get_cached_value(
		"Healthcare Service Request",
		{"source_doctype": "Patient Encounter", "source_docname": mcr_doc.patient_encounter},
		"name",
	)

	if not hsr_id:
		return

	services_to_be_removed = []
	hsr_doc = frappe.get_doc("Healthcare Service Request", hsr_id)

	# Step 1: Identify HSR services and payments to remove (for removed drugs)
	for service in hsr_doc.services:
		if service.service_type == "Medication" and service.service_name in removed_drug_codes:
			services_to_be_removed.append(service)

	for payment in hsr_doc.payments:
		if payment.service_type == "Medication" and payment.service_name in removed_drug_codes:
			services_to_be_removed.append(payment)

	# Step 2: Delete removed services and payments, and cancel their HRE
	for service in services_to_be_removed:
		# If it's a payment, cancel its HRE first
		if service.doctype == "Healthcare Service Request Payment":
			update_returned_or_cancelled_revenue_entry(
				service.ref_docname,
				"Medication Change Request",
				mcr_doc.name,
				is_cancelled=1,
				remarks=f"Reason for Service Replacement: <br><br>{frappe.bold(mcr_doc.hms_tz_comment)}"
				if mcr_doc.hms_tz_comment
				else "",
			)

		frappe.delete_doc(
			service.doctype,
			service.name,
			force=1,
			ignore_permissions=True,
			delete_permanently=True,
		)

	hsr_doc.reload()

	# Step 3: Build drug map from the UPDATED encounter for adding/updating services
	encounter_doc = get_patient_encounter_doc(mcr_doc.patient_encounter)

	drug_map = {}
	for d in encounter_doc.drug_prescription:
		if d.prescribe == 1 or d.is_not_available_inhouse == 1 or d.is_cancelled == 1:
			continue

		drug_map.setdefault(d.drug_code, []).append(d)

	# Step 4: Add or update services
	new_ref_docnames_for_hre = add_or_update_service(
		hsr_doc,
		drug_map,
		mcr_doc.name,
		mcr_doc.hms_tz_comment,
		added_drug_codes,
		unchanged_drug_codes,
	)

	# Step 5: Save HSR changes
	hsr_doc.db_update()
	hsr_doc.db_update_all()

	hsr_doc.reload()
	hsr_doc.run_method("before_save")
	hsr_doc.db_update()
	hsr_doc.db_update_all()
	hsr_doc.add_comment(
		comment_type="Comment",
		text=f"Changes made from Medication Change Request: <a href='{mcr_doc.get_url()}'>{frappe.bold(mcr_doc.name)}</a>",
	)

	hsr_doc.reload()

	# Step 6: Create HRE for newly added services
	if len(new_ref_docnames_for_hre) > 0:
		create_revenue_entry_from_insurance_mcr(mcr_doc, new_ref_docnames_for_hre)


def update_cash_inpatient_hre(mcr_doc, removed_drug_codes, added_drug_codes, unchanged_drug_codes):
	"""Update Hospital Revenue Entry for cash inpatient Medication Change Request
	Args:
	    mcr_doc: Medication Change Request document
	    removed_drug_codes: Set of drug codes that were removed in MCR
	    added_drug_codes: Set of drug codes that were newly added in MCR
	    unchanged_drug_codes: Set of drug codes that existed before and still exist
	"""

	enc_details = frappe.get_cached_value(
		"Patient Encounter",
		mcr_doc.patient_encounter,
		["inpatient_record", "insurance_subscription"],
		as_dict=True,
	)
	if enc_details.insurance_subscription or not enc_details.inpatient_record:
		return

	hre = DocType("Hospital Revenue Entry")
	updated_by = get_fullname(frappe.session.user)

	# For cash inpatients, cancel HRE for removed drugs
	if len(removed_drug_codes) > 0:
		remarks = (
			f"Reason for Service Replacement: <br><br>{frappe.bold(mcr_doc.hms_tz_comment)}"
			if mcr_doc.hms_tz_comment
			else ""
		)
		for drug_code in removed_drug_codes:
			# Create fresh query for each drug to avoid accumulating conditions
			cancel_query = (
				frappe.qb.update(hre)
				.set(hre.is_cancelled, 1)
				.set(hre.remarks, remarks)
				.set(hre.updated_by, updated_by)
				.set(hre.updated_from_doctype, mcr_doc.doctype)
				.set(hre.updated_from_docname, mcr_doc.name)
				.where(
					(hre.patient == mcr_doc.patient)
					& (hre.source_doctype == "Patient Encounter")
					& (hre.source_docname == mcr_doc.patient_encounter)
					& (hre.service_type == "Medication")
					& (hre.service_name == drug_code)
				)
			)
			cancel_query.run()

	# Create HRE for newly added drugs and update qty, rate & amount for unchanged drugs
	if len(added_drug_codes) > 0 or len(unchanged_drug_codes) > 0:
		new_ref_docnames = []
		remarks = (
			f"Reason for Qty Change: <br><br>{frappe.bold(mcr_doc.hms_tz_comment)}"
			if mcr_doc.hms_tz_comment
			else ""
		)

		encounter_doc = get_patient_encounter_doc(mcr_doc.patient_encounter)
		for d in encounter_doc.drug_prescription:
			if d.is_cancelled == 1 or d.is_not_available_inhouse == 1:
				continue

			if d.drug_code in added_drug_codes:
				new_ref_docnames.append(d.name)

			if d.drug_code in unchanged_drug_codes:
				qty = d.quantity - d.quantity_returned
				amount = d.amount * qty

				# Create fresh query for each drug to avoid accumulating conditions
				update_query = (
					frappe.qb.update(hre)
					.set(hre.qty, qty)
					.set(hre.rate, d.amount)
					.set(hre.amount, amount)
					.set(hre.remarks, remarks)
					.set(hre.updated_by, updated_by)
					.set(hre.updated_from_doctype, mcr_doc.doctype)
					.set(hre.updated_from_docname, mcr_doc.name)
					.where(
						(hre.patient == mcr_doc.patient)
						& (hre.source_doctype == "Patient Encounter")
						& (hre.source_docname == mcr_doc.patient_encounter)
						& (hre.service_type == "Medication")
						& (hre.service_name == d.drug_code)
					)
				)
				update_query.run()

		if len(new_ref_docnames) > 0:
			create_revenue_entry_from_inpatient_cash_mcr(mcr_doc, new_ref_docnames)


def add_or_update_service(
	hsr_doc,
	drug_map,
	mcr_id,
	mcr_comment,
	added_drug_codes,
	unchanged_drug_codes,
):
	"""Add or update services in the Healthcare Service Request

	Args:
	    hsr_doc: Healthcare Service Request document
	    drug_map: Dict mapping drug_code to list of Drug Prescription rows
	    mcr_id: Medication Change Request name
	    mcr_comment: Comment/reason for the change
	    added_drug_codes: Set of drug codes that were newly added in MCR
	    unchanged_drug_codes: Set of drug codes that existed before and still exist
	"""

	new_ref_docnames_for_hre = []

	# Process each drug in the map
	for drug_code, prescriptions in drug_map.items():
		# Skip drugs that are not in added or unchanged sets
		# (these would be drugs from other parts of the encounter not related to this MCR)
		if drug_code not in added_drug_codes and drug_code not in unchanged_drug_codes:
			continue

		existing_service = None

		# Check if service already exists in HSR
		for service in hsr_doc.services:
			if service.service_type == "Medication" and service.service_name == drug_code:
				existing_service = service
				break

		# Calculate aggregated values from all prescriptions of this drug
		total_qty = sum(row.delivered_quantity or row.quantity for row in prescriptions)
		has_copayment = any(row.has_copayment for row in prescriptions)
		is_restricted = any(row.is_restricted for row in prescriptions)
		discount_applied = any(row.hms_tz_is_discount_applied for row in prescriptions)

		# Use the first prescription for reference fields
		first_prescription = prescriptions[0]

		if existing_service and drug_code in unchanged_drug_codes:
			# Update existing service (drug existed before and still exists, possibly with qty change)
			existing_service.qty = total_qty
			existing_service.has_copayment = has_copayment
			existing_service.is_restricted = is_restricted
			existing_service.discount_applied = discount_applied
			existing_service.department_hsu = first_prescription.healthcare_service_unit
			existing_service.ref_docname = first_prescription.name
			existing_service.ref_doctype = first_prescription.doctype

			# Recalculate amounts
			updated_service = set_service_amounts(
				existing_service,
				hsr_doc.company,
				hsr_doc.insurance_company,
				hsr_doc.insurance_subscription,
			)

			updated_service.db_update()

			# Update corresponding payment entries
			new_payment = update_service_payments(
				hsr_doc,
				updated_service,
				first_prescription.delivery_note,
				first_prescription.dn_detail,
				mcr_id,
				mcr_comment,
			)

			if new_payment:
				# Track for HRE creation if a new payment was created
				new_ref_docnames_for_hre.append(first_prescription.name)
		else:
			# Add new service
			new_service = hsr_doc.append("services", {})
			new_service.update(
				{
					"service_type": "Medication",
					"service_name": drug_code,
					"qty": total_qty,
					"has_copayment": has_copayment,
					"is_restricted": is_restricted,
					"discount_applied": discount_applied,
					"department_hsu": first_prescription.healthcare_service_unit,
					"ref_docname": first_prescription.name,
					"ref_doctype": first_prescription.doctype,
					"insurance_company": hsr_doc.insurance_company,
					"insurance_subscription": hsr_doc.insurance_subscription,
					"payor_plan": hsr_doc.insurance_coverage_plan,
					"item_code": get_item_refcode(
						"Medication",
						drug_code,
						hsr_doc.company,
						hsr_doc.insurance_company,
					),
				}
			)

			new_service.percent_covered = hsr_doc.get_percent_covered(item_obj=new_service)

			# Calculate amounts for new service
			updated_service = set_service_amounts(
				new_service,
				hsr_doc.company,
				hsr_doc.insurance_company,
				hsr_doc.insurance_subscription,
			)

			# Create corresponding payment entries
			create_service_payments(
				hsr_doc,
				updated_service,
				first_prescription.delivery_note,
				first_prescription.dn_detail,
			)

			# Track for HRE creation
			new_ref_docnames_for_hre.append(first_prescription.name)

	return new_ref_docnames_for_hre


def update_service_payments(hsr_doc, service_row, delivery_note, dn_detail, mcr_id, mcr_comment):
	"""Update existing HSR payment entries for a service

	This function handles multiple payment entries for a single medication/drug.
	Each payment entry represents different payment methods (Insurance, Cash, etc.)
	with their own percent_covered and amounts.
	"""

	# Find existing payments for this service
	existing_payments = []
	for payment in hsr_doc.payments:
		if payment.service_type == "Medication" and payment.service_name == service_row.service_name:
			existing_payments.append(payment)

	if existing_payments:
		updated_by = get_fullname(frappe.session.user)
		hre_comment = f"Reason for Qty Change: <br><br>{frappe.bold(mcr_comment)}" if mcr_comment else ""

		# Update existing payment entries with new values
		for payment in existing_payments:
			old_payor_plan = payment.payor_plan
			old_ref_docname = payment.ref_docname
			old_ref_doctype = payment.ref_doctype

			payment.qty = service_row.qty
			payment.amount = ((payment.percent_covered / 100) * payment.rate) * service_row.qty
			payment.ref_docname = service_row.ref_docname
			payment.ref_doctype = service_row.ref_doctype
			payment.department_hsu = service_row.department_hsu
			payment.has_copayment = service_row.has_copayment
			payment.is_restricted = service_row.is_restricted
			payment.lrpmt_doc_created = 1
			payment.lrpmt_status = "Draft"
			payment.dn_detail = dn_detail
			payment.lrpmt_docname = delivery_note
			payment.lrpmt_doctype = "Delivery Note"

			payment.db_update()
			payment.reload()

			# Update revenue entry if necessary and if payor plan is not Cash
			# (Cash HRE will be updated via sales invoice)
			if old_payor_plan and old_payor_plan != "Cash":
				hre = DocType("Hospital Revenue Entry")
				query = (
					frappe.qb.update(hre)
					.set(hre.qty, payment.qty)
					.set(hre.amount, payment.amount)
					.set(hre.ref_docname, payment.ref_docname)
					.set(hre.ref_doctype, payment.ref_doctype)
					.set(hre.lrpmt_status, payment.lrpmt_status)
					.set(hre.lrpmt_docname, payment.lrpmt_docname)
					.set(hre.lrpmt_doctype, payment.lrpmt_doctype)
					.set(hre.healthcare_service_unit, payment.department_hsu)
					.set(hre.updated_by, updated_by)
					.set(hre.updated_from_doctype, "Medication Change Request")
					.set(hre.updated_from_docname, mcr_id)
					.set(hre.remarks, hre_comment)
					.where(
						(hre.service_name == service_row.service_name)
						& (hre.ref_doctype == old_ref_doctype)
						& (hre.ref_docname == old_ref_docname)
						& (hre.insurance_coverage_plan == old_payor_plan)
					)
				)
				query.run()
	else:
		# Create new payment entry if none exists
		# This should rarely happen for unchanged drugs, but handles edge cases
		new_payment = create_service_payments(hsr_doc, service_row, delivery_note, dn_detail)

		return new_payment


def create_service_payments(hsr_doc, service_row, delivery_note, dn_detail):
	"""Create payment entries for a new service"""

	ref_code = get_item_refcode(
		"Medication",
		service_row.get("service_name"),
		hsr_doc.company,
		hsr_doc.insurance_company,
	)

	# Get percent_covered from service_row or default to 100
	percent_covered = service_row.get("percent_covered") or 100

	# Create payment entry based on insurance subscription
	new_payment = frappe.get_doc(
		{
			"doctype": "Healthcare Service Request Payment",
			"parent": hsr_doc.name,
			"parentfield": "payments",
			"parenttype": "Healthcare Service Request",
			"service_name": service_row.get("service_name"),
			"service_type": "Medication",
			"item_code": ref_code,
			"qty": service_row.qty,
			"rate": service_row.rate,
			"amount": ((percent_covered / 100) * service_row.rate) * service_row.qty,
			"price_list": service_row.price_list,
			"ref_docname": service_row.ref_docname,
			"ref_doctype": service_row.ref_doctype,
			"lrpmt_doc_created": 1,
			"lrpmt_doctype": "Delivery Note",
			"lrpmt_docname": delivery_note,
			"dn_detail": dn_detail,
			"lrpmt_status": "Draft",
			"department_hsu": service_row.department_hsu,
			"has_copayment": service_row.has_copayment,
			"is_restricted": service_row.is_restricted,
			"discount_applied": service_row.get("discount_applied"),
			"insurance_subscription": hsr_doc.insurance_subscription,
			"payor_plan": hsr_doc.insurance_coverage_plan,
			"insurance_company": hsr_doc.insurance_company,
			"payment_type": "Insurance" if hsr_doc.insurance_subscription else "Cash",
			"percent_covered": percent_covered,
			"years_of_insurance": hsr_doc.years_of_insurance,
			"authorization_number": frappe.get_cached_value(
				"Patient Appointment", hsr_doc.appointment, "authorization_number"
			),
		}
	)
	new_payment.flags.ignore_permissions = True
	new_payment.flags.ignore_mandatory = True
	new_payment.insert()
	new_payment.reload()

	return new_payment


def re_update_drug_prescription(delivery_note):
	"""
	Re-update Drug Prescription entries linked to the Delivery Note
	after Medication Change Request submission to ensure they reflect
	the latest changes.

	This update is only for Delivery Notes that are submitted (docstatus == 1).

	params:
	    delivery_note (str): The name of the Delivery Note to update.
	"""
	dn_doc = frappe.get_doc("Delivery Note", delivery_note)
	if dn_doc.docstatus == 0:
		return

	update_drug_prescription(dn_doc)
