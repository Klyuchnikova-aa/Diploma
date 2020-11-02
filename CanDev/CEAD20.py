import sys, signal
import Device_pattern
import time, threading, struct
import some_bit_operations
import random

'''''
Reading commands from input
You can set in and out registers. Commands:
Device_id In/Out/ADC Num_of_register/Adc_channel Register_value/ADC_value
F.E cmd Out 1 1 sets out_reg[1] with value 1
'''''

def_send = "tcp://192.168.0.105:5556"
def_recv = "tcp://192.168.0.105:5557"

# def_send = "tcp://192.168.43.105:5556"
# def_recv = "tcp://192.168.43.105:5557"

def_id = 0x17
def_code = 23
def_hw_ver = 1
def_sw_ver = 1

ADC_pos_up_code = 0x3fffff
ADC_pos_up_volt = +10
ADC_pos_low_code = 0
ADC_pos_low_volt = 0

ADC_neg_up_code = 0xffffff
ADC_neg_up_volt = -0
ADC_neg_low_code = 0xC00000
ADC_neg_low_volt = -10

time_code = [1, 2, 5, 10, 20, 40, 80, 160]


# Message: id - 4, time - 4 + 4, flags - 4, len - 1, data - len bytes


class CEAD20(Device_pattern.Device_pattern):
    global def_send, def_recv, def_id, def_hw_ver, def_sw_ver, def_code

    def __init__(self, event, send_addr=def_send, recv_addr=def_recv, id=def_id, dev_code=def_code, hw_ver=def_hw_ver,
                 sw_ver=def_sw_ver, ADC_n=20, in_reg=4, out_reg=4, read_input_flag=True, random_regs_flag=False, random_ADC_flag=False):
        """Constructor"""
        Device_pattern.Device_pattern.__init__(self, event, send_addr, recv_addr, id, dev_code, hw_ver, sw_ver)
        self.random_ADC_flag = random_ADC_flag
        self.in_reg_num = in_reg
        self.out_reg_num = out_reg
        if int(out_reg / 8) > 0:
            self.out_reg = bytearray(int(out_reg / 8))
        else:
            self.out_reg = bytearray(1)

        if int(in_reg / 8) > 0:
            self.in_reg = bytearray(int(in_reg / 8))
        else:
            self.in_reg = bytearray(1)
        self.channels_ADC_num = ADC_n
        self.channels_ADC = [0] * ADC_n

        self.buf_size = 128
        self.buffer = [None] * self.buf_size
        self.buf_s = 0
        self.buf_e = 0

        self.start_ch = 0
        self.end_ch = 0
        self.time = 0
        self.group_label = 0
        self.descriptor = 0

        self.multichannel = False
        self.run_measure = False
        self.is_single_measure = True
        self.is_need_measure = False
        self.is_need_send = False
        self.is_need_store = False

        t = threading.Thread(target=self.__start_measure, name="ADC")
        t.start()

        if random_regs_flag == True:
            rand_t = threading.Thread(target=self.__random_my_timer, name="Random reg", args=(5,))
            rand_t.start()
        if read_input_flag == True:
            read_t = threading.Thread(target=self.__start_read_input, name="Input")
            read_t.start()

    def __start_measure(self):
        while True:
            self.event.wait()
            if self.run_measure == 0:
                pass
            else:
                if self.is_single_measure and self.is_need_measure or not self.is_single_measure:
                    self.is_single_measure = False
                    if self.random_ADC_flag:
                        for i in range(self.start_ch, self.end_ch + 1):
                            self.channels_ADC[i] = random.uniform(-10., 10.)

                    if self.is_need_store:
                        for i in range(self.start_ch, self.end_ch + 1):
                            self.buffer[self.buf_e] = [i, self.channels_ADC[i]]
                            self.buf_e = (self.buf_e + 1) % self.buf_size
                            if self.buf_e == self.buf_s:
                                self.buf_s = (self.buf_s + 1) % self.buf_size

                    if self.is_need_send:
                        for i in range(self.start_ch, self.end_ch + 1):
                            answer_data = bytearray(5)
                            answer_data[0] = self.descriptor
                            answer_data[1] = i
                            answer_data[2:5] = self._make_code(self.channels_ADC[i], ADC_neg_low_code, ADC_neg_up_code, ADC_neg_low_volt,
                                                    ADC_neg_up_volt, ADC_pos_low_code, ADC_pos_up_code, ADC_pos_low_volt, ADC_pos_up_volt)
                            answer = self.form_answer_message(answer_data)
                            self.send_socket.send(answer)

            time.sleep(self.time)

    def __random_change_inputs(self):
        self.set_in_reg(self.__random_i, 1)
        self.set_in_reg((self.__random_i-1)%8, 0)

        self.__random_i += 1
        if self.__random_i > 7:
            self.__random_i = 0

    def __random_my_timer(self, timer_time):
        while True:
            self.event.wait()
            time.sleep(timer_time)
            self.__random_change_inputs()

    def __start_read_input(self):
        while True:
            self.event.wait()
            s = input()
            a = s.split()
            if len(a) != 4 or not a[2].isdigit():
                print('Wrong command format. Please, enter Device_id In/Out Num_of_register Register_value')
                continue

            if int(a[0], 0) != self.id:
                continue
            num = int(a[2])
            val = None
            if a[1] in set(['in', 'In', 'IN']):
                try:
                    val = int(a[3])
                except ValueError:
                    print("Error value")
                self.set_in_reg(num, val)
            elif a[1] in set(['Out', 'out', 'OUT']):
                try:
                    val = int(a[3])
                except ValueError:
                    print("Error value")
                self.set_out_reg(num, val)
            elif a[1] in set(['ADC', 'adc', 'Adc']):
                try:
                    val = float(a[3])
                except ValueError:
                    print("Error value")
                self.set_ADC_channel(num, val)
            else:
                print('Wrong command format. Please, enter Device_id In/Out/ADC Num_of_register/Adc_channel value')

    def x00_cmd(self):
        self.run_measure = 0
        self.time = 0

    def x01_cmd(self, data):
        self.start_ch = data[1]
        self.end_ch = data[2]
        if self.start_ch > self.channels_ADC_num-1 or self.end_ch > self.channels_ADC_num-1:
            print("Error channels numbers in CEAC124: start = ", self.start_ch, " end = ", self.end_ch)
            self.start_ch = self.end_ch = 0
            return
        self.time = time_code[int(data[3])]
        self.group_label = data[5]
        self.run_measure = 1
        self.multichannel = 1
        self.descriptor = 0x01

        if 0 == some_bit_operations.get_bit(data[4], 4):
            self.is_single_measure = True
            self.is_need_measure = True
        else:
            self.is_single_measure = False
            self.is_need_measure = False

        if 1 == some_bit_operations.get_bit(data[4], 5):
            self.is_need_send = True
            self.is_need_store = True
        else:
            self.is_need_send = False
            self.is_need_store = True

    def x02_cmd(self, data):
        self.start_ch = (data[1] & 0b00111111)
        if self.start_ch > self.channels_ADC_num-1:
            print("Error channel numbers in CEAC124: start = ", self.start_ch)
            self.start_ch = self.end_ch = 0
            return
        self.end_ch = self.start_ch
        self.time = time_code[int(data[2])]
        self.run_measure = 1
        self.multichannel = 0
        self.descriptor = 0x02
        if 0 == some_bit_operations.get_bit(data[3], 4):
            self.is_single_measure = True
            self.is_need_measure = True
        else:
            self.is_single_measure = False
            self.is_need_measure = False

        if 1 == some_bit_operations.get_bit(data[3], 5):
            self.is_need_send = True
            self.is_need_store = False
        else:
            self.is_need_send = False
            self.is_need_store = True

    def x03_cmd(self, data):
        # verify that multichannel and need send??????
        answer = bytearray(5)
        answer[0] = 0x03
        channel = data[1]
        answer[1] = channel
        s = self.buf_s
        e = self.buf_e
        while s != e:
            if self.buffer[s][0] == channel:
                answer[2:5] = self._make_code(self.buffer[s][1], ADC_neg_low_code, ADC_neg_up_code, ADC_neg_low_volt,
                                                    ADC_neg_up_volt, ADC_pos_low_code, ADC_pos_up_code, ADC_pos_low_volt, ADC_pos_up_volt)
                return answer
            s = (s + 1) % self.buf_size

        if self.buffer[s][0] == channel:
            answer[2:5] = self._make_code(self.buffer[s][1], ADC_neg_low_code, ADC_neg_up_code, ADC_neg_low_volt,
                                                    ADC_neg_up_volt, ADC_pos_low_code, ADC_pos_up_code, ADC_pos_low_volt, ADC_pos_up_volt)
        return answer

    def x04_cmd(self, data):
        measure_num = struct.unpack("h", data[1:3])[0]
        answer = bytearray(5)
        answer[0] = 0x04
        answer[1] = self.buffer[measure_num % 128][0]
        answer[2:5] = self._make_code(self.buffer[measure_num][1], ADC_neg_low_code, ADC_neg_up_code, ADC_neg_low_volt,
                                                    ADC_neg_up_volt, ADC_pos_low_code, ADC_pos_up_code, ADC_pos_low_volt, ADC_pos_up_volt)
        return answer

    def xF8_cmd(self):
        answer = bytearray(3)
        answer[0] = 0xF8
        answer[1] = self.out_reg[0]
        answer[2] = self.in_reg[0]
        return answer

    def xF9_cmd(self, data):
        self.out_reg[0] = data[1]

    def xFE_cmd(self):
        answer = bytearray(5)
        answer[0] = 0xFE
        answer[1] = some_bit_operations.set_bit(answer[1], 4, int(self.multichannel))
        answer[1] = some_bit_operations.set_bit(answer[1], 3, int(self.run_measure))
        answer[2] = self.group_label
        answer[3] = self.buf_e
        # answer[4] = pHIGH ADC
        return answer

    def process_data(self, data, priority):
        descriptor = data[0]
        # print("descriptor = ", bin(data[0]))

        if descriptor == 0xFF:
            return self.xFF_cmd(priority)
        elif descriptor == 0x00:
            return self.x00_cmd()
        elif descriptor == 0x01:
            return self.x01_cmd(data)
        elif descriptor == 0x02:
            return self.x02_cmd(data)
        elif descriptor == 0x03:
            return self.x03_cmd(data)
        elif descriptor == 0x04:
            return self.x04_cmd(data)
        elif descriptor == 0xF8:
            return self.xF8_cmd()
        elif descriptor == 0xF9:
            return self.xF9_cmd(data)
        elif descriptor == 0xFE:
            return self.xFE_cmd()
        else:
            print("Unknown descriptor", data[0])

    def set_ADC_channel(self, channel_num, value):
        if channel_num >= self.channels_ADC_num:
            print("Error. channel_num >= ", self.channels_ADC_num)
            return
        self.channels_ADC[channel_num] = value

    def set_out_reg(self, num_reg, value):
        if not (num_reg in range(0, self.out_reg_num)) or not (value in range(0, 2)):
            print("Wrong out register num or value is not in range(0,2)")
            return
        self.out_reg[0] = some_bit_operations.set_bit(self.out_reg[0], num_reg, value)

    def set_in_reg(self, num_reg, value):
        if not (num_reg in range(0, self.in_reg_num)) or not (value in range(0, 2)):
            print("Wrong in register num or value is not in range(0,2)")
            return
        self.in_reg[0] = some_bit_operations.set_bit(self.in_reg[0], num_reg, value)
