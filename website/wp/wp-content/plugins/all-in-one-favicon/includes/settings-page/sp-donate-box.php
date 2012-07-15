<?php
/**
 * @package Techotronic
 * @subpackage All in one Favicon
 *
 * @since 4.0
 * @author Arne Franken
 *
 * Donate-Box for settings page
 */
?>
<div id="poststuff">
  <div id="aio-favicon-donate" class="postbox">
    <h3 id="donate"><?php _e('Donate', AIOFAVICON_TEXTDOMAIN) ?></h3>

    <div class="inside">
      <p>
        <?php _e('If you would like to make a small (or large) contribution towards future development please consider making a donation.', AIOFAVICON_TEXTDOMAIN) ?>
      </p>

      <form action="https://www.paypal.com/cgi-bin/webscr" method="post">
        <input type="hidden" name="cmd" value="_xclick"/>
        <input type="hidden" name="business" value="G75G3Z6PQWXXQ"/>
        <input type="hidden" name="item_name" value="<?php _e('Techotronic Development Support', AIOFAVICON_TEXTDOMAIN); ?>"/>
        <input type="hidden" name="item_number" value="<?php echo AIOFAVICON_NAME ?>"/>
        <input type="hidden" name="no_shipping" value="0"/>
        <input type="hidden" name="no_note" value="0"/>
        <input type="hidden" name="cn" value="<?php _e("Please enter the URL you'd like me to link to in the donors lists", AIOFAVICON_TEXTDOMAIN); ?>."/>
        <input type="hidden" name="return" value="<?php $this->getReturnLocation(); ?>"/>
        <input type="hidden" name="cbt" value="<?php _e('Return to Your Dashboard', AIOFAVICON_TEXTDOMAIN); ?>"/>
        <input type="hidden" name="currency_code" value="USD"/>
        <input type="hidden" name="lc" value="US"/>
        <input type="hidden" name="bn" value="PP-DonationsBF"/>
        <label for="preset-amounts"><?php _e('Select Preset Amount', AIOFAVICON_TEXTDOMAIN); echo ": "; ?></label>
        <select name="amount" id="preset-amounts">
          <option value="10">10</option>
          <option value="20" selected>20</option>
          <option value="30">30</option>
          <option value="40">40</option>
          <option value="50">50</option>
          <option value="100">100</option>
        </select><span><?php _e('USD', AIOFAVICON_TEXTDOMAIN) ?></span>
        <br/><br/><?php _e('Or', AIOFAVICON_TEXTDOMAIN); ?><br/><br/>
        <label for="custom-amounts"><?php _e('Enter Custom Amount', AIOFAVICON_TEXTDOMAIN); echo ": "; ?></label>
        <input type="text" name="amount" size="4" id="custom-amounts"/>
        <span><?php _e('USD', AIOFAVICON_TEXTDOMAIN) ?></span>
        <br/><br/>
        <input type="submit" value="<?php _e('Submit', AIOFAVICON_TEXTDOMAIN) ?>" class="button-secondary"/>
      </form>
    </div>
  </div>
</div>