import frappe
from frappe.handler import run_doc_method
from frappe.tests.utils import FrappeTestCase

BODY_PART = "_Test Exercise Knee"


class TestTherapyTypeExercises(FrappeTestCase):
	def setUp(self):
		frappe.get_doc(doctype="Body Part", body_part=BODY_PART).insert()
		self.exercise = frappe.get_doc(
			doctype="Exercise Type",
			exercise_name="_Test Knee Bend",
			body_parts=[{"body_part": BODY_PART}],
		).insert()

	def tearDown(self):
		frappe.db.rollback()

	def test_no_body_parts_returns_no_exercises(self):
		therapy_type = frappe.new_doc("Therapy Type")

		self.assertEqual(therapy_type.get_exercises_for_body_parts(), [])

		therapy_type.add_exercises()
		self.assertEqual(therapy_type.exercises, [])

	def test_body_part_returns_matching_exercise(self):
		therapy_type = frappe.new_doc("Therapy Type")
		therapy_type.append("therapy_for", {"body_part": BODY_PART})

		therapy_type.add_exercises()

		self.assertEqual([row.exercise_type for row in therapy_type.exercises], [self.exercise.name])

	def test_add_exercises_button_runs_from_form(self):
		previous_request = getattr(frappe.local, "request", None)
		self.addCleanup(setattr, frappe.local, "request", previous_request)
		frappe.local.request = frappe._dict(method="POST")
		therapy_type = frappe.new_doc("Therapy Type")
		therapy_type.append("therapy_for", {"body_part": BODY_PART})

		run_doc_method("add_exercises", docs=frappe.as_json(therapy_type.as_dict()))

		exercises = frappe.response.docs[-1].exercises
		self.assertEqual([row.exercise_type for row in exercises], [self.exercise.name])
