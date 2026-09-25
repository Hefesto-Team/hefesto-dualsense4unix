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
* devolva o sono do canal ao alarme (``selo_do_som``) ou à pílula
  (``mesa_viva.selo_do_alto_falante``) — os casos do canal PARADO reprovam
  (O-ALTO-FALANTE-DIZ-ATIVO-01, 23/09/2026; a régua dona é
  ``test_o_alto_falante_diz_ativo.py``);
* faça ``sufixo_do_canal("")`` devolver a palavra de acordado —
  ``test_sem_leitura_o_rotulo_nao_afirma_nada`` reprova;
* tire o ``card-vpad`` do pacote — ``TestADicaDoTitulo`` reprova;
* faça ``ressalva_do_transporte`` digitar a frase em vez de ler o mapa —
  ``test_a_celula_que_vira_apaga_a_ressalva`` reprova;
* tire o ``[data-bloco]`` do seletor da guarda no gerador —
  ``test_a_guarda_nao_alcanca_a_moldura_do_led`` reprova.

**O MICROFONE SEM FONTE** (MIC-SEM-FONTE-01, 13/09/2026) tem a seção 8, e as
mordidas dela estão na entrega da sprint: tire a pergunta da fonte de
``microfone_apagado``; devolva a moldura do microfone ao endereço da outra com a
fonte dentro dele; ponha o botão do microfone no seletor do ``sem-fonte``.

**O ALTO-FALANTE SEM ENDEREÇO** (RESTOS-DA-ONDA-DOIS-01, 13/09/2026) deixou o
``title`` da moldura pelo ``alto-apagado``, na forma do microfone: a camada da
dica da casa levava o ``title`` para ``data-hef-dica``, e a guarda nunca acendeu
no WebKit. A prova no piloto oculto está em ``test_os_restos_da_onda_dois.py``.
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

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

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
    dica_canal_sem_a_regra,
    DICA_TITULO_SEM_VPAD,
    SUFIXO_CANAL_ACORDADO,
    SUFIXO_CANAL_DORMINDO,
    TEXTO_AUDIO_SEM_ENDERECO,
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
DA_BANCADA = frozenset({"alto-apagado", "card-vpad", "alto-selo",
                        "alto-canal", "alto-canal-porque"})


def _entrada(**mais: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "uniq": UNIQ, "player": 1, "connected": True, "is_primary": True,
        "transport": "usb", "inputs": {}, "audio": {}, "battery_pct": 64,
    }
    return {**base, **mais}


def _cards(entradas: list[dict[str, Any]], mesa: list[dict[str, Any]], *,
           state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Os cards que o pacote monta, por `uniq`, com os endereços da bancada ligados."""
    from pacotes import Contexto

    antes = mod._ENDERECOS
    try:
        mod._ENDERECOS = frozenset(mod._enderecos_da_pagina() | DA_BANCADA)
        cheio = {"controllers": entradas, **(state or {})}
        return mod.pacote(Contexto(state=cheio, mesa=mesa,
                                   conectados=entradas))["cards"]
    finally:
        mod._ENDERECOS = antes


def _card(entrada: dict[str, Any], *, state: dict[str, Any] | None = None,
          mesa: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """O card que o pacote monta para UMA entrada."""
    cards = _cards([entrada], mesa if mesa is not None else MESA, state=state)
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
    """O alarme do bloco é UM: a saída muda (a camada 1).

    O SEGUNDO INFORMANTE SAIU EM 23/09/2026 — O-ALTO-FALANTE-DIZ-ATIVO-01. O
    alarme acendia também `Canal dormindo` num canal PARADO, e a foto dela
    mostrou duas pílulas num alto-falante que ninguém calou. O caso que prova a
    saída mora em `test_o_alto_falante_diz_ativo.py`, pelo pacote inteiro.
    """

    def test_a_saida_muda_acende_o_alarme(self) -> None:
        assert mod.selo_do_som(True) == TEXTO_SELO_SAIDA_MUDA

    @pytest.mark.parametrize("muda", [False, None])
    def test_so_true_acende_a_saida_muda(self, muda: bool | None) -> None:
        """`False` é "a saída está aberta" e `None` é "não sei" — os dois calam.

        Um selo "saída viva" seria ruído em cima do que a barra já diz, e um
        selo aceso a partir de `None` seria alarme sobre o que ninguém mediu.
        """
        assert mod.selo_do_som(muda) == ""


class TestOSeloDoAltoFalante:
    """O selo do rótulo — `sufixo_do_canal` morreu aqui em 19/09/2026.

    A PEÇA QUE ESTA CLASSE MEDIA devolvia a palavra do daemon
    (`acordado`/`dormindo`) para um chip cinza. Por ordem dela o chip virou o
    SELO do alto-falante, com a mesma cara e a mesma língua do selo do
    microfone: *"Ativo e Desligado pros dois não seria melhor que dormindo?"*
    <!-- noqa-acento: citação literal dela -->

    AS DUAS REGRAS QUE ELA GUARDAVA CONTINUAM, e por isso a classe fica em vez
    de sair: a palavra não se digita (vem do dono), e a AUSÊNCIA de leitura não
    vira afirmação.
    """

    def test_os_dois_estados_entram_no_rotulo(self) -> None:
        """As duas palavras saem do dono, e são DIFERENTES entre si.

        MORDE: faça `selo_do_alto_falante` devolver a mesma palavra nos dois.
        """
        import mesa_viva

        assert mesa_viva.selo_do_alto_falante(False, True) == mesa_viva.ATIVO
        assert mesa_viva.selo_do_alto_falante(True, True) == mesa_viva.DESLIGADO
        assert mesa_viva.ATIVO != mesa_viva.DESLIGADO

    def test_o_canal_parado_nao_desliga_o_selo(self, sono_lido) -> None:
        """Canal PARADO é ATIVO; só o mudo do ♪ desliga — 23/09/2026.

        FATO ERRADO, SUBSTITUÍDO: este teste cobrava o contrário (*"os DOIS
        fatos entram na mesma palavra"*), e era a régua do defeito que ela
        fotografou: todo controle no rádio nascia DESLIGADO, porque o nó dele
        dorme sempre que ninguém toca. A régua dona agora é
        `test_o_alto_falante_diz_ativo.py`.

        MORDE: devolva o sono do canal à pílula e o canal parado volta a
        aparecer como DESLIGADO ao lado de um ♪ ligado.
        """
        import mesa_viva

        sono_lido(audio_saida.CANAL_DORMINDO)
        parado = _card(_entrada(speaker={"volume": 60, "muted": False}))
        assert parado["alto-canal"] == mesa_viva.ATIVO
        calado = _card(_entrada(speaker={"volume": 60, "muted": True}))
        assert calado["alto-canal"] == mesa_viva.DESLIGADO

    def test_sem_leitura_o_rotulo_nao_afirma_nada(self) -> None:
        """`sabemos=False` é NÃO SEI, e não "está tocando".

        Sem placa de som — o caso do rádio, medido em 15/08/2026 — afirmar que o
        som sai prometeria o que o controle não tem por onde fazer. É a mesma
        regra do terceiro estado do selo do microfone.

        MORDE: faça `selo_do_alto_falante` cair no ATIVO por padrão.
        """
        import mesa_viva

        assert mesa_viva.selo_do_alto_falante(False, False) == mesa_viva.SEM_LEITOR
        assert mesa_viva.selo_do_alto_falante(True, False) == mesa_viva.SEM_LEITOR

    def test_o_cartao_cala_quando_o_canal_nao_foi_lido(self, sono_lido) -> None:
        """E no CARTÃO a ausência vira o marcador, não uma palavra.

        MORDE: faça o campo `alto-canal` chamar o dono mesmo com o canal sem
        leitura, e o rótulo do rádio passa a exibir um selo.
        """
        sono_lido("", False)
        assert _card(_entrada())["alto-canal"] == mod.NADA_A_DIZER


class TestADicaDoCanal:
    """A dica da pílula não fala do canal — 23/09/2026.

    VIROU RÓTULO EM 13/09/2026 (FRASES-E-DICAS-02) e SAIU EM 23/09/2026
    (O-ALTO-FALANTE-DIZ-ATIVO-01): ela dizia `Canal de áudio dormindo`, a última
    porta por onde a palavra do servidor de som chegava à tela. O endereço fica
    na página publicada e recebe o VAZIO, que apaga a dica — o alvo é
    `atributo`, e ali o marcador de nada viraria texto; a pílula fica como a do
    microfone, sem dica.
    """

    def test_a_funcao_saiu_do_pacote(self) -> None:
        """MORDE: devolva `dica_do_canal` ao pacote e esta linha reprova."""
        assert not hasattr(mod, "dica_do_canal")

    @pytest.mark.parametrize(
        "sono", ["", audio_saida.CANAL_ACORDADO, audio_saida.CANAL_DORMINDO])
    def test_a_dica_nao_narra_o_canal(self, sono_lido, sono: str) -> None:
        """MORDE: devolva a frase do canal ao `alto-canal-porque`."""
        sono_lido(sono)
        dita = _card(_entrada())["alto-canal-porque"]
        assert dita == ""
        for frase in (DICA_CANAL_ACORDADO, DICA_CANAL_DORMINDO,
                      DICA_CANAL_E_PADRAO, dica_canal_sem_a_regra()):
            assert frase not in dita, f"a dica do canal voltou a narrar: {dita!r}"


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
        """A metade VISÍVEL: o `data-apagado` da moldura do alto-falante.

        A do microfone lê `mic-apagado` desde 13/09/2026 — ver a seção 8. A do
        alto-falante escrevia o `title` da moldura até o mesmo dia, e a camada da
        dica da casa o levava para `data-hef-dica`: no WebKit a folha nunca o
        casou (RESTOS-DA-ONDA-DOIS-01, com a prova no piloto em
        `test_os_restos_da_onda_dois.py`). Agora é valor de atributo, sem frase.

        MORDE: tire o `alto-apagado` do pacote e este caso reprova.
        """
        card = _card(_entrada(uniq=None))
        assert card["alto-apagado"] == mod.MIC_SEM_ALVO
        assert TEXTO_AUDIO_SEM_ENDERECO not in card.values()

    def test_com_endereco_o_campo_volta_vazio_e_a_guarda_solta(self) -> None:
        """Vazio faz o piloto REMOVER o `data-apagado`, e a folha devolve as peças.

        A volta acontece sozinha — a guarda não precisa lembrar quem apagou.
        """
        assert _card(_entrada())["alto-apagado"] == ""

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
    def test_o_canal_parado_pinta_ativo_e_cala_o_resto(self, sono_lido) -> None:
        """O canal PARADO chega ao cartão como UMA pílula, ATIVO — 23/09/2026.

        FATO ERRADO, SUBSTITUÍDO: este caso cobrava `Canal dormindo` no alarme e
        DESLIGADO na pílula — as duas pílulas da foto dela.
        """
        import mesa_viva

        sono_lido(audio_saida.CANAL_DORMINDO, False)
        card = _card(_entrada())
        assert card["alto-selo"] == mod.NADA_A_DIZER
        assert card["alto-canal"] == mesa_viva.ATIVO
        assert card["alto-canal-porque"] == ""

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
        for campo in ("alto-selo", "alto-canal"):
            assert card[campo] == mod.NADA_A_DIZER, campo
        # A DICA É ATRIBUTO, e para atributo o nada é o VAZIO, que apaga — o
        # marcador viraria texto (O-ALTO-FALANTE-DIZ-ATIVO-01, 23/09/2026).
        assert card["alto-canal-porque"] == ""

    # `test_o_estado_e_o_porque_apagam_juntos` SAIU EM 23/09/2026: o porquê
    # (`alto-canal-porque`) não diz mais nada em estado nenhum — ver
    # `TestADicaDoCanal` —, e a régua de "os dois apagam juntos" passaria a
    # cobrar que a pílula apagasse com uma dica que não existe.


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

    def test_a_celula_do_mapa_so_vira_com_a_prova(self) -> None:
        """**A METADE QUE IMPEDE A CURA DE VIRAR MENTIRA.**

        Calar a tela é ordem dela; virar a célula sem prova não é. Esta régua
        dizia *"Quem fechar a `SOM-QUE-SAI-01` vira esta célula, e é esta régua
        que reprova se alguém a virar antes"* — e o canal FECHOU: o som saiu do
        plástico pelo rádio em 10/09 (report `0x35`, 70 s com a orelha dela) e
        a háptica passou pelo mesmo fio em 18/09. O commit `9f1920152` virou a
        célula com a régua que morde, e até 18/09/2026 esta asserção exigia
        `aciona != "sim"` — um fato que a casa derrubou.

        O QUE ELA COBRA AGORA: com a célula em `sim`, a procedência é
        `medido`; com a célula em `não`, a causa continua NOSSA. É a mesma
        honestidade dos dois lados — nem fingir que fechou, nem fingir que
        continua aberto.

        MORDE: troque `radio.de_onde_sei` para qualquer coisa que não seja
        `medido` com a célula em `sim`, e esta linha reprova.
        """
        celula = FATOS["audio.alto_falante@dualsense"]["radio"]
        assert isinstance(celula, dict)
        if celula["aciona"] == "sim":
            assert celula["de_onde_sei"] == "medido", (
                "a célula do alto-falante no rádio diz `sim` sem procedência "
                "`medido` — virar sem a medição é mentir ao contrário")
            return
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
        """O cartão não confessa dívida nossa no rádio — 07/09/2026.

        **E O CAMPO INTEIRO SAIU EM 22/09/2026, por ordem dela.** Aqui estava
        escrito que ele continuava existindo com o outro informante — o
        desacordo das duas camadas de som. Esse informante mandava clicar num
        botão que a fileira não tem desde 21/09, e ela pediu a frase fora. O
        que esta régua cobra hoje é que nenhum campo do alto-falante volte a
        falar do Hefesto.
        """
        card = _card(_entrada(transport="bt"))
        assert "alto-ressalva" not in card, (
            "a ressalva do alto-falante voltou ao cartão — ela saiu inteira em "
            "22/09/2026, por ordem dela, e a página não tem mais o endereço")
        assert not any("Hefesto" in str(v) for k, v in card.items()
                       if str(k).startswith("alto-")), (
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
        assert card["alto-apagado"] == ""
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
        assert "Canal dormindo" not in doc

    def test_os_dois_transportes_mostram_ativo(self) -> None:
        """A cena é o caso normal, e ela vale no cabo E no rádio — 23/09/2026.

        FATO ERRADO, SUBSTITUÍDO: esta régua cobrava que o controle do rádio
        não mostrasse pílula nenhuma, porque o DualSense não publica placa ALSA
        por rádio. A conclusão caiu em 10/09/2026, quando o produto passou a
        publicar o nó de som por controle (`hefesto_som_<hex6>`), e a foto dela
        de 23/09 mostra a pílula no controle do rádio. A MATRIZ da sprint vale
        para a cena também: a regra não é só do cabo.

        MORDE: faça `aba02.sufixo_do_canal` voltar a depender do transporte.
        """
        from monta import MESA as MESA_DO_DESENHO

        import aba02
        import mesa_viva

        na_mesa = [c for c in MESA_DO_DESENHO if c.get("conectado", True)]
        no_cabo = [c for c in na_mesa if c.get("transporte") == "usb"]
        no_radio = [c for c in na_mesa if c.get("transporte") == "bt"]
        assert no_cabo and no_radio, "a cena precisa dos dois transportes"
        for c in no_cabo + no_radio:
            chip = aba02.sufixo_do_canal(c)
            assert f">{mesa_viva.ATIVO}</span>" in chip, c["pref"]
            assert 'class="selo-ativo no-rotulo on"' in chip, c["pref"]
            assert mod.NADA_A_DIZER not in chip, c["pref"]
        # O LUGAR VAZIO não tem controle, logo não tem canal: a pílula some.
        vazios = [c for c in MESA_DO_DESENHO if not c.get("conectado", True)]
        assert vazios, "a cena precisa de um lugar vazio"
        assert all(mod.NADA_A_DIZER in aba02.sufixo_do_canal(c) for c in vazios)

    def test_a_palavra_do_sufixo_vem_do_produto(self) -> None:
        """O gerador não digita a palavra do canal: ele chama o dono.

        Se digitasse, a cena e a tela viva divergiriam CALADAS na primeira troca
        de palavra do `audio_saida` — um texto que não casa não dá erro nenhum.
        """
        fonte = (RAIZ / "src/hefesto_dualsense4unix/interface/aba02.py").read_text(
            encoding="utf-8")
        assert "mesa_viva.selo_do_alto_falante(" in fonte, (
            "o gerador voltou a digitar a palavra do selo em vez de perguntar "
            "ao dono (`mesa_viva.selo_do_alto_falante`) — a cena e a tela viva "
            "vão divergir CALADAS na primeira troca de palavra")

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
        # SÃO DOIS BLOCOS DESDE 19/09/2026: o alarme (`.selo-som`) guardou os
        # seletores dele, e o chip do canal virou selo — com as mesmas três
        # regras, sob o nome novo. O que a régua guarda é o COMPORTAMENTO: nem
        # um nem outro deixa vão no rótulo quando não há o que dizer.
        assert ".rot .selo-som:has(.nada){display:none}" in doc
        assert ".rot .selo-som:empty{display:none}" in doc
        assert ".rot .selo-ativo.no-rotulo:has(.nada){display:none}" in doc
        assert ".rot .selo-ativo.no-rotulo:has(.selo-palavra:empty){display:none}" in doc

    def test_o_nome_do_cartao_veste_a_dica_e_nasce_sem_ela(self) -> None:
        """O par físico↔virtual é do serviço; o desenho não o crava."""
        doc = _bancada()
        assert ('class="card-nome" data-campo="card-vpad" data-hef-alvo="atributo"'
                ' data-hef-atributo="title"') in doc
        assert "alimenta o gamepad virtual" not in doc.lower()


# ---------------------------------------------------------------------------
# 8. O MICROFONE SEM FONTE — MIC-SEM-FONTE-01, 13/09/2026
# ---------------------------------------------------------------------------
# O deslizante do microfone de um controle no rádio arrastava, e só DEPOIS o
# daemon respondia `sem_fonte`; a resposta já viajava no tique anterior, em
# `audio.canal_fonte` nulo. A ROTA CORRIGIDA da sprint pede o cinza ANTES do
# arrasto, num endereço só do microfone, e sem frase nenhuma.

#: A MESA MISTA da §1 da sprint, na faixa forjada: dois no cabo com a fonte
#: publicada e dois no rádio com a fonte nula.
MISTA = (
    ("p1", "aa:bb:cc:00:00:3a", "usb", "alsa_input.usb-regua-00.iec958-stereo"),
    ("p2", "aa:bb:cc:00:00:7d", "bt", None),
    ("p3", "aa:bb:cc:00:00:c4", "usb", "hefesto_mic_0000c4"),
    ("p4", "aa:bb:cc:00:00:e9", "bt", None),
)


def _com_fonte(fonte: str | None, **mais: Any) -> dict[str, Any]:
    """Uma entrada cujo daemon DISSE a fonte do microfone, nula ou não."""
    return _entrada(audio={"mic_mudo": False, "canal_fonte": fonte}, **mais)


def _regras_do_microfone(doc: str) -> list[tuple[str, str]]:
    """Cada seletor da moldura do microfone, com a declaração da regra dele."""
    estilo = "".join(re.findall(r"<style[^>]*>(.*?)</style>", doc, flags=re.S))
    estilo = re.sub(r"/\*.*?\*/", "", estilo, flags=re.S)
    pares = []
    for seletores, declaracao in re.findall(r"([^{}]*)\{([^{}]*)\}", estilo):
        for seletor in seletores.split(","):
            if 'data-bloco="microfone"' in seletor:
                pares.append((" ".join(seletor.split()), declaracao))
    return pares


class TestOMicrofoneSemFonte:
    """O cinza chega ANTES do arrasto, e só na moldura do microfone."""

    def test_a_fonte_nula_apaga_o_microfone_e_nao_o_alto_falante(self) -> None:
        """A mordida da ROTA CORRIGIDA, na metade do pacote.

        MORDE: tire a pergunta da fonte de `microfone_apagado` (o microfone
        acende) ou ponha a fonte no `alto-apagado` (o alto-falante apaga).
        """
        card = _card(_com_fonte(None, transport="bt"))
        assert card["mic-apagado"] == mod.MIC_SEM_FONTE
        assert card["alto-apagado"] == ""

    def test_com_fonte_o_microfone_acende(self) -> None:
        """A metade contrária: apagar o microfone do cabo seria pior que o defeito."""
        assert _card(_com_fonte("alsa_input.usb-regua"))["mic-apagado"] == ""

    def test_sem_a_chave_nao_ha_cinza(self) -> None:
        """Chave ausente é "não sei": o laço do canal ainda não perguntou.

        MORDE: faça `microfone_apagado` apagar na ausência da chave.
        """
        assert _card(_entrada(audio={"mic_mudo": False}))["mic-apagado"] == ""

    def test_sem_endereco_o_microfone_apaga_inteiro(self) -> None:
        """A guarda de antes continua, e o endereço vence a fonte."""
        card = _card(_com_fonte("alsa_input.usb-regua", uniq=None))
        assert card["mic-apagado"] == mod.MIC_SEM_ALVO
        assert card["alto-apagado"] == mod.MIC_SEM_ALVO

    def test_a_mesa_mista_apaga_so_os_dois_do_radio(self) -> None:
        """POR CONTROLE: um teste de um controle só passaria com a leitura global.

        MORDE: responda o cinza pela primeira entrada da mesa, para todos.
        """
        entradas = [
            _entrada(uniq=uniq, player=n, is_primary=n == 1, transport=via,
                     audio={"mic_mudo": False, "canal_fonte": fonte})
            for n, (_pref, uniq, via, fonte) in enumerate(MISTA, start=1)]
        mesa = [{"pref": pref, "jogador": n, "uniq": uniq, "nome": "Régua",
                 "via": "USB" if via == "usb" else "BT", "cor": "cosmic-red",
                 "mascara": "DualSense"}
                for n, (pref, uniq, via, _fonte) in enumerate(MISTA, start=1)]
        cards = _cards(entradas, mesa)
        visto = {uniq: (cards[uniq]["mic-apagado"], cards[uniq]["alto-apagado"])
                 for _pref, uniq, _via, _fonte in MISTA}
        assert visto == {
            MISTA[0][1]: ("", ""), MISTA[1][1]: (mod.MIC_SEM_FONTE, ""),
            MISTA[2][1]: ("", ""), MISTA[3][1]: (mod.MIC_SEM_FONTE, "")}

    @pytest.mark.parametrize("publicado", [False, True])
    def test_a_moldura_do_microfone_tem_endereco_proprio(self, publicado: bool) -> None:
        """Na bancada e no publicado: cada moldura de som lê o seu `data-apagado`.

        O microfone lê `mic-apagado` (MIC-SEM-FONTE-01) e o alto-falante lê
        `alto-apagado` (RESTOS-DA-ONDA-DOIS-01). Sem a página publicada o pacote
        nem emite o campo (`_so_se_a_pagina_tiver`), e a cura ficaria só no código.

        MORDE: devolva a moldura de uma das duas ao endereço da outra.
        """
        doc = onde.pagina(PAGINA, publicado=publicado).read_text(encoding="utf-8")
        mics = re.findall(r'<div class="moldura"[^>]*data-bloco="microfone"[^>]*>', doc)
        altos = re.findall(r'<div class="moldura"[^>]*data-bloco="alto-falante"[^>]*>',
                           doc)
        assert mics and len(mics) == len(altos), (len(mics), len(altos))
        for tag in mics:
            assert 'data-campo="mic-apagado"' in tag, tag
            assert 'data-hef-atributo="data-apagado"' in tag, tag
            assert "alto-apagado" not in tag, tag
        for tag in altos:
            assert 'data-campo="alto-apagado"' in tag, tag
            assert 'data-hef-atributo="data-apagado"' in tag, tag
            assert "mic-apagado" not in tag, tag

    def test_sem_fonte_so_o_deslizante_apaga(self) -> None:
        """O botão do microfone pede o canal: apagá-lo trancaria a única saída.

        MORDE: ponha `.mudo-i` ou `.rota` num seletor que case o `sem-fonte`, ou
        tire o `.trilho` da regra de opacidade.

        O ALVO É UMA LISTA DO QUE PODE APAGAR, e não uma lista do que não pode
        (validação, 13/09/2026). Procurar só `.mudo-i` e `.rota` no alvo deixava
        passar `[data-apagado] .vol`, que apaga a LINHA onde o 🎙 mora, e o
        seletor de prefixo `[data-apagado^="sem"]`: as duas sabotagens
        passaram verdes. Toda regra que casa um `data-apagado` que não seja só o
        `sem-alvo` tem de terminar numa peça do deslizante.
        """
        so_sem_alvo = re.compile(r'(?<!:not\()\[data-apagado="sem-alvo"\]')
        casa_sem_fonte = [
            (seletor, declaracao)
            for seletor, declaracao in _regras_do_microfone(_bancada())
            if "data-apagado" in seletor and not so_sem_alvo.search(seletor)]
        assert casa_sem_fonte, "a folha não tem regra para o microfone sem fonte"
        for seletor, _declaracao in casa_sem_fonte:
            alvo = seletor.rsplit("]", 1)[-1].split()
            assert alvo and alvo[-1] in {".trilho", ".n", ".puxa-vol"}, seletor
        assert any(".trilho" in s and "opacity" in d for s, d in casa_sem_fonte)
        assert any(".puxa-vol" in s and "not-allowed" in d for s, d in casa_sem_fonte)
