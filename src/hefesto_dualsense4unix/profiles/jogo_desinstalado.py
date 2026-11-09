"""O perfil de jogo cujo jogo saiu do disco: quem o reconhece e quem o troca pelo padrão.

Leitura única para a aba Perfis (que esconde) e para o serviço (que troca o ativo). O catálogo é
memoizado pela assinatura da biblioteca, e o censo é relido só na mudança dessa assinatura.
"""
from __future__ import annotations

import time
from typing import Any, NamedTuple

ESPERA_DEPOIS_DA_FALHA_S = 5.0

_NOMES_DOS_JOGOS: tuple[tuple[tuple[str, int], ...], dict[str, str]] | None = None
_FORA_DO_DISCO: tuple[object, frozenset[str]] | None = None


class FotoDoCatalogo(NamedTuple):
    """O catálogo de jogos desta máquina, perguntado UMA vez por tique."""

    nomes: dict[str, str]
    ofertas: list[Any]


def nomes_dos_jogos() -> dict[str, str]:
    """``{appid: nome}`` do disco, relido só quando a biblioteca muda."""
    global _NOMES_DOS_JOGOS
    from hefesto_dualsense4unix.integrations.jogos_locais import (
        assinatura_da_biblioteca,
        catalogo_de_jogos,
        nomes_por_appid,
    )

    assinatura = assinatura_da_biblioteca()
    if _NOMES_DOS_JOGOS is not None and _NOMES_DOS_JOGOS[0] == assinatura:
        return _NOMES_DOS_JOGOS[1]
    nomes = nomes_por_appid(catalogo_de_jogos())
    _NOMES_DOS_JOGOS = (assinatura, nomes)
    return nomes


def ofertas_de_jogos(nomes: dict[str, str]) -> list[Any]:
    """Os jogos DESTA máquina, das duas origens; nunca levanta."""
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import (
            JogoLocal,
            jogos_de_janela,
            ofertas_do_campo_do_jogo,
        )

        return list(ofertas_do_campo_do_jogo(
            [JogoLocal(appid=appid, nome=nome, fonte="steam") for appid, nome in nomes.items()],
            jogos_de_janela()))
    except Exception:
        return []


def foto_do_catalogo() -> FotoDoCatalogo:
    """As duas perguntas ao catálogo, uma vez cada; nunca levanta."""
    try:
        nomes = nomes_dos_jogos()
    except Exception:
        nomes = {}
    return FotoDoCatalogo(nomes=nomes, ofertas=ofertas_de_jogos(nomes))


def chaves_fora_do_disco() -> frozenset[str]:
    """Os jogos que o censo sabe desinstalados, relidos só quando a biblioteca muda."""
    global _FORA_DO_DISCO
    try:
        from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo

        assinatura = censo.assinatura_das_bibliotecas()
        if _FORA_DO_DISCO is None or _FORA_DO_DISCO[0] != assinatura:
            _FORA_DO_DISCO = (assinatura, censo.chaves_de_janela_fora_do_disco())
        return _FORA_DO_DISCO[1]
    except Exception:
        return frozenset()


def a_steam_responde() -> bool:
    """A biblioteca da Steam existe aqui; sem a biblioteca, nenhum jogo da Steam sai."""
    try:
        from hefesto_dualsense4unix.integrations.jogos_locais import assinatura_da_biblioteca

        return any(mtime >= 0 for _pasta, mtime in assinatura_da_biblioteca())
    except Exception:
        return False


def jogo_fora_do_disco(prof: Any, foto: FotoDoCatalogo, steam: bool,
                       fora: frozenset[str]) -> bool:
    """O perfil é de um jogo que o censo sabe desinstalado."""
    from hefesto_dualsense4unix.integrations.jogos_locais import jogo_da_janela
    from hefesto_dualsense4unix.profiles.simple_match import (
        detect_simple_preset,
        normalize_appid,
        simple_extra,
    )

    match = getattr(prof, "match", None)
    if match is None:
        return False
    preset = detect_simple_preset(match)
    chave = simple_extra(match)
    if preset == "steam_game":
        appid = normalize_appid(chave)
        if appid is None or not steam or appid in foto.nomes:
            return False
        return not any(normalize_appid(str(getattr(j, "chave", "") or "")) == appid
                       for j in foto.ofertas)
    if preset in ("game", "janela") and chave:
        return chave.casefold() in fora and jogo_da_janela(chave, foto.ofertas) is None
    return False


def casa_a_janela(prof: Any, janela: str) -> bool:
    """O perfil casa a janela de outro app em cena: o jogo dele está aberto, e o censo erra."""
    try:
        return bool(janela) and bool(prof.matches({"wm_class": janela}))
    except Exception:
        return False


def fora_do_disco(todos: list[Any], foto: FotoDoCatalogo, janela: str = "") -> list[Any]:
    """Os perfis de jogo que o censo sabe desinstalado; sem a Steam legível, nenhum."""
    steam = bool(foto.nomes) and a_steam_responde()
    fora = chaves_fora_do_disco()
    return [p for p in todos
            if jogo_fora_do_disco(p, foto, steam, fora) and not casa_a_janela(p, janela)]


def assinatura_das_bibliotecas() -> tuple[object, ...]:
    """A impressão barata das bibliotecas: muda quando um jogo entra ou sai."""
    from hefesto_dualsense4unix.integrations.censo_dos_lancadores import (
        assinatura_das_bibliotecas as dos_lancadores,
    )
    from hefesto_dualsense4unix.integrations.jogos_locais import assinatura_da_biblioteca

    return (assinatura_da_biblioteca(), dos_lancadores())


class VigiaDoPadrao:
    """O serviço troca o perfil ativo de jogo desinstalado pelo padrão, uma vez, sem laço.

    ``decidir`` só olha o disco quando a assinatura das bibliotecas, o perfil ativo ou a janela em
    cena mudam; a pergunta repetida custa a comparação da chave. Uma troca recusada volta a sair
    `ESPERA_DEPOIS_DA_FALHA_S` segundos depois.
    """

    def __init__(self) -> None:
        self._chave: tuple[object, ...] | None = None
        self._falhou_em: float | None = None

    def decidir(self, ativo: str, perfis: list[Any], janela: str = "") -> bool:
        """O perfil ativo é de jogo fora do disco e não há janela dele em cena."""
        if not ativo:
            self._chave = None
            return False
        if (self._falhou_em is not None
                and time.monotonic() - self._falhou_em < ESPERA_DEPOIS_DA_FALHA_S):
            return False
        try:
            chave = (assinatura_das_bibliotecas(), ativo, janela)
        except Exception:
            return False
        if chave == self._chave:
            return False
        self._chave = chave
        self._falhou_em = None
        alvo = [p for p in perfis if str(getattr(p, "name", "") or "") == ativo]
        if not alvo:
            return False
        return bool(fora_do_disco(alvo, foto_do_catalogo(), janela))

    def falhou(self) -> None:
        """A troca não assumiu: a chave se esquece e a próxima tentativa sai depois da espera."""
        self._chave = None
        self._falhou_em = time.monotonic()
