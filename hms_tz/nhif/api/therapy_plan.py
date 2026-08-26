from hms_tz.hms_tz.doctype.hospital_revenue_entry.hospital_revenue_entry import create_revenue_entry


def before_insert(doc, method):
	total_sessions = 0
	total_sessions_cancelled = 0
	for entry in doc.therapy_plan_details:
		if entry.no_of_sessions:
			total_sessions += entry.no_of_sessions

		if entry.sessions_cancelled:
			total_sessions_cancelled += entry.sessions_cancelled

	doc.total_sessions = total_sessions
	doc.total_sessions_cancelled = total_sessions_cancelled


def after_insert(doc, method):
	create_revenue_entry(doc)


def validate(doc, method):
	set_totals(doc)
	set_status(doc)


def set_status(doc):
	if doc.total_sessions == 0 and doc.total_sessions_cancelled > 0:
		doc.status = "Not Serviced"

	elif doc.total_sessions and not doc.total_sessions_completed:
		doc.status = "Not Started"

	elif doc.total_sessions_completed < doc.total_sessions:
		doc.status = "In Progress"

	elif doc.total_sessions != 0 and (doc.total_sessions_completed == doc.total_sessions):
		doc.status = "Completed"


def set_totals(doc):
	total_sessions_completed = 0
	total_sessions_cancelled = 0
	for entry in doc.therapy_plan_details:
		if entry.sessions_completed:
			total_sessions_completed += entry.sessions_completed

		if entry.sessions_cancelled:
			total_sessions_cancelled += entry.sessions_cancelled

	doc.total_sessions_completed = total_sessions_completed
	doc.total_sessions_cancelled = total_sessions_cancelled
