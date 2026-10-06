"""A seção Rádio e Adaptadores faz o que diz — A-CONEXOES-O-QUE-A-LISTA-DELA-ACHOU-01."""

from __future__ import annotations

import re
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import central_do_radio as cr
from hefesto_dualsense4unix.integrations import diario_do_radio
from tests.unit import radio_de_mentira as rm
from tests.unit.radio_de_mentira import AZUL, QUARTO, ROXO, SALA, VARANDA, VERDE, VERMELHO

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


@pytest.mark.parametrize("controles", [1, 2, 3, 4])
@pytest.mark.parametrize("adaptadores", [2, 3])
def test_o_mover_move_qualquer_um_dos_quatro_em_qualquer_mesa(
    mesa: Any, relogio: rm.Relogio, controles: int, adaptadores: int
) -> None:
    """De 1 a 4 controles, cada um deles, com 2 e 3 adaptadores: ele chega, os"""
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
    """O passo c1, medido: com o controle ligado, o PS + Create se perde."""
    mundo, _dono, _ = mesa(1)
    mundo.segurar_ps_create(VERMELHO)
    assert mundo.gestos_perdidos == [VERMELHO]
    assert mundo.onde_esta(rm.uniq(VERMELHO)) == SALA

    mundo.desligar(VERMELHO)
    mundo.segurar_ps_create(VERMELHO)
    assert mundo.fisicos[VERMELHO].pareando is True


def test_o_controle_nao_volta_sozinho_para_a_origem(mesa: Any, relogio: rm.Relogio) -> None:
    """O passo c2: *«muda de adaptador, fica um tempo, e volta para o anterior»*."""
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


@pytest.mark.parametrize("controles", [1, 2, 3, 4])
def test_o_conectar_mostra_chegando_quem_volta_pelo_pareamento_antigo(
    mesa: Any, relogio: rm.Relogio, controles: int
) -> None:
    """A foto 2 da lista dela: o «Conectar» procurando na Direita, e ela liga o"""
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
    """O caminho de sempre continua: um controle novo, em modo de parear, chega"""
    mundo, _dono, central = mesa(3)
    mundo.fisicos[ROXO] = rm.Fisico(ROXO, rm.CLASSE_DE_CONTROLE)
    rm.ela_pareia(relogio, mundo, central, ROXO)

    feito = central.conectar(QUARTO)

    assert (feito.estado, feito.motivo, feito.aparelho) == (cr.CHEGOU, "", ROXO)
    assert mundo.onde_esta(rm.uniq(ROXO)) == QUARTO


def test_o_nome_que_ela_deu_vai_junto_no_mover(diario: Path, relogio: rm.Relogio) -> None:
    """O passo a2: *«O nome renomeado não aparece»*. O BlueZ guarda o ``Alias``
    POR OBJETO — um por adaptador —, e o mover criava um objeto novo com o nome
    de fábrica. O nome dela vai junto. <!-- noqa-acento: citação literal -->

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
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(AZUL))
    azul = central.mover(AZUL, VARANDA)
    assert azul.nome == ""
    assert not [e for e in mundo.escritas if e[2] == "Alias"
                and e[0] == rm.no_de(VARANDA, AZUL)]
    dono.fechar()


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
    """Os passos b4 e b5 dela: os quatro num adaptador, dois vazios ao lado, e"""
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
    """De 1 a 4 controles em dois adaptadores: propõe quando a diferença é de"""
    mesa = ([_no_ar(u, SALA) for u in QUATRO[:na_sala]]
            + [_no_ar(u, QUARTO) for u in QUATRO[na_sala:na_sala + no_quarto]])
    ordem = _plano(mesa, (SALA, QUARTO))
    assert (ordem is not None) is propoe, (na_sala, no_quarto)


def test_um_adaptador_so_nao_propoe_nada() -> None:
    assert _plano([_no_ar(u, SALA) for u in QUATRO], (SALA,)) is None


def test_quem_sai_para_equilibrar_e_o_ultimo_sem_som() -> None:
    """O som de quem já tem fica onde está: sai o último que chegou SEM ponte,"""
    mesa = [_no_ar(VERMELHO, SALA), _no_ar(AZUL, SALA), _no_ar(VERDE, SALA),
            _no_ar(ROXO, SALA, "som")]
    ordem = _plano(mesa, (SALA, QUARTO))
    assert ordem is not None and ordem.controle == rm.uniq(VERDE)


def test_as_pontes_alem_do_limite_continuam_na_frente() -> None:
    """Três pontes num adaptador que comporta duas: a ordem é a das pontes, e"""
    mesa = [_no_ar(VERMELHO, SALA, "som"), _no_ar(AZUL, SALA, "som"),
            _no_ar(VERDE, SALA, "haptica"), _no_ar(ROXO, SALA)]
    ordem = _plano(mesa, (SALA, QUARTO, VARANDA))
    assert ordem is not None
    assert (ordem.controle, ordem.modo) == (rm.uniq(VERDE), "haptica")
    assert ordem.pontes_na_origem_depois == 2


def test_a_central_publica_a_proposta_de_equilibrar(mesa: Any, relogio: rm.Relogio) -> None:
    """A proposta chega ao ``state_full["radio_central"]`` — é ela que acende a
    lâmpada e dá o que perguntar ao «Equilibrar» (o resto é da tela, abaixo)."""
    *_, central = mesa(4)
    publicado = central.publicar([_no_ar(u, SALA) for u in QUATRO])
    assert publicado["proposta"] is not None
    assert publicado["proposta"]["controle"] == rm.uniq(ROXO)
    assert publicado["proposta"]["destino"] == QUARTO


PCI = "0000:00:14.0"
ADAPTADORES_DA_TELA = ("aa:bb:cc:00:00:09", "aa:bb:cc:00:00:15", "aa:bb:cc:00:00:21")
LUGARES_DA_TELA = (f"pci-{PCI}-usb-0:1.2", f"pci-{PCI}-usb-0:4.1.4", f"pci-{PCI}-usb-0:4.1.3")
NOMES_DA_TELA = ("Esquerda", "Direita", "Centro")


def _id(endereco: str) -> str:
    """O id da tela: 12 hex em maiúsculas, a forma do `_mac` do pacote."""
    return endereco.replace(":", "").upper()


def _objeto(adaptador: int, aparelho: str, **kw: Any) -> Any:
    from hefesto_dualsense4unix.integrations.bluez_dbus import AparelhoDoBluez

    no = f"/org/bluez/hci{adaptador}/dev_{aparelho.upper().replace(':', '_')}"
    return AparelhoDoBluez(no, f"/org/bluez/hci{adaptador}", aparelho.upper(), **kw)


@pytest.fixture()
def a08(monkeypatch: pytest.MonkeyPatch) -> Any:
    from hefesto_dualsense4unix.integrations.mesa_de_radio import Mesa
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    monkeypatch.setattr(a08_conexoes, "LER_NA_HORA", True)
    monkeypatch.setattr(a08_conexoes, "_FUNDO", {})
    monkeypatch.setattr(a08_conexoes, "_ABERTO", {})
    monkeypatch.setattr(a08_conexoes, "_CENA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_SALA_NA_TELA", {})
    monkeypatch.setattr(a08_conexoes, "_CHEGADAS", {})
    monkeypatch.setattr(a08_conexoes, "_mesa_do_radio", lambda recarregar=False: Mesa())
    monkeypatch.setattr(a08_conexoes, "_ler_o_historico", lambda: {})
    return a08_conexoes


def _montar(a08: Any, monkeypatch: pytest.MonkeyPatch, *, adaptadores: int = 3,
            aparelhos: tuple[Any, ...] = ()) -> None:
    """O BlueZ e o `maquina.json` da mesa declarada, com ``adaptadores`` deles."""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez
    from hefesto_dualsense4unix.utils.maquina import MaquinaConfig

    lidos = tuple(
        AdaptadorDoBluez(f"/org/bluez/hci{i}", f"hci{i}", ADAPTADORES_DA_TELA[i].upper(),
                         lugar=LUGARES_DA_TELA[i], varrendo=False)
        for i in range(adaptadores))
    monkeypatch.setattr(a08, "_FUNDO", {})
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (lidos, aparelhos))
    maquina = MaquinaConfig(adaptadores={_id(ADAPTADORES_DA_TELA[i]).lower():
                                         {"nome": NOMES_DA_TELA[i]}
                                         for i in range(adaptadores)})
    monkeypatch.setattr(a08, "_ler_a_maquina", lambda: (maquina, {3: PCI}))


def _estado(onde: dict[str, int], *, pontes: dict[str, str] | None = None,
            central: dict[str, Any] | None = None) -> dict[str, Any]:
    """``onde`` = {controle: índice do adaptador}; o daemon publica cada um."""
    pontes = pontes or {}
    return {
        "controllers": [
            {"uniq": rm.uniq(c), "transport": "bt", "connected": True,
             "adaptador": ADAPTADORES_DA_TELA[i], "hz_movimento": 150.0, "hz_voz": 0.0,
             "ponte_do_radio": pontes.get(c), "audio": {"mic_mudo": True}}
            for c, i in onde.items()],
        "radio_central": central or {"movimentos": [], "proposta": None},
    }


def _ctx(estado: dict[str, Any], jogadores: dict[str, int] | None = None) -> Any:
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    cores = {VERMELHO: ("cosmic-red", "Cosmic Red"), AZUL: ("white", "White"),
             VERDE: ("", ""), ROXO: ("galactic-purple", "Galactic Purple")}
    jogadores = jogadores or {c: n for n, c in enumerate(QUATRO, start=1)}
    mesa = [{"uniq": rm.uniq(c), "cor": cores[c][0], "nome": cores[c][1],
             "jogador": jogadores[c]}
            for c in QUATRO if any(e["uniq"] == rm.uniq(c) for e in estado["controllers"])]
    return Contexto(state=estado, conectados=list(estado["controllers"]), mesa=mesa)


def _cena(a08: Any, estado: dict[str, Any], **kw: Any) -> dict[str, Any]:
    ctx = _ctx(estado, **kw)
    a08.campos_do_radio(ctx)
    return dict(a08._CENA_NA_TELA)


def _linha(a08: Any, cena: dict[str, Any], quem: str) -> str:
    ap = next(a for a in cena["aparelhos"] if a["id"].replace(":", "").lower()
              == quem.replace(":", "").lower())
    return str(a08.html_da_linha(ap, cena))


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
def test_a_lotacao_conta_as_pontes_e_nao_os_controles(
    a08: Any, monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    """O item 4, MEDIDO: não é defeito de conta. A foto 3 dela mostra três"""
    _montar(a08, monkeypatch)
    onde = {c: 1 for c in QUATRO[:quantos]}
    cena = _cena(a08, _estado(onde))
    direita = next(lug for lug in cena["lugares"] if lug["id"] == _id(ADAPTADORES_DA_TELA[1]))
    cartao = a08.html_do_lugar(direita, cena)
    assert '0/2</span>' in cartao
    assert 'title="Controles com som ou vibração: 0 de 2"' in cartao

    com_som = _cena(a08, _estado(onde, pontes={c: "som" for c in onde}))
    direita = next(lug for lug in com_som["lugares"]
                   if lug["id"] == _id(ADAPTADORES_DA_TELA[1]))
    cartao = a08.html_do_lugar(direita, com_som)
    assert f"{quantos}/2</span>" in cartao
    if quantos > 2:
        assert "estourou" in cartao and "Passou do limite" in cartao


@pytest.mark.parametrize("quantos", [2, 3, 4])
def test_os_controles_amontoados_acendem_a_lampada_e_o_equilibrar_tem_o_que_perguntar(
    a08: Any, monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    """Os passos b4 e b5: com 2, 3 ou 4 controles na Direita e o Centro vazio,"""
    from hefesto_dualsense4unix.integrations import plano_de_radio

    _montar(a08, monkeypatch)
    onde = {c: 1 for c in QUATRO[:quantos]}
    controles = _estado(onde)["controllers"]
    planos = plano_de_radio.plano_por_adaptador(
        controles, adaptadores=ADAPTADORES_DA_TELA, listar=lambda _p: [], raiz="/nao/existe")
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is not None
    cena = _cena(a08, _estado(onde, central={"movimentos": [], "proposta": ordem.publicar()}))

    destino = _id(ordem.destino)
    assert cena["proposta"] == {"controle": ordem.controle, "destino": destino}
    cartao = a08.html_do_lugar(next(lug for lug in cena["lugares"] if lug["id"] == destino),
                               cena)
    assert 'class="lampada"' in cartao
    moldes = a08.html_dos_moldes(cena)
    assert f'class="balao-molde" data-controle="{ordem.controle}"' in moldes
    assert (f'data-alvo="{ordem.controle}" data-destino="{destino}" data-sim="Mover"'
            in moldes), "o «Equilibrar» não teria pergunta para abrir"
    assert a08.equilibrar_radio(None, {}, None) == {"armou": True}


def test_sem_proposta_o_equilibrar_treme(a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """2/1/1 é o equilíbrio: sem proposta, o botão treme (R8) e nada acende."""
    _montar(a08, monkeypatch)
    cena = _cena(a08, _estado({VERMELHO: 0, AZUL: 0, VERDE: 1, ROXO: 2}))
    assert cena["proposta"] is None
    assert "lampada" not in a08.html_da_sala(cena)
    with pytest.raises(RuntimeError):
        a08.equilibrar_radio(None, {}, None)


def _esperando(aparelho: str, destino: int, **kw: Any) -> dict[str, Any]:
    return {"aparelho": aparelho, "destino": ADAPTADORES_DA_TELA[destino],
            "estado": "esperando", "passo": "gesto", "motivo": "", "origens": [],
            "quando": time.time(), **kw}


def test_o_teclado_esperando_nao_pede_ps_create_nem_veste_dualsense(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O passo c3: mover um TECLADO pedia «segure PS + Create» e mostrava o
    desenho do DualSense. A linha dele agora tem o desenho do teclado e nenhum
    gesto inventado — a pergunta antes de mover já disse o que fazer.

    MORDIDA: faça ``gesto_de_parear`` devolver sempre o ``SEGURE`` — o teclado
    volta a pedir PS + Create e esta régua reprova.
    """
    _montar(a08, monkeypatch)
    central = {"movimentos": [_esperando(TECLADO, 2, e_controle=False,
                                         classe=rm.CLASSE_DE_TECLADO, modalias="",
                                         nome="BT5.0 Keyboard")],
               "proposta": None}
    cena = _cena(a08, _estado({VERMELHO: 0}, central=central))
    linha = _linha(a08, cena, TECLADO)
    assert "#rd-teclado" in linha and "#rd-ds" not in linha
    assert "PS + Create" not in linha
    assert "ponha o teclado para parear" in linha
    centro = next(lug for lug in cena["lugares"] if lug["id"] == _id(ADAPTADORES_DA_TELA[2]))
    assert not centro.get("conectando"), "a régua precisa da caixa sem a busca do «Conectar»"
    topo = a08._marcas_de_onde(centro, cena)
    visivel = topo.replace(re.search(r'<span class="espera busca".*?</span>', topo).group(0), "")
    assert "PS + Create" not in visivel and "#rd-teclado" in visivel


@pytest.mark.parametrize(("modalias", "gesto"), [
    ("bluetooth:v054Cp0CE6d0100", "Segure PS + Create"),   # DualSense
    ("bluetooth:v054Cp0DF2d0100", "Segure PS + Create"),   # DualSense Edge
    ("bluetooth:v054Cp09CCd0100", "Segure PS + Share"),
    ("bluetooth:v2DC8p6002d0100", ""),
    ("", "Segure PS + Create"),
])
def test_cada_controle_diz_o_gesto_do_modelo_dele(a08: Any, modalias: str, gesto: str) -> None:
    ap = {"tipo": "controle", "modalias": modalias}
    assert a08.gesto_de_parear(ap) == gesto
    fala = a08._como_se_pareia(ap)
    if gesto:
        assert gesto.removeprefix("Segure ") in fala
    else:
        assert "PS" not in fala and "ponha o controle para parear" in fala


def test_o_outro_aparelho_nao_vira_o_outro(a08: Any) -> None:
    """«Depois, ponha o outro para parear» era a frase do tipo «outro»."""
    assert a08._como_se_pareia({"tipo": "outro"}) == "Depois, ponha o aparelho para parear."
    assert a08._como_se_pareia({"tipo": "caixa"}) == "Depois, ponha a caixa de som para parear."


def test_o_teclado_de_baixo_consumo_tem_o_desenho_do_teclado(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O passo b7: o «BT5.0 Keyboard» não mostrava o teclado. Ele é de baixo"""
    aparelhos = (
        _objeto(0, TECLADO, nome="BT5.0 Keyboard", conectado=True, icone="input-keyboard"),
        _objeto(1, "aa:bb:cc:00:00:6d", nome="Mouse", conectado=False, rssi=-50,
                icone="input-mouse"),
        _objeto(1, "aa:bb:cc:00:00:6e", nome="Celular", conectado=False, rssi=-60,
                icone="phone"),
        _objeto(2, "aa:bb:cc:00:00:6f", nome="Fone", conectado=True, classe=0x240404),
    )
    _montar(a08, monkeypatch, aparelhos=aparelhos)
    a08._ABERTO["lugar"] = _id(ADAPTADORES_DA_TELA[1])
    cena = _cena(a08, _estado({VERMELHO: 0}))
    assert cena["destino_do_conectar"] == _id(ADAPTADORES_DA_TELA[1])
    tipos = {a["id"]: a["tipo"] for a in cena["aparelhos"]}
    assert tipos[_id(TECLADO)] == "teclado"
    assert tipos[_id("aa:bb:cc:00:00:6f")] == "fone"
    assert "#rd-teclado" in _linha(a08, cena, TECLADO)
    perto = {a["id"]: a["tipo"] for a in cena["perto"]}
    assert perto[_id("aa:bb:cc:00:00:6d")] == "mouse"
    assert perto[_id("aa:bb:cc:00:00:6e")] == "celular"
    moldes = a08.html_dos_moldes(cena)
    painel = moldes[moldes.index('data-painel="conectar"'):]
    assert "#rd-mouse" in painel and "#rd-celular" in painel
    assert "#rd-radio" not in painel, "a antena é só do adaptador"


def test_o_vizinho_que_o_sistema_reconhece_mostra_o_desenho_dele(a08: Any) -> None:
    """O rótulo da pista do rádio vizinho: declarado, o tipo dele; lido pelo kernel, o
    desenho do que ele leu; sem ninguém que saiba, o «?» — e a antena nunca."""
    cena = {"lugares": [{"id": "L1", "nome": "Sala"}], "aparelhos": [], "vizinhos": [
        {"id": "046d:c52b", "tipo": "", "nome": "", "sugestao": "Teclado",
         "sugestao_tipo": "teclado", "lido": "Teclado"},
        {"id": "0bda:8179", "tipo": "wifi", "nome": "Wi-Fi", "sugestao": "",
         "sugestao_tipo": ""},
        {"id": "1234:5678", "tipo": "", "nome": "", "sugestao": "", "sugestao_tipo": ""},
    ]}
    rotulos = re.findall(r'<button class="rotulo vizinho".*?</button>', a08.html_dos_canais(cena))
    assert len(rotulos) == 3
    assert "#rd-teclado" in rotulos[0]
    assert "#rd-wifi" in rotulos[1]
    assert "#rd-ajuda" in rotulos[2]
    assert all("#rd-radio" not in r for r in rotulos)


def test_o_nome_segue_o_controle_e_o_numero_segue_o_daemon(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O passo a2: *«O vermelho era P4, reconectou como P3, e a tela mostrava o"""
    aparelhos = (
        _objeto(0, VERMELHO, nome="Vitória", conectado=True),
        _objeto(2, VERMELHO, nome="André", conectado=False),
    )
    _montar(a08, monkeypatch, aparelhos=aparelhos)
    estado = _estado({VERMELHO: 0, AZUL: 0})
    cena = _cena(a08, estado, jogadores={VERMELHO: 4, AZUL: 1, VERDE: 2, ROXO: 3})
    vermelho = next(a for a in cena["aparelhos"] if a["id"] == rm.uniq(VERMELHO))
    assert a08.nome_na_conexoes(vermelho) == "Vitória ● Cosmic Red ● P4"
    linha = _linha(a08, cena, VERMELHO)
    assert 'value="Vitória"' in linha and "● Cosmic Red ● P4" in linha

    cena = _cena(a08, estado, jogadores={VERMELHO: 3, AZUL: 1, VERDE: 2, ROXO: 4})
    vermelho = next(a for a in cena["aparelhos"] if a["id"] == rm.uniq(VERMELHO))
    assert a08.nome_na_conexoes(vermelho) == "Vitória ● Cosmic Red ● P3"
    azul = next(a for a in cena["aparelhos"] if a["id"] == rm.uniq(AZUL))
    assert a08.nome_na_conexoes(azul) == "Player 1 ● White ● P1"
    assert "Vitória ● Cosmic Red ● P3" in a08.html_dos_moldes(cena)


def test_renomear_escreve_o_nome_em_todo_adaptador_que_conhece_o_controle(
    diario: Path, monkeypatch: pytest.MonkeyPatch, a08: Any
) -> None:
    """O nome vai para TODOS os objetos do controle — senão o adaptador em que"""
    mundo = rm.RadioDeMentira()
    mundo.pareado(SALA, VERMELHO, nome="André")
    mundo.pareado(QUARTO, VERMELHO, host=False)
    dono = _dono(mundo)
    monkeypatch.setattr(bd, "dono", lambda: dono)

    escrita = a08._alias_do_aparelho(VERMELHO.upper(), "Vitória")

    assert escrita.feita
    assert mundo.objeto(SALA, VERMELHO)["Alias"] == "Vitória"
    assert mundo.objeto(QUARTO, VERMELHO)["Alias"] == "Vitória"
    dono.fechar()


def test_quem_voltou_pelo_pareamento_antigo_pisca_no_adaptador_em_que_chegou(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O movimento «chegou» pelo pareamento antigo tem o destino ONDE ele"""
    _montar(a08, monkeypatch)
    chegou = {"aparelho": ROXO, "destino": ADAPTADORES_DA_TELA[0], "estado": "chegou",
              "passo": "fim", "motivo": cr.MOTIVO_PELO_PAREAMENTO_ANTIGO, "origens": [],
              "e_controle": True, "quando": time.time()}
    cena = _cena(a08, _estado({VERMELHO: 0, ROXO: 0},
                              central={"movimentos": [chegou], "proposta": None}))
    esquerda = next(lug for lug in cena["lugares"]
                    if lug["id"] == _id(ADAPTADORES_DA_TELA[0]))
    assert esquerda["chegou"] == [ROXO]
    assert f'data-chegou="{ROXO}"' in a08.html_do_lugar(esquerda, cena)


def test_com_um_adaptador_so_a_caixa_nasce_e_fica_aberta(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*«Essa área se só tiver um conector ela tá sempre aberta.»*"""
    _montar(a08, monkeypatch, adaptadores=1)
    cena = _cena(a08, _estado({VERMELHO: 0, AZUL: 0}))
    unico = cena["lugares"][0]
    assert cena["aberto"] == unico["id"]
    assert 'class="lugar aberto"' in a08.html_do_lugar(unico, cena)
    a08.abrir_adaptador(None, {"alvo": unico["id"]}, None)
    assert _cena(a08, _estado({VERMELHO: 0, AZUL: 0}))["aberto"] == unico["id"]

    _montar(a08, monkeypatch, adaptadores=2)
    cena = _cena(a08, _estado({VERMELHO: 0, AZUL: 1}))
    assert cena["aberto"] is None


def test_a_ordem_que_ela_arrasta_fica_gravada(a08: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """*«segurar a área do conector e arrastar ela pra mudar de ordem entre
    eles»*: o gesto grava a ordem no adaptador, pelo ENDEREÇO (o dono do nome
    dele, desde 28/09/2026 — antes era o ``gui_prefs``, pelo lugar), e a sala
    nasce nela. <!-- noqa-acento: citação literal -->

    MORDIDA: tire o ``_na_ordem_dela`` do ``cena_do_radio`` — a sala volta à
    ordem do BlueZ e esta régua reprova.
    """
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, ordem_dos_adaptadores

    _montar(a08, monkeypatch)
    cena = _cena(a08, _estado({VERMELHO: 0}))
    ids = [lug["id"] for lug in cena["lugares"]]
    assert ids == [_id(a) for a in ADAPTADORES_DA_TELA]

    nova = [ids[2], ids[0], ids[1]]
    a08.adaptador_reordenar(None, {"valor": " ".join(nova)}, None)

    assert ordem_dos_adaptadores(carregar_maquina()) == [
        _id(ADAPTADORES_DA_TELA[i]).lower() for i in (2, 0, 1)]
    depois = _cena(a08, _estado({VERMELHO: 0}))
    assert [lug["id"] for lug in depois["lugares"]] == nova
    with pytest.raises(ValueError):
        a08.adaptador_reordenar(None, {"valor": "AABBCC0000FF"}, None)


def test_a_ordem_de_antes_vale_ate_ela_arrastar_de_novo(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A ordem que ela arrastou antes de 28/09/2026 morava no ``gui_prefs``,
    pela chave do LUGAR (A-ENTRADA-TEM-UM-REGISTRO-SO-01). Ela vale, traduzida
    pelos adaptadores da tela, sem ninguém escrever na leitura; o arrastar
    seguinte a leva ao adaptador, pelo endereço, e a lista de lá sai.

    MORDIDA: tire o ``_a_ordem_de_antes`` do ``_na_ordem_dela`` — a sala nasce
    na ordem do BlueZ, e a arrumação dela se perde na atualização.
    """
    from hefesto_dualsense4unix.app import gui_prefs
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, ordem_dos_adaptadores

    gui_prefs.set_pref("adaptadores", [LUGARES_DA_TELA[1], LUGARES_DA_TELA[2]])
    _montar(a08, monkeypatch)
    cena = _cena(a08, _estado({VERMELHO: 0}))
    assert [lug["id"] for lug in cena["lugares"]] == [
        _id(ADAPTADORES_DA_TELA[i]) for i in (1, 2, 0)]
    assert ordem_dos_adaptadores(carregar_maquina()) == [], "a leitura escreveu"

    nova = [_id(ADAPTADORES_DA_TELA[i]) for i in (0, 1, 2)]
    a08.adaptador_reordenar(None, {"valor": " ".join(nova)}, None)
    assert ordem_dos_adaptadores(carregar_maquina()) == [n.lower() for n in nova]
    assert gui_prefs.a_ordem_dos_adaptadores_de_antes() == [], "a lista de antes ficou"
    assert "adaptadores" not in gui_prefs.load_gui_prefs()


def test_a_caixa_unica_nao_tem_seta_e_as_varias_se_arrastam(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A caixa única não tem a seta (abriria e fecharia nada) nem se arrasta;"""
    for quantos in (1, 2, 3):
        _montar(a08, monkeypatch, adaptadores=quantos)
        cena = _cena(a08, _estado({VERMELHO: 0, AZUL: 0}))
        for lug in cena["lugares"]:
            cartao = a08.html_do_lugar(lug, cena)
            assert ('class="abre-lugar"' in cartao) is (quantos > 1), quantos
            assert ('<div class="lugar-topo" draggable="true"' in cartao) is (quantos > 1)


@pytest.mark.parametrize("quantos", [1, 2, 3, 4])
@pytest.mark.parametrize("adaptadores", [2, 3])
def test_o_conectar_nasce_no_adaptador_de_menos_controles(
    a08: Any, monkeypatch: pytest.MonkeyPatch, quantos: int, adaptadores: int
) -> None:
    """A foto 2 dela: o chip do «Procurando» nascia na DIREITA, a dos três"""
    _montar(a08, monkeypatch, adaptadores=adaptadores)
    for cheio in range(adaptadores):
        cena = _cena(a08, _estado({c: cheio for c in QUATRO[:quantos]}))
        assert cena["destino_do_conectar"] != _id(ADAPTADORES_DA_TELA[cheio]), (quantos, cheio)


def test_com_a_janela_aberta_o_chip_e_o_da_janela_e_o_outro_recusa(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O adaptador em que a janela abriu passa a VARRER, e a D8 manda quem varre"""
    from hefesto_dualsense4unix.integrations.bluez_dbus import AdaptadorDoBluez

    _montar(a08, monkeypatch)
    centro = ADAPTADORES_DA_TELA[2]
    lidos = tuple(
        AdaptadorDoBluez(f"/org/bluez/hci{i}", f"hci{i}", ADAPTADORES_DA_TELA[i].upper(),
                         lugar=LUGARES_DA_TELA[i], varrendo=(i == 2))
        for i in range(3))
    monkeypatch.setattr(a08, "_ler_o_bluez", lambda: (lidos, ()))
    janela = {"aparelho": "", "destino": centro, "estado": "esperando", "passo": "gesto",
              "motivo": "", "origens": [], "e_controle": True, "quando": time.time()}
    busca = {"adaptador": centro, "desde": time.time(), "ate": time.time() + 120.0}
    cena = _cena(a08, _estado({VERMELHO: 1, AZUL: 1},
                              central={"movimentos": [janela], "proposta": None,
                                       "busca": busca}))
    assert cena["destino_do_conectar"] == _id(centro)
    assert cena["aberto"] == _id(centro), "a caixa da janela abre sozinha"
    ponte = _PonteDaCentralOcupada()
    with pytest.raises(RuntimeError):
        a08.escolher_adaptador(None, {"alvo": _id(ADAPTADORES_DA_TELA[0])}, ponte)
    assert ponte.pedidos == [{"destino": _id(ADAPTADORES_DA_TELA[0])}]
    a08.escolher_adaptador(None, {"alvo": _id(centro)}, ponte)
    assert len(ponte.pedidos) == 1, "o chip da janela não pergunta nada ao rádio"


class _PonteDaCentralOcupada:
    """O `radio.mover` com a central ocupada: o que o tratador real responde"""

    def __init__(self) -> None:
        self.pedidos: list[dict[str, Any]] = []

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        assert metodo == "radio.mover"
        self.pedidos.append(dict(params))
        return {"status": "ocupado", "movimento": {"estado": "nao_chegou", "motivo": "ocupado"}}


@pytest.mark.parametrize("destino", [0, 1, 2])
def test_a_caixa_de_quem_espera_o_gesto_abre_sozinha(
    a08: Any, monkeypatch: pytest.MonkeyPatch, destino: int
) -> None:
    """O «Segure PS + Create» mora na linha que espera, DENTRO da caixa do"""
    _montar(a08, monkeypatch)
    alvo = ADAPTADORES_DA_TELA[destino]
    mover = {"aparelho": VERMELHO, "destino": alvo, "estado": "esperando", "passo": "gesto",
             "motivo": "", "origens": [ADAPTADORES_DA_TELA[(destino + 1) % 3]],
             "e_controle": True, "quando": time.time()}
    cena = _cena(a08, _estado({AZUL: 0}, central={"movimentos": [mover], "proposta": None}))
    assert cena["aberto"] == _id(alvo)
    cartao = a08.html_do_lugar(next(lug for lug in cena["lugares"] if lug["id"] == _id(alvo)), cena)
    assert ("aberto" in cartao.split('"', 2)[1]
            and '<span class="segure">Segure PS + Create</span>' in cartao)
    assert _cena(a08, _estado({AZUL: 0}))["aberto"] is None


# O QUE O CONFERENTE ACHOU (25/09/2026) — a cura que só valia para o DualSense
# O rádio de mentira respondia o `HID_PHYS` só pelo DualSense e dava movimento a
# que o daemon (ele só mede o movimento do DualSense). Com ele fiel, três curas
# desta sprint caíam fora do DualSense de classe publicada.

TECLADO_LE = "aa:bb:cc:00:00:7d"
OUTRO_CONTROLE = "aa:bb:cc:00:00:8b"


@pytest.mark.parametrize("controles", [1, 4])
def test_o_teclado_de_baixo_consumo_se_move_como_teclado(
    mesa: Any, relogio: rm.Relogio, controles: int
) -> None:
    """O «BT5.0 Keyboard» dela é de baixo consumo: sem ``Class``, com o ``Icon``
    que o BlueZ deriva da ``Appearance``, e com hidraw pelo rádio como todo HID.
    Ele se move como teclado — não vira controle, não espera o movimento de
    DualSense, e chega.

    MORDIDA: devolva ao ``_e_controle`` a pergunta ao kernel no lugar do ``Icon``
    (*«o aparelho que tem hidraw no rádio é controle»*) — o teclado vira
    controle, o CONFERIR espera um movimento que ele não tem, e esta régua
    reprova.
    """
    mundo, dono, central = mesa(controles)
    mundo.pareado(SALA, TECLADO_LE, classe=None, icone="input-keyboard", hid=True)
    dono._fotografar()
    assert mundo.onde_esta(rm.uniq(TECLADO_LE)) == SALA, "o kernel dá hidraw ao teclado"
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(TECLADO_LE))

    feito = central.mover(TECLADO_LE, QUARTO)

    assert feito.e_controle is False, "o teclado de baixo consumo virou controle"
    assert (feito.estado, feito.destino) == (cr.CHEGOU, QUARTO)
    assert feito.publicar()["icone"] == "input-keyboard"
    assert mundo.lapides == [(SALA, TECLADO_LE)]
    for outro in QUATRO[:controles]:
        assert mundo.onde_esta(rm.uniq(outro)) == SALA


@pytest.mark.parametrize("modalias", [
    "bluetooth:v2DC8p6002d0100",
    "bluetooth:v054Cp09CCd0100",
])
@pytest.mark.parametrize("caminho", ["mover", "conectar"])
def test_o_controle_que_o_daemon_nao_le_chega_pelo_hid_phys(
    mesa: Any, relogio: rm.Relogio, modalias: str, caminho: str
) -> None:
    """O controle desconhecido da régua dela: é controle pela classe, e o daemon"""
    mundo, dono, central = mesa(2)
    if caminho == "mover":
        mundo.pareado(SALA, OUTRO_CONTROLE, modalias=modalias)
        dono._fotografar()
        mundo.desligar(OUTRO_CONTROLE)
        relogio.agendar(2.0, lambda: mundo.segurar_ps_create(OUTRO_CONTROLE))
        feito = central.mover(OUTRO_CONTROLE, QUARTO)
    else:
        mundo.fisicos[OUTRO_CONTROLE] = rm.Fisico(OUTRO_CONTROLE, rm.CLASSE_DE_CONTROLE,
                                                  modalias=modalias)
        rm.ela_pareia(relogio, mundo, central, OUTRO_CONTROLE)
        feito = central.conectar(QUARTO)

    assert mundo.hz(rm.uniq(OUTRO_CONTROLE)) is None, "o daemon não mede este controle"
    assert (feito.estado, feito.aparelho, feito.destino) == (
        cr.CHEGOU, OUTRO_CONTROLE, QUARTO), feito.motivo
    assert feito.e_controle is True
    assert not central.em_curso, "a central ficou ocupada com ele já lá"


def test_o_dualsense_sem_movimento_medido_continua_esperando(
    mesa: Any, relogio: rm.Relogio
) -> None:
    """A cura de cima não afrouxa o DualSense: o movimento dele o daemon mede, e
    «não sei» (o ``SensorHub`` antes de fechar uma janela) não é «chegou».

    MORDIDA: faça o ``_o_daemon_mede`` responder sempre que não — o DualSense
    passa a chegar sem movimento nenhum, e esta régua reprova.
    """
    mundo, _dono, central = mesa(2)
    central._movimento = lambda _u: None
    relogio.agendar(2.0, lambda: mundo.segurar_ps_create(VERMELHO))

    feito = central.mover(VERMELHO, QUARTO)

    assert mundo.onde_esta(rm.uniq(VERMELHO)) == QUARTO
    assert (feito.estado, feito.motivo) == (cr.ESPERANDO, cr.MOTIVO_SEM_CONFIRMACAO)


def test_o_teclado_de_baixo_consumo_esperando_tem_o_desenho_do_teclado(
    a08: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A linha de quem espera, pelo que a central leu: sem classe, o ``Icon``"""
    _montar(a08, monkeypatch)
    central = {"movimentos": [_esperando(TECLADO_LE, 2, e_controle=False, classe=None,
                                         icone="input-keyboard", modalias="", nome="")],
               "proposta": None}
    cena = _cena(a08, _estado({VERMELHO: 0}, central=central))
    linha = _linha(a08, cena, TECLADO_LE)
    assert "#rd-teclado" in linha and "#rd-ds" not in linha
    assert "PS + Create" not in linha
    assert "ponha o teclado para parear" in linha


@pytest.mark.parametrize("quantos", [2, 3, 4])
def test_a_lampada_aparece_sem_ela_abrir_caixa_nenhuma(
    a08: Any, monkeypatch: pytest.MonkeyPatch, quantos: int
) -> None:
    """O passo b5 dela, pelo que ela VÊ: a lâmpada mora no corpo da caixa do"""
    from hefesto_dualsense4unix.integrations import plano_de_radio

    _montar(a08, monkeypatch)
    onde = {c: 1 for c in QUATRO[:quantos]}
    planos = plano_de_radio.plano_por_adaptador(
        _estado(onde)["controllers"], adaptadores=ADAPTADORES_DA_TELA,
        listar=lambda _p: [], raiz="/nao/existe")
    ordem = plano_de_radio.ordem_de_redistribuicao(planos)
    assert ordem is not None
    estado = _estado(onde, central={"movimentos": [], "proposta": ordem.publicar()})
    cena = _cena(a08, estado)

    destino = _id(ordem.destino)
    # as caixas nascem fechadas (desenho aprovado de 05/10/2026): a proposta é o cartão
    # «Mover P N» da Gestão, que ela vê sem abrir caixa nenhuma; a lâmpada continua na caixa
    assert cena["aberto"] is None
    cartao = a08.html_do_lugar(next(lug for lug in cena["lugares"] if lug["id"] == destino),
                               cena)
    assert 'class="lampada"' in cartao
    dicas = a08._html_das_dicas([], cena)
    assert f'data-destino="{destino}"' in dicas and ">Mover P" in dicas

    a08.abrir_adaptador(None, {"alvo": destino}, None)
    assert _cena(a08, estado)["aberto"] == destino
    a08.abrir_adaptador(None, {"alvo": _id(ADAPTADORES_DA_TELA[1])}, None)
    assert _cena(a08, estado)["aberto"] == _id(ADAPTADORES_DA_TELA[1])
