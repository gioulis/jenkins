pipeline {
    agent { label 'sdwan_pipeline' }

    parameters {
        string( defaultValue: '', name: 'lab_name',  trim: true )
        string( defaultValue: 'R11_2_2_13_888881', name: 'target_version',  trim: true )
        choice( choices: ['development', 'master'], name: 'services_registry')
    }

    environment {
        agent_root_dir = '/var/jenkins'
        scripts_path = '/sdwan_pipeline_test_aut/lab_infra/scripts/'
        openstack_path = '/sdwan_pipeline_test_aut/lab_infra/openstack/'
        localstack_template_path = "${openstack_path }" + 'heat/localstack.yaml'

        devtest_openstack_path = '/devtest/SDWAN_CORE/Lib/SDWAN_LIB/patras_infra/openstack/'
        vpx_create_script_path = "${devtest_openstack_path}" + 'topologies/vpx-labs/tools/provision_vpx_basic_labs/create_vpx_lab.py'
        labs_path = "${devtest_openstack_path}" + 'instances/'
      	orch_lib = "/devtest/SDWAN_CORE/Lib/SDWAN_LIB/patras_orchestrator_utils/"

        localstack_ip=""
        mcn_ip=""
        branch_ip=""
    }

    stages {
        stage('Checkout localstack heat template') {
            steps {
                checkout([$class: 'GitSCM',
                    branches: [[name: '*/master']],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: '/var/jenkins/sdwan_pipeline_test_aut']],
                    submoduleCfg: [],
                    userRemoteConfigs: [[credentialsId: 'svcacct_utmagent',
                    url: 'https://git.server/scm/sdwa/sdwan_pipeline_test_aut.git']]])
            }
        }
        stage('Create local-stack instance') {
            steps {
                script {
                    withCredentials([sshUserPrivateKey(credentialsId: 'svcacct_utmagent_ssh_key', keyFileVariable: 'key_file')]) {
                        cmd = ". /sdwan-openrc.sh && openstack --insecure stack create --parameter services_registry=${services_registry} --parameter-file import_key=${key_file} -t " + env.agent_root_dir + env.localstack_template_path + ' ' + params.lab_name + '_localstack'
                        env.result = sh(script: cmd, returnStdout: true)
                        echo env.result
                        sleep 60
                        cmd = ". /sdwan-openrc.sh && openstack --insecure stack output show --all " + params.lab_name + "_localstack -f json | jq -r '.instance_ip' | jq -r '.output_value' "
                        def ver_script = $/eval "$cmd" /$
                        localstack_ip = sh([script: "${ver_script}", returnStdout: true]).trim()
                        echo "localstack_ip $localstack_ip"
                    }
                }
            }
        }
        stage('Checkout terraform templates') {
            steps {
                checkout([$class: 'GitSCM',
                    branches: [[name: '*/master']],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [[$class: 'RelativeTargetDirectory', relativeTargetDir: '/var/jenkins/devtest'],
                    [$class: 'SparseCheckoutPaths',  sparseCheckoutPaths:[[$class:'SparseCheckoutPath', path:'SDWAN_CORE/Lib/SDWAN_LIB/']]]
                    ],
                    submoduleCfg: [],
                    userRemoteConfigs: [[credentialsId: 'svcacct_utmagent',
                    url: 'https://git.server/scm/sdwa/devtest.git']]])
            }
        }
        stage('Create lab') {
            steps {
                script {
                    cmd = env.agent_root_dir + vpx_create_script_path + ' ' + params.lab_name + ' 1wan dev'
                    env.result = sh(script: cmd, returnStdout: true)
                    echo env.result
                }
            }
        }
         stage('Create testbed descriptor file and connect to localstack') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'default_credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                        cmd = "python "+ env.agent_root_dir + env.scripts_path  + "generate_testbed_yaml.py $localstack_ip"
                        result = sh(script: cmd, returnStdout: true)
                        echo "$result"

                        cmd = "python "+ env.agent_root_dir + env.scripts_path  + "get_device_ip.py $localstack_ip branch"
                        branch_ip = sh([script: cmd, returnStdout: true]).trim()
                        echo "Branch ip = $branch_ip"

                        cmd = "python "+ env.agent_root_dir + env.scripts_path  + "get_device_ip.py $localstack_ip mcn"
                        mcn_ip = sh([script: cmd, returnStdout: true]).trim()
                        echo "MCN ip = $mcn_ip"

                        sleep(120)  //need to wait for nitro
                        cmd = env.agent_root_dir + env.scripts_path  + "connect_devices_to_localstack.sh -l $localstack_ip -b $branch_ip -m $mcn_ip -p ${PASSWORD}"
                        result = sh(script: cmd, returnStdout: true)
                        echo "$result"
                    }
                }
            }
        }

        stage('Update serial numbers') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'default_credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                        cmd = env.agent_root_dir + env.scripts_path + "update_serial_numbers.py -c $lab_name -m $mcn_ip -b $branch_ip -p ${PASSWORD}"
                        env.result = sh(script: cmd, returnStdout: true)
                        echo env.result
                    }
                }
            }
        }
        stage('Check Orchestrator images availability') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'default_credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                        cmd = env.agent_root_dir + env.scripts_path + "check_image_availability.py -i ${localstack_ip} -u ${USERNAME} -p ${PASSWORD} -r ${services_registry}"
                        env.result = sh(script: cmd, returnStdout: true)
                        echo env.result
                    }
                }
            }
        }
        stage('Poll until Local-stack is UP') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'default_credentials', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                        cmd = env.agent_root_dir + env.scripts_path + "poll_localstack_is_up.py -i ${localstack_ip} -u ${USERNAME} -p ${PASSWORD}"
                        env.result = sh(script: cmd, returnStdout: true)
                        echo env.result
                    }
                }
            }
        }
        stage('Apply initial configuration') {
            steps {
                script {
                    sleep(120) // Giving 2 mins extra to finish publishing sdwan-ae-utm.zip
                    cmd = 'export PYTHONPATH="\$(dirname \$(readlink -f \$(locate -b \'\\orchestrator_utils.py\' | grep patras)))" && ' + env.agent_root_dir + env.scripts_path + "network_config.py -c $lab_name -v $target_version -l $localstack_ip -j " + env.agent_root_dir + env.scripts_path + "config.json"
                    dir("$agent_root_dir$orch_lib") {
                        env.result = sh(script: cmd, returnStdout: true)
                        echo env.result
                    }
                }
            }
        }
        stage('Apply license') {
            steps {
                script {
                    withCredentials([usernamePassword(credentialsId: 'CBVWSSH', usernameVariable: 'USERNAME', passwordVariable: 'PASSWORD')]) {
                        cmd = env.agent_root_dir + env.scripts_path  + "workaround_utm_licenses.py -i $branch_ip -u ${USERNAME} -p \"${PASSWORD}\" -f "+ env.agent_root_dir + env.scripts_path + "licenses.js-workaround"
                        result = sh(script: cmd, returnStdout: true)
                        echo "$result"
                    }
                }
            }
        }
/*        stage('Apply UTM related configuration') {
            steps {
                script {
                    cmd = "python " + env.agent_root_dir + env.orch_lib + "config_agent.py  -e localstack -b sdwan-onprem-brand -m sdwan-onprem-msp -c $lab_name -l $localstack_ip"
                    result = sh(script: cmd, returnStdout: true)
                    echo "$result"
                }
            }
        }
*/
    }
}

