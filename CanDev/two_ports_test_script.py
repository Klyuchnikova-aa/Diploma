import CEAC124
from Executor import *
import zmq, signal, sys, time

# def_send_0 = "tcp://192.168.0.105:5556"
# def_recv_0 = "tcp://192.168.0.105:5557"
#
# def_send_1 = "tcp://192.168.0.105:6666"
# def_recv_1 = "tcp://192.168.0.105:6667"


def_send_0 = "tcp://192.168.43.105:5556"
def_recv_0 = "tcp://192.168.43.105:5557"

def_send_1 = "tcp://192.168.43.105:6666"
def_recv_1 = "tcp://192.168.43.105:6667"

devices = []
event = threading.Event()

for i in range(0,64):
    devices.append(CEAC124.CEAC124(event=event, send_addr=def_send_0, recv_addr=def_recv_0, id=i, random_regs_flag=True))

for i in range(64, 128):
    devices.append(CEAC124.CEAC124(event=event, send_addr=def_send_1, recv_addr=def_recv_1, id=i, random_regs_flag=True))


poller = zmq.Poller()
my_executor = Executor(poller, devices, event)
my_executor.start()
