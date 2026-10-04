"""O «Nativo» do microfone fica cinza no rádio — APARELHO-NAO-SE-CONTRADIZ-01, 3.

A PERGUNTA FOI DELA, 20/09/2026: *"Tenho pensado se o botão virtual ou nativo do
microfone ainda fazem sentido. Pq meio que todo o Mic dele é virtual por conta
dos modos não?"*

A DECISÃO TAMBÉM: *"Fica os dois botões. Mas no rádio o botão fica cinza sem ser
ativado"*. Ela recusou as três opções oferecidas — sumir no rádio, escrever o
módulo de kernel, aposentar o par — e deu a quarta.

## O que foi medido, e a intuição dela estava certa pela metade

No RÁDIO só existe a ponte do Hefesto: as fontes na máquina dela, com três
controles no rádio, são ``hefesto_mic_…`` e nenhuma fonte do kernel. No CABO
existem AS DUAS: a ``alsa_input.usb-Sony_…`` que o UCM publica (sem ``HEFESTO``
no nome) e a ponte ao lado.

E não dá para criar a nativa no rádio: o BlueZ registra **dois UUIDs** para o
DualSense — HID (``0x1124``) e PnP (``0x1200``) — e nenhum A2DP ou HFP.

## A TRAVA CONTRA A VOLTA, e é o ponto de desenho desta cura

A régua **não** digita «rádio → cinza». Ela pergunta ao aparelho: existe uma
fonte de captura deste controle que não seja NOSSA? No dia em que o BlueZ
publicar um perfil de áudio, a fonte nativa aparece e o botão volta ao alcance
sem que ninguém toque numa linha.

## A mordida

:class:`TestAMordida` arranca a recusa do gesto e exige que ele volte a gravar
no rádio — que é a metade que a sprint pede: *"com um controle no rádio, clicar
no «Nativo» não pode mudar nada nem gravar nada"*.

Nenhum endereço real: faixa forjada ``aa:bb:cc:…``.
"""
from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

from hefesto_dualsense4unix.integrations.fontes_de_captura import (
    PREFIXO_SOURCE_CANAL_DO_MIC,
    PREFIXO_SOURCE_PONTE_BT,
    fontes_dualsense,
    fontes_nativas,
)

UNIQ = "aa:bb:cc:00:00:01"

NO_CABO = (
    "42\talsa_input.usb-Sony_Interactive_Entertainment_Wireless_Controller-00"
    ".HiFi__Mic__source\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED\n"
    f"43\t{PREFIXO_SOURCE_CANAL_DO_MIC}aabbcc\tPipeWire\ts16le 1ch 48000Hz\tIDLE\n"
)

NO_RADIO = (
    f"51\t{PREFIXO_SOURCE_CANAL_DO_MIC}aabbcc\tPipeWire\ts16le 1ch 48000Hz\tIDLE\n"
    f"52\t{PREFIXO_SOURCE_PONTE_BT}aabbcc\tPipeWire\ts16le 1ch 48000Hz\tIDLE\n"
)


@pytest.fixture
def a02(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O pacote da aba, com o cache do nativo limpo entre as réguas."""
    from hefesto_dualsense4unix.interface.pacotes import a02_controles

    monkeypatch.setattr(a02_controles, "_MIC_NATIVO", {})
    return a02_controles


class TestAPerguntaEAoAparelho:
    """Quem separa o nativo do nosso é o NOME, e o dono dele é um só."""

    def test_no_cabo_existe_uma_fonte_que_nao_e_nossa(self) -> None:
        nativas = fontes_nativas(NO_CABO)
        assert len(nativas) == 1
        assert nativas[0].startswith("alsa_input.usb-Sony")
        assert "hefesto" not in nativas[0].lower()

    def test_no_radio_nao_existe_nenhuma(self) -> None:
        """As duas do rádio são nossas — inclusive a que tem «dualsense» no nome."""
        assert fontes_dualsense(NO_RADIO), "a mesa de teste ficou vazia"
        assert fontes_nativas(NO_RADIO) == []

    def test_a_regua_nao_digita_o_transporte(self) -> None:
        """Nenhuma linha do dono pergunta «é cabo?» — é a trava contra a volta."""
        fonte = pathlib.Path(
            RAIZ / "src/hefesto_dualsense4unix/integrations/fontes_de_captura.py")
        corpo = fonte.read_text(encoding="utf-8")
        inicio = corpo.index("def fontes_nativas")
        corpo_da_funcao = corpo[corpo.index('"""', corpo.index('"""', inicio) + 3):]
        corpo_da_funcao = corpo_da_funcao[: corpo_da_funcao.index("\ndef ")]
        for palavra in ("transport", "usb", "\"bt\"", "'bt'"):
            assert palavra not in corpo_da_funcao, (
                f"o dono passou a decidir por transporte ({palavra!r}) — a tela "
                f"deixa de acompanhar o aparelho sozinha")


class TestARazaoEUmaSo:
    """Um campo só alimenta o cinza e o `?` — o contrato de `monta.botao_cinza`."""

    def test_sem_fonte_nativa_ha_razao(self, a02: Any) -> None:
        a02._MIC_NATIVO[UNIQ] = False
        assert a02.nativo_fora_de_alcance(UNIQ) == a02.RAZAO_DO_NATIVO_FORA

    def test_com_fonte_nativa_nao_ha_razao(self, a02: Any) -> None:
        a02._MIC_NATIVO[UNIQ] = True
        assert a02.nativo_fora_de_alcance(UNIQ) == ""

    def test_nao_sei_nao_apaga_botao(self, a02: Any) -> None:
        """`None` e a chave AUSENTE são a mesma coisa: não sei."""
        a02._MIC_NATIVO[UNIQ] = None
        assert a02.nativo_fora_de_alcance(UNIQ) == ""
        del a02._MIC_NATIVO[UNIQ]
        assert a02.nativo_fora_de_alcance(UNIQ) == ""

    def test_a_frase_diz_o_fato_sem_confessar_divida(self, a02: Any) -> None:
        """Regra dela, 07/09/2026: o que falta mora no mapa, nunca na tela."""
        frase = a02.RAZAO_DO_NATIVO_FORA
        assert "rádio" in frase and "Hefesto" in frase
        for confissao in ("ainda", "por enquanto", "falta", "não implement"):
            assert confissao not in frase.lower(), (
                f"a frase confessa dívida nossa ({confissao!r})")


class TestOGestoRecusaDizendo:
    """O botão fica cinza E continua respondendo — quem diz «não dá» é o gesto."""

    @staticmethod
    def _ctx(transporte: str) -> Any:
        from pacotes import Contexto

        return Contexto(
            state={}, mesa=[],
            conectados=[{"uniq": UNIQ, "transport": transporte}], estados={})

    class _Ponte:
        def __init__(self) -> None:
            self.declarados: list[Any] = []

        def machine_declare(self, decl: Any) -> tuple[bool, str]:
            self.declarados.append(decl)
            return (True, "")

    def test_no_radio_o_nativo_nao_grava_nada(self, a02: Any,
                                              monkeypatch: pytest.MonkeyPatch) -> None:
        a02._MIC_NATIVO[UNIQ] = False
        monkeypatch.setattr(a02, "_DECLARADOS", {"aabbcc000001": SimpleNamespace()})
        ponte = self._Ponte()
        with pytest.raises(RuntimeError) as erro:
            a02.mic_modo(self._ctx("bt"), {"uniq": UNIQ, "micModo": "nativo"}, ponte)
        assert str(erro.value) == a02.RAZAO_DO_NATIVO_FORA
        assert ponte.declarados == [], (
            "o gesto gravou no disco um modo que o aparelho não alcança")

    def test_no_cabo_o_mesmo_controle_grava(self, a02: Any,
                                            monkeypatch: pytest.MonkeyPatch) -> None:
        """A outra metade da mordida da sprint, e ela é o oráculo desta régua."""
        a02._MIC_NATIVO[UNIQ] = True
        monkeypatch.setattr(a02, "_DECLARADOS", {"aabbcc000001": SimpleNamespace()})
        monkeypatch.setattr(a02, "_controles_declarados", lambda recarregar=False: {})
        ponte = self._Ponte()
        a02.mic_modo(self._ctx("usb"), {"uniq": UNIQ, "micModo": "nativo"}, ponte)
        assert ponte.declarados, "no cabo o «Nativo» tem de gravar"

    def test_o_virtual_continua_gravando_no_radio(self, a02: Any,
                                                  monkeypatch: pytest.MonkeyPatch) -> None:
        """Só o «Nativo» recusa. O «Virtual» grava nos dois desde a D-12."""
        a02._MIC_NATIVO[UNIQ] = False
        monkeypatch.setattr(a02, "_DECLARADOS", {"aabbcc000001": SimpleNamespace()})
        monkeypatch.setattr(a02, "_controles_declarados", lambda recarregar=False: {})
        ponte = self._Ponte()
        a02.mic_modo(self._ctx("bt"), {"uniq": UNIQ, "micModo": "virtual"}, ponte)
        assert ponte.declarados, "o «Virtual» parou de gravar pelo rádio"


class TestODesenhoTemOndeOProdutoEscrever:
    """A página que o produto mostra sabe apagar o botão.

    O par «Virtual | Nativo» saiu da bancada em 03/10/2026 (a decisão dela de
    02/10, OS-NOS-DE-SOM-SEM-O-ENDERECO-NO-NOME-01); até o ``--publicar 02``
    ele vive na página publicada, e esta classe sai junto com o gesto.
    """

    @staticmethod
    def _bancada() -> str:
        from hefesto_dualsense4unix.interface import onde

        return onde.pagina("02-controles.html", publicado=True).read_text(encoding="utf-8")

    def test_o_endereco_esta_na_pagina_publicada(self) -> None:
        corpo = self._bancada()
        assert 'data-campo="mic-nativo-fora"' in corpo
        assert 'data-hef-classe="sem-nativo"' in corpo

    def test_um_campo_so_alimenta_o_cinza_e_a_razao(self) -> None:
        """O contrato de `monta.botao_cinza`: com dois campos, eles divergem."""
        corpo = self._bancada()
        assert 'data-campo="mic-nativo-fora" data-hef-alvo="classe"' in corpo
        assert ('<span class="dica" data-campo="mic-nativo-fora" '
                'data-hef-alvo="html">') in corpo

    def test_o_endereco_do_container_e_de_alvo_classe_e_nunca_de_texto(self) -> None:
        """A exceção ao «container endereçado é container que some» é de ALVO."""
        corpo = self._bancada()
        assert 'class="rota mic-modo" data-campo="mic-nativo-fora" data-hef-alvo="classe"' in corpo
        piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
                  ).read_text(encoding="utf-8")
        assert "if(alvo === 'classe'){" in piloto

    def test_a_folha_sabe_pintar_o_cinza(self) -> None:
        """Sem a regra, a classe chega e não muda um pixel."""
        corpo = self._bancada()
        assert '.mic-modo.sem-nativo button[data-mic-modo="nativo"]' in corpo

    def test_o_pacote_so_emite_o_que_a_pagina_publicada_tem(self, a02: Any) -> None:
        """A guarda que impede a chave de virar órfã no casamento das dez."""
        from hefesto_dualsense4unix.interface import onde

        publicado = onde.pagina("02-controles.html", publicado=True).read_text(
            encoding="utf-8")
        tem = publicado.count('data-hef-classe="sem-nativo"') > 0
        assert tem == a02.A_PAGINA_APAGA_O_NATIVO


class TestNoCaboONativoNaoNasceCinza:
    """O VALOR QUE A TELA RECEBE, lido com a régua do PILOTO — conferência da"""

    @staticmethod
    def _apagados_pelo_piloto() -> set[str]:
        """Os valores que o alvo `classe` lê como APAGADOS — lidos do piloto."""
        import re

        piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py"
                  ).read_text(encoding="utf-8")
        inicio = piloto.index("function ligado(t){")
        corpo = piloto[inicio:piloto.index("}", inicio)]
        apagados = set(re.findall(r"b === '([^']*)'", corpo))
        assert "" in apagados and "—" in apagados, apagados
        return apagados

    @pytest.mark.parametrize("transporte", ["usb", "bt"])
    def test_o_valor_da_chave_segue_o_aparelho(self, a02: Any,
                                              monkeypatch: pytest.MonkeyPatch,
                                              transporte: str) -> None:
        """Alcança: a chave vai num valor que o piloto APAGA; não alcança: vai"""
        from pacotes import Contexto

        apagados = self._apagados_pelo_piloto()
        monkeypatch.setattr(a02, "A_PAGINA_APAGA_O_NATIVO", True)
        dele = {"uniq": UNIQ, "transport": transporte, "connected": True,
                "inputs": {}, "audio": {}, "speaker": {}}
        for razao, apagado in (("", True), (a02.RAZAO_DO_NATIVO_FORA, False)):
            monkeypatch.setattr(a02, "nativo_fora_de_alcance", lambda uniq, r=razao: r)
            ctx = Contexto(state={}, mesa=[], conectados=[dele], estados={})
            valor = next(iter(a02.pacote(ctx)["cards"].values()))["mic-nativo-fora"]
            assert (str(valor).strip().lower() in apagados) is apagado, (
                f"{transporte}: com o aparelho dizendo {razao!r}, a chave foi "
                f"{valor!r} — o «Nativo» ficaria "
                f"{'cinza' if apagado else 'aceso'} contra o aparelho")


class TestAMordida:
    """Arranque a recusa e veja o rádio voltar a gravar."""

    def test_sem_a_recusa_o_radio_grava_o_nativo(self, a02: Any,
                                                 monkeypatch: pytest.MonkeyPatch) -> None:
        """A cura arrancada = o gesto sem o `raise` do «Nativo»."""
        monkeypatch.setattr(a02, "_DECLARADOS", {"aabbcc000001": SimpleNamespace()})
        monkeypatch.setattr(a02, "_controles_declarados", lambda recarregar=False: {})
        ctx = TestOGestoRecusaDizendo._ctx("bt")

        a02._MIC_NATIVO[UNIQ] = True
        ponte = TestOGestoRecusaDizendo._Ponte()
        a02.mic_modo(ctx, {"uniq": UNIQ, "micModo": "nativo"}, ponte)
        assert ponte.declarados, "a mordida não reproduziu o mundo pré-cura"

        a02._MIC_NATIVO[UNIQ] = False
        ponte = TestOGestoRecusaDizendo._Ponte()
        with pytest.raises(RuntimeError):
            a02.mic_modo(ctx, {"uniq": UNIQ, "micModo": "nativo"}, ponte)
        assert ponte.declarados == []
