import json

from frappe.tests.utils import FrappeTestCase
from werkzeug.test import EnvironBuilder
from werkzeug.wrappers import Request, Response

from hms_tz.api.page_errors import drop_alerts_from_page_errors

ERROR = {"message": "Value cannot be changed for Appointment Type", "raise_exception": 1}
SECOND_ERROR = {"message": "Value missing for Patient Appointment: Source", "indicator": "red"}
ALERT = {"message": "Authorization number not set to proceed to create vitals", "alert": 1}


def failed_response(*messages, status=417):
	body = {"exc_type": "ValidationError", "_server_messages": json.dumps([json.dumps(m) for m in messages])}
	return Response(json.dumps(body), status=status, mimetype="application/json")


def request_from(referer):
	return Request(EnvironBuilder(path="/api/method/x", headers={"Referer": referer}).get_environ())


def messages_of(response):
	return [json.loads(m) for m in json.loads(json.loads(response.get_data())["_server_messages"])]


PAGE = "http://hms15-test.localhost:8000/frontend/appointments"
DESK = "http://hms15-test.localhost:8000/app/patient-appointment/HLC-APP-1"


class TestPageErrors(FrappeTestCase):
	def test_page_errors_leave_out_alerts(self):
		response = failed_response(ALERT, ERROR, SECOND_ERROR)
		drop_alerts_from_page_errors(response, request_from(PAGE))

		self.assertEqual(messages_of(response), [ERROR, SECOND_ERROR])
		self.assertEqual(json.loads(response.get_data())["exc_type"], "ValidationError")

	def test_desk_errors_keep_alerts(self):
		response = failed_response(ALERT, ERROR)
		drop_alerts_from_page_errors(response, request_from(DESK))

		self.assertEqual(messages_of(response), [ALERT, ERROR])

	def test_a_failure_with_only_alerts_keeps_them(self):
		response = failed_response(ALERT)
		drop_alerts_from_page_errors(response, request_from(PAGE))

		self.assertEqual(messages_of(response), [ALERT])

	def test_successful_responses_are_not_changed(self):
		response = failed_response(ALERT, ERROR, status=200)
		drop_alerts_from_page_errors(response, request_from(PAGE))

		self.assertEqual(messages_of(response), [ALERT, ERROR])

	def test_page_path_must_match_exactly(self):
		response = failed_response(ALERT, ERROR)
		drop_alerts_from_page_errors(response, request_from("http://host/frontend-other/page"))

		self.assertEqual(messages_of(response), [ALERT, ERROR])
