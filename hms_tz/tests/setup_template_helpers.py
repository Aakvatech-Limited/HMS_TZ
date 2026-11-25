import frappe
from frappe.utils.csvutils import to_csv

from hms_tz.api.rooms import get_company_rooms
from hms_tz.api.setup import get_company_setup
from hms_tz.api.setup_records import get_screen
from hms_tz.tests.test_standard_records import create_for

COMPANY = "_Test Company"
OTHER_COMPANY = "_Test Company 1"


def prepare_company():
	"""A fresh HMS TZ Setting of the test company with complete settings, so template screens save."""
	frappe.delete_doc_if_exists("Setup Status", COMPANY)
	frappe.delete_doc_if_exists("HMS TZ Setting", COMPANY)
	frappe.db.set_single_value(
		"Healthcare Settings", {"collect_registration_fee": 0, "enable_free_follow_ups": 0}
	)
	frappe.get_doc({"doctype": "HMS TZ Setting", "company": COMPANY, "facility_code": "TEST"}).insert()
	create_for(COMPANY)
	create_for(OTHER_COMPANY)
	get_company_setup(COMPANY)


def get_service_unit(company, unit_name):
	"""A room of the company, under its root service unit, created when missing."""
	name = f"{unit_name} - {frappe.get_cached_value('Company', company, 'abbr')}"
	if frappe.db.exists("Healthcare Service Unit", name):
		return name
	get_company_rooms(company)
	root = frappe.db.get_value("Healthcare Service Unit", {"company": company, "is_group": 1})
	unit = frappe.get_doc(
		{
			"doctype": "Healthcare Service Unit",
			"healthcare_service_unit_name": unit_name,
			"company": company,
			"is_group": 0,
			"parent_healthcare_service_unit": root,
		}
	)
	return unit.insert(ignore_mandatory=True).name


def delete_templates(doctype, names, item_codes):
	"""Remove test templates with their child rows, Items and Item Prices, without the trash hooks."""
	for table in frappe.get_meta(doctype).get_table_fields():
		frappe.db.delete(table.options, {"parenttype": doctype, "parent": ["in", names]})
	frappe.db.delete(doctype, {"name": ["in", names]})
	delete_items(item_codes)


def delete_items(item_codes):
	"""Remove Items with their child rows and prices; child rows left behind would load into a new Item."""
	for table in frappe.get_meta("Item").get_table_fields():
		frappe.db.delete(table.options, {"parenttype": "Item", "parent": ["in", item_codes]})
	frappe.db.delete("Item Price", {"item_code": ["in", item_codes]})
	frappe.db.delete("Item", {"name": ["in", item_codes]})


def get_template_rows(screen):
	"""The screen's import template with all records, as CSV rows: the header row first."""
	return get_screen(screen, COMPANY).get_exporter("all", "CSV").get_csv_array_for_export()


def upload_csv(rows, file_name):
	file = frappe.get_doc(
		{"doctype": "File", "file_name": file_name, "content": to_csv(rows), "is_private": 1}
	)
	return file.insert().file_url


def column(header, label):
	"""Index of the template column whose header starts with the label, such as "Service Unit"."""
	return next(index for index, title in enumerate(header) if title.startswith(label))
