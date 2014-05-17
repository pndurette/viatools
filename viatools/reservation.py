from viatools.station import Station
from viatools.trip import Trip, TripIncompleteError 
import logging

class Reservation:
    supported_types = ["boardingpass"]

    def __init__(self, from_type, data):
        if from_type not in self.supported_types:
            raise AttributeError("'from_type' must be one of the supported input types: {0}".format(self.supported_types))

        self.LOG = logging.getLogger(__name__)
        if from_type == "boardingpass":
            self._init_reservation_from_boardingpass(boardingpass=data)

    def _init_reservation_from_boardingpass(self, boardingpass):
        # The raw Aztec barcode data
        self.barcode_message = boardingpass.message
        
        # Attributes from the boardingpass
        self.etf = boardingpass.info["etf"]
        self.reservation_confirmation = boardingpass.info["reservation_confirmation"]        

        self.passenger_last_name = boardingpass.info["passenger_last_name"]
        self.passenger_first_name = boardingpass.info["passenger_first_name"]

        self.train_car = boardingpass.info["train_car"]
        self.train_seat = boardingpass.info["train_seat"]
        self.train_operator = boardingpass.info["train_operator"]
        self.train_luggage_rule = boardingpass.info["train_luggage_rule"] 

        # The Trip. Trip needs only the date in %Y-%m-%d string format.
        self.train_number = boardingpass.info["train_number"]
        self.depart_date = boardingpass.info["depart_time"]
        try:
            self.trip = Trip(self.train_number, self.depart_date.strftime("%Y-%m-%d")) 
        except TripIncompleteError, e:
            # The trip is missing data, don't calculate extra values
            self.trip = Trip(self.train_number, self.depart_date.strftime("%Y-%m-%d"), metadata=False)
            self.LOG.debug(str(e))
        except Exception, e:
            # There was a problem getting the trip
            self.LOG.debug(str(e))
            self.trip = None

        # The Stations
        try:
            self.depart_station = Station(code=boardingpass.info["depart_station_code"])
            self.arrival_station = Station(code=boardingpass.info["arrival_station_code"])
        except Exception, e:
            self.LOG.debug(str(e))
