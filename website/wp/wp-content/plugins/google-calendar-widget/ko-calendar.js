
var ko_calendar = function ()
{
	var result = {};

	function log(message)
	{
		// Firebug debugging console
		//console.log(message);
	}
	
	function buildDate(entry)
	{
		/* display the date/time */
		var dateString = 'All Day Event';

		/* if the event has a date & time, override the default text */
		var startTime = getStartTime(entry);
		var endTime = getEndTime(entry);

		if (startTime && endTime)
		{
			var startJSDate = startTime.getDate();
			var endJSDate = new Date(endTime.getDate());

			// If the start and end are dates (full day event)
			// then the end day is after the last day of the event (midnight that morning)
			var allDayEvent = false;
			if (startTime.isDateOnly() && endTime.isDateOnly())
			{
				endJSDate.setDate(endJSDate.getDate() - 1);

				if (endJSDate.getTime() == startJSDate.getTime()) 
				{
					// This is a one day event.
					allDayEvent = true;
				}
			}
			
			var oneDayEvent = false;
			{
				var startDay = new Date(startJSDate.getFullYear(), startJSDate.getMonth(), startJSDate.getDate());
				var endDay = new Date(endJSDate.getFullYear(), endJSDate.getMonth(), endJSDate.getDate());
				if (startDay.getTime() == endDay.getTime())
				{
					oneDayEvent = true;
				}
			}

			if (allDayEvent)
			{
				dateString = 'All Day Event';
			}
			else if (oneDayEvent)
			{
				dateString = startJSDate.toString("ddd, MMM d, yyyy");
				dateString += ', ';
				dateString += startJSDate.toString("h:mm tt");
				dateString += ' - ';
				dateString += endJSDate.toString("h:mm tt");
			}
			else
			{
				if (!startTime.isDateOnly())
				{
					dateString = startJSDate.toString("ddd, MMM d, yyyy h:mm tt");
				}
				else
				{
					dateString = startJSDate.toString("ddd, MMM d, yyyy");
				}
				dateString += ' - ';
				if (!endTime.isDateOnly())
				{
					dateString += endJSDate.toString("ddd, MMM d, yyyy h:mm tt");
				}
				else
				{
					dateString += endJSDate.toString("ddd, MMM d, yyyy");
				}
			}
		}
		var dateRow = document.createElement('div');
		dateRow.setAttribute('className','ko-calendar-entry-date-row');
		dateRow.setAttribute('class','ko-calendar-entry-date-row');

		/*dateLabel = document.createElement('div');
		dateLabel.appendChild(document.createTextNode('When: '));
		dateLabel.setAttribute('className','ko-calendar-entry-date-label');
		dateLabel.setAttribute('class','ko-calendar-entry-date-label');
		dateRow.appendChild(dateLabel);
		*/

		dateDisplay = document.createElement('div');
		//dateDisplay.appendChild(document.createTextNode(dateString));
		dateDisplay.innerHTML = dateString;
		dateDisplay.setAttribute('className','ko-calendar-entry-date-text');
		dateDisplay.setAttribute('class','ko-calendar-entry-date-text');
		dateRow.appendChild(dateDisplay);

		return dateRow;
	}

	function buildLocation(entry)
	{
		var locationDiv = document.createElement('div');
		var locationString = entry.getLocations()[0].getValueString();
		if (locationString != null)
		{
			locationDiv.appendChild(document.createTextNode(locationString));
			locationDiv.setAttribute('className','ko-calendar-entry-location-text');
			locationDiv.setAttribute('class','ko-calendar-entry-location-text');
		}
		
		return locationDiv;
	}

	function formatEventDetails(titleFormat, event)
	{
		// titleFormat contains the format string from the user.
		// event is the calendar event.
		//
		// [TITLE] will be substituted with the event title.
		// [STARTTIME] will become the start time (or "All Day" if it is an all day event).
		// [ENDTIME] will become the end time (or blank if it is an all day event).
		//
		// Any extra characters included within the [] will be inserted if the value exists.
		// That is, [ENDTIME - ] will insert " - " after the end time, if and only if there is an end time.
		//
		// If an event is an all-day event, then [STARTTIME] will be replaced with "All Day" and
		// no [ENDTIME] will defined.
		//
		// Examples
		// "[STARTTIME] - [TITLE]"				becomes "6:00AM - Test Event" or "All Day - Test Event"
		// "[STARTTIME] - [ENDTIME - ][TITLE]"	becomes "6:00AM - 9:00AM - Test Event" or "All Day - Test Event"
		// "[STARTTIME][ - ENDTIME] : [TITLE]"	becomes "6:00AM - 9:00AM : Test Event" or "All Day : Test Event"

		var startTimeString = null;
		var endTimeString = null;

		var title = event.getTitle().getText();
		var startDateTime = getStartTime(event);
		var endDateTime = getEndTime(event);
		
		if (startDateTime)
		{
			if (startDateTime.isDateOnly())
			{
				startTimeString = "All Day";
			}
			else
			{
				startTimeString = startDateTime.getDate().toString("h:mm tt");
				if (endDateTime)
				{
					endTimeString = endDateTime.getDate().toString("h:mm tt");
				}
			}
		}

		function replaceTITLE(strMatchingString, strGroup1, strGroup2)
		{
			return title ? strGroup1 + title + strGroup2 : "";
		}

		function replaceSTARTTIME(strMatchingString, strGroup1, strGroup2)
		{
			return startTimeString ? strGroup1 + startTimeString + strGroup2 : "";
		}

		function replaceENDTIME(strMatchingString, strGroup1, strGroup2)
		{
			return endTimeString ? strGroup1 + endTimeString + strGroup2 : "";
		}
		
		var output = titleFormat.replace(/\[([^\]]*)TITLE([^\]]*)\]/g, replaceTITLE);
		output = output.replace(/\[([^\]]*)STARTTIME([^\]]*)\]/g, replaceSTARTTIME);
		output = output.replace(/\[([^\]]*)ENDTIME([^\]]*)\]/g, replaceENDTIME);
		
		return output;
	}

	function getStartTime(calendarEntry)
	{
		var result = null;

		if (calendarEntry != null)
		{
			var times = calendarEntry.getTimes();
			if (times.length > 0)
			{
				result = times[0].getStartTime(); //.getDate();
			}
		}

		return result;
	}
	
	function getEndTime(calendarEntry)
	{
		var result = null;

		if (calendarEntry != null)
		{
			var times = calendarEntry.getTimes();
			if (times.length > 0)
			{
				result = times[0].getEndTime();
			}
		}

		return result;
	}

	/**
	 * Show or hide the calendar entry (as a <div> child of item) when the item is clicked.
	 * Initially this will show a div containing the content text.
	 * This could collect other information such as start/stop time
	 * and location and include it in the node.
	 *
	 * @param {div} HTML element into which we will add and remove the calendar entry details.
	 * @param {calendar entry} Google Calendar entry from which we will get the details.
	 */
	function createClickHandler(item, entry)
	{
		var entryDesc = entry.getContent().getText();
		if (entryDesc == null)
		{
			return function() {}
		}

		var descDiv = null;
		return function () 
		{
			if (descDiv == null)
			{
				descDiv = document.createElement('div');
				
				descDiv.appendChild(buildDate(entry));
				descDiv.appendChild(buildLocation(entry));
				
				bodyDiv = document.createElement('div');
				bodyDiv.setAttribute('className','ko-calendar-entry-body');
				bodyDiv.setAttribute('class','ko-calendar-entry-body');
				bodyDiv.innerHTML = Wiky.toHtml(entryDesc);
				descDiv.appendChild(bodyDiv);

				item.appendChild(descDiv);
			}
			else
			{
				// Hide all the children of this node (which should be text we added above)
				item.removeChild(descDiv);
				descDiv = null;
			}
		}
	}

	/**
	 * Callback function for the Google data JS client library to call with a feed 
	 * of events retrieved.
	 *
	 * Creates an unordered list of events in a human-readable form.  This list of
	 * events is added into a div with the id of 'outputId'.  The title for the calendar is
	 * placed in a div with the id of 'titleId'.
	 *
	 * @param {json} feedRoot is the root of the feed, containing all entries 
	 */
	function createListEvents(titleId, outputId, maxResults, autoExpand, googleService, urls, titleFormat)
	{
		function mergeFeeds(resultArray)
		{
			// This function merges the input arrays of feeds into one single feed array.
			// It is assumed that each feed is sorted by date.  We find the earliest item in
			// the lists by comparing the items at the start of each array.

			// Store all of the feed arrays in an an array so we can "shift" items off the list.
			var entries = new Array();
			for (var i=0; i < resultArray.length; i++)
			{
				if (resultArray[i])
				{
					log("Feed " + i + " has " + resultArray[i].feed.getEntries().length + " entries");
					entries.push(resultArray[i].feed.getEntries());
				}
			}
			
			log("Merging " + entries.length + " feeds into " + maxResults + " results.");
			
			// Now look at the first element in each feed to figure out which one is first.
			// Insert them in the output in chronological order.
			var output = new Array();

			while(output.length < maxResults)
			{
				var firstStartTime = null;
				var firstStartIndex = null;
				for (var i=0; i < entries.length; i++)
				{
					var startTime = getStartTime(entries[i][0]);
					if (startTime != null)
					{
						var startDate = startTime.getDate();
						if (firstStartTime == null || startDate < firstStartTime)
						{
							//log( startDate + " from feed " + i + " is before " + firstStartTime + " from feed " + firstStartIndex);
							firstStartTime = startDate;
							firstStartIndex = i;
						}
					}
				}
				if (firstStartTime != null)
				{
					// Add the entry to the output and shift it off the input.
					var uid = entries[firstStartIndex][0].getUid().getValue();
					log("Pushing " + firstStartTime + " " + uid);
					var uniqueEntry = true;

					// Remove duplicate events.  They are events with the same start time and the same Uid.
					if (output.length > 0)
					{
						var lastOutput = output[output.length-1];
						var lastStartTime = getStartTime(lastOutput);
						var lastUid = lastOutput.getUid().getValue();

						if ((lastStartTime.getDate().getTime() == firstStartTime.getTime()) && (lastUid == uid))
						{
							// This is a duplicate.
							log("Duplicate event");
							uniqueEntry = false;
						}
					}

					if (uniqueEntry)
					{
						output.push(entries[firstStartIndex].shift());
					}
					else
					{
						entries[firstStartIndex].shift();
					}
				}
				else
				{
					// No new items were found, so we must have run out.
					break;
				}
			}

			return output;
		}

		function processFinalFeed(feedRoot) {
			// var entries = feedRoot.feed.getEntries();
			var entries = feedRoot;
			var eventDiv = document.getElementById(outputId);
	
			// Remove all the children of this node (should just be the loading gif)
			while (eventDiv.childNodes.length > 0) {
				eventDiv.removeChild(eventDiv.childNodes[0]);
			}

			/* set the ko-calendar-title div with the name of the calendar */
			//document.getElementById(titleId).innerHTML = feedRoot.feed.title.$t;

			/* loop through each event in the feed */
			var prevDateString = null;
			var eventList = null;
			var len = entries.length;
			for (var i = 0; i < len; i++) {
				var entry = entries[i];
				var title = entry.getTitle().getText();
				var startDateTime = getStartTime(entry);
				var startJSDate = startDateTime ? startDateTime.getDate() : null;
				var entryLinkHref = null;
				if (entry.getHtmlLink() != null) {
					entryLinkHref = entry.getHtmlLink().getHref();
				}
				dateString = startJSDate.toString('MMM dd');

				if (dateString != prevDateString) {

					// Append the previous list of events to the widget
					if (eventList != null) {
						eventDiv.appendChild(eventList);
					}

					// Create a date div element
					var dateDiv = document.createElement('div');
					dateDiv.setAttribute('className','ko-calendar-date');
					dateDiv.setAttribute('class','ko-calendar-date');
					dateDiv.appendChild(document.createTextNode(dateString));

					// Add the date to the calendar
					eventDiv.appendChild(dateDiv);

					// Create an div to add each agenda item
					eventList = document.createElement('div');
					eventList.setAttribute('className','ko-calendar-event-list');
					eventList.setAttribute('class','ko-calendar-event-list');
					
					prevDateString = dateString;
				}

				var li = document.createElement('div');
				
				/* if we have a link to the event, create an 'a' element */
				/*
				if (entryLinkHref != null) {
					entryLink = document.createElement('a');
					entryLink.setAttribute('href', entryLinkHref);
					entryLink.appendChild(document.createTextNode(title));
					li.appendChild(entryLink);
					//li.appendChild(document.createTextNode(' - ' + dateString));
				}
				else
				*/
				{				
					// Add the title as the first thing in the list item
					// Make it an anchor so that we can set an onclick handler and
					// make it look like a clickable link
					var entryTitle = document.createElement('a');
					entryTitle.setAttribute('className','ko-calendar-entry-title');
					entryTitle.setAttribute('class','ko-calendar-entry-title');
					entryTitle.setAttribute('href', "javascript:;");

					var titleString = formatEventDetails(titleFormat, entry);
					entryTitle.appendChild(document.createTextNode(titleString));

					// Show and hide the entry text when the entryTitleDiv is clicked.
					entryTitle.onclick = createClickHandler(li, entry);

					li.appendChild(entryTitle);

					if (autoExpand)
					{
						entryTitle.onclick();
					}
				}

				eventList.appendChild(li);
			}
			
			if (eventList != null) {
				eventDiv.appendChild(eventList);
			}
		}
		
		// Keep a list of all of the queries to be sorted later.
		var sQueries = new Array();
		
		// Store the list of urls which we will be iterating through.
		var sUrls = urls;

		function callback(feedRoot)
		{
			// If the feed is not invalid then push it into a list.
			if (feedRoot)
			{
				sQueries.push(feedRoot);
			}
			
			var url = '';
			
			// Skip blank urls.
			do 
			{
				url = sUrls.pop();

			} while (url == '');
			
			if (url != undefined)
			{
				var query = new google.gdata.calendar.CalendarEventQuery(url);
				query.setOrderBy('starttime');
				query.setSortOrder('ascending');
				query.setFutureEvents(true);
				query.setSingleEvents(true);
				query.setMaxResults(maxResults);
				googleService.getEventsFeed(query, callback, handleGDError);
			}
			else
			{
				// We are done.
				// Merge the events in sQueries and apply them.				
				// For now we just insert them individually.
				// for (var i=0; i < sQueries.length; i++)
				// {
					// if (sQueries[i])
					// {
						// processFinalFeed(sQueries[i]);
					// }
				// }
				
				var finalFeed = mergeFeeds(sQueries);
				processFinalFeed(finalFeed);
			}
		}
		
		return callback;
		
	}

	/**
	 * Callback function for the Google data JS client library to call when an error
	 * occurs during the retrieval of the feed.  Details available depend partly
	 * on the web browser, but this shows a few basic examples. In the case of
	 * a privileged environment using ClientLogin authentication, there may also
	 * be an e.type attribute in some cases.
	 *
	 * @param {Error} e is an instance of an Error 
	 */
	function handleGDError(e) {
		
		// For production code, just ignore the error
		// Remove the return below for testing.
		return;
	
		//document.getElementById('jsSourceFinal').setAttribute('style', 'display:none');
		if (e instanceof Error) {
			/* alert with the error line number, file and message */
			alert('Error at line ' + e.lineNumber + ' in ' + e.fileName + '\n' + 'Message: ' + e.message);
			/* if available, output HTTP error code and status text */
			if (e.cause) {
				var status = e.cause.status;
				var statusText = e.cause.statusText;
				alert('Root cause: HTTP error ' + status + ' with status text of: ' + statusText);
			}
		} else {
			alert(e.toString());
		}
	}

	/**
	 * Uses Google data JS client library to retrieve a calendar feed from the specified
	 * URL.  The feed is controlled by several query parameters and a callback 
	 * function is called to process the feed results.
	 *
	 * @param {string} titleId is the id of the element in which the title could be written.
	 * @param {string} outputId is the id of the element in which the output is to be written.
	 * @param {string} calendarUrl is the URL for a public calendar feed
	 * @param {string} calendarUrl2 is the URL for a second public calendar feed
	 * @param {number} maxResults is the maximum number of results to be written to the output element.
	 * @param {string} titleFormat is a format string for the event details.
	 */  
	function loadCalendar(titleId, outputId, maxResults, autoExpand, calendars, titleFormat)
	{
		// Uncomment the following two lines for offline testing.
		//ko_calendar_test.testCalendar();
		//return;

		var service = new google.gdata.calendar.CalendarService('google-calendar-widget');
		var requestFunc = createListEvents(titleId, outputId, maxResults, autoExpand, service, calendars, titleFormat);

		// Calling the created callback with no parameters will start the process of downloading
		// the set of calendars pushed in with calendar.
		requestFunc();
	}

	result.loadCalendarDefered = function(titleId, outputId, maxResults, autoExpand, calendarUrl, calendarUrl2, calendarUrl3, titleFormat)
	{
		var calendars = new Array();
		calendars.push(calendarUrl);
		calendars.push(calendarUrl2);
		calendars.push(calendarUrl3);

		// google won't be defined if there was a problem loading the Google js library
		if (typeof(google) != "undefined")
		{
			google.setOnLoadCallback(function() { loadCalendar(titleId, outputId, maxResults, autoExpand, calendars, titleFormat); });
		}
	}
	
	result.init = function()
	{
		if (typeof(google) != "undefined")
		{
			// init the Google data JS client library with an error handler
			google.gdata.client.init(handleGDError);
		}
	}

	return result;

} ();

if (typeof(google) != "undefined")
{
	google.load("gdata", "2.x");
	google.setOnLoadCallback(ko_calendar.init);
}
