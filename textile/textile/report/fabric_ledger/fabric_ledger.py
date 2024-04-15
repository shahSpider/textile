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
		
		data = frappe.db.sql("""
			select 
				sle.item_code, item.item_name, sle.warehouse, sle.posting_date as date, sle.voucher_type, sle.voucher_no,
				sle.party_type, sle.party, sle.stock_uom as uom, sle.actual_qty, sle.qty_after_transaction
				from `tabStock Ledger Entry` sle
				inner join `tabStock Entry` ste on sle.voucher_no = ste.name
				inner join `tabItem` item on sle.item_code=item.item_code
				where sle.voucher_type='Stock Entry' and ste.stock_entry_type in ('Customer Fabric Receipt', 'Rejected Fabric') {}
		""".format(conditions), as_dict=1)

		for d in data:
			entry_changes = {
				"in_qty" : d.actual_qty if d.actual_qty > 0 else 0,
				"out_qty" : d.actual_qty if d.actual_qty < 0 else 0, 
			}
			d.update(entry_changes)
		
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
			{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 110},
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