import CEAC124
from Executor import *
import zmq, threading

# def_send = "tcp://192.168.0.105:5556"
# def_recv = "tcp://192.168.0.105:5557"

def_send = "tcp://192.168.43.105:5556"
def_recv = "tcp://192.168.43.105:5557"

devices = []
event = threading.Event()

for i in range(0x19, 0x1D):
    devices.append(CEAC124.CEAC124(event=event, id=i, send_addr=def_send, recv_addr=def_recv, random_ADC_flag=True, dev_code=3, ADC_n=5, DAC_n=20, in_reg=8, out_reg=8))

poller = zmq.Poller()
my_executor = Executor(poller, devices, event)
my_executor.start()

for i in range(0,8):
    for d in devices:
        d.set_in_reg(i,1)
