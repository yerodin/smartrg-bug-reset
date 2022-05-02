import datetime
import queue
import time

import paramiko
from paramiko.ssh_exception import SSHException
import threading
from subprocess import Popen, DEVNULL, PIPE

router_host = '192.168.1.1'
username = 'admin'
password = 'Adm1n@L1m3#'
service_name = 'pppoe_0_0_1'
service_timeout = 7.0
check_interval = 3
dns_check = True
dns_timeout = 15
use_ping = True
reboot_wait = 50  # time to wait after reboot
startup_wait = 8  # time to wait after first connecting
dns_check_setting = ('myip.opendns.com', 'resolver1.opendns.com')
set_debug_led = True


# ssh_port = 22
# time_between_reboot = 3 * 60


def main():
    while True:
        try:
            if use_ping:
                print('Checking connectivity to router {0} using ping'.format(router_host))
                ping_wait(router_host)
                print('Able to reach router!')
            print('Attempting to connect to router {0} as user {1}'.format(router_host, username))
            client = connect(router_host, username, password)
            if set_debug_led:
                set_debug_led(client)
            print('Connected to router! {0}'.format(datetime.datetime.now()))
            time.sleep(startup_wait)
            while True:
                reboot = False
                if set_debug_led:
                    set_debug_led(client)
                try:
                    print('Checking Status of {0}'.format(service_name))
                    ip, status = get_wan_service_info(client, service_name)
                    print('Public IP: {0}\tStatus: {1} \tTime:{2}'.format(ip, status, datetime.datetime.now()))
                    time_waiting = 0.0
                    if status != 'Connected':
                        print("Router disconnected, waiting {0}s for connection...".format(service_timeout))
                    while status != 'Connected':
                        if time_waiting > service_timeout:
                            print("Timeout of {0}s reached for router service, rebooting...".format(service_timeout))
                            reboot = True
                            break
                        time.sleep(0.1)
                        time_waiting = time_waiting + 0.1
                        ip, status = get_wan_service_info(client, service_name)

                    if not reboot and dns_check:
                        print('Checking DNS Status with timeout of {0}s'.format(dns_timeout))
                        q = queue.LifoQueue()
                        t = threading.Thread(name='dns_check', target=dns_process_func, args=(q,))
                        t.start()
                        try:
                            if not q.get(timeout=dns_timeout):
                                raise Exception
                            print('DNS Available!')
                        except Exception as e:
                            print(e)
                            print("Timeout of {0}s reached or wrong answer for DNS, rebooting and Waiting {1}s before reconnecting to router......".format(dns_timeout, reboot_wait))
                            reboot = True
                    if reboot:
                        client = reboot_router(client)
                    print()
                    if set_debug_led:
                        run_cmd(client, 'setallledon')
                    time.sleep(check_interval)
                except Exception as e:
                    break
        except Exception as e:
            print(e)
            continue


def reboot_router(client):
    ssh_reboot(client)
    time.sleep(reboot_wait)
    if use_ping:
        ping_wait(router_host)
    return connect(router_host, username, password)


def connect(host, u, p, timeout=0):
    connected = False
    time_waiting = 0.0
    while not connected:
        if timeout != 0 and time_waiting > timeout:
            raise TimeoutError
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(host, username=u, password=p)
            return c
        except SSHException as e:
            pass
        except Exception as e:
            pass
        time.sleep(0.5)
        time_waiting = time_waiting + 0.5


def ping_wait(host):
    while True:
        p = Popen(["ping"] + '-c 1 {0}'.format(host).split(), stdout=DEVNULL, stderr=DEVNULL)
        code = p.wait()
        if code == 0:
            break


def get_wan_service_info(ssh_client, service):
    for line in run_cmd(ssh_client, 'wan show service'):
        if '\t' + service + '\t' in line:
            ip = line.split("\t")[-1].replace(" ", '').replace("\n", '')
            status = line.split("\t")[-2].replace(" ", '').replace("\n", '')
            return ip, status
    return None


def ssh_reboot(ssh_client):
    run_cmd(ssh_client, 'reboot')
    ssh_client.close()
    time.sleep(2)


def web_reboot(secure=False):
    pass


def run_cmd(ssh_client, cmd):
    ssh_stdin, ssh_stdout, ssh_stderr = ssh_client.exec_command('')
    ssh_stdin.write('{0}\n'.format(cmd))
    ssh_stdin.close()
    ssh_stdout.flush()
    return ssh_stdout.readlines()


def set_debug_led(ssh_client):
    run_cmd(ssh_client, 'resetethled')
    run_cmd(ssh_client, 'allledoff')
    run_cmd(ssh_client, 'wlctl ledbh 3 0')
    run_cmd(ssh_client, 'allredledon')


def banner():
    print("----------------------------------")
    print("SmartRG Router Bug Reset Tool v0.1")
    print("----------------------------------")
    print()


def dns_connection_check():
    p = Popen(["nslookup"] + '{0} {1}'.format(dns_check_setting[0], dns_check_setting[1]).split(), stdout=PIPE, stderr=DEVNULL)
    p.wait()
    output = str(p.communicate()[0])
    return output is not None and 'answer' in output


def dns_process_func(q):
    q.put(dns_connection_check())


if __name__ == '__main__':
    banner()
    main()
