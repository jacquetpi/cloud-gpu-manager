from monitoring import *
from gpu_settings import *
from workloads import *

import sys, time, re

#########################
# Create MIG instances  #
#########################
def setup_namespace_and_launch(kubectl_wrapper, monitors_wrapper):
    kubectl_wrapper.set_kube_replicas_policy(3, config_name="oversub-all-3")
    kubectl_wrapper.patch_cluster_policy(config_name="oversub-all-3")
    while(True):
        current_value = kubectl_wrapper.get_current_oversub_policy()
        if current_value == 3: break
        time.sleep(1)   
    print("Current oversub policy:", kubectl_wrapper.get_current_oversub_policy())
    print("GPU instance count:", kubectl_wrapper.get_gpu_instance_count())
    kubectl_wrapper.launch_pods(kubectl_wrapper.get_gpu_instance_count())
    kubectl_wrapper.destroy_all_pods()

if __name__ == "__main__":

    print('Starting time-slice experiment')

    #########################
    # Hardware management   #
    #########################
    mig_wrapper = MIGWrapper(sudo_command='sudo-g5k')
    gpu_count = mig_wrapper.gpu_count()
    if gpu_count <= 0:
        print('Not enough GPU to continue')
        sys.exit(-1)
    kubectl_wrapper = KubectlWrapper()

    ##########################
    # Monitoring management  #
    ##########################
    mon_labels = ConstMonitor({'context':'init'}, gpu_count=gpu_count, include_gpu_x=True)
    mon_ipmi = IPMIMonitor(sudo_command='sudo-g5k')
    mon_ipmi.discover()
    mon_smi  = SMIMonitor(sudo_command='sudo-g5k')
    mon_dcgm = DCGMMonitor(url='http://localhost:9400/metrics')

    monitors = [mon_labels,mon_ipmi,mon_smi,mon_dcgm] # index matters for update
    monitors_wrapper = MonitorWrapper(monitors=monitors)

    ##########################
    # Starting  measurements #
    ##########################

    try:
        monitors_wrapper.start_monitoring()

        print('Capturing idle')
        monitors_wrapper.update_monitoring({'context':'idle'}, monitor_index=0, reset_launch=False)
        time.sleep(300)
        print('Idle capture ended')

        setup_namespace_and_launch(kubectl_wrapper, monitors_wrapper)

    except KeyboardInterrupt:
        pass
    print('Exiting')
    monitors_wrapper.stop_monitoring()