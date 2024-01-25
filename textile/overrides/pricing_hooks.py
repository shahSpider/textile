import frappe
from frappe.utils import flt
from textile.fabric_printing.doctype.print_pricing_rule.print_pricing_rule import (
	get_printing_rate,
	get_printing_rate_rule
)


def get_price_list_rate(item_code, price_list, args):
	if not item_code or not price_list:
		return

	item = frappe.get_cached_doc("Item", item_code)

	if item.textile_item_type == "Printed Design":
		customer = args.get("customer") or (args.get("quotation_to") == "Customer" and args.get("party_name"))
		printing_rate = get_printing_rate(item_code, price_list, customer=customer)
		fabric_rate = get_fabric_rate(item.fabric_item, price_list, args)

		return printing_rate + fabric_rate


def get_fabric_rate(fabric_item_code, price_list, args=None):
	from erpnext.stock.get_item_details import get_price_list_rate_for

	if not args:
		args = frappe._dict()

	is_customer_provided_item = frappe.get_cached_value("Item", fabric_item_code, "is_customer_provided_item")
	if is_customer_provided_item:
		fabric_rate = 0
	else:
		fabric_rate = flt(get_price_list_rate_for(fabric_item_code, price_list, args))

	return fabric_rate


@frappe.whitelist()
def get_design_item_price_breakup(item_code, price_list, customer=None):
	item = frappe.get_cached_doc("Item", item_code)
	if item.textile_item_type == "Printed Design":
		fabric_item_code = item.fabric_item
	else:
		fabric_item_code = item_code

	out = get_printing_rate_rule(item_code, price_list, customer)
	fabric_rate = get_fabric_rate(fabric_item_code, price_list, frappe._dict({"customer": customer}))

	out["fabric_rate"] = fabric_rate
	out["price_list_rate"] = fabric_rate + flt(out.get("printing_rate"))

	return out
