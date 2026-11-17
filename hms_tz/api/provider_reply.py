import json
from contextlib import contextmanager

import frappe
from frappe.utils import now_datetime

RESPONSE_LOGS = {"NHIF": "NHIF Response Log", "Jubilee": "Jubilee Response Log"}


class ProviderReplyError(frappe.ValidationError):
	"""A provider API call failed; the message is the provider's error report as JSON, for the page to show."""


@contextmanager
def provider_call(provider):
	"""Raises an error inside the block as a ProviderReplyError carrying the provider function's error report.

	The provider functions report a failed reply with a msgprint such as "NHIF API Error". An error with no
	reply logged during the block is a local validation and is raised unchanged.
	"""
	since = now_datetime()
	first_message = len(frappe.local.message_log)
	try:
		yield
	except ProviderReplyError:
		raise
	except frappe.ValidationError:
		if has_reply(provider, since):
			# Success alerts of earlier steps come first; the report is the first real message.
			reports = [m for m in frappe.local.message_log[first_message:] if not m.get("alert")]
			raise_reply(provider, reports[0])
		raise


def has_reply(provider, since):
	"""Whether the provider replied to this user since `since`, from its response log."""
	return provider in RESPONSE_LOGS and frappe.db.exists(
		RESPONSE_LOGS[provider], {"user_id": frappe.session.user, "creation": (">=", since)}
	)


def raise_reply(provider, report):
	title = report.get("title")
	payload = {
		"title": title if title and title != "Message" else f"{provider} API Error",
		"message": report.get("message"),
	}
	frappe.local.message_log = []
	frappe.throw(json.dumps(payload), exc=ProviderReplyError)
