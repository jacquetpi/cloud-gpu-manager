from monitoring import *
from gpu_settings import *
from workloads import *

import sys

#########################
# Create MIG instances  #
#########################
def iterate_on_gi(mig_wrapper, monitors_wrapper, suitable_gpus):
    gi_profile_list = mig_wrapper.list_gpu_instance_profiles(gpu_id=suitable_gpus[0]) # We assume homogeneity on GPUs
    for gi_profile in gi_profile_list:
        if gi_profile['free_instances'] > 0:
            print('Creating', gi_profile['name'], 'on all GPUs')

            # I) Create GIs on all GPUs
            for suitable_gpu in suitable_gpus: 
                mig_wrapper.create_gpu_instance(gpu_id=suitable_gpu, gi_profiles=gi_profile['name']) # Create MIG instance
                list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpu)
                if not list_gi_active:  # Check if everything went well
                    print('GI creation: Something went wrong on GPU', suitable_gpu)

            # II) Iterate on all CIs profile
            iterate_on_ci(mig_wrapper, monitors_wrapper, suitable_gpus)

            # III) Destroy all GIs
            for suitable_gpu in suitable_gpus: 
                list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpu)
                for gi_active in list_gi_active:
                    mig_wrapper.destroy_gpu_instance(gpu_id=suitable_gpu, gi_ids=gi_active['gi_id'])

#############################
# Create a Compute instance #
#############################
def iterate_on_ci(mig_wrapper, monitors_wrapper, suitable_gpus):
    # Again, we assume homogeneity on GPUs and takes GPU0 as a referential
    list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpus[0])
    ci_profile_list = mig_wrapper.list_compute_instance_profiles(gpu_id=suitable_gpus[0], gi_id=list_gi_active[0]['gi_id'])

    for ci_profile in ci_profile_list:
        
        # Monitoring update
        setting_name = list_gi_active[0]['name'] + '|' + ci_profile['name']
        monitors_wrapper.update_monitoring({'context': setting_name}, monitor_index=0, reset_launch=True)

        # I) Create CIs on all GIs
        for suitable_gpu in suitable_gpus: 
            list_gi_active_specific = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpu)
            mig_wrapper.create_compute_instance(gpu_id=suitable_gpu, gi_id=list_gi_active_specific[0]['gi_id'], ci_profiles=ci_profile['name']) # Create Compute instance
            list_ci_active = mig_wrapper.list_compute_instance_active(gpu_id=suitable_gpu, gi_id=list_gi_active[0]['gi_id']) # index is 0 in our context where we operate only one GI per GPU
            if not list_ci_active: # Check if everything went well
                print('CI creation: Something went wrong on GPU', suitable_gpu)
                continue

        # II) Launch stress on all CIs
        launch_stress(mig_wrapper, monitors_wrapper, suitable_gpus, mig_wrapper.list_usable_mig_partition())

        # III) Destroy all CIs
        for suitable_gpu in suitable_gpus: 
            list_gi_active_specific = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpu)
            list_ci_active = mig_wrapper.list_compute_instance_active(gpu_id=suitable_gpu, gi_id=list_gi_active_specific[0]['gi_id']) # index is 0 in our context where we operate only one GI per GPU
            for ci_active in list_ci_active:
                mig_wrapper.destroy_compute_instance(gpu_id=ci_active['gpu_id'], gi_id=ci_active['gi_id'], ci_ids=ci_active['ci_id'])

#############################
# Launch stress on CIs      #
#############################             
def launch_stress(mig_wrapper, monitors_wrapper, suitable_gpus, uuid_list):
    workloads = []
    for uuid in uuid_list:
        workload = WorkloadBurn()
        workload.run(gpu_id=uuid)
        workloads.append(workload)

    for workload in workloads:
        workload.wait()

if __name__ == "__main__":

    print('Starting demo experiment')

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

    monitors = [mon_ipmi,mon_smi,mon_dcgm,mon_labels]
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
    monitors_wrapper.update_monitoring({'context':'init'}, monitor_index=0, reset_launch=False)

    try:
        monitors_wrapper.start_monitoring()
        iterate_on_gi(mig_wrapper, monitors_wrapper, suitable_gpus)

    except KeyboardInterrupt:
        pass
    print('Exiting')
    monitors_wrapper.stop_monitoring()