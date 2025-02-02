# Copyright 2023 ByteDance and/or its affiliates.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import argparse
import pathlib
import logging
import subprocess

CUR_DIR = pathlib.Path.cwd().absolute()
BYTE_MLPERF_ROOT = pathlib.Path(__file__).parent.absolute()
sys.path.insert(0, BYTE_MLPERF_ROOT)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lanuch")


def parse_task(task_dir):
    tasks = []
    if os.path.isdir(task_dir):
        for root, _, files in os.walk(task_dir, topdown=False):
            for name in files:
                if name.endswith(".json"):
                    tasks.append(name.rsplit('.', 1)[0])
    return tasks



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    # hardware config
    parser.add_argument(
        "--hardware_type",
        default="GPU", 
        help="The backend going to be evaluted, refs to backends/",
    )
    parser.add_argument(
        "--vendor_path",
        help="The hardware configs need to be loaded, refs to vendor_zoo/",
    )

    # task config
    parser.add_argument(
        "--task_dir", 
        default=str(BYTE_MLPERF_ROOT.joinpath("workloads").absolute()), 
        help="The direcotry of tasks going to be evaluted, e.g., set to workloads"
    )
    parser.add_argument(
        "--task", 
        default="all", 
        help="The task going to be evaluted, refs to workloads/, default use all tasks in workloads/"
    )

    # list all supported task and hardware
    parser.add_argument(
        "--show_task_list", 
        action="store_true", 
        help="Print all available task names"
    )
    parser.add_argument(
        "--show_hardware_list",
        action="store_true",
        help="Print all hardware bytemlperf supported",
    )

    # feature control
    parser.add_argument(
        "--install_requirements", action="store_true", 
        help="Install all required packages"
    )
    parser.add_argument(
        "--activate_venv", action="store_true",
        help="Enable python virtual environment"
    )
    args = parser.parse_args()

    args.vendor_path = pathlib.Path(args.vendor_path).absolute() if args.vendor_path else None
    args.task_dir = pathlib.Path(args.task_dir).absolute()
    os.chdir(str(BYTE_MLPERF_ROOT))


    # show tasks
    task_list = [file.stem for file in args.task_dir.iterdir()]
    task_list.sort()

    task_mapping = {
        "all": task_list, 
        "gemm_ops": [], 
        "unary_ops": [], 
        "binary_ops": [], 
        "reduction_ops": [], 
        "index_ops": [], 
        "ccl_ops": [], 
        "h2d_ops": []
    }
    for task in task_list:
        if task in ["gemm", "gemv", "batch_gemm", "group_gemm"]:
            task_mapping["gemm_ops"].append(task)

        if task in ["sin", "cos", "exp", "exponential", "silu", "gelu", "swiglu", "cast"]:
            task_mapping["unary_ops"].append(task)

        if task in ["add", "mul", "sub", "div"]:
            task_mapping["binary_ops"].append(task)

        if task in ["layernorm", "softmax", "reduce_sum", "reduce_max", "reduce_min"]:
            task_mapping["reduction_ops"].append(task)
        
        if task in ["index_add", "sort", "unique", "gather", "scatter"]:
            task_mapping["index_ops"].append(task)

        if task in ["allgather", "allreduce", "alltoall", "broadcast", "p2p", "reduce_scatter"]:
            task_mapping["ccl_ops"].append(task)
        
        if task in ["host2device", "device2host", "device2device"]:
            task_mapping["h2d_ops"].append(task)
    

    if args.show_task_list:
        logger.info("******************* Supported Task *******************")
        print(task_list)        
        exit(0)

    # show hardwares
    hardware_list = []
    for file in BYTE_MLPERF_ROOT.joinpath("backends").iterdir():
        if file.is_dir() and file.stem.startswith("_") is False:
            hardware_list.append(file.stem)
    if args.show_hardware_list:
        logger.info("***************** Supported Hardware Backend *****************")
        print(hardware_list)
        exit(0)

    # check task
    test_cases = []
    if args.task in task_mapping.keys():
        test_cases = task_mapping[args.task]
    else:
        specified_tasks = args.task.split(",")
        for task in specified_tasks:
            if task not in task_list:
                logger.error(f"Task {task} not found in {args.task_dir}")
                exit(1)
            test_cases.append(task)

    logger.info(f"******************* Tasks: *****************")
    logger.info(f"{test_cases}\n")


    # check hardware
    hardware = args.hardware_type
    if hardware not in hardware_list:
        logger.error(f"Hardware {hardware} not found in {BYTE_MLPERF_ROOT.joinpath('backends')}")
        exit(1)

    logger.info(f"******************* hardware: *****************")
    logger.info(f"{hardware}\n")

    if args.install_requirements:
        logger.info("******************* Pip Package Installing *******************")
        subprocess.run(
            "python3 -m pip install --upgrade pip --quiet", 
            shell=True
        )
        subprocess.run(
            "python3 -m pip install -r requirements.txt --quiet", 
            shell=True
        )
        if not args.activate_venv and BYTE_MLPERF_ROOT.joinpath("backends", args.hardware_type, "requirements.txt").exists():
            subprocess.run(
                f"python3 -m pip install -r backends/{args.hardware_type}/requirements.txt --quiet",
                shell=True
            )

    failed_tasks = []
    for task in test_cases:

        activate_venv = "--activate_venv" if args.activate_venv else ""

        cmd = f"python3 ./core/perf_engine.py --hardware_type {args.hardware_type} --task {task} --vendor_path {args.vendor_path} --task_dir {args.task_dir} {activate_venv}"
        exit_code = subprocess.call(cmd, shell=True)
        if exit_code != 0:
            failed_tasks.append(task)
        
    if failed_tasks:
        logger.error(f"Failed tasks: {failed_tasks}")
        exit(1)
