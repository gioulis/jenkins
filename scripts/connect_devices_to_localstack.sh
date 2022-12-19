#!/bin/bash
# Script that automates procedure to define and connect VPX instances (mcn, branch) to localstack Orchestrator
# Example usage: ./connect_devices_to_localstack.sh -l 10.78.92.159 -m 10.78.92.207 -b 10.78.92.197 -p xxxx

function usage(){
    echo 'Please provide ips for localstack, mcn and branch'
    echo 'Example format: ./connect_devices_to_localstack.sh -l 10.78.x.x -m 10.78.y.y -b 10.78.z.z -p "abc"'
}

while getopts l:p:m:b: arg
  do
    case "${arg}" in
      l) LOCALSTACK_IP=${OPTARG};;
      p) PASSWORD=${OPTARG};;
      m) MCN_IP=${OPTARG};;
      b) BRANCH_IP=${OPTARG};;
      *)usage
        exit 1
        ;;
    esac
	done
echo "localstack ip: $LOCALSTACK_IP";
echo "mcn ip: $MCN_IP";
echo "branch ip: $BRANCH_IP";

if [[ $# -eq 0 ]] ; then
    usage
    exit 1
fi

# First check if localstack is UP
if ping -c 1 $LOCALSTACK_IP &> /dev/null
then
  echo "Localstack OK. Proceed with connection of devices"
else
  echo "Localstack is DOWN. Exiting..."
  exit 1
fi

for VPX_IP in $MCN_IP $BRANCH_IP
do
  # Login
  OUT=$(curl --silent -X POST -c /tmp/cookies.txt -H "Content-Type: application/json" --insecure https://$VPX_IP/sdwan/nitro/v1/config/login --data '{"login":{"username":"admin","password":"'$PASSWORD'"}}')
  if [[ $OUT == *"Login Success"* ]]; then
   echo "Login Success for device $VPX_IP"
  else
    echo "Not able to login to $VPX_IP"
    exit 1
  fi

  # Set Authentication type
  OUT=$(curl -X PUT -b /tmp/cookies.txt --insecure https://$VPX_IP/sdwan/nitro/v1/onprem_orchestrator/onprem_authentication_type --data '{"onprem_authentication_type":{"authentication_type":"No Authentication" }}' -H "Content-Type: application/json")
  if [[ $OUT == *"Authentication Type is configured successfully"* ]]; then
   echo "Authentication Type is configured successfully for device $VPX_IP"
  else
    echo "Authentication Type NOT configured for $VPX_IP"
    exit 1
  fi

  # Set OnPrem Orchestrator IP
  OUT=$(curl -X PUT -b /tmp/cookies.txt --insecure https://$VPX_IP/sdwan/nitro/v1/onprem_orchestrator/onprem_identity --data '{"onprem_identity":{ "onprem_orchestrator_domain":"", "onprem_orchestrator_ip":"'$LOCALSTACK_IP'", "onprem_orchestrator_connectivity":"true"}}' -H "Content-Type: application/json")
  if [[ $OUT == *"is configured successfully"* ]]; then
    echo "OnPrem IP configured successfully for device $VPX_IP"
  else
    echo "OnPrem IP NOT set for $VPX_IP"
    exit 1
  fi

done

echo "Done!"
exit 0
