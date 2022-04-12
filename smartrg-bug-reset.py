import datetime
import os
import time

import paramiko
from paramiko.ssh_exception import SSHException
import multiprocessing

router_host = '192.168.1.1'
username = 'admin'
password = 'Adm1n@L1m3#'
service_name = 'pppoe_0_0_1'
service_timeout = 10.0
check_interval = 1
dns_check = True
dns_timeout = 15
use_ping = True
reboot_wait = 60  # time to wait after reboot
#ssh_port = 22
#time_between_reboot = 3 * 60


def dns_process_func(q):
    q.put(dns_connection_check())


def main():
    while True:
        try:
            if use_ping:
                print('Checking connectivity to router {0} using ping'.format(router_host))
                ping_wait(router_host)
                print('Able to reach router!')
            print('Attempting to connect to router {0} as user {1}'.format(router_host, username))
            client = connect(router_host, username, password)
            print('Connected to router! {0}'.format(datetime.datetime.now()))
            time.sleep(reboot_wait)
            while True:
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
                            client = reboot_router(client)
                        time.sleep(0.1)
                        time_waiting = time_waiting + 0.1
                        ip, status = get_wan_service_info(client, service_name)

                    if dns_check:
                        print('Checking DNS Status with timeout of {0}s'.format(dns_timeout))
                        q = multiprocessing.Queue()
                        p = multiprocessing.Process(target=dns_process_func, args=(q,))
                        p.start()
                        try:
                            if not q.get(timeout=dns_timeout):
                                raise Exception
                            print('DNS Available!')
                        except Exception as e:
                            print(e)
                            print("Timeout of {0}s reached or wrong answer for DNS, rebooting...".format(dns_timeout))
                            # client = reboot_router(client)
                    print()

                    time.sleep(check_interval)
                except Exception as e:
                    print(e)
                    break
        except Exception as e:
            print(e)
            continue


def reboot_router(client):
    ssh_reboot(client)
    if use_ping:
        ping_wait(router_host)
    time.sleep(reboot_wait)
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
            print(e)
        except Exception:
            continue
        time.sleep(0.5)
        time_waiting = time_waiting + 0.5


def ping_wait(host):
    while os.system("ping -c 1 {0} > {1} 2>&1".format(host, os.devnull)) != 0:
        time.sleep(0.1)


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


def banner():
    print("----------------------------------")
    print("SmartRG Router Bug Reset Tool v0.1")
    print("----------------------------------")
    print()


if __name__ == '__main__':
    banner()
    main()


def dns_connection_check():
    return 'answer' in os.popen('nslookup myip.opendns.com resolver1.opendns.com').read()
