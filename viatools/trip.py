import requests, re
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import logging, timeit

"""
A VIA Rail Canada trip

Table (ex.):
http://reservia.viarail.ca/tsi/GetTrainStatus.aspx?TsiCCode=VIA&TsiTrainNumber=79&ArrivalDate=2014-03-22
  +------------+-----+-----------+-----------+--------+
  | Station          | Scheduled | Estimated | Actual |
  +------------+-----+-----------+-----------+--------+
  | TORONTO    | Dep:|   19:05   |           | 19:05  |
  +------------+-----+-----------+-----------+--------+
  | OAKVILLE   | Arr:|   19:26   |           | 19:31  |
  |            +-----+-----------+-----------+--------+
  |            | Dep:|   19:28   |           | 19:33  |
  +------------+-----+-----------+-----------+--------+
    ...
  +------------+-----+-----------+-----------+--------+
  | CHATHAM    | Arr:|   22:17   |   22:20   |        |
  |            +-----+-----------+-----------+--------+
  |            | Dep:|   22:19   |   22:22   |        |
  +------------+-----+-----------+-----------+--------+
  | WINDSOR    | Arr:|   23:10   |   23:13   |        |
  +------------+-----+-----------+-----------+--------+

Notes:
   The first station has no arrival times (all arrivals set to None)
   The last station has no departure times (all departures set to None)
   'estimated' and 'actual' time are mutualy exclusive, for each of arrival and departure

The times tells us the status:
   If the first station has depart_time_actual set, the trip has departed;
   If a station has arrival_time_estimated set, the train has not reached this station
   If a station has arrival_time_actual set, the train has reached this station
   If a station has arrival_time_actual set but not departure_time_actual set, the train is at that station
   If the last station has arrival_time_actual set, the trip has concluded
"""

class Trip:
    """A Via Rail Trip
    Time information is only available for the Windsor-Quebec City Corridor"""
    train_schedule_url = "http://reservia.viarail.ca/tsi/GetTrainStatus.aspx"

    def __init__(self, train, date, metadata = True):
        """Args:
            train: Via train number integer
            date: Arrival date string in format "YYYY-MM-DD"
            metadata: Calculate and infer additional properties
                      Set to False when a trip is imcomplete or when only the scheduled
                      times and list of stations are required
        """
        # TODO validate input
        self.LOG = logging.getLogger(__name__)
        
        self.train = train
        self.date = date
        self.metadata = metadata

        # Main list of station dicts, such as:
        # [{"station": "TORONTO",
        # "arrival_time_scheduled": None, "arrival_time_estimated": None, "arrival_time_actual": None,
        # "depart_time_scheduled": "19:05", "depart_time_estimated": None, "depart_time_actual": "19:50"}]
        self.schedule = []

        # Trip properties        
        self.departed = False
        self.arrived = False
        self.num_stations = 0
        self.start_station_name = None
        self.end_station_name = None
        self.current_station = None
        self.current_station_name = None
        self.late = False
        self.early = False
        self.schedule_timedelta = None
        self.time_elapsed = None
        self.time_left = None

        # Fill in blanks
        self.update()

    def update(self):
        """Requests a trip update from Via. Call to refresh the trip"""
        try:
            soup = self._fetch_raw_train_status() # The raw
            self.schedule = self._create_trip_struct(soup) # The struct
           
            if self.metadata:
                self._generate_properties(self.schedule) # Generate has_arrived, has_departed, ...
                self.schedule = self._adjust_day_difference(self.schedule) # Adjust days if necessary
                self._calculate_time_deltas(self.schedule) # Calculate the misc. times (left, since departure, late, early)
        except TripNotFoundError, e:
            raise
        except Exception, e:
            raise

    def _create_trip_struct(self, soup):
        """Creates a trip list struct by parsing the train status html page
        Args:
            soup: the BeautifulSoup of the train status page
        Returns:
            The main schedule structure
        """
        if self.LOG.getEffectiveLevel() is logging.DEBUG: start = timeit.default_timer()
        trip_schedule = []

        # Get the <table> under <div id='tsicontent'>
        rows = soup.find(id="tsicontent").find("table").contents # The <tr>s under main table (one per station)

        # The number of stations of this trip equals the number of <tr> minus 3
        # (the top caption (first row), the bottom caption (last row) and the column titles (second row) are <tr>s)
        station_rows = rows[2:-1] # Skip row 0, 1 and last

        # Departure station
        station_position = 0 # The position on the (0-index)
        tds = station_rows[0].contents # The <td>s (see table above)
        
        first_station = { "station_name": tds[0].text.encode('utf8'),
                    "station_position" : station_position, 
                    "arrival_time_scheduled": None,
                    "arrival_time_estimated": None,
                    "arrival_time_actual":    None,
                    "depart_time_scheduled":  self._datetime(self.date, tds[2].text),
                    "depart_time_estimated":  self._datetime(self.date, tds[3].text),
                    "depart_time_actual":     self._datetime(self.date, tds[4].text) }
        trip_schedule.append(first_station)

        # Intermediate stations
        station_position += 1
        for row in station_rows[1:-1]: # All but first and last
            # The <td>s (see table above).
            # Each time column [scheduled (col 2), Estimated (col 3), Actual (col 4)] contains another table:
            # It contains 2 <tr><td></td></tr> containing the arrival (0) and departure (1) time, respectively.
            tds = row.contents

            # First <td> is arrival; second is departure
            scheduled = tds[2].find_all("td")  
            estimated = tds[3].find_all("td")
            actual = tds[4].find_all("td")
 
            this_station = { "station_name": tds[0].text.encode('utf8'),
                    "station_position" : station_position,
                    "arrival_time_scheduled": self._datetime(self.date, scheduled[0].text),
                    "arrival_time_estimated": self._datetime(self.date, estimated[0].text),
                    "arrival_time_actual":    self._datetime(self.date, actual[0].text),
                    "depart_time_scheduled":  self._datetime(self.date, scheduled[1].text),
                    "depart_time_estimated":  self._datetime(self.date, estimated[1].text),
                    "depart_time_actual":     self._datetime(self.date, actual[1].text) }
            trip_schedule.append(this_station)
            station_position += 1 

        # Arrival station
        tds = station_rows[-1].contents # The <td>s (see table above)
        last_station = { "station_name": tds[0].text.encode('utf8'),
                    "station_position" : station_position,
                    "arrival_time_scheduled": self._datetime(self.date, tds[2].text),
                    "arrival_time_estimated": self._datetime(self.date, tds[3].text),
                    "arrival_time_actual":    self._datetime(self.date, tds[4].text),
                    "depart_time_scheduled":  None,
                    "depart_time_estimated":  None,
                    "depart_time_actual":     None }
        trip_schedule.append(last_station)

        if self.LOG.getEffectiveLevel() is logging.DEBUG:
            stop = timeit.default_timer()
            self.LOG.debug("_create_trip_dict: %ss" % (stop - start))
        
        return trip_schedule

    def _adjust_day_difference(self, schedule):
        """Scans the trip struct for each time column (scheduled, estimated, actual),
        Adds a day if necessary (if next time is smaller, it's the next day)
        When we compare two times, we add an arbritary extensions (ex: 10 minutes)
        to the second time because in some cases (at a station), the arrival time can happen 1min
        after the departure time.
        
        Args:
            schedule: a schedule struct
        Returns:
            a time updated schedule struct
        """
        time_type = ["scheduled", "estimated", "actual"]

        for i, obj in enumerate(self.schedule):
            for t in time_type:
                # Same station: between Arr. and Dep.
                if schedule[i]["arrival_time_" + t] and schedule[i]["depart_time_" + t] \
                and schedule[i]["depart_time_" + t] + timedelta(minutes=10) < schedule[i]["arrival_time_" + t]:
                    schedule[i]["depart_time_" + t] += timedelta(days=1)
 
                # Interstation: between Dep. and Arr.
                if schedule[i]["depart_time_" + t] and schedule[i+1]["arrival_time_" + t] \
                and schedule[i+1]["arrival_time_" + t] < schedule[i]["depart_time_" + t]:
                    schedule[i+1]["arrival_time_" + t] += timedelta(days=1)
        return schedule

    def _generate_properties(self, schedule):
        """Generate properties of this trip
        Args:
            schedule: a schedule struct
        Returns:
            Nothing. The class attributes are changed
        """
        self.departed = True if schedule[0]["depart_time_actual"] else False
        self.arrived = True if schedule[-1]["arrival_time_actual"] else False
        
        self.num_stations = len(self.schedule)
        self.start_station_name = schedule[0]["station_name"]
        self.end_station_name = schedule[-1]["station_name"]
        self.current_station = self._get_current_train_location(schedule)
        self.current_station_name = self.current_station["station_name"]
        
    def _calculate_time_deltas(self, schedule):
        """Calculate the time lenghts of the trip"""
        # Time difference with scheduled time (scheduled vs. actual)
        # The trip has not yet departed OR is departed but not reached the first station
        if schedule[0]["depart_time_scheduled"] and not schedule[0]["depart_time_actual"] or not schedule[1]["arrival_time_actual"]:
            self.late = True if schedule[0]["depart_time_estimated"] and schedule[0]["depart_time_estimated"] > schedule[0]["depart_time_scheduled"] else False
            self.early = True if schedule[0]["depart_time_estimated"] and schedule[0]["depart_time_estimated"] < schedule[0]["depart_time_scheduled"] else False
            if self.late:
                self.schedule_timedelta = schedule[0]["arrival_time_estimated"] - schedule[-1]["arrival_time_scheduled"]
            elif self.early:
                self.schedule_timedelta = schedule[0]["arrival_time_scheduled"] - schedule[-1]["arrival_time_estimated"]
            else: self.schedule_timedelta = timedelta()
            self.time_elapsed = timedelta()
            self.time_left = schedule[-1]["arrival_time_scheduled"] - schedule[0]["depart_time_scheduled"]

        # Trip has concluded
        elif schedule[-1]["arrival_time_actual"]:
            self.late = True if schedule[-1]["arrival_time_actual"] > schedule[-1]["arrival_time_scheduled"] else False
            self.early = True if schedule[-1]["arrival_time_actual"] < schedule[-1]["arrival_time_scheduled"] else False
            if self.late:
                self.schedule_timedelta = schedule[-1]["arrival_time_actual"] - schedule[-1]["arrival_time_scheduled"]
            elif self.early:
                self.schedule_timedelta = schedule[-1]["arrival_time_scheduled"] - schedule[-1]["arrival_time_actual"]
            else: self.schedule_timedelta = timedelta()
            self.time_elapsed = schedule[-1]["arrival_time_actual"] - schedule[0]["depart_time_actual"]
            self.time_left = timedelta()
        
        # Trip is in progress.
        # Current station and reference time (either current station's arrival or departure time)
        else:
            if self.current_station["arrival_time_actual"]:
                reference_time = self.current_station["arrival_time_actual"]
                self.late = True if self.current_station["arrival_time_actual"] > self.current_station["arrival_time_scheduled"] else False
                self.early = True if self.current_station["arrival_time_actual"] < self.current_station["arrival_time_scheduled"] else False
                if self.late:
                    self.schedule_timedelta = self.current_station["arrival_time_actual"] - self.current_station["arrival_time_scheduled"]
                elif self.early:
                    self.schedule_timedelta = self.current_station["arrival_time_scheduled"] - self.current_station["arrival_time_actual"]
                else: self.schedule_timedelta = timedelta()    
            else: # departure_time_actual
                reference_time = self.current_station["depart_time_actual"]
                self.late = True if self.current_station["arrival_time_actual"] > self.current_station["arrival_time_scheduled"] else False
                self.early = True if self.current_station["arrival_time_actual"] < self.current_station["arrival_time_scheduled"] else False
                if self.late:
                    self.schedule_timedelta = self.current_station["arrival_time_actual"] - self.current_station["arrival_time_scheduled"]
                elif self.early:
                    self.schedule_timedelta = self.current_station["arrival_time_scheduled"] - self.current_station["arrival_time_actual"]
                else: self.schedule_timedelta = timedelta()

            self.schedule_timedelta = reference_time - self.current_station["arrival_time_scheduled"]
            self.time_elapsed = reference_time - schedule[0]["depart_time_actual"]
            self.time_left = schedule[-1]["arrival_time_estimated"] - reference_time

    def _get_current_train_location(self, schedule):
        """Finds which station the train was last seen.
        Args:
            schedule: a schedule struct
        Returns:
            a station struct representing the station dict where the train was last seen
        """
        # The train is at the start or the end of the trip
        if not schedule[0]["depart_time_actual"]: return schedule[0]
        if schedule[-1]["arrival_time_actual"]: return schedule[-1]

        # The train is elsewhere
        for i, obj in enumerate(schedule):
            # If the next station has no 'arrival_time_actual', the train is between current and next
            if not schedule[i+1]["arrival_time_actual"]:
                return schedule[i]

            # If a station has 'arrival_time_actual' but not 'depart_time_actual', the train is at that station
            if schedule[i]["arrival_time_actual"] and not schedule[i]["depart_time_actual"]:
                return schedule[i]

    def _fetch_raw_train_status(self):
        """Fetch train html page into a Soup"""
        start = timeit.default_timer()
        params = { "TsiCCode" : "VIA",
                   "TsiTrainNumber" : self.train,
                   "ArrivalDate": self.date }
        r = requests.get(url=self.train_schedule_url, params=params)
        soup = BeautifulSoup(r.text)

        # If there's no div of id='tsicontent' we assume the train was not found.
        # Possible reasons:
        # 1. Invalid train number;
        # 2. Invalid trip (train number + arrival time combination);
        # 3. At least one station of this trip is outside of the Windsor-Quebec City Corridor.
        # Some trains pages don't have incomplete information. In this case, a "Currently, further
        # information is unavailable" message is found on the page. We raise an exception.

        if not soup.find(id="tsicontent"):
            error_msg = ("Invalid train number, trip (train doesn't run on the date specified), " 
            "is too far in the past or the future, or one of the station of this trip is outside of the "
            "Windsor-Quebec City Corridor")
            raise TripNotFoundError(error_msg)
        elif soup.find_all(text=re.compile("Currently, further information is unavailable")):
            error_msg = "The trip was found but is missing data"
            raise TripIncompleteError(error_msg)
        
        stop = timeit.default_timer()
        self.LOG.debug("_fetch_raw_train_status: %ss" % (stop - start)) 
        return soup

    def _datetime(self, date_str, time_str):
        """Create a datetime from a date and time
        Args:
            date_str: a date string, YYYY-MM-DD format.
            time_str: a time string, HH:MM format.
        Returns a datetime or None if time date or time are missing or invalid.
        """ 
        # Date
        date_str = date_str.strip()
        date_pattern = "^([0-9]{4})-(0[1-9]|1[012])-(0[1-9]|[12]\d|3[01])$"
        if not re.match(date_pattern, date_str): return None

        # Time
        time_str = time_str.strip()
        time_pattern = "^([0-9]|0[0-9]|1[0-9]|2[0-3]):[0-5][0-9]$"
        if not re.match(time_pattern, time_str): return None

        return datetime.strptime("{0} {1}".format(date_str, time_str), "%Y-%m-%d %H:%M") 

    def pretty_print(self):
        """Pretty prints the trip schedule struct"""
        from pprint import pprint
        pprint(self.schedule, indent=4)

    def table(self):
        """Returns a multiline string of a formatted trip timetable"""
        import prettytable
        table = prettytable.PrettyTable(["Station", "", "Scheduled", "Estimated", "Actual"])
        table.align = "l"
        for s in self.schedule:
            table.add_row([s["station_name"], "Arr:", s["arrival_time_scheduled"], s["arrival_time_estimated"], s["arrival_time_actual"]])
            table.add_row(["",                "Dep:", s["depart_time_scheduled"],  s["depart_time_estimated"],  s["depart_time_actual"]])
        return str(table)

    def __repr__(self):
        """Recap. and current timetable of the trip"""
        train_info = "Trip: Train #{0} ({1} to {2}) on {3}:".format(self.train, self.start_station_name, self.end_station_name, self.date)
        
        if self.departed: departure_info = "The train has left {0} at {1}.".format(self.start_station_name, self.schedule[0]["depart_time_actual"])
        else: departure_info = "The train has not left {0} yet. It is scheduled to leave on {1}".format(self.start_station_name, self.schedule[0]["depart_time_scheduled"])
       
        if self.arrived: arrival_info = "The train has arrived in {0} at {1}".format(self.end_station_name, self.schedule[-1]["arrival_time_actual"])
        elif self.departed: arrival_info = "The train is estimated to arrive in {0} at {1}".format(self.end_station_name, self.schedule[-1]["arrival_time_estimated"])
        else: arrival_info = "The train is scheduled to arrive in {0} at {1}".format(self.end_station_name, self.schedule[-1]["arrival_time_scheduled"])

        location_info = "The train was last seen in {0}.".format(self.current_station_name)

        if self.late: lateness_info = "late"
        elif self.early: lateness_info = "early"
        else: lateness_info = "on time"

        print "Time difference with schedule: {0} ({1}).".format(self.schedule_timedelta, lateness_info)
        print "Time Elapsed", self.time_elapsed
        print "Time Left", self.time_left

        return train_info + "\n" + departure_info + "\n" + arrival_info + "\n" + location_info + "\n" + self.table()

class TripNotFoundError(Exception):
    pass

class TripIncompleteError(Exception):
    pass

if __name__ == "__main__":
    pass
