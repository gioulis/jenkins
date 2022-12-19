#!/usr/bin/env python3
'''
 Script that polls status_file of local-stack until is UP
 and sdwan-ae-utm.zip for last line of sdwan_release file
 is published

  +-------+           +-------------+
  |       |    ssh    |             |
  | node  |---------->| local-stack |
  |       |           |             |
  +-------+           +-------------+

  -h, --help  show this help message and exit
  -i I        VM ip where local-stack is running
  -u U        VM username
  -p P        VM password

'''
import time
import sys
import re
import pathlib
import argparse
import paramiko

LS_BASEPATH = '/local-stack'
UTM_BASEPATH = '/root/sdws/minio/download-firmware/auth/SDWAN/'

def main(script_namespace):
    vm_ip = script_namespace.i
    vm_user = script_namespace.u
    vm_pass = script_namespace.p

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm_ip, username=vm_user, password=vm_pass, allow_agent=False)

        print("Poll status_file")
        cmd = f"cat {LS_BASEPATH}/status_file"
        status_up = False
        while status_up is False:
            stdin, stdout, stderr = client.exec_command(cmd)
            status = stdout.readlines()[0]
            print(status)
            if status == "UP\n":
                status_up = True
                break
            elif status.upper() == "DOWN\n":
                grep_cmd = f"grep 'DB migration failed' {LS_BASEPATH}/local-stack-logs.out"
                stdin, stdout, stderr = client.exec_command(grep_cmd)
                out = stdout.readlines()
                if len(out) != 0:
                    sys.exit("DB migration failure. Cannot bring-up localstack")
                sys.exit("Cannot bring-up localstack. Please investigate")
            else:
                time.sleep(60)

        print("Poll sdwan-ae-utm.zip of last line in sdwan_release")
        cmd = f"tail -n 1 {LS_BASEPATH}/sdwan_release"
        stdin, stdout, stderr = client.exec_command(cmd)
        last_version = stdout.readlines()[0].rstrip()
        if not last_version:
            sys.exit('Could not get last version in sdwan_release file')
        formated_last_version = f"{last_version.split('_')[0]}.{last_version.split('_')[1]}"
        cmd = f"ls {UTM_BASEPATH}/{formated_last_version}/sdwan-ae-utm.zip"
        utm_zip_exists = False
        while utm_zip_exists is False:
            stdin, stdout, stderr = client.exec_command(cmd)
            for line in stderr.readlines():
                print(line)
            if stdout.channel.recv_exit_status():
                time.sleep(60)
            else:
                utm_zip_exists = True


        client.close()
    except paramiko.AuthenticationException:
        sys.exit('Authentication failed')
    except paramiko.ssh_exception.BadHostKeyException:
        sys.exit('Host key could not be verified')
    except paramiko.SSHException:
        sys.exit('Unable to establish SSH connection')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Polls status_file of local-stack, until is UP')
    parser.add_argument('-i', help='VM ip where local-stack is running', required=True)
    parser.add_argument('-u', help='VM username', required=True)
    parser.add_argument('-p', help='VM password', required=True)
    script_namespace = parser.parse_args()

    # Check IP validity
    pattern = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if not pattern.match(script_namespace.i):
        sys.exit('Invalid local-stack IP')

    main(script_namespace)


