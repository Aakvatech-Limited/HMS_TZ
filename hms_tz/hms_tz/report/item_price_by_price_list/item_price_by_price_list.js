// Copyright (c) 2023, Aakvatech and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Item Prices by Price List"] = {
  filters: [
    {
      fieldname: "price_list",
      label: __("Price List"),
      fieldtype: "Link",
      options: "Price List",
    },
    {
      fieldname: "item_group",
      label: __("Item Group"),
      fieldtype: "Link",
      options: "Item Group",
    }
  ],
};
