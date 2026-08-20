# mavparser

`mavparser` is a CPython extension for reading ArduPilot DataFlash `.BIN`
logs. Each message is a standard Python `dict` compatible in shape with
`pymavlink`'s `message.to_dict()` output.

```python
import mavparser

# Return every decoded message at once.
messages = mavparser.parse("data/00000081.BIN")

# Consume messages incrementally, without building a result list.
for message in mavparser.parse("data/00000081.BIN", mode="iterator"):
    print(message)
```

The parser recognises DataFlash `FMT` records before decoding their associated
messages. Unknown or malformed bytes are skipped safely while searching for the
next packet header.
