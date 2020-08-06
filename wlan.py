import credentials, network, time


# WIFI Setup
class WLAN:
    def __init__(self):
        # Try to connect to WiFi if Station SSID is specified
        if credentials.WIFI_STA['SSID']:
            self.interface = network.WLAN(network.STA_IF)
            self.interface.active(True)
            self.interface.connect(credentials.WIFI_STA['SSID'], credentials.WIFI_STA['PASSWORD'])
            total_time = 5000  # Give wifi 5 seconds to connect
            start_time = time.ticks_ms()
            while self.interface.status() != network.STAT_GOT_IP and (time.ticks_ms() - start_time) < total_time:
                pass
            # Start ip an Access Point
            if not self.interface.isconnected():
                self.interface.active(False)
                self.startAccessPoint()
        else:
            self.startAccessPoint()

    def startAccessPoint(self):
        self.interface = network.WLAN(network.AP_IF)
        self.interface.active(True)
        self.interface.config(essid=credentials.WIFI_AP['SSID'], password=credentials.WIFI_AP['PASSWORD'],
                    authmode=network.AUTH_WPA_WPA2_PSK)
        # TODO: check if there is a better way than time out
        total_time = 5000  # Give wifi 5 seconds to start AP
        start_time = time.ticks_ms()
        while not self.interface.active() and (time.ticks_ms() - start_time) < total_time:
            pass

    def isNotReady(self):
        return not self.interface.active() and not self.interface.isconnected()
