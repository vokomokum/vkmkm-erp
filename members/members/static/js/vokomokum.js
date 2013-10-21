$(document).ready(function(){
	
	//Clickable table rows
	$(document).on('click', 'table tbody tr[data-href]', function(){
		var href = $(this).attr('data-href');
		if( typeof href != 'undefined') 
			window.location = href;
	});
	
});