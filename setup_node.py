#  Move need files over to ESP32. It assumes 1:1 file and directory match
# Required: ampy installed
import os
from contextlib import suppress
import argparse
import ast
import subprocess


# Convert --ports '["/dev/ttyS16", "/dev/ttyS7"]' to an array of strings
def args_ports(string):
    return ast.literal_eval(string)


# Generate base ampy command w/ baud and port(s)
parser = argparse.ArgumentParser()
parser.add_argument('--ports', help='Serial port', type=args_ports, required=False)
parser.add_argument('--baud', help='Serial baud', type=str, required=True)
args = parser.parse_args()
print(args)

itemNames = [
    'boot.py',
    'main.py',
    'credentials.py',
    'config_lora.py',
    'www'
]  # files/directories to be copied over, ( name, is_dir)


# determine which ampy operation needs to be performed
def ampy_operation(path, port, is_dir):
    root_ampy_cmd = f'ampy --port {port} --baud {args.baud}'
    if is_dir:
        ampy_cmd(f'{root_ampy_cmd} rmdir {path}', True)
        ampy_cmd(f'{root_ampy_cmd} put {path}/')
    else:
        ampy_cmd(f'{root_ampy_cmd} put {path}')


def ampy_cmd(cmd, rm_dir=False):
    print(cmd, end='', flush=True)
    print(' ...', end='', flush=True)
    os.system(cmd)
    try:
        if rm_dir:
            # Note: trying to suppress error since we dont care if folder isnt found but doesnt work
            subprocess.check_output(cmd, shell=True,
                                    stderr=subprocess.STDOUT)  # delete dir if its there, this will fail if the destination folder is not present
        else:
            os.system(cmd)
        print('COMPLETED')
    except Exception as error:
        print('FAILED')


for port in args.ports:
    for name in itemNames:
        is_dir = os.path.isdir('./' + name)  # use relative path to determine if its file or dir
        ampy_operation(name, port, is_dir)
