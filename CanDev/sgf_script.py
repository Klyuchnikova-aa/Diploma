import CEDIO_D
import CEAC124
from Executor import *
import zmq, signal, sys, time

def_send = "tcp://192.168.0.105:5556"
def_recv = "tcp://192.168.0.105:5557"

# def_send = "tcp://192.168.0.105:7776"
# def_recv = "tcp://192.168.0.105:7777"

# def_send = "tcp://192.168.43.105:5556"
# def_recv = "tcp://192.168.43.105:5557"

event = threading.Event()

ceac1e = CEAC124.CEAC124(event=event, send_addr=def_send, recv_addr=def_recv, id=0x1E)
ceac1f = CEAC124.CEAC124(event=event, send_addr=def_send, recv_addr=def_recv, id=0x1f)
ceac23 = CEAC124.CEAC124(event=event, send_addr=def_send, recv_addr=def_recv, id=0x23)
cedio24 = CEDIO_D.CEDIO_D(event=event, send_addr=def_send, recv_addr=def_recv, id=0x24)
cedio20 = CEDIO_D.CEDIO_D(event=event, send_addr=def_send, recv_addr=def_recv, id=0x20)

poller = zmq.Poller()
my_executor = Executor(poller, [ceac1e, cedio24, cedio20,ceac1f, ceac23], event)
my_executor.start()

for i in range(0,12):
    ceac1e.set_ADC_channel(i, 1.2)
    ceac1f.set_ADC_channel(i, 2.4)
    time.sleep(1)
    ceac23.set_ADC_channel(i, 0.5)
    time.sleep(1)
    cedio20.set_in_reg(1, 1)







