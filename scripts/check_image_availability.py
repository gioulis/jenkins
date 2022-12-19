#!/usr/bin/env python3
'''
 Script for pulling orchestrator service images before
 calling local-stack.sh up and report any missing images

  +-------+           +-------------+
  |       |    ssh    |             |
  | node  |---------->| local-stack |
  |       |           |             |
  +-------+           +-------------+

  -h, --help  show this help message and exit
  -i I        VM ip where local-stack is running
  -u U        VM username
  -p P        VM password
  -r R        Docker registry for Orchestrator services

'''
import re
import sys
import argparse
import paramiko
import time

# Parse Arguments
parser = argparse.ArgumentParser(description='Provides information about local-stack health and status.')
parser.add_argument('-i', "--ip_address", type=str, required=True, help='VM ip where local-stack is running')
parser.add_argument('-u', "--username", type=str, required=True, help='VM username')
parser.add_argument('-p', "--password", type=str, required=True, help='VM password')
parser.add_argument('-r', "--services_registry", type=str, required=True, help='Docker registry for Orchestrator services')
args = parser.parse_args()

ls_basepath = '/local-stack'
vm_ip = args.ip_address
vm_user = args.username
vm_pass = args.password
services_registry = args.services_registry

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

def ensure_docker_installed():
    cmd = f"docker -v &>/dev/null; echo $?"
    for i in range(30):
        stdin, stdout, stderr = ssh_handle.exec_command(cmd)
        out = stdout.readlines()
        if int(out[0].strip()) == 127:
            print("Docker is not yet available")
            time.sleep(10)
            continue
        break
    return True

def get_image_list():
    image_list = []
    cmd = f"grep sdwan-services-{services_registry} {ls_basepath}/settings.env"
    while not image_list:
        stdin, stdout, stderr = ssh_handle.exec_command(cmd)
        out = stdout.readlines()
        for line in out:
            line = line.strip().replace(' \\', '').split(':')
            url = line[2] + ":" + line[3]
            image_list.append(url)
        if image_list:
            break
        print("Settings file not found")
        time.sleep(10)
    return image_list

not_found = []
def pull_images(image_list):
    for item in image_list:
        cmd = f"docker pull {item}"
        print("Pulling image: {}".format(item))
        stdin, stdout, stderr = ssh_handle.exec_command(cmd)
        err = stderr.readlines()
        if len(err) > 0:
            err = err[0].strip()
        if any(word in err for word in ['Error', 'not found', 'manifest unknown']):
            print("Image not found: {}".format(err))
            not_found.append(item)
    if len(not_found) > 0:
        return False
    return True

if __name__ == "__main__":
    ensure_docker_installed()
    image_list = get_image_list()
    if not pull_images(image_list):
        print("The following images were not available in the registry: ", *not_found, sep = "\n")
        sys.exit(1)


