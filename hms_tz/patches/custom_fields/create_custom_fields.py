import json
import os
import sys

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

folder = "./custom_fields_json"


def load_json(file):
	CURR_DIR = os.path.abspath(os.path.dirname(__file__))
	json_file_path = os.path.join(CURR_DIR, folder, file)
	# TODO do not load the file if already applied
	with open(json_file_path) as file:
		data = json.load(file)
	return data


def create_fields_from_json(custom_fields_obj):
	disallowed_fields = [
		"name",
		"owner",
		"creation",
		"modified",
		"modified_by",
		"docstatus",
		"idx",
		"is_system_generated",
		"__last_sync_on",
	]
	doctype_custom_fields_dict = {}

	for custom_field in custom_fields_obj:
		doctype = custom_field["dt"]
		all_fields = frappe.get_meta("Custom Field").get_valid_columns()
		field_list = set(all_fields).difference(disallowed_fields)
		custom_field_dict = {}
		for field_name in field_list:
			custom_field_dict[field_name] = custom_field.get(field_name)

		# Ensure the list for the doctype is initialized
		if doctype not in doctype_custom_fields_dict:
			doctype_custom_fields_dict[doctype] = []

		doctype_custom_fields_dict[doctype].append(custom_field_dict)

	# Sort fields so that Dynamic Link fields are created after Link fields.
	# Frappe validates that a Dynamic Link's `options` references an existing
	# Link field with options="DocType". If the Link field hasn't been created
	# yet (because it appears later in the list), the validation fails.
	for doctype in doctype_custom_fields_dict:
		doctype_custom_fields_dict[doctype].sort(
			key=lambda f: 1 if f.get("fieldtype") == "Dynamic Link" else 0
		)

	# Try creating all fields in one batch first (fast path).
	# If that fails, fall back to creating fields one-by-one per doctype
	# so that a single bad field does not block the rest.
	try:
		create_custom_fields(doctype_custom_fields_dict, update=False)
	except Exception:
		for doctype, fields in doctype_custom_fields_dict.items():
			for df in fields:
				fieldname = df.get("fieldname", df.get("label", "unknown"))
				try:
					create_custom_fields({doctype: [df]}, update=False)
				except Exception as e:
					print(
						f"WARNING [hms_tz]: Failed to create custom field '{fieldname}' on '{doctype}': {e}",
						file=sys.stderr,
					)
					frappe.log_error(
						title=f"hms_tz: custom field failed - {doctype}.{fieldname}",
						message=frappe.get_traceback(),
					)


def execute():
	# read names of only json files in this folder and put it into files list
	files = list(
		filter(
			lambda x: x.endswith(".json"),
			os.listdir(os.path.join(os.path.abspath(os.path.dirname(__file__)), folder)),
		)
	)
	for file in files:
		try:
			data = load_json(file)
			create_fields_from_json(data)
		except Exception as e:
			print(
				f"WARNING [hms_tz]: Failed to process custom fields from '{file}': {e}",
				file=sys.stderr,
			)
			frappe.log_error(
				title=f"hms_tz: custom field file failed - {file}",
				message=frappe.get_traceback(),
			)


@frappe.whitelist()
def export_custom_fields(docnames):
	docnames = frappe.parse_json(docnames)
	custom_fields = []

	for docname in docnames:
		doc = frappe.get_cached_doc("Custom Field", docname)
		custom_fields.append(
			doc.as_dict(
				convert_dates_to_str=True,
				no_default_fields=True,
				no_nulls=True,
			)
		)

	return str(custom_fields)
