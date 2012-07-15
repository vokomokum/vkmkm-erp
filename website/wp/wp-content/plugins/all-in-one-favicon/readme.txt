=== All In One Favicon ===
Contributors: techotronic  
Donate link: http://www.techotronic.de/donate/  
Tags: theme, favicon, admin, blog, wordpress, image, images, graphic, graphics, icon, iphone, multisite  
Requires at least: 2.8  
Tested up to: 3.3  
Stable tag: 4.0

Easily add a Favicon to your site and the WordPress admin pages. Complete with upload functionality. Supports all three Favicon types (ico,png,gif).

== Description ==

All In One Favicon adds favicons to your site and your admin pages.  
You can either use favicons you already uploaded or use the builtin upload mechanism to upload a favicon to your WordPress installation.

All three favicon types are supported - .ico, .png and .gif (may be animated)  
Also, Apple Touch Icons are supported.

See [plugin page](http://www.techotronic.de/plugins/all-in-one-favicon/) for more information, a "first steps" guide and screenshots.

**Localization**

* Bahasa Indonesia (`id_ID`) by [EKO](http://movableid.com/)
* Czech (`cs_CZ`) by [Neteyes](http://www.neteyes.cz)
* Danish (`da_DK`) by [GeorgWP](http://wordpress.blogos.dk/)
* Dutch (`nl_NL`) by Pieter Carette
* English (`en_EN`) by [Arne Franken](http://www.techotronic.de/)
* French (`fr_FR`) by Christophe Guilloux
* German (`de_DE`) by [Arne Franken](http://www.techotronic.de/)
* Italian (`it_IT`) by [Valerio Vendrame](http://www.valeriovendrame.it/)
* Polish (`pl_PL`) by [Piotr Czarnecki](http://www.facebook.com/piniu69/)
* Serbian (`sr_RS`) by [Balkanboy Media team](http://dralvaro.com/)
* Simplified Chinese (`zh_CN`) by [Tunghsiao Liu](http://sparanoid.com/)
* Spanish (`es_ES`) by [Juan Pablo Pérez Manes](mailto:jppm30@gmail.com)
* Slovak (`sk_SK`) by [Viliam Brozman](http://www.brozman.sk/blog)
* Swedish (`sv_SE`) by [Christian Nilsson](http://www.theindiaexperience.se/)

Is your native language missing?  
Translating the plugin is easy if you understand english and are fluent in another language.  
I described in the [FAQ](http://wordpress.org/extend/plugins/all-in-one-favicon/faq/) how the translation works.

== Installation ==

###Updgrading From A Previous Version###

To upgrade from a previous version of this plugin, use the built in update feature of WordPress or copy the files on top of the current installation.

###Installing The Plugin###

Either use the built in plugin installation feature of WordPress, or extract all files from the ZIP file, making sure to keep the file structure intact, and then upload it to `/wp-content/plugins/`.  
Then just visit your admin area and activate the plugin. That's it!

###Configuring The Plugin###

Go to the settings page and and upload your Favicon(s) or add the path/URL to already existing Favicon(s).

**See Also:** ["Installing Plugins" article on the WP Codex](http://codex.wordpress.org/Managing_Plugins#Installing_Plugins)

== Frequently Asked Questions ==

* When I try to upload a favicon, I get the error: "File type does not meet security guidelines. Try another.”  
  You are probably using a WordPress Multisite installation? Then you'll need to add "ico" to the allowed file types property on the "Super Admin -> Options" page.

* Internet Explorer: Why does my favicon show up in the backend but not in the frontend or not at all?  
  Internet Explorer behaves weird, not only when favicons are concerned. You may take a look at this  
  [FAQ](http://jeffcode.blogspot.com/2007/12/why-doesnt-favicon-for-my-site-appear.html).

* Why is All In One Favicon not available in my language?  
  I speak German and English fluently, but unfortunately no other language well enough to do a translation.  
  Would you like to help? Translating the plugin is easy if you understand English and are fluent in another language.

* How do I translate All In One Favicon?  
  Take a look at the WordPress site and identify [your langyage code](http://codex.wordpress.org/WordPress_in_Your_Language):  
  e.g. the language code for German is `de_DE`.

  1. download [POEdit](http://www.poedit.net/)
  2. download All In One Favicon (from your FTP server or from [WordPress.org](http://wordpress.org/extend/plugins/all-in-one-favicon/))
  3. copy the file `localization/aio-favicon-en_EN.po` and rename it. (in this case `aio-favicon-de_DE.po`)
  4. open the file with POEdit.
  5. translate all strings. Things like `{total}` or `%1$s` mean that a value will be inserted later.
  6. The string that says "English translation by Arne ...", this is where you put your name, website (or email) and your language in. ;-)
  7. (optional) Go to POEdit -> Catalog -> Settings and enter your name, email, language code etc
  8. Save the file. Now you will see two files, `aio-favicon-de_DE.po` and `aio-favicon-de_DE.mo`.
  9. Upload your files to your FTP server into the All In One Favicon directory (usually `/wp-content/plugins/all-in-one-favicon/`)
  10. When you are sure that all translations are working correctly, send the po-file to me and I will put it into the next All In One Favicon version.


* My question isn't answered here. What do I do now?  
  Feel free to open a thread at [the All In One Favicon WordPress.org forum](http://wordpress.org/tags/all-in-one-favicon?forum_id=10#postform).  
  I'll include new FAQs in every new version.

== Screenshots ==

[Please visit my site for screenshots](http://www.techotronic.de/plugins/all-in-one-favicon/).

== Changelog ==
= 4.0 (2012-03-14) =
* NEW: Simplified Chinese translation by Tunghsiao Liu
* NEW: Czech translation by Neteyes
* NEW: French translation by Christophe Guilloux
* NEW: Slovak translation by Viliam Brozman
* NEW: Serbian translation by Balkanboy Media team
* NEW: Dutch translation by Pieter Carette
* NEW: Option to not add reflective shine to Apple Touch Icons
* CHANGE: uploaded favicons can be deleted
* CHANGE: new upload buttons, uploading of favicons is now much easier
* CHANGE: uploaded favicons are now shown on settings page
* CHANGE: fixed link to Apple Touch Icon howto
* CHANGE: Major refactoring, hopefully speeds up frontend and backend rendering

= 3.1 (2011-01-16) =
* CHANGE: made plugin compatible to PHP4

= 3.0 (2011-01-15) =
* NEW: Added option to remove link from meta box.
* BUGFIX: Fixed a bug where the plugin would break WordPress 3.0 with Multisite enabled.
* NEW: Added latest donations and top donations to settings page
* NEW: Danish translation by GeorgWP
* NEW: Bahasa Indonesia translation by EKO
* NEW: Polish translation by Piotr Czarnecki
* NEW: Swedish translation by Christian Nilsson
* NEW: Italian translation by Valerio Vendrame
* NEW: Spanish translation by Juan Pablo Pérez Manes

= 2.1 (2010-06-06) =
* BUGFIX: Fixing bug where favicons would not be displayed in certain cases.

= 2.0 (2010-06-03) =
* NEW: now supports Apple Touch Icons for backend and frontend
* NEW: more links to websites containing information.

= 1.0 (2010-05-06) =
* NEW: Initial release.
