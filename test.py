import mavparser

messages = mavparser.parse("data/log_file_test_01.BIN")

print(len(messages))
print(messages[:5])