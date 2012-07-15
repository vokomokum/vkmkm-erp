<?php
/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * @since 4.0
 * @author Arne Franken
 *
 * Object that handles all actions in the WordPress frontend
 */
class AioFaviconFrontend {

  /**
   * Constructor
   *
   * @since 3.2
   * @access public
   * @access static
   * @author Arne Franken
   *
   * @param array $aioFaviconSettings user settings
   */
  //public static function AioFaviconFrontend($aioFaviconSettings) {
  function AioFaviconFrontend($aioFaviconSettings) {

    $this->aioFaviconSettings = $aioFaviconSettings;

    add_action('wp_head', array(& $this, 'aioFaviconRenderBlogHeader'));

    //only add link to meta box
    if (isset($this->aioFaviconSettings['removeLinkFromMetaBox']) && !$this->aioFaviconSettings['removeLinkFromMetaBox']) {
      add_action('wp_meta', array(& $this, 'renderMetaLink'));
    }

  }

  // AioFaviconFrontend()

  /**
   * Renders Favicon
   *
   * @since 1.0
   * @access public
   * @author Arne Franken
   */
  //public function aioFaviconRenderBlogHeader() {
  function aioFaviconRenderBlogHeader() {
    if (!empty($this->aioFaviconSettings)) {
      foreach ((array)$this->aioFaviconSettings as $type => $url) {
        if (!empty($url)) {
          if (preg_match('/frontend/i', $type)) {
            if (preg_match('/ico/i', $type)) {
?>
<link rel="shortcut icon" href="<?php echo htmlspecialchars($url)?>"/><?php

            }
            else if (preg_match('/gif/i', $type)) {
?>
<link rel="icon" href="<?php echo htmlspecialchars($url)?>" type="image/gif"/><?php

            }
            else if (preg_match('/png/i', $type)) {
?>
<link rel="icon" href="<?php echo htmlspecialchars($url)?>" type="image/png"/><?php

            }
            else if (preg_match('/apple/i', $type)) {
              if ((isset($this->aioFaviconSettings['removeReflectiveShine']) && !$this->aioFaviconSettings['removeReflectiveShine'])) {
?>
<link rel="apple-touch-icon" href="<?php echo htmlspecialchars($url)?>"/><?php
              }
              else {
?>
<link rel="apple-touch-icon-precomposed" href="<?php echo htmlspecialchars($url)?>"/><?php
              }

            }
          }
        }
      }
    }
  }

  // aioFaviconRenderBlogHeader()

  /**
   * Renders plugin link in Meta widget
   *
   * @since 1.0
   * @access public
   * @author Arne Franken
   */
  //public function renderMetaLink() {
  function renderMetaLink() {
    ?>
  <li><?php _e('Using', AIOFAVICON_TEXTDOMAIN);?>
    <a href="http://www.techotronic.de/plugins/all-in-one-favicon/" target="_blank" title="<?php echo AIOFAVICON_NAME ?>"><?php echo AIOFAVICON_NAME ?></a>
  </li>
  <?php
  }

  // renderMetaLink()
}

// AioFaviconFrontend()
?>