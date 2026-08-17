import struct
from datetime import datetime
import mmap
from time import sleep
class MAVLinkBinParserOptimized:

    HEADER_PATTERN = b'\xA3\x95'
    
    FORMAT_TO_STRUCT = {
        'b': 'b', 'B': 'B', 'h': 'h', 'H': 'H',
        'i': 'i', 'I': 'I', 'f': 'f', 'd': 'd',
        'n': '4s', 'N': '16s', 'Z': '64s',
        'c': 'h', 'C': 'H', 'e': 'i', 'E': 'I',
        'L': 'i', 'M': 'B', 'q': 'q', 'Q': 'Q',
    }
    
    def __init__(self, filename):
        self.filename = filename
        self.formats = {}
        self.messages = []
        self.data = None

        self.fmt_struct = struct.Struct('<BB4s16s64s')
        
    def parse(self):
        """Parse using memory-mapped file for maximum speed"""
        # msg_count = 0
        
        with open(self.filename, 'rb') as f:
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmapped_file:
                file_size = len(mmapped_file)
                offset = 0
                
                while offset < file_size - 3:
                    pos = mmapped_file.find(self.HEADER_PATTERN, offset)
                    
                    if pos == -1:
                        break
                    
                    if pos + 2 >= file_size:
                        break
                    
                    msg_type = mmapped_file[pos + 2]
                    
                    msg, bytes_read = self._parse_message(mmapped_file, pos, msg_type)
                    # if msg:
                        # msg_count += 1
                    
                    offset = pos + (bytes_read if bytes_read > 0 else 1)

        return self.messages

    def _parse_message(self, data, offset, msg_type):
        try:
            if msg_type == 0x80:
                return self.parse_fmt_message(data, offset)
            
            if msg_type in self.formats:
                return self.parse_data_message(data, offset, msg_type)
            
            return None, 3
            
        except Exception:
            return None, 1
    
    def parse_fmt_message(self, data, offset):
        try:
            header_size = 3
            fmt_size = self.fmt_struct.size
            
            
            if offset + header_size + fmt_size > len(data):
                return None, 1
            
            msg_data = data[offset + header_size:offset + header_size + fmt_size]
            msg_type, msg_len, name, fmt, columns = self.fmt_struct.unpack(msg_data)

            name = name.rstrip(b'\x00').decode('utf-8')
            fmt_str = fmt.rstrip(b'\x00').decode('utf-8')
            columns_str = columns.rstrip(b'\x00').decode('utf-8')
            
            struct_fmt = '<'
            for c in fmt_str:
                if c in self.FORMAT_TO_STRUCT:
                    struct_fmt += self.FORMAT_TO_STRUCT[c]
            
            self.formats[msg_type] = {
                'name': name,
                'format': fmt_str,
                'columns': columns_str.split(','),
                'length': msg_len,
                'struct': struct.Struct(struct_fmt)
            }
            return {'type': 'FMT'}, header_size + fmt_size
            
        except Exception:
            return None, 1
    
    def parse_data_message(self, data, offset, msg_type):
        try:
            fmt_def = self.formats[msg_type]
            compiled_struct = fmt_def['struct']
            
            header_size = 3
            data_size = compiled_struct.size
            
            if offset + header_size + data_size > len(data):
                return None, 1
            
            msg_data = data[offset + header_size:offset + header_size + data_size]
            values = compiled_struct.unpack(msg_data)
            
            msg = {'type': fmt_def['name'], 'msg_type': msg_type}
            col_names = fmt_def['columns']
            for i, val in enumerate(values):
                if i < len(col_names):
                    col_name = col_names[i].strip()
                    if col_name:
                        if isinstance(val, bytes):
                            val = val.rstrip(b'\x00').decode('utf-8', errors='ignore')
                        msg[col_name] = val

            msg = True
            
            
            return msg, header_size + data_size
            
        except Exception:
            return None, 1

if __name__ == "__main__":

    start = datetime.now()
    parser1 = MAVLinkBinParserOptimized('log_file_test_01.bin')
    parser1.parse()
    duration1 = datetime.now() - start
    print(f"   Time: {duration1}")