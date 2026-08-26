# Copyright (c) 2021, Aakvatech and contributors
# For license information, please see license.txt

import frappe


def execute(filters=None):
	data = get_data(filters)
	columns = get_columns(filters)
	return columns, data


def get_columns(filters=None):
	columns = [
		{
			"label": "Appointment Number ",
			"fieldname": "appointment",
			"fieldtype": "Link",
			"options": "Patient Appointment",
			"width": 200,
		},
		{
			"label": "Patient",
			"fieldname": "patient",
			"fieldtype": "Link",
			"options": "Patient",
			"width": 150,
		},
		{
			"label": "Patient Name",
			"fieldname": "patient_name",
			"fieldtype": "Data",
			"width": 200,
		},
		{
			"label": "Appoitment",
			"fieldname": "appoitment_creation",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": "Vital Signs",
			"fieldname": "vital_edit",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": "First Encounter",
			"fieldname": "first_encounter_first_update",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": "Laster Encounter",
			"fieldname": "last_encounter_creation",
			"fieldtype": "Datetime",
			"width": 170,
		},
		{
			"label": "NHIF Patient Claim ",
			"fieldname": "patient_claim_creation",
			"fieldtype": "Datetime",
			"width": 170,
		},
	]
	return columns


def get_data(filters=None):
	appointments = frappe.get_all(
		"Patient Appointment",
		filters={
			"status": "Closed",
			"inpatient_record": ["in", [0, "", None]],
			"appointment_date": [
				"between",
				[filters.get("from_date"), filters.get("to_date")],
			],
			"company": filters.get("company"),
		},
		fields=["*"],
		order_by="creation desc",
	)

	data = []
	for appointment in appointments:
		vital_edit = frappe.get_cached_value("Vital Signs", {"appointment": appointment.name}, "modified")
		encounters = frappe.get_all(
			"Patient Encounter",
			filters={"appointment": appointment.name, "docstatus": 1},
			order_by="creation",
			fields=["name", "creation", "modified", "finalized"],
		)
		first_encounter = None
		last_encounter = None
		first_encounter_first_update = None
		last_encounter_creation = None
		if len(encounters) > 0:
			first_encounter = encounters[0].name
		if len(encounters) > 1:
			last_encounter = encounters[-1]
			if last_encounter.finalized:
				last_encounter_creation = last_encounter.creation
		if first_encounter:
			encounter_versions = frappe.get_all(
				"Version",
				filters={"docname": ["like", first_encounter]},
				order_by="creation",
				page_length=1,
				fields=["creation"],
			)
			if len(encounter_versions):
				first_encounter_first_update = encounter_versions[0].creation

		patient_claim_creation = frappe.get_cached_value(
			"NHIF Patient Claim",
			{"patient_appointment": appointment.name},
			"creation",
		)

		data.append(
			{
				"appointment": appointment.name,
				"patient": appointment.patient,
				"patient_name": appointment.patient_name,
				"appoitment_creation": appointment.creation,
				"vital_edit": "" if not vital_edit else str(vital_edit),
				"first_encounter_first_update": first_encounter_first_update,
				"last_encounter_creation": last_encounter_creation,
				"patient_claim_creation": patient_claim_creation,
			}
		)
	return data
