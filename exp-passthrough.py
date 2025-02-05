from monitoring import *
from gpu_settings import *
from workloads import *

import sys, time

#########################
# Create MIG instances  #
#########################
def iterate_on_gi(mig_wrapper, monitors_wrapper, suitable_gpus):

    largest_gi = mig_wrapper.list_gpu_instance_profiles(gpu_id=suitable_gpus[0])[-1] # We assume homogeneity on GPUs
    for suitable_gpu in suitable_gpus: # Create GIs on all GPUs
        mig_wrapper.create_gpu_instance(gpu_id=suitable_gpu, gi_profiles=largest_gi)

    # Iterate based on chosen granularity
    list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpus[0])
    ci_profile_list = mig_wrapper.list_compute_instance_profiles(gpu_id=suitable_gpus[0], gi_id=list_gi_active[0]['gi_id']) # At that time, there is only one GI on GPU0
    ci_training = [None, ci_profile_list[int(len(ci_profile_list)/2)+1], ci_profile_list[-1]]

    print('GIs created, will iterate through all combinaison of GI and following profiles', training)
    iterate_on_ci(mig_wrapper, monitors_wrapper, suitable_gpus, training)

#############################
# Create Compute instances  #
#############################
def iterate_on_combinaison(mig_wrapper, monitors_wrapper, suitable_gpus, ci_profile_list):

    # First enumerate all combinations
    total_combinations = len(ci_training) ** len(suitable_gpus)
    print(total_combinations, 'found')
    combinations = []
    for i in range(total_combinations):
        combo = []
        num = i
        for _ in range(objects):
            combo.append(settings[num % len(settings)])
            num //= len(settings)
        combinations.append(tuple(combo))

    # Then iterate on all of them
    for combination in combinations:
        
        # I) Create CIs on all GPUs
        for suitable_gpu, config in zip(suitable_gpus,combination):
            if config == None:
                continue # Idle case, nothing to do

            list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpu)
            mig_wrapper.create_compute_instance(gpu_id=suitable_gpu, gi_id=list_gi_active[0]['gi_id'], ci_profiles=config) # Still only one GI per GPU on our setting

        # II) Update monitoring
        setting_name = '|'.join('0' if config == None else re.match(r"^\d+", config).group() for config in combination)
        print(setting_name)
        monitors_wrapper.update_monitoring({'context': setting_name}, monitor_index=0, reset_launch=True)

        # III) Launch stress on all CIs
        launch_stress(mig_wrapper, monitors_wrapper, suitable_gpus, mig_wrapper.list_usable_mig_partition())
        iterate_on_complements(mig_wrapper, monitors_wrapper, suitable_gpus, list_gi_active[0]['name'], protagonist_ci=ci_profile['name'])

        # IV) Destroy all CIs
        for suitable_gpu in suitable_gpus: mig_wrapper.destroy_compute_instance(gpu_id=suitable_gpu)

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

    print('Capturing idle')
    monitors_wrapper.update_monitoring({'context':'idle'}, monitor_index=0, reset_launch=False)
    time.sleep(180)
    print('Idle capture ended')
    
    try:
        monitors_wrapper.start_monitoring()
        iterate_on_gi(mig_wrapper, monitors_wrapper, suitable_gpus)

    except KeyboardInterrupt:
        pass
    print('Exiting')
    monitors_wrapper.stop_monitoring()
