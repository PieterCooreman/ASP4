import pyodbc
import sqlite3
import sys
import os
import glob
import datetime

# Fix for Python 3.12+ Date/Time warning
sqlite3.register_adapter(datetime.datetime, lambda val: val.isoformat(" "))
sqlite3.register_adapter(datetime.date, lambda val: val.isoformat())

def convert_database(access_db_path, sqlite_db_path):
# ... the rest of your code remains exactly the same ...
    conn_str = (
        r'Driver={Microsoft Access Driver (*.mdb, *.accdb)};'
        f'DBQ={access_db_path};'
    )

    try:
        access_conn = pyodbc.connect(conn_str)
        access_crsr = access_conn.cursor()
    except pyodbc.Error as e:
        print(f"  [!] Error connecting to {os.path.basename(access_db_path)}: {e}")
        return False

    if os.path.exists(sqlite_db_path):
        os.remove(sqlite_db_path)
        
    sqlite_conn = sqlite3.connect(sqlite_db_path)
    sqlite_crsr = sqlite_conn.cursor()

    tables = [row.table_name for row in access_crsr.tables(tableType='TABLE')]

    for table in tables:
        print(f"  -> Processing table: {table}...")

        pk_columns = []
        idx_dict = {}

        # 1. Extract Indexes & Primary Keys
        try:
            indexes = access_crsr.statistics(table).fetchall()
            for idx in indexes:
                idx_name = idx.index_name
                col_name = idx.column_name
                
                if not idx_name or not col_name:
                    continue
                
                if idx_name.lower() == 'primarykey':
                    if col_name not in pk_columns:
                        pk_columns.append(col_name)
                else:
                    if idx_name not in idx_dict:
                        idx_dict[idx_name] = {'unique': not idx.non_unique, 'columns': []}
                    if col_name not in idx_dict[idx_name]['columns']:
                        idx_dict[idx_name]['columns'].append(col_name)
        except Exception as e:
            print(f"    [!] Warning: Could not fetch indexes for {table}: {e}")

        # 2. Extract Columns
        columns = access_crsr.columns(table).fetchall()
        col_defs = []

        for col in columns:
            col_name = col.column_name
            type_name = col.type_name.upper() if col.type_name else 'TEXT'

            sqlite_type = "TEXT"
            if 'COUNTER' in type_name:
                sqlite_type = "INTEGER"
            elif any(t in type_name for t in ['INT', 'BYTE', 'BIT']):
                sqlite_type = "INTEGER"
            elif any(t in type_name for t in ['FLOAT', 'DOUBLE', 'REAL', 'NUMERIC']):
                sqlite_type = "REAL"

            if col_name in pk_columns and len(pk_columns) == 1 and 'COUNTER' in type_name:
                col_defs.append(f'"{col_name}" INTEGER PRIMARY KEY AUTOINCREMENT')
                pk_columns.remove(col_name) 
            else:
                col_defs.append(f'"{col_name}" {sqlite_type}')

        # 3. Add composite Primary Keys
        if pk_columns:
            pk_str = ", ".join([f'"{pk}"' for pk in pk_columns])
            col_defs.append(f'PRIMARY KEY ({pk_str})')

        create_sql = f'CREATE TABLE "{table}" (\n  ' + ',\n  '.join(col_defs) + '\n);'
        sqlite_crsr.execute(create_sql)

        # 4. Extract and Insert Data
        access_crsr.execute(f'SELECT * FROM [{table}]')
        rows = access_crsr.fetchall()

        if rows:
            # Identify boolean columns (Access BIT type stores True as -1, False as 0)
            bool_col_indices = {
                i for i, col in enumerate(columns)
                if col.type_name and 'BIT' in col.type_name.upper()
            }

            placeholders = ", ".join(["?"] * len(columns))
            insert_sql = f'INSERT INTO "{table}" VALUES ({placeholders})'

            def fix_row(row):
                if not bool_col_indices:
                    return tuple(row)
                return tuple(
                    (1 if v else 0) if i in bool_col_indices else v
                    for i, v in enumerate(row)
                )

            data = [fix_row(row) for row in rows]
            sqlite_crsr.executemany(insert_sql, data)

        # 5. Rebuild Secondary Indexes
        for idx_name, info in idx_dict.items():
            unique_str = "UNIQUE " if info['unique'] else ""
            cols_str = ", ".join([f'"{c}"' for c in info['columns']])
            
            safe_idx_name = f"idx_{table}_{idx_name}".replace(" ", "_")
            create_idx_sql = f'CREATE {unique_str}INDEX "{safe_idx_name}" ON "{table}" ({cols_str});'
            try:
                sqlite_crsr.execute(create_idx_sql)
            except sqlite3.OperationalError as e:
                print(f"    [!] Warning: Could not create index {safe_idx_name}: {e}")

    sqlite_conn.commit()
    access_conn.close()
    sqlite_conn.close()
    print(f"  [+] Success! Saved to {os.path.basename(sqlite_db_path)}")
    return True

if __name__ == "__main__":
    # The .strip('"') removes the sneaky quotation mark caused by Windows batch files
    target_dir = sys.argv[1].strip('"') if len(sys.argv) > 1 else os.getcwd()
    
    print(f"=== ASP/PY Bulk Converter ===")
    print(f"Scanning directory: {target_dir}\n")

    # Gather both .mdb and .accdb files into a single list
    mdb_files = glob.glob(os.path.join(target_dir, "*.mdb"))
    accdb_files = glob.glob(os.path.join(target_dir, "*.accdb"))
    all_databases = mdb_files + accdb_files

    if not all_databases:
        print("No .mdb or .accdb files found in this directory.")
        sys.exit(0)

    for db_file in all_databases:
        base_name = os.path.splitext(db_file)[0]
        sqlite_file = f"{base_name}.sqlite"
        
        print(f"Converting: {os.path.basename(db_file)}")
        convert_database(db_file, sqlite_file)
        print("-" * 40)

    print("\nAll conversions complete!")
