<?php
/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * Plugin Name: All in one Favicon
 * Plugin URI: http://www.techotronic.de/plugins/all-in-one-favicon/
 * Description: All in one Favicon management. Easily add a Favicon to your site and the WordPress admin pages. Complete with upload functionality. Supports all three Favicon types (ico,png,gif)
 * Version: 4.0
 * Author: Arne Franken
 * Author URI: http://www.techotronic.de/
 * License: GPL
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */

require_once (dirname (__FILE__) . '/includes/aio-favicon-frontend.php');
require_once (dirname (__FILE__) . '/includes/aio-favicon-backend.php');
require_once (dirname (__FILE__) . '/includes/donationloader.php');
require_once (dirname (__FILE__) . '/includes/debugger.php');

// define constants
define('AIOFAVICON_VERSION', '4.0');

if (!defined('AIOFAVICON_PLUGIN_BASENAME')) {
  //all-in-one-favicon/all-in-one-favicon.php
  define('AIOFAVICON_PLUGIN_BASENAME', plugin_basename(__FILE__));
}
if (!defined('AIOFAVICON_PLUGIN_NAME')) {
  //all-in-one-favicon
  define('AIOFAVICON_PLUGIN_NAME', trim(dirname(AIOFAVICON_PLUGIN_BASENAME), '/'));
}
if (!defined('AIOFAVICON_NAME')) {
  define('AIOFAVICON_NAME', __('All in one Favicon',AIOFAVICON_TEXTDOMAIN));
}
if (!defined('AIOFAVICON_TEXTDOMAIN')) {
  define('AIOFAVICON_TEXTDOMAIN', 'aio-favicon');
}
if (!defined('AIOFAVICON_PLUGIN_DIR')) {
  // /path/to/wordpress/wp-content/plugins/all-in-one-favicon
  define('AIOFAVICON_PLUGIN_DIR', dirname(__FILE__));
}
if (!defined('AIOFAVICON_PLUGIN_URL')) {
  // http://www.domain.com/wordpress/wp-content/plugins/all-in-one-favicon
  define('AIOFAVICON_PLUGIN_URL', WP_PLUGIN_URL . '/' . AIOFAVICON_PLUGIN_NAME);
}
if (!defined('AIOFAVICON_SETTINGSNAME')) {
  define('AIOFAVICON_SETTINGSNAME', 'aio-favicon_settings');
}
if (!defined('AIOFAVICON_USERAGENT')) {
  define('AIOFAVICON_USERAGENT', 'All-in-One Favicon V' . AIOFAVICON_VERSION . '; (' . get_bloginfo('url') . ')');
}

/**
 * Main plugin class
 *
 * @since 1.0
 * @author Arne Franken
 */
class AllInOneFavicon {

  /**
   * Plugin initialization
   *
   * @since 1.0
   * @access public
   * @author Arne Franken
   */
  //public function AllInOneFavicon(){
  function AllInOneFavicon() {
    if (!function_exists('plugins_url')) {
      return;
    }

    load_plugin_textdomain(AIOFAVICON_TEXTDOMAIN, false, '/all-in-one-favicon/localization/');

    //register method for uninstall
    if (function_exists('register_uninstall_hook')) {
      register_uninstall_hook(__FILE__, array('AllInOneFavicon', 'uninstallAioFavicon'));
    }

    // Create the settings array by merging the user's settings and the defaults
    $usersettings = (array)get_option(AIOFAVICON_SETTINGSNAME);
    $defaultArray = $this->aioFaviconDefaultSettings();
    $this->aioFaviconSettings = wp_parse_args($usersettings, $defaultArray);

    if (is_admin()) {
      $donationLoader = new AIOFaviconDonationLoader();
      new AioFaviconBackend($this->aioFaviconSettings, $this->aioFaviconDefaultSettings(),$donationLoader);
    } else if (!is_admin()) {
      new AioFaviconFrontend($this->aioFaviconSettings);
    }

  }

  // AllInOneFavicon()

  /**
   * executed during activation.
   *
   * @since 1.0
   * @access public
   * @author Arne Franken
   */
  //public function activateAioFavicon() {
  function activateAioFavicon() {
    //do nothing at the moment
  }

  // activateAioFavicon()

  //==================================================================

  /**
   * Default array of All In One Favicon settings
   *
   * @since 3.0
   * @access private
   * @static
   * @author Arne Franken
   *
   * @return array of default settings
   */
  //private function aioFaviconDefaultSettings() {
  function aioFaviconDefaultSettings() {

    // Create and return array of default settings
    return array(
      'aioFaviconVersion' => AIOFAVICON_VERSION,
      'debugMode' => false,
      'removeReflectiveShine' => false,
      'removeLinkFromMetaBox' => true
    );
  }

  // aioFaviconDefaultSettings()

  /**
   * Delete jQuery Tinytips settings
   *
   * handles deletion from WordPress database
   *
   * @since 1.3
   * @access private
   * @author Arne Franken
   */
  //private function uninstallAioFavicon() {
  function uninstallAioFavicon() {
    delete_option(AIOFAVICON_SETTINGSNAME);
  }

  // uninstallAioFavicon()

}
//=================================================================================
?><?php
/**
 * Workaround for PHP4
 * initialize plugin, call constructor
 *
 * @since 1.0
 * @access public
 * @author Arne Franken
 */
function initAioFavicon() {
  new AllInOneFavicon();
}

//initAioFavicon()

// add AllInOneFavicon() to WordPress initialization
add_action('init', 'initAioFavicon', 7);

//static call to constructor is only possible if constructor is 'public static', therefore not PHP4 compatible:
//add_action('init', array('AllInOneFavicon','AllInOneFavicon'), 7);

// register method for activation
register_activation_hook(__FILE__, array('AllInOneFavicon', 'activateAioFavicon'));
?>