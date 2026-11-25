import frappe
from frappe import _

from hms_tz.api.setup import get_company_setup
from hms_tz.hms_tz.setup_screens.appointment_type import AppointmentType
from hms_tz.hms_tz.setup_screens.coverage import Coverage
from hms_tz.hms_tz.setup_screens.coverage_plan import CoveragePlan
from hms_tz.hms_tz.setup_screens.insurance_company import InsuranceCompany
from hms_tz.hms_tz.setup_screens.jubilee_update import JubileeUpdate
from hms_tz.hms_tz.setup_screens.nhif_item import NHIFItem
from hms_tz.hms_tz.setup_screens.nhif_scheme import NHIFScheme
from hms_tz.hms_tz.setup_screens.nhif_update import NHIFUpdate
from hms_tz.hms_tz.setup_screens.practitioner import Practitioner

# Setup screens of company records, by the key the page route passes.
SCREENS = {
	"doctors": Practitioner,
	"insurance_companies": InsuranceCompany,
	"coverage_plans": CoveragePlan,
	"visit_types": AppointmentType,
	"coverages": Coverage,
	"nhif_schemes": NHIFScheme,
	"nhif_updates": NHIFUpdate,
	"jubilee_updates": JubileeUpdate,
	"nhif_items": NHIFItem,
}


def get_screen(screen, company=None):
	if screen not in SCREENS:
		frappe.throw(_("{0} is not a setup screen").format(screen))
	return SCREENS[screen](company)


@frappe.whitelist()
def get_screen_fields(screen):
	"""The screen's labels, its fields in form order and the fields its list can be filtered by."""
	records = get_screen(screen)
	frappe.has_permission(records.doctype, "read", throw=True)
	return {
		"doctype": records.doctype,
		"label": records.label,
		"plural_label": records.plural_label,
		"title_field": records.title_field,
		"has_add_actions": records.has_add_actions,
		"is_read_only": records.is_read_only,
		"has_child_rows": bool(records.child_table),
		"fields": records.fields,
		"list_filters": records.list_filter_fields,
	}


@frappe.whitelist()
def get_company_records(screen, company, list_filters=None):
	"""The company's records of the screen matching the list filters, and whether its settings are complete."""
	records = get_screen(screen, company)
	frappe.has_permission(records.doctype, "read", throw=True)
	setup = get_company_setup(company)
	return {
		"setting": setup["setting"],
		"settings_complete": setup["settings_complete"],
		**records.get_records(frappe.parse_json(list_filters)),
		"action_groups": records.action_groups,
		"action_runs": records.action_runs,
	}


@frappe.whitelist(methods=["POST"])
def save_company_record(screen, company, values, name=None):
	"""Add a record, or change one of the company's records."""
	return get_screen(screen, company).save(frappe.parse_json(values), name)


@frappe.whitelist()
def download_records_template(screen, company, samples="0", file_type="Excel"):
	"""Import template of the screen with "all" or that many of the company's records as samples."""
	records = get_screen(screen, company)
	frappe.has_permission(records.doctype, "read", throw=True)
	records.download_template(samples, file_type)


@frappe.whitelist(methods=["POST"])
def import_company_records(screen, company, file_url):
	"""Add or change the company's records from a filled template."""
	return get_screen(screen, company).import_file(file_url)


@frappe.whitelist(methods=["POST"])
def run_screen_action(screen, company, action):
	"""Queue one action of the screen's action dropdowns for the company as a background job."""
	records = get_screen(screen, company)
	frappe.has_permission(records.doctype, "write", throw=True)
	return records.run_action(action)


@frappe.whitelist()
def get_record_child_rows(screen, company, name, start=0):
	"""One page of the child table rows of one of the company's records, read only."""
	records = get_screen(screen, company)
	frappe.has_permission(records.doctype, "read", doc=name, throw=True)
	return records.get_child_rows(name, start)
