# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


import datetime as dt
import json

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class PractitionerAvailabilityDetail(Document):
	pass


def create_practitioner_availability_detail(pa_doc, date):
	"""
	return created doc in memory with the info from Practitioner Availability doc
	"""
	from_time = dt.datetime.strptime(pa_doc.from_time, "%H:%M:%S").time()
	from_date = dt.datetime.combine(getdate(date), from_time)

	to_time = dt.datetime.strptime(pa_doc.to_time, "%H:%M:%S").time()
	to_date = dt.datetime.combine(getdate(date), to_time)

	doc = frappe.new_doc("Practitioner Availability Detail")
	doc.practitioner_availability = pa_doc.name
	doc.availability_type = pa_doc.availability_type
	doc.availability = pa_doc.availability
	doc.practitioner = pa_doc.practitioner
	doc.healthcare_practitioner_name = pa_doc.healthcare_practitioner_name
	doc.from_date = from_date
	doc.from_time = pa_doc.from_time
	doc.to_date = to_date
	doc.to_time = pa_doc.to_time
	doc.repeat_this_event = pa_doc.repeat_this_event
	doc.present = pa_doc.present
	doc.appointment_type = pa_doc.appointment_type
	doc.duration = pa_doc.duration
	doc.service_unit = pa_doc.service_unit
	doc.total_service_unit_capacity = pa_doc.total_service_unit_capacity
	doc.color = pa_doc.color
	doc.out_patient_consulting_charge_item = pa_doc.out_patient_consulting_charge_item
	doc.op_consulting_charge = pa_doc.op_consulting_charge
	doc.inpatient_visit_charge_item = pa_doc.inpatient_visit_charge_item
	doc.inpatient_visit_charge = pa_doc.inpatient_visit_charge
	return doc


def delelte_all_related_practitioner_availability_detail(pa_doc):
	frappe.db.sql(
		f"DELETE FROM `tabPractitioner Availability Detail` WHERE practitioner_availability = '{pa_doc.name}'"
	)


@frappe.whitelist()
def get_events(doctype, start, end, field_map, filters=None, fields=None):
	field_map = frappe._dict(json.loads(field_map))

	doc_meta = frappe.get_meta(doctype)
	for d in doc_meta.fields:
		if d.fieldtype == "Color":
			field_map.update({"color": d.fieldname})

	if filters:
		filters = json.loads(filters or "")

	if not fields:
		fields = [field_map.start, field_map.end, field_map.title, "name"]
	else:
		fields = json.loads(fields)

	if field_map.color:
		fields.append(field_map.color)

	start_date = f"ifnull({field_map.start}, '0001-01-01 00:00:00')"
	end_date = f"ifnull({field_map.end}, '2199-12-31 00:00:00')"

	filters += [
		[doctype, start_date, "<=", end],
		[doctype, end_date, ">=", start],
	]

	return frappe.get_list(doctype, fields=fields, filters=filters)
