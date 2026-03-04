# ASP4 - Classic ASP/VBScript to Python Transpiler

ASP4 is a Python-based runtime that executes Classic ASP (VBScript) pages. It provides compatibility with most VBScript built-in functions, the Classic ASP object model (Request, Response, Session, Application, Server), and various COM components commonly used in legacy ASP applications.

## Platform Support

ASP4 works on:
- Windows
- Linux
- macOS

## Dependencies

The following Python libraries are required:

| Library | Purpose |
|---------|---------|
| Python 3.8+ | Runtime environment |
| fpdf2 | PDF generation (`pip install fpdf2`) |
| bcrypt | Password hashing (`pip install bcrypt`) |
| Pillow | Image processing (`pip install pillow`) |
| pyodbc | Access/Excel/ODBC database providers (`pip install pyodbc`) |
| certifi (optional) | TLS CA bundle for MSXML HTTP (`pip install certifi`) |
| zipfile (built-in) | ZIP file handling |

---

# VBScript Built-in Functions

Compatibility notes for built-ins:

- ASP4 targets practical Classic ASP/VBScript compatibility, but does not guarantee byte-for-byte parity with IIS VBScript for every edge case.
- The function lists below describe the exposed runtime surface; behavior can still differ in locale, coercion, error wording, and edge conditions.
- Functions implemented through compatibility shims/stubs (for example formatting/script-engine helpers) are intended for app portability, not strict engine emulation.
- SQL/dialect translation is intentionally out of scope; database commands are executed as provided by the script and underlying provider/driver.
- If exact behavior matters for a critical path, validate with your app-specific regression tests.

## String Functions

| Function | Description |
|----------|-------------|
| `Len(string)` | Returns the length of a string |
| `LenB(expression)` | Returns the length of a string in bytes |
| `UCase(string)` | Converts a string to uppercase |
| `LCase(string)` | Converts a string to lowercase |
| `Trim(string)` | Removes leading and trailing spaces |
| `LTrim(string)` | Removes leading spaces |
| `RTrim(string)` | Removes trailing spaces |
| `StrReverse(string)` | Reverses a string |
| `StrComp(string1, string2[, compare])` | Compares two strings |
| `Left(string, length)` | Returns leftmost characters |
| `Right(string, length)` | Returns rightmost characters |
| `Mid(string, start[, length])` | Returns characters from a string |
| `LeftB(string, length)` | Returns leftmost bytes |
| `RightB(string, length)` | Returns rightmost bytes |
| `MidB(expr, start[, length])` | Returns bytes from a string |
| `InStr([start, ]string1, string2[, compare])` | Finds one string within another |
| `InStrB([start, ]string1, string2)` | Finds one string within another (byte) |
| `Replace(expression, find, replace[, start[, count[, compare]]])` | Replaces text in a string |
| `Split(expression[, delimiter[, count[, compare]]])` | Splits a string into an array |
| `Join(list[, delimiter])` | Joins an array into a string |
| `Filter(inputstrings, value[, include[, compare]])` | Returns a filtered array |
| `Space(number)` | Returns a string of spaces |
| `String(number, character)` | Returns a repeating character string |
| `Asc(string)` | Returns the ANSI code of the first character |
| `AscW(string)` | Returns the Unicode code of the first character |
| `AscB(string)` | Returns the first byte of a string |
| `Chr(charcode)` | Returns the character associated with an ANSI code |
| `ChrW(charcode)` | Returns the character associated with a Unicode code |
| `ChrB(charcode)` | Returns a single-byte character |
| `Hex(number)` | Returns the hexadecimal value |
| `Oct(number)` | Returns the octal value |

---

## Array Functions

| Function | Description |
|----------|-------------|
| `Array(arglist)` | Creates an array |
| `IsArray(varname)` | Returns True if variable is an array |
| `LBound(arrayname[, dimension])` | Returns the lowest subscript |
| `UBound(arrayname[, dimension])` | Returns the highest subscript |

---

## Type Conversion Functions

| Function | Description |
|----------|-------------|
| `CBool(expression)` | Converts to Boolean |
| `CByte(expression)` | Converts to Byte |
| `CCur(expression)` | Converts to Currency |
| `CDbl(expression)` | Converts to Double |
| `CInt(expression)` | Converts to Integer |
| `CLng(expression)` | Converts to Long |
| `CSng(expression)` | Converts to Single |
| `CStr(expression)` | Converts to String |
| `CDate(date)` | Converts to Date |

---

## Date/Time Functions

| Function | Description |
|----------|-------------|
| `Now()` | Returns current date and time |
| `Date()` | Returns current system date |
| `Time()` | Returns current system time |
| `Timer()` | Returns seconds since midnight |
| `Year(date)` | Returns the year |
| `Month(date)` | Returns the month (1-12) |
| `Day(date)` | Returns the day (1-31) |
| `Hour(time)` | Returns the hour (0-23) |
| `Minute(time)` | Returns the minute (0-59) |
| `Second(time)` | Returns the second (0-59) |
| `DateSerial(year, month, day)` | Returns a date |
| `TimeSerial(hour, minute, second)` | Returns a time |
| `DateAdd(interval, number, date)` | Adds a time interval |
| `DateDiff(interval, date1, date2[, firstdayofweek[, firstweekofyear]])` | Returns the difference |
| `DatePart(interval, date[, firstdayofweek[, firstweekofyear]])` | Returns a part of a date |
| `Weekday(date[, firstdayofweek])` | Returns the weekday (1-7) |
| `WeekdayName(weekday[, abbreviate[, firstdayofweek]])` | Returns the weekday name |
| `MonthName(month[, abbreviate])` | Returns the month name |
| `DateValue(string)` | Returns a date from a string |
| `TimeValue(string)` | Returns a time from a string |
| `CDate(string)` | Converts a string to a date |
| `IsDate(expression)` | Returns True if expression is a date |
| `FormatDateTime(date[, namedformat])` | Formats a date/time |

### Date Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `vbSunday` | 1 | Sunday |
| `vbMonday` | 2 | Monday |
| `vbTuesday` | 3 | Tuesday |
| `vbWednesday` | 4 | Wednesday |
| `vbThursday` | 5 | Thursday |
| `vbFriday` | 6 | Friday |
| `vbSaturday` | 7 | Saturday |
| `vbUseSystemDayOfWeek` | 0 | Use system day of week |
| `vbFirstJan1` | 1 | First week with Jan 1 |
| `vbFirstFourDays` | 2 | First week with 4 days |
| `vbFirstFullWeek` | 3 | First full week |
| `vbGeneralDate` | 0 | General date format |
| `vbLongDate` | 1 | Long date format |
| `vbShortDate` | 2 | Short date format |
| `vbLongTime` | 3 | Long time format |
| `vbShortTime` | 4 | Short time format |
| `vbBinaryCompare` | 0 | Binary comparison |
| `vbTextCompare` | 1 | Text comparison |

---

## Math Functions

| Function | Description |
|----------|-------------|
| `Abs(number)` | Returns absolute value |
| `Atn(number)` | Returns arctangent |
| `Cos(number)` | Returns cosine |
| `Exp(number)` | Returns e raised to a power |
| `Fix(number)` | Returns integer portion |
| `Int(number)` | Returns integer portion (floor) |
| `Log(number)` | Returns natural logarithm |
| `Rnd([number])` | Returns random number |
| `Round(expression[, numdecimalplaces])` | Rounds a number |
| `Sqr(number)` | Returns square root |
| `Sgn(number)` | Returns sign of a number |

---

## Format Functions

Note: formatting functions are compatibility-focused and may differ from IIS under some locale/regional settings.

| Function | Description |
|----------|-------------|
| `FormatNumber(expression[, numdigitsafterdecimal[, includeleadingdigit[, useparensfornegativenumbers[, groupdigits]]]])` | Formats a number |
| `FormatCurrency(expression[, numdigitsafterdecimal[, includeleadingdigit[, useparensfornegativenumbers[, groupdigits]]]])` | Formats as currency |
| `FormatPercent(expression[, numdigitsafterdecimal[, includeleadingdigit[, useparensfornegativenumbers[, groupdigits]]]])` | Formats as percentage |

---

## Information Functions

Note: type/coercion semantics generally follow VBScript, but may differ in edge cases involving Empty/Null/Nothing and host objects.

| Function | Description |
|----------|-------------|
| `IsArray(varname)` | Returns True if variable is an array |
| `IsDate(expression)` | Returns True if expression is a date |
| `IsEmpty(expression)` | Returns True if variable is Empty |
| `IsNull(expression)` | Returns True if expression is Null |
| `IsNumeric(expression)` | Returns True if expression is numeric |
| `IsObject(expression)` | Returns True if expression is an object |
| `TypeName(varname)` | Returns the type name |
| `VarType(varname)` | Returns the variant type |

### VarType Constants

| Constant | Value | Description |
|----------|-------|-------------|
| `vbEmpty` | 0 | Empty (uninitialized) |
| `vbNull` | 1 | Null (no valid data) |
| `vbInteger` | 2 | Integer |
| `vbLong` | 3 | Long integer |
| `vbSingle` | 4 | Single-precision |
| `vbDouble` | 8 | Double-precision |
| `vbCurrency` | 6 | Currency |
| `vbDate` | 7 | Date |
| `vbString` | 8 | String |
| `vbObject` | 9 | Object |
| `vbBoolean` | 11 | Boolean |
| `vbArray` | 8192 | Array |

---

## Color Functions

| Function | Description |
|----------|-------------|
| `RGB(red, green, blue)` | Returns an RGB color value |

---

# Classic ASP Objects

## Server Object

### Methods

| Method | Description |
|--------|-------------|
| `CreateObject(progid)` | Creates an instance of a COM object |
| `HTMLEncode(string)` | Encodes HTML characters |
| `URLEncode(string)` | URL-encodes a string |
| `MapPath(path)` | Maps a virtual path to a physical path |
| `Execute(path)` | Executes an ASP file |
| `Transfer(path)` | Transfers execution to another ASP file |
| `GetLastError()` | Returns the last error object |

### Properties

| Property | Description |
|----------|-------------|
| `ScriptTimeout` | Gets/sets script timeout in seconds |

### Extension Methods (ASP4-specific)

| Method | Description |
|--------|-------------|
| `ASP4ListAspPages()` | Lists all .asp pages under docroot |
| `ASP4Run(virtual_path)` | Runs another ASP page and captures output |

### Supported `Server.CreateObject` ProgIDs

- `Scripting.Dictionary`
- `Scripting.FileSystemObject`
- `ADODB.Connection`, `ADODB.Recordset`, `ADODB.Command`, `ADODB.Stream`
- `VBScript.RegExp` / `RegExp`
- `MSXML2.ServerXMLHTTP`, `MSXML2.XMLHTTP`, `MSXML2.DOMDocument` (incl. `.3.0`/`.6.0` aliases)
- `Microsoft.XMLDOM`, `MSXML.DOMDocument`
- `CDO.Message`, `CDOSYS.Message`
- `ASP4.POP3`, `ASPPY.POP3`, `ASP4.IMAP`, `ASPPY.IMAP`

---

## Request Object

### Properties

| Property | Description |
|----------|-------------|
| `QueryString` | NameValueCollection of query string parameters |
| `Form` | NameValueCollection of form data parsed from `POST` only |
| `Cookies` | NameValueCollection of cookies |
| `ServerVariables` | NameValueCollection of server variables |
| `TotalBytes` | Total bytes in request body |
| `Files` | Collection of uploaded files |
| `Request` (default) | Access to QueryString, Form, Cookies |

### Methods

| Method | Description |
|--------|-------------|
| `BinaryRead(count)` | Reads raw bytes from request body |

### HTTP methods and body parsing

- ASP4 passes through HTTP methods to ASP pages without a verb allow-list.
- `Request.ServerVariables("REQUEST_METHOD")` returns the incoming verb string (for example: `GET`, `POST`, `PUT`, `DELETE`, `PATCH`, `HEAD`, `OPTIONS`).
- `Request.Form` is parsed for `POST` with supported form encodings (`application/x-www-form-urlencoded`, `multipart/form-data`).
- For non-`POST` bodies (`PUT`, `DELETE`, `PATCH`, etc.), read raw bytes via `Request.BinaryRead(...)`; `Request.Form` remains empty.
- `Request.TotalBytes` reflects the request body size for any method.

### Request.Files Collection

Access uploaded files from multipart form submissions.

```vbscript
' Iterate over all uploaded files
For Each file In Request.Files
    Response.Write(file.FileName)
    Response.Write(file.Size)
    Response.Write(file.ContentType)
    ' Save to disk
    file.SaveAs Server.MapPath("/uploads/" & file.FileName)
Next

' Access specific file
Set f = Request.Files("myfile")
If Not f Is Nothing Then
    Response.Write f.Name
    Response.Write f.FileName
    Response.Write f.Size
    Response.Write f.ContentType
End If

' Check if file exists
If Request.Files.Exists("myfile") Then
    ' File was uploaded
End If

' Get count
Response.Write Request.Files.Count
```

#### UploadedFile Properties

| Property | Description |
|----------|-------------|
| `Name` | Form field name |
| `FileName` | Original filename |
| `ContentType` | MIME content type |
| `Size` | File size in bytes |

#### UploadedFile Methods

| Method | Description |
|--------|-------------|
| `SaveAs(path)` | Saves the file to disk |

#### Files Collection Methods

| Method | Description |
|--------|-------------|
| `Count` | Number of uploaded files |
| `Exists(name)` | Checks if file with given name exists |
| `Item(name)` | Gets uploaded file by name |
| `Keys()` | Returns array of field names |
| `Items()` | Returns array of UploadedFile objects |

---

## Response Object

### Properties

| Property | Description |
|----------|-------------|
| `Buffer` | Enables/disables response buffering |
| `Cookies` | Collection of cookies to send |
| `LCID` | Locale identifier |

### Methods

| Method | Description |
|--------|-------------|
| `Write(string)` | Writes output to the response |
| `BinaryWrite(data)` | Writes binary data |
| `Clear()` | Clears the buffered output |
| `Flush()` | Flushes buffered output |
| `End()` | Stops script execution |
| `AddHeader(name, value)` | Adds a custom header |
| `AppendToLog(message)` | Appends to server log |
| `Redirect(url)` | Redirects to another URL |
| `File(path[, inline])` | Serves a file (inline=True for display, False for download) |

---

## Session Object

### Properties

| Property | Description |
|----------|-------------|
| `SessionID` | Unique session identifier |
| `Timeout` | Session timeout in minutes |
| `Contents` | Collection of session variables |
| `StaticObjects` | Collection of session-scoped objects |

### Methods

| Method | Description |
|--------|-------------|
| `Abandon()` | Ends the session |

---

## Application Object

### Properties

| Property | Description |
|----------|-------------|
| `Contents` | Collection of application variables |
| `StaticObjects` | Collection of static objects |

### Methods

| Method | Description |
|--------|-------------|
| `Lock()` | Locks application variables |
| `Unlock()` | Unlocks application variables |

---

# ASP4 Extended Objects

## ASP4 Object

The ASP4 object provides additional functionality beyond classic ASP.

It is available as global `ASP4` in script scope.

### JSON

```vbscript
ASP4.JSON.Encode(value[, pretty])  ' Returns JSON string
ASP4.JSON.Decode(json_string)      ' Returns VBScript value
```

Note: member access is case-insensitive in VBScript; runtime members are exposed as `json`, `zip`, `image`, `crypto`, `pdf`.

### ZIP

```vbscript
ASP4.Zip.Zip(path[, out_path])     ' Creates a ZIP file
ASP4.Zip.Unzip(zip_path, dest_folder[, overwrite])  ' Extracts a ZIP file
```

### Image (Pillow)

```vbscript
ASP4.Image.open(path)               ' Opens an image file
ASP4.Image.new(mode, size, color)    ' Creates a new image
ASP4.Image.merge(mode, bands)       ' Merges image bands
ASP4.Image.blend(img1, img2, alpha) ' Blends two images
ASP4.Image.composite(img1, img2, mask) ' Creates composite

ASP4.ImageDraw.Draw(img)            ' Creates a draw object
ASP4.ImageFilter.BLUR               ' Blur filter constant
ASP4.ImageFilter.CONTOUR            ' Contour filter
ASP4.ImageFilter.EDGE_ENHANCE       ' Edge enhancement
ASP4.ImageFilter.SHARPEN            ' Sharpen filter
ASP4.ImageFilter.GaussianBlur(radius) ' Gaussian blur

ASP4.ImageEnhance.Brightness(img)   ' Brightness enhancer
ASP4.ImageEnhance.Contrast(img)     ' Contrast enhancer
```

#### ImageInstance Properties/Methods

| Property/Method | Description |
|----------------|-------------|
| `size` | Image dimensions (width, height) |
| `width` | Image width |
| `height` | Image height |
| `mode` | Image color mode |
| `format` | Image format |
| `save(path)` | Saves the image |
| `resize(size)` | Resizes the image |
| `thumbnail(size)` | Creates thumbnail |
| `crop(box)` | Crops the image |
| `rotate(angle)` | Rotates the image |
| `convert(mode)` | Converts color mode |
| `split()` | Splits into bands |
| `getpixel(xy)` | Gets pixel value |
| `putpixel(xy, value)` | Sets pixel value |
| `filter(filter_obj)` | Applies filter |
| `paste(other_img, box[, mask])` | Pastes another image |

### PDF (FPDF)

```vbscript
Set pdf = ASP4.Pdf.New([orientation[, unit[, format]]])
```

#### PdfDoc Methods

| Method | Description |
|--------|-------------|
| `add_page([orientation])` | Adds a new page |
| `set_margins(left, top[, right])` | Sets page margins |
| `set_auto_page_break(auto[, margin])` | Sets auto page break |
| `set_font(family[, style[, size]])` | Sets the font |
| `set_text_color(r[, g[, b]])` | Sets text color |
| `set_draw_color(r[, g[, b]])` | Sets drawing color |
| `set_fill_color(r[, g[, b]])` | Sets fill color |
| `set_line_width(width)` | Sets line width |
| `fill_page(r[, g[, b]])` | Fills the page with color |
| `text(x, y, text)` | Writes text at position |
| `cell(w[, h[, text[, border[, ln[, align[, fill[, link]]]]]]])` | Writes a cell |
| `multi_cell(w, h, text[, border[, align[, fill]]])` | Writes multi-cell |
| `set_xy(x, y)` | Sets current position |
| `ln([h])` | Moves to next line |
| `image(path[, x[, y[, w[, h]]]])` | Adds an image |
| `output(path)` | Saves PDF to file |

### Crypto (bcrypt)

```vbscript
ASP4.Crypto.Hash(password[, rounds])    ' Hashes a password (rounds 4-31, default 12)
ASP4.Crypto.Verify(password, hashed)     ' Verifies password against hash
```

---

# COM Objects

## Scripting.Dictionary

```vbscript
Set dict = Server.CreateObject("Scripting.Dictionary")
```

| Property/Method | Description |
|----------------|-------------|
| `Count` | Number of items |
| `CompareMode` | Comparison mode (0=Binary, 1=Text, 2=Database) |
| `Item(key)` | Gets/sets item value |
| `Keys` | Returns array of keys |
| `Items` | Returns array of items |
| `Add(key, item)` | Adds a key/item pair |
| `Exists(key)` | Returns True if key exists |
| `Remove(key)` | Removes a key |
| `RemoveAll()` | Removes all items |

## Scripting.FileSystemObject

```vbscript
Set fso = Server.CreateObject("Scripting.FileSystemObject")
```

| Property/Method | Description |
|----------------|-------------|
| `BuildPath(path, name)` | Builds a path |
| `CreateTextFile(filename[, overwrite[, unicode]])` | Creates text file |
| `OpenTextFile(filename[, iomode[, create[, format]]])` | Opens text file |
| `GetFile(filepath)` | Gets File object |
| `GetFolder(folderpath)` | Gets Folder object |
| `GetDrive(drivespec)` | Gets Drive object |
| `DriveExists(drivespec)` | Checks if drive exists |
| `FileExists(filepath)` | Checks if file exists |
| `FolderExists(folderpath)` | Checks if folder exists |

### File Object

| Property/Method | Description |
|----------------|-------------|
| `Path` | Full path |
| `Name` | File name |
| `Size` | File size |
| `Type` | File type |
| `DateCreated` | Creation date |
| `DateLastAccessed` | Last access date |
| `DateLastModified` | Last modified date |
| `Drive` | Drive letter |
| `ParentFolder` | Parent folder |
| `ShortName` | 8.3 name |
| `ShortPath` | 8.3 path |
| `Attributes` | File attributes |
| `Copy(destination[, overwrite])` | Copies file |
| `Move(destination)` | Moves file |
| `Delete([force])` | Deletes file |
| `OpenAsTextStream([iomode[, format]])` | Opens as text stream |

### Folder Object

| Property/Method | Description |
|----------------|-------------|
| `Path` | Full path |
| `Name` | Folder name |
| `Size` | Total size of folder |
| `DateCreated` | Creation date |
| `DateLastAccessed` | Last access date |
| `DateLastModified` | Last modified date |
| `Drive` | Drive letter |
| `IsRootFolder` | True if root |
| `Files` | Files collection |
| `SubFolders` | Subfolders collection |
| `Attributes` | Folder attributes |
| `Copy(destination[, overwrite])` | Copies folder |
| `Move(destination)` | Moves folder |
| `Delete([force])` | Deletes folder |

### TextStream Object

| Property/Method | Description |
|----------------|-------------|
| `AtEndOfStream` | True at end of file |
| `Read(n)` | Reads n characters |
| `ReadLine()` | Reads a line |
| `ReadAll()` | Reads entire file |
| `Write(string)` | Writes string |
| `WriteLine([string])` | Writes line |
| `WriteBlankLines(n)` | Writes blank lines |
| `Close()` | Closes the stream |
| `Skip(n)` | Skips n characters |
| `SkipLine()` | Skips a line |

## VBScript.RegExp

```vbscript
Set regex = Server.CreateObject("VBScript.RegExp")
```

| Property/Method | Description |
|----------------|-------------|
| `Pattern` | Regular expression pattern |
| `IgnoreCase` | Case-insensitive matching |
| `Global` | Match all occurrences |
| `MultiLine` | Multi-line matching |
| `Test(string)` | Tests for a match |
| `Replace(string, replace_with)` | Replaces matches |
| `Execute(string)` | Returns match collection |

## ADODB.Connection

```vbscript
Set conn = Server.CreateObject("ADODB.Connection")
```

| Property/Method | Description |
|----------------|-------------|
| `ConnectionString` | Connection string |
| `State` | Connection state |
| `CommandTimeout` | Command timeout |
| `CursorLocation` | Cursor location |
| `Open([connection_string])` | Opens connection |
| `Close()` | Closes connection |
| `Execute(sql[, records_affected[, options]])` | Executes SQL |
| `BeginTrans()` | Begins transaction |
| `CommitTrans()` | Commits transaction |
| `RollbackTrans()` | Rolls back transaction |

Connection string notes:

- Execution support is currently SQLite (`sqlite3`), Access (`pyodbc` + Access ODBC driver), Excel (`pyodbc` + Excel ODBC driver), and generic ODBC (`pyodbc`) in this runtime.
- ASP4 now parses and classifies common legacy ADO connection string families (Access, SQL Server, ODBC, MySQL, Oracle, PostgreSQL) so unsupported providers fail with explicit migration guidance instead of generic errors.
- For SQLite, use `Provider=SQLite;Data Source=<path>` (or `Provider=SQLite;Database=<path>`), or a bare file path.
- For Access, use legacy Access-style strings (`Provider=Microsoft.Jet.OLEDB.4.0` / `Provider=Microsoft.ACE.OLEDB.12.0`) with `Data Source=<path to .mdb/.accdb>`.
- For Excel, use legacy Excel-style strings (for example `Provider=Microsoft.ACE.OLEDB.12.0;Data Source=<path>;Extended Properties="Excel 12.0 Xml;HDR=YES;IMEX=1";`).
- Excel support is currently read-only in ASP4 (`SELECT` queries only).
- For ODBC, use `DSN=...;Uid=...;Pwd=...;` or `Driver={...};Server=...;Database=...;Uid=...;Pwd=...;`.
- PostgreSQL is supported via ODBC (`Provider=PostgreSQL;Server=...;Database=...;User Id=...;Password=...;Port=5432;`) or explicit `Driver={PostgreSQL ...}` / `DSN=...`.
- SQL dialect translation is not performed; application SQL is executed as-is by the selected provider/driver.
- Internally, provider adapters now use a registry + capability flags, so future DBMS support can be added as pluggable adapters without changing the ADO surface API.

## ADODB.Recordset

```vbscript
Set rs = Server.CreateObject("ADODB.Recordset")
```

| Property/Method | Description |
|----------------|-------------|
| `State` | Recordset state |
| `EOF` | End of file |
| `BOF` | Beginning of file |
| `RecordCount` | Number of records |
| `Fields` | Fields collection |
| `Open([source[, active_conn[, cursor_type[, lock_type[, options]]]]])` | Opens recordset |
| `Close()` | Closes recordset |
| `MoveFirst()` | Moves to first record |
| `MoveLast()` | Moves to last record |
| `MoveNext()` | Moves to next record |
| `MovePrevious()` | Moves to previous record |
| `Move(n)` | Moves n records |
| `AddNew()` | Starts insert mode for a new record |
| `Update()` | Commits pending field changes |
| `Delete()` | Deletes current record |
| `Resync` | Resyncs with database |

## ADODB.Command

```vbscript
Set cmd = Server.CreateObject("ADODB.Command")
```

| Property/Method | Description |
|----------------|-------------|
| `ActiveConnection` | Connection used for execution |
| `CommandText` | SQL command text |
| `CommandType` | Command type (text) |
| `Parameters` | Parameters collection |
| `CreateParameter(...)` | Creates a parameter object |
| `Execute(...)` | Executes command and returns a recordset |

## ADODB.Parameter / Parameters

| Property/Method | Description |
|----------------|-------------|
| `Name` | Parameter name |
| `Type` | ADO type constant |
| `Direction` | Direction (`adParamInput`, etc.) |
| `Size` | Declared size |
| `Value` | Parameter value |
| `Parameters.Append(param)` | Adds parameter |
| `Parameters.Item(name_or_index)` | Gets parameter |
| `Parameters.Count` | Number of parameters |

## ADODB.Stream

```vbscript
Set stream = Server.CreateObject("ADODB.Stream")
```

| Property/Method | Description |
|----------------|-------------|
| `Type` | Stream type (1=Binary, 2=Text) |
| `Charset` | Character set |
| `Position` | Current position |
| `Size` | Stream size |
| `EOS` | End of stream |
| `State` | Stream state |
| `LineSeparator` | Line separator |
| `Mode` | Open mode |
| `Open()` | Opens stream |
| `Close()` | Closes stream |
| `LoadFromFile(filename)` | Loads from file |
| `SaveToFile(filename[, options])` | Saves to file |
| `Read([count])` | Reads bytes |
| `ReadText([count])` | Reads text |
| `Write(data)` | Writes bytes |
| `WriteText(string)` | Writes text |
| `CopyTo(dest_stream[, count])` | Copies to another stream |
| `SetEOS()` | Sets EOS |
| `SkipLine()` | Skips line |
| `Flush()` | Flushes buffer |

## MSXML2 Objects

### ServerXMLHTTP

```vbscript
Set http = Server.CreateObject("MSXML2.ServerXMLHTTP")
```

| Property/Method | Description |
|----------------|-------------|
| `ReadyState` | Request state |
| `Status` | HTTP status code |
| `StatusText` | HTTP status text |
| `ResponseText` | Response as text |
| `ResponseXML` | Response as XML DOM |
| `ResponseBody` | Response as binary |
| `Option` | MSXML option |
| `Open(method, url[, async[, user[, password]]])` | Opens request |
| `SetRequestHeader(header, value)` | Sets request header |
| `Send([body])` | Sends request |
| `WaitForResponse([timeout])` | Waits for response |
| `Abort()` | Aborts request |

### XMLHTTP

```vbscript
Set http = Server.CreateObject("MSXML2.XMLHTTP")
```

Same interface as ServerXMLHTTP.

### DOMDocument

```vbscript
Set xml = Server.CreateObject("MSXML2.DOMDocument")
```

| Property/Method | Description |
|----------------|-------------|
| `async` | Async loading |
| `readyState` | Document state |
| `xml` | XML content |
| `text` | Text content |
| `load(url)` | Loads from URL |
| `loadXML(xml_string)` | Loads from string |
| `save(destination)` | Saves document |
| `selectNodes(xpath)` | Selects nodes |
| `selectSingleNode(xpath)` | Selects single node |
| `getElementsByTagName(tagname)` | Gets elements |

## CDO.Message

```vbscript
Set msg = Server.CreateObject("CDO.Message")
```

| Property/Method | Description |
|----------------|-------------|
| `From` | Sender address |
| `To` | Recipient address(es) |
| `CC` | CC recipients |
| `BCC` | BCC recipients |
| `Subject` | Message subject |
| `HTMLBody` | HTML body |
| `TextBody` | Plain text body |
| `BodyPart` | Body part object |
| `Configuration` | Configuration object |
| `DisableSend` | If True, `Send()` is no-op success |
| `AddAttachment(url)` | Adds attachment |
| `Send()` | Sends the message |

## ASP4.POP3

```vbscript
Set pop = Server.CreateObject("ASP4.POP3")
```

| Method | Description |
|--------|-------------|
| `Connect/Open(host[, port[, use_ssl[, timeout]]])` | Connects to POP3 server |
| `Login(user, pass)` | Authenticates |
| `Stat()` | Returns message count and mailbox size |
| `List()` | Returns message listing |
| `UIDL([msg_num])` | UID listing or UID for one message |
| `Retr/GetMessage(msg_num)` | Fetches a message object |
| `Delete/Dele(msg_num)` | Marks message for deletion |
| `DeleteAll()` | Marks all for deletion |
| `Quit/Close()` | Closes connection |

## ASP4.IMAP

```vbscript
Set imap = Server.CreateObject("ASP4.IMAP")
```

| Method | Description |
|--------|-------------|
| `Connect/Open(host[, port[, use_ssl[, timeout]]])` | Connects to IMAP server |
| `Login(user, pass)` | Authenticates |
| `Select([folder[, readonly]])` | Selects mailbox |
| `Search([criteria])` | Finds messages by sequence number |
| `SearchUID([criteria])` | Finds messages by UID |
| `Fetch/GetMessage(msg_num)` | Fetches message by sequence number |
| `GetMessageByUID(uid)` | Fetches message by UID |
| `Delete/Dele(msg_num)` | Marks message deleted |
| `DeleteAll()` | Marks all selected messages deleted |
| `Expunge()` | Permanently removes deleted messages |
| `Logout/Close()` | Closes connection |

## Runtime Environment Variables

| Variable | Description |
|----------|-------------|
| `ASP_PY_LOG` | Enables request log output from built-in server |
| `ASP_PY_TRACE_REQUEST` | Enables verbose request/body trace logging |
| `ASP_PY_REQ_MEM_MAX` | Max in-memory request body bytes before temp-file buffering |
| `ASP_PY_ADO_ROOT` | Sandbox root for `ADODB.Stream` filesystem operations |
| `ASP_PY_FSO_ROOT` | Sandbox root for `Scripting.FileSystemObject` |
| `ASP_PY_HTTP_MAX_BYTES` | Max response bytes for MSXML HTTP requests |
| `ASP_PY_HTTP_ALLOW_HOSTS` | Comma-separated HTTP host allowlist for MSXML |
| `ASP_PY_ALLOW_LOCALHOST` | Allows MSXML HTTP access to localhost |
| `ASP_PY_ALLOW_PRIVATE_NETS` | Allows MSXML HTTP access to private subnets |
| `ASP_PY_XML_ALLOW_LOCAL` | Allows DOMDocument local file loading |
| `ASP_PY_CDO_DISABLE_SEND` | Disables SMTP send in `CDO.Message` |
| `ASP_PY_CDO_ALLOW_OUTSIDE_DOCROOT` | Allows CDO attachments outside docroot |

## VBScript Compatibility Notes

- `UBound/LBound`: follow VBScript-like array allocation rules; uninitialized/invalid-array usage raises runtime errors.
- `VBScript.RegExp.Replace`: supports VB-style replacement tokens (`$1`, `$&`, ``$` ``, `$'`, `$$`).
- `Request.Form`: parsed for `POST` only; non-POST bodies are available via `Request.BinaryRead`.
- Date/number formatting and script-engine metadata helpers are implemented for compatibility and may differ from IIS in edge locale cases.

## Compatibility Matrix

| Subsystem | Level | Notes |
|-----------|-------|-------|
| Core VBScript built-ins | Near | Broad coverage for common Classic ASP apps; edge coercion/locale behaviors can differ |
| Date/time and numeric formatting | Partial | Compatibility-oriented; locale-specific IIS parity not guaranteed |
| Request/Response/Server/Application/Session | Near | Classic object model implemented; some operational semantics differ from IIS hosting internals |
| `VBScript.RegExp` | Near | Common API and VB-style replacement tokens supported |
| `Scripting.Dictionary` | Near | Core collection behavior supported; COM-level quirks may differ |
| `Scripting.FileSystemObject` / `ADODB.Stream` | Partial | Supported in sandboxed model (docroot/root-constrained) |
| `ADODB.Connection/Recordset/Command` | Partial | Provider support is runtime-dependent; ADO surface is compatibility-oriented |
| Database providers | Partial | SQLite, Access, Excel(read-only), generic ODBC, PostgreSQL via ODBC |
| MSXML HTTP/DOM shims | Partial | Security-guarded and stdlib-focused; not full MSXML COM parity |
| `CDO.Message` | Partial | Practical SMTP/pickup subset; not complete CDOSYS feature parity |
| POP3/IMAP shims | Partial | Legacy-friendly subset for mailbox workflows |

---

# Global.asa Support

ASP4 supports the Global.asa file with the following events:

- `Application_OnStart`
- `Application_OnEnd`
- `Session_OnStart`
- `Session_OnEnd`

Example Global.asa:
```asp
<script language="vbscript" runat="server">
Sub Application_OnStart
    Application("StartTime") = Now()
End Sub

Sub Session_OnStart
    Session("UserID") = ""
End Sub
</script>
```

---

# Running ASP4

Start the built-in server:

```bash
python -m ASP4.server [host] [port] [docroot]
```

Example:
```bash
python -m ASP4.server 0.0.0.0 8080 www
```

The server will serve both static files and .asp pages from the specified document root.
