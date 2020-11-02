import CEAC124, CEAC208
from Executor import *
import zmq, threading

def_send = "tcp://192.168.0.105:5556"
def_recv = "tcp://192.168.0.105:5557"

# def_send = "tcp://192.168.43.105:5556"
# def_recv = "tcp://192.168.43.105:5557"

devices = []
event = threading.Event()

for i in range(0x01, 0x09):
    devices.append(CEAC208.CEAC208(event=event, send_addr=def_send, recv_addr=def_recv, id=i, random_ADC_flag=True))

for i in range(0x09, 0x11):
    devices.append(CEAC124.CEAC124(event=event, send_addr=def_send, recv_addr=def_recv, id=i, random_ADC_flag=True))

poller = zmq.Poller()
my_executor = Executor(poller, devices, event)
my_executor.start()
