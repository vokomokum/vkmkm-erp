<?php 
/* 
Plugin Name: Styled Facebook Like Box
Description: Displays a Facebook Like Box with options for <strong>border color</strong>, <strong>backgound color</strong> and a <strong>field to ajust the div via custom css styles</strong> such as positioning, border radius etc. Observe that some default Facebook styles, such as border, can't be overwriten.
Version: 1.6
Author: Eduardo Russo
Author URI: http://universo.mobi
Plugin URI: http://wordpress.org/extend/plugins/styled-facebook-like-box
License: GPL2
*/

$styled_facebook_like_box_options['widget_fields']['title'] = array('label'=>'Widget title:', 'type'=>'text', 'default'=>'Facebook', 'class'=>'widefat', 'size'=>'', 'help'=>'The title before your widget');
$styled_facebook_like_box_options['widget_fields']['profile_url'] = array('label'=>'FanPage URL:', 'type'=>'text', 'default'=>'http://facebook.com/universo.mobi', 'class'=>'widefat', 'size'=>'', 'help'=>'Your Facebook Fan Page URL');
$styled_facebook_like_box_options['widget_fields']['language'] = array('label'=>'Language:', 'type'=>'text', 'default'=>'en_US', 'class'=>'', 'size'=>'5', 'help'=>'en_US, fr_FR, pt_BR… the language code you want the Widget to display');
$styled_facebook_like_box_options['widget_fields']['width'] = array('label'=>'Width:', 'type'=>'text', 'default'=>'300', 'class'=>'', 'size'=>'3', 'help'=>'(Value in px)');
$styled_facebook_like_box_options['widget_fields']['height'] = array('label'=>'Height:', 'type'=>'text', 'default'=>'550', 'class'=>'', 'size'=>'3', 'help'=>'(Value in px)');
$styled_facebook_like_box_options['widget_fields']['border_color'] = array('label'=>'Border color:', 'type'=>'text', 'default'=>'#000', 'class'=>'', 'size'=>'', 'help'=>'(#E1E4E6, white)');
$styled_facebook_like_box_options['widget_fields']['background_color'] = array('label'=>'Background color:', 'type'=>'text', 'default'=>'#FFF', 'class'=>'', 'size'=>'', 'help'=>'(#E123F0, blue)');
$styled_facebook_like_box_options['widget_fields']['faces'] = array('label'=>'Show faces:', 'type'=>'checkbox', 'default'=>true, 'class'=>'', 'size'=>'', 'help'=>'Show profile photos');
$styled_facebook_like_box_options['widget_fields']['stream'] = array('label'=>'Show stream:', 'type'=>'checkbox', 'default'=>false, 'class'=>'', 'size'=>'', 'help'=>'Show profile stream');
$styled_facebook_like_box_options['widget_fields']['header'] = array('label'=>'Show header:', 'type'=>'checkbox', 'default'=>false, 'class'=>'', 'size'=>'', 'help'=>'Show default Facebook header');
$styled_facebook_like_box_options['widget_fields']['style_code'] = array('label'=>'Style code:', 'type'=>'textarea', 'default'=>'-moz-border-radius: 10px; border-radius: 10px; -webkit-border-radius:10px;', 'class'=>'', 'rows'=>'6', 'cols'=>'31', 'help'=>'margin-left: -40px; border-radius: 10px;');

//Insert Facebook default JavaScript
function facebook_default_javascript(){
	global $styled_facebook_like_box_options; 
	$options = get_option('widget_styled_facebook_like_box');
	$language = $options['language'];
	
	echo "<script>
	(function(d, s, id) {
  		var js, fjs = d.getElementsByTagName(s)[0];
  		if (d.getElementById(id)) return;
  		js = d.createElement(s); js.id = id;
  		js.src = '//connect.facebook.net/$language/all.js#xfbml=1';
  		fjs.parentNode.insertBefore(js, fjs);
	}(document, 'script', 'facebook-jssdk'));
</script>
";
}
// Output the widget in the sidebar
function styled_facebook_like_box($title, $profile_url, $width, $height, $faces, $border_color, $background_color, $stream, $header, $style_code){
	//Insert the styled Like Box
	echo "<div id='fb-root' class='widget widget_facebook_like_box'><div class='fb-like-box' data-href='$profile_url' data-width='$width' data-height='$height' data-show-faces='$faces' data-border-color='$border_color' data-stream='$stream' data-header='$header' style='background-color:$background_color;";
	if ($style_code)
		echo $style_code;
	echo "'></div>";
}

function widget_styled_facebook_like_box_init(){
	if (!function_exists('register_sidebar_widget'))
		return;
	$check_options = get_option('widget_styled_facebook_like_box');

	// Save the form data
	function widget_styled_facebook_like_box($args){

		global $styled_facebook_like_box_options; 
		extract($args);
		$options = get_option('widget_styled_facebook_like_box');
		
		// Fill options with default values if value is not set
		$item = $options;
		foreach($styled_facebook_like_box_options['widget_fields'] as $key => $field){
			if (! isset($item[$key])){
				$item[$key] = $field['default'];
			}
		} 
		
		$title = $item['title']; 
		$profile_url = $item['profile_url'];
		$language = $item['language'];
		$width = $item['width'];
		$height = $item['height'];
		$faces = $item['faces'] ? "true" : "false";
		$border_color = $item['border_color'];
		$background_color = $item['background_color'];
		$stream = ($item['stream']) ? "true" : "false";
		$header = ($item['header']) ? "true" : "false";
		$style_code = $item['style_code'];

		//Remove the Wordpress Title if none was set
		if ($title)
			echo $before_widget . $before_title . $title;
		
		echo $after_title; 

 	styled_facebook_like_box($title, $profile_url, $width, $height, $faces, $border_color, $background_color, $stream, $header, $style_code);
 	echo $after_widget;
	}
	
	// Output the widget form
	function widget_styled_facebook_like_box_control(){
	
		global $styled_facebook_like_box_options;

		$options = get_option('widget_styled_facebook_like_box');
		if (isset($_POST['styled_facebook_like_box-submit'])){

			foreach($styled_facebook_like_box_options['widget_fields'] as $key => $field){
				$options[$key] = $field['default'];
				$field_name = sprintf('%s', $key); 
				if ($field['type'] == 'text' || $field['type'] == 'textarea'){
					$options[$key] = strip_tags(stripslashes($_POST[$field_name]));
				}
				elseif ($field['type'] == 'checkbox'){
					$options[$key] = isset($_POST[$field_name]);
				}
			}

			update_option('widget_styled_facebook_like_box', $options);
		}
 
		foreach($styled_facebook_like_box_options['widget_fields'] as $key => $field){
			// print_r($field);
			$field_name = sprintf('%s', $key);
			$field_checked = '';
			if ($field['type'] == 'text' || $field['type'] == 'textarea'){
				$field_value = (isset($options[$key])) ? htmlspecialchars($options[$key], ENT_QUOTES) : htmlspecialchars($field['default'], ENT_QUOTES);
			} elseif ($field['type'] == 'checkbox'){
				$field_value = (isset($options[$key])) ? $options[$key] :$field['default'] ;
				if ($field_value == 1){
					$field_checked = 'checked="checked"';
				}
			}
			$jump = ($field['type'] != 'checkbox') ? '<br />' : '&nbsp;';
			$field_class = $field['class'];
			$field_size = ($field['class'] != '') ? '' : 'size="'.$field['size'].'"';
			$field_help = ($field['help'] == '') ? '' : '<small>'.$field['help'].'</small>';
			//Exclusive for textarea
			$field_rows = ($field['rows'] == '') ? '' : 'rows="'.$field['rows'].'"';
			$field_cols = ($field['cols'] == '') ? '' : 'cols="'.$field['cols'].'"';
			if ($field['type'] != 'textarea'){
				printf("<p class='styled_facebook_like_box_field'>".
						"<label for='$field_name'>" . __($field['label']) . "</label>$jump".
						"<input id='$field_name' name='$field_name' type='" . $field['type'] . "' value='$field_value' class='$field_class' $field_size $field_checked />".
						"$field_help</p>");
			}
			else{
				printf("<p class='styled_facebook_like_box_field'>".
						"<label for='$field_name'>" . __($field['label']) . "</label>$jump".
						"<textarea id='$field_name' name='$field_name' value='$field_value' class='$field_class' $field_rows $field_cols>$field_value</textarea>".
						"$field_help</p>");
			}
		}
		echo '<input type="hidden" id="styled_facebook_like_box-submit" name="styled_facebook_like_box-submit" value="1" />';
	}
	
	// Register the widget with WordPress
	function widget_styled_facebook_like_box_register(){		
		$title = 'Styled Facebook Like Box';
		// Register widget for use
		register_sidebar_widget($title, 'widget_styled_facebook_like_box'); 
		// Register settings for use, 300x100 pixel form
		register_widget_control($title, 'widget_styled_facebook_like_box_control');
	}
	widget_styled_facebook_like_box_register();
}
add_action('wp_head', 'facebook_default_javascript');
add_action('widgets_init', 'widget_styled_facebook_like_box_init');
?>