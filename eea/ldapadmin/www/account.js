$(document).ready(function(){
	$('.hidden').hide();

	/**
	 * For tables with select all option check if all checkboxes are selected.
	 * If one of them is unchecked then uncheck the main select all checkbox.
	*/
	$('.account-datatable tbody tr td.checkbox-td input[type="checkbox"]').click(function(){
		name = $(this).attr('name').split(":list")[0];
		if($(this).attr('class') != 'selectall'){
			if($(this).attr('checked') == false){
				$('.selectall').attr('checked', false);
				$(this).attr('checked', false);
			}else {
				var not_all = false;
				$.each($('.account-datatable tbody tr td.checkbox-td input[@name="' + name + '"][type="checkbox"]'), function(i, e){
					if($(this).attr('checked') == false){
						not_all = true;
					}
				});
				if(not_all == false){
					$('.selectall').attr('checked', true);
				}
			}
		}
	});
});

function toggleView(selector){
	$(selector).toggle();
	return false;
}

function selectAll(name){
	$('.account-datatable tbody tr td.checkbox-td input[@name="' + name + '"][type="checkbox"]').attr('checked', $('.selectall').attr('checked'));
	return false;
}
