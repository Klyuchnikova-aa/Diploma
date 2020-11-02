import zmq
import sys, signal
import time, threading
import struct


# Message: id - 4, time - 4 + 4, flags - 4, len - 1, data - len bytes
# FF - запрос атрибутов устройства


class Device_pattern:
    def __init__(self, event, send_addr="tcp://192.168.0.105:5556", recv_addr="tcp://192.168.0.105:5557", id=0, dev_code=0, hw_ver=1,
                 sw_ver=1):
        """Constructor"""
        self.id = id
        self.Device_code = dev_code
        self.HW_version = hw_ver
        self.SW_version = sw_ver

        self.recv_context = zmq.Context()
        self.recv_socket = self.recv_context.socket(zmq.SUB)
        self.recv_socket.connect(recv_addr)
        self.recv_socket.setsockopt(zmq.SUBSCRIBE, b'')

        self.send_context = zmq.Context()
        self.send_socket = self.send_context.socket(zmq.PUB)
        self.send_socket.connect(send_addr)

        self.event = event

        print("Device listen on %s" % recv_addr)
        print("Device send messages on %s" % send_addr)
        print("Device address = ", self.id)

    def close(self):
        self.send_socket.close()
        self.send_context.destroy()
        self.recv_socket.close()
        self.recv_context.destroy()

    def _make_code(self, val, neg_low_code, neg_up_code, neg_low_volt, neg_up_volt, pos_low_code, pos_up_code,
                         pos_low_volt, pos_up_volt):
        # res = val*1.0 * (pos_up_code*1.0 - pos_low_code*1.0) / (pos_up_volt*1.0) + pos_low_code*1.0
        # return struct.pack("i", round(res))
        if val < neg_up_volt:
            res = neg_up_code + (val - neg_up_volt) / (neg_up_volt - neg_low_volt) * (neg_up_code - neg_low_code)
            return struct.pack("i", round(res))
        else:
            res = pos_up_code + (val - pos_up_volt) / (pos_up_volt - pos_low_volt) * (pos_up_code - pos_low_code)
            return struct.pack("i", round(res))

    def _make_value(self, byte_val, neg_low_code, neg_up_code, neg_low_volt, neg_up_volt, pos_low_code, pos_up_code,
                    pos_low_volt, pos_up_volt):
        # val = struct.unpack("i", byte_val)[0]
        # res = (val*1.0 - pos_low_code*1.0) * pos_up_volt*1.0 / (pos_up_code*1.0 - pos_low_code*1.0)
        # return res
        val = struct.unpack("i", byte_val)[0] #TEST
        if val < neg_up_code:
            return neg_up_volt + (val - neg_up_code) / (neg_up_code - neg_low_code) * (neg_up_volt - neg_low_volt)
        else:
            return pos_up_volt + (val - pos_up_code) / (pos_up_code - pos_low_code) * (pos_up_volt - pos_low_volt)

    def xFF_cmd(self, priority):
        answer = bytearray(5)
        answer[0] = 0xFF
        answer[1] = self.Device_code
        answer[2] = self.HW_version
        answer[3] = self.SW_version
        if priority == 5:
            answer[4] = 3
        else:
            answer[4] = 2
        return answer

    def process_id(self, id):
        # Пользователь должен посылать устройству нулевую комбинацию.
        reserve = (id[0] & 0b00000011)  # # 0b00000000000000000000000000000011
        phys_address = ((id[0] & 0b11111100) >> 2)  # # 0b000000000000000000000000111111
        priority = (id[1] & 0b00000111)  # id[2]  # 0b000000000000000000000111
        return priority, phys_address, reserve

    def process_data(self, data, priority):
        descriptor = data[0]
        #print("descriptor = ", bin(data[0]))

        if descriptor == 0xFF:
            return self.xFF_cmd(priority)
        else:
            print("Unknown descriptor")

        #ADD YOUR DESCRIPTORS

    def form_answer_id(self, answer_code=7):
        answer_id = bytearray(4)
        answer_id[0] = (answer_id[0] | self.id) << 2
        # reserve is 0 here
        answer_id[1] = (answer_id[1] | answer_code)
        return answer_id

    def form_answer_message(self, answer_data, answer_code=7):
        answer_id = self.form_answer_id(answer_code)
        #print("SEND answer, answer_id: ")
        answer = bytearray(25)
        answer[:4] = answer_id
        # for i in answer[:4]:
        #      print(bin(i))
        ts = time.time()
        tms = ts*10**-6
        bs = bytearray(struct.pack("f", ts))
        bms = bytearray(struct.pack("f", tms))
        answer[4:8] = bs
        answer[8:12] = bms
        answer[16] = len(answer_data)
        #print("data len = ", int(answer[16]))
        answer[17:] = answer_data
        # for i in answer[17:26]:
        #     print(bin(i))
        # print(" ")
        return answer

    def process_message(self, msg):
        #id 32 bit
        msg_id = msg[:4]
        priority, phys_address, reserve = self.process_id(msg_id)

        if priority == 6 and phys_address != self.id:
            #print("msg for another device")
            return

        msg_data = msg[17:17+msg[16]]
        answer_data = self.process_data(msg_data, priority)

        if answer_data is not None:
            answer = self.form_answer_message(answer_data)
            try:
                self.send_socket.send(answer, flags=zmq.NOBLOCK)
            except zmq.ZMQError as x:
                print(x)

    def recv_from_can(self):
        try:
            msg = self.recv_socket.recv()
            if len(msg) >= 25:
                self.process_message(msg)
                # print("id = ", self.id, " processed descriptor ", hex(msg[17]))
                # print()
        except zmq.Again as e:
            pass
