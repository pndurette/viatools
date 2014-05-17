import os, json

class Station:
    """A Via Rail station
    A Simple interface to the Stations data
    """
    station_json_file = os.path.join(os.path.dirname(__file__), "data", "stations_via_full.json")

    def __init__(self, code = None, name = None):
        
        if not code and not name \
        or code and name:
            raise AttributeError("Expected either 'code' or 'name' parameter for Station")
        
        with open(self.station_json_file) as json_file:
            self.stations = json.load(json_file)

        try:
            if code: self.station = self._get_station_by_code(code)
            if name: self.station = self._get_station_by_name(name)
        except Exception, e:
            raise
        
        self.code = self.station["sc"]
        self.fullname = self.station["name"] if self.station["name"] else self.station["sn"]
        self.url = self.station["url"]
        self.lat = self.station["lat"] if self.station["lat"] else None
        self.long = self.station["long"] if self.station["long"] else None
        self.name = self.station["sn"]
        self.address = self.station["address"] if self.station["address"] else None

    def _get_station_by_name(self, name):
        for s in self.stations:
            if s['sn'].lower() == name.lower(): # sn: station name
                return s
        raise StationNotFound("No station found with name '{0}'".format(name))

    def _get_station_by_code(self, code):
        for s in self.stations:
            if s['sc'].lower() == code.lower(): # sc: station code
                return s
        raise StationNotFound("No station found with code '{0}'".format(code))

    def __repr__(self):
        return "Station code: {0}".format(self.code)

class StationNotFound(Exception):
    pass
