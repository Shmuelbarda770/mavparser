import struct
from datetime import datetime
from split_bin_file import split_bin_file_safe
class MAVLinkBinParser:
    
    HEAD1 = 0xA3
    HEAD2 = 0x95
    
    FORMAT_TO_STRUCT = {
        'b': 'b',  # int8_t
        'B': 'B',  # uint8_t
        'h': 'h',  # int16_t
        'H': 'H',  # uint16_t
        'i': 'i',  # int32_t
        'I': 'I',  # uint32_t
        'f': 'f',  # float
        'd': 'd',  # double
        'n': '4s', # char[4]
        'N': '16s',# char[16]
        'Z': '64s',# char[64]
        'c': 'h',  # int16_t * 100
        'C': 'H',  # uint16_t * 100
        'e': 'i',  # int32_t * 100
        'E': 'I',  # uint32_t * 100
        'L': 'i',  # latitude/longitude
        'M': 'B',  # flight mode
        'q': 'q',  # int64_t
        'Q': 'Q',  # uint64_t
    }
    
    def __init__(self, filename):
        self.filename = filename
        self.formats = {}
        self.messages = []
        self.data = None
        
    def read_file(self):
        with open(self.filename, 'rb') as f:
            self.data = f.read()
        print(f"File loaded: {len(self.data)} bytes")
        return self.data
    
    def parse(self):
        if not self.data:
            self.read_file()
        
        offset = 0
        msg_count = 0
        
        while offset < len(self.data) - 3:
            if self.data[offset] == self.HEAD1 and self.data[offset + 1] == self.HEAD2:
                
                msg_type = self.data[offset + 2]
                
                msg, bytes_read = self.parse_message(offset, msg_type)
                
                if msg:
                    msg_count += 1
                
                offset += bytes_read if bytes_read > 0 else 1
            else:
                offset += 1
        return self.messages

    def parse_message(self, offset, msg_type):
        try:
            if msg_type == 0x80:
                return self.parse_fmt_message(offset)
            
            if msg_type in self.formats:
                return self.parse_data_message(offset, msg_type)
            
            return None, 3
            
        except Exception:
            return None, 1
    
    def parse_fmt_message(self, offset):
        try:
            # FMT format: HEAD1, HEAD2, 0x80, Type, Length, Name, Format, Columns
            header_size = 3
            fmt_struct = '<BB4s16s64s'
            fmt_size = struct.calcsize(fmt_struct)
            data = self.data[offset + header_size:offset + header_size + fmt_size]
            
            msg_type, msg_len, name, fmt, columns = struct.unpack(fmt_struct, data)
            
            # Clean strings
            name = name.rstrip(b'\x00').decode('utf-8')
            fmt = fmt.rstrip(b'\x00').decode('utf-8')
            columns = columns.rstrip(b'\x00').decode('utf-8')
            
            # Store format definition
            self.formats[msg_type] = {
                'name': name,
                'format': fmt,
                'columns': columns.split(','),
                'length': msg_len
            }
            
            msg = {
                'type': 'FMT',
                'msg_type': msg_type,
                'name': name,
                'format': fmt,
                'columns': columns
            }
            return msg, header_size + fmt_size
            
        except Exception:
            return None, 1
    
    def parse_data_message(self, offset, msg_type):
        try:
            fmt_def = self.formats[msg_type]
         
            struct_fmt = '<'  # little-endian
            for c in fmt_def['format']:
                if c in self.FORMAT_TO_STRUCT:
                    struct_fmt += self.FORMAT_TO_STRUCT[c]
           
            data_size = struct.calcsize(struct_fmt)
            header_size = 3
            
            data = self.data[offset + header_size:offset + header_size + data_size]
            if len(data) < data_size:
                return None, 1
            
            values = struct.unpack(struct_fmt, data)
            msg = {
                'type': fmt_def['name'],
                'msg_type': msg_type
            }
            
            col_names = fmt_def['columns']
            for i, val in enumerate(values):
                if i < len(col_names):
                    col_name = col_names[i].strip()
                    if col_name:
                        if isinstance(val, bytes):
                            val = val.rstrip(b'\x00').decode('utf-8', errors='ignore')
                        msg[col_name] = val

            
            return msg, header_size + data_size
            
        except Exception:
            return None, 1

if __name__ == "__main__":
    start_time = datetime.now()
   
    parser = MAVLinkBinParser('log_file_test_01.bin')
    num_parts = 1
    parser.parse()


    end_time = datetime.now()
    duration = end_time - start_time

    print(f"Time taken for all {len(parser.parse())} parts in parallel: {duration}")

