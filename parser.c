#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <time.h>

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

int parse_fmt_message(MAVLinkParser* parser, const uint8_t* data, size_t offset, size_t file_size, int* success) {
    *success = 0;
    
    // try:
    int header_size = 3;
    int fmt_size = 86; // struct.Struct('<BB4s16s64s').size
    
    // if offset + header_size + fmt_size > len(data):
    //     return None, 1
    if (offset + header_size + fmt_size > file_size) {
        return 1;
    }
    
    const uint8_t* msg_data = data + offset + header_size;
    
    // msg_type, msg_len, name, fmt, columns = self.fmt_struct.unpack(msg_data)
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
    
    // columns_str.split(',')
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
    
    // return {'type': 'FMT'}, header_size + fmt_size
    *success = 1;
    return header_size + fmt_size;
    
    // except Exception:
    //     return None, 1
}

int parse_data_message(MAVLinkParser* parser, const uint8_t* data, size_t offset, 
                       size_t file_size, uint8_t msg_type, int* success) {
    *success = 0;
    
    // try:
    // fmt_def = self.formats[msg_type]
    FormatDef* fmt = &parser->formats[msg_type];
    
    int header_size = 3;
    int data_size = fmt->struct_size;
    
    // if offset + header_size + data_size > len(data):
    //     return None, 1
    if (offset + header_size + data_size > file_size) {
        return 1;
    }
    
    // msg_data = data[offset + header_size:offset + header_size + data_size]
    // values = compiled_struct.unpack(msg_data)
    // msg = True
    *success = 1;
    
    // return msg, header_size + data_size
    return header_size + data_size;
    
    // except Exception:
    //     return None, 1
}

int parse_message(MAVLinkParser* parser, const uint8_t* data, size_t offset, 
                  size_t file_size, uint8_t msg_type, int* msg_valid) {
    *msg_valid = 0;

    if (msg_type == 0x80) {
        int success = 0;
        int bytes_read = parse_fmt_message(parser, data, offset, file_size, &success);
        *msg_valid = success; // {'type': 'FMT'} is truthy
        return bytes_read;
    }
    
    //     if msg_type in self.formats:
    //         return self.parse_data_message(data, offset, msg_type)
    if (parser->formats[msg_type].name[0] != '\0') {
        int success = 0;
        int bytes_read = parse_data_message(parser, data, offset, file_size, msg_type, &success);
        *msg_valid = success; // msg = True
        return bytes_read;
    }
    
    //     return None, 3
    *msg_valid = 0; // None is falsy
    return 3;
    
    // except Exception:
    //     return None, 1
}
void parse(MAVLinkParser* parser, const char* filename) {
    int msg_count = 0;
    
    // with open(self.filename, 'rb') as f:
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
    
    // with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
    uint8_t* data = mmap(NULL, file_size, PROT_READ, MAP_PRIVATE, fd, 0);
    if (data == MAP_FAILED) {
        perror("Error mapping file");
        close(fd);
        return;
    }
    
    // file_size = len(mmapped_file)
    // offset = 0
    const uint8_t HEADER_PATTERN[2] = {0xA3, 0x95};
    size_t offset = 0;
    
    // while offset < file_size - 3:
    while (offset < file_size - 3) {
        // pos = mmapped_file.find(self.HEADER_PATTERN, offset)
        uint8_t* pos = memmem(data + offset, file_size - offset, HEADER_PATTERN, 2);
        
        // if pos == -1:
        //     break
        if (pos == NULL) {
            break;
        }
        
        size_t found_offset = pos - data;
        
        // if pos + 2 >= file_size:
        //     break
        if (found_offset + 2 >= file_size) {
            break;
        }
        
        // msg_type = mmapped_file[pos + 2]
        uint8_t msg_type = data[found_offset + 2];
        
        // msg, bytes_read = self._parse_message(mmapped_file, pos, msg_type)
        int msg_valid = 0;
        int bytes_read = parse_message(parser, data, found_offset, file_size, msg_type, &msg_valid);
        
        // if msg:
        //     msg_count += 1
        if (msg_valid) {
            msg_count += 1;
        }
        
        // offset = pos + (bytes_read if bytes_read > 0 else 1)
        offset = found_offset + (bytes_read > 0 ? bytes_read : 1);
    }
    
    // print(msg_count)
    printf("%d\n", msg_count);
    
    munmap(data, file_size);
    close(fd);
}

int main() {
    // start = datetime.now()
    clock_t start = clock();
    
    MAVLinkParser parser = {0};
    
    parse(&parser, "log_file_test_01.bin");
    
    clock_t end = clock();
    double duration = ((double)(end - start)) / CLOCKS_PER_SEC;
    printf("   Time: %.6f seconds\n", duration);
    
    return 0;
}
