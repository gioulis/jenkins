#!/usr/bin/env python3
'''
 Script that:
 1. Calculates UVM password
 2. Makes sshd_config changes in order to be able reach UVM
 3. Copies UTM licenses in UVM
 4. Restarts untangle-vm.service


  +------+           +-------------+         +-----+
  |      |           |             |         |     |
  | node |---------->| Branch appl |-------->| UVM |
  |      |           |             |         |     |
  +------+           +-------------+         +-----+

  -h, --help  show this help message and exit
  -i I        sd-wan branch ip
  -u U        sd-wan branch username
  -p P        sd-wan branch password
  -f F        licenses filepath

'''
import re
import sys
from time import sleep
import pathlib
import argparse
import paramiko
import sshtunnel
import json

def main(script_namespace):
    licenses_file = pathlib.Path(script_namespace.f) 
    licenses_filename = licenses_file.name
    sdwan_branch_ip = script_namespace.i
    sdwan_branch_user = script_namespace.u
    sdwan_branch_pass = script_namespace.p

    if not licenses_file.exists ():
        sys.exit('No licenses file found')
    
    with open(licenses_file, 'r') as json_file:
        json_data = json.load(json_file)
        uid = json_data['licenses']['list'][0]['UID']


    try:
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(sdwan_branch_ip, username=sdwan_branch_user, password=sdwan_branch_pass)
        cmd = "/etc/platform/bin/vnf_security_mgr.sh --utm_uuid | cut -d= -f2 |  cut -c 5-23 | sha1sum -t | awk '{print $1}' | cut -c 1-12"
        stdin, stdout, stderr = c.exec_command(cmd)
        uvm_passwd = stdout.readlines()[0].rstrip()
        if not uvm_passwd:
            sys.exit('Could not get UVM password')

        print("Allowing tcp forwarding and tunnel in sshd_conf...")
        cmd = "sudo sed -i -r 's/^(AllowTcpForwarding\s+).*/AllowTcpForwarding yes/' /etc/ssh/sshd_config"
        stdin, stdout, stderr = c.exec_command(cmd)
        if stdout.channel.recv_exit_status():
            sys.exit('Could not allow tcp forwarding')

        cmd = "sudo sed -i -r 's/^(PermitTunnel\s+).*/PermitTunnel yes/' /etc/ssh/sshd_config"
        stdin, stdout, stderr = c.exec_command(cmd)
        if stdout.channel.recv_exit_status():
            sys.exit('Could not permit tunnel')
        
        print("Restarting sshd...")
        cmd = "sudo /etc/init.d/S50sshd restart"
        stdin, stdout, stderr = c.exec_command(cmd)
        c.close()
    except paramiko.AuthenticationException:
        sys.exit('Authentication failed')
    except paramiko.ssh_exception.BadHostKeyException:
        sys.exit('Host key could not be verified')
    except paramiko.SSHException:
        sys.exit('Unable to establish SSH connection')


    print("Sleeping for 10sec...")
    sleep(10)


    print("Checking UTM status...")
    for i in range(20):
        try:
            c = paramiko.SSHClient()
            c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            c.connect(sdwan_branch_ip, username=sdwan_branch_user, password=sdwan_branch_pass)
            cmd = "/etc/platform/bin/vnf_security_mgr.sh --utm_status"
            stdin, stdout, stderr = c.exec_command(cmd)
            utm_status = stdout.readlines()[0].rstrip()
            if utm_status == 'Up':
                print(utm_status)
                c.close()
                break
            else:
                print(utm_status)
                c.close()
                sleep(30)
            if i == 20:
                sys.exit('UTM status: ' + utm_status)
        except paramiko.AuthenticationException:
            sys.exit('Authentication failed')
        except paramiko.ssh_exception.BadHostKeyException:
            sys.exit('Host key could not be verified')
        except paramiko.SSHException:
            print('Unable to establish SSH connection')
            c.close()
            sleep(30)
        except EOFError:
            print('Could not establish connection to remote side of the tunnel')
            c.close()
            sleep(30)

    print('Before ssh_tunnel')
    for i in range(20):
        try:
            with sshtunnel.open_tunnel(
                    (sdwan_branch_ip, 22),
                    ssh_username = sdwan_branch_user,
                    ssh_password = sdwan_branch_pass,
                    remote_bind_address = ("169.254.100.2", 22),
                    local_bind_address = ('0.0.0.0', 20022)
                    ) as tunnel:
                client = paramiko.SSHClient()
                client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
                client.connect('127.0.0.1', 20022, username="root", password=uvm_passwd)
                print("Copying and linking utm licenses...")
                cmd = f"echo {uid} > /usr/share/untangle/conf/uid"
                stdin, stdout, stderr = client.exec_command(cmd)
                if stdout.channel.recv_exit_status():
                    sys.exit('Could not edit uid file')
                
                sftp_client = client.open_sftp()
                sftp_client.put(licenses_file, f"/usr/share/untangle/conf/licenses/{licenses_filename}")
            
                cmd = f"cd /usr/share/untangle/conf/licenses && ln -sf {licenses_filename} licenses.js"
                stdin, stdout, stderr = client.exec_command(cmd)
                if stdout.channel.recv_exit_status():
                    sys.exit('Could not create symlink')
                
                print("Restarting untangle-vm.service...")
                cmd = 'systemctl restart untangle-vm.service'
                stdin, stdout, stderr = client.exec_command(cmd)
                if stdout.channel.recv_exit_status():
                    sys.exit('Could not restart untangle-vm.service')
                break
                client.close()
        except paramiko.AuthenticationException:
            sys.exit('Authentication failed')
        except paramiko.ssh_exception.BadHostKeyException:
            sys.exit('Host key could not be verified')
        except paramiko.SSHException:
            print('Unable to establish SSH connection')
            client.close()
            sleep(30)
        except IOError:
            print('Could not copy license file')
            client.close()
            sleep(30)
        except EOFError:
            print('Could not establish connection to remote side of the tunnel')
            client.close()
            sleep(30)
        if i == 20:
            sys.exit('Reached 20 sshtunnel retries')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Copy UTM licenses in UVM')
    parser.add_argument('-i', help='sd-wan branch ip', required=True)
    parser.add_argument('-u', help='sd-wan branch username', required=True)
    parser.add_argument('-p', help='sd-wan branch password', required=True)
    parser.add_argument('-f', help='licenses filepath', required=True)
    script_namespace = parser.parse_args()

    main(script_namespace)
