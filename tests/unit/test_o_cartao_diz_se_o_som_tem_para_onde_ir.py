#!/usr/bin/env python3
"""O CARTÃO DIZ SE O SOM TEM PARA ONDE IR — CONTROLES-OS-TRES-SELOS-01.

Quatro linhas do CSV da paridade fecham aqui, e as quatro são **LEITURA de
estado que já existe**: nenhuma delas oferece um botão novo, e nenhuma reescreve
a regra de um dono.

===========  =======================================================
linha 45     a dica do título — QUAL gamepad virtual este controle alimenta
linha 57     a guarda "sem endereço" — as peças que MANDAM som apagam
linha 89     o selo ``Saída muda`` — a camada 1 do PipeWire
linha 90     ``acordado`` / ``dormindo`` no rótulo da moldura
===========  =======================================================

**E O QUARTO SELO**, que é a T6 da ``STATUS-DIZ-O-QUE-VE-01``, viva desde 25/08
e nunca executada: a guarda do bloco de som ganha a SEGUNDA pergunta — o
TRANSPORTE —, e a resposta vem do MAPA, nunca da cabeça de quem escreve. A
célula ``audio.alto_falante@dualsense`` diz, no rádio, ``aciona=não`` com causa
``divida``; com ``divida`` a única ``Fala`` legal é ``AFIRMA_NADA`` com
``porque=``, e a frase honesta é *"o Hefesto ainda não faz"* — nunca *"o
controle não faz"*.

**A RÉGUA QUE PROVA QUE ISSO É LEITURA E NÃO FRASE DIGITADA** é a
``TestOQuartoSelo``: ela troca a célula num dublê do mapa e vê a frase TROCAR.
No dia em que a ``SOM-QUE-SAI-01`` virar aquela célula, o selo muda sozinho e
esta régua continua verde — que é o fluxo inteiro da ``PAREAMENTO-01``.

AS MORDIDAS, todas feitas e devolvidas antes deste arquivo ser commitado:

* tire a guarda de endereço de ``porques_do_som`` — ``TestAGuardaSemEndereco``
  reprova nas duas metades (a razão e o cinza);
* faça ``selo_do_som`` responder pelo canal ANTES da saída muda — o caso dos
  dois males ao mesmo tempo reprova;
* faça ``sufixo_do_canal("")`` devolver a palavra de acordado —
  ``test_sem_leitura_o_rotulo_nao_afirma_nada`` reprova;
* tire o ``card-vpad`` do pacote — ``TestADicaDoTitulo`` reprova;
* faça ``ressalva_do_transporte`` digitar a frase em vez de ler o mapa —
  ``test_a_celula_que_vira_apaga_a_ressalva`` reprova;
* tire o ``[data-bloco]`` do seletor da guarda no gerador —
  ``test_a_guarda_nao_alcanca_a_moldura_do_led`` reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.app import audio_saida
from hefesto_dualsense4unix.app.fala_do_mapa import (
    CAUSA_DE_FORA,
)
from hefesto_dualsense4unix.app.fatos_do_mapa import FATOS
from hefesto_dualsense4unix.app.widgets.controller_card import (
    DICA_AUDIO_SEM_ENDERECO,
    DICA_CANAL_ACORDADO,
    DICA_CANAL_DORMINDO,
    DICA_CANAL_E_PADRAO,
    DICA_CANAL_SEM_A_REGRA,
    DICA_TITULO_SEM_VPAD,
    SUFIXO_CANAL_ACORDADO,
    SUFIXO_CANAL_DORMINDO,
    TEXTO_AUDIO_SEM_ENDERECO,
    TEXTO_SELO_CANAL_DORMINDO,
    TEXTO_SELO_SAIDA_MUDA,
)
from hefesto_dualsense4unix.interface import onde
from hefesto_dualsense4unix.interface.pacotes import a02_controles as mod

PAGINA = "02-controles.html"  # (noqa-acento) nome de arquivo

#: Endereços da faixa forjada da casa — nunca o do aparelho dela.
UNIQ = "aa:bb:cc:00:00:02"
SINK = "alsa_output.pci-0000_00_1f.3.analog-stereo"

MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "USB", "cor": "cosmic-red", "mascara": "DualSense"}]

#: Os quatro endereços que a BANCADA tem e a página publicada ainda não —
#: publicar é ato dela. Sem forçá-los, a régua mediria a espera pela publicação
#: em vez da cura, e daria verde com o pacote apagado.
DA_BANCADA = frozenset({"som-sem-endereco", "card-vpad", "alto-selo",
                        "alto-canal", "alto-canal-porque"})


def _entrada(**mais: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "uniq": UNIQ, "player": 1, "connected": True, "is_primary": True,
        "transport": "usb", "inputs": {}, "audio": {}, "battery_pct": 64,
    }
    return {**base, **mais}


def _card(entrada: dict[str, Any], *, state: dict[str, Any] | None = None,
          mesa: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """O card que o pacote monta, com os endereços da bancada ligados."""
    from pacotes import Contexto

    antes = mod._ENDERECOS
    try:
        mod._ENDERECOS = frozenset(mod._enderecos_da_pagina() | DA_BANCADA)
        cheio = {"controllers": [entrada], **(state or {})}
        cards = mod.pacote(Contexto(state=cheio,
                                    mesa=mesa if mesa is not None else MESA,
                                    conectados=[entrada]))["cards"]
    finally:
        mod._ENDERECOS = antes
    assert len(cards) == 1, f"esperava um card, vieram {len(cards)}"
    return next(iter(cards.values()))


@pytest.fixture
def sono_lido():
    """Escreve direto no cache do sono — sem thread, sem `pactl`, sem relógio.

    É o mesmo ponto de injeção que a `_CAMADA_1` já declara: *"quem quiser medir
    o desacordo das duas camadas escreve no cache e não espera thread nenhuma —
    uma régua que dependesse de um relógio seria uma corrida, e corrida na suíte
    é vermelho que aparece uma vez em dez"*.
    """
    guardado = dict(mod._SONO), mod._REGRA_DO_SONO[0]

    def por(estado: str, regra: bool | None = True) -> None:
        mod._SONO.clear()
        mod._SONO[UNIQ] = estado
        mod._REGRA_DO_SONO[0] = regra
    yield por
    mod._SONO.clear()
    mod._SONO.update(guardado[0])
    mod._REGRA_DO_SONO[0] = guardado[1]


def _bancada() -> str:
    return onde.pagina(PAGINA).read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 1. A LEITURA DO SONO — um `pactl` para a mesa inteira, e o dono é quem traduz
# ---------------------------------------------------------------------------

#: A lista curta do `pactl`, no formato que `estados_crus_dos_sinks` parseia:
#: índice, nome, driver, formato, ESTADO — separados por TAB.
LISTA_CURTA = (
    f"35872\t{SINK}\tPipeWire\ts16le 2ch 48000Hz\tSUSPENDED\n"
    "35873\talsa_output.outro\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"
)


class TestALeituraDoSono:
    """`_ler_o_sono` pergunta ao dono e não reescreve o vocabulário."""

    def test_o_sink_suspenso_e_o_ocioso_sao_lidos_pelo_dono(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Quem traduz `SUSPENDED`/`IDLE` é `audio_saida.estado_do_canal`.

        MORDE: escreva um `if cru == "SUSPENDED"` dentro de `_ler_o_sono` e este
        teste continua verde — por isso ele NÃO basta sozinho, e o irmão
        `test_o_vocabulario_tem_um_dono_so` é quem tranca a segunda gramática.
        """
        monkeypatch.setattr(audio_saida, "rodar_leitura", lambda argv: LISTA_CURTA)
        lido = mod._ler_o_sono({
            UNIQ: audio_saida.RotaDasDuasCamadas(byte=2, sink_do_controle=SINK),
            "outro": audio_saida.RotaDasDuasCamadas(
                byte=2, sink_do_controle="alsa_output.outro"),
        })
        assert lido == {UNIQ: audio_saida.CANAL_DORMINDO,
                        "outro": audio_saida.CANAL_ACORDADO}

    def test_sem_sink_nao_entra_chave(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """O caso do RÁDIO: não há placa ALSA, logo não há canal a descrever.

        A ausência da chave é o "não sei" honesto — um `""` gravado seria
        indistinguível de "li a coluna e não reconheci o estado".
        """
        monkeypatch.setattr(audio_saida, "rodar_leitura", lambda argv: LISTA_CURTA)
        assert mod._ler_o_sono(
            {UNIQ: audio_saida.RotaDasDuasCamadas(byte=None, sink_do_controle="")}
        ) == {}

    def test_a_leitura_que_falha_nao_inventa_estado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem `pactl` na máquina, a tela cala — nunca "acordado" por omissão."""
        def explode(argv: list[str]) -> str:
            raise OSError("não há pactl aqui")

        monkeypatch.setattr(audio_saida, "rodar_leitura", explode)
        assert mod._ler_o_sono(
            {UNIQ: audio_saida.RotaDasDuasCamadas(byte=2, sink_do_controle=SINK)}
        ) == {}

    def test_o_vocabulario_tem_um_dono_so(self) -> None:
        """As duas pontas dizem a MESMA palavra, e isso é medido, não confiado.

        `audio_saida` PRODUZ (`CANAL_ACORDADO`/`CANAL_DORMINDO`) e o card da GTK
        CONSOME (`SUFIXO_CANAL_*`). Se um dos dois trocar de palavra sem o
        outro, o selo desta aba para de acender CALADO — comparação de string
        que não casa não dá erro nenhum.
        """
        assert audio_saida.CANAL_ACORDADO == SUFIXO_CANAL_ACORDADO
        assert audio_saida.CANAL_DORMINDO == SUFIXO_CANAL_DORMINDO


# ---------------------------------------------------------------------------
# 2. OS DOIS SELOS — a prioridade é a da GTK, e ela não é arbitrária
# ---------------------------------------------------------------------------


class TestOsSelos:
    def test_a_saida_muda_ganha_do_canal_dormindo(self) -> None:
        """Os dois males ao mesmo tempo dizem UMA coisa: a que cala o som.

        Uma saída muda cala o som venha o canal de onde vier; um canal dormindo
        só come o começo. Dizer as duas na mesma linha troca um alarme por dois
        avisos.

        MORDE: inverta as duas perguntas de `selo_do_som` e este caso reprova.
        """
        assert mod.selo_do_som(True, audio_saida.CANAL_DORMINDO) == TEXTO_SELO_SAIDA_MUDA

    def test_o_canal_dormindo_acende_sozinho(self) -> None:
        assert mod.selo_do_som(False, audio_saida.CANAL_DORMINDO) == (
            TEXTO_SELO_CANAL_DORMINDO)
        assert mod.selo_do_som(None, audio_saida.CANAL_DORMINDO) == (
            TEXTO_SELO_CANAL_DORMINDO)

    @pytest.mark.parametrize("muda", [False, None])
    def test_so_true_acende_a_saida_muda(self, muda: bool | None) -> None:
        """`False` é "a saída está aberta" e `None` é "não sei" — os dois calam.

        Um selo "saída viva" seria ruído em cima do que a barra já diz, e um
        selo aceso a partir de `None` seria alarme sobre o que ninguém mediu.
        """
        assert mod.selo_do_som(muda, audio_saida.CANAL_ACORDADO) == ""

    def test_o_selo_nao_existe_no_estado_bom(self) -> None:
        assert mod.selo_do_som(False, audio_saida.CANAL_ACORDADO) == ""
        assert mod.selo_do_som(None, "") == ""


class TestOSufixoDoCanal:
    def test_os_dois_estados_entram_no_rotulo(self) -> None:
        assert mod.sufixo_do_canal(audio_saida.CANAL_ACORDADO) == "· acordado"
        assert mod.sufixo_do_canal(audio_saida.CANAL_DORMINDO) == "· dormindo"

    def test_sem_leitura_o_rotulo_nao_afirma_nada(self) -> None:
        """`""` é NÃO SEI, e não "acordado".

        Sem placa de som — o caso do rádio, medido em 15/08/2026 — escrever
        "acordado" a partir de ausência prometeria que o som sai inteiro num
        controle que não tem por onde tocá-lo.

        MORDE: faça `sufixo_do_canal` cair no acordado por padrão.
        """
        assert mod.sufixo_do_canal("") == ""


class TestADicaDoCanal:
    """As frases são as do dono, e a do PADRÃO depende da REGRA estar no lugar."""

    def test_sem_leitura_nao_ha_frase(self) -> None:
        assert mod.dica_do_canal("", True) == ""

    def test_a_regra_instalada_diz_que_e_o_padrao(self) -> None:
        dita = mod.dica_do_canal(audio_saida.CANAL_ACORDADO, True)
        assert DICA_CANAL_ACORDADO in dita and DICA_CANAL_E_PADRAO in dita

    def test_a_cura_arrancada_e_denunciada(self) -> None:
        """Com o drop-in 54 fora do lugar, a tela DIZ — o sintoma é silencioso."""
        dita = mod.dica_do_canal(audio_saida.CANAL_DORMINDO, False)
        assert DICA_CANAL_DORMINDO in dita and DICA_CANAL_SEM_A_REGRA in dita

    def test_ninguem_perguntou_nao_afirma_nem_um_nem_outro(self) -> None:
        """`None` é "ninguém perguntou": nem "é o padrão", nem "falta a regra".

        Um nó pode estar acordado por acaso com a cura fora do lugar; chamar
        isso de padrão seria a tela dando por curado o que só está de pé agora.
        """
        dita = mod.dica_do_canal(audio_saida.CANAL_ACORDADO, None)
        assert dita == DICA_CANAL_ACORDADO
        assert DICA_CANAL_E_PADRAO not in dita
        assert DICA_CANAL_SEM_A_REGRA not in dita


# ---------------------------------------------------------------------------
# 3. A GUARDA SEM ENDEREÇO — linha 57
# ---------------------------------------------------------------------------


class TestAGuardaSemEndereco:
    """Sem MAC, todo comando de som deste card cai no controle PRIMÁRIO."""

    @pytest.mark.parametrize("uniq", [None, "", "   "])
    def test_a_razao_dos_dois_botoes_e_a_do_endereco(self, uniq: object) -> None:
        """As três formas de "sem endereço" viram a MESMA frase, a do dono.

        `""` e `"   "` valem `None` de propósito: um endereço em branco viaja no
        IPC como "sem alvo" e o daemon cai no primário — o defeito que a guarda
        existe para impedir. Quem decide isso é `uniq_do_entry`, na GTK.

        MORDE: tire o `if uniq_do_entry(entry) is None` de `porques_do_som`.
        """
        porques = mod.porques_do_som(_entrada(uniq=uniq))
        assert porques == {"mic-porque": DICA_AUDIO_SEM_ENDERECO,
                           "alto-porque": DICA_AUDIO_SEM_ENDERECO}

    def test_o_endereco_ganha_da_razao_da_posse(self) -> None:
        """Sem endereço, "arraste o volume ao lado" manda fazer o estrago.

        O deslizante aplicaria no controle ERRADO. A frase da posse só pode ser
        dita quando há a quem aplicar.
        """
        assert mod.DICA_ALTO_SEM_POSSE not in mod.porques_do_som(
            _entrada(uniq=None)).values()

    def test_com_endereco_a_razao_volta_a_ser_a_da_posse(self) -> None:
        """A guarda não engole o estado normal: com MAC, quem decide é o motor."""
        porques = mod.porques_do_som(_entrada())
        assert porques["alto-porque"] == mod.DICA_ALTO_SEM_POSSE
        assert DICA_AUDIO_SEM_ENDERECO not in porques.values()

    def test_o_cartao_apaga_as_pecas_que_mandam_som(self) -> None:
        """A metade VISÍVEL: o campo que veste o `title` das duas molduras.

        MORDE: tire o `som-sem-endereco` do pacote e este caso reprova.
        """
        assert _card(_entrada(uniq=None))["som-sem-endereco"] == (
            TEXTO_AUDIO_SEM_ENDERECO)

    def test_com_endereco_o_campo_volta_vazio_e_a_guarda_solta(self) -> None:
        """Vazio faz o piloto REMOVER o `title`, e a folha devolve as peças.

        A volta acontece sozinha — a guarda não precisa lembrar quem apagou.
        """
        assert _card(_entrada())["som-sem-endereco"] == ""

    def test_a_leitura_fica_ligada(self) -> None:
        """Sem endereço, o que o daemon publicou sobre ESTE controle continua.

        Quem mente sem endereço é o COMANDO. Apagar a leitura junto seria
        esconder o que continua verdadeiro.
        """
        card = _card(_entrada(uniq=None, battery_pct=64,
                              speaker={"volume": 60, "muted": False}))
        assert card["bateria"] == "64 %"
        assert card["alto-num"] != ""


# ---------------------------------------------------------------------------
# 4. A DICA DO TÍTULO — linha 45
# ---------------------------------------------------------------------------


class TestADicaDoTitulo:
    """QUAL gamepad virtual este controle alimenta, do dono da frase."""

    def test_o_par_fisico_e_virtual_chega_ao_cartao(self) -> None:
        """A frase inteira é do dono; o pacote só a leva ao endereço.

        MORDE: tire o `card-vpad` do pacote, ou troque o `ctx.state` por `{}`.
        """
        estado = {"coop": {"mesa": [{"uniq": UNIQ, "player": 3,
                                     "vpad_backend": "uinput",
                                     "vpad_uniq": "aa:bb:cc:00:00:09"}]}}
        dica = _card(_entrada(), state=estado)["card-vpad"]
        assert "uinput" in dica and "aa:bb:cc:00:00:09" in dica
        assert "Jogador 3" in dica

    def test_o_fisico_sem_virtual_diz_ainda_nao(self) -> None:
        """"Ainda não" e "não sei" são respostas diferentes, e o card já pagou
        caro por dizê-las igual."""
        estado = {"coop": {"mesa": [{"uniq": UNIQ, "player": 1}]}}
        assert _card(_entrada(), state=estado)["card-vpad"] == DICA_TITULO_SEM_VPAD

    def test_sem_lista_o_cartao_nao_inventa_par(self) -> None:
        """Daemon velho, ou controle fora da mesa de jogadores: o `title` some.

        `""` faz o piloto remover o atributo — nada aparece, em vez de o card
        afirmar um par que ninguém montou.
        """
        assert _card(_entrada())["card-vpad"] == ""
        assert _card(_entrada(uniq=None), state={"coop": {"mesa": []}})[
            "card-vpad"] == ""


# ---------------------------------------------------------------------------
# 5. OS SELOS NO CARTÃO — linhas 89 e 90 chegando ao endereço
# ---------------------------------------------------------------------------


class TestOsSelosNoCartao:
    def test_o_canal_dormindo_pinta_os_tres_campos(self, sono_lido) -> None:
        sono_lido(audio_saida.CANAL_DORMINDO, False)
        card = _card(_entrada())
        assert card["alto-selo"] == TEXTO_SELO_CANAL_DORMINDO
        assert card["alto-canal"] == "· dormindo"
        assert DICA_CANAL_SEM_A_REGRA in card["alto-canal-porque"]

    def test_a_saida_muda_acende_pelo_payload(self, sono_lido) -> None:
        """A camada 1 chega pelo `speaker.saida_muda`, lida pelo dono."""
        sono_lido(audio_saida.CANAL_ACORDADO, True)
        card = _card(_entrada(speaker={"volume": 60, "muted": False,
                                       "saida_muda": True}))
        assert card["alto-selo"] == TEXTO_SELO_SAIDA_MUDA

    def test_sem_leitura_os_tres_mandam_o_marcador_de_nada(self) -> None:
        """A chave vai em TODO tique, com o marcador — nunca omitida.

        Omitir deixaria a frase velha na tela para sempre, e mandar `""` faria
        o piloto escrever um travessão solto no rótulo da moldura.
        """
        card = _card(_entrada())
        for campo in ("alto-selo", "alto-canal", "alto-canal-porque"):
            assert card[campo] == mod.NADA_A_DIZER, campo

    def test_o_estado_e_o_porque_apagam_juntos(self, sono_lido) -> None:
        """Os dois nascem do mesmo `sono`: não há caminho para um sem o outro.

        Um sufixo sem razão, ou uma razão sem sufixo, é o defeito que a forma de
        dois elementos existe para não cometer.
        """
        for estado in ("", audio_saida.CANAL_ACORDADO, audio_saida.CANAL_DORMINDO):
            sono_lido(estado, True)
            card = _card(_entrada())
            vazio_do_sufixo = card["alto-canal"] == mod.NADA_A_DIZER
            vazio_da_razao = card["alto-canal-porque"] == mod.NADA_A_DIZER
            assert vazio_do_sufixo == vazio_da_razao, estado


# ---------------------------------------------------------------------------
# 6. O QUARTO SELO SAIU DA TELA — 07/09/2026, e a dívida ficou no mapa
# ---------------------------------------------------------------------------


class TestOQuartoSeloSaiuDaTela:
    """A ordem dela, e ela vale para a tela inteira:

        *"O app tem que funcionar e não mostrar na tela que o app não presta. Se
         não tem como, ok. Testamos e criamos o canal. até lá tudo bem, o layout
         não informa os nossos defeitos."*

    **SEIS TESTES MORAVAM AQUI**, e mediam bem o que a peça fazia: que a frase
    era uma `Fala` com `AFIRMA_NADA`, que só o rádio a ganhava, que trocar a
    célula num dublê a apagava. Eles saem com a peça, e a razão de sair em vez
    de serem adaptados é a mesma que a casa já pagou: *um teste que continua
    exigindo a peça reprova a ordem dela em vez do defeito*.

    O QUE FICA NO LUGAR são as DUAS metades que a ordem dela cria — e é o par
    que nenhuma metade sozinha prova:

    1. **A TELA CALOU.** O campo do cartão não carrega mais aquela frase, e o
       pacote não a declara mais.
    2. **A DÍVIDA NÃO SUMIU.** A célula do mapa continua dizendo `aciona=não`
       com causa `divida`, e virá-la para calar a tela seria mentir ao
       contrário. É esta segunda metade que separa *"tiramos da tela"* de
       *"fingimos que fechou"*.
    """

    def test_a_celula_do_mapa_continua_dizendo_a_divida(self) -> None:
        """**A METADE QUE IMPEDE A CURA DE VIRAR MENTIRA.**

        Calar a tela é ordem dela; virar a célula não é. O canal continua
        fechado, e é no mapa — que é de quem desenvolve — que isso tem de
        continuar escrito. Quem fechar a `SOM-QUE-SAI-01` vira esta célula, e é
        esta régua que reprova se alguém a virar antes.

        MORDE: troque `radio.aciona` para `"sim"` no mapa sem fechar o canal e
        esta linha reprova.
        """
        celula = FATOS["audio.alto_falante@dualsense"]["radio"]
        assert isinstance(celula, dict)
        assert celula["aciona"] != "sim", (
            "a célula do alto-falante no rádio virou para `sim` — o canal "
            "continua fechado, e virá-la é mentir ao contrário")
        assert celula["por_que_nao_aciona"] not in CAUSA_DE_FORA, (
            "a causa deixou de ser NOSSA no mapa — se ela mudou de dono, a "
            "medição tem de vir junto")

    def test_o_pacote_nao_declara_mais_a_frase(self) -> None:
        """A peça saiu inteira: a `Fala` e a função que a lia.

        MORDE: devolva a `Fala` ou a função ao pacote e esta linha reprova.
        """
        for morto in ("RESSALVA_DO_ALTO_NO_RADIO", "ressalva_do_transporte",
                      "lado_do_mapa", "CHAVE_DO_ALTO_FALANTE"):
            assert not hasattr(mod, morto), (
                f"`{morto}` voltou ao pacote — ela mandou a tela calar sobre "
                f"esta dívida em 07/09/2026")

    def test_o_cartao_nao_confessa_no_radio(self) -> None:
        """O campo continua existindo; o que ele não faz mais é confessar.

        E ELE NÃO FICOU MUDO POR ISSO: o outro informante (o desacordo das duas
        camadas de som) continua lá, e é o certo — aquilo é um fato de AGORA,
        que ela desfaz trocando a saída do sistema. Estado presente a tela pode
        dizer; capacidade por entregar, não.
        """
        card = _card(_entrada(transport="bt"))
        assert "alto-ressalva" in card, (
            "o campo sumiu do pacote — um campo que a página tem e o pacote "
            "não manda fica congelado no que o gerador escreveu")
        assert "Hefesto" not in str(card["alto-ressalva"]), (
            "o cartão voltou a confessar dívida nossa no rádio")

    def test_os_gestos_nao_apagam_por_uma_divida_nossa(self) -> None:
        """A dívida é NOSSA: apagar quatro gestos por ela é empurrá-la para ela.

        A célula da ROTA é `aciona=sim` nos dois lados, e o mudo do microfone é
        `parcial` — nenhum dos dois autoriza apagar coisa nenhuma. Isto não
        mudou com a saída do selo: a tela deixou de DIZER, e continua sem
        apagar nada.
        """
        rota = FATOS["audio.alto_falante.rota@dualsense"]["radio"]
        assert isinstance(rota, dict) and rota["aciona"] == "sim"
        card = _card(_entrada(transport="bt"))
        assert card["som-sem-endereco"] == ""
        assert card["alto-porque"] == mod.DICA_ALTO_SEM_POSSE


# ---------------------------------------------------------------------------
# 7. O DESENHO — o que a bancada ganhou, e o que ela NÃO ganhou
# ---------------------------------------------------------------------------


class TestODesenho:
    def test_os_cinco_enderecos_estao_na_bancada(self) -> None:
        doc = _bancada()
        for campo in sorted(DA_BANCADA):
            assert f'data-campo="{campo}"' in doc, campo

    def test_o_selo_nasce_apagado(self) -> None:
        """O ALARME não se crava no desenho: acendê-lo sem medição é mentira."""
        doc = _bancada()
        assert TEXTO_SELO_SAIDA_MUDA not in doc
        assert TEXTO_SELO_CANAL_DORMINDO not in doc

    def test_o_cabo_mostra_acordado_e_o_radio_nao_mostra_nada(self) -> None:
        """A cena é o caso normal, e o rádio não finge ter placa de som.

        Um desenho em que o controle do RÁDIO dissesse "acordado" ensinaria de
        volta a mentira que `sufixo_do_canal("")` existe para não contar.

        MORDE: faça `aba02.sufixo_do_canal` responder acordado para todos.
        """
        from monta import MESA as MESA_DO_DESENHO

        import aba02

        no_cabo = [c for c in MESA_DO_DESENHO if c.get("transporte") == "usb"]
        no_radio = [c for c in MESA_DO_DESENHO if c.get("transporte") == "bt"]
        assert no_cabo and no_radio, "a cena precisa dos dois transportes"
        assert all("· acordado" in aba02.sufixo_do_canal(c) for c in no_cabo)
        assert all(mod.NADA_A_DIZER in aba02.sufixo_do_canal(c) for c in no_radio)

    def test_a_palavra_do_sufixo_vem_do_produto(self) -> None:
        """O gerador não digita `· acordado`: ele chama o dono.

        Se digitasse, a cena e a tela viva divergiriam CALADAS na primeira troca
        de palavra do `audio_saida` — um texto que não casa não dá erro nenhum.
        """
        fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py").read_text(
            encoding="utf-8")
        assert "_sufixo_do_canal(sono)" in fonte

    def test_a_guarda_nao_alcanca_a_moldura_do_led(self) -> None:
        """A moldura do LED tem `title` FIXO — um `.moldura[title]` solto a apaga.

        MORDE: troque os seletores por `.moldura[title]` e este caso reprova.
        """
        doc = _bancada()
        assert re.search(r'class="moldura led"[^>]*title="', doc), (
            "a moldura do LED perdeu o `title` fixo — o risco que este caso "
            "guarda mudou de forma, releia o seletor da guarda")
        for seletor in re.findall(r"\.moldura\[[^{]*\{", doc):
            assert "data-bloco" in seletor, (
                f"o seletor {seletor!r} alcança TODA moldura com `title`, "
                f"inclusive a do LED do jogador")

    def test_o_sufixo_e_o_selo_somem_com_o_marcador(self) -> None:
        """As três regras da folha: o marcador, a dica vazia e o `:empty`."""
        doc = _bancada()
        assert ".rot .canal:has(.nada),.rot .selo-som:has(.nada){display:none}" in doc
        assert ".rot .canal:empty,.rot .selo-som:empty{display:none}" in doc

    def test_o_nome_do_cartao_veste_a_dica_e_nasce_sem_ela(self) -> None:
        """O par físico↔virtual é do serviço; o desenho não o crava."""
        doc = _bancada()
        assert ('class="card-nome" data-campo="card-vpad" data-hef-alvo="atributo"'
                ' data-hef-atributo="title"') in doc
        assert "alimenta o gamepad virtual" not in doc.lower()
