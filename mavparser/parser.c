/*
 * mavparser: Ultra-optimized CPython extension for ArduPilot DataFlash BIN logs.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define FORMAT_COUNT 256
#define MAX_COLUMNS 64
#define MAX_NAME 5
#define MAX_FORMAT 17

typedef struct {
    char name[MAX_NAME];
    char format[MAX_FORMAT];
    char columns[MAX_COLUMNS][32];
    PyObject *py_name;                            /* Cached PyUnicode message name */
    PyObject *py_columns[MAX_COLUMNS];            /* Pre-interned PyUnicode field keys */
    uint8_t is_z_data[MAX_COLUMNS];               /* Pre-computed flag for Z field 'Data' */
    unsigned char column_count;
    size_t payload_size;
    int defined;
} FormatDefinition;

typedef struct {
    PyObject_HEAD
    unsigned char *data;
    size_t data_size;
    size_t offset;
    FormatDefinition formats[FORMAT_COUNT];
    
    /* Pre-interned constant keys for speed */
    PyObject *py_mavpackettype_key;
    PyObject *py_fmt_name;
    PyObject *py_type_key;
    PyObject *py_length_key;
    PyObject *py_name_key;
    PyObject *py_format_key;
    PyObject *py_columns_key;
} MessageIterator;

/* --- Fast Inline Native Endian Reads --- */
static inline uint16_t read_u16(const unsigned char *v) { uint16_t r; memcpy(&r, v, 2); return r; }
static inline int16_t read_i16(const unsigned char *v) { int16_t r; memcpy(&r, v, 2); return r; }
static inline uint32_t read_u32(const unsigned char *v) { uint32_t r; memcpy(&r, v, 4); return r; }
static inline int32_t read_i32(const unsigned char *v) { int32_t r; memcpy(&r, v, 4); return r; }
static inline uint64_t read_u64(const unsigned char *v) { uint64_t r; memcpy(&r, v, 8); return r; }
static inline int64_t read_i64(const unsigned char *v) { int64_t r; memcpy(&r, v, 8); return r; }
static inline float read_f32(const unsigned char *v) { float r; memcpy(&r, v, 4); return r; }
static inline double read_f64(const unsigned char *v) { double r; memcpy(&r, v, 8); return r; }

static size_t field_size(char code) {
    switch (code) {
        case 'b': case 'B': case 'M': return 1;
        case 'h': case 'H': case 'c': case 'C': return 2;
        case 'i': case 'I': case 'f': case 'e': case 'E': case 'L': return 4;
        case 'd': case 'q': case 'Q': return 8;
        case 'n': return 4;
        case 'N': return 16;
        case 'Z': case 'a': return 64;
        default: return 0;
    }
}

static size_t format_payload_size(const char *format) {
    size_t size = 0;
    for (; *format; ++format) {
        size_t current_size = field_size(*format);
        if (current_size == 0) return 0;
        size += current_size;
    }
    return size;
}

static inline PyObject *decode_text(const unsigned char *value, size_t length) {
    size_t actual_length = 0;
    while (actual_length < length && value[actual_length] != '\0') ++actual_length;
    return PyUnicode_DecodeUTF8((const char *)value, (Py_ssize_t)actual_length, "replace");
}

static void free_format_definition(FormatDefinition *definition) {
    if (definition->defined) {
        Py_XDECREF(definition->py_name);
        definition->py_name = NULL;
        for (unsigned char i = 0; i < definition->column_count; ++i) {
            Py_XDECREF(definition->py_columns[i]);
            definition->py_columns[i] = NULL;
        }
        definition->defined = 0;
    }
}

static int parse_format_definition(MessageIterator *iterator, const unsigned char *packet) {
    const unsigned char *payload = packet + 3;
    unsigned char type = payload[0];
    FormatDefinition *definition = &iterator->formats[type];
    
    free_format_definition(definition);
    memset(definition, 0, sizeof(*definition));

    memcpy(definition->name, payload + 2, 4);
    definition->name[4] = '\0';
    memcpy(definition->format, payload + 6, 16);
    definition->format[16] = '\0';
    definition->payload_size = format_payload_size(definition->format);

    definition->py_name = PyUnicode_InternFromString(definition->name);

    char labels[65];
    memcpy(labels, payload + 22, 64);
    labels[64] = '\0';
    char *cursor = labels;
    while (*cursor && definition->column_count < MAX_COLUMNS) {
        char *next = strchr(cursor, ',');
        if (next) *next = '\0';
        while (*cursor == ' ') ++cursor;
        size_t label_length = strnlen(cursor, sizeof(definition->columns[0]) - 1);
        memcpy(definition->columns[definition->column_count], cursor, label_length);
        definition->columns[definition->column_count][label_length] = '\0';
        
        definition->is_z_data[definition->column_count] = (strcmp(definition->columns[definition->column_count], "Data") == 0);
        definition->py_columns[definition->column_count] = PyUnicode_InternFromString(definition->columns[definition->column_count]);

        ++definition->column_count;
        if (!next) break;
        cursor = next + 1;
    }
    definition->defined = definition->payload_size > 0;
    return definition->defined ? 0 : -1;
}

static inline PyObject *decode_field(char code, const unsigned char *value) {
    switch (code) {
        case 'b': return PyLong_FromLong((int8_t)value[0]);
        case 'B': case 'M': return PyLong_FromUnsignedLong(value[0]);
        case 'h': return PyLong_FromLong(read_i16(value));
        case 'H': return PyLong_FromUnsignedLong(read_u16(value));
        case 'i': return PyLong_FromLong(read_i32(value));
        case 'I': return PyLong_FromUnsignedLong(read_u32(value));
        case 'q': return PyLong_FromLongLong(read_i64(value));
        case 'Q': return PyLong_FromUnsignedLongLong(read_u64(value));
        case 'c': return PyFloat_FromDouble((double)read_i16(value) * 0.01);
        case 'C': return PyFloat_FromDouble((double)read_u16(value) * 0.01);
        case 'e': return PyFloat_FromDouble((double)read_i32(value) * 0.01);
        case 'E': return PyFloat_FromDouble((double)read_u32(value) * 0.01);
        case 'L': return PyFloat_FromDouble((double)read_i32(value) * 0.0000001);
        case 'f': return PyFloat_FromDouble((double)read_f32(value));
        case 'd': return PyFloat_FromDouble(read_f64(value));
        case 'n': return decode_text(value, 4);
        case 'N': return decode_text(value, 16);
        case 'Z': return PyBytes_FromStringAndSize((const char *)value, 64);
        case 'a': {
            PyObject *items = PyList_New(32);
            if (items == NULL) return NULL;
            for (Py_ssize_t index = 0; index < 32; ++index) {
                PyObject *item = PyLong_FromLong(read_i16(value + index * 2));
                if (item == NULL) { Py_DECREF(items); return NULL; }
                PyList_SET_ITEM(items, index, item);
            }
            return items;
        }
        default: PyErr_SetString(PyExc_ValueError, "unsupported DataFlash field format"); return NULL;
    }
}

static PyObject *decode_data_message(MessageIterator *iterator, unsigned char type, const unsigned char *packet) {
    FormatDefinition *definition = &iterator->formats[type];
    PyObject *message = PyDict_New();
    if (!message) return NULL;

    if (PyDict_SetItem(message, iterator->py_mavpackettype_key, definition->py_name) < 0) goto failed;

    const unsigned char *value = packet + 3;
    for (size_t index = 0; definition->format[index] != '\0'; ++index) {
        char fmt_code = definition->format[index];
        size_t size = field_size(fmt_code);
        
        PyObject *decoded = (fmt_code == 'Z' && !definition->is_z_data[index])
            ? decode_text(value, 64)
            : decode_field(fmt_code, value);

        if (decoded == NULL) goto failed;

        if (index < definition->column_count && definition->py_columns[index] != NULL) {
            if (PyDict_SetItem(message, definition->py_columns[index], decoded) < 0) {
                Py_DECREF(decoded);
                goto failed;
            }
        }
        Py_DECREF(decoded);
        value += size;
    }
    return message;

failed:
    Py_XDECREF(message);
    return NULL;
}

static PyObject *decode_fmt_message(MessageIterator *iterator, const unsigned char *packet) {
    const unsigned char *payload = packet + 3;
    if (parse_format_definition(iterator, packet) < 0) {
        PyErr_SetString(PyExc_ValueError, "invalid FMT definition");
        return NULL;
    }
    FormatDefinition *definition = &iterator->formats[payload[0]];
    PyObject *message = PyDict_New();
    if (!message) return NULL;

    PyObject *type = PyLong_FromUnsignedLong(payload[0]);
    PyObject *length = PyLong_FromUnsignedLong(payload[1]);
    PyObject *format = PyUnicode_FromString(definition->format);
    PyObject *columns = decode_text(payload + 22, 64);

    if (!type || !length || !format || !columns ||
        PyDict_SetItem(message, iterator->py_mavpackettype_key, iterator->py_fmt_name) < 0 ||
        PyDict_SetItem(message, iterator->py_type_key, type) < 0 ||
        PyDict_SetItem(message, iterator->py_length_key, length) < 0 ||
        PyDict_SetItem(message, iterator->py_name_key, definition->py_name) < 0 ||
        PyDict_SetItem(message, iterator->py_format_key, format) < 0 ||
        PyDict_SetItem(message, iterator->py_columns_key, columns) < 0) {
        Py_XDECREF(type); Py_XDECREF(length); Py_XDECREF(format); Py_XDECREF(columns); goto failed;
    }
    Py_DECREF(type); Py_DECREF(length); Py_DECREF(format); Py_DECREF(columns);
    return message;
failed:
    Py_XDECREF(message);
    return NULL;
}

static PyObject *MessageIterator_next(MessageIterator *iterator) {
    while (iterator->offset + 3 <= iterator->data_size) {
        size_t found = iterator->offset;
        while (found + 3 <= iterator->data_size &&
               !(iterator->data[found] == 0xA3 && iterator->data[found + 1] == 0x95)) ++found;
        if (found + 3 > iterator->data_size) break;

        unsigned char type = iterator->data[found + 2];
        if (type == 0x80) {
            if (found + 89 > iterator->data_size) break;
            iterator->offset = found + 89;
            PyObject *format_message = decode_fmt_message(iterator, iterator->data + found);
            if (format_message != NULL) return format_message;
            PyErr_Clear();
            iterator->offset = found + 1;
            continue;
        }

        FormatDefinition *definition = &iterator->formats[type];
        if (!definition->defined || found + 3 + definition->payload_size > iterator->data_size) {
            iterator->offset = found + 1;
            continue;
        }
        iterator->offset = found + 3 + definition->payload_size;
        return decode_data_message(iterator, type, iterator->data + found);
    }
    PyErr_SetNone(PyExc_StopIteration);
    return NULL;
}

static void MessageIterator_dealloc(MessageIterator *iterator) {
    Py_XDECREF(iterator->py_mavpackettype_key);
    Py_XDECREF(iterator->py_fmt_name);
    Py_XDECREF(iterator->py_type_key);
    Py_XDECREF(iterator->py_length_key);
    Py_XDECREF(iterator->py_name_key);
    Py_XDECREF(iterator->py_format_key);
    Py_XDECREF(iterator->py_columns_key);

    for (int i = 0; i < FORMAT_COUNT; ++i) {
        free_format_definition(&iterator->formats[i]);
    }
    if (iterator->data) PyMem_Free(iterator->data);
    Py_TYPE(iterator)->tp_free((PyObject *)iterator);
}

static PyTypeObject MessageIteratorType = {
    PyVarObject_HEAD_INIT(NULL, 0)
    .tp_name = "mavparser.MessageIterator",
    .tp_basicsize = sizeof(MessageIterator),
    .tp_dealloc = (destructor)MessageIterator_dealloc,
    .tp_flags = Py_TPFLAGS_DEFAULT,
    .tp_doc = "Lazy iterator yielding one decoded DataFlash message dictionary at a time.",
    .tp_iter = PyObject_SelfIter,
    .tp_iternext = (iternextfunc)MessageIterator_next,
};

static PyObject *new_iterator_from_path(const char *path) {
    FILE *file = fopen(path, "rb");
    if (!file) return PyErr_SetFromErrnoWithFilename(PyExc_OSError, path);
    if (fseek(file, 0, SEEK_END) != 0) { fclose(file); return PyErr_SetFromErrnoWithFilename(PyExc_OSError, path); }
    long length = ftell(file);
    if (length < 0) { fclose(file); return PyErr_SetFromErrnoWithFilename(PyExc_OSError, path); }
    rewind(file);

    MessageIterator *iterator = PyObject_New(MessageIterator, &MessageIteratorType);
    if (!iterator) { fclose(file); return NULL; }
    memset(iterator, 0, sizeof(*iterator));
    PyObject_INIT(iterator, &MessageIteratorType);

    /* Pre-intern common keys */
    iterator->py_mavpackettype_key = PyUnicode_InternFromString("mavpackettype");
    iterator->py_fmt_name          = PyUnicode_InternFromString("FMT");
    iterator->py_type_key         = PyUnicode_InternFromString("Type");
    iterator->py_length_key       = PyUnicode_InternFromString("Length");
    iterator->py_name_key         = PyUnicode_InternFromString("Name");
    iterator->py_format_key       = PyUnicode_InternFromString("Format");
    iterator->py_columns_key      = PyUnicode_InternFromString("Columns");

    iterator->data_size = (size_t)length;
    iterator->data = PyMem_Malloc(iterator->data_size ? iterator->data_size : 1);
    if (!iterator->data || fread(iterator->data, 1, iterator->data_size, file) != iterator->data_size) {
        fclose(file); Py_DECREF(iterator); PyErr_SetString(PyExc_OSError, "failed to read BIN log"); return NULL;
    }
    fclose(file);
    return (PyObject *)iterator;
}

static PyObject *mavparser_iter_messages(PyObject *module, PyObject *args) {
    const char *path;
    if (!PyArg_ParseTuple(args, "s:iter_messages", &path)) return NULL;
    return new_iterator_from_path(path);
}

static PyObject *mavparser_parse(PyObject *module, PyObject *args, PyObject *keywords) {
    static char *keyword_names[] = {"path", "mode", NULL};
    const char *path;
    const char *mode = "all";
    if (!PyArg_ParseTupleAndKeywords(args, keywords, "s|s:parse", keyword_names, &path, &mode)) return NULL;
    PyObject *iterator = new_iterator_from_path(path);
    if (!iterator) return NULL;
    if (strcmp(mode, "iterator") == 0) return iterator;
    if (strcmp(mode, "all") != 0) { Py_DECREF(iterator); PyErr_SetString(PyExc_ValueError, "mode must be 'all' or 'iterator'"); return NULL; }
    PyObject *messages = PySequence_List(iterator);
    Py_DECREF(iterator);
    return messages;
}

static PyMethodDef module_methods[] = {
    {"parse", (PyCFunction)mavparser_parse, METH_VARARGS | METH_KEYWORDS, "Parse a BIN log into a list, or return an iterator with mode='iterator'."},
    {"iter_messages", mavparser_iter_messages, METH_VARARGS, "Return a lazy iterator of decoded message dictionaries."},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef module_definition = {
    PyModuleDef_HEAD_INIT, "_mavparser", "C implementation of a DataFlash BIN parser.", -1, module_methods
};

PyMODINIT_FUNC PyInit__mavparser(void) {
    if (PyType_Ready(&MessageIteratorType) < 0) return NULL;
    PyObject *module = PyModule_Create(&module_definition);
    if (!module) return NULL;
    Py_INCREF(&MessageIteratorType);
    if (PyModule_AddObject(module, "MessageIterator", (PyObject *)&MessageIteratorType) < 0) {
        Py_DECREF(&MessageIteratorType); Py_DECREF(module); return NULL;
    }
    return module;
}