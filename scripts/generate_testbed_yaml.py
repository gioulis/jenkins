#!/usr/bin/python
import json
import yaml
import subprocess
import os
import sys


lab_name = os.getenv('lab_name')
localstack_ip = sys.argv[1]
print("localstack_ip=", localstack_ip)
wd = os.getenv('agent_root_dir') + os.getenv('labs_path') + lab_name
os.chdir(wd)
json_file = subprocess.check_output(['terraform', 'output', '-json'])
tf_output = json.loads(json_file)

# Read all needed info from terraform output
mcn_mgmt_ip = tf_output['mcn']['value']['mgmt_ip']
mcn_name = tf_output['mcn']['value']['name']
branch_mgmt_ip = tf_output['branch']['value']['mgmt_ip']
branch_name = tf_output['branch']['value']['name']
mcn_host_mgmt_ip = tf_output['mcn-host1']['value']['mgmt_ip']
branch_host_mgmt_ip = tf_output['branch-host1']['value']['mgmt_ip']

with open(os.getenv('agent_root_dir') + os.getenv('openstack_path') +'/testbed_template.yaml') as testbed_file:
    testbed_description = yaml.load(testbed_file, Loader=yaml.FullLoader)
"""
Example for testbed yaml:
STATE: AVAILABLE
ENV:
  ORCHESTRATOR:
    name: placeholder
    ip: placeholder_only_valid_for_localstack
  CUSTOMER:
    name: placeholder
SITES:
  BRANCH1:
    basic_settings:
      mode: client
      model: cbvpx
      site_name: BRANCH1_KVMVPX
    vm_ip: placeholder
  MCN:
    basic_settings:
      mode: primary_mcn
      model: cbvpx
      site_name: MCN_KVMVPX
    vm_ip: placeholder
CLIENT:
  ip: placeholder
  username: placeholder
  password: placeholder
SERVER:
  ip: placeholder
  username: placeholder
  password: placeholder
  
"""
testbed_description["ENV"]["ORCHESTRATOR"]["name"] = "localstack"
testbed_description["ENV"]["ORCHESTRATOR"]["ip"] = localstack_ip
testbed_description["ENV"]["CUSTOMER"]["name"] = lab_name

testbed_description["SITES"]["BRANCH1"]["basic_settings"]["site_name"] = branch_name
testbed_description["SITES"]["BRANCH1"]["vm_ip"] = branch_mgmt_ip

testbed_description["SITES"]["MCN"]["basic_settings"]["site_name"] = mcn_name
testbed_description["SITES"]["MCN"]["vm_ip"] = mcn_mgmt_ip

testbed_description["CLIENT"]["ip"] = tf_output['mcn-host1']['value']['mgmt_ip']
testbed_description["SERVER"]["ip"] = tf_output['branch-host1']['value']['mgmt_ip']

print("Testbed descriptor yaml:")
print(testbed_description)

with open('edge_config.yaml', 'w') as f:
    yaml.safe_dump(testbed_description, f, allow_unicode=True, default_flow_style=False)

sys.exit(0)


