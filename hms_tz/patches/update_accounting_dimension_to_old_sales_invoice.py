import frappe
from frappe.query_builder import DocType


def execute():
	refdocs = [
		"Lab Prescription",
		"Radiology Procedure Prescription",
		"Procedure Prescription",
		"Therapy Plan Detail",
	]
	sii_items = frappe.get_all(
		"Sales Invoice Item",
		filters={
			"reference_dt": ["in", refdocs],
			"reference_dn": ["!=", ""],
			"healthcare_service_unit": "",
			"healthcare_practitioner": "",
		},
		fields=["name"],
		pluck="name",
	)

	if not sii_items:
		return

	sii = DocType("Sales Invoice Item")
	pe = DocType("Patient Encounter")
	updates = {}
	for refdoc in refdocs:
		lrpt = DocType(refdoc)
		rows = (
			frappe.qb.from_(sii)
			.inner_join(lrpt)
			.on((sii.reference_dn == lrpt.name) & (sii.reference_dt == refdoc))
			.inner_join(pe)
			.on(lrpt.parent == pe.name)
			.select(sii.name, lrpt.department_hsu, pe.practitioner)
			.where(sii.name.isin(sii_items))
		).run(as_dict=True)

		for row in rows:
			updates[row.name] = {
				"healthcare_service_unit": row.department_hsu,
				"healthcare_practitioner": row.practitioner,
			}

	frappe.db.bulk_update("Sales Invoice Item", updates, update_modified=False)
	frappe.db.commit()
