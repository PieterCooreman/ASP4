"""ADODB shim for ASPPY – SQLite backend.

Implements enough of the ADO object model to run Classic ASP / aspLite apps
against SQLite.

Supported ProgIDs (all map here via server_object.py):
  ADODB.Connection
  ADODB.Recordset
  ADODB.Command

Thread-safety note: each ASP request runs in its own thread; objects are
request-scoped and are not shared across threads.
"""

from __future__ import annotations

import datetime
import importlib
import os
import re
import threading
from dataclasses import dataclass
from typing import Any, Optional

# Database drivers are imported lazily (only when a page actually opens a
# connection), to keep importing this module cheap for pages without ADO.
sqlite3 = None
pyodbc = None


def _ensure_sqlite3():
    global sqlite3
    if sqlite3 is None:
        sqlite3 = importlib.import_module('sqlite3')
    return sqlite3


def _ensure_pyodbc():
    global pyodbc
    if pyodbc is None:
        try:
            pyodbc = importlib.import_module('pyodbc')
        except Exception:
            pyodbc = None
    return pyodbc

from .vb_runtime import vbs_cstr, vbs_cbool
from .vm.values import VBEmpty, VBNothing, VBNull

# ---------------------------------------------------------------------------
# ADO constants
# ---------------------------------------------------------------------------
adOpenForwardOnly = 0
adOpenKeyset = 1
adOpenDynamic = 2
adOpenStatic = 3

adLockReadOnly = 1
adLockPessimistic = 2
adLockOptimistic = 3
adLockBatchOptimistic = 4

adCmdText = 1
adCmdTable = 2
adCmdStoredProc = 4
adCmdUnknown = 8

# CursorLocationEnum (subset)
adUseServer = 2
adUseClient = 3

adStateOpen = 1
adStateClosed = 0

adEditNone = 0
adEditInProgress = 1
adEditAdd = 2

adRecOK = 0

adParamInput = 1
adParamOutput = 2
adParamInputOutput = 3
adParamReturnValue = 4

# DataTypeEnum (subset)
adEmpty = 0
adSmallInt = 2
adInteger = 3
adSingle = 4
adDouble = 5
adCurrency = 6
adDate = 7
adBSTR = 8
adIDispatch = 9
adError = 10
adBoolean = 11
adVariant = 12
adIUnknown = 13
adDecimal = 14
adTinyInt = 16
adUnsignedTinyInt = 17
adUnsignedSmallInt = 18
adUnsignedInt = 19
adBigInt = 20
adUnsignedBigInt = 21
adFileTime = 64
adDBDate = 133
adDBTime = 134
adDBTimeStamp = 135
adChar = 129
adVarChar = 200
adLongVarChar = 201
adWChar = 130
adVarWChar = 202
adLongVarWChar = 203
adBinary = 128
adVarBinary = 204
adLongVarBinary = 205
adChapter = 136
adNumeric = 131

# FieldAttributeEnum (subset)
adFldMayBeNull = 64
adFldKeyColumn = 0x00000002

_SQLITE_TYPE_MAP = {
    'integer': adInteger,
    'real': adDouble,
    'text': adVarWChar,
    'blob': adLongVarBinary,
    'numeric': adNumeric,
    'boolean': adBoolean,
    '': adVariant,
}

# ---------------------------------------------------------------------------
# Connection string parsing / database path resolution
# ---------------------------------------------------------------------------

from .vb_errors import raise_runtime


@dataclass
class ParsedConnectionString:
    raw: str
    attrs: dict[str, str]
    provider_kind: str
    data_source: str
    errors: list[str]


@dataclass
class ProviderCapabilities:
    can_open: bool
    uses_stdlib_only: bool
    supports_transactions: bool
    supports_positional_params: bool
    supports_named_params: bool
    supports_multiple_recordsets: bool
    supports_schema_discovery: bool
    notes: str = ""


def _split_conn_parts(s: str) -> list[str]:
    parts: list[str] = []
    buf: list[str] = []
    in_quote = False
    i = 0
    while i < len(s):
        ch = s[i]
        if ch == '"':
            in_quote = not in_quote
            buf.append(ch)
            i += 1
            continue
        if ch == ';' and not in_quote:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    tail = ''.join(buf).strip()
    if tail:
        parts.append(tail)
    return parts


def _parse_conn_attrs(conn_str: str) -> tuple[dict[str, str], str]:
    cs = conn_str.strip()
    attrs: dict[str, str] = {}
    bare = ""
    has_equals = False
    for part in _split_conn_parts(cs):
        if '=' in part:
            has_equals = True
            k, v = part.split('=', 1)
            key = str(k).strip().lower()
            val = str(v).strip()
            if len(val) >= 2 and val[0] == '"' and val[-1] == '"':
                val = val[1:-1]
            attrs[key] = val
    if not has_equals and cs:
        bare = cs
    return attrs, bare


def _pick_attr(attrs: dict[str, str], *names: str) -> str:
    for n in names:
        if n in attrs and attrs[n] != "":
            return attrs[n]
    return ""


def _classify_conn_provider(attrs: dict[str, str], bare: str) -> str:
    provider = _pick_attr(attrs, 'provider').lower()
    driver = _pick_attr(attrs, 'driver').lower()
    dsn = _pick_attr(attrs, 'dsn').strip()
    ext = _pick_attr(attrs, 'extended properties').lower()
    data_source = _pick_attr(attrs, 'data source', 'datasource', 'server', 'address', 'addr', 'network address')
    candidate = (data_source or bare).lower()

    if provider:
        if 'sqlite' in provider:
            return 'sqlite'
        if provider == 'sqloledb' or 'sqlncli' in provider or 'msoledbsql' in provider:
            return 'sqlserver'
        if provider.startswith('microsoft.jet.oledb'):
            if 'excel' in ext:
                return 'excel'
            if 'text' in ext or 'csv' in ext:
                return 'text'
            return 'access'
        if provider.startswith('microsoft.ace.oledb'):
            if 'excel' in ext:
                return 'excel'
            if 'text' in ext or 'csv' in ext:
                return 'text'
            return 'access'
        if 'oraoledb.oracle' in provider:
            return 'oracle'
        if 'mysql' in provider:
            return 'mysql'
        if 'mariadb' in provider:
            return 'mariadb'
        if 'postgres' in provider or 'pgsql' in provider:
            return 'postgresql'

    if dsn:
        return 'odbc'

    if driver:
        if 'mysql' in driver:
            return 'mysql'
        if 'sql server' in driver:
            return 'sqlserver'
        if 'oracle' in driver:
            return 'oracle'
        if 'postgres' in driver:
            return 'postgresql'
        if 'sqlite' in driver:
            return 'sqlite'
        return 'odbc'

    if candidate.endswith(('.sqlite', '.sqlite3', '.db', '.db3')):
        return 'sqlite'
    if candidate.endswith(('.xls', '.xlsx', '.xlsm', '.xlsb')):
        return 'excel'
    if candidate.endswith(('.mdb', '.accdb')):
        return 'access'

    return 'unknown'


def parse_connection_string(conn_str: str) -> ParsedConnectionString:
    attrs, bare = _parse_conn_attrs(conn_str)
    provider_kind = _classify_conn_provider(attrs, bare)
    data_source = _pick_attr(
        attrs,
        'data source',
        'datasource',
        'database',
        'initial catalog',
    ) or bare
    return ParsedConnectionString(
        raw=conn_str,
        attrs=attrs,
        provider_kind=provider_kind,
        data_source=data_source,
        errors=[],
    )


def _resolve_sqlite_path(info: ParsedConnectionString, docroot: str) -> Optional[str]:
    raw = (info.data_source or '').strip()
    if not raw:
        return None
    raw = raw.replace('\\', os.sep).replace('/', os.sep)
    if not os.path.isabs(raw):
        raw = os.path.join(docroot, raw)
    return os.path.abspath(raw)


def _resolve_access_path(info: ParsedConnectionString, docroot: str) -> Optional[str]:
    raw = (info.data_source or '').strip()
    if not raw:
        return None
    raw = raw.replace('\\', os.sep).replace('/', os.sep)
    if not os.path.isabs(raw):
        raw = os.path.join(docroot, raw)
    return os.path.abspath(raw)


class _ADOProviderAdapter:
    kind = "unknown"
    capabilities = ProviderCapabilities(
        can_open=False,
        uses_stdlib_only=False,
        supports_transactions=False,
        supports_positional_params=False,
        supports_named_params=False,
        supports_multiple_recordsets=False,
        supports_schema_discovery=False,
        notes="Provider adapter scaffold only",
    )

    def get_capabilities(self) -> ProviderCapabilities:
        return self.capabilities

    def open(self, conn: 'ADOConnection', info: ParsedConnectionString):
        raise_runtime(
            'ADO_UNSPECIFIED',
            f"Connection provider not available in this ASPPY runtime: {info.provider_kind}",
        )


class _SQLiteProviderAdapter(_ADOProviderAdapter):
    kind = "sqlite"
    capabilities = ProviderCapabilities(
        can_open=True,
        uses_stdlib_only=True,
        supports_transactions=True,
        supports_positional_params=True,
        supports_named_params=False,
        supports_multiple_recordsets=True,
        supports_schema_discovery=True,
        notes="Built-in sqlite3 backend",
    )

    def open(self, conn: 'ADOConnection', info: ParsedConnectionString):
        phys = _resolve_sqlite_path(info, conn._docroot)
        if not phys:
            raise_runtime('ADO_UNSPECIFIED', "Invalid data source")
        assert phys is not None
        try:
            db = _ensure_sqlite3().connect(phys, check_same_thread=False)
            db.isolation_level = None
            db.row_factory = None
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA foreign_keys=ON")
            conn._conn = db
            conn._is_open = True
            conn.State = adStateOpen
            conn._db_path = phys
            conn._provider_kind = self.kind
            _ado_thread.last_conn = conn
            conns = _get_open_conns()
            if conn not in conns:
                conns.append(conn)
        except Exception as e:
            raise_runtime('ADO_UNSPECIFIED', f"Connection Open error: {e}")


class _UnavailableProviderAdapter(_ADOProviderAdapter):
    def __init__(self, kind: str, *, notes: str = ""):
        self.kind = kind or "unknown"
        self.capabilities = ProviderCapabilities(
            can_open=False,
            uses_stdlib_only=False,
            supports_transactions=False,
            supports_positional_params=False,
            supports_named_params=False,
            supports_multiple_recordsets=False,
            supports_schema_discovery=False,
            notes=notes or "Planned provider scaffold; adapter not implemented",
        )

    def open(self, conn: 'ADOConnection', info: ParsedConnectionString):
        raise_runtime(
            'ADO_UNSPECIFIED',
            (
                f"Connection provider not available in this ASPPY runtime: {self.kind}. "
                "Built-in support is currently SQLite, Access, Excel, and ODBC (pyodbc) only. "
                "Install an external adapter/driver path or migrate this connection string to SQLite."
            ),
        )


class _AccessProviderAdapter(_ADOProviderAdapter):
    kind = "access"
    capabilities = ProviderCapabilities(
        can_open=True,
        uses_stdlib_only=False,
        supports_transactions=True,
        supports_positional_params=True,
        supports_named_params=False,
        supports_multiple_recordsets=True,
        supports_schema_discovery=False,
        notes="Requires pyodbc + Microsoft Access ODBC driver",
    )

    def open(self, conn: 'ADOConnection', info: ParsedConnectionString):
        odb = _ensure_pyodbc()
        if odb is None:
            raise_runtime(
                'ADO_UNSPECIFIED',
                "Access provider requires pyodbc module. Install with: python -m pip install pyodbc",
            )
        assert odb is not None

        phys = _resolve_access_path(info, conn._docroot)
        if not phys:
            raise_runtime('ADO_UNSPECIFIED', "Invalid data source")
        assert phys is not None
        if not os.path.isfile(phys):
            raise_runtime('FILE_NOT_FOUND', phys)

        lower_phys = phys.lower()
        if not (lower_phys.endswith('.mdb') or lower_phys.endswith('.accdb')):
            raise_runtime('ADO_UNSPECIFIED', f"Access data source must be .mdb or .accdb: {phys}")

        driver = info.attrs.get('driver', '').strip()
        if not driver:
            driver = 'Microsoft Access Driver (*.mdb, *.accdb)'
        if not driver.startswith('{'):
            driver = '{' + driver
        if not driver.endswith('}'):
            driver = driver + '}'

        uid = _pick_attr(info.attrs, 'user id', 'uid', 'user')
        # Classic ASP writes Access database passwords as the Jet OLE DB
        # property "Jet OLEDB:Database Password". The Access ODBC driver
        # expects it as PWD=. Prefer the Jet-specific attribute, then the
        # generic Password/Pwd forms.
        pwd = _pick_attr(info.attrs, 'jet oledb:database password', 'password', 'pwd')
        parts = [f"Driver={driver}", f"DBQ={phys}"]
        if uid:
            parts.append(f"Uid={uid}")
        if pwd:
            parts.append(f"Pwd={pwd}")
        odbc_cs = ';'.join(parts) + ';'

        try:
            db = odb.connect(odbc_cs, autocommit=True)
            conn._conn = db
            conn._is_open = True
            conn.State = adStateOpen
            conn._db_path = phys
            conn._provider_kind = self.kind
            _ado_thread.last_conn = conn
            conns = _get_open_conns()
            if conn not in conns:
                conns.append(conn)
        except Exception as e:
            raise_runtime('ADO_UNSPECIFIED', f"Connection Open error: {e}")


class _ExcelProviderAdapter(_ADOProviderAdapter):
    kind = "excel"
    capabilities = ProviderCapabilities(
        can_open=True,
        uses_stdlib_only=False,
        supports_transactions=False,
        supports_positional_params=True,
        supports_named_params=False,
        supports_multiple_recordsets=True,
        supports_schema_discovery=False,
        notes="Read-only adapter via pyodbc + Microsoft Excel ODBC driver",
    )

    def open(self, conn: 'ADOConnection', info: ParsedConnectionString):
        odb = _ensure_pyodbc()
        if odb is None:
            raise_runtime(
                'ADO_UNSPECIFIED',
                "Excel provider requires pyodbc module. Install with: python -m pip install pyodbc",
            )
        assert odb is not None

        phys = _resolve_access_path(info, conn._docroot)
        if not phys:
            raise_runtime('ADO_UNSPECIFIED', "Invalid data source")
        assert phys is not None
        if not os.path.isfile(phys):
            raise_runtime('FILE_NOT_FOUND', phys)

        lower_phys = phys.lower()
        if not lower_phys.endswith(('.xls', '.xlsx', '.xlsm', '.xlsb')):
            raise_runtime('ADO_UNSPECIFIED', f"Excel data source must be .xls, .xlsx, .xlsm, or .xlsb: {phys}")

        driver = info.attrs.get('driver', '').strip()
        if not driver:
            driver = 'Microsoft Excel Driver (*.xls, *.xlsx, *.xlsm, *.xlsb)'
        if not driver.startswith('{'):
            driver = '{' + driver
        if not driver.endswith('}'):
            driver = driver + '}'

        ext_props = _pick_attr(info.attrs, 'extended properties')
        parts = [f"Driver={driver}", f"DBQ={phys}", "ReadOnly=1"]
        if ext_props:
            parts.append(f'Extended Properties="{ext_props}"')
        odbc_cs = ';'.join(parts) + ';'

        try:
            db = odb.connect(odbc_cs, autocommit=True)
            conn._conn = db
            conn._is_open = True
            conn.State = adStateOpen
            conn._db_path = phys
            conn._provider_kind = self.kind
            _ado_thread.last_conn = conn
            conns = _get_open_conns()
            if conn not in conns:
                conns.append(conn)
        except Exception as e:
            raise_runtime('ADO_UNSPECIFIED', f"Connection Open error: {e}")


class _ODBCProviderAdapter(_ADOProviderAdapter):
    kind = "odbc"
    capabilities = ProviderCapabilities(
        can_open=True,
        uses_stdlib_only=False,
        supports_transactions=True,
        supports_positional_params=True,
        supports_named_params=False,
        supports_multiple_recordsets=True,
        supports_schema_discovery=False,
        notes="Generic ODBC adapter via pyodbc (DSN or Driver connection strings)",
    )

    def _pick_installed_driver(self, odb, preferred: list[str]) -> str:
        try:
            drivers = [str(d) for d in odb.drivers()]
        except Exception:
            drivers = []
        if not drivers:
            return ""

        pref_lower = [p.lower() for p in preferred]
        for i, p in enumerate(pref_lower):
            for d in drivers:
                dl = d.lower()
                if dl == p:
                    return d
                if p in dl:
                    return d
        return ""

    def _build_postgresql_odbc_attrs(self, odb, attrs: dict[str, str]) -> dict[str, str]:
        out = dict(attrs)
        if not _pick_attr(out, 'driver'):
            drv = self._pick_installed_driver(
                odb,
                [
                    'PostgreSQL Unicode(x64)',
                    'PostgreSQL Unicode',
                    'PostgreSQL ANSI(x64)',
                    'PostgreSQL ANSI',
                ],
            )
            if not drv:
                raise_runtime(
                    'ADO_UNSPECIFIED',
                    (
                        "No suitable PostgreSQL ODBC driver found. "
                        "Install psqlODBC (Unicode/ANSI), or provide Driver={...} in the connection string."
                    ),
                )
            out['driver'] = drv

        # Normalize common ADO aliases to ODBC-friendly names.
        if 'database' not in out and 'initial catalog' in out:
            out['database'] = out['initial catalog']
        if 'uid' not in out:
            u = _pick_attr(out, 'user id', 'user')
            if u:
                out['uid'] = u
        if 'pwd' not in out:
            p = _pick_attr(out, 'password')
            if p:
                out['pwd'] = p
        if 'server' not in out:
            s = _pick_attr(out, 'data source', 'datasource')
            if s:
                out['server'] = s

        if not _pick_attr(out, 'dsn') and not _pick_attr(out, 'server'):
            raise_runtime(
                'ADO_UNSPECIFIED',
                "PostgreSQL ODBC connection requires Server=... (or DSN=...)",
            )
        return out

    def open(self, conn: 'ADOConnection', info: ParsedConnectionString):
        odb = _ensure_pyodbc()
        if odb is None:
            raise_runtime(
                'ADO_UNSPECIFIED',
                "ODBC provider requires pyodbc module. Install with: python -m pip install pyodbc",
            )
        assert odb is not None

        attrs = dict(info.attrs)
        if (info.provider_kind or '').lower() == 'postgresql':
            attrs = self._build_postgresql_odbc_attrs(odb, attrs)

        has_dsn = bool(_pick_attr(attrs, 'dsn'))
        has_driver = bool(_pick_attr(attrs, 'driver'))
        if not has_dsn and not has_driver:
            raise_runtime(
                'ADO_UNSPECIFIED',
                "ODBC connection string must include DSN=... or Driver={...}",
            )

        parts: list[str] = []
        for k, v in attrs.items():
            lk = str(k).strip().lower()
            if lk in ('provider',):
                continue
            key_out = k
            if lk == 'data source':
                key_out = 'Server'
            elif lk == 'user id':
                key_out = 'Uid'
            elif lk == 'password':
                key_out = 'Pwd'
            elif lk == 'initial catalog':
                key_out = 'Database'
            elif lk == 'driver':
                drv = str(v).strip()
                if drv and not drv.startswith('{'):
                    drv = '{' + drv
                if drv and not drv.endswith('}'):
                    drv = drv + '}'
                v = drv
            parts.append(f"{key_out}={v}")
        odbc_cs = ';'.join(parts)
        if odbc_cs and not odbc_cs.endswith(';'):
            odbc_cs += ';'

        try:
            db = odb.connect(odbc_cs, autocommit=True)
            conn._conn = db
            conn._is_open = True
            conn.State = adStateOpen
            conn._db_path = ''
            logical_kind = (info.provider_kind or '').strip().lower()
            conn._provider_kind = logical_kind if logical_kind and logical_kind != 'unknown' else self.kind
            _ado_thread.last_conn = conn
            conns = _get_open_conns()
            if conn not in conns:
                conns.append(conn)
        except Exception as e:
            raise_runtime('ADO_UNSPECIFIED', f"Connection Open error: {e}")


_PROVIDER_ADAPTERS: dict[str, _ADOProviderAdapter] = {
    'sqlite': _SQLiteProviderAdapter(),
    'access': _AccessProviderAdapter(),
    'excel': _ExcelProviderAdapter(),
    'odbc': _ODBCProviderAdapter(),
    'postgresql': _ODBCProviderAdapter(),
    'sqlserver': _UnavailableProviderAdapter('sqlserver', notes='Planned adapter contract; likely via ODBC or native SQL Server driver'),
    'mysql': _UnavailableProviderAdapter('mysql', notes='Planned adapter contract; likely via ODBC or native MySQL driver'),
    'mariadb': _UnavailableProviderAdapter('mariadb', notes='Planned adapter contract; likely via ODBC or native MariaDB driver'),
    'oracle': _UnavailableProviderAdapter('oracle', notes='Planned adapter contract; typically requires external Oracle client/driver'),
    'mongodb': _UnavailableProviderAdapter('mongodb', notes='Planned adapter contract; document model may need non-tabular ADO mapping'),
    'text': _UnavailableProviderAdapter('text', notes='Planned adapter contract; CSV/text folder provider semantics'),
}


def register_provider_adapter(kind: str, adapter: _ADOProviderAdapter):
    k = str(kind or '').strip().lower()
    if not k:
        raise ValueError("Provider kind is required")
    _PROVIDER_ADAPTERS[k] = adapter


def _get_provider_adapter(kind: str) -> _ADOProviderAdapter:
    k = str(kind or '').strip().lower()
    if k in _PROVIDER_ADAPTERS:
        return _PROVIDER_ADAPTERS[k]
    return _UnavailableProviderAdapter(k or 'unknown')


def _should_route_to_odbc(info: ParsedConnectionString) -> bool:
    kind = (info.provider_kind or '').lower()
    attrs = info.attrs
    if kind == 'postgresql':
        return True
    has_odbc_marker = ('dsn' in attrs) or ('driver' in attrs)
    if not has_odbc_marker:
        return False
    if kind in ('sqlite', 'access', 'excel'):
        return False
    return kind in ('odbc', 'sqlserver', 'mysql', 'mariadb', 'postgresql', 'oracle', 'unknown')


def list_provider_adapters() -> list[str]:
    return sorted(_PROVIDER_ADAPTERS.keys())


def get_provider_capabilities(kind: str) -> ProviderCapabilities:
    adapter = _get_provider_adapter(kind)
    return adapter.get_capabilities()


def _conn_or_raise(conn: 'ADOConnection | None') -> Any:
    if conn is None:
        raise_runtime('ADO_OBJECT_CLOSED')
    assert conn is not None
    db = conn._conn
    if db is None:
        raise_runtime('ADO_OBJECT_CLOSED')
    assert db is not None
    return db


def _normalize_param(v: Any) -> Any:
    # Use module-level sentinel checks (identity) rather than re-importing per call.
    if v is VBEmpty or v is VBNull or v is VBNothing or v is None:
        return None
    if isinstance(v, bool):
        return bool(v)
    return v


# ---------------------------------------------------------------------------
# Row / Field objects
# ---------------------------------------------------------------------------

class ADOField:
    """Represents one column in a Recordset row."""

    def __init__(self, name: str, value: Any, col_type: int = adVariant,
                 defined_size: int = 0, owner: 'ADORecordset | None' = None):
        self.Name = name
        self._value = value
        self.Type = col_type
        self.DefinedSize = defined_size
        self.ActualSize = len(str(value)) if value is not None else 0
        self.NumericScale = 0
        self.Precision = 0
        self._pending = value  # for AddNew/Update
        self._row = None  # type: Any
        self._col_idx = None  # type: Any
        self._owner = owner

    @property
    def Value(self):
        # If this field is bound to a recordset row, always reflect current row value.
        if self._row is not None and self._col_idx is not None:
            try:
                v = _coerce_value(self._row[self._col_idx])
                return _coerce_field_value(self, v)
            except Exception:
                v = _coerce_value(self._value)
                return _coerce_field_value(self, v)
        v = _coerce_value(self._value)
        return _coerce_field_value(self, v)

    @Value.setter
    def Value(self, v):
        if self._owner is not None:
            try:
                self._owner.__vbs_index_set__(self.Name, v)
                return
            except Exception:
                pass
        self._value = v
        self._pending = v

    def AppendChunk(self, data):
        if data is None:
            return
        if data is VBNull:
            return
        if isinstance(data, (bytes, bytearray)):
            chunk = bytes(data)
        else:
            chunk = vbs_cstr(data).encode('latin-1', errors='replace')

        cur = self.Value
        if cur is VBNull or cur is None:
            new_val = chunk
        elif isinstance(cur, (bytes, bytearray)):
            new_val = bytes(cur) + chunk
        else:
            cur_b = vbs_cstr(cur).encode('latin-1', errors='replace')
            new_val = cur_b + chunk

        if self._owner is not None:
            try:
                self._owner.__vbs_index_set__(self.Name, new_val)
                return
            except Exception:
                pass
        self._value = new_val
        self._pending = new_val

    def __str__(self):
        return vbs_cstr(self.Value)


def _coerce_value(v: Any) -> Any:
    """Return Python value in VBScript-friendly form."""
    if v is None:
        return VBNull
    if isinstance(v, (int, float, bool, str)):
        return v
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v
    return v


def _is_bool_field_name(name: str) -> bool:
    n = str(name or "").lower()
    if not n:
        return False
    if n.startswith("b") and len(n) > 1:
        return True
    if n.startswith("is") or n.startswith("has"):
        return True
    if n.endswith("flag"):
        return True
    return False


def _coerce_field_value(field: ADOField, v: Any) -> Any:
    if v is VBNull:
        return VBNull
    if field.Type == adBoolean:
        return vbs_cbool(v)
    return v


class ADOFields:
    """Collection of ADOField objects for a Recordset row."""

    def __init__(self, fields: list[ADOField], owner: 'ADORecordset | None' = None):
        self._fields = fields
        self._owner = owner
        # Keys are stored lowercased for case-insensitive lookup.
        self._name_map: dict[str, int] = {}
        for i, f in enumerate(fields):
            self._name_map[f.Name.lower()] = i

    @property
    def Count(self) -> int:
        return len(self._fields)

    def Item(self, key) -> ADOField:
        if isinstance(key, int) or (isinstance(key, float) and key == int(key)):
            idx = int(key)
            if idx < 0 or idx >= len(self._fields):
                raise_runtime('ADO_ARGS_WRONG_TYPE', f"Index {idx} out of range")
            return self._fields[idx]
        k = vbs_cstr(key).lower()
        if k not in self._name_map:
            raise_runtime('ADO_ARGS_WRONG_TYPE', f"Unknown field: {key}")
        return self._fields[self._name_map[k]]

    def Append(self, name, field_type=None, defined_size=0, attr=None, field_value=None):
        nm = vbs_cstr(name)
        if not nm:
            raise_runtime('INVALID_PROC_CALL', "Fields.Append: name required")
        k = nm.lower()
        if k in self._name_map:
            raise_runtime('INVALID_PROC_CALL', f"Fields.Append: duplicate field '{nm}'")
        if field_type is None:
            field_type = adVariant
        try:
            field_type = int(field_type)
        except Exception:
            pass
        try:
            defined_size = int(defined_size) if defined_size is not None else 0
        except Exception:
            defined_size = 0

        f = ADOField(nm, field_value, field_type, defined_size=defined_size, owner=self._owner)
        f._col_idx = len(self._fields)
        self._fields.append(f)
        self._name_map[k] = len(self._fields) - 1

        if self._owner is not None:
            owner = self._owner
            owner._col_names.append(nm)
            owner._col_names_lower.append(k)
            owner._col_types.append(field_type)
            if owner._is_addnew:
                owner._addnew_row[nm] = field_value
            if owner._rows:
                new_rows = []
                for row in owner._rows:
                    row_list = list(row)
                    row_list.append(field_value if field_value is not None else None)
                    new_rows.append(tuple(row_list))
                owner._rows = new_rows
            if owner._base_rows is not None:
                new_base = []
                for row in owner._base_rows:
                    row_list = list(row)
                    row_list.append(field_value if field_value is not None else None)
                    new_base.append(tuple(row_list))
                owner._base_rows = new_base
            owner._invalidate_fields_cache()

    def __vbs_index_get__(self, key) -> Any:
        # Return the Field object (default property is Value in VBScript).
        return self.Item(key)

    def __vbs_index_set__(self, key, value):
        f = self.Item(key)
        f.Value = value

    def __iter__(self):
        return iter(self._fields)


# ---------------------------------------------------------------------------
# Recordset
# ---------------------------------------------------------------------------

class ADORecordset:
    """Classic ADO Recordset shim backed by SQLite."""

    def __init__(self, conn: 'ADOConnection | None' = None):
        self._conn: Optional[ADOConnection] = conn
        self.ActiveConnection: Optional[ADOConnection] = conn
        self.CursorType: int = adOpenForwardOnly
        self.LockType: int = adLockReadOnly
        self.CursorLocation: int = 3  # adUseClient
        self.CacheSize: int = 100
        self.MaxRecords: int = 0
        self.PageSize: int = 10
        self.Source: str = ""
        self.State: int = adStateClosed
        self._status: int = adRecOK
        self._edit_mode: int = adEditNone
        self._filter: str = ""
        self._sort: str = ""
        self._base_rows: Optional[list[tuple]] = None
        self._next_recordsets: list['ADORecordset'] = []
        self._batch_updates: dict[int, dict[str, Any]] = {}

        self._rows: list[tuple] = []
        self._col_names: list[str] = []
        self._col_names_lower: list[str] = []  # cached lowercase version of _col_names
        self._col_types: list[int] = []
        self._cur_idx: int = 0
        self._is_open: bool = False
        self._is_addnew: bool = False
        self._addnew_row: dict[str, Any] = {}
        self._table_name: str = ""
        self._original_sql: str = ""

        # For update support we track original row pk
        self._pk_col: Optional[str] = None
        self._pk_val: Any = None
        self._fields_cache = None
        self._fields_cache_row = None
        self._fields_cache_addnew = False
        self._fields_static = None

    def _set_col_names(self, names: list[str], types: list[int]):
        """Set column names and types, keeping the lowercase cache in sync."""
        self._col_names = names
        self._col_names_lower = [n.lower() for n in names]
        self._col_types = types

    # --- Navigation ---

    @property
    def EOF(self) -> bool:
        if not self._is_open:
            return True
        return self._cur_idx >= len(self._rows)

    @property
    def BOF(self) -> bool:
        if not self._is_open:
            return True
        return self._cur_idx < 0

    @property
    def RecordCount(self) -> int:
        if not self._is_open:
            return -1
        return len(self._rows)

    @property
    def PageCount(self) -> int:
        if not self._is_open or self.PageSize <= 0:
            return 0
        return (self.RecordCount + self.PageSize - 1) // self.PageSize

    @property
    def AbsolutePosition(self) -> int:
        if not self._is_open or self.EOF:
            return -1
        return self._cur_idx + 1

    @AbsolutePosition.setter
    def AbsolutePosition(self, value):
        if not self._is_open:
            return
        try:
            pos = int(value)
        except Exception:
            return
        if pos <= 0:
            self._cur_idx = 0
        else:
            self._cur_idx = pos - 1
        self._invalidate_fields_cache()

    @property
    def Status(self) -> int:
        return self._status

    @property
    def EditMode(self) -> int:
        return self._edit_mode

    @property
    def Sort(self) -> str:
        return self._sort

    @Sort.setter
    def Sort(self, value):
        self._sort = vbs_cstr(value) if value is not None else ""
        self._refresh_view()

    @property
    def Filter(self) -> str:
        return self._filter

    @Filter.setter
    def Filter(self, value):
        self._filter = vbs_cstr(value) if value is not None else ""
        self._refresh_view()

    def MoveNext(self):
        if self._is_open:
            self._cur_idx += 1
        self._bind_fields_row()

    def MovePrevious(self):
        if self._is_open:
            self._cur_idx = max(-1, self._cur_idx - 1)
        self._bind_fields_row()

    def MoveFirst(self):
        if self._is_open:
            self._cur_idx = 0 if self._rows else 0
        self._bind_fields_row()

    def MoveLast(self):
        if self._is_open:
            self._cur_idx = max(0, len(self._rows) - 1)
        self._bind_fields_row()

    def Move(self, n, start=None):
        if self._is_open:
            if start is not None:
                self._cur_idx = int(start) - 1
            self._cur_idx += int(n)
        self._bind_fields_row()

    # --- Fields ---

    @property
    def Fields(self) -> ADOFields:
        if self._fields_cache is not None and not self._fields_cache_addnew and not self._is_addnew:
            self._bind_fields_row()
            return self._fields_cache

        if self._is_addnew:
            fields = []
            for i, name in enumerate(self._col_names):
                val = self._addnew_row.get(name)
                f = ADOField(name, val, self._col_types[i] if i < len(self._col_types) else adVariant, owner=self)
                fields.append(f)
            self._fields_cache = ADOFields(fields, owner=self)
            self._fields_cache_row = self._cur_idx
            self._fields_cache_addnew = True
            return self._fields_cache

        if not self._is_open or self.EOF or self._cur_idx >= len(self._rows):
            # Return empty Fields for empty/closed RS
            self._fields_cache = ADOFields([ADOField(n, None, t, owner=self)
                              for n, t in zip(self._col_names, self._col_types)], owner=self)
            self._fields_cache_row = self._cur_idx
            self._fields_cache_addnew = False
            return self._fields_cache

        # Build static fields once (column structure only) and bind to current row.
        if self._fields_static is None:
            fields = []
            for i, name in enumerate(self._col_names):
                ct = self._col_types[i] if i < len(self._col_types) else adVariant
                f = ADOField(name, None, ct, owner=self)
                f._col_idx = i
                fields.append(f)
            self._fields_static = ADOFields(fields, owner=self)
        self._fields_cache = self._fields_static
        self._fields_cache_addnew = False
        self._bind_fields_row()
        self._fields_cache_row = self._cur_idx
        return self._fields_cache

    def __vbs_index_get__(self, key) -> Any:
        f = self.Fields.Item(key)
        return f.Value

    def __vbs_index_set__(self, key, value):
        """rs("field") = value  — sets the field on the current row."""
        if self._is_addnew:
            self._edit_mode = adEditAdd
            col = vbs_cstr(key)
            col_lower = col.lower()
            for name, name_lower in zip(self._col_names, self._col_names_lower):
                if name_lower == col_lower:
                    self._addnew_row[name] = value
                    return
            self._addnew_row[col] = value
        else:
            # Update-in-place on current row (pending until .Update())
            col = vbs_cstr(key)
            col_lower = col.lower()
            if self.LockType == adLockBatchOptimistic:
                updates = self._batch_updates.setdefault(self._cur_idx, {})
                for name, name_lower in zip(self._col_names, self._col_names_lower):
                    if name_lower == col_lower:
                        updates[name] = value
                        break
                else:
                    updates[col] = value
            else:
                if not hasattr(self, '_pending_updates'):
                    self._pending_updates: dict[str, Any] = {}
                for name, name_lower in zip(self._col_names, self._col_names_lower):
                    if name_lower == col_lower:
                        self._pending_updates[name] = value
                        break
                else:
                    self._pending_updates[col] = value
            self._edit_mode = adEditInProgress
            if self._fields_cache is not None:
                try:
                    f = self._fields_cache.Item(col)
                    f._value = value
                except Exception:
                    pass

    # --- Open / Close ---

    def Open(self, source=None, active_connection=None, cursor_type=None,
             lock_type=None, options=None):
        if source is not None:
            self.Source = vbs_cstr(source)
        if active_connection is not None:
            self.ActiveConnection = active_connection
        if cursor_type is not None:
            self.CursorType = int(cursor_type)
        if lock_type is not None:
            self.LockType = int(lock_type)

        sql = self.Source
        if sql is None:
            sql = ""
        if isinstance(sql, str) and sql.strip() == "":
            # Disconnected/in-memory recordset (fields may be appended before Open).
            self._original_sql = sql
            if self._rows is None:
                self._rows = []
            self._base_rows = list(self._rows)
            self._cur_idx = 0
            self._is_open = True
            self.State = adStateOpen
            self._invalidate_fields_cache()
            return

        conn = self.ActiveConnection
        if conn is VBEmpty or conn is VBNothing:
            conn = None
        if conn is None:
            # Fallback: use last opened connection in this thread.
            conn = getattr(_ado_thread, 'last_conn', None)
            if conn is None:
                raise_runtime('ADO_OBJECT_CLOSED', "No ActiveConnection")
        assert conn is not None
        if isinstance(conn, str):
            # Connection string passed directly
            conn_str = conn
            conn = ADOConnection()
            conn.Open(conn_str)
            self.ActiveConnection = conn

        if not conn._is_open:
            conn.Open()

        self._original_sql = self.Source
        self._execute(conn, sql)
        self._invalidate_fields_cache()

    def _execute(self, conn: 'ADOConnection', sql: str):
        try:
            db = _conn_or_raise(conn)
            cursor = db.cursor()
            cursor.execute(sql)
            desc = cursor.description or []
            self._set_col_names(
                [d[0] for d in desc],
                [_column_type_to_ado(d[1]) for d in desc],
            )
            self._rows = cursor.fetchall()
            self._base_rows = list(self._rows)
            self._cur_idx = 0
            self._is_open = True
            self.State = adStateOpen
            # Detect primary key for updates
            self._detect_pk(conn, sql)
        except Exception as e:
            src = self._original_sql
            raise_runtime('ADO_UNSPECIFIED', f"Open error: {e}\nSQL: {sql}\nOriginalSQL: {src}")

    def _detect_pk(self, conn: 'ADOConnection', sql: str):
        """Try to detect which table and pk column this RS is based on."""
        m = re.search(r'(?i)\bFROM\s+\[?(\w+)\]?', sql)
        if not m:
            return
        table = m.group(1)
        self._table_name = table
        try:
            db = _conn_or_raise(conn)
            cur = db.cursor()
            cur.execute(f"PRAGMA table_info([{table}])")
            for row in cur.fetchall():
                # row: (cid, name, type, notnull, dflt_value, pk)
                if row[5] == 1:  # pk flag
                    self._pk_col = row[1]
                    break
        except Exception:
            pass
        if not self._pk_col:
            # Fallback: common PK naming conventions.
            if 'iid' in self._col_names_lower:
                self._pk_col = self._col_names[self._col_names_lower.index('iid')]
            elif 'id' in self._col_names_lower:
                self._pk_col = self._col_names[self._col_names_lower.index('id')]

    def Close(self):
        self._is_open = False
        self.State = adStateClosed
        self._rows = []
        self._base_rows = []
        self._invalidate_schema_cache()

    def Requery(self):
        conn = self.ActiveConnection
        if conn and self._original_sql:
            sql = self._original_sql
            self._execute(conn, sql)
            self._refresh_view()
            self._invalidate_fields_cache()

    # --- AddNew / Update / Delete ---

    def _quote_ident(self, name: str) -> str:
        n = str(name)
        kind = ''
        try:
            kind = str(getattr(self.ActiveConnection, '_provider_kind', '') or '').lower()
        except Exception:
            kind = ''

        if kind in ('sqlite', 'access', 'sqlserver', 'excel'):
            return f'[{n}]'

        # For ODBC-backed engines (postgres/mysql/oracle/generic), keep simple
        # identifiers unquoted for cross-engine compatibility.
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', n):
            return n
        return '"' + n.replace('"', '""') + '"'

    def AddNew(self):
        self._is_addnew = True
        self._addnew_row = {name: None for name in self._col_names}
        self._edit_mode = adEditAdd
        self._invalidate_fields_cache()

    def Update(self):
        conn = self.ActiveConnection
        if conn is None or not getattr(conn, '_is_open', False):
            # Disconnected/in-memory recordset: finalize row locally.
            if self._is_addnew:
                row = self._addnew_row
                new_row = tuple(row.get(c) for c in self._col_names)
                if self._rows is None:
                    self._rows = []
                self._rows.append(new_row)
                self._base_rows = list(self._rows)
                self._cur_idx = len(self._rows) - 1 if self._rows else 0
                self._is_open = True
                self.State = adStateOpen
                self._is_addnew = False
                self._edit_mode = adEditNone
                self._addnew_row = {}
                self._invalidate_fields_cache()
                return
            # If not adding, just apply pending updates to current row in memory.
            if getattr(self, '_pending_updates', None) and self._rows:
                row = list(self._rows[self._cur_idx])
                for i, name in enumerate(self._col_names):
                    if name in self._pending_updates:
                        row[i] = self._pending_updates[name]
                self._rows[self._cur_idx] = tuple(row)
                self._base_rows = list(self._rows)
                self._pending_updates = {}
                self._edit_mode = adEditNone
                self._invalidate_fields_cache()
                return
            raise_runtime('ADO_OBJECT_CLOSED', "Update: no connection")
        db = _conn_or_raise(conn)
        cur = db.cursor()

        if self._is_addnew:
            # INSERT
            row = self._addnew_row
            # Filter out pk column if it's auto-increment (let SQLite assign)
            cols = [c for c in self._col_names
                    if not (c == self._pk_col and row.get(c) is None)]
            vals = [_normalize_param(row.get(c)) for c in cols]
            if not cols:
                raise_runtime('ADO_ARGS_WRONG_TYPE', "AddNew: no columns to insert")
            ph = ','.join(['?' for _ in cols])
            qcols = ','.join([self._quote_ident(c) for c in cols])
            qtable = self._quote_ident(self._table_name) if self._table_name else ''
            try:
                cur.execute(f"INSERT INTO {qtable} ({qcols}) VALUES ({ph})", vals)
                db.commit()
                last_id = getattr(cur, 'lastrowid', None)
                # Refresh row with new pk
                if self._pk_col and last_id is not None:
                    qpk = self._quote_ident(self._pk_col)
                    cur.execute(f"SELECT * FROM {qtable} WHERE {qpk}=?", (last_id,))
                    row_data = cur.fetchone()
                    if row_data:
                        self._rows = [row_data]
                        self._cur_idx = 0
                        if self._pk_col and self._pk_col in self._col_names_lower:
                            pk_idx = self._col_names_lower.index(self._pk_col.lower())
                            self._addnew_row[self._pk_col] = row_data[pk_idx]
            except Exception as e:
                db.rollback()
                raise_runtime('ADO_UNSPECIFIED', f"Update error (AddNew): {e}")
            finally:
                self._is_addnew = False
                self._addnew_row = {}
                self._edit_mode = adEditNone
                self._invalidate_fields_cache()
        else:
            # UPDATE current row
            pending = getattr(self, '_pending_updates', {})
            if not pending:
                return
            if not self._table_name:
                raise_runtime('ADO_OBJECT_CLOSED', "Update: cannot determine table")

            db = _conn_or_raise(conn)
            cur = db.cursor()

            # Prepare SET clause
            sets = ', '.join([f'{self._quote_ident(c)}=?' for c in pending.keys()])
            set_vals = [_normalize_param(v) for v in pending.values()]
            qtable = self._quote_ident(self._table_name)

            try:
                if self._pk_col:
                    # PK-based update
                    pk_idx = self._col_names_lower.index(self._pk_col.lower())
                    pk_val = self._rows[self._cur_idx][pk_idx]
                    qpk = self._quote_ident(self._pk_col)
                    cur.execute(f"UPDATE {qtable} SET {sets} WHERE {qpk}=?", set_vals + [_normalize_param(pk_val)])
                else:
                    # Fallback: Optimistic update using all columns in WHERE clause
                    where_parts = []
                    where_vals = []
                    original_row = self._rows[self._cur_idx]
                    for i, col_name in enumerate(self._col_names):
                        val = original_row[i]
                        if val is None:
                            where_parts.append(f"{self._quote_ident(col_name)} IS NULL")
                        else:
                            where_parts.append(f"{self._quote_ident(col_name)}=?")
                            where_vals.append(_normalize_param(val))

                    where_clause = " AND ".join(where_parts)
                    cur.execute(f"UPDATE {qtable} SET {sets} WHERE {where_clause}", set_vals + where_vals)

                    if cur.rowcount == 0:
                        # Row changed or deleted?
                        pass

                db.commit()

                # Update memory row directly since we can't reliably re-fetch without PK
                row_list = list(self._rows[self._cur_idx])
                for col, val in pending.items():
                    try:
                        idx = self._col_names_lower.index(col.lower())
                        row_list[idx] = val
                    except ValueError:
                        pass

                self._rows[self._cur_idx] = tuple(row_list)

            except Exception as e:
                db.rollback()
                raise_runtime('ADO_UNSPECIFIED', f"Update error: {e}")
            finally:
                self._pending_updates = {}
                self._edit_mode = adEditNone
                self._invalidate_fields_cache()

    def CancelUpdate(self):
        self._is_addnew = False
        self._addnew_row = {}
        if hasattr(self, '_pending_updates'):
            self._pending_updates = {}
        self._edit_mode = adEditNone
        self._invalidate_fields_cache()

    def Delete(self, affect_records=1):
        conn = self.ActiveConnection
        if conn is None or not conn._is_open:
            raise_runtime('ADO_OBJECT_CLOSED', "Delete: no connection")
        if not self._table_name or not self._pk_col:
            raise_runtime('ADO_OBJECT_CLOSED', "Delete: cannot determine table/pk")
        assert self._pk_col is not None
        pk_idx = self._col_names_lower.index(self._pk_col.lower())
        pk_val = self._rows[self._cur_idx][pk_idx]
        db = _conn_or_raise(conn)
        cur = db.cursor()
        try:
            qtable = self._quote_ident(self._table_name)
            qpk = self._quote_ident(self._pk_col)
            cur.execute(f"DELETE FROM {qtable} WHERE {qpk}=?", (pk_val,))
            db.commit()
            rows = list(self._rows)
            rows.pop(self._cur_idx)
            self._rows = rows
            if self._base_rows is not None:
                base = list(self._base_rows)
                base.pop(self._cur_idx)
                self._base_rows = base
            if self._cur_idx >= len(self._rows):
                self._cur_idx = len(self._rows)
            self._invalidate_fields_cache()
        except Exception as e:
            db.rollback()
            raise_runtime('ADO_UNSPECIFIED', f"Delete error: {e}")

    # --- GetRows ---

    def GetRows(self, rows=-1, start=None, fields=None):
        """Return a VBArray in ADO GetRows shape: (field, record)."""
        from .vm.values import VBArray

        # Determine starting row
        if start is None or start == "":
            i = self._cur_idx
        else:
            try:
                i = int(start)
            except Exception:
                i = self._cur_idx

        # Determine which fields to return
        if fields is None or fields == "":
            col_indices = list(range(len(self._col_names)))
        else:
            flist = [fields] if isinstance(fields, (str, int)) else list(fields)
            col_indices = []
            for f in flist:
                if isinstance(f, int) or (isinstance(f, float) and f == int(f)):
                    col_indices.append(int(f))
                else:
                    name = vbs_cstr(f)
                    try:
                        col_indices.append(self._col_names.index(name))
                    except ValueError:
                        raise_runtime('ADO_ARGS_WRONG_TYPE', f"Field not found: {name}")

        # Determine row indices
        row_indices = []
        count = 0
        while i < len(self._rows):
            if rows >= 0 and count >= rows:
                break
            row_indices.append(i)
            i += 1
            count += 1

        self._cur_idx = i
        self._invalidate_fields_cache()

        # Empty result => empty VBArray
        if not row_indices or not col_indices:
            return VBArray(-1)

        field_count = len(col_indices)
        row_count = len(row_indices)
        arr = VBArray([field_count - 1, row_count - 1])
        # Fill column-major: flat index = fi + ri * field_count
        items = arr._items
        for ri, row_idx in enumerate(row_indices):
            row = self._rows[row_idx]
            base = ri * field_count
            for fi, col_idx in enumerate(col_indices):
                items[base + fi] = _coerce_value(row[col_idx] if col_idx < len(row) else None)
        return arr

    # --- Find / Filter / Sort ---

    def Find(self, criteria, skip=0, search_direction=1, start=None):
        if not self._is_open:
            return
        if start is not None and start != "":
            try:
                self._cur_idx = int(start)
            except Exception:
                pass
        if skip:
            self._cur_idx += int(skip)
        matcher = _criteria_matcher(criteria, self._col_names, "Find")
        idx = self._cur_idx
        while idx < len(self._rows):
            if matcher(self._rows[idx]):
                self._cur_idx = idx
                self._bind_fields_row()
                return
            idx += 1
        self._cur_idx = len(self._rows)
        self._bind_fields_row()

    def Supports(self, options):
        return True

    def UpdateBatch(self, affect_records=0):
        if not self._batch_updates:
            return
        original_idx = self._cur_idx
        for row_idx, updates in list(self._batch_updates.items()):
            self._cur_idx = row_idx
            self._pending_updates = dict(updates)
            self.Update()
        self._batch_updates = {}
        self._cur_idx = original_idx

    def CancelBatch(self, affect_records=0):
        self._batch_updates = {}
        self.Requery()

    def Resync(self, affect_records=0, resync_values=0):
        self.Requery()

    def Save(self, destination, persist_format=0):
        path = vbs_cstr(destination)
        if not path:
            return
        try:
            import csv
            with open(path, 'w', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                if self._col_names:
                    w.writerow(self._col_names)
                for row in self._rows:
                    w.writerow([v for v in row])
        except Exception as e:
            raise Exception(f"ADODB.Recordset.Save: {e}") from e

    def Clone(self, lock_type=None):
        rs = ADORecordset(self.ActiveConnection)
        rs.CursorType = self.CursorType
        rs.LockType = self.LockType if lock_type is None else int(lock_type)
        rs.CursorLocation = self.CursorLocation
        rs.PageSize = self.PageSize
        rs.Source = self.Source
        rs._col_names = list(self._col_names)
        rs._col_names_lower = list(self._col_names_lower)
        rs._col_types = list(self._col_types)
        rs._rows = list(self._rows)
        rs._base_rows = list(self._base_rows) if self._base_rows is not None else list(self._rows)
        rs._cur_idx = self._cur_idx
        rs._is_open = self._is_open
        rs.State = self.State
        rs._table_name = self._table_name
        rs._pk_col = self._pk_col
        rs._filter = self._filter
        rs._sort = self._sort
        return rs

    def NextRecordset(self, records_affected=None):
        if self._next_recordsets:
            return self._next_recordsets.pop(0)
        return VBNothing

    def _invalidate_fields_cache(self):
        """Invalidate the row-level fields cache only. Does not reset column structure."""
        self._fields_cache = None
        self._fields_cache_row = None
        self._fields_cache_addnew = False

    def _invalidate_schema_cache(self):
        """Invalidate both the column structure cache and the row-level fields cache.
        Call this when _col_names changes (Open, Close, Fields.Append).
        """
        self._fields_static = None
        self._invalidate_fields_cache()

    def _bind_fields_row(self):
        if self._fields_cache is None or self._fields_cache_addnew:
            return
        row = None
        if self._is_open and (not self.EOF) and self._cur_idx < len(self._rows):
            row = self._rows[self._cur_idx]
        try:
            for f in self._fields_cache:
                f._row = row
        except Exception:
            pass
        self._fields_cache_row = self._cur_idx

    def _refresh_view(self):
        if not self._is_open:
            return
        rows = list(self._base_rows) if self._base_rows is not None else list(self._rows)
        if self._filter:
            matcher = _criteria_matcher(self._filter, self._col_names, "Filter")
            rows = [r for r in rows if matcher(r)]
        if self._sort:
            rows = _sort_rows(rows, self._sort, self._col_names)
        self._rows = rows
        self._cur_idx = 0
        self._invalidate_fields_cache()

    def __str__(self):
        return 'Recordset'


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

_docroot_ref: list[str] = ['']  # set from server_object.py when creating
_ado_thread = threading.local()


def _get_open_conns():
    lst = getattr(_ado_thread, 'open_conns', None)
    if lst is None:
        lst = []
        _ado_thread.open_conns = lst
    return lst


def close_all_connections():
    conns = list(_get_open_conns())
    for c in conns:
        try:
            c.Close()
        except Exception:
            pass


class ADOConnection:
    """Classic ADO Connection shim backed by SQLite."""

    def __init__(self, docroot: str = ''):
        self._docroot = docroot or _docroot_ref[0] or '.'
        self._conn: Optional[Any] = None
        self._is_open: bool = False
        self._provider_kind: str = 'unknown'
        self.ConnectionString: str = ''
        self.ConnectionTimeout: int = 30
        self.CommandTimeout: int = 30
        self.CursorLocation: int = 3  # adUseClient
        self.Mode: int = 0
        self.Provider: str = 'SQLite'
        self.DefaultDatabase: str = ''
        # Stub collection so Connection.Properties reads as an empty collection
        # instead of raising error 438. ASPPY has no OLE DB provider to
        # enumerate; see ADOProperties.
        self.Properties = ADOProperties()
        self.State: int = adStateClosed
        self._db_path: str = ''
        self._in_transaction: bool = False
        self._auto_escape: bool = False  # SQL injection auto-protection (disabled by default)

    def Open(self, connection_string: str = '', user_id: str = '',
             password: str = '', options: int = -1):
        if connection_string:
            self.ConnectionString = vbs_cstr(connection_string)
        cs = self.ConnectionString.strip()
        if not cs:
            raise_runtime('ADO_ARGS_WRONG_TYPE', "No connection string")

        # Parse AutoEscapeSQL option from connection string
        auto_escape_match = re.search(r'(?i)\bAutoEscapeSQL\s*=\s*(\w+)', cs)
        if auto_escape_match:
            self._auto_escape = auto_escape_match.group(1).lower() in ('1', 'true', 'yes', 'on')

        info = parse_connection_string(cs)

        # ADO: explicit UserID/Password arguments to Open() override any
        # credentials in the connection string.
        uid_arg = vbs_cstr(user_id).strip() if user_id else ''
        pwd_arg = vbs_cstr(password) if password else ''
        if uid_arg:
            info.attrs['user id'] = uid_arg
        if pwd_arg:
            info.attrs['password'] = pwd_arg

        self.Provider = info.attrs.get('provider', info.provider_kind or 'unknown')
        self._provider_kind = info.provider_kind or 'unknown'
        adapter_kind = 'odbc' if _should_route_to_odbc(info) else self._provider_kind
        adapter = _get_provider_adapter(adapter_kind)
        adapter.open(self, info)

    def Close(self):
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
        self._conn = None
        self._is_open = False
        self.State = adStateClosed
        try:
            conns = _get_open_conns()
            if self in conns:
                conns.remove(self)
        except Exception:
            pass

    def Execute(self, sql: str, records_affected=None, options: int = -1):
        """Execute SQL, returning a Recordset for SELECTs or None for others."""
        if not self._is_open:
            if self.ConnectionString:
                try:
                    self.Open(self.ConnectionString)
                except Exception:
                    pass
        if not self._is_open:
            raise_runtime('ADO_OBJECT_CLOSED')
        translated = vbs_cstr(sql)

        db = _conn_or_raise(self)
        cur = db.cursor()
        try:
            statements = _split_sql_statements(translated)
            recordsets: list[ADORecordset] = []
            for stmt in statements:
                if self._provider_kind == 'excel' and not _is_readonly_query(stmt):
                    raise_runtime(
                        'ADO_UNSPECIFIED',
                        "Excel provider is read-only in ASPPY. Only SELECT queries are supported.",
                    )
                cur.execute(stmt)
                if cur.description is not None:
                    rs = ADORecordset(self)
                    rs._set_col_names(
                        [d[0] for d in cur.description],
                        [_column_type_to_ado(d[1]) for d in cur.description],
                    )
                    rs._rows = cur.fetchall()
                    rs._base_rows = list(rs._rows)
                    rs._cur_idx = 0
                    rs._is_open = True
                    rs.State = adStateOpen
                    m = re.search(r'(?i)\bFROM\s+\[?(\w+)\]?', stmt)
                    if m:
                        rs._table_name = m.group(1)
                        rs._detect_pk(self, stmt)
                    recordsets.append(rs)
                else:
                    db.commit()
            if recordsets:
                rs0 = recordsets[0]
                rs0._next_recordsets = recordsets[1:]
                return rs0
            return ADORecordset(self)
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            raise_runtime('ADO_UNSPECIFIED', f"Execute error: {e}")

    def BeginTrans(self):
        if not self._is_open:
            raise_runtime('ADO_OBJECT_CLOSED')
        if self._in_transaction:
            return 1

        db = _conn_or_raise(self)
        if self._provider_kind == 'sqlite':
            db.execute("BEGIN")
        else:
            try:
                db.autocommit = False
            except Exception:
                pass
        self._in_transaction = True
        return 1

    def CommitTrans(self):
        if self._is_open:
            if not self._in_transaction:
                pass

            db = _conn_or_raise(self)
            try:
                if self._provider_kind == 'sqlite':
                    db.execute("COMMIT")
                else:
                    db.commit()
            except Exception as e:
                if "no transaction is active" not in str(e).lower():
                    raise
            finally:
                if self._provider_kind != 'sqlite':
                    try:
                        db.autocommit = True
                    except Exception:
                        pass
            self._in_transaction = False

    def RollbackTrans(self):
        if self._is_open:
            db = _conn_or_raise(self)
            try:
                if self._provider_kind == 'sqlite':
                    db.execute("ROLLBACK")
                else:
                    db.rollback()
            except Exception as e:
                if "no transaction is active" not in str(e).lower():
                    raise
            finally:
                if self._provider_kind != 'sqlite':
                    try:
                        db.autocommit = True
                    except Exception:
                        pass
            self._in_transaction = False

    @property
    def Errors(self):
        return _EmptyCollection()

    def __str__(self):
        return 'Connection'


class _EmptyCollection:
    @property
    def Count(self):
        return 0

    def __iter__(self):
        return iter([])


class ADOProperties:
    """Provider-specific `Properties` collection.

    ASPPY has no OLE DB provider to enumerate, so this collection is always
    empty. That is exactly what IIS reports for an object with no live
    connection (verified: `Command.Properties.Count` = 0 and
    `TypeName(cmd.Properties)` = "Properties" on IIS for a Command with no
    ActiveConnection). A *connected* Jet command reports roughly 88 provider
    properties there, which ASPPY cannot reproduce - but returning an empty
    collection lets scripts run instead of raising error 438.
    """

    def __vbs_typename__(self):
        return 'Properties'

    @property
    def Count(self):
        return 0

    def __iter__(self):
        return iter([])

    def Item(self, key):
        raise_runtime('ADO_UNSPECIFIED',
                      "Item cannot be found in the collection corresponding to "
                      "the requested name or ordinal")


# ---------------------------------------------------------------------------
# Command / Parameters
# ---------------------------------------------------------------------------

class ADOParameter:
    def __init__(self, name='', type_=adVariant, direction=adParamInput,
                 size=0, value=None):
        self.Name = vbs_cstr(name)
        self.Type = int(type_)
        self.Direction = int(direction)
        self.Size = int(size)
        self.Value = value
        self.Precision = 0
        self.NumericScale = 0


class ADOParameters:
    def __init__(self):
        self._params: list[ADOParameter] = []
        self._name_map: dict[str, int] = {}

    def Append(self, param: ADOParameter):
        idx = len(self._params)
        self._params.append(param)
        self._name_map[param.Name.lower()] = idx

    def Item(self, key) -> ADOParameter:
        if isinstance(key, int) or (isinstance(key, float) and key == int(key)):
            return self._params[int(key)]
        k = vbs_cstr(key).lower()
        if k not in self._name_map:
            raise KeyError(f"Unknown parameter: {key}")
        return self._params[self._name_map[k]]

    def __vbs_index_get__(self, key):
        return self.Item(key).Value

    def __vbs_index_set__(self, key, value):
        self.Item(key).Value = value

    @property
    def Count(self) -> int:
        return len(self._params)

    def __iter__(self):
        return iter(self._params)


class ADOCommand:
    def __init__(self, conn: Optional[ADOConnection] = None):
        self.ActiveConnection: Optional[ADOConnection] = conn
        self.CommandText: str = ''
        # IIS reports adCmdUnknown (8) for a freshly created Command, not
        # adCmdText - verified against IIS.
        self.CommandType: int = adCmdUnknown
        self.CommandTimeout: int = 30
        self.Prepared: bool = False
        self.Parameters = ADOParameters()
        # A Command has no observable open state: IIS reports adStateClosed both
        # before and after a synchronous Execute (adStateExecuting only shows
        # during async execution, which a script can never catch). Verified
        # against IIS, so this deliberately stays 0 rather than flipping to
        # adStateOpen on Execute.
        self.State: int = adStateClosed
        self.Properties = ADOProperties()

    def CreateParameter(self, name='', type_=adVariant, direction=adParamInput,
                        size=0, value=None) -> ADOParameter:
        return ADOParameter(name, type_, direction, size, value)

    def Execute(self, records_affected=None, parameters=None, options: int = -1):
        conn = self.ActiveConnection
        if conn is None:
            raise_runtime('ADO_OBJECT_CLOSED', "No ActiveConnection")
        assert conn is not None
        if not conn._is_open:
            conn.Open()

        sql = vbs_cstr(self.CommandText)

        # Replace named/positional ? markers with parameter values
        param_vals = [p.Value for p in self.Parameters]
        if parameters is not None:
            # Override with explicitly passed parameters
            if hasattr(parameters, '__iter__'):
                param_vals = list(parameters)

        param_vals = [_normalize_param(v) for v in param_vals]

        db = _conn_or_raise(conn)
        cur = db.cursor()
        try:
            if conn._provider_kind == 'excel' and not _is_readonly_query(sql):
                raise_runtime(
                    'ADO_UNSPECIFIED',
                    "Excel provider is read-only in ASPPY. Only SELECT queries are supported.",
                )
            cur.execute(sql, param_vals)
            if cur.description is not None:
                rs = ADORecordset(conn)
                rs._set_col_names(
                    [d[0] for d in cur.description],
                    [_column_type_to_ado(d[1]) for d in cur.description],
                )
                rs._rows = cur.fetchall()
                rs._cur_idx = 0
                rs._is_open = True
                rs.State = adStateOpen
                return rs
            else:
                db.commit()
                return ADORecordset(conn)
        except Exception as e:
            try:
                db.rollback()
            except Exception:
                pass
            raise_runtime('ADO_UNSPECIFIED', f"Command Execute error: {e}")

    def __str__(self):
        return 'Command'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _column_type_to_ado(type_meta: Any) -> int:
    if type_meta is None:
        return adVariant

    if isinstance(type_meta, str):
        t = type_meta.strip().lower().split('(')[0]
        return _SQLITE_TYPE_MAP.get(t, adVariant)

    name = str(type_meta).lower()
    if 'int' in name:
        return adInteger
    if 'float' in name or 'double' in name or 'real' in name or 'decimal' in name or 'numeric' in name:
        return adDouble
    if 'bool' in name:
        return adBoolean
    if 'date' in name or 'time' in name:
        return adDate
    if 'bytes' in name or 'binary' in name or 'blob' in name:
        return adLongVarBinary
    if 'char' in name or 'text' in name or 'str' in name:
        return adVarWChar
    return adVariant


def TypeName(obj) -> str:
    if isinstance(obj, ADORecordset):
        return 'Recordset'
    if isinstance(obj, ADOConnection):
        return 'Connection'
    if isinstance(obj, ADOCommand):
        return 'Command'
    return type(obj).__name__


def _split_sql_statements(sql: str) -> list[str]:
    statements: list[str] = []
    buf: list[str] = []
    in_single = False
    in_double = False
    i = 0
    while i < len(sql):
        ch = sql[i]
        if in_single:
            buf.append(ch)
            if ch == "'":
                if i + 1 < len(sql) and sql[i + 1] == "'":
                    buf.append(sql[i + 1])
                    i += 1
                else:
                    in_single = False
            elif ch == "\\" and i + 1 < len(sql):
                buf.append(sql[i + 1])
                i += 1
            i += 1
            continue
        if in_double:
            buf.append(ch)
            if ch == '"':
                if i + 1 < len(sql) and sql[i + 1] == '"':
                    buf.append(sql[i + 1])
                    i += 1
                else:
                    in_double = False
            elif ch == "\\" and i + 1 < len(sql):
                buf.append(sql[i + 1])
                i += 1
            i += 1
            continue
        if ch == "'":
            in_single = True
            buf.append(ch)
            i += 1
            continue
        if ch == '"':
            in_double = True
            buf.append(ch)
            i += 1
            continue
        if ch == ';':
            stmt = ''.join(buf).strip()
            if stmt:
                statements.append(stmt)
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    stmt = ''.join(buf).strip()
    if stmt:
        statements.append(stmt)
    return statements


def _is_readonly_query(sql: str) -> bool:
    s = vbs_cstr(sql).strip()
    if not s:
        return True
    return re.match(r'(?is)^(select|with)\b', s) is not None


def _criteria_matcher(criteria: Any, col_names: list[str], source: str = "Filter"):
    crit = vbs_cstr(criteria) if criteria is not None else ""
    m = re.match(r"\s*\[?(\w+)\]?\s*(=|<>|!=|>=|<=|>|<)\s*(.+)\s*", crit)
    if not m:
        return lambda row: False
    field, op, raw = m.group(1), m.group(2), m.group(3).strip()
    if raw.startswith("'") and raw.endswith("'"):
        value = raw[1:-1]
    else:
        try:
            value = int(raw)
        except Exception:
            try:
                value = float(raw)
            except Exception:
                value = raw
    idx = -1
    try:
        idx = [c.lower() for c in col_names].index(field.lower())
    except ValueError:
        raise_runtime('ADO_ARGS_WRONG_TYPE', f"ADODB.Recordset.{source}: field not found: {field}")
    if idx < 0:
        raise_runtime('ADO_ARGS_WRONG_TYPE', f"ADODB.Recordset.{source}: field not found: {field}")

    def _cmp(a, b):
        try:
            if isinstance(a, str) or isinstance(b, str):
                a = vbs_cstr(a).lower()
                b = vbs_cstr(b).lower()
            if op == '=':
                return a == b
            if op in ('<>', '!='):
                return a != b
            if op == '>':
                return a > b
            if op == '>=':
                return a >= b
            if op == '<':
                return a < b
            if op == '<=':
                return a <= b
        except Exception:
            return False
        return False

    return lambda row: _cmp(row[idx], value)


def _sort_rows(
    rows: list[tuple],
    sort_expr: str,
    col_names: list[str],
    source: str = "Sort",
) -> list[tuple]:
    expr = vbs_cstr(sort_expr)
    parts = [p.strip() for p in expr.split(',') if p.strip()]
    terms: list[tuple[int, bool]] = []
    for part in parts:
        m = re.match(r"\s*\[?(\w+)\]?\s*(ASC|DESC)?\s*", part, re.I)
        if not m:
            continue
        field = m.group(1)
        direction = (m.group(2) or "ASC").upper()
        idx = -1
        try:
            idx = [c.lower() for c in col_names].index(field.lower())
        except ValueError:
            raise_runtime('ADO_ARGS_WRONG_TYPE', f"ADODB.Recordset.{source}: field not found: {field}")
        if idx < 0:
            raise_runtime('ADO_ARGS_WRONG_TYPE', f"ADODB.Recordset.{source}: field not found: {field}")
        terms.append((idx, direction == "DESC"))
    if not terms:
        return rows
    out = list(rows)

    def key_value(v):
        if v is None:
            return ""
        if isinstance(v, str):
            return v.lower()
        return v

    for idx, desc in reversed(terms):
        out.sort(key=lambda r: key_value(r[idx] if idx < len(r) else None), reverse=desc)
    return out
