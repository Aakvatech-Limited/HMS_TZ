# Copyright (c) 2022, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder import DocType
from frappe.query_builder.functions import Count


def execute(filters=None):
	if not filters:
		return

	columns = get_columns()
	records = get_data(filters)
	if len(records) == 0:
		frappe.msgprint(_("No records found for the selected filters"))
		return [], []

	data = sorted(
		records,
		key=lambda x: (
			x["appointment_date"],
			x["patient"],
			x["authorization_number"],
		),
	)

	return columns, data


def get_columns():
	return [
		{
			"fieldname": "appointment_date",
			"label": _("Appointment Date"),
			"fieldtype": "Date",
		},
		{"fieldname": "patient", "label": _("Patient"), "fieldtype": "Data"},
		{
			"fieldname": "patient_name",
			"label": _("Patient Name"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "appointment_no",
			"label": _("AppointmentNo"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "authorization_number",
			"label": _("AuthorizationNo"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "appointment_status",
			"label": _("Appointment Status"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "encounter",
			"label": _("Last Encounter"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "encounter_status",
			"label": _("Status of Last Encounter"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "inpatient_record",
			"label": _("Inpatient Record"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "inpatient_status",
			"label": _("Inpatient Status"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "nhif_patient_claim",
			"label": _("NHIF Patient Claim"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "signature",
			"label": _("Signature Captured"),
			"fieldtype": "Data",
		},
		{
			"fieldname": "claim_status",
			"label": _("Claim Status"),
			"fieldtype": "Data",
		},
	]


def get_appointment_data(filters):
	pa = DocType("Patient Appointment")
	ip = DocType("Inpatient Record")
	npc = DocType("NHIF Patient Claim")

	status_map = None
	if filters.status == "Open":
		status_map = pa.status == "Open"
	elif filters.status == "Closed":
		status_map = pa.status == "Closed"
	elif filters.status == "Scheduled":
		status_map = pa.status == "Scheduled"
	elif filters.status == "Cancelled":
		status_map = pa.status == "Cancelled"
	else:
		status_map = pa.status.isnotnull()

	q = (
		frappe.qb.from_(pa)
		.left_join(npc)
		.on(pa.nhif_patient_claim == npc.name)
		.select(
			pa.name.as_("appointment_no"),
			pa.patient,
			pa.patient_name,
			pa.appointment_date,
			pa.status.as_("appointment_status"),
			pa.authorization_number,
			pa.nhif_patient_claim,
			pa.coverage_plan_card_number,
			npc.patient_signature.as_("patient_signature"),
			npc.docstatus,
		)
		.where(
			(pa.appointment_date.between(filters.from_date, filters.to_date))
			& (pa.company == filters.company)
			& (pa.insurance_company.like("NHIF"))
			& (status_map)
		)
		.orderby(pa.appointment_date)
	)
	if filters.patient_type == "In-patient":
		q = q.inner_join(ip).on((pa.name == ip.patient_appointment) & (ip.insurance_company.like("NHIF")))
		q = q.select(
			ip.name.as_("inpatient_record"),
			ip.status.as_("inpatient_status"),
		)
	if filters.patient_type == "Out-patient":
		inpatient_appointmens = (
			frappe.qb.from_(ip)
			.select(ip.patient_appointment)
			.where(
				(ip.insurance_company.like("NHIF"))
				& (ip.patient_appointment.isnotnull())
				& (ip.scheduled_date.between(filters.from_date, filters.to_date))
			)
			.orderby(ip.scheduled_date)
		).run(as_dict=True)
		q = q.where(~pa.name.isin([d.patient_appointment for d in inpatient_appointmens]))

	if not filters.patient_type:
		q = q.left_join(ip).on((pa.name == ip.patient_appointment) & (ip.insurance_company.like("NHIF")))
		q = q.select(
			ip.name.as_("inpatient_record"),
			ip.status.as_("inpatient_status"),
		)
	appointment_data = q.run(as_dict=True)

	return appointment_data


def get_repeated_auth_no(filters):
	pa = DocType("Patient Appointment")

	status_map = None
	if filters.status == "Open":
		status_map = pa.status == "Open"
	elif filters.status == "Closed":
		status_map = pa.status == "Closed"
	elif filters.status == "Scheduled":
		status_map = pa.status == "Scheduled"
	elif filters.status == "Cancelled":
		status_map = pa.status == "Cancelled"
	else:
		status_map = pa.status.isnotnull()

	q = (
		frappe.qb.from_(pa)
		.select(
			pa.patient,
			pa.coverage_plan_card_number,
			pa.authorization_number,
			Count(pa.name).as_("count"),
		)
		.where(
			(pa.appointment_date.between(filters.from_date, filters.to_date))
			& (pa.company == filters.company)
			& (pa.insurance_company.like("NHIF"))
			& (status_map)
		)
		.groupby(pa.patient, pa.coverage_plan_card_number, pa.authorization_number)
	)
	repeated_auth_no = q.run(as_dict=True)
	return repeated_auth_no


def get_encounter_data(filter, appointment_nos):
	pe = DocType("Patient Encounter")

	q = (
		frappe.qb.from_(pe)
		.select(
			pe.patient,
			pe.docstatus,
			pe.appointment,
			pe.name.as_("encounter"),
		)
		.where((pe.appointment.isin(appointment_nos)) & (pe.company == filter.company) & (pe.duplicated == 0))
		.orderby(pe.encounter_date)
	)
	encounter_data = q.run(as_dict=True)
	return encounter_data


def get_data(filters):
	appointment_list = []

	appointment_data = get_appointment_data(filters)
	auth_details = get_repeated_auth_no(filters)
	if len(appointment_data) == 0:
		return []

	appointment_nos = [d.appointment_no for d in appointment_data]
	for row in appointment_data:
		if row.nhif_patient_claim:
			status = None
			if row.docstatus == 0:
				status = "Draft"
			if row.docstatus == 1:
				status = "Submitted"
			if row.docstatus == 2:
				status = "Cancelled"
			row.claim_status = status
		if row.patient_signature:
			row.signature = "Yes"
		else:
			row.signature = ""

		for auth in auth_details:
			if (
				auth.count > 1
				and row.patient == auth.patient
				and row.authorization_number == auth.authorization_number
				and row.coverage_plan_card_number == auth.coverage_plan_card_number
			):
				row.repeated_auth_no = True
		appointment_list.append(row)

	patient_encounter_data = get_encounter_data(filters, appointment_nos)
	if len(patient_encounter_data) == 0:
		return appointment_list

	encounter_details = []
	for appointment in appointment_list:
		for encounter in patient_encounter_data:
			if (
				appointment.patient == encounter.patient
				and appointment.appointment_no == encounter.appointment
			):
				status = None
				if encounter.docstatus == 0:
					status = "Draft"
				if encounter.docstatus == 1:
					status = "Submitted"
				if encounter.docstatus == 2:
					status = "Cancelled"

				appointment.encounter = encounter.encounter
				appointment.encounter_status = status

		encounter_details.append(appointment)

	return encounter_details
