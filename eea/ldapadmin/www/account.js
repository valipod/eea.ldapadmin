$(document).ready(function(){
	$('.hidden').hide();
});

function toggleView(selector){
	$(selector).toggle();
	
	return false;
}