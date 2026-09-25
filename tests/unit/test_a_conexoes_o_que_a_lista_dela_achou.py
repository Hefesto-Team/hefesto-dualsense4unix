"""A seção Rádio e Adaptadores faz o que diz — A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01.

Ela testou a aba 08 com os quatro controles pelo rádio, em 25/09/2026, seguindo
a lista «Conexões hoje»: sete passos deram certo e doze não. A régua dela, da
mesma noite, é a desta régua inteira:

    *«nossas soluções tem que serem pensadas em produto, não só solução pro
    player 1 e tal. ou no modo X, ou conexão z. Isso é basilar pra gente.»*
    <!-- noqa-acento: citação literal dela -->

Então cada item roda na MATRIZ: de 1 a 4 controles em qualquer posição, de 1 a
3 adaptadores, o controle e o teclado. O rádio é o ``radio_de_mentira`` com a
física que a lista dela mediu (ligado, o PS + Create não faz nada; o controle
volta sozinho ao pareamento antigo quando a chave existe lá), e o dono do BlueZ
por cima é o ``DonoVivo`` de verdade.

O QUE ESTA RÉGUA COBRA, item por item da sprint:

1. o Mover desliga o controle e esquece a origem ANTES de pedir o gesto, e o
   controle não volta para lá — nem com o PS, nem sozinho;
2. o Mover diz o gesto de CADA tipo — o teclado não pede PS + Create;
3. o «Equilibrar» e a lâmpada nascem com os controles amontoados num adaptador;
4. a lotação: ``N/2`` conta pontes (R10), e três controles sem som dão ``0/2``;
5. todo tipo que o produto conhece tem desenho, e o desconhecido, o genérico;
7. o «Conectar» mostra chegando o controle que volta pelo pareamento antigo;
8. o nome é do controle (endereço) e o número é do daemon — e o formato da
   aba Conexões é ``Nome ● Modelo do plástico ● Pn``.

Faixa sintética da casa: ``aa:bb:cc``, octetos 4 e 5 zerados.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO

#: Os quatro da mesa, na ordem em que chegam.
QUATRO = (VERMELHO, AZUL, VERDE, ROXO)
TECLADO = "aa:bb:cc:00:00:7e"


@pytest.fixture()
def diario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A trava e o diário numa pasta de teste — nunca os dela, em ``/run``."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    caminho = tmp_path / "radio-diario.jsonl"
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(caminho))
    return caminho


@pytest.fixture()
def relogio() -> rm.Relogio:
    return rm.Relogio()


def _mundo(controles: int, adaptadores: int = 3) -> rm.RadioDeMentira:
    """``controles`` DualSense ligados na sala, com ``adaptadores`` na mesa."""
    radio = rm.RadioDeMentira(adaptadores=(SALA, QUARTO, VARANDA)[:adaptadores])
    for aparelho in QUATRO[:controles]:
        radio.pareado(SALA, aparelho)
    return radio


def _dono(mundo: rm.RadioDeMentira) -> bd.DonoVivo:
    vivo = bd.DonoVivo(mundo)
    assert vivo.ligar()
    return vivo


def _central(dono: bd.LeitorDoBluez, mundo: rm.RadioDeMentira, relogio: rm.Relogio,
             **extra: Any) -> cr.CentralDoRadio:
    return cr.CentralDoRadio(
        dono=dono,
        onde_esta=mundo.onde_esta,
        movimento=mundo.hz,
        esquecer_na_ponte=mundo.esquecer_na_ponte,
        relogio=relogio,
        dormir=relogio.dormir,
        sysfs={"listar": lambda _p: [], "raiz": "/nao/existe"},
        **extra,
    )


@pytest.fixture()
def mesa(diario: Path, relogio: rm.Relogio) -> Iterator[Any]:
    """Uma fábrica de mesas: ``mesa(controles, adaptadores)`` → (mundo, dono, central)."""
    abertos: list[bd.DonoVivo] = []

    def montar(controles: int, adaptadores: int = 3) -> tuple[Any, ...]:
        mundo = _mundo(controles, adaptadores)
        dono = _dono(mundo)
        abertos.append(dono)
        return mundo, dono, _central(dono, mundo, relogio)

    yield montar
    for dono in abertos:
        dono.fechar()


# ---------------------------------------------------------------------------
# 1. o Mover desliga, esquece a origem, e o controle não volta para lá
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("controles", [1, 2, 3, 4])
@pytest.mark.parametrize("adaptadores", [2, 3])
def test_o_mover_move_qualquer_um_dos_quatro_em_qualquer_mesa(
    mesa: Any, relogio: rm.Relogio, controles: int, adaptadores: int
) -> None:
    """De 1 a 4 controles, cada um deles, com 2 e 3 adaptadores: ele chega, os
    outros ficam ligados onde estavam, e sai UMA lápide — a dele na sala.

    MORDIDA: tire o ``Disconnect`` do :meth:`_desligar_e_esquecer_a_origem` — o
    PS + Create dela cai com o controle ligado (passo c1), e nenhum chega.
    """
    for posicao in range(controles):
        mundo, _dono, central = mesa(controles, adaptadores)
        quem = QUATRO[posicao]
        relogio.agendar(2.0, lambda m=mundo, q=quem: m.segurar_ps_create(q))

        feito = central.mover(quem, QUARTO)

        assert (feito.estado, feito.destino) == (cr.CHEGOU, QUARTO), (controles, posicao)
        assert mundo.onde_esta(rm.uniq(quem)) == QUARTO
        assert mundo.gestos_perdidos == []
        assert mundo.lapides == [(SALA, quem)]
        for outro in QUATRO[:controles]:
            if outro != quem:
                assert mundo.onde_esta(rm.uniq(outro)) == SALA, "desligou quem não ia"


def test_ligado_o_gesto_dela_nao_faz_nada_e_por_isso_o_produto_desliga_antes(
    mesa: Any, relogio: rm.Relogio
) -> None:
    """O passo c1, medido: com o controle ligado, o PS + Create se perde.

    É a física do rádio de mentira — e é por ela que o mover desliga primeiro.
    """
    mundo, _dono, _ = mesa(1)
    mundo.segurar_ps_create(VERMELHO)
    assert mundo.gestos_perdidos == [VERMELHO]
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA

    mundo.desligar(VERMELHO)
    mundo.segurar_ps_create(VERMELHO)
    assert mundo.fisicos[VERMELHO].pareando is True


def test_o_controle_nao_volta_sozinho_para_a_origem(mesa: Any, relogio: rm.Relogio) -> None:
    """O passo c2: *«muda de adaptador, fica um tempo, e volta para o anterior»*.
    <!-- noqa-acento: citação literal dela -->

    O controle chega no quarto e, na primeira vez que o kernel o vê lá, tenta
    voltar sozinho ao pareamento antigo — é o «fica um tempo, e volta». Com a
    sala já esquecida, não há chave lá, e ele fica no quarto.

    MORDIDA: faça o :meth:`_desligar_e_esquecer_a_origem` só desligar, sem
    esquecer — o controle volta para a sala no meio da conferência, o movimento
    não chega, e esta régua reprova.
    """
    mundo, dono, _ = mesa(2)
    voltou: list[str] = []

    def onde_esta(u: str) -> str:
        """O ``HID_PHYS`` — e o controle que, mal chega, tenta voltar sozinho."""
        if not voltou and mundo.fisicos[VERMELHO].conectado_em == QUARTO:
            voltou.append(mundo.voltar_sozinho(VERMELHO) or "ficou")
        return mundo.onde_esta(u)

    central = _central(dono, mundo, relogio)
    central._onde_esta = onde_esta
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert voltou == ["ficou"], "ele tentou voltar e achou a chave na sala"

    assert feito.estado == cr.CHEGOU
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    assert mundo.voltar_sozinho(VERMELHO) == "", "a sala ainda tinha a chave dele"
    assert mundo.objeto(SALA, VERMELHO) is None


def test_um_adaptador_so_nao_tem_para_onde_mover(mesa: Any, relogio: rm.Relogio) -> None:
    """Com um adaptador só, mover para ele mesmo é «já estava», e nada se escreve."""
    mundo, _dono, central = mesa(4, adaptadores=1)

    feito = central.mover(AZUL, SALA)

    assert (feito.estado, feito.motivo) == (cr.CHEGOU, cr.MOTIVO_JA_ESTAVA)
    assert mundo.chamadas == [] and mundo.lapides == []
    assert central.mover(AZUL).motivo == cr.MOTIVO_SEM_DESTINO


# ---------------------------------------------------------------------------
# 2. o teclado se move como teclado
# ---------------------------------------------------------------------------


def test_o_teclado_se_move_sem_desenho_de_dualsense(mesa: Any, relogio: rm.Relogio) -> None:
    """O passo c3: mover um TECLADO. Ele também desliga e sai da sala antes, e
    o movimento publica a classe dele — é por ela que a tela sabe que não é um
    DualSense, e não pede PS + Create (o resto do item 2 é da tela, abaixo)."""
    mundo, dono, central = mesa(1)
    mundo.pareado(SALA, TECLADO, classe=rm.CLASSE_DE_TECLADO)
    dono._fotografar()
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(TECLADO))

    feito = central.mover(TECLADO, QUARTO)

    assert (feito.estado, feito.e_controle) == (cr.CHEGOU, False)
    assert feito.publicar()["classe"] == rm.CLASSE_DE_TECLADO
    assert feito.publicar()["modalias"] == ""
    assert mundo.objeto(QUARTO, TECLADO)["Connected"] is True
    assert mundo.lapides == [(SALA, TECLADO)]
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA


# ---------------------------------------------------------------------------
# 7. o «Conectar» mostra quem volta pelo pareamento antigo
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("controles", [1, 2, 3, 4])
def test_o_conectar_mostra_chegando_quem_volta_pelo_pareamento_antigo(
    mesa: Any, relogio: rm.Relogio, controles: int
) -> None:
    """A foto 2 da lista dela: o «Conectar» procurando na Direita, e ela liga o
    controle só com o PS (ou o PS com outro botão) — ele volta para o adaptador
    que tinha a chave dele, sem passar pela janela.

    O último da mesa está desligado; os outros continuam ligados e NÃO são o
    dela. O «Conectar» acaba «chegou» onde ele chegou, sem apagar nada.

    MORDIDA: tire a pergunta ``_quem_voltou_sozinho`` do
    :meth:`_esperar_um_controle_novo` — o «Conectar» fica procurando até a
    janela fechar e acaba «não chegou» com o controle já ligado.
    """
    mundo, _dono, central = mesa(controles)
    dela = QUATRO[controles - 1]
    mundo.desligar(dela)
    relogio.agendar(2.0, lambda: mundo.apertar_ps(dela))

    feito = central.conectar(QUARTO)

    assert (feito.estado, feito.motivo) == (cr.CHEGOU, cr.MOTIVO_PELO_PAREAMENTO_ANTIGO)
    assert (feito.aparelho, feito.destino) == (dela, SALA)
    assert mundo.lapides == []
    assert mundo.propriedade_do_adaptador(QUARTO, "Discovering") is False
    assert mundo.propriedade_do_adaptador(QUARTO, "Pairable") is False
    assert [m.aparelho for m in central.movimentos()] == [dela]


def test_o_conectar_ainda_pareia_quem_segura_ps_create(mesa: Any, relogio: rm.Relogio) -> None:
    """O caminho de sempre continua: um controle novo, em modo de parear, chega
    pela janela — e o que já estava ligado não é confundido com ele."""
    mundo, _dono, central = mesa(3)
    mundo.fisicos[ROXO] = rm.Fisico(ROXO, rm.CLASSE_DE_CONTROLE)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(ROXO))

    feito = central.conectar(QUARTO)

    assert (feito.estado, feito.motivo, feito.aparelho) == (cr.CHEGOU, "", ROXO)
    assert mundo.onde_esta(rm.uniq(ROXO)) == QUARTO


# ---------------------------------------------------------------------------
# 8. o nome é do controle: ele vai junto no mover
# ---------------------------------------------------------------------------


def test_o_nome_que_ela_deu_vai_junto_no_mover(diario: Path, relogio: rm.Relogio) -> None:
    """O passo a2: *«O nome renomeado não aparece»*. O BlueZ guarda o ``Alias``
    POR OBJETO — um por adaptador —, e o mover criava um objeto novo com o nome
    de fábrica. O nome dela vai junto. <!-- noqa-acento: citação literal dela -->

    MORDIDA: tire o ``_dar_o_nome`` do :meth:`_parear_e_conferir` — o quarto
    fica com «DualSense Wireless Controller» e esta régua reprova.
    """
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="Vitória")
    mundo.pareado(SALA, AZUL)
    dono = _dono(mundo)
    central = _central(dono, mundo, relogio)
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert feito.estado == cr.CHEGOU
    assert mundo.objeto(QUARTO, VERMELHO)["Alias"] == "Vitória"
    assert feito.publicar()["nome"] == "Vitória"
    # O nome de fábrica não é nome dela: nada se escreve por ele.
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(AZUL))
    azul = central.mover(AZUL, VARANDA)
    assert azul.nome == ""
    assert not [e for e in mundo.escritas if e[2] == "Alias"
                and e[0] == rm.no_de(VARANDA, AZUL)]
    dono.fechar()


# ---------------------------------------------------------------------------
# 3. o «Equilibrar» nasce com os controles amontoados
# ---------------------------------------------------------------------------


def _no_ar(u: str, adaptador: str, ponte: str | None = None) -> dict[str, Any]:
    """Um controle do ``state["controllers"]`` como o daemon o publica."""
    return {"uniq": rm.uniq(u), "transport": "bt", "connected": True,
            "adaptador": adaptador, "ponte_do_radio": ponte}


def _plano(controles: list[dict[str, Any]], adaptadores: tuple[str, ...]) -> Any:
    from hefesto_dualsense4unix.integrations import plano_de_radio

    planos = plano_de_radio.plano_por_adaptador(
        controles, adaptadores=adaptadores, listar=lambda _p: [], raiz="/nao/existe")
    return plano_de_radio.ordem_de_redistribuicao(planos)


def test_quatro_num_adaptador_so_pedem_equilibrar_ate_dois_um_um() -> None:
    """Os passos b4 e b5 dela: os quatro num adaptador, dois vazios ao lado, e
    o «Equilibrar» mudo. Agora ele propõe UM por vez: 4/0/0 → 3/1/0 → 2/1/1, e
    para aí. Quem sai é o último a chegar.

    MORDIDA: devolva o ``return None`` no lugar do ``_ordem_que_equilibra`` em
    ``ordem_de_redistribuicao`` — a primeira ordem não nasce e esta régua
    reprova.
    """
    tres = (SALA, QUARTO, VARANDA)
    mesa = [_no_ar(u, SALA) for u in QUATRO]
    primeira = _plano(mesa, tres)
    assert primeira is not None
    assert (primeira.origem, primeira.destino, primeira.controle) == (
        SALA, QUARTO, rm.uniq(ROXO))
    assert primeira.modo == ""
    assert (primeira.pontes_na_origem_depois, primeira.pontes_no_destino_depois) == (0, 0)

    mesa = [_no_ar(u, SALA) for u in QUATRO[:3]] + [_no_ar(ROXO, QUARTO)]
    segunda = _plano(mesa, tres)
    assert segunda is not None
    assert (segunda.origem, segunda.destino, segunda.controle) == (
        SALA, VARANDA, rm.uniq(VERDE))

    mesa = [_no_ar(VERMELHO, SALA), _no_ar(AZUL, SALA), _no_ar(ROXO, QUARTO),
            _no_ar(VERDE, VARANDA)]
    assert _plano(mesa, tres) is None, "2/1/1 é o equilíbrio de quatro em três"


@pytest.mark.parametrize(("na_sala", "no_quarto", "propoe"), [
    (1, 0, False), (2, 0, True), (2, 1, False), (3, 0, True), (3, 1, True),
    (4, 0, True), (2, 2, False),
])
def test_dois_adaptadores_equilibram_pela_diferenca(
    na_sala: int, no_quarto: int, propoe: bool
) -> None:
    """De 1 a 4 controles em dois adaptadores: propõe quando a diferença é de
    dois ou mais, e nunca para trocar quem está apertado."""
    mesa = ([_no_ar(u, SALA) for u in QUATRO[:na_sala]]
            + [_no_ar(u, QUARTO) for u in QUATRO[na_sala:na_sala + no_quarto]])
    ordem = _plano(mesa, (SALA, QUARTO))
    assert (ordem is not None) is propoe, (na_sala, no_quarto)


def test_um_adaptador_so_nao_propoe_nada() -> None:
    assert _plano([_no_ar(u, SALA) for u in QUATRO], (SALA,)) is None


def test_quem_sai_para_equilibrar_e_o_ultimo_sem_som() -> None:
    """O som de quem já tem fica onde está: sai o último que chegou SEM ponte,
    mesmo que um com ponte tenha chegado depois dele."""
    mesa = [_no_ar(VERMELHO, SALA), _no_ar(AZUL, SALA), _no_ar(VERDE, SALA),
            _no_ar(ROXO, SALA, "som")]
    ordem = _plano(mesa, (SALA, QUARTO))
    assert ordem is not None and ordem.controle == rm.uniq(VERDE)


def test_as_pontes_alem_do_limite_continuam_na_frente() -> None:
    """Três pontes num adaptador que comporta duas: a ordem é a das pontes, e
    ela move quem leva o som — equilibrar número vem depois."""
    mesa = [_no_ar(VERMELHO, SALA, "som"), _no_ar(AZUL, SALA, "som"),
            _no_ar(VERDE, SALA, "haptica"), _no_ar(ROXO, SALA)]
    ordem = _plano(mesa, (SALA, QUARTO, VARANDA))
    assert ordem is not None
    assert (ordem.controle, ordem.modo) == (rm.uniq(VERDE), "haptica")
    assert ordem.pontes_na_origem_depois == 2


def test_a_central_publica_a_proposta_de_equilibrar(mesa: Any, relogio: rm.Relogio) -> None:
    """A proposta chega ao ``state_full["radio_central"]`` — é ela que acende a
    lâmpada e dá o que perguntar ao «Equilibrar» (o resto é da tela, abaixo)."""
    _mundo_, _dono_, central = mesa(4)
    publicado = central.publicar([_no_ar(u, SALA) for u in QUATRO])
    assert publicado["proposta"] is not None
    assert publicado["proposta"]["controle"] == rm.uniq(ROXO)
    assert publicado["proposta"]["destino"] == QUARTO
