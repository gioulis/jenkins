#!/usr/bin/env python3
'''
 Script that if needed:
 1. Edits sdwan_release file
    in a VM where local-stack runs
 2. Stops local-stack
 3. Starts local-stack with options: -l onprem -p sdwan_release

  +-------+           +-------------+
  |       |    ssh    |             |
  | node  |---------->| local-stack |
  |       |           |             |
  +-------+           +-------------+

  -h, --help  show this help message and exit
  -i I        VM ip where local-stack is running
  -u U        VM username
  -p P        VM password
  -b R        SDWAN build

'''
import time
import sys
import re
import pathlib
import argparse
import paramiko

LS_BASEPATH = '/local-stack'

def main(script_namespace):
    vm_ip = script_namespace.i
    vm_user = script_namespace.u
    vm_pass = script_namespace.p
    build = script_namespace.b

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm_ip, username=vm_user, password=vm_pass, allow_agent=False)

        print('Checking and adding entry')
        cmd = f"if grep -q '{build}' {LS_BASEPATH}/sdwan_release;then >&2 echo '{build} already exists';else echo {build} >> {LS_BASEPATH}/sdwan_release;fi"
        stdin, stdout, stderr = client.exec_command(cmd)
        for line in stderr.readlines():
            print(line)
            if 'already exists' in line:
                release_exists = True
                print('....')
        if stdout.channel.recv_exit_status():
            sys.exit('Could not check for ' + release)

        
        print("Checking existence of sdwan build")
        major = build.split('_')[0]
        minor = build.split('_')[1]
        version_path = f"{LS_BASEPATH}/sdwan_releases/{build}"
        cmd = f"[ -d {version_path} ]"
        stdin, stdout, stderr = client.exec_command(cmd)
        if stdout.channel.recv_exit_status():
            print(f"Downloading and publishing sdwan build")
            cmd = f"mkdir -p {version_path} && {LS_BASEPATH}/buildManager/publish-sdwan.sh {major} {minor} -d {version_path} -o linux"
            stdin, stdout, stderr = client.exec_command(cmd)
            for line in stdout.readlines():
                print(line)
            if stdout.channel.recv_exit_status():
                print(f"Could not publish sdwan build, deleting directory {version_path} ...")
                cmd = f"rm -rf {version_path}"
                stdin, stdout, stderr = client.exec_command(cmd)
                if stdout.channel.recv_exit_status():
                    sys.exit('Could not delete the directory')
                else:
                    sys.exit()
        else:
            print(f"sdwan build {build} already exists")
            sys.exit()



        print('Bringing down local-stack')
        cmd = f"cd {LS_BASEPATH} && ./local-stack.sh down"
        stdin, stdout, stderr = client.exec_command(cmd)
        while True:
            print(stdout.readline())
            if stdout.channel.exit_status_ready():
                break

        cmd = f"cat {LS_BASEPATH}/status_file"
        status_down = False
        while status_down is False:
            stdin, stdout, stderr = client.exec_command(cmd)
            for line in stdout.readlines():
                print(line)
                if 'Down' in line:
                    status_down = True
            time.sleep(5)


        print('Bringing up local-stack')
        cmd = f"cd {LS_BASEPATH} && ./local-stack.sh up -i {vm_ip} -l onprem -p sdwan_release > local-stack-logs.out 2>&1 &"
        stdin, stdout, stderr = client.exec_command(cmd)
        while not stdout.channel.exit_status_ready():
            pass


        cmd = f"cat {LS_BASEPATH}/status_file"
        status_up = False
        while status_up is False:
            stdin, stdout, stderr = client.exec_command(cmd)
            for line in stdout.readlines():
                print(line)
                if line == "UP\n":
                    status_up = True
            time.sleep(20)


        client.close()
    except paramiko.AuthenticationException:
        sys.exit('Authentication failed')
    except paramiko.ssh_exception.BadHostKeyException:
        sys.exit('Host key could not be verified')
    except paramiko.SSHException:
        sys.exit('Unable to establish SSH connection')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Add sdwan build in local-stack')
    parser.add_argument('-i', help='VM ip where local-stack is running', required=True)
    parser.add_argument('-u', help='VM username', required=True)
    parser.add_argument('-p', help='VM password', required=True)
    parser.add_argument('-b', help='SDWAN build', required=True)
    script_namespace = parser.parse_args()

    # Check IP validity
    pattern = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if not pattern.match(script_namespace.i):
        sys.exit('Invalid local-stack IP')

    # Check build validity
    pattern = re.compile("^\d{1,2}\.\d{1,2}\.\d{1,2}_\d{1,5}$")
    if not pattern.match(script_namespace.b):
        sys.exit('Invalid build format i.e. 11.2.2_14')

    main(script_namespace)

