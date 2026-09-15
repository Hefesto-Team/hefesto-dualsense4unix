#!/usr/bin/env python3
"""O CHIP «PERFIL ATIVO» TEM UM DONO SÓ, e as dez abas pintam o mesmo nome.

FRASES-E-DICAS-03, 13/09/2026. O defeito foi achado pela VAO-DO-ESQUELETO-01 no
piloto oculto, com um perfil valendo: a 03 e a 04 pintavam «—» e as outras oito
pintavam o nome (a entrega de 13/09/2026 da `VAO-DO-ESQUELETO-01`,
«O que sobrou», item 1). Remedido no ANTES desta sprint: o mesmo quadro.

A CAUSA ERAM DOIS DONOS PARA UM ENDEREÇO. `pacotes.topo()` pergunta ao dono do
perfil que vale (`perfil.nome_do_ativo`, as duas pernas: o daemon, depois o
marcador em disco). `a03_gatilhos.pacote` e `a04_iluminacao.pacote` emitiam
também `perfil`, lido CRU do `active_profile` do daemon. O piloto completa o
cabeçalho com `setdefault`: quem chega primeiro ganha, e o pacote da aba chega
primeiro. Com o daemon respondendo `active_profile: null` — o estado da máquina
dela — o `""` da aba vencia o nome que o disco dava.

A regra já estava escrita em `a09_sistema.pacote`: um pacote de aba só emite
endereço DAQUELA página. O chip mora no `topo.html`, que é das dez.

A RÉGUA PASSA PELO CAMINHO DO PILOTO — `pacote_da_pagina`, `normalizar` e
`topo` com `setdefault`, nesta ordem —, nas dez abas, com o daemon calado e um
perfil no disco do lar de mentira.

A MORDIDA: devolva `"perfil": ctx.state.get("active_profile") or ""` ao retorno
de `a03_gatilhos.pacote` e esta régua reprova nomeando a 03; tire-o de lá e
devolva-o só ao de `a04_iluminacao.pacote`, e ela reprova nomeando a 04.

NADA AQUI TOCA A MÁQUINA DELA: o `conftest.py` desvia `HOME` e os `XDG_*`, e a
fixture confere o desvio contra o lar do `passwd` antes de gravar o perfil.
"""
from __future__ import annotations

import os
import pathlib
import pwd
import sys
from collections.abc import Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.daemon.subsystems import external_mask as mask_mod
from hefesto_dualsense4unix.interface import pacotes
from hefesto_dualsense4unix.interface.pacotes import Contexto
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
from hefesto_dualsense4unix.utils import session as sessao
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

#: AS DEZ, e a lista é FIXA: derivá-la de `PACOTES` faria a régua passar por
#: vacuidade no dia em que uma aba saísse da tabela.
ABAS = (
    "01-jogar.html", "02-controles.html", "03-gatilhos.html", "04-iluminacao.html",
    "05-vibracao.html", "06-navegacao.html", "07-lancadores.html",
    "08-conexoes.html", "09-sistema.html", "10-perfis.html",
)

#: O perfil do disco nesta régua. Não é nome de perfil dela.
NO_DISCO = "chip-de-um-dono"

#: Um controle na forma do daemon e o mesmo na forma do desenho — os dois
#: vocabulários que os pacotes leem (o molde de `test_o_despachante_serve_as_dez`).
#: Endereço da faixa sintética da casa.
UNIQ = "aa:bb:cc:00:00:01"
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua", "via": "USB",
         "cor": "starlight-blue", "mascara": "DualSense", "alvo": True}]
FALSO = {
    "uniq": UNIQ, "player": 1, "connected": True, "battery_pct": 95, "transport": "usb",
    "vpad_backend": "uhid", "lightbar_rgb": [0, 0, 255], "is_primary": True,
    "inputs": {"lx": 127, "ly": 128, "rx": 127, "ry": 128, "l2_raw": 0, "r2_raw": 0,
               "buttons": []},
    "audio": {"mic_mudo": False, "mic_mudo_desejado": None},
    "speaker": {"volume": 102, "muted": False},
}


@pytest.fixture
def perfil_no_disco() -> Iterator[str]:
    """Um perfil no disco e os dois marcadores da sessão apontando para ele.

    A ÂNCORA É O LAR DO `passwd`, não o `$HOME`: o `$HOME` é o que o desvio do
    `conftest` mexe, e perguntá-lo seria conferir o desvio com ele mesmo (o
    molde é `test_a_perna_que_falta_01_a_segunda_perna_do_perfil_ativo`).
    """
    lar_real = pathlib.Path(pwd.getpwuid(os.getuid()).pw_dir).resolve()
    alvo = profiles_dir(ensure=True).resolve()
    assert not alvo.is_relative_to(lar_real), (
        f"profiles_dir() caiu DENTRO do lar real dela: {alvo}. Esta régua grava "
        "perfil e marcadores — sem o desvio do `conftest` ela gravaria no "
        "~/.config que o daemon vivo está usando agora.")
    mask_mod._zerar_registro_de_mascaras()
    try:
        save_profile(Profile(name=NO_DISCO, match=MatchManual()), origem="regua")
        sessao.save_last_profile(NO_DISCO)
        sessao.save_active_marker(NO_DISCO)
        yield NO_DISCO
    finally:
        mask_mod._zerar_registro_de_mascaras()


def _com_o_daemon_calado() -> Contexto:
    """O daemon responde `active_profile: null` — o estado da máquina dela."""
    return Contexto(state={"active_profile": None, "rumble_policy": "balanceado"},
                    mesa=[dict(m) for m in MESA], conectados=[dict(FALSO)], estados={})


def _o_que_o_chip_recebe(pagina: str, ctx: Contexto) -> Any:
    """As três linhas de `hefesto_vivo.py`, na ordem em que o piloto as roda.

    O valor devolvido é o que o pintor recebe para o `data-campo="perfil"` do
    `topo.html` — não o que o pacote devolveu antes de o cabeçalho entrar.
    """
    bruto = pacotes.pacote_da_pagina(pagina, ctx) or {}
    carga = pacotes.normalizar(bruto, {UNIQ: "p1"})
    for chave, valor in pacotes.topo(ctx).items():
        carga["mesa"].setdefault(chave, valor)
    return carga["mesa"].get("perfil")


def test_o_dono_do_chip_acha_o_perfil_do_disco(perfil_no_disco: str) -> None:
    """Sem esta, a régua das dez compararia «—» com «—» e passaria por vacuidade."""
    assert set(ABAS) <= set(pacotes.PACOTES), (
        f"faltam abas na tabela de pacotes: {sorted(set(ABAS) - set(pacotes.PACOTES))}")
    ativo = pacotes.topo(_com_o_daemon_calado())["perfil"]
    assert ativo == perfil_no_disco, (
        f"com o daemon calado, `pacotes.topo()` escreveu {ativo!r} e o disco diz "
        f"{perfil_no_disco!r} — a segunda perna do dono não achou o marcador")


def test_a_regua_pega_um_pacote_que_emite_perfil(
        perfil_no_disco: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua sabe recusar: um pacote que emite `perfil` vence o dono no piloto."""
    pagina = "05-vibracao.html"
    original = pacotes.PACOTES[pagina]
    monkeypatch.setitem(pacotes.PACOTES, pagina,
                        lambda ctx: {**original(ctx), "perfil": ""})
    assert _o_que_o_chip_recebe(pagina, _com_o_daemon_calado()) == "", (
        "o segundo dono dublado não chegou ao chip — o caminho desta régua deixou "
        "de ser o do piloto, e a régua das dez passaria com o defeito de volta")


def test_as_dez_abas_pintam_o_mesmo_nome_no_chip(perfil_no_disco: str) -> None:
    """Com o daemon calado e um perfil no disco, o chip diz o mesmo nome nas dez."""
    ctx = _com_o_daemon_calado()
    pintado = {aba: _o_que_o_chip_recebe(aba, ctx) for aba in ABAS}
    fora = {aba: valor for aba, valor in pintado.items() if valor != perfil_no_disco}
    assert not fora, (
        f"com o perfil {perfil_no_disco!r} no disco e o daemon calado, estas abas "
        f"pintam outro valor no chip «Perfil ativo»: {fora}. Um pacote de aba "
        f"voltou a emitir `perfil`, e o piloto completa o cabeçalho com "
        f"`setdefault` — quem chega primeiro ganha, e o pacote chega primeiro.")
