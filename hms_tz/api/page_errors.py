import json
from urllib.parse import urlparse

# Path of the Vue pages (frontend/src/router.js).
PAGE_PATH = "/frontend"


def drop_alerts_from_page_errors(response, request):
	"""Leaves the info alerts out of a failed request from the Vue pages.

	A failed request is rolled back, so its alerts describe work that did not happen. frappe-ui drops the
	alert flag of each message, so the pages would list the alerts as errors. Desk requests keep them.
	"""
	if response.status_code < 400 or response.mimetype != "application/json" or not is_page_request(request):
		return
	data = json.loads(response.get_data())
	messages = [json.loads(message) for message in json.loads(data.get("_server_messages") or "[]")]
	errors = [message for message in messages if not message.get("alert")]
	# A failure that carries only alerts keeps them, so the user still reads why it failed.
	if not errors or len(errors) == len(messages):
		return
	data["_server_messages"] = json.dumps([json.dumps(message) for message in errors])
	response.set_data(json.dumps(data))


def is_page_request(request):
	"""Whether the request comes from one of the Vue pages, by the page that sent it."""
	path = urlparse(request.headers.get("Referer", "")).path
	return path == PAGE_PATH or path.startswith(f"{PAGE_PATH}/")
