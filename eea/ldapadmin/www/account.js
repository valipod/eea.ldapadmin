$(document).ready(function(){
	$('.hidden').hide();
});

function toggleView(selector){
	$(selector).slideToggle();
	
	return false;
}