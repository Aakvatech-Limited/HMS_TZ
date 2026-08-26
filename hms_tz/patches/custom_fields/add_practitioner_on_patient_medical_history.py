import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import create_batch

from hms_tz.nhif.api.medical_record import set_practitioner


def execute():
	fields = {
		"Patient Medical Record": [
			{
				"fieldname": "practitioner",
				"fieldtype": "Link",
				"options": "Healthcare Practitioner",
				"label": "Healthcare Practitioner",
				"insert_after": "user",
				"reqd": 1,
			}
		]
	}
	create_custom_fields(fields, update=True)
	frappe.db.commit()

	frappe.reload_doctype("Patient Medical Record", force=True)
	update_practitioner_to_old_records()


def update_practitioner_to_old_records():
	medical_records = frappe.db.get_all(
		"Patient Medical Record",
		filters={"practitioner": ""},
		order_by="creation desc",
		limit=1000,
	)

	for records in create_batch(medical_records, 100):
		for record in records:
			doc = frappe.get_cached_doc("Patient Medical Record", record.name)
			set_practitioner(doc)
			doc.db_update()
			doc.db_update_all()
		frappe.db.commit()
