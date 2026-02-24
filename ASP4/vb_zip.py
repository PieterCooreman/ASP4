"""Zip utility shim for VBScript."""

from __future__ import annotations

import os
import zipfile

from .vb_runtime import VBScriptRuntimeError, vbs_cstr
from .vm.values import VBEmpty, VBNull, VBNothing


class ZipShim:
    def Zip(self, path, out_path=None):
        if path is VBEmpty or path is VBNull or path is VBNothing or path is None:
            raise VBScriptRuntimeError("Zip: path is required")
        src = vbs_cstr(path)
        if src == "":
            raise VBScriptRuntimeError("Zip: path is required")
        if not os.path.exists(src):
            raise VBScriptRuntimeError("Zip: path not found")
        if not os.path.isabs(src):
            raise VBScriptRuntimeError("Zip: path must be a physical path")

        if out_path is VBEmpty or out_path is VBNull or out_path is VBNothing or out_path is None:
            out_path = ""
        out_path = vbs_cstr(out_path) if out_path != "" else (src + ".zip")
        if out_path == "":
            raise VBScriptRuntimeError("Zip: output path is required")
        if not os.path.isabs(out_path):
            raise VBScriptRuntimeError("Zip: output must be a physical path")
        if os.path.isdir(src):
            _zip_folder(src, out_path)
        else:
            _zip_file(src, out_path)
        return out_path

    def Unzip(self, zip_path, dest_folder, overwrite=True):
        if zip_path is VBEmpty or zip_path is VBNull or zip_path is VBNothing or zip_path is None:
            raise VBScriptRuntimeError("Unzip: zip file is required")
        if dest_folder is VBEmpty or dest_folder is VBNull or dest_folder is VBNothing or dest_folder is None:
            raise VBScriptRuntimeError("Unzip: destination folder is required")
        zp = vbs_cstr(zip_path)
        dst = vbs_cstr(dest_folder)
        if zp == "" or dst == "":
            raise VBScriptRuntimeError("Unzip: zip file and destination are required")
        if not os.path.exists(zp):
            raise VBScriptRuntimeError("Unzip: zip file not found")
        if not os.path.isabs(dst):
            raise VBScriptRuntimeError("Unzip: destination must be a physical path")

        os.makedirs(dst, exist_ok=True)
        with zipfile.ZipFile(zp, "r") as zf:
            _safe_extractall(zf, dst, overwrite=bool(overwrite))
        return dst


def _zip_file(src, out_path):
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(src, arcname=os.path.basename(src))


def _zip_folder(src, out_path):
    base = os.path.basename(os.path.normpath(src))
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        added_dir = False
        for root, dirs, files in os.walk(src):
            rel_root = os.path.relpath(root, src)
            rel_root = "" if rel_root == "." else rel_root
            if not files and not dirs:
                arc_dir = os.path.join(base, rel_root) + "/"
                zf.writestr(arc_dir, "")
                added_dir = True
            for fname in files:
                full = os.path.join(root, fname)
                arc = os.path.join(base, rel_root, fname)
                zf.write(full, arcname=arc)
        if not added_dir and not any(os.scandir(src)):
            zf.writestr(base + "/", "")


def _safe_extractall(zf: zipfile.ZipFile, dest: str, overwrite: bool = True):
    base = os.path.abspath(dest)
    for info in zf.infolist():
        name = info.filename
        if name.startswith("/") or name.startswith("\\"):
            raise VBScriptRuntimeError("Unzip: invalid entry path")
        target = os.path.abspath(os.path.join(base, name))
        if not target.startswith(base + os.sep) and target != base:
            raise VBScriptRuntimeError("Unzip: blocked path traversal")
        if not overwrite and os.path.exists(target) and not target.endswith(os.sep):
            raise VBScriptRuntimeError("Unzip: target exists")
    zf.extractall(dest)
