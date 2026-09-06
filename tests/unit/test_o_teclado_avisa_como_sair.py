#!/usr/bin/env python3
"""A RÉGUA DA FRASE QUE FALTAVA — o teclado abre, e a tela DIZ como sair.

O DEFEITO, MEDIDO NO RELÓGIO DELA (30/08/2026)
===============================================
Um clique no analógico esquerdo pôs um teclado na tela dela às **00:29:23**. Ela
perguntou *"pq tem um teclado virtual aberto? pode me ajudar a remover ele?"* às
**00:49** — vinte minutos depois. No intervalo, a tela não disse **nada**: nem o
que tinha aberto, nem como fechar. O gesto de saída existia só em
``docs/usage/hotkeys.md``, que ninguém lê com o teclado tapando a barra de
tarefas, e o único registro do produto era um ``osk_opened`` no journal.

O produto funcionou exatamente como desenhado. O que faltava era ele **dizer**.

O QUE ESTA RÉGUA MEDE, E POR QUE PELO CAMINHO PÚBLICO
======================================================
Ela entra por ``dispatch_token(..., "press")`` — o callback que o
``UinputKeyboardDevice`` chama quando o analógico é clicado —, e não por
``open()`` direto. É o caminho do controle dela; um teste que chamasse o método
interno provaria que o método funciona e deixaria o fio até o botão sem prova.

**Os DOIS tokens de abertura são exercidos**, e isso é correção de rota, não
zelo: a sprint foi escrita em 30/08 quando o L3 de fábrica era ``__OPEN_OSK__``,
e em 02/09 ele virou ``__TOGGLE_OSK__`` por decisão dela (*"deixar no preset do
botão L3 ... abrir o teclado virtual e fechar o teclado virtual caso apertado
novamente"*). O ``__OPEN_OSK__`` não morreu — continua sendo o que a aba
Navegação grava quando ela escolhe "Abrir o teclado na tela" —, então quem abre
o teclado hoje são **dois** caminhos, e o aviso tem de nascer nos dois.

NADA DE JANELA DE VERDADE — E ISSO É A TELA DELA, NÃO ECONOMIA
===============================================================
O teclado na tela é ``layer-shell``: ele aparece **por cima de todos os
workspaces**, o dela inclusive, e por isso não há workspace onde parqueá-lo.
A única proteção é dublar o binário, e dublar exige acertar o NOME dos três
atributos do cache do ``_resolve`` (``_resolved_bin`` / ``_resolved_checked`` /
``_resolved_em``). Quem coordenou a sprint errou esse nome em 30/08, o
``_resolve()`` correu de verdade, achou o ``wvkbd`` e **abriu um teclado na tela
dela por ~20 s no meio da noite**. Aqui o dublê vem pelo caminho declarado —
``_osk_candidatos``/``_OSK_CANDIDATES``/``_OSK_SPAWN_ARGS`` mais o ``which`` —,
e o processo que nasce é um ``sleep``.

A FRASE NÃO É DIGITADA AQUI, ELA É LIDA DA DECISÃO DELA
========================================================
``test_a_frase_e_a_que_ela_decidiu`` lê o texto de
``docs/data/decisoes-dela.csv`` (``D-0609-A-FRASE-DO-TECLADO-NA-TELA``) e
compara com o que o produto publica. Uma régua que redigitasse a frase mediria a
própria digitação — a forma exata do defeito *"a régua digita o que devia LER"*,
que já derrubou onze réguas desta casa num dia só. Assim, trocar a frase no
código sem passar por ela reprova, e trocá-la COM a palavra dela (mudando a
decisão) passa.

AS QUATRO ARRANCADAS (a tabela do §5 da sprint)
================================================
=========================================  ==================================
arranque isto                               tem de reprovar com
=========================================  ==================================
``self._avisar_abertura()`` do ``open()``   nenhuma notificação no clique de L3
o ``R3`` do texto publicado                 a frase não ensina a saída
o ``return`` do ``open()`` já-aberto        dois avisos para um teclado só
o guarda ``resolved is None`` (avisar        os dois avisos no mesmo gesto
antes de resolver o binário)
=========================================  ==================================

As quatro foram executadas em 06/09/2026; as saídas estão na entrega
``docs/process/agentes/2026-09-06/O-TECLADO-QUE-NAO-DIZ-COMO-SAIR-01-opus.md``.
"""
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

#: O dublê do binário do teclado na tela — o mesmo da régua irmã
#: (``test_o_teclado_nao_sobrevive_ao_daemon.py``): existe em qualquer máquina
#: que rode esta suíte, morre com ``SIGTERM`` sem reclamar, e não desenha nada.
_DUBLE = "sleep"
_DUBLE_ARGV = [_DUBLE, "600"]

_RAIZ = Path(__file__).resolve().parents[2]
_DECISOES = _RAIZ / "docs" / "data" / "decisoes-dela.csv"
_ID_DA_DECISAO = "D-0609-A-FRASE-DO-TECLADO-NA-TELA"


def _frase_que_ela_decidiu() -> str:
    """A frase entre aspas na linha da decisão dela, lida do CSV.

    Não se digita a frase nesta régua: ver o cabeçalho do módulo. Se a linha
    sumir do CSV, isto levanta em vez de devolver um padrão silencioso — uma
    régua que não acha a própria fonte tem de gritar, não passar.
    """
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
    """Teclado na tela dublado por ``sleep``, e todo `notify` recolhido numa lista.

    O ``XDG_RUNTIME_DIR`` próprio importa: o arquivo de sessão é o fio entre dois
    daemons, e um caso que o herdasse do anterior mediria o teclado do vizinho.

    O ``notify`` é dublado **na função de baixo** — não nas ``notify_*`` — de
    propósito: assim os DOIS avisos deste gesto (o de abertura e o de ausência)
    caem na mesma lista, e o caso do binário faltando consegue afirmar que
    apareceu **um** e não dois. Dublar as duas funções separadas deixaria a
    dupla-emissão invisível.
    """
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
        # Nenhum `sleep` desta régua atravessa para a máquina de quem a rodou —
        # nem quando um caso reprova no meio.
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
    """Os avisos que anunciam um teclado ABERTO, separados dos de ausência.

    A separação pergunta ao produto (a constante do título publicado) em vez de
    procurar uma palavra escolhida aqui.
    """
    return [a for a in emitidos if a["summary"] == avisos._OSK_ABERTO_TITULO]


# ---------------------------------------------------------------------------
# (1) abrir NOTIFICA — os dois tokens que o analógico esquerdo pode carregar
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("token", [TOKEN_TOGGLE_OSK, TOKEN_OPEN_OSK])
def test_abrir_o_teclado_pelo_controle_avisa_na_tela(
    mesa: dict[str, Any], token: str
) -> None:
    """Ela clica o analógico esquerdo, o teclado abre — e a tela FALA.

    A MORDIDA: arranque a chamada ``self._avisar_abertura()`` do fim do
    ``open()`` (``daemon/subsystems/keyboard.py``) — este caso reprova dizendo
    que nenhum aviso saiu no clique, que é o defeito medido no relógio dela.
    """
    controlador = _OSKController()
    controlador.dispatch_token(token, "press")

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
    """Clicar é UM gesto — press e release não podem virar dois avisos.

    O ``dispatch_token`` já ignora tudo que não é ``press``; esta é a prova de
    que o aviso nasceu do lado certo daquele guarda. Sem ela, uma futura
    chamada movida para o release passaria despercebida e ela levaria dois
    recados idênticos por clique.
    """
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "release")

    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert len(abertura) == 1, (
        "um clique só do analógico produziu "
        f"{len(abertura)} avisos de abertura — o release está avisando junto"
    )


# ---------------------------------------------------------------------------
# (2) a frase DIZ COMO SAIR, e é a que ela decidiu
# ---------------------------------------------------------------------------


def test_a_frase_ensina_o_gesto_de_saida(mesa: dict[str, Any]) -> None:
    """A frase nomeia o R3 — sem isso ela sabe o que abriu e continua presa.

    A MORDIDA: arranque o ``R3`` do texto publicado em
    ``desktop_notifications._OSK_ABERTO_CORPO`` — este caso reprova dizendo que
    a frase não ensina a saída, que é metade exata do defeito de 30/08 (o gesto
    de saída existia só em ``docs/usage/hotkeys.md``).
    """
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")

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
    """O texto publicado é, palavra por palavra, o da decisão dela.

    ``D-0609-A-FRASE-DO-TECLADO-NA-TELA``, lida do CSV — nunca digitada aqui.
    Texto de tela é decisão dela; esta régua é o que impede a próxima pessoa de
    "melhorar" a frase em silêncio.
    """
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")

    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert abertura, "nenhum aviso de abertura para comparar com a decisão dela"
    decidida = _frase_que_ela_decidiu()
    assert _texto(abertura[0]) == decidida, (
        f"o produto publica {_texto(abertura[0])!r} e a decisão dela diz "
        f"{decidida!r}. Texto de tela é dela: mude a linha do "
        "`decisoes-dela.csv` COM a palavra dela, ou devolva a frase"
    )


# ---------------------------------------------------------------------------
# (3) NÃO avisa quando o teclado JÁ está aberto
# ---------------------------------------------------------------------------


def test_o_teclado_ja_aberto_nao_ganha_um_segundo_aviso(mesa: dict[str, Any]) -> None:
    """Dois avisos para um teclado só seria ruído — e mentira sobre o estado.

    O segundo ``__OPEN_OSK__`` é no-op desde sempre (o guarda ``_pid_vivo()``),
    e o aviso tem de morar DEPOIS desse guarda.

    A MORDIDA: arranque o ``return`` do ``open()`` já-aberto, ou mova o
    ``_avisar_abertura()`` para antes dele — este caso reprova com dois avisos
    para um teclado só.
    """
    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_OPEN_OSK, "press")
    controlador.dispatch_token(TOKEN_OPEN_OSK, "press")

    assert len(mesa["nascidos"]) == 1, (
        "o segundo `__OPEN_OSK__` abriu um SEGUNDO teclado — o caso não chega a "
        "medir o aviso porque o guarda de 'já aberto' está quebrado"
    )
    abertura = _avisos_de_abertura(mesa["emitidos"])
    assert len(abertura) == 1, (
        f"um teclado só e {len(abertura)} avisos de abertura — o aviso está "
        "acima do guarda de 'já aberto' e fala de uma abertura que não houve"
    )


# ---------------------------------------------------------------------------
# (4) NÃO avisa quando não há binário — o outro aviso já tem dono
# ---------------------------------------------------------------------------


def test_sem_programa_de_teclado_o_unico_aviso_e_o_da_ausencia(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nenhum teclado na tela instalado: sai UM recado, e é o que já tinha dono.

    O caminho da ausência avisa desde a TECLADO-QUE-NAO-DIGITA-01. Um segundo
    aviso no mesmo gesto — ainda por cima anunciando um teclado que não abriu —
    seria a tela mentindo sobre o que existe.

    A MORDIDA: mova o ``_avisar_abertura()`` para antes do guarda
    ``resolved is None`` — este caso reprova com os dois avisos no mesmo gesto.
    """
    monkeypatch.setattr(subsistema.shutil, "which", lambda _nome: None)

    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")

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
    """O binário existe, o ``Popen`` estoura — e a tela NÃO diz que abriu.

    É o terceiro ramo que volta antes do aviso, e o mais fácil de perder numa
    reescrita: o ``except`` já zera ``self._process`` e retorna, então basta o
    ``_avisar_abertura()`` subir uma linha para a tela passar a anunciar um
    teclado que nunca nasceu.
    """

    def _estoura(*_a: Any, **_k: Any) -> Any:
        raise OSError("dublê: o teclado na tela recusou a nascer")

    monkeypatch.setattr(subsistema.subprocess, "Popen", _estoura)

    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")

    assert not mesa["emitidos"], (
        "o `Popen` estourou e a tela anunciou um teclado aberto: "
        f"{[_texto(a) for a in mesa['emitidos']]}"
    )


# ---------------------------------------------------------------------------
# (5) o aviso é best-effort — ele não pode derrubar o gesto que veio explicar
# ---------------------------------------------------------------------------


def test_o_aviso_que_estoura_nao_derruba_o_teclado(
    mesa: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sem barramento de notificação, o teclado abre do mesmo jeito.

    A cicatriz é de 04/09/2026: um recado de recusa **quebrava a tela que vinha
    explicar**. Um aviso que estoura levaria junto o ``open()``, e ela ficaria
    sem o teclado E sem a frase.
    """

    def _estoura(*_a: Any, **_k: Any) -> bool:
        raise RuntimeError("dublê: sem servidor de notificação nesta sessão")

    monkeypatch.setattr(avisos, "notify", _estoura)

    controlador = _OSKController()
    controlador.dispatch_token(TOKEN_TOGGLE_OSK, "press")

    assert mesa["nascidos"], "o aviso que estourou levou o teclado junto"
    assert controlador.aberto() is True, (
        "o teclado nasceu mas o controlador não o reconhece como aberto — o "
        "estouro do aviso interrompeu o `open()` antes do fim"
    )
