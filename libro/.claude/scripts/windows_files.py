"""Operaciones nativas para Windows 10/11. Sin seguir junctions ni reparse points.

Los handles de los directorios permanecen abiertos sin FILE_SHARE_DELETE durante
cada operación. El diario, hashes, candidatos y decisiones siguen en Book.
"""
import contextlib
import ctypes
from ctypes import wintypes as w
import msvcrt
import os
from pathlib import Path
import uuid
import weakref

from schemas import require, Problem

k = ctypes.WinDLL('kernel32', use_last_error=True)


def api(name, arguments, result=w.BOOL):
    fn = getattr(k, name)
    fn.argtypes, fn.restype = arguments, result
    return fn


create = api('CreateFileW', [w.LPCWSTR, w.DWORD, w.DWORD, ctypes.c_void_p, w.DWORD, w.DWORD, w.HANDLE], w.HANDLE)
close = api('CloseHandle', [w.HANDLE])
move = api('MoveFileExW', [w.LPCWSTR, w.LPCWSTR, w.DWORD])
open_process = api('OpenProcess', [w.DWORD, w.BOOL, w.DWORD], w.HANDLE)
process_times = api('GetProcessTimes', [w.HANDLE, ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME), ctypes.POINTER(w.FILETIME)])
exit_code = api('GetExitCodeProcess', [w.HANDLE, ctypes.POINTER(w.DWORD)])


class FileInfo(ctypes.Structure):
    _fields_ = [('attributes', w.DWORD), ('created', w.FILETIME), ('accessed', w.FILETIME),
                ('written', w.FILETIME), ('volume', w.DWORD), ('size_high', w.DWORD),
                ('size_low', w.DWORD), ('links', w.DWORD), ('index_high', w.DWORD), ('index_low', w.DWORD)]


file_info = api('GetFileInformationByHandle', [w.HANDLE, ctypes.POINTER(FileInfo)])
file_type = api('GetFileType', [w.HANDLE], w.DWORD)


def handle(path, *, directory=False, write=False):
    flags = 0x00200000 | (0x02000000 if directory else 0)  # OPEN_REPARSE_POINT, BACKUP_SEMANTICS
    access = 0 if directory else (0x40000000 if write else 0x80000000)
    h = create(str(path), access, 3 if directory else 1, None, 1 if write else 3, flags, None)
    if h == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = FileInfo()
        if not file_info(h, ctypes.byref(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        require(file_type(h) == 1, 'El destino no es un archivo de disco.', 'path-outside-scope')
        require(not info.attributes & 0x400, 'No se siguen enlaces, junctions ni puntos de reanálisis.', 'path-outside-scope')
        require(bool(info.attributes & 0x10) == directory, 'Tipo de archivo inesperado.', 'path-outside-scope')
        require(directory or info.links == 1, 'No se permiten archivos con enlaces físicos.', 'path-outside-scope')
        return h
    except BaseException:
        close(h)
        raise


def identity(pid):
    h = open_process(0x1000, False, pid)
    if not h:
        return None
    try:
        times = [w.FILETIME() for _ in range(4)]
        if not process_times(h, *(ctypes.byref(t) for t in times)):
            return None
        return 'windows:' + str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
    finally:
        close(h)


def dead(pid):
    h = open_process(0x1000, False, pid)
    if not h:
        return ctypes.get_last_error() == 87  # PID no existe; acceso denegado no demuestra muerte.
    try:
        code = w.DWORD()
        return bool(exit_code(h, ctypes.byref(code))) and code.value != 259
    finally:
        close(h)


class WindowsFiles:
    def __init__(self, book):
        self.book = weakref.proxy(book)
        require(not str(book.root).startswith('\\\\'), 'Use una carpeta local para el libro, no una ruta de red.', 'path-outside-scope')
        self.handles = []
        try:
            for directory in reversed([book.root, *book.root.parents]):
                self.handles.append(handle(directory, directory=True))
        except BaseException:
            self.close()
            raise

    def close(self):
        for h in reversed(self.handles):
            close(h)
        self.handles.clear()

    @contextlib.contextmanager
    def parent(self, relative, create_dirs=False):
        target = self.book.path(relative)
        handles = []
        try:
            # Abrir todos los antecesores evita cambiar cualquiera de ellos por un junction.
            for directory in reversed([target.parent, *target.parent.parents]):
                if create_dirs and not directory.exists():
                    directory.mkdir()
                handles.append(handle(directory, directory=True))
            yield target
        finally:
            for h in reversed(handles):
                close(h)

    def read(self, relative, shared=False, max_bytes=None):
        self.book.path(relative, shared=shared)
        try:
            with self.parent(relative) as target:
                h = handle(target)
                fd = msvcrt.open_osfhandle(h, os.O_RDONLY | os.O_BINARY)
                with os.fdopen(fd, 'rb') as stream:
                    data = stream.read() if max_bytes is None else stream.read(max_bytes + 1)
                    require(max_bytes is None or len(data) <= max_bytes, 'El archivo supera el límite autorizado de lectura.', 'invalid-input')
                    return data
        except FileNotFoundError:
            return None

    def unlink(self, relative):
        with self.parent(relative) as target:
            target.unlink()

    def new_directory(self, relative):
        with self.parent(relative, True) as target:
            try:
                target.mkdir()
            except FileExistsError as exc:
                raise Problem('invalid-input', 'El directorio de destino ya existe; no se reutiliza.') from exc

    def write(self, relative, data, *, exclusive=False, expected=None, shared=False):
        from book import sha
        with self.parent(relative, True) as target:
            temporary = target.with_name('.book-' + uuid.uuid4().hex)
            h = handle(temporary, write=True)
            fd = msvcrt.open_osfhandle(h, os.O_WRONLY | os.O_BINARY)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                if shared:
                    require(sha(self.book.read(relative, shared=True)) == expected, 'El texto cambió antes de guardar. La propuesta permanece separada.', 'stale-base')
                # WRITE_THROUGH; omitir REPLACE_EXISTING hace exclusiva una creación.
                flags = 8 | (0 if exclusive else 1)
                if not move(str(temporary), str(target), flags):
                    error = ctypes.get_last_error()
                    if shared and error in (80, 183):
                        raise Problem('stale-base', 'El archivo ya existe; se conserva sin cambios.')
                    raise ctypes.WinError(error)
            finally:
                temporary.unlink(missing_ok=True)
