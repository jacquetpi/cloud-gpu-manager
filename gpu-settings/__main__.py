from .mig_wrapper import MIGWrapper
import sys

if __name__ == '__main__':

    mig_wrapper = MIGWrapper(sudo_command='sudo-g5k')

    gpu_count = mig_wrapper.gpu_count()
    if gpu_count <= 0:
        print('Not enough GPU to continue')
        sys.exit(-1)
    print(gpu_count, 'GPUs found')

    # https://docs.nvidia.com/datacenter/tesla/mig-user-guide/

    mig_wrapper.clean_reset()

    suitable_gpus = list() # List of gpu id
    mig_status = mig_wrapper.check_mig_status()
    for id, status in enumerate(mig_status):
        active, _ = status
        if active: suitable_gpus.append(id)
    print('List of GPUs with MIG currently operational:', suitable_gpus)

    #for id in range(gpu_count): print(mig_wrapper.enable_mig(gpu_id=id))

    gi_profile_list = mig_wrapper.list_gpu_instance_profiles(gpu_id=suitable_gpus[0])
    for gi_profile in gi_profile_list:
        if gi_profile['free_instances'] > 0:
            print('Creating', gi_profile['name'], 'on', '')
            mig_wrapper.create_gpu_instance(gpu_id=suitable_gpus[0], gi_profiles=gi_profile['name'])
            list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpus[0])

            if list_gi_active:
                index = 0
                ci_profile_list = mig_wrapper.list_compute_instance_profiles(gpu_id=list_gi_active[index]['gpu_id'], gi_id=list_gi_active[index]['gi_id'])
                print('#ci', ci_profile_list)
                mig_wrapper.create_compute_instance(gpu_id=list_gi_active[index]['gpu_id'], gi_id=list_gi_active[index]['gi_id'], ci_profiles=ci_profile_list[0]['name'])
                list_ci_active = mig_wrapper.list_compute_instance_active(gpu_id=suitable_gpus[0], gi_id=list_gi_active[index]['gi_id'])
                print(list_ci_active)

                print('Setup done, launching stress')
                docker_partitions = mig_wrapper.list_usable_mig_partition()
                for partition in docker_partitions:
                    mig_wrapper.launch_docker(mig_identifier=partition['mig_uuid'])
                    break

                break
                list_ci_active = mig_wrapper.list_compute_instance_active(gpu_id=suitable_gpus[0], gi_id=list_gi_active[0]['gi_id'])
                for ci_active in list_ci_active:
                    mig_wrapper.destroy_compute_instance(gpu_id=ci_active['gpu_id'], gi_id=ci_active['gi_id'], ci_ids=ci_active['ci_id'])
            
            break
            list_gi_active = mig_wrapper.list_gpu_instance_active(gpu_id=suitable_gpus[0])
            for gi_active in list_gi_active:
                mig_wrapper.destroy_gpu_instance(gpu_id=suitable_gpus[0],gi_ids=gi_active['gi_id'])
