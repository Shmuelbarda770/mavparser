#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <unistd.h>

#ifndef ntohll
#if defined(__APPLE__)
#include <libkern/OSByteOrder.h>
#define ntohll(x) OSSwapBigToHostInt64(x)
#else
#define ntohll(x) be64toh(x)
#endif
#endif

typedef void (*msg_callback_t)(uint64_t timestamp, uint32_t msg_id, const void* payload, uint8_t payload_len);

size_t parse_tlog_fast(const char* filepath, msg_callback_t callback, size_t max_callbacks) {
    int fd = open(filepath, O_RDONLY);
    if (fd < 0) return 0;

    struct stat st;
    if (fstat(fd, &st) < 0) {
        close(fd);
        return 0;
    }

    size_t filesize = st.st_size;
    uint8_t* map = (uint8_t*)mmap(NULL, filesize, PROT_READ, MAP_SHARED, fd, 0);
    if (map == MAP_FAILED) {
        close(fd);
        return 0;
    }

#ifdef MADV_SEQUENTIAL
    madvise(map, filesize, MADV_SEQUENTIAL);
#endif

    size_t offset = 0;
    size_t msg_count = 0;
    size_t callbacks_sent = 0;

    while (offset + 8 < filesize) {
        uint64_t raw_time = *(uint64_t*)(map + offset);
        uint64_t timestamp_us = ntohll(raw_time);
        offset += 8;

        if (offset >= filesize) break;

        uint8_t magic = map[offset];
        size_t header_len = 0;
        size_t pkt_len = 0;
        uint32_t msg_id = 0;
        uint8_t payload_len = 0;

        if (magic == 0xFD) { // MAVLink v2
            if (offset + 10 > filesize) break;
            payload_len = map[offset + 1];
            uint8_t incompat_flags = map[offset + 2];
            msg_id = map[offset + 7] | (map[offset + 8] << 8) | (map[offset + 9] << 16);
            header_len = 10;
            size_t sig_len = (incompat_flags & 0x01) ? 13 : 0;
            pkt_len = header_len + payload_len + 2 + sig_len;
        } else if (magic == 0xFE) { // MAVLink v1
            if (offset + 6 > filesize) break;
            payload_len = map[offset + 1];
            msg_id = map[offset + 5];
            header_len = 6;
            pkt_len = header_len + payload_len + 2;
        } else {
            offset -= 7;
            continue;
        }

        const uint8_t* payload = map + offset + header_len;

        if (callback && callbacks_sent < max_callbacks) {
            callback(timestamp_us, msg_id, payload, payload_len);
            callbacks_sent++;
        }

        offset += pkt_len;
        msg_count++;
    }

    munmap(map, filesize);
    close(fd);

    return msg_count;
}