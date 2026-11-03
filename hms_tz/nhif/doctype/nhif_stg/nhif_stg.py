# Copyright (c) 2026, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class NHIFSTG(Document):
	pass


STG_DIAGNOSIS_TABLES = ("patient_encounter_preliminary_diagnosis", "patient_encounter_final_diagnosis")
STG_PRESCRIPTION_FIELDS = {
	"lab_test_prescription": ("Lab Test Template", "lab_test_code"),
	"radiology_procedure_prescription": ("Radiology Examination Template", "radiology_examination_template"),
	"procedure_prescription": ("Clinical Procedure Template", "procedure"),
	"therapies": ("Therapy Type", "therapy_type"),
}


@frappe.whitelist()
def get_moh_stg(encounter):
	"""Return the NHIF STG of the encounter diagnoses, the diagnoses without STG and the services not in STG."""
	doc = frappe.get_doc(frappe.parse_json(encounter))
	doc.check_permission("read")
	if not is_moh_stg_shown(doc):
		return

	check = get_stg_check(doc)
	del check["services"]
	return check


def validate_moh_stg(doc):
	if not is_moh_stg_shown(doc) or not frappe.get_cached_value(
		"HMS TZ Setting", doc.company, "enforce_stg_on_patient_encounter"
	):
		return

	not_in_stg = get_stg_check(doc)["not_in_stg"]
	if not_in_stg:
		frappe.throw(
			_("These services are not in the MOH STG of the encounter diagnoses: {0}").format(
				", ".join(frappe.bold(service) for service in not_in_stg)
			),
			title=_("MOH STG"),
		)


def is_moh_stg_shown(doc):
	return frappe.get_cached_value("HMS TZ Setting", doc.company, "show_stg_on_patient_encounter")


def get_stg_check(doc):
	"""A prescribed service is not in STG when no diagnosis code of the encounter lists it."""
	diagnoses = {
		row.code_value: row for table in STG_DIAGNOSIS_TABLES for row in doc.get(table) if row.code_value
	}
	stg_rows = get_stg_rows(diagnoses)
	stg_keys = {(row.service_type, row.service_name) for row in stg_rows}
	codes_not_in_stg = sorted(set(diagnoses) - {row.code_value for row in stg_rows})
	services = get_prescribed_services(doc)
	not_in_stg = list(dict.fromkeys(label for label, keys in services if not keys & stg_keys))

	return {
		"stg": stg_rows,
		"codes_not_in_stg": codes_not_in_stg,
		"services": services,
		"not_in_stg": not_in_stg,
	}


def get_stg_rows(diagnoses):
	if not diagnoses:
		return []

	stg_rows = frappe.get_all(
		"NHIF STG",
		filters={"code_value": ["in", list(diagnoses)], "disabled": 0},
		fields=["code_value", "stg_type", "service_type", "service_name"],
		order_by="code_value, stg_type, service_name",
	)
	for row in stg_rows:
		row.definition = diagnoses[row.code_value].definition

	return stg_rows


def get_prescribed_services(doc):
	"""Return (label, STG keys) for each prescribed service; a drug matches STG through its Medication."""
	services = [
		(row.get(fieldname), {(service_type, row.get(fieldname))})
		for table, (service_type, fieldname) in STG_PRESCRIPTION_FIELDS.items()
		for row in doc.get(table)
		if row.get(fieldname)
	]

	drug_rows = [row for row in doc.get("drug_prescription") if row.drug_code]
	medication_keys = {}
	if drug_rows:
		for medication in frappe.get_all(
			"Medication",
			filters={"item": ["in", [row.drug_code for row in drug_rows]]},
			fields=["name", "item"],
		):
			medication_keys.setdefault(medication.item, set()).add(("Medication", medication.name))

	return services + [(row.drug_code, medication_keys.get(row.drug_code, set())) for row in drug_rows]
