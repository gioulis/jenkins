import json
import subprocess
import os
import sys

lab_name = os.getenv('lab_name')
localstack_ip = sys.argv[1]
device_type = sys.argv[2] # Can be mcn or branch
wd = os.getenv('agent_root_dir') + os.getenv('labs_path') + lab_name
os.chdir(wd)
json_file = subprocess.check_output(['terraform', 'output', '-json'])
tf_output = json.loads(json_file)

# Read info from terraform output
device_mgmt_ip = tf_output[device_type]['value']['mgmt_ip']
print(device_mgmt_ip)

sys.exit(0)


