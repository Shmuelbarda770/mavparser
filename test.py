import mavparser

messages = mavparser.parse("data/00000081.BIN")

print(len(messages))
print(messages[:5])