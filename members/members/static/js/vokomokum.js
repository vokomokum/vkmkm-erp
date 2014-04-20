$(document).ready(function(){

    //Workgroup add shift form
    function toggleUntilSpec(){
      if ($('#repeat').val() == 'once')
        $('#until-spec').hide();
      else
        $('#until-spec').show();
    }

	//Clickable table rows
	$(document)
	.on('click', 'table tbody tr[data-href]', function(){
		var href = $(this).attr('data-href');
		if( typeof href != 'undefined') 
			window.location = href;
	})
	.on('change', '#list-options input[name="include_inactive"]', function(){
		//Members list inactive
		$(this).closest('form').submit();
	})
    .on('change', '#repeat', function() { toggleUntilSpec() });

    toggleUntilSpec();

});

$(".chzn-select").chosen(); $(".chzn-select-deselect").chosen({allow_single_deselect:true});

// shed outer layout when this is embedded (e.g. in an iframe)
if (top != self) {
  var head = document.getElementsByTagName("head")[0];
  var css = document.createElement('link');
  css.type = 'text/css';
  css.rel = 'stylesheet';
  css.href = '${portal_url}' + "/static/css/embed.css";
  css.media = 'screen';
  head.appendChild(css);
}
