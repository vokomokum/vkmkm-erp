
function createCalendarTest()
{
	function CalendarEntry(date, title, body)
	{
		this.getTitle = function ()
		{
			var result = new Object;
			result.getText = function ()
			{
				return title;
			};
			
			return result;
		};
		
		this.getTimes = function ()
		{
			function CalendarTime()
			{
				this.getDate = function()
				{
					return date;
				};
			};

			var timelist = new Array(1);
			timelist[0] = new Object();
			timelist[0].getStartTime = function ()
			{
				return new CalendarTime();
			};
			
			return timelist;
		}
		
		this.getHtmlLink = function ()
		{
			return null;
		};
		
		this.getContent = function ()
		{
			function CalendarContent()
			{
				this.getText = function ()
				{
					return body;
				};
			};
			
			return new CalendarContent();
		}
		
	}

	var result = new Object();
	result.testCalendar = function()
	{
		var feedRoot = {};
		feedRoot.feed = {};
		feedRoot.feed.title = {};
		feedRoot.feed.title.$t = "Calendar Title";
		feedRoot.feed.getEntries = function()
		{
			var result = new Array(2);
			result[0] = new CalendarEntry(new Date(2009, 12, 20), "Nancy Green Free Ski Day", "This is the Nancy Green free ski day where you can come and try it out");
			result[1] = new CalendarEntry(new Date(2009, 12, 20), "No Description");
			result[2] = new CalendarEntry(new Date(2009, 12, 21), "Christmas Camp", "The Nancy Green Christmas camp is open to all K-Stars and those Nancy Green Athletes who have paid the registration.");
			return result;
		};
		
		listEvents(feedRoot);
	}
	
	return result;
};

ko_calendar_test = createCalendarTest();
