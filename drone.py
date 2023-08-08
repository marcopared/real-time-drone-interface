import sys
sys.path.append('./rktellolib/src')
from rktellolib import Tello
import time
import re

start_time = time.time()

def dead_reckoning(x, y, z, vgx, vgy, vgz, time_diff=0.1):
    x = round(x + vgx * time_diff, 2)
    y = round(y + vgy * time_diff, 2)
    z = round(z + vgz * time_diff, 2)
    return x, y, z

def parse(data):
    match = re.search(r'vgx:(-?\d+);vgy:(-?\d+);vgz:(-?\d+)', data)
    if match:
        vgx, vgy, vgz = map(int, match.groups())
        vgx, vgy, vgz = vgx*-1, vgy*-1, vgz*-1
        current_time = round(time.time() - start_time, 1) # Gets the current time in seconds since the epoch
        print(f'Time: {current_time}, vgx: {vgx}, vgy: {vgy}, vgz: {vgz}')
        return current_time, vgx, vgy, vgz

def read_telemetry():
    x, y, z = 0, 0, 0
    with open("sample_data.txt", "r") as f:
        for line in f:
            time.sleep(0.1)
            current_time, vgx, vgy, vgz = parse(line)
            x, y, z = dead_reckoning(x, y, z, vgx, vgy, vgz)
            print(f'Position: ({x}, {y}, {z})')

if __name__ == '__main__':
    read_telemetry()
