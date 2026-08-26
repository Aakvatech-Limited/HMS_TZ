import json
import os
import sys

import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter

folder = "./property_setters_json"


def load_json(file):
	CURR_DIR = os.path.abspath(os.path.dirname(__file__))
	json_file_path = os.path.join(CURR_DIR, folder, file)
	with open(json_file_path) as file:
		data = json.load(file)
	return data


def create_property_setter_from_json(property_setters_obj):
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

	existing_setters = {
		d.name for d in frappe.db.get_all("Property Setter", fields=["name"], page_length=10000)
	}

	for property_setter in property_setters_obj:
		if property_setter.get("name") in existing_setters:
			continue

		if property_setter.get("doctype_or_field") == "DocType":
			for_doctype = True
		else:
			for_doctype = False

		all_fields = frappe.get_meta("Property Setter").get_valid_columns()
		field_list = set(all_fields).difference(disallowed_fields)

		property_setter_dict = {
			field: property_setter.get(field) for field in field_list if field in property_setter
		}

		try:
			make_property_setter(
				doctype=property_setter_dict.get("doc_type"),
				fieldname=property_setter_dict.get("field_name", None),
				property=property_setter_dict.get("property"),
				value=property_setter_dict.get("value"),
				property_type=property_setter_dict.get("property_type"),
				for_doctype=for_doctype,
			)
		except Exception as e:
			ps_name = property_setter.get("name", "unknown")
			print(
				f"WARNING [hms_tz]: Failed to create property setter '{ps_name}': {e}",
				file=sys.stderr,
			)
			frappe.log_error(
				title=f"hms_tz: property setter failed - {ps_name}",
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
			create_property_setter_from_json(data)
		except Exception as e:
			print(
				f"WARNING [hms_tz]: Failed to process property setters from '{file}': {e}",
				file=sys.stderr,
			)
			frappe.log_error(
				title=f"hms_tz: property setter file failed - {file}",
				message=frappe.get_traceback(),
			)
