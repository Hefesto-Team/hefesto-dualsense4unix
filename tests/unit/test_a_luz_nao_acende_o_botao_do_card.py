"""O botão "A luz não acende" do card, e a espera pelo botão PS.

22/08/2026. A barra do DualSense por rádio nasce travada em algumas instâncias
de conexão, e a única cura conhecida é derrubar a conexão pelo BlueZ e deixar a
pessoa apertar PS. Este arquivo guarda as três regras dela sobre esse botão, e
guarda a mentira que a espera existe para não contar.

AS REGRAS DELA, uma classe de teste cada
----------------------------------------

1. *"sempre visível mas só acionável quando tiver no rádio"* — no cabo o defeito
   não existe, e botão que SOME ensina que a tela é instável;
2. **o produto não reconecta** — o botão PS é dela, e nada aqui pode chamar um
   ``Connect``;
3. **o fim da espera diz o que aconteceu**, e "não voltou" tem de dizer que o
   controle continua PAREADO — sem isso a pessoa reapareia um controle pareado.

A MENTIRA QUE A ESPERA NÃO PODE CONTAR
--------------------------------------

No instante do clique o controle AINDA ESTÁ no sysfs: o ``Disconnect`` foi
pedido e o nó leva um tempo para sumir. Uma espera que só perguntasse "ele está
aí?" responderia **voltou** no primeiro tique, o card piscaria, e ninguém
apertaria PS nenhum. Por isso são dois marcos em ordem — ver sumir, e só então
ver voltar.

AS MORDIDAS, ARRANCADAS E CONFERIDAS EM 22/08/2026
--------------------------------------------------

Cada uma é uma linha de `src/` trocada, o arquivo rodado, e a cura devolvida.
Vinte e nove casos no total:

===========================================================  ===========
mutação                                                      reprova
===========================================================  ===========
``pode_derrubar`` deixa de olhar ``no_cabo``                  3 de 29
``tique`` declara ``voltou`` sem nunca ter visto cair         3 de 29
a sonda cega (``None``) passa a contar como "caiu"            1 de 29
``frase_nao_voltou`` perde a oração do "continua pareado"     1 de 29
``_oculto`` para de chamar ``set_no_show_all``                1 de 29
o bloco entra DEPOIS da linha do jogador                      2 de 29
===========================================================  ===========

A terceira e a quarta reprovam um caso só, e isso é o desenho: são as duas
frases que separam "não sei" de "não" — quem as apagar tem de ver exatamente
qual promessa quebrou.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o botão A luz não acende do card externo")

import os
from typing import Any

import pytest

from hefesto_dualsense4unix.app.actions.config.secao_controles import (
    DICA_NO_CABO,
    DICA_NO_RADIO,
    ESPERA_CANCELADA,
    ESPERA_NAO_CAIU,
    ESPERA_NAO_VOLTOU,
    ESPERA_PELO_PS_S,
    ESPERA_PROCURANDO,
    ESPERA_VOLTOU,
    FRASE_APERTE_PS,
    FRASE_NAO_CAIU,
    TEXTO_CANCELAR,
    TEXTO_DO_BOTAO,
    EsperaPeloPS,
    dica_do_botao,
    frase_da_procura,
    frase_nao_voltou,
    pode_derrubar,
    uniq_normalizado,
)
from hefesto_dualsense4unix.interface.dados_do_controle import DadosDoControle

#: Um DualSense no rádio. MAC na faixa sintética `aa:bb:cc` que o portão de
NO_RADIO = DadosDoControle(
    chave="k1",
    titulo="Jogador 2",
    subtitulo="Sony · Bluetooth",
    uniq="aa:bb:cc:00:00:01",
    slot=2,
    adotado=True,
    endereco="aabbcc000001",
    no_cabo=False,
)
NO_CABO = DadosDoControle(**{**NO_RADIO.__dict__, "chave": "k2", "no_cabo": True})
NAO_ADOTADO = DadosDoControle(
    chave="k3",
    titulo="Jogador 3",
    subtitulo="8BitDo · Bluetooth",
    uniq="aa:bb:cc:00:00:02",
    slot=3,
    adotado=False,
    endereco="aabbcc000002",
)

ALVO = uniq_normalizado(NO_RADIO.uniq)

_CONDENADO: dict[str, Any] = {
    "confianca": "suspeita",
    "porque": (
        "nasceu com outro processo segurando o nó do controle — nesta condição "
        "a barra não obedece, e só a reconexão devolve"
    ),
    "pede_reconexao": True,
    "instancia": "0028",
    "hw_version": "0x00000811",
    "firme": True,
}


class _SondaDeMentira:
    """Devolve um roteiro de leituras, uma por tique. `None` = "não consegui olhar"."""

    def __init__(self, roteiro: list[set[str] | None]) -> None:
        self._roteiro = list(roteiro)
        self.chamadas = 0

    def __call__(self) -> set[str] | None:
        self.chamadas += 1
        if not self._roteiro:
            return set()
        return self._roteiro.pop(0)


class TestSoAcionavelNoRadio:
    def test_no_radio_o_botao_e_clicavel(self) -> None:
        assert pode_derrubar(NO_RADIO) is True

    def test_no_cabo_o_botao_nao_e_clicavel(self) -> None:
        """A regra dela, e a única diferença entre os dois dados é o transporte."""
        assert pode_derrubar(NO_CABO) is False

    def test_controle_que_o_hefesto_nao_adotou_nao_ganha_o_gesto(self) -> None:
        """Sem barra não há o que curar — e prometer curaria uma luz que não há."""
        assert pode_derrubar(NAO_ADOTADO) is False

    def test_sem_endereco_nao_ha_quem_o_bluez_procure(self) -> None:
        sem_uniq = DadosDoControle(**{**NO_RADIO.__dict__, "uniq": ""})
        assert pode_derrubar(sem_uniq) is False

    def test_a_dica_do_cabo_diz_por_que_esta_apagado(self) -> None:
        """Botão insensível sem explicação é o defeito que esta casa já pagou."""
        from hefesto_dualsense4unix.app.actions.home_actions import (
            palavra_do_transporte as palavra,
        )

        dica = dica_do_botao(NO_CABO)
        assert dica == DICA_NO_CABO
        assert palavra("usb") in dica and palavra("bt") in dica

    def test_a_dica_do_radio_diz_que_o_ps_e_dela(self) -> None:
        dica = dica_do_botao(NO_RADIO)
        assert "PS" in dica
        assert "não reconecta sozinho" in dica

    def test_a_dica_do_radio_e_so_o_que_o_botao_faz(self) -> None:
        """FRASES-E-DICAS-02, 13/09/2026: o aviso da mesa suja saiu da dica."""
        import inspect

        assert list(inspect.signature(dica_do_botao).parameters) == ["dados"]
        assert dica_do_botao(NO_RADIO) == DICA_NO_RADIO


class TestPrimeiroVerCairDepoisVerVoltar:
    def test_o_controle_ainda_presente_no_primeiro_tique_nao_e_voltou(self) -> None:
        """A mordida principal deste arquivo."""
        espera = EsperaPeloPS(ALVO, total_s=5, sonda=_SondaDeMentira([{ALVO}] * 3))
        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.caiu is False

    def test_sumiu_e_voltou_e_o_unico_caminho_para_voltou(self) -> None:
        sonda = _SondaDeMentira([{ALVO}, set(), set(), {ALVO}])
        espera = EsperaPeloPS(ALVO, total_s=10, sonda=sonda)
        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.caiu is True
        assert espera.tique() == ESPERA_PROCURANDO
        assert espera.tique() == ESPERA_VOLTOU

    def test_a_sonda_cega_nao_conta_como_sumiu(self) -> None:
        """`None` é "não consegui olhar" e não pode virar notícia."""
        espera = EsperaPeloPS(ALVO, total_s=4, sonda=_SondaDeMentira([None, None]))
        espera.tique()
        espera.tique()
        assert espera.caiu is False


class TestOFimDaEsperaTemNome:
    def test_nunca_caiu_nao_manda_apertar_ps(self) -> None:
        """O `Disconnect` respondeu e o controle não saiu: nada a apertar."""
        espera = EsperaPeloPS(ALVO, total_s=3, sonda=_SondaDeMentira([{ALVO}] * 5))
        for _ in range(3):
            estado = espera.tique()
        assert estado == ESPERA_NAO_CAIU
        assert espera.porque == FRASE_NAO_CAIU
        assert "continua pareado" in espera.porque

    def test_caiu_e_nao_voltou_diz_que_o_pareamento_esta_de_pe(self) -> None:
        """Sem esta oração a pessoa reapareia um controle que está pareado."""
        espera = EsperaPeloPS(ALVO, total_s=3, sonda=_SondaDeMentira([set()] * 5))
        for _ in range(3):
            estado = espera.tique()
        assert estado == ESPERA_NAO_VOLTOU
        assert "continua pareado" in espera.porque
        assert "3s" in espera.porque

    def test_os_dois_fins_ruins_nao_se_confundem(self) -> None:
        """"não caiu" e "não voltou" pedem gestos diferentes dela."""
        assert frase_nao_voltou(ESPERA_PELO_PS_S) != FRASE_NAO_CAIU

    def test_cancelar_encerra_e_nao_reconecta(self) -> None:
        sonda = _SondaDeMentira([set(), {ALVO}])
        espera = EsperaPeloPS(ALVO, total_s=9, sonda=sonda)
        espera.tique()
        espera.cancelar()
        assert espera.estado == ESPERA_CANCELADA
        assert espera.tique() == ESPERA_CANCELADA
        assert espera.porque == ""

    def test_o_relogio_para_no_fim(self) -> None:
        """Tique depois do fim não mexe em nada — o card já saiu da espera."""
        espera = EsperaPeloPS(ALVO, total_s=1, sonda=_SondaDeMentira([set()] * 4))
        assert espera.tique() == ESPERA_NAO_VOLTOU
        assert espera.tique() == ESPERA_NAO_VOLTOU
        assert espera.restantes == 0

    def test_a_contagem_conta_para_baixo_e_nao_fica_negativa(self) -> None:
        assert frase_da_procura(38) == "procurando…  38s"
        assert frase_da_procura(-4) == "procurando…  0s"


class TestNenhumaFraseLeALampada:
    """Ninguém nesta casa consegue LER a barra — nenhuma frase pode fingir."""

    def test_nenhuma_frase_afirma_acesa_ou_apagada(self) -> None:
        frases = [
            TEXTO_DO_BOTAO,
            TEXTO_CANCELAR,
            FRASE_APERTE_PS,
            FRASE_NAO_CAIU,
            DICA_NO_RADIO,
            DICA_NO_CABO,
            frase_nao_voltou(60),
            frase_da_procura(38),
        ]
        for frase in frases:
            baixa = frase.lower()
            assert "acesa" not in baixa
            assert "apagada" not in baixa
            assert "vai acender" not in baixa

    def test_o_rotulo_e_a_queixa_dela_e_nao_o_remedio(self) -> None:
        """Quem procura o botão procura o sintoma, nunca "reiniciar Bluetooth"."""
        assert TEXTO_DO_BOTAO == "A luz não acende"


class TestNormalizacaoDoEndereco:
    def test_as_duas_formas_que_circulam_no_produto_batem(self) -> None:
        assert uniq_normalizado("AA:BB:CC:00:00:01") == "aabbcc000001"
        assert uniq_normalizado("aabbcc000001") == "aabbcc000001"

    def test_o_que_nao_e_mac_nao_vira_alvo(self) -> None:
        for lixo in ("", None, "abc", "zz:bb:cc:00:00:01"):
            assert uniq_normalizado(lixo) == ""


gi = pytest.importorskip("gi", reason="o bloco na tela precisa de PyGObject")
gi.require_version("Gtk", "3.0")

CABECA = pytest.mark.skipif(
    not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY"),
    reason="sem display: rode com xvfb-run -a",
)


class _CaiuDeVerdade:
    """O que `gesto_de_reconexao.desconectar` devolve quando o controle caiu."""

    caiu = True
    porque = "Desconectei o controle. Aperte PS nele para ele voltar."


class _NaoDeu:
    """O quarto estado do gesto: não sei se caiu. Nunca é sucesso."""

    caiu = False
    porque = (
        "Não consegui falar com o Bluetooth do sistema, então não sei se o "
        "controle caiu. Ele continua pareado."
    )
