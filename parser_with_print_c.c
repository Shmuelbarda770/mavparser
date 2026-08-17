#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>
#include <inttypes.h> 

#define MAX_FORMATS 256
#define MAX_COLUMNS 64
#define MAX_FIELD_SIZE 128

typedef struct {
    char name[5];
    char format[17];
    char columns[MAX_COLUMNS][MAX_FIELD_SIZE];
    int num_columns;
    uint8_t msg_len;
    int struct_size;
} FormatDef;

typedef struct {
    FormatDef formats[MAX_FORMATS];
    int msg_count;
} MAVLinkParser;



int calculate_struct_size(const char* fmt_str) {
    int size = 0;
    for (int i = 0; fmt_str[i] != '\0'; i++) {
        switch (fmt_str[i]) {
            case 'b': case 'B': case 'M': size += 1; break;
            case 'h': case 'H': case 'c': case 'C': size += 2; break;
            case 'i': case 'I': case 'f': case 'e': case 'E': case 'L': size += 4; break;
            case 'd': case 'q': case 'Q': size += 8; break;
            case 'n': size += 4; break;
            case 'N': size += 16; break;
            case 'Z': size += 64; break;
        }
    }
    return size;
}



void print_value(const uint8_t** ptr, char fmt_char) {
    switch (fmt_char) {
        case 'b': { int8_t v = **(int8_t**)ptr; *ptr += 1; printf("%d", v); break; }
        case 'B': { uint8_t v = **ptr; *ptr += 1; printf("%u", v); break; }
        case 'h': { int16_t v; memcpy(&v, *ptr, 2); *ptr += 2; printf("%d", v); break; }
        case 'H': { uint16_t v; memcpy(&v, *ptr, 2); *ptr += 2; printf("%u", v); break; }
        case 'i': { int32_t v; memcpy(&v, *ptr, 4); *ptr += 4; printf("%d", v); break; }
        case 'I': { uint32_t v; memcpy(&v, *ptr, 4); *ptr += 4; printf("%u", v); break; }
        case 'f': { float v; memcpy(&v, *ptr, 4); *ptr += 4; printf("%f", v); break; }
        case 'd': { double v; memcpy(&v, *ptr, 8); *ptr += 8; printf("%lf", v); break; }
        case 'q': { int64_t v; memcpy(&v, *ptr, 8); *ptr += 8; printf("%" PRId64, v); break; }
        case 'Q': { uint64_t v; memcpy(&v, *ptr, 8); *ptr += 8; printf("%" PRIu64, v); break; }
        case 'n': { uint32_t v; memcpy(&v, *ptr, 4); *ptr += 4; printf("%u", v); break; }
        case 'Z': { char str[65]; memcpy(str, *ptr, 64); str[64] = 0; *ptr += 64; printf("\"%s\"", str); break; }
        default: printf("?"); break;
    }
}


int parse_fmt_message(MAVLinkParser* parser, const uint8_t* data, size_t offset, size_t file_size, int* success) {
    *success = 0;
    int header_size = 3;
    int fmt_size = 86;

    if (offset + header_size + fmt_size > file_size) {
        return 1;
    }

    const uint8_t* msg_data = data + offset + header_size;

    uint8_t msg_type = msg_data[0];
    uint8_t msg_len = msg_data[1];

    char name[5] = {0};
    memcpy(name, msg_data + 2, 4);

    char fmt_str[17] = {0};
    memcpy(fmt_str, msg_data + 6, 16);

    char columns_str[65] = {0};
    memcpy(columns_str, msg_data + 22, 64);

    FormatDef* fmt = &parser->formats[msg_type];
    strncpy(fmt->name, name, 5);
    fmt->name[4] = '\0';
    strncpy(fmt->format, fmt_str, 17);
    fmt->format[16] = '\0';
    fmt->msg_len = msg_len;
    fmt->struct_size = calculate_struct_size(fmt_str);

    fmt->num_columns = 0;
    char columns_copy[65];
    strncpy(columns_copy, columns_str, 64);
    columns_copy[64] = '\0';
    char* token = strtok(columns_copy, ",");
    while (token != NULL && fmt->num_columns < MAX_COLUMNS) {
        while (*token == ' ') token++;
        strncpy(fmt->columns[fmt->num_columns], token, MAX_FIELD_SIZE - 1);
        fmt->columns[fmt->num_columns][MAX_FIELD_SIZE - 1] = '\0';
        fmt->num_columns++;
        token = strtok(NULL, ",");
    }

    *success = 1;
    return header_size + fmt_size;
}


int parse_data_message(MAVLinkParser* parser, const uint8_t* data, size_t offset, 
                       size_t file_size, uint8_t msg_type, int* success) {
    *success = 0;
    FormatDef* fmt = &parser->formats[msg_type];
    int header_size = 3;
    int data_size = fmt->struct_size;

    if (offset + header_size + data_size > file_size) {
        return 1;
    }

    const uint8_t* msg_data = data + offset + header_size;
    const uint8_t* p = msg_data;

    // printf("Message [%s] type=%u len=%u → ", fmt->name, msg_type, fmt->msg_len);
    // for (int i = 0; i < fmt->num_columns && fmt->format[i] != '\0'; i++) {
    //     printf("%s=", fmt->columns[i]);
    //     print_value(&p, fmt->format[i]);
    //     if (i < fmt->num_columns - 1) printf(", ");
    // }
    // printf("\n");

    *success = 1;
    return header_size + data_size;
}


int parse_message(MAVLinkParser* parser, const uint8_t* data, size_t offset, 
                  size_t file_size, uint8_t msg_type, int* msg_valid) {
    *msg_valid = 0;

    if (msg_type == 0x80) {
        int success = 0;
        int bytes_read = parse_fmt_message(parser, data, offset, file_size, &success);
        *msg_valid = success;
        return bytes_read;
    }

    if (parser->formats[msg_type].name[0] != '\0') {
        int success = 0;
        int bytes_read = parse_data_message(parser, data, offset, file_size, msg_type, &success);
        *msg_valid = success;
        return bytes_read;
    }

    *msg_valid = 0;
    return 3;
}


void parse(MAVLinkParser* parser, const char* filename) {
    int msg_count = 0;

    int fd = open(filename, O_RDONLY);
    if (fd == -1) {
        perror("Error opening file");
        return;
    }

    struct stat sb;
    if (fstat(fd, &sb) == -1) {
        perror("Error getting file size");
        close(fd);
        return;
    }
    size_t file_size = sb.st_size;

    uint8_t* data = mmap(NULL, file_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (data == MAP_FAILED) {
        perror("Error mapping file");
        close(fd);
        return;
    }

    const uint8_t HEADER_PATTERN[2] = {0xA3, 0x95};
    size_t offset = 0;

    while (offset < file_size - 3) {
        uint8_t* pos = memmem(data + offset, file_size - offset, HEADER_PATTERN, 2);
        if (pos == NULL) break;
        size_t found_offset = pos - data;
        if (found_offset + 2 >= file_size) break;

        uint8_t msg_type = data[found_offset + 2];

        int msg_valid = 0;
        int bytes_read = parse_message(parser, data, found_offset, file_size, msg_type, &msg_valid);
        if (msg_valid) msg_count += 1;

        offset = found_offset + (bytes_read > 0 ? bytes_read : 1);
    }

    printf("Total messages parsed: %d\n", msg_count);

    munmap(data, file_size);
    close(fd);
}



int main() {
    clock_t start = clock();

    MAVLinkParser parser = {0};
    parse(&parser, "log_file_test_01.bin");

    clock_t end = clock();
    double duration = ((double)(end - start)) / CLOCKS_PER_SEC;
    printf("   Time: %.6f seconds\n", duration);

    return 0;
}
