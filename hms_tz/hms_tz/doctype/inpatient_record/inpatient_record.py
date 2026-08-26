# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import json

import frappe
from frappe import _
from frappe.desk.reportview import get_match_cond
from frappe.model.document import Document
from frappe.utils import get_datetime, getdate, now_datetime, today


class InpatientRecord(Document):
	def before_insert(self):
		self.validate_already_scheduled_or_admitted()

	def after_insert(self):
		frappe.db.set_value("Patient", self.patient, "inpatient_record", self.name)
		frappe.db.set_value("Patient", self.patient, "inpatient_status", self.status)

		if self.admission_encounter:  # Update encounter
			frappe.db.set_value(
				"Patient Encounter",
				self.admission_encounter,
				"inpatient_record",
				self.name,
			)
			frappe.db.set_value(
				"Patient Encounter",
				self.admission_encounter,
				"inpatient_status",
				self.status,
			)

	def validate(self):
		self.validate_dates()
		if self.status == "Discharged":
			if not frappe.db.exists(
				"Inpatient Record",
				{
					"patient": self.patient,
					"status": [
						"in",
						[
							"Admitted",
							"Admission Scheduled",
							"Discharge Scheduled",
						],
					],
					"name": ["!=", self.name],
				},
			):
				frappe.db.set_value("Patient", self.patient, "inpatient_status", None)
				frappe.db.set_value("Patient", self.patient, "inpatient_record", None)

	def validate_dates(self):
		if (getdate(self.expected_discharge) < getdate(self.scheduled_date)) or (
			getdate(self.discharge_ordered_date) < getdate(self.scheduled_date)
		):
			frappe.throw(_("Expected and Discharge dates cannot be less than Admission Schedule date"))

		for entry in self.inpatient_occupancies:
			if (
				entry.check_in
				and entry.check_out
				and get_datetime(entry.check_in) > get_datetime(entry.check_out)
			):
				frappe.throw(_(f"Row #{entry.idx}: Check Out datetime cannot be less than Check In datetime"))

	def validate_already_scheduled_or_admitted(self):
		query = """
			select name, status
			from `tabInpatient Record`
			where (status = 'Admitted' or status = 'Admission Scheduled')
			and patient = %(patient)s
			"""

		ip_record = frappe.db.sql(query, {"patient": self.patient}, as_dict=1)

		if len(ip_record) > 0:
			msg = _(
				f"""Already {ip_record[0].status} Patient {self.patient} with Inpatient Record: \
                    <b><a href="#Form/Inpatient Record/{ip_record[0].name}">{ip_record[0].name}</a></b>"""
			)
			frappe.throw(msg)

	@frappe.whitelist()
	def admit(
		self,
		service_unit,
		check_in,
		admission_no=None,
		admission_type=None,
		poc_reference_no=None,
		expected_discharge=None,
	):
		return admit_patient(
			self, service_unit, check_in, admission_no, admission_type, poc_reference_no, expected_discharge
		)

	@frappe.whitelist()
	def discharge(self, discharge_type=None):
		return discharge_patient(self, discharge_type)

	@frappe.whitelist()
	def transfer(self, service_unit, check_in, leave_from, poc_reference_no=None):
		return transfer_patient(
			self,
			service_unit,
			check_in,
			check_out=check_in,
			leave_from=leave_from,
			poc_reference_no=poc_reference_no,
		)

	@frappe.whitelist()
	def add_bed(self, service_unit, check_in, check_out, left):
		add_bed_charge(self, service_unit, check_in, check_out, left)


@frappe.whitelist()
def schedule_inpatient(args):
	admission_order = json.loads(args)  # admission order via Encounter
	if not admission_order or not admission_order["patient"] or not admission_order["admission_encounter"]:
		frappe.throw(_("Missing required details, did not create Inpatient Record"))

	inpatient_record = frappe.new_doc("Inpatient Record")

	# Admission order details
	set_details_from_ip_order(inpatient_record, admission_order)

	# Patient details
	patient = frappe.get_cached_doc("Patient", admission_order["patient"])
	inpatient_record.patient = patient.name
	inpatient_record.patient_name = patient.patient_name
	inpatient_record.gender = patient.sex
	inpatient_record.blood_group = patient.blood_group
	inpatient_record.dob = patient.dob
	inpatient_record.mobile = patient.mobile
	inpatient_record.email = patient.email
	inpatient_record.phone = patient.phone
	inpatient_record.scheduled_date = admission_order["admission_ordered_for"]

	# Set encounter detials
	encounter = frappe.get_cached_doc("Patient Encounter", admission_order["admission_encounter"])
	if encounter and encounter.symptoms:  # Symptoms
		set_ip_child_records(inpatient_record, "chief_complaint", encounter.symptoms)

	if encounter and encounter.diagnosis:  # Diagnosis
		set_ip_child_records(inpatient_record, "diagnosis", encounter.diagnosis)

	if encounter and encounter.drug_prescription:  # Medication
		set_ip_child_records(inpatient_record, "drug_prescription", encounter.drug_prescription)

	if encounter and encounter.lab_test_prescription:  # Lab Tests
		set_ip_child_records(
			inpatient_record,
			"lab_test_prescription",
			encounter.lab_test_prescription,
		)

	if encounter and encounter.procedure_prescription:  # Procedure Prescription
		set_ip_child_records(
			inpatient_record,
			"procedure_prescription",
			encounter.procedure_prescription,
		)

	if encounter and encounter.therapies:  # Therapies
		inpatient_record.therapy_plan = encounter.therapy_plan
		set_ip_child_records(inpatient_record, "therapies", encounter.therapies)

	if encounter and encounter.radiology_procedure_prescription:  # radiology
		set_ip_child_records(
			inpatient_record,
			"radiology_procedure_prescription",
			encounter.radiology_procedure_prescription,
		)

	if encounter and encounter.diet_recommendation:  # diet Prescription
		set_ip_child_records(
			inpatient_record,
			"diet_recommendation",
			encounter.diet_recommendation,
		)

	if encounter and encounter.source:  # Source
		inpatient_record.source = encounter.source

	if encounter and encounter.referring_practitioner:  # Referring Practitioner
		inpatient_record.referring_practitioner = encounter.referring_practitioner

	if encounter.get("insurance_subscription"):
		inpatient_record.insurance_subscription = encounter.insurance_subscription
	if encounter.get("insurance_coverage_plan"):
		inpatient_record.insurance_coverage_plan = encounter.insurance_coverage_plan
	if encounter.get("insurance_company"):
		inpatient_record.insurance_company = encounter.insurance_company

	inpatient_record.status = "Admission Scheduled"
	inpatient_record.save(ignore_permissions=True)


@frappe.whitelist()
def schedule_discharge(args):
	discharge_order = json.loads(args)
	inpatient_record_id = frappe.get_cached_value("Patient", discharge_order["patient"], "inpatient_record")
	if inpatient_record_id:
		inpatient_record = frappe.get_cached_doc("Inpatient Record", inpatient_record_id)
		check_out_inpatient(inpatient_record)
		set_details_from_ip_order(inpatient_record, discharge_order)
		validate_discharge(inpatient_record)
		inpatient_record.status = "Discharge Scheduled"
		inpatient_record.save(ignore_permissions=True)
		frappe.db.set_value(
			"Patient",
			discharge_order["patient"],
			"inpatient_status",
			inpatient_record.status,
		)
		frappe.db.set_value(
			"Patient Encounter",
			inpatient_record.discharge_encounter,
			"inpatient_status",
			inpatient_record.status,
		)


def set_details_from_ip_order(inpatient_record, ip_order):
	for key in ip_order:
		inpatient_record.set(key, ip_order[key])


def set_ip_child_records(inpatient_record, inpatient_record_child, encounter_child):
	for item in encounter_child:
		table = inpatient_record.append(inpatient_record_child)
		for df in table.meta.get("fields"):
			table.set(df.fieldname, item.get(df.fieldname))


def check_out_inpatient(inpatient_record):
	if inpatient_record.inpatient_occupancies:
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.left != 1:
				inpatient_occupancy.left = True
				inpatient_occupancy.check_out = now_datetime()
				frappe.db.set_value(
					"Healthcare Service Unit", inpatient_occupancy.service_unit, "occupancy_status", "Vacant"
				)


def discharge_patient(inpatient_record, discharge_type=None):
	validate_discharge(inpatient_record)
	validate_invoiced_inpatient(inpatient_record)
	inpatient_record.discharge_date = today()
	inpatient_record.status = "Discharged"
	inpatient_record.discharge_type = discharge_type

	inpatient_record.save(ignore_permissions=True)
	return True


def validate_invoiced_inpatient(inpatient_record):
	if inpatient_record.insurance_subscription:
		return
	if (
		frappe.get_cached_value(
			"HMS TZ Setting",
			inpatient_record.company,
			"allow_discharge_patient_with_pending_unbilled_invoices",
		)
		== 1
	):
		return

	pending_invoices = []
	if inpatient_record.inpatient_occupancies:
		service_unit_names = False
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.invoiced != 1 and inpatient_occupancy.is_confirmed == 1:
				if service_unit_names:
					service_unit_names += (
						f"<br>Bed: {inpatient_occupancy.service_unit}   RowNo: {inpatient_occupancy.idx}"
					)
				else:
					service_unit_names = (
						f"Bed: {inpatient_occupancy.service_unit}   RowNo: {inpatient_occupancy.idx}"
					)
		if service_unit_names:
			pending_invoices.append(f"<b>Inpatient Occupancy:</b><br> {service_unit_names}")

	if inpatient_record.inpatient_consultancy:
		consultancies = None
		for cons in inpatient_record.inpatient_consultancy:
			if cons.hms_tz_invoiced != 1 and cons.is_confirmed == 1:
				if consultancies:
					consultancies += f"<br>ConsItem: {cons.consultation_item}   RowNo: {cons.idx}"
				else:
					consultancies = f"ConsItem: {cons.consultation_item}   RowNo: {cons.idx}"
		if consultancies:
			pending_invoices.append(f"<br><br><b>Inpatient Consultancy:</b>  <br>{consultancies}")

	# docs = ["Patient Appointment", "Patient Encounter", "Lab Test", "Clinical Procedure"]
	# Changed on 2021-03-30 07:20:09 by MPCTZ to include only Patient
	# Appointment
	docs = ["Patient Appointment"]

	for doc in docs:
		doc_name_list = get_inpatient_docs_not_invoiced(doc, inpatient_record)
		if doc_name_list:
			pending_invoices = get_pending_doc(doc, doc_name_list, pending_invoices)

	if pending_invoices:
		frappe.throw(
			_(
				f"<b>Can not mark Inpatient Record Discharged, there are Unbilled Invoices:</b><br> {', '.join(pending_invoices)}"
			),
			title=_("Unbilled Invoices"),
		)


def get_pending_doc(doc, doc_name_list, pending_invoices):
	if doc_name_list:
		doc_ids = False
		for doc_name in doc_name_list:
			if doc_ids:
				doc_ids += ", " + doc_name.name
			else:
				doc_ids = doc_name.name
		if doc_ids:
			pending_invoices.append(doc + " (" + doc_ids + ")")

	return pending_invoices


def get_inpatient_docs_not_invoiced(doc, inpatient_record):
	return frappe.db.get_list(
		doc,
		filters={
			"patient": inpatient_record.patient,
			"inpatient_record": inpatient_record.name,
			"docstatus": 1,
			"invoiced": 0,
		},
	)


def admit_patient(
	inpatient_record,
	service_unit,
	check_in,
	admission_no=None,
	admission_type=None,
	poc_reference_no=None,
	expected_discharge=None,
):
	inpatient_record.admitted_datetime = check_in
	inpatient_record.status = "Admitted"
	inpatient_record.admission_no = admission_no
	inpatient_record.admission_type = admission_type
	inpatient_record.poc_reference_no = poc_reference_no
	inpatient_record.expected_discharge = expected_discharge

	inpatient_record.set("inpatient_occupancies", [])
	transfer_patient(
		inpatient_record, service_unit, check_in, admission_no=admission_no, poc_reference_no=poc_reference_no
	)

	frappe.db.set_value("Patient", inpatient_record.patient, "inpatient_status", "Admitted")
	frappe.db.set_value(
		"Patient",
		inpatient_record.patient,
		"inpatient_record",
		inpatient_record.name,
	)
	return True


def transfer_patient(
	inpatient_record,
	service_unit,
	check_in,
	check_out=None,
	leave_from=None,
	admission_no=None,
	poc_reference_no=None,
):
	if len(inpatient_record.inpatient_occupancies) > 0 and leave_from:
		for inpatient_occupancy in inpatient_record.inpatient_occupancies:
			if inpatient_occupancy.left != 1 and inpatient_occupancy.service_unit == leave_from:
				inpatient_occupancy.left = True
				inpatient_occupancy.check_out = check_out

				frappe.db.set_value(
					"Healthcare Service Unit",
					inpatient_occupancy.service_unit,
					"occupancy_status",
					"Vacant",
				)

	if service_unit:
		item_line = inpatient_record.append("inpatient_occupancies", {})
		item_line.service_unit = service_unit
		item_line.check_in = check_in

		frappe.db.set_value(
			"Healthcare Service Unit",
			service_unit,
			"occupancy_status",
			"Occupied",
		)

	if admission_no:
		inpatient_record.admission_no = admission_no

	if poc_reference_no:
		inpatient_record.poc_reference_no = poc_reference_no

	if service_unit or leave_from or admission_no or poc_reference_no:
		inpatient_record.save(ignore_permissions=True)

	return True


def add_bed_charge(inpatient_record, service_unit, check_in, check_out, left):
	item_line = inpatient_record.append("inpatient_occupancies", {})
	item_line.service_unit = service_unit
	item_line.check_in = check_in
	item_line.check_out = check_out
	item_line.left = left

	inpatient_record.save(ignore_permissions=True)


@frappe.whitelist()
@frappe.validate_and_sanitize_search_inputs
def get_leave_from(doctype, txt, searchfield, start, page_len, filters):
	docname = filters["docname"]

	query = """select io.service_unit
		from `tabInpatient Occupancy` io, `tabInpatient Record` ir
		where io.parent = '{docname}' and io.parentfield = 'inpatient_occupancies'
		and io.left!=1 and io.parent = ir.name"""

	return frappe.db.sql(
		query.format(
			**{
				"docname": docname,
				"searchfield": searchfield,
				"mcond": get_match_cond(doctype),
			}
		),
		{
			"txt": f"%{txt}%",
			"_txt": txt.replace("%", ""),
			"start": start,
			"page_len": page_len,
		},
	)


def validate_discharge(inpatient_record):
	if inpatient_record.status == "Admission Scheduled":
		frappe.throw(
			frappe.bold(
				"Cannot schedule discharge for the patient who was not admitted,<br><br>\
            Please inform receptionist to admit a patient before discharge"
			)
		)

	patient = inpatient_record.patient
	appointment = inpatient_record.patient_appointment

	conditions = {
		"patient": patient,
		"appointment": appointment,
		"inpatient_record": inpatient_record.name,
		"company": inpatient_record.company,
		"docstatus": 0,
	}

	lrpmt_msg = ""
	lrpmt_docs = frappe.db.get_all("LRPMT Returns", filters=conditions, fields=["name"])
	if lrpmt_docs:
		for d in lrpmt_docs:
			lrpmt_msg = _(
				lrpmt_msg
				+ f"LRPMT Returns: {frappe.bold(d.name)} to return and cancel items\
                was not submitted <br>"
			)

		lrpmt_msg += """<div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">\
              <p class="text-center"><i>please contact relevent department to Submit/Cancel draft LRPMT Returns\
                before Scheduling Discharge</i></p>
            </div>"""

	procedure_msg = ""
	procedure_docs = frappe.db.get_all(
		"Clinical Procedure",
		filters={
			"docstatus": 0,
			"patient": patient,
			"appointment": appointment,
			"ref_doctype": "Patient Encounter",
			"workflow_state": ["!=", "Not Serviced"],
		},
		fields=["name", "procedure_template"],
	)

	if procedure_docs:
		for procedure in procedure_docs:
			procedure_msg = _(
				procedure_msg
				+ f"Clinical Procedure: {frappe.bold(procedure['procedure_template'])} of {frappe.bold(procedure['name'])}\
                    was not Submitted <br>"
			)

		procedure_msg += """<div style="border-left: 4px solid #ffc107; background-color: #fff3cd; padding: 15px; border-radius: 10px; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.1); margin: 10px;">\
              <p class="text-center"><i>please contact relevent department to Submit/Cancel draft Clinical Procedure\
                before Scheduling Discharge</i></p>
            </div>"""

	msg_throw = lrpmt_msg + procedure_msg
	if msg_throw:
		frappe.throw(title="Discharge Stopped", msg=msg_throw)

	lab_msg = ""
	lab_docs = frappe.db.get_all(
		"Lab Test",
		filters={
			"docstatus": 0,
			"patient": patient,
			"appointment": appointment,
			"ref_doctype": "Patient Encounter",
			"workflow_state": ["!=", "Not Serviced"],
		},
		fields=["name", "template"],
	)

	if lab_docs:
		for lab in lab_docs:
			lab_msg = _(
				lab_msg
				+ f"<li>Lab Test: {frappe.bold(lab['template'])} of {frappe.bold(lab['name'])}\
                was not Submitted </li>"
			)

	radiology_msg = ""
	radiology_docs = frappe.db.get_all(
		"Radiology Examination",
		filters={
			"docstatus": 0,
			"patient": patient,
			"appointment": appointment,
			"ref_doctype": "Patient Encounter",
			"workflow_state": ["!=", "Not Serviced"],
		},
		fields=["name", "radiology_examination_template"],
	)

	if radiology_docs:
		for radiology in radiology_docs:
			radiology_msg = _(
				radiology_msg
				+ f"<li>Radiology Examination: {frappe.bold(radiology['radiology_examination_template'])} \
                    of {frappe.bold(radiology['name'])} was not Submitted </li>"
			)

	drug_msg = ""
	dn_name = frappe.db.get_all(
		"Delivery Note",
		filters={
			"docstatus": 0,
			"is_return": 0,
			"patient": patient,
			"hms_tz_appointment_no": appointment,
			"reference_doctype": "Patient Encounter",
		},
		fields=["name"],
	)

	if dn_name:
		for dn in dn_name:
			drug_msg = _(drug_msg + f"<li>Delivery Note: #{frappe.bold(dn.name)}, was not Submitted </li>")

	msg = "<ul>" + lab_msg + radiology_msg + drug_msg + "</ul>"

	if msg:
		frappe.msgprint(title="Notification", msg=msg)
