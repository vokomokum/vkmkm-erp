<?php
/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * @since 1.0
 * @author Arne Franken
 *
 * HTML for settings page
 */
?>
<div class="wrap">
  <div>
    <?php screen_icon(); ?>
    <h2><?php echo AIOFAVICON_NAME . ' ' . __('Settings', AIOFAVICON_TEXTDOMAIN); ?></h2>
    <br class="clear"/>

    <?php settings_fields(AIOFAVICON_SETTINGSNAME); ?>
<?php
    require_once 'settings-page/sp-left-column.php';
    require_once 'settings-page/sp-right-column.php';
    ?>
  </div>
<?php
  require_once 'settings-page/sp-footer.php';
  ?>
</div>