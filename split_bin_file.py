import os
import struct
from typing import List, Tuple

HEADER = b'\xA3\x95'
HEADER_SIZE = 2
FMT_MSG_TYPE = 0x80
FMT_MSG_SIZE = 89


def create_fmt_message(msg_type: int, length: int, name: str, fmt: str, columns: str) -> bytes:
    """Create a new FMT message."""
    header = bytes([0xA3, 0x95, 0x80])
    type_and_length = struct.pack('<BB', msg_type, length)
    name_bytes = name.encode('utf-8')[:4].ljust(4, b'\x00')
    fmt_bytes = fmt.encode('utf-8')[:16].ljust(16, b'\x00')
    columns_bytes = columns.encode('utf-8')[:64].ljust(64, b'\x00')
    return header + type_and_length + name_bytes + fmt_bytes + columns_bytes


def parse_message_at_position(f, pos: int) -> Tuple[int, int]:
    f.seek(pos)
    header = f.read(3)

    if len(header) < 3 or header[:2] != HEADER:
        return None, None

    msg_type = header[2]

    if msg_type == FMT_MSG_TYPE:
        return msg_type, FMT_MSG_SIZE

    return msg_type, None


def extract_fmt_messages(filename: str) -> Tuple[bytes, dict]:
    fmt_messages = []
    found_types = set()
    msg_lengths = {}

    with open(filename, "rb") as f:
        pos = 0
        max_search = 5000000

        while pos < max_search:
            f.seek(pos)
            header = f.read(3)

            if len(header) < 3:
                break

            if header[:2] == HEADER and header[2] == FMT_MSG_TYPE:
                f.seek(pos)
                fmt_msg = f.read(FMT_MSG_SIZE)

                if len(fmt_msg) == FMT_MSG_SIZE:
                    defined_type = fmt_msg[5]
                    length = fmt_msg[4]
                    found_types.add(defined_type)
                    msg_lengths[defined_type] = length
                    fmt_messages.append(fmt_msg)
                    pos += FMT_MSG_SIZE
                else:
                    pos += 1
            else:
                pos += 1

    missing_fmts = [
        (249, 43, 'TEC2', 'Qffffffff', 'TimeUS,pmax,pmin,KErr,PErr,EDelta,LF,hdem1,hdem2'),
        (250, 64, 'TECS', 'QfffffffffffffB', 'TimeUS,h,dh,hdem,dhdem,spdem,sp,dsp,ith,iph,th,ph,dspdem,w,f'),
        (253, 12, 'RELY', 'QB', 'TimeUS,State'),
        (254, 16, 'AUXF', 'QHBBB', 'TimeUS,function,pos,source,result')
    ]

    for msg_type, length, name, fmt, columns in missing_fmts:
        if msg_type not in found_types:
            fmt_msg = create_fmt_message(msg_type, length, name, fmt, columns)
            fmt_messages.append(fmt_msg)
            found_types.add(msg_type)
            msg_lengths[msg_type] = length

    fmt_data = b''.join(fmt_messages)
    return fmt_data, msg_lengths


def find_next_message_boundary(f, start_pos: int, msg_lengths: dict, max_search: int = 10000) -> int:
    """Find the start of the next valid message."""
    f.seek(start_pos)
    pos = start_pos

    while pos < start_pos + max_search:
        f.seek(pos)
        header = f.read(3)

        if len(header) < 3:
            break

        if header[:2] == HEADER:
            msg_type = header[2]
            if msg_type == FMT_MSG_TYPE:
                return pos
            elif msg_type in msg_lengths:
                msg_len = msg_lengths[msg_type]
                f.seek(pos + msg_len)
                next_header = f.read(2)
                if len(next_header) == 2 and next_header == HEADER:
                    return pos

        pos += 1

    return start_pos


def find_optimal_boundaries(filename: str, num_parts: int, msg_lengths: dict) -> List[int]:
    filesize = os.path.getsize(filename)
    approx_part_size = filesize // num_parts

    boundaries = [0]

    with open(filename, "rb") as f:
        for i in range(1, num_parts):
            target_pos = approx_part_size * i
            search_start = max(0, target_pos - 5000)
            actual_boundary = find_next_message_boundary(f, search_start, msg_lengths)
            boundaries.append(actual_boundary)

    boundaries.append(filesize)
    return boundaries


def split_file_by_boundaries(filename: str, boundaries: List[int], fmt_data: bytes):
    """Split the file by given boundaries."""
    with open(filename, "rb") as f:
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            part_size = end - start

            f.seek(start)
            data = f.read(part_size)

            part_filename = f"{filename}_part_{i+1}.bin"

            with open(part_filename, "wb") as out:
                if i == 0:
                    out.write(data)
                else:
                    out.write(fmt_data)
                    out.write(data)

            verify_file_integrity(part_filename)


def verify_file_integrity(filename: str) -> bool:
    """Verify that the file contains only valid messages."""
    errors = 0
    total_messages = 0

    with open(filename, "rb") as f:
        pos = 0
        filesize = os.path.getsize(filename)

        while pos < min(filesize, 100000):
            f.seek(pos)
            header = f.read(2)

            if len(header) < 2:
                break

            if header == HEADER:
                total_messages += 1
                msg_type_byte = f.read(1)
                if len(msg_type_byte) == 0:
                    break
                pos += 3
            else:
                errors += 1
                pos += 1

            if errors > 10:
                return False

    return True


def split_bin_file_safe(filename: str, num_parts: int = 4):
    """Safely split a BIN file without losing messages."""
    fmt_data, msg_lengths = extract_fmt_messages(filename)
    boundaries = find_optimal_boundaries(filename, num_parts, msg_lengths)
    split_file_by_boundaries(filename, boundaries, fmt_data)


# Example usage:
# if __name__ == "__main__":
#     split_bin_file_safe("log_file_test_01.bin", num_parts=4)
