from nucleo_api import *
import os
def run_builder(gpio_l, gpio_h):
    gpio_l = ",".join(gpio_l)
    gpio_h = ",".join(gpio_h)
    subprocess.call(
        f"python3 caravel_board/firmware_vex/gpio_config/gpio_config_builder.py -gpio_l {gpio_l} -gpio_h {gpio_h} -num_io 19 -config C_MGMT_OUT -d",
        shell=True,
    )


def manipulate_hex(file):
    bak_file = open(f"{file}.bak", "w")
    source_file = open(f"{file}", "r")
    for line in source_file:
        bak_file.write(f"{line}") 
    bak_file.close()
    source_file.close()

def modify_hex(hex_file, c_file, first_line=1):
    c_file = open(c_file, "r")
    hex_data = []
    new_hex_data = ""
    flag = False
    for aline in c_file:
        aline = aline.strip()
        if aline:
            if aline.startswith("char"):
                idx = aline.find("{")
                line = aline[idx + 1 : -4]
                data = [item.strip() for item in line.split(",")]
            if aline.startswith("int"):
                indx = aline.find("=")
                arr_size = aline[indx + 1 : -1].strip()
                if int(arr_size) > 255:
                    print(" Array size should be less that 255")
                    exit(1)
    for i in data:
        hex_data.append(i[2:])

    manipulate_hex(hex_file)
    bak_file = open(f"{hex_file}.bak", "r")
    source_file = open(f"{hex_file}", "w")
    for line in bak_file:
        line = line.strip()
        if line:
            if line.startswith("@"):
                if first_line > 0:
                    source_file.write(f"{line}\n")
                    first_line = first_line - 1
                else:
                    source_file.write(f"{line}\n")
                    flag = True
            elif flag == False:
                source_file.write(f"{line}\n")
            elif flag == True:
                count = 0
                for d in hex_data:
                    if count < 16:
                        new_hex_data = new_hex_data + " " + d
                        count = count + 1
                    else:
                        source_file.write(f"{new_hex_data[1:]}\n")
                        new_hex_data = ""
                        count = 1
                        new_hex_data = new_hex_data + " " + d
                while len(new_hex_data[1:].split()) < 16:
                    new_hex_data = new_hex_data + " " + "00"
                source_file.write(f"{new_hex_data[1:]}\n")
                source_file.write(
                    f"{str(hex(int(arr_size)))[2:].capitalize()} 00 00 00 00 00 00 00 \n"
                )
                break
    bak_file.close()
    source_file.close()


def exec_flash(test):
    print("   Flashing CPU")
    test.apply_reset()
    test.powerup_sequence()
    test.flash(f"{test.test_name}.hex")
    test.powerup_sequence()
    test.release_reset()


def run_test(test):
    phase = 0
    io_pulse = 0
    rst = 0
    end_pulses = 0
    while end_pulses < 2:
        pulse_count = test.receive_packet()
        if phase == 0 and pulse_count == 1:
            print("Start test")
            phase = phase + 1
        elif phase > 0 and pulse_count == 1:
            rst = rst + 1
            end_pulses = end_pulses + 1
        elif pulse_count > 1:
            end_pulses = 0
            if rst < 2:
                channel = (pulse_count - 2) + (9 * rst)
            elif rst == 2:
                channel = 37 - (pulse_count - 2)
            elif rst == 3:
                channel = 28 - (pulse_count - 2)
            phase = phase + 1
            print(f"start sending pulses to gpio[{channel}]")
            state = "HI"
            timeout = time.time() + 0.5
            accurate_delay(12.5)
            while 1:
                accurate_delay(25)
                x = Dio(channel).get_value()
                if state == "LOW":
                    if x == True:
                        state = "HI"
                elif state == "HI":
                    if x == False:
                        state = "LOW"
                        io_pulse = io_pulse + 1
                if io_pulse == 4:
                    io_pulse = 0
                    print(f"gpio[{channel}] Passed")
                    break
                if time.time() > timeout:
                    print(f"Timeout failure on gpio[{channel}]!")
                    return False, channel
    return True, None


def change_config(channel, gpio_l, gpio_h, voltage, start_time, test):
    end_time = (time.time() - start_time) / 60.0
    if channel > 18:
        if gpio_h.get_config(37 - channel) == "H_INDEPENDENT":
            gpio_h.set_config(37 - channel, "H_DEPENDENT")
            gpio_h.increment_fail_count(37 - channel)
        elif gpio_h.get_config(37 - channel) == "H_DEPENDENT":
            gpio_h.set_config(37 - channel, "H_INDEPENDENT")
            gpio_h.increment_fail_count(37 - channel)
        if gpio_h.get_fail_count(37 - channel) > 1:
            gpio_h.gpio_failed()
            print(f"gpio[{channel}] not working")
            print("Final configuration for gpio_l: ", gpio_l.array)
            print("Final configuration for gpio_h: ", gpio_h.array)
            print(
                "Configuring the ios took: ",
                (time.time() - start_time) / 60.0,
                "minutes",
            )
            f = open(f"configuration.txt", "a")
            f.write(f"voltage: {voltage}\n")
            f.write("Final configuration: \n")
            f.write(
                f"configuration failed in gpio[{channel}], anything after is invalid\n"
            )
            f.write(f"gpio from 37 to 19: {gpio_h.array}\n")
            f.write(f"Execution time: {end_time} minutes\n")
            f.close()
            test.turn_off_devices()

    else:
        if gpio_l.get_config(channel) == "H_INDEPENDENT":
            gpio_l.set_config(channel, "H_DEPENDENT")
            gpio_l.increment_fail_count(channel)
        elif gpio_l.get_config(channel) == "H_DEPENDENT":
            gpio_l.set_config(channel, "H_INDEPENDENT")
            gpio_l.increment_fail_count(channel)
        if gpio_l.get_fail_count(channel) > 1:
            gpio_l.gpio_failed()
            print(f"gpio[{channel}] not working")
            print("Final configuration for gpio_l: ", gpio_l.array)
            print("Final configuration for gpio_h: ", gpio_h.array)
            print(
                "Configuring the ios took: ",
                (time.time() - start_time) / 60.0,
                "minutes",
            )
            f = open(f"configuration.txt", "a")
            f.write(f"voltage: {voltage}\n")
            f.write("Final configuration: \n")
            f.write(
                f"configuration failed in gpio[{channel}], anything after is invalid\n"
            )
            f.write(f"gpio from 0 to 18: {gpio_l.array}\n")
            f.write(f"Execution time: {end_time} minutes\n")
            f.close()
            test.turn_off_devices()
    return gpio_l, gpio_h


def choose_test(
    test,
    test_name,
    gpio_l,
    gpio_h,
    start_time,
    chain="low",
    high=False
):
    test_result = False
    while not test_result:
        test.test_name = test_name
        run_builder(gpio_l.array, gpio_h.array)
        modify_hex(
            f"{test_name}.hex",
            "gpio_config_data.c",
        )
        exec_flash(test)
        if not high:
            test_result, channel_failed = run_test(test)
        else:
            test_result, channel_failed = run_test(test)
        if test_result:
            print("Test Passed!")
            print("Final configuration for gpio_l: ", gpio_l.array)
            print("Final configuration for gpio_h: ", gpio_h.array)
            test_passed(test, start_time, gpio_l, gpio_h, chain)
        else:
            gpio_l, gpio_h = change_config(
                channel_failed, gpio_l, gpio_h, test.voltage, start_time, test
            )
        if gpio_h.get_gpio_failed() is True or gpio_l.get_gpio_failed() is True:
            break


def test_passed(test, start_time, gpio_l, gpio_h, chain):
    end_time = (time.time() - start_time) / 60.0

    print("Configuring the ios took: ", end_time, "minutes")

    f = open(f"configuration.txt", "a")
    f.write(f"voltage: {test.voltage}\n")
    f.write(f"configuration of {chain} chain was successful\n")
    f.write(f"Final configuration of {chain} chain: \n")
    if chain == "low":
        f.write(f"gpio from 0 to 18: {gpio_l.array}\n")
    elif chain == "high":
        f.write(f"gpio from 37 to 19: {gpio_h.array}\n")
    f.write(f"Execution time: {end_time} minutes\n")
    f.close()


if __name__ == "__main__":

    test = Test()
    gpio_l = Gpio()
    gpio_h = Gpio()

    start_time = time.time()
    start_program = time.time()
    global pid
    pid = None

    if os.path.exists(f"./configuration.txt"):
        os.remove(f"./configuration.txt")

    choose_test(test, "config_io_o_l", gpio_l, gpio_h, start_time)

    gpio_l = Gpio()
    gpio_h = Gpio()
    start_time = time.time()
    choose_test(test, "config_io_o_h", gpio_l, gpio_h, start_time, "high", True)

    end_time = (time.time() - start_program) / 60.0
    f = open(f"configuration.txt", "a")
    f.write(f"\n\nTotal Execution time: {end_time} minutes")
    f.close()
    test.close_devices()
    exit(0)
