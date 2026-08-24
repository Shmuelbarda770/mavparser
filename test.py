# import mavparser
# import time
# s=time.time()
# messages = mavparser.parse("data/ArduPlane-PPPPeriph-00000484.BIN")
# print(time.time() - s)
# print(len(messages))
# print(messages[:5])

import time
from pymavlink import mavutil

log_path = "data/ArduPlane-TerrainMission-autotest-1787233492431164.tlog"

# Start timer
start_time = time.perf_counter()

mav = mavutil.mavlink_connection(log_path)
msg_count = 0

# Silent parsing loop
while True:
    msg = mav.recv_match(blocking=False)
    if msg is None:
        break
    msg_count += 1

# Stop timer
elapsed_time = time.perf_counter() - start_time

print(f"Parsed {msg_count:,} messages in {elapsed_time:.4f} seconds.")
if elapsed_time > 0:
    print(f"Parsing rate: {int(msg_count / elapsed_time):,} messages/second.")