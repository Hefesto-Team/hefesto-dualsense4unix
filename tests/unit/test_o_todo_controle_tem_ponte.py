"""Todo controle tem ponte: a conta dos adaptadores, a repartição, a falta, a queda pelo motor."""

from __future__ import annotations

import math
from array import array
from itertools import combinations
from types import MappingProxyType, SimpleNamespace
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
from hefesto_dualsense4unix.daemon import ganho_da_haptica, state_store
from hefesto_dualsense4unix.daemon.subsystems import alto_falante as af
from hefesto_dualsense4unix.daemon.subsystems import tato_vivo as tv
from hefesto_dualsense4unix.integrations import plano_de_radio as pr
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from hefesto_dualsense4unix.integrations.mesa_de_radio import Adaptador
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from hefesto_dualsense4unix.profiles import formas_de_haptica as fh

A, B, C, D = ("aa:bb:cc:00:00:0a", "aa:bb:cc:00:00:0b", "aa:bb:cc:00:00:0c", "aa:bb:cc:00:00:0d")


def _controle(n: int, adaptador: str, ponte: str | None = None) -> dict[str, Any]:
    return {"transport": "bt", "connected": True, "uniq": f"aabbcc0000{n:02x}",
            "adaptador": adaptador, "ponte_do_radio": ponte}


def _planos(*controles: dict[str, Any], adaptadores: tuple[str, ...] = (A,)) -> dict[str, Any]:
    return pr.plano_por_adaptador(controles, adaptadores=adaptadores, listar=lambda _r: [])


@pytest.mark.parametrize(("cheio", "s", "ar", "esperado"), [
    (4, 187.5, 1504, 94), (4, 375.0, 1504, 0), (4, 187.5, 1312, 70),
    (2, 187.5, 1504, 282), (2, 375.0, 1504, 188), (2, 562.5, 1504, 95),
    (2, 187.5, 1312, 234), (2, 375.0, 1312, 140), (2, 562.5, 1312, 47),
    (1, 187.5, 1504, 658), (1, 562.5, 1504, 471), (1, 187.5, 1312, 562), (1, 562.5, 1312, 375),
])
def test_a_conta_casa_com_a_tabela(cheio: int, s: float, ar: float, esperado: int) -> None:
    assert abs(rm.hz_por_controle_na_conta(ar, cheio, cheias=cheio, custo=s) - esperado) <= 1


@pytest.mark.parametrize(("pontes", "s", "ar", "pedidos"), [
    (1, 187.5, 1504, 1), (2, 187.5, 1504, 1), (3, 187.5, 1504, 2), (4, 187.5, 1504, 2),
    (4, 375.0, 1504, 2), (4, 562.5, 1504, 4), (4, 375.0, 1312, 2), (4, 562.5, 1312, 4),
    (4, 500.0, 1504, 2), (4, 503.0, 1504, 4), (4, 405.0, 1312, 2), (4, 407.0, 1312, 4),
    (0, 187.5, 1504, 0),
])
def test_quantos_adaptadores_a_formacao_pede(
    pontes: int, s: float, ar: float, pedidos: int,
) -> None:
    assert rm.adaptadores_que_a_formacao_pede(pontes, ar=ar, custo=s) == pedidos


def test_quem_nao_tem_ponte_divide_a_entrada_e_entra_na_conta() -> None:
    assert rm.adaptadores_que_a_formacao_pede(2, sem_ponte=2, ar=1312.0, custo=187.5) == 2
    assert rm.adaptadores_que_a_formacao_pede(2, sem_ponte=2, ar=1504.0, custo=187.5) == 1


def test_o_custo_mora_numa_constante_so_e_a_conta_inteira_acompanha(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert rm.custo_da_ponte() == (rm.FATIAS_DA_PONTE - 1) * rm.HZ_DA_PONTE
    assert rm.adaptadores_que_a_formacao_pede(4) == 2
    planos = _planos(*(_controle(i, A) for i in range(2)), adaptadores=(A, B))
    assert pr.repartir_a_formacao(planos, atras_de_hub=[A, B]).cabe
    monkeypatch.setattr(rm.custo_da_ponte, "__defaults__", (rm.HZ_DA_PONTE, 5.8))
    assert rm.adaptadores_que_a_formacao_pede(4) == 2
    assert rm.hz_por_controle_na_conta(1504.0, 2, cheias=2) == pytest.approx(
        (1504 - 2 * 4.8 * 93.75) / 2 / 2)
    assert not pr.repartir_a_formacao(planos, atras_de_hub=[A, B]).cabe
    monkeypatch.setattr(rm.custo_da_ponte, "__defaults__", (rm.HZ_DA_PONTE, 7))
    assert rm.adaptadores_que_a_formacao_pede(4) == 4


@pytest.mark.parametrize(("adaptadores", "faltam", "pedidos"), [
    ((A,), 1, 2), ((A, B), 0, 2), ((A, B, C, D), 0, 2),
])
def test_quatro_no_radio_com_um_dois_e_quatro_adaptadores(
    adaptadores: tuple[str, ...], faltam: int, pedidos: int,
) -> None:
    planos = _planos(*(_controle(i, A) for i in range(4)), adaptadores=adaptadores)
    conta = pr.repartir_a_formacao(planos)
    assert conta.faltam == faltam
    assert conta.pedidos == pedidos
    assert len(conta.assentos) == 4
    assert all(hz >= rm.HZ_QUE_ENGASGA for hz in conta.hz_previsto.values())


def test_quem_ja_tem_ponte_fica_e_a_ordem_nao_e_o_numero_do_jogador() -> None:
    controles = [_controle(0, A), _controle(1, A), _controle(2, A, "som"),
                 _controle(3, A, "haptica")]
    for i, c in enumerate(reversed(controles)):
        c["player_slot"] = i + 1
    conta = pr.repartir_a_formacao(_planos(*controles))
    assert set(conta.sem_lugar) == {"aabbcc000000", "aabbcc000001"}


@pytest.mark.parametrize("quem", [(2,), (1, 2, 3), (0, 2), (3, 1)])
def test_a_conta_nao_depende_da_posicao_do_jogador(quem: tuple[int, ...]) -> None:
    controles = [{**_controle(i, A), "player_slot": i + 1} for i in quem]
    conta = pr.repartir_a_formacao(_planos(*controles))
    assert conta.pedidos == (1 if len(quem) <= 2 else 2)
    assert conta.faltam == (0 if len(quem) <= 2 else 1)


@pytest.mark.parametrize(("no_ar", "pedidos"), [(4, 2), (3, 2), (2, 1), (1, 1), (0, 0)])
def test_as_mesas_de_cabo_e_radio(no_ar: int, pedidos: int) -> None:
    cabos = [{"transport": "usb", "connected": True, "uniq": f"aabbcc0000f{i}"}
             for i in range(4 - no_ar)]
    radios = [_controle(i, A) for i in range(no_ar)]
    for controles in (cabos + radios, radios + cabos):
        assert pr.repartir_a_formacao(_planos(*controles)).pedidos == pedidos


def test_quatro_com_tres_adaptadores_dividem_o_que_sobra() -> None:
    planos = _planos(*(_controle(i, A) for i in range(4)), adaptadores=(A, B, C))
    conta = pr.repartir_a_formacao(planos)
    assert [a.destino for a in conta.assentos if a.fica] == [A, A]
    assert sorted(a.destino for a in conta.mudam) == [B, C]
    assert conta.faltam == 0


def test_tres_no_mesmo_adaptador_pedem_dois_pelo_teto() -> None:
    conta = pr.repartir_a_formacao(_planos(*(_controle(i, A) for i in range(3))))
    assert (conta.pedidos, conta.faltam, len(conta.sem_lugar)) == (2, 1, 1)


def test_o_cabo_nao_gasta_ar() -> None:
    cabo = {"transport": "usb", "connected": True, "uniq": "aabbcc0000ff"}
    conta = pr.repartir_a_formacao(_planos(cabo, _controle(0, A), _controle(1, A)))
    assert conta.cabe
    assert conta.pedidos == 1


def test_o_controle_sem_voice_coil_nao_pede_ponte_e_nao_recebe_aviso() -> None:
    pro = [_controle(i, A) for i in range(4)]
    conta = pr.repartir_a_formacao(_planos(*pro), pedem_ponte=[])
    assert conta.pedidos == 1
    assert (conta.faltam, conta.assentos) == (0, ())


def test_quem_divide_com_o_pro_pode_ficar_sem_lugar_pelo_hz() -> None:
    misto = [_controle(i, A) for i in range(4)]
    planos = _planos(*misto)
    pedem = [str(c["uniq"]) for c in misto[:2]]
    assert pr.repartir_a_formacao(planos, pedem_ponte=pedem).faltam == 0
    atras = pr.repartir_a_formacao(planos, pedem_ponte=pedem, atras_de_hub=[A])
    assert atras.sem_lugar == ("aabbcc000001",)
    assert atras.trocar_de_porta == (A,)


def test_a_recomendacao_nao_ignora_o_hub(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rm.custo_da_ponte, "__defaults__", (rm.HZ_DA_PONTE, 5.8))
    planos = _planos(*(_controle(i, A) for i in range(2)), adaptadores=(A, B))
    assert pr.repartir_a_formacao(planos).cabe
    atras = pr.repartir_a_formacao(planos, atras_de_hub=[A, B])
    assert atras.faltam == 0
    assert len(atras.mudam) == 1
    assert atras.trocar_de_porta == (A, B)


def test_o_teto_vem_do_plano_nunca_de_um_numero_fixo() -> None:
    planos = pr.plano_por_adaptador(
        [_controle(i, A) for i in range(2)], adaptadores=(A,), n_max=1, listar=lambda _r: [])
    assert pr.repartir_a_formacao(planos).sem_lugar == ("aabbcc000001",)


def test_quem_nao_tem_adaptador_sabido_nao_entra_na_conta() -> None:
    planos = {rm.SEM_ADAPTADOR: pr.PlanoDoAdaptador(endereco=rm.SEM_ADAPTADOR)}
    conta = pr.repartir_a_formacao(planos)
    assert (conta.pedidos, conta.faltam) == (0, 0)


def test_a_porta_vem_do_dono_dos_adaptadores() -> None:
    na_mesa = {"hci0": A.upper(), "hci1": B}
    lista = (Adaptador("hci0", atras_de_hub=True), Adaptador("hci1"))

    def atras(endereco: str) -> bool:
        return rm.atras_de_hub_no_sysfs(
            endereco, na_mesa=lambda: na_mesa, adaptadores=lambda: lista)

    assert atras(A) is True
    assert atras(B) is False
    assert atras(C) is False


def test_o_n_max_ligado_usa_a_porta_do_adaptador(monkeypatch: pytest.MonkeyPatch) -> None:
    rm._PORTA_LIDA.clear()
    monkeypatch.setattr(rm, "atras_de_hub_no_sysfs", lambda _e: True)
    assert rm.n_max_do_adaptador(4, ligado=True, endereco=A) == 1
    rm._PORTA_LIDA.clear()
    monkeypatch.setattr(rm, "atras_de_hub_no_sysfs", lambda _e: False)
    assert rm.n_max_do_adaptador(4, ligado=True, endereco=A) == 2
    rm._PORTA_LIDA.clear()


def test_o_n_max_desligado_nao_le_a_porta(monkeypatch: pytest.MonkeyPatch) -> None:
    def explode(_e: str) -> bool:
        raise AssertionError("o tique não varre /sys com o interruptor desligado")

    monkeypatch.setattr(rm, "atras_de_hub_no_sysfs", explode)
    assert rm.n_max_do_adaptador(4, endereco=A) == rm.N_MAX_PONTES


P = tuple(f"aa:bb:cc:00:00:{i:02x}" for i in range(1, 5))
CABO, COM_PONTE, SEM_PONTE, PRO, OITO_BITDO = "cabo", "com_ponte", "sem_ponte", "pro", "8bitdo"
SONY, XBOX, NINTENDO, STEAM, NAVEGACAO, NATIVO = (
    "dualsense", "xbox", "nintendo", "steam", "navegacao", "nativo")
APPID = 1196590
_RECEITA = tv.Receita(som_no_corpo_escolhido=True)


class _Tocador:
    def __init__(self) -> None:
        self.corpo: list[int] = []

    def levar_o_corpo(self, amostras: Any, _lado: str, *, sink: str, dono: str) -> None:
        self.corpo.append(len(amostras))


class _Backend:
    primary_uniq: str | None = None

    def __init__(self) -> None:
        self.rumble: list[tuple[str, int, int]] = []

    def set_rumble_for(self, uniq: str, fraco: int, forte: int) -> bool:
        self.rumble.append((uniq, fraco, forte))
        return True


class _Cabo:
    def __init__(self, donos: dict[str, str]) -> None:
        self.donos = donos

    def aparelhos(self) -> dict[str, Any]:
        return {m: SimpleNamespace(dono=d) for m, d in self.donos.items()}

    def leva_os_motores(self, _marca: str) -> bool:
        return True


def _pad(mascara: str, *, rumble: bool = False) -> Any:
    if mascara in (NAVEGACAO, NATIVO, STEAM):
        return None
    visto = {"rumble": 0.1} if rumble else {}
    return SimpleNamespace(backend="uhid" if mascara == SONY else "uinput", game_open=True,
                           visto_ha_s=visto)


class _Mesa:
    """Um daemon com ``Passo``, saída e alto-falante do produto; só tocador e nó são dublês."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, conexoes: dict[str, str], *,
        mascara: str = XBOX, forca: int = 80, rumble: bool = False,
        mascaras: dict[str, str] | None = None,
    ) -> None:
        monkeypatch.setattr(tv, "estilo_ativo", lambda _d: None)
        monkeypatch.setattr(tv, "_barras_dos_motores", lambda _d, _u: (100, 100))
        monkeypatch.setattr(ganho_da_haptica.GANHO, "pct", lambda _u: self.forca)
        monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: False)
        monkeypatch.setattr(tv, "_mults_no_report", lambda _d, _u: (1.0, 1.0))
        self.forca = forca
        self.backend = _Backend()
        self.alto = af.AltoFalanteSubsystem()
        self.alto._cabo = _Cabo({})
        self.tocadores: dict[str, _Tocador] = {}
        self.no: list[tuple[str, int, int]] = []
        aparelhos: dict[str, str] = {}
        for uniq, via in conexoes.items():
            if via in (PRO, OITO_BITDO):
                continue
            marca = f"m{uniq[-2:]}"
            aparelhos[uniq] = marca
            self.alto._endpoints[marca] = SimpleNamespace(module_id=1, nome=f"no_{marca}")
            self.tocadores[uniq] = _Tocador()
            if via == CABO:
                self.alto._cabo.donos[marca] = uniq
            elif via == COM_PONTE:
                self.subir_a_ponte(uniq)
        self.alto._aparelho_de = MappingProxyType(aparelhos)
        self.alto._tocadores = MappingProxyType(
            {f"m{u[-2:]}": t for u, t in self.tocadores.items()})
        self.pads = {u: _pad((mascaras or {}).get(u, mascara), rumble=rumble) for u in conexoes}
        primeiro = next(iter(conexoes))
        self.backend.primary_uniq = primeiro
        jogadores = {
            u: SimpleNamespace(reader=SimpleNamespace(snapshot=lambda: None), vpad=self.pads[u],
                               motion_reader=None, externo=c in (PRO, OITO_BITDO))
            for u, c in conexoes.items() if u != primeiro
        }
        self.daemon = SimpleNamespace(
            controller=self.backend, _gamepad_device=self.pads[primeiro], _last_state=None,
            _motion_reader=None, _coop_manager=SimpleNamespace(_players=jogadores),
            _alto_falante_subsystem=self.alto,
            is_native_mode=lambda: mascara in (NATIVO, STEAM),
            display_authority="game", appid_em_cena=APPID, store=state_store.StateStore())
        self.motor = tv.TatoVivo([])
        self.motor.escolhas = {norm_mac(u): fh.SOM_NO_CORPO for u in conexoes}
        if mascara == STEAM:
            self.motor.steam_input = frozenset({APPID})
        self.daemon._tato_vivo = self.motor
        self.passo = tv.Passo(self.daemon, self.motor)
        monkeypatch.setattr(self.passo, "receita_de_agora", lambda _a: _RECEITA)
        self.passo.receita_vigente = _RECEITA
        monkeypatch.setattr(
            "hefesto_dualsense4unix.daemon.subsystems.gamepad.vibrar_o_externo",
            lambda _d, _m, u, fraco, forte: self.no.append((u, fraco, forte)) or (fraco, forte))
        self.t = 0.0

    def subir_a_ponte(self, uniq: str) -> None:
        nome = f"no_m{uniq[-2:]}"
        self.alto._pontes[uniq] = SimpleNamespace(esta_de_pe=lambda: True)
        self.alto._leva_da_ponte = MappingProxyType({**self.alto._leva_da_ponte, uniq: True})
        self.alto._endpoint_da_ponte = MappingProxyType(
            {**self.alto._endpoint_da_ponte, uniq: nome})

    def correr(self, segundos: float, *, som: bool = True) -> None:
        fim = self.t + segundos
        while self.t <= fim:
            if som:
                self.passo.alimentar_o_corpo(_grave(160))
            self.passo(self.t)
            self.t += tv.INTERVALO_S

    def motores(self, uniq: str) -> list[tuple[int, int]]:
        return ([(a, b) for u, a, b in self.backend.rumble if u == uniq]
                + [(a, b) for u, a, b in self.no if u == uniq])


def _grave(n: int) -> bytes:
    fase: list[int] = []
    for i in range(n):
        v = int(24000 * math.sin(2 * math.pi * 60 * i / 48000))
        fase += [v, v]
    return array("h", fase).tobytes()


def test_sem_ponte_o_grave_vai_ao_par_de_motores_e_o_tocador_segue_acordando_a_ponte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(1.0)
    par = mesa.motores(P[0])
    assert par and any(a and a == b for a, b in par)
    assert mesa.tocadores[P[0]].corpo, "sem o tocador a ponte nunca sobe"


def test_a_queda_fica_em_dezesseis_escritas_por_segundo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(3.0)
    assert 3 * 14 <= len(mesa.motores(P[0])) <= 3 * tv.ESCRITAS_DA_QUEDA_POR_S + 1


def test_a_ponte_sobe_e_o_motor_zera_no_mesmo_tique_e_nao_volta(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(1.0)
    assert mesa.motores(P[0])[-1] != (0, 0)
    antes = len(mesa.motores(P[0]))
    mesa.subir_a_ponte(P[0])
    mesa.correr(tv.INTERVALO_S / 2)
    assert mesa.motores(P[0])[antes:] == [(0, 0)]
    mesa.correr(2.0)
    assert mesa.motores(P[0])[antes:] == [(0, 0)], "motor por report não convive com o PCM"
    assert mesa.motor.queda.estados == {}


@pytest.mark.parametrize("via", [COM_PONTE, CABO])
def test_com_o_caminho_de_pe_nao_ha_queda(
    monkeypatch: pytest.MonkeyPatch, via: str,
) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: via})
    mesa.correr(1.0)
    assert mesa.motores(P[0]) == []


@pytest.mark.parametrize("mascara", [NATIVO, STEAM])
def test_nunca_onde_o_hefesto_nao_fala(monkeypatch: pytest.MonkeyPatch, mascara: str) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE, P[1]: SEM_PONTE}, mascara=mascara)
    mesa.correr(1.0)
    assert mesa.motores(P[0]) == mesa.motores(P[1]) == []


@pytest.mark.parametrize("mascara", [SONY, XBOX, NINTENDO, NAVEGACAO])
@pytest.mark.parametrize("quem", range(4))
def test_toda_opcao_da_aba_jogar_com_um_jogador_em_cada_posicao(
    monkeypatch: pytest.MonkeyPatch, mascara: str, quem: int,
) -> None:
    mesa = _Mesa(monkeypatch, {P[quem]: SEM_PONTE}, mascara=mascara)
    mesa.correr(0.5)
    assert mesa.motores(P[quem])


@pytest.mark.parametrize("ordem", [(0, 1, 2, 3), (3, 2, 1, 0), (2, 0, 3, 1)])
def test_a_ordem_de_ligar_nao_muda_quem_cai(
    monkeypatch: pytest.MonkeyPatch, ordem: tuple[int, ...],
) -> None:
    vias = dict(zip(P, (CABO, SEM_PONTE, COM_PONTE, SEM_PONTE), strict=True))
    mesa = _Mesa(monkeypatch, {P[i]: vias[P[i]] for i in ordem})
    mesa.correr(0.5)
    assert {u for u in P if mesa.motores(u)} == {P[1], P[3]}


def test_mascaras_misturadas_na_mesma_mesa(monkeypatch: pytest.MonkeyPatch) -> None:
    mascaras = dict(zip(P, (SONY, XBOX, NINTENDO, SONY), strict=True))
    mesa = _Mesa(monkeypatch, dict.fromkeys(P, SEM_PONTE), mascaras=mascaras)
    mesa.correr(0.5)
    assert all(mesa.motores(u) for u in P)


@pytest.mark.parametrize(("uma", "outra"), list(combinations((SONY, XBOX, NINTENDO, NAVEGACAO), 2)))
def test_toda_opcao_da_aba_jogar_por_pares(
    monkeypatch: pytest.MonkeyPatch, uma: str, outra: str,
) -> None:
    mascaras = dict(zip(P, (uma, outra, outra, uma), strict=True))
    mesa = _Mesa(monkeypatch, dict.fromkeys(P, SEM_PONTE), mascaras=mascaras)
    mesa.correr(0.5)
    assert all(mesa.motores(u) for u in P)


def test_o_rumble_do_jogo_passa_na_frente(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE}, rumble=True)
    mesa.correr(1.0)
    assert mesa.motores(P[0]) == []


def test_a_forca_zero_cala_e_nao_cai_para_o_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE}, forca=0)
    mesa.correr(1.0)
    assert mesa.motores(P[0]) == []


def test_a_forca_a_zero_no_meio_solta_o_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(0.5)
    mesa.forca = 0
    mesa.correr(0.1)
    assert mesa.motores(P[0])[-1] == (0, 0)
    assert mesa.motor.queda.estados == {}


def test_a_bateria_longa_no_meio_solta_o_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(0.5)
    monkeypatch.setattr(tv, "_controle_na_economia", lambda _u: True)
    mesa.correr(tv.SILENCIO_DA_QUEDA_S * 2)
    assert mesa.motores(P[0])[-1] == (0, 0)


def test_o_jogo_no_endpoint_cala_a_queda(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.alto._aparelhos_com_jogo = frozenset({f"m{P[0][-2:]}"})
    mesa.correr(0.5)
    assert mesa.motores(P[0]) == []


def test_no_cabo_sem_o_laco_o_grave_cai_pelo_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: CABO})
    mesa.alto._cabo.donos.clear()
    mesa.correr(0.5)
    assert mesa.motores(P[0])
    mesa.alto._cabo.donos[f"m{P[0][-2:]}"] = P[0]
    mesa.correr(0.1)
    assert mesa.motores(P[0])[-1] == (0, 0)


def test_o_silencio_solta_o_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(0.5)
    mesa.correr(tv.SILENCIO_DA_QUEDA_S * 2, som=False)
    assert mesa.motores(P[0])[-1] == (0, 0)


def test_a_mudanca_para_o_nativo_nao_deixa_o_motor_preso(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(0.5)
    mesa.daemon.is_native_mode = lambda: True
    mesa.correr(0.2)
    assert mesa.motores(P[0])[-1] == (0, 0)


def test_o_motor_parado_zera_a_queda(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(0.5)
    mesa.motor.parar(mesa.t)
    assert mesa.motores(P[0])[-1] == (0, 0)


def test_a_falha_de_um_controle_nao_cala_os_outros(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE, P[2]: SEM_PONTE})
    escrever = mesa.backend.set_rumble_for

    def falha_no_primeiro(uniq: str, fraco: int, forte: int) -> bool:
        if uniq == P[0]:
            raise OSError("o controle saiu no meio da escrita")
        return escrever(uniq, fraco, forte)

    mesa.backend.set_rumble_for = falha_no_primeiro
    mesa.correr(0.5)
    assert any(any(par) for par in mesa.motores(P[2]))


def test_a_falha_ao_parar_nao_segura_a_devolucao_dos_outros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE, P[2]: SEM_PONTE})
    mesa.correr(0.5)
    devolvidos: list[float] = []
    mesa.motor.atuadores = [SimpleNamespace(canal="luz", devolver_tudo=devolvidos.append)]
    escrever = mesa.backend.set_rumble_for

    def falha_no_primeiro(uniq: str, fraco: int, forte: int) -> bool:
        if uniq == P[0]:
            raise OSError("o controle saiu no meio da escrita")
        return escrever(uniq, fraco, forte)

    mesa.backend.set_rumble_for = falha_no_primeiro
    mesa.motor.parar(mesa.t)
    assert mesa.motores(P[2])[-1] == (0, 0)
    assert devolvidos == [mesa.t]


@pytest.mark.parametrize("familia", [PRO, OITO_BITDO])
def test_pro_e_8bitdo_seguem_pelo_no_deles_sem_prazo(
    monkeypatch: pytest.MonkeyPatch, familia: str,
) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: CABO, P[1]: familia})
    with structlog.testing.capture_logs() as linhas:
        mesa.correr(tv.PRAZO_DA_PONTE_S + 1)
    assert any(f and f == g for _u, f, g in mesa.no)
    assert mesa.backend.rumble == []
    assert not [x for x in linhas if "prazo" in x["event"]]
    assert mesa.motor.queda.estados.get(P[1]) != tv.QUEDA_PASSOU_DO_PRAZO


def test_passou_do_prazo_vai_ao_diario_uma_vez_e_a_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.alto._dizer_por_que_sem_ponte(P[0], "o governador do rádio recusou a vaga")
    with structlog.testing.capture_logs() as linhas:
        mesa.correr(tv.PRAZO_DA_PONTE_S - 1)
        assert mesa.motor.queda.estados == {P[0]: tv.QUEDA_NO_MOTOR}
        mesa.correr(5.0)
    avisos = [x for x in linhas if x["event"] == "tato_corpo_pelo_motor_passou_do_prazo"]
    assert len(avisos) == 1
    assert avisos[0]["motivo"] == "o governador do rádio recusou a vaga"
    assert mesa.motor.queda.estados == {P[0]: tv.QUEDA_PASSOU_DO_PRAZO}
    mesa.subir_a_ponte(P[0])
    mesa.correr(0.1)
    assert mesa.motor.queda.estados == {}


def test_a_folga_de_silencio_nao_zera_o_relogio_do_prazo(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    for _ in range(4):
        mesa.correr(4.0)
        mesa.correr(1.0, som=False)
    assert mesa.motor.queda.estados.get(P[0]) == tv.QUEDA_PASSOU_DO_PRAZO


FORMACOES = [
    (COM_PONTE, SEM_PONTE, SEM_PONTE, COM_PONTE),
    (SEM_PONTE, COM_PONTE, COM_PONTE, SEM_PONTE),
    (CABO, SEM_PONTE, SEM_PONTE, SEM_PONTE),
    (CABO, CABO, SEM_PONTE, COM_PONTE),
    (CABO, CABO, CABO, SEM_PONTE),
    (SEM_PONTE, SEM_PONTE, SEM_PONTE, SEM_PONTE),
    (PRO, COM_PONTE, CABO, SEM_PONTE),
    (CABO, OITO_BITDO, SEM_PONTE, COM_PONTE),
]


@pytest.mark.parametrize("mascara", [SONY, XBOX])
@pytest.mark.parametrize("arranjo", FORMACOES)
def test_a_mesa_misturada_em_toda_posicao(
    monkeypatch: pytest.MonkeyPatch, arranjo: tuple[str, ...], mascara: str,
) -> None:
    conexoes = dict(zip(P, arranjo, strict=True))
    if arranjo[0] in (PRO, OITO_BITDO):
        conexoes = dict(reversed(list(conexoes.items())))
    mesa = _Mesa(monkeypatch, conexoes, mascara=mascara)
    mesa.correr(1.0)
    for uniq, via in conexoes.items():
        tocou = bool(mesa.motores(uniq))
        assert tocou == (via in (SEM_PONTE, PRO, OITO_BITDO)), (uniq, via)


@pytest.mark.parametrize("quem", range(4))
def test_queda_e_volta_de_um_com_os_outros_jogando(
    monkeypatch: pytest.MonkeyPatch, quem: int,
) -> None:
    mesa = _Mesa(monkeypatch, dict.fromkeys(P, SEM_PONTE))
    mesa.correr(0.5)
    mesa.subir_a_ponte(P[quem])
    mesa.correr(0.5)
    outros = [u for i, u in enumerate(P) if i != quem]
    assert mesa.motores(P[quem])[-1] == (0, 0)
    assert all(mesa.motores(u)[-1] != (0, 0) for u in outros)
    mesa.alto._pontes.pop(P[quem])
    antes = len(mesa.motores(P[quem]))
    mesa.correr(0.5)
    assert mesa.motores(P[quem])[antes:], "sem a ponte, a queda volta"


def test_na_fila_da_vaga_o_grave_cai_pelo_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.alto._esperando_vaga = frozenset({(P[0], "haptica")})
    mesa.correr(0.5)
    assert mesa.tocadores[P[0]].corpo == [], "o rádio cede, e o tocador não acorda nada"
    assert mesa.motores(P[0])


def test_a_ponte_de_pe_que_cede_a_vez_nao_liga_o_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: COM_PONTE})
    mesa.alto._vaga_da_ponte = MappingProxyType({P[0]: SimpleNamespace(cedendo=True)})
    mesa.correr(0.5)
    assert mesa.motores(P[0]) == []


def test_o_padrao_nos_motores_passa_na_frente_da_queda(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    monkeypatch.setattr(mesa.motor, "segurando", lambda _c: frozenset({P[0]}))
    mesa.correr(0.5)
    assert mesa.motores(P[0]) == []


def test_o_silencio_nao_zera_o_motor_que_o_padrao_segura(monkeypatch: pytest.MonkeyPatch) -> None:
    mesa = _Mesa(monkeypatch, {P[0]: SEM_PONTE})
    mesa.correr(0.5)
    antes = len(mesa.motores(P[0]))
    monkeypatch.setattr(mesa.motor, "segurando", lambda _c: frozenset({P[0]}))
    mesa.correr(tv.SILENCIO_DA_QUEDA_S * 2, som=False)
    assert mesa.motores(P[0])[antes:] == [], "o motor é do padrão enquanto ele segura"
    monkeypatch.setattr(mesa.motor, "segurando", lambda _c: frozenset())
    mesa.correr(0.2, som=False)
    assert mesa.motores(P[0])[antes:] == [], "quem zera o que tocou é o padrão"
    mesa.correr(0.5)
    assert mesa.motores(P[0])[antes:], "a queda volta com o som"


def test_a_chave_do_state_full_diz_quem_esta_pelo_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    from tests.unit.test_o_ganho_da_haptica_tem_dono import BRANCO, PRETO, _Handlers

    h = _Handlers(ativo=None, primario=BRANCO)
    h._sensor_hub = object()  # type: ignore[attr-defined]
    h.daemon._tato_vivo = SimpleNamespace(  # type: ignore[attr-defined]
        queda=SimpleNamespace(estados={PRETO: rm.QUEDA_PASSOU_DO_PRAZO}))
    monkeypatch.setattr(h, "_adaptadores_do_radio", lambda _u: {}, raising=False)
    entradas: list[dict[str, Any]] = [{"uniq": BRANCO, "transport": "usb"},
                                      {"uniq": PRETO, "transport": "bt"}]
    h._merge_radio(entradas)
    assert [e["corpo_pelo_motor"] for e in entradas] == [None, rm.QUEDA_PASSOU_DO_PRAZO]


def _linha(n: int, lugar: str, **campos: Any) -> dict[str, Any]:
    return {"id": f"aabbcc0000{n:02x}", "tipo": "controle", "lugar": lugar, "pede_ponte": True,
            "ponte": None, "rotulo": f"Player {n}", "nome": "", "esperando": False,
            "hz_mov": 150.0, "sinal": -40, "mic": False, **campos}


def _de_fora(n: int, lugar: str) -> dict[str, Any]:
    """Pro e 8BitDo na forma que `_aparelhos_da_cena` monta: vêm do BlueZ, como «gamepad»."""
    return {"id": f"aabbcc0000{n:02x}", "tipo": "gamepad", "lugar": lugar, "nome": "Pro Controller",
            "rotulo": "Pro Controller", "pareado": True, "esperando": False, "fixo": False}


def _sala(*aparelhos: dict[str, Any], lugares: tuple[str, ...] = (A,),
          hub: tuple[str, ...] = ()) -> dict[str, Any]:
    return {"aparelhos": list(aparelhos),
            "lugares": [{"id": e, "nome": "", "entrada": "Entrada", "lugar": e, "hub": e in hub}
                        for e in lugares]}


def test_a_mira_abaixo_do_piso_diz_que_o_adaptador_esta_cheio() -> None:
    linhas = [_linha(i, A, hz_mov=117.0, ponte="som" if i < 2 else None) for i in range(4)]
    cena = _sala(*linhas, hub=(A,))
    d = a08._diagnostico_do_controle(linhas[3], linhas, cena, False, 0.0)
    assert (d.nivel, d.causa) == (rm.NIVEL_ENGASGA, rm.CAUSA_ADAPTADOR_CHEIO)
    assert a08.dica_do_movimento(d.nivel, d.causa) == "Movimento por segundo: adaptador cheio"


def test_sem_sinal_lido_a_conta_ainda_diz_a_causa() -> None:
    linhas = [_linha(i, A, hz_mov=117.0, sinal=None, ponte="som" if i < 2 else None)
              for i in range(4)]
    cena = _sala(*linhas, hub=(A,))
    d = a08._diagnostico_do_controle(linhas[0], linhas, cena, False, 0.0)
    assert d.causa == rm.CAUSA_ADAPTADOR_CHEIO


def test_o_controle_de_fora_divide_a_entrada_na_conta_da_mira() -> None:
    linhas = [_linha(i, A, hz_mov=117.0, ponte="som" if i < 2 else None) for i in range(3)]
    cena = _sala(*linhas, _de_fora(3, A), hub=(A,))
    d = a08._diagnostico_do_controle(linhas[2], linhas, cena, False, 0.0)
    assert d.causa == rm.CAUSA_ADAPTADOR_CHEIO


def test_a_cena_real_declara_quem_pede_ponte_e_quem_e_de_fora(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(a08, "_tipo_que_o_usuario_disse", lambda _e: "")
    uniq = "aa:bb:cc:00:00:21"
    st = {"controllers": [{"uniq": uniq, "transport": "bt", "adaptador": A,
                           "corpo_pelo_motor": rm.QUEDA_PASSOU_DO_PRAZO}]}
    pro = SimpleNamespace(endereco="aa:bb:cc:00:00:22", adaptador="/org/bluez/hci0", conectado=True,
                          modalias="usb:v057Ep2009d0001", icone="input-gaming", classe=None,
                          nome="Pro Controller", pareado=True)
    ctx = SimpleNamespace(mesa=[])
    end = a08.nome_do_jogador.mac(A)
    dual, fora = a08._aparelhos_da_cena(ctx, st, {}, [], (pro,), {"/org/bluez/hci0": end}, [end])
    assert (dual["tipo"], dual["pede_ponte"]) == ("controle", True)
    assert dual["pelo_motor"] == rm.QUEDA_PASSOU_DO_PRAZO
    assert fora["tipo"] in a08.TIPOS_QUE_DIVIDEM_O_AR
    assert not fora.get("pede_ponte")


def test_quem_cabe_na_conta_e_engasga_nao_culpa_o_adaptador() -> None:
    linhas = [_linha(i, A, hz_mov=90.0, ponte="som") for i in range(2)]
    d = a08._diagnostico_do_controle(linhas[0], linhas, _sala(*linhas), False, 0.0)
    assert d.causa == rm.CAUSA_INTERFERENCIA


def test_a_falta_nao_aparece_sem_a_escolha_de_quem_usa() -> None:
    cena = _sala(*(_linha(i, A) for i in range(4)))
    assert a08.OPCAO_DA_FALTA == ""
    assert a08.com_a_falta(cena) is cena
    assert 'class="falta"' not in a08.campos_da_secao(cena)["radio-sala"]


def test_a_linha_fala_quantos_adaptadores_faltam(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(a08, "OPCAO_DA_FALTA", "a")
    cena = _sala(*(_linha(i, A, ponte="som" if i < 2 else None) for i in range(4)))
    sala = a08.campos_da_secao(cena)["radio-sala"]
    assert sala.count('class="falta"') == 2
    assert ">Falta 1 adaptador<" in sala
    assert "pedem 2 adaptadores" in sala


@pytest.mark.parametrize("letra", sorted(a08.FALAS_DA_FALTA))
def test_cada_opcao_conta_os_adaptadores(letra: str) -> None:
    cena = _sala(*(_linha(i, A) for i in range(4)))
    falas = a08.com_a_falta(cena, letra)["falas_da_falta"]
    assert len(falas) == 2
    assert all("1" in fala for fala, _dica in falas.values())


def test_quem_cabe_noutro_adaptador_ouve_o_nome_e_o_gesto_da_mao() -> None:
    cena = _sala(*(_linha(i, A) for i in range(3)), lugares=(A, B))
    falas = a08.com_a_falta(cena, "a")["falas_da_falta"]
    [(fala, dica)] = falas.values()
    assert fala.startswith("Cabe em ")
    assert "PS + Create" in dica


def test_o_adaptador_varrendo_e_o_ultimo_destino() -> None:
    cena = _sala(*(_linha(i, A) for i in range(3)), lugares=(A, B, C))
    cena["lugares"][1]["varrendo"] = True
    assert [a.destino for a in a08.reparticao_da_cena(cena).mudam] == [C]


def test_todo_controle_com_ponte_nao_recebe_frase() -> None:
    cena = _sala(_linha(0, A), _linha(1, A), _linha(2, B), _linha(3, B), lugares=(A, B))
    assert a08.com_a_falta(cena, "a")["falas_da_falta"] == {}


def test_o_pro_divide_o_ar_e_nao_ouve_falta() -> None:
    cena = _sala(_linha(0, A), _linha(1, A), _de_fora(2, A), _de_fora(3, A), hub=(A,))
    falas = a08.com_a_falta(cena, "a")["falas_da_falta"]
    assert list(falas) == ["aabbcc000001"]


def test_o_cabo_nao_conta_na_falta() -> None:
    cena = _sala(_linha(0, A), _linha(1, A), _linha(2, A, usb=True), _linha(3, A, usb=True))
    assert a08.com_a_falta(cena, "a")["falas_da_falta"] == {}


def test_a_porta_ruim_pede_porta_direta(monkeypatch: pytest.MonkeyPatch) -> None:
    cena = _sala(_linha(0, A), _linha(1, A), _de_fora(2, A), _de_fora(3, A), hub=(A,))
    [(fala, _dica)] = a08.com_a_falta(cena, "a")["falas_da_falta"].values()
    assert fala == a08.FALA_DA_PORTA


def test_a_tela_le_o_prazo_da_ponte() -> None:
    cena = _sala(_linha(0, A, pelo_motor=rm.QUEDA_PASSOU_DO_PRAZO))
    assert a08.com_a_falta(cena, "a")["falas_da_falta"] == {
        "aabbcc000000": (a08.FALA_DO_PRAZO, a08.DICA_DO_PRAZO)}


def test_toda_contagem_da_aba_sai_do_mesmo_n_max(monkeypatch: pytest.MonkeyPatch) -> None:
    cena = _sala(*(_linha(i, A, ponte="som" if i == 0 else None) for i in range(4)), hub=(A,))
    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    campos = a08.campos_da_secao(cena)
    assert a08.n_max_do_lugar(cena, A) == 1
    assert "1 de 1" in campos["radio-sala"]
    assert "de 2" not in campos["radio-sala"]
    assert campos["radio-sala"].count('class="vaga-ponte') == 1


def test_o_painel_de_mover_conta_pelo_mesmo_n_max(monkeypatch: pytest.MonkeyPatch) -> None:
    cena = _sala(*(_linha(i, A, ponte="som" if i == 0 else None) for i in range(4)),
                 _linha(4, B), lugares=(A, B), hub=(A,))
    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    assert "com som 1 de 1" in a08.campos_da_secao(cena)["radio-moldes"]


def test_quem_ainda_espera_nao_divide_o_ar() -> None:
    linhas = [_linha(i, A, ponte="som") for i in range(2)]
    cena = _sala(*linhas, _linha(2, A, esperando=True), _linha(3, A, esperando=True), hub=(A,))
    assert len(a08._controles_no_radio(cena, A)) == 2
    assert a08._a_conta_fecha(cena, A)


def test_o_n_max_da_tela_sai_do_dono_e_da_porta(monkeypatch: pytest.MonkeyPatch) -> None:
    cena = _sala(*(_linha(i, A, ponte="som" if i == 0 else None) for i in range(4)), hub=(A,))
    assert a08.n_max_do_lugar(cena, A) == rm.N_MAX_PONTES
    monkeypatch.setattr(rm, "N_MAX_PELA_CAPACIDADE", True)
    assert a08.n_max_do_lugar(cena, A) == 1
    linha = a08.html_da_linha(cena["aparelhos"][0], cena)
    assert "Som 1 de 1" in linha
