from monitoring import *
from gpu_settings import *
from workloads import *

import sys, time, re

#########################
# Create MIG instances  #
#########################
def setup_namespace_and_launch(mig_wrapper, monitors_wrapper, suitable_gpus):
    kubectl = KubectlWrapper()
    kubectl.set_kube_replicas_policy(3, config_name="oversub-all-3")
    kubectl.patch_cluster_policy(config_name="oversub-all-3")
    while(True)
        current_value = kubectl.get_current_oversub_policy()
        if current_value == 3: break
        time.sleep(1)   
    print("Current oversub policy:", kubectl.get_current_oversub_policy())
    print("GPU instance count:", kubectl.get_gpu_instance_count())
    kubectl.launch_pods(kubectl.get_gpu_instance_count())
    kubectl.destroy_all_pods()

if __name__ == "__main__":

    print('Starting pass-through experiment')

    #########################
    # Hardware management   #
    #########################
    mig_wrapper = MIGWrapper(sudo_command='sudo-g5k')
    gpu_count = mig_wrapper.gpu_count()
    if gpu_count <= 0:
        print('Not enough GPU to continue')
        sys.exit(-1)

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
    # Setup experiment       #
    ##########################
    mig_wrapper.clean_reset()

    suitable_gpus = list() # List of gpu id
    mig_status = mig_wrapper.check_mig_status()
    for mig_gpu, status in enumerate(mig_status):
        active, _ = status
        if active: suitable_gpus.append(mig_gpu)
    print('List of GPUs with MIG currently operational:', suitable_gpus)
    if not suitable_gpus:
        print('Not enough MIG hardware to continue')
        sys.exit(-1)

    ##########################
    # Starting  measurements #
    ##########################

    try:
        monitors_wrapper.start_monitoring()

        print('Capturing idle')
        monitors_wrapper.update_monitoring({'context':'idle'}, monitor_index=0, reset_launch=False)
        time.sleep(300)
        print('Idle capture ended')
        
        setup_gi_and_launch(mig_wrapper, monitors_wrapper, suitable_gpus)

    except KeyboardInterrupt:
        pass
    print('Exiting')
    monitors_wrapper.stop_monitoring()
