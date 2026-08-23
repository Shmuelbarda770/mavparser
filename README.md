# mavparser

[![PyPI version](https://img.shields.io/pypi/v/mavparser.svg)](https://pypi.org/project/mavparser/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> ⚡ **Blazing-fast C-extension parser for ArduPilot DataFlash binary (`.BIN`) logs.**

`mavparser` is a high-performance Python library written in native C, designed to parse ArduPilot DataFlash binary log files up to **10x–30x faster** than pure-Python implementations such as `pymavlink`.

---

## 🚀 Key Features

* ⚡ **Extreme Speed** — Decodes over **1.5 million messages per second** with 60+ MB/s throughput.
* 🧩 **C-Native Core** — Binary parsing is implemented directly as a CPython extension for minimal overhead.
* 🌍 **Cross-Platform Wheels** — Pre-compiled binaries available for:

  * Linux (`x86_64`, `aarch64`)
  * macOS (Intel, Apple Silicon)
  * Windows
  * Python 3.9–3.13
* 📦 **Zero Runtime Dependencies** — Pure C implementation with no third-party runtime requirements.

---

## 📦 Installation

```bash
pip install mavparser
```

---

## 💡 Usage

### Mode 1: Batch Parsing — `mavparser.parse()`

Parses the entire `.BIN` log into a Python `list` in memory.

Ideal for fast slicing, indexing, and small-to-medium-sized files.

```python
import mavparser

# Parse the entire log file into a list of dictionaries
messages = mavparser.parse("flight_log.BIN")

print(f"Total messages parsed: {len(messages):,}")

# Access messages directly
print("First message:", messages[0])
print("Last message:", messages[-1])

# Filter in memory
gps_data = [msg for msg in messages if msg.get("type") == "GPS"]

print(f"Total GPS records: {len(gps_data):,}")
```

### Mode 2: Streaming Parsing — `mavparser.parse()`

Processes messages sequentially using a Python generator.

Ideal for huge log files where loading the entire file into memory is undesirable.

```python
import mavparser

gps_count = 0
high_alt_count = 0

# Stream messages without allocating a giant list in RAM
for msg in mavparser.parse("flight_log.BIN"):
    if msg.get("mavpackettype") == "GPS":
        gps_count += 1
        if msg.get("Alt", 0) > 100:
            high_alt_count += 1

print(f"Stream complete! Found {gps_count:,} GPS messages ({high_alt_count:,} above 100m).")
```

---

## 📊 Benchmark

Tested on a **285.91 MB** ArduPilot `.BIN` log containing approximately **7,597,096 messages**.

| Parser                        | Execution Time | Processing Speed |     Performance |
| ----------------------------- | -------------: | ---------------: | --------------: |
| **`mavparser` (C Extension)** |  **~4.69 sec** |   **~61.0 MB/s** | **1× baseline** |
| `pymavlink`                   |     ~95.20 sec |        ~3.0 MB/s | **~13× slower** |

> **Note:** Benchmark results depend on hardware, Python version, storage performance, and log characteristics.

---

## 📜 License

Distributed under the [MIT License](LICENSE).
