#!/usr/bin/env python3
"""A RÉGUA DA FRASE QUE FALTAVA — o teclado abre, e a tela DIZ como sair."""
from __future__ import annotations

import contextlib
import csv
import os
import re
import signal
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core.keyboard_mappings import (
    TOKEN_OPEN_OSK,
    TOKEN_TOGGLE_OSK,
)
from hefesto_dualsense4unix.daemon.subsystems import keyboard as subsistema
from hefesto_dualsense4unix.daemon.subsystems.keyboard import _OSKController
from hefesto_dualsense4unix.integrations import desktop_notifications as avisos

_DUBLE = "sleep"
_DUBLE_ARGV = [_DUBLE, "600"]

_RAIZ = Path(__file__).resolve().parents[2]
_DECISOES = _RAIZ / "docs" / "data" / "decisoes-dela.csv"
_ID_DA_DECISAO = "D-0609-A-FRASE-DO-TECLADO-NA-TELA"


def _frase_que_ela_decidiu() -> str:
    """A frase entre aspas na linha da decisão dela, lida do CSV."""
    with _DECISOES.open(encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha.get("id") != _ID_DA_DECISAO:
                continue
            achado = re.search(r'"(.+?)"', linha.get("titulo", ""))
            assert achado, (
                f"a linha {_ID_DA_DECISAO} do {_DECISOES.name} existe mas o "
                "`titulo` dela não traz a frase entre aspas — a fonte da frase "
                "de tela mudou de forma e esta régua deixou de saber o que ler"
            )
            return achado.group(1)
    raise AssertionError(
        f"{_ID_DA_DECISAO} não está em {_DECISOES} — a frase que o produto "
        "publica ficou sem decisão dela por trás"
    )


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[dict[str, Any]]:
    """Teclado na tela dublado por ``sleep``, e todo `notify` recolhido numa lista."""
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(subsistema, "_OSK_CANDIDATES", (_DUBLE,))
    monkeypatch.setattr(subsistema, "_osk_candidatos", lambda: (_DUBLE,))
    monkeypatch.setattr(subsistema, "_OSK_SPAWN_ARGS", {_DUBLE: list(_DUBLE_ARGV)})
    monkeypatch.setattr(
        subsistema.shutil,
        "which",
        lambda nome: f"/usr/bin/{nome}" if nome == _DUBLE else None,
    )
    monkeypatch.setattr(subsistema, "_OSK_SONDA", [(float("-inf"), False)])

    emitidos: list[dict[str, Any]] = []

    def _notify(summary: str, body: str = "", **kw: Any) -> bool:
        emitidos.append({"summary": summary, "body": body, **kw})
        return True

    monkeypatch.setattr(avisos, "notify", _notify)
    avisos.reset_once_cache()

    nascidos: list[int] = []
    popen_real = subprocess.Popen

    def _popen(argv: list[str], **kw: Any) -> Any:
        proc = popen_real(argv, **kw)
        nascidos.append(proc.pid)
        return proc

    monkeypatch.setattr(subsistema.subprocess, "Popen", _popen)

    try:
        yield {"emitidos": emitidos, "nascidos": nascidos, "runtime": tmp_path}
    finally:
        for pid in nascidos:
            with contextlib.suppress(ProcessLookupError, PermissionError):
                os.kill(pid, signal.SIGKILL)
        for pid in nascidos:
            with contextlib.suppress(ChildProcessError, OSError):
                os.waitpid(pid, 0)
        avisos.reset_once_cache()


def _texto(aviso: dict[str, Any]) -> str:
    """Título e corpo do aviso colados — é o que ela LÊ no canto da tela."""
    return f"{aviso['summary']} {aviso['body']}".strip()


def _avisos_de_abertura(emitidos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Os avisos que anunciam um teclado ABERTO, separados dos de ausência."""
    return [a for a in emitidos if a["summary"] == avisos._OSK_ABERTO_TITULO]


@pytest.mark.parametrize("token", [TOKEN_TOGGLE_OSK, TOKEN_OPEN_OSK])
def test_abrir_o_teclado_pelo_controle_avisa_na_tela(
    mesa: dict[str, Any], token: str
) -> None:
    """Ela clica o analógico esquerdo, o teclado abre — e a tela FALA."""
    controlador = _OSKController()
    controlador.dispatch_token(token, "press")
    assert controlador.esperar_os_toques(5.0)

    assert mesa["nascidos"], (
        f"o dublê do teclado na tela nem chegou a nascer no press de {token} — "
        "o caso está medindo outra coisa que não a abertura"
    )
    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert len(abertura) == 1, (
        f"o teclado na tela abriu por {token} e a tela emitiu {len(abertura)} "
        "avisos de abertura em vez de 1 — foi o silêncio deste momento que "
        f"deixou ela vinte minutos sem saber o que abriu. Emitido: "
        f"{[_texto(a) for a in mesa['emitidos']]}"
    )


def test_o_release_do_analogico_nao_repete_o_aviso(mesa: dict[str, Any]) -> None:
    """Clicar é UM gesto — press e release não podem virar dois avisos."""
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "release")
    assert controlador.esperar_os_toques(5.0)

    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert len(abertura) == 1, (
        "um clique só do analógico produziu "
        f"{len(abertura)} avisos de abertura — o release está avisando junto"
    )


def test_a_frase_ensina_o_gesto_de_saida(mesa: dict[str, Any]) -> None:
    """A frase nomeia o R3 — sem isso ela sabe o que abriu e continua presa."""
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert controlador.esperar_os_toques(5.0)

    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert abertura, "nenhum aviso de abertura para conferir a frase"
    texto = _texto(abertura[0])
    assert "R3" in texto, (
        f"a frase publicada não nomeia o R3: {texto!r}. Ela diz o que abriu e "
        "cala sobre como sair — o gesto de saída volta a existir só na "
        "documentação, que é o que ninguém lê com o teclado tapando a tela"
    )
    assert "L3" in texto, (
        f"a frase publicada não nomeia o L3: {texto!r}. Sem dizer QUAL botão "
        "abriu, ela fica sabendo que há um teclado e não sabe o que apertou"
    )


def test_a_frase_e_a_que_ela_decidiu(mesa: dict[str, Any]) -> None:
    """O texto publicado é, palavra por palavra, o da decisão dela."""
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert controlador.esperar_os_toques(5.0)

    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert abertura, "nenhum aviso de abertura para comparar com a decisão dela"
    decidida = _frase_que_ela_decidiu()
    assert _texto(abertura[0]) == decidida, (
        f"o produto publica {_texto(abertura[0])!r} e a decisão dela diz "
        f"{decidida!r}. Texto de tela é dela: mude a linha do "
        "`decisoes-dela.csv` COM a palavra dela, ou devolva a frase"
    )


def test_o_teclado_ja_aberto_nao_ganha_um_segundo_aviso(mesa: dict[str, Any]) -> None:
    """Dois avisos para um teclado só seria ruído — e mentira sobre o estado."""
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_OPEN_OSK, "press")
    controlador.dispatch_token(TOKEN_OPEN_OSK, "press")
    assert controlador.esperar_os_toques(5.0)

    assert len(mesa["nascidos"]) == 1, (
        "o segundo `__OPEN_OSK__` abriu um SEGUNDO teclado — o caso não chega a "
        "medir o aviso porque o guarda de 'já aberto' está quebrado"
    )
    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert len(abertura) == 1, (
        f"um teclado só e {len(abertura)} avisos de abertura — o aviso está "
        "acima do guarda de 'já aberto' e fala de uma abertura que não houve"
    )


def test_sem_programa_de_teclado_o_unico_aviso_e_o_da_ausencia(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nenhum teclado na tela instalado: sai UM recado, e é o que já tinha dono."""
    monkeypatch.setattr(subsistema.shutil, "which", lambda _nome: None)

    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert controlador.esperar_os_toques(5.0)

    assert not mesa["nascidos"], "sem binário nenhum processo pode nascer"
    assert not _avisos_de_abertura(mesa["emitidos"]), (
        "a tela anunciou 'teclado na tela aberto' sem teclado nenhum ter "
        f"aberto: {[_texto(a) for a in mesa['emitidos']]}"
    )
    assert len(mesa["emitidos"]) == 1, (
        f"um gesto só produziu {len(mesa['emitidos'])} avisos: "
        f"{[_texto(a) for a in mesa['emitidos']]} — o gesto que não abriu nada "
        "tem UM recado, o da ausência"
    )
    assert mesa["emitidos"][0]["summary"] == "Teclado na tela não instalado", (
        "o único recado do gesto sem binário não é o da ausência: "
        f"{_texto(mesa['emitidos'][0])!r}"
    )


def test_o_spawn_que_estoura_nao_anuncia_teclado_nenhum(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """O binário existe, o ``Popen`` estoura — e a tela NÃO diz que abriu."""

    def _estoura(*_a: Any, **_k: Any) -> Any:
        raise OSError("dublê: o teclado na tela recusou a nascer")

    monkeypatch.setattr(subsistema.subprocess, "Popen", _estoura)

    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert controlador.esperar_os_toques(5.0)

    assert not mesa["emitidos"], (
        "o `Popen` estourou e a tela anunciou um teclado aberto: "
        f"{[_texto(a) for a in mesa['emitidos']]}"
    )


def test_o_aviso_que_estoura_nao_derruba_o_teclado(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem barramento de notificação, o teclado abre do mesmo jeito."""

    def _estoura(*_a: Any, **_k: Any) -> bool:
        raise RuntimeError("dublê: sem servidor de notificação nesta sessão")

    monkeypatch.setattr(avisos, "notify", _estoura)

    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    assert controlador.esperar_os_toques(5.0)

    assert mesa["nascidos"], "o aviso que estourou levou o teclado junto"
    assert controlador.aberto() is True, (
        "o teclado nasceu mas o controlador não o reconhece como aberto — o "
        "estouro do aviso interrompeu o `open()` antes do fim"
    )
