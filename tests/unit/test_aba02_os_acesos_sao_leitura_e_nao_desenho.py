#!/usr/bin/env python3
"""OS QUATRO BOTÕES QUE DIZIAM "ESTE É O ESCOLHIDO" SEM LER NADA — 03/09/2026.

A aba Controles tem QUATRO botões de estado, em dois pares: a rota do
alto-falante (`Sons do jogo` / `Todo o som do PC`) e o modo do microfone
(`Virtual` / `Nativo`). Até hoje o aceso de todos eles era a classe `on` que o
gerador escreveu **uma vez**, no dia em que montou o arquivo.

O QUE ESTAVA NA TELA DELA, medido com o daemon vivo em 03/09/2026:

    na tela (o desenho)                no aparelho / no disco
    card 2: "Todo o som do PC" aceso   speaker.rota = 2  (= Sons do jogo)
    card 1: "Virtual" aceso            maquina.json sem `microfone` (= Nativo)

E O PRIMEIRO NÃO É UM ENGANO NEUTRO: aquele botão aceso AFIRMA que o som
inteiro do PC está saindo naquele controle. Se ela olhar a tela para responder
*"por que o som não vem pelo controle?"*, a tela responde errado.

OS DOIS PARES SÃO O MESMO DEFEITO COM DONOS DIFERENTES, e é por isso que as
curas não se parecem:

    alto-rota        o dono é o APARELHO — `speaker.rota`, publicado a cada
                     tique no `daemon.state_full`.
    mic-modo-aceso   o dono é o DISCO — a declaração dela no `maquina.json`. O
                     `machine.declare` fica FORA do `state_full` de propósito
                     (`a02_controles.SEM_ECO`), então não há eco a esperar.

POR QUE AS RÉGUAS QUE JÁ EXISTIAM SÃO CEGAS A ISTO, e as duas por construção: o
`casamento.medir` compara o que o pacote emite com os `data-campo` da página e
fechava PERFEITO — zero órfãos — justamente porque nenhum dos dois lados tinha
estes endereços; e a régua do mockup conta `data-campo`, e estes quatro botões
não tinham nenhum. As duas mediam o que existe; nenhuma mede o que a tela
AFIRMA sem ter lido.

A MORDIDA (arranque a cura, veja reprovar, devolva):

  * troque `rota_na_tela` por `return "jogo"` (o valor que a mesa dela dá hoje,
    e por isso o mais convincente): reprova em `test_a_rota_vem_do_byte_do_
    aparelho` e em `test_a_rota_desconhecida_nao_acende_botao_nenhum`;
  * tire o `data-hef-quando` de um dos quatro botões no gerador: reprova em
    `test_os_quatro_botoes_dizem_quem_sao_no_desenho`;
  * ponha o `data-campo` no `<span class="rota mic-modo">` que ENVOLVE os dois,
    em vez de em cada botão: reprova em
    `test_o_endereco_do_aceso_nao_mora_no_container`.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

BANCADA = RAIZ / "mockup/02-controles.html"
PUBLICADO = RAIZ / "src/hefesto_dualsense4unix/interface/paginas/02-controles.html"

#: MAC da faixa sintética da casa — há dois portões de anonimato nesta árvore.
UNIQ_CABO = "aa:bb:cc:00:00:01"


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


# ---------------------------------------------------------------------------
# 1. A ROTA — o dono é o aparelho
# ---------------------------------------------------------------------------
def test_a_rota_vem_do_byte_do_aparelho(a02):
    """Os dois bytes que estes dois botões significam, PERGUNTADOS ao dono.

    Os números não entram digitados: `ROTA_DO_CANAL` é o mapa que a GTK usa
    para exatamente estes dois botões (`controller_card.py:716`), e ele sai de
    `core/ds_output_report.py`. Uma régua com `== 2` envelheceria no dia em que
    o protocolo mudasse de número — e reprovaria a melhora.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import (
        CANAL_SONS_DO_JOGO,
        CANAL_TODO_O_PC,
        ROTA_DO_CANAL,
    )

    jogo = {"speaker": {"volume": 102, "rota": ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]}}
    tudo = {"speaker": {"volume": 102, "rota": ROTA_DO_CANAL[CANAL_TODO_O_PC]}}
    assert a02.rota_na_tela(jogo) == "jogo"
    assert a02.rota_na_tela(tudo) == "pc"


def test_a_rota_desconhecida_nao_acende_botao_nenhum(a02):
    """Rota 0 e 1 são do protocolo e NÃO são estes dois botões.

    `""` apaga os dois — o piloto escreve o travessão, e no alvo `classe` com
    `data-hef-quando` nem `jogo` nem `pc` casam com ele. Acender o "mais
    parecido" seria arredondar um byte para um botão.
    """
    from hefesto_dualsense4unix.core.ds_output_report import (
        SAIDA_ESTEREO_NO_FONE,
        SAIDA_MONO_NO_FONE,
    )

    for byte in (SAIDA_ESTEREO_NO_FONE, SAIDA_MONO_NO_FONE):
        assert a02.rota_na_tela({"speaker": {"volume": 102, "rota": byte}}) == ""


def test_sem_bloco_de_alto_falante_a_tela_nao_afirma_rota(a02):
    """O daemon só publica `speaker` depois do primeiro `speaker.set`.

    Antes dele NÃO HÁ leitura, e o desenho acendia um dos dois assim mesmo.
    """
    assert a02.rota_na_tela({"uniq": UNIQ_CABO}) == ""
    assert a02.rota_na_tela({"speaker": {"volume": 102}}) == ""
    assert a02.rota_na_tela(None) == ""


def test_a_rota_nao_confunde_booleano_com_byte(a02):
    """`True` é `int` em Python, e `ROTA_DO_CANAL.get(True)` acharia a rota 1.

    Um daemon que publicasse `rota: true` faria a tela acender um botão a partir
    de um valor que não é rota nenhuma.
    """
    assert a02.rota_na_tela({"speaker": {"volume": 102, "rota": True}}) == ""


def test_a_rota_sai_do_mesmo_bloco_que_o_volume(a02):
    """A régua ANTI-DERIVA das duas leituras da mesma regra.

    `_bloco_do_speaker` repete o que `speaker_do_entry` sabe sobre ONDE o bloco
    mora — nas duas posições em que o daemon o publica —, porque o dono devolve
    só `(volume, muted)` e a rota não passa por ele. Esta régua não digita as
    posições: ela **pergunta aos dois** sobre as mesmas entradas e cobra que
    achem o mesmo volume. Se o daemon mudar de lugar e só um acompanhar, ela
    reprova nomeando o caso.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import speaker_do_entry

    casos = {
        "de fora": {"speaker": {"volume": 102, "muted": False, "rota": 2}},
        "de dentro": {"inputs": {"speaker": {"volume": 40, "muted": True, "rota": 3}}},
        "nas duas": {"speaker": {"volume": 7, "rota": 2},
                     "inputs": {"speaker": {"volume": 99, "rota": 3}}},
        "em nenhuma": {"inputs": {"buttons": []}},
        "não é dict": {"speaker": "nada"},
    }
    for nome, entrada in casos.items():
        dono = speaker_do_entry(entrada)
        meu = a02._bloco_do_speaker(entrada)
        if dono is None:
            assert meu is None or meu.get("volume") is None, (
                f"{nome}: o dono não achou volume e o leitor da rota achou bloco")
            continue
        assert meu is not None, f"{nome}: o dono achou o bloco e o leitor da rota não"
        assert meu.get("volume") == dono[0], (
            f"{nome}: os dois leram blocos DIFERENTES — "
            f"{meu.get('volume')!r} contra {dono[0]!r}")


# ---------------------------------------------------------------------------
# 2. O MODO DO MICROFONE — o dono é o disco
# ---------------------------------------------------------------------------
def test_o_modo_do_mic_e_a_regra_da_gtk_so_true_e_virtual(a02, monkeypatch):
    """`meu.get("microfone") is True` — `secao_controles.py:876`, uma linha.

    Ausência e `False` deixam a ponte no chão do mesmo jeito, e por isso as duas
    são Nativo. É a mesma razão de o gesto gravar `None` ao desligar, em vez de
    `False`.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(a02, "_DECLARADOS", {
        "aabbcc000001": SimpleNamespace(microfone=True),
        "aabbcc000002": SimpleNamespace(microfone=False),
        "aabbcc000003": SimpleNamespace(microfone=None),
    })
    assert a02.modo_do_mic("aabbcc000001") == "virtual"
    assert a02.modo_do_mic("aabbcc000002") == "nativo"
    assert a02.modo_do_mic("aabbcc000003") == "nativo"
    assert a02.modo_do_mic("aabbcc000009") == "nativo"


def test_sem_endereco_o_modo_do_mic_nao_acende_nenhum(a02, monkeypatch):
    """Um controle sem `uniq` normalizado não tem linha no `maquina.json`.

    Escrever "Nativo" ali seria afirmar uma escolha que ninguém fez — e é o
    mesmo cuidado que a `GUARDA-SEM-ENDEREÇO-01` toma do lado da GTK.
    """
    monkeypatch.setattr(a02, "_DECLARADOS", {})
    assert a02.modo_do_mic("") == ""


def test_o_gesto_do_modo_invalida_a_leitura_em_cache(a02, monkeypatch):
    """O botão que grava e não muda de cor é o defeito que esta cura veio matar.

    `_controles_declarados` guarda o `maquina.json` porque ele só muda por gesto
    dela — e este É o gesto. Sem o `recarregar=True`, o aceso continuaria sendo
    o de antes do clique até alguém reabrir a janela.
    """
    from types import SimpleNamespace

    from pacotes import Contexto

    endereco = "aabbcc000001"
    monkeypatch.setattr(a02, "_DECLARADOS", {endereco: SimpleNamespace(microfone=True)})
    recarregado: list[bool] = []

    def falso_recarregar(recarregar: bool = False) -> dict:
        recarregado.append(recarregar)
        return {}

    monkeypatch.setattr(a02, "_controles_declarados", falso_recarregar)

    class Ponte:
        def machine_declare(self, _decl):
            return (True, "")

    ctx = Contexto(state={}, mesa=[],
                   conectados=[{"uniq": UNIQ_CABO, "transport": "usb"}], estados={})
    a02.mic_modo(ctx, {"uniq": UNIQ_CABO, "micModo": "nativo"}, Ponte())
    assert True in recarregado, (
        "o gesto gravou no disco e não derrubou a leitura em cache")


# ---------------------------------------------------------------------------
# 3. O DESENHO TEM ONDE O PRODUTO ESCREVER — nos dois lados
# ---------------------------------------------------------------------------
#: OS DOIS PARES, com os valores que cada botão representa **perguntados ao
#: pacote**. Digitar `["jogo", "pc"]` aqui seria a régua que reprova o dia em
#: que o vocabulário da página mudar, em vez de acompanhá-lo.
def _pares(a02) -> dict[str, list[str]]:
    return {
        "alto-rota": sorted(a02.NOME_DO_BOTAO_DA_ROTA.values()),
        "mic-modo-aceso": ["nativo", "virtual"],
    }


@pytest.mark.parametrize("onde", [BANCADA, PUBLICADO], ids=["bancada", "publicado"])
def test_os_quatro_botoes_dizem_quem_sao_no_desenho(a02, onde):
    """Cada botão do par: o mesmo `data-campo`, o alvo `classe`, e o SEU `quando`.

    Os TRÊS atributos são necessários juntos. Sem `data-hef-alvo="classe"` o
    piloto escreveria o valor como TEXTO por cima do rótulo do botão; sem
    `data-hef-quando` o alvo vira booleano e os DOIS acenderiam ao mesmo tempo.
    """
    doc = onde.read_text(encoding="utf-8")
    # A CONTA DE CARTÕES PASSOU A ACEITAR O `off` — 07/09/2026,
    # CONTROLES-O-LUGAR-VAZIO-TEM-ENDERECO-01. Aqui estava
    # `doc.count('class="ctl card"')`, casamento EXATO, e desde hoje o lugar
    # vazio é o MESMO cartão com uma classe a mais (`ctl card off`). O
    # casamento exato daria 2 numa página de 4 cartões e a régua passaria
    # medindo METADE da mesa — que é a forma exata do defeito que a mudança
    # veio curar: com os quatro DualSense dela ligados, dois assentos ficavam
    # sem endereço nenhum e nenhuma régua desta casa via.
    #
    # NA PÁGINA PUBLICADA ELE CONTINUA DANDO 2, porque lá o lugar vazio ainda é
    # `class="ctl off"` (sem `card`) — publicar é ato dela. Os dois casos deste
    # parâmetro medem, cada um, a mesa que a sua página tem.
    cards = len(re.findall(r'class="ctl card[^"]*"', doc))
    assert cards >= 2, "o desenho precisa de mais de um card para esta régua morder"
    for campo, valores in _pares(a02).items():
        for valor in valores:
            achados = re.findall(
                rf'data-campo="{campo}" data-hef-alvo="classe" data-hef-quando="{valor}"',
                doc)
            assert len(achados) == cards, (
                f'{onde.name}: `{campo}`/`{valor}` aparece {len(achados)} vez(es) '
                f"e há {cards} cartões — todo lugar da mesa precisa dos dois botões")


def test_o_endereco_do_aceso_nao_mora_no_container(a02):
    """`data-campo` no `<span>` que envolve os botões APAGA os dois.

    Medido no Chrome em 01/09/2026 sobre a página publicada: `[data-mic-modo]`
    caiu de 4 para 0. O `escrever` do piloto faz `el.textContent = t` no alvo
    padrão, e o container inteiro vira uma palavra.
    """
    doc = PUBLICADO.read_text(encoding="utf-8")
    for container in re.findall(r'<span class="rota mic-modo"[^>]*>', doc):
        assert "data-campo" not in container, (
            "o endereço voltou para o container — ele troca os dois botões por "
            "um travessão")
    for div in re.findall(r'<div class="rota">', doc):
        assert "data-campo" not in div


def test_o_pacote_emite_os_dois_acesos_para_a_pagina_publicada(a02, monkeypatch):
    """O elo que faltava: emitir para um endereço que a página publicada NÃO tem
    não pinta nada e ainda conta como pintura (`cobertura.pintados`).

    Esta régua confere o caminho INTEIRO — o pacote emite, e a página publicada
    tem onde pôr —, que é o que separa "escrevi o código" de "chegou à tela".

    **O `alto-rota` PASSOU A LER AS DUAS CAMADAS — 04/09/2026, decisão [09].**
    O byte 3 sozinho NÃO acende mais "Todo o som do PC": foi assim que o card 2
    dela ficou aceso em 03/09 com o som saindo na TV. Quem decide agora é
    `audio_saida.botao_da_rota_aceso`, e ele exige que a saída padrão do
    sistema seja a placa DESTE controle.

    POR ISSO A CAMADA 1 É INJETADA, e não esperada: `a02._CAMADA_1` é o ponto
    de injeção da régua, como o `_LENTO` da `a09_sistema`. Esperar a thread
    seria uma corrida — e uma corrida na suíte é vermelho que aparece uma vez
    em dez.
    """
    from types import SimpleNamespace

    from hefesto_dualsense4unix.app.audio_saida import RotaDasDuasCamadas
    from pacotes import Contexto

    monkeypatch.setattr(a02, "_ENDERECOS", None)
    monkeypatch.setattr(a02, "_DECLARADOS", {"aabbcc000001": SimpleNamespace(microfone=True)})
    monkeypatch.setattr(a02, "_CAMADA_1", {UNIQ_CABO: RotaDasDuasCamadas(
        byte=3, sink_do_controle="alsa_output.dualsense",
        sink_padrao="alsa_output.dualsense")})
    monkeypatch.setattr(a02, "_CAMADA_1_EM_VOO", [True])
    controle = {
        "uniq": UNIQ_CABO, "transport": "usb", "battery_pct": 85, "player_slot": 1,
        "speaker": {"volume": 102, "muted": False, "rota": 3},
        "inputs": {"buttons": []},
    }
    campos = a02.pacote(Contexto(state={}, mesa=[], conectados=[controle],
                                 estados={}))["cards"][UNIQ_CABO]
    assert campos["alto-rota"] == "pc"
    assert campos["mic-modo-aceso"] == "virtual"


# ---------------------------------------------------------------------------
# 4. A CARGA FALA A GRAMÁTICA DA CASA
# ---------------------------------------------------------------------------
def test_a_bateria_escreve_o_numero_com_a_grafia_da_gtk(a02, monkeypatch):
    """`85 %`, com espaço — e o card mostrava as DUAS gramáticas ao mesmo tempo.

    Três centímetros abaixo, o `alto-estado` sai de `sensor_widgets.texto_volume`,
    que é `f"{...} %"`. A régua pergunta ao dono em vez de digitar o espaço:
    a grafia da carga tem de casar com a do volume, que é do produto.
    """
    from hefesto_dualsense4unix.app.widgets.sensor_widgets import texto_volume
    from pacotes import Contexto

    monkeypatch.setattr(a02, "_ENDERECOS", None)
    monkeypatch.setattr(a02, "_DECLARADOS", {})
    controle = {"uniq": UNIQ_CABO, "transport": "usb", "battery_pct": 85,
                "player_slot": 1, "speaker": {"volume": 102, "muted": False}}
    campos = a02.pacote(Contexto(state={}, mesa=[], conectados=[controle],
                                 estados={}))["cards"][UNIQ_CABO]
    # `texto_volume(102, False)` é "100 %": o separador entre número e unidade é
    # o que se compara, e ele sai do produto.
    separador = texto_volume(102, False).replace("100", "").replace("%", "")
    assert campos["bateria"] == f"85{separador}%", (
        f"a carga escreve {campos['bateria']!r} e o volume ao lado usa "
        f"{texto_volume(102, False)!r} — duas gramáticas no mesmo card")


def test_a_carga_desconhecida_e_a_da_janela_antiga(a02, monkeypatch):
    """A carga sem leitura é `— %`, como a GTK. Decisão dela, 03/09/2026.

    O QUE CADUCOU, e esta régua era ele: até 03/09 o teste se chamava
    `test_a_carga_desconhecida_e_o_travessao_seco` e cobrava o travessão SECO,
    pela regra de *campo sem informação não mostra nada* e para casar com o
    `alto-estado` e o `touch-estado` do mesmo card. Ela decidiu o contrário —
    **"— %, como a janela antiga"** —, e a paridade com a janela que ela usa
    vence a harmonia interna do card. A decisão é dela.

    E A FRASE É PERGUNTADA, não digitada: o dono é
    `StatusActionsMixin._bateria_da_mesa`, o mesmo que a GTK usa. Uma régua com
    `== "— %"` reprovaria a MELHORA no dia em que a GTK mudasse a grafia.
    """
    from hefesto_dualsense4unix.app.actions.status_actions import StatusActionsMixin
    from pacotes import Contexto

    monkeypatch.setattr(a02, "_ENDERECOS", None)
    monkeypatch.setattr(a02, "_DECLARADOS", {})
    controle = {"uniq": UNIQ_CABO, "transport": "usb", "player_slot": 1}
    campos = a02.pacote(Contexto(state={}, mesa=[], conectados=[controle],
                                 estados={}))["cards"][UNIQ_CABO]
    assert campos["bateria"] == StatusActionsMixin._bateria_da_mesa({})[1], (
        "a carga desconhecida saiu da grafia da janela antiga — ela pediu "
        "paridade literal"
    )
