frappe.listview_settings["Pretreatment Pricing Rule"] = {
	onload: function(listview) {
		listview.page.add_menu_item(__("Check Pretreatment Rate"), () => {
			textile.pretreatment_pricing_dialog();
		});
	}
};
