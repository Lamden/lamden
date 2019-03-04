class Event:
    evt_sock = None
    @classmethod
    def set_evt_sock(cls, evt_sock):
        cls.evt_sock = evt_sock

    @classmethod
    def emit(cls, json_data):
        if cls.evt_sock:
            cls.evt_sock.send_json(json_data)
