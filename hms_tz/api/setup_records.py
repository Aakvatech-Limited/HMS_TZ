import frappe
from frappe import _

from hms_tz.api.setup import get_company_setup
from hms_tz.hms_tz.setup_screens.coverage_plan import CoveragePlan
from hms_tz.hms_tz.setup_screens.insurance_company import InsuranceCompany
from hms_tz.hms_tz.setup_screens.practitioner import Practitioner

# Setup screens of company records, by the key the page route passes.
SCREENS = {
	"doctors": Practitioner,
	"insurance_companies": InsuranceCompany,
	"coverage_plans": CoveragePlan,
}


def get_screen(screen, company=None):
	if screen not in SCREENS:
		frappe.throw(_("{0} is not a setup screen").format(screen))
	return SCREENS[screen](company)


@frappe.whitelist()
def get_screen_fields(screen):
	"""The screen's labels and its fields in form order."""
	records = get_screen(screen)
	frappe.has_permission(records.doctype, "read", throw=True)
	return {
		"doctype": records.doctype,
		"label": records.label,
		"plural_label": records.plural_label,
		"title_field": records.title_field,
		"fields": records.fields,
	}


@frappe.whitelist()
def get_company_records(screen, company):
	"""The company's records of the screen and whether its settings are complete, which unlocks adding."""
	records = get_screen(screen, company)
	frappe.has_permission(records.doctype, "read", throw=True)
	setup = get_company_setup(company)
	return {
		"setting": setup["setting"],
		"settings_complete": setup["settings_complete"],
		"records": records.records,
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
