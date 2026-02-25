# Access_To_SQLite: Access to SQLite Converter

Access_To_SQLite is a lightweight, Python-based command-line tool designed to automatically convert Microsoft Access databases (`.mdb` and `.accdb`) into SQLite databases (`.sqlite`). 

It handles schema extraction, data type translation, record migration, and automatically rebuilds your keys and indexes.

## Features
* **Zero-Config Bulk Conversion:** By default, the script automatically detects and converts all Access databases residing in the exact same folder as the script.
* **Smart Autonumber Handling:** Detects Access `COUNTER` (IDENTITY) fields and seamlessly translates them to SQLite's `INTEGER PRIMARY KEY AUTOINCREMENT` standard.
* **Key & Index Migration:** Automatically extracts and recreates Primary Keys (including composite keys) and rebuilds Secondary Indexes with globally unique naming to comply with SQLite constraints.
* **Future-Proof Date Handling:** Includes custom SQLite adapters to bypass Python 3.12+ `datetime` deprecation warnings.

## Prerequisites

1. **Python 3** installed on your Windows machine.
2. **Microsoft Access Database Engine** installed.
   * *Important:* The bit-version of your MS Access Engine (32-bit vs. 64-bit) must exactly match the bit-version of your Python installation, or the ODBC driver will fail to connect.
3. **pyodbc library** for database connections. Install it via command prompt:
   ```bash
   pip install pyodbc