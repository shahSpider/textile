# Copyright (c) 2024, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _


def execute(filters=None):
	return FabricLedger(filters).run()


class FabricLedger:
	def __init__(self, filters=None):
		self.filters = frappe._dict(filters or {})

	def run(self):
		self.get_data()
		self.get_columns()

		return self.columns, self.data

	def get_data(self):
		conditions = self.get_conditions()
		data = []

		balance_cond = ""
		if self.filters.item_code:
			balance_cond += " and sle.item_code = '%s'"%self.filters.item_code
		if self.filters.from_date:
			balance_cond += " and sle.posting_date < '%s'"%self.filters.from_date
		if self.filters.warehouse:
			balance_cond += " and sle.warehouse = '%s'"%self.filters.warehouse

		previous_balance_qty = frappe.db.sql(""" 
			select ROUND(IFNULL(qty_after_transaction), 2) as qty_after_transaction
				from `tabStock Ledger Entry` sle
				inner join `tabItem` item on sle.item_code=item.item_code
				where (((sle.voucher_type = 'Stock Entry') and ((SELECT stock_entry_type FROM `tabStock Entry` where name=sle.voucher_no) in ('Customer Fabric Receipt', 'Rejected Fabric'))) OR (sle.voucher_type='Stock Reconciliation')) {}
				order by sle.creation DESC limit 1
			""".format(balance_cond), as_dict=1)
		
		report_query = frappe.db.sql("""
			select
				sle.item_code, item.item_name, sle.warehouse, sle.posting_date as date, sle.voucher_type, sle.voucher_no,
				sle.party_type, sle.party, sle.stock_uom as uom, ROUND(IFNULL(sle.actual_qty, 0), 2) as actual_qty, ROUND(IFNULL(sle.qty_after_transaction, 0), 2) as qty_after_transaction
				from `tabStock Ledger Entry` sle
				inner join `tabItem` item on sle.item_code=item.item_code
				where (((sle.voucher_type = 'Stock Entry') and ((SELECT stock_entry_type FROM `tabStock Entry` where name=sle.voucher_no) in ('Customer Fabric Receipt', 'Rejected Fabric'))) OR (sle.voucher_type='Stock Reconciliation')) {}
				order by sle.creation
		""".format(conditions), as_dict=1, debug=1)
		
		data.extend(previous_balance_qty)
		data.extend(report_query)
		total_in_qty = 0.0
		total_out_qty = 0.0
		balance_qty = data[-1].qty_after_transaction if data else 0
		for d in data[1:]:
			entry_changes = {
				"purpose": frappe.get_value(d.get("voucher_type"), d.get("voucher_no"), "purpose" if d.voucher_type=="Stock Reconciliation" else "stock_entry_type"),
				"in_qty" : d.actual_qty if d.actual_qty > 0 else 0,
				"out_qty" : d.actual_qty if d.actual_qty < 0 else 0, 
			}
			d.update(entry_changes)
			total_in_qty += d.actual_qty if d.actual_qty > 0 else 0
			total_out_qty += d.actual_qty if d.actual_qty < 0 else 0
		
		report_date = (frappe.utils.format_date(frappe.utils.getdate(), "d MMM y")).upper()
		report_from_date = frappe.utils.format_date(self.filters.from_date, "dd MMM y")
		report_to_date = frappe.utils.format_date(self.filters.to_date, "dd MMM y")

		
		print_details = {
			"report_date": report_date,
			"report_from_date": report_from_date,
			"report_to_date": report_to_date,
			"total_in_qty": round(total_in_qty, 2),
			"total_out_qty": round(total_out_qty),
			"balance_qty": balance_qty,
			"previous_balance_qty": previous_balance_qty[0].qty_after_transaction if previous_balance_qty else 0,
		}
		data.insert(0, print_details)
		
		self.data = data
	
	def get_conditions(self):
		filters = self.filters
		conditions = ""
		
		if filters.get("company"):
			conditions += " and sle.company = '%s'"%(filters.company)
		if filters.get("from_date"):
			conditions += " and sle.posting_date >= '%s'"%(filters.from_date)
		if filters.get("to_date"):
			conditions += " and sle.posting_date <= '%s'"%(filters.to_date)
		if filters.get("customer"):
			conditions += " and sle.party = '%s'"%(filters.customer)
		if filters.get("item_code"):
			conditions += " and sle.item_code = '%s'"%(filters.item_code)
		if filters.get("warehouse"):
			conditions += " and sle.warehouse = '%s'"%(filters.warehouse)
		return conditions
		
	def get_columns(self):
		columns = [
			{"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 95},
			{"label": _("Customer"), "fieldname": "party", "fieldtype": "Link", "options":"Customer", "width": 180, "align": "left"},
			{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 150},
			{"label": _("Voucher #"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 150},
			{"label": _("Item Code"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 200},
			{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 250, "hide_if_filtered": 1},
			{"label": _("Warehouse"), "fieldname": "warehouse", "fieldtype": "Link", "options": "Warehouse", "width": 200, "hide_if_filtered": 1},
			{"label": _("UOM"), "fieldname": "uom", "fieldtype": "Link", "options": "UOM", "width": 60},
			{"label": _("In Qty"), "fieldname": "in_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
			{"label": _("Out Qty"), "fieldname": "out_qty", "fieldtype": "Float", "width": 80, "convertible": "qty"},
			{"label": _("Balance Qty"), "fieldname": "qty_after_transaction", "fieldtype": "Float", "width": 100, "convertible": "qty"},
		]
		self.columns = columns