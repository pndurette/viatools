import unittest
from via.trip import Trip

class TestValidTrip(unittest.TestCase):
    def setUp(self):
        """Create train instance with valid train"""
        self.train = 79 # A valid Via Train (Toronto-Windsor)
        self.date = "2015-02-02" # Runs everyday
        expected_stations = ["TORONTO", "OAKVILLE", "ALDERSHOT", "BRANTFORD",
                            "WOODSTOCK", "INGERSOLL", "LONDON", "GLENCOE",
                            "CHATHAM", "WINDSOR"]
        self.trip = Trip(self.train, self.date)

    def test_number_of_stations(self):
        """Number of stations in trip"""
        assertEqual(self.trip.num_stations, len(self.expected_stations))

    def test_scheduled_stations(self):
        """List of stations for trip"""
        stations = []
        schedule = self.trip.get_schedule()
        for s in schedule: stations.append(upper(s.station_name))
        assert sorted(stations) == sorted(self.expected_stations)

    def test_departure_station(self):
        """The first station of the trip"""
        assertEqual(upper(self.trip.get_schedule()[0]["station_name"]), expected_stations[0]) 

    def test_arrival_station(self):
        """The last station of the trip"""
        assertEqual(upper(self.trip.get_schedule()[-1]["station_name"]), expected_stations[-1])

class TestInvalidTrip(unittest.TestCase):
    def SetUp(self):
        self.train = 999 # An invalid Via Train
        

if __name__ == '__main__':
    unittest.main()
