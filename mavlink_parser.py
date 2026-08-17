from pymavlink import mavutil
from datetime import datetime

try:
    start_time = datetime.now()  

    mav = mavutil.mavlink_connection('log_file_test_01.bin')
    count = 0
    errors = 0

    while True:
        msg = mav.recv_match()
        if msg is None:
            break
        count += 1

except Exception as e:
    errors += 1
    print(f'Part : Error - {str(e)[:100]}')

end_time = datetime.now() 
duration = end_time - start_time

print(f'Part : Parsed {count} messages with {errors} errors.')
print(f'Time taken: {duration}')
