"""O modo que a extensão pede fica ao lado do Modo automático.

Sprint de 01/11/2026. O manifesto traz
``modos_de_aba``; o perfil guarda o modo da extensão por seção; com a extensão viva o efeito fixo
da seção se suspende, e com a extensão fora volta no mesmo tique; o tópico ``modo.aba`` diz, por
controle, onde o modo aceso vale. Tudo por dublê: lar de mentira, porta num soquete temporário.
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from hefesto_dualsense4unix.core.events import TOPICOS_DE_ESTADO, EventBus, EventTopic
from hefesto_dualsense4unix.daemon.subsystems import luz_animada as luz
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.daemon.subsystems import vibracao_do_jogo as vj
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods import porta as porta_mod
from hefesto_dualsense4unix.mods.manifesto import (
    TOPICOS_DE_LEITURA,
    Manifesto,
    modos_pedidos,
    permissao_valida,
)
from hefesto_dualsense4unix.mods.porta import EscritorDoServico, Porta
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import (
    MODO_AUTOMATICO,
    MODO_PERSONALIZADO,
    PREFIXO_DO_MODO_DA_EXTENSAO,
    LedsConfig,
    MatchAny,
    Profile,
    extensao_do_modo,
    modo_que_vale,
    perfil_no_modo,
)

MOD = "pede"
PRE = PREFIXO_DO_MODO_DA_EXTENSAO
MODO = PRE + MOD
P1 = "aa:bb:cc:00:00:71"
P2 = "aa:bb:cc:00:00:72"
VIVA = frozenset({MOD})
NENHUMA: frozenset[str] = frozenset()
BASE: dict[str, Any] = {"id": MOD, "nome": "Pede", "api": ">=2,<3", "tipos": ["tema"],
                        "tema": {}}
BASE["versao"] = "1.0.0"  # (noqa-acento)
BASE["licenca"] = "MIT"
UM_MODO = {"id": "fundo", "rotulo": "Modo da extensão", "dica": "A extensão governa a seção.",
           "abas": ["02", "03", "04", "05", "10"]}


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> instalador.Lugares:
    lugares = instalador.Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                                 dados=tmp_path / "dados", registro=tmp_path / "mods.json",
                                 estado=tmp_path / "estado.json")
    monkeypatch.setattr(instalador.Lugares, "do_xdg", classmethod(lambda cls: lugares))
    return lugares


def _instalada(lg: instalador.Lugares, *, ligada: bool = True, mod_id: str = MOD,
               modos: list[dict[str, Any]] | None = None) -> None:
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto = {**BASE, "id": mod_id, "modos_de_aba": [UM_MODO] if modos is None else modos}
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[mod_id] = instalador.Entrada(
        id=mod_id, nome="Pede", versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=[], ligada=ligada, ligada_em="2026-11-01T10:00:00")
    instalador.gravar_registro(lg.registro, registro)


def _perfil(**campos: Any) -> Profile:
    return Profile(name="Noite", match=MatchAny(), **campos)


def test_o_manifesto_traz_um_modo_de_aba_e_recusa_o_que_sai_da_forma() -> None:
    m = Manifesto.model_validate({**BASE, "modos_de_aba": [UM_MODO]})
    assert [x.abas for x in m.modos_de_aba] == [["02", "03", "04", "05", "10"]]
    assert Manifesto.model_validate(BASE).modos_de_aba == []
    ruins = [
        [UM_MODO, {**UM_MODO, "id": "outro"}],
        [{**UM_MODO, "rotulo": "x" * 21}],
        [{**UM_MODO, "dica": "x" * 121}],
        [{**UM_MODO, "abas": ["06"]}],
        [{**UM_MODO, "abas": []}],
        [{**UM_MODO, "abas": ["03", "03"]}],
        [{**UM_MODO, "id": "Com Espaco"}],
        [{**UM_MODO, "cor": "vermelho"}],
    ]
    for modos in ruins:
        with pytest.raises(ValidationError):
            Manifesto.model_validate({**BASE, "modos_de_aba": modos})


def test_so_a_extensao_ligada_traz_o_modo(lg: instalador.Lugares) -> None:
    assert modos_pedidos() == ()
    _instalada(lg)
    [pedido] = modos_pedidos()
    assert pedido == {"valor": MODO, "rotulo": UM_MODO["rotulo"], "dica": UM_MODO["dica"],
                      "abas": ("02", "03", "04", "05", "10")}
    _instalada(lg, ligada=False)
    assert modos_pedidos() == ()
    _instalada(lg, mod_id="sem", modos=[])
    _instalada(lg)
    assert [p["valor"] for p in modos_pedidos()] == [MODO]


def test_o_perfil_guarda_o_modo_da_extensao_e_recusa_o_desconhecido() -> None:
    perfil = _perfil(triggers={"modo": MODO}, leds={"modo": MODO}, rumble={"modo": MODO},
                     controles_modo=MODO)
    loader.save_profile(perfil, origem="régua")
    lido = loader.load_profile("Noite")
    assert (lido.triggers.modo, lido.leds.modo, lido.rumble.modo, lido.controles_modo) == (
        MODO, MODO, MODO, MODO)
    for ruim in (PRE, PRE + "Com Espaco", "outro", PRE + "a" * 33):
        with pytest.raises(ValidationError):
            _perfil(triggers={"modo": ruim})
    assert extensao_do_modo(MODO) == MOD
    assert extensao_do_modo(MODO_AUTOMATICO) is None
    assert modo_que_vale(MODO, VIVA) == MODO
    assert modo_que_vale(MODO, NENHUMA) == MODO_PERSONALIZADO
    assert modo_que_vale(MODO_AUTOMATICO, NENHUMA) == MODO_AUTOMATICO


def test_com_a_extensao_viva_o_perfil_cala_o_gatilho_e_a_luz_e_sem_a_extensao_devolve() -> None:
    perfil = _perfil(
        triggers={"left": {"mode": "Rigid", "params": [2, 220]}, "modo": MODO},
        leds={"lightbar": (200, 10, 10), "auto_player_colors": False, "modo": MODO})
    calado = perfil_no_modo(perfil, VIVA)
    assert calado.triggers.left.mode == "Off" and calado.triggers.modo == MODO
    assert calado.leds.lightbar == (0, 0, 0) and calado.leds.auto_player_colors is True
    solto = perfil_no_modo(perfil, NENHUMA)
    assert solto.triggers.left.mode == "Rigid"
    assert solto.leds.lightbar == (200, 10, 10)
    outra = perfil_no_modo(perfil, frozenset({"outra"}))
    assert outra.triggers.left.mode == "Rigid"


def _o_p2_no_modo() -> Profile:
    return _perfil(
        triggers={"right": {"mode": "SemiAutoGun", "params": [4, 6, 7]}},
        controllers={P2: {"triggers": {"modo": MODO}}})


def test_o_gatilho_do_p2_se_suspende_com_a_extensao_viva_e_o_do_p1_nao() -> None:
    perfil = _o_p2_no_modo()
    vivo = tv.planos_do_perfil(perfil, VIVA)
    assert vivo.do(P1, "direito") is not None
    assert vivo.do(P2, "direito") is None and vivo.do(P2, "esquerdo") is None
    morto = tv.planos_do_perfil(perfil, NENHUMA)
    assert morto.do(P2, "direito") is not None
    assert morto.do(P2, "direito") == morto.do(P1, "direito")
    vib_viva = tv.vibracao_do_gatilho_do_perfil(perfil, VIVA)
    vib_morta = tv.vibracao_do_gatilho_do_perfil(perfil, NENHUMA)
    assert vib_viva.de(P2) is False
    assert vib_viva.de(P1) == vib_morta.de(P1) == vib_morta.de(P2)
    armas_vivas = tv.armas_do_gatilho_do_perfil(perfil, VIVA)
    armas_mortas = tv.armas_do_gatilho_do_perfil(perfil, NENHUMA)
    assert armas_vivas.de(P2, "direito") is None
    assert armas_vivas.de(P1, "direito") == armas_mortas.de(P2, "direito")


def test_o_perfil_que_vai_ao_aparelho_cala_so_o_gatilho_e_a_luz_do_p2() -> None:
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_specs

    perfil = _perfil(
        triggers={"right": {"mode": "SemiAutoGun", "params": [4, 6, 7]}},
        leds={"lightbar": (10, 200, 10), "auto_player_colors": False},
        controllers={
            P1: {"leds": {"lightbar": (200, 10, 10)}},
            P2: {"triggers": {"modo": MODO}, "leds": {"lightbar": (10, 10, 200), "modo": MODO}},
        })
    p1, p2 = P1.replace(":", ""), P2.replace(":", "")
    vivo = perfil_no_modo(perfil, VIVA)
    specs = _controllers_to_specs(vivo.controllers, vivo.leds)
    assert specs[p2].trigger_right is not None and specs[p2].trigger_right.mode.name == "OFF"
    assert specs[p2].led is None
    assert specs[p1].led is not None and specs[p1].trigger_right is None
    assert vivo.triggers.right.mode == "SemiAutoGun" and vivo.leds.lightbar == (10, 200, 10)
    assert (vivo.controllers or {})[p2].triggers.modo == MODO
    morto = perfil_no_modo(perfil, NENHUMA)
    specs_mortos = _controllers_to_specs(morto.controllers, morto.leds)
    assert specs_mortos[p2].trigger_right is None and specs_mortos[p2].led is not None
    assert luz.plano_do_perfil(
        _perfil(leds=LedsConfig(efeito="piscar;FF0000;4"),
                controllers={P2: {"leds": {"modo": MODO}}}),
        [P1, P2], vivas=VIVA).keys() == {P1}


def test_no_perfil_inteiro_o_modo_vivo_suspende_os_quatro_controles() -> None:
    perfil = _perfil(triggers={"right": {"mode": "SemiAutoGun", "params": [4, 6, 7]},
                               "modo": MODO})
    uniqs = [f"aa:bb:cc:00:00:7{n}" for n in range(1, 5)]
    vivo = tv.planos_do_perfil(perfil, VIVA)
    assert not vivo
    morto = tv.planos_do_perfil(perfil, NENHUMA)
    assert all(morto.do(u, "direito") is not None for u in uniqs)


def test_com_a_extensao_viva_a_luz_animada_nao_escreve_e_sem_a_extensao_volta() -> None:
    perfil = _perfil(leds=LedsConfig(efeito="piscar;FF0000;4", modo=MODO))
    assert luz.plano_do_perfil(perfil, [P1, P2], vivas=VIVA) == {}
    assert set(luz.plano_do_perfil(perfil, [P1, P2], vivas=NENHUMA)) == {P1, P2}


@pytest.fixture
def vista(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    caixa: dict[str, Any] = {"perfil": _o_p2_no_modo()}
    monkeypatch.setattr(tv, "_MODO_DA_ABA_DITO", {})
    monkeypatch.setattr(tv, "_nome_do_perfil_ativo", lambda _d: "Noite")
    monkeypatch.setattr(tv, "controles_do_daemon",
                        lambda _d: [SimpleNamespace(uniq=P1), SimpleNamespace(uniq=P2)])
    monkeypatch.setattr(vj, "_jogador_de", lambda _d, u: {P1: 1, P2: 2}[u])
    monkeypatch.setattr(tv, "_VISTA_LIDA", None)

    def ler() -> None:
        tv._VISTA_LIDA = ("Noite", caixa["perfil"])

    caixa["ler"] = ler
    return caixa


def test_o_modo_aba_do_p2_diz_a_extensao_e_o_do_p1_nao(vista: dict[str, Any]) -> None:
    bus = EventBus()
    fila = bus.subscribe(EventTopic.MODO_ABA)
    daemon = SimpleNamespace(bus=bus)
    vista["ler"]()
    tv.publicar_o_modo_da_aba(daemon, VIVA)
    cargas = [fila.get_nowait() for _ in range(fila.qsize())]
    por_uniq = {c["uniq"]: c for c in cargas}
    assert set(por_uniq) == {P1, P2}
    assert por_uniq[P2]["secoes"]["gatilhos"] == MODO
    assert por_uniq[P1]["secoes"]["gatilhos"] != MODO
    assert (por_uniq[P1]["jogador"], por_uniq[P2]["jogador"]) == (1, 2)
    assert set(por_uniq[P2]["secoes"]) == set(tv.SECOES_DO_MODO)
    tv.publicar_o_modo_da_aba(daemon, VIVA)
    assert fila.qsize() == 0
    tv.publicar_o_modo_da_aba(daemon, NENHUMA)
    [morta] = [fila.get_nowait() for _ in range(fila.qsize())]
    assert morta["uniq"] == P2 and morta["secoes"]["gatilhos"] == MODO_PERSONALIZADO
    assert EventTopic.MODO_ABA in TOPICOS_DE_LEITURA["modo.aba"]
    assert permissao_valida("ler:modo.aba")
    assert EventTopic.MODO_ABA not in TOPICOS_DE_ESTADO


class _Porta:
    def __init__(self) -> None:
        self.agora: frozenset[str] = NENHUMA

    def vivas(self) -> frozenset[str]:
        return self.agora


def test_a_extensao_que_cai_devolve_o_efeito_fixo_no_mesmo_tique(
    vista: dict[str, Any], monkeypatch: pytest.MonkeyPatch,
) -> None:
    porta = _Porta()
    bus = EventBus()
    daemon = SimpleNamespace(
        bus=bus, display_authority="game", store=SimpleNamespace(active_profile="Noite"),
        controller=None, _mods_supervisor=SimpleNamespace(porta=porta))
    lidas: list[str] = []

    def receita(_d: Any) -> Any:
        lidas.append("lida")
        vista["ler"]()
        return tv.DESLIGADA

    monkeypatch.setattr(tv, "receita_ativa", receita)
    passo = tv.Passo(daemon, tv.TatoVivo([]))
    passo.receita_de_agora(100.0)
    assert passo.motor.armas_do_gatilho.de(P2, "direito") is not None
    porta.agora = VIVA
    passo.receita_de_agora(100.01)
    assert len(lidas) == 2
    assert passo.motor.armas_do_gatilho.de(P2, "direito") is None
    assert passo.motor.armas_do_gatilho.de(P1, "direito") is not None
    assert passo.motor.vibra_o_gatilho.de(P2) is False
    passo.receita_de_agora(100.02)
    assert len(lidas) == 2
    porta.agora = NENHUMA
    passo.receita_de_agora(100.03)
    assert len(lidas) == 3
    assert passo.motor.armas_do_gatilho.de(P2, "direito") is not None


class _Cliente:
    def __init__(self, caminho: Path) -> None:
        import socket

        self.sock = socket.socket(socket.AF_UNIX)
        self.sock.connect(str(caminho))
        self.sock.settimeout(5)
        self.arquivo = self.sock.makefile("rb")
        self.proximo = 0

    def pedir(self, metodo: str, params: dict[str, Any]) -> dict[str, Any]:
        self.proximo += 1
        linha = {"jsonrpc": "2.0", "id": self.proximo, "method": metodo, "params": params}
        self.sock.sendall(json.dumps(linha).encode() + b"\n")
        while True:
            resposta: dict[str, Any] = json.loads(self.arquivo.readline())
            if resposta.get("id") == self.proximo:
                return resposta

    def evento(self) -> dict[str, Any]:
        recebido: dict[str, Any] = json.loads(self.arquivo.readline())
        return recebido

    def fechar(self) -> None:
        self.arquivo.close()
        self.sock.close()


def test_a_porta_diz_quem_vive_e_repete_o_modo_aba_a_quem_assina_depois(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    carga = {"uniq": P2, "jogador": 2, "secoes": {"gatilhos": MODO}}
    monkeypatch.setattr(tv, "_MODO_DA_ABA_DITO", {P2: carga})

    async def corrida() -> tuple[list[frozenset[str]], dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="pm") as pasta:
            caminho = Path(pasta) / "mods.sock"
            bus = EventBus()

            async def escritor(_m: str, _p: dict[str, Any]) -> Any:
                return {"status": "ok"}

            porta = Porta(caminho, bus, escritor=escritor,
                          o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1)
            await porta.iniciar()
            vistas = [porta_mod.extensoes_vivas()]
            porta.registrar("ficha", MOD, os.getpid(), ["ler:modo.aba"])
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
                vistas.append(porta_mod.extensoes_vivas())
                aceito = await asyncio.to_thread(
                    cliente.pedir, "eventos.assinar", {"topicos": ["modo.aba"]})
                assert aceito["result"] == {"assinados": ["modo.aba"]}
                evento = await asyncio.wait_for(asyncio.to_thread(cliente.evento), 3)
            finally:
                cliente.fechar()
            for _ in range(100):
                if not porta.vivas():
                    break
                await asyncio.sleep(0.02)
            vistas.append(porta.vivas())
            await porta.parar()
            vistas.append(porta_mod.extensoes_vivas())
            return vistas, evento

    vistas, evento = asyncio.run(corrida())
    assert vistas == [NENHUMA, VIVA, NENHUMA, NENHUMA]
    assert evento["params"]["nome"] == "modo.aba"
    assert evento["params"]["dados"] == carga


def test_entrar_e_sair_reaplica_o_perfil_que_nomeia_a_extensao(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secoes: dict[str, str] = {"gatilhos": MODO, "luz": MODO_PERSONALIZADO}
    monkeypatch.setattr(tv, "modos_do_perfil_ativo", lambda _d: ("Noite", dict(secoes)))
    levados: list[tuple[str, dict[str, Any]]] = []

    async def levar(self: Porta, metodo: str, _servico: str, pedido: dict[str, Any]) -> Any:
        levados.append((metodo, pedido))
        return True

    monkeypatch.setattr(Porta, "_levar", levar)

    async def corrida(mod_id: str) -> None:
        with tempfile.TemporaryDirectory(prefix="pr") as pasta:
            caminho = Path(pasta) / "mods.sock"
            porta = Porta(caminho, EventBus(), escritor=EscritorDoServico(SimpleNamespace()),
                          o_jogo_escreve=lambda _u, _c: False, uniq_do_posto=lambda: P1)
            await porta.iniciar()
            porta.registrar("ficha", mod_id, os.getpid(), [])
            cliente = _Cliente(caminho)
            try:
                await asyncio.to_thread(cliente.pedir, "mod.ola", {"ficha": "ficha"})
                await asyncio.sleep(0.05)
            finally:
                cliente.fechar()
            for _ in range(100):
                if not porta.vivas():
                    break
                await asyncio.sleep(0.02)
            await asyncio.sleep(0.05)
            await porta.parar()

    asyncio.run(corrida(MOD))
    assert levados == [("profile.reaplicar", {"name": "Noite"})] * 2
    levados.clear()
    asyncio.run(corrida("outra"))
    assert levados == []
