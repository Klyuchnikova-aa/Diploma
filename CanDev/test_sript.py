import CEDIO_A
from Executor import *
import zmq, threading

# def_send = "tcp://192.168.0.105:5556"
# def_recv = "tcp://192.168.0.105:5557"

def_send = "tcp://192.168.43.105:5556"
def_recv = "tcp://192.168.43.105:5557"

event = threading.Event()

devices = [CEDIO_A.CEDIO_A(event=event, send_addr=def_send, recv_addr=def_recv, id=1, random_regs_flag=True)]

poller = zmq.Poller()
my_executor = Executor(poller, devices, event)
my_executor.start()
