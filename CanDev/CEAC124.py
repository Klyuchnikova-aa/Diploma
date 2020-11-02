import zmq
import time, threading, struct
import Device_pattern
import some_bit_operations
import random

'''''
Reading commands from input
You can set in and out registers. Commands:
Device_id In/Out/ADC Num_of_register/Adc_channel Register_value/ADC_value
F.E cmd Out 1 1 sets out_reg[1] with value 1
'''''

def_send = "tcp://192.168.43.105:5556"
def_recv = "tcp://192.168.43.105:5557"

# def_send = "tcp://192.168.0.105:5556"
# def_recv = "tcp://192.168.0.105:5557"

def_id = 0x1E
def_code = 20
def_hw_ver = 1
def_sw_ver = 3


ADC_pos_up_code = 0x3fffff
ADC_pos_up_volt = +10
ADC_pos_low_code = 0
ADC_pos_low_volt = 0

ADC_neg_up_code = 0xffffff
ADC_neg_up_volt = -0
ADC_neg_low_code = 0xC00000
ADC_neg_low_volt = -10

DAC_pos_up_code = 0xffff
DAC_pos_up_volt = +9.9997
DAC_pos_low_code = 0x8000
DAC_pos_low_volt = 0

DAC_neg_up_code = 0x7fff
DAC_neg_up_volt = -0.0003
DAC_neg_low_code = 0
DAC_neg_low_volt = -10

time_code = [0.001*12, 0.002*12, 0.005*12, 0.01*12, 0.02*12, 0.04*12, 0.08*12, 0.160*12]


# Message: id - 4, time - 4 + 4, flags - 4, len - 1, data - len bytes


class CEAC124(Device_pattern.Device_pattern):
    global def_send, def_recv, def_id, def_hw_ver, def_sw_ver, def_code

    def __init__(self, event, send_addr=def_send, recv_addr=def_recv, id=def_id, dev_code=def_code, hw_ver=def_hw_ver,
                 sw_ver=def_sw_ver, ADC_n=16, DAC_n=4, in_reg=4, out_reg=4, read_input_flag=True, random_regs_flag=False, random_ADC_flag=False):
        """Constructor"""
        Device_pattern.Device_pattern.__init__(self, event, send_addr, recv_addr, id, dev_code, hw_ver, sw_ver)
        self.in_reg_num=in_reg
        self.out_reg_num =out_reg
        if int(out_reg/8) > 0:
            self.out_reg = bytearray(int(out_reg/8))
        else:
            self.out_reg = bytearray(1)

        if int(in_reg/8) > 0:
            self.in_reg = bytearray(int(in_reg/8))
        else:
            self.in_reg = bytearray(1)

        self.channels_ADC_num = ADC_n
        self.channels_ADC = [0] * ADC_n
        self.random_ADC_flag = random_ADC_flag
        self.even_ampl = 1 << 6
        self.odd_ampl = 1 << 6

        self.channels_DAC_num = DAC_n
        self.channels_DAC = [0] * DAC_n

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

        self.file_full_size = 27 * (2 + 4*4)
        self.file = [0, 0, bytearray(self.file_full_size)] #descriptor = 0b00000001, len, records
        self.file_status = 0
        self.file_cur_inc_addr = 0
        self.file_next_record = 0

        t = threading.Thread(target=self.__start_measure, name="ADC thread") #daemon=True
        t.start()

        DAC_t = threading.Thread(target=self.__start_DAC_file, name="DAC thread") #daemon=True
        DAC_t.start()

        self.__random_i = 0
        if random_regs_flag == True:
            rand_t = threading.Thread(target=self.__random_my_timer, name="Random reg thread", args=(5,), daemon=True)
            rand_t.start()
        if read_input_flag == True:
            read_t = threading.Thread(target=self.__start_read_input, name="Input thread", daemon=True)
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
                            answer_data[1] &= 0b00111111
                            if i % 2 == 0:
                                answer_data[1] |= self.even_ampl
                            else:
                                answer_data[1] |= self.odd_ampl

                            answer_data[2:5] = self._make_code(self.channels_ADC[i], ADC_neg_low_code, ADC_neg_up_code, ADC_neg_low_volt,
                                                               ADC_neg_up_volt, ADC_pos_low_code, ADC_pos_up_code, ADC_pos_low_volt, ADC_pos_up_volt)[:3]
                            answer = self.form_answer_message(answer_data)
                            try:
                                self.send_socket.send(answer, flags=zmq.NOBLOCK)
                            except zmq.ZMQError as x:
                                print(x)
                            time.sleep(self.time)

            time.sleep(self.time)

    def __start_DAC_file(self):
        while True:
            self.event.wait()
            if some_bit_operations.get_bit(self.file_status, 0) == 0 or \
                    some_bit_operations.get_bit(self.file_status, 2) == 1 or \
                    self.file_cur_inc_addr >= self.file_next_record:
                # not run or pause or file end
                pass
            else:
                for i in range(4):
                    if self.file_cur_inc_addr + 2 + i + 4 > self.file_next_record:
                        break

                    self.channels_DAC[i] += self._make_value(self.file[2][self.file_cur_inc_addr + 2 + i:self.file_cur_inc_addr + 2 + i + 4],
                                                             DAC_neg_low_code, DAC_neg_up_code, DAC_neg_low_volt,
                                                             DAC_neg_up_volt, DAC_pos_low_code, DAC_pos_up_code,
                                                             DAC_pos_low_volt, DAC_pos_up_volt)

                new_increment = struct.unpack('h', self.file[2][self.file_cur_inc_addr:self.file_cur_inc_addr + 2])[0] - 1
                self.file[2][self.file_cur_inc_addr:self.file_cur_inc_addr + 2] = struct.pack('h', new_increment)
                if new_increment == 0:
                    self.file_cur_inc_addr += 18
                time.sleep(10)

    def __random_change_inputs(self):
        self.set_in_reg(self.__random_i, 1)
        self.set_in_reg((self.__random_i-1)%4, 0)

        self.__random_i += 1
        if self.__random_i > 3:
            self.__random_i = 0

    def __random_my_timer(self, timer_time):
        data = threading.local()
        while True:
            self.event.wait()
            time.sleep(timer_time)
            self.__random_change_inputs()

    def __start_read_input(self):
        data = threading.local()
        while True:
            self.event.wait()
            s = input()
            a = s.split()
            if len(a) != 4 or not a[2].isdigit():
                print('Wrong command length or args 2 wrong. Please, enter Device_id In/Out/Adc Num_of_register/Adc_channel value')
                continue
            try:
                id = int(a[0], 0)
                if id != self.id:
                    continue
            except ValueError:
                print("Error value")

            num = int(a[2])
            val = None
            if a[1] in set(['in', 'In', 'IN']):
                try:
                    val = int(a[3])
                    self.set_in_reg(num, val)
                except ValueError:
                    print("Error value")
            elif a[1] in set(['Out', 'out', 'OUT']):
                try:
                    val = int(a[3])
                except ValueError:
                    print("Error value")
                self.set_out_reg(num, val)
            elif a[1] in set(['ADC', 'adc', 'Adc']):
                try:
                    val = float(a[3])
                    self.set_ADC_channel(num, val)
                except ValueError:
                    print("Error value")
            else:
                print('Wrong command. Please, enter Device_id In/Out/ADC Num_of_register/Adc_channel value')

    def x00_cmd(self, data):
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

        self.odd_ampl = (data[4] & 0b00000011) << 6
        self.even_ampl = (data[4] & 0b00001100) << 4

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
        channel = data[1]
        answer = bytearray(5)
        answer[0] = 0x03
        answer[1] = channel
        if int(channel) in range(0, self.channels_ADC_num):
            #amplification coeff???
            answer[2:5] = self._make_code(self.channels_ADC[channel], ADC_neg_low_code, ADC_neg_up_code, ADC_neg_low_volt,
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

    def xF8_cmd(self, data):
        answer = bytearray(3)
        answer[0] = 0xF8
        answer[1] = self.out_reg[0]
        answer[2] = self.in_reg[0]
        return answer

    def xF9_cmd(self, data):
        self.out_reg[0] = data[1]

    def xFE_cmd(self, data):
        answer = bytearray(8)
        answer[0] = 0xFE
        answer[1] = some_bit_operations.set_bit(answer[1], 4, int(self.multichannel))
        answer[1] = some_bit_operations.set_bit(answer[1], 3, int(self.run_measure))
        answer[1] = some_bit_operations.set_bit(answer[1], 1, some_bit_operations.get_bit(self.file_status,1))
        answer[1] = some_bit_operations.set_bit(answer[1], 0, some_bit_operations.get_bit(self.file_status,0))
        answer[2] = self.group_label
        answer[3] = self.buf_e
        # answer[4] = pHIGH ADC
        answer[5] = self.file[0]
        answer[6:8] = struct.pack('h', self.file_next_record) #??????
        return answer

    def x8n_cmd(self, data):
        channel = data[0] - 0x80
        val_ar = bytearray(4)
        if some_bit_operations.get_bit(self.file_status, 7) == 0: # if file os used
            val_ar[0] = data[2]
            val_ar[1] = data[1]
        else:
            val_ar[0] = data[4]
            val_ar[1] = data[3]
            val_ar[2] = data[2]
            val_ar[3] = data[1]

        self.channels_DAC[channel] = self._make_value(val_ar, DAC_neg_low_code, DAC_neg_up_code, DAC_neg_low_volt,
                                                    DAC_neg_up_volt, DAC_pos_low_code, DAC_pos_up_code, DAC_pos_low_volt, DAC_pos_up_volt)

    def x9n_cmd(self, data):
        channel = data[0] - 0x90
        answer = bytearray(5)
        answer[0] = data[0]
        val_ar = self._make_code(self.channels_DAC[channel], DAC_neg_low_code, DAC_neg_up_code, DAC_neg_low_volt,
                                                    DAC_neg_up_volt, DAC_pos_low_code, DAC_pos_up_code, DAC_pos_low_volt, DAC_pos_up_volt)

        if some_bit_operations.get_bit(self.file_status, 7) == 0: # is file is used
            answer[1] = val_ar[1]
            answer[2] = val_ar[0]
        else:
            answer[1] = val_ar[3]
            answer[2] = val_ar[2]
            answer[3] = val_ar[1]
            answer[4] = val_ar[0]
        return answer

    def xE7_cmd(self, data):
        #RESUME 2 == 0 -> file run alse file pause
        if self.file[0] == data[1]:
            some_bit_operations.set_bit(self.file_status, 4, 1)
            self.file_status = some_bit_operations.set_bit(self.file_status, 2, 0)
            self.file_status = some_bit_operations.set_bit(self.file_status, 3, 0)
            self.file_status = some_bit_operations.set_bit(self.file_status, 4, 0)

    def xEB_cmd(self, data):
        #PAUSE
        if self.file[0] == data[1]:
            some_bit_operations.set_bit(self.file_status, 3, 1)
            self.file_status = some_bit_operations.set_bit(self.file_status, 3, 1)
            self.file_status = some_bit_operations.set_bit(self.file_status, 2, 1)

    def xF2_cmd(self, data):
        if self.file[0] == data[1]:
            addr_in_file = struct.pack('h', data[2:4])
            if addr_in_file < self.file_full_size-4:
                self.file[2][addr_in_file:addr_in_file + 4] = data[4:]

    def xF3_cmd(self, data):
        self.file = [data[1], 0, bytearray(self.file_full_size)]
        self.file_next_record = 0
        self.file_cur_inc_addr = 0
        self.file_status = 0b10000000 # status is opened

    def xF4_cmd(self, data):
        if self.file_next_record >= self.file_full_size:
            print("file is full")
            return
        if some_bit_operations.get_bit(self.file_status, 7) == 0:
            print('file is closed for sequential records')
            return
        self.file[2][self.file_next_record:self.file_next_record+len(data)-1] = data[1:len(data)]
        self.file_next_record += len(data)-1

    def form_xF5_answer(self):
        answer = bytearray(4)
        answer[0] = 0xF5
        answer[1] = self.file[0]
        answer[2:4] = struct.pack('h', self.file[1])
        return answer

    def xF5_cmd(self, data):
        #close to record step by step only by address
        if self.file[0] == data[1]:
            answer = self.form_xF5_answer()
            self.file_status = some_bit_operations.set_bit(self.file_status, 7, 0)
            return answer

    def xFB_cmd(self, data):
        # PAUSE
        if self.file[0] == data[1]:
            self.file_status = some_bit_operations.set_bit(self.file_status, 0, 0)
            self.file_status = some_bit_operations.set_bit(self.file_status, 2, 0)
            self.file_status = some_bit_operations.set_bit(self.file_status, 3, 0)
            self.file_status = some_bit_operations.set_bit(self.file_status, 4, 0)

    def xF6_cmd(self, data):
        if self.file[0] == data[1]:
            address = struct.unpack('h', data[2:4])[0]
            if address <= self.file_full_size - 4:
                answer = bytearray(5)
                answer[0] = 0xF6
                answer[1:5] = self.file[2][address:address+4]
                return answer
            else:
                print("file record address = ", address," is too long")

    def xF7_cmd(self, data):
        if self.file[0] == data[1]:
            self.file_status = some_bit_operations.set_bit(self.file_status, 1, 1)
            self.file_status = some_bit_operations.set_bit(self.file_status, 0, 1)

    def xFD_cmd(self, data):
        answer = bytearray(7)
        answer[0] = 0xFD
        answer[1] = self.file_status
        answer[2] = self.file[0]
        answer[3:5] = struct.pack('h', self.file_next_record) #??????
        answer[5:7] = self.file[2][self.file_cur_inc_addr:self.file_cur_inc_addr+2]
        return answer

    def process_data(self, data, priority):
        descriptor = data[0]
        #print("descriptor = ", hex(data[0]))
        if descriptor == 0xFF:
            return self.xFF_cmd(priority)
        elif descriptor == 0x00:
            return self.x00_cmd(data)
        # elif descriptor == 0x01:
        #     return self.x01_cmd(data)
        elif descriptor == 0x02:
            return self.x02_cmd(data)
        elif descriptor == 0x03:
            return self.x03_cmd(data)
        elif descriptor == 0x04:
            return self.x04_cmd(data)
        elif descriptor in range(0x80, 0x84):
            #print("self id = ", self.id, " descriptor = ", hex(descriptor))
            return self.x8n_cmd(data)
        elif descriptor in range(0x90, 0x94):
            return self.x9n_cmd(data)
        elif descriptor == 0xF2:
            return self.xF2_cmd(data)
        elif descriptor == 0xF3:
            return self.xF3_cmd(data)
        elif descriptor == 0xF4:
            return self.xF4_cmd(data)
        elif descriptor == 0xF5:
            return self.xF5_cmd(data)
        elif descriptor == 0xF6:
            return self.xF6_cmd(data)
        elif descriptor == 0xF7:
            return self.xF7_cmd(data)
        elif descriptor == 0xF8:
            return self.xF8_cmd(data)
        elif descriptor == 0xF9:
            return self.xF9_cmd(data)
        elif descriptor == 0xFE:
            return self.xFE_cmd(data)
        elif descriptor == 0xFD:
            return self.xFD_cmd(data)
        elif self.SW_version <= 4:
            if descriptor == 0xE7:
                return self.xE7_cmd(data)
            elif descriptor == 0xFB:
                pass
            elif descriptor == 0xEB:
                return self.xEB_cmd(data)
        else:
            pass

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
