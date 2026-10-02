#!/usr/bin/env python3
"""Os controles que o Hefesto VÊ e NÃO adota chegam à aba 01 e à aba 08.

**EXTERNOS-01, 06/09/2026 — as linhas 16 e 305 de
`docs/data/paridade-gtk-html.csv`**, e as duas descrevem o mesmo silêncio:

* linha 16 (`01-jogar`) — *"com dois DualSense e um 8BitDo na mesa a aba dizia
  '2 controles' ao lado de três cards noutra tela"*. A janela antiga fechou isso
  em 25/08 (a `I5`); a tela nova nasceu com o defeito de volta;
* linha 305 (`08-conexoes`) — *"uma aba chamada Conexões que não lista metade
  dos controles conectados"*.

**O `porque` das duas era o mesmo, e era um grep:** *"não é ausência de dado —
`controller.list {external:true}` responde; ninguém pergunta"*. Esta régua mede
que alguém passou a perguntar, e que a resposta chega à tela.

**O DUBLÊ É DO `controller.list`, E ELE SABE RECUSAR.** Régua que só sabe passar
não é régua (`COMO-EXECUTAR-UMA-SPRINT.md` §4): o teste do daemon mudo exercita
o caminho de erro, e é ele que prova que uma leitura que FALHOU não apaga a
lista boa — a confusão que esta casa chama de *ausência de notícia lida como
sucesso*.

**SEM APARELHO NA BANCADA.** Não havia Nintendo Pro nem 8BitDo na mesa em
06/09/2026 (medido em `/sys/bus/hid/devices`: só `054C:0CE6` e `054C:0DF2`,
os dois Sony). A prova de aparelho fica para a `MESA-DE-QUATRO-01`; o que se
mede aqui é o caminho inteiro do payload até o HTML, com o payload que o daemon
publica — a forma está escrita em `daemon/ipc_handlers._handle_controller_list`.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a01_jogar as jogar

UM_8BITDO: dict[str, Any] = {
    "name": "8BitDo Pro 2",
    "vid": "2dc8",
    "pid": "6003",
    "bus": "bluetooth",
    "uniq": "e4:17:d8:00:00:2f",
    "driver": "hid-generic",
    "player_slot": 3,
}

UM_PRO: dict[str, Any] = {
    "name": "Pro Controller",
    "vid": "057e",
    "pid": "2009",
    "bus": "bluetooth",
    "uniq": "e4:17:d8:00:00:5b",
    "driver": "hid-nintendo",
    "player_slot": 4,
}

VIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(externos: list[dict[str, Any]]) -> Contexto:
    return Contexto(state=dict(VIVO), mesa=[], conectados=[], externos=externos)


def test_o_externo_nao_entra_nos_assentos() -> None:
    """`externos` é campo próprio: nunca dentro de `conectados` nem de `mesa`."""
    ctx = _ctx([UM_8BITDO])
    assert ctx.externos == [UM_8BITDO]
    assert ctx.conectados == []
    assert ctx.mesa == []


def test_o_contexto_nasce_sem_externo_nenhum() -> None:
    """Sem a chave, a lista é vazia — e vazia quer dizer "não desenha nada"."""
    assert Contexto(state={}).externos == []


def test_a_jogar_escreve_o_cartao_do_externo() -> None:
    """O cartão traz o NÚMERO, a MARCA e o transporte, pelos donos da frase."""
    html = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    assert 'class="ext-cartao"' in html
    # de player do aparelho. Ele vem do `player_slot` que o daemon mandou, e não
    assert "Controle 3" in html
    assert "8BitDo" in html
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )
    assert palavra_do_transporte("bt") in html
    assert "bluetooth" not in html.lower()
    assert "só vê" in html


def test_a_jogar_escreve_um_cartao_por_externo() -> None:
    html = jogar.pacote(_ctx([UM_8BITDO, UM_PRO]))["externos"]
    assert html.count('class="ext-cartao"') == 2
    assert "Controle 3" in html and "Controle 4" in html


def test_a_jogar_apaga_a_secao_quando_nao_ha_externo() -> None:
    """Vazio é o MARCADOR `.nada` — e `""` deixava um travessão solto na grade.

    Uma frase de "nenhum controle externo" acusaria ausência, e nenhuma das duas
    abas acusa: a lista vazia é *"não há"* **e** *"ainda não perguntei"*. O que
    mudou em 07/09/2026 é COMO se diz "nada".

    **O DEFEITO ESTAVA NA TELA DELA, e foi fotografado:** com quatro DualSense na
    mesa e nenhum externo, a aba Jogar mostrava um `—` solto logo abaixo dos
    quatro cartões. `escrever()` troca valor vazio por travessão de propósito
    (`hefesto_vivo.py`), a `.ext-vaga` é `display:contents`, e esse travessão
    virava um item anônimo da grade `.pecas` — um quinto assento com um traço
    dentro. O `<i class="nada">` da página não salvava: o alvo `html` troca o
    miolo inteiro na primeira pintura.

    A MORDIDA: devolva `""` em qualquer um dos DOIS `return` de
    `_html_dos_externos` e esta régua reprova. **São dois de propósito** — a
    saída curta (`if not ctx.externos`) é o caminho que a máquina dela percorre,
    e curar só o de baixo deixa o travessão exatamente onde ela o viu. Foi o que
    aconteceu na primeira volta desta cura.
    """
    import monta

    vazio = jogar.pacote(_ctx([]))["externos"]
    assert vazio == monta.NADA_A_DIZER, (
        f"a Jogar sem externo devolveu {vazio!r} — com `''` o piloto escreve "
        f"`—` e a grade dos assentos ganha um quinto item com um traço dentro")
    assert ".ext-vaga > .nada{display:none}" in (
        INTERFACE / "aba01.py").read_text(encoding="utf-8"), (
        "a regra que esconde o marcador saiu do CSS da aba 01")


def _a_saida_estavel() -> str:
    """O fim do aviso do `hid-nintendo`, com a palavra PERGUNTADA ao dono."""
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    return f"pelo {palavra_do_transporte('usb')} é estável"


def test_a_jogar_avisa_a_armadilha_do_driver_so_no_nintendo() -> None:
    """O aviso do `hid-nintendo` nasce no Pro por rádio, e em mais ninguém."""
    do_pro = jogar.pacote(_ctx([UM_PRO]))["externos"]
    assert _a_saida_estavel() in do_pro
    do_8bitdo = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    assert _a_saida_estavel() not in do_8bitdo


def test_a_jogar_nao_inventa_cor_de_plastico_para_o_externo() -> None:
    """A folha das 28 cores é dos DualSense — um 8BitDo não tem linha nela.

    Uma borda colorida aqui seria a tela afirmando um modelo que ninguém mediu,
    que é a mesma regra que faz `_cor_do_plastico` devolver `""`.
    """
    html = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    assert "--plastico" not in html
    assert "data-colorway" not in html


def test_o_externo_nao_usa_a_classe_dos_assentos() -> None:
    """`.cartao` e `data-controle` são dos quatro assentos, e só deles."""
    html = jogar.pacote(_ctx([UM_8BITDO, UM_PRO]))["externos"]
    assert 'class="cartao' not in html
    assert "data-controle" not in html


def test_o_endereco_dos_externos_esta_prometido_na_pagina() -> None:
    """`externos` está em `DA_PAGINA` — senão a `cobertura` mente."""
    assert "externos" in jogar.DA_PAGINA


def test_a_conexoes_lista_o_externo() -> None:
    from pacotes import a08_conexoes as conexoes

    html = conexoes._html_dos_externos(_ctx([UM_PRO]))
    assert 'class="ext-linha"' in html
    assert "Controle 4" in html
    assert "só vê" in html
    assert _a_saida_estavel() in html


def test_a_conexoes_apaga_a_lista_quando_nao_ha_externo() -> None:
    from pacotes import a08_conexoes as conexoes

    assert conexoes._html_dos_externos(_ctx([])) == ""


def test_as_duas_abas_dizem_a_mesma_coisa_do_mesmo_aparelho() -> None:
    """O nome e o transporte batem entre as duas — um dono, duas telas."""
    from pacotes import a08_conexoes as conexoes

    do_01 = jogar.pacote(_ctx([UM_8BITDO]))["externos"]
    do_08 = conexoes._html_dos_externos(_ctx([UM_8BITDO]))
    from hefesto_dualsense4unix.app.actions.home_actions import (
        palavra_do_transporte,
    )

    for pedaco in ("Controle 3", "8BitDo", palavra_do_transporte("bt"), "só vê"):
        assert pedaco in do_01 and pedaco in do_08, pedaco


def test_as_duas_paginas_da_bancada_tem_onde_escrever() -> None:
    """O `data-campo` com alvo `html` está nas duas páginas da bancada."""
    for arquivo, campo in (("01-jogar.html", "externos"),
                           ("08-conexoes.html", "externos-lista")):
        texto = onde.pagina(arquivo).read_text()
        assert f'data-campo="{campo}" data-hef-alvo="html"' in texto, arquivo


def test_nenhum_aparelho_de_exemplo_nasce_no_desenho() -> None:
    """A página parada não afirma um externo — quem afirma é o produto."""
    for arquivo, marca in (("01-jogar.html", 'class="ext-cartao"'),
                           ("08-conexoes.html", 'class="ext-linha"')):
        assert marca not in onde.pagina(arquivo).read_text(), arquivo


class _PilotoDeMentira:
    """O mínimo do piloto que a leitura dos externos toca."""

    def __init__(self) -> None:
        self._externos: list[dict[str, Any]] = []
        self._externos_lidos_em = 0.0
        self._externos_no_ar = False
        self.leitor = _LeitorDeMentira()

    SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS = (
        __import__("hefesto_dualsense4unix.interface.hefesto_vivo",
                   fromlist=["Piloto"]).Piloto.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS)
    SEGUNDOS_DE_ESPERA_DOS_EXTERNOS = (
        __import__("hefesto_dualsense4unix.interface.hefesto_vivo",
                   fromlist=["Piloto"]).Piloto.SEGUNDOS_DE_ESPERA_DOS_EXTERNOS)

    _talvez_ler_os_externos = (
        __import__("hefesto_dualsense4unix.interface.hefesto_vivo",
                   fromlist=["Piloto"]).Piloto._talvez_ler_os_externos)


class _LeitorDeMentira:
    """O leitor de cor do plástico, calado. Ele não é o assunto desta régua."""

    def conhecidos(self) -> dict[str, Any]:
        return {}

    def esquecer_ausentes(self, _vivos: set[str]) -> None:
        return None

    def disparar(self, _entradas: list[dict[str, Any]]) -> None:
        return None


def _ler(piloto: _PilotoDeMentira, resposta: Any, levanta: bool = False) -> None:
    """Roda `_talvez_ler_os_externos` com um `controller.list` de mentira."""
    import threading

    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface.pacotes import ponte

    chamadas: list[tuple[str, dict[str, Any]]] = []

    def falso(metodo: str, timeout: float | None = None, **params: Any) -> Any:
        chamadas.append((metodo, params))
        if levanta:
            raise RuntimeError("o daemon não respondeu a controller.list")
        return resposta

    vivas = set(threading.enumerate())
    antes = ponte.resultado
    ponte.resultado = falso  # type: ignore[assignment]
    try:
        hefesto_vivo.Piloto._talvez_ler_os_externos(piloto)  # type: ignore[arg-type]
        for t in threading.enumerate():
            if t not in vivas:
                t.join(timeout=5)
    finally:
        ponte.resultado = antes  # type: ignore[assignment]
    piloto.chamadas = getattr(piloto, "chamadas", []) + chamadas  # type: ignore[attr-defined]


def test_o_piloto_pergunta_pelos_externos_com_o_opt_in() -> None:
    """A pergunta é `controller.list {"external": True}` — sem o opt-in, nada vem."""
    p = _PilotoDeMentira()
    _ler(p, {"controllers": [], "external": [UM_8BITDO]})
    assert p.chamadas == [("controller.list", {"external": True})]  # type: ignore[attr-defined]
    assert p._externos == [UM_8BITDO]


def test_o_piloto_nao_repete_a_pergunta_dentro_do_teto() -> None:
    """Uma leitura por `SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS`, e não uma por tique."""
    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    _ler(p, {"external": [UM_PRO]})
    assert len(p.chamadas) == 1  # type: ignore[attr-defined]
    assert p._externos == [UM_8BITDO]


def test_o_daemon_mudo_nao_apaga_a_lista_boa() -> None:
    """**A MORDIDA.** *"Não consegui perguntar"* não vira *"não há controle"*."""
    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    p._externos_lidos_em = 0.0
    _ler(p, None, levanta=True)
    assert p._externos == [UM_8BITDO]
    assert p._externos_no_ar is False


def test_a_resposta_sem_a_chave_external_esvazia_a_lista() -> None:
    """Um daemon que responde SEM a chave é resposta boa: não há externo."""
    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    p._externos_lidos_em = 0.0
    _ler(p, {"controllers": []})
    assert p._externos == []


def test_o_contexto_do_tique_carrega_os_externos_lidos() -> None:
    """**A MORDIDA QUE FALTAVA, e ela reprovou a primeira régua desta sprint.**"""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    p = _PilotoDeMentira()
    _ler(p, {"external": [UM_8BITDO]})
    ctx, _ = hefesto_vivo.Piloto._contexto(p, dict(VIVO))  # type: ignore[arg-type]
    assert ctx.externos == [UM_8BITDO]
    assert ctx.conectados == []


def test_o_tique_pergunta_sozinho_pelos_externos() -> None:
    """`_contexto` DISPARA a leitura — senão a lista nunca sai de vazia."""
    from hefesto_dualsense4unix.interface import hefesto_vivo
    from hefesto_dualsense4unix.interface.pacotes import ponte

    p = _PilotoDeMentira()
    chamadas: list[str] = []

    def falso(metodo: str, timeout: float | None = None, **_: Any) -> Any:
        chamadas.append(metodo)
        return {"external": []}

    antes = ponte.resultado
    ponte.resultado = falso  # type: ignore[assignment]
    try:
        fios_antes = set(__import__("threading").enumerate())
        hefesto_vivo.Piloto._contexto(p, dict(VIVO))  # type: ignore[arg-type]
        for t in set(__import__("threading").enumerate()) - fios_antes:
            t.join(timeout=5)
    finally:
        ponte.resultado = antes  # type: ignore[assignment]
    assert chamadas == ["controller.list"]


def test_o_teto_de_tempo_e_o_da_janela_antiga() -> None:
    """Um número para a mesma pergunta — o da GTK, não um segundo escolhido aqui."""
    from hefesto_dualsense4unix.app.actions.home_actions import HomeActionsMixin
    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert (hefesto_vivo.Piloto.SEGUNDOS_ENTRE_LEITURAS_DOS_EXTERNOS
            == HomeActionsMixin.EXTERNOS_THROTTLE_S)
