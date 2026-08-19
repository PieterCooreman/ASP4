"""Classic ASP Server object emulation (cross-platform)."""

from __future__ import annotations

import html
import glob
import os
import re
import shutil
import uuid
import urllib.parse
from typing import Any, cast
import mimetypes
import datetime

from .vb_runtime import vbs_cstr, VBScriptRuntimeError, VBScriptCOMError
from .vb_errors import VBScriptError, RUNTIME_ERRORS, raise_runtime
from .vm.values import VBNull


def make_asp_error(request_path: str, exc: Exception) -> ASPError:
    from .parser import ParseError
    from .lexer import LexerError

    start_line = getattr(exc, 'asp_start_line', 0)
    start_col = getattr(exc, 'asp_start_col', 0)
    src_block = getattr(exc, 'asp_source_block', '')
    src_line = ''
    if src_block:
        lines = src_block.splitlines()
        if len(lines) <= 1:
            src_line = src_block.strip()
        else:
            # asp_source_block should already be a single source line
            src_line = lines[0].strip() if lines else src_block.strip()

    number = 0x80004005
    category = "ASPPY runtime error" # Default to runtime error
    description = str(exc)

    if isinstance(exc, VBScriptError):
        if exc.error_def and exc.error_def.hex_code:
            try:
                number = int(exc.error_def.hex_code, 16)
            except ValueError:
                pass
        description = exc.description
        # Distinguish compilation vs runtime if possible
        # VBScriptCompilationError is a subclass of VBScriptError
        if "Compilation" in exc.__class__.__name__:
             category = "ASPPY compilation error"
        else:
             category = "ASPPY runtime error"

    elif isinstance(exc, (ParseError, LexerError)):
        # IIS: 800a03ea = VBScript compilation error (syntax)
        number = 0x800A03EA
        category = "ASPPY compilation error"

    elif isinstance(exc, IndexError):
        # Map Python IndexError to VBScript "Subscript out of range" (error 9)
        number = 0x800A0009
        description = str(exc)
        category = "ASPPY runtime error"

    else:
        category = "ASPPY runtime error"
        # Map well-known VBScript runtime error descriptions to proper error codes.
        # This handles vb_runtime.VBScriptRuntimeError which is a plain Exception
        # and not a subclass of vb_errors.VBScriptError.
        _desc_lower = description.lower()
        for _err_def in RUNTIME_ERRORS.values():
            if _err_def.description.lower() in _desc_lower:
                try:
                    number = int(_err_def.hex_code, 16)
                except ValueError:
                    pass
                break

    err_file = getattr(exc, 'asp_file', '') or request_path

    return ASPError(
        number=number,
        description=description,
        category=category,
        asp_code="",
        asp_description="",
        file=err_file,
        line=start_line,
        column=start_col,
        source=src_line,
    )


class ServerTransferException(Exception):
    def __init__(self, target: str):
        super().__init__(target)
        self.target = target


_WSH_ENV_REG_PATHS = {
    'SYSTEM': (r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment", 'HKLM'),
    'USER': (r"Environment", 'HKCU'),
    'VOLATILE': (r"Volatile Environment", 'HKCU'),
}


def _read_persistent_environment(scope: str) -> dict:
    """Read a persistent (non-PROCESS) WSH environment scope.

    On Windows these live in the registry and form a smaller set than the
    process environment. On other platforms -- and if the registry is
    unreadable -- fall back to the process environment so the collection is
    still usable rather than empty.
    """
    entry = _WSH_ENV_REG_PATHS.get(scope)
    if entry is None:
        return dict(os.environ)
    sub, hive_name = entry
    try:
        import winreg  # Windows-only; absent elsewhere
    except ImportError:
        return dict(os.environ)
    hive = winreg.HKEY_LOCAL_MACHINE if hive_name == 'HKLM' else winreg.HKEY_CURRENT_USER
    out = {}
    try:
        with winreg.OpenKey(hive, sub) as key:
            i = 0
            while True:
                try:
                    name, value, _kind = winreg.EnumValue(key, i)
                except OSError:
                    break
                out[str(name)] = str(value)
                i += 1
    except OSError:
        return dict(os.environ)
    return out


class WshEnvironment:
    """WScript.Shell Environment collection (IWshEnvironment).

    Verified against IIS:
      - Item(name) / env(name) are case-insensitive; a missing name yields "".
      - Count is the number of variables.
      - For Each yields "KEY=VALUE" strings (not just the keys).
    """

    def __init__(self, scope: str = "SYSTEM"):
        self._scope = str(scope or "SYSTEM").upper()
        # Only the PROCESS scope reflects the live process environment. The
        # persistent scopes (SYSTEM/USER/VOLATILE) come from the registry on
        # Windows and are a SMALLER set -- e.g. COMPUTERNAME is a process-only
        # variable and is absent there (verified against IIS).
        if self._scope == 'PROCESS':
            self._d = dict(os.environ)
        else:
            self._d = _read_persistent_environment(self._scope)
        self._kmap = {k.upper(): k for k in self._d}

    @property
    def Count(self):
        from .vb_runtime import VBLong
        return VBLong(len(self._d))

    @property
    def Length(self):
        # IWshEnvironment exposes both; Length is the IWshCollection spelling.
        from .vb_runtime import VBLong
        return VBLong(len(self._d))

    def Item(self, name=None):
        if name is None:
            return ""
        k = vbs_cstr(name).upper()
        real = self._kmap.get(k)
        return self._d.get(real, "") if real is not None else ""

    def __vbs_index_get__(self, name):
        return self.Item(name)

    def Remove(self, name):
        k = vbs_cstr(name).upper()
        real = self._kmap.pop(k, None)
        if real is not None:
            self._d.pop(real, None)

    def __iter__(self):
        # WSH yields "KEY=VALUE" pairs when iterating an Environment.
        return iter([f"{k}={v}" for k, v in self._d.items()])

    def __vbs_typename__(self):
        return "IWshEnvironment"


def _lnk_string_data(text: str) -> bytes:
    """A StringData block: UTF-16LE character count, then the characters."""
    s = str(text or "")
    return len(s).to_bytes(2, 'little') + s.encode('utf-16-le')


def _lnk_hotkey(text: str) -> int:
    """"CTRL+ALT+T" -> the HotKeyFlags word used in the ShellLinkHeader."""
    mods = {'SHIFT': 0x01, 'CTRL': 0x02, 'CONTROL': 0x02, 'ALT': 0x04}
    lo = hi = 0
    for part in str(text or "").upper().replace(' ', '').split('+'):
        if not part:
            continue
        if part in mods:
            hi |= mods[part]
        elif len(part) == 1:
            lo = ord(part)
        elif part.startswith('F') and part[1:].isdigit():
            n = int(part[1:])
            if 1 <= n <= 24:
                lo = 0x6F + n            # VK_F1 = 0x70
    return (hi << 8) | lo


def _shell_target_idlist(target: str) -> bytes:
    """Serialised LinkTargetIDList for `target`, or b"" if unavailable.

    Windows resolves a shortcut's target from the IDList, NOT from the
    LinkInfo path - a .lnk carrying only LinkInfo opens as a link but reports
    an empty target and will not launch. Rather than hand-assemble ITEMIDLIST
    structures (which Windows rejects if anything is slightly off), the list is
    built by the shell itself through ctypes, so the bytes are exactly what
    Explorer would have written. Requires Windows and an existing target;
    otherwise the link falls back to LinkInfo only.
    """
    if os.name != 'nt':
        return b""
    try:
        import ctypes
        from ctypes import wintypes

        shell32 = ctypes.windll.shell32
        shell32.SHParseDisplayName.argtypes = [
            wintypes.LPCWSTR, ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_ulong,
            ctypes.POINTER(ctypes.c_ulong)]
        shell32.ILGetSize.argtypes = [ctypes.c_void_p]
        shell32.ILGetSize.restype = ctypes.c_uint
        shell32.ILFree.argtypes = [ctypes.c_void_p]

        pidl = ctypes.c_void_p()
        attrs = ctypes.c_ulong(0)
        hr = shell32.SHParseDisplayName(
            str(target), None, ctypes.byref(pidl), 0, ctypes.byref(attrs))
        if hr != 0 or not pidl:
            return b""
        try:
            size = shell32.ILGetSize(pidl)
            if not size:
                return b""
            buf = (ctypes.c_char * size).from_address(pidl.value)
            return bytes(buf)
        finally:
            shell32.ILFree(pidl)
    except Exception:
        return b""


def _write_shell_link(path: str, target: str, arguments: str, working_dir: str,
                      description: str, icon_location: str, icon_index: int,
                      window_style: int, hotkey: str) -> None:
    """Write a Windows Shell Link (.lnk) file.

    Built to the [MS-SHLLINK] layout rather than through the Shell COM object,
    so it works the same way on a non-Windows host. The link carries a LinkInfo
    block with the target's local path plus the optional StringData sections;
    the LinkTargetIDList is omitted, which Windows accepts.
    """
    HAS_LINK_INFO = 0x00000002
    HAS_NAME = 0x00000004
    HAS_RELATIVE_PATH = 0x00000008
    HAS_WORKING_DIR = 0x00000010
    HAS_ARGUMENTS = 0x00000020
    HAS_ICON_LOCATION = 0x00000040
    IS_UNICODE = 0x00000080

    HAS_LINK_TARGET_IDLIST = 0x00000001

    target = str(target or "")
    idlist = _shell_target_idlist(target)
    flags = HAS_LINK_INFO | IS_UNICODE
    if idlist:
        flags |= HAS_LINK_TARGET_IDLIST
    if description:
        flags |= HAS_NAME
    if working_dir:
        flags |= HAS_WORKING_DIR
    if arguments:
        flags |= HAS_ARGUMENTS
    if icon_location:
        flags |= HAS_ICON_LOCATION

    header = bytearray()
    header += (0x4C).to_bytes(4, 'little')                       # HeaderSize
    header += bytes.fromhex('01140200000000C000000000000046')[:0]  # placeholder
    # LinkCLSID {00021401-0000-0000-C000-000000000046}
    header += (0x00021401).to_bytes(4, 'little')
    header += (0).to_bytes(2, 'little') + (0).to_bytes(2, 'little')
    header += bytes((0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46))
    header += flags.to_bytes(4, 'little')                        # LinkFlags
    header += (0x00000080).to_bytes(4, 'little')                 # FILE_ATTRIBUTE_NORMAL
    header += b'\x00' * 24                                       # 3 x FILETIME
    header += (0).to_bytes(4, 'little')                          # FileSize
    header += int(icon_index).to_bytes(4, 'little', signed=True)  # IconIndex
    header += int(window_style or 1).to_bytes(4, 'little')       # ShowCommand
    header += _lnk_hotkey(hotkey).to_bytes(2, 'little')          # HotKey
    header += b'\x00' * 2                                        # Reserved1
    header += b'\x00' * 4                                        # Reserved2
    header += b'\x00' * 4                                        # Reserved3

    # LinkInfo with a VolumeID and a LocalBasePath (ANSI). Setting the
    # VolumeIDAndLocalBasePath flag REQUIRES a VolumeID structure - without one
    # Windows ignores the path and TargetPath reads back empty.
    base = target.encode('mbcs', errors='replace') if os.name == 'nt' \
        else target.encode('utf-8', errors='replace')

    vol = bytearray()
    vol += (17).to_bytes(4, 'little')                 # VolumeIDSize
    vol += (3).to_bytes(4, 'little')                  # DriveType = DRIVE_FIXED
    vol += (0).to_bytes(4, 'little')                  # DriveSerialNumber
    vol += (16).to_bytes(4, 'little')                 # VolumeLabelOffset
    vol += b'\x00'                                    # empty volume label

    hdr_len = 28
    vol_off = hdr_len
    local_base_off = vol_off + len(vol)
    common_path_off = local_base_off + len(base) + 1
    total = common_path_off + 1

    li = bytearray()
    li += total.to_bytes(4, 'little')                 # LinkInfoSize
    li += hdr_len.to_bytes(4, 'little')               # LinkInfoHeaderSize
    li += (0x00000001).to_bytes(4, 'little')          # VolumeIDAndLocalBasePath
    li += vol_off.to_bytes(4, 'little')               # VolumeIDOffset
    li += local_base_off.to_bytes(4, 'little')        # LocalBasePathOffset
    li += (0).to_bytes(4, 'little')                   # CommonNetworkRelativeLink
    li += common_path_off.to_bytes(4, 'little')       # CommonPathSuffixOffset
    li += vol
    li += base + b'\x00'
    li += b'\x00'                                     # empty CommonPathSuffix

    out = bytearray(header)
    if idlist:
        out += len(idlist).to_bytes(2, 'little') + idlist
    out += li
    if description:
        out += _lnk_string_data(description)
    if working_dir:
        # RELATIVE_PATH is not emitted; WORKING_DIR is what scripts read back.
        out += _lnk_string_data(working_dir)
    if arguments:
        out += _lnk_string_data(arguments)
    if icon_location:
        out += _lnk_string_data(icon_location)
    out += (0).to_bytes(4, 'little')                  # terminal block

    with open(path, 'wb') as f:
        f.write(bytes(out))


class WshShortcut:
    """WScript.Shell.CreateShortcut() result for a .lnk path (IWshShortcut)."""

    def __init__(self, full_name: str):
        self.FullName = full_name
        self.TargetPath = ""
        self.Arguments = ""
        self.Description = ""
        self.WorkingDirectory = ""
        self.IconLocation = ",0"
        self.Hotkey = ""
        self.WindowStyle = 1
        self.RelativePath = ""
        # If the file already exists, ADO-style scripts expect CreateShortcut
        # to load it. Only the fields written below are recovered.
        self._load()

    def _load(self):
        # Reading a .lnk back is not implemented; the properties keep their
        # defaults, which is what a freshly created shortcut reports anyway.
        return

    def _icon_parts(self):
        loc = vbs_cstr(self.IconLocation or "")
        if ',' in loc:
            head, _, tail = loc.rpartition(',')
            try:
                return head.strip(), int(tail.strip() or 0)
            except ValueError:
                return loc.strip(), 0
        return loc.strip(), 0

    def Save(self):
        path = vbs_cstr(self.FullName)
        if not path:
            raise_runtime('INVALID_PROC_CALL', "WshShortcut.Save: no FullName")
        icon_path, icon_idx = self._icon_parts()
        try:
            _write_shell_link(
                path,
                vbs_cstr(self.TargetPath),
                vbs_cstr(self.Arguments),
                vbs_cstr(self.WorkingDirectory),
                vbs_cstr(self.Description),
                icon_path,
                icon_idx,
                int(self.WindowStyle or 1),
                vbs_cstr(self.Hotkey),
            )
        except Exception as e:
            raise_runtime('ADO_UNSPECIFIED', f"WshShortcut.Save: {e}")

    def __vbs_typename__(self):
        return "IWshShortcut"


class WshUrlShortcut:
    """WScript.Shell.CreateShortcut() result for a .url path (IWshURLShortcut).

    A .url is a plain INI file, so this is exact rather than approximate.
    """

    def __init__(self, full_name: str):
        self.FullName = full_name
        self.TargetPath = ""
        self._load()

    def _load(self):
        try:
            if os.path.isfile(self.FullName):
                with open(self.FullName, 'r', encoding='utf-8', errors='replace') as f:
                    for line in f:
                        if line.strip().lower().startswith('url='):
                            self.TargetPath = line.split('=', 1)[1].strip()
                            break
        except Exception:
            pass

    def Save(self):
        path = vbs_cstr(self.FullName)
        if not path:
            raise_runtime('INVALID_PROC_CALL', "WshUrlShortcut.Save: no FullName")
        try:
            with open(path, 'w', encoding='utf-8', newline='\r\n') as f:
                f.write("[InternetShortcut]\n")
                f.write("URL=%s\n" % vbs_cstr(self.TargetPath))
        except Exception as e:
            raise_runtime('ADO_UNSPECIFIED', f"WshUrlShortcut.Save: {e}")

    def __vbs_typename__(self):
        return "IWshURLShortcut"


class WshSpecialFolders:
    """WScript.Shell.SpecialFolders (IWshCollection).

    Indexing with an unknown name returns "" rather than raising, which is what
    WSH does. Under a service account many per-user folders are legitimately
    empty, and scripts rely on that being a value rather than an error.
    """

    _NAMES = ("AllUsersDesktop", "AllUsersStartMenu", "AllUsersPrograms",
              "AllUsersStartup", "Desktop", "Favorites", "Fonts", "MyDocuments",
              "NetHood", "PrintHood", "Programs", "Recent", "SendTo",
              "StartMenu", "Startup", "Templates", "System", "Temp",
              "AppData", "ProgramFiles", "Windows")

    def _resolve(self, name: str) -> str:
        n = str(name or "").strip().lower()
        env = {k.upper(): v for k, v in os.environ.items()}
        win = env.get('SYSTEMROOT') or env.get('WINDIR') or ''
        prof = env.get('USERPROFILE') or ''
        appdata = env.get('APPDATA') or ''
        table = {
            'windows': win,
            'system': os.path.join(win, 'System32') if win else '',
            'fonts': os.path.join(win, 'Fonts') if win else '',
            'temp': env.get('TEMP') or env.get('TMP') or '',
            'appdata': appdata,
            'programfiles': env.get('PROGRAMFILES') or '',
            'desktop': os.path.join(prof, 'Desktop') if prof else '',
            'mydocuments': os.path.join(prof, 'Documents') if prof else '',
            'favorites': os.path.join(prof, 'Favorites') if prof else '',
            'recent': os.path.join(appdata, r'Microsoft\Windows\Recent') if appdata else '',
            'sendto': os.path.join(appdata, r'Microsoft\Windows\SendTo') if appdata else '',
            'startmenu': os.path.join(appdata, r'Microsoft\Windows\Start Menu') if appdata else '',
            'programs': os.path.join(appdata, r'Microsoft\Windows\Start Menu\Programs') if appdata else '',
            'startup': os.path.join(appdata, r'Microsoft\Windows\Start Menu\Programs\Startup') if appdata else '',
            'templates': os.path.join(appdata, r'Microsoft\Windows\Templates') if appdata else '',
        }
        val = table.get(n, '')
        # Only report a folder that is really there, like WSH does.
        return val if val and os.path.isdir(val) else ('' if n in table else '')

    @property
    def Count(self):
        return len(self._NAMES)

    @property
    def Length(self):
        return len(self._NAMES)

    def Item(self, index=None):
        if index is None:
            return ""
        if isinstance(index, (int, float)) and not isinstance(index, bool):
            i = int(index)
            return self._resolve(self._NAMES[i]) if 0 <= i < len(self._NAMES) else ""
        return self._resolve(vbs_cstr(index))

    def __vbs_index_get__(self, index):
        return self.Item(index)

    def __iter__(self):
        return iter([self._resolve(n) for n in self._NAMES])

    def __vbs_typename__(self):
        return "IWshCollection"


class WScriptShell:
    """Partial WScript.Shell (IWshShell3).

    Implemented: the read-only members that legacy Classic ASP uses for config
    interpolation -- ExpandEnvironmentStrings, Environment and CurrentDirectory.

    NOT implemented: Run and Exec. Those execute arbitrary shell commands from
    a web request, which would contradict the sandboxing ASPPY applies
    elsewhere (FileSystemObject is confined to the docroot). They raise a
    catchable ActiveX error (429) instead of failing silently.
    """

    _ENV_SCOPES = ("SYSTEM", "USER", "VOLATILE", "PROCESS")

    def _unsupported(self, name: str):
        # Previously this raised a free-text VBScriptRuntimeError, which left
        # Err.Number = 0 -- so On Error Resume Next code could not detect the
        # failure at all. Use a real, catchable ActiveX error number instead.
        raise_runtime('COMPONENT_CANT_CREATE',
                      f"WScript.Shell.{name} is not supported in ASPPY")

    def ExpandEnvironmentStrings(self, template=""):
        """Expand %NAME% placeholders.

        Unlike os.path.expandvars, WSH PRESERVES unknown placeholders:
        ExpandEnvironmentStrings("%NOPE%") returns "%NOPE%" (verified on IIS).
        Lookup is case-insensitive, and a lone '%' is left alone.
        """
        s = vbs_cstr(template)
        if not s:
            return ""
        upper_map = {k.upper(): v for k, v in os.environ.items()}

        def _sub(m):
            name = m.group(1)
            val = upper_map.get(name.upper())
            return val if val is not None else m.group(0)

        return re.sub(r"%([^%]+)%", _sub, s)

    def Environment(self, scope=None):
        if scope is None:
            # WSH defaults to the SYSTEM scope when called without arguments.
            return WshEnvironment("SYSTEM")
        name = vbs_cstr(scope).upper()
        if name not in self._ENV_SCOPES:
            # IIS raises error 5 for an unknown scope (verified).
            raise_runtime('INVALID_PROC_CALL',
                          f"Unknown WScript.Shell environment scope: {scope}")
        return WshEnvironment(name)

    @property
    def CurrentDirectory(self):
        return os.getcwd()

    @CurrentDirectory.setter
    def CurrentDirectory(self, value):
        try:
            os.chdir(vbs_cstr(value))
        except Exception:
            raise_runtime('INVALID_PROC_CALL',
                          "WScript.Shell.CurrentDirectory: path not found")

    @property
    def SpecialFolders(self):
        return WshSpecialFolders()

    def CreateShortcut(self, path=None):
        """Return a WshShortcut (.lnk) or WshUrlShortcut (.url).

        WSH picks the object from the file extension and raises for anything
        else; the file is not written until Save is called.
        """
        p = vbs_cstr(path)
        if not p:
            raise_runtime('INVALID_PROC_CALL',
                          "WScript.Shell.CreateShortcut: path is required")
        p = os.path.abspath(p)
        ext = os.path.splitext(p)[1].lower()
        if ext == '.url':
            return WshUrlShortcut(p)
        if ext == '.lnk':
            return WshShortcut(p)
        raise_runtime('INVALID_PROC_CALL',
                      "WScript.Shell.CreateShortcut: path must end in .lnk or .url")

    def RegRead(self, name=None):
        """Read a registry value. Windows only; a missing key raises, as in WSH.

        A name ending in '\\' reads the key's default value.
        """
        key_path = vbs_cstr(name)
        if not key_path:
            raise_runtime('INVALID_PROC_CALL',
                          "WScript.Shell.RegRead: name is required")
        if os.name != 'nt':
            raise_runtime('COMPONENT_CANT_CREATE',
                          "WScript.Shell.RegRead is only available on Windows")
        import winreg

        roots = {
            'HKEY_CLASSES_ROOT': winreg.HKEY_CLASSES_ROOT, 'HKCR': winreg.HKEY_CLASSES_ROOT,
            'HKEY_CURRENT_USER': winreg.HKEY_CURRENT_USER, 'HKCU': winreg.HKEY_CURRENT_USER,
            'HKEY_LOCAL_MACHINE': winreg.HKEY_LOCAL_MACHINE, 'HKLM': winreg.HKEY_LOCAL_MACHINE,
            'HKEY_USERS': winreg.HKEY_USERS, 'HKU': winreg.HKEY_USERS,
            'HKEY_CURRENT_CONFIG': winreg.HKEY_CURRENT_CONFIG, 'HKCC': winreg.HKEY_CURRENT_CONFIG,
        }
        head, _, rest = key_path.replace('/', '\\').partition('\\')
        root = roots.get(head.upper())
        if root is None:
            raise_runtime('INVALID_PROC_CALL',
                          f"WScript.Shell.RegRead: invalid root key '{head}'")

        if rest.endswith('\\'):          # trailing slash = the default value
            sub, value_name = rest.rstrip('\\'), ''
        else:
            sub, _, value_name = rest.rpartition('\\')

        try:
            with winreg.OpenKey(root, sub) as k:
                data, kind = winreg.QueryValueEx(k, value_name)
        except OSError:
            raise_runtime('ADO_UNSPECIFIED',
                          f"WScript.Shell.RegRead: unable to open registry key {key_path}")
        if kind == winreg.REG_MULTI_SZ:
            from .vm.values import VBArray
            items = list(data or [])
            arr = VBArray(len(items) - 1, allocated=True, dynamic=True)
            for i, v in enumerate(items):
                arr.__vbs_index_set__(i, str(v))
            return arr
        if kind == winreg.REG_BINARY:
            return bytes(data or b'')
        if kind in (winreg.REG_DWORD, winreg.REG_QWORD):
            return int(data)
        return str(data)

    def Run(self, *_args, **_kwargs):
        self._unsupported('Run')

    def Exec(self, *_args, **_kwargs):
        self._unsupported('Exec')

    def __vbs_typename__(self):
        return "IWshShell3"

    def _vbs_get_prop(self, name: str):
        up = str(name).upper()
        if up == 'CURRENTDIRECTORY':
            return self.CurrentDirectory
        if up == 'EXPANDENVIRONMENTSTRINGS':
            return self.ExpandEnvironmentStrings
        if up == 'ENVIRONMENT':
            return self.Environment
        if up == 'SPECIALFOLDERS':
            return self.SpecialFolders
        if up == 'CREATESHORTCUT':
            return self.CreateShortcut
        if up == 'REGREAD':
            return self.RegRead
        if up == 'RUN':
            return self.Run
        if up == 'EXEC':
            return self.Exec
        # Anything else genuinely does not exist on this object: IIS reports
        # 438 (e.g. WScript.Shell has no GetEnv member).
        raise_runtime('OBJECT_NOT_SUPPORT',
                      f"WScript.Shell does not support this property or method: {name}")

    def _vbs_set_prop(self, name: str, value):
        if str(name).upper() == 'CURRENTDIRECTORY':
            self.CurrentDirectory = value
            return
        raise_runtime('OBJECT_NOT_SUPPORT',
                      f"WScript.Shell does not support this property or method: {name}")


class ASPError:
    """ASPError object returned by Server.GetLastError().

    Properties are intended to be read-only from VBScript.
    """

    def __init__(
        self,
        *,
        number: int = 0x80004005,
        description: str = "",
        category: str = "ASPPY",
        asp_code: str = "",
        asp_description: str = "",
        file: str = "",
        line: int = 0,
        column: int = 0,
        source: str = "",
    ):
        self.ASPCode = asp_code
        self.ASPDescription = asp_description
        self.Category = category
        self.Column = int(column)
        self.Description = description
        self.File = file
        self.Line = int(line)
        self.Number = int(number)
        self.Source = source


class _DictKeyProxy:
    """Indexable proxy backing Scripting.Dictionary's Key property.

    Enables `d.Key("old") = "new"` (rename). Reads return the stored
    (original-case) key when present (permissive; IIS treats Key as
    write-only).
    """

    def __init__(self, owner: 'ScriptingDictionary'):
        self._owner = owner

    def __vbs_index_get__(self, key):
        ent = self._owner._d.get(self._owner._norm(key))
        return ent[0] if ent is not None else ""

    def __vbs_index_set__(self, key, new_key):
        self._owner._rename_key(key, new_key)


class ScriptingDictionary:
    """Scripting.Dictionary adapter with VBScript Variant key semantics.

    - Keys are Variants: 5 and "5" are DIFFERENT keys; 5, 5.0 and True/-1
      compare numerically; strings honor CompareMode.
    - Reading a MISSING key via Item auto-adds the key with an Empty value
      (documented Scripting.Dictionary behavior on IIS).
    - Add on an existing key raises error 457; Remove on a missing key
      raises error 32811 ("Element not found").
    """

    def __init__(self):
        # normalized_key -> (original_key_variant, value)
        self._d: dict[Any, tuple[Any, Any]] = {}
        # 0=BinaryCompare (case-sensitive), 1=TextCompare (case-insensitive), 2=DatabaseCompare
        self._compare_mode = 0

    def _norm(self, key):
        """Normalize a Variant key to a hashable bucket key."""
        if isinstance(key, str):
            return ('s', key if self._compare_mode == 0 else key.lower())
        if isinstance(key, bool):
            return ('n', -1.0 if key else 0.0)
        if isinstance(key, (int, float)):
            return ('n', float(key))
        if isinstance(key, datetime.datetime):
            return ('n', (key - datetime.datetime(1899, 12, 30)).total_seconds() / 86400.0)
        if isinstance(key, datetime.date):
            return ('n', (datetime.datetime(key.year, key.month, key.day)
                          - datetime.datetime(1899, 12, 30)).total_seconds() / 86400.0)
        try:
            from .vm.values import VBEmpty, VBNull, VBNothing
            if key is VBEmpty or key is None:
                return ('e', None)
            if key is VBNull:
                return ('u', None)
            if key is VBNothing:
                return ('o', id(key))
        except Exception:
            pass
        from decimal import Decimal as _Dec
        if isinstance(key, _Dec):
            return ('n', float(key))
        # Objects: identity-keyed, like VBScript object keys.
        return ('o', id(key))

    @property
    def Count(self):
        return len(self._d)

    @property
    def CompareMode(self):
        return self._compare_mode

    @CompareMode.setter
    def CompareMode(self, value):
        from .vb_errors import raise_runtime
        v = int(value)
        if v not in (0, 1, 2):
            raise_runtime('INVALID_PROC_CALL', "Invalid CompareMode")
        # Scripting.Dictionary refuses a CompareMode change once it holds
        # data: IIS raises error 5 (Invalid procedure call or argument) with
        # the plain standard description.
        if self._d and v != self._compare_mode:
            raise_runtime('INVALID_PROC_CALL')
        self._compare_mode = v

    def Add(self, key, item):
        k = self._norm(key)
        if k in self._d:
            from .vb_errors import raise_runtime
            raise_runtime('KEY_ALREADY_EXISTS')
        self._d[k] = (key, item)

    def Exists(self, key):
        return self._norm(key) in self._d

    def Remove(self, key):
        k = self._norm(key)
        if k not in self._d:
            from .vb_errors import raise_runtime
            raise_runtime('ELEMENT_NOT_FOUND')
        del self._d[k]

    def RemoveAll(self):
        self._d.clear()

    def __vbs_index_get__(self, key):
        ent = self._d.get(self._norm(key))
        if ent is not None:
            return ent[1]
        # VBScript: reading a missing key AUTO-ADDS it with an Empty value.
        from .vm.values import VBEmpty
        self._d[self._norm(key)] = (key, VBEmpty)
        return VBEmpty

    def __vbs_index_set__(self, key, value):
        nk = self._norm(key)
        if nk in self._d:
            old_orig, _old_val = self._d[nk]
            self._d[nk] = (old_orig, value)
        else:
            self._d[nk] = (key, value)

    @property
    def Item(self):
        # VBScript: Item is the default member (indexable).
        # This allows both reads:  d.Item("k")
        # and writes:             d.Item("k") = "v"
        return self

    @property
    def Key(self):
        # VBScript: d.Key("old") = "new" renames a key (item and insertion
        # order are preserved).
        return _DictKeyProxy(self)

    def _rename_key(self, key, new_key):
        old_norm = self._norm(key)
        if old_norm not in self._d:
            # Scripting.Dictionary raises "Element not found" (32811)
            from .vb_errors import raise_runtime
            raise_runtime('ELEMENT_NOT_FOUND')
        new_norm = self._norm(new_key)
        if new_norm == old_norm:
            # Same key (e.g. casing change under TextCompare): keep item,
            # update the stored original casing.
            _old_orig, val = self._d[old_norm]
            self._d[old_norm] = (new_key, val)
            return
        if new_norm in self._d:
            from .vb_errors import raise_runtime
            raise_runtime('KEY_ALREADY_EXISTS')
        # Rebuild to preserve insertion order (rename in place).
        new_d: dict[Any, tuple[Any, Any]] = {}
        for nk, (orig, val) in self._d.items():
            if nk == old_norm:
                new_d[new_norm] = (new_key, val)
            else:
                new_d[nk] = (orig, val)
        self._d = new_d

    @property
    def Keys(self):
        # Return a VBArray of keys
        try:
            from .vm.values import VBArray
        except Exception:
            return [k for (k, _v) in self._d.values()]
        keys = [k for (k, _v) in self._d.values()]
        a = VBArray(len(keys) - 1, allocated=True, dynamic=True)
        for i, k in enumerate(keys):
            a.__vbs_index_set__(i, k)
        return a

    @property
    def Items(self):
        try:
            from .vm.values import VBArray
        except Exception:
            return [v for (_k, v) in self._d.values()]
        items = [v for (_k, v) in self._d.values()]
        a = VBArray(len(items) - 1, allocated=True, dynamic=True)
        for i, v in enumerate(items):
            a.__vbs_index_set__(i, v)
        return a

    def __iter__(self):
        return iter([k for (k, _v) in self._d.values()])


class Server:
    def __init__(
        self,
        docroot: str,
        current_path: str,
        render_include_fn,
        last_error_getter=None,
        ctx_getter=None,
    ):
        self._docroot = os.path.abspath(docroot)
        self._current_path = current_path or "/"
        self._render_include_fn = render_include_fn
        self._last_error_getter = last_error_getter or (lambda: None)
        self._ctx_getter = ctx_getter
        self._script_timeout = 90

    @property
    def ScriptTimeout(self):
        return self._script_timeout

    @ScriptTimeout.setter
    def ScriptTimeout(self, value):
        self._script_timeout = int(value)

    def CreateObject(self, progid):
        pid = str(progid).strip().lower()
        if pid == "wscript.shell":
            return WScriptShell()
        if pid == "scripting.dictionary":
            return ScriptingDictionary()
        if pid == "scripting.filesystemobject":
            return FileSystemObject(self._docroot)
        if pid == "adodb.stream":
            return ADODBStream(self._docroot)
        if pid in ("vbscript.regexp", "regexp"):
            return VBScriptRegExp()
        if pid in ("msxml2.serverxmlhttp", "msxml2.serverxmlhttp.6.0", "msxml2.serverxmlhttp.3.0"):
            from .msxml import ServerXMLHTTP

            return ServerXMLHTTP()
        if pid in ("msxml2.xmlhttp", "msxml2.xmlhttp.6.0", "msxml2.xmlhttp.3.0"):
            from .msxml import XMLHTTP

            return XMLHTTP()
        if pid in ("msxml2.domdocument", "msxml2.domdocument.6.0", "msxml2.domdocument.3.0"):
            from .msxml import DOMDocument

            return DOMDocument(docroot=self._docroot)
        if pid in ("microsoft.xmldom", "msxml.domdocument"):
            from .msxml import DOMDocument

            return DOMDocument(docroot=self._docroot)
        # The free-threaded DOM is the same object model, just a different
        # threading model - irrelevant here, and IIS reports TypeName
        # "DOMDocument" for these too (verified on IIS 10). Legacy code uses
        # them for cached/Application-scoped XML, e.g. PowerEasy's
        # Server.CreateObject("Microsoft.FreeThreadedXMLDOM").
        if pid in ("microsoft.freethreadedxmldom",
                   "msxml2.freethreadeddomdocument",
                   "msxml2.freethreadeddomdocument.3.0",
                   "msxml2.freethreadeddomdocument.6.0"):
            from .msxml import DOMDocument

            return DOMDocument(docroot=self._docroot)
        if pid in ("cdo.message", "cdosys.message"):
            from .cdo import CDOMessage

            return CDOMessage(docroot=self._docroot)
        if pid == "cdo.configuration":
            from .cdo import CDOConfiguration

            return CDOConfiguration()
        if pid == "asppy.pop3":
            from .pop3 import ASPPYPOP3

            return ASPPYPOP3()
        if pid == "asppy.imap":
            from .imap import ASPPYIMAP

            return ASPPYIMAP()
        if pid in ("adodb.connection",):
            from .adodb import ADOConnection
            obj = ADOConnection(docroot=self._docroot)
            return obj
        if pid in ("adodb.recordset",):
            from .adodb import ADORecordset
            return ADORecordset()
        if pid in ("adodb.command",):
            from .adodb import ADOCommand
            return ADOCommand()
        # IIS reports an ASP 0177 failure with HRESULT 0x800401F3
        # (invalid class string) for an unknown ProgID. Err.Number becomes
        # -2147221005, which pages test for, so mirror that exactly.
        raise VBScriptCOMError(-2147221005,
                               "006~ASP 0177~Server.CreateObject failed~800401f3")

    def HTMLEncode(self, s):
        # The Server methods report Type mismatch (13) for Null, not Invalid use
        # of Null (94) as the VBScript string functions do. Verified against IIS.
        if s is VBNull:
            raise VBScriptCOMError(13, "Type mismatch")
        # VBScript coerces Empty/Nothing/Null to an empty string in most
        # string contexts; avoid leaking sentinel reprs like "VBEmpty".
        t = vbs_cstr(s)
        return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

    def URLEncode(self, s):
        # Type mismatch (13), matching Server.HTMLEncode - see note there.
        if s is VBNull:
            raise VBScriptCOMError(13, "Type mismatch")
        # Use '+' for spaces like typical URL encoding
        return urllib.parse.quote_plus(vbs_cstr(s))

    def MapPath(self, path):
        if path is VBNull:
            raise VBScriptCOMError(94, "Invalid use of Null")
        p = str(path)
        # IIS parity: an empty path is rejected with E_FAIL (Err.Number
        # -2147467259), it does NOT quietly resolve to the application root.
        if p.strip() == "":
            raise VBScriptCOMError(-2147467259, "Unspecified error")
        # Remove querystring
        p = p.split('?', 1)[0]
        if p.startswith('~'):
            p = p[1:]

        if p.startswith('/') or p.startswith('\\'):
            rel = p.lstrip('/\\')
            target = os.path.abspath(os.path.join(self._docroot, rel))
        else:
            # Relative to current file
            cur_dir = os.path.dirname(self._current_path.lstrip('/\\'))
            target = os.path.abspath(os.path.join(self._docroot, cur_dir, p))

        # Prevent path traversal outside docroot
        if os.path.commonpath([self._docroot, target]) != self._docroot:
            raise Exception("Server.MapPath: path outside application")

        # Case-insensitive fallback for Linux
        if os.name != "nt" and not os.path.isfile(target):
            if os.path.isdir(os.path.dirname(target)):
                dir_path = os.path.dirname(target)
                filename = os.path.basename(target)
                try:
                    entries = os.listdir(dir_path)
                except Exception:
                    pass
                else:
                    filename_lower = filename.lower()
                    for name in entries:
                        if name.lower() == filename_lower:
                            target = os.path.join(dir_path, name)
                            break

        return target

    def Execute(self, path):
        # Include another ASP file and continue.
        self._render_include_fn(str(path), transfer=False)

    def Transfer(self, path):
        # Transfer control to another ASP file.
        # IIS keeps already-generated output (typically buffered) and stops executing
        # the current page.
        self._render_include_fn(str(path), transfer=True)
        raise ServerTransferException(str(path))

    def GetLastError(self):
        e = self._last_error_getter()
        if e is None:
            # IIS behavior: when no error occurred, properties are mostly blank/zero.
            return ASPError(
                number=0,
                description="",
                category="",
                asp_code="",
                asp_description="",
                file="",
                line=0,
                column=-1,
                source="",
            )
        if isinstance(e, ASPError):
            return e
        return ASPError(description=str(e))

    def ASPPYListAspPages(self):
        """ASPPY extension: list .asp pages under docroot.

        Returns a VBArray of virtual paths like "/hello.asp".
        """
        try:
            from .vm.values import VBArray
        except Exception:
            VBArray = None

        paths = []
        for root, _dirs, files in os.walk(self._docroot):
            for fn in files:
                if not fn.lower().endswith('.asp'):
                    continue
                phys = os.path.join(root, fn)
                rel = os.path.relpath(phys, self._docroot)
                v = '/' + rel.replace('\\', '/').replace(os.sep, '/').lstrip('/')
                paths.append(v.lower())
        paths = sorted(set(paths))
        if VBArray is None:
            return paths
        a = VBArray(len(paths) - 1, allocated=True, dynamic=True)
        for i, p in enumerate(paths):
            a.__vbs_index_set__(i, p)
        return a

    def ASPPYRun(self, virtual_path: str):
        """ASPPY extension: render another ASP page and capture status.

        Runs in an isolated view of the current Session/Application (state is restored).
        """
        from .http_response import RenderResult, Response, ResponseEndException
        from .asp_page import parse_asp_page, exec_asp_nodes
        from .vm.context import ExecutionContext
        from .vm.interpreter import VBInterpreter
        from .runner_vm import _build_globals_env
        from .http_request import Request
        from .asp_include import expand_includes, IncludeError
        from .vb_err import VBErr

        target_v = str(virtual_path).strip() or "/"
        if not target_v.startswith('/'):
            target_v = '/' + target_v

        class ASPPYRunResult:
            def __init__(self, path: str, status_code: int, status_message: str, error: str):
                self.Path = path
                self.StatusCode = int(status_code)
                self.StatusMessage = str(status_message or "")
                self.Error = str(error or "")

        parent_ctx = None
        if callable(self._ctx_getter):
            try:
                parent_ctx = self._ctx_getter()
            except Exception:
                parent_ctx = None

        sess = getattr(parent_ctx, 'Session', None) if parent_ctx is not None else None
        app = getattr(parent_ctx, 'Application', None) if parent_ctx is not None else None
        parent_req = getattr(parent_ctx, 'Request', None) if parent_ctx is not None else None

        sess_backing = None
        sess_static = None
        sess_abandoned = None
        app_backing = None
        app_static = None
        try:
            if sess is not None and hasattr(sess, '_backing'):
                sess_backing = dict(getattr(sess, '_backing'))
                sess_abandoned = bool(getattr(sess, '_abandoned', False))
                if hasattr(sess, '_static_objects'):
                    sess_static = dict(getattr(sess, '_static_objects'))
            if app is not None and hasattr(app, '_backing'):
                app_backing = dict(getattr(app, '_backing'))
                if hasattr(app, '_static_objects'):
                    app_static = dict(getattr(app, '_static_objects'))

            phys = self.MapPath(target_v)
            if not os.path.isfile(phys):
                return ASPPYRunResult(target_v, 404, "Not Found", "")
            with open(phys, 'r', encoding='utf-8') as f:
                raw = f.read()

            try:
                raw = expand_includes(raw, current_phys=phys, docroot=self._docroot, current_virtual=target_v)
            except IncludeError as e:
                return ASPPYRunResult(target_v, 500, "Internal Server Error", str(e))

            # Build a response for the child run.
            res = RenderResult()
            body_out = bytearray()
            resp = Response(res, body_out)

            holder = cast(dict[str, Any], {'interp': None, 'ctx': None})

            def render_include(target_path: str, transfer: bool = False):
                interp = holder['interp']
                # Map relative to current page.
                tmp_server = Server(self._docroot, target_v, render_include_fn=lambda *_a, **_k: None)
                inc_phys = tmp_server.MapPath(target_path)
                if not os.path.isfile(inc_phys):
                    raise Exception("Server.Execute/Transfer: file not found")
                with open(inc_phys, 'r', encoding='utf-8') as f2:
                    inc_text = f2.read()
                try:
                    inc_text = expand_includes(inc_text, current_phys=inc_phys, docroot=self._docroot, current_virtual=target_path)
                except IncludeError as e:
                    raise Exception(f"Include error: {e}")
                exec_asp_nodes(parse_asp_page(inc_text), interp)

            child_box = cast(dict[str, Any], {'ctx': None})
            child_srv = Server(self._docroot, target_v, render_include_fn=render_include, ctx_getter=lambda: child_box['ctx'])

            headers = {}
            remote = ""
            if parent_req is not None and hasattr(parent_req, '_headers'):
                try:
                    headers = dict(getattr(parent_req, '_headers'))
                except Exception:
                    headers = {}
            if parent_req is not None and hasattr(parent_req, '_remote_addr'):
                try:
                    remote = str(getattr(parent_req, '_remote_addr'))
                except Exception:
                    remote = ""
            req = Request('GET', target_v, '', headers, b'', remote_addr=remote, docroot=self._docroot)

            ctx = ExecutionContext(response=resp, request=req, session=sess, application=app, server=child_srv, err=VBErr())
            child_box['ctx'] = ctx
            env = _build_globals_env(ctx)
            interp = VBInterpreter(ctx, env)
            holder['interp'] = interp
            holder['ctx'] = ctx

            try:
                exec_asp_nodes(parse_asp_page(raw), interp)
            except (ServerTransferException, ResponseEndException):
                pass
            except Exception as e:
                res.status_code = 500
                res.status_message = 'Internal Server Error'
                resp.Write('Error during ASP execution: ' + str(e) + '\n')
                resp.Flush()
                resp._finalize_headers()
                res.body = bytes(body_out)
                return ASPPYRunResult(target_v, res.status_code, res.status_message, str(e))
            finally:
                try:
                    resp.Flush()
                except Exception:
                    pass
                try:
                    resp._finalize_headers()
                except Exception:
                    pass
                res.body = bytes(body_out)

            return ASPPYRunResult(target_v, res.status_code, res.status_message, "")
        finally:
            # Restore parent session/application state.
            try:
                if sess is not None and sess_backing is not None and hasattr(sess, '_backing'):
                    b = getattr(sess, '_backing')
                    b.clear()
                    b.update(sess_backing)
                    if sess_abandoned is not None:
                        setattr(sess, '_abandoned', bool(sess_abandoned))
                    if sess_static is not None and hasattr(sess, '_static_objects'):
                        so = getattr(sess, '_static_objects')
                        so.clear()
                        so.update(sess_static)
            except Exception:
                pass
            try:
                if app is not None and app_backing is not None and hasattr(app, '_backing'):
                    b = getattr(app, '_backing')
                    b.clear()
                    b.update(app_backing)
                    if app_static is not None and hasattr(app, '_static_objects'):
                        so = getattr(app, '_static_objects')
                        so.clear()
                        so.update(app_static)
            except Exception:
                pass


def _has_ads(path: str) -> bool:
    # Disallow NTFS alternate data streams ("file.txt:stream").
    # Allow a single drive letter colon prefix ("C:\...").
    p = str(path)
    if ':' not in p:
        return False
    if len(p) >= 2 and p[1] == ':':
        return p.count(':') != 1
    return True


class VBScriptRegExpSubMatches:
    def __init__(self, groups: list[str]):
        self._groups = list(groups)

    @property
    def Count(self):
        return len(self._groups)

    def Item(self, idx):
        i = int(idx)
        return self._groups[i]

    def __vbs_index_get__(self, idx):
        return self.Item(idx)

    def __iter__(self):
        return iter(self._groups)


class VBScriptRegExpMatch:
    def __init__(self, value: str, first_index: int, length: int, groups: list[str]):
        self.Value = value
        self.FirstIndex = int(first_index)
        self.Length = int(length)
        self.SubMatches = VBScriptRegExpSubMatches(groups)


class VBScriptRegExpMatches:
    def __init__(self, matches: list[VBScriptRegExpMatch]):
        self._matches = list(matches)

    @property
    def Count(self):
        return len(self._matches)

    def Item(self, idx):
        i = int(idx)
        return self._matches[i]

    def __vbs_index_get__(self, idx):
        return self.Item(idx)

    def __iter__(self):
        return iter(self._matches)


class VBScriptRegExp:
    """Minimal VBScript.RegExp shim (enough for common legacy apps)."""

    def __init__(self):
        self.Pattern = ""
        self.IgnoreCase = False
        self.Global = False
        self.MultiLine = False

    def _compile(self):
        import re

        flags = 0
        if bool(self.IgnoreCase):
            flags |= re.IGNORECASE
        if bool(self.MultiLine):
            flags |= re.MULTILINE
        try:
            return re.compile(vbs_cstr(self.Pattern), flags)
        except Exception as e:
            raise Exception(f"RegExp pattern error: {e}")

    def Test(self, s):
        r = self._compile()
        return r.search(vbs_cstr(s)) is not None

    def Replace(self, s, replace_with):
        r = self._compile()
        text = vbs_cstr(s)
        repl = vbs_cstr(replace_with)
        def _expand(m):
            return self._expand_vbscript_replacement(m, repl, text)
        if bool(self.Global):
            return r.sub(_expand, text)
        return r.sub(_expand, text, count=1)

    def _expand_vbscript_replacement(self, m, repl: str, text: str) -> str:
        out: list[str] = []
        i = 0
        n = len(repl)
        while i < n:
            ch = repl[i]
            if ch != '$' or i + 1 >= n:
                out.append(ch)
                i += 1
                continue

            nxt = repl[i + 1]
            if nxt == '$':
                out.append('$')
                i += 2
                continue
            if nxt == '&':
                out.append(m.group(0))
                i += 2
                continue
            if nxt == '`':
                out.append(text[:m.start()])
                i += 2
                continue
            if nxt == "'":
                out.append(text[m.end():])
                i += 2
                continue
            if nxt.isdigit():
                j = i + 1
                while j < n and repl[j].isdigit():
                    j += 1
                try:
                    idx = int(repl[i + 1:j])
                except Exception:
                    idx = -1
                if idx > 0:
                    try:
                        val = m.group(idx)
                    except Exception:
                        val = ""
                    out.append(val if val is not None else "")
                    i = j
                    continue

            out.append('$')
            i += 1
        return ''.join(out)

    def Execute(self, s):
        r = self._compile()
        text = vbs_cstr(s)
        out: list[VBScriptRegExpMatch] = []
        for m in r.finditer(text):
            groups = [g if g is not None else "" for g in m.groups()]
            out.append(VBScriptRegExpMatch(m.group(0), m.start(), m.end() - m.start(), groups))
            if not bool(self.Global):
                break
        return VBScriptRegExpMatches(out)


class ADODBStream:
    """Sandboxed ADODB.Stream shim.

    Implements the small subset used by legacy apps (read/write text and binary,
    load/save files).
    """

    # Common ADODB.Stream constants
    adTypeBinary = 1
    adTypeText = 2

    adSaveCreateNotExist = 1
    adSaveCreateOverWrite = 2

    def __init__(self, default_root: str):
        root = os.environ.get('ASP_PY_ADO_ROOT', '')
        self._root = os.path.abspath(root) if root else os.path.abspath(default_root)

        self._opened = False
        self._type = self.adTypeText
        # ADODB.Stream default Charset under Windows/ADO is typically "Unicode".
        self.Charset = "Unicode"
        # Default line separator for text streams (adCRLF).
        # ADO exposes LineSeparator as a LineSeparatorEnum, and IIS reports the
        # enum value (adCRLF = -1), not the literal separator string. Verified
        # against IIS. _get_line_separator() resolves it to characters.
        self.LineSeparator = -1  # adCRLF
        self.Mode = 1
        self._pos = 0
        self._buf_text = ""
        self._buf_bin = bytearray()

    def _ensure_in_root(self, phys: str) -> str:
        phys = os.path.abspath(phys)
        if os.path.commonpath([self._root, phys]) != self._root:
            raise Exception("ADODB.Stream: path outside sandbox")
        return phys

    def _resolve(self, path: str) -> str:
        if _has_ads(path):
            raise Exception("ADODB.Stream: ADS not allowed")
        p = vbs_cstr(path).strip()
        if p.startswith('\\'):
            raise Exception("ADODB.Stream: UNC paths not supported")

        p_os = p.replace('\\', os.sep)

        # Absolute physical paths (including Server.MapPath output)
        if os.path.isabs(p_os):
            return self._ensure_in_root(p_os)

        # Windows drive-letter paths on non-Windows hosts: treat as sandbox-rooted.
        p_norm = p.replace('\\', '/')
        if len(p_norm) >= 3 and p_norm[1] == ':' and p_norm[2] == '/':
            rest = p_norm[3:]
            phys = os.path.join(self._root, rest)
            return self._ensure_in_root(phys)

        phys = os.path.join(self._root, p_os)
        return self._ensure_in_root(phys)

    @property
    def Type(self):
        return int(self._type)

    @Type.setter
    def Type(self, v):
        new_t = int(v)
        old_t = int(getattr(self, '_type', self.adTypeText))
        self._type = new_t
        self._pos = 0
        # Best-effort conversion between buffers to match common ADO.Stream usage:
        # - binary -> text: defer decoding until ReadText (Charset may be set after Type)
        # - text -> binary: encode text using Charset
        try:
            if old_t == self.adTypeBinary and new_t == self.adTypeText:
                # Keep binary buffer; decode lazily so setting Charset after
                # Type change behaves like ADO.Stream.
                self._buf_text = ""
            elif old_t == self.adTypeText and new_t == self.adTypeBinary:
                # The binary view of a text stream is exactly what it would
                # write out, BOM included - switching Type is how ADO scripts
                # inspect the encoded bytes. This used to re-encode without the
                # BOM, so the byte view disagreed with Size and SaveToFile.
                if vbs_cstr(self._buf_text):
                    self._buf_bin = bytearray(self._text_bytes_for_io())
                    self._buf_text = ""
        except Exception:
            pass

    @property
    def CharSet(self):
        return getattr(self, 'Charset', '')

    @CharSet.setter
    def CharSet(self, v):
        self.Charset = v

    def _text_is_authoritative(self) -> bool:
        """True when the character buffer, not the byte buffer, holds the data."""
        if self._type == self.adTypeBinary:
            return False
        return not (len(self._buf_bin) > 0 and not self._buf_text)

    def _char_to_byte(self, nchars: int) -> int:
        """Character index in the text buffer -> ADO byte offset (BOM included)."""
        txt = vbs_cstr(self._buf_text)
        n = max(0, min(int(nchars), len(txt)))
        if not txt or n == 0:
            # Byte 0 and the first byte after the BOM both denote character 0;
            # ADO reports the start of the stream as 0, so prefer that.
            return 0
        enc, bom = self._encoding_and_bom()
        try:
            return len(bom) + len(txt[:n].encode(enc, errors='replace'))
        except Exception:
            return len(bom) + len(txt[:n].encode('utf-8', errors='replace'))

    def _byte_to_char(self, nbytes: int) -> int:
        """ADO byte offset -> character index in the text buffer."""
        raw = self._text_bytes_for_io()
        if not raw:
            return 0
        enc, bom = self._encoding_and_bom()
        n = max(0, min(int(nbytes), len(raw)))
        body = raw[len(bom):n] if n > len(bom) else b""
        try:
            return len(body.decode(enc, errors='ignore'))
        except Exception:
            return len(body.decode('utf-8', errors='ignore'))

    @property
    def Position(self):
        # ADO reports Position in BYTES, so at end-of-stream it equals Size.
        # Internally _pos indexes the character buffer for text streams, hence
        # the translation here (and in the setter).
        if self._text_is_authoritative():
            return self._char_to_byte(self._pos)
        return int(self._pos)

    @Position.setter
    def Position(self, v):
        n = int(v)
        if n < 0:
            n = 0
        if self._text_is_authoritative():
            self._pos = self._byte_to_char(n)
            return
        # Legacy upload scripts (freeASPUpload) drive a TEXT-mode stream that
        # actually holds bytes, and pass a position 2 too high; Size adds the
        # matching +2 for that same case. Left exactly as it was.
        if n > 0 and self._type == self.adTypeText and len(self._buf_bin) > 0 and (not self._buf_text):
            n -= 2
            if n < 0:
                n = 0
        self._pos = n

    @property
    def Size(self):
        # Some legacy scripts write raw bytes via WriteText into a text stream.
        # If binary buffer is populated, prefer it.
        if len(self._buf_bin) > 0 and (not self._buf_text):
            # ADO.Stream in text mode can report a size slightly larger than the
            # raw payload (implementation detail). This matches common IIS
            # behavior and keeps legacy upload scripts working.
            if self._type == self.adTypeText:
                return len(self._buf_bin) + 2
            return len(self._buf_bin)
        if self._type == self.adTypeBinary:
            return len(self._buf_bin)
        # Text stream: ADO reports the length in BYTES of what the stream would
        # write out, BOM included. (This used to approximate it as character
        # count + 2, which was only ever right for UTF-16 ASCII text.)
        return len(self._text_bytes_for_io())

    @property
    def EOS(self):
        return int(self._pos) >= int(self._effective_length())

    @property
    def State(self):
        # adStateClosed=0, adStateOpen=1
        return 1 if self._opened else 0

    def _effective_length(self) -> int:
        if len(self._buf_bin) > 0 and (not self._buf_text):
            return len(self._buf_bin)
        if self._type == self.adTypeBinary:
            return len(self._buf_bin)
        return len(vbs_cstr(self._buf_text))

    def _get_line_separator(self):
        ls = getattr(self, 'LineSeparator', "\r\n")
        if isinstance(ls, int):
            if ls == -1:
                return "\r\n"
            if ls == 10:
                return "\n"
            if ls == 13:
                return "\r"
            return "\r\n"
        s = vbs_cstr(ls)
        return s or "\r\n"

    def _encoding_and_bom(self) -> tuple:
        """Python codec and byte-order mark for the current Charset.

        ADO writes a BOM for the Unicode encodings and nothing for single-byte
        code pages. Verified against IIS by writing 16 characters plus one LF
        and reading the buffer back as binary:

            Charset         Size   first bytes
            utf-8            20    EF BB BF 48   <- 3-byte BOM
            Unicode          36    FF FE 48 00   <- 2-byte BOM, UTF-16LE
            windows-1252     17    48 65 6C 6C   <- no BOM
        """
        cs = vbs_cstr(getattr(self, 'Charset', '') or 'Unicode').strip()
        cs_l = cs.lower()
        if cs_l in ('unicode', 'utf-16', 'utf16', 'utf-16le', 'utf-16-le'):
            return 'utf-16-le', b"\xff\xfe"
        if cs_l in ('utf-8', 'utf8'):
            return 'utf-8', b"\xef\xbb\xbf"
        if cs_l in ('iso-8859-1', 'latin1', 'latin-1'):
            return 'latin-1', b""
        if cs_l in ('windows-1252', 'cp1252'):
            return 'cp1252', b""
        return (cs or 'utf-8'), b""

    def _text_bytes_for_io(self) -> bytes:
        """The text buffer as ADO would hand it out: BOM + encoded text.

        This is the single byte view used by Size, SaveToFile and CopyTo, so
        the three cannot disagree. SaveToFile used to re-encode without any
        BOM, which meant a UTF-8 file written through ADODB.Stream - the usual
        way legacy ASP produces CSV and XML - came out without the BOM its
        consumers (Excel above all) expect.
        """
        txt = vbs_cstr(self._buf_text)
        if not txt:
            # An empty stream is 0 bytes on IIS - the BOM only appears once
            # there is content to write.
            return b""
        enc, bom = self._encoding_and_bom()
        try:
            return bom + txt.encode(enc, errors='replace')
        except Exception:
            return bom + txt.encode('utf-8', errors='replace')

    def Open(self):
        self._opened = True

    def Close(self):
        self._opened = False

    def Cancel(self):
        return

    def SetEOS(self):
        """Make the current position the end of the stream, discarding the rest.

        This used to do the opposite - move the POSITION to the end - so
        `stm.Position = 0 : stm.SetEOS` left the content untouched instead of
        emptying the stream.

        For a text stream the cut is made on the BYTE offset, as ADO does, so
        `Position = 0` also removes the BOM and leaves Size at 0. (Note the
        wider caveat on Position below: ReadText and SkipLine still treat it as
        a character offset in text mode.)
        """
        self._ensure_open()
        if self._type == self.adTypeBinary or (len(self._buf_bin) > 0 and not self._buf_text):
            pos = max(0, int(self._pos))
            del self._buf_bin[pos:]
            self._pos = min(pos, len(self._buf_bin))
            return

        # _pos indexes characters here; the cut is on the byte offset.
        pos = self._char_to_byte(self._pos)
        raw = self._text_bytes_for_io()[:pos]
        enc, bom = self._encoding_and_bom()
        if raw.startswith(bom):
            raw = raw[len(bom):]
        elif bom:
            # The cut landed inside the BOM: nothing decodable survives.
            raw = b""
        try:
            self._buf_text = raw.decode(enc, errors='ignore')
        except Exception:
            self._buf_text = raw.decode('utf-8', errors='ignore')
        self._pos = min(pos, int(self._effective_length()))

    def SkipLine(self):
        self._ensure_open()
        sep = self._get_line_separator()
        if not sep:
            return

        if len(self._buf_bin) > 0 and (not self._buf_text):
            src = bytes(self._buf_bin)
            sep_b = sep.encode('latin-1', errors='replace')
            start = min(max(0, int(self._pos)), len(src))
            idx = src.find(sep_b, start)
            if idx == -1:
                self._pos = len(src)
            else:
                self._pos = idx + len(sep_b)
            return

        text = vbs_cstr(self._buf_text)
        start = min(max(0, int(self._pos)), len(text))
        idx = text.find(sep, start)
        if idx == -1:
            self._pos = len(text)
        else:
            self._pos = idx + len(sep)
        return

    def _ensure_open(self):
        if not self._opened:
            self.Open()

    def LoadFromFile(self, filename):
        self._ensure_open()
        phys = self._resolve(filename)
        if not os.path.isfile(phys):
            # Graceful fallback: if path ends with duplicate extension
            # (e.g. .inc.inc), try single extension.
            base, ext1 = os.path.splitext(phys)
            base2, ext2 = os.path.splitext(base)
            if ext1 and ext2 and ext1.lower() == ext2.lower():
                alt = base
                if os.path.isfile(alt):
                    phys = alt
        if self._type == self.adTypeBinary:
            with open(phys, 'rb') as f:
                self._buf_bin = bytearray(f.read())
            self._pos = 0
            return

        with open(phys, 'rb') as f:
            raw = f.read()
        cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
        try:
            self._buf_text = raw.decode(cs, errors='replace')
        except Exception:
            self._buf_text = raw.decode('utf-8', errors='replace')
        self._pos = 0

    def SaveToFile(self, filename, option=adSaveCreateOverWrite):
        self._ensure_open()
        phys = self._resolve(filename)
        opt = int(option)
        if opt == self.adSaveCreateNotExist and os.path.exists(phys):
            raise Exception("ADODB.Stream: file already exists")

        os.makedirs(os.path.dirname(phys) or '.', exist_ok=True)

        if self._type == self.adTypeBinary or (len(self._buf_bin) > 0 and (not self._buf_text)):
            data = bytes(self._buf_bin)
            with open(phys, 'wb') as f:
                f.write(data)
            return

        # Same byte view as Size/CopyTo, so the file on disk carries the BOM.
        with open(phys, 'wb') as f:
            f.write(self._text_bytes_for_io())

    def Read(self, count=None):
        self._ensure_open()
        if self._type == self.adTypeText:
            from .vb_runtime import VBScriptCOMError

            # Match ADODB.Stream behavior: Read() is not valid for text streams.
            raise VBScriptCOMError(-2147024809, "The parameter is incorrect.")
        has_binary = (len(self._buf_bin) > 0 and (not self._buf_text))
        if has_binary:
            # Binary data stored in text-mode stream - use 0-based position
            start = int(self._pos)
            start = min(max(0, start), len(self._buf_bin))
            if count is None:
                out = bytes(self._buf_bin[start:])
                self._pos = len(self._buf_bin)
                return out
            n = int(count)
            if n < 0:
                n = 0
            out = bytes(self._buf_bin[start:start + n])
            self._pos = start + len(out)
            return out
        if self._type != self.adTypeBinary:
            # Best-effort: return encoded text.
            cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
            try:
                b = vbs_cstr(self._buf_text).encode(cs, errors='replace')
            except Exception:
                b = vbs_cstr(self._buf_text).encode('utf-8', errors='replace')
            start = min(self._pos, len(b))
            if count is None:
                out = b[start:]
                self._pos = len(b)
                return out
            n = int(count)
            if n < 0:
                n = 0
            out = b[start:start + n]
            self._pos = start + len(out)
            return out

        start = min(self._pos, len(self._buf_bin))
        if count is None:
            out = bytes(self._buf_bin[start:])
            self._pos = len(self._buf_bin)
            return out
        n = int(count)
        if n < 0:
            n = 0
        out = bytes(self._buf_bin[start:start + n])
        self._pos = start + len(out)
        return out

    def ReadText(self, count=-1):
        self._ensure_open()
        if len(self._buf_bin) > 0 and (not self._buf_text):
            cs = vbs_cstr(getattr(self, 'Charset', '') or 'utf-8')
            start = int(self._pos)
            if self._type == self.adTypeText and start > 0:
                start -= 1
            start = min(max(0, start), len(self._buf_bin))
            n = int(count) if count is not None else -1
            if n < 0:
                chunk = bytes(self._buf_bin[start:])
                self._pos = len(self._buf_bin)
            else:
                chunk = bytes(self._buf_bin[start:start + n])
                self._pos = start + len(chunk)
            try:
                return chunk.decode(cs, errors='strict')
            except Exception:
                # Avoid raising here; callers often use On Error Resume Next.
                # Returning empty matches common ADO.Stream behavior when the
                # byte sequence isn't valid for the selected Charset.
                return ""
        # If we are in text mode but only binary data exists, decode lazily.
        if self._type == self.adTypeText and (not self._buf_text) and len(self._buf_bin) > 0:
            try:
                self.Type = self.adTypeText
            except Exception:
                pass
        text = vbs_cstr(self._buf_text)
        start = min(self._pos, len(text))
        n = int(count) if count is not None else -1
        if n < 0:
            out = text[start:]
            self._pos = len(text)
            return out
        out = text[start:start + n]
        self._pos = start + len(out)
        return out

    def Write(self, data):
        self._ensure_open()
        if self._type != self.adTypeBinary:
            # Best-effort: treat as bytes and append to text via latin-1.
            b = self._coerce_bytes(data)
            try:
                s = b.decode('latin-1')
            except Exception:
                s = ''
            return self.WriteText(s)

        b = self._coerce_bytes(data)
        pos = min(self._pos, len(self._buf_bin))
        end = pos + len(b)
        if end <= len(self._buf_bin):
            self._buf_bin[pos:end] = b
        else:
            if pos < len(self._buf_bin):
                self._buf_bin[pos:] = b
            else:
                self._buf_bin.extend(b)
        self._pos = end

    def WriteText(self, s, options=0):
        """Write text to the stream.

        `options` is a StreamWriteEnum: adWriteChar (0, default) writes the text
        as-is, adWriteLine (1) appends LineSeparator afterwards.
        """
        self._ensure_open()
        if isinstance(s, (bytes, bytearray)) and self._type == self.adTypeText:
            # Preserve bytes 1:1 in the binary buffer (upload scripts depend on this).
            b = bytes(s)
            pos = int(self._pos)
            if pos < 0:
                pos = 0
            if pos > len(self._buf_bin):
                self._buf_bin.extend(b"\x00" * (pos - len(self._buf_bin)))
            end = pos + len(b)
            if end <= len(self._buf_bin):
                self._buf_bin[pos:end] = b
            else:
                if pos < len(self._buf_bin):
                    self._buf_bin[pos:] = b
                else:
                    self._buf_bin.extend(b)
            self._pos = end
            # Mark text buffer as not authoritative.
            self._buf_text = ""
            return
        if self._type == self.adTypeBinary:
            return self.Write(self._coerce_bytes(s))

        ins = vbs_cstr(s)
        try:
            write_line = int(options) == 1        # adWriteLine
        except Exception:
            write_line = False
        if write_line:
            ins = ins + self._get_line_separator()
        text = vbs_cstr(self._buf_text)
        pos = min(self._pos, len(text))
        if pos == 0:
            self._buf_text = ins
            self._pos = len(ins)
            return
        if pos >= len(text):
            self._buf_text = text + ins
            self._pos = len(self._buf_text)
            return
        self._buf_text = text[:pos] + ins + text[pos + len(ins):]
        self._pos = pos + len(ins)

    def CopyTo(self, dest_stream, count=None):
        """Copy bytes from this stream to dest_stream.

        Used heavily by legacy upload scripts.
        """
        self._ensure_open()
        if dest_stream is None:
            raise Exception("ADODB.Stream.CopyTo: dest is Nothing")

        # Get a byte view of the source.
        has_binary = (len(self._buf_bin) > 0 and (not self._buf_text))
        if has_binary:
            src = bytes(self._buf_bin)
        elif self._type == self.adTypeBinary:
            src = bytes(self._buf_bin)
        else:
            src = self._text_bytes_for_io()

        start = int(self._pos)
        start = min(max(0, start), len(src))
        n = None
        if count is not None and str(count) != "":
            try:
                n = int(count)
            except Exception:
                n = None
        chunk = src[start:] if n is None else src[start:start + max(0, n)]
        self._pos = start + len(chunk)

        try:
            dest_stream.Write(chunk)
        except Exception:
            dest_stream.WriteText(chunk)

    def Flush(self):
        self._ensure_open()

        # Materialize the current stream content in the active representation.
        # This mirrors ADO's "commit buffered data" intent even though this
        # shim keeps data in memory.
        if self._type == self.adTypeBinary:
            if len(self._buf_bin) == 0 and self._buf_text:
                self._buf_bin = bytearray(self._text_bytes_for_io())
        else:
            if self._buf_text and len(self._buf_bin) == 0:
                self._buf_bin = bytearray(self._text_bytes_for_io())

        # Keep position within valid bounds after materialization.
        end = int(self._effective_length())
        if self._pos < 0:
            self._pos = 0
        elif self._pos > end:
            self._pos = end

    def _coerce_bytes(self, data) -> bytes:
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, (list, tuple)):
            return bytes(int(x) & 0xFF for x in data)
        # VBArray (from vm.values) best-effort
        try:
            if hasattr(data, '__vbs_index_get__') and hasattr(data, 'UBound'):
                ub = int(data.UBound(1))
                out = bytearray()
                for i in range(0, ub + 1):
                    out.append(int(data.__vbs_index_get__(i)) & 0xFF)
                return bytes(out)
        except Exception:
            pass
        try:
            return vbs_cstr(data).encode('latin-1')
        except Exception:
            return vbs_cstr(data).encode('utf-8', errors='replace')


class TextStream:
    def __init__(self, f):
        self._f = f
        # Line/Column tracking (Scripting TextStream is 1-based for both).
        self._line = 1
        self._col = 1

    def Close(self):
        if self._f is None:
            return
        try:
            self._f.close()
        finally:
            self._f = None

    def _track(self, s: str):
        """Advance Line/Column counters over text that was read or written."""
        if not s:
            return
        nl = s.count("\r\n") + s.replace("\r\n", "").count("\n") + s.replace("\r\n", "").count("\r")
        if nl:
            self._line += nl
            # Column = chars after the last line break, 1-based
            tail = s.replace("\r\n", "\n").replace("\r", "\n").rsplit("\n", 1)[-1]
            self._col = len(tail) + 1
        else:
            self._col += len(s)

    @property
    def AtEndOfStream(self):
        if self._f is None:
            return True
        pos = self._f.tell()
        ch = self._f.read(1)
        self._f.seek(pos)
        return ch == ""

    @property
    def AtEndOfLine(self):
        if self._f is None:
            return True
        pos = self._f.tell()
        ch = self._f.read(1)
        self._f.seek(pos)
        return ch == "" or ch in ("\r", "\n")

    @property
    def Line(self):
        return self._line

    @property
    def Column(self):
        return self._col

    def Read(self, characters):
        if self._f is None:
            return ""
        n = int(characters)
        if n <= 0:
            return ""
        s = self._f.read(n)
        self._track(s)
        return s

    def ReadAll(self):
        if self._f is None:
            return ""
        s = self._f.read()
        self._track(s)
        return s

    def ReadLine(self):
        if self._f is None:
            return ""
        s = self._f.readline()
        self._track(s)
        if s.endswith("\r\n"):
            return s[:-2]
        if s.endswith("\n"):
            return s[:-1]
        if s.endswith("\r"):
            return s[:-1]
        return s

    def Skip(self, characters):
        if self._f is None:
            return
        n = int(characters)
        if n > 0:
            self._track(self._f.read(n))

    def SkipLine(self):
        if self._f is None:
            return
        self._track(self._f.readline())

    def Write(self, s):
        if self._f is None:
            return
        t = vbs_cstr(s)
        self._f.write(t)
        self._track(t)

    def WriteLine(self, s=""):
        if self._f is None:
            return
        t = vbs_cstr(s) + "\r\n"
        self._f.write(t)
        self._track(t)

    def WriteBlankLines(self, lines):
        if self._f is None:
            return
        n = int(lines)
        if n > 0:
            self._f.write("\r\n" * n)
            self._line += n
            self._col = 1


class Drive:
    """Scripting.Drive adapter (Script 5.6 exposes 12 properties).

    Windows-specific values (FileSystem, SerialNumber, VolumeName, DriveType)
    come from Win32 APIs via ctypes; non-Windows platforms return sensible
    fallbacks so coverage code keeps working cross-platform.
    """

    # FSO's Drive object reads as its Path in a value context, so
    # `"Drive=" & f.Drive` yields "Drive=C:" as it does on IIS.
    __vbs_default__ = 'Path'

    def __init__(self, path: str):
        # Path is the drive spec WITHOUT a trailing separator ("C:", not
        # "C:\"); RootFolder is what carries the backslash.
        p = str(path or "")
        if os.name == 'nt' and len(p) >= 2 and p[1] == ':':
            p = p[:2]
        elif len(p) > 1:
            p = p.rstrip('\\/') or p
        self.Path = p

    def _root(self) -> str:
        p = str(self.Path)
        if os.name == 'nt' and len(p) >= 2 and p[1] == ':':
            return p[:2] + '\\'
        return p if p.endswith(os.sep) else p + os.sep

    def _volume_info(self):
        """Returns (volume_name, serial_number, filesystem) best-effort."""
        if os.name == 'nt':
            try:
                import ctypes
                vol_buf = ctypes.create_unicode_buffer(261)
                fs_buf = ctypes.create_unicode_buffer(261)
                serial = ctypes.c_uint32(0)
                max_len = ctypes.c_uint32(0)
                flags = ctypes.c_uint32(0)
                ok = ctypes.windll.kernel32.GetVolumeInformationW(
                    ctypes.c_wchar_p(self._root()),
                    vol_buf, 261,
                    ctypes.byref(serial),
                    ctypes.byref(max_len),
                    ctypes.byref(flags),
                    fs_buf, 261,
                )
                if ok:
                    # FSO SerialNumber is a signed 32-bit Long.
                    sn = serial.value
                    if sn & 0x80000000:
                        sn -= 0x100000000
                    return vol_buf.value, sn, fs_buf.value
            except Exception:
                pass
            return "", 0, ""
        # POSIX fallback
        return "", 0, ""

    @property
    def DriveLetter(self):
        p = str(self.Path)
        if len(p) >= 2 and p[1] == ':':
            return p[0].upper()
        return ""

    @property
    def DriveType(self):
        # FSO: 0=Unknown, 1=Removable, 2=Fixed, 3=Network, 4=CD-ROM, 5=RAM disk
        if os.name == 'nt':
            try:
                import ctypes
                t = ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(self._root()))
                return {2: 1, 3: 2, 4: 3, 5: 4, 6: 5}.get(int(t), 0)
            except Exception:
                return 0
        return 2  # treat POSIX root as a fixed drive

    @property
    def IsReady(self):
        try:
            return os.path.exists(self._root())
        except Exception:
            return False

    @property
    def FileSystem(self):
        return self._volume_info()[2]

    @property
    def SerialNumber(self):
        return self._volume_info()[1]

    @property
    def ShareName(self):
        # Only meaningful for mapped network drives; empty otherwise.
        if os.name == 'nt' and self.DriveType == 3:
            try:
                import ctypes
                buf = ctypes.create_unicode_buffer(1024)
                length = ctypes.c_uint32(1024)
                dev = (self.DriveLetter + ':')
                if ctypes.windll.mpr.WNetGetConnectionW(
                        ctypes.c_wchar_p(dev), buf, ctypes.byref(length)) == 0:
                    return buf.value
            except Exception:
                pass
        return ""

    @property
    def VolumeName(self):
        return self._volume_info()[0]

    @VolumeName.setter
    def VolumeName(self, value):
        if os.name == 'nt':
            try:
                import ctypes
                ctypes.windll.kernel32.SetVolumeLabelW(
                    ctypes.c_wchar_p(self._root()), ctypes.c_wchar_p(vbs_cstr(value)))
            except Exception:
                pass

    @property
    def TotalSize(self):
        try:
            return shutil.disk_usage(self._root()).total
        except Exception:
            return 0

    @property
    def FreeSpace(self):
        try:
            return shutil.disk_usage(self._root()).free
        except Exception:
            return 0

    @property
    def AvailableSpace(self):
        return self.FreeSpace

    @property
    def RootFolder(self):
        return Folder(self._root())


class DrivesCollection:
    def __init__(self, drives: list[Drive]):
        self._drives = drives

    def __iter__(self):
        return iter(self._drives)

    @property
    def Count(self):
        return len(self._drives)


class File:
    def __init__(self, path: str):
        self.Path = path

    @property
    def Name(self):
        return os.path.basename(self.Path)

    @Name.setter
    def Name(self, new_name):
        nm = vbs_cstr(new_name).strip()
        if not nm:
            return
        nm = os.path.basename(nm)
        base = os.path.dirname(self.Path)
        dest = os.path.abspath(os.path.join(base, nm))
        src = os.path.abspath(self.Path)
        if dest == src:
            return
        try:
            os.replace(src, dest)
        except Exception:
            shutil.move(src, dest)
        self.Path = dest

    @property
    def Attributes(self):
        """Best-effort Scripting.File.Attributes bitmask.

        Windows: returns GetFileAttributesW value (shares common bit values with FSO).
        Non-Windows: approximates ReadOnly/Hidden/Directory/Archive.
        """
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes

                GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
                GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
                GetFileAttributesW.restype = ctypes.c_uint32
                attrs = int(GetFileAttributesW(p))
                if attrs == 0xFFFFFFFF:
                    return 0
                return attrs
        except Exception:
            pass

        # Fallback approximation
        attrs = 0
        try:
            # Read-only
            if not os.access(p, os.W_OK):
                attrs |= 1
            # Hidden (unix-style)
            if os.path.basename(p).startswith('.'):
                attrs |= 2
            # Directory
            if os.path.isdir(p):
                attrs |= 16
            # Archive (treat as regular file)
            if os.path.isfile(p):
                attrs |= 32
        except Exception:
            return 0
        return attrs

    @property
    def Size(self):
        try:
            return os.path.getsize(self.Path)
        except Exception:
            return 0

    @property
    def DateCreated(self):
        try:
            ts = os.path.getctime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastAccessed(self):
        try:
            ts = os.path.getatime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastModified(self):
        try:
            ts = os.path.getmtime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def Drive(self):
        drive, _ = os.path.splitdrive(self.Path)
        if drive:
            root = drive
            if not root.endswith('\\') and not root.endswith('/'):
                root = root + '\\'
            return Drive(root)
        return Drive(self.Path)

    @property
    def ParentFolder(self):
        parent = os.path.dirname(self.Path)
        return Folder(parent) if parent else Folder(self.Path)

    @property
    def ShortName(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        # ShortName is the 8.3 NAME; ShortPath is the full
                        # short path. GetShortPathName returns the latter.
                        return os.path.basename(s)
        except Exception:
            pass
        return os.path.basename(self.Path)

    @property
    def ShortPath(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        return s
        except Exception:
            pass
        return self.Path

    @property
    def Type(self):
        mime, _ = mimetypes.guess_type(self.Path)
        if mime:
            return mime
        ext = os.path.splitext(self.Path)[1]
        if ext:
            return f"{ext[1:].upper()} File"
        return "File"

    def Copy(self, destination, overwrite=True):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(self.Path))
        dest = os.path.abspath(dest)
        if os.path.exists(dest) and not bool(overwrite):
            raise Exception("Copy: destination exists")
        shutil.copy2(self.Path, dest)

    def Move(self, destination):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(self.Path))
        dest = os.path.abspath(dest)
        shutil.move(self.Path, dest)
        self.Path = dest
        self.Name = os.path.basename(dest)

    def OpenAsTextStream(self, iomode=1, create=False, format=-2):
        mode = int(iomode)
        if mode == 1:
            fmode = 'r'
        elif mode == 2:
            fmode = 'w'
        elif mode == 8:
            fmode = 'a'
        else:
            raise Exception("OpenAsTextStream: invalid iomode")

        phys = self.Path
        if (not os.path.exists(phys)) and (not bool(create)) and fmode == 'r':
            raise Exception("OpenAsTextStream: file not found")

        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")

        f = open(phys, fmode, encoding='utf-8', newline='')
        return TextStream(f)

    def Delete(self, force=False):
        try:
            os.remove(self.Path)
        except Exception:
            if bool(force):
                try:
                    os.chmod(self.Path, 0o666)
                    os.remove(self.Path)
                except Exception:
                    pass
            else:
                raise

    def __str__(self):
        return str(self.Path)


class Folder:
    def __init__(self, path: str):
        self.Path = path
        self.Name = os.path.basename(os.path.normpath(path))

    def __str__(self):
        return str(self.Path)

    @property
    def Files(self):
        return FilesCollection(self.Path)

    @property
    def SubFolders(self):
        return FoldersCollection(self.Path)

    @property
    def Attributes(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes

                GetFileAttributesW = ctypes.windll.kernel32.GetFileAttributesW
                GetFileAttributesW.argtypes = [ctypes.c_wchar_p]
                GetFileAttributesW.restype = ctypes.c_uint32
                attrs = int(GetFileAttributesW(p))
                if attrs == 0xFFFFFFFF:
                    return 0
                return attrs
        except Exception:
            pass

        attrs = 0
        try:
            if not os.access(p, os.W_OK):
                attrs |= 1
            if os.path.basename(p).startswith('.'):
                attrs |= 2
            if os.path.isdir(p):
                attrs |= 16
            if os.path.isdir(p):
                attrs |= 32
        except Exception:
            return 0
        return attrs

    @property
    def DateCreated(self):
        try:
            ts = os.path.getctime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastAccessed(self):
        try:
            ts = os.path.getatime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def DateLastModified(self):
        try:
            ts = os.path.getmtime(self.Path)
            return datetime.datetime.fromtimestamp(ts)
        except Exception:
            return None

    @property
    def Drive(self):
        drive, _ = os.path.splitdrive(self.Path)
        if drive:
            root = drive
            if not root.endswith('\\') and not root.endswith('/'):
                root = root + '\\'
            return Drive(root)
        return Drive(self.Path)

    @property
    def IsRootFolder(self):
        try:
            p = os.path.abspath(self.Path)
            parent = os.path.dirname(p)
            return parent == p
        except Exception:
            return False

    @property
    def ShortName(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        # ShortName is the 8.3 NAME; ShortPath is the full
                        # short path. GetShortPathName returns the latter.
                        return os.path.basename(s)
        except Exception:
            pass
        return os.path.basename(self.Path)

    @property
    def ShortPath(self):
        p = self.Path
        try:
            if os.name == 'nt':
                import ctypes
                from ctypes import create_unicode_buffer

                GetShortPathNameW = ctypes.windll.kernel32.GetShortPathNameW
                GetShortPathNameW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
                GetShortPathNameW.restype = ctypes.c_uint
                buf = create_unicode_buffer(260)
                if GetShortPathNameW(p, buf, 260):
                    s = buf.value
                    if s:
                        return s
        except Exception:
            pass
        return self.Path

    @property
    def Size(self):
        total = 0
        try:
            for root, _dirs, files in os.walk(self.Path):
                for name in files:
                    p = os.path.join(root, name)
                    try:
                        total += os.path.getsize(p)
                    except Exception:
                        pass
        except Exception:
            return 0
        return total

    @property
    def Type(self):
        return "File Folder"

    @property
    def ParentFolder(self):
        parent = os.path.dirname(self.Path)
        return Folder(parent) if parent else Folder(self.Path)

    def Copy(self, destination, overwrite=True):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(os.path.normpath(self.Path)))
        dest = os.path.abspath(dest)
        if os.path.exists(dest):
            if not bool(overwrite):
                raise Exception("Copy: destination exists")
            shutil.rmtree(dest, ignore_errors=True)
        parent = os.path.dirname(dest)
        if parent and not os.path.isdir(parent):
            raise Exception("Copy: destination parent not found")
        shutil.copytree(self.Path, dest)

    def CreateTextFile(self, filename, overwrite=True, unicode=False):
        phys = os.path.join(self.Path, vbs_cstr(filename).strip())
        if os.path.exists(phys) and not bool(overwrite):
            raise Exception("CreateTextFile: file already exists")
        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")
        f = open(phys, 'w', encoding='latin-1', errors='replace', newline='')
        return TextStream(f)

    def Delete(self, force=False):
        try:
            if bool(force):
                def _onerror(func, path, _exc):
                    try:
                        os.chmod(path, 0o666)
                        func(path)
                    except Exception:
                        pass

                shutil.rmtree(self.Path, onerror=_onerror)
            else:
                shutil.rmtree(self.Path)
        except Exception:
            if bool(force):
                return
            raise

    def Move(self, destination):
        dest = destination
        if os.path.isdir(destination) or destination.endswith(('/', '\\')):
            dest = os.path.join(destination, os.path.basename(os.path.normpath(self.Path)))
        dest = os.path.abspath(dest)
        parent = os.path.dirname(dest)
        if parent and not os.path.isdir(parent):
            raise Exception("Move: destination parent not found")
        shutil.move(self.Path, dest)
        self.Path = dest
        self.Name = os.path.basename(os.path.normpath(dest))

    def GetFile(self, filename):
        phys = os.path.join(self.Path, vbs_cstr(filename).strip())
        phys = os.path.abspath(phys)
        if not os.path.isfile(phys):
            raise Exception("GetFile: not found")
        return File(phys)

    def GetFolder(self, foldername):
        phys = os.path.join(self.Path, vbs_cstr(foldername).strip())
        phys = os.path.abspath(phys)
        if not os.path.isdir(phys):
            raise Exception("GetFolder: not found")
        return Folder(phys)

    def CreateFolder(self, name):
        phys = os.path.join(self.Path, vbs_cstr(name).strip())
        if os.path.exists(phys):
            raise Exception("Folder already exists")
        os.makedirs(phys, exist_ok=False)
        return Folder(phys)

    def DeleteFolder(self, folder, force=False):
        pat = os.path.join(self.Path, vbs_cstr(folder).strip())
        if not os.path.isdir(pat) and not os.path.exists(pat):
            return
        if bool(force):
            def _onerror(func, path, _exc):
                try:
                    os.chmod(path, 0o666)
                    func(path)
                except Exception:
                    pass

            shutil.rmtree(pat, onerror=_onerror)
        else:
            shutil.rmtree(pat)


class FoldersCollection:
    def __init__(self, folder_path: str):
        self._path = folder_path

    def __iter__(self):
        try:
            names = sorted(os.listdir(self._path), key=str.lower)
        except Exception:
            names = []
        for n in names:
            p = os.path.join(self._path, n)
            if os.path.isdir(p):
                yield Folder(p)

    @property
    def Count(self):
        try:
            return sum(1 for e in os.scandir(self._path) if e.is_dir())
        except Exception:
            return 0


class FilesCollection:
    def __init__(self, folder_path: str):
        self._path = folder_path

    def __iter__(self):
        try:
            names = sorted(os.listdir(self._path), key=str.lower)
        except Exception:
            names = []
        for n in names:
            p = os.path.join(self._path, n)
            if os.path.isfile(p):
                yield File(p)

    @property
    def Count(self):
        try:
            return sum(1 for e in os.scandir(self._path) if e.is_file())
        except Exception:
            return 0


class FileSystemObject:
    """Sandboxed Scripting.FileSystemObject adapter.

    By default, all paths are restricted to the ASP server docroot.
    Override with ASP_PY_FSO_ROOT to widen/narrow the sandbox.
    """

    def __init__(self, default_root: str):
        root = os.environ.get('ASP_PY_FSO_ROOT', '')
        self._root = os.path.abspath(root) if root else os.path.abspath(default_root)

    def _ensure_in_root(self, phys: str) -> str:
        phys = os.path.abspath(phys)
        if os.path.commonpath([self._root, phys]) != self._root:
            raise Exception("FileSystemObject: path outside sandbox")
        return phys

    def _resolve(self, path: str) -> str:
        if _has_ads(path):
            raise Exception("FileSystemObject: ADS not allowed")
        p = vbs_cstr(path).strip()
        if p.startswith('\\\\'):
            raise Exception("FileSystemObject: UNC paths not supported")

        p_os = p.replace('\\', os.sep)

        # Absolute physical paths (including Server.MapPath output).
        if os.path.isabs(p_os):
            return self._ensure_in_root(p_os)

        # Windows drive-letter paths on non-Windows hosts: treat as sandbox-rooted.
        p_norm = p.replace('\\', '/')
        if len(p_norm) >= 3 and p_norm[1] == ':' and p_norm[2] == '/':
            rest = p_norm[3:]
            phys = os.path.join(self._root, rest)
            return self._ensure_in_root(phys)

        # Relative paths are sandbox-root-relative.
        phys = os.path.join(self._root, p_os)
        return self._ensure_in_root(phys)

    def _resolve_pattern(self, pattern: str) -> tuple[str, list[str]]:
        if _has_ads(pattern):
            raise Exception("FileSystemObject: ADS not allowed")
        raw = vbs_cstr(pattern).strip()
        raw_os = raw.replace('\\', os.sep)
        if os.path.isabs(raw_os):
            phys_pat = raw_os
        else:
            raw_norm = raw.replace('\\', '/')
            if len(raw_norm) >= 3 and raw_norm[1] == ':' and raw_norm[2] == '/':
                rest = raw_norm[3:]
                phys_pat = os.path.join(self._root, rest)
            else:
                phys_pat = os.path.join(self._root, raw_os)

        phys_pat = os.path.abspath(phys_pat)
        if os.path.commonpath([self._root, phys_pat]) != self._root:
            raise Exception("FileSystemObject: path outside sandbox")

        matches = glob.glob(phys_pat)
        out = []
        for m in matches:
            m2 = os.path.abspath(m)
            if os.path.commonpath([self._root, m2]) != self._root:
                continue
            out.append(m2)
        return phys_pat, out

    def BuildPath(self, path, name):
        base = vbs_cstr(path).strip().replace('\\', os.sep)
        nm = vbs_cstr(name).strip().lstrip('\\/').replace('\\', os.sep)
        return os.path.join(base, nm)

    def FileExists(self, path):
        # A pure existence check must never raise: IIS answers True/False for
        # any path. Anything the sandbox refuses simply "does not exist",
        # so legacy pages like If fso.FolderExists("C:\") Then keep working.
        try:
            phys = self._resolve(path)
        except Exception:
            return False
        return os.path.isfile(phys)

    def FolderExists(self, path):
        try:
            phys = self._resolve(path)
        except Exception:
            return False
        return os.path.isdir(phys)

    def CreateFolder(self, path):
        phys = self._resolve(path)
        if os.path.exists(phys):
            raise Exception("Folder already exists")
        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")
        os.mkdir(phys)
        return Folder(phys)

    def DeleteFolder(self, folder, force=False):
        _pat, matches = self._resolve_pattern(folder)
        if not matches:
            return
        for m in matches:
            if not os.path.isdir(m):
                continue
            if bool(force):
                def _onerror(func, path, _exc):
                    try:
                        os.chmod(path, 0o666)
                        func(path)
                    except Exception:
                        pass

                shutil.rmtree(m, onerror=_onerror)
            else:
                shutil.rmtree(m)

    def DeleteFile(self, filespec, force=False):
        _pat, matches = self._resolve_pattern(filespec)
        if not matches:
            return
        for m in matches:
            if not os.path.isfile(m):
                continue
            try:
                os.remove(m)
            except Exception:
                if bool(force):
                    try:
                        os.chmod(m, 0o666)
                        os.remove(m)
                    except Exception:
                        pass
                else:
                    raise

    def CopyFile(self, source, destination, overwrite=True):
        _pat, sources = self._resolve_pattern(source)
        if not sources:
            raise Exception("CopyFile: source not found")

        dest_phys = self._resolve(destination)
        dest_is_dir = os.path.isdir(dest_phys) or vbs_cstr(destination).strip().endswith(('\\', '/'))
        if len(sources) > 1 and not dest_is_dir:
            raise Exception("CopyFile: destination must be a folder")

        if dest_is_dir and not os.path.isdir(dest_phys):
            raise Exception("CopyFile: destination folder not found")

        for src in sources:
            if dest_is_dir:
                dst = os.path.join(dest_phys, os.path.basename(src))
            else:
                dst = dest_phys
            dst = self._ensure_in_root(dst)
            if os.path.exists(dst) and not bool(overwrite):
                raise Exception("CopyFile: destination exists")
            shutil.copy2(src, dst)

    def MoveFile(self, source, destination):
        _pat, sources = self._resolve_pattern(source)
        if not sources:
            raise Exception("MoveFile: source not found")

        dest_phys = self._resolve(destination)
        dest_is_dir = os.path.isdir(dest_phys) or vbs_cstr(destination).strip().endswith(('\\', '/'))
        if len(sources) > 1 and not dest_is_dir:
            raise Exception("MoveFile: destination must be a folder")
        if dest_is_dir and not os.path.isdir(dest_phys):
            raise Exception("MoveFile: destination folder not found")

        for src in sources:
            if dest_is_dir:
                dst = os.path.join(dest_phys, os.path.basename(src))
            else:
                dst = dest_phys
            dst = self._ensure_in_root(dst)
            shutil.move(src, dst)

    def CopyFolder(self, source, destination, overwrite=True):
        src = self._resolve(source)
        dst = self._resolve(destination)
        if not os.path.isdir(src):
            raise Exception("CopyFolder: source not found")
        if os.path.exists(dst):
            if not bool(overwrite):
                raise Exception("CopyFolder: destination exists")
            shutil.rmtree(dst, ignore_errors=True)
        parent = os.path.dirname(dst)
        if parent and not os.path.isdir(parent):
            raise Exception("CopyFolder: destination parent not found")
        shutil.copytree(src, dst)

    def MoveFolder(self, source, destination):
        src = self._resolve(source)
        dst = self._resolve(destination)
        if not os.path.isdir(src):
            raise Exception("MoveFolder: source not found")
        parent = os.path.dirname(dst)
        if parent and not os.path.isdir(parent):
            raise Exception("MoveFolder: destination parent not found")
        shutil.move(src, dst)

    def GetAbsolutePathName(self, path):
        return self._resolve(path)

    def GetBaseName(self, path):
        b = os.path.basename(vbs_cstr(path).replace('\\', os.sep))
        return os.path.splitext(b)[0]

    def GetDriveName(self, path):
        p = vbs_cstr(path).strip()
        if len(p) >= 2 and p[1] == ':':
            return p[:2]
        return ""

    def DriveExists(self, drive):
        d = vbs_cstr(drive).strip()
        if len(d) == 1:
            d = d + ':'
        if len(d) == 2 and d[1] == ':':
            if os.name == 'nt':
                return os.path.exists(d + '\\')
            return False
        return False

    def GetDrive(self, drive_spec):
        d = vbs_cstr(drive_spec).strip()
        if len(d) == 1:
            d = d + ':'
        if os.name == 'nt' and len(d) == 2 and d[1] == ':':
            return Drive(d + '\\')
        # POSIX: single root drive
        return Drive(self._root)

    @property
    def Drives(self):
        if os.name == 'nt':
            ds: list[Drive] = []
            for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ':
                p = c + ':\\'
                if os.path.exists(p):
                    ds.append(Drive(p))
            return DrivesCollection(ds)
        return DrivesCollection([Drive(self._root)])

    def GetExtensionName(self, path):
        p = vbs_cstr(path).replace('\x00', '')
        b = os.path.basename(p.replace('\\', os.sep))
        ext = os.path.splitext(b)[1]
        if ext.startswith('.'):
            ext = ext[1:]
        ext = ext.strip()
        if ext:
            ext = "".join(ch for ch in ext if ch.isalnum())
        ext = ext.strip(".")
        return ext

    def GetFileName(self, path):
        return os.path.basename(vbs_cstr(path).replace('\\', os.sep))

    def GetParentFolderName(self, path):
        p = vbs_cstr(path).replace('\\', os.sep)
        return os.path.dirname(p)

    def GetTempName(self):
        return "rad" + uuid.uuid4().hex[:6] + ".tmp"

    def GetSpecialFolder(self, folder_spec):
        # 0=WindowsFolder, 1=SystemFolder, 2=TemporaryFolder
        # Real FSO returns a Folder object (Folder stringifies to its Path,
        # so string concatenation keeps working).
        n = int(folder_spec)
        if n == 2:
            p = os.path.join(self._root, '_tmp')
            p = self._ensure_in_root(p)
            os.makedirs(p, exist_ok=True)
            return Folder(p)
        return Folder(self._root)

    def GetFile(self, path):
        phys = self._resolve(path)
        if not os.path.isfile(phys):
            raise Exception("GetFile: not found")
        return File(phys)

    def GetFolder(self, path):
        phys = self._resolve(path)
        if not os.path.isdir(phys):
            raise Exception("GetFolder: not found")
        return Folder(phys)

    def OpenTextFile(self, filename, iomode=1, create=False, format=-2):
        mode = int(iomode)
        phys = self._resolve(filename)
        # Do not expose ForReading/ForWriting/ForAppending as properties.
        # In Classic ASP these are typically user-defined Const values.
        if mode == 1:
            fmode = 'r'
        elif mode == 2:
            fmode = 'w'
        elif mode == 8:
            fmode = 'a'
        else:
            raise Exception("OpenTextFile: invalid iomode")

        if (not os.path.exists(phys)) and (not bool(create)) and fmode == 'r':
            raise Exception("OpenTextFile: file not found")

        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")

        f = open(phys, fmode, encoding='latin-1', errors='replace', newline='')
        return TextStream(f)

    def CreateTextFile(self, filename, overwrite=True, unicode=False):
        phys = self._resolve(filename)
        if os.path.exists(phys) and not bool(overwrite):
            raise Exception("CreateTextFile: file already exists")
        parent = os.path.dirname(phys)
        if parent and not os.path.isdir(parent):
            raise Exception("Path not found")
        f = open(phys, 'w', encoding='latin-1', errors='replace', newline='')
        return TextStream(f)
