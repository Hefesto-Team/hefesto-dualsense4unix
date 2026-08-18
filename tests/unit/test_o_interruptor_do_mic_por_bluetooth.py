"""O interruptor da ponte de microfone por Bluetooth — decisão dela de 07/08.

*"no card do controle, junto do medidor"* — resposta 7 do painel
(`docs/process/2026-08-07-DECISOES-DELA-as-onze-respostas-do-painel.md`).

O buraco que ele fecha, medido em 25/07 com os quatro controles por BT: por
Bluetooth o DualSense **não expõe placa de áudio** (`pactl list sources` não tem
uma linha de DualSense), porque o áudio dele trafega como Opus tunelado em
reports HID. A ponte que decodifica isso existe há semanas
(`integrations/dualsense_bt_audio.py`, validada ao vivo gravando WAV) e o
subsystem sobe (`daemon/subsystems/bt_mic.py`) — mas a única forma de ligá-la
era a variável de ambiente `HEFESTO_DUALSENSE4UNIX_BT_MIC=1` ou o terminal.
**Nenhuma linha dela no `main.glade`.** A janela não sabia que a ponte existia.

O que este arquivo cobra, e por quê:

1. **o estado** — função pura (`acao_ponte_bt`), sem GTK, sem sysfs, sem disco:
   ela roda no tique de 10 Hz da aba e um `diagnosticar()` ali dentro custaria
   uma varredura de sysfs por décimo de segundo;
2. **a decisão de subir** (`ligar_ponte_bt`) com o mundo injetado — o caminho de
   produção toca hidraw, libopus e PipeWire, e um teste que dependesse disso não
   rodaria no CI nem diria nada sobre a decisão que este código toma;
3. **o texto** — que ele NÃO promete mudar o padrão, e que o preço medido está à
   vista. Continuar opt-in é o estado de hoje, e sair dele depende de uma
   medição com os quatro no rádio que ela ainda não fez.
"""

from __future__ import annotations

from typing import Any

import pytest

from hefesto_dualsense4unix.app.widgets.controller_card import (
    DICA_MIC_BT_DESLIGAR,
    DICA_MIC_BT_LIGAR,
    DICA_MIC_BT_NO_CABO,
    TEXTO_MIC_BT_ROTULO,
    acao_ponte_bt,
    desligar_ponte_bt,
    ligar_ponte_bt,
)

#: MAC da FAIXA SINTÉTICA que o portão de anonimato aceita (`aa:bb:cc`).
#: A máscara da casa (octetos 4 e 5 zerados) não basta aqui: ela preserva o
#: OUI, que é identidade de fabricante — e `test_anonimato_de_fixtures`
#: reprova qualquer MAC de fixture fora de `02:fe`/`aa:bb:cc`/`e8:47:3a`.
MAC = "aa:bb:cc:00:11:22"
OUTRO_MAC = "aa:bb:cc:00:33:44"


class _No:
    """Um `NoDualSenseBT` de mentira — só o que o filtro por controle usa."""

    def __init__(self, uniq: str, caminho: str = "/dev/hidraw9") -> None:
        self.uniq = uniq
        self.caminho = caminho


class _Diag:
    def __init__(self, impedimentos: list[str] | None = None) -> None:
        self.impedimentos = impedimentos or []


class _Gerenciador:
    """Dublê do `GerenciadorMicBluetooth`: registra o que lhe pediram."""

    ultimo: _Gerenciador | None = None

    def __init__(self, *, sobe: bool = True) -> None:
        self.pontes: dict[str, Any] = {}
        self.reconciliados: list[list[Any]] = []
        self.parou = 0
        self._sobe = sobe
        _Gerenciador.ultimo = self

    def reconciliar(self, nos: list[Any] | None = None) -> None:
        self.reconciliados.append(list(nos or []))
        if self._sobe:
            for no in nos or []:
                self.pontes[no.caminho] = object()

    def parar(self) -> None:
        self.parou += 1
        self.pontes.clear()


# ---------------------------------------------------------------------------
# O estado do interruptor (puro)
# ---------------------------------------------------------------------------


def test_no_cabo_o_interruptor_fica_apagado_e_diz_por_que() -> None:
    """Apagado, e NUNCA escondido: sumir é indistinguível de "não tem mic".

    É a mesma regra que a MIC-PRESENTE-01 cravou nesta coluna, e a queixa que a
    originou foi dela: *"na aba status falta a presença permanente do
    microfone (mesmo que não esteja funcionando no bt...)"*.
    """
    acao = acao_ponte_bt({"transport": "usb"})

    assert acao.sensivel is False
    assert acao.ativa is False
    assert acao.dica == DICA_MIC_BT_NO_CABO
    assert "no cabo" in acao.dica.lower()


def test_no_radio_o_interruptor_liga_e_a_dica_diz_o_preco() -> None:
    acao = acao_ponte_bt({"transport": "bt"})

    assert acao.sensivel is True
    assert acao.ativa is False
    assert acao.dica == DICA_MIC_BT_LIGAR


def test_com_a_ponte_de_pe_o_interruptor_mostra_ligado() -> None:
    acao = acao_ponte_bt({"transport": "bt"}, ligada=True)

    assert (acao.sensivel, acao.ativa) == (True, True)
    assert acao.dica == DICA_MIC_BT_DESLIGAR


def test_o_recado_de_uma_falha_manda_na_dica() -> None:
    """O motivo medido na hora vale mais que a explicação genérica."""
    acao = acao_ponte_bt({"transport": "bt"}, recado="libopus ausente")

    assert acao.dica == "libopus ausente"
    assert acao.ativa is False


def test_entry_sem_transporte_nao_promete_nada() -> None:
    """Sem saber o transporte, o interruptor fica apagado — não ligado no chute."""
    assert acao_ponte_bt(None).sensivel is False
    assert acao_ponte_bt({}).sensivel is False


# ---------------------------------------------------------------------------
# Subir a ponte — a decisão, com o mundo injetado
# ---------------------------------------------------------------------------


def test_sobe_a_ponte_so_do_controle_deste_card() -> None:
    """A MORDIDA: sem o filtro por `uniq`, um clique sobe ponte para os QUATRO.

    Ela clica no card de UM controle. `reconciliar()` sem lista varre o sysfs e
    sobe ponte para todo DualSense no rádio — quatro microfones abertos por um
    clique, e três deles sem ninguém ter pedido.
    """
    ger, recado = ligar_ponte_bt(
        MAC,
        diagnosticar=lambda: _Diag(),
        nos=lambda: [_No(MAC, "/dev/hidraw3"), _No(OUTRO_MAC, "/dev/hidraw4")],
        gerenciador=_Gerenciador,
    )

    assert recado == ""
    assert ger is not None
    assert [no.uniq for no in ger.reconciliados[0]] == [MAC], (
        "a ponte subiu para outro controle além do que ela clicou"
    )


def test_controle_fora_do_radio_nao_sobe_ponte_nenhuma() -> None:
    ger, recado = ligar_ponte_bt(
        MAC,
        diagnosticar=lambda: _Diag(),
        nos=lambda: [_No(OUTRO_MAC)],
        gerenciador=_Gerenciador,
    )

    assert ger is None
    assert "não está no rádio" in recado


def test_impedimento_da_maquina_vira_recado_e_nao_ponte_muda() -> None:
    """Sem libopus a ponte não sobe — e o interruptor tem de DIZER isso.

    Voltar sozinho sem explicação é o defeito que a MIC-BT-01 nomeia: "sumiu" é
    indistinguível de "não existe".
    """
    ger, recado = ligar_ponte_bt(
        MAC,
        diagnosticar=lambda: _Diag(["libopus ausente — instale libopus0"]),
        nos=lambda: [_No(MAC)],
        gerenciador=_Gerenciador,
    )

    assert ger is None
    assert "libopus" in recado


def test_ponte_que_nao_sobe_nao_deixa_gerenciador_orfao() -> None:
    """Ponte que não subiu tem de soltar o gerenciador — ele segura hidraw."""
    ger, recado = ligar_ponte_bt(
        MAC,
        diagnosticar=lambda: _Diag(),
        nos=lambda: [_No(MAC)],
        gerenciador=lambda: _Gerenciador(sobe=False),
    )

    assert ger is None
    assert "não subiu" in recado
    assert _Gerenciador.ultimo is not None
    assert _Gerenciador.ultimo.parou == 1, (
        "o gerenciador ficou de pé depois de falhar: ele segura o hidraw e a "
        "próxima tentativa disputaria o contador de sequência com ele"
    )


def test_desligar_e_idempotente_e_nunca_levanta() -> None:
    ger = _Gerenciador()
    ger.reconciliar([_No(MAC)])

    desligar_ponte_bt(ger)
    desligar_ponte_bt(ger)
    desligar_ponte_bt(None)

    assert ger.parou == 2
    assert ger.pontes == {}


class _GerenciadorQueExplode(_Gerenciador):
    def parar(self) -> None:
        raise RuntimeError("PipeWire sumiu no meio")


def test_falha_ao_desligar_nao_derruba_a_janela() -> None:
    """Fechar a janela não pode virar traceback por causa do servidor de som."""
    desligar_ponte_bt(_GerenciadorQueExplode())


# ---------------------------------------------------------------------------
# O texto — o que ele promete, e o que ele NÃO promete
# ---------------------------------------------------------------------------


def test_a_dica_diz_que_o_padrao_nao_muda() -> None:
    """Continuar opt-in é o estado de hoje, e a tela não pode sugerir outro.

    Sair do opt-in depende de uma medição com os quatro controles no rádio que
    ela ainda não fez — a ponte disputa o contador de sequência do report
    `0x32` com o driver. Um texto que dissesse "agora o mic funciona sempre"
    prometeria o que ninguém mediu.
    """
    assert "opt-in" in DICA_MIC_BT_LIGAR
    assert "não muda o padrão" in DICA_MIC_BT_LIGAR
    assert "quatro controles no rádio" in DICA_MIC_BT_LIGAR


def test_a_dica_poe_o_preco_a_vista() -> None:
    """Custo à vista é entrega da MIC-BT-01: ~260/s caem para ~170/s."""
    assert "~260/s" in DICA_MIC_BT_LIGAR and "~170/s" in DICA_MIC_BT_LIGAR
    assert "55-75%" in DICA_MIC_BT_LIGAR


def test_o_rotulo_cabe_no_espaco_do_card() -> None:
    """O rótulo é curto porque a coluna do som é o pixel mais disputado da aba."""
    assert len(TEXTO_MIC_BT_ROTULO) <= 12


@pytest.mark.parametrize(
    "texto", [DICA_MIC_BT_LIGAR, DICA_MIC_BT_DESLIGAR, DICA_MIC_BT_NO_CABO]
)
def test_nenhuma_dica_fala_de_variavel_de_ambiente(texto: str) -> None:
    """Ela não abre terminal para ligar microfone — é o que esta entrega cura."""
    assert "HEFESTO_DUALSENSE4UNIX_BT_MIC" not in texto
    assert "export " not in texto
