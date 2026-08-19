from pymavlink import mavutil
from datetime import datetime

try:
    start_time = datetime.now()  

    mav = mavutil.mavlink_connection('data/log_file_test_01.bin')
    count = 0
    errors = 0

    while True:
        msg = mav.recv_match().to_dict()
        print(msg)
        if msg is None:
            break

except Exception as e:
    print(f'Part : Error - {str(e)[:100]}')

end_time = datetime.now() 
duration = end_time - start_time

print(f'Time taken: {duration}')
