"""O ganho da háptica por áudio tem dono — O-GANHO-DA-HAPTICA-TEM-DONO-01, 29/09/2026.

Ela, depois da Forja com os quatro: *«no cabo ficou muito baixo a vibração
específica»*. <!-- noqa-acento: citação literal dela --> Do jogo à placa tudo
já estava em 0 dB; faltava ganho acima de 100 %, com UM dono por controle, e as
duas portas perguntando a ele: os traseiros da placa no cabo e o conversor da
ponte no rádio, antes do int8.

Nenhuma régua daqui mede a própria saída: o volume é o que o SERVIDOR de
mentira guardou (e ele traduz as quatro formas do ``pactl`` como o de verdade,
com régua própria contra o número medido em 29/09), e o bloco do rádio é o que
a bomba de verdade monta.
"""

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
from tests.unit.test_cada_motor_tem_o_seu_multiplicador import (
    BRANCO,
    PRETO,
    _grava_ipc,
    _Handlers,
)

#: As duas placas do cabo e um endpoint do Hefesto, com os nomes na forma do
#: servidor (a faixa forjada da casa; nenhum endereço real).
_SONY = "alsa_output.usb-Sony_Interactive_Entertainment_Wireless_Controller"
PLACA_BRANCO = f"{_SONY}-00.analog-surround-40"
PLACA_PRETO = f"{_SONY}-00.2.analog-surround-40"
ENDPOINT = "alsa_output.usb-HEFESTO-lugar1-00.analog-surround-40"


# ---------------------------------------------------------------------------
# O servidor de som de mentira: guarda o volume CRU, como o de verdade
# ---------------------------------------------------------------------------


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
                return None  # o `pactl` recusa canais em formas diferentes
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
    quarenta = [26214, 26214, VOLUME_NORMAL, VOLUME_NORMAL]  # a frente em 40 %
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
        """``40%`` é −23,88 dB: o WirePlumber guardou 0,063997 linear na placa dela."""  # noqa: RUF002
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


# ---------------------------------------------------------------------------
# 1. O campo, no perfil
# ---------------------------------------------------------------------------


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
        """Régua 6: o ``load → save`` de um perfil sem ``haptica_pct`` sai igual.

        MORDIDA: tirar o ``model_serializer`` → a chave aparece com ``None``.
        """
        velho = ControllerRumbleOverride.model_validate({"motor_forte_pct": 50})
        assert "haptica_pct" not in velho.model_dump()
        assert "haptica_pct" not in velho.model_dump(mode="json")
        mexeu = ControllerRumbleOverride.model_validate({"haptica_pct": 180})
        assert mexeu.model_dump(mode="json")["haptica_pct"] == 180


# ---------------------------------------------------------------------------
# 2. A porta do cabo: os traseiros da placa daquele controle
# ---------------------------------------------------------------------------


class TestACaboAPlaca:
    def test_a_placa_recebe_fator_linear(self) -> None:
        """Régua 1: 150 % vira 1,5 no servidor, e não 3,375 (o ``%`` é cúbico).

        MORDIDA: escrever ``150%`` → o servidor guarda 3,375 → reprova.
        """
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
        """Régua 2: ``haptica_pct=50``, duas voltas → −6,02 dB nos traseiros.

        A volta do subsystem escreve o ganho e DEPOIS levanta o piso sobre
        ``placas_do_piso``. MORDIDA: o piso sobre a lista inteira → a segunda
        volta termina em 0 dB → reprova.
        """  # noqa: RUF002
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
        """Régua 3: dois controles, 50 e 150; o endpoint fica em 0 dB.

        MORDIDA: escrever o ganho por toda placa de quatro canais → o endpoint
        e a placa do outro recebem → reprova.
        """
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
        """Régua 8: o ganho não sobrevive ao Hefesto — 1,5 volta a 1,0.

        MORDIDA: tirar a devolução → a placa fica em 1,5 → reprova.
        """
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


# ---------------------------------------------------------------------------
# 3. A porta do rádio: o conversor da ponte, antes do int8
# ---------------------------------------------------------------------------


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
        """Régua 4: nível constante (e não seno: o filtro tiraria do pico).

        MORDIDA: o conversor sem o ganho → 64 nos dois → reprova.
        """
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


# ---------------------------------------------------------------------------
# 4. O pedido: `rumble.motores.set` leva `haptica_pct`
# ---------------------------------------------------------------------------


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
        dele = (loader_module.load_profile("Bancada").controllers or {})[BRANCO]
        assert dele.rumble is not None and dele.rumble.haptica_pct == 180
        assert "motor_forte_pct" not in dele.rumble.model_fields_set
        assert dono.pct(BRANCO) == 180

    def test_o_padrao_nao_ocupa_chave(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        _grava_ipc(h, uniq=BRANCO, haptica_pct=0)
        corpo = _grava_ipc(h, uniq=BRANCO, haptica_pct=HAPTICA_PCT_PADRAO)
        assert corpo["haptica_pct"] == HAPTICA_PCT_PADRAO
        dele = (loader_module.load_profile("Bancada").controllers or {}).get(BRANCO)
        assert dele is None or dele.rumble is None or (
            "haptica_pct" not in dele.rumble.model_fields_set
        )

    def test_fora_da_faixa_e_recusado_sem_gravar(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="haptica_pct"):
            _grava_ipc(h, uniq=BRANCO, haptica_pct=HAPTICA_PCT_MAX + 1)
        assert not (loader_module.load_profile("Bancada").controllers or {})

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


# ---------------------------------------------------------------------------
# 5. O que o `state_full` devolve, por controle
# ---------------------------------------------------------------------------


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
