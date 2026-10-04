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

UNIQ_CABO = "aa:bb:cc:00:00:01"


@pytest.fixture(scope="module")
def a02():
    from pacotes import a02_controles

    return a02_controles


def test_a_rota_vem_do_byte_do_aparelho(a02):
    """Os dois bytes que estes dois botões significam, PERGUNTADOS ao dono."""
    from hefesto_dualsense4unix.interface.cartao_do_controle import (
        CANAL_SONS_DO_JOGO,
        CANAL_TODO_O_PC,
        ROTA_DO_CANAL,
    )

    jogo = {"speaker": {"volume": 102, "rota": ROTA_DO_CANAL[CANAL_SONS_DO_JOGO]}}
    tudo = {"speaker": {"volume": 102, "rota": ROTA_DO_CANAL[CANAL_TODO_O_PC]}}
    assert a02.rota_na_tela(jogo) == "jogo"
    assert a02.rota_na_tela(tudo) == "pc"


def test_a_rota_desconhecida_nao_acende_botao_nenhum(a02):
    """A rota 1 é do protocolo e NÃO é nenhum destes botões."""
    from hefesto_dualsense4unix.core.ds_output_report import SAIDA_MONO_NO_FONE

    assert a02.rota_na_tela(
        {"speaker": {"volume": 102, "rota": SAIDA_MONO_NO_FONE}}) == ""


def test_sem_bloco_de_alto_falante_a_tela_nao_afirma_rota(a02):
    """O daemon só publica `speaker` depois do primeiro `speaker.set`."""
    assert a02.rota_na_tela({"uniq": UNIQ_CABO}) == ""
    assert a02.rota_na_tela({"speaker": {"volume": 102}}) == ""
    assert a02.rota_na_tela(None) == ""


def test_a_rota_nao_confunde_booleano_com_byte(a02):
    """`True` é `int` em Python, e `ROTA_DO_CANAL.get(True)` acharia a rota 1."""
    assert a02.rota_na_tela({"speaker": {"volume": 102, "rota": True}}) == ""


def test_a_rota_sai_do_mesmo_bloco_que_o_volume(a02):
    """A régua ANTI-DERIVA das duas leituras da mesma regra."""
    from hefesto_dualsense4unix.interface.cartao_do_controle import speaker_do_entry

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


def test_o_modo_do_mic_segue_a_inversao_so_false_e_nativo(a02, monkeypatch):
    """A tabela do daemon — `bt_mic.uniqs_recusados` —, com três valores.

    Ausência LIGA desde a ordem dela de 18/09/2026 (*"todos os controles tem
    que nascer com tudo mic, giroscopio e afins"*), então só o `False` é
    Nativo. A régua antiga cobrava a regra da GTK (`microfone is True`), e com
    ela o cartão de todo controle não declarado acendia «Nativo» sobre uma
    ponte de pé — medido na mesa dela em 22/09/2026.

    MORDIDA: devolva `is True` a `modo_do_mic`, e as duas últimas linhas
    reprovam.
    """
    from types import SimpleNamespace

    monkeypatch.setattr(a02, "_DECLARADOS", {
        "aabbcc000001": SimpleNamespace(microfone=True),
        "aabbcc000002": SimpleNamespace(microfone=False),
        "aabbcc000003": SimpleNamespace(microfone=None),
    })
    assert a02.modo_do_mic("aabbcc000001") == "virtual"
    assert a02.modo_do_mic("aabbcc000002") == "nativo"
    assert a02.modo_do_mic("aabbcc000003") == "virtual"
    assert a02.modo_do_mic("aabbcc000009") == "virtual"


def test_o_nativo_da_aba_02_grava_o_mesmo_que_o_desligado_da_aba_08(a02):
    """Um valor só para "não quero": o `False` do `maquina.json`."""
    prova = [p for p in a02.PROVAS
             if p["gesto"] == "mic-modo" and p["clique"]["micModo"] == "nativo"]
    assert len(prova) == 1, "a prova do «Nativo» sumiu das PROVAS da aba"
    declarado = prova[0]["chama"][0][1][0]["controles"]
    assert list(declarado.values()) == [{"microfone": False}], declarado


def test_sem_endereco_o_modo_do_mic_nao_acende_nenhum(a02, monkeypatch):
    """Um controle sem `uniq` normalizado não tem linha no `maquina.json`."""
    monkeypatch.setattr(a02, "_DECLARADOS", {})
    assert a02.modo_do_mic("") == ""


def test_o_gesto_do_modo_invalida_a_leitura_em_cache(a02, monkeypatch):
    """O botão que grava e não muda de cor é o defeito que esta cura veio matar."""
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


def _pares(a02, onde=None) -> dict[str, list[str]]:
    rota = sorted(a02.BOTOES_DA_FILEIRA_DO_SOM)
    if onde == PUBLICADO and _a_02_esta_em_trabalho():
        rota = [v for v in rota if v != a02.ROTA_TUDO_NO_CONTROLE]
    pares = {"alto-rota": rota}
    if onde != BANCADA:
        # O par «Virtual | Nativo» saiu da bancada em 03/10/2026 (a decisão
        # dela de 02/10); a página publicada o tem até o `--publicar 02`.
        pares["mic-modo-aceso"] = ["nativo", "virtual"]
    return pares


def _a_02_esta_em_trabalho() -> bool:
    """A 02 declarada em trabalho, perguntado ao portão — ver `_pares`."""
    import importlib.util

    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_dos_acesos", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_dos_acesos"] = mod
    spec.loader.exec_module(mod)
    return "02-controles.html" in mod.declaradas()


@pytest.mark.parametrize("onde", [BANCADA, PUBLICADO], ids=["bancada", "publicado"])
def test_os_quatro_botoes_dizem_quem_sao_no_desenho(a02, onde):
    """Cada botão do par: o mesmo `data-campo`, o alvo `classe`, e o SEU `quando`.

    Os TRÊS atributos são necessários juntos. Sem `data-hef-alvo="classe"` o
    piloto escreveria o valor como TEXTO por cima do rótulo do botão; sem
    `data-hef-quando` o alvo vira booleano e os DOIS acenderiam ao mesmo tempo.
    """
    doc = onde.read_text(encoding="utf-8")
    # veio curar: com os quatro DualSense dela ligados, dois assentos ficavam
    cards = len(re.findall(r'class="ctl card[^"]*"', doc))
    assert cards >= 2, "o desenho precisa de mais de um card para esta régua morder"
    for campo, valores in _pares(a02, onde).items():
        for valor in valores:
            achados = re.findall(
                rf'data-campo="{campo}" data-hef-alvo="classe" data-hef-quando="{valor}"',
                doc)
            assert len(achados) == cards, (
                f'{onde.name}: `{campo}`/`{valor}` aparece {len(achados)} vez(es) '
                f"e há {cards} cartões — todo lugar da mesa precisa dos dois botões")


def test_o_endereco_do_aceso_nao_mora_no_container(a02):
    """Endereço de TEXTO no `<span>` que envolve os botões APAGA os dois.

    Medido no Chrome em 01/09/2026 sobre a página publicada: `[data-mic-modo]`
    caiu de 4 para 0. O `escrever` do piloto faz `el.textContent = t` no alvo
    padrão, e o container inteiro vira uma palavra.

    **ELA MEDIA A FORMA E NÃO O ATO — corrigida em 20/09/2026.** A redação
    anterior proibia QUALQUER `data-campo` no container, e reprovou a decisão
    dela do mesmo dia (*"Fica os dois botões. Mas no rádio o botão fica cinza
    sem ser ativado"*), que endereça o container com
    `data-hef-alvo="classe"` — de propósito, porque a razão de o «Nativo» ficar
    cinza é do conjunto, não de um botão.

    O defeito de 01/09 **não é o endereço; é o ALVO**. O piloto resolve
    `const alvo = el.dataset.hefAlvo || 'texto'`
    (`interface/hefesto_vivo.py:241`), e só o ramo padrão chama `textContent`
    (`:915`). Um container com alvo declarado nunca passa por ali.

    Então a régua passa a proibir o que de fato apaga: endereço no container
    **sem** `data-hef-alvo`, ou com ele em `texto`.

    MORDIDA: tirar o `data-hef-alvo="classe"` do container da `.mic-modo`.
    """
    doc = PUBLICADO.read_text(encoding="utf-8")
    padroes = (r'<span class="rota mic-modo"[^>]*>', r'<div class="rota"[^>]*>')
    for padrao in padroes:
        for container in re.findall(padrao, doc):
            if "data-campo" not in container:
                continue
            m = re.search(r'data-hef-alvo="([^"]*)"', container)
            alvo = m.group(1) if m else "texto"
            assert alvo != "texto", (
                "o endereço voltou para o container COM ALVO DE TEXTO — ele "
                f"troca os dois botões por um travessão: {container}")


def test_o_pacote_emite_os_dois_acesos_para_a_pagina_publicada(a02, monkeypatch):
    """O elo que faltava: emitir para um endereço que a página publicada NÃO tem"""
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


def test_a_bateria_escreve_o_numero_com_a_grafia_da_gtk(a02, monkeypatch):
    """`85 %`, com espaço — e o card mostrava as DUAS gramáticas ao mesmo tempo."""
    from hefesto_dualsense4unix.interface.sensores import texto_volume
    from pacotes import Contexto

    monkeypatch.setattr(a02, "_ENDERECOS", None)
    monkeypatch.setattr(a02, "_DECLARADOS", {})
    controle = {"uniq": UNIQ_CABO, "transport": "usb", "battery_pct": 85,
                "player_slot": 1, "speaker": {"volume": 102, "muted": False}}
    campos = a02.pacote(Contexto(state={}, mesa=[], conectados=[controle],
                                 estados={}))["cards"][UNIQ_CABO]
    separador = texto_volume(102, False).replace("100", "").replace("%", "")
    assert campos["bateria"] == f"85{separador}%", (
        f"a carga escreve {campos['bateria']!r} e o volume ao lado usa "
        f"{texto_volume(102, False)!r} — duas gramáticas no mesmo card")


def test_a_carga_desconhecida_e_a_da_janela_antiga(a02, monkeypatch):
    """A carga sem leitura é `— %`, como a GTK. Decisão dela, 03/09/2026."""
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
