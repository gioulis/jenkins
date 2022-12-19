#!/usr/bin/env python3
'''
 Script that:
 1. Copies utm-config-client binary
    in a VM where local-stack runs
 2. Publishes utm-config-client binary

  +-------+           +-------------+
  |       |    ssh    |             |
  | node  |---------->| local-stack |
  |       |           |             |
  +-------+           +-------------+

  -h, --help  show this help message and exit
  -i I        VM ip where local-stack is running
  -u U        VM username
  -p P        VM password
  -f F        utm-config-client filepath
  -s S        sync with publish.git repo

'''
import sys
import pathlib
import argparse
import paramiko

LOCALSTACK_BASEPATH = '/local-stack'

def main(script_namespace):
    binary_file = pathlib.Path(script_namespace.f)
    vm_ip = script_namespace.i
    vm_user = script_namespace.u
    vm_pass = script_namespace.p
    sync_publish = script_namespace.s


    if not binary_file.exists ():
        sys.exit('No file found')

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        client.connect(vm_ip, username=vm_user, password=vm_pass, allow_agent=False)
        sftp_client = client.open_sftp()
        sftp_client.put(binary_file, "/var/tmp/utm-config-client")
        cmd = f"export MINIO_PRESENT=true; export MINIO_ENDPOINT=http://localhost:9000; export MINIO_ACCESS_KEY=minio; export MINIO_SECRET_KEY=minio123; export AWS_REGION=us1; {LOCALSTACK_BASEPATH}/buildManager/buildManager-linux -OPERATION upload -FILE /var/tmp/utm-config-client -PRODUCT=utm-config-client -BUILD=1 -MODEL=utm-config-client -AUTH_REQUIRED=true -UPLOAD_S3_BUCKET=download-firmware"
        stdin, stdout, stderr = client.exec_command(cmd)
        for line in stderr.readlines():
            print(line)
        if stdout.channel.recv_exit_status():
            sys.exit('Could not publish binary')

        if sync_publish == 'false':
            print('No sync with publish.git repo selected')
            sys.exit()

        cmd = f"cd {LOCALSTACK_BASEPATH} && ./update_publish.sh"
        stdin, stdout, stderr = client.exec_command(cmd)
        for line in stderr.readlines():
            print(line)
        if stdout.channel.recv_exit_status():
            sys.exit('Could not clone publish.git repo')
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
            sys.exit('Could not sync with publish.git repo')

        client.close()
    except paramiko.AuthenticationException:
        sys.exit('Authentication failed')
    except paramiko.ssh_exception.BadHostKeyException:
        sys.exit('Host key could not be verified')
    except paramiko.SSHException:
        sys.exit('Unable to establish SSH connection')
    except IOError:
        sys.exit('Could not copy binary file')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Publish utm-config-client in local-stack')
    parser.add_argument('-i', help='VM ip where local-stack is running', required=True)
    parser.add_argument('-u', help='VM username', required=True)
    parser.add_argument('-p', help='VM password', required=True)
    parser.add_argument('-f', help='utm-config-client filepath', required=True)
    parser.add_argument('-s', help='[true|false] sync with publish.git repo', default='true')
    script_namespace = parser.parse_args()

    main(script_namespace)
