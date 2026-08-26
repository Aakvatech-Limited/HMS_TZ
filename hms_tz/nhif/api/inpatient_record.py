# Copyright (c) 2021, Aakvatech and contributors
# For license information, please see license.txt


import json

import frappe
from erpnext.accounts.doctype.sales_invoice.sales_invoice import get_bank_cash_account
from erpnext.accounts.party import get_party_account
from frappe import _
from frappe.utils import add_days, create_batch, date_diff, get_datetime, get_url_to_form, nowdate

from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import (
	create_inpatient_revenue_entries,
)
from hms_tz.nhif.api.healthcare_utils import (
	create_healthcare_docs,
	get_discount_percent,
	get_healthcare_services_to_invoice,
	get_item_price,
	get_item_rate,
	get_mop_amount,
	get_warehouse_from_service_unit,
	validate_nhif_patient_claim_status,
)
from hms_tz.nhif.api.patient_encounter import validate_patient_balance_vs_patient_costs


def before_insert(doc, method):
	validate_similary_authozation_number(doc)


def validate(doc, method):
	set_beds_price(doc)
	validate_inpatient_occupancies(doc)


def before_save(doc, method):
	if len(doc.inpatient_occupancies) == 0:
		return

	last_row = doc.inpatient_occupancies[len(doc.inpatient_occupancies) - 1]
	if last_row.service_unit:
		service_unit_type = frappe.get_cached_value(
			"Healthcare Service Unit",
			last_row.service_unit,
			"service_unit_type",
		)
		if doc.admission_service_unit_type != service_unit_type:
			doc.admission_service_unit_type = service_unit_type

	create_inpatient_revenue_entries(doc)


def validate_inpatient_occupancies(doc):
	if doc.is_new():
		return
	old_doc = frappe.get_cached_doc(doc.doctype, doc.name)
	count = 0
	for old_row in old_doc.inpatient_occupancies:
		count += 1
		if not old_row.is_confirmed:
			continue
		valid = True
		row = doc.inpatient_occupancies[count - 1]
		if str(row.check_in) != str(old_row.check_in):
			valid = False
		if str(row.check_out) != str(old_row.check_out):
			valid = False
		if str(row.get("amount", 0)) != str(old_row.get("amount", 0)):
			valid = False
		if row.left != old_row.left:
			valid = False
		if row.service_unit != old_row.service_unit:
			valid = False
		if not valid:
			frappe.msgprint(
				_(
					f"In Inpatient Occupancy line '{old_row.idx}' has been invoiced. It should not be modified or deleted"
				)
			)


def daily_update_inpatient_occupancies():
	def update_beds(occupancies):
		docs_to_process = []

		for item in occupancies:
			try:
				doc = frappe.get_doc("Inpatient Record", item.get("name"))
				occupancies_len = len(doc.inpatient_occupancies)

				if occupancies_len > 0:
					count = 0
					last_check_in = get_datetime(doc.inpatient_occupancies[-1].check_in)
					last_check_out = doc.inpatient_occupancies[-1].check_out or last_check_in
					date_count = date_diff(nowdate(), last_check_out)

					if date_count <= 0:
						continue

					last_row = doc.inpatient_occupancies[-1]
					if not last_row.left:
						base_check_in = get_datetime(last_row.check_in).replace(
							hour=0, minute=0, second=0, microsecond=0
						)
						new_rows_data = []

						while count < date_count:
							current_checkin_calc = add_days(base_check_in, count + 1)
							current_checkout_calc = add_days(current_checkin_calc, 1)

							new_rows_data.append(
								{
									"check_in": current_checkin_calc,
									"check_out": current_checkout_calc if count < date_count - 1 else None,
									"left": True if count < date_count - 1 else False,
									"service_unit": last_row.service_unit,
								}
							)
							count += 1

						if len(new_rows_data) == 0:
							continue

						last_row.left = True
						last_row.check_out = new_rows_data[0]["check_in"]

						for row_data in new_rows_data:
							doc.append("inpatient_occupancies", row_data)

						docs_to_process.append(doc)

			except Exception as e:
				frappe.log_error(
					title=f"Daily Update Beds Error for {item.get('name')}: {str(e)[:100]}",
					message=frappe.get_traceback(),
				)
				continue

		if docs_to_process:
			for doc in docs_to_process:
				try:
					doc.save(ignore_permissions=True)
				except Exception as e:
					frappe.log_error(
						title=f"Save Error for {doc.name}: {str(e)[:100]}", message=frappe.get_traceback()
					)
					continue

	occupancies = frappe.db.get_all("Inpatient Record", filters={"status": "Admitted"}, fields=["name"])

	if len(occupancies) == 0:
		return

	for batch in create_batch(occupancies, 50):
		update_beds(batch)
		frappe.db.commit()


@frappe.whitelist()
def confirmed(company, appointment, insurance_company=None):
	if insurance_company and "NHIF" in insurance_company:
		return validate_nhif_patient_claim_status(
			"Inpatient Record",
			company,
			appointment,
			insurance_company,
			"inpatient_record",
		)


def set_beds_price(self):
	if not self.inpatient_occupancies:
		return

	# apply discount if it is available on Heathcare Insurance Company
	discount_percent = 0
	if self.insurance_company and "NHIF" not in self.insurance_company:
		discount_percent = get_discount_percent(self.insurance_company)

	for bed in self.inpatient_occupancies:
		if bed.get("amount", 0) == 0:
			if self.insurance_subscription:
				service_unit_type = frappe.get_cached_value(
					"Healthcare Service Unit",
					bed.service_unit,
					"service_unit_type",
				)
				item_code = frappe.get_cached_value(
					"Healthcare Service Unit Type",
					service_unit_type,
					"item_code",
				)
				item_price = get_item_rate(item_code, self.company, self.insurance_subscription)
				bed.amount = item_price - (item_price * (discount_percent / 100))
				if discount_percent > 0:
					bed.hms_tz_is_discount_applied = 1
				payment_type = "Insurance"
			else:
				mode_of_payment = frappe.get_cached_value(
					"Patient Encounter",
					self.admission_encounter,
					"mode_of_payment",
				)
				service_unit_type = frappe.get_cached_value(
					"Healthcare Service Unit",
					bed.service_unit,
					"service_unit_type",
				)
				item_code = frappe.get_cached_value(
					"Healthcare Service Unit Type",
					service_unit_type,
					"item_code",
				)
				bed.amount = get_mop_amount(item_code, mode_of_payment, self.company, self.patient)
				payment_type = mode_of_payment
			frappe.msgprint(
				_(
					f"{payment_type} Bed prices set for {item_code} as of {str(bed.check_in)} for amount {str(bed.get('amount', 0))}"
				)
			)


def after_insert(doc, method):
	if not doc.admission_encounter:
		return

	encounter_list = [doc.admission_encounter]
	create_healthcare_docs(doc.admission_encounter, encounter_list, method="after_insert")


@frappe.whitelist()
def make_deposit(
	inpatient_record,
	deposit_amount,
	mode_of_payment,
	reference_number=None,
	reference_date=None,
):
	if float(deposit_amount) <= 0:
		frappe.throw(_("<b>Deposit amount cannot be less than or equal to zero</b>"))

	if not mode_of_payment:
		frappe.throw(_("The mode of payment is required"))

	if frappe.get_cached_value("Mode of Payment", mode_of_payment, "type") != "Cash":
		if not reference_number:
			frappe.throw(_("The reference number is required, since the mode of payment is not cash"))
		if not reference_date:
			frappe.throw(_("The reference date is required, since the mode of payment is not cash"))

	inpatient_record_doc = frappe.get_cached_doc("Inpatient Record", inpatient_record)
	if inpatient_record_doc.insurance_subscription:
		frappe.throw(_("You cannot make deposit for insurance patient"))

	customer = frappe.get_cached_value("Patient", inpatient_record_doc.patient, "customer")

	try:
		payment = frappe.new_doc("Payment Entry")
		payment.posting_date = nowdate()
		payment.payment_type = "Receive"
		payment.party_type = "Customer"
		payment.party = customer
		payment.company = inpatient_record_doc.company
		payment.mode_of_payment = str(mode_of_payment)
		payment.paid_from = get_party_account("Customer", customer, inpatient_record_doc.company)
		payment.paid_to = get_bank_cash_account(mode_of_payment, inpatient_record_doc.company)["account"]
		payment.paid_amount = float(deposit_amount)
		payment.received_amount = float(deposit_amount)
		payment.source_exchange_rate = 1
		payment.target_exchange_rate = 1
		payment.reference_no = reference_number
		payment.reference_date = reference_date
		payment.setup_party_account_field()
		payment.set_missing_values()
		payment.save()
		payment.reload()
		payment.submit()
		url = get_url_to_form(payment.doctype, payment.name)
		frappe.msgprint(
			f"Payment Entry: <a href='{url}'>{frappe.bold(payment.name)}</a> for Deposit is created successful"
		)
		return payment.name
	except Exception as e:
		frappe.msgprint(_(f"Error: <b>{e}</b>"))
		return False


@frappe.whitelist()
def create_sales_invoice(args):
	args = frappe._dict(json.loads(args))
	patient_encounter_list = frappe.get_all(
		"Patient Encounter",
		filters={
			"docstatus": 1,
			"patient": args.patient,
			"appointment": args.appointment_no,
			"inpatient_record": args.inpatient_record,
		},
		fields=["name", "inpatient_record"],
	)
	if len(patient_encounter_list) == 0:
		frappe.msgprint(
			_(
				f"No Patient Encounters found for this Inpatient Record: <b>{args.inpatient_record}</b> and Patient Appointment: <b>{args.appointment_no}</b>"
			)
		)
		return False

	services = get_healthcare_services_to_invoice(
		patient_encounter_list=patient_encounter_list,
	)
	if len(services) == 0:
		frappe.msgprint(
			_(
				f"No Healthcare Services found for this Inpatient Record: <b>{args.inpatient_record}</b> and Patient Appointment: <b>{args.appointment_no}</b>"
			)
		)
		return False

	invoice_doc = frappe.new_doc("Sales Invoice")
	invoice_doc.patient = args.patient
	invoice_doc.customer = frappe.get_cached_value("Patient", args.patient, "customer")
	invoice_doc.company = args.company
	mode_of_payment = frappe.get_cached_value(
		"Patient Encounter", patient_encounter_list[0].name, "mode_of_payment"
	)
	price_list = frappe.get_cached_value("Mode of Payment", mode_of_payment, "price_list")

	for service in services:
		item = invoice_doc.append("items", {})
		item.item_code = service.get("service")
		item.qty = service.get("qty")
		item.rate = get_item_price(service.get("service"), price_list, args.company)
		item.amount = item.rate * item.qty
		item.reference_dt = service.get("reference_type")
		item.reference_dn = service.get("reference_name")
		if item.reference_dt == "Drug Prescription":
			item.healthcare_service_unit = frappe.get_cached_value(
				service.get("reference_type"),
				service.get("reference_name"),
				"healthcare_service_unit",
			)
			item.warehouse = get_warehouse_from_service_unit(item.healthcare_service_unit)

	if hasattr(invoice_doc, "enabled_auto_create_delivery_notes"):
		invoice_doc.enabled_auto_create_delivery_notes = 0
	invoice_doc.update_stock = 0
	invoice_doc.is_pos = 0
	invoice_doc.allocate_advances_automatically = 1
	invoice_doc.set_missing_values()
	invoice_doc.set_taxes()
	invoice_doc.save()

	return invoice_doc.name


@frappe.whitelist()
def validate_inpatient_balance_vs_inpatient_cost(
	patient,
	patient_name,
	appointment,
	inpatient_record,
	company,
	inpatient_cost,
	cash_limit,
	caller=None,
):
	return validate_patient_balance_vs_patient_costs(
		patient,
		patient_name,
		appointment,
		inpatient_record,
		company,
		inpatient_cost=inpatient_cost,
		cash_limit=cash_limit,
		caller=caller,
	)


def validate_similary_authozation_number(doc):
	"""Validate if NHIF Patient Claim for this AuthorizationNo is already submitted."""

	if not doc.insurance_subscription:
		return

	insurance_company = doc.insurance_company

	if not insurance_company:
		insurance_company = frappe.get_cached_value(
			"Healthcare Insurance Subscription",
			doc.insurance_subscription,
			"insurance_company",
		)

	if insurance_company and "NHIF" in insurance_company:
		auth_no = frappe.get_cached_value(
			"Patient Appointment",
			doc.patient_appointment,
			"authorization_number",
		)
		claims = frappe.db.get_all(
			"NHIF Patient Claim",
			filters={"patient": doc.patient, "authorization_no": auth_no},
			fields=["name", "docstatus"],
		)
		if len(claims) > 0:
			is_submitted = False
			submitted_claim = None
			for row in claims:
				if row.docstatus == 1:
					is_submitted = True
					submitted_claim = row.name
					break

			if is_submitted:
				claim_url = get_url_to_form("NHIF Patient Claim", submitted_claim)
				app_url = get_url_to_form("Patient Appointment", doc.patient_appointment)
				msg = f"""<div style="  text-align: justify; border: 1px solid #ccc; background-color: #f9f9f9; padding: 10px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1); margin: 10px;">
                        NHIF Patient Claim: <a href='{claim_url}'><b>{submitted_claim}</b></a> for this AuthorizationNo: <b>{auth_no}</b> and Appointment: <a href='{app_url}'><b>{doc.patient_appointment}</b></a> is already submitted.<br><br>
                        <i>Please <strong>do not Admit this patient</strong>, Let patient ask for a new AuthorizationNo from NHIF.</i>
                    </div>"""
				frappe.throw(
					title=f"NHIF Patient Claim: <a href='{claim_url}'><b>{submitted_claim}</b></a> Already Submitted",
					msg=msg,
					exc=frappe.ValidationError,
				)


@frappe.whitelist()
def get_last_encounter(patient, inpatient_record):
	pe = frappe.qb.DocType("Patient Encounter")
	encounters = (
		frappe.qb.from_(pe)
		.select(pe.name)
		.where((pe.patient == patient) & (pe.inpatient_record == inpatient_record) & (pe.duplicated == 0))
	).run(as_dict=True)
	return encounters[0].name if len(encounters) > 0 else None
