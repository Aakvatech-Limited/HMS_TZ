import frappe

from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status


@frappe.whitelist()
def get_company_setup(company):
	"""The company's HMS TZ Setting name and setup steps; the steps are empty until the setting exists."""
	frappe.has_permission("HMS TZ Setting", "read", throw=True)
	setting = frappe.db.get_value("HMS TZ Setting", {"company": company})
	if not setting:
		return {"setting": None, "steps": []}

	status = get_setup_status(setting)
	status.mark_steps_with_records()
	steps = [{"document_type": row.document_type, "completed": row.completed} for row in status.steps]
	return {"setting": setting, "steps": steps}


@frappe.whitelist()
def get_setting_fields():
	"""HMS TZ Setting fields in form order, so the setup page follows the DocType layout."""
	frappe.has_permission("HMS TZ Setting", "read", throw=True)
	keys = ("fieldname", "fieldtype", "label", "options", "default", "reqd", "read_only", "hidden")
	keys += ("depends_on", "mandatory_depends_on", "link_filters")
	return [{key: field.get(key) for key in keys} for field in frappe.get_meta("HMS TZ Setting").fields]
