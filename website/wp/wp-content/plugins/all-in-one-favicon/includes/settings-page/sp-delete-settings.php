<?php
/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * @since 4.0
 * @author Arne Franken
 *
 * Delete Settings for settings page
 */
?>
<div id="poststuff">
  <div id="aio-favicon-delete_settings" class="postbox">
    <h3 id="delete_options"><?php _e('Delete Settings', AIOFAVICON_TEXTDOMAIN) ?></h3>

    <div class="inside">
      <p><?php _e('Check the box and click this button to delete settings of this plugin.', AIOFAVICON_TEXTDOMAIN); ?></p>

      <form name="delete_settings" method="post" action="admin-post.php">
        <?php if (function_exists('wp_nonce_field') === true) wp_nonce_field('aio-favicon-delete_settings-form'); ?>
        <p id="submitbutton">
          <input type="hidden" name="action" value="aioFaviconDeleteSettings"/>
          <input type="submit" name="aioFaviconDeleteSettings" value="<?php _e('Delete Settings', AIOFAVICON_TEXTDOMAIN); ?> &raquo;" class="button-secondary"/>
          <input type="checkbox" name="delete_settings-true"/>
        </p>
      </form>
    </div>
  </div>
</div>