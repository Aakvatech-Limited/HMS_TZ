import re

import frappe
from frappe import _
from frappe.utils import cstr

from hms_tz.hms_tz.doctype.setup_status.setup_status import get_setup_status

SETTING_DOCTYPE = "HMS TZ Setting"
DEFAULTS_HOOK = "hms_tz_setting_defaults"
BILLING_DOCTYPE = "Healthcare Settings"

# Healthcare Settings tab and section shown in the Billing tab.
BILLING_PARTS = ("sb_op_settings", "billing_accounts")

# Healthcare Settings tables holding one account row per company, with the desk account filters.
COMPANY_ACCOUNTS = {
	"income_account": [["Account", "root_type", "=", "Income"]],
	"receivable_account": [["Account", "account_type", "=", "Receivable"]],
}

LAYOUT_TYPES = ("Tab Break", "Section Break", "Column Break")
FIELD_KEYS = ("fieldname", "fieldtype", "label", "options", "default", "reqd")
FIELD_KEYS += ("depends_on", "mandatory_depends_on", "link_filters")


@frappe.whitelist()
def get_company_setup(company):
	"""The company's values, what each settings group still misses, and the setup steps once the setting exists."""
	frappe.has_permission(SETTING_DOCTYPE, "read", throw=True)
	setting = frappe.db.get_value(SETTING_DOCTYPE, {"company": company})
	values = {SETTING_DOCTYPE: get_setting_values(setting), BILLING_DOCTYPE: get_billing_values(company)}
	groups = get_settings_groups(get_setting_fields(), values)
	setup = {"setting": setting, "values": values, "groups": groups, "settings_complete": False, "steps": []}
	if not setting:
		return setup

	status = get_setup_status(setting)
	status.mark_steps_with_records()
	status.set_settings_complete(not any(group["missing"] for group in groups))
	setup["settings_complete"] = bool(status.settings_complete)
	setup["steps"] = [
		{"document_type": row.document_type, "completed": row.completed} for row in status.steps
	]
	return setup


@frappe.whitelist()
def get_setup_navigation(company):
	"""What the setup sidebar marks on each screen: whether its setup step is done, and the NHIF codes to review."""
	setup = get_company_setup(company)
	return {
		"settings_complete": setup["settings_complete"],
		"steps": setup["steps"],
		"nhif_templates_to_review": frappe.db.count("NHIF Template Mapping", {"status": "Review"}),
	}


@frappe.whitelist()
def get_setting_fields():
	"""Editable setup fields in form order: HMS TZ Setting, then the Billing tab from Healthcare Settings."""
	frappe.has_permission(SETTING_DOCTYPE, "read", throw=True)
	billing_tab = {"fieldname": "billing_tab", "fieldtype": "Tab Break", "label": "Billing"}
	setting_fields = get_editable_fields(SETTING_DOCTYPE, frappe.get_meta(SETTING_DOCTYPE).fields)
	return [
		*apply_setting_defaults(setting_fields),
		{**billing_tab, "doctype": BILLING_DOCTYPE},
		*get_editable_fields(BILLING_DOCTYPE, get_billing_docfields()),
	]


@frappe.whitelist(methods=["POST"])
def save_company_setup(company, values):
	"""Create or update the company's HMS TZ Setting and billing values in one transaction."""
	values = frappe.parse_json(values)
	save_setting(company, values.get(SETTING_DOCTYPE) or {})
	save_billing(company, values.get(BILLING_DOCTYPE) or {})
	return get_company_setup(company)


def apply_setting_defaults(fields):
	"""Defaults other installed apps register for a new HMS TZ Setting, for example in hooks.py:
	hms_tz_setting_defaults = [{"fieldname": "enable_nhif_api", "value": 1}]"""
	by_fieldname = {field["fieldname"]: field for field in fields if field["fieldtype"] not in LAYOUT_TYPES}
	for default in frappe.get_hooks(DEFAULTS_HOOK):
		if default["fieldname"] not in by_fieldname:
			frappe.throw(_("{0} is not an editable HMS TZ Setting field").format(default["fieldname"]))
		by_fieldname[default["fieldname"]]["default"] = default["value"]
	return fields


def get_editable_fields(doctype, docfields):
	fields = []
	for docfield in docfields:
		if docfield.fieldname in COMPANY_ACCOUNTS:
			fields.append(get_account_field(docfield))
		elif is_editable(docfield):
			fields.append({key: docfield.get(key) for key in FIELD_KEYS})
	return [{**field, "doctype": doctype} for field in fields]


def is_editable(docfield):
	if docfield.fieldtype in LAYOUT_TYPES:
		return True
	return not (
		docfield.fieldname == "company"
		or docfield.hidden
		or docfield.read_only
		or docfield.fieldtype in frappe.model.no_value_fields
	)


def get_account_field(docfield):
	"""A company account table as one Account link for the selected company."""
	filters = [
		["Account", "company", "=", "eval: doc.company"],
		["Account", "is_group", "=", 0],
		*COMPANY_ACCOUNTS[docfield.fieldname],
	]
	return {
		"fieldname": docfield.fieldname,
		"fieldtype": "Link",
		"label": docfield.label,
		"options": "Account",
		"link_filters": frappe.as_json(filters, indent=None),
	}


def get_billing_docfields():
	"""Healthcare Settings fields inside BILLING_PARTS, without their tab breaks."""
	docfields, tab, section = [], None, None
	for docfield in frappe.get_meta(BILLING_DOCTYPE).fields:
		if docfield.fieldtype == "Tab Break":
			tab, section = docfield.fieldname, None
			continue
		if docfield.fieldtype == "Section Break":
			section = docfield.fieldname
		if tab in BILLING_PARTS or section in BILLING_PARTS:
			docfields.append(docfield)
	return docfields


def get_value_fieldnames(doctype):
	return [
		field["fieldname"]
		for field in get_setting_fields()
		if field["doctype"] == doctype and field["fieldtype"] not in LAYOUT_TYPES
	]


def get_setting_values(setting):
	if not setting:
		return None
	doc = frappe.get_doc(SETTING_DOCTYPE, setting)
	return {fieldname: doc.get(fieldname) for fieldname in get_value_fieldnames(SETTING_DOCTYPE)}


def get_billing_values(company):
	settings = frappe.get_single(BILLING_DOCTYPE)
	values = {fieldname: settings.get(fieldname) for fieldname in get_value_fieldnames(BILLING_DOCTYPE)}
	for table in COMPANY_ACCOUNTS:
		values[table] = next((row.account for row in settings.get(table) if row.company == company), None)
	return values


def save_setting(company, values):
	setting = frappe.db.get_value(SETTING_DOCTYPE, {"company": company})
	doc = frappe.get_doc(SETTING_DOCTYPE, setting) if setting else frappe.new_doc(SETTING_DOCTYPE)
	doc.update(pick(values, get_value_fieldnames(SETTING_DOCTYPE)))
	doc.company = company
	doc.save()


def save_billing(company, values):
	settings = frappe.get_single(BILLING_DOCTYPE)
	values = pick(values, get_value_fieldnames(BILLING_DOCTYPE))
	for table in COMPANY_ACCOUNTS:
		set_company_account(settings, table, company, values.pop(table, None))
	settings.update(values)
	settings.save()


def set_company_account(settings, table, company, account):
	"""Set the account on the company's row, adding the row when the company has none."""
	row = next((row for row in settings.get(table) if row.company == company), None)
	if row:
		row.account = account
	elif account:
		settings.append(table, {"company": company, "account": account})


def pick(values, fieldnames):
	"""Only known editable fields reach the documents."""
	return {fieldname: values[fieldname] for fieldname in fieldnames if fieldname in values}


def get_settings_groups(fields, values):
	"""Each settings tab with the labels of its shown required fields that have no value."""
	groups = [{"label": "Details", "missing": []}]
	section_shown = True
	for field in fields:
		doc = values.get(field["doctype"]) or {}
		if field["fieldtype"] == "Tab Break":
			groups.append({"label": field["label"], "missing": []})
			section_shown = True
		elif field["fieldtype"] == "Section Break":
			section_shown = is_rule_true(field.get("depends_on"), doc)
		elif field["fieldtype"] != "Column Break" and section_shown and is_missing(field, doc):
			groups[-1]["missing"].append(field["label"])
	return groups


def is_missing(field, doc):
	shown = is_rule_true(field.get("depends_on"), doc)
	rule = field.get("mandatory_depends_on")
	required = field.get("reqd") or (rule and is_rule_true(rule, doc))
	return bool(shown and required and not cstr(doc.get(field["fieldname"])).strip())


def is_rule_true(rule, doc):
	"""Desk depends_on rule: "eval:" JS using ==, &&, || and !, or a fieldname that must be set."""
	if not rule:
		return True
	if not rule.startswith("eval:"):
		return bool(doc.get(rule))
	expression = (
		rule[5:].replace("===", "==").replace("!==", "!=").replace("&&", " and ").replace("||", " or ")
	)
	expression = re.sub(r"!(?!=)", " not ", expression)
	# Desk rules are JavaScript, where a statement may end with a semicolon.
	expression = expression.strip().rstrip(";")
	return bool(frappe.safe_eval(expression, None, {"doc": frappe._dict(doc)}))
