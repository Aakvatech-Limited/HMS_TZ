# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt


import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder import Criterion, DatePart, DocType
from frappe.query_builder.functions import Extract, IfNull
from frappe.utils import formatdate, getdate, time_diff_in_seconds


class PractitionerAvailability(Document):
	def validate(self):
		self.validate_repeat_on()
		if self.present == 1:
			validate_duration(self)
		else:
			validate_existing_appointment(self)
		validate_date(self)
		self.to_date = self.from_date
		validate_overlap(self)
		validate_service_unit_capacity(self)

	def validate_repeat_on(self):
		if self.repeat_on == "Every Day":
			have_atleast_one_weekday = False
			weekdays = [
				"monday",
				"tuesday",
				"wednesday",
				"thursday",
				"friday",
				"saturday",
				"sunday",
			]
			for weeday in weekdays:
				if self.get(weeday) == 1:
					have_atleast_one_weekday = True
			if not have_atleast_one_weekday:
				frappe.throw("Please select atleast one day")


def validate_duration(doc):
	if not doc.duration or doc.duration <= 0:
		frappe.throw(_("Duration must be geater than zero"))
	else:
		# time diff in minutes = in seconds / 60
		total_time_diff = time_diff_in_seconds(doc.to_time, doc.from_time) / 60
		if total_time_diff <= 0:
			frappe.throw(_("From Time should not be greater than or equal to To Time"))
		if total_time_diff < doc.duration:
			frappe.throw(
				_("Duration between from time and to time must be greater than or equal to duration given")
			)
		elif total_time_diff % doc.duration != 0:
			frappe.throw(_("Duration between from time and to time must be multiple of duration given"))


def validate_existing_appointment(doc):
	appointment = DocType("Patient Appointment")
	appointments = (
		frappe.qb.from_(appointment)
		.select(appointment.name)
		.where(
			(appointment.practitioner == doc.get("practitioner"))
			& (appointment.docstatus < 2)
			& (appointment.status != "Cancelled")
			& (appointment.appointment_date == doc.from_date)
			& (appointment.appointment_time >= doc.from_time)
			& (appointment.appointment_time < doc.to_time)
		)
	).run(as_dict=True)
	if appointments:
		frappe.throw(
			_("Cannot create event!  There are booked appointments at the time, cancel them and proceed.")
		)


def validate_date(doc):
	if doc.repeat_this_event == 1 and doc.repeat_till and getdate(doc.from_date) > getdate(doc.repeat_till):
		frappe.throw(_("Practitioner Event Repeat Till must be after From Date"))


def validate_overlap(doc):
	validate_event_overlap(doc)


def validate_service_unit_capacity(doc):
	if doc.service_unit:
		service_unit_capacity = frappe.get_cached_value(
			"Healthcare Service Unit",
			doc.service_unit,
			"total_service_unit_capacity",
		)
		if (
			doc.total_service_unit_capacity
			and service_unit_capacity
			and (int(doc.total_service_unit_capacity) > int(service_unit_capacity))
		):
			frappe.throw(_(f"Not Allowed - Maximum Capacity {service_unit_capacity}"))


def get_repeating_event_overlap(doc, availability):
	repeat_till = IfNull(availability.repeat_till, "3000-01-01")
	doc_repeat_till = doc.repeat_till or "3000-01-01"
	weekdays = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
	return (
		(availability.repeat_this_event == 1)
		& (
			availability.from_date.between(doc.from_date, doc_repeat_till)
			| repeat_till.between(doc.from_date, doc_repeat_till)
			| ((availability.from_date < doc.from_date) & (repeat_till > doc_repeat_till))
		)
		& (
			(
				(availability.repeat_on == "Every Day")
				& Criterion.any(availability[day] == doc.get(day) for day in weekdays)
			)
			| (
				(availability.repeat_on == "Every Month")
				& (Extract(DatePart.month, availability.from_date) == getdate(doc.from_date).month)
			)
		)
	)


def get_single_event_overlap(doc, availability):
	return (availability.repeat_this_event != 1) & (
		((availability.from_date <= doc.from_date) & (availability.to_date >= doc.from_date))
		| ((availability.from_date <= doc.to_date) & (availability.to_date >= doc.to_date))
		| ((availability.from_date > doc.from_date) & (availability.to_date < doc.to_date))
	)


def get_time_overlap(doc, availability):
	return (
		((availability.from_time >= doc.from_time) & (availability.from_time < doc.to_time))
		| ((availability.to_time > doc.from_time) & (availability.to_time <= doc.to_time))
		| (
			availability.from_time.between(doc.from_time, doc.to_time)
			& availability.to_time.between(doc.from_time, doc.to_time)
		)
		| ((availability.from_time < doc.from_time) & (availability.to_time > doc.to_time))
	)


def validate_event_overlap(doc):
	if not doc.name:
		# hack! if name is null, it could cause problems with !=
		doc.name = "New " + doc.doctype

	availability = DocType("Practitioner Availability")
	overlap_doc = (
		frappe.qb.from_(availability)
		.select(
			availability.name,
			availability.from_date,
			availability.from_time,
			availability.to_time,
			availability.service_unit,
		)
		.where(
			(availability.name != doc.name)
			& (availability.present == doc.present)
			& (availability.practitioner == doc.get("practitioner"))
			& (availability.docstatus < 2)
			& (get_repeating_event_overlap(doc, availability) | get_single_event_overlap(doc, availability))
			& get_time_overlap(doc, availability)
		)
	).run(as_dict=True)

	if overlap_doc:
		if doc.service_unit:
			for overlap in overlap_doc:
				if doc.service_unit == overlap.service_unit:
					throw_overlap_error(
						doc,
						doc.practitioner,
						overlap.name,
						overlap.from_date,
						overlap.from_time,
						overlap.to_time,
					)
		else:
			throw_overlap_error(
				doc,
				doc.practitioner,
				overlap_doc[0].name,
				overlap_doc[0].from_date,
				overlap_doc[0].from_time,
				overlap_doc[0].to_time,
			)


def throw_overlap_error(doc, exists_for, overlap_doc, from_date, from_time, to_time):
	msg = (
		_(f"A {doc.doctype} exists on {formatdate(from_date)} with time {from_time} to {to_time} (")
		+ f""" <b><a href="#Form/{doc.doctype}/{overlap_doc}">{overlap_doc}</a></b>"""
		+ _(f") for {exists_for}")
	)
	frappe.throw(msg)
