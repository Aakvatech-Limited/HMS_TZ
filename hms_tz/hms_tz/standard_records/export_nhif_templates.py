import os
from collections import Counter, defaultdict

import frappe

from hms_tz.hms_tz.doctype.nhif_template_mapping.nhif_knowledge import THERAPY
from hms_tz.hms_tz.standard_records.standard_records import DATA_DIR, load_records

# Template values that do not come from the name; templates and Items are named after the NHIF item.
TEMPLATE_FIELDS = {
	"Lab Test Template": (),
	"Radiology Examination Template": ("modality_type",),
	"Clinical Procedure Template": (),
	"Medication": ("medication_class", "default_dosage_form", "stock_uom"),
	"Therapy Type": ("default_duration",),
}
BED_DOCTYPE = "Healthcare Service Unit Type"
APPOINTMENT_ITEM_FIELDS = (
	"assistant_md_followup_item",
	"gp_followup_item",
	"specialist_followup_item",
	"super_specialist_followup_item",
	"assistant_md_fasttrack_item",
	"gp_fasttrack_item",
	"specialist_fasttrack_item",
	"super_specialist_fasttrack_item",
)
# Reference site spellings of the same unit or dosage form; anything else unknown becomes Nos or blank.
UOMS = {
	"tablet": "Tablet",
	"tablets": "Tablet",
	"vaginal tablets": "Tablet",
	"capsule": "Capsule",
	"capsules": "Capsule",
	"vial": "Vial",
	"penfill": "Vial",
	"ampule": "Ampoule",
	"ampoule": "Ampoule",
	"bottle": "Bottle",
	"tube": "Tube",
	"sachet": "Sachet",
	"satchets": "Sachet",
	"pack": "Pack",
	"packet": "Pack",
	"strip": "Strip",
	"pair": "Pair",
	"syringe": "Syringe",
	"box": "Box",
	"kit": "Kit",
	"pen": "Pen",
	"repsules": "Respule",
	"respules": "Respule",
	"pessaries": "Pessary",
	"suppositories": "Suppository",
	"spray": "Spray",
	"can": "Can",
	"unit": "Unit",
}
DOSAGE_FORMS = {
	"cap": "Capsule",
	"capsules": "Capsule",
	"rectal": "Suppository",
	"mist expectorant mixture": "Syrup",
}


def export():
	"""Write the NHIF template files from the current site, a reference site whose templates carry NHIF codes.

	Run: bench --site <site> execute hms_tz.hms_tz.standard_records.export_nhif_templates.export
	It only reads the site and writes no prices, companies, accounts or patient data.
	"""
	codes = get_template_codes()
	write("nhif_template_codes.json", codes)
	templates = [row for row in codes if row["doctype"] in TEMPLATE_FIELDS]
	write("medication_classes.json", get_medication_classes(templates))
	write("dosage_forms.json", get_dosage_forms(templates))
	write("uoms.json", [{"uom_name": uom} for uom in sorted(set(UOMS.values()) | {"Nos"})])
	print(f"Exported {len(codes)} NHIF template rows")


def write(file_name, rows):
	with open(os.path.join(DATA_DIR, file_name), "w") as file:
		file.write(frappe.as_json(rows, indent=1) + "\n")


def get_template_codes():
	"""Rows of the site's NHIF-coded templates and Items; local codes and branch copies are left out."""
	nhif_items = {row.itemcode: row for row in frappe.get_all("NHIF Item", fields=NHIF_FIELDS)}
	branches = get_branch_words()
	rows = defaultdict(list)
	for row in sorted(
		[*get_template_rows(), *get_consultation_rows(), *get_bed_rows()], key=lambda row: row["name"]
	):
		if row["nhif_code"] in nhif_items and not any(branch in row["name"].lower() for branch in branches):
			rows[row["nhif_code"]].append(row)
	code_rows = [
		{**get_nhif_values(nhif_items[code]), **row}
		for code, rows_of_code in rows.items()
		for row in get_code_rows(rows_of_code)
	]
	return sorted(code_rows, key=lambda row: (row["doctype"], row["nhif_code"], row.get("name", "")))


NHIF_FIELDS = ["itemcode", "itemname", "itemtypeid", "servicetypeid"]


def get_nhif_values(nhif_item):
	return {
		"nhif_item_name": nhif_item.itemname,
		"item_type_id": nhif_item.itemtypeid,
		"service_type_id": nhif_item.servicetypeid,
	}


def get_branch_words():
	"""Branch names of the site's companies, such as "mwanza" in "Hospital - Mwanza"."""
	return {
		name.rsplit(" - ", 1)[1].lower() for name in frappe.get_all("Company", pluck="name") if " - " in name
	}


def get_code_rows(rows):
	"""The rows of one code's most used doctype, without the reference site's names.

	A code becomes one record named after its NHIF item. Only names NHIF cannot give are kept: the shipped
	service unit types of bed codes, and the therapy types that share one NHIF code.
	"""
	doctype = Counter(row["doctype"] for row in rows).most_common(1)[0][0]
	rows = [row for row in rows if row["doctype"] == doctype]
	if doctype == BED_DOCTYPE or (doctype == THERAPY and len(rows) > 1):
		return rows
	links = [link for row in rows for link in row.get("links", [])]
	row = {key: value for key, value in rows[0].items() if key != "name"}
	if links:
		row["links"] = [dict(link) for link in {tuple(link.items()): link for link in links}.values()]
	return [row]


def get_nhif_codes(item_names):
	"""NHIF ref code of each Item; the reference site keeps one NHIF code per Item."""
	customer = frappe.db.get_value("HMS TZ Setting", {"enable_nhif_api": 1}, "nhif_customer_name")
	rows = frappe.get_all(
		"Item Customer Detail",
		filters={"parenttype": "Item", "customer_name": customer, "parent": ["in", list(item_names) or [""]]},
		fields=["parent", "ref_code"],
	)
	return {row.parent: row.ref_code for row in rows if row.ref_code}


def get_template_rows():
	rows = []
	for doctype, fields in TEMPLATE_FIELDS.items():
		templates = frappe.get_all(doctype, fields=["name", "item", *fields])
		codes = get_nhif_codes({template.item for template in templates if template.item})
		rows += [
			{
				"nhif_code": codes[template.item],
				"doctype": doctype,
				"name": template.name,
				"values": get_template_values(doctype, template),
			}
			for template in templates
			if template.item in codes
		]
	return rows


def get_template_values(doctype, template):
	"""The template values other than its name, with the units and dosage forms normalised."""
	values = {
		field: template[field]
		for field in TEMPLATE_FIELDS[doctype]
		if template[field] not in (None, "", template.name)
	}
	if doctype == "Medication":
		values["stock_uom"] = UOMS.get((template.stock_uom or "").lower(), "Nos")
		form = template.default_dosage_form
		if form:
			values["default_dosage_form"] = DOSAGE_FORMS.get(form.lower(), form)
	return values


def get_consultation_rows():
	"""Consultation Items of practitioners and visit types, with the shipped visit type fields they fill."""
	visit_types = {row["appointment_type"] for row in load_records("visit_types.json")}
	links = {}
	for appointment_type in frappe.get_all("Appointment Type", fields=["name", *APPOINTMENT_ITEM_FIELDS]):
		for field in APPOINTMENT_ITEM_FIELDS:
			if appointment_type[field] and appointment_type.name in visit_types:
				links.setdefault(appointment_type[field], []).append(
					{"doctype": "Appointment Type", "name": appointment_type.name, "field": field}
				)
	practitioner_items = set()
	for row in frappe.get_all(
		"Healthcare Practitioner", fields=["op_consulting_charge_item", "inpatient_visit_charge_item"]
	):
		practitioner_items.update(item for item in row.values() if item)
	items = practitioner_items | set(links)
	codes = get_nhif_codes(items)
	return [
		{
			"nhif_code": codes[item],
			"doctype": "Item",
			"name": item,
			"values": {},
			"links": links.get(item, []),
		}
		for item in sorted(items)
		if item in codes
	]


def get_bed_rows():
	"""Bed charge codes, set on the shipped service unit type whose name starts the reference site's type."""
	shipped = [
		row["service_unit_type"] for row in load_records("service_unit_types.json") if row.get("item_code")
	]
	unit_types = frappe.get_all(
		"Healthcare Service Unit Type", filters={"item": ["is", "set"]}, fields=["name", "item"]
	)
	codes = get_nhif_codes({unit_type.item for unit_type in unit_types})
	rows = []
	for unit_type in unit_types:
		target = next((name for name in shipped if unit_type.name.startswith(name)), None)
		if target and unit_type.item in codes:
			rows.append(
				{
					"nhif_code": codes[unit_type.item],
					"doctype": "Healthcare Service Unit Type",
					"name": target,
				}
			)
	return rows


def get_medication_classes(templates):
	used = {row["values"].get("medication_class") for row in templates if row["doctype"] == "Medication"}
	classes = frappe.get_all(
		"Medication Class",
		filters={"name": ["in", [name for name in used if name]]},
		fields=["medication_class", "prescribed_after"],
	)
	return sorted(classes, key=lambda row: row.medication_class)


def get_dosage_forms(templates):
	forms = Counter(
		row["values"].get("default_dosage_form") for row in templates if row["doctype"] == "Medication"
	)
	return [{"dosage_form": form} for form in sorted(form for form in forms if form)]
