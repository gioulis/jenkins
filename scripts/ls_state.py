#!/usr/bin/env python3
'''
 Script that provides feedback about local-stack health and
 information about the status of the current deployment

  +-------+           +-------------+
  |       |    ssh    |             |
  | node  |---------->| local-stack |
  |       |           |             |
  +-------+           +-------------+

  -h, --help  show this help message and exit
  -i I        VM ip where local-stack is running
  -u U        VM username
  -p P        VM password
  -a A        Action - Available choices=['health', 'status', 'all']

'''
import time
import sys
import re
import pathlib
import argparse
import paramiko

# Parse Arguments
parser = argparse.ArgumentParser(description='Provides information about local-stack health and status.')
parser.add_argument('-i', "--ip_address", type=str, required=True, help='VM ip where local-stack is running')
parser.add_argument('-u', "--username", type=str, required=True, help='VM username')
parser.add_argument('-p', "--password", type=str, required=True, help='VM password')
parser.add_argument('-a', "--action", choices=['health', 'status', 'all'], type=str, required=False, default="all", help='Action (default: all)')
args = parser.parse_args()

ls_basepath = '/local-stack'
vm_ip = args.ip_address
vm_user = args.username
vm_pass = args.password
action = args.action

# Check IP validity
pattern = re.compile("^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
if not pattern.match(vm_ip):
    sys.exit('Invalid local-stack IP')

try:
    ssh_handle = paramiko.SSHClient()
    ssh_handle.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh_handle.connect(vm_ip, username=vm_user, password=vm_pass, allow_agent=False)
except paramiko.AuthenticationException:
    sys.exit('Authentication failed')
except paramiko.ssh_exception.BadHostKeyException:
    sys.exit('Host key could not be verified')
except paramiko.SSHException:
    sys.exit('Unable to establish SSH connection')

def get_image_list():
    cmd = f"docker inspect --format='{{{{.Name}}}} {{{{.Image}}}}' $(docker ps -aq)"
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    print("\nDocker containers and image IDs:\n")
    for line in stdout.readlines():
        print(line.strip())

def get_sw_versions():
    cmd = f"cat {ls_basepath}/sdwan_release"
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    print("\nSupported SDWAN appliance software versions:\n")
    for line in stdout.readlines():
        print(line.strip())

def get_ls_mode():
    cmd = f"ps -ef | grep local-stack | grep -v grep | awk '{{print $14}}'"
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    print("\nLocal-stack is running in mode:\n")
    for line in stdout.readlines():
        print(line.strip())

def commits_behind_remote_counterpart():
    cmd = f"cd {ls_basepath}; git fetch; git rev-list --left-right --count origin/development...development | awk '{{print $1}}'"
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    print("\nLocal development branch of current local-stack deployment is behind it's remote counterpart by:\n")
    for line in stdout.readlines():
        print(line.strip()+" commits")

def ls_up():
    print("Polling status_file")
    cmd = f"cat {ls_basepath}/status_file"
    status_up = False
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    for line in stdout.readlines():
        if line == "UP\n":
            status_up = True
    if status_up:
        print("Localstack status is up")
        return True
    print("Localstack status is down")
    return False

def ls_ui_up():
    cmd = f"curl -fsS http://localhost > /dev/null"
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    out = stdout.readlines()
    if len(out) == 0:
        print("Localstack UI is up")
        return True
    print("Localstack UI is down")
    return False

def ls_containers():
    cmd = f"curl -s --unix-socket /var/run/docker.sock http://localhost/containers/json | jq '. | length'"
    stdin, stdout, stderr = ssh_handle.exec_command(cmd)
    count = stdout.readlines()[0].strip()
    print("Running local-stack containers: {}".format(count))
    return int(count)

def get_ls_health():
    if ls_up() and ls_ui_up() and ls_containers() == 34:
        print("\nLocalstack health: OK")
        return True
    print("\nLocalstack health: UNHEALTHY")
    return False

def get_ls_status():
    get_ls_mode()
    commits_behind_remote_counterpart()
    get_sw_versions()
    get_image_list()

def main():
    if action == "health":
        get_ls_health()

    if action == "status":
        get_ls_status()

    if action == "all":
        get_ls_health()
        get_ls_status()

if __name__ == "__main__":
    main()

