<?php
/*
Plugin Name: Wordpress Facebook Like Plugin
Plugin URI: http://allanjosephbatac.com/Wordpress-Facebook-Like-Plugin/
Description: Wordpress Facebook Like Plugin - Add a Facebook "Like" Button to your blog posts and increase your visitor engagement instantly! This plugin adds a simple and easy to use Facebook Like functionality with admin options to change the location of Facebook Like button, font, show faces, use the box with count as well as other cool and useful options. Visitors "liking" your content automatically posts them as shared item on their Facebook profile with a thumbnail of your site's image post. Pretty cool! The Like button lets a user share your content with friends on Facebook. When the user clicks the Like button on your site, a story appears in the user's friends' News Feed with a link back to your website.
Donate link: http://allanjosephbatac.com/blog/
Tags: facebook like plugin, wordpress facebook like, admin, custom, face book, Facebook, facebook like, Facebook like widget, Facebook Widget, fb, fb like, featured, featured posts, Like, page, plugin, Post, posts, wordpress like, facebook recommend, wordpress facebook recommend, facebook send button, facebook send
Author: AJ Batac
Version: 0.4
Requires at least: 2.0.2
Tested up to: 3.1.2
Stable tag: 9.9
Author URI: http://allanjosephbatac.com/blog/
*/

if( !function_exists('wp_fb_like_settings') )
{
	function wp_fb_like_settings ()
	{
		//add_menu_page(page_title, menu_title, capability, handle, [function], [icon_url]);
		add_menu_page("Facebook Like", "Facebook Like", 8, basename(__FILE__), "wp_fb_like_opt");
	}
}

if ( !function_exists('wp_fb_like_opt') )
{
	function wp_fb_like_opt()
	{
	?>
	<div class="wrap">
	<div id="icon-themes" class="icon32"></div>
	<h2><strong>Facebook "Like" Button Settings</strong></h2>
	<span style="font-size:11px;color:#DE1187;"><strong>New!</strong> Now with the Facebook "Send" button option. Just enable the option below and save.</span>
	
	<?php
	if(isset($_POST['wp_fb_form_submit']))
	{
		echo '<div style="color:green;font-weight:bold;background:#FFC;padding:4px;margin:2px 0;">Your Facebook "Like" Settings was saved successfully!</div>';
	}
	?>
	
	<fieldset>
	<form name="wp_fb_option_form" method="post">
	
	<h2>Select button placement</h2>
	<select name="wp_fb_like_align" id="wp_fb_like_align">
		<option value="nb" <?php if ((get_option("wp_fb_like_align") == "nb") || (!get_option("wp_fb_like_align"))) echo ' selected'; ?>>None (Bottom)</option>
		<option value="nt" <?php if (get_option("wp_fb_like_align") == "nt") echo 'selected'; ?>>None (Top)</option>
		<option value="tl" <?php if (get_option("wp_fb_like_align") == "tl") echo 'selected'; ?>>Top Left</option>
		<option value="tr" <?php if (get_option("wp_fb_like_align") == "tr") echo 'selected'; ?>>Top Right</option>
		<option value="bl" <?php if (get_option("wp_fb_like_align") == "bl") echo 'selected'; ?>>Bottom Left</option>
		<option value="br" <?php if (get_option("wp_fb_like_align") == "br") echo 'selected'; ?>>Bottom Right</option>
	</select>
	
	<h2>Layout Style</h2>
	<div class="description">Determines the size and amount of social context next to the button</div>
	<select name="wp_fb_like_layout" id="wp_fb_like_layout">
		<option value="standard" <?php if (get_option("wp_fb_like_layout") == "standard") echo 'selected'; ?>>standard</option>
		<option value="button_count" <?php if (get_option("wp_fb_like_layout") == "button_count") echo 'selected'; ?>>button_count</option>
		<option value="box_count" <?php if (get_option("wp_fb_like_layout") == "box_count") echo 'selected'; ?>>box_count</option>
	</select>
	
	<h2>Show Faces?</h2>
	<div class="description">Show profile pictures below the button</div>
	<select name="wp_fb_like_show_faces" id="wp_fb_like_show_faces">
		<option value="true" <?php if (get_option("wp_fb_like_show_faces") == "true") echo 'selected'; ?>>Yes</option>
		<option value="false" <?php if (get_option("wp_fb_like_show_faces") == "false") echo 'selected'; ?>>No</option>
	</select>
	
	<h2>Verb to display</h2>
	<div class="description">The verb to display in the button. Currently only &#039;like&#039; and &#039;recommend&#039; are supported.</div>
	<select name="wp_fb_like_action" id="wp_fb_like_action">
		<option value="like" <?php if (get_option("wp_fb_like_action") == "like") echo 'selected'; ?>>like</option>
		<option value="recommend" <?php if (get_option("wp_fb_like_action") == "recommend") echo 'selected'; ?>>recommend</option>
	</select>
	
	<h2>Font</h2>
	<div class="description">The font of the plugin</div>
	<select name="wp_fb_like_font" id="wp_fb_like_font">
		<option value="arial" <?php if (get_option("wp_fb_like_font") == "arial") echo 'selected'; ?>>Arial</option>
		<option value="lucida+grande" <?php if (get_option("wp_fb_like_font") == "lucida+grande") echo 'selected'; ?>>Lucida Grande</option>
		<option value="segoe+ui" <?php if (get_option("wp_fb_like_font") == "segoe+ui") echo 'selected'; ?>>Segoe UI</option>
		<option value="tahoma" <?php if (get_option("wp_fb_like_font") == "tahoma") echo 'selected'; ?>>Tahoma</option>
		<option value="trebuchet+ms" <?php if (get_option("wp_fb_like_font") == "trebuchet+ms") echo 'selected'; ?>>Trebuchet MS</option>
		<option value="verdana" <?php if (get_option("wp_fb_like_font") == "verdana") echo 'selected'; ?>>Verdana</option>
	</select>
	
	<h2>Color Scheme</h2>
	<div class="description">The color scheme of the plugin (Default: light)</div>
	<select name="wp_fb_like_colorscheme" id="wp_fb_like_colorscheme">
		<option value="light" <?php if (get_option("wp_fb_like_colorscheme") == "light") echo 'selected'; ?>>light</option>
		<option value="dark" <?php if (get_option("wp_fb_like_colorscheme") == "dark") echo 'selected'; ?>>dark</option>
	</select>
	
	<?php
	$wp_fb_like_width = get_option("wp_fb_like_width");
	  	if($wp_fb_like_width == '') { $wp_fb_like_width = '450'; }
		
	$wp_fb_like_height = get_option("wp_fb_like_height");
	  	if($wp_fb_like_height == '') { $wp_fb_like_height = '100'; }        
	?>
	
	<h2>Width</h2>
	<div class="description">Width of the Facebook Like (Default: 400)</div>
	<input maxlength="4" size="1" type="text" name="wp_fb_like_width" id="wp_fb_like_width" value="<?= $wp_fb_like_width ?>">
	
	<h2>Height</h2>
	<div class="description">Height of the Facebook Like (Default: 100)</div>
	<input maxlength="4" size="1" type="text" name="wp_fb_like_height" id="wp_fb_like_height" value="<?= $wp_fb_like_height ?>">
	
	<h2>Add the Facebook Send button?</h2>
	<div class="description">The Send Button allows your users to easily send your content to their friends.</div>
	<select name="wp_fb_like_send" id="wp_fb_like_send">
		<?php 
		if ( !get_option("wp_fb_like_send") )
		{
		?>
		<option value="">Select...</option>
		<?php
		}
		?>
		<option value="true" <?php if (get_option("wp_fb_like_send") == "true") echo 'selected'; ?>>Yes</option>
		<option value="false" <?php if (get_option("wp_fb_like_send") == "false") echo 'selected'; ?>>No</option>
	</select>
	
	<br />
	<br />
	<div class="description">Finally, save it and enjoy your Facebook "Like" button!</div>
	<br />
	<input type="submit" value="Save Facebook Like Button" class="button-primary">
	<input type="hidden" name="wp_fb_form_submit" value="true" />
	</form>
	<br />
	<br />
	
	</fieldset>
	
	</div>
	
	<hr>
	<strong>Did this plugin help? If you like it and it is/was useful, please consider donating (Buy me a cup of coffee?) :) Many thanks!</strong></p>
	<p>
	<form action="https://www.paypal.com/cgi-bin/webscr" method="post">
	<input type="hidden" name="cmd" value="_s-xclick">
	<input type="hidden" name="hosted_button_id" value="LP7GD3EXU4Q9Q">
	<input type="image" src="https://www.paypal.com/en_US/i/btn/btn_donateCC_LG.gif" border="0" name="submit" alt="PayPal - The safer, easier way to pay online!">
	<img alt="" border="0" src="https://www.paypal.com/en_US/i/scr/pixel.gif" width="1" height="1">
	</form>
	</p>
	<br />
	<p>
	<a href="http://www.twitter.com/ajbatac"><img src="http://twitter-badges.s3.amazonaws.com/follow_me-c.png" alt="Follow ajbatac on Twitter"/></a>
	</p>
	<br />
	
	<?php
	}
}

if( !function_exists('wp_fb_like_update') )
{
	function wp_fb_like_update()
	{
		if(isset($_POST['wp_fb_form_submit']))
		{
			// update_option( $option_name, $newvalue );
			// options:
			// 1) wp_fb_like_align
			// 2) wp_fb_like_layout
			// 3) wp_fb_like_show_faces
			// 4) wp_fb_like_action
			// 5) wp_fb_like_font
			// 6) wp_fb_like_colorscheme
			// 7) wp_fb_like_width
			// 8) wp_fb_like_height
			
			update_option("wp_fb_like_align", $_POST['wp_fb_like_align']);
			update_option("wp_fb_like_layout", $_POST['wp_fb_like_layout']);
			update_option("wp_fb_like_show_faces", $_POST['wp_fb_like_show_faces']);
			update_option("wp_fb_like_action", $_POST['wp_fb_like_action']);
			update_option("wp_fb_like_font", $_POST['wp_fb_like_font']);
			update_option("wp_fb_like_colorscheme", $_POST['wp_fb_like_colorscheme']);
			update_option("wp_fb_like_width", intval($_POST['wp_fb_like_width']));
			update_option("wp_fb_like_height", intval($_POST['wp_fb_like_height']));
			// new Facebook Send Button
			update_option("wp_fb_like_send", $_POST['wp_fb_like_send']);
		}
	}
}

if( !function_exists('wp_fb_like_format') )
{
	function wp_fb_like_format( $align )
	{
		if($align == 'left') { $margin = '5px 5px 5px 0'; }
		if($align == 'none') { $margin = '5px 0'; }
		if($align == 'right') { $margin = '5px 0 5px 5px'; }
		
		$layout = get_option("wp_fb_like_layout");
		if($layout == '') { $layout = 'standard'; }
		
		$show_faces = get_option("wp_fb_like_show_faces");
		if($show_faces == '') { $show_faces = 'true'; }
		
		$action = get_option("wp_fb_like_action");
		if($action == '') { $layout = 'like'; }
		
		$font = get_option("wp_fb_like_font");
		if($font == '') { $font = 'arial'; }
		
		$colorscheme = get_option("wp_fb_like_colorscheme");
		if($colorscheme == '') { $colorscheme = 'light'; }
		
		$width = get_option("wp_fb_like_width");
		if($width == '') { $width = '450'; }
		
		$height = get_option("wp_fb_like_height");
		if($height == '') { $height = '100'; }
		
		$fbsend = get_option("wp_fb_like_send");
		if($fbsend == '') { $fbsend = 'false'; }
			
		$permalink = get_permalink();
		
		$output = '<div id="wp_fb_like_button" style="margin:'.$margin.';float:'.$align.';height:'.$height.'px;"><script src="http://connect.facebook.net/en_US/all.js#xfbml=1"></script><fb:like href="'.rawurlencode($permalink).'" send="'.$fbsend.'" layout="'.$layout.'" width="'.$width.'" show_faces="'.$show_faces.'" font="'.$font.'" action="'.$action.'" colorscheme="'.$colorscheme.'"></fb:like></div>';
		
		return $output;
	}
}

if ( !function_exists('wp_fb_like') )
{
	function wp_fb_like( $content )
	{
		if( !is_feed() && !is_page() && !is_archive() && !is_search() && !is_404() )
		{
			switch( get_option("wp_fb_like_align") )
			{
				case 'tl': // Top Left
					return wp_fb_like_format('left') . $content;
				break;
				
				case 'tr':
					return wp_fb_like_format('right') . $content;
				break;
				
				case 'bl':
					return $content . wp_fb_like_format('left');
				break;
				
				case 'br':
					return $content . wp_fb_like_format('right');
				break;
				
				case 'nt': // None (Top)
					return wp_fb_like_format('none') . $content;
				break;
				
				case 'nb': // None (Bottom)
					return $content . wp_fb_like_format('none');
				break;
				
				default:
					return $content . wp_fb_like_format('none');
			}
		}
		else
		{
			return $content;
		}
	}
}

add_filter('the_content', 'wp_fb_like');
add_action('admin_menu', 'wp_fb_like_settings');
add_action('init', 'wp_fb_like_update');
?>