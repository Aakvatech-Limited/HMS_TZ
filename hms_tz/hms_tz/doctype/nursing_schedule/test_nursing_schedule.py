# Copyright (c) 2026, Aakvatech and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from hms_tz.hms_tz.doctype.nursing_schedule.nursing_schedule import _shift_ended_before


def _schedule(start, end):
	return frappe._dict(shift_start_time=start, shift_end_time=end)


class TestNursingSchedule(FrappeTestCase):
	def test_day_shift_ended_before_afternoon_admission(self):
		schedule = _schedule("07:00:00", "13:00:00")
		self.assertTrue(_shift_ended_before("2026-09-17", schedule, "2026-09-17 13:01:44"))

	def test_day_shift_still_running_at_admission(self):
		schedule = _schedule("13:00:00", "19:00:00")
		self.assertFalse(_shift_ended_before("2026-09-17", schedule, "2026-09-17 13:01:44"))

	def test_overnight_shift_ends_next_day(self):
		schedule = _schedule("19:00:00", "07:00:00")
		self.assertFalse(_shift_ended_before("2026-09-17", schedule, "2026-09-17 23:30:00"))
		self.assertTrue(_shift_ended_before("2026-09-17", schedule, "2026-09-18 08:00:00"))

	def test_missing_times_never_skip(self):
		self.assertFalse(_shift_ended_before("2026-09-17", _schedule(None, None), "2026-09-17 23:00:00"))
		self.assertFalse(_shift_ended_before("2026-09-17", _schedule("07:00:00", "13:00:00"), None))
