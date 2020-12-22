from pylab import *

import argparse
import dateutil
import inspect
import os
import pandas as pd
import sys

import path_utils

#
# If we're using Python 2, then import the Deadline Python module as usual. If we're using
# Python 3, then add the path "../third_party" (relative to this source file) to the
# system path before importing Deadline. This design allows for the Hypersim Toolkit to
# make use of a customized implementation of the Deadline Python module, e.g., that has
# been modified to work correctly with Python 3.
#

if sys.version_info[0] == 2:
    import Deadline.DeadlineConnect
else:
    path_utils.add_path_to_sys_path("../third_party", mode="relative_to_current_source_dir", frame=inspect.currentframe())
    import Deadline.DeadlineConnect

path_utils.add_path_to_sys_path("..", mode="relative_to_current_source_dir", frame=inspect.currentframe())
import _system_config

parser = argparse.ArgumentParser()
parser.add_argument("--analysis_dir", required=True)
args = parser.parse_args()



print("[HYPERSIM: DATASET_GENERATE_RENDERING_JOBS_STATISTICS_DEADLINE] Begin...")



metadata_camera_trajectories_csv_file      = os.path.join(args.analysis_dir, "metadata_camera_trajectories.csv")
metadata_rendering_jobs_deadline_csv_file  = os.path.join(args.analysis_dir, "metadata_rendering_jobs.csv")
metadata_rendering_tasks_deadline_csv_file = os.path.join(args.analysis_dir, "metadata_rendering_tasks.csv")

df_camera_trajectories = pd.read_csv(metadata_camera_trajectories_csv_file).rename_axis("camera_trajectory_id").reset_index().set_index("Animation")
camera_trajectories = df_camera_trajectories.to_records()



deadline_con = Deadline.DeadlineConnect.DeadlineCon(_system_config.cloud_server_hostname, _system_config.cloud_server_port)
assert deadline_con.Repository.GetDeadlineVersion().startswith("v")



print("[HYPERSIM: DATASET_GENERATE_RENDERING_JOBS_STATISTICS_DEADLINE] Connected to Deadline server, downloading jobs...")

jobs_dict = deadline_con.Jobs.GetJobs()
assert len(jobs_dict) == camera_trajectories.shape[0]*3



instance_types_sorted = [ "large", "xlarge", "2xlarge", "4xlarge", "9xlarge", "12xlarge", "18xlarge", "24xlarge" ]

vcpu_per_instance = {
    "large"    : 2,
    "xlarge"   : 4,
    "2xlarge"  : 8,
    "4xlarge"  : 6,
    "9xlarge"  : 36,
    "12xlarge" : 48,
    "18xlarge" : 72,
    "24xlarge" : 96
}

# https://aws.amazon.com/ec2/instance-types
memory_gib_per_instance = {
    "large"    : 4.0,
    "xlarge"   : 8.0,
    "2xlarge"  : 16.0,
    "4xlarge"  : 32.0,
    "9xlarge"  : 72.0,
    "12xlarge" : 96.0,
    "18xlarge" : 144.0,
    "24xlarge" : 192.0
}

# https://aws.amazon.com/ec2/spot/pricing
cost_aws_dollars_per_instance_hour = {
    "large"    : 0.0322,
    "xlarge"   : 0.0813,
    "2xlarge"  : 0.154,
    "4xlarge"  : 0.2904,
    "9xlarge"  : 0.5935,
    "12xlarge" : 0.7727,
    "18xlarge" : 1.16,
    "24xlarge" : 1.5454
}

# https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instance-optimize-cpu.html
vcpu_per_core = 2.0
cores_per_vcpu = 1.0/vcpu_per_core

# https://marketplace.thinkboxsoftware.com/collections/v-ray-render
cost_vray_dollars_per_core_hour = 0.018
cost_vray_dollars_per_vcpu_hour = cost_vray_dollars_per_core_hour*cores_per_vcpu

seconds_per_hour = 3600.0
hours_per_second = 1.0/seconds_per_hour

max_memory_usage_fraction = 0.95

bytes_per_gib = 1024*1024*1024
gib_per_byte = 1.0/bytes_per_gib

render_passes = [ "geometry", "pre", "final" ]



print("[HYPERSIM: DATASET_GENERATE_RENDERING_JOBS_STATISTICS_DEADLINE] Processing jobs...")

df_jobs_columns = ["job_name", "instance_type", "vcpu_per_instance", "time_instance_seconds", "time_vcpu_seconds", "cost_cloud_dollars", "cost_vray_dollars", "used_clock", "total_clock", "cpu_utilization", "peak_memory_usage_gib", "min_feasible_instance_type", "camera_trajectory_included_in_dataset"]
df_jobs = pd.DataFrame(columns=df_jobs_columns)

df_tasks_columns = ["job_name", "task_id", "instance_type", "vcpu_per_instance", "time_instance_seconds", "time_vcpu_seconds", "cost_cloud_dollars", "cost_vray_dollars", "used_clock", "total_clock", "cpu_utilization", "peak_memory_usage_gib", "min_feasible_instance_type", "camera_trajectory_included_in_dataset"]
df_tasks = pd.DataFrame(columns=df_tasks_columns)

for r in render_passes:
    for c in camera_trajectories:

        job_name      = c["Rendering job (" + r + ")"]
        instance_type = c["Instance type (" + r + ")"]

        jobs_list_filtered = [ j for j in jobs_dict if j["Props"]["Name"] == job_name ]
        assert len(jobs_list_filtered) == 1
        job = jobs_list_filtered[0]

        # check if camera trajectory is flagged for exclusion
        scene_name  = job["Props"]["Ex2"]
        camera_name = job["Props"]["Ex3"]
        camera_trajectory_name = scene_name + "_" + camera_name
        scene_type = df_camera_trajectories.loc[camera_trajectory_name]["Scene type"]
        camera_trajectory_included_in_dataset = scene_type != "OUTSIDE VIEWING AREA (BAD INITIALIZATION)" and scene_type != "OUTSIDE VIEWING AREA (BAD TRAJECTORY)"

        if not camera_trajectory_included_in_dataset:
            print("[HYPERSIM: DATASET_GENERATE_SCENE_LABELING_STATISTICS] Camera trajectory " + camera_trajectory_name + " is bad, setting camera_trajectory_included_in_dataset to False...")

        tasks_dict = deadline_con.Tasks.GetJobTasks(job["_id"])
        tasks_list = tasks_dict["Tasks"]
        num_tasks  = len(tasks_list)

        assert num_tasks == 100

        job_time_instance_seconds  = 0.0
        job_used_clock             = 0
        job_total_clock            = 0
        job_aws_cost_dollars       = 0.0
        job_peak_memory_usage_gib  = 0.0

        for i in range(num_tasks):

            task_dict = tasks_list[i]

            task_start_time_str = task_dict["Start"]
            task_end_time_str = task_dict["Comp"]
            task_used_clock = task_dict["UsedClock"]
            task_total_clock = task_dict["TotalClock"]
            task_peak_memory_usage_bytes = task_dict["RamPeak"]

            start_time = dateutil.parser.parse(task_start_time_str)
            end_time = dateutil.parser.parse(task_end_time_str)

            task_time_instance_seconds = (end_time - start_time).total_seconds()
            task_time_vcpu_seconds     = task_time_instance_seconds*vcpu_per_instance[instance_type]
            task_cost_aws_dollars      = task_time_instance_seconds*hours_per_second*cost_aws_dollars_per_instance_hour[instance_type]
            task_cost_vray_dollars     = task_time_vcpu_seconds*hours_per_second*cost_vray_dollars_per_vcpu_hour
            task_cpu_utilization       = float(task_used_clock)/float(task_total_clock)
            task_peak_memory_usage_gib = task_peak_memory_usage_bytes*gib_per_byte

            task_feasible_instance_types = array([ task_peak_memory_usage_gib <= max_memory_usage_fraction*memory_gib_per_instance[k] for k in instance_types_sorted ])
            assert any(task_feasible_instance_types)
            task_min_feasible_instance_type = instance_types_sorted[where(task_feasible_instance_types)[0][0]]

            df_tasks_curr = pd.DataFrame(columns=df_tasks_columns,
                                         data={"job_name":[job_name],
                                               "task_id":[i],
                                               "instance_type":[instance_type],
                                               "vcpu_per_instance":[vcpu_per_instance[instance_type]],
                                               "time_instance_seconds":[task_time_instance_seconds],
                                               "time_vcpu_seconds":[task_time_vcpu_seconds],
                                               "cost_cloud_dollars":[task_cost_aws_dollars],
                                               "cost_vray_dollars":[task_cost_vray_dollars],
                                               "used_clock":[task_used_clock],
                                               "total_clock":[task_total_clock],
                                               "cpu_utilization":[task_cpu_utilization],
                                               "peak_memory_usage_gib":[task_peak_memory_usage_gib],
                                               "min_feasible_instance_type":[task_min_feasible_instance_type],
                                               "camera_trajectory_included_in_dataset":[camera_trajectory_included_in_dataset]})

            df_tasks = df_tasks.append(df_tasks_curr, ignore_index=True)

            job_time_instance_seconds += task_time_instance_seconds
            job_used_clock            += task_used_clock
            job_total_clock           += task_total_clock
            job_peak_memory_usage_gib = max(job_peak_memory_usage_gib, task_peak_memory_usage_gib)

        job_time_vcpu_seconds = job_time_instance_seconds*vcpu_per_instance[instance_type]
        job_cost_aws_dollars  = job_time_instance_seconds*hours_per_second*cost_aws_dollars_per_instance_hour[instance_type]
        job_cost_vray_dollars = job_time_vcpu_seconds*hours_per_second*cost_vray_dollars_per_vcpu_hour
        job_cpu_utilization   = float(job_used_clock)/float(job_total_clock)

        job_feasible_instance_types = array([ job_peak_memory_usage_gib <= max_memory_usage_fraction*memory_gib_per_instance[k] for k in instance_types_sorted ])
        assert any(job_feasible_instance_types)
        job_min_feasible_instance_type = instance_types_sorted[where(job_feasible_instance_types)[0][0]]

        df_jobs_curr = pd.DataFrame(columns=df_jobs_columns,
                                    data={"job_name":[job_name],
                                          "instance_type":[instance_type],
                                          "vcpu_per_instance":[vcpu_per_instance[instance_type]],
                                          "time_instance_seconds":[job_time_instance_seconds],
                                          "time_vcpu_seconds":[job_time_vcpu_seconds],
                                          "cost_cloud_dollars":[job_cost_aws_dollars],
                                          "cost_vray_dollars":[job_cost_vray_dollars],
                                          "used_clock":[job_used_clock],
                                          "total_clock":[job_total_clock],
                                          "cpu_utilization":[job_cpu_utilization],
                                          "peak_memory_usage_gib":[job_peak_memory_usage_gib],
                                          "min_feasible_instance_type":[job_min_feasible_instance_type],
                                          "camera_trajectory_included_in_dataset":[camera_trajectory_included_in_dataset]})

        df_jobs = df_jobs.append(df_jobs_curr, ignore_index=True)

        print("[HYPERSIM: DATASET_GENERATE_RENDERING_JOBS_STATISTICS_DEADLINE] " + job_name + " (AWS cost = " + str(job_cost_aws_dollars) + ", V-Ray cost = " + str(job_cost_vray_dollars) + ")")



df_jobs.to_csv(metadata_rendering_jobs_deadline_csv_file, index=False)
df_tasks.to_csv(metadata_rendering_tasks_deadline_csv_file, index=False)



print("[HYPERSIM: DATASET_GENERATE_RENDERING_JOBS_STATISTICS_DEADLINE] Finished.")
