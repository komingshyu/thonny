#! python
#
# Enumerate serial ports on Windows including a human readable description
# and hardware information.
#
# This file is part of pySerial. https://github.com/pyserial/pyserial
# (C) 2001-2016 Chris Liechti <cliechti@gmx.net>
#
# SPDX-License-Identifier:    BSD-3-Clause

from __future__ import absolute_import

# pylint: disable=invalid-name,too-few-public-methods
import re
import ctypes
from ctypes.wintypes import BOOL, HWND, DWORD, WORD, LONG, ULONG, HKEY, PULONG, HANDLE, LPVOID
from serial.win32 import CreateFileW, GENERIC_WRITE, OPEN_EXISTING, CloseHandle, ULONG_PTR, LPOVERLAPPED
from serial.tools import list_ports_common


def ValidHandle(value, func, arguments):
    if value == 0:
        raise ctypes.WinError()
    return value


NULL = 0
HDEVINFO = ctypes.c_void_p
LPCTSTR = ctypes.c_wchar_p
PCTSTR = ctypes.c_wchar_p
PTSTR = ctypes.c_wchar_p
LPDWORD = PDWORD = ctypes.POINTER(DWORD)
LPBYTE = PBYTE = ctypes.c_void_p        # XXX avoids error about types
ACCESS_MASK = DWORD
REGSAM = ACCESS_MASK


class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', DWORD),
        ('Data2', WORD),
        ('Data3', WORD),
        ('Data4', ctypes.c_uint8 * 8),
    ]

    def __str__(self):
        return "{{{:08x}-{:04x}-{:04x}-{}-{}}}".format(
            self.Data1,
            self.Data2,
            self.Data3,
            ''.join(["{:02x}".format(d) for d in self.Data4[:2]]),
            ''.join(["{:02x}".format(d) for d in self.Data4[2:]]),
        )


class SP_DEVINFO_DATA(ctypes.Structure):
    _fields_ = [
        ('cbSize', DWORD),
        ('ClassGuid', GUID),
        ('DevInst', DWORD),
        ('Reserved', ULONG_PTR),
    ]

    def __str__(self):
        return "ClassGuid:{} DevInst:{}".format(self.ClassGuid, self.DevInst)


class SetupPacket(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('bmRequest', ctypes.c_uint8),
        ('bRequest', ctypes.c_uint8),
        ('wValue', ctypes.c_uint16),
        ('wIndex', ctypes.c_uint16),
        ('wLength', ctypes.c_uint16),
    ]


class USB_DESCRIPTOR_REQUEST(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('ConnectionIndex', ctypes.c_uint32),
        ('SetupPacket', SetupPacket),
    ]


class USB_COMMON_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('bLength', ctypes.c_uint8),
        ('bDescriptorType', ctypes.c_uint8),
    ]


class USB_CONFIGURATION_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('bLength', ctypes.c_uint8),
        ('bDescriptorType', ctypes.c_uint8),
        ('wTotalLength', ctypes.c_uint16),
        ('bNumInterfaces', ctypes.c_uint8),
        ('bConfigurationValue', ctypes.c_uint8),
        ('iConfiguration', ctypes.c_uint8),
        ('bmAttributes', ctypes.c_uint8),
        ('MaxPower', ctypes.c_uint8),
    ]


class USB_DEVICE_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('bLength', ctypes.c_uint8),
        ('bDescriptorType', ctypes.c_uint8),
        ('bcdUSB', ctypes.c_uint16),
        ('bDeviceClass', ctypes.c_uint8),
        ('bDeviceSubClass', ctypes.c_uint8),
        ('bDeviceProtocol', ctypes.c_uint8),
        ('bMaxPacketSize0', ctypes.c_uint8),
        ('idVendor', ctypes.c_uint16),
        ('idProduct', ctypes.c_uint16),
        ('bcdDevice', ctypes.c_uint16),
        ('iManufacturer', ctypes.c_uint8),
        ('iProduct', ctypes.c_uint8),
        ('iSerialNumber', ctypes.c_uint8),
        ('bNumConfigurations', ctypes.c_uint8),
    ]


class USB_INTERFACE_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('bLength', ctypes.c_uint8),
        ('bDescriptorType', ctypes.c_uint8),
        ('bInterfaceNumber', ctypes.c_uint8),
        ('bAlternateSetting', ctypes.c_uint8),
        ('bNumEndpoints', ctypes.c_uint8),
        ('bInterfaceClass', ctypes.c_uint8),
        ('bInterfaceSubClass', ctypes.c_uint8),
        ('bInterfaceProtocol', ctypes.c_uint8),
        ('iInterface', ctypes.c_uint8),
    ]


class USB_STRING_DESCRIPTOR(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('bLength', ctypes.c_uint8),
        ('bDescriptorType', ctypes.c_uint8),
        ('bString', ctypes.c_wchar * 255),
    ]


class USB_NODE_CONNECTION_INFORMATION_EX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ('ConnectionIndex', ctypes.c_ulong),
        ('DeviceDescriptor', USB_DEVICE_DESCRIPTOR),
        ('CurrentConfigurationValue', ctypes.c_uint8),
        ('Speed', ctypes.c_uint8),
        ('DeviceIsHub', ctypes.c_uint8),
        ('DeviceAddress', ctypes.c_uint16),
        ('NumberOfOpenPipes', ctypes.c_ulong),
        ('ConnectionStatus', ctypes.c_uint),
    ]


class DEVPROPKEY(ctypes.Structure):
    _fields_ = [
        ('fmtid', GUID),
        ('pid', ULONG)
    ]


DEVPKEY_Device_Address = DEVPROPKEY((0xa45c254e, 0xdf1c, 0x4efd, (0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0)), 30)
DEVPKEY_Device_BusReportedDeviceDesc = DEVPROPKEY((0x540b947e, 0x8b40, 0x45bc, (0xa8, 0xa2, 0x6a, 0x0b, 0x89, 0x4c, 0xbd, 0xa2)), 4)
DEVPKEY_Device_FriendlyName = DEVPROPKEY((0xa45c254e, 0xdf1c, 0x4efd, (0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0)), 14)
DEVPKEY_Device_LocationPaths = DEVPROPKEY((0xa45c254e, 0xdf1c, 0x4efd, (0x80, 0x20, 0x67, 0xd1, 0x46, 0xa8, 0x50, 0xe0)), 37)

GUID_DEVINTERFACE_USB_HUB = GUID(0xf18a0e88, 0xc30c, 0x11d0, (0x88, 0x15, 0x00, 0xa0, 0xc9, 0x06, 0xbe, 0xd8))

PDEVPROPTYPE = ctypes.POINTER(ULONG)
PDEVPROPKEY = ctypes.POINTER(DEVPROPKEY)

DEVPROP_TYPEMOD_LIST = 0x00002000   # list of variable-sized data elements
DEVPROP_TYPE_UINT32 = 0x00000007    # 32-bit unsigned int (ULONG)
DEVPROP_TYPE_STRING = 0x00000012    # null-terminated string
DEVPROP_TYPE_STRING_LIST = (DEVPROP_TYPE_STRING | DEVPROP_TYPEMOD_LIST)     # multi-sz string list

CR_SUCCESS = 0
CR_BUFFER_SMALL = 26

PSP_DEVINFO_DATA = ctypes.POINTER(SP_DEVINFO_DATA)

PSP_DEVICE_INTERFACE_DETAIL_DATA = ctypes.c_void_p

setupapi = ctypes.windll.LoadLibrary("setupapi")
SetupDiDestroyDeviceInfoList = setupapi.SetupDiDestroyDeviceInfoList
SetupDiDestroyDeviceInfoList.argtypes = [HDEVINFO]
SetupDiDestroyDeviceInfoList.restype = BOOL

SetupDiClassGuidsFromName = setupapi.SetupDiClassGuidsFromNameW
SetupDiClassGuidsFromName.argtypes = [PCTSTR, ctypes.POINTER(GUID), DWORD, PDWORD]
SetupDiClassGuidsFromName.restype = BOOL

SetupDiEnumDeviceInfo = setupapi.SetupDiEnumDeviceInfo
SetupDiEnumDeviceInfo.argtypes = [HDEVINFO, DWORD, PSP_DEVINFO_DATA]
SetupDiEnumDeviceInfo.restype = BOOL

SetupDiGetClassDevs = setupapi.SetupDiGetClassDevsW
SetupDiGetClassDevs.argtypes = [ctypes.POINTER(GUID), PCTSTR, HWND, DWORD]
SetupDiGetClassDevs.restype = HDEVINFO
SetupDiGetClassDevs.errcheck = ValidHandle

SetupDiGetDeviceProperty = setupapi.SetupDiGetDevicePropertyW
SetupDiGetDeviceProperty.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, PDEVPROPKEY, PDEVPROPTYPE, PBYTE, DWORD, PDWORD, DWORD]
SetupDiGetDeviceProperty.restype = BOOL

SetupDiGetDeviceRegistryProperty = setupapi.SetupDiGetDeviceRegistryPropertyW
SetupDiGetDeviceRegistryProperty.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, DWORD, PDWORD, PBYTE, DWORD, PDWORD]
SetupDiGetDeviceRegistryProperty.restype = BOOL

SetupDiGetDeviceInstanceId = setupapi.SetupDiGetDeviceInstanceIdW
SetupDiGetDeviceInstanceId.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, PTSTR, DWORD, PDWORD]
SetupDiGetDeviceInstanceId.restype = BOOL

SetupDiOpenDevRegKey = setupapi.SetupDiOpenDevRegKey
SetupDiOpenDevRegKey.argtypes = [HDEVINFO, PSP_DEVINFO_DATA, DWORD, DWORD, DWORD, REGSAM]
SetupDiOpenDevRegKey.restype = HKEY

advapi32 = ctypes.windll.LoadLibrary("Advapi32")
RegCloseKey = advapi32.RegCloseKey
RegCloseKey.argtypes = [HKEY]
RegCloseKey.restype = LONG

RegQueryValueEx = advapi32.RegQueryValueExW
RegQueryValueEx.argtypes = [HKEY, LPCTSTR, LPDWORD, LPDWORD, LPBYTE, LPDWORD]
RegQueryValueEx.restype = LONG

cfgmgr32 = ctypes.windll.LoadLibrary("Cfgmgr32")
CM_Get_Parent = cfgmgr32.CM_Get_Parent
CM_Get_Parent.argtypes = [PDWORD, DWORD, ULONG]
CM_Get_Parent.restype = LONG

CM_Get_Device_IDW = cfgmgr32.CM_Get_Device_IDW
CM_Get_Device_IDW.argtypes = [DWORD, PTSTR, ULONG, ULONG]
CM_Get_Device_IDW.restype = LONG

CM_MapCrToWin32Err = cfgmgr32.CM_MapCrToWin32Err
CM_MapCrToWin32Err.argtypes = [DWORD, DWORD]
CM_MapCrToWin32Err.restype = DWORD

CM_Get_DevNode_Status = cfgmgr32.CM_Get_DevNode_Status
CM_Get_DevNode_Status.argtypes = [PULONG, PULONG, DWORD, ULONG]
CM_Get_DevNode_Status.restype = DWORD

CM_Get_DevNode_PropertyW = cfgmgr32.CM_Get_DevNode_PropertyW
CM_Get_DevNode_PropertyW.argtypes = [DWORD, PDEVPROPKEY, PULONG, PBYTE, PULONG, ULONG]
CM_Get_DevNode_PropertyW.restype = DWORD

DeviceIoControl = ctypes.windll.kernel32.DeviceIoControl
DeviceIoControl.argtypes = [HANDLE, DWORD, LPVOID, DWORD, LPVOID, DWORD, LPDWORD, LPOVERLAPPED]
DeviceIoControl.restype = BOOL

DIGCF_PRESENT = 2
DIGCF_DEVICEINTERFACE = 16
INVALID_HANDLE_VALUE = 0
ERROR_INSUFFICIENT_BUFFER = 122
ERROR_NOT_FOUND = 1168
SPDRP_HARDWAREID = 1
SPDRP_FRIENDLYNAME = 12
SPDRP_ADDRESS = 28
SPDRP_LOCATION_PATHS = 35
SPDRP_MFG = 11
DICS_FLAG_GLOBAL = 1
DIREG_DEV = 0x00000001
KEY_READ = 0x20019
USB_REQUEST_GET_DESCRIPTOR = 6
USB_DEVICE_DESCRIPTOR_TYPE = 1
USB_CONFIGURATION_DESCRIPTOR_TYPE = 2
USB_STRING_DESCRIPTOR_TYPE = 3
USB_INTERFACE_DESCRIPTOR_TYPE = 4
IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION = 2229264
IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX = 2229320


MAX_USB_DEVICE_TREE_TRAVERSAL_DEPTH = 5


def get_parent_serial_number(child_devinst, child_vid, child_pid, depth=0, last_serial_number=None):
    """ Get the serial number of the parent of a device.

    Args:
        child_devinst: The device instance handle to get the parent serial number of.
        child_vid: The vendor ID of the child device.
        child_pid: The product ID of the child device.
        depth: The current iteration depth of the USB device tree.
    """

    # If the traversal depth is beyond the max, abandon attempting to find the serial number.
    if depth > MAX_USB_DEVICE_TREE_TRAVERSAL_DEPTH:
        return '' if not last_serial_number else last_serial_number

    # Get the parent device instance.
    devinst = DWORD()
    ret = CM_Get_Parent(ctypes.byref(devinst), child_devinst, 0)

    if ret:
        win_error = CM_MapCrToWin32Err(DWORD(ret), DWORD(0))

        # If there is no parent available, the child was the root device. We cannot traverse
        # further.
        if win_error == ERROR_NOT_FOUND:
            return '' if not last_serial_number else last_serial_number

        raise ctypes.WinError(win_error)

    # Get the ID of the parent device and parse it for vendor ID, product ID, and serial number.
    parentHardwareID = ctypes.create_unicode_buffer(250)

    ret = CM_Get_Device_IDW(
        devinst,
        parentHardwareID,
        ctypes.sizeof(parentHardwareID) - 1,
        0)

    if ret:
        raise ctypes.WinError(CM_MapCrToWin32Err(DWORD(ret), DWORD(0)))

    parentHardwareID_str = parentHardwareID.value
    m = re.search(r'VID_([0-9a-f]{4})(&PID_([0-9a-f]{4}))?(&MI_(\d{2}))?(\\(.*))?',
                  parentHardwareID_str,
                  re.I)

    # return early if we have no matches (likely malformed serial, traversed too far)
    if not m:
        return '' if not last_serial_number else last_serial_number

    vid = None
    pid = None
    serial_number = None
    if m.group(1):
        vid = int(m.group(1), 16)
    if m.group(3):
        pid = int(m.group(3), 16)
    if m.group(7):
        serial_number = m.group(7)

    # store what we found as a fallback for malformed serial values up the chain
    found_serial_number = serial_number

    # Check that the USB serial number only contains alphanumeric characters. It may be a windows
    # device ID (ephemeral ID).
    if serial_number and not re.match(r'^\w+$', serial_number):
        serial_number = None

    if not vid or not pid:
        # If pid and vid are not available at this device level, continue to the parent.
        return get_parent_serial_number(devinst, child_vid, child_pid, depth + 1, found_serial_number)

    if pid != child_pid or vid != child_vid:
        # If the VID or PID has changed, we are no longer looking at the same physical device. The
        # serial number is unknown.
        return '' if not last_serial_number else last_serial_number

    # In this case, the vid and pid of the parent device are identical to the child. However, if
    # there still isn't a serial number available, continue to the next parent.
    if not serial_number:
        return get_parent_serial_number(devinst, child_vid, child_pid, depth + 1, found_serial_number)

    # Finally, the VID and PID are identical to the child and a serial number is present, so return
    # it.
    return serial_number


def request_usb_string_description(h_hub_device, usb_hub_port, idx):
    if idx == 0:
        # There is no string description at this index.
        return None

    # Filling setup package.
    description_request_buffer = ctypes.create_string_buffer(ctypes.sizeof(USB_DESCRIPTOR_REQUEST) + ctypes.sizeof(USB_STRING_DESCRIPTOR))
    description_request = ctypes.cast(description_request_buffer, ctypes.POINTER(USB_DESCRIPTOR_REQUEST))
    description_request.contents.ConnectionIndex = usb_hub_port
    description_request.contents.SetupPacket.wValue = (USB_STRING_DESCRIPTOR_TYPE << 8) | idx
    description_request.contents.SetupPacket.wIndex = 0
    description_request.contents.SetupPacket.wLength = ctypes.sizeof(description_request_buffer) - ctypes.sizeof(USB_DESCRIPTOR_REQUEST)

    # Send string description request.
    if not DeviceIoControl(
            h_hub_device,
            IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION,
            description_request_buffer,
            ctypes.sizeof(description_request_buffer),
            description_request_buffer,
            ctypes.sizeof(description_request_buffer),
            None,
            None
    ):
        return None

    # Parse string description from wstring buffer.
    description = ctypes.cast(ctypes.byref(description_request_buffer, ctypes.sizeof(USB_DESCRIPTOR_REQUEST)),
                              ctypes.POINTER(USB_STRING_DESCRIPTOR))
    return ctypes.wstring_at(description.contents.bString, description.contents.bLength // 2 - 1)


def request_usb_configuration_description(h_hub_device, usb_hub_port, idx):
    # Filling setup package for requesting configuration description.
    configuration_description_request_buffer = ctypes.create_string_buffer(
        ctypes.sizeof(USB_DESCRIPTOR_REQUEST) + ctypes.sizeof(USB_CONFIGURATION_DESCRIPTOR)
    )
    configuration_description_request = ctypes.cast(
        configuration_description_request_buffer,
        ctypes.POINTER(USB_DESCRIPTOR_REQUEST)
    )
    configuration_description_request.contents.ConnectionIndex = usb_hub_port
    configuration_description_request.contents.SetupPacket.bmRequest = 0x80
    configuration_description_request.contents.SetupPacket.bRequest = USB_REQUEST_GET_DESCRIPTOR
    configuration_description_request.contents.SetupPacket.wValue = (USB_CONFIGURATION_DESCRIPTOR_TYPE << 8) | idx
    configuration_description_request.contents.SetupPacket.wLength = ctypes.sizeof(USB_CONFIGURATION_DESCRIPTOR)

    # Send usb configuration description request.
    if not DeviceIoControl(
            h_hub_device,
            IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION,
            configuration_description_request_buffer,
            ctypes.sizeof(configuration_description_request_buffer),
            configuration_description_request_buffer,
            ctypes.sizeof(configuration_description_request_buffer),
            None,
            None
    ):
        return None

    # Get configuration description.
    configuration_description = USB_CONFIGURATION_DESCRIPTOR()
    ptr = ctypes.cast(
        ctypes.byref(configuration_description_request_buffer, ctypes.sizeof(USB_DESCRIPTOR_REQUEST)),
        ctypes.POINTER(USB_CONFIGURATION_DESCRIPTOR)
    )
    ctypes.memmove(ctypes.addressof(configuration_description), ptr, ctypes.sizeof(USB_CONFIGURATION_DESCRIPTOR))
    return configuration_description


def request_usb_interface_descriptions(h_hub_device, usb_hub_port, configuration_description, bInterfaceNumber):
    # Now request the entire Configuration Descriptor using a dynamically
    # allocated buffer which is sized big enough to hold the entire descriptor
    configuration_description_request_buffer = ctypes.create_string_buffer(
        ctypes.sizeof(USB_DESCRIPTOR_REQUEST) + configuration_description.wTotalLength
    )
    configuration_description_request = ctypes.cast(
        configuration_description_request_buffer,
        ctypes.POINTER(USB_DESCRIPTOR_REQUEST)
    )
    configuration_description_request.contents.ConnectionIndex = usb_hub_port
    configuration_description_request.contents.SetupPacket.bmRequest = 0x80
    configuration_description_request.contents.SetupPacket.bRequest = USB_REQUEST_GET_DESCRIPTOR
    configuration_description_request.contents.SetupPacket.wValue = (USB_CONFIGURATION_DESCRIPTOR_TYPE << 8) | (configuration_description.bConfigurationValue - 1)
    configuration_description_request.contents.SetupPacket.wLength = configuration_description.wTotalLength

    # Send usb configuration description request.
    if not DeviceIoControl(
            h_hub_device,
            IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION,
            configuration_description_request_buffer,
            ctypes.sizeof(configuration_description_request_buffer),
            configuration_description_request_buffer,
            ctypes.sizeof(configuration_description_request_buffer),
            None,
            None
    ):
        return None

    # https://github.com/microsoft/Windows-driver-samples/blob/main/usb/usbview/enum.c#L2413
    common_description_offset = 0
    result_descriptions = []
    while True:
        if common_description_offset + ctypes.sizeof(USB_COMMON_DESCRIPTOR) < configuration_description.wTotalLength:
            common_description = ctypes.cast(
                ctypes.byref(configuration_description_request_buffer, ctypes.sizeof(USB_DESCRIPTOR_REQUEST) + common_description_offset),
                ctypes.POINTER(USB_COMMON_DESCRIPTOR)
            )
            if common_description_offset + common_description.contents.bLength <= configuration_description.wTotalLength:
                if common_description.contents.bDescriptorType == USB_INTERFACE_DESCRIPTOR_TYPE:
                    if common_description.contents.bLength == ctypes.sizeof(USB_INTERFACE_DESCRIPTOR):
                        interface_description = ctypes.cast(
                            ctypes.byref(configuration_description_request_buffer, ctypes.sizeof(USB_DESCRIPTOR_REQUEST) + common_description_offset),
                            ctypes.POINTER(USB_INTERFACE_DESCRIPTOR)
                        )
                        if interface_description.contents.bInterfaceNumber == bInterfaceNumber:
                            target_interface_description = USB_INTERFACE_DESCRIPTOR()
                            ctypes.memmove(ctypes.addressof(target_interface_description), interface_description, ctypes.sizeof(USB_INTERFACE_DESCRIPTOR))
                            result_descriptions.append(target_interface_description)
                    else:
                        break
                common_description_offset += common_description.contents.bLength
            else:
                break
        else:
            break
    return result_descriptions


def request_usb_device_description(h_hub_device, usb_hub_port):
    # Filling setup package for requesting device description.
    device_description_request_buffer = ctypes.create_string_buffer(
        ctypes.sizeof(USB_DESCRIPTOR_REQUEST) + ctypes.sizeof(USB_DEVICE_DESCRIPTOR)
    )
    device_description_request = ctypes.cast(device_description_request_buffer, ctypes.POINTER(USB_DESCRIPTOR_REQUEST))
    device_description_request.contents.ConnectionIndex = usb_hub_port
    device_description_request.contents.SetupPacket.bmRequest = 0x80
    device_description_request.contents.SetupPacket.bRequest = USB_REQUEST_GET_DESCRIPTOR
    device_description_request.contents.SetupPacket.wValue = USB_DEVICE_DESCRIPTOR_TYPE << 8
    device_description_request.contents.SetupPacket.wLength = ctypes.sizeof(USB_DEVICE_DESCRIPTOR)

    # Send usb device description request.
    if not DeviceIoControl(
            h_hub_device,
            IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION,
            device_description_request_buffer,
            ctypes.sizeof(device_description_request_buffer),
            device_description_request_buffer,
            ctypes.sizeof(device_description_request_buffer),
            None,
            None
    ):
        return None

    # Get device description.
    device_description = USB_DEVICE_DESCRIPTOR()
    ptr = ctypes.cast(
        ctypes.byref(device_description_request_buffer, ctypes.sizeof(USB_DESCRIPTOR_REQUEST)),
        ctypes.POINTER(USB_DEVICE_DESCRIPTOR)
    )
    ctypes.memmove(ctypes.addressof(device_description), ptr, ctypes.sizeof(USB_DEVICE_DESCRIPTOR))
    return device_description


def request_usb_connection_info(h_hub_device, usb_hub_port):
    connection_info = USB_NODE_CONNECTION_INFORMATION_EX()
    connection_info.ConnectionIndex = usb_hub_port
    if not DeviceIoControl(
            h_hub_device,
            IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX,
            ctypes.byref(connection_info),
            ctypes.sizeof(USB_NODE_CONNECTION_INFORMATION_EX),
            ctypes.byref(connection_info),
            ctypes.sizeof(USB_NODE_CONNECTION_INFORMATION_EX),
            None,
            None
    ):
        return None
    return connection_info


def get_device_instance_identifier(instance_number):
    instance_id = ctypes.create_unicode_buffer(250)
    if CM_Get_Device_IDW(
            instance_number,
            instance_id,
            ctypes.sizeof(instance_id) - 1,
            0
    ) != CR_SUCCESS:
        return None
    return ctypes.wstring_at(instance_id)


def get_parent_device_instance_number(child_instance_number):
    node_status = ULONG()
    problem_number = ULONG()
    if CM_Get_DevNode_Status(ctypes.byref(node_status), ctypes.byref(problem_number), child_instance_number, 0) != 0:
        return None
    parent_instance_number = DWORD()
    if CM_Get_Parent(ctypes.byref(parent_instance_number), child_instance_number, 0) != 0:
        return None
    return parent_instance_number.value


def get_location_string(instance_number, bConfigurationValue=None, bInterfaceNumber=None):
    if (bConfigurationValue is None) and (bInterfaceNumber is not None):
        bConfigurationValue = 'x'
    # Calculate a location string.
    loc_path_str = get_device_property(instance_number, DEVPKEY_Device_LocationPaths)
    if loc_path_str:
        m = re.finditer(r'USBROOT\((\w+)\)|#USB\((\w+)\)', loc_path_str[0])
        location = []
        for g in m:
            if g.group(1):
                location.append('{:d}'.format(int(g.group(1)) + 1))
            else:
                if len(location) > 1:
                    location.append('.')
                else:
                    location.append('-')
                location.append(g.group(2))
        if bInterfaceNumber is not None:
            location.append(':{}.{}'.format(
                bConfigurationValue,
                bInterfaceNumber))
        if location:
            return ''.join(location)
    return None


def get_device_property(instance_number, property_key):
    buffer_size = ULONG()
    property_type = ULONG()
    ret = CM_Get_DevNode_PropertyW(
        instance_number,
        ctypes.byref(property_key),
        ctypes.byref(property_type),
        None,
        ctypes.byref(buffer_size),
        0
    )
    if ret != CR_BUFFER_SMALL and ret != CR_SUCCESS:
        return None
    buffer = ctypes.create_string_buffer(buffer_size.value)
    if CM_Get_DevNode_PropertyW(
            instance_number,
            ctypes.byref(property_key),
            ctypes.byref(property_type),
            buffer,
            ctypes.byref(buffer_size),
            0
    ) != CR_SUCCESS:
        return None
    if property_type.value == DEVPROP_TYPE_STRING:
        return ctypes.wstring_at(buffer, buffer_size.value // 2 - 1)
    elif property_type.value == DEVPROP_TYPE_UINT32:
        return ctypes.cast(buffer, PULONG).contents.value
    elif property_type.value == DEVPROP_TYPE_STRING_LIST:
        return ctypes.wstring_at(buffer, buffer_size.value // 2).strip('\0').split('\0')
    else:
        raise NotImplementedError(f'DEVPROPTYPE {property_type.value} is not implemented!')


def get_all_hub_instance_number():
    g_hdi = SetupDiGetClassDevs(
        ctypes.byref(GUID_DEVINTERFACE_USB_HUB),
        None,
        NULL,
        DIGCF_PRESENT | DIGCF_DEVICEINTERFACE
    )

    devinfo = SP_DEVINFO_DATA()
    devinfo.cbSize = ctypes.sizeof(devinfo)
    index = 0
    hubs = []
    while SetupDiEnumDeviceInfo(g_hdi, index, ctypes.byref(devinfo)):
        hubs.append(devinfo.DevInst)
        index += 1
    SetupDiDestroyDeviceInfoList(g_hdi)
    return hubs


def get_interface_string_from_interface_descriptions(h_hub_device, usb_hub_port, configuration_description, bInterfaceNumber=None, bAlternateSetting=None):
    if bInterfaceNumber is None:
        # Single interface usb device.
        bInterfaceNumber = 0
    # Request all alternative interface descriptions.
    interface_descriptions = request_usb_interface_descriptions(h_hub_device, usb_hub_port, configuration_description, bInterfaceNumber)
    if bAlternateSetting is not None:
        for interface_description in interface_descriptions:
            # Find the target interface and request string description.
            if interface_description.bAlternateSetting == bAlternateSetting:
                return request_usb_string_description(h_hub_device, usb_hub_port, interface_description.iInterface)
    if interface_descriptions:
        # There is only one alternative interface in most cases.
        # If we don't know bAlternateSetting, then use the first interface.
        return request_usb_string_description(h_hub_device, usb_hub_port, interface_descriptions[0].iInterface)
    # Still can't find the target interface.
    return None


def parse_interface_number_from_hardware_id(hardware_id):
    # https://learn.microsoft.com/en-us/windows-hardware/drivers/install/standard-usb-identifiers
    # USB example: USB\VID_303A&PID_4001&MI_00\6&182C0AC9&0&0000
    m = re.fullmatch(r'USB\\VID_[0-9a-f]{4}&PID_[0-9a-f]{4}&MI_(\d{2})\\.*?', hardware_id, re.IGNORECASE)
    if m is not None:
        return int(m.group(1))
    # FTDIBUS example: FTDIBUS\VID_0403+PID_6001+B001ADZMA\0000
    m = re.fullmatch(r'FTDIBUS\\VID_[0-9a-f]{4}\+PID_[0-9a-f]{4}\+.*?\\([0-9a-f]*?)', hardware_id, re.IGNORECASE)
    if m is not None:
        return int(m.group(1))
    return None


def get_usb_info_from_iocontrol(devinfo, hardware_id, hub_instance_numbers, info):
    # Get parent hub instance number and usb instance number recursively.
    # +----------------------------------------------------------------------------------------------------+
    # |    (root_hub / hub)    --->    (usb_device)     --->    (child_devices)    --->     (serial_port)  |
    # |           ^                          ^                         ^                          ^        |
    # | parent_instance_number     child_instance_number     0 or several children         devinfo.DevInst |
    # +----------------------------------------------------------------------------------------------------+
    # The parent device of a serial port may be itself or an usb device. What we want to get is the description of the
    # usb device. To do so, we need to find out which usb hub the usb device is connected to and then send a
    # DeviceIoControl request through the hub. Fortunately, Any usb device is a child of a hub device. So we traverse
    # up from the serial port. When parent device is an usb hub, his child device is the usb device we want.
    child_instance_number = devinfo.DevInst
    for _ in range(max(MAX_USB_DEVICE_TREE_TRAVERSAL_DEPTH, 1)):
        parent_instance_number = get_parent_device_instance_number(child_instance_number)
        if parent_instance_number is None:
            # We cannot find the parent_instance_number.
            return False
        if parent_instance_number in hub_instance_numbers:
            # Got it!
            break
        child_instance_number = parent_instance_number
    else:
        # Traversal depth exceeds MAX_USB_DEVICE_TREE_TRAVERSAL_DEPTH.
        return False

    # Get the port number that the usb device is connected to.
    # https://learn.microsoft.com/en-us/windows-hardware/drivers/install/devpkey-device-address
    usb_hub_port = get_device_property(child_instance_number, DEVPKEY_Device_Address)
    if usb_hub_port is None:
        return False

    # Get hub instance identifier to generate the hub path.
    parent_instance_id = get_device_instance_identifier(parent_instance_number)
    if parent_instance_id is None:
        return False

    # Generate the hub path and open it.
    # https://stackoverflow.com/questions/28007468/how-do-i-obtain-usb-device-descriptor-given-a-device-path
    hub_location = "\\\\?\\" + parent_instance_id.replace("\\", "#") + f"#{GUID_DEVINTERFACE_USB_HUB}"
    h_hub_device = CreateFileW(
        hub_location,
        GENERIC_WRITE,
        2,
        None,
        OPEN_EXISTING,
        0,
        0
    )
    if h_hub_device == INVALID_HANDLE_VALUE:
        return False

    # Request usb device connection info.
    connection_info = request_usb_connection_info(h_hub_device, usb_hub_port)
    if connection_info is None:
        # Fallback to request usb device description.
        device_description = request_usb_device_description(h_hub_device, usb_hub_port)
        if device_description is None:
            # We can't get any information.
            CloseHandle(h_hub_device)
            return False
    else:
        device_description = connection_info.DeviceDescriptor

    # Get product identifier and vendor identifier.
    info.pid = device_description.idProduct
    info.vid = device_description.idVendor

    # Request string description at iProduct, iManufacturer and iSerialNumber.
    info.product = request_usb_string_description(h_hub_device, usb_hub_port, device_description.iProduct)
    info.manufacturer = request_usb_string_description(h_hub_device, usb_hub_port, device_description.iManufacturer)
    info.serial_number = request_usb_string_description(h_hub_device, usb_hub_port, device_description.iSerialNumber)

    # Get the bConfigurationValue.
    bConfigurationValue = None
    if connection_info is not None:
        # Get bConfigurationValue from device connection info.
        bConfigurationValue = connection_info.CurrentConfigurationValue
    elif device_description.bNumConfigurations == 1:
        # Mostly, there is only one Configuration, and bConfigurationValue is equal to 1.
        bConfigurationValue = 1

    # Get the bInterfaceNumber.
    bInterfaceNumber = None
    location_paths = get_device_property(devinfo.DevInst, DEVPKEY_Device_LocationPaths)
    if location_paths is not None:
        # Parse interface number from location paths.
        for p in location_paths:
            # Find the #USBMI(?) patten in the last part of location string.
            m = re.fullmatch(r'.*?#USBMI\((\d+)\)', p, re.IGNORECASE)
            if m is not None:
                bInterfaceNumber = int(m.group(1))
                break
    else:
        # Try to parse interface number from hardware identifier string.
        bInterfaceNumber = parse_interface_number_from_hardware_id(hardware_id)

    # Read interface description.
    if bConfigurationValue is not None:
        # When bConfigurationValue and bInterfaceNumber are known,
        # the interface description is available through DeviceIOControl.
        # https://github.com/microsoft/Windows-driver-samples/blob/main/usb/usbview/enum.c#L2413
        # This is a better approach, but there is a big problem whether bConfigurationValue
        # and bInterfaceNumber can be obtained.
        configuration_description = request_usb_configuration_description(h_hub_device, usb_hub_port, bConfigurationValue - 1)
        if configuration_description is None:
            # Somehow getting the usb configuration description fails.
            info.interface = get_device_property(devinfo.DevInst, DEVPKEY_Device_BusReportedDeviceDesc)
        else:
            if configuration_description.bNumInterfaces == 1:
                # Usb device with single interface.
                bInterfaceNumber = None     # Set to None to distinguish composite devices.
                info.interface = get_interface_string_from_interface_descriptions(h_hub_device, usb_hub_port, configuration_description, bInterfaceNumber)
            elif bInterfaceNumber is not None:
                # Get interface string of bInterfaceNumber.
                info.interface = get_interface_string_from_interface_descriptions(h_hub_device, usb_hub_port, configuration_description, bInterfaceNumber)
            else:
                # Doesn't know the bInterfaceNumber :(
                info.interface = get_device_property(devinfo.DevInst, DEVPKEY_Device_BusReportedDeviceDesc)
    else:
        # Read interface description from DEVPKEY_Device_BusReportedDeviceDesc
        # https://github.com/pyserial/pyserial/pull/571
        # May be the same or similar string as iInterface. Most of the time, it works.
        info.interface = get_device_property(devinfo.DevInst, DEVPKEY_Device_BusReportedDeviceDesc)

    # Because the device and name attributes of the serial port are duplicated in Windows. Set to friendly name.
    info.name = get_device_property(devinfo.DevInst, DEVPKEY_Device_FriendlyName)

    # Generate location string hwid and description compatible with linux and macOS.
    info.location = get_location_string(
        child_instance_number,
        bConfigurationValue=bConfigurationValue,
        bInterfaceNumber=bInterfaceNumber
    )
    info.apply_usb_info()

    # Everything is fine! Finished and close the hub handle.
    CloseHandle(h_hub_device)
    return True


def get_usb_info_from_device_property(g_hdi, devinfo, szHardwareID_str, info):
    # in case of USB, make a more readable string, similar to that form
    # that we also generate on other platforms
    if szHardwareID_str.startswith('USB'):
        bInterfaceNumber = None
        m = re.search(r'VID_([0-9a-f]{4})(&PID_([0-9a-f]{4}))?(&MI_(\d{2}))?(\\(.*))?', szHardwareID_str, re.I)
        if m:
            info.vid = int(m.group(1), 16)
            if m.group(3):
                info.pid = int(m.group(3), 16)
            if m.group(5):
                bInterfaceNumber = int(m.group(5))

            # Check that the USB serial number only contains alphanumeric characters. It
            # may be a windows device ID (ephemeral ID) for composite devices.
            if m.group(7) and re.match(r'^\w+$', m.group(7)):
                info.serial_number = m.group(7)
            else:
                info.serial_number = get_parent_serial_number(devinfo.DevInst, info.vid, info.pid)

        # calculate a location string
        info.location = get_location_string(devinfo.DevInst, bInterfaceNumber=bInterfaceNumber)
        info.hwid = info.usb_info()
    elif szHardwareID_str.startswith('FTDIBUS'):
        m = re.search(r'VID_([0-9a-f]{4})\+PID_([0-9a-f]{4})(\+(\w+))?', szHardwareID_str, re.I)
        if m:
            info.vid = int(m.group(1), 16)
            info.pid = int(m.group(2), 16)
            if m.group(4):
                info.serial_number = m.group(4)
        # USB location is hidden by FDTI driver :(
        info.hwid = info.usb_info()
    else:
        info.hwid = szHardwareID_str

    # manufacturer
    szManufacturer = ctypes.create_unicode_buffer(250)
    if SetupDiGetDeviceRegistryProperty(
            g_hdi,
            ctypes.byref(devinfo),
            SPDRP_MFG,
            None,
            ctypes.byref(szManufacturer),
            ctypes.sizeof(szManufacturer) - 1,
            None):
        info.manufacturer = szManufacturer.value

    # description
    szFriendlyName = ctypes.create_unicode_buffer(250)
    if SetupDiGetDeviceRegistryProperty(
            g_hdi,
            ctypes.byref(devinfo),
            SPDRP_FRIENDLYNAME,
            None,
            ctypes.byref(szFriendlyName),
            ctypes.sizeof(szFriendlyName) - 1,
            None):
        info.description = szFriendlyName.value

    # interface
    szInterface = ctypes.create_unicode_buffer(250)
    if SetupDiGetDeviceProperty(
            g_hdi,
            ctypes.byref(devinfo),
            ctypes.byref(DEVPKEY_Device_BusReportedDeviceDesc),
            ctypes.byref(ULONG(DEVPROP_TYPE_STRING)),
            ctypes.byref(szInterface),
            ctypes.sizeof(szInterface) - 1,
            None,
            0):
        info.interface = szInterface.value


def iterate_comports(enable_iocontrol=True):
    """Return a generator that yields descriptions for serial ports"""
    PortsGUIDs = (GUID * 8)()  # so far only seen one used, so hope 8 are enough...
    ports_guids_size = DWORD()
    if not SetupDiClassGuidsFromName(
            "Ports",
            PortsGUIDs,
            ctypes.sizeof(PortsGUIDs),
            ctypes.byref(ports_guids_size)):
        raise ctypes.WinError()

    ModemsGUIDs = (GUID * 8)()  # so far only seen one used, so hope 8 are enough...
    modems_guids_size = DWORD()
    if not SetupDiClassGuidsFromName(
            "Modem",
            ModemsGUIDs,
            ctypes.sizeof(ModemsGUIDs),
            ctypes.byref(modems_guids_size)):
        raise ctypes.WinError()

    GUIDs = PortsGUIDs[:ports_guids_size.value] + ModemsGUIDs[:modems_guids_size.value]

    # Get and store the instance numbers of all connected usb hubs.
    if enable_iocontrol:
        hub_instance_numbers = get_all_hub_instance_number()

    # repeat for all possible GUIDs
    for index in range(len(GUIDs)):
        g_hdi = SetupDiGetClassDevs(
            ctypes.byref(GUIDs[index]),
            None,
            NULL,
            DIGCF_PRESENT)  # was DIGCF_PRESENT|DIGCF_DEVICEINTERFACE which misses CDC ports

        devinfo = SP_DEVINFO_DATA()
        devinfo.cbSize = ctypes.sizeof(devinfo)
        index = 0
        while SetupDiEnumDeviceInfo(g_hdi, index, ctypes.byref(devinfo)):
            index += 1

            # get the real com port name
            hkey = SetupDiOpenDevRegKey(
                g_hdi,
                ctypes.byref(devinfo),
                DICS_FLAG_GLOBAL,
                0,
                DIREG_DEV,  # DIREG_DRV for SW info
                KEY_READ)
            port_name_buffer = ctypes.create_unicode_buffer(250)
            port_name_length = ULONG(ctypes.sizeof(port_name_buffer))
            RegQueryValueEx(
                hkey,
                "PortName",
                None,
                None,
                ctypes.byref(port_name_buffer),
                ctypes.byref(port_name_length))
            RegCloseKey(hkey)

            # unfortunately does this method also include parallel ports.
            # we could check for names starting with COM or just exclude LPT
            # and hope that other "unknown" names are serial ports...
            if port_name_buffer.value.startswith('LPT'):
                continue

            # hardware ID
            szHardwareID = ctypes.create_unicode_buffer(250)
            # try to get ID that includes serial number
            if not SetupDiGetDeviceInstanceId(
                    g_hdi,
                    ctypes.byref(devinfo),
                    #~ ctypes.byref(szHardwareID),
                    szHardwareID,
                    ctypes.sizeof(szHardwareID) - 1,
                    None):
                # fall back to more generic hardware ID if that would fail
                if not SetupDiGetDeviceRegistryProperty(
                        g_hdi,
                        ctypes.byref(devinfo),
                        SPDRP_HARDWAREID,
                        None,
                        ctypes.byref(szHardwareID),
                        ctypes.sizeof(szHardwareID) - 1,
                        None):
                    # Ignore ERROR_INSUFFICIENT_BUFFER
                    if ctypes.GetLastError() != ERROR_INSUFFICIENT_BUFFER:
                        raise ctypes.WinError()
            # stringify
            szHardwareID_str = szHardwareID.value

            info = list_ports_common.ListPortInfo(port_name_buffer.value, skip_link_detection=True)

            # Whether to generate usb info consistent with other platforms via DeviceIoControl.
            if enable_iocontrol:
                # Request pid, vid, product, manufacturer, serial_number using DeviceIoControl.
                # When it fails it will return False and fallback to the previous version.
                if not get_usb_info_from_iocontrol(
                    devinfo,
                    szHardwareID_str,
                    hub_instance_numbers,
                    info
                ):
                    # If we cannot request above using DeviceIoControl, doing this compatible with previous versions.
                    get_usb_info_from_device_property(g_hdi, devinfo, szHardwareID_str, info)
            else:
                # Just like the previous version.
                get_usb_info_from_device_property(g_hdi, devinfo, szHardwareID_str, info)

            yield info
        SetupDiDestroyDeviceInfoList(g_hdi)


def comports(include_links=False):
    """Return a list of info objects about serial ports"""
    return list(iterate_comports())


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# test
if __name__ == '__main__':
    for port, desc, hwid in sorted(comports()):
        print("{}: {} [{}]".format(port, desc, hwid))