"""Read macOS output devices without changing the system's audio settings."""
import ctypes
from ctypes.util import find_library
import sys


class CoreAudioError(RuntimeError):
    pass


class PropertyAddress(ctypes.Structure):
    _fields_ = [("selector", ctypes.c_uint32), ("scope", ctypes.c_uint32),
                ("element", ctypes.c_uint32)]


def fourcc(value):
    return int.from_bytes(value.encode("ascii"), "big")


GLOBAL = fourcc("glob")
OUTPUT = fourcc("outp")
UTF8 = 0x08000100


class CoreAudio:
    def __init__(self):
        if sys.platform != "darwin":
            raise CoreAudioError("CoreAudio output selection requires macOS")
        self.audio = ctypes.CDLL(find_library("CoreAudio"))
        self.cf = ctypes.CDLL(find_library("CoreFoundation"))
        self.audio.AudioObjectGetPropertyDataSize.argtypes = [ctypes.c_uint32, ctypes.POINTER(PropertyAddress),
                                                               ctypes.c_uint32, ctypes.c_void_p,
                                                               ctypes.POINTER(ctypes.c_uint32)]
        self.audio.AudioObjectGetPropertyDataSize.restype = ctypes.c_int32
        self.audio.AudioObjectGetPropertyData.argtypes = [ctypes.c_uint32, ctypes.POINTER(PropertyAddress),
                                                           ctypes.c_uint32, ctypes.c_void_p,
                                                           ctypes.POINTER(ctypes.c_uint32), ctypes.c_void_p]
        self.audio.AudioObjectGetPropertyData.restype = ctypes.c_int32
        self.cf.CFStringGetLength.argtypes = [ctypes.c_void_p]
        self.cf.CFStringGetLength.restype = ctypes.c_long
        self.cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                                ctypes.c_long, ctypes.c_uint32]
        self.cf.CFStringGetCString.restype = ctypes.c_bool
        self.cf.CFRelease.argtypes = [ctypes.c_void_p]

    def property(self, object_id, selector, scope=GLOBAL):
        address = PropertyAddress(fourcc(selector), scope, 0)
        size = ctypes.c_uint32()
        status = self.audio.AudioObjectGetPropertyDataSize(object_id, ctypes.byref(address),
                                                            0, None, ctypes.byref(size))
        if status != 0 or size.value == 0:
            raise CoreAudioError("Could not read a CoreAudio property")
        data = (ctypes.c_ubyte * size.value)()
        status = self.audio.AudioObjectGetPropertyData(object_id, ctypes.byref(address),
                                                        0, None, ctypes.byref(size), data)
        if status != 0:
            raise CoreAudioError("Could not read a CoreAudio property")
        return bytes(data[:size.value])

    def number(self, object_id, selector, scope=GLOBAL):
        data = self.property(object_id, selector, scope)
        if len(data) != 4:
            raise CoreAudioError("Unexpected CoreAudio property size")
        return int.from_bytes(data, sys.byteorder)

    def string(self, object_id, selector):
        data = self.property(object_id, selector)
        if len(data) != ctypes.sizeof(ctypes.c_void_p):
            raise CoreAudioError("Unexpected CoreAudio string size")
        reference = int.from_bytes(data, sys.byteorder)
        if not reference:
            raise CoreAudioError("CoreAudio string is empty")
        try:
            length = self.cf.CFStringGetLength(reference) * 4 + 1
            buffer = ctypes.create_string_buffer(length)
            if not self.cf.CFStringGetCString(reference, buffer, length, UTF8):
                raise CoreAudioError("Could not decode a CoreAudio string")
            return buffer.value.decode("utf-8")
        finally:
            self.cf.CFRelease(reference)

    def outputs(self):
        default_id = self.number(1, "dOut")
        raw = self.property(1, "dev#")
        if len(raw) % 4:
            raise CoreAudioError("Unexpected CoreAudio device list")
        devices = []
        for offset in range(0, len(raw), 4):
            object_id = int.from_bytes(raw[offset:offset + 4], sys.byteorder)
            try:
                if not self.number(object_id, "dflt", OUTPUT):
                    continue
                name = self.string(object_id, "lnam")
                uid = self.string(object_id, "uid ")
            except CoreAudioError:
                continue
            devices.append({"id": object_id, "uid": uid, "name": name,
                            "is_default": object_id == default_id})
        return devices


def outputs():
    return CoreAudio().outputs()
