"""Qual é a área de trabalho desta sessão — e o que dizer sobre a barra do sistema."""
from __future__ import annotations

import os
from collections.abc import Mapping

from hefesto_dualsense4unix.app.gui_prefs import load_gui_prefs, set_pref

CHAVE_AMBIENTE = "ambiente_corrigido"

AMBIENTES: tuple[tuple[str, str], ...] = (
    ("cosmic", "COSMIC"),
    ("gnome", "GNOME"),
    ("outro", "Outro"),
)

NOMES_DE_TELA: dict[str, str] = dict(AMBIENTES)

_VARIAVEIS_DA_SESSAO = ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP")


def ambiente_lido(*, variaveis: Mapping[str, str] | None = None) -> str:
    """O que a sessão declara, cru, como `tray.py:92-97` já lê."""
    fonte = os.environ if variaveis is None else variaveis
    partes = [fonte.get(nome, "") for nome in _VARIAVEIS_DA_SESSAO]
    return ":".join(parte for parte in partes if parte)


def ambiente_normalizado(bruto: str | None) -> str:
    """Reduz a declaração crua a um dos três ids de `AMBIENTES`."""
    texto = (bruto or "").lower()
    if "cosmic" in texto:
        return "cosmic"
    if "gnome" in texto:
        return "gnome"
    return "outro"


def ambiente_efetivo(*, variaveis: Mapping[str, str] | None = None) -> str:
    """O ambiente que vale para a tela: a correção dela vence a detecção."""
    escolha = load_gui_prefs().get(CHAVE_AMBIENTE)
    if isinstance(escolha, str) and escolha in NOMES_DE_TELA:
        return escolha
    return ambiente_normalizado(ambiente_lido(variaveis=variaveis))


def gravar_correcao_de_ambiente(escolha: str) -> None:
    """Grava a correção manual. Id desconhecido não grava nada."""
    if escolha not in NOMES_DE_TELA:
        return
    set_pref(CHAVE_AMBIENTE, escolha)


def frase_do_detectado(bruto: str) -> str:
    """A linha que diz o que foi detectado, para a pessoa poder discordar."""
    if not bruto:
        return "A sessão não diz qual é o ambiente. Corrija se souber qual é."
    return f"Detectado: {NOMES_DE_TELA[ambiente_normalizado(bruto)]}. Corrija se estiver errado."


def mensagem_da_bandeja(ambiente: str, watcher_presente: bool) -> str:
    """O que a seção diz sobre o ícone na barra do sistema."""
    if watcher_presente:
        return "A barra do sistema desta sessão recebe o ícone do Hefesto."
    if ambiente == "gnome":
        return (
            "A barra do sistema desta sessão não recebe o ícone. No GNOME ele depende "
            "de uma extensão: ligue a extensão ubuntu-appindicators@ubuntu.com, saia "
            "da sua conta e entre de novo."
        )
    if ambiente == "cosmic":
        return (
            "A barra do sistema desta sessão não recebe o ícone. No COSMIC, ligue o "
            "applet 'Área de status' em Configurações > Painel."
        )
    return (
        "A barra do sistema desta sessão não recebe o ícone, e neste ambiente o Hefesto "
        "não sabe dizer o motivo. A janela continua abrindo normalmente."
    )


__all__ = [
    "AMBIENTES",
    "CHAVE_AMBIENTE",
    "NOMES_DE_TELA",
    "ambiente_efetivo",
    "ambiente_lido",
    "ambiente_normalizado",
    "frase_do_detectado",
    "gravar_correcao_de_ambiente",
    "mensagem_da_bandeja",
]
