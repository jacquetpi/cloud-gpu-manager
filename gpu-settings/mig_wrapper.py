import re
import subprocess
from typing import List, Union

# Portions of this code are adapted from https://github.com/HuaizhengZhang/MIGProfiler
# Copyright (c) 2022 Li Yuanming
# Licensed under the MIT License (see LICENSE file for details).

class MIGWrapper(object):

    CREATE_GI_PATTERN = re.compile(r'.+GPU instance ID\s+(\d+).+\s+(\d+).+(MIG\s+\d+g\.\d+gb)\s+\(ID\s+(\d+)')
    CREATE_CI_PATTERN = re.compile(r'.+compute instance ID\s+(\d+).+\s(\d+).+\s(\d+).+(MIG\s+\d+g\.\d+gb|MIG\s+\d+c\.\d+\.\d+gb)\s+\(ID\s+(\d+)')

    GI_STATUS_PATTERN = re.compile(r'\|\s+(\d+)\s+(MIG\s+\d+g\.\d+gb)\s+(\d+)\s+(\d+)\s+(\d+)\:(\d+)')
    CI_STATUS_PATTERN = re.compile(r'\|\s+(\d+)\s+(\d+)\s+(MIG\s+\d+g\.\d+gb|MIG\s+\d+c\.\d+g\.\d+gb)\s+(\d+)\s+(\d+)\s+(\d+)\:(\d+)')

    GI_PROFILE_PATTERN = re.compile(r'\|\s+(\d+)\s+(MIG\s+\d+g\.\d+gb)\s+(\d+)\s+(\d+)\/(\d+)\s+([\d\.]+)\s+(Yes|No)\s+(\d+)\s+(\d+)\s+(\d+)')
    CI_PROFILE_PATTERN = re.compile(r'\|\s+(\d+)\s+(\d+)\s+(MIG\s+\d+g\.\d+gb)\s+(\d+\*?)\s+(\d+)\/(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)')

    GI_PLACEMENT_PATTERN = re.compile(r'GPU\s+(\d+)\s+Profile\s+ID\s+(\d+)\s+Placements?:\s*({[0-9,]+})(?::(\d+))?')
    CI_PLACEMENT_PATTERN = re.compile(r'GPU\s+(\d+)\s+GI\s+(\d+)\s+Profile\s+ID\s+(\d+)\s+Placements?:\s*({[0-9,]+})(?::(\d+))?')

    LIST_GPU_PATTERN = re.compile(r'^GPU\s+(\d+):\s+([^\(]+)\s+\(UUID:\s+([A-Za-z0-9\-:]+)\)$')
    LIST_MIG_PATTERN = re.compile(r'\s+MIG (\S+)\s+Device\s+(\d+):\s+\(UUID:\s+(\S+)\)')

    def __init__(self, sudo_command : str):
        self.sudo_command = sudo_command

    def enable_mig(self, gpu_id: int = None):
        # TODO PJ: Also enable persitence mode ? || sudo-g5k nvidia-smi -i 0 -pm 1
        """sudo nvidia-smi -i ${gpu_id} -mig 1"""
        cmd = [self.sudo_command, 'nvidia-smi', '-mig', '1']
        if gpu_id is not None:  cmd.extend(['-i', str(gpu_id)])
           
        # Enable NVIDIA MIG
        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()
        if 'Warning' in output:
            print(output) # TODO PJ: check for message: Warning: MIG mode is in pending enable state for
    
    def disable_mig(self, gpu_id: int = None):
        """Execute command: sudo nvidia-smi -i ${gpu_id} -mig 0"""
        cmd = [self.sudo_command, 'nvidia-smi', '-mig', '0']
        if gpu_id is not None: cmd.extend(['-i', str(gpu_id)])
        # Disable NVIDIA MIG
        return subprocess.call(cmd)

    def check_mig_status(self, gpu_id: int = None):
        """Execute command: nvidia-smi --query-gpu=mig.mode.current,mig.mode.pending --format=csv,noheader

        Returns:
            A list of tuple, contains all GPU's current MIG status and pending MIG status if `gpu_id` is not specified.
            Or a tuple contains the specified GPU's current MIG status and pending MIG status if `gpu_id` is provided.
        """
        p = subprocess.Popen(
            [
                'nvidia-smi', '--query-gpu=mig.mode.current,mig.mode.pending',
                '--format=csv,noheader',
            ],
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()
        # parse output CSV string
        mig_status_list = list()
        for line in output.splitlines():
            current_state, pending_state = line.split(', ')
            current_state, pending_state = (
                current_state == 'Enabled'), (pending_state == 'Enabled')
            mig_status_list.append((current_state, pending_state))
        # select the intereted GPU ID
        if gpu_id is not None:
            return mig_status_list[gpu_id]
        else:
            return mig_status_list

    def create_gpu_instance(self, gi_profiles: Union[str, List[str]], gpu_id: int = None, create_ci: bool = False):
        """Create GPU instance on MIG-enabled GPU device.
        The function is equivalant to executing the command: 
        :code:`sudo nvidia-smi mig -i ${gpu_id} -cgi ${gi_profiles}`
        
        Args:
            gi_profiles (str or list of str): Profile tuple or a list of profile 
                tuple. A profile tuple consists of 1. a profile name or ID and 
                2. an optional placement specifier, which consists of a colon and a 
                placement start index.
                For example, 
                    :code:`1g.10gb`, or :code:`15`: GI with profile 1/7 SM + 10gb memory.
                    :code:`1g.10gb:0`, or :code:`15:0`: GI with profile 1/7 SM + 10gb memory placed at 0.
            gpu_id (int, optional): ID of the specified GPU to create the GPU instance.
                Not specifying :code:`gpu_id` will result in create GPU instances on
                every available GPUs.
            create_ci (bool, optional): Create the default* compute instance 
                after each GPU instance creation. Default to `False`.
        Returns:
            list of dict: A list of created GPU instance status.
                The dictionary contains: :code:`gpu_id`, :code:`name`, 
                :code:`profile_id`, and :code:`gi_id` (GPU instance ID).
        Raises:
            ValueError: If creating of the GPU instance fails.
        """
        if isinstance(gi_profiles, list):
            gi_profiles = ','.join(gi_profiles)

        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-i', str(gpu_id), '-cgi', gi_profiles]
        if create_ci:
            # Also create the corresponding compute Instances (CI)
            cmd.append('-C')
        print(cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, encoding='utf-8')
        output, _ = p.communicate()
        if 'Failed' in output or 'No' in output:
            raise ValueError(
                f'Failed to create GPU instance when executing the command: {" ".join(cmd)}\n'
                f'{output}'
            )

        gi_status_list = list()
        for line in output.splitlines():
            match_groups = cls.CREATE_GI_PATTERN.match(line)
            if match_groups is not None:
                gi_id, g_id, name, profile_id = match_groups.groups()
                gi_status_list.append({
                    'gpu_id': int(g_id), 'name': name, 'profile_id': int(profile_id), 'gi_id': int(gi_id),
                })

        return gi_status_list

    def create_compute_instance(self, ci_profiles: Union[str, List[str]] = None, gpu_id: int = None, gi_id: int = None):
        """Create compute instance on MIG-enabled GPU device.
        The function is equivalant to executing the command: 
        :code:`sudo nvidia-smi mig -i ${gpu_id} -gi ${gi_id} -cci ${ci_profiles}`
        
        Args:
            ci_profiles (str or list of str): Profile name / ID or a list of profile
                names / IDs. If no profile name or ID is given, then the default*
                compute instance profile ID will be used.
                For example, 
                    :code:`1c.1g.10gb`, or :code:`0`: use 1/7 SM.
            gpu_id (int, optional): ID of the specified GPU to create the compute instance.
                Not specifying :code:`gpu_id` will result in create compute instances on
                every available GPUs.
            gi_id (bool, optional): ID of the specified GPU instance to create 
                the compute instance. Not specifying :code:`gi_id` will result in
                create compute instances on every avaliable GPU instances.
        Returns:
            list of dict: A list of created GPU instance status.
                The dictionary contains: :code:`gpu_id`, :code:`name`, 
                :code:`profile_id`, and :code:`gi_id` (GPU instance ID).
        Raises:
            ValueError: If creating of the GPU instance fails.
        """
        if isinstance(ci_profiles, list):
            ci_profiles = ','.join(ci_profiles)

        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-cci']
        if ci_profiles is not None:
            cmd.append(ci_profiles)
        if gpu_id is not None:
            cmd.extend(['-i', str(gpu_id)])
        if gi_id is not None:
            cmd.extend(['-gi', str(gi_id)])
        print('debug', cmd)
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, encoding='utf-8')
        output, _ = p.communicate()
        # Check if there are something failed
        if 'Failed' in output or 'No' in output:
            raise ValueError(
                f'Failed to create compute instance when executing the command: {" ".join(cmd)}\n'
                f'{output}'
            )

        ci_status_list = list()
        for line in output.splitlines():
            match_groups = cls.CREATE_CI_PATTERN.match(line)
            if match_groups is not None:
                ci_id, g_id, gi_id, name, profile_id = match_groups.groups()
                ci_status_list.append({
                    'gpu_id': int(g_id), 'gi_id': int(gi_id), 'name': name, 'ci_id': int(ci_id), 
                    'profile_id': int(profile_id),
                })
    
        return ci_status_list

    def list_gpu_instance_active(self, gpu_id: int = None):
        """sudo nvidia-smi mig -lgi -i ${gpu_id}
        
        Returns: list of dict.
            A list of GPU Instance status. Example: [{'gpu': 0, 'gi_id': 13, 'name': 'MIG 1g.10gb', 
                'profile_id': 19, 'ci_id': 1, 'placement': {'start': 0, 'size': 1}}]
        """
        """
        """
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-lgi']
        if gpu_id is not None:
            cmd.extend(['-i', str(gpu_id)])

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()
        # parse output string
        gi_status_list = list()
        for line in output.splitlines():
            match_groups = cls.GI_STATUS_PATTERN.match(line)
            if match_groups:
                g_id, name, profile_id, gi_id, placement_start, placement_size = match_groups.groups()
                gi_status_list.append({
                    'gpu_id': int(g_id), 'name': name, 'profile_id': int(profile_id), 'gi_id': int(gi_id),
                    'placement': {'start': int(placement_start), 'size': int(placement_size)}
                })
        
        return gi_status_list
    
    def list_compute_instance_active(self, gpu_id: int = None, gi_id: int = None):
        """sudo nvidia-smi -lci -i ${gpu_id} -gi ${gi_id}

        Returns: list of dict.
            A list of Compute Instance status. Example: [{'gpu': 0, 'name': 'MIG 1g.10gb', 'profile_id': 19,
                  'gi_id': 11, 'placement': {'start': 4, 'size': 1}}]
        """
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-lci']
        if gpu_id is not None:
            cmd.extend(['-i', str(gpu_id)])
        if gi_id is not None:
            cmd.extend(['-gi', str(gi_id)])

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()
        # parse output string
        ci_status_list = list()
        for line in output.splitlines():
            match_groups = cls.CI_STATUS_PATTERN.match(line)
            if match_groups:
                g_id, gi_id, name, profile_id, ci_id, placement_start, placement_size = match_groups.groups()
                ci_status_list.append({
                    'gpu_id': int(g_id), 'gi_id': int(gi_id), 'name': name, 'profile_id': int(profile_id), 
                    'ci_id': int(ci_id), 'placement': {'start': int(placement_start), 'size': int(placement_size)}
                })
        return ci_status_list

    def destroy_gpu_instance(self, gpu_id: int = None, gi_ids: Union[int, List[int]] = None):
        """sudo nvidia-smi mig -dgi -gi ${gi_id} -i ${gpu_id}"""
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-dgi']
        if isinstance(gi_ids, list):
            gi_ids = ','.join(gi_ids)
        if gi_ids is not None:
            cmd.extend(['-gi', str(gi_ids)])
        if gpu_id is not None:
            cmd.extend(['-i', str(gpu_id)])
        return subprocess.call(cmd)

    def destroy_compute_instance(self, gpu_id: int = None, gi_id: int = None, ci_ids: Union[int, List[int]] = None):
        """sudo nvidia-smi mig -dci -gi ${gi_id} -ci ${ci_ids} -i ${gpu_id}"""
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-dci']

        if isinstance(ci_ids, list):
            ci_ids = ','.join(ci_ids)
        if ci_ids is not None:
            cmd.extend(['-ci', str(ci_ids)])
        if gi_id is not None:
            cmd.extend(['-gi', str(gi_id)])
        if gpu_id is not None:
            cmd.extend(['-i', str(gpu_id)])
        return subprocess.call(cmd)
    
    def list_gpu_instance_profiles(self, gpu_id: int = None):
        """nvidia-smi -lgip -i ${gpu_id}"""
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-lgip']
        if gpu_id is not None: cmd.extend(['-i', str(gpu_id)])

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()

        # parse output string
        gi_profile_list = list()
        for line in output.splitlines():
            match_groups = cls.GI_PROFILE_PATTERN.match(line)
            if match_groups:
                gpu_id, name, profile_id, free_instances, total_instances, memory, p2p, sm, dec, enc = match_groups.groups()
                gi_profile_list.append({
                    'gpu_id': int(gpu_id), 'name': name, 'profile_id': int(profile_id), 'free_instances': int(free_instances), 'total_instances': int(total_instances),
                    'memory': float(memory), 'P2P': (p2p.upper() == 'YES'), 'sm': int(sm), 'dec': int(dec), 'enc': int(enc)})
        
        return gi_profile_list
    
    def list_gpu_instance_possible_placements(self, gpu_id: int = None):
        """nvidia-smi -lgipp -i ${gpu_id}"""
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-lgipp']
        if gpu_id is not None: cmd.extend(['-i', str(gpu_id)])

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()

        # parse output string
        gi_placement_list = list()
        for line in output.splitlines():
            match_groups = cls.GI_PLACEMENT_PATTERN.match(line)
            if match_groups:
                g_id, profile_id, placements, size = match_groups.groups()
                gi_placement_list.append({
                    'gpu_id': int(g_id), 'profile_id': int(profile_id),
                    'placement': [{'start': int(start), 'size': int(size)} for start in placements.strip('{}').split(',')]
                })
        return gi_placement_list

    
    def list_compute_instance_profiles(self, gpu_id: int = None, gi_id: int = None):
        """nvidia-smi -lcip -i ${gpu_id} -gi ${gi_id}"""
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-lcip']
        if gpu_id is not None: cmd.extend(['-i', str(gpu_id)])
        if gi_id is not None: cmd.extend(['-gi', str(gi_id)])

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()

        # parse output string
        ci_profile_list = list()
        for line in output.splitlines():
            match_groups = cls.CI_PROFILE_PATTERN.match(line)
            if match_groups:
                g_id, gpu_instance_id, name, profile_id, free_instances, total_instances, sm, dec, enc, ofa = match_groups.groups()
                ci_profile_list.append({
                    'gpu_id': int(g_id),  'gpu_instance_id': int(gpu_instance_id), 'name': name, 'profile_id': int(profile_id.replace('*', '')), 'free_instances': int(free_instances), 'total_instances': int(total_instances),
                    'sm': int(sm), 'dec': int(dec), 'enc': int(enc), 'ofa':int(ofa)})
        
        return ci_profile_list
    
    def list_compute_instance_possible_placements(self, gpu_id: int = None):
        cmd = [self.sudo_command, 'nvidia-smi', 'mig', '-lcipp']
        if gpu_id is not None: cmd.extend(['-i', str(gpu_id)])

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()

        # parse output string
        ci_placement_list = list()
        for line in output.splitlines():
            match_groups = cls.CI_PLACEMENT_PATTERN.match(line)
            if match_groups:
                g_id, gi_id, profile_id, placements, size = match_groups.groups()
                ci_placement_list.append({
                    'gpu_id': int(g_id), 'gi_id': int(gi_id), 'profile_id': int(profile_id),
                    'placement': [{'start': int(start), 'size': int(size)} for start in placements.strip('{}').split(',')]
                })
        return ci_placement_list

    def clean_reset(self, gpu_id: int = None):
        cmd_dci = [self.sudo_command, 'nvidia-smi', 'mig', '-dci']
        cmd_dgi = [self.sudo_command, 'nvidia-smi', 'mig', '-dgi']
        if gpu_id is not None: 
            cmd_dci.extend(['-i', str(gpu_id)])
            cmd_dgi.extend(['-i', str(gpu_id)])
        subprocess.call(cmd_dci)
        return subprocess.call(cmd_dgi)

    def list_usable_mig_partition(self):
        cmd = [self.sudo_command, 'nvidia-smi', '-L']

        p = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            encoding='utf-8',
        )
        output, _ = p.communicate()
        print(output)
        mig_profiles = []
        gpu_id = None       
        for line in output.splitlines():
            # Match GPU line
            
            gpu_match = cls.LIST_GPU_PATTERN.match(line)
            print('debug', line)
            
            if gpu_match: gpu_id, _, _ = gpu_match.groups()
            print('debug1', gpu_match, gpu_id)

            mig_match = cls.LIST_MIG_PATTERN.match(line)
            print('debug2', mig_match)
            if mig_match and gpu_id:
                mig_profile_name, device_number, mig_uuid = mig_match.groups()
                mig_profiles.append({'profile_name': mig_profile_name, 'gpu_id': int(gpu_id),
                                     'device_id': int(device_number), 'mig_uuid': mig_uuid,
                })

        return mig_profiles