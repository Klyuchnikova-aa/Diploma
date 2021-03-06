import CEDIO_A
from Executor import *
import zmq, signal, sys, time

# def_send = "tcp://192.168.0.105:5556"
# def_recv = "tcp://192.168.0.105:5557"

def_send = "tcp://192.168.43.105:5556"
def_recv = "tcp://192.168.43.105:5557"

devices = []
event = threading.Event()

for i in range(0,64):
    devices.append(CEDIO_A.CEDIO_A(event=event, send_addr=def_send, recv_addr=def_recv, id=i, random_regs_flag=False))

poller = zmq.Poller()
my_executor = Executor(poller, devices, event)
my_executor.start()
