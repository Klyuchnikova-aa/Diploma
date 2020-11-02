import sys, signal, struct
import time, threading
import Device_pattern
import some_bit_operations

def_send = "tcp://192.168.43.105:5556"
def_recv = "tcp://192.168.43.105:5557"

# def_send = "tcp://192.168.0.105:5556"
# def_recv = "tcp://192.168.0.105:5557"

def_id = 0
def_code = 42
def_hw_ver = 1
def_sw_ver = 1


# Message: id - 4, time - 4 + 4, flags - 4, len - 1, data - len bytes

'''''
Reading commands from input
You can set in and out registers. Commands:
Device_id In/Out Num_of_register Register_value
F.E cmd Out 1 1 sets out_reg[1] with value 1
'''''


class CEDIO_D(Device_pattern.Device_pattern):
    global def_send, def_recv, def_id, def_hw_ver, def_sw_ver, random_thread

    def __init__(self, event, send_addr=def_send, recv_addr=def_recv, id=def_id, dev_code=def_code, hw_ver=def_hw_ver,
                 sw_ver=def_sw_ver, read_input_flag=True, random_regs_flag=False):
        """Constructor"""
        Device_pattern.Device_pattern.__init__(self, event, send_addr, recv_addr, id, dev_code, hw_ver, sw_ver)

        self.out_reg = bytearray(2)  # 2 bytes
        self.out_reg[0] = 1
        self.in_reg = bytearray(2)
        self.in_reg[1] = 1
        self.CD_mask = bytearray(2)
        self.in_reg_changed = bytearray(2)
        self.channels = [0]*3
        self.is_need_start = 0
        self.is_start = 0

        self.__random_i = 0

        if random_regs_flag == True:
            rand_t = threading.Thread(target=self.__random_my_timer, name="Random thread", args=(5,), daemon=True)
            rand_t.start()

        if read_input_flag == True:
            read_t = threading.Thread(target=self.__start_read_input, name="Input thread", daemon=True)
            read_t.start()

    def __random_change_inputs(self):
        self.set_in_reg(self.__random_i, 1)
        self.set_in_reg((self.__random_i-1)%8, 0)

        def form_xFA_answer():
            if (self.in_reg_changed[0] & self.CD_mask[0]) != 0 or (self.in_reg_changed[1] & self.CD_mask[1]) != 0:
                answer = bytearray(7)
                answer[0] = 0xFA
                answer[1] = self.CD_mask[0]
                answer[2] = self.in_reg_changed[0]
                answer[3] = self.in_reg[0]
                answer[4] = self.CD_mask[1]
                answer[5] = self.in_reg_changed[1]
                answer[6] = self.in_reg[1]
                self.in_reg_changed[0] = 0
                self.in_reg_changed[1] = 0

        if self.in_reg_changed[0] != 0 or self.in_reg_changed[1] != 0:
            answer_data = form_xFA_answer()
            if answer_data is not None:
                answer = self.form_answer_message(answer_data)
                self.send_socket.send(answer)

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
            if len(a) != 4 or not a[3].isdigit() or not a[2].isdigit():
                print('Wrong command format. Please, enter Device_id In/Out Num_of_register Register_value')
                continue
            if int(a[0], 0) != self.id:
                continue
            reg_num = int(a[2])
            val = int(a[3])

            if a[1] in set(['in', 'In', 'IN']):
                self.set_in_reg(reg_num, val)
            elif a[1] in set(['Out', 'out', 'OUT']):
                self.set_out_reg(reg_num, val)
            else:
                print('Wrong command format. Please, enter Device_id In/Out Num_of_register Register_value')

            if self.in_reg_changed[0] != 0 or self.in_reg_changed[1] != 0:
                answer_data = self.form_FA_answer()
                if answer_data is not None:
                    answer = self.form_answer_message(answer_data)
                    self.send_socket.send(answer)

    def x8n_cmd(self, data):
        channel = data[0] - 0x80
        if channel in range(0,3):
            # Если не используется работа с файлами, то значения младших байтов безразличны.  ?
            self.channels[channel] = struct.unpack("i", data[1:5])[0]

    def x84_cmd(self, data):
        self.is_need_start = data[1]

    def x9n_cmd(self, data):
        answer = bytearray(5)
        answer[0] = data[0]
        channel = data[0] - 0x90
        if channel in range(0,3):
            # Если не используется работа с файлами, то значения младших байтов безразличны.  ?
            answer[1:5] = struct.pack("i", self.channels[channel])
            return answer

    def x94_cmd(self):
        answer = bytearray(2)
        answer[0] = 0x94
        answer[1] = self.is_start
        return answer

    def xE8_cmd(self):
        answer = bytearray(7)
        answer[0] = 0xE8
        answer[1:3] = self.out_reg
        answer[3:5] = self.in_reg
        answer[5] = 0
        answer[6] = 0
        return answer

    def xE9_cmd(self, data):
        self.out_reg[0] = data[1]
        self.out_reg[1] = data[2]

    def xF7_cmd(self, data):
        if data[1] == self.is_need_start: #not passive channel??
            self.is_start = 1

    def xFB_cmd(self):
        self.is_start = 0

    def xFE_cmd(self):
        answer = bytearray(2)
        answer[0] = 0xFE
        answer[1] = some_bit_operations.set_bit(answer[1], 0, self.is_start)
        answer[1] = some_bit_operations.set_bit(answer[1], 1, self.is_need_start)
        if self.channels[0] != 0 or self.channels[1] != 0 or self.channels[2] != 0:
            answer[1] = some_bit_operations.set_bit(answer[1], 2, 1)
        return answer

    def process_data(self, data, priority):
        descriptor = data[0]

        if descriptor == 0xE8:
            return self.xE8_cmd()

        elif descriptor == 0xE9:
            self.xE9_cmd(data)

        elif descriptor in range(0x80, 0x84):
            self.x8n_cmd(data)

        elif descriptor == 0x84:
            self.x84_cmd(data)

        elif descriptor in range(0x90, 0x94):
            self.x9n_cmd(data)

        elif descriptor == 0x94:
            self.x94_cmd()

        elif descriptor == 0xF7:
            return self.xF7_cmd(data)

        elif descriptor == 0xFB:
            return self.xFB_cmd()

        elif descriptor == 0xFE:
            return self.xFE_cmd()

        elif descriptor == 0xFF:
            return self.xFF_cmd(priority)
        else:
            pass

    def set_in_reg(self, num_reg, value):
        if not (num_reg in range(0, 14)) or not (value in range(0, 2)):
            print("register num is not in range(0,14) or value is not in range(0,2)")
            return

        self.in_reg_changed[0] = 0
        self.in_reg_changed[1] = 0

        if num_reg <= 7:
            new_data = some_bit_operations.set_bit(self.in_reg[0], num_reg, value)
            self.in_reg_changed[0] = some_bit_operations.compare_bits(new_data, self.in_reg[0])
            self.in_reg[0] = new_data
        else:
            new_data = some_bit_operations.set_bit(self.in_reg[1], num_reg - 7, value)
            self.in_reg_changed[1] = some_bit_operations.compare_bits(new_data, self.in_reg[1])
            self.in_reg[1] = new_data

    def set_out_reg(self, num_reg, value):
        if not (num_reg in range(0, 14)) or not (value in range(0, 2)):
            print("register num is not in range(0,14) or value is not in range(0,2)")
            return

        if num_reg <= 7:
            self.out_reg[0] = some_bit_operations.set_bit(self.out_reg[0], num_reg, value)
        else:
            self.out_reg[1] = some_bit_operations.set_bit(self.out_reg[1], num_reg - 7, value)
