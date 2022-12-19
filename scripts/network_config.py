#!/usr/bin/env python3

from orchestrator_utils import OrchestratorAPIClient
import json
import sys
import argparse
import requests
import time
from requests.packages.urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

# Parse Arguments
parser = argparse.ArgumentParser()
parser.add_argument("-c", "--customer_name", type=str, required=True, help="Customer name")
parser.add_argument("-l", "--localstack_ip", type=str, required=True, help="Localstack Orchestrator IP")
parser.add_argument("-j", "--json_file", type=str, required=True, help="Json config file")
parser.add_argument("-v", "--version", type=str, required=False, default="R11_2_2_14_888881", help="Target version for Staging")
args = parser.parse_args()

environment = "localstack"
brand_name = "sdwan-onprem-brand"
msp_name = "sdwan-onprem-msp"
customer_name = args.customer_name
localstack_ip = args.localstack_ip
config_file = args.json_file
version = args.version
s = requests.Session()
with open(config_file) as json_file:
    site_data=json.load(json_file)["sites"]
mcn_serial = [site["serial"] for site in site_data if site["name"].endswith("mcn")][0]
branch_serial = [site["serial"] for site in site_data if site["name"].endswith("branch")][0]

my_api = OrchestratorAPIClient(environment, brand_name, msp_name, customer_name, localstack_ip)

if __name__ == "__main__":
    if not my_api.create_customer(customer_name):
        sys.exit(1)
    if not my_api.import_config(config_file):
        sys.exit(1)
    if not my_api.patch_serial("mcn", mcn_serial):
        sys.exit(1)
    if not my_api.patch_serial("branch", branch_serial):
        sys.exit(1)
    if not my_api.set_version(version):
        sys.exit(1)
    timer, counter = 0, 3
    url = "{}/{}/policy/v1/customer/{}/status".format(my_api.api_endpoint, my_api.ccId, my_api.customer_id)
    while timer < 300:
        sites_status = requests.get(url, headers=my_api.headers, verify=my_api.verify).json()["cmSiteStatus"]
        if all(site["onlineStatus"] == "online" for site in sites_status):
            counter += 1
        else:
            print("Sites not yet online")
            counter -= 1
        if counter == 10:   # This is used to verify that sites are online and stable for some time
            break
        time.sleep(10)
        timer += 10
    outcome = my_api.stage_and_activate()
    print("Stage and activate result: " + str(outcome))
