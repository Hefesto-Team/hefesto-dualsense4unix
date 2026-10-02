"""O PERFIL DE DESEMPENHO É DE CADA CONTROLE — A-GESTAO-DOS-CONTROLES-NO-PRODUTO-01.

Decisões dela de 26/09/2026: o Perfil de Desempenho mora em cada cartão da aba
Conexões (`D-2609-O-PERFIL-DE-DESEMPENHO-E-POR-CONTROLE`), «Eu escolho» virou
«Personalizado» (`D-2609-EU-ESCOLHO-VIRA-PERSONALIZADO`), os outros dois viraram
«Perfil Máximo» e «Perfil Econômico» (pedido dela na mesma noite) e o cartão e a aba
Sistema falam o MESMO perfil, por um dono e pelo mesmo gesto do daemon
(`D-2609-A-CONEXOES-E-A-SISTEMA-FALAM-O-MESMO-PERFIL`).

O que cada seção prova, e a mordida que a derruba:

1. o dono (`secao_orcamento`): os três rótulos, o disco de cada perfil e quem
   vence — MORDIDA: faça `perfil_do_controle` ignorar a mesa → reprova;
2. o clique no cartão grava só aquele controle, e recarregar acende o mesmo
   botão — P1 a P4, cabo e rádio — MORDIDA: troque `_uniq(o)` por `UNIQS[0]`
   no gesto → reprova no P2, P3 e P4;
3. a aba Sistema e o cartão são o mesmo dado — MORDIDA: faça `perfil_na_linha`
   ler só o controle (sem o teto da mesa) → reprova;
4. o aparelho: «Aplicar» e DEPOIS a «Bateria Longa» no P<k> põe o teto nele, e
   só nele — P1 a P4, cabo e rádio — MORDIDA: tire o `soltar(...)` de
   `lifecycle.reaplicar_se_a_economia_mudou` → o P<k> fica a 70% e no Médio.

O LAR É DE MENTIRA: o `conftest` desvia o `HOME` e os `XDG_*`; o `maquina.json`
e o perfil gravados aqui moram dentro dele.

A régua dela, a de toda decisão: *«nunca é pensada só em um modo, rota, forma
de conexão se cabo ou se bt, ou só pro player 1.»* <!-- noqa-acento: citação literal dela -->
"""
from __future__ import annotations

import pathlib
import re
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa as réguas da aba 04, que carregam o GTK")

from tests.unit.test_a_marca_da_cor_nao_some import NOME, UNIQS


RAIZ = pathlib.Path(__file__).resolve().parents[2]
PAGINAS = [RAIZ / "mockup/08-conexoes.html",
           RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"]
PAGINAS_09 = [RAIZ / "mockup/09-sistema.html",
              RAIZ / "src/hefesto_dualsense4unix/interface/paginas/09-sistema.html"]


def _orc() -> Any:
    from hefesto_dualsense4unix.app.actions.config import secao_orcamento

    return secao_orcamento


def _a08() -> Any:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


def test_os_rotulos_sao_os_do_desenho_e_personalizado_e_o_terceiro() -> None:
    orc = _orc()
    assert [orc.ROTULOS_DOS_PERFIS[p] for p in orc.PERFIS] == [
        "Perfil Máximo", "Perfil Econômico", "Personalizado"]
    assert orc.DICAS_DO_CARTAO[orc.PERFIL_EU_ESCOLHO].endswith("neste controle.")
    assert orc.DICAS_DO_CARTAO[orc.PERFIL_BATERIA_LONGA] == orc.DICAS[orc.PERFIL_BATERIA_LONGA]


@pytest.mark.parametrize("teto", [None, "balanceado", "max", "auto", "economia"])
@pytest.mark.parametrize("escolha", [None, True, False])
def test_quem_vence_e_a_regra_do_esquema(teto: str | None, escolha: bool | None) -> None:
    """A «Bateria Longa» global vale para todos; fora dela, cada controle tem o seu."""
    orc = _orc()
    aceso = orc.perfil_do_controle(teto, escolha)
    if teto == "economia" or escolha is True:
        assert aceso == orc.PERFIL_BATERIA_LONGA
    elif escolha is False:
        assert aceso == orc.PERFIL_EU_ESCOLHO
    else:
        assert aceso == orc.PERFIL_TUDO_LIGADO, "todo controle nasce com tudo ligado"


@pytest.mark.parametrize("k", [1, 2, 3, 4], ids=["P1", "P2", "P3", "P4"])
def test_o_corpo_do_clique_e_o_do_dono_da_economia(k: int) -> None:
    """O corpo é o do `machine.declare` que a economia já usa, com o valor do perfil."""
    from hefesto_dualsense4unix.profiles.schema import declaracao_da_economia

    orc = _orc()
    chave = next(iter(declaracao_da_economia(UNIQS[k - 1], True)["controles"]))
    for perfil, valor in orc.ECONOMIA_POR_PERFIL.items():
        assert orc.declaracao_do_perfil(UNIQS[k - 1], perfil) == {
            "controles": {chave: {"economia": valor}}}
        assert orc.perfil_do_controle(None, valor) == perfil, (
            f"o disco de «{orc.ROTULOS_DOS_PERFIS[perfil]}» não acende o mesmo botão")


class _PonteDoDisco:
    """O `machine.declare` do daemon, sem o daemon: a fusão contra o disco."""

    def __init__(self) -> None:
        self.corpos: list[dict[str, Any]] = []

    def machine_declare(self, corpo: dict[str, Any]) -> tuple[bool, str]:
        from hefesto_dualsense4unix.utils.maquina import gravar_maquina

        self.corpos.append(corpo)
        return bool(gravar_maquina(corpo)), ""


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> Iterator[_PonteDoDisco]:
    """O `maquina.json` do lar de mentira, lido pela LEITURA DA ABA (`_declaracao`)."""
    a08 = _a08()
    monkeypatch.setattr(a08, "_DECLARACAO", None)
    monkeypatch.setattr(a08, "_SELO_DA_DECLARACAO", None)
    yield _PonteDoDisco()


def _clicar(ponte: _PonteDoDisco, k: int, perfil: str, via: str = "usb") -> None:
    a08 = _a08()
    a08.perfil_do_controle_gesto(None, {"uniq": UNIQS[k - 1], "valor": perfil,
                                        "controle": f"p{k}", "via": via}, ponte)


def _acesos() -> dict[int, str]:
    """O botão aceso de cada cartão, pela MESMA leitura que o tique pinta."""
    a08 = _a08()
    dec = a08._declaracao()
    return {n: a08.perfil_na_linha(dec, UNIQS[n - 1])["perfil"] for n in (1, 2, 3, 4)}


@pytest.mark.parametrize("via", ["usb", "bt"])
@pytest.mark.parametrize("k", [1, 2, 3, 4], ids=["P1", "P2", "P3", "P4"])
def test_o_clique_grava_so_aquele_controle(disco: _PonteDoDisco, k: int, via: str) -> None:
    orc = _orc()
    assert _acesos() == dict.fromkeys((1, 2, 3, 4), orc.PERFIL_TUDO_LIGADO)
    _clicar(disco, k, orc.PERFIL_BATERIA_LONGA, via)
    esperado = dict.fromkeys((1, 2, 3, 4), orc.PERFIL_TUDO_LIGADO)
    esperado[k] = orc.PERFIL_BATERIA_LONGA
    assert _acesos() == esperado, "a «Bateria Longa» do cartão mexeu noutro controle"
    _clicar(disco, k, orc.PERFIL_EU_ESCOLHO, via)
    esperado[k] = orc.PERFIL_EU_ESCOLHO
    assert _acesos() == esperado
    _clicar(disco, k, orc.PERFIL_TUDO_LIGADO, via)
    assert _acesos() == dict.fromkeys((1, 2, 3, 4), orc.PERFIL_TUDO_LIGADO)
    assert len(disco.corpos) == 3


def test_o_mesmo_clique_de_novo_nao_grava(disco: _PonteDoDisco) -> None:
    orc = _orc()
    _clicar(disco, 2, orc.PERFIL_TUDO_LIGADO)
    assert disco.corpos == [], "clicar no botão já aceso gravou"


def test_um_perfil_que_nao_existe_recusa_sem_gravar(disco: _PonteDoDisco) -> None:
    with pytest.raises(ValueError):
        _clicar(disco, 1, "eu escolho")
    with pytest.raises(ValueError):
        _a08().perfil_do_controle_gesto(None, {"valor": "tudo_ligado"}, disco)
    assert disco.corpos == []


def test_a_bateria_longa_da_sistema_acende_os_quatro_cartoes(disco: _PonteDoDisco) -> None:
    """O clique do Perfil Global é o gesto da aba 09, e o cartão lê o mesmo disco."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema

    orc = _orc()
    _clicar(disco, 2, orc.PERFIL_BATERIA_LONGA)
    _clicar(disco, 3, orc.PERFIL_EU_ESCOLHO)
    a09_sistema.perfil_da_mesa(None, {"v": orc.PERFIL_BATERIA_LONGA}, disco)
    assert _acesos() == dict.fromkeys((1, 2, 3, 4), orc.PERFIL_BATERIA_LONGA)
    antes = len(disco.corpos)
    for k in (1, 2, 3, 4):
        with pytest.raises(RuntimeError, match="Perfil Global de Bateria"):
            _clicar(disco, k, orc.PERFIL_TUDO_LIGADO)
    _clicar(disco, 2, orc.PERFIL_BATERIA_LONGA)
    assert len(disco.corpos) == antes
    a09_sistema.perfil_da_mesa(None, {"v": orc.PERFIL_TUDO_LIGADO}, disco)
    assert _acesos() == {1: orc.PERFIL_TUDO_LIGADO, 2: orc.PERFIL_BATERIA_LONGA,
                         3: orc.PERFIL_EU_ESCOLHO, 4: orc.PERFIL_TUDO_LIGADO}


@pytest.mark.parametrize("arquivo", PAGINAS_09, ids=["bancada", "publicada"])
def test_a_sistema_diz_personalizado_e_a_relacao_com_o_cartao(arquivo: pathlib.Path) -> None:
    html = arquivo.read_text(encoding="utf-8")
    botoes = re.findall(r'data-gesto="perfil-da-mesa" data-v="(\w+)"[^>]*title="([^"]*)">([^<]+)<',
                        html)
    orc = _orc()
    assert [(v, r) for v, _t, r in botoes] == [
        (p, orc.ROTULOS_DOS_PERFIS[p]) for p in orc.PERFIS], botoes
    dicas = {v: t for v, t, _r in botoes}
    assert dicas["bateria_longa"].endswith("Vale para todos os controles."), dicas
    for v in ("tudo_ligado", "eu_escolho"):
        assert dicas[v].endswith("cada um pode ter o seu na aba Conexões."), dicas
    assert "Eu escolho" not in html


@pytest.mark.parametrize("arquivo", PAGINAS, ids=["bancada", "publicada"])
def test_cada_cartao_tem_os_tres_botoes_com_endereco(arquivo: pathlib.Path) -> None:
    orc = _orc()
    html = arquivo.read_text(encoding="utf-8")
    for n in (1, 2, 3, 4):
        cartao = html[html.index(f'data-controle="p{n}"'):]
        cartao = cartao[:cartao.index('class="gc-luz"')]
        botoes = re.findall(r'<button class="btn[^"]*" data-gesto="perfil-do-controle" '
                            r'value="(\w+)"[^>]*data-campo="perfil" data-hef-alvo="classe" '
                            r'data-hef-classe="on" data-hef-quando="(\w+)" '
                            r'data-hef-atributo="aria-checked" title="([^"]*)">([^<]+)</button>',
                            cartao)
        assert [(v, q, r) for v, q, _t, r in botoes] == [
            (p, p, orc.ROTULOS_DOS_PERFIS[p]) for p in orc.PERFIS], (n, botoes)
        assert [t for _v, _q, t, _r in botoes] == [orc.DICAS_DO_CARTAO[p] for p in orc.PERFIS]
    assert "economia-do-controle" not in html and "eco-luz" not in html


@pytest.mark.parametrize("arquivo", PAGINAS, ids=["bancada", "publicada"])
def test_o_clique_so_acende_sozinho_na_bancada(arquivo: pathlib.Path) -> None:
    """No produto quem acende é o tique: um clique recusado não fica aceso."""
    html = arquivo.read_text(encoding="utf-8")
    trecho = html[html.index('closest(".gc-perfil .seg .btn")') - 200:]
    assert "if (window.__hef) return;" in trecho[:400]


def test_o_pacote_pinta_o_perfil_de_cada_controle(disco: _PonteDoDisco) -> None:
    """A carga do tique leva `perfil` a cada coluna, do disco — P1 a P4, misto."""
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    orc = _orc()
    _clicar(disco, 2, orc.PERFIL_BATERIA_LONGA)
    _clicar(disco, 4, orc.PERFIL_EU_ESCOLHO)
    vias = ["usb", "bt", "usb", "bt"]
    mesa = [{"pref": f"p{n}", "uniq": UNIQS[n - 1], "jogador": n, "cor": "", "nome": "DualSense",
             "via": vias[n - 1].upper(), "transporte": vias[n - 1], "mascara": "Xbox 360"}
            for n in (1, 2, 3, 4)]
    conectados = [{"uniq": UNIQS[n - 1], "transport": vias[n - 1], "connected": True,
                   "battery_pct": 60} for n in (1, 2, 3, 4)]
    ctx = Contexto(state={"controllers": conectados, "native_mode": False},
                   mesa=mesa, conectados=conectados, estados={})
    colunas = _a08().pacote(ctx)["colunas"]
    assert {n: colunas[UNIQS[n - 1]]["perfil"] for n in (1, 2, 3, 4)} == {
        1: orc.PERFIL_TUDO_LIGADO, 2: orc.PERFIL_BATERIA_LONGA,
        3: orc.PERFIL_TUDO_LIGADO, 4: orc.PERFIL_EU_ESCOLHO}


@pytest.fixture
def declarar() -> Iterator[Any]:
    """Grava no `maquina.json` do lar de mentira, e a ativação o lê de lá."""
    from hefesto_dualsense4unix.profiles.schema import registrar_declaracao_da_mesa
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina, gravar_maquina

    registrar_declaracao_da_mesa(carregar_maquina)

    def gravar(corpo: dict[str, Any]) -> None:
        assert gravar_maquina(corpo), f"o lar de mentira recusou {corpo}"

    yield gravar
    registrar_declaracao_da_mesa(None)


def _o_clique_chega_ao_daemon(mesa: Any, declarar: Any, corpo: dict[str, Any]) -> None:
    """O que o `machine.declare` faz depois de gravar: `reaplicar_se_a_economia_mudou`."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.utils.maquina import carregar_maquina

    antes = carregar_maquina()
    declarar(corpo)
    vivo = SimpleNamespace(controller=mesa.ctl, _maquina=carregar_maquina(), _native_mode=False,
                           _reapply_last_profile=lambda: mesa.trocar(NOME, "system"))
    assert Daemon.reaplicar_se_a_economia_mudou(vivo, antes)  # type: ignore[arg-type]


def _donos_da_luz(mesa: Any) -> dict[int, str | None]:
    """A camada dona das luzes de número de cada controle (`usuaria` ou `perfil`)."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac

    with mesa.ctl._io_lock:
        return {n: (mesa.ctl._desired_owner_by_uniq.get(norm_mac(UNIQS[n - 1])) or {})
                .get("player_led_brightness") for n in (1, 2, 3, 4)}


