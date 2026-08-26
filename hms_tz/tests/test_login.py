# Copyright (c) 2025, Aakvatech and Contributors
# See license.txt
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.api.login import on_session_creation


def login_manager_for(user):
	return frappe._dict(user=user)


class TestSingleDeviceLogin(FrappeTestCase):
	def test_new_login_clears_all_other_sessions(self):
		"""force=True bypasses simultaneous_sessions, so every other device is logged out."""
		with patch("hms_tz.api.login.clear_sessions") as clear_sessions:
			on_session_creation(login_manager_for("nurse@example.com"))

		clear_sessions.assert_called_once_with(user="nurse@example.com", keep_current=True, force=True)

	def test_new_login_notifies_other_devices(self):
		"""Old devices get a realtime event so they log out instantly, not on next click."""
		with (
			patch("hms_tz.api.login.clear_sessions"),
			patch("hms_tz.api.login.frappe.publish_realtime") as publish_realtime,
		):
			on_session_creation(login_manager_for("nurse@example.com"))

		publish_realtime.assert_called_once_with(
			"hms_tz_sessions_cleared", user="nurse@example.com", after_commit=True
		)

	def test_guest_sessions_are_not_touched(self):
		with patch("hms_tz.api.login.clear_sessions") as clear_sessions:
			on_session_creation(login_manager_for("Guest"))

		clear_sessions.assert_not_called()

	def test_administrator_sessions_are_not_touched(self):
		with patch("hms_tz.api.login.clear_sessions") as clear_sessions:
			on_session_creation(login_manager_for("Administrator"))

		clear_sessions.assert_not_called()
