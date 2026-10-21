import frappe
from frappe.query_builder import DocType
from frappe.utils import nowdate

PRESCRIPTION_TEMPLATES = (
	("Lab Prescription", "Lab Test Template", "lab_test_code"),
	("Radiology Procedure Prescription", "Radiology Examination Template", "radiology_examination_template"),
	("Procedure Prescription", "Clinical Procedure Template", "procedure"),
	("Therapy Plan Detail", "Therapy Type", "therapy_type"),
)


def execute():
	return

	today = nowdate()
	encounters = frappe.get_all(
		"Patient Encounter",
		{"encounter_date": ["<=", today]},
		["name"],
		pluck="name",
	)

	if len(encounters) == 0:
		return

	pe = DocType("Patient Encounter")
	hco = DocType("Healthcare Company Option")
	for prescription_doctype, template_doctype, template_field in PRESCRIPTION_TEMPLATES:
		lrpt = DocType(prescription_doctype)
		item_template = DocType(template_doctype)
		rows = (
			frappe.qb.from_(lrpt)
			.inner_join(pe)
			.on(lrpt.parent == pe.name)
			.inner_join(item_template)
			.on((lrpt[template_field] == item_template.name) & (item_template.disabled == 0))
			.inner_join(hco)
			.on((item_template.name == hco.parent) & (hco.company == pe.company))
			.select(lrpt.name, hco.service_unit)
			.where(pe.name.isin(encounters))
		).run(as_dict=True)

		updates = {}
		for row in rows:
			updates.setdefault(row.name, {"department_hsu": row.service_unit})

		frappe.db.bulk_update(prescription_doctype, updates, update_modified=False)

	frappe.db.commit()
