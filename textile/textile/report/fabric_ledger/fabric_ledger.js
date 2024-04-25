// Copyright (c) 2024, ParaLogic and contributors
// For license information, please see license.txt
/* eslint-disable */

frappe.query_reports["Fabric Ledger"] = {
	"filters": [
		{
			"fieldname":"company",
			"label": __("Company"),
			"fieldtype": "Link",
			"options": "Company",
			"default": frappe.defaults.get_user_default("Company"),
			"bold": 1
		},
		{
			"fieldname":"from_date",
			"label": __("From Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			"reqd": 1
		},
		{
			"fieldname":"to_date",
			"label": __("To Date"),
			"fieldtype": "Date",
			"default": frappe.datetime.get_today(),
			"reqd": 1
		},
		{
			"fieldname": "customer",
			"label": __("Customer"),
			"fieldtype": "Link",
			"options": "Customer"
		},
		{
			"fieldname":"item_code",
			"label": __("Item"),
			"fieldtype": "Link",
			"options": "Item",
			"get_query": function() {
				return {
					query: "erpnext.controllers.queries.item_query",
					filters: {'include_disabled': 1, "include_templates": 1, "textile_item_type": "Ready Fabric"}
				}
			},
			on_change: function() {
				var item_code = frappe.query_report.get_filter_value('item_code');
				if(!item_code) {
					frappe.query_report.set_filter_value('item_name', "");
				} else {
					frappe.db.get_value("Item", item_code, 'item_name', function(value) {
						frappe.query_report.set_filter_value('item_name', value['item_name']);
					});
				}
			}
		},
		{
			"fieldname":"item_name",
			"label": __("Item Name"),
			"fieldtype": "Data",
			"hidden": 1
		},
		{
			"fieldname":"warehouse",
			"label": __("Warehouse"),
			"fieldtype": "Link",
			"options": "Warehouse"
		}
	],
	
	formatter: function(value, row, column, data, default_formatter) {
		var style = {};
	
		$.each(['in_qty', 'out_qty'], function (i, f) {
			if (column.fieldname === 'in_qty') {
				style['color'] = 'green';
			}
			if (column.fieldname === 'out_qty') {
				style['color'] = 'red';
			}
		});
	
		return default_formatter(value, row, column, data, {css: style});
	},
};
