import os
import time
import cv2
import numpy as np

LOG_FILE = "data/log_file_test_01.BIN"
if not os.path.exists(LOG_FILE) and os.path.exists("data/log_file_test_01.bin"):
    LOG_FILE = "data/log_file_test_01.bin"


def run_pymavlog():
    from pymavlog import MavLog
    time_start = time.perf_counter()
    mavlog = MavLog(LOG_FILE)
    mavlog.parse()
    count = len(mavlog.parsed_data)
    t_end = time.perf_counter() - time_start
    return count, [(0.0, 0), (t_end, count)]


def run_pymavlink():
    from pymavlink.DFReader import DFReader_binary
    t0 = time.perf_counter()
    log = DFReader_binary(LOG_FILE)
    count = 0
    points = [(0.0, 0)]
    while log.recv_msg() is not None:
        count += 1
        if count % 500000 == 0:
            points.append((time.perf_counter() - t0, count))
    t_end = time.perf_counter() - t0
    points.append((t_end, count))
    return count, points


def run_pymavlink_mavnative():
    os.environ["ENABLE_MAVNATIVE"] = "1"
    from pymavlink.DFReader import DFReader_binary
    t0 = time.perf_counter()
    log = DFReader_binary(LOG_FILE)
    count = 0
    points = [(0.0, 0)]
    while log.recv_msg() is not None:
        count += 1
        if count % 500000 == 0:
            points.append((time.perf_counter() - t0, count))
    t_end = time.perf_counter() - t0
    points.append((t_end, count))
    return count, points


def run_my_custom_engine():
    import mavparser
    t0 = time.perf_counter()
    res = mavparser.parse(LOG_FILE)
    count = len(res) if isinstance(res, list) else 0
    t_end = time.perf_counter() - t0
    return count, [(0.0, 0), (t_end, count)]


BENCHMARKS = [
    ("pymavlog (Baseline)", run_pymavlog),
    ("pymavlink (Pure Python)", run_pymavlink),
    ("pymavlink (mavnative)", run_pymavlink_mavnative),
    ("Custom C Engine (Your Code)", run_my_custom_engine),
]

print("Starting Benchmark Suite...\n")
results = {}
curves = {}

for name, func in BENCHMARKS:
    print(f"Running: {name}...")
    try:
        msg_count, points = func()
        elapsed = points[-1][0]
        results[name] = (elapsed, msg_count)
        curves[name] = points
        print(f"  -> Finished in {elapsed:.4f}s ({msg_count:,} msgs)")
    except Exception as e:
        print(f"  -> Skipped/Failed: {e}")

if not results:
    raise RuntimeError("No benchmark results were collected.")

img_h, img_w = 720, 1150
canvas = np.full((img_h, img_w, 3), (24, 26, 32), dtype=np.uint8)

cv2.putText(canvas, "Cumulative Parsing Progress Over Time", (40, 45),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)
cv2.putText(canvas, "Cumulative messages parsed (Y) vs execution time in seconds (X)", (40, 72),
            cv2.FONT_HERSHEY_SIMPLEX, 0.48, (170, 170, 170), 1, cv2.LINE_AA)

margin_left = 110
margin_right = 320
margin_top = 110
margin_bottom = 90

plot_w = img_w - margin_left - margin_right
plot_h = img_h - margin_top - margin_bottom

max_time = max(p[-1][0] for p in curves.values() if p)
max_msgs = max(p[-1][1] for p in curves.values() if p)
if max_msgs == 0: max_msgs = 1
if max_time == 0: max_time = 1.0

cv2.rectangle(canvas, (margin_left, margin_top), (margin_left + plot_w, margin_top + plot_h), (50, 55, 65), 1)

num_y_grid = 5
for i in range(num_y_grid + 1):
    val = (max_msgs / num_y_grid) * i
    y_pos = int(margin_top + plot_h - (i / num_y_grid) * plot_h)
    cv2.line(canvas, (margin_left, y_pos), (margin_left + plot_w, y_pos), (40, 44, 52), 1)
    lbl = f"{val/1e6:.1f}M" if max_msgs >= 1e6 else f"{int(val):,}"
    cv2.putText(canvas, lbl, (margin_left - 80, y_pos + 5),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

num_x_grid = 5
for i in range(num_x_grid + 1):
    val = (max_time / num_x_grid) * i
    x_pos = int(margin_left + (i / num_x_grid) * plot_w)
    cv2.line(canvas, (x_pos, margin_top), (x_pos, margin_top + plot_h), (40, 44, 52), 1)
    lbl = f"{val:.1f}s"
    cv2.putText(canvas, lbl, (x_pos - 15, margin_top + plot_h + 25),
                cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 160, 160), 1, cv2.LINE_AA)

cv2.putText(canvas, "Time (Seconds)", (margin_left + plot_w // 2 - 40, margin_top + plot_h + 60),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1, cv2.LINE_AA)

color_map = {
    "Custom C Engine (Your Code)": (0, 230, 115),     
    "pymavlink (Pure Python)": (240, 180, 50),      
    "pymavlink (mavnative)": (220, 100, 240),        
    "pymavlog (Baseline)": (80, 120, 240)            
}

card_x = img_w - margin_right + 25
card_y_start = margin_top

for i, (name, points) in enumerate(curves.items()):
    color = color_map.get(name, (200, 200, 200))

    pixel_pts = []
    for t, m in points:
        px = int(margin_left + (t / max_time) * plot_w)
        py = int(margin_top + plot_h - (m / max_msgs) * plot_h)
        pixel_pts.append((px, py))

    for j in range(len(pixel_pts) - 1):
        cv2.line(canvas, pixel_pts[j], pixel_pts[j + 1], color, 2, cv2.LINE_AA)

    for px, py in pixel_pts:
        cv2.circle(canvas, (px, py), 4, color, -1, cv2.LINE_AA)

    cy = card_y_start + i * 125
    cv2.rectangle(canvas, (card_x, cy), (card_x + 270, cy + 110), (35, 38, 48), -1)
    cv2.rectangle(canvas, (card_x, cy), (card_x + 270, cy + 110), color, 1)

    cv2.rectangle(canvas, (card_x + 12, cy + 15), (card_x + 24, cy + 27), color, -1)
    short_name = name.split("(")[0].strip()
    cv2.putText(canvas, short_name, (card_x + 32, cy + 26),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

    elapsed_t, total_m = results[name]
    rate = total_m / elapsed_t if elapsed_t > 0 else 0

    cv2.putText(canvas, f"Parsed: {total_m:,} msgs", (card_x + 12, cy + 50),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"Time: {elapsed_t:.2f}s", (card_x + 12, cy + 70),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, (210, 210, 210), 1, cv2.LINE_AA)
    cv2.putText(canvas, f"Speed: {rate:,.0f} msgs/s", (card_x + 12, cy + 90),
                cv2.FONT_HERSHEY_SIMPLEX, 0.42, color, 1, cv2.LINE_AA)

output_filename = "benchmark_relative_results.png"
cv2.imwrite(output_filename, canvas)
print(f"\nGraph saved successfully as: {output_filename}")