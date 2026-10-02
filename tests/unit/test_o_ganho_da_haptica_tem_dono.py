"""O ganho da háptica por áudio tem dono — O-GANHO-DA-HAPTICA-TEM-DONO-01, 29/09/2026."""

from __future__ import annotations

import ast
import functools
import inspect
import math
import textwrap
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ganho_da_haptica import (
    VOLUME_NORMAL,
    GanhoDaHaptica,
    linear_do_cru,
    placas_do_piso,
)
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations.alto_falante_bt import garantir_motores_audiveis
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.schema import (
    HAPTICA_PCT_MAX,
    HAPTICA_PCT_PADRAO,
    ControllerOverrides,
    ControllerRumbleOverride,
    MatchAny,
    Profile,
    pct_da_haptica,
)
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale
from tests.unit import test_no_modo_xbox_a_haptica_fina as xbox
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import (
    BRANCO,
    PRETO,
    _grava_ipc,
    _Handlers,
)

_SONY = "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller"
PLACA_BRANCO = f"{_SONY}-00.analog-surround-40"
PLACA_PRETO = f"{_SONY}-00.2.analog-surround-40"
ENDPOINT = "alsa_output.usb-HEFESTO-lugar1-00.analog-surround-40"


def _cru_do_linear(fator: float) -> int:
    return round(VOLUME_NORMAL * (max(fator, 0.0) ** (1.0 / 3.0)))


def _forma(texto: str) -> str:
    if texto.endswith("dB"):
        return "db"
    if texto.endswith("%"):
        return "pct"
    if "." in texto:
        return "linear"
    return "cru"


def _cru_do_texto(texto: str) -> int:
    """As quatro formas do ``pactl``: cru, fator linear, ``%`` (cúbico) e dB."""
    forma = _forma(texto)
    if forma == "db":
        return _cru_do_linear(10 ** (float(texto[:-2]) / 20.0))
    if forma == "pct":
        return round(VOLUME_NORMAL * float(texto[:-1]) / 100.0)
    if forma == "linear":
        return _cru_do_linear(float(texto))
    return int(texto)


class ServidorDeMentira:
    """O ``pactl`` do lado do servidor: lista e escreve o volume cru por canal."""

    def __init__(self, sinks: dict[str, list[int]]) -> None:
        self.sinks = {n: list(v) for n, v in sinks.items()}
        self.escritas: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "set-sink-volume"]:
            nome, vols = argv[2], argv[3:]
            if len({_forma(v) for v in vols}) > 1:
                return None
            self.escritas.append(list(argv))
            self.sinks[nome] = [_cru_do_texto(v) for v in vols]
            return ""
        if argv[:3] == ["pactl", "list", "sinks"] and len(argv) == 3:
            blocos = []
            for nome, vols in self.sinks.items():
                canais = ["front-left", "front-right", "rear-left", "rear-right"]
                partes = [
                    f"{c}: {v} / {round(100 * v / VOLUME_NORMAL)}% / "
                    f"{20 * math.log10(max(linear_do_cru(v), 1e-9)):.2f} dB"
                    for c, v in zip(canais, vols, strict=False)
                ]
                blocos.append(f"Sink #1\n\tName: {nome}\n\tVolume: {',   '.join(partes)}\n")
            return "\n".join(blocos)
        if argv[:2] == ["pactl", "list"] and "short" in argv:
            return "\n".join(
                f"{i}\t{n}\tmodule-alsa-card.c\ts16le 4ch 48000Hz\tRUNNING"
                for i, n in enumerate(self.sinks, start=1)
            )
        return None

    def traseiros(self, nome: str) -> list[float]:
        return [round(linear_do_cru(v), 3) for v in self.sinks[nome][2:4]]

    def frente(self, nome: str) -> list[int]:
        return self.sinks[nome][:2]


def _servidor() -> ServidorDeMentira:
    cheio = [VOLUME_NORMAL] * 4
    quarenta = [26214, 26214, VOLUME_NORMAL, VOLUME_NORMAL]
    return ServidorDeMentira({PLACA_BRANCO: quarenta, PLACA_PRETO: list(cheio), ENDPOINT: cheio})


def _placa_de(uniq: str, _mesa: Any) -> str:
    return {BRANCO: PLACA_BRANCO, PRETO: PLACA_PRETO}.get(uniq, "")


def _dono(**pcts: int) -> GanhoDaHaptica:
    """Um dono lido de um perfil com ``{BRANCO: pct, PRETO: pct}``."""
    dono = GanhoDaHaptica()
    nomes = {"branco": BRANCO, "preto": PRETO}
    dono.ler_do_perfil({
        nomes[k]: ControllerOverrides(rumble=ControllerRumbleOverride(haptica_pct=v))
        for k, v in pcts.items()
    })
    return dono


class TestOServidorDeMentiraNaoEMaisFrouxoQueOReal:
    def test_quarenta_por_cento_guarda_o_numero_medido_em_29_09(self) -> None:
        """``40%`` é -23,88 dB: o WirePlumber guardou 0,063997 linear na placa dela."""
        srv = _servidor()
        srv(["pactl", "set-sink-volume", PLACA_PRETO, "40%", "40%", "40%", "40%"])
        guardado = linear_do_cru(srv.sinks[PLACA_PRETO][0])
        assert round(guardado, 6) == pytest.approx(0.063997, abs=2e-6)

    def test_as_quatro_formas(self) -> None:
        srv = _servidor()
        srv(["pactl", "set-sink-volume", PLACA_PRETO, "1.5", "1.5", "1.5", "1.5"])
        assert srv.traseiros(PLACA_PRETO) == [1.5, 1.5]
        srv(["pactl", "set-sink-volume", PLACA_PRETO, "3.52dB", "3.52dB", "3.52dB", "3.52dB"])
        assert srv.traseiros(PLACA_PRETO) == [1.5, 1.5]
        srv(["pactl", "set-sink-volume", PLACA_PRETO, "150%", "150%", "150%", "150%"])
        assert srv.traseiros(PLACA_PRETO) == [3.375, 3.375]

    def test_formas_misturadas_sao_recusadas(self) -> None:
        srv = _servidor()
        misturado = ["pactl", "set-sink-volume", PLACA_PRETO, "65536", "65536", "1.5", "1.5"]
        assert srv(misturado) is None


class TestOCampo:
    def test_sem_opiniao_vale_o_padrao(self) -> None:
        assert pct_da_haptica(None) == HAPTICA_PCT_PADRAO
        assert pct_da_haptica(ControllerRumbleOverride()) == HAPTICA_PCT_PADRAO
        assert pct_da_haptica(ControllerRumbleOverride(haptica_pct=0)) == 0

    @pytest.mark.parametrize("valor", [-1, HAPTICA_PCT_MAX + 1])
    def test_fora_da_faixa_morre_na_borda(self, valor: int) -> None:
        with pytest.raises(ValueError, match="haptica_pct"):
            ControllerRumbleOverride(haptica_pct=valor)

    def test_a_faixa_passa_de_cem(self) -> None:
        assert ControllerRumbleOverride(haptica_pct=HAPTICA_PCT_MAX).haptica_pct == 200

    def test_o_perfil_antigo_nao_ganha_a_chave(self) -> None:
        """Régua 6: o ``load → save`` de um perfil sem ``haptica_pct`` sai igual."""
        velho = ControllerRumbleOverride.model_validate({"motor_forte_pct": 50})
        assert "haptica_pct" not in velho.model_dump()
        assert "haptica_pct" not in velho.model_dump(mode="json")
        mexeu = ControllerRumbleOverride.model_validate({"haptica_pct": 180})
        assert mexeu.model_dump(mode="json")["haptica_pct"] == 180


class TestACaboAPlaca:
    def test_a_placa_recebe_fator_linear(self) -> None:
        """Régua 1: 150 % vira 1,5 no servidor, e não 3,375 (o ``%`` é cúbico)."""
        srv = _servidor()
        dono = _dono(branco=150)
        com_dono = dono.escrever_nas_placas(
            [BRANCO], [BRANCO], list(srv.sinks), runner=srv, placa_de=_placa_de
        )
        assert com_dono == {PLACA_BRANCO}
        assert srv.traseiros(PLACA_BRANCO) == [1.5, 1.5]
        assert srv.frente(PLACA_BRANCO) == [26214, 26214], "a frente é dela e não se toca"
        db = 20 * math.log10(srv.traseiros(PLACA_BRANCO)[0])
        assert db == pytest.approx(3.52, abs=0.01)

    def test_sem_opiniao_vale_o_padrao_na_placa(self) -> None:
        srv = _servidor()
        GanhoDaHaptica().escrever_nas_placas(
            [BRANCO], [BRANCO], list(srv.sinks), runner=srv, placa_de=_placa_de
        )
        assert srv.traseiros(PLACA_BRANCO) == [HAPTICA_PCT_PADRAO / 100] * 2

    def test_o_piso_nao_briga_com_o_ganho(self) -> None:
        """Régua 2: ``haptica_pct=50``, duas voltas → -6,02 dB nos traseiros."""
        srv = _servidor()
        dono = _dono(branco=50)
        for _volta in range(2):
            lidos = af.sinks_com_motores(srv)
            com_dono = dono.escrever_nas_placas(
                [BRANCO], [BRANCO], lidos, runner=srv, placa_de=_placa_de
            )
            for sink in placas_do_piso(lidos, com_dono):
                garantir_motores_audiveis(sink, srv)
        assert srv.traseiros(PLACA_BRANCO) == [0.5, 0.5]
        assert 20 * math.log10(0.5) == pytest.approx(-6.02, abs=0.01)

    def test_a_volta_do_subsystem_pula_a_placa_com_dono(self) -> None:
        """A volta de verdade passa pelo ``placas_do_piso`` (o que a régua 2 reproduz)."""
        from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem

        fonte = textwrap.dedent(inspect.getsource(AltoFalanteSubsystem._casar_as_pontes))
        chamadas = [
            n for n in ast.walk(ast.parse(fonte))
            if isinstance(n, ast.For) and isinstance(n.iter, ast.Call)
            and getattr(n.iter.func, "id", "") == "placas_do_piso"
        ]
        assert chamadas, "a varredura do piso tem de pular as placas com dono"
        assert any(
            isinstance(c, ast.Call) and getattr(c.func, "id", "") == "garantir_motores_audiveis"
            for c in ast.walk(chamadas[0])
        )

    def test_o_ganho_vai_a_placa_daquele_controle_e_so_a_ela(self) -> None:
        """Régua 3: dois controles, 50 e 150; o endpoint fica em 0 dB."""
        srv = _servidor()
        dono = _dono(branco=50, preto=150)
        dono.escrever_nas_placas(
            [BRANCO, PRETO], [BRANCO, PRETO], list(srv.sinks), runner=srv, placa_de=_placa_de
        )
        assert srv.traseiros(PLACA_BRANCO) == [0.5, 0.5]
        assert srv.traseiros(PLACA_PRETO) == [1.5, 1.5]
        assert srv.traseiros(ENDPOINT) == [1.0, 1.0]

    def test_o_endpoint_nunca_e_placa_com_dono(self) -> None:
        srv = _servidor()
        com_dono = _dono(branco=180).escrever_nas_placas(
            [BRANCO], [BRANCO], list(srv.sinks), runner=srv, placa_de=lambda _u, _m: ENDPOINT
        )
        assert com_dono == set()
        assert srv.traseiros(ENDPOINT) == [1.0, 1.0]

    def test_desligada_cala_os_traseiros(self) -> None:
        srv = _servidor()
        _dono(branco=0).escrever_nas_placas(
            [BRANCO], [BRANCO], list(srv.sinks), runner=srv, placa_de=_placa_de
        )
        assert srv.traseiros(PLACA_BRANCO) == [0.0, 0.0]

    def test_so_escreve_quando_difere(self) -> None:
        srv = _servidor()
        dono = _dono(branco=150)
        for _ in range(3):
            dono.escrever_nas_placas(
                [BRANCO], [BRANCO], list(srv.sinks), runner=srv, placa_de=_placa_de
            )
        assert len(srv.escritas) == 1

    def test_o_stop_devolve_a_placa(self) -> None:
        """Régua 8: o ganho não sobrevive ao Hefesto — 1,5 volta a 1,0."""
        srv = _servidor()
        dono = _dono(branco=150)
        dono.escrever_nas_placas(
            [BRANCO], [BRANCO], list(srv.sinks), runner=srv, placa_de=_placa_de
        )
        dono.devolver_as_placas(runner=srv)
        assert srv.traseiros(PLACA_BRANCO) == [1.0, 1.0]
        assert srv.frente(PLACA_BRANCO) == [26214, 26214]

    def test_o_stop_do_subsystem_chama_a_devolucao(self) -> None:
        from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem

        assert "GANHO.devolver_as_placas" in inspect.getsource(AltoFalanteSubsystem.stop)


def _meia_escala(n: int) -> bytes:
    """PCM 4 canais s16le com os traseiros num nível CONSTANTE de 16384."""
    quadro = (0).to_bytes(2, "little", signed=True) * 2 + (16384).to_bytes(
        2, "little", signed=True
    ) * 2
    return (quadro * (n // len(quadro) + 1))[:n]


def _bloco(ganho: Any) -> bytes:
    bomba = af.BombaDeSomPeloRadio(
        arranjo=af.ARRANJO_HAPTICA_032,
        fonte=lambda n: bytes(n),
        fonte_haptica=_meia_escala,
        ganho_da_haptica=ganho,
    )
    bloco = bomba._bloco_haptico()
    assert bloco is not None
    return bloco


class TestORadioOConversor:
    def test_duzentos_saem_127_e_cem_saem_64(self) -> None:
        """Régua 4: nível constante (e não seno: o filtro tiraria do pico)."""
        assert set(_bloco(2.0)) == {127}
        assert set(_bloco(1.0)) == {64}

    def test_o_ganho_e_perguntado_ao_dono_por_controle(self) -> None:
        """A ponte recebe o chamável do dono (``functools.partial(GANHO.fator, uniq)``)."""
        dono = _dono(branco=200, preto=100)
        assert set(_bloco(functools.partial(dono.fator, BRANCO))) == {127}
        assert set(_bloco(functools.partial(dono.fator, PRETO))) == {64}
        assert set(_bloco(functools.partial(dono.fator, "aa:bb:cc:00:00:99"))) == {95}

    def test_desligada_sai_silencio(self) -> None:
        assert set(_bloco(0.0)) == {0}

    def test_a_ponte_repassa_o_ganho_a_bomba(self) -> None:
        fonte = inspect.getsource(af.PonteDeSomPorRadio.subir)
        assert "ganho_da_haptica=self.ganho_da_haptica" in fonte
        from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem

        assert "ganho_da_haptica=functools.partial(GANHO.fator, uniq)" in inspect.getsource(
            AltoFalanteSubsystem._casar_as_pontes
        )


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


class TestOPedido:
    def test_grava_no_perfil_e_o_dono_rele_no_mesmo_ato(
        self, perfis: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O arraste a 180 cai no disco, relido pelo esquema, e o dono já responde 180."""
        from hefesto_dualsense4unix.daemon import ganho_da_haptica as mod

        dono = GanhoDaHaptica()
        monkeypatch.setattr(mod, "GANHO", dono)
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, haptica_pct=180)

        assert corpo["status"] == "ok" and corpo["gravado"] is True
        assert corpo["haptica_pct"] == 180
        dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[BRANCO]
        assert dele.rumble is not None and dele.rumble.haptica_pct == 180
        assert "motor_forte_pct" not in dele.rumble.model_fields_set
        assert dono.pct(BRANCO) == 180

    def test_o_padrao_nao_ocupa_chave(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        _grava_ipc(h, uniq=BRANCO, haptica_pct=0)
        corpo = _grava_ipc(h, uniq=BRANCO, haptica_pct=HAPTICA_PCT_PADRAO)
        assert corpo["haptica_pct"] == HAPTICA_PCT_PADRAO
        dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {}).get(BRANCO)
        assert dele is None or dele.rumble is None or (
            "haptica_pct" not in dele.rumble.model_fields_set
        )

    def test_fora_da_faixa_e_recusado_sem_gravar(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="haptica_pct"):
            _grava_ipc(h, uniq=BRANCO, haptica_pct=HAPTICA_PCT_MAX + 1)
        assert not (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})

    def test_a_barra_dos_motores_segue_com_teto_cem(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError):
            _grava_ipc(h, uniq=BRANCO, forte_pct=150)

    def test_a_ponte_do_app_leva_o_campo(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        pedidos: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(
            ipc_bridge, "_corpo_do_daemon", lambda m, p: pedidos.append((m, p)) or {"status": "ok"}
        )
        ok, _ = ipc_bridge.rumble_motores_set(uniq=BRANCO, haptica_pct=175)
        assert ok and pedidos == [("rumble.motores.set", {"haptica_pct": 175, "uniq": BRANCO})]


# 5. O que o `state_full` devolve, por controle


class TestOStateFull:
    def test_cada_controle_diz_o_seu_ganho_e_se_o_hefesto_alcanca(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon import ganho_da_haptica as mod
        from hefesto_dualsense4unix.daemon.subsystems import rumble

        monkeypatch.setattr(mod, "GANHO", _dono(branco=180))
        monkeypatch.setattr(rumble, "modo_nativo_manda_nos_motores", lambda _d: True)
        h = _Handlers(ativo=None, primario=BRANCO)
        h._sensor_hub = object()  # type: ignore[attr-defined]
        monkeypatch.setattr(h, "_adaptadores_do_radio", lambda _u: {}, raising=False)
        entries: list[dict[str, Any]] = [
            {"uniq": BRANCO, "transport": "usb"},
            {"uniq": PRETO, "transport": "bt"},
        ]
        h._merge_radio(entries)
        assert entries[0]["haptica_pct"] == 180 and entries[0]["haptica_alcanca"] is True
        assert entries[1]["haptica_pct"] == HAPTICA_PCT_PADRAO
        assert entries[1]["haptica_alcanca"] is False, (
            "Nativo pelo rádio sem a ponte: o jogo escreve no hidraw e o ganho não alcança"
        )


class TestALeituraDoPerfil:
    def test_o_perfil_fora_do_nome_do_arquivo_e_lido_pelo_carregador(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O perfil que só o `load_profile` acha: lido uma vez, e de novo quando o gravador pede."""
        from types import SimpleNamespace

        from hefesto_dualsense4unix.profiles import manager

        cargas: list[str] = []
        perfil = SimpleNamespace(controllers={
            BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(haptica_pct=60))
        })

        def _carregar(nome: str) -> Any:
            cargas.append(nome)
            return perfil

        monkeypatch.setattr(loader_module, "perfil_em_disco", lambda _n: None)
        monkeypatch.setattr(loader_module, "load_profile", _carregar)
        monkeypatch.setattr(manager, "nome_do_perfil_que_grava", lambda _a: "Estilo")
        daemon = SimpleNamespace(store=SimpleNamespace(active_profile="Estilo"))
        dono = GanhoDaHaptica()
        dono.ler_do_daemon(daemon)
        dono.ler_do_daemon(daemon)
        assert dono.pct(BRANCO) == 60 and cargas == ["Estilo"]
        dono.ler_do_daemon(daemon, forcar=True)
        assert cargas == ["Estilo", "Estilo"]


def _haptica_do_p1_em(pct: int, monkeypatch: pytest.MonkeyPatch, uniq: str) -> None:
    """O perfil diz ``pct`` para ``uniq``; a volta relê o mesmo (sem disco)."""
    from hefesto_dualsense4unix.daemon import ganho_da_haptica

    dono = ganho_da_haptica.GANHO
    perfil = {uniq: ControllerOverrides(rumble=ControllerRumbleOverride(haptica_pct=pct))}
    monkeypatch.setattr(dono, "ler_do_daemon", lambda *_a, **_k: dono.ler_do_perfil(perfil))
    dono.ler_do_perfil(perfil)


mesa = xbox.mesa
mundo = xbox.mundo


@pytest.fixture
def xbox_mundo(mundo: Any, monkeypatch: pytest.MonkeyPatch) -> Any:
    """O mundo do Xbox com o dono do ganho zerado, sem vazar de outra régua."""
    from hefesto_dualsense4unix.daemon import ganho_da_haptica

    monkeypatch.setattr(ganho_da_haptica.GANHO, "_escritos", {})
    return mundo


@pytest.mark.parametrize("transporte", ["cabo", "radio"])
def test_no_xbox_a_haptica_em_zero_devolve_o_rumble_ao_hid(
    xbox_mundo: Any, monkeypatch: pytest.MonkeyPatch, transporte: str
) -> None:
    """Com a háptica do P1 em 0, o rumble do pad Xbox volta aos motores do HID."""
    m = xbox_mundo
    p1 = xbox._QUATRO[0]
    controles = (
        xbox._no_cabo_os_quatro(m) if transporte == "cabo" else xbox._no_radio_os_quatro(m)
    )
    m.mesa.volta(*controles)
    m.rumble(p1, 100, 200)
    m.mesa.volta(*controles)
    assert m.backend.do(p1)[-1] == (0, 0), "o caminho da háptica não abriu"
    _haptica_do_p1_em(0, monkeypatch, p1)
    m.mesa.volta(*controles)
    assert m.backend.do(p1)[-1] == (100, 200), "com a háptica em 0 o HID não voltou a levar"
    assert m.rumble(p1, 40, 90) == (40, 90)
    assert m.backend.do(p1)[-1] == (40, 90)
    assert m.tocador(p1).nivel == (0, 0), "o tocador segue somando com a háptica em 0"


def _mesa_com_orcamento(orcamento: str | None) -> Any:
    """O daemon na forma que o funil do rumble lê: ``config.orcamento_da_mesa``."""
    from types import SimpleNamespace

    return SimpleNamespace(config=SimpleNamespace(orcamento_da_mesa=lambda: orcamento))


class TestAEconomiaCortaAHaptica:
    def test_na_economia_o_dono_responde_o_teto_nas_duas_portas(self) -> None:
        """Régua 7: ``haptica_pct=150`` vale 0,3 na Economia, e 1,5 no Balanceado."""
        dono = _dono(branco=150)
        dono.ler_o_teto(_mesa_com_orcamento("economia"))
        assert dono.fator(BRANCO) == pytest.approx(0.3)
        assert dono.pct(BRANCO) == 150, "o teto é leitura: o que ela escolheu não muda"
        assert dono.pct_que_vale(BRANCO) == 30
        srv = _servidor()
        dono.escrever_nas_placas([BRANCO], [BRANCO], [PLACA_BRANCO], runner=srv,
                                 placa_de=_placa_de)
        assert srv.traseiros(PLACA_BRANCO) == [0.3, 0.3]
        assert set(_bloco(functools.partial(dono.fator, BRANCO))) == {19}

        dono.ler_o_teto(_mesa_com_orcamento("balanceado"))
        assert dono.fator(BRANCO) == pytest.approx(1.5)
        dono.escrever_nas_placas([BRANCO], [BRANCO], [PLACA_BRANCO], runner=srv,
                                 placa_de=_placa_de)
        assert srv.traseiros(PLACA_BRANCO) == [1.5, 1.5]

    def test_o_teto_e_min_e_nunca_produto(self) -> None:
        """Abaixo do teto, o ganho passa inteiro: 20 % na Economia é 0,2, e não 0,06."""
        dono = _dono(branco=20)
        dono.ler_o_teto(_mesa_com_orcamento("economia"))
        assert dono.fator(BRANCO) == pytest.approx(0.2)

    def test_o_teto_e_relido_com_o_perfil_a_cada_volta(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A volta do som e o pedido releem os dois juntos (``ler_do_daemon``)."""
        from types import SimpleNamespace

        from hefesto_dualsense4unix.profiles import manager

        perfil = SimpleNamespace(controllers={
            BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(haptica_pct=150))
        })
        monkeypatch.setattr(loader_module, "perfil_em_disco", lambda _n: perfil)
        monkeypatch.setattr(manager, "nome_do_perfil_que_grava", lambda _a: "Estilo")
        orcamento = {"agora": "economia"}
        daemon = SimpleNamespace(
            store=SimpleNamespace(active_profile="Estilo"),
            config=SimpleNamespace(orcamento_da_mesa=lambda: orcamento["agora"]),
        )
        dono = GanhoDaHaptica()
        dono.ler_do_daemon(daemon)
        assert dono.fator(BRANCO) == pytest.approx(0.3)
        orcamento["agora"] = None
        dono.ler_do_daemon(daemon)
        assert dono.fator(BRANCO) == pytest.approx(1.5)

    def test_o_state_full_diz_o_que_vale_ao_lado_do_que_ela_escolheu(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from hefesto_dualsense4unix.daemon import ganho_da_haptica as mod

        dono = _dono(branco=150)
        dono.ler_o_teto(_mesa_com_orcamento("economia"))
        monkeypatch.setattr(mod, "GANHO", dono)
        h = _Handlers(ativo=None, primario=BRANCO)
        h._sensor_hub = object()  # type: ignore[attr-defined]
        monkeypatch.setattr(h, "_adaptadores_do_radio", lambda _u: {}, raising=False)
        entries: list[dict[str, Any]] = [{"uniq": BRANCO, "transport": "usb"}]
        h._merge_radio(entries)
        assert entries[0]["haptica_pct"] == 150
        assert entries[0]["haptica_vale_pct"] == 30

    def test_a_economia_de_um_controle_corta_a_haptica_dele_e_so_a_dele(self) -> None:
        """O botão de economia da linha do controle corta a háptica DAQUELE controle."""
        from types import SimpleNamespace

        from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
        from hefesto_dualsense4unix.profiles import schema

        declaracao = SimpleNamespace(
            orcamento=SimpleNamespace(teto=None),
            controles={norm_mac(BRANCO): SimpleNamespace(economia=True)},
        )
        schema.registrar_declaracao_da_mesa(lambda: declaracao)
        try:
            dono = _dono(branco=150, preto=150)
            dono.ler_o_teto(_mesa_com_orcamento(None))
            assert dono.fator(BRANCO) == pytest.approx(0.3)
            assert dono.pct_que_vale(BRANCO) == 30
            assert dono.pct(BRANCO) == 150, "o teto é leitura: o que ela escolheu não muda"
            assert dono.fator(PRETO) == pytest.approx(1.5), "a economia é DAQUELE controle"
            srv = _servidor()
            dono.escrever_nas_placas([BRANCO], [BRANCO], [PLACA_BRANCO], runner=srv,
                                     placa_de=_placa_de)
            assert srv.traseiros(PLACA_BRANCO) == [0.3, 0.3]
            assert set(_bloco(functools.partial(dono.fator, BRANCO))) == {19}
            declaracao.controles = {}
            dono.ler_o_teto(_mesa_com_orcamento(None))
            assert dono.fator(BRANCO) == pytest.approx(1.5)
        finally:
            schema.registrar_declaracao_da_mesa(None)

    def test_a_luz_no_ar_do_state_full_e_a_do_subsystem_do_som(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O ``haptica_no_ar`` de cada controle é o que o subsystem do som responde.

        O controle desconectado não pergunta, e o subsystem que levanta não
        derruba o ``state_full``: a luz fica apagada.

        MORDIDA: em ``_merge_radio``, escreva ``False`` no lugar do ``no_ar`` →
        a luz do branco não acende, e reprova.
        """
        from types import SimpleNamespace

        from hefesto_dualsense4unix.daemon import ganho_da_haptica as mod

        monkeypatch.setattr(mod, "GANHO", _dono(branco=150))
        perguntas: list[str] = []

        def no_ar(uniq: str) -> bool:
            perguntas.append(uniq)
            if uniq == PRETO:
                raise RuntimeError("o ouvido caiu")
            return uniq == BRANCO

        h = _Handlers(ativo=None, primario=BRANCO)
        h._sensor_hub = object()  # type: ignore[attr-defined]
        h.daemon._alto_falante_subsystem = SimpleNamespace(haptica_no_ar=no_ar)  # type: ignore[attr-defined]
        monkeypatch.setattr(h, "_adaptadores_do_radio", lambda _u: {}, raising=False)
        entries: list[dict[str, Any]] = [
            {"uniq": BRANCO, "transport": "usb"},
            {"uniq": PRETO, "transport": "bt"},
            {"uniq": "aa:bb:cc:00:00:09", "transport": "bt", "connected": False},
        ]
        h._merge_radio(entries)
        assert [e["haptica_no_ar"] for e in entries] == [True, False, False]
        assert "aa:bb:cc:00:00:09" not in perguntas, "o desconectado não pergunta"


@pytest.fixture
def sala_do_radio(monkeypatch: pytest.MonkeyPatch) -> Any:
    from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import Mesa

    m = Mesa(monkeypatch)
    yield m
    m.fechar()


def _ganho_fixo(monkeypatch: pytest.MonkeyPatch, **por_uniq: int) -> None:
    """O dono com estes ganhos, sem a volta reler o disco (o daemon é de mentira)."""
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.daemon.ganho_da_haptica import GANHO

    monkeypatch.setattr(GANHO, "_escritos", {norm_mac(u): p for u, p in por_uniq.items()})
    monkeypatch.setattr(GANHO, "_teto", None)
    monkeypatch.setattr(GANHO, "ler_do_daemon", lambda *_a, **_k: None)


def test_pelo_radio_a_haptica_desligada_deixa_o_radio_com_o_alto_falante(
    sala_do_radio: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O jogo toca nos motores e o P4 está com a háptica em 0: a ponte não vai à háptica."""
    from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import (
        MOTOR,
        P3,
        P4,
        no_do,
    )

    sala = sala_do_radio
    _ganho_fixo(monkeypatch, **{P4: 0, P3: 150})
    for uniq in (P3, P4):
        sala.fonte(no_do(uniq)).quadro = MOTOR
    sala.abrir_a_sala(P3, P4)
    sala.volta()
    for uniq in (P3, P4):
        sala.esperar(no_do(uniq), True)
    sala.mexer(P3, P4)
    sala.volta()
    assert sala.arranjo(P3) == af.ARRANJO_HAPTICA_032.nome
    assert sala.arranjo(P4) != af.ARRANJO_HAPTICA_032.nome, (
        "com a háptica do P4 em 0 a ponte foi à háptica mandar silêncio"
    )


def test_no_radio_a_luz_e_a_ponte_em_haptica_com_sinal(
    sala_do_radio: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rádio: acesa com a ponte em háptica e sinal nos motores; apagada no silêncio e em 0."""
    from tests.unit.test_a_haptica_por_audio_e_o_alto_falante_chegam_ao_radio import (
        MOTOR,
        P2,
        no_do,
    )

    sala = sala_do_radio
    _ganho_fixo(monkeypatch, **{P2: 150})
    endpoint = no_do(P2)
    sala.fonte(endpoint).quadro = MOTOR
    sala.abrir_a_sala(P2)
    sala.volta()
    sala.esperar(endpoint, True)
    sala.mexer(P2)
    sala.volta()
    assert sala.arranjo(P2) == af.ARRANJO_HAPTICA_032.nome
    sala.esperar(endpoint, True)
    assert sala.sub.haptica_no_ar(P2) is True
    _ganho_fixo(monkeypatch, **{P2: 0})
    assert sala.sub.haptica_no_ar(P2) is False, "com o ganho em 0 o motor não mexe"
    _ganho_fixo(monkeypatch, **{P2: 150})
    sala.fonte(endpoint).quadro = None
    sala.esperar(endpoint, False)
    assert sala.arranjo(P2) == af.ARRANJO_HAPTICA_032.nome
    assert sala.sub.haptica_no_ar(P2) is False, "a ponte em háptica sem sinal acendeu a luz"


def test_no_cabo_a_luz_ouve_a_placa_do_controle(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cabo: o ouvido da placa lê o monitor dela, e a luz segue o sinal dos traseiros."""
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem
    from tests.unit.test_o_gravador_do_monitor_entrega_so_o_pcm import Gravadores

    gravadores = Gravadores(monkeypatch)
    monkeypatch.setattr(af, "OUVIDO", af.OuvidoDosNos())
    monkeypatch.setattr(af, "JANELA_DO_SINAL_S", 0.2)
    _ganho_fixo(monkeypatch, **{BRANCO: 150})
    sub = AltoFalanteSubsystem(daemon=None)
    try:
        gravadores.toca[PLACA_BRANCO] = (0, 0, 9000, -9000)
        sub._casar_os_ouvidos_das_placas({BRANCO: PLACA_BRANCO})
        [proc] = gravadores.abertos
        propriedades = proc.argv[proc.argv.index("-P") + 1]
        assert "node.dont-reconnect=true" in propriedades
        assert "node.dont-fallback=true" in propriedades
        assert f"--rate={af.TAXA_DO_OUVIDO_DA_PLACA}" in proc.argv
        _esperar_que(lambda: sub.haptica_no_ar(BRANCO) is True)
        gravadores.toca[PLACA_BRANCO] = (5000, 5000, 0, 0)
        _esperar_que(lambda: sub.haptica_no_ar(BRANCO) is False)
        sub._casar_os_ouvidos_das_placas({})
        assert proc.returncode is not None, "o ouvido de quem saiu do cabo ficou vivo"
        assert not sub._ouvidos_das_placas
    finally:
        for ouvido in dict(sub._ouvidos_das_placas).values():
            ouvido.descer()
        gravadores.fechar()


def test_a_volta_do_cabo_casa_o_ouvido_da_placa(monkeypatch: pytest.MonkeyPatch) -> None:
    """A volta de produção (``_casar_o_cabo``) sobe o ouvido da placa de quem está no cabo."""
    from types import SimpleNamespace

    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem
    from hefesto_dualsense4unix.integrations import alto_falante_bt as afb

    subidos: list[tuple[str, str]] = []

    class _OuvidoQueAnota:
        def __init__(self, *, placa: str, uniq: str) -> None:
            self.placa, self.uniq = placa, uniq
            self.vivo = True

        def subir(self) -> bool:
            subidos.append((self.uniq, self.placa))
            return True

        def descer(self) -> None:
            self.vivo = False

    monkeypatch.setattr(afb, "OuvidoDaPlaca", _OuvidoQueAnota)
    monkeypatch.setattr(afb, "sink_do_controle", lambda u, _m, **_k: _placa_de(u, None))
    sub = AltoFalanteSubsystem(daemon=None)
    controles = [
        SimpleNamespace(uniq=BRANCO, transporte="usb", caminho="/dev/hidraw40"),
        SimpleNamespace(uniq=PRETO, transporte="usb", caminho="/dev/hidraw41"),
    ]
    sub._casar_o_cabo(controles, set(), [PLACA_BRANCO, PLACA_PRETO])
    assert sorted(subidos) == sorted([(BRANCO, PLACA_BRANCO), (PRETO, PLACA_PRETO)])


def _esperar_que(condicao: Any, prazo_s: float = 5.0) -> None:
    import time

    fim = time.monotonic() + prazo_s
    while time.monotonic() < fim:
        if condicao():
            return
        time.sleep(0.01)
    raise AssertionError("a condição não chegou no prazo")
