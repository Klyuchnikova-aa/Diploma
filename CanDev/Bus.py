import binascii
import zmq
import sys, signal
from collections import deque
import numpy as np

# Bus has params
# Bus sends all messages to all devices (Publish)
# Bus gets messages from devices and reply on publish socket (Subscribe)
# Bus gets commands from gateway: RECV, SEND
# Message: id - 4, time - 4 + 4, flags - 4, len - 1, data - len bytes

def_gw = "127.0.0.1:5555"
def_rcv = "*:5556"
def_snd = "*:5557"

RECV = 0
SEND = 1

MAX_BUF = 500
MAX_NUM_TO_GW = 100

class Bus:
    global def_gw, def_snd, def_rcv, def_log,def_baud, def_type, MAX_BUF

    def __init__(self, gw_address=def_gw, send_address=def_snd, recv_address=def_rcv):
        """Constructor"""
        self.context_gw = None
        self.socket_gw = None
        self.context_recv = None
        self.socket_recv = None
        self.context_send = None
        self.socket_send = None

        self.num_stored_recv = 0
        self.recv_buffer = deque(maxlen=MAX_BUF)

        self.init_gw_socket(gw_address)
        self.init_recv_socket(recv_address)
        self.init_send_socket(send_address)

        print()


    def init_recv_socket(self, address):
        self.context_recv = zmq.Context()
        self.socket_recv = self.context_recv.socket(zmq.SUB)
        self.socket_recv.bind("tcp://%s" % address)
        self.socket_recv.setsockopt(zmq.SUBSCRIBE, b'')
        print("Virtual CANbus listen can devices on %s"% address)

    def init_send_socket(self, address):
        self.context_send = zmq.Context()
        self.socket_send = self.context_send.socket(zmq.PUB)
        self.socket_send.bind("tcp://%s" % address)
        print("Virtual CANbus send to can devices on %s" % address)

    def init_gw_socket(self, address):
        self.context_gw = zmq.Context()
        self.socket_gw = self.context_gw.socket(zmq.REP)
        self.socket_gw.connect("tcp://%s" % address)
        print("Virtual CANbus listen and send to gateway on %s" % address)

    def close(self):
        self.socket_gw.close()
        self.context_gw.destroy()
        self.socket_recv.close()
        self.context_recv.destroy()
        self.socket_send.close()
        self.context_send.destroy()

    def __send_to_gw(self):
        rc = []
        num_to_send = 0
        while self.num_stored_recv > 0 and num_to_send <= MAX_NUM_TO_GW:
            message = self.recv_buffer.popleft()
            rc.append(message)
            self.num_stored_recv -= 1
            num_to_send += 1
        buf = np.array(rc)
        # print(binascii.hexlify(buf))
        try:
            self.socket_gw.send(buf, flags=zmq.NOBLOCK)
        except zmq.ZMQError as x:
            print(x)

    def __send_to_can(self, message):
        # PARSE ON DIFFERENT CAN MESSAGES AND SEND TO DEVICES
        msg_len = len(message)
        sent = 0
        while sent < msg_len:
            data_len = 8
            m = message[sent:(sent + 16 + 1 + data_len + 1)]
            self.socket_send.send(m)
            sent += 16 + 1 + data_len
        #send reply for req/rep socket
        try:
            self.socket_gw.send_string("g", flags=zmq.NOBLOCK)
        except zmq.ZMQError as x:
            print(x)

    def recv_from_gw(self):
        message = self.socket_gw.recv()
        message = np.frombuffer(message, dtype='S1')
        if int(message[0]) == RECV:
            self.__send_to_gw()
        elif int(message[0]) == SEND:
            self.__send_to_can(message[1:])
        else:
            self.socket_gw.send_string("e", flags=zmq.NOBLOCK)  # for protocol req/rep

    def recv_from_can(self):
        message = self.socket_recv.recv()
        if len(message) == 0:
            return

        if message[1] & 0b00000111 != 7:
            self.socket_send(message)
            return

        self.recv_buffer.append(message)
        if self.num_stored_recv < MAX_BUF:
            self.num_stored_recv += 1


CanBus = None

def keyboardInterruptHandler(signal, frame):
    global CanBus
    print("KeyboardInterrupt (ID: {}) has been caught. Cleaning up...".format(signal))
    CanBus.close()
    exit(0)

def main():
    global def_gw, def_snd, def_rcv, CanBus
    if len(sys.argv) > 3:
        print("")
        def_gw = sys.argv[1]
        def_rcv = sys.argv[2]
        def_snd = sys.argv[3]
        n = def_rcv.find(":")
        if def_rcv[:n] == "127.0.0.1" or def_rcv[:n] == "localhost" :
            def_rcv = "*" + def_rcv[n:]
        n = def_snd.find(":")
        if def_snd[:n] == "127.0.0.1" or def_snd[:n] == "localhost" :
            def_snd = "*" + def_snd[n:]

    CanBus = Bus(gw_address=def_gw, send_address=def_snd, recv_address=def_rcv)

    # Initialize poll set
    poller = zmq.Poller()
    poller.register(CanBus.socket_recv, zmq.POLLIN)
    poller.register(CanBus.socket_gw, zmq.POLLIN)

    while True:
        socks = dict(poller.poll())
        if CanBus.socket_recv in socks and socks[CanBus.socket_recv] == zmq.POLLIN:
            CanBus.recv_from_can()

        if CanBus.socket_gw in socks and socks[CanBus.socket_gw] == zmq.POLLIN:
            CanBus.recv_from_gw()


if __name__ == '__main__':
    signal.signal(signal.SIGINT, keyboardInterruptHandler)
    main()
