"""O leitor do estado do jogo: lê só os endereços que a receita declara e publica os valores.

A extensão nunca recebe acesso ao processo do jogo. A receita declara os valores (o nome, o
módulo, a cadeia de ponteiros, o tipo e o ``hz``); o leitor, pai do jogo, segue cada cadeia por
``process_vm_readv`` e devolve ``{nome: valor, t}``. Com ``ptrace_scope=1`` só um ancestral lê:
por isso o leitor entra na frente do ``argv`` do jogo (``--pai``) e o espera.

A trava vem antes de qualquer leitura: a chave «Memória» do jogo ligada (quem a grava é o
Hefesto, nunca a extensão), o aviso de anticheat visto quando o jogo está na lista e o
``buildid`` de agora dentro da faixa da receita.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import errno
import json
import os
import re
import secrets
import struct
import sys
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HZ_MAXIMO = 30
ENTRADAS_POR_RECEITA = 64
ELOS_DA_CADEIA = 8
TIPOS: dict[str, str] = {
    "i8": "<b", "u8": "<B", "i16": "<h", "u16": "<H", "i32": "<i", "u32": "<I",
    "i64": "<q", "u64": "<Q", "f32": "<f", "f64": "<d",
}
COMPARACOES = ("igual", "subiu", "desceu", "nao_mudou")
TETO_DA_VARREDURA = 256 * 1024 * 1024
BLOCO_DA_VARREDURA = 1024 * 1024
CANDIDATOS_SEM_VALOR = 1_000_000
NOME_DA_ENTRADA = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
TOPICO_DA_MEMORIA = "jogo.memoria"
ANTICHEAT = Path(__file__).with_name("anticheat_conhecido.json")


class LeituraRecusadaError(Exception):
    """A leitura não começa (ou parou); ``frase`` diz por quê, numa frase."""

    def __init__(self, frase: str) -> None:
        super().__init__(frase)
        self.frase = frase


class AvisoDoAnticheatError(LeituraRecusadaError):
    """O jogo está na lista de anticheat e o aviso do risco à conta ainda não foi visto."""


@dataclass(frozen=True)
class Entrada:
    nome: str
    modulo: str
    cadeia: tuple[int, ...]
    tipo: str
    hz: float


def entradas_da_receita(lista: Sequence[Mapping[str, Any]]) -> tuple[Entrada, ...]:
    """A lista declarada, conferida: nome curto, tipo conhecido, cadeia de 1 a 8 elos, ``hz`` até
    30. Qualquer linha fora disso recusa a lista inteira."""
    if not isinstance(lista, Sequence) or not lista or len(lista) > ENTRADAS_POR_RECEITA:
        raise LeituraRecusadaError(
            f"A receita declara de 1 a {ENTRADAS_POR_RECEITA} valores para ler.")
    entradas = []
    for linha in lista:
        try:
            nome = str(linha["nome"])
            modulo = str(linha.get("modulo") or "")  # (noqa-acento)
            cadeia = tuple(int(x) for x in linha["cadeia_de_ponteiros"])
            tipo = str(linha["tipo"])
            hz = float(linha.get("hz", HZ_MAXIMO))
        except (KeyError, TypeError, ValueError) as exc:
            raise LeituraRecusadaError("Uma linha da receita não tem a forma declarada.") from exc
        if not NOME_DA_ENTRADA.match(nome):
            raise LeituraRecusadaError(f"O nome «{nome}» não serve para um valor da receita.")
        if tipo not in TIPOS:
            raise LeituraRecusadaError(f"O tipo «{tipo}» não é um dos que o leitor conhece.")
        if not 1 <= len(cadeia) <= ELOS_DA_CADEIA or any(x < 0 for x in cadeia):
            raise LeituraRecusadaError(f"A cadeia de «{nome}» precisa de 1 a 8 deslocamentos.")
        if not 0 < hz <= HZ_MAXIMO:
            raise LeituraRecusadaError(f"«{nome}» pede mais de {HZ_MAXIMO} leituras por segundo.")
        entradas.append(Entrada(nome, modulo, cadeia, tipo, hz))
    if len({e.nome for e in entradas}) != len(entradas):
        raise LeituraRecusadaError("A receita repete um nome.")
    return tuple(entradas)


class _IoVec(ctypes.Structure):
    _fields_ = [("iov_base", ctypes.c_void_p), ("iov_len", ctypes.c_size_t)]


_LIBC: Any = None


def _libc() -> Any:
    global _LIBC
    if _LIBC is None:
        _LIBC = ctypes.CDLL(ctypes.util.find_library("c") or "libc.so.6", use_errno=True)
        _LIBC.process_vm_readv.restype = ctypes.c_ssize_t
        _LIBC.process_vm_readv.argtypes = [
            ctypes.c_int, ctypes.POINTER(_IoVec), ctypes.c_ulong,
            ctypes.POINTER(_IoVec), ctypes.c_ulong, ctypes.c_ulong]
    return _LIBC


def ler_bytes(pid: int, endereco: int, tamanho: int) -> bytes:
    """``tamanho`` bytes do processo ``pid`` em ``endereco``, por ``process_vm_readv``."""
    destino = ctypes.create_string_buffer(tamanho)
    local = _IoVec(ctypes.cast(destino, ctypes.c_void_p), tamanho)
    remoto = _IoVec(ctypes.c_void_p(endereco), tamanho)
    lidos = _libc().process_vm_readv(pid, ctypes.byref(local), 1, ctypes.byref(remoto), 1, 0)
    if lidos == tamanho:
        return destino.raw
    erro = ctypes.get_errno()
    if erro == errno.EPERM:
        raise LeituraRecusadaError("O jogo não nasceu do leitor: o sistema recusa a leitura.")
    if erro == errno.ESRCH:
        raise LeituraRecusadaError("O jogo fechou.")
    raise LeituraRecusadaError("O endereço declarado está fora da memória do jogo.")


def base_do_modulo(pid: int, modulo: str) -> int:
    """Onde o módulo (o nome do arquivo) começa no jogo; ``0`` para endereço absoluto."""
    if not modulo:
        return 0
    try:
        linhas = Path(f"/proc/{pid}/maps").read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise LeituraRecusadaError("O jogo fechou.") from exc
    for linha in linhas.splitlines():
        partes = linha.split(maxsplit=5)
        if len(partes) == 6 and Path(partes[5]).name == modulo and int(partes[2], 16) == 0:
            return int(partes[0].split("-")[0], 16)
    raise LeituraRecusadaError(f"O módulo «{modulo}» não está carregado no jogo.")


def resolver(pid: int, entrada: Entrada) -> int:
    """O endereço final: a base do módulo mais o primeiro deslocamento; cada elo seguinte lê o
    ponteiro de 8 bytes e soma o deslocamento dele."""
    endereco = base_do_modulo(pid, entrada.modulo) + entrada.cadeia[0]
    for deslocamento in entrada.cadeia[1:]:
        endereco = struct.unpack("<Q", ler_bytes(pid, endereco, 8))[0] + deslocamento
    return endereco


def ler_valor(pid: int, entrada: Entrada) -> int | float:
    formato = TIPOS[entrada.tipo]
    bruto = ler_bytes(pid, resolver(pid, entrada), struct.calcsize(formato))
    valor: int | float = struct.unpack(formato, bruto)[0]
    return valor


def conferir_buildid(atual: str | int | None, faixa: Mapping[str, Any] | None) -> None:
    """Recusa quando o ``buildid`` de agora está fora da faixa ``{min, max}`` da receita."""
    if not faixa:
        return
    try:
        numero = int(str(atual))
    except ValueError as exc:
        raise LeituraRecusadaError("A versão do jogo não se leu; a receita não vale.") from exc
    menor, maior = faixa.get("min"), faixa.get("max")
    if (menor is not None and numero < int(menor)) or (maior is not None and numero > int(maior)):
        raise LeituraRecusadaError(
            f"A versão do jogo ({numero}) está fora da faixa da receita; nada se lê.")


def anticheat_do_jogo(pasta: Path | None, appid: str | None = None,
                      lista: Path = ANTICHEAT) -> str:
    """O anticheat conhecido do jogo (o nome), pela lista do ``appid`` e pelos marcadores de
    arquivo na pasta; vazio quando nenhum casa."""
    dados = json.loads(lista.read_text(encoding="utf-8"))
    por_appid: Mapping[str, str] = dados.get("por_appid") or {}
    if appid and str(appid) in por_appid:
        return str(por_appid[str(appid)])
    if pasta is None or not pasta.is_dir():
        return ""
    marcadores: Mapping[str, Sequence[str]] = dados.get("marcadores") or {}
    nomes = {p.name.lower() for p in _arquivos_rasos(pasta)}
    for anticheat, achados in marcadores.items():
        if any(m.lower() in nomes for m in achados):
            return str(anticheat)
    return ""


def _arquivos_rasos(pasta: Path, fundo: int = 3) -> Iterable[Path]:
    raiz = len(pasta.parts)
    vistos = 0
    for atual, pastas, arquivos in os.walk(pasta):
        for nome in (*pastas, *arquivos):
            vistos += 1
            if vistos > 20_000:
                return
            yield Path(atual) / nome
        if len(Path(atual).parts) - raiz >= fundo:
            pastas.clear()


class ChavesDaMemoria:
    """A chave «Memória» de cada jogo: nasce desligada e só o Hefesto a grava.

    Ligar num jogo com anticheat pede o aviso visto antes; o aviso não impede.
    """

    def __init__(self, arquivo: Path) -> None:
        self.arquivo = arquivo

    def _ler(self) -> dict[str, dict[str, Any]]:
        try:
            dados = json.loads(self.arquivo.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return {str(k): dict(v) for k, v in dados.items() if isinstance(v, dict)}

    def ligada(self, jogo: str) -> bool:
        return bool(self._ler().get(jogo, {}).get("ligada"))

    def gravar(self, jogo: str, ligada: bool, *, anticheat: str = "",
               aviso_visto: bool = False) -> None:
        if ligada and anticheat and not aviso_visto:
            raise AvisoDoAnticheatError(
                f"Este jogo usa {anticheat}: ler a memória dele pode pôr a conta em risco.")
        dados = self._ler()
        dados[jogo] = {"ligada": bool(ligada), "anticheat": anticheat}
        self.arquivo.parent.mkdir(parents=True, exist_ok=True)
        provisorio = self.arquivo.with_suffix(".tmp")
        provisorio.write_text(json.dumps(dados, ensure_ascii=False), encoding="utf-8")
        os.replace(provisorio, self.arquivo)


class Leitor:
    """Lê as entradas declaradas de um jogo e publica ``{nome: valor, t}``.

    A trava roda no construtor, antes de qualquer leitura: a chave do jogo e o ``buildid``.
    """

    def __init__(self, pid: int, entradas: Sequence[Entrada], *, chave_ligada: bool,
                 buildid: str | int | None = None,
                 faixa: Mapping[str, Any] | None = None,
                 relogio: Callable[[], float] = time.monotonic) -> None:
        if not chave_ligada:
            raise LeituraRecusadaError("A chave «Memória» deste jogo está desligada.")
        conferir_buildid(buildid, faixa)
        self.pid = pid
        self.entradas = tuple(entradas)
        self._relogio = relogio
        self._ultima: dict[str, float] = {}

    def ler(self) -> dict[str, Any]:
        agora = self._relogio()
        valores: dict[str, Any] = {}
        for entrada in self.entradas:
            if agora - self._ultima.get(entrada.nome, -1e9) < 1.0 / entrada.hz:
                continue
            self._ultima[entrada.nome] = agora
            try:
                valores[entrada.nome] = ler_valor(self.pid, entrada)
            except LeituraRecusadaError as exc:
                if exc.frase == "O jogo fechou.":
                    raise
                valores[entrada.nome] = None
        valores["t"] = agora
        return valores


def _regioes_gravaveis(pid: int) -> list[tuple[int, int]]:
    regioes = []
    try:
        linhas = Path(f"/proc/{pid}/maps").read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise LeituraRecusadaError("O jogo fechou.") from exc
    for linha in linhas.splitlines():
        partes = linha.split()
        if len(partes) < 5 or not partes[1].startswith("rw"):
            continue
        if len(partes) == 6 and partes[5].startswith("[v"):
            continue
        inicio, fim = (int(x, 16) for x in partes[0].split("-"))
        regioes.append((inicio, fim))
    return regioes


class Varredura:
    """O caçador do estúdio: guarda os candidatos do lado do leitor e devolve só a contagem e
    um token; o endereço sai só quando sobra um."""

    def __init__(self, pid: int, tipo: str, *, chave_ligada: bool,
                 valor: int | float | None = None) -> None:
        if not chave_ligada:
            raise LeituraRecusadaError("A chave «Memória» deste jogo está desligada.")
        if tipo not in TIPOS:
            raise LeituraRecusadaError(f"O tipo «{tipo}» não é um dos que o leitor conhece.")
        self.pid = pid
        self.tipo = tipo
        self.token = secrets.token_hex(8)
        self._formato = TIPOS[tipo]
        self._passo = struct.calcsize(self._formato)
        self._candidatos: dict[int, int | float] = {}
        self._comecar(valor)

    def _guardar(self, endereco: int, bloco: bytes, valor: int | float | None) -> None:
        if valor is not None:
            agulha = struct.pack(self._formato, valor)
            achado = bloco.find(agulha)
            while achado >= 0:
                if achado % self._passo == 0:
                    self._candidatos[endereco + achado] = valor
                achado = bloco.find(agulha, achado + 1)
            return
        util = len(bloco) - len(bloco) % self._passo
        if len(self._candidatos) + util // self._passo > CANDIDATOS_SEM_VALOR:
            raise LeituraRecusadaError(
                "Candidatos de mais para guardar: comece por um valor conhecido.")
        for i, (lido,) in enumerate(struct.iter_unpack(self._formato, bloco[:util])):
            self._candidatos[endereco + i * self._passo] = lido

    def _comecar(self, valor: int | float | None) -> None:
        lidos = 0
        for inicio, fim in _regioes_gravaveis(self.pid):
            endereco = inicio
            while endereco < fim and lidos < TETO_DA_VARREDURA:
                tamanho = min(BLOCO_DA_VARREDURA, fim - endereco)
                try:
                    bloco = ler_bytes(self.pid, endereco, tamanho)
                except LeituraRecusadaError as exc:
                    if exc.frase != "O endereço declarado está fora da memória do jogo.":
                        raise
                    break
                lidos += tamanho
                self._guardar(endereco, bloco, valor)
                endereco += tamanho

    @property
    def contagem(self) -> int:
        return len(self._candidatos)

    def refinar(self, comparacao: str, valor: int | float | None = None) -> int:
        if comparacao not in COMPARACOES:
            raise LeituraRecusadaError(f"A comparação «{comparacao}» não existe.")
        if comparacao == "igual" and valor is None:
            raise LeituraRecusadaError("A comparação «igual» pede o valor.")
        ficam: dict[int, int | float] = {}
        for endereco, antes in self._candidatos.items():
            try:
                agora = struct.unpack(self._formato,
                                      ler_bytes(self.pid, endereco, self._passo))[0]
            except LeituraRecusadaError as exc:
                if exc.frase == "O jogo fechou.":
                    raise
                continue
            if ((comparacao == "igual" and agora == valor)
                    or (comparacao == "subiu" and agora > antes)
                    or (comparacao == "desceu" and agora < antes)
                    or (comparacao == "nao_mudou" and agora == antes)):
                ficam[endereco] = agora
        self._candidatos = ficam
        return self.contagem

    def resumo(self) -> dict[str, Any]:
        return {"token": self.token, "contagem": self.contagem}

    def endereco(self) -> int:
        if self.contagem != 1:
            raise LeituraRecusadaError(
                f"Sobram {self.contagem} candidatos; o endereço sai quando sobra um.")
        return next(iter(self._candidatos))


def argv_com_o_leitor(argv: Sequence[str], *, permitido: bool) -> list[str]:
    """O ``argv`` do jogo com o leitor na frente, como pai; sem a permissão e a chave, igual."""
    if not permitido:
        return list(argv)
    return [sys.executable, "-m", "hefesto_dualsense4unix.integrations.leitor_do_estado",
            "--pai", "--", *argv]


def _ser_pai(argv: Sequence[str]) -> int:
    filho = os.fork()
    if filho == 0:
        try:
            os.execvp(argv[0], list(argv))
        finally:
            os._exit(127)
    _, status = os.waitpid(filho, 0)
    return os.waitstatus_to_exitcode(status)


def main(args: Sequence[str] | None = None) -> int:
    resto = list(sys.argv[1:] if args is None else args)
    if resto[:2] != ["--pai", "--"] or len(resto) < 3:
        print("uso: leitor_do_estado --pai -- <comando do jogo>", file=sys.stderr)
        return 2
    return _ser_pai(resto[2:])


__all__ = [
    "CANDIDATOS_SEM_VALOR",
    "COMPARACOES",
    "HZ_MAXIMO",
    "TIPOS",
    "TOPICO_DA_MEMORIA",
    "AvisoDoAnticheatError",
    "ChavesDaMemoria",
    "Entrada",
    "Leitor",
    "LeituraRecusadaError",
    "Varredura",
    "anticheat_do_jogo",
    "argv_com_o_leitor",
    "base_do_modulo",
    "conferir_buildid",
    "entradas_da_receita",
    "ler_bytes",
    "ler_valor",
    "resolver",
]

if __name__ == "__main__":
    raise SystemExit(main())
