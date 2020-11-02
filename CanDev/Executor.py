import zmq, signal, threading

class Executor():

    def __init__(self, poller, devices, event):
        self.poller = poller
        self.devices = devices
        self.event = event

    def poll_cycle(self):
        while True:
            socks = dict(self.poller.poll())
            for device in self.devices:
                if device.recv_socket in socks and socks[device.recv_socket] == zmq.POLLIN:
                    self.event.clear()
                    device.recv_from_can()
                    self.event.set()


    def start(self):
        for device in self.devices:
            self.poller.register(device.recv_socket, zmq.POLLIN)
        t = threading.Thread(target=self.poll_cycle, name="Cycle thread")
        t.start()
