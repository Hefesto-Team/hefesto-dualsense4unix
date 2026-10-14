"""As receitas de ambiente por sinal: o jogo que só abre com uma variável a recebe pelo wrapper.

A tabela `docs/data/receitas-de-ambiente.csv` diz, por sinal no disco do jogo, qual variável vale
e que peça ela exige. Três regras que ela não quebra: sem appid embarcado (o jogo se reconhece
pelo que traz na pasta); só com a peça ao lado do executável (sem ela o override quebraria o
jogo, e o prontuário diz «falta a peça»); só o que o wrapper aceita (letra morta calada não
entra). 100% stdlib, como o prontuário.
"""
from __future__ import annotations

import csv
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

try:
    from .api_de_entrada import escolher_executavel
except ImportError:  # pragma: no cover - executado como script avulso
    from api_de_entrada import escolher_executavel  # type: ignore[no-redef]

TABELA = Path(__file__).resolve().parents[3] / "docs" / "data" / "receitas-de-ambiente.csv"

#: As variáveis que o wrapper deixa passar com forma conferida. Espelho de `decide_envs`.
VARIAVEIS_DO_WRAPPER = frozenset({"WINEDLLOVERRIDES"})

_NOME_DE_DLL = re.compile(r"^[A-Za-z0-9_.-]+$")


def override_valido(valor: str) -> bool:
    """A forma que o wrapper aceita: ``nome[,nome]=n`` ou ``=n,b``, entradas por ``;``.

    O espelho em Python de ``override_de_dll_valido`` em ``assets/hefesto-launch.sh``; uma régua
    confere as duas pontas com o mesmo vetor.
    """
    if not valor:
        return False
    entradas = [e for e in valor.split(";") if e]
    if not entradas:
        return False
    for entrada in entradas:
        nomes, igual, modo = entrada.partition("=")
        if not igual or modo not in ("n", "n,b") or not nomes:
            return False
        for nome in nomes.split(","):
            if not _NOME_DE_DLL.match(nome):
                return False
    return True


@dataclass(frozen=True)
class Receita:
    """Uma linha da tabela."""

    id: str
    sinais: tuple[str, ...]
    variavel: str
    valor: str
    peca: str


@dataclass(frozen=True)
class Leitura:
    """O que o disco de UM jogo diz sobre uma receita que o sinal ligou."""

    receita: Receita
    sinal: str
    #: ``True``/``False``; ``None`` quando nenhum executável se lê (não dá para saber).
    peca_presente: bool | None


def _linha_valida(linha: dict[str, str]) -> Receita | None:
    sinais = tuple(s.strip() for s in (linha.get("sinais") or "").split("|") if s.strip())
    variavel = (linha.get("variavel") or "").strip()
    valor = (linha.get("valor") or "").strip()
    peca = (linha.get("peca") or "").strip()
    ident = (linha.get("id") or "").strip()
    if not (ident and sinais and peca):
        return None
    if any("/" in s or s.startswith(".") for s in sinais) or "/" in peca:
        return None
    if variavel not in VARIAVEIS_DO_WRAPPER or not override_valido(valor):
        return None
    return Receita(ident, sinais, variavel, valor, peca)


def carregar_tabela(caminho: Path | None = None) -> tuple[Receita, ...]:
    """As receitas da tabela; tabela ausente ou linha fora da regra não derruba nada."""
    alvo = caminho if caminho is not None else TABELA
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError:
        return ()
    corpo = (ln for ln in texto.splitlines() if ln.strip() and not ln.lstrip().startswith("#"))
    achadas: list[Receita] = []
    vistos: set[str] = set()
    for linha in csv.DictReader(corpo):
        receita = _linha_valida({k: (v or "") for k, v in linha.items() if k})
        if receita is None or receita.id in vistos:
            continue
        vistos.add(receita.id)
        achadas.append(receita)
    return tuple(achadas)


def _peca_ao_lado_do_executavel(raiz: Path, peca: str) -> bool | None:
    exe = escolher_executavel(raiz)
    if exe is None:
        return None
    alvo = peca.lower()
    try:
        return any(p.name.lower() == alvo and p.is_file() for p in exe.parent.iterdir())
    except OSError:
        return None


def ler_jogo(raiz: Path | None, tabela: Iterable[Receita] | None = None) -> tuple[Leitura, ...]:
    """As receitas que o disco do jogo liga, cada uma com o veredito da peça."""
    if raiz is None:
        return ()
    receitas = carregar_tabela() if tabela is None else tuple(tabela)
    achadas: list[Leitura] = []
    for receita in receitas:
        sinal = next((s for s in receita.sinais if (raiz / s).is_file()), None)
        if sinal is None:
            continue
        achadas.append(Leitura(receita, sinal, _peca_ao_lado_do_executavel(raiz, receita.peca)))
    return tuple(achadas)


def ambiente_do_jogo(raiz: Path | None, tabela: Iterable[Receita] | None = None) -> dict[str, str]:
    """As variáveis que valem: só as receitas com a peça confirmada ao lado do executável."""
    env: dict[str, str] = {}
    for leitura in ler_jogo(raiz, tabela):
        if leitura.peca_presente is not True:
            continue
        r = leitura.receita
        env[r.variavel] = f"{env[r.variavel]};{r.valor}" if r.variavel in env else r.valor
    return env


def pecas_que_faltam(raiz: Path | None, tabela: Iterable[Receita] | None = None) -> tuple[str, ...]:
    """Os nomes das peças que o sinal pede e o disco não tem (executável lido, peça ausente)."""
    return tuple(
        leitura.receita.peca
        for leitura in ler_jogo(raiz, tabela)
        if leitura.peca_presente is False
    )


def ambientes_dos_jogos(home: Path | None = None) -> dict[str, dict[str, str]]:
    """``{appid: ambiente}`` dos jogos instalados cujo disco liga uma receita com a peça."""
    tabela = carregar_tabela()
    if not tabela:
        return {}
    try:
        from .prontuario_dos_jogos import jogos_instalados
    except ImportError:  # pragma: no cover - executado como script avulso
        from prontuario_dos_jogos import jogos_instalados  # type: ignore[no-redef]
    fora: dict[str, dict[str, str]] = {}
    for appid, _nome, raiz in jogos_instalados(home):
        env = ambiente_do_jogo(raiz, tabela)
        if env:
            fora[appid] = env
    return fora


__all__ = [
    "TABELA",
    "VARIAVEIS_DO_WRAPPER",
    "Leitura",
    "Receita",
    "ambiente_do_jogo",
    "ambientes_dos_jogos",
    "carregar_tabela",
    "ler_jogo",
    "override_valido",
    "pecas_que_faltam",
]
