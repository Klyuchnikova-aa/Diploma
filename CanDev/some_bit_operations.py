def is_equal_bit(byte1, byte2, num_of_bit):
    if (byte1 >> num_of_bit) & 1 != (byte2 >> num_of_bit) & 1:
        return False
    else:
        return True

def set_bit(byte, num_of_bit, value):
    if value == 1:
        return byte | (1 << num_of_bit)
    else:
        return byte & ~(1 << num_of_bit)

def compare_bits(byte1, byte2):
    changed = 0
    for compare in range(8):
        if not is_equal_bit(byte1, byte2, compare):
            changed ^= 1 << compare
    return changed

def get_bit(byte, num_of_bit):
    return int( (byte >> num_of_bit ) & 1)
