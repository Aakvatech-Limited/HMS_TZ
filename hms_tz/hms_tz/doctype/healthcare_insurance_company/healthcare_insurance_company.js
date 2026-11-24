// Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and contributors
// For license information, please see license.txt

frappe.ui.form.on("Healthcare Insurance Company", {
  refresh: function (frm) {
    frappe.dynamic_link = {
      doc: frm.doc,
      fieldname: "name",
      doctype: "Insurance Company",
    };

    if (frm.doc.__islocal) {
      hide_field(["address_html", "contact_html", "address_contacts"]);
      frappe.contacts.clear_address_and_contact(frm);
    } else {
      unhide_field(["address_html", "contact_html", "address_contacts"]);
      frappe.contacts.render_address_and_contact(frm);
    }
  },
});
