#
# Copyright 2007-2015 Charles du Jeu - Abstrium SAS <team (at) pyd.io>
#  This file is part of Pydio.
#
#  Pydio is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  Pydio is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with Pydio.  If not, see <http://www.gnu.org/licenses/>.
#
#  The latest code can be found at <http://pyd.io/>.
#
import os
import ctypes
import ctypes.util
import ctypes.macholib.dyld
import contextlib
from ctypes import c_char_p, c_short, POINTER, c_int, c_int32, c_long, c_uint16, c_uint32, c_uint8, c_ulong, c_void_p

# CONSTANTS
errNone = 0
kCFAllocatorDefault = None
kCFStringEncodingMacRoman = 0
kCFStringEncodingUTF8 = 134217984
kCFURLPOSIXPathStyle = 0
kCFURLHFSPathStyle = 1
kCFURLWindowsPathStyle = 2

#TYPES
OSStatus = c_int32
UniChar = c_uint16
Boolean = c_uint8
CFAllocatorRef = c_void_p
CFArrayRef = c_void_p
CFIndex = c_long
CFPropertyListRef = c_void_p
CFStringEncoding = c_uint32
CFStringRef = c_void_p
CFTypeRef = c_void_p
CFTypeID = c_ulong
CFURLPathStyle = c_int
CFURLRef = c_void_p
LSSharedFileListRef = c_void_p
LSSharedFileListItemRef = c_void_p
IconRef = c_void_p


class CFDictionaryRef(c_void_p):
    pass


class LibWrapper(object):
    def __init__(self):
        self._dynalib = None
        self._libname = None

        self._signatures = {}
        self._constants = {}
        self._functions = dict()

    def _create_func(self, name, func_def):
        try:
            new_func = getattr(self._libname, name)
        except Exception as e:
            new_func = func_def['when_not_found']
        else:
            setattr(new_func, 'restype', func_def['OUTPUT'])
            setattr(new_func, 'argtypes', func_def['PARAMS'])

        self._functions[name] = new_func
        return new_func

    def _create_const(self, const_name, const_type):
        try:
            self._functions[const_name] = const_type.in_dll(self._libname, const_name)
        except Exception:
            raise AttributeError("Cannot find %r in %r" % (const_name, self._dynalib))

        return self._functions[const_name]

    def __getattr__(self, name):
        if self._libname is None:
            self.init()
        if name in self._functions:
            return self._functions[name]
        try:
            return self._create_func(name, self._signatures[name])
        except KeyError:
            if name not in self._constants:
                raise AttributeError('Cannot find %r in %r' % (name, self._dynalib))
            return self._create_const(name, self._constants[name])


class FrameworkWrapper(LibWrapper):
    def init(self):
        self._libname = ctypes.cdll.LoadLibrary(ctypes.macholib.dyld.framework_find(self._dynalib))


class LibError(Exception):
    def __init__(self, err):
        super(LibError, self).__init__(err)
        self.errno = err
        self.errno_tup = None

    def __str__(self):
        try:
            return 'Error %d - %s - %s' % self.errno_tup
        except Exception:
            if not self.errno_tup:
                try:
                    self.errno_tup = (self.errno, CoreServices.GetMacOSStatusErrorString(self.errno),
                                      CoreServices.GetMacOSStatusCommentString(self.errno))
                    return 'Error %d - %s - %s' % self.errno_tup
                except Exception:
                    pass

            try:
                return 'Error %d' % self.errno
            except Exception:
                return 'Error OS'

    __repr__ = __str__


def OSStatusCheck(result, func, args):
    if result == errNone:
        return
    raise LibError(result)


class CoreFoundationWrapper(FrameworkWrapper):
    def __init__(self):
        super(CoreFoundationWrapper, self).__init__()
        self._dynalib = u'CoreFoundation'
        self._signatures = {}

        def wrap(name, args=None, ret=None):
            self._signatures[name] = {'OUTPUT': ret, 'PARAMS': args}

        wrap('CFRetain', [CFTypeRef], CFTypeRef)
        wrap('CFRelease', [CFTypeRef], None)
        wrap('CFGetTypeID', [CFPropertyListRef], c_ulong)
        wrap('CFStringCreateWithCString', [CFAllocatorRef, c_char_p, CFStringEncoding], CFStringRef)
        wrap('CFStringCreateWithCharacters', [CFAllocatorRef, POINTER(UniChar), CFIndex], CFStringRef)
        wrap('CFStringGetCString', [CFStringRef, c_char_p, c_int32, CFStringEncoding], c_short)
        wrap('CFStringGetCStringPtr', [CFStringRef, CFStringEncoding], c_char_p)
        wrap('CFStringGetLength', [CFStringRef], c_int32)
        wrap('CFStringGetMaximumSizeForEncoding', [c_int32, CFStringEncoding], c_int32)
        wrap('CFStringGetTypeID', [], c_ulong)
        wrap('CFURLCreateWithFileSystemPath', [CFAllocatorRef, CFStringRef, CFURLPathStyle, Boolean], CFURLRef)


class CoreServicesWrapper(FrameworkWrapper):
    def __init__(self):
        super(CoreServicesWrapper, self).__init__()
        self._dynalib = u'CoreServices'
        self._signatures = {}

        def wrap(name, args=None, ret=None):
            self._signatures[name] = {'OUTPUT': ret, 'PARAMS': args}

        wrap('GetMacOSStatusErrorString', [OSStatus], c_char_p)
        wrap('GetMacOSStatusCommentString', [OSStatus], c_char_p)
        wrap('LSSharedFileListCreate', [CFAllocatorRef, CFStringRef, CFTypeRef], LSSharedFileListRef)
        wrap('LSSharedFileListInsertItemURL', [LSSharedFileListRef, LSSharedFileListItemRef, CFStringRef, IconRef, CFURLRef, CFDictionaryRef, CFArrayRef], LSSharedFileListItemRef)

        self._constants['kLSSharedFileListItemLast'] = LSSharedFileListItemRef
        self._constants['kLSSharedFileListItemBeforeFirst'] = LSSharedFileListItemRef
        self._constants['kLSSharedFileListFavoriteItems'] = LSSharedFileListItemRef
        self._constants['kLSSharedFileListSessionLoginItems'] = LSSharedFileListItemRef


class ProxiedLib(object):
    def __init__(self, proxied_class):
        self.proxied_class = proxied_class
        self.initted = None

    def __getattr__(self, name):
        if self.initted is None:
            self.initted = self.proxied_class()
        return getattr(self.initted, name)


CoreFoundation = ProxiedLib(CoreFoundationWrapper)
CoreServices = ProxiedLib(CoreServicesWrapper)


class CFString(object):
    def __init__(self, ref, retain=False):
        if not isinstance(ref, CFStringRef):
            ref = CFStringRef(ref)
        if CoreFoundation.CFGetTypeID(ref) != CoreFoundation.CFStringGetTypeID():
            raise ValueError('Type is not a CFString')
        self.value = ref
        if not retain:
            CoreFoundation.CFRetain(ref)

    def __del__(self):
        if self.value:
            CoreFoundation.CFRelease(self.value)

    def get_ref(self):
        return self.value


def object_to_native_cfstring(ref):
    if isinstance(ref, unicode):
        ref = CoreFoundation.CFStringCreateWithCString(kCFAllocatorDefault, ref.encode('utf-8'), kCFStringEncodingUTF8)
    elif isinstance(ref, str):
        ref = CoreFoundation.CFStringCreateWithCString(kCFAllocatorDefault, ref, kCFStringEncodingUTF8)
    else:
        raise NotImplementedError("%r" % ref)
    ref = CFString(ref, retain=True)
    return ref


@contextlib.contextmanager
def autorelease(ref):
    try:
        yield ref
    finally:
        if ref:
            CoreFoundation.CFRelease(ref)


def macos_add_to_favorites(path, position_top=False):
    path_cf_str = object_to_native_cfstring(path)
    basename_cf_str = object_to_native_cfstring(os.path.basename(path))
    with autorelease(CoreFoundation.CFURLCreateWithFileSystemPath(kCFAllocatorDefault, path_cf_str.get_ref(),
                                                                  kCFURLPOSIXPathStyle, 1)) as path_url:
        with autorelease(
                CoreServices.LSSharedFileListCreate(kCFAllocatorDefault, CoreServices.kLSSharedFileListFavoriteItems,
                                                    None)) as the_list:
            pos = CoreServices.kLSSharedFileListItemBeforeFirst if position_top else CoreServices.kLSSharedFileListItemLast
            with autorelease(
                    CoreServices.LSSharedFileListInsertItemURL(the_list, pos, basename_cf_str.get_ref(), None, path_url,
                                                               None, None)):
                pass
