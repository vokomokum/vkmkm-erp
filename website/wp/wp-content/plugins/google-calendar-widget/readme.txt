=== Google Calendar Widget ===
Contributors: poco
Donate link: http://notions.okuda.ca
Tags: google, calendar, widget
Requires at least: 2.8
Tested up to: 3.2.1
Stable tag: trunk

This plugin installs a sidebar widget that can show the upcoming events from a Google Calendar feed.

== Description ==

This plugin installs a widget for showing a Google Calendar agenda on the sidebar.
Once installed it adds a sidebar widget called 'Google Calendar' that may be dragged into your sidebar.
Each widget can be configured with a URL of the calendar feed, a title, and the number of agenda items to show.

The calendar feed is the URL you get when clicking on the XML icon next to 'Calendar Address:' in the Google Calendar settings. [See the full instructions here](http://www.google.com/support/calendar/bin/answer.py?hl=en&answer=37103).

Multiple widgets can be used on the same page and each one can reference a different feed.

See also [http://notions.okuda.ca/wordpress-plugins/google-calendar-widget/](http://notions.okuda.ca/wordpress-plugins/google-calendar-widget/)

== Installation ==

1. Upload all the files to the `/wp-content/plugins/google-calendar-widget` directory
1. Activate the plugin through the 'Plugins' menu in WordPress
1. Drag the 'Google Calendar' widget to your sidebar
1. Fill out the settings for each instance in your sidebar.  You can ge the calendar URL from your Google calendar settings, just be sure to change the "/basic" to "/full".

For example:

* Calendar Title : Google Developer Calendar 
* Calendar URL 1: http://www.google.com/calendar/feeds/developer-calendar@google.com/public/full 
* Calendar URL 2: http://www.google.com/calendar/feeds/insert your feed here/public/full 
* Calendar URL 3: <blank>
* Event Title Format: [STARTTIME -][TITLE]
* Maximum Results: 6 

== Frequently Asked Questions ==

= Where do I get the calendar feed? =

See the [Google Calendar Support Page](http://www.google.com/support/calendar/bin/answer.py?hl=en&answer=37103).  Just don't forget to change the "/basic" to "/full".

= How do I change the language of the dates =

You can [download localized versions of date.js from here](http://code.google.com/p/datejs/downloads/list).  Find the correct language version in the "build" folder of the zip file, and replace the date.js in the plugin folder.

= How can I change the format of the dates and times =

The date and time is formatted using the date.js library.
Look for code like the following two lines in ko-calendar.js and change the format argument to match the format you want.

	startJSDate.toString("ddd, MMM d, yyyy h:mm tt")
	dateString = startJSDate.toString('MMM dd');

The formatting represents how the information will look on the page "MMM" translates to the abbreviated name of the month.
 
Take a look at the documentation for how you can change that formatting string to match what you want.
http://code.google.com/p/datejs/wiki/FormatSpecifiers
 
For example, you can change the following

	dateString = startJSDate.toString('MMM dd');

to this

    dateString = startJSDate.toString('dd.MM.yyyy');

to change the agenda item "Jan 2" to "02.01.2009"

= Why is HTML in my calendar entry getting mangled =

The plugin uses the [wiky.js library](http://goessner.net/articles/wiky/) that generates HTML from a wiki-like markup language.
It expects that the calendar item descriptions are marked up using that format.  This is done to simplify the formatting for users who are already familiar with wiki markup and make the calendar entries easier to read when not interpreted.

If you wish to remove this transformation simply replace the following line in ko-calendar.js

	bodyDiv.innerHTML = Wiky.toHtml(entryDesc);

With

	bodyDiv.innerHTML = entryDesc;

= How do I insert this in a theme without a sidebar =

You can insert the widget into a template directly, without adding it to a sidebar, by inserting php code directly into your theme.

	<?php
	the_widget("WP_Widget_KO_Calendar",
		array(
			'title' => 'Calendar Title',
			'url' => 'http://www.google.com/calendar/feeds/yourcalendar@gmail.com/public/full',
		),
		array('before_widget' => '<div class="calendarwidget">',
			'after_widget' => '</div>',
			'before_title' => '<div class="calendartitle">',
			'after_title' => '</div>'
	));
	?>

You can configure it with the same options available in the widget, as the second parameter to the_widget.

* 'title' will appear at the top of the calendar.
* 'url' is the url of your Google Calendar (see the Installation instructions for more details)
* 'url2', and 'url3' allow you to specify multiple calendars to be shown in the one view.
* 'maxresults' restricts the number of events to show.  The default is 5.
* 'titleformat' is the format of the event titles.  The default is "STARTTIME - TITLE".
* If 'autoexpand' is TRUE, the calendar will show the details of each event by default.  The default is FALSE.

The third parameter lists the standard widget options.  See the wordpress Widget documentation for more details.
They can each be blank (i.e. 'before_widget'=>'') or contain whatever formatting you desire to be inserted in the flow.

= How do I customize the event titles? =

The "Event Title Format" option for each calendar allows you to format how you wish the calendar events to appear in the event list.
The default format is "[STARTTIME - ][TITLE]" so, for example, an event that starts at 6:00pm would called "Birthday Party" would appear as "6:00PM - Birthday Party".

*	[TITLE] will be substituted with the event title.
*	[STARTTIME] will become the start time (or "All Day" if it is an all day event).
*	[ENDTIME] will become the end time (or blank if it is an all day event).

Any extra characters included within the [] will be inserted if the value exists.
That is, [ENDTIME - ] will insert " - " after the end time, if and only if there is an end time.

If an event is an all-day event, then [STARTTIME] will be replaced with "All Day" and no [ENDTIME] will defined.

Examples

*	"[STARTTIME] - [TITLE]"				becomes "6:00AM - Test Event" or "All Day - Test Event"
*	"[STARTTIME] - [ENDTIME - ][TITLE]"	becomes "6:00AM - 9:00AM - Test Event" or "All Day - Test Event"
*	"[STARTTIME][ - ENDTIME] : [TITLE]"	becomes "6:00AM - 9:00AM : Test Event" or "All Day : Test Event"

= Can I use this code outside of Wordpress in an HTML page? =

Yes!

I have included an example with the plugin in "examples/stand_alone.html" that shows an example using the plugin code.
Each element is tagged so it should be flexible for styling; see the existing stylesheet for examples.

== Screenshots ==

1. The widget showing the upcoming Google developer calendar events on the sidebar of the default Wordpress theme.

== Changelog ==

= 1.0 =
* Initial release

= 1.1 =
* Added ability to support multiple feeds (up to 3) from one widget.

= 1.2 =
* Added "Expand Entries by Default" checkbox to widget settings to auto expand all the calendar entries.  If this is checked, the each calendar item will open as though they were clicked by default.

= 1.3 =
* Remove duplicate events when showing multiple calendars that have been invited to the same event.  If you create an event in calendar A and invite calendar B as a guest, then load them as "url" and "url2", the event should only appear once.
* Added "Event Title Format" option to specify a format string to customize event titles (with or without the time).
* Added error checking for errors that can occur when used offline (for test servers).
* Changed the layout of the widget settings to increase the size of the text boxes.

= 1.3.1 =
* Fixed problem where spaces around the loading GIF caused it to not stop when the calendar loads.

= 1.3.2 =
* Optimizations:
** Removed the version number from the Google jsapi so as to allow for more cache hits with other users.
** Removed the script includes from the admin interface.
