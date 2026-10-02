#!/usr/bin/env python3
"""A aba Jogar LÊ o que mostra — o interruptor, o chip, a máscara e os avisos.

POR QUE ESTA RÉGUA EXISTE, e o que ela mede foi fotografado em 02/09/2026 e
remedido no daemon dela em 03/09. Com ``native_mode false`` e
``gamepad_emulation.enabled false`` — logo ``mode_of_state`` = **desktop** — a
página publicada mostrava, ao mesmo tempo:

    interruptor      **Ligado**       (o `<input>` do arquivo nasce `checked`)
    fileira de modo  **Sony DualSense** aceso (`aba01.MODO_ACESO`, cravado)
    cartão do P2     **Xbox 360** aceso, com o daemon em `flavor=dualsense`
    coluna Atenção   selo verde **CERTO** sob o cabeçalho laranja "Atenção"
    conta            "3 avisos", com UM par `aviso-selo`/`aviso-texto` na página

Nenhuma dessas quatro coisas era atraso de tique: **não havia quem repintasse**.
A página tinha 11 `data-campo` e ZERO `data-hef-quando`, então nenhum ESTADO —
posição do interruptor, chip aceso, máscara acesa — chegava do daemon.

O QUE A RÉGUA COBRA, e cada item é uma forma de a cura morrer calada:

* o pacote **lê** os três estados (posição, chip, máscara) das funções do
  produto, e a régua troca essas funções para provar que ele as segue — uma
  régua que comparasse textos passaria com o pacote digitando o valor;
* **daemon calado não pinta nada.** É a armadilha desta aba: ``mode_of_state({})``
  devolve ``desktop``, então um pacote descuidado acende **Ligado** sobre um
  estado que ninguém leu;
* a coluna **Atenção** sai de ``painel.avisos_do_estado`` — as seis fontes puras
  da GTK — mais o opt-out antigo, e **não** dos achados `certo` do Check-up;
* o selo do exame é o do produto: a linha antiga montava
  ``{"selo": …, **i}`` e o ``**i`` sobrescrevia o selo pretendido;
* a página publica os endereços, na quantidade certa — um a menos deixa uma
  posição acesa para sempre;
* o ``ACHADO_DO_TIMEOUT`` fala do ``ponte.TETOS`` de hoje, e não dos 250 ms que
  a cura já tinha substituído.
"""
from __future__ import annotations

import collections
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.jogar.painel`, que carrega o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import monta
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.interface import aba01, onde
from pacotes import Contexto
from pacotes import a01_jogar as aba

VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense",
                          "wrapper_used": None, "mascara_divergente": None},
    "paused": False,
    "controllers": [{"uniq": "aa", "connected": True, "player_slot": 1}],
}
VIVO_GAMEPAD_XBOX: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": True, "flavor": "xbox", "caminho": "xbox"},
    "paused": False,
}
VIVO_NATIVO: dict[str, Any] = {
    "connected": True,
    "native_mode": True,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


UNIQ_A = "aa:bb:cc:00:00:01"
UNIQ_B = "aa:bb:cc:00:00:02"


def _com_mesa(state: dict[str, Any], por_aparelho: dict[str, str] | None = None,
              quantos: int = 1) -> Contexto:
    """Um contexto com mesa VIVA — a máscara passou a ser de cada cartão.

    A mesa sai de `mesa_viva.mesa_do_estado`, que é o dono do valor por
    aparelho: ela lê `gamepad_emulation.por_aparelho` e cai na máscara da
    sessão para quem não escolheu. Montá-la à mão aqui seria escrever a regra
    de herança uma segunda vez, e a de cá envelheceria sozinha.
    """
    from hefesto_dualsense4unix.interface import mesa_viva

    conectados = [
        {"uniq": u, "connected": True, "player_slot": i, "transport": t}
        for i, (u, t) in enumerate(((UNIQ_A, "usb"), (UNIQ_B, "bluetooth"))[:quantos],
                                   start=1)
    ]
    cheio = {**state, "controllers": conectados}
    if por_aparelho is not None:
        emul = dict(cheio.get("gamepad_emulation") or {})
        emul["por_aparelho"] = por_aparelho
        cheio["gamepad_emulation"] = emul
    mesa = mesa_viva.mesa_do_estado(cheio, {})
    return Contexto(state=cheio, mesa=mesa, conectados=conectados, estados={})


def _mascaras_dos_cartoes(ctx: Contexto) -> list[str]:
    """O que cada cartão recebeu, na ordem da mesa."""
    return [c["mascara-cartao"] for c in aba.pacote(ctx)["cartoes"].values()]


@pytest.mark.parametrize(
    ("state", "posicao", "chip"),
    [
        (VIVO_NAVEGACAO, "ligado", "navegacao"),
        (VIVO_GAMEPAD_XBOX, "ligado", "xbox"),
        (VIVO_NATIVO, "desligado", ""),
    ],
)
def test_o_interruptor_e_o_chip_saem_do_daemon(
    state: dict[str, Any], posicao: str, chip: str
) -> None:
    """Os três casos que a tela cravada errava — e o do meio é o que mais dói.

    Com o daemon em `desktop` a GTK marcaria "Controlar o PC"; a página mostrava
    **Ligado** + **Sony DualSense**. O `Ligado` até está certo (o Hefesto está no
    meio), mas por acaso: nada o tinha lido.

    COM UM CONTROLE NA MESA desde 22/09/2026: sem ninguém a fileira apaga
    inteira (`a01_jogar._a_fileira_com_a_mesa`, pedido dela), e o que esta régua
    mede é de onde vem o chip quando ele acende.
    """
    fora = aba.pacote(_com_mesa(state))
    assert fora["hef-posicao"] == posicao, (
        f"a posição do interruptor saiu {fora['hef-posicao']!r} com o daemon em "
        f"{painel.modo_vivo(state)!r}")
    assert fora["modo-aceso"] == chip, (
        f"o chip aceso saiu {fora['modo-aceso']!r} e o daemon está em "
        f"{painel.modo_vivo(state)!r}")


def test_a_mascara_do_cartao_e_a_do_aparelho() -> None:
    """Quem não escolheu segue a sessão — e é o cartão que recebe, não a página."""
    assert _mascaras_dos_cartoes(_com_mesa(VIVO_NAVEGACAO)) == ["DualSense"]
    assert _mascaras_dos_cartoes(_com_mesa(VIVO_GAMEPAD_XBOX)) == ["Xbox 360"]


def test_dois_controles_duas_mascaras() -> None:
    """A DECISÃO DELA, 03/09/2026: *"É uma máscara por controle."*

    ESTE É O DEFEITO QUE A CURA MATOU, e ele era de PINTURA, não de leitura:
    `mesa_viva` já trazia a máscara de cada aparelho, mas o pacote emitia
    `mascara-cartao` como valor DE PÁGINA — e o piloto escreve valor de página
    em todo elemento com aquele `data-campo`. A máscara da SESSÃO ia para os
    três chips dos quatro cartões, e dois controles com escolhas diferentes
    acendiam o MESMO chip.

    A MORDIDA: devolva `"mascara-cartao"` a `DA_PAGINA` e emita-o uma vez em
    `_estado_da_tela` — este teste reprova com os dois cartões em `DualSense`,
    que é exatamente o que a tela dela mostrava.
    """
    ctx = _com_mesa(VIVO_GAMEPAD_XBOX,
                    por_aparelho={UNIQ_A: "dualsense", UNIQ_B: "xbox"},
                    quantos=2)
    assert _mascaras_dos_cartoes(ctx) == ["DualSense", "Xbox 360"], (
        "os dois cartões receberam a mesma máscara — o valor voltou a ser da "
        "página, e a escolha por aparelho parou de chegar à tela")
    assert "mascara-cartao" not in aba.pacote(ctx), (
        "`mascara-cartao` voltou ao nível de página: o piloto o escreveria em "
        "TODOS os chips de TODOS os cartões, que é o defeito curado em 03/09")


def test_rotulo_desenhado_que_o_produto_nao_monta_fica_apagado(
    monkeypatch: Any,
) -> None:
    """O chip apaga quando a tela DESENHA um rótulo que o produto não monta."""
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    so_no_desenho = "Máscara Só Desenhada"
    assert so_no_desenho not in set(NOME_DA_MASCARA.values()), (
        "o rótulo de mentira virou rótulo de verdade — troque-o")
    monkeypatch.setattr(
        aba, "_MASCARAS_DESENHADAS",
        lambda: set(NOME_DA_MASCARA.values()) | {so_no_desenho})

    ctx = _com_mesa(VIVO_GAMEPAD_XBOX, por_aparelho={UNIQ_A: so_no_desenho})
    assert _mascaras_dos_cartoes(ctx) == [""], (
        "um rótulo que a tela desenha e o produto não sabe montar acendeu um "
        "chip — o cartão passou a afirmar uma máscara que o daemon recusa")

    ctx = _com_mesa(VIVO_GAMEPAD_XBOX, por_aparelho={UNIQ_A: "nem desenhado"})
    assert _mascaras_dos_cartoes(ctx) == ["Xbox 360"], (
        "os dois silêncios voltaram a ser um só: um nome que a tela nem "
        "desenha tem de herdar a sessão, não apagar o chip")


def test_a_nintendo_pro_acende_como_as_outras_duas() -> None:
    """A máscara nova é chip de primeira classe — 07/09/2026, ordem dela."""
    from hefesto_dualsense4unix.daemon.subsystems.external_mask import (
        mascaras_validas,
    )
    from hefesto_dualsense4unix.interface.mesa_viva import NOME_DA_MASCARA

    assert "nintendo" in mascaras_validas(), (
        "a máscara saiu do catálogo — se foi decisão dela, este teste cai "
        "junto; se não foi, o chip dela apagou na tela sem ninguém pedir")

    for sabor in sorted(mascaras_validas()):
        rotulo = NOME_DA_MASCARA.get(sabor)
        assert rotulo, (
            f"{sabor!r} está no catálogo e não tem rótulo em `NOME_DA_MASCARA` "
            "— o chip dele nasce cinza na tela dela")
        ctx = _com_mesa(VIVO_GAMEPAD_XBOX, por_aparelho={UNIQ_A: sabor})
        assert _mascaras_dos_cartoes(ctx) == [rotulo], (
            f"o cartão não acendeu o chip de {sabor!r}: a escolha por aparelho "
            "não chegou à tela")


def test_o_daemon_calado_nao_acende_nada() -> None:
    """A armadilha desta aba: `mode_of_state({})` devolve **desktop**.

    Ele só devolve `None` para um NÃO-dicionário. Sem a guarda, um tique sem
    resposta acenderia **Ligado** e o chip **Navegação** sobre um estado que
    ninguém leu — a tela afirmando com o Hefesto fora do ar.
    """
    fora = aba.pacote(_ctx({}))
    assert fora["hef-posicao"] == ""
    assert fora["modo-aceso"] == ""
    assert fora["cartoes"] == {}


def test_a_leitura_e_do_produto_e_nao_uma_copia(monkeypatch: Any) -> None:
    """Troca os dois leitores do produto e cobra que o pacote os siga."""
    # DualSense» acendia. AGORA troca `painel.caminho_vivo` e cobra que o chip
    from hefesto_dualsense4unix.app.actions import home_actions

    monkeypatch.setattr(painel, "hefesto_ligado", lambda _s: False)
    monkeypatch.setattr(painel, "modo_vivo", lambda _s: "gamepad")
    monkeypatch.setattr(painel, "caminho_vivo", lambda _s: "xbox")
    monkeypatch.setattr(home_actions, "mascara_do_aparelho", lambda _s: "dualsense")
    fora = aba.pacote(_com_mesa(VIVO_NAVEGACAO))
    assert fora["hef-posicao"] == "desligado", (
        "o pacote deixou de usar `painel.hefesto_ligado` — a posição virou cópia")
    assert fora["modo-aceso"] == "xbox", (
        "o pacote deixou de usar `painel.modo_vivo` + `painel.caminho_vivo` — ou "
        "voltou a acender o chip de modo pela máscara")


def test_a_mascara_do_cartao_tem_a_MESA_por_dona() -> None:  # noqa: N802
    """Quem responde pela máscara de um aparelho é `mesa_viva`, e não o pacote.

    A REGRA DE HERANÇA MORA NO REGISTRO (`external_mask.mascara_efetiva`) e
    chega à tela por `mesa_viva.mesa_do_estado`, que lê `por_aparelho` e cai na
    sessão para quem não escolheu. Se o pacote relesse o `state` por conta
    própria, seriam DUAS verdades sobre o mesmo fato — e a de cá envelheceria no
    dia em que a herança mudasse.

    A RÉGUA TROCA A MESA em vez de comparar textos: um valor digitado no pacote
    passaria em todos os outros testes deste arquivo.
    """
    ctx = _com_mesa(VIVO_GAMEPAD_XBOX, por_aparelho={UNIQ_A: "dualsense"})
    assert _mascaras_dos_cartoes(ctx) == ["DualSense"], (
        "o cartão ignorou o que a mesa disse — o pacote voltou a ler o estado")

    sem_mascara = Contexto(
        state=ctx.state,
        mesa=[{k: v for k, v in m.items() if k != "mascara"} for m in ctx.mesa],
        conectados=ctx.conectados,
        estados={},
    )
    assert _mascaras_dos_cartoes(sem_mascara) == ["Xbox 360"], (
        "a mesa muda deixou de herdar a máscara da sessão")


VIVO_JOGO_SEM_ATALHO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "paused": False,
    "gamepad_emulation": {"enabled": True, "flavor": "dualsense",
                          "backend": "uhid", "wrapper_used": False},
    "window_detect_last_class": "steam_app_570",
    "controllers": [{"uniq": "aa", "connected": True, "player_slot": 1}],
}


def _sem_a_maquina(monkeypatch: Any) -> None:
    """Cala as DUAS fontes da coluna que perguntam ao HARDWARE desta máquina.

    **É ISTO QUE DERRUBOU NOVE RÉGUAS DESTE ARQUIVO, e a causa é uma só** —
    medida em 11/09/2026, na leva de `OS-VINTE-E-SEIS-VERMELHOS-01`. Em
    06/09 a **cura do travamento do USB** entrou como mais uma fonte de
    `a01_jogar._avisos`, e ela não pergunta ao ``state`` que estes testes
    montam: ela lê o disco — `/sys/module/snd_usb_audio/parameters/quirk_flags`
    e `/etc/modprobe.d/hefesto-dualsense-storm.conf`. O arquivo irmão
    (`test_a01_a_coluna_atencao_acende_o_mais_grave.py`) nasceu já calando-a,
    com a razão escrita no `_so_estes` dele; **este aqui não foi junto**, e as
    nove réguas da coluna passaram a responder sobre a máquina em que rodam.

    **O QUE FAZ A RÉGUA VIRAR É O QUE ESTÁ NO CABO AGORA, e não a máquina.**
    Há UMA máquina aqui (`MeowSystem`): a árvore dela e a de qualquer agente
    dividem o mesmo disco, e `/sys/module` e `/etc/modprobe.d` são da MÁQUINA,
    não da árvore — então a régua vira no TEMPO, não no lugar. O
    `snd_usb_audio` só é carregado quando há aparelho de áudio USB plugado, e
    um DualSense no cabo é um deles:

    * **sem áudio USB no cabo** — o módulo não foi carregado (e, se já
      estava, ele não cai no desplugue: módulo carregado não descarrega
      sozinho), o `quirk_flags` nem existe, sobra o drop-in de
      `/etc/modprobe.d`, e o
      veredito é ``[INFO]``: *"a cura está agendada"*. Uma linha de selo
      ``CONTROLE`` entra na coluna, e as nove reprovam com nove diffs
      diferentes da MESMA causa. **É o estado de 11/09/2026**, medido:
      `/proc/asound/cards` sem nenhuma placa DualSense;
    * **com o módulo carregado trazendo o quirk** — veredito ``[ OK ]``,
      nenhuma linha a mais na coluna, as nove VERDES.

    OS DOIS LADOS, sem plugar nada — `check_snd_quirk` é pura quando se dá o
    texto do `quirk_flags`::

        .venv/bin/python -c "from hefesto_dualsense4unix.integrations.storm_doctor \
            import check_snd_quirk as c; print(c()); \
            print(c('054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m'))"
        ('[INFO]', 'a cura do travamento está agendada. …')  ← o cabo de hoje
        ('[ OK ]', 'cura do travamento do USB ATIVA …')      ← o quirk no ar

    **O ``[ OK ]`` NÃO FOI OBSERVADO AQUI com controle no cabo** — ele saiu da
    função com o texto dado à mão, acima. **Mas ele JÁ FOI VISTO VIVO nesta
    máquina**, do sysfs real, em 06/09/2026 e com a bancada LIVRE a sessão
    inteira: `docs/process/agentes/2026-09-06/ONDA5-01-01.md:53-62` registra o
    `/sys/module/snd_usb_audio/parameters/quirk_flags` EXISTINDO com o quirk e
    o `check_snd_quirk()` devolvendo ``[ OK ]``. É a prova de que o ramo bom é
    alcançável, e é por isso que ele não custa um gesto dela na bancada: esta
    casa já pagou essa medição.

    `_do_exame` ENTRA PELO MESMO MOTIVO, e não por asseio: ele chama
    `a08_conexoes._exame()`, que examina os controles que estão na mesa AGORA.
    Com a mesa VAZIA ele cala, e por isso as quatro réguas do selo ``JOGO``
    nunca precisaram silenciá-lo — com os quatro DualSense na mesa ele fala, e
    as mesmas quatro caem de novo por outro nome. **A virada é a mesma da cura
    do travamento: o que muda é o que está plugado no minuto em que a suíte
    roda.** Calar um e deixar o outro seria pagar este diagnóstico duas vezes.

    **O QUE ESTE ARQUIVO NÃO MEDE, e tem dono:** a cura do travamento é de
    `test_a01_a_coluna_atencao_acende_o_mais_grave.py`, que a exercita com a
    função REAL sobre uma máquina de fixture; o exame da mesa é das réguas da
    `a08`. Aqui o assunto é outro — o que a coluna faz com o que as fontes
    dizem.

    A NEUTRALIZAÇÃO NÃO APODRECE CALADA: `monkeypatch.setattr` levanta
    `AttributeError` se um dos dois nomes sumir do produto, então uma
    renomeação grita em vez de devolver as nove réguas à máquina.
    """
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", lambda: None)


@pytest.fixture()
def duas_listas_vazias(tmp_path: Any, monkeypatch: Any) -> Any:
    """As DUAS listas de recusa em disco, num diretório só deste teste."""
    from hefesto_dualsense4unix.app.actions import launch_wrapper_dialog as lwd
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    dispensados = tmp_path / "launch_dialog_dismissed.json"
    sem_wrapper = tmp_path / "jogos_sem_wrapper.txt"
    monkeypatch.setattr(lwd, "_dismissed_path", lambda **_: dispensados)
    monkeypatch.setattr(slo, "sem_wrapper_path", lambda *_a, **_k: sem_wrapper)
    _sem_a_maquina(monkeypatch)
    return lwd, slo


def _coluna(ctx: Contexto) -> tuple[list[str], list[str]]:
    """Os selos e os textos do CANAL de avisos, na ordem da gravidade."""
    fora = aba._em_ordem(aba._avisos(ctx))
    return [a["selo"] for a in fora], [a["texto"] for a in fora]


def test_o_aviso_do_jogo_sem_atalho_acende_na_coluna(duas_listas_vazias: Any) -> None:
    """Sem recusa nenhuma, a coluna acusa — e é do dono que a frase vem."""
    from hefesto_dualsense4unix.app.actions import home_actions

    selos, textos = _coluna(_ctx(VIVO_JOGO_SEM_ATALHO))
    assert selos == ["JOGO"], f"a coluna não acendeu o aviso do jogo: {selos!r}"
    assert textos == [home_actions.WRAPPER_MISSING_TEXT], (
        "o texto da coluna deixou de ser o do dono")


def test_a_bancada_desta_aba_abre_a_pagina_que_a_aba_publica() -> None:
    """A BANCADA desta aba mediu o VAZIO — medido em 06/09/2026, ONDA5-07-03."""
    jogar_vivo = pytest.importorskip(
        "hefesto_dualsense4unix.interface.jogar_vivo",
        reason="a bancada precisa do Gtk/WebKit do sistema",
    )
    assert jogar_vivo.PAGINA.exists(), (
        f"a bancada da aba Jogar abre {jogar_vivo.PAGINA}, que não existe — "
        "ela mede o vazio e sai verde")
    assert jogar_vivo.PAGINA.samefile(onde.PUBLICADO / "01-jogar.html"), (
        f"a bancada abre {jogar_vivo.PAGINA}, e não a página que esta aba publica")


def test_a_coluna_atencao_sai_das_fontes_da_gtk(monkeypatch: Any) -> None:
    """Troca `painel.avisos_do_estado` e cobra que os avisos venham de lá.

    As seis fontes de `painel.AVISOS_DA_TELA` já existiam em `home_actions` e
    quem as chamava era a BANCADA (`interface/jogar_vivo.py`). O produto
    mostrava, no lugar delas, o Check-up da aba Conexões — dois conjuntos
    disjuntos, e o da GTK era o que respondia pelas perguntas desta tela.
    """
    monkeypatch.setattr(
        painel, "avisos_do_estado",
        lambda _s: [{"selo": "PAUSA", "texto": "de outro dono", "fonte": "x"}])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    selos, textos = _coluna(_ctx(VIVO_NAVEGACAO))
    assert "PAUSA" in selos, (
        "o pacote deixou de chamar `painel.avisos_do_estado`")
    assert "de outro dono" in textos


def test_uma_boa_noticia_nao_entra_na_coluna_atencao(monkeypatch: Any) -> None:
    """O `**i` que sobrescrevia o selo, e o que ele punha na tela dela."""
    _sem_a_maquina(monkeypatch)
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [
        {"selo": "CERTO", "titulo": "Economia de energia desligada", "grave": False},
        {"selo": "AJUSTAR", "titulo": "Dois rádios em portas vizinhas", "grave": True},
    ])
    selos, textos = _coluna(_ctx(VIVO_NAVEGACAO))
    assert "CERTO" not in selos, (
        "uma boa notícia voltou a aparecer sob o cabeçalho 'Atenção'")
    assert selos == ["AJUSTAR"], (
        f"o selo do exame não é mais o do produto: {selos!r}")
    assert textos[0] == "Dois rádios em portas vizinhas"


def test_uma_fonte_que_quebra_nao_apaga_a_coluna(monkeypatch: Any) -> None:
    """O `except` largo do `_do_exame` já comeu meia coluna calado uma vez.

    A política é a de `painel.avisos_do_estado`: a que falhou vira um aviso com
    o selo `ERRO`. Silêncio é o pior dos dois desfechos — ele se lê como "não
    havia achado nenhum".
    """
    def explode() -> list[dict[str, Any]]:
        raise RuntimeError("o exame caiu")

    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", explode)
    selos, _textos = _coluna(_ctx(VIVO_NAVEGACAO))
    assert "ERRO" in selos, (
        "o exame quebrou e a coluna ficou vazia — o silêncio voltou")


def test_nenhuma_fonte_fala_sem_este_arquivo_saber(monkeypatch: Any) -> None:
    """Caladas as fontes que este arquivo conhece, `_avisos` não diz NADA.

    **A RÉGUA QUE FALTAVA EM 06/09/2026, e a falta custou nove vermelhos.**
    Naquele dia a cura do travamento do USB virou mais uma fonte de
    `a01_jogar._avisos` — uma que lê o `/sys` e o `/etc` desta máquina. As
    nove réguas da coluna deste arquivo calavam as fontes uma a uma, pelo
    nome, e nenhuma sabia da décima: em 11/09 as nove reprovaram com nove
    diffs diferentes, e o trabalho foi descobrir que a causa era UMA.

    **O QUE ESTA AQUI COMPRA É O NOME.** Ela reprova UMA vez, e a mensagem
    diz o campo ``fonte`` de quem falou — que é literalmente o endereço da
    função a acrescentar em :func:`_sem_a_maquina`. Nove diffs de lista
    contra uma frase que manda no lugar certo.

    **O LIMITE, DECLARADO:** ela pega a fonte nova que FALA no estado em que a
    máquina está QUANDO a suíte roda. Uma fonte nova que esteja calada nesse
    minuto passa — e é por isso que ela não substitui `_sem_a_maquina`, só
    avisa mais cedo. Foi exatamente o caso da cura do travamento: ela responde
    ``[INFO]`` sem áudio USB no cabo (e aí FALA, e esta régua a pega) e
    ``[ OK ]`` com o quirk carregado (e aí cala, e esta régua não a veria). O
    lado que vira é o do CABO, não o da máquina — ver :func:`_sem_a_maquina`.

    AS FONTES QUE ESTE ARQUIVO CONHECE são as puras de estado — que
    `VIVO_NAVEGACAO` já responde — mais as duas de máquina de
    `_sem_a_maquina` e as duas que voltam em markup (`painel.avisos_do_estado`
    e `_aviso_da_ponte`), que os testes acima calam pelo nome.
    """
    _sem_a_maquina(monkeypatch)
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    sobrando = aba._avisos(_ctx(VIVO_NAVEGACAO))
    assert sobrando == [], (
        "uma fonte que este arquivo não conhece acendeu a coluna: "
        + ", ".join(f"{a.get('fonte')} ({a.get('selo')})" for a in sobrando)
        + " — acrescente-a a `_sem_a_maquina` se ela perguntar à máquina, "
        "ou cale-a pelo nome no teste que a tiver por assunto")


def _em_trabalho() -> bool:
    arquivo = onde.BANCADA / "DIVERGENCIAS.md"
    if not arquivo.exists():
        return False
    corpo = arquivo.read_text(encoding="utf-8").split("\n---\n", 1)[-1]
    return "\n## 01-jogar.html" in f"\n{corpo}"


def _atras_so_por_endereco() -> bool:
    import importlib.util

    alvo = RAIZ / "scripts" / "check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("_desenho_aprovado", alvo)
    if spec is None or spec.loader is None:  # pragma: no cover - defesa
        return False
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    nome = "01-jogar.html"
    bancada, produto = onde.BANCADA / nome, onde.PUBLICADO / nome
    if not produto.exists() or bancada.read_bytes() == produto.read_bytes():
        return False
    return bool(modulo.so_mudou_endereco(nome))


@pytest.mark.parametrize("publicado", [False, True])
def test_a_pagina_publica_os_enderecos_na_quantidade_certa(publicado: bool) -> None:
    """Um endereço a menos deixa uma posição acesa para sempre."""
    if publicado and _em_trabalho():
        pytest.skip("01-jogar está declarada em trabalho no `mockup/DIVERGENCIAS.md`: "
                    "o produto recebe no `--publicar`, que é ato de quem coordena")
    if publicado and _atras_so_por_endereco():
        pytest.skip("o produto está atrás da bancada SÓ POR ENDEREÇO — nenhum "
                    "pixel mudou. Fecha com: scripts/check_o_desenho_aprovado.py "
                    "--publicar-enderecos 01")
    corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(encoding="utf-8")
    # exclusivo dos outros — «Sony DualSense» e «Steam Input» são verdade ao
    por_campo = collections.Counter(aba01._campo_do_chip(m) for m in aba01.MODOS)
    esperado = {
        "hef-posicao": len(aba01.INTERRUPTOR),
        "modo-aceso": por_campo["modo-aceso"],
        "steam-input-aceso": por_campo["steam-input-aceso"],
        "mascara-cartao": len(monta.MASCARAS) * len(aba01.MESA),
        "pendente-ha": 1,
    }
    for campo, quantos in esperado.items():
        achei = corpo.count(f'data-campo="{campo}" data-hef-alvo="classe"')
        assert achei == quantos, (
            f"{'publicado' if publicado else 'bancada'}: o endereço {campo!r} "
            f"aparece {achei} vezes e deviam ser {quantos}")
    cliques = corpo.count('data-gesto="mascara"')
    assert cliques == len(monta.MASCARAS) * len(aba01.MESA), (
        f"{'publicado' if publicado else 'bancada'}: o clique da máscara "
        f"alcança {cliques} chips e a mesa tem {len(aba01.MESA)} lugares")


def test_todo_endereco_que_o_pacote_emite_existe_na_pagina() -> None:
    """A régua nos DOIS sentidos — sem ela, o pacote emite para o vazio."""
    corpo = onde.pagina("01-jogar.html", publicado=not _em_trabalho()).read_text(
        encoding="utf-8")
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    for campo in fora:
        if campo in {"cartoes", "cobertura", "sem_dono", "blocos"}:
            continue
        assert f'data-campo="{campo}"' in corpo, (
            f"o pacote emite {campo!r} e a página publicada não tem onde escrever")


def test_a_cena_da_coluna_atencao_continua_com_um_aviso() -> None:
    """A CENA MUDOU POR ORDEM DELA — 07/09/2026, e esta régua trocou de sinal."""
    for publicado in (False, True):
        corpo = onde.pagina("01-jogar.html", publicado=publicado).read_text(
            encoding="utf-8")
        onde_ = "publicado" if publicado else "bancada"
        for morto in ('class="aviso-item', 'class="col-atencao"',
                      'class="conta-avisos"',
                      'data-campo="aviso-vivo"', 'data-campo="atencao-conta"'):
            assert morto not in corpo, f"{onde_}: a coluna Atenção voltou ({morto!r})"
        assert corpo.count('data-gesto="reconectar"') == 1, (
            f"{onde_}: o botão Reconectar Controles sumiu — ele é o que ela "
            f"mandou DEIXAR, e uma régua que só proíbe passaria sem ele")


def test_os_metodos_da_troca_de_modo_tem_a_folga_do_produto() -> None:
    """`ACHADO_DO_TIMEOUT` afirmava 250 ms; `ponte.TETOS` já dava 2,0 s."""
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_IPC_TIMEOUT_S
    from pacotes import ponte

    # `gamepad.mask.set` entrou em `METODOS` junto com a cura da chamada dele, e
    # `mouse.emulation.restore` saiu do conjunto porque saiu do PLANO, e o passo
    # razão do `gamepad.mask.set`, com o sinal trocado: ele abre um `.json` de
    # perfil do disco e tem teto PRÓPRIO de 3,0 s, a família do `profile.switch`.
    for metodo in aba.METODOS_DA_TROCA_DE_MODO:
        assert ponte.teto(metodo) == MODE_IPC_TIMEOUT_S, (
            f"{metodo} espera {ponte.teto(metodo)}s e o produto declara "
            f"{MODE_IPC_TIMEOUT_S}s para trocar de modo")
    assert "TETOS" in aba.ACHADO_DO_TIMEOUT and "2,0 s" in aba.ACHADO_DO_TIMEOUT, (
        f"o fato caduco voltou — o texto precisa nomear a tabela que já dá a "
        f"folga: {aba.ACHADO_DO_TIMEOUT!r}")


def test_o_arranjo_do_desktop_tem_teto_proprio_e_maior() -> None:
    """O passo que abre perfil não pode cair nos 250 ms do bridge.

    Ele está FORA de `METODOS_DA_TROCA_DE_MODO`, e sem esta régua esse "fora"
    seria um teto esquecido: `ponte.teto()` devolve o default de 250 ms para
    todo método ausente da tabela, em silêncio. É o mesmo furo que o
    `gamepad.mask.set` deixou aberto até 04/09.
    """
    from hefesto_dualsense4unix.app.actions.mode_transition import MODE_IPC_TIMEOUT_S
    from pacotes import ponte

    assert "desktop.arranjo.apply" in aba.METODOS, (
        "o arranjo do desktop saiu da declaração desta aba — e é o terceiro "
        "passo do modo Navegação."
    )
    teto = ponte.teto("desktop.arranjo.apply")
    assert teto > MODE_IPC_TIMEOUT_S, (
        f"o arranjo tem teto de {teto}s contra os {MODE_IPC_TIMEOUT_S}s da "
        "troca de modo. Ele faz MAIS: abre um perfil do disco além de falar "
        "com os devices."
    )
