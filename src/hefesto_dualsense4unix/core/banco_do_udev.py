"""O que o udev sabe de um nó, perguntado à biblioteca dele e não ao arquivo dele.

O banco do udev (`/run/udev/data/c<maj>:<min>`) é interno do systemd: ele o
declara assim e muda o formato quando quer. Ler o arquivo à mão é ler o que
ninguém prometeu, e o sintoma de uma mudança seria silêncio (a propriedade some
e o nó é tratado como "sem marca"). Quem tem o contrato é a `libudev`, e é ela
que este módulo chama, por `ctypes` (stdlib): nenhuma dependência nova no
pacote, e o mesmo caminho serve ao daemon, ao Flatpak e ao `python3` do sistema.

**Só stdlib e sem importar o pacote**, de propósito: o `sinal_da_barra` roda
fora do daemon, e este módulo não pode puxar nada atrás de si.

Resposta ausente é "não sei" (`None`): sem a biblioteca, sem o nó ou sem a
propriedade, o chamador decide o que "não sei" significa para ele. Nenhuma
função aqui levanta.
"""

from __future__ import annotations

import ctypes
import threading
from typing import Any

__all__ = ["propriedade_do_devnum", "propriedade_do_syspath"]

_TRAVA = threading.Lock()
_BIBLIOTECA: Any = None  # None = ainda não tentou; False = não há


def _biblioteca() -> Any:
    """A `libudev` com as assinaturas postas, carregada uma vez. `None` = não há."""
    global _BIBLIOTECA
    with _TRAVA:
        if _BIBLIOTECA is None:
            try:
                lib = ctypes.CDLL("libudev.so.1", use_errno=True)
                lib.udev_new.restype = ctypes.c_void_p
                lib.udev_new.argtypes = []
                lib.udev_unref.restype = ctypes.c_void_p
                lib.udev_unref.argtypes = [ctypes.c_void_p]
                lib.udev_device_new_from_devnum.restype = ctypes.c_void_p
                lib.udev_device_new_from_devnum.argtypes = [
                    ctypes.c_void_p, ctypes.c_char, ctypes.c_ulong]
                lib.udev_device_new_from_syspath.restype = ctypes.c_void_p
                lib.udev_device_new_from_syspath.argtypes = [
                    ctypes.c_void_p, ctypes.c_char_p]
                lib.udev_device_get_property_value.restype = ctypes.c_char_p
                lib.udev_device_get_property_value.argtypes = [
                    ctypes.c_void_p, ctypes.c_char_p]
                lib.udev_device_unref.restype = ctypes.c_void_p
                lib.udev_device_unref.argtypes = [ctypes.c_void_p]
                _BIBLIOTECA = lib
            except (OSError, AttributeError):
                _BIBLIOTECA = False
        return _BIBLIOTECA or None


def _propriedade(abrir: str, argumento: tuple[Any, ...], nome: str) -> str | None:
    lib = _biblioteca()
    if lib is None:
        return None
    contexto = lib.udev_new()
    if not contexto:
        return None
    try:
        dispositivo = getattr(lib, abrir)(contexto, *argumento)
        if not dispositivo:
            return None
        try:
            valor = lib.udev_device_get_property_value(dispositivo, nome.encode("ascii"))
        finally:
            lib.udev_device_unref(dispositivo)
        return None if valor is None else valor.decode("utf-8", errors="replace")
    except (ctypes.ArgumentError, UnicodeError, OSError):
        return None
    finally:
        lib.udev_unref(contexto)


def propriedade_do_devnum(tipo: str, devnum: int, nome: str) -> str | None:
    """A propriedade ``nome`` do nó de ``devnum`` (`st_rdev`); ``tipo`` é ``"c"`` ou ``"b"``."""
    if tipo not in ("c", "b"):
        return None
    return _propriedade("udev_device_new_from_devnum", (tipo.encode("ascii"), devnum), nome)


def propriedade_do_syspath(syspath: str, nome: str) -> str | None:
    """A propriedade ``nome`` do dispositivo em ``/sys/...`` (ex.: ``USEC_INITIALIZED``)."""
    return _propriedade("udev_device_new_from_syspath", (str(syspath).encode("utf-8"),), nome)
