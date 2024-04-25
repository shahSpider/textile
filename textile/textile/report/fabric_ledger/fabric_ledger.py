# Copyright (c) 2024, ParaLogic and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt
from collections import defaultdict

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
		data = []
		conditions = self.get_conditions()
		balance_cond = self.get_conditions()

		if self.filters.from_date:
			balance_cond += " and sle.posting_date < '%s'"%self.filters.from_date

		if self.filters.get("from_date"):
			conditions += " and sle.posting_date >= '%s'"%(self.filters.from_date)
		if self.filters.get("to_date"):
			conditions += " and sle.posting_date <= '%s'"%(self.filters.to_date)

		previous_balance_qty = frappe.db.sql(""" 
			select "<b>Opening</b>" as voucher_type, sle.qty_after_transaction
				from `tabStock Ledger Entry` sle
				inner join `tabItem` item on sle.item_code=item.item_code
				where sle.is_cancelled = 0 and
					((((sle.voucher_type = 'Stock Entry') and ((SELECT stock_entry_type FROM `tabStock Entry` where name=sle.voucher_no) = 'Customer Fabric Receipt'))
					OR (sle.voucher_type='Stock Reconciliation'))
					OR ((sle.voucher_type='Packing Slip') and ((select is_customer_provided_item FROM `tabItem` where name = item.fabric_item) = 1)
					 and sle.warehouse = (select rejected_warehouse from `tabPacking Slip` where name=sle.voucher_no)) 
					OR ((sle.voucher_type='Delivery Note') and ((select is_customer_provided_item FROM `tabItem` where name = item.fabric_item) = 1))) {conditions}
				order by
						sle.posting_date, sle.posting_time DESC limit 1
			""".format(conditions = balance_cond), as_dict=1)
		
		report_query = frappe.db.sql("""
			select
				sle.item_code, item.item_name, sle.warehouse, sle.posting_date as date, sle.voucher_type, sle.voucher_no,
				sle.party_type, sle.party, sle.stock_uom as uom, ROUND(IFNULL(sle.actual_qty, 0), 2) as actual_qty, IF(sle.actual_qty > 0, sle.actual_qty, 0) as in_qty,
				IF(sle.actual_qty < 0, sle.actual_qty, 0) as out_qty, ROUND(IFNULL(sle.qty_after_transaction, 0), 2) as qty_after_transaction, 
				IF(item.is_customer_provided_item=1, item.item_code, item.fabric_item) as fabric_item,
				IF(item.is_customer_provided_item=1, item.item_name, item.fabric_item_name) as fabric_item_name
				from `tabStock Ledger Entry` sle
				inner join `tabItem` item on sle.item_code=item.item_code and item.fabric_item IS NOT NULL
				where sle.is_cancelled = 0 and
					((((sle.voucher_type = 'Stock Entry') and ((SELECT stock_entry_type FROM `tabStock Entry` where name=sle.voucher_no) = 'Customer Fabric Receipt'))
					OR (sle.voucher_type='Stock Reconciliation'))
					OR ((sle.voucher_type='Packing Slip') and ((select is_customer_provided_item FROM `tabItem` where name = item.fabric_item) = 1)
						 and sle.warehouse = (select rejected_warehouse from `tabPacking Slip` where name=sle.voucher_no))
					OR ((sle.voucher_type='Delivery Note') and ((select is_customer_provided_item FROM `tabItem` where name = item.fabric_item) = 1))) {conditions}
				order by
						sle.posting_date, sle.posting_time
		""".format(conditions=conditions), as_dict=1)
		
		data.extend(previous_balance_qty)
		
		data_grouped_by_fabric_item = defaultdict(list)
		for sle in report_query:
			fabric_item_voucher_key = sle.fabric_item+sle.voucher_no
			data_grouped_by_fabric_item[fabric_item_voucher_key].append(sle)
		
		fabric_item_wise_map = [] 
		for fabric_item_voucher_key, sl_entries in data_grouped_by_fabric_item.items():
			row = defaultdict()
			row.update(sl_entries[0] if sl_entries else {})
			row["in_qty"] = 0
			row["out_qty"] = 0
			row["qty_after_transaction"] = 0
			for sle in sl_entries:
				row["item_code"] = sle.fabric_item
				row["item_name"] = sle.fabric_item_name
				row["in_qty"] += flt(sle.in_qty)
				row["out_qty"] += flt(sle.out_qty)
				row["qty_after_transaction"] += sle.actual_qty
			fabric_item_wise_map.append(row)

		data.extend(fabric_item_wise_map)
		
		# some calculations and formatting of data required in print format
		total_in_qty = 0
		total_out_qty = 0

		for d in data:
			total_in_qty += flt(sle.in_qty)
			total_out_qty += flt(sle.out_qty)

			purpose = d.get("voucher_type")
			if d.get("voucher_type") == "Stock Entry":
				purpose = frappe.get_value(d.get("voucher_type"), d.get("voucher_no"), "stock_entry_type")
			if row.get("voucher_type") == "Stock Reconciliation":
				purpose = frappe.get_value(row.get("voucher_type"), d.get("voucher_no"), "purpose")
			
			entry_changes = {
				"purpose": purpose,
				"in_qty" : "{0:,.2f}".format(flt(d.get("in_qty"))), 
				"out_qty" : "{0:,.2f}".format(flt(d.get("out_qty"))),
				"qty_after_transaction" : "{0:,.2f}".format(flt(d.get("qty_after_transaction"))),
			}
			d.update(entry_changes)
		
		balance_qty = flt(data[-1].get("qty_after_transaction", 0))
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
		if filters.get("customer"):
			conditions += " and sle.party = '%s'"%(filters.customer)
		if filters.get("item_code"):
			conditions += " and IF(item.is_customer_provided_item=1, item.item_code, item.fabric_item) = '%s'"%(filters.item_code)
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