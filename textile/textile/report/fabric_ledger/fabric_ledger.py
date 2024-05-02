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
		if self.filters.get("voucher_type"):
			conditions += " and sle.voucher_type = '%s'"%(self.filters.voucher_type)
		if self.filters.get("voucher_no"):
			conditions += " and sle.voucher_no = '%s'"%(self.filters.voucher_no)

		previous_balance_qty = frappe.db.sql(""" 
			select "<b>Opening</b>" as voucher_type, sle.qty_after_transaction
				from `tabStock Ledger Entry` sle
				inner join `tabItem` item on sle.item_code=item.item_code and NOT(item.textile_item_type IS NULL OR item.textile_item_type = '') and item.textile_item_type not in ('Print Process', 'Process Component', 'Filter Cartridge', 'Filter Media', 'Filter Core', 'Filter End Adapter')
				left join `tabStock Entry` ste on sle.voucher_type = "Stock Entry" and sle.voucher_no = ste.name
				where sle.is_cancelled = 0  and ((ste.purpose IS NULL) OR (ste.purpose NOT IN ('Manufacture', 'Material Transfer for Manufacture', 'Material Consumption for Manufacture',  'Material Transfer'))) {conditions}
				order by sle.posting_date DESC, sle.posting_time DESC, sle.creation DESC limit 1
			""".format(conditions = balance_cond), as_dict=1)
		
		report_query = frappe.db.sql("""
			select
				sle.item_code, item.item_name, sle.warehouse, sle.posting_date as date, sle.voucher_type, sle.voucher_no,
				sle.party_type, sle.party, sle.stock_uom as uom, IFNULL(sle.actual_qty, 0) as actual_qty, IF(sle.actual_qty > 0, sle.actual_qty, 0) as in_qty,
				IF(sle.actual_qty < 0, sle.actual_qty, 0) as out_qty, IFNULL(sle.qty_after_transaction, 0) as qty_after_transaction, 
				IF(item.textile_item_type='Printed Design', item.fabric_item, item.item_code) as fabric_item,
				IF(item.textile_item_type='Printed Design', item.fabric_item_name, item.item_name) as fabric_item_name,
				ps.rejected_warehouse, psi.source_warehouse, psi.qty as packed_qty, psi.rejected_qty as rejected_qty
				from `tabStock Ledger Entry` sle
				inner join `tabItem` item on sle.item_code=item.item_code and NOT(item.textile_item_type IS NULL OR item.textile_item_type = '') and item.textile_item_type not in ('Print Process', 'Process Component', 'Filter Cartridge', 'Filter Media', 'Filter Core', 'Filter End Adapter')
				left join `tabStock Entry` ste on sle.voucher_type = "Stock Entry" and sle.voucher_no = ste.name
				left join `tabPacking Slip Item` psi on sle.voucher_no = psi.parent and sle.item_code = psi.item_code and psi.rejected_qty > 0
				left join `tabPacking Slip` ps on psi.parent = ps.name
				where sle.is_cancelled = 0 and ((ste.purpose IS NULL) OR (ste.purpose NOT IN ('Manufacture', 'Material Transfer for Manufacture', 'Material Consumption for Manufacture', 'Material Transfer'))) {conditions}
				order by sle.posting_date ASC, sle.posting_time ASC, sle.creation ASC
		""".format(conditions=conditions), as_dict=1)
		
		data_grouped_by_fabric_item = defaultdict(list)
		for sle in report_query:
			if sle.voucher_type == "Packing Slip":				
				if sle.voucher_type == "Packing Slip" and sle.rejected_qty and sle.actual_qty > 0 and sle.warehouse == sle.rejected_warehouse:
					sle.warehouse = "Rejected Fabric"
					sle.out_qty = -sle.in_qty
					sle.in_qty = 0
				else:
					continue
			
			fabric_item_voucher_warehouse_key = sle.fabric_item + sle.voucher_no + sle.warehouse
			data_grouped_by_fabric_item[fabric_item_voucher_warehouse_key].append(sle)
		
		fabric_item_wise_map = [] 
		for fabric_item_voucher_warehouse_key, sl_entries in data_grouped_by_fabric_item.items():
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
			total_in_qty += flt(d.get("in_qty"))
			total_out_qty += flt(d.get("out_qty"))

			purpose = d.get("voucher_type")
			if d.get("voucher_type") == "Stock Entry":
				purpose = frappe.get_value(d.get("voucher_type"), d.get("voucher_no"), "stock_entry_type")
			if d.get("voucher_type") == "Stock Reconciliation":
				purpose = frappe.get_value(d.get("voucher_type"), d.get("voucher_no"), "purpose")
			
			entry_changes = {
				"purpose": purpose,
				"in_qty" : "{0:,.2f}".format(flt(d.get("in_qty"))), 
				"out_qty" : "{0:,.2f}".format(flt(d.get("out_qty"))),
				"qty_after_transaction" : "{0:,.2f}".format(flt(d.get("qty_after_transaction"))),
			}
			d.update(entry_changes)
		balance_qty = 0
		if data:
			balance_qty = flt(data[-1].get("qty_after_transaction", 0))
		report_date = (frappe.utils.format_date(frappe.utils.getdate(), "d MMM y")).upper()
		report_from_date = frappe.utils.format_date(self.filters.from_date, "dd MMM y")
		report_to_date = frappe.utils.format_date(self.filters.to_date, "dd MMM y")
		
		prev_balance_qty = previous_balance_qty[0].qty_after_transaction if previous_balance_qty else 0
		print_details = {
			"voucher_type": "<b>Opening</b>",
			"qty_after_transaction": prev_balance_qty,
			"report_date": report_date,
			"report_from_date": report_from_date,
			"report_to_date": report_to_date,
			"total_in_qty": round(total_in_qty, 2),
			"total_out_qty": round(total_out_qty),
			"balance_qty": balance_qty,
			"previous_balance_qty": prev_balance_qty,
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
			conditions += " and  '{item_code}' IN (SELECT item.item_code from `tabItem` where item_code='{item_code}' or fabric_item='{item_code}')".format(item_code=filters.item_code)
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