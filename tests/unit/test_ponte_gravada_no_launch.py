"""PONTE-ESCADA-01 — a ponte gravada passa a valer NO LANÇAMENTO.

*"Ela confirma UMA vez qual pegou; o produto grava para sempre."* O lugar em
que "para sempre" acontece é o `arm_launch_profile`: é ele que arma o modo
ANTES de o jogo executar (R-04). Este arquivo prova as três metades da divisão
de poderes que a leva declarou, e cada teste é escrito para MORDER:

- **o perfil manda.** Carimbo discordando do `mode` não troca a máscara dela —
  grita a divergência e obedece ao perfil;
- **o carimbo preenche o silêncio.** Perfil sem `mode` era o ramo em que nada
  era armado; com o `Profile.ponte` carimbado, é ele que arma;
- **a ponte entregue só é relatada quando a máscara CONVERGIU**, e o arming
  não carimba nada — quem grava é `profiles/manager.confirmar_ponte`.

A gaveta é UMA (`Profile.ponte`, PONTE-CONFIRMADA-01): estes testes leem o
carimbo do próprio perfil, e nenhum arquivo de estado paralelo existe.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.profiles.schema import (
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

APPID = 1599660  # Sackboy: A Big Adventure


def _marker(tmp_path: Path, *, appid: int = APPID, epoch: int = 1000) -> Path:
    (tmp_path / "last_run").write_text(
        f"appid={appid}\nepoch={epoch}\npid=1\n", encoding="utf-8"
    )
    return tmp_path


def _perfil(
    mode: ProfileModeConfig | None, *, ponte: PonteConfirmada | None = None
) -> Profile:
    return Profile(
        name="sackboy",
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=80,
        mode=mode,
        ponte=ponte,
    )


class _DaemonFalso:
    """Mesa em `dualsense`/uhid — o estado em que o primeiro degrau CONVERGE."""

    def __init__(self, flavor: str = "dualsense") -> None:
        self.aplicados: list[tuple[Any, Any, str]] = []
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor=flavor
        )
        self._gamepad_device = SimpleNamespace(backend="uhid")
        self._coop_manager = None
        self.controller = SimpleNamespace()

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append((mode, profile, origin))
        # O applier de verdade também MUDA a mesa; sem isto a divergência
        # nunca fecharia e o teste mediria o dublê, não o produto.
        if getattr(mode, "kind", None) == "gamepad":
            self.config.gamepad_flavor = mode.gamepad_flavor
        return "aplicado"


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    return tmp_path


class TestOCarimboPreencheOSilencioDoPerfil:
    def test_perfil_sem_modo_arma_a_ponte_carimbada(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O ramo que antes não armava nada. Agora honra o gesto dela."""
        _marker(env_dir)
        perfil = _perfil(
            None, ponte=PonteConfirmada(kind="gamepad", gamepad_flavor="xbox")
        )
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])
        daemon = _DaemonFalso()

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["armado"] is True
        assert resultado["ponte_do_carimbo"] is True
        assert resultado["ponte"] == "gamepad/xbox"
        assert len(daemon.aplicados) == 1
        mode, _perfil_arg, origem = daemon.aplicados[0]
        assert mode.kind == "gamepad" and mode.gamepad_flavor == "xbox"
        assert origem == "launch", "o arming do carimbo não fura o lock (R-03)"

    def test_ponte_nativa_carimbada_arma_o_modo_nativo(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _marker(env_dir)
        perfil = _perfil(None, ponte=PonteConfirmada(kind="native"))
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])
        daemon = _DaemonFalso()

        le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert daemon.aplicados[0][0].kind == "native"

    def test_sem_carimbo_e_sem_modo_a_escada_arma_o_primeiro_degrau(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """SUBSTITUI `test_sem_carimbo_o_ramo_continua_sendo_o_de_antes`.

        NOTA DATADA — 19/08/2026 (PONTE-ESCADA-LACO-01). Este teste afirmava
        *"perfil sem modo continua sem armar nada"*, e essa afirmação era
        verdadeira enquanto a escada não tinha chamador: `proximo_degrau` era
        uma decisão sem ninguém para tomá-la. Não é decisão medida que se
        apaga — é o retrato de um buraco, e o buraco foi fechado. O ramo
        "nada a armar" era exatamente onde ela ficava com a máscara que
        estivesse de pé por acaso.

        O que NÃO mudou, e continua provado abaixo: nada é carimbado no
        lançamento.
        """
        _marker(env_dir)
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, _perfil(None))])
        daemon = _DaemonFalso(flavor="xbox")

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["armado"] is True
        assert resultado["ponte_da_escada"] is True
        assert resultado["ponte"] == "gamepad/dualsense", "o primeiro degrau"
        assert resultado["ponte_confirmada"] is None, "o lançamento não carimba"
        mode, _perfil_arg, origem = daemon.aplicados[0]
        assert mode.kind == "gamepad" and mode.gamepad_flavor == "dualsense"
        assert origem == "launch", "a escada não fura o lock manual (R-03)"


class TestOPerfilManda:
    def test_carimbo_discordando_nao_troca_a_mascara_dela(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Trocar o modo de um jogo dela sem ela pedir é a regra ao contrário."""
        _marker(env_dir)
        perfil = _perfil(
            ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"),
            ponte=PonteConfirmada(kind="gamepad", gamepad_flavor="xbox"),
        )
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])
        daemon = _DaemonFalso(flavor="xbox")

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["ponte_do_carimbo"] is False
        assert daemon.aplicados[0][0].gamepad_flavor == "dualsense"
        # A discordância aparece INTEIRA para quem tem a palavra.
        assert resultado["ponte"] == "gamepad/dualsense"
        assert resultado["ponte_confirmada"] == "gamepad/xbox"


class TestRelatarNaoEConfirmar:
    def test_o_lancamento_relata_a_ponte_entregue_sem_carimbar(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _marker(env_dir)
        perfil = _perfil(ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"))
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])

        resultado = le.arm_launch_profile(
            _DaemonFalso(), base_dir=env_dir, now=1001.0
        )

        assert resultado is not None
        assert resultado["ponte"] == "gamepad/dualsense"
        assert resultado["ponte_confirmada"] is None, (
            "gravar 'funciona' sobre algo que ninguém confirmou é a mentira "
            "que o balde `sem_impedimento_conhecido` existe para não contar"
        )
        assert perfil.ponte is None, "o arming NÃO carimba: quem carimba é o gesto"
        # E a escada continua tendo para onde ir.
        assert (
            pe.proximo_degrau(ponte_atual=pe.ESCADA[0].ponte) is pe.ESCADA[1]
        )

    def test_mascara_recusada_pelo_gate_nao_vira_ponte_entregue(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-04 recusou: o jogo nunca viu essa ponte, e o relatório não mente."""
        _marker(env_dir)
        perfil = _perfil(ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"))
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])

        class _DaemonQueRecusa(_DaemonFalso):
            def apply_profile_mode(
                self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
            ) -> str:
                # `bloqueado_por_jogo`: devolve "aplicou" e a mesa NÃO muda.
                self.aplicados.append((mode, profile, origin))
                return "bloqueado_por_jogo"

        resultado = le.arm_launch_profile(
            _DaemonQueRecusa(flavor="xbox"), base_dir=env_dir, now=1001.0
        )

        assert resultado is not None and resultado["convergiu"] is False
        assert resultado["ponte"] is None

    def test_o_appid_da_allowlist_nao_relata_ponte_pela_mascara(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Na allowlist o arming pula a seção `mode` — não há ponte entregue."""
        _marker(env_dir)
        monkeypatch.setattr(le, "steam_input_appids", lambda path=None: {APPID})
        perfil = _perfil(ProfileModeConfig(kind="gamepad", gamepad_flavor="dualsense"))
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])

        resultado = le.arm_launch_profile(_DaemonFalso(), base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["motivo"] == "allowlist_steam_input"
        assert "ponte" not in resultado
