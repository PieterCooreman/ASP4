"""VBScript built-in constants (Script 5.6 documentation set).

NOTE: runner_vm re-injects this module into the script environment LAST so
these names always win over Python-level imports leaked by the dir()-based
scans of other modules (e.g. the VBNull/VBEmpty sentinels or the VBArray
class would otherwise shadow vbNull=1 / vbEmpty=0 / vbArray=8192).
"""

# Day-of-week constants
vbUseSystemDayOfWeek = 0
vbSunday = 1
vbMonday = 2
vbTuesday = 3
vbWednesday = 4
vbThursday = 5
vbFriday = 6
vbSaturday = 7

# First-week-of-year constants
vbUseSystem = 0
vbFirstJan1 = 1
vbFirstFourDays = 2
vbFirstFullWeek = 3

# FormatDateTime constants
vbGeneralDate = 0
vbLongDate = 1
vbShortDate = 2
vbLongTime = 3
vbShortTime = 4

# InStr / comparison constants
vbBinaryCompare = 0
vbTextCompare = 1

vbObjectError = -2147221504

# Color constants (vsconcolor)
vbBlack = 0x00
vbRed = 0xFF
vbGreen = 0xFF00
vbYellow = 0xFFFF
vbBlue = 0xFF0000
vbMagenta = 0xFF00FF
vbCyan = 0xFFFF00
vbWhite = 0xFFFFFF

# MsgBox parameter constants (vsconmsgbox) - button types
vbOKOnly = 0
vbOKCancel = 1
vbAbortRetryIgnore = 2
vbYesNoCancel = 3
vbYesNo = 4
vbRetryCancel = 5
# - icon types
vbCritical = 16
vbQuestion = 32
vbExclamation = 48
vbInformation = 64
# - default button
vbDefaultButton1 = 0
vbDefaultButton2 = 256
vbDefaultButton3 = 512
vbDefaultButton4 = 768
# - modality / extras
vbApplicationModal = 0
vbSystemModal = 4096
vbMsgBoxHelpButton = 16384
vbMsgBoxSetForeground = 65536
vbMsgBoxRight = 524288
vbMsgBoxRtlReading = 1048576

# MsgBox return value constants (vsconmsgbox)
vbOK = 1
vbCancel = 2
vbAbort = 3
vbRetry = 4
vbIgnore = 5
vbYes = 6
vbNo = 7

# VarType constants (vsconvartype)
vbEmpty = 0
vbNull = 1
vbInteger = 2
vbLong = 3
vbSingle = 4
vbDouble = 5
vbCurrency = 6
vbDate = 7
vbString = 8
vbObject = 9
vbError = 10
vbBoolean = 11
vbVariant = 12
vbDataObject = 13
vbDecimal = 14
vbByte = 17
vbArray = 8192
