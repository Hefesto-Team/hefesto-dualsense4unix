"""A conta de fatias POR ADAPTADOR, com nome de jogador — e o que ela recusa dizer."""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("a conta de fatias da seção Desempenho")

from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")

from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    PALAVRA_CHEIA,
    PALAVRAS_DE_CULPA,
)

HUB_A = "e8:47:3a:00:00:09"
HUB_B = "e8:47:3a:00:00:15"
P1 = "aa:bb:cc:00:00:11"
P2 = "aa:bb:cc:00:00:22"
P3 = "aa:bb:cc:00:00:33"
P4 = "aa:bb:cc:00:00:44"
P5 = "aa:bb:cc:00:00:55"
P6 = "aa:bb:cc:00:00:66"


def _sem_dois_pontos(mac: str) -> str:
    """Como o `uniq` do estado do daemon chega: 12 hex, sem separador."""
    return mac.replace(":", "")


def _bancada(mapa: dict[str, str]) -> dict[str, Any]:
    """Um `/sys/class/hidraw` de mentira: `{uniq do controle: MAC do adaptador}`."""
    nos = {f"hidraw{i}": (uniq, phys) for i, (uniq, phys) in enumerate(mapa.items())}
    textos = {
        f"/sys/class/hidraw/{no}/device/uevent": f"HID_UNIQ={uniq}\nHID_PHYS={phys}\n"
        for no, (uniq, phys) in nos.items()
    }
    return {
        "listar": lambda _raiz: sorted(nos),
        "ler": lambda caminho: textos.get(caminho, ""),
    }


def _controle(uniq: str, slot: int | None = None, **extra: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "transport": "bt",
        "connected": True,
        "uniq": _sem_dois_pontos(uniq),
        "player_slot": slot,
    }
    base.update(extra)
    return base


def test_dois_controles_no_mesmo_adaptador_viram_um_plano_com_dois_jogadores() -> None:
    """MORDIDA 1. Um plano, dois jogadores, e a conta somada — não duas de 260."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1), _controle(P2, 2)],
        **_bancada({P1: HUB_A, P2: HUB_A}),
    )
    assert list(planos) == [HUB_A], (
        "o agrupamento é por ADAPTADOR: dois planos aqui seriam duas barras de "
        "260 onde há uma fila de 521"
    )
    plano = planos[HUB_A]
    assert plano.jogadores == (1, 2)
    assert plano.agora.controles == 2
    assert plano.agora.slots_total == pytest.approx(HZ_INPUT_SEM_MIC * 2)


def test_dois_adaptadores_nao_se_misturam() -> None:
    """Cada `HID_PHYS` é uma fila, e a conta de uma não empresta a da outra."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1), _controle(P2, 2), _controle(P3, 3)],
        **_bancada({P1: HUB_A, P2: HUB_A, P3: HUB_B}),
    )
    assert set(planos) == {HUB_A, HUB_B}
    assert planos[HUB_A].agora.controles == 2
    assert planos[HUB_B].agora.controles == 1


def test_o_controle_no_cabo_nao_ocupa_fatia_de_ninguem() -> None:
    """Controle negativo medido nesta bancada em 22/08: no fio não há rádio."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1, transport="usb"), _controle(P2, 2)],
        **_bancada({P2: HUB_A}),
    )
    assert planos[HUB_A].agora.controles == 1
    assert planos[HUB_A].jogadores == (2,)


def test_controle_sem_endereco_legivel_nao_empresta_o_adaptador_do_vizinho() -> None:
    """Sem `HID_PHYS` de MAC a resposta é "não sei", nunca o hub do vizinho."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1), _controle(P2, 2)],
        **_bancada({P1: HUB_A, P2: "usb-0000:0c:00.3-1/input3"}),
    )
    assert planos[HUB_A].jogadores == (1,)
    assert planos[""].jogadores == (2,)
    assert planos[""].nome_na_tela == plano_de_radio.ADAPTADOR_DESCONHECIDO


def test_o_jogador_sem_numero_nao_e_chutado_pela_posicao() -> None:
    """`índice + 1` já deu "Jogador 4" a DOIS cards da mesma mesa (22/08)."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, None), _controle(P2, 2)],
        **_bancada({P1: HUB_A, P2: HUB_A}),
    )
    plano = planos[HUB_A]
    assert plano.jogadores == (None, 2)


def test_a_ponte_pedida_e_a_ponte_de_pe_sao_duas_contas() -> None:
    """MORDIDA 2. Declarada e não subida: `planejada` cobra, `agora` não."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1)],
        com_ponte_de_mic=(),
        mic_declarado=[_sem_dois_pontos(P1)],
        **_bancada({P1: HUB_A}),
    )
    plano = planos[HUB_A]
    assert plano.planejada.slots_audio == pytest.approx(HZ_AUDIO_COM_MIC)
    assert plano.agora.slots_audio == 0.0, (
        "`agora` alimentada pela declaração é o produto respondendo pelo "
        "PEDIDO em vez de pelo EFEITO"
    )
    assert plano.agora.slots_total == pytest.approx(HZ_INPUT_SEM_MIC)


def test_o_declarado_que_nao_subiu_aparece_na_tela() -> None:
    """Ausência de notícia lida como sucesso é o padrão do Sackboy."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1)],
        mic_declarado=[_sem_dois_pontos(P1)],
        **_bancada({P1: HUB_A}),
    )
    assert planos[HUB_A].declarado_que_nao_subiu


def test_quando_a_ponte_subiu_a_tela_nao_tem_nada_a_corrigir() -> None:
    """A régua sabe RECUSAR: coincidindo as duas contas, a linha não aparece."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1)],
        com_ponte_de_mic=[_sem_dois_pontos(P1)],
        mic_declarado=[_sem_dois_pontos(P1)],
        **_bancada({P1: HUB_A}),
    )
    plano = planos[HUB_A]
    assert not plano.declarado_que_nao_subiu
    assert plano.agora.slots_total == pytest.approx(HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC)


def _mesa_de_cinco_num_hub_so() -> dict[str, plano_de_radio.PlanoDoAdaptador]:
    return plano_de_radio.plano_por_adaptador(
        [
            _controle(P1, 1),
            _controle(P2, 2),
            _controle(P3, 3),
            _controle(P4, 4),
            _controle(P5, 5),
        ],
        com_ponte_de_mic=[_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)],
        apelidos={HUB_A: "Hub 9"},
        **_bancada(dict.fromkeys((P1, P2, P3, P4, P5), HUB_A)),
    )


def _cinco_apertados_mais_um_folgado() -> dict[str, plano_de_radio.PlanoDoAdaptador]:
    """Cinco com microfone no "Hub 9" (três com ponte de som) e um no "Hub 15"."""
    return plano_de_radio.plano_por_adaptador(
        [
            _controle(P1, 1, ponte_do_radio="som"),
            _controle(P2, 2, ponte_do_radio="som"),
            _controle(P3, 3, ponte_do_radio="som"),
            _controle(P4, 4),
            _controle(P5, 5),
            _controle(P6, 6),
        ],
        com_ponte_de_mic=[_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)],
        apelidos={HUB_A: "Hub 9", HUB_B: "Hub 15"},
        **_bancada(
            {P1: HUB_A, P2: HUB_A, P3: HUB_A, P4: HUB_A, P5: HUB_A, P6: HUB_B}
        ),
    )


def test_a_ordem_so_nasce_quando_ha_para_onde_mover() -> None:
    """Cinco num hub só: 1384/1600, "Cheia" — e nenhuma ordem, porque não há destino."""
    planos = _mesa_de_cinco_num_hub_so()
    assert round(planos[HUB_A].agora.slots_total) == 1384
    assert planos[HUB_A].agora.rotulo == PALAVRA_CHEIA
    assert plano_de_radio.ordem_de_redistribuicao(planos) is None


def test_o_balde_do_nao_sei_nunca_e_destino_de_ordem() -> None:
    """MORDIDA 4. Mandar mover para um adaptador que o produto não sabe nomear."""
    planos = plano_de_radio.plano_por_adaptador(
        [
            _controle(P1, 1),
            _controle(P2, 2),
            _controle(P3, 3),
            _controle(P4, 4),
            _controle(P5, 5),
            _controle(P6, 6),
        ],
        com_ponte_de_mic=[_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)],
        apelidos={HUB_A: "Hub 9"},
        **_bancada(
            {
                P1: HUB_A,
                P2: HUB_A,
                P3: HUB_A,
                P4: HUB_A,
                P5: HUB_A,
                P6: "usb-0000:0c:00.3-1/input3",
            }
        ),
    )
    assert "" in planos, "o cenário precisa do balde do não-sei para morder"
    assert round(planos[HUB_A].agora.slots_total) == 1384
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is None, (
        "a ordem nasceu apontando para o balde do 'não sei de quem é' — a tela "
        f"mandaria mover um controle para {ordem.destino_na_tela!r}"
        if ordem is not None
        else ""
    )


def test_com_um_segundo_adaptador_a_ordem_nasce_e_aponta_para_ele() -> None:
    """Havendo folga em outro adaptador, a ordem diz de onde para onde."""
    planos = _cinco_apertados_mais_um_folgado()
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is not None
    assert ordem.origem == HUB_A and ordem.destino == HUB_B
    assert ordem.origem_na_tela == "Hub 9" and ordem.destino_na_tela == "Hub 15"


def test_a_ordem_calcula_o_ganho_e_nao_o_promete() -> None:
    """O "Ganho esperado" nomeia as PONTES dos dois lados depois — sem adjetivo."""
    planos = _cinco_apertados_mais_um_folgado()
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is not None
    assert ordem.pontes_na_origem_depois == 2
    assert ordem.pontes_no_destino_depois == 1
    assert f"com 2 de {ordem.n_max}" in ordem.ganho_esperado
    assert f"com 1 de {ordem.n_max}" in ordem.ganho_esperado
    assert ordem.controle == _sem_dois_pontos(P3), "sai o último a chegar com ponte"
    assert "fatia" not in ordem.ganho_esperado + ordem.o_que_eu_vi
    for palavra in ("melhor", "resolve", "conserta", "ideal"):
        assert palavra not in ordem.ganho_esperado.lower()


def test_a_mesa_folgada_nao_manda_mudar_nada() -> None:
    """A régua sabe RECUSAR: dois adaptadores folgados não geram ordem."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1), _controle(P2, 2)],
        apelidos={HUB_A: "Hub 9", HUB_B: "Hub 15"},
        **_bancada({P1: HUB_A, P2: HUB_B}),
    )
    assert plano_de_radio.ordem_de_redistribuicao(planos) is None


def test_o_plano_nao_carrega_palavra_de_culpa() -> None:
    """Ocupação não é qualidade, e a desigualdade do rádio continua ABERTA."""
    planos = _cinco_apertados_mais_um_folgado()
    textos: list[str] = [
        plano_de_radio.FRASE_DO_ADAPTADOR_UNICO,
        plano_de_radio.POR_QUE_IMPORTA,
    ]
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is not None
    textos.extend([ordem.o_que_eu_vi, ordem.por_que_importa, ordem.ganho_esperado])

    achados = [
        f"{palavra!r} em {texto!r}"
        for texto in textos
        for palavra in PALAVRAS_DE_CULPA
        if palavra in texto.lower()
    ]
    assert not achados, (
        "a conta passou a ligar ocupação a qualidade, e a bancada não "
        "sustenta essa causa:\n  " + "\n  ".join(achados)
    )


def test_a_tela_nunca_chama_o_adaptador_de_hci() -> None:
    """`hciN` é a VAGA, não o aparelho — e o índice inverte entre boots. (D-HCI1-BLOQUEADO)"""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1)], **_bancada({P1: HUB_A})
    )
    plano = planos[HUB_A]
    assert plano.nome_na_tela == plano_de_radio.ADAPTADOR_SEM_NOME
    assert "hci" not in plano.nome_na_tela.lower()


def test_o_microfone_nasce_ligado_e_o_dono_responde() -> None:
    """O dono do padrão (`profiles/schema.py`, `dono=`) diz ligado.
    (D-O-MIC-LIGADO-VALE-NO-RADIO)
    """
    assert plano_de_radio.microfone_nasce_ligado() is True


class _Host:
    """O mínimo que a seção toca no hospedeiro, mais os pontos de injeção."""

    def __init__(
        self,
        estado: dict[str, Any] | None,
        *,
        sysfs: dict[str, Any] | None = None,
        dongles: tuple[Any, ...] = (),
    ) -> None:
        self._maquina_pendente: dict[str, Any] | None = None
        self._orcamento_lido = lambda: None
        self._desempenho_leitor = lambda: estado
        self._desempenho_sysfs = sysfs or {}
        self._config_dongles = dongles
        self._caixa: Any = None

    def _get(self, _ident: str) -> Any:
        return None


class _Dongle:
    def __init__(self, endereco: str, nome: str) -> None:
        self.endereco = endereco
        self.nome = nome


HUB_C = "e8:47:3a:00:00:21"
P7 = "aa:bb:cc:00:00:77"
P8 = "aa:bb:cc:00:00:88"


