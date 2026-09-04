#!/usr/bin/env python3
"""A RÉGUA DA ONDA2-02: as dez decisões da aba Controles, uma a uma.

**A fonte é `docs/process/2026-09-04-O-PO-DECIDE-as-54-e-os-sete-conflitos.md`,
§2, `02-controles`.** Vinte das trinta e quatro linhas desta aba eram `DESENHO`
— a aba que mais esperava pela palavra dela —, e nenhuma espera mais.

O QUE ESTE ARQUIVO COBRA, e por que cada bloco existe:

1. **O selo composto (decisão [03], conflito C-2, pela D-12).** ATIVO só quando
   as QUATRO faces concordam. `mic_da_mesa.eleito` está FORA de propósito: a
   ONDA1-D1 o mediu MENTINDO, e `canal_ativo` é leitura enquanto `eleito` é
   memória.
2. **A palavra da barra de luz (decisão [02]).** Quatro estados dividiam um
   travessão só; agora cada um tem a palavra dela, e a frase inteira vai no
   `title` da linha.
3. **O botão que avisa antes do clique (decisões [04] e [06]).**
4. **A rota das duas camadas (decisão [09]).** O byte 3 sozinho não acende mais
   "Todo o som do PC" — foi assim que o card 2 dela ficou aceso com o som
   saindo na TV, em 03/09.
5. **O ato do microfone (S-05).** Um pedido só, e a frase diz QUAL metade
   faltou.
6. **A confissão do volume (decisão [08]).** O mudo que caiu no controle de
   outra pessoa vira aviso no cartão.
7. **A degradação da máscara (decisão [07]).**
8. **Os dois anéis (D-06 / S-11).**

**O DUBLÊ DAQUI É ESTRITO, E ISSO É O PONTO INTEIRO DE ELE EXISTIR.** O dublê
compartilhado (`test_os_botoes_tem_dono.PonteDeMentira`) responde `True` a todo
nome que não conhece — e um dublê mais frouxo que a ponte real é a cicatriz de
04/09/2026, que custou **duas** máscaras que passaram verdes sem gravar um
byte. As funções `_detalhado` da ponte devolvem `dict | None`, e é isso que o
dublê daqui devolve; um `bool` não tem `motivo` nem `por_uniq`, e é justamente
o que os caminhos medidos aqui precisam.

**E A PARTE DE TELA LÊ, NÃO DIGITA.** Nenhuma cor está escrita neste arquivo. A
régua abre a página da BANCADA no Chrome do sistema (headless — nenhuma janela
nasce na tela dela) e pergunta ao motor o que ele DESENHA, comparando elementos
da MESMA página.
"""
from __future__ import annotations

import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import mesa_viva
from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.widgets.controller_card import (
    TEXTO_MIC_ALVO_NAO_HONRADO,
    rotulo_lightbar,
)
from hefesto_dualsense4unix.interface import onde
from pacotes import Contexto
from pacotes import a02_controles as a02

#: O MESMO MOTOR DAS OUTRAS RÉGUAS DE TELA desta casa, e ele roda headless.
CHROME = pathlib.Path("/usr/bin/google-chrome")

#: A CHAVE DA CASA, e não um endereço real — a máscara é `docs/…` e há dois
#: portões que a cobram.
UNIQ = "aa:bb:cc:00:00:01"

BASE: dict[str, Any] = {
    "uniq": UNIQ, "player": 1, "connected": True, "transport": "usb",
    "battery_pct": 50, "is_primary": True, "inputs": {"buttons": []},
}


class PonteEstrita:
    """O dublê que é TÃO estrito quanto a ponte de verdade.

    Cada nome devolve o que `interface/pacotes/ponte.py` devolve — `dict | None`
    para as `_detalhado`, `bool` para as outras —, e um nome que a ponte não
    tem levanta `AttributeError` em vez de responder `True`. É a diferença
    entre medir o botão e medir o próprio dublê.
    """

    def __init__(self, **respostas: Any) -> None:
        self.chamadas: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = []
        self._respostas = respostas

    def _anotar(self, nome: str) -> Any:
        import hefesto_dualsense4unix.interface.pacotes.ponte as ponte_real

        if not hasattr(ponte_real, nome):
            raise AttributeError(
                f"a ponte real não tem `{nome}` — um dublê que responde a "
                f"nomes que a ponte não expõe mede a si mesmo")

        def chamar(*a: Any, **kw: Any) -> Any:
            self.chamadas.append((nome, a, kw))
            return self._respostas.get(nome, True)

        return chamar

    def __getattr__(self, nome: str) -> Any:
        return self._anotar(nome)


def _ctx(entry: dict[str, Any] | None = None, **extra: Any) -> Contexto:
    dele = {**BASE, **(entry or {})}
    return Contexto(state=extra.pop("state", {}), mesa=[], conectados=[dele],
                    estados={}, **extra)


def _enderecos_da_bancada() -> frozenset[str]:
    """Todo `data-campo` do DESENHO de hoje — e a bancada é onde ele mora.

    **POR QUE A BANCADA E NÃO O PUBLICADO.** O `_so_se_a_pagina_tiver` do
    pacote pergunta ao PUBLICADO de propósito: emitir para um endereço que a
    página do produto não tem enche `casamento.medir(...)["orfaos"]` e faz o
    pacote se reportar pintando o que não pinta. Isso continua valendo, e não é
    o que esta régua mede.

    O QUE ELA MEDE é a decisão dela chegando ao card, e as decisões desta onda
    nascem na BANCADA — publicar é ATO DELA, depois do olho dela na aba
    inteira (`PROVA-DE-TELA-01`, a regra mais velha desta casa). Apontar a
    régua para o publicado daria **verde por ausência**: os campos novos não
    sairiam, e nenhum caso reprovaria.
    """
    doc = onde.pagina("02-controles.html").read_text(encoding="utf-8")
    import re as _re
    return frozenset(_re.findall(r'data-campo="([^"]+)"', doc))


def _card(entry: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Os campos do card DESTE controle, com o DESENHO DE HOJE endereçado."""
    a02._ENDERECOS = _enderecos_da_bancada()
    try:
        fora = a02.pacote(_ctx(entry, **extra))
    finally:
        a02._ENDERECOS = None
    return dict(fora["cards"][UNIQ])


# ===========================================================================
# 1. O SELO DIZ O ESTADO COMPOSTO — decisão [03], conflito C-2, pela D-12
# ===========================================================================
ATIVO = mesa_viva.selo_do_mic(False, True)
MUDO = mesa_viva.selo_do_mic(True, True)
NAO_SEI = mesa_viva.selo_do_mic(False, False)

#: AS QUATRO FACES E O QUE CADA ARRANJO TEM DE DIZER. A palavra é PERGUNTADA a
#: `mesa_viva.selo_do_mic` acima — digitar "ATIVO" aqui mediria este arquivo.
NO_AR = {"mic_mudo": False, "canal_ativo": True, "canal_mudo": False}
FACES = [
    # (audio, esperado, por quê)
    (NO_AR, ATIVO, "as quatro concordam: firmware no ar e canal ouvindo"),
    ({**NO_AR, "mic_mudo": True}, MUDO, "o plástico calou"),
    ({**NO_AR, "canal_ativo": False}, MUDO,
     "o canal deste controle não é a fonte ativa — o som não chega ao PC"),
    ({**NO_AR, "canal_mudo": True}, MUDO, "a fonte está muda no PipeWire"),
    ({**NO_AR, "mic_mudo_desejado": True}, MUDO,
     "nós pedimos mudo; a face do desejo diz calado"),
    ({**NO_AR, "mic_mudo_desejado": None}, ATIVO,
     "`None` é 'a posse é do kernel' — um fato sobre QUEM MANDA, não sobre o "
     "mudo, e tratá-lo como ausência deixaria a mesa dela inteira em `—`"),
    ({}, NAO_SEI, "nenhuma face lida"),
    ({"mic_mudo": False}, NAO_SEI, "o canal ainda não foi perguntado"),
    ({"mic_mudo": True}, MUDO,
     "um FATO vence uma ausência: o firmware calado decide sem o canal"),
    ({**NO_AR, "canal_mudo": None}, NAO_SEI,
     "`None` no canal_mudo é 'não consegui ler', e não 'está no ar'"),
]


@pytest.mark.parametrize("audio, esperado, porque", FACES)
def test_o_selo_le_as_quatro_faces(audio: dict[str, Any], esperado: str,
                                   porque: str) -> None:
    """ATIVO só quando as quatro concordam — a D-12 dela, virada em régua.

    MORDE: devolva `selo_do_mic(bool(a.get("mic_mudo")),
    isinstance(a.get("mic_mudo"), bool))` — que é o que esta linha era até
    04/09 — e caem os três casos em que o FIRMWARE está no ar e o canal não.
    """
    assert a02.selo_composto(audio) == esperado, porque


def test_o_selo_nao_le_o_eleito_que_a_d1_viu_mentir() -> None:
    """`mic_da_mesa.eleito` é MEMÓRIA, e `canal_ativo` é LEITURA.

    A ONDA1-D1 mediu o `eleito` mentindo: com o canal trocado por fora
    (`pactl set-default-source`), o `state_full` seguiu dizendo `eleito:
    <uniq>` com o ativo sendo a webcam — o `EleitorDeMicrofone` só se corrige
    em gesto. **Onde os dois divergem, a leitura ganha.**

    MORDE: some `eleito` às faces e este caso reprova, porque um `eleito`
    mentindo passaria a acender ATIVO sobre um canal que não é o deste
    controle.
    """
    mentindo = {**NO_AR, "canal_ativo": False, "eleito": True}
    assert a02.selo_composto(mentindo) == MUDO


def test_o_selo_chega_ao_card(monkeypatch: pytest.MonkeyPatch) -> None:
    """O caminho inteiro: o `state_full` entra e o `mic-selo` sai composto.

    MORDE: devolva o pintor a `selo_do_mic(mudo, sabemos)` e este caso reprova
    com `ATIVO != MUDO` — o card diria que está capturando com o canal em
    outro controle.
    """
    campos = _card({"audio": {**NO_AR, "canal_ativo": False}})
    assert campos["mic-selo"] == MUDO


# ===========================================================================
# 2. A PALAVRA DA BARRA DE LUZ — decisão [02]
# ===========================================================================
#: OS QUATRO ESTADOS, com a ENTRADA que só aquele ramo do motor atende. A
#: palavra sai da tabela do pacote (que por sua vez pergunta ao motor); o que
#: esta lista digita é só a entrada.
ESTADOS_DA_LUZ = [
    ({"lightbar_rgb": [0, 0, 0], "lightbar_source": "desconhecida"}, {},
     a02.ROTULO_DA_LUZ_DESCONHECIDA),
    ({"lightbar_rgb": [0, 0, 0], "lightbar_source": "desconhecida"},
     {"native_mode": True}, a02.ROTULO_DA_LUZ_EM_NATIVO),
    ({"lightbar_rgb": [0, 0, 0], "lightbar_source": "desconhecida",
      "lightbar_disputada": True}, {}, a02.ROTULO_DA_LUZ_SEGURADA),
    ({"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs",
      "lightbar_on": False}, {}, a02.ROTULO_DA_LUZ_APAGADA),
]


def test_os_quatro_rotulos_sao_perguntados_ao_motor_e_diferentes() -> None:
    """As quatro chaves da tabela saem de `rotulo_lightbar`, e são quatro.

    ELA É O QUE IMPEDE A TABELA DE ENVELHECER CALADA: no dia em que o motor
    trocar uma frase, a chave deixa de casar e a palavra volta a ser o
    travessão. Esta régua reprova ANTES disso, porque cobra que as quatro
    entradas mínimas produzam quatro rótulos distintos e que os quatro estejam
    na tabela.

    MORDE: digite `"Lightbar: apagada"` na tabela do pacote em vez de perguntar,
    e mude a frase do motor — este caso reprova nomeando a que sobrou de fora.
    """
    lidos = {rotulo_lightbar(entry, estado)[0]
             for entry, estado, _ in ESTADOS_DA_LUZ}
    assert len(lidos) == 4, f"o motor devolveu {len(lidos)} rótulo(s): {lidos}"
    assert lidos == set(a02.PALAVRA_DA_LUZ), (
        "a tabela de palavras e os rótulos do motor divergiram:\n"
        f"  do motor : {sorted(lidos)}\n"
        f"  na tabela: {sorted(a02.PALAVRA_DA_LUZ)}")


@pytest.mark.parametrize("entry, estado, rotulo", ESTADOS_DA_LUZ)
def test_a_palavra_curta_substitui_o_travessao(
    entry: dict[str, Any], estado: dict[str, Any], rotulo: str
) -> None:
    """Cada um dos quatro estados mostra a SUA palavra — não um `—` para todos.

    MORDE: devolva `luz_palavra` a `luz_hex` e os quatro casos reprovam com o
    travessão, que é o que a tela mostrava até 04/09.
    """
    campos = _card(entry, state=estado)
    assert campos["luz-hex"] == a02.PALAVRA_DA_LUZ[rotulo]
    assert not campos["luz-hex"].startswith("#"), (
        "a cor CRUA voltou a aparecer num estado em que ninguém a mediu")


def test_a_cor_conhecida_continua_sendo_o_codigo() -> None:
    """A metade que impede a cura de virar "nunca mais mostra cor nenhuma"."""
    campos = _card({"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs",
                    "lightbar_on": True})
    assert campos["luz-hex"] == "#0000FF"


@pytest.mark.parametrize("entry, estado, rotulo", ESTADOS_DA_LUZ)
def test_a_frase_inteira_vai_para_o_hover(
    entry: dict[str, Any], estado: dict[str, Any], rotulo: str
) -> None:
    """O `title` da linha recebe a frase do MOTOR, palavra por palavra.

    É a outra metade da decisão [02] — *"frase inteira no hover"* —, e sem ela
    a palavra curta seria uma perda de informação em vez de uma tradução.

    MORDE: devolva `luz_porque` a `""` e os quatro casos reprovam.
    """
    assert _card(entry, state=estado)["luz-porque"] == rotulo


def test_com_a_cor_conhecida_o_hover_explica_de_quem_e_a_cor() -> None:
    """Sem rótulo não há o que explicar sobre o estado — então o `title` volta
    a ser a explicação de quem escolhe a cor, que é o texto que o desenho tinha.

    MORDE: devolva `str(rotulo or "")` sem o ramo da cor conhecida e o `title`
    some da linha no primeiro tique (o piloto REMOVE o atributo em valor vazio),
    levando junto a explicação que ela vê hoje.
    """
    campos = _card({"lightbar_rgb": [0, 0, 255], "lightbar_source": "sysfs",
                    "lightbar_on": True})
    assert campos["luz-porque"] == a02.DICA_DA_LUZ


# ===========================================================================
# 3. O BOTÃO AVISA ANTES DO CLIQUE — decisões [04] e [06]
# ===========================================================================
def test_a_razao_do_microfone_e_a_do_motor() -> None:
    """A frase do `?` é a MESMA que o gesto levanta — e não uma cópia dela.

    Com a cópia, a tela poderia apagar um botão que o gesto aceita, ou deixar
    aceso um que ele recusa. É a cicatriz que o `mic-modo` desta aba já carrega
    escrita no gesto.

    MORDE: escreva a condição à mão (`"audio" not in c`) e mude a regra do
    motor — este caso reprova comparando as duas frases.
    """
    from hefesto_dualsense4unix.app.widgets.controller_card import acao_mic

    sem_leitura = {**BASE, "audio": {}}
    assert a02.porques_do_som(sem_leitura)["mic-porque"] == acao_mic(
        sem_leitura).dica


def test_com_leitura_o_botao_do_microfone_nao_fica_cinza() -> None:
    """A metade que prova que a cura não apagou o botão para sempre."""
    assert a02.porques_do_som({**BASE, "audio": {"mic_mudo": False}})[
        "mic-porque"] == ""


def test_a_razao_do_alto_falante_aponta_para_o_deslizante() -> None:
    """A frase do ♪ manda para o que DESTRAVA o botão, e ele existe desde a D-08.

    A do motor (`DICA_SPEAKER_SEM_DADO`) mandava *"use o controle deslizante
    primeiro"* quando esta janela não tinha deslizante nenhum — mandar alguém a
    um controle que não está na tela é pior que não dizer nada. Hoje ele existe,
    e a frase daqui aponta para ele.
    """
    razao = a02.porques_do_som({**BASE, "speaker": {}})["alto-porque"]
    assert razao == a02.DICA_ALTO_SEM_POSSE
    assert "deslizante" in razao or "Arraste" in razao


def test_com_volume_conhecido_o_alto_falante_nao_fica_cinza() -> None:
    assert a02.porques_do_som(
        {**BASE, "speaker": {"volume": 102, "muted": False}})["alto-porque"] == ""


def test_as_duas_razoes_chegam_ao_card() -> None:
    """O caminho inteiro — o pacote emite os dois `?` no card daquele controle.

    MORDE: tire o `**porques_do_som(c)` do pintor e os dois botões voltam a
    descobrir a recusa DEPOIS do clique, que é a queixa inteira da D-03.
    """
    campos = _card({"audio": {}, "speaker": {}})
    assert campos["mic-porque"] and campos["alto-porque"]


# ===========================================================================
# 4. A ROTA LÊ AS DUAS CAMADAS — decisão [09]
# ===========================================================================
BYTE_PC = audio_saida.BYTE_TODO_O_SOM_DO_PC
BYTE_JOGO = audio_saida.BYTE_SONS_DO_JOGO
SINK = "alsa_output.usb-Sony-DualSense"


@pytest.fixture(autouse=True)
def _camada_1_parada(monkeypatch: pytest.MonkeyPatch) -> None:
    """A camada 1 NÃO conversa com o PipeWire desta máquina durante a suíte.

    O cache é o ponto de injeção da régua (o mesmo desenho do `_LENTO` da
    `a09_sistema`), e `_CAMADA_1_EM_VOO` travado em `True` impede a thread de
    nascer. Uma régua que esperasse a leitura de verdade seria uma corrida —
    e corrida na suíte é vermelho que aparece uma vez em dez.
    """
    monkeypatch.setattr(a02, "_CAMADA_1", {})
    monkeypatch.setattr(a02, "_CAMADA_1_EM_VOO", [True])
    monkeypatch.setattr(a02, "_CAMADA_1_QUANDO", [0.0])


def _com_camada_1(**kw: Any) -> None:
    a02._CAMADA_1[UNIQ] = audio_saida.RotaDasDuasCamadas(**kw)


def test_o_byte_do_pc_com_a_saida_em_outro_lugar_nao_acende_nada() -> None:
    """O estado que ela VIU em 03/09: o botão aceso e o som saindo na TV.

    MORDE: devolva `aceso_da_rota` a `rota_na_tela(entry)` e este caso reprova
    com `'pc' != ''` — a tela volta a afirmar que todo o som do PC está saindo
    naquele controle enquanto ele sai noutro lugar.
    """
    _com_camada_1(byte=BYTE_PC, sink_do_controle=SINK, sink_padrao="hdmi")
    assert a02.aceso_da_rota(UNIQ, {"speaker": {"rota": BYTE_PC}}) == ""


def test_o_byte_do_pc_com_a_saida_no_controle_acende_pc() -> None:
    """A metade que prova que a cura não apagou o botão para sempre."""
    _com_camada_1(byte=BYTE_PC, sink_do_controle=SINK, sink_padrao=SINK)
    assert a02.aceso_da_rota(UNIQ, {"speaker": {"rota": BYTE_PC}}) == "pc"


def test_o_desacordo_vira_frase_no_cartao() -> None:
    """Apagar os dois botões não explica; a ressalva é o que explica.

    A frase é do MOTOR (`audio_saida.MOTIVO_ROTA_SO_NO_BYTE`) — escrevê-la aqui
    seria a segunda cópia, e a que envelheceria calada.
    """
    _com_camada_1(byte=BYTE_PC, sink_do_controle=SINK, sink_padrao="hdmi")
    assert a02.recado_da_rota(UNIQ) == audio_saida.MOTIVO_ROTA_SO_NO_BYTE


def test_sem_desacordo_a_ressalva_manda_o_marcador_e_a_linha_some() -> None:
    """A chave vai em TODO tique, e sem frase ela leva o `.nada`.

    Omiti-la deixaria a frase velha na tela para sempre — o defeito oposto, e
    pior. E mandar `""` escreveria um travessão solto: `escrever()` troca vazio
    por `—` para TODOS os alvos, o `html` incluído.
    """
    _com_camada_1(byte=BYTE_JOGO, sink_do_controle=SINK, sink_padrao=SINK)
    campos = _card({"speaker": {"volume": 102, "muted": False,
                                "rota": BYTE_JOGO}})
    assert campos["alto-ressalva"] == a02.NADA_A_DIZER


def test_sem_a_camada_1_lida_o_byte_ainda_responde() -> None:
    """O cache vazio é o estado dos primeiros tiques — e ali sobra o byte.

    Apagar os dois botões durante dois segundos afirmaria uma ignorância que
    não existe: o byte é um fato lido, e é metade da resposta.
    """
    assert a02.aceso_da_rota(UNIQ, {"speaker": {"rota": BYTE_JOGO}}) == "jogo"
    assert a02.recado_da_rota(UNIQ) == ""


def test_o_pintor_nao_conversa_com_o_pipewire_no_tique() -> None:
    """A leitura é BLOQUEANTE e nunca roda no laço da janela.

    `pactl` num pintor de 10 Hz trava a janela dela — é por isso que o
    `ipc_bridge.run_in_thread` existe, e é o que a ONDA1-D1 escreveu com todas
    as letras sobre esta leitura.

    MORDE: devolva a primeira leitura ao caminho SÍNCRONO (era assim na
    primeira redação) e este caso reprova, porque o pintor passa a chamar
    `ler_as_duas_camadas` de dentro do tique.
    """
    chamou: list[Any] = []

    def nao_deveria(*a: Any, **kw: Any) -> Any:
        chamou.append(a)
        raise AssertionError("o pintor chamou o PipeWire dentro do tique")

    original = audio_saida.ler_as_duas_camadas
    audio_saida.ler_as_duas_camadas = nao_deveria  # type: ignore[assignment]
    try:
        _card({"speaker": {"volume": 102, "muted": False, "rota": BYTE_JOGO}})
    finally:
        audio_saida.ler_as_duas_camadas = original  # type: ignore[assignment]
    assert not chamou


# ===========================================================================
# 5. O MICROFONE É UM ATO SÓ — S-05, a D-12 dela
# ===========================================================================
def test_o_gesto_chama_o_ato_e_nao_a_metade_do_firmware() -> None:
    """O 🎙 manda `mic.canal.set`, e o `ligado` é o INVERSO do mudo de agora.

    MORDE: volte para `p.mic_set(not agora, uniq=uniq)` e este caso reprova
    nomeando a função — o botão volta a pedir só a metade do firmware, e a
    resposta perde a notícia de qual metade faltou.
    """
    p = PonteEstrita(mic_canal_set_detalhado={"status": "ok"})
    a02.mudo(_ctx({"audio": {"mic_mudo": True}}),
             {"uniq": UNIQ, "mudo": "microfone"}, p)
    assert p.chamadas == [("mic_canal_set_detalhado", (True,), {"uniq": UNIQ})]


def test_o_clique_num_microfone_no_ar_pede_para_desligar() -> None:
    """A outra ponta do mesmo inverso — o botão ALTERNA, e a leitura decide."""
    p = PonteEstrita(mic_canal_set_detalhado={"status": "ok"})
    a02.mudo(_ctx({"audio": {"mic_mudo": False}}),
             {"uniq": UNIQ, "mudo": "microfone"}, p)
    assert p.chamadas == [("mic_canal_set_detalhado", (False,), {"uniq": UNIQ})]


def test_meio_ato_vira_a_frase_do_dono_no_cartao() -> None:
    """Modo Nativo: o canal foi eleito e o firmware ficou represado.

    A FRASE É A DO DAEMON, e a decisão de a mostrar é a razão inteira desta
    troca: um `RuntimeError` genérico devolveria o *"não deu"* que não diz nada
    a quem está com o controle na mão.

    MORDE: troque `frase_do_ato_do_microfone(corpo)` por um `if corpo.get(
    "status") != "ok"` com frase própria, e este caso reprova comparando o
    texto — a tela passa a inventar a razão em vez de repetir a do daemon.
    """
    motivo = ("o microfone foi ligado no canal deste controle, mas o Hefesto "
              "não conseguiu escrever o mudo no aparelho")
    p = PonteEstrita(mic_canal_set_detalhado={
        "status": "incompleto", "canal_feito": True, "firmware_pedido": False,
        "motivo": motivo})
    with pytest.raises(RuntimeError) as erro:
        a02.mudo(_ctx({"audio": {"mic_mudo": True}}),
                 {"uniq": UNIQ, "mudo": "microfone"}, p)
    assert str(erro.value) == motivo


def test_daemon_calado_continua_dizendo_daemon_calado() -> None:
    """`None` é o daemon que não respondeu, e a frase dele é outra."""
    p = PonteEstrita(mic_canal_set_detalhado=None)
    with pytest.raises(RuntimeError) as erro:
        a02.mudo(_ctx({"audio": {"mic_mudo": True}}),
                 {"uniq": UNIQ, "mudo": "microfone"}, p)
    assert "Hefesto está parado" in str(erro.value)


# ===========================================================================
# 6. O MUDO QUE CAIU NO CONTROLE ERRADO — decisão [08]
# ===========================================================================
def test_o_volume_do_microfone_confessa_quando_cai_na_rota_global() -> None:
    """`por_uniq: False` — o daemon mexeu no microfone de OUTRA pessoa.

    A FRASE É A DO PRODUTO (`controller_card.frase_do_alvo_do_mic`), e a janela
    ANTIGA já a diz desde 26/08. Quem não a dizia era esta.

    MORDE: volte para `p.mic_volume_set(...)` e este caso reprova — o `bool`
    daquele colapsa `por_uniq` no mesmo `True` de um pedido honrado, e a tela
    pinta o selo do card certo sobre um número que ele nunca teve.
    """
    p = PonteEstrita(mic_volume_set_detalhado={
        "status": "ok", "fonte": "webcam", "volume": 42, "por_uniq": False})
    with pytest.raises(RuntimeError) as erro:
        a02.volume(_ctx(), {"uniq": UNIQ, "volume": "microfone",
                            "valor": "42"}, p)
    assert str(erro.value) == TEXTO_MIC_ALVO_NAO_HONRADO


@pytest.mark.parametrize("por_uniq", [True, None])
def test_honrado_e_nao_sei_nao_confessam(por_uniq: bool | None) -> None:
    """*"Não sei" não é "não honrei"* — inventar a confissão por ausência de
    notícia acusaria o produto de um erro que ninguém mediu.

    É a regra do próprio dono (`frase_do_alvo_do_mic`), e ela vale para o
    daemon velho que não publica o campo.
    """
    corpo: dict[str, Any] = {"status": "ok", "fonte": "ds", "volume": 42}
    if por_uniq is not None:
        corpo["por_uniq"] = por_uniq
    p = PonteEstrita(mic_volume_set_detalhado=corpo)
    a02.volume(_ctx(), {"uniq": UNIQ, "volume": "microfone", "valor": "42"}, p)
    assert p.chamadas[0][0] == "mic_volume_set_detalhado"


def test_o_duble_estrito_recusa_um_nome_que_a_ponte_nao_tem() -> None:
    """A régua da RÉGUA — a cicatriz de 04/09, em forma de caso.

    Duas vezes num dia um gesto passou VERDE sem gravar um byte porque o dublê
    do teste era mais frouxo que a ponte real. Este caso é o que impede a
    terceira: se alguém escrever `p.mic_canal_setx(...)` num gesto, o dublê
    daqui levanta em vez de responder `True`.
    """
    with pytest.raises(AttributeError):
        PonteEstrita().mic_canal_setx()


def test_a_ponte_expoe_o_que_esta_aba_declara() -> None:
    """Todo nome em `PONTE` existe de verdade — um nome inventado morre aqui,
    e não na mão de quem clica.
    """
    import hefesto_dualsense4unix.interface.pacotes.ponte as ponte_real

    faltam = [n for n in a02.PONTE if not hasattr(ponte_real, n)]
    assert not faltam, f"a ponte não expõe: {faltam}"


# ===========================================================================
# 7. A DEGRADAÇÃO DA MÁSCARA — decisão [07]
# ===========================================================================
def test_o_motivo_da_degradacao_chega_ao_card() -> None:
    """O ajudante existia e NENHUM dos dez pacotes o chamava.

    MORDE: tire o `mascara-degradou` do pintor e a marca some da tela — o card
    volta a mostrar "DualSense" sem dizer que a emulação caiu para uinput.
    """
    from hefesto_dualsense4unix.interface import pacotes

    entry = {"vpad_backend": "uinput", "vpad_motivo": "sem_uhid"}
    esperado = pacotes.degradacao_de(entry)
    assert esperado, "o dono não devolveu motivo — a régua mediria o vazio"
    assert _card(entry)["mascara-degradou"] == esperado


def test_sem_degradacao_o_campo_vai_vazio_e_a_marca_some() -> None:
    """`uinput` sem motivo é a máscara Xbox POR DESENHO, e não é defeito.

    O vazio é o que faz o piloto REMOVER o `title`, e é o `[title]` da folha
    que apaga a marca. Um valor qualquer aqui acenderia um asterisco sobre um
    controle que está inteiro.
    """
    assert _card({"vpad_backend": "uinput", "vpad_motivo": None})[
        "mascara-degradou"] == ""


# ===========================================================================
# 8. O QUE O NAVEGADOR DESENHA — a parte que LÊ a tela
# ===========================================================================
O_QUE_O_NAVEGADOR_DESENHA = r"""
(() => {
  const card = document.querySelector('.ctl.card[data-controle]');
  const cs = e => {
    if (!e) return {ausente: true};
    const c = getComputedStyle(e);
    return {cor: c.color, borda: c.borderTopColor, cursor: c.cursor,
            display: c.display, largura: e.getBoundingClientRect().width};
  };
  // O ♪ E A SUA LINHA. A régua acende o cinza pelo MESMO caminho do produto —
  // o atributo que o alvo `atributo` escreve —, e não por uma classe posta à
  // mão: medir uma classe que o produto não escreve mediria este arquivo.
  const bloco = card.querySelector('[data-bloco="alto-falante"]');
  const linha = bloco.querySelector('.vol');
  const botao = bloco.querySelector('.mudo-i');
  const antes = cs(botao);
  const ajuda = bloco.querySelector('.ajuda.porque');
  const porque_sem = cs(ajuda);
  // O PRODUTO ESCREVE AS DUAS EXPRESSÕES DO MESMO CAMPO, num tique só: o
  // atributo da linha (alvo `atributo`) e o conteúdo da dica (alvo `html`). A
  // régua faz o mesmo — escrever só o atributo mediria meia pintura, e a folha
  // das dez esconde o `?` com a dica vazia, com razão.
  linha.setAttribute('data-porque', 'razão de prova');
  ajuda.querySelector('.dica').innerHTML = 'razão de prova';
  const depois = cs(botao);
  const porque_com = cs(ajuda);
  // O CLIQUE — a metade que `disabled` mataria. Num botão `disabled`,
  // `HTMLElement.click()` não dispara ouvinte nenhum.
  let recebeu = 0;
  botao.addEventListener('click', () => { recebeu += 1; });
  botao.click();
  linha.removeAttribute('data-porque');

  // A MARCA DA DEGRADAÇÃO, pelo mesmo caminho: o `title` é o que o produto
  // escreve, e a folha decide a marca a partir dele.
  const sup = card.querySelector('.degradou');
  const marca_sem = cs(sup);
  sup.setAttribute('title', 'motivo de prova');
  const marca_com = cs(sup);
  sup.removeAttribute('title');

  // OS DOIS ANÉIS. O de fora é a borda do card (o plástico); o de dentro é o
  // elemento próprio, e a régua o pinta pelo mesmo `style.color` que o alvo
  // `cor` do piloto escreve.
  // ELEMENTO AUSENTE É MEDIDA, E NÃO ERRO DE INSTRUMENTO: sem esta guarda a
  // mordida (tirar o `<span class="anel-vivo">` do gerador) estoura no
  // `getComputedStyle` e derruba a leitura INTEIRA — a régua reprovaria pelo
  // caso errado, e quem lesse o vermelho procuraria o defeito noutro lugar.
  const anel = card.querySelector('.anel-vivo');
  const casco = getComputedStyle(card).borderTopColor;
  let anel_apagado = 'sem o anel', anel_aceso = 'sem o anel', anel_dentro = false;
  if (anel) {
    anel_apagado = getComputedStyle(anel).borderTopColor;
    anel.style.color = 'rgb(0, 0, 255)';
    anel_aceso = getComputedStyle(anel).borderTopColor;
    const caixa_do_card = card.getBoundingClientRect();
    const caixa_do_anel = anel.getBoundingClientRect();
    anel_dentro = (caixa_do_anel.left >= caixa_do_card.left
                   && caixa_do_anel.right <= caixa_do_card.right);
    anel.style.color = '';
  }

  return {
    botao_antes: antes, botao_depois: depois, clique_recebido: recebeu,
    botao_tem_disabled: botao.hasAttribute('disabled'),
    porque_sem: porque_sem, porque_com: porque_com,
    marca_sem: marca_sem, marca_com: marca_com,
    casco: casco, anel_apagado: anel_apagado, anel_aceso: anel_aceso,
    anel_dentro: anel_dentro,
    // OS DOIS ELEMENTOS DO MESMO ENDEREÇO, que é o que impede o anel e o
    // retângulo de discordarem.
    luz_cor_no_card: card.querySelectorAll('[data-campo="luz-cor"]').length,
    radio_alvo: card.querySelector('.radio-mesa').dataset.hefAlvo,
    radio_campo: card.querySelector('.radio-mesa').dataset.campo,
  };
})()
"""


@pytest.fixture(scope="module")
def desenhado() -> dict[str, Any]:
    """O que o Chrome desenha na página da BANCADA — uma abertura para todos."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    from playwright.sync_api import sync_playwright

    alvo = onde.pagina("02-controles.html")
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME),
                                       args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(alvo.as_uri())
            saida = pg.evaluate(O_QUE_O_NAVEGADOR_DESENHA)
        finally:
            navegador.close()
    return dict(saida)


def test_o_botao_de_som_apaga_e_ainda_assim_responde(desenhado: dict[str, Any]) -> None:
    """As duas metades que nenhuma sozinha prova: CINZA e CLICÁVEL.

    MORDE: comente `.vol[data-porque] .mudo-i{…}` no CSS desta aba e a primeira
    asserção reprova — a tela em repouso volta a não distinguir o botão que
    funciona do que vai recusar, que é a queixa inteira da D-03.
    """
    antes, depois = desenhado["botao_antes"], desenhado["botao_depois"]
    # A BORDA É O QUE MUDA, E NÃO A COR — medido neste motor, e é a mesma
    # descoberta que a ONDA0-F fez sobre o `.seg button:disabled`: o `.mudo-i`
    # JÁ NASCE em `--texto-mudo`, então não há cor a apagar. Quem diz "travado"
    # nesta gramática é a borda (de `--border-forte` para `--border-sutil`) e o
    # cursor. Uma asserção sobre a COR reprovaria sobre a folha certa.
    assert depois["borda"] != antes["borda"], (
        f"o botão com razão tem a MESMA borda do clicável ({antes['borda']}) — "
        f"a tela em repouso não distingue os dois")
    assert depois["cursor"] == "not-allowed"
    assert antes["cursor"] == "pointer", (
        "o botão SEM razão já nascia travado — o cinza deixou de ser um sinal")
    assert desenhado["clique_recebido"] == 1, (
        "o botão cinza não recebeu o clique — sem ele não há caminho de quem "
        "navega pelo controle até a razão")
    assert not desenhado["botao_tem_disabled"], (
        "o `disabled` voltou: ele mata o clique, e o PO decidiu o contrário")
    # O `?` SEGUE O MESMO ATRIBUTO, e este par saiu da FOTO: com o campo vazio
    # o piloto escreve o travessão no `innerHTML` da dica, ela deixa de ser
    # `:empty`, e o `?` apareceu na tela **com um `—` dentro**, ao lado de dois
    # botões clicáveis.
    assert desenhado["porque_sem"]["display"] == "none", (
        "o `?` apareceu ao lado de um botão que NÃO está apagado — um `?` sem "
        "nada a explicar é ruído com cara de dado")
    assert desenhado["porque_com"]["display"] != "none", (
        "o `?` não apareceu com o botão apagado — a razão ficou inalcançável")


def test_a_marca_da_degradacao_so_aparece_com_motivo(desenhado: dict[str, Any]) -> None:
    """Sem `title` a marca não ocupa nada; com ele, ela aparece.

    MORDE: comente `.degradou{display:none}` e a primeira asserção reprova —
    um asterisco laranja nasce em todo card, sobre controles que estão
    inteiros.
    """
    assert desenhado["marca_sem"]["display"] == "none"
    assert desenhado["marca_com"]["display"] != "none"
    assert desenhado["marca_com"]["cursor"] == "help"


def test_o_casco_fica_fora_e_a_luz_viva_dentro(desenhado: dict[str, Any]) -> None:
    """D-06 / S-11 — dois anéis, duas perguntas, e eles não se disputam.

    MORDE: tire o `<span class="anel-vivo">` do gerador e a régua reprova na
    contagem dos dois elementos do mesmo endereço; tire a regra de CSS e o anel
    deixa de mudar de cor.
    """
    assert desenhado["anel_apagado"] != desenhado["anel_aceso"], (
        "o anel interno não seguiu a cor de linha — ele deixou de ser a luz "
        "viva e virou desenho")
    assert desenhado["anel_aceso"] == "rgb(0, 0, 255)"
    assert desenhado["anel_aceso"] != desenhado["casco"], (
        "o anel interno e o casco pintaram a MESMA cor — são duas perguntas "
        "diferentes, e uma delas deixou de ser respondida")
    assert desenhado["anel_dentro"], "o anel interno saiu de dentro do casco"
    assert desenhado["luz_cor_no_card"] == 2, (
        "o retângulo e o anel deixaram de compartilhar o endereço `luz-cor` — "
        "com dois campos, os dois podem discordar na tela")


def test_o_acordeao_publica_o_decimo_alvo(desenhado: dict[str, Any]) -> None:
    """T-07 — o alvo `marcado` existe no piloto desde a ONDA0-P; o ENDEREÇO é
    desta aba, e é por ele que a régua do mockup passa a saber qual card está
    aberto.
    """
    assert desenhado["radio_alvo"] == "marcado"
    assert desenhado["radio_campo"] == "card-aberto"


# ===========================================================================
# 9. O MARCADOR É O MESMO DAS DUAS CASAS
# ===========================================================================
def test_o_nada_a_dizer_nao_divergiu_do_da_folha() -> None:
    """A cópia declarada do `monta.NADA_A_DIZER` — e a régua que a segura.

    O pacote NÃO PODE importar `monta`: ele é bancada, e importá-lo de dentro
    de um pacote arrasta o gerador para o fecho de produção — o
    `portao_a_casa_sabe_e_o_produto_nao_faz` já reprovou exatamente isso em
    02/09, nomeando três lápides. Um TESTE pode, porque teste não é fecho de
    produção; e é isso que impede as duas cópias de divergirem calado.
    """
    import monta

    assert a02.NADA_A_DIZER == monta.NADA_A_DIZER
