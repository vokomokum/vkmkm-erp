<?php
/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * @since 4.0
 * @author Arne Franken
 *
 * Donations for settings page
 */
?>
<div id="poststuff">
  <div id="aio-favicon-topdonations" class="postbox">
    <h3><?php _e('Top donations', AIOFAVICON_TEXTDOMAIN) ?></h3>

    <div class="inside">
      <div id="Topdonations">
        <div id="Toploader" align="center"><img src="<?php echo AIOFAVICON_PLUGIN_URL ?>/images/ajax-loader.gif" alt="loading"/></div>
        <div id="Topdonationslist" style="display: none;"></div>
        <div id="Toperror" style="display: none;"><p><?php _e('Thank you for your donation.', AIOFAVICON_TEXTDOMAIN) ?></p></div>
      </div>
    </div>
  </div>
</div>
<div id="poststuff">
  <div id="aio-favicon-latestdonations" class="postbox">
    <h3><?php _e('Latest donations', AIOFAVICON_TEXTDOMAIN) ?></h3>

    <div class="inside">
      <div id="Latestdonations">
        <div id="Latestloader" align="center"><img src="<?php echo AIOFAVICON_PLUGIN_URL ?>/images/ajax-loader.gif" alt="loading"/></div>
        <div id="Latestdonationslist" style="display: none;"></div>
        <div id="Latesterror" style="display: none;"><p><?php _e('Thank you for your donation.', AIOFAVICON_TEXTDOMAIN) ?></p></div>
      </div>
    </div>
  </div>
</div>