import os, subprocess, logging, timeit
from datetime import datetime
from .station import Station

class BoardingPass:
    """Representation of a Via Rail boarding pass"""
    supported_types = ["barcode"]

    def __init__(self, from_type, data):
        if from_type not in self.supported_types:        
            raise AttributeError("'from_type' must be one of the supported input types: {0}".format(self.supported_types))

        self.LOG = logging.getLogger(__name__)
        if from_type == "barcode":
            self._process_barcode(image=data)

    def _process_barcode(self, image):
        try:
            decoded = self._read_barcode(image)
            #decoded = "0507201327229Durette                       4   8D MTRLWDONVIA79  201403311905Pierre Nicolas      P1YSADTZZG41720130705225402C2 NB "
        except Exception, e:
            raise

        # Validate lenght
        if len(decoded) != 130:
            error_msg = "Incorrect decoded string length. Excepted 130."
            raise BarcodeFormatError(error_msg) 

        # Split fields
        """
        Fields of a standard barcode string (example):

        0507201327229Durette                       4   8D MTRLTRTOVIA69  
        |------------|----------------------------|---|--|---|---|--|---| ...
          \_ ETF       \_ Last name      Train car_/    | |    |  |   \_Train number   
                                            Train seat_/  |    |  \_Train Operator
                                        Departure Station_/    \ Arrival Station
       
        ...  201308111830Pierre Nicolas      P1YSADTZZG41720130705225402C2 NB
        ... ------------|------------------|------|-----|-------------|-----|
               \_Departure time  |    Unknown_/   |        |            \_Luggage rule
                                 \_First name     |         \_Reservation time
                                                  \_Reservation confirmation
        """

        # Construct boarding pass fields
        self.raw_info = {
            "etf" : decoded[0:13],
            "passenger_last_name" : decoded[13:43],
            "train_car" : decoded[43:45],
            "train_seat" : decoded[47:50],
            "depart_station_code" : decoded[50:54],
            "arrival_station_code" : decoded[54:58],
            "train_operator" : decoded[58:61],
            "train_number" : decoded[61:65],
            "depart_time" : decoded[65:77],
            "passenger_first_name" : decoded[77:97],
            "unknown" : decoded[97:104],
            "reservation_confirmation" : decoded[104:110],
            "reservation_time" : decoded[110:124],
            "train_luggage_rule" : decoded[124:136]
        }

        # We keep the raw to reconstruct the barcode
        info = dict(self.raw_info)

        # Datetimes. ex: 201308111830 (depart_time) and 20130811183000 (reservation time)
        info["depart_time"] = datetime.strptime(info["depart_time"], "%Y%m%d%H%M")
        info["reservation_time"] = datetime.strptime(info["reservation_time"], "%Y%m%d%H%M%S")

        # Integers
        info["train_car"] = int(info["train_car"].strip()) if info["train_car"].strip() else None
        info["train_number"] = int(info["train_number"].strip())

        # Strings
        info["passenger_first_name"] = info["passenger_first_name"].strip().title() 
        info["passenger_last_name"] = info["passenger_last_name"].strip().title()
        info["train_luggage_rule"] = info["train_luggage_rule"].strip()
        info["train_seat"] = info["train_seat"].strip() if info["train_seat"].strip() else None

        # Extra validation
        try:
            depart = Station(code=info["depart_station_code"])
            arrival = Station(code=info["arrival_station_code"])
        except Exception, e:
            raise BarcodeFormatError(str(e))

        self.message = decoded
        self.info = info

    def _read_barcode(self, image):
        """Returns the decoded string of an Aztec barcode.
        A wrapper for ZXing's com.google.zxing.client.j2se.CommandLineRunner:
        java -cp javase-3.0.0.jar:core-3.0.0.jar com.google.zxing.client.j2se.CommandLineRunner <image> --possibleFormats=AZTEC
        """
        if self.LOG.getEffectiveLevel() is logging.DEBUG:
            start = timeit.default_timer()
        
        runner = "com.google.zxing.client.j2se.CommandLineRunner"
        libs = ["javase-3.0.0.jar", "core-3.0.0.jar"]
        libs_fullpath = [os.path.join(os.path.dirname(__file__), "lib", lib) for lib in libs]
        classpath = ":".join(libs_fullpath)

        p = subprocess.Popen(["java", "-cp", classpath, runner, image, "--possibleFormats=AZTEC"],
                            stdout=subprocess.PIPE, 
                            stderr=subprocess.PIPE)
        out, err = p.communicate()
       
        # There was a problem.. 
        if p.returncode != 0:
            # Attempt to get a meaninful error
            err_lines = err.split('\n')
            out_lines = out.split('\n')
            if len(err_lines) > 5: # Assume a Java stack trace
                for line in err_lines:
                    if line.startswith("Caused by"):
                        error_msg = line
                        break
            elif out: error_msg = out_lines[0] 
            else: error_msg = err_lines[0]
            raise BarcodeDecodeError(error_msg)

        decoded = out.split('\n')[2] # Get 3rd line (raw string)
        
        if self.LOG.getEffectiveLevel() is logging.DEBUG:
            stop = timeit.default_timer()
            self.LOG.debug("_read_barcode: %ss" % (stop - start))
        
        return decoded

    def pprint(self):
        from pprint import pprint
        pprint(self.info, indent=4)

    def __repr__(self):
        return str(self.info)

class BarcodeFormatError(Exception):
    pass

class BarcodeDecodeError(Exception):
    pass
