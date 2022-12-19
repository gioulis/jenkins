#!/usr/bin/env python3
'''
 Script that:
 1. Copies sdwan script(utm_log_daemon)
    in a VM where local-stack runs
 2. Publishes sdwan script

  +-------+           +-------------+
  |       |    ssh    |             |
  | node  |---------->| local-stack |
  |       |           |             |
  +-------+           +-------------+

  -h, --help  show this help message and exit
  -i I        VM ip where local-stack is running
  -u U        VM username
  -p P        VM password
  -f F        script filepath

'''
import sys
import pathlib
import argparse
import paramiko

LOCALSTACK_BASEPATH = '/local-stack'

def main(script_namespace):
    script_file = pathlib.Path(script_namespace.f)
    script_name = script_file.name
    vm_ip = script_namespace.i
    vm_user = script_namespace.u
    vm_pass = script_namespace.p


    if not script_file.exists ():
        sys.exit('No file found')

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm_ip, username=vm_user, password=vm_pass, allow_agent=False)
        sftp_client = client.open_sftp()
        sftp_client.put(script_file, f"{LOCALSTACK_BASEPATH}/publish/scripts/{script_name}")
        
        cmd = "ip -4 addr show dev docker0 | grep \"inet \" | awk \'{print $2}\' | cut -d/ -f1"
        stdin, stdout, stderr = client.exec_command(cmd)
        docker_bridge_ip = stdout.readlines()[0].rstrip()
        if not docker_bridge_ip:
            sys.exit('Could not get docker bridge ip')

        cmd = f"export INTERNAL_HOST_IP={docker_bridge_ip} && cd {LOCALSTACK_BASEPATH} && ./buildManager/publish-scripts.sh linux && ./publish/local-publish.sh"
        stdin, stdout, stderr = client.exec_command(cmd)
        for line in stderr.readlines():
            print(line)
        if stdout.channel.recv_exit_status():
            sys.exit('Could not publish script')
        client.close()
    except paramiko.AuthenticationException:
        sys.exit('Authentication failed')
    except paramiko.ssh_exception.BadHostKeyException:
        sys.exit('Host key could not be verified')
    except paramiko.SSHException:
        sys.exit('Unable to establish SSH connection')
    except IOError as e:
        sys.exit('Could not copy script file' + e)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Publish sdwan script in local-stack')
    parser.add_argument('-i', help='VM ip where local-stack is running', required=True)
    parser.add_argument('-u', help='VM username', required=True)
    parser.add_argument('-p', help='VM password', required=True)
    parser.add_argument('-f', help='script filepath', required=True)
    script_namespace = parser.parse_args()

    main(script_namespace)

