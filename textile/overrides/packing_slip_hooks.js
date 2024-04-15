frappe.provide("textile");

frappe.ui.form.on("Packing Slip", {
	setup: function(frm) {
		frm.cscript.calculate_total_hooks.push(textile.calculate_panel_qty);
	},

	refresh: function(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__('Pretreatment Order'), function() {
				textile.get_items_from_pretreatment_order(
					frm,
					"textile.fabric_pretreatment.doctype.pretreatment_order.pretreatment_order.make_packing_slip",
					{packing_status: "To Pack"}
				);
			}, __("Get Items From"));

			frm.add_custom_button(__('Print Order'), function() {
				textile.get_items_from_print_order(
					frm,
					"textile.fabric_printing.doctype.print_order.print_order.make_packing_slip",
					{packing_status: "To Pack"}
				);
			}, __("Get Items From"));

			frm.fields_dict.items.grid.add_custom_button(__("Add Return Fabric"), function () {
				return frm.call("add_return_fabric");
			});
		}
	},
});

frappe.ui.form.on("Packing Slip Item", {
	panel_qty: function(frm, cdt, cdn) {
		textile.calculate_panel_length_meter(frm, cdt, cdn);
	},

	panel_based_qty: function(frm, cdt, cdn) {
		frm.cscript.calculate_totals();
	},
	rejected_qty: function(frm, cdt, cdn) {
		let row = frappe.get_doc(cdt, cdn);
		frappe.call({
			method: "textile.utils.is_this_item_return_fabric",
			args: {
				doc: frappe.get_doc(frm.doc.doctype, frm.doc.name),
				row: row,
			},
			callback: function (r) {
				if (r.message && row.rejected_qty != 0) {
					row.rejected_qty = 0;
				}

				if (!r.message) {
					frappe.model.set_value(cdt, cdn, "qty", row.qty - row.rejected_qty);			
					frm.doc.total_rejected_qty = 0;
					for (let item of frm.doc.items) {
						frm.doc.total_rejected_qty += item.rejected_qty;
					}
				}
			}
		})
	}
});
