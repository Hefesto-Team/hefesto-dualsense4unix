"""A conta de fatias POR ADAPTADOR, com nome de jogador — e o que ela recusa dizer.

DESEMPENHO-A-CONTA-DE-SLOTS-01, 25/08/2026. O produto mediu quanto do rádio cada
controle gasta, sabe qual controle está em qual adaptador, e a tela não gastava
esse número em nada. Este arquivo prende as cinco coisas que a conta tem de
fazer e as quatro que ela não pode fazer.

AS MORDIDAS, arrancadas e conferidas em 25/08/2026
---------------------------------------------------

1. **Arrancar o agrupamento por endereço** (uma chave por `uniq` em vez de uma
   por `HID_PHYS`): reprova
   `test_dois_controles_no_mesmo_adaptador_viram_um_plano_com_dois_jogadores` —
   a tela mostraria duas barras de 260 onde há uma de 521, e a mesa cheia
   pareceria folgada em dois lugares ao mesmo tempo.
2. **Alimentar `agora` com a DECLARAÇÃO** (em vez de `bt_mic.uniqs`): reprova
   `test_a_ponte_pedida_e_a_ponte_de_pe_sao_duas_contas` com
   `agora.slots_audio == 106.2` — o produto respondendo pelo pedido em vez de
   pelo efeito, que é o padrão que a queixa do Sackboy revelou.
3. **Trocar `palavra_da_ocupacao` por um corte próprio** em `cabe_mais_um`:
   reprova `test_cabe_mais_um_usa_o_corte_do_medidor_e_nao_um_proprio` — duas
   réguas sobre o mesmo número, que divergem na primeira mudança de corte.
4. **Arrancar a guarda do adaptador único** em `ordem_de_redistribuicao`:
   reprova `test_a_ordem_so_nasce_quando_ha_para_onde_mover` com uma ordem cujo
   destino é a própria origem — a tela mandando a pessoa mover um controle para
   onde ele já está.
5. **Arrancar o `_daemon_respondeu`** do bloco da seção: reprova
   `test_sem_resposta_do_daemon_a_palavra_nao_e_folgada`, que é a cura da B1
   medida em 23/08 — com o Hefesto parado as barras diziam "Folgada", em verde,
   `0/1600`, byte a byte a tela de um rádio vazio.
6. **Digitar "1042" na frase de capacidade**: reprova
   `test_a_frase_de_capacidade_e_derivada_do_medidor`, que remexe a constante e
   exige que a frase acompanhe.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

# GUARDA-GI-REAL-01: metade deste arquivo monta widgets de verdade, e "pulei
# porque não tenho GTK" é reprovação no job `gtk-real`.
exigir_gi_real("a conta de fatias da seção Desempenho")

from typing import Any

import pytest

_gi = pytest.importorskip("gi", reason="precisa de PyGObject")
_gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from hefesto_dualsense4unix.app.actions.config import secao_orcamento
from hefesto_dualsense4unix.integrations import plano_de_radio
from hefesto_dualsense4unix.integrations.radio_da_mesa import (
    HZ_AUDIO_COM_MIC,
    HZ_INPUT_COM_MIC,
    HZ_INPUT_SEM_MIC,
    PALAVRA_APERTADA,
    PALAVRA_CHEIA,
    PALAVRA_FOLGADA,
    PALAVRAS_DE_CULPA,
    SLOTS_POR_SEGUNDO,
    Ocupacao,
)

#: Endereços da FAIXA DA CASA (`e8:47:3a`, `aa:bb:cc`), com os octetos 4 e 5
#: zerados. Nada de MAC real em arquivo versionado — há dois portões, e um
#: deles pega por FORMA.
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
    """Um `/sys/class/hidraw` de mentira: `{uniq do controle: MAC do adaptador}`.

    Devolve o par `listar`/`ler` no formato que `plano_por_adaptador` aceita.
    Sem isto o teste mediria a bancada de quem o roda — o defeito "medir contra
    a biblioteca errada" pela porta do sysfs.
    """
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


# ---------------------------------------------------------------------------
# 1. O agrupamento — uma barra por adaptador, não uma por controle
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 2. Duas contas, não uma: o que ela pediu e o que está de pé
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# 3. "Cabe mais um?" — a pergunta do planejamento
# ---------------------------------------------------------------------------


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
    """MORDIDA 3. A fronteira do "cabe" é o corte da "Cheia" do `radio_da_mesa`.

    Varre a vizinhança do corte: em toda ocupação testada, "cabe" e "a palavra
    depois não é Cheia" têm de dar a MESMA resposta. Um corte próprio dentro do
    `plano_de_radio` divergiria aqui na primeira mudança de `CORTE_APERTADA`.
    """
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


# ---------------------------------------------------------------------------
# 4. A ordem de redistribuição — e o caso em que ela cala
# ---------------------------------------------------------------------------


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
    """Cinco com microfone no "Hub 9" (1384/1600, Cheia) e um sozinho no "Hub 15".

    É o cenário exato em que a ordem de serviço tem de nascer: a origem passou
    do corte da "Apertada" e existe outro adaptador que continua fora da
    "Cheia" depois de receber.
    """
    return plano_de_radio.plano_por_adaptador(
        [
            _controle(P1, 1),
            _controle(P2, 2),
            _controle(P3, 3),
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
    """Cinco num hub só: 1384/1600, "Cheia" — e nenhuma ordem, porque não há destino.

    **NÃO É MORDIDA, e a distinção é medida.** Arrancar a guarda
    `p.endereco != origem.endereco` (que impediria a origem de ser destino de si
    mesma) deixa este nó VERDE, conferido em 25/08/2026: com os cortes de hoje a
    origem nunca pode ser seu próprio destino, porque para entrar na lista ela já
    passou de `CORTE_APERTADA` (1360 fatias) e receber mais um controle a leva
    para além da "Cheia" em qualquer combinação. Aquela guarda é cinto, não
    tirante. Quem morde de verdade está no nó seguinte.

    O que ESTE nó prende é o resultado que a tela precisa: com um adaptador só,
    a resposta é a frase do adaptador único, e não uma ordem.
    """
    planos = _mesa_de_cinco_num_hub_so()
    assert round(planos[HUB_A].agora.slots_total) == 1384
    assert planos[HUB_A].agora.rotulo == PALAVRA_CHEIA
    assert plano_de_radio.ordem_de_redistribuicao(planos) is None


def test_o_balde_do_nao_sei_nunca_e_destino_de_ordem() -> None:
    """MORDIDA 4. Mandar mover para um adaptador que o produto não sabe nomear.

    O balde `SEM_ADAPTADOR` junta todo controle no rádio cujo `HID_PHYS` não é
    MAC legível — ele NÃO é um adaptador, é a ausência de resposta. Arrancar o
    filtro `endereco != SEM_ADAPTADOR` de `ordem_de_redistribuicao` faz a ordem
    nascer apontando para ele, e a tela manda a pessoa mover um controle para
    *"Adaptador que não sei qual é"* — trabalho impossível dado como conserto.
    """
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
    """O "Ganho esperado" nomeia as duas ocupações depois — sem adjetivo."""
    planos = _cinco_apertados_mais_um_folgado()
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is not None
    assert str(round(ordem.origem_depois.slots_total)) in ordem.ganho_esperado
    assert str(round(ordem.destino_depois.slots_total)) in ordem.ganho_esperado
    assert ordem.origem_depois.controles == 4
    assert ordem.destino_depois.controles == 2
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


# ---------------------------------------------------------------------------
# 5. O selo, e a confissão do que nunca foi medido
# ---------------------------------------------------------------------------


def test_o_selo_nomeia_as_tres_procedencias() -> None:
    """Especificação, medido e derivado — e sumir com uma reprova nomeando."""
    plano = plano_de_radio.PlanoDoAdaptador(
        endereco=HUB_A, agora=Ocupacao(slots_input=HZ_INPUT_SEM_MIC * 2, controles=2)
    )
    selo = " ".join(plano_de_radio.selo_das_procedencias(plano)).lower()
    for palavra in ("especificação", "medido", "derivado"):
        assert palavra in selo, f"o selo parou de dizer `{palavra}`"


def test_com_tres_controles_o_selo_confessa_a_extrapolacao() -> None:
    """O maior ensaio desta casa foi de DOIS; do terceiro em diante, confessa.

    Arrancar o corte faz a frase aparecer no plano de um controle, onde a conta
    É a medição — e aí a confissão vira ruído em vez de informação.
    """
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


# ---------------------------------------------------------------------------
# 6. Nenhuma palavra de culpa em nada que este módulo produz
# ---------------------------------------------------------------------------


def test_o_plano_nao_carrega_palavra_de_culpa() -> None:
    """Ocupação não é qualidade, e a desigualdade do rádio continua ABERTA.

    A varredura é sobre TUDO que o módulo produz para tela, e não sobre o que
    alguém lembrou de olhar: a lista de textos é montada a partir dos planos, da
    ordem de serviço e das frases soltas.
    """
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
    """`hciN` é a VAGA, não o aparelho — e o índice inverte entre boots.

    Medido em 24/08/2026: o serial que a `D-HCI1-BLOQUEADO` chamava de `hci1` é
    o `hci0` de hoje. Um rótulo por índice mandaria a pessoa mexer no adaptador
    errado.
    """
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


# ---------------------------------------------------------------------------
# 7. O preço do microfone — o número que a decisão dela precisa ter na mesa
# ---------------------------------------------------------------------------


def test_a_frase_de_capacidade_e_derivada_do_medidor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MORDIDA 6. Digitar "1042" à mão sobrevive à remedição do A/B.

    Remexe `HZ_INPUT_SEM_MIC` e exige que a frase acompanhe. Um literal no
    código passaria neste ponto e a tela passaria a afirmar o que a bancada já
    negou.
    """
    assert "1042" in plano_de_radio.frase_da_capacidade_do_mic(4)
    assert "1107" in plano_de_radio.frase_da_capacidade_do_mic(4)
    monkeypatch.setattr(plano_de_radio, "HZ_INPUT_SEM_MIC", 100.0)
    assert "400" in plano_de_radio.frase_da_capacidade_do_mic(4)
    assert "1042" not in plano_de_radio.frase_da_capacidade_do_mic(4)


def test_a_frase_diz_o_achado_que_muda_a_decisao() -> None:
    """O microfone não é o vilão: quem enche o adaptador é a QUANTIDADE.

    É o achado de 2.3 da sprint, e a frase que existia não o dizia: ela dava o
    custo do microfone e parava ali. Quatro pontos entre 65,1 % e 69,2 %.
    """
    frase = plano_de_radio.frase_da_capacidade_do_mic(4)
    assert "4 pontos" in frase
    assert "quantidade de controles" in frase


def test_o_preco_por_controle_esta_na_tela_com_os_dois_numeros() -> None:
    """`D-O-MIC-LIGADO-VALE-NO-RADIO` precisa dos dois lados para ser decidida."""
    frase = plano_de_radio.frase_do_preco_por_controle()
    assert "260,4" in frase and "276,7" in frase
    assert str(SLOTS_POR_SEGUNDO) in frase


def test_o_padrao_do_microfone_e_lido_do_dono_e_nao_opinado(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A linha que fica PRONTA para receber a decisão dela — e é derivada.

    `microfone_nasce_ligado` lê o `default` de `ControleDeclarado.microfone`, o
    dono único do padrão. Hoje ele é `None`, e a frase diz "nasce desligado".
    Quando a `D-O-MIC-LIGADO-VALE-NO-RADIO` for decidida, quem muda é aquele
    campo — e esta frase acompanha sozinha, sem ninguém precisar lembrar.

    Arrancar a derivação (escrever "nasce desligado" como literal): este nó
    reprova, porque o padrão remexido não muda a frase.
    """
    from hefesto_dualsense4unix.utils.maquina import ControleDeclarado

    assert plano_de_radio.microfone_nasce_ligado() is False
    assert "nasce desligado" in plano_de_radio.frase_do_preco_por_controle()

    campo = ControleDeclarado.model_fields["microfone"]
    monkeypatch.setattr(campo, "default", True)
    assert plano_de_radio.microfone_nasce_ligado() is True
    assert "nasce ligado" in plano_de_radio.frase_do_preco_por_controle()


# ---------------------------------------------------------------------------
# 8. A conta na TELA — a seção montada
# ---------------------------------------------------------------------------


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
        #: PENDURADA no hospedeiro: solta numa local, a caixa é coletada ao fim
        #: do `montar` e o GTK destrói os filhos junto.
        self._caixa: Any = None

    def _get(self, _ident: str) -> Any:
        return None


class _Dongle:
    def __init__(self, endereco: str, nome: str) -> None:
        self.endereco = endereco
        self.nome = nome


def _montar(host: _Host) -> Any:
    host._caixa = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    secao_orcamento.montar(host, host._caixa)
    return host._config_conta_de_slots  # type: ignore[attr-defined]


def test_sem_resposta_do_daemon_a_palavra_nao_e_folgada() -> None:
    """MORDIDA 5. A cura da B1, medida em 23/08/2026.

    Com o Hefesto parado as três barras da outra seção diziam "Folgada", em
    verde, `0/1600` — byte a byte a tela de um rádio vazio. Zero pinta verde, e
    "0/1600" é afirmação numérica sobre o que não se leu.
    """
    conta = _montar(_Host(None))
    falas = " ".join(conta.falas())
    assert PALAVRA_FOLGADA not in falas
    assert f"0/{SLOTS_POR_SEGUNDO}" not in falas
    assert "não respondeu" in falas


def test_com_o_daemon_vivo_e_o_radio_vazio_a_tela_diz_isso_e_nao_nao_sei() -> None:
    """"Não sei" e "não há ninguém" são coisas diferentes, e a tela separa."""
    conta = _montar(_Host({"controllers": []}))
    falas = " ".join(conta.falas())
    assert secao_orcamento.NINGUEM_NO_RADIO in falas
    assert "não respondeu" not in falas


def test_a_secao_nomeia_o_adaptador_e_nunca_o_hci() -> None:
    """O nome é o DELA. Trocar pelo índice mandaria mexer no aparelho errado."""
    conta = _montar(
        _Host(
            {
                "controllers": [_controle(P1, 1), _controle(P2, 2)],
                "bt_mic": {"uniqs": [_sem_dois_pontos(P1)]},
            },
            sysfs=_bancada({P1: HUB_A, P2: HUB_A}),
            dongles=(_Dongle(HUB_A.upper(), "Hub 9"),),
        )
    )
    falas = conta.falas()
    assert any("Hub 9" in linha for linha in falas)
    assert not any("hci" in linha.lower() for linha in falas)
    assert any("Jogadores 1 e 2" in linha for linha in falas)


def test_a_secao_mostra_a_ordem_quando_ha_para_onde_mover() -> None:
    """A ordem chega à tela com as três linhas do formato `D-ORDEM-DE-SERVICO`."""
    conta = _montar(
        _Host(
            {
                "controllers": [
                    _controle(P1, 1),
                    _controle(P2, 2),
                    _controle(P3, 3),
                    _controle(P4, 4),
                    _controle(P5, 5),
                    _controle(P6, 6),
                ],
                "bt_mic": {
                    "uniqs": [_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)]
                },
            },
            sysfs=_bancada(
                {P1: HUB_A, P2: HUB_A, P3: HUB_A, P4: HUB_A, P5: HUB_A, P6: HUB_B}
            ),
            dongles=(_Dongle(HUB_A, "Hub 9"), _Dongle(HUB_B, "Hub 15")),
        )
    )
    falas = " ".join(conta.falas())
    assert "mudança recomendada" in falas
    assert "O que eu vi aqui:" in falas
    assert "Por que importa:" in falas
    assert "Ganho esperado:" in falas


def test_a_secao_cala_a_ordem_e_diz_a_frase_do_adaptador_unico() -> None:
    """Cinco num hub só: não há para onde mover, e a tela diz por quê."""
    conta = _montar(
        _Host(
            {
                "controllers": [
                    _controle(P1, 1),
                    _controle(P2, 2),
                    _controle(P3, 3),
                    _controle(P4, 4),
                    _controle(P5, 5),
                ],
                "bt_mic": {
                    "uniqs": [_sem_dois_pontos(p) for p in (P1, P2, P3, P4, P5)]
                },
            },
            sysfs=_bancada(dict.fromkeys((P1, P2, P3, P4, P5), HUB_A)),
        )
    )
    falas = " ".join(conta.falas())
    assert "mudança recomendada" not in falas
    assert plano_de_radio.FRASE_DO_ADAPTADOR_UNICO in falas


def test_o_preco_do_microfone_esta_na_tela_em_todos_os_estados() -> None:
    """O número que a decisão dela espera não some quando o daemon cala."""
    for estado in (None, {"controllers": []}):
        conta = _montar(_Host(estado))
        falas = " ".join(conta.falas())
        assert "260,4" in falas and "276,7" in falas
