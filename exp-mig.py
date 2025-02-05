from monitoring import *
from gpu_settings import *
from workloads import *

import sys, time

#########################
# Create MIG instances  #
#########################
def iterate_on_gi(mig_wrapper, monitors_wrapper, suitable_gpus):
    gi_profile_list = mig_wrapper.list_gpu_instance_profiles(gpu_id=suitable_gpus[0]) # We assume homogeneity on GPUs
    for gi_profile in gi_profile_list:
        if gi_profile['free_instances'] > 0:

            print('Creating', gi_profile['name'], 'on all GPUs')
            iterate_on_ci(mig_wrapper, monitors_wrapper, suitable_gpus, gi_profile['name'])

#############################
# Create a Compute instance #
#############################
def iterate_on_ci(mig_wrapper, monitors_wrapper, suitable_gpus, protagonist_gi):

    # First, we have to create a mig to retrieve the associate list of CI profile
    mig_wrapper.create_gpu_instance(gpu_id=suitable_gpus[0], gi_profiles=protagonist_gi)
    list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpus[0])
    ci_profile_list = mig_wrapper.list_compute_instance_profiles(gpu_id=suitable_gpus[0], gi_id=list_gi_active[0]['gi_id']) # At that time, there is only one GI on GPU0
    mig_wrapper.destroy_gpu_instance(gpu_id=suitable_gpus[0])

    # Then we iterate on CI profiles
    for ci_profile in ci_profile_list:

        # I) Create GIs on all GPUs
        for suitable_gpu in suitable_gpus:
            mig_wrapper.create_gpu_instance(gpu_id=suitable_gpu, gi_profiles=protagonist_gi) # Create MIG instance

        # II) iterate_on_complements
        iterate_on_complements(mig_wrapper, monitors_wrapper, suitable_gpus, list_gi_active[0]['name'], protagonist_ci=ci_profile['name'])

        # III) Destroy all CIs
        for suitable_gpu in suitable_gpus:
            mig_wrapper.destroy_compute_instance(gpu_id=suitable_gpu)
            mig_wrapper.destroy_gpu_instance(gpu_id=suitable_gpu)

#########################
#Complementary instances#
#########################
def iterate_on_complements(mig_wrapper, monitors_wrapper, suitable_gpus, protagonist_gi, protagonist_ci):

    # First, the main protagonist
    for suitable_gpu in suitable_gpus:
        list_gi_active_specific = [gi for gi in mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpu) if gi['name'] == protagonist_gi] # We now may have multiple GIs due to iteration
        mig_wrapper.create_compute_instance(gpu_id=suitable_gpu, gi_id=list_gi_active_specific[0]['gi_id'], ci_profiles=protagonist_ci) # Create Compute instance

    # Capture idle
    setting_name = protagonist_gi.replace(' ','_') + '|' + protagonist_ci.replace(' ','_') + '|idle'
    monitors_wrapper.update_monitoring({'context': setting_name}, monitor_index=0, reset_launch=True)
    time.sleep(180)

    first_round = True
    last_round = False
    index=0
    # Then test on load
    while True:

        # I) Create complement CIs on all GIs (the increasing workload)
        if not first_round:
            for suitable_gpu in suitable_gpus:
                smallest_profile = mig_wrapper.list_gpu_instance_profiles(gpu_id=suitable_gpu)[0]
                if smallest_profile['free_instances'] > 0:
                    mig_wrapper.create_gpu_instance(gpu_id=suitable_gpu, gi_profiles=smallest_profile['name'], create_ci=True)

        first_round = False

        # II) Update monitoring
        setting_name = protagonist_gi.replace(' ','_') + '|' + protagonist_ci.replace(' ','_') + '|' + str(index)
        monitors_wrapper.update_monitoring({'context': setting_name}, monitor_index=0, reset_launch=True)

        # III) Launch stress on all CIs
        launch_stress(mig_wrapper, monitors_wrapper, suitable_gpus, mig_wrapper.list_usable_mig_partition())

        # V) Exit condition
        index+=1
        for suitable_gpu in suitable_gpus:
            smallest_profile = mig_wrapper.list_gpu_instance_profiles(gpu_id=suitable_gpu)[0]
            if smallest_profile['free_instances'] <= 0: last_round = True
        if last_round:
            break

#############################
# Launch stress on CIs      #
#############################
def launch_stress(mig_wrapper, monitors_wrapper, suitable_gpus, mig_list):
    workloads = []
    for mig in mig_list:
        workload = WorkloadBurn()
        workload.run(gpu_id=mig['mig_uuid'])
        workloads.append(workload)

    for workload in workloads:
        workload.wait()

# Also measure idle
if __name__ == "__main__":

    print('Starting MIG experiment')

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
        time.sleep(180)
        print('Idle capture ended')
    
        iterate_on_gi(mig_wrapper, monitors_wrapper, suitable_gpus)

    except KeyboardInterrupt:
        pass
    print('Exiting')
    monitors_wrapper.stop_monitoring()
