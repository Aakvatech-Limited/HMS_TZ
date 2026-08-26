import frappe
from frappe.custom.doctype.property_setter.property_setter import make_property_setter


def execute():
	for doctype in ["Lab Test", "Radiology Examination", "Clinical Procedure"]:
		make_property_setter(
			doctype=doctype,
			fieldname="patient",
			property="read_only",
			value=1,
			property_type="Check",
			for_doctype=False,
			validate_fields_for_doctype=False,
		)

		if doctype == "Lab Test":
			for field in ["employee", "employee_name", "employee_designation"]:
				make_property_setter(
					doctype=doctype,
					fieldname=field,
					property="hidden",
					value=1,
					property_type="Check",
					for_doctype=False,
					validate_fields_for_doctype=False,
				)

	frappe.db.commit()
