import pyshark
import sys
import ipaddress
from filter import Filter


class Result:
    def __init__(self, tag, comment):
        self.tag = tag
        self.comment = comment


class Probability:
    def __init__(self, device_type, value):
        self.device_type = device_type
        self.value = value


def calculate_heartbeat(cap_sum):  # use cap_sum
    time_differences = []
    for i in range(1, len(cap_sum)):
        time_differences.append(float(cap_sum[i].time) - float(cap_sum[i-1].time))
    heartbeat = sum(time_differences) / (len(cap_sum) - 1)
    return heartbeat


def calculate_upload_and_download_ratio(ip, cap):  # use cap
    upload_size = 0
    download_size = 0
    for pkt in cap:
        try:
            if ipaddress.ip_address(pkt.ip.src).is_multicast or ipaddress.ip_address(pkt.ip.dst).is_multicast:
                continue
            elif pkt.ip.src == '255.255.255.255' or pkt.ip.dst == '255.255.255.255':
                continue
            elif pkt.ip.src == ip:
                upload_size = upload_size + int(pkt.length)
            elif pkt.ip.dst == ip:
                download_size = download_size + int(pkt.length)
        except AttributeError:
                pass

    upload_ratio = upload_size / (upload_size + download_size)
    download_ratio = download_size / (download_size + upload_size)
    return upload_ratio, download_ratio


def calculate_local_and_global_packets_ratio(cap):  # use cap
    local_packets = 0
    multicast_packets = 0
    global_packets = 0
    for pkt in cap:
        try:
            if ipaddress.ip_address(pkt.ip.src).is_private and ipaddress.ip_address(pkt.ip.dst).is_private:
                local_packets = local_packets + 1
            elif ipaddress.ip_address(pkt.ip.src).is_multicast or ipaddress.ip_address(pkt.ip.dst).is_multicast:
                multicast_packets = multicast_packets + 1
            else:
                global_packets = global_packets + 1
        except AttributeError:
                pass
    total_packets = local_packets + multicast_packets + global_packets
    local_packets_ratio = local_packets / total_packets
    global_packets_ratio = global_packets / total_packets
    return local_packets_ratio, global_packets_ratio


def calculate_data_rate(cap_sum):  # use cap_sum
    time = []
    cumulative_size = 0
    for pkt in cap_sum:
        time.append(pkt.time)
        cumulative_size = cumulative_size + float(pkt.length)
    total_time = float(time[-1]) - float(time[0])
    data_rate = cumulative_size / total_time
    return data_rate


def generate_protocol_list(cap_sum):  # use cap_sum
    protocols = []
    for pkt in cap_sum:
        for protocol in protocols:
            if protocol == pkt.protocol:
                break
        else:
            protocols.append(pkt.protocol)
    return protocols


def use_tuya_api(cap):  # use cap
    for pkt in cap:
        try:
            protocol = pkt.transport_layer
            dst_port = pkt[pkt.transport_layer].dstport
            if protocol == "UDP" and dst_port == "6666":
                return 1
        except AttributeError:  # ignore packets that aren't TCP/UDP or IPv4
            pass
    else:
        return 0


def has_public_ip(mac, cap):
    for pkt in cap:
        try:
            if (pkt.eth.src == mac and ipaddress.ip_address(pkt.ip.src).is_global) or (
                    pkt.eth.dst == mac and ipaddress.ip_address(pkt.ip.dst).is_global):
                return 1
        except AttributeError:
            pass
    else:
        return 0


def is_encrypted(protocols):
    for protocol in protocols:
        if protocol == 'TLSv1.2' or protocol == 'TLSv1':
            return 1
    return 0


def is_lightweight(protocols):
    for protocol in protocols:
        if protocol == 'MQTT':
            return 1
    return 0


def is_iot(protocols):
    for protocol in protocols:
        if protocol == 'MDNS':
            return 1
    return 0


def is_upnp(protocols):
    for protocol in protocols:
        if protocol == 'SSDP':
            return 1
    return 0


def is_time_synchronizer(protocols):
    for protocol in protocols:
        if protocol == 'NTP':
            return 1
    return 0


def is_unreliable(protocols):
    for protocol in protocols:
        if protocol == 'UDP':
            return 1
    return 0


def is_low_local_ratio(local_packets_ratio):
    if local_packets_ratio < 0.1:
        return 1
    else:
        return 0


def is_medium_local_ratio(local_packets_ratio):
    if 0.1 <= local_packets_ratio <= 0.3:
        return 1
    else:
        return 0


def is_high_local_ratio(local_packets_ratio):
    if local_packets_ratio > 0.3:
        return 1
    else:
        return 0


def is_talkative(data_rate, heartbeat):
    if data_rate > 500 and heartbeat < 1:
        return 1
    else:
        return 0


def is_neither_talkative_nor_shy(data_rate, heartbeat):
    if 90 <= data_rate <= 500 or 1 <= heartbeat <= 3:
        return 1
    else:
        return 0


def is_shy(data_rate, heartbeat):
    if data_rate < 90 and heartbeat > 3:
        return 1
    else:
        return 0


def is_uploader(upload_ratio, download_ratio):
    if upload_ratio - download_ratio >= 0.45:
        return 1
    else:
        return 0


def is_neither_uploader_nor_downloader(upload_ratio, download_ratio):
    if abs(upload_ratio - download_ratio) < 0.45:
        return 1
    else:
        return 0


def is_downloader(upload_ratio, download_ratio):
    if download_ratio - upload_ratio >= 0.45:
        return 1
    else:
        return 0


def check_premium():
    if has_public_ip(mac, cap):
        return 0
    else:
        premium_probability = 0.5 * is_medium_local_ratio(local_ratio) + 0.15 * is_encrypted(protocol_list) \
                              + 0.2 * is_talkative(data_rate, heartbeat) + 0.15 * is_time_synchronizer(protocol_list)
        return premium_probability


def check_bulb():
    if has_public_ip(mac, cap):
        return 0
    else:
        bulb_probability = 0.45 * is_low_local_ratio(local_ratio) + 0.35 * is_iot(protocol_list) \
                           + 0.2 * is_shy(data_rate, heartbeat) \
                           + 0.2 * is_neither_talkative_nor_shy(data_rate, heartbeat)
        return bulb_probability


def check_strip():
    if has_public_ip(mac, cap):
        return 0
    else:
        strip_probability1 = 0.8 * is_lightweight(protocol_list) + 0.1 * is_unreliable(protocol_list) \
                             + 0.1 * is_iot(protocol_list)
        strip_probability2 = 0.8 * is_high_local_ratio(local_ratio) + 0.2 * is_iot(protocol_list)
        if strip_probability1 > strip_probability2:
            return strip_probability1
        else:
            return strip_probability2


def check_camera():
    if has_public_ip(mac, cap):
        return 0
    else:
        camera_probability = 0.6 * is_uploader(upload_ratio, download_ratio) + 0.4 * is_talkative(data_rate, heartbeat)
        return camera_probability


def check_router():
    return has_public_ip(mac, cap)


def continue_or_exit():
    while True:
        try:
            print()
            choice = input("Do you want to profile another device in the same .pcap file? (y/n) ")
            if choice == 'y' or choice == 'Y':
                return
            elif choice == 'n' or choice == 'N':
                print("Thanks for using. Goodbye!")
                exit()
            else:
                raise ValueError
        except ValueError:
            print("Invalid input! Please try again.")


def add_tags(manufacturer):
    print("Now profiling: " + manufacturer, end='', flush=True)
    if use_tuya_api(cap):
        results.append(Result("Tuya IoT Platform", "Using Tuya API"))
    if has_public_ip(mac, cap):
        results.append(Result("Has public IP", "Has public IP associated with MAC"))
    if is_uploader(upload_ratio, download_ratio):
        results.append(Result("Uploader", "Upload % = {:.2f}%, Download % = {:.2f}%".format(upload_ratio * 100, download_ratio * 100)))
    if is_neither_uploader_nor_downloader(upload_ratio, download_ratio):
        results.append(Result("Neither uploader nor downloader", "Upload % = {:.2f}%, Download % = {:.2f}%".format(upload_ratio * 100, download_ratio * 100)))
    if is_downloader(upload_ratio, download_ratio):
        results.append(Result("Downloader", "Upload % = {:.2f}%, Download % = {:.2f}%".format(upload_ratio * 100, download_ratio * 100)))
    if is_iot(protocol_list):
        results.append(Result("IoT", "Using MDNS Protocol"))
    if is_unreliable(protocol_list):
        results.append(Result("Has unreliable traffic", "Using UDP Protocol"))
    if is_lightweight(protocol_list):
        results.append(Result("Lightweight", "Using MQTT Protocol"))
    if is_upnp(protocol_list):
        results.append(Result("Universal plug and play", "Using SSDP Protocol"))
    if is_encrypted(protocol_list):
        results.append(Result("Encrypted", "Using TLSv1 or TLSv1.2 Protocol"))
    if is_time_synchronizer(protocol_list):
        results.append(Result("Time synchronizer", "Using NTP Protocol"))
    if is_high_local_ratio(local_ratio):
        results.append(Result("High local packets ratio", "Local % = {:.2f}%, Global % = {:.2f}%".format(local_ratio * 100, global_ratio * 100)))
    if is_medium_local_ratio(local_ratio):
        results.append(Result("Medium local packets ratio", "Local % = {:.2f}%, Global % = {:.2f}%".format(local_ratio * 100, global_ratio * 100)))
    if is_low_local_ratio(local_ratio):
        results.append(Result("Low local packets ratio", "Local % = {:.2f}%, Global % = {:.2f}%".format(local_ratio * 100, global_ratio * 100)))
    if is_talkative(data_rate, heartbeat):
        results.append(Result("Talkative", "Data Rate = {:.2f}B/s, Heartbeat = {:.2f}s".format(data_rate, heartbeat)))
    if is_neither_talkative_nor_shy(data_rate, heartbeat):
        results.append(Result("Neither talkative nor shy", "Data Rate = {:.2f}B/s, Heartbeat = {:.2f}s".format(data_rate, heartbeat)))
    if is_shy(data_rate, heartbeat):
        results.append(Result("Shy", "Data Rate = {:.2f}B/s, Heartbeat = {:.2f}s".format(data_rate, heartbeat)))
    print("...Done")


def print_tags():
    print()
    print('{:^78s}'.format("Profiling Result"))
    print('------------------------------------------------------------------------------')
    print('| {:^31s} | {:^40s} |'.format("Tag", "Comment"))
    print('------------------------------------------------------------------------------')
    for result in results:
        print('| {:^31s} | {:^40s} |'.format(result.tag, result.comment))
        print('------------------------------------------------------------------------------')
    print()


def calculate_probabilities(manufacturer):
    print("Now calculating probabilities for: " + manufacturer, end='', flush=True)
    probabilities.append(Probability("Router", "{:.2f}%".format(check_router() * 100)))
    probabilities.append(Probability("Voice Assistant", "{:.2f}%".format(check_premium() * 100)))
    probabilities.append(Probability("Bulb", "{:.2f}%".format(check_bulb() * 100)))
    probabilities.append(Probability("Strip", "{:.2f}%".format(check_strip() * 100)))
    probabilities.append(Probability("Camera", "{:.2f}%".format(check_camera() * 100)))
    print("...Done")


def print_probabilities():
    print()
    print('{:^29s}'.format("Probable Type"))
    print('-----------------------------')
    print('| {:^15s} | {:^7s} |'.format("Device Type", "Value"))
    print('-----------------------------')
    for probability in probabilities:
        print('| {:^15s} | {:^7s} |'.format(probability.device_type, probability.value))
        print('-----------------------------')


if __name__ == "__main__":
    unfiltered_cap = pyshark.FileCapture(sys.argv[1])
    unfiltered_cap_sum = pyshark.FileCapture(sys.argv[1], only_summaries=True)
    pkt_filter = Filter(unfiltered_cap, unfiltered_cap_sum)

    pkt_filter.create_device_list()
    while True:
        results = []
        probabilities = []
        pkt_filter.print_device_list()
        pkt_filter.ask_for_device()
        cap, cap_sum = pkt_filter.filter_packets()
        ip = pkt_filter.get_profile_device_ip()
        mac = pkt_filter.get_profile_device_mac()
        manufacturer = pkt_filter.get_profile_device_manufacturer()

        upload_ratio, download_ratio = calculate_upload_and_download_ratio(ip, cap)
        protocol_list = generate_protocol_list(cap_sum)
        local_ratio, global_ratio = calculate_local_and_global_packets_ratio(cap)
        data_rate = calculate_data_rate(cap_sum)
        heartbeat = calculate_heartbeat(cap_sum)

        add_tags(manufacturer)
        print_tags()

        calculate_probabilities(manufacturer)
        print_probabilities()

        continue_or_exit()
