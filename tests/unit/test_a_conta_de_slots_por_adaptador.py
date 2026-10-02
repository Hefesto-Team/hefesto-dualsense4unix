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
    PALAVRA_APERTADA,
    PALAVRA_CHEIA,
    PALAVRAS_DE_CULPA,
    SLOTS_POR_SEGUNDO,
    Ocupacao,
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
    fala = plano_de_radio.nomes_dos_jogadores(plano)
    assert plano_de_radio.SEM_NUMERO in fala
    assert "Jogador 1" not in fala


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
    linha = plano_de_radio.linha_do_declarado_que_nao_subiu(planos[HUB_A])
    assert linha is not None and "ainda não subiu" in linha


def test_quando_a_ponte_subiu_a_tela_nao_tem_nada_a_corrigir() -> None:
    """A régua sabe RECUSAR: coincidindo as duas contas, a linha não aparece."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1)],
        com_ponte_de_mic=[_sem_dois_pontos(P1)],
        mic_declarado=[_sem_dois_pontos(P1)],
        **_bancada({P1: HUB_A}),
    )
    plano = planos[HUB_A]
    assert plano_de_radio.linha_do_declarado_que_nao_subiu(plano) is None
    assert plano.agora.slots_total == pytest.approx(HZ_INPUT_COM_MIC + HZ_AUDIO_COM_MIC)


def test_cabe_mais_um_com_mic_no_adaptador_de_tres() -> None:
    """Três sem mic (781) mais um com mic dá 1058 e "Apertada" — e cabe."""
    tres = Ocupacao(slots_input=HZ_INPUT_SEM_MIC * 3, controles=3)
    cabe, depois = plano_de_radio.cabe_mais_um(tres, com_mic=True)
    assert cabe is True
    assert round(depois.slots_total) == 1058
    assert depois.rotulo == PALAVRA_APERTADA


def test_com_cinco_de_pe_nao_cabe_mais_um() -> None:
    """A régua sabe dizer NÃO — sem isso ela não é régua."""
    cinco = Ocupacao(
        slots_input=HZ_INPUT_COM_MIC * 5,
        slots_audio=HZ_AUDIO_COM_MIC * 5,
        controles=5,
        com_microfone=5,
    )
    assert cinco.rotulo == PALAVRA_CHEIA
    cabe, depois = plano_de_radio.cabe_mais_um(cinco, com_mic=True)
    assert cabe is False
    assert depois.rotulo == PALAVRA_CHEIA


def test_cabe_mais_um_usa_o_corte_do_medidor_e_nao_um_proprio() -> None:
    """MORDIDA 3. A fronteira do "cabe" é o corte da "Cheia" do `radio_da_mesa`."""
    for controles in range(0, 7):
        base = Ocupacao(
            slots_input=HZ_INPUT_SEM_MIC * controles, controles=controles
        )
        for com_mic in (False, True):
            cabe, depois = plano_de_radio.cabe_mais_um(base, com_mic=com_mic)
            assert cabe is (depois.rotulo != PALAVRA_CHEIA)


def test_a_linha_do_cabe_mais_um_diz_o_numero_e_nao_so_o_sim() -> None:
    """"Sim" sozinho não planeja nada: a linha nomeia como ficaria."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1), _controle(P2, 2), _controle(P3, 3)],
        apelidos={HUB_A: "Hub 9"},
        **_bancada({P1: HUB_A, P2: HUB_A, P3: HUB_A}),
    )
    linha = plano_de_radio.linha_do_cabe_mais_um(planos[HUB_A])
    assert "Hub 9" in linha
    assert "sim" in linha
    assert "1058" in linha and str(SLOTS_POR_SEGUNDO) in linha


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


def test_o_selo_nomeia_as_tres_procedencias() -> None:
    """Especificação, medido e derivado — e sumir com uma reprova nomeando."""
    plano = plano_de_radio.PlanoDoAdaptador(
        endereco=HUB_A, agora=Ocupacao(slots_input=HZ_INPUT_SEM_MIC * 2, controles=2)
    )
    selo = " ".join(plano_de_radio.selo_das_procedencias(plano)).lower()
    for palavra in ("especificação", "medido", "derivado"):
        assert palavra in selo, f"o selo parou de dizer `{palavra}`"


def test_com_tres_controles_o_selo_confessa_a_extrapolacao() -> None:
    """O maior ensaio desta casa foi de DOIS; do terceiro em diante, confessa."""
    def _plano(controles: int) -> plano_de_radio.PlanoDoAdaptador:
        return plano_de_radio.PlanoDoAdaptador(
            endereco=HUB_A,
            agora=Ocupacao(
                slots_input=HZ_INPUT_SEM_MIC * controles, controles=controles
            ),
        )

    frase = plano_de_radio.frase_da_extrapolacao()
    assert frase not in plano_de_radio.selo_das_procedencias(_plano(1))
    assert frase not in plano_de_radio.selo_das_procedencias(_plano(2))
    assert frase in plano_de_radio.selo_das_procedencias(_plano(3))


def test_o_selo_nao_digita_nenhum_numero() -> None:
    """Os números do selo saem das constantes — remexê-las move o selo."""
    assert str(SLOTS_POR_SEGUNDO) in plano_de_radio.selo_da_especificacao()
    medido = plano_de_radio.selo_do_medido()
    assert "260,4" in medido and "276,7" in medido


def test_o_plano_nao_carrega_palavra_de_culpa() -> None:
    """Ocupação não é qualidade, e a desigualdade do rádio continua ABERTA."""
    planos = _cinco_apertados_mais_um_folgado()
    textos: list[str] = [
        plano_de_radio.FRASE_DO_ADAPTADOR_UNICO,
        plano_de_radio.POR_QUE_IMPORTA,
        plano_de_radio.frase_da_capacidade_do_mic(),
        plano_de_radio.frase_da_extrapolacao(),
        plano_de_radio.frase_do_preco_por_controle(),
    ]
    for plano in planos.values():
        textos.append(plano_de_radio.linha_do_plano(plano))
        textos.append(plano_de_radio.linha_do_cabe_mais_um(plano))
        textos.append(plano_de_radio.linha_do_cabe_mais_um(plano, com_mic=False))
        textos.append(plano_de_radio.nomes_dos_jogadores(plano))
        textos.extend(plano_de_radio.selo_das_procedencias(plano))
        pendente = plano_de_radio.linha_do_declarado_que_nao_subiu(plano)
        if pendente:
            textos.append(pendente)
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
    """`hciN` é a VAGA, não o aparelho — e o índice inverte entre boots."""
    planos = plano_de_radio.plano_por_adaptador(
        [_controle(P1, 1)], **_bancada({P1: HUB_A})
    )
    plano = planos[HUB_A]
    assert plano.nome_na_tela == plano_de_radio.ADAPTADOR_SEM_NOME
    for texto in (
        plano_de_radio.linha_do_plano(plano),
        plano_de_radio.linha_do_cabe_mais_um(plano),
    ):
        assert "hci" not in texto.lower()


def test_a_frase_de_capacidade_e_derivada_do_medidor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 6. Digitar "1042" à mão sobrevive à remedição do A/B."""
    assert "1042" in plano_de_radio.frase_da_capacidade_do_mic(4)
    assert "1107" in plano_de_radio.frase_da_capacidade_do_mic(4)
    monkeypatch.setattr(plano_de_radio, "HZ_INPUT_SEM_MIC", 100.0)
    assert "400" in plano_de_radio.frase_da_capacidade_do_mic(4)
    assert "1042" not in plano_de_radio.frase_da_capacidade_do_mic(4)


def test_a_frase_diz_o_achado_que_muda_a_decisao() -> None:
    """O microfone não é o vilão: quem enche o adaptador é a QUANTIDADE."""
    frase = plano_de_radio.frase_da_capacidade_do_mic(4)
    assert "4 pontos" in frase
    assert "quantidade de controles" in frase


def test_o_preco_por_controle_esta_na_tela_com_os_dois_numeros() -> None:
    """`D-O-MIC-LIGADO-VALE-NO-RADIO` precisa dos dois lados para ser decidida."""
    frase = plano_de_radio.frase_do_preco_por_controle()
    assert "260,4" in frase and "276,7" in frase
    assert str(SLOTS_POR_SEGUNDO) in frase


def test_a_tela_diz_o_padrao_de_hoje_e_ele_e_ligado() -> None:
    """A linha que a `D-O-MIC-LIGADO-VALE-NO-RADIO` exigia — e ela fechou."""
    assert plano_de_radio.microfone_nasce_ligado() is True
    frase = plano_de_radio.frase_do_preco_por_controle()
    assert "nasce ligado" in frase
    assert "nasce desligado" not in frase, (
        "a tela diz à pessoa que o microfone nasce desligado depois de ele "
        "ter subido sozinho na conexão"
    )
    assert "260,4" in frase and "276,7" in frase, (
        "o preço saiu da frase — a condição dela era o padrão COM o preço"
    )


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


