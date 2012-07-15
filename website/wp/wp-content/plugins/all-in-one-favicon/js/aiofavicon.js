/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * @since 3.2
 * @author Arne Franken
 *
 * AioFavicon Javascript
 */

/**
 * call favicon loader on page load.
 */
jQuery(document).ready(function() {
    faviconLoader();
});

/**
 * faviconLoader
 * 
 * load all uploaded favicons
 */
(function(jQuery) {
    faviconLoader = function() {
        jQuery.each(Aiofavicon, function(key, value) {
            var $imgTag = "<img src=\"" + value  + "\" />";
            var selector = "#"+key+"-favicon";
            jQuery(selector).empty().html($imgTag).fadeIn();
        });
    }
})(jQuery);

// faviconLoader()