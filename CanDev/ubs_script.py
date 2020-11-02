import CEDIO_A, CEAD20
from Executor import *
import zmq, threading

def_send = "tcp://192.168.0.105:5556"
def_recv = "tcp://192.168.0.105:5557"

# def_send = "tcp://192.168.43.105:5556"
# def_recv = "tcp://192.168.43.105:5557"

devices = []
event = threading.Event()

for i in range(17, 23):
    devices.append(CEDIO_A.CEDIO_A(event=event, send_addr=def_send, recv_addr=def_recv, id=i, random_regs_flag=True))

devices.append(CEAD20.CEAD20(event=event, send_addr=def_send, recv_addr=def_recv, id=23, random_ADC_flag=True))

poller = zmq.Poller()
my_executor = Executor(poller, devices, event)
my_executor.start()

