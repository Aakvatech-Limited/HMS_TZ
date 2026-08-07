# -*- coding: utf-8 -*-
# Copyright (c) 2025, Aakvatech and contributors
# For license information, please see license.txt

import frappe
from frappe.sessions import clear_sessions


def on_session_creation(login_manager):
    """Enforce single-device login (Ministry of Health requirement).

    When a user logs in from a new device, every other active session for
    that user is terminated, so credentials can never be in use on two
    devices at once. The newest login always wins.

    Frappe's own deny_multiple_sessions setting is not enough: it calls
    clear_sessions without force, so the offset from the user's
    simultaneous_sessions field keeps the most recent other session alive.
    force=True ignores that count and clears all sessions except this one.
    """
    user = login_manager.user
    if user == "Administrator":
        return

    clear_sessions(user=user, keep_current=True, force=True)
    frappe.publish_realtime("hms_tz_sessions_cleared", user=user, after_commit=True)
