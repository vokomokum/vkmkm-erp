$(document).ready(function(){
	
	//Clickable table rows
	$(document)
	.on('click', 'table tbody tr[data-href]', function(){
		var href = $(this).attr('data-href');
		if( typeof href != 'undefined') 
			window.location = href;
	})
	.on('change', '#list-options input[name="include_inactive"]', function(){
		//Members list inxactive
		$(this).closest('form').submit();
	});
	
	
});

$(".chzn-select").chosen(); $(".chzn-select-deselect").chosen({allow_single_deselect:true});

// shed outer layout when this is embedded (e.g. in an iframe)
if (top != self) {
  var head = document.getElementsByTagName("head")[0];
  var css = document.createElement('link');
  css.type = 'text/css';
  css.rel = 'stylesheet';
  css.href = '${portal_url}' + "/static/embed.css";
  css.media = 'screen';
  head.appendChild(css);
}