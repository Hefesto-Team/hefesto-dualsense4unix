"""O `shortcuts.vdf`: os jogos de fora que a Steam guarda em VDF binário, por conta.

Cada entrada tem o número do atalho (o mesmo que o `CompatToolMapping` e o `SteamAppId` usam, sem
sinal), o nome, o executável e as opções de lançamento. Este módulo só lê e só troca as opções de
UMA entrada: os bytes de fora do valor trocado passam iguais. Sem rede, sem Steam, sem disco além
do arquivo que recebe.
"""
from __future__ import annotations

import struct
import zlib
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

NOME_DO_ARQUIVO = "shortcuts.vdf"

_DICIONARIO = 0x00
_TEXTO = 0x01
_INTEIRO = 0x02
_REAL = 0x03
_PONTEIRO = 0x04
_TEXTO_LARGO = 0x05
_COR = 0x06
_INTEIRO_LARGO = 0x07
_FIM = 0x08
_INTEIRO_COM_SINAL = 0x0A

_TAMANHO_DO_VALOR = {
    _INTEIRO: 4, _REAL: 4, _PONTEIRO: 4, _COR: 4, _INTEIRO_LARGO: 8, _INTEIRO_COM_SINAL: 8,
}
_ESCAPE = "surrogateescape"


class AtalhoDeFora(NamedTuple):
    """Um jogo de fora da Steam: o número sem sinal, o nome, o executável e as opções."""

    appid: str
    nome: str
    exe: str
    opcoes: str

    @property
    def e_do_windows(self) -> bool:
        """O executável é de Windows (`.exe`, `.bat`, `.cmd`): só ele precisa do Proton."""
        exe = self.exe.strip().strip("\"'").lower()
        return exe.endswith((".exe", ".bat", ".cmd"))


@dataclass(frozen=True)
class _Campo:
    tipo: int
    chave: str
    valor: bytes | list[_Campo]
    valor_ini: int
    valor_fim: int


def _cstring(buf: bytes, pos: int) -> tuple[bytes, int]:
    fim = buf.find(b"\0", pos)
    if fim < 0:
        raise ValueError(f"texto sem fim na posição {pos}")
    return buf[pos:fim], fim + 1


def _dicionario(buf: bytes, pos: int) -> tuple[list[_Campo], int, int]:
    """Os campos de um dicionário a partir de ``pos``; devolve também onde fica o byte de fim."""
    campos: list[_Campo] = []
    while True:
        if pos >= len(buf):
            raise ValueError("o arquivo termina no meio de um dicionário")
        tipo = buf[pos]
        if tipo == _FIM:
            return campos, pos, pos + 1
        chave_bruta, pos = _cstring(buf, pos + 1)
        chave = chave_bruta.decode("utf-8", _ESCAPE)
        if tipo == _DICIONARIO:
            ini = pos
            filhos, _, pos = _dicionario(buf, pos)
            campos.append(_Campo(tipo, chave, filhos, ini, pos))
        elif tipo in (_TEXTO, _TEXTO_LARGO):
            ini = pos
            valor, pos = _cstring(buf, pos)
            campos.append(_Campo(tipo, chave, valor, ini, ini + len(valor)))
        elif tipo in _TAMANHO_DO_VALOR:
            ini = pos
            pos += _TAMANHO_DO_VALOR[tipo]
            if pos > len(buf):
                raise ValueError("o arquivo termina no meio de um número")
            campos.append(_Campo(tipo, chave, buf[ini:pos], ini, pos))
        else:
            raise ValueError(f"tipo {tipo:#04x} desconhecido na posição {pos - 1}")


def _entradas(bruto: bytes) -> list[tuple[list[_Campo], int]]:
    """As entradas do arquivo e, de cada uma, a posição do byte de fim do seu dicionário."""
    if not bruto.startswith(b"\x00"):
        raise ValueError("não é um shortcuts.vdf: não abre com um dicionário")
    raiz, pos = _cstring(bruto, 1)
    if raiz.lower() != b"shortcuts":
        raise ValueError("não é um shortcuts.vdf: a raiz não é `shortcuts`")
    achadas: list[tuple[list[_Campo], int]] = []
    while True:
        if pos >= len(bruto):
            raise ValueError("o arquivo termina no meio de `shortcuts`")
        if bruto[pos] == _FIM:
            return achadas
        if bruto[pos] != _DICIONARIO:
            raise ValueError(f"entrada de tipo {bruto[pos]:#04x} em `shortcuts` (posição {pos})")
        _, pos = _cstring(bruto, pos + 1)
        campos, fim, pos = _dicionario(bruto, pos)
        achadas.append((campos, fim))


def _texto_de(campos: list[_Campo], chave: str) -> _Campo | None:
    for campo in campos:
        if campo.chave.lower() == chave and campo.tipo in (_TEXTO, _TEXTO_LARGO):
            return campo
    return None


def _decodificar(campo: _Campo | None) -> str:
    if campo is None or not isinstance(campo.valor, bytes):
        return ""
    return campo.valor.decode("utf-8", _ESCAPE)


def _appid(campos: list[_Campo], exe: str, nome: str) -> str:
    """O número sem sinal da entrada: o campo `appid`, ou o que a Steam deriva do exe e do nome."""
    for campo in campos:
        if campo.chave.lower() == "appid" and campo.tipo == _INTEIRO \
                and isinstance(campo.valor, bytes):
            return str(struct.unpack("<I", campo.valor)[0])
    derivado = zlib.crc32((exe + nome).encode("utf-8", _ESCAPE)) | 0x80000000
    return str(derivado)


def atalhos_do_bruto(bruto: bytes) -> list[AtalhoDeFora]:
    """Os jogos de fora do arquivo; ``ValueError`` se ele não é um `shortcuts.vdf` inteiro."""
    achados: list[AtalhoDeFora] = []
    for campos, _ in _entradas(bruto):
        nome = _decodificar(_texto_de(campos, "appname"))
        exe = _decodificar(_texto_de(campos, "exe"))
        achados.append(AtalhoDeFora(
            _appid(campos, exe, nome), nome, exe, _decodificar(_texto_de(campos, "launchoptions"))
        ))
    return achados


def atalhos_do_arquivo(arquivo: Path) -> list[AtalhoDeFora]:
    """Os jogos de fora de ``arquivo``; vazio se ele não existe ou não se lê. Nunca levanta."""
    try:
        return atalhos_do_bruto(arquivo.read_bytes())
    except (OSError, ValueError):
        return []


def os_que_nao_abrem(raiz: Path) -> list[str]:
    """O motivo de cada arquivo de jogos de fora sob ``raiz`` que o produto não lê inteiro.

    Cortado, ou bytes que não são VDF binário, ou ilegível. Arquivo ausente não é quebra; o arquivo
    que abre com entrada sem nome ou sem executável é de :func:`entradas_sem_nome_ou_executavel`.
    """
    motivos: list[str] = []
    for arquivo in sorted((raiz / "userdata").glob(f"*/config/{NOME_DO_ARQUIVO}")):
        try:
            atalhos_do_bruto(arquivo.read_bytes())
        except OSError as erro:
            motivos.append(str(erro.strerror))
        except ValueError as erro:
            motivos.append(str(erro))
    return motivos


def entradas_sem_nome_ou_executavel(raiz: Path) -> int:
    """Quantas entradas, nos arquivos de jogos de fora que ABREM inteiros sob ``raiz``, não têm nome
    ou não têm executável: os dois campos que o catálogo e o pino usam."""
    total = 0
    for arquivo in sorted((raiz / "userdata").glob(f"*/config/{NOME_DO_ARQUIVO}")):
        try:
            atalhos = atalhos_do_bruto(arquivo.read_bytes())
        except (OSError, ValueError):
            continue
        total += sum(1 for atalho in atalhos if not atalho.nome or not atalho.exe)
    return total


def com_as_opcoes(bruto: bytes, appid: str, opcoes: str) -> bytes:
    """O arquivo com as opções de lançamento de UMA entrada trocadas; o resto passa igual.

    ``ValueError`` se o arquivo não se lê inteiro ou nenhuma entrada tem esse número. A entrada
    sem o campo `LaunchOptions` ganha o campo no fim do seu dicionário.
    """
    novo = opcoes.encode("utf-8", _ESCAPE)
    if b"\0" in novo:
        raise ValueError("as opções não podem ter o byte zero")
    for campos, fim in _entradas(bruto):
        nome = _decodificar(_texto_de(campos, "appname"))
        exe = _decodificar(_texto_de(campos, "exe"))
        if _appid(campos, exe, nome) != str(appid):
            continue
        alvo = _texto_de(campos, "launchoptions")
        if alvo is None:
            return bruto[:fim] + b"\x01LaunchOptions\x00" + novo + b"\x00" + bruto[fim:]
        return bruto[: alvo.valor_ini] + novo + bruto[alvo.valor_fim :]
    raise ValueError(f"nenhum atalho com o número {appid}")
