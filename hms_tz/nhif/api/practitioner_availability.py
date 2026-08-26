# Copyright (c) 2020, Aakvatech and contributors
# For license information, please see license.txt


from frappe.utils import add_days, add_months, add_years, getdate, time_diff_in_seconds

from hms_tz.nhif.doctype.practitioner_availability_detail.practitioner_availability_detail import (
	create_practitioner_availability_detail,
	delelte_all_related_practitioner_availability_detail,
)


def validate(doc, method):
	delelte_all_related_practitioner_availability_detail(doc)
	if not doc.repeat_this_event:
		detail_doc = create_practitioner_availability_detail(doc, doc.from_date)
		detail_doc.insert(ignore_permissions=True)
	else:
		start_date = doc.from_date
		end_date = doc.repeat_till
		current_date = start_date

		if doc.repeat_on == "Every Year":
			while check_dates(current_date, end_date):
				detail_doc = create_practitioner_availability_detail(doc, current_date)
				detail_doc.insert(ignore_permissions=True)
				current_date = add_years(current_date, 1)

		elif doc.repeat_on == "Every Month":
			while check_dates(current_date, end_date):
				detail_doc = create_practitioner_availability_detail(doc, current_date)
				detail_doc.insert(ignore_permissions=True)
				current_date = add_months(current_date, 1)

		elif doc.repeat_on == "Every Week":
			while check_dates(current_date, end_date):
				detail_doc = create_practitioner_availability_detail(doc, current_date)
				detail_doc.insert(ignore_permissions=True)
				current_date = add_days(current_date, 7)

		elif doc.repeat_on == "Every Day":
			while check_dates(current_date, end_date):
				weekday = get_weekday(current_date)
				if doc.get(weekday):
					detail_doc = create_practitioner_availability_detail(doc, current_date)
					detail_doc.insert(ignore_permissions=True)
				current_date = add_days(current_date, 1)


def on_trash(doc, method):
	delelte_all_related_practitioner_availability_detail(doc)


def get_weekday(date):
	date = getdate(date)
	weekday = date.strftime("%A")
	return weekday.lower()


def check_dates(start_date, end_date):
	diff = time_diff_in_seconds(end_date, start_date)
	if diff < 0:
		return False
	else:
		return True
