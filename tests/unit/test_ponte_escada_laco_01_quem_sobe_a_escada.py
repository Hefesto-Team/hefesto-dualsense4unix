"""PONTE-ESCADA-LACO-01 (19/08/2026) — o LAÇO que sobe a escada.

A escada estava construída e ninguém a subia: `proximo_degrau`, `como_subir` e
`confirmacao_por_silencio` eram três decisões corretas sem chamador em
produção — o defeito-mãe desta casa, e o
`portao_a_casa_sabe_e_o_produto_nao_faz.py` as acusava pelo nome.

Este arquivo trava os três momentos do laço e as duas fronteiras que ele não
pode atravessar:

1. **no lançamento** — jogo COM carimbo não vê escada nenhuma (regressão pura
   seria o produto mexer no que já funcionava); jogo SEM carimbo e sem `mode`
   ganha o primeiro degrau; jogo com `mode` continua mandando;
2. **no gesto `PS + R3`** — o gesto SEMPRE troca (é vontade dela), e o laço
   aprende com ele que o degrau de pé não funcionou;
3. **no silêncio** — passado o prazo com o jogo VIVO, carimba uma vez; com o
   jogo fechado, NUNCA.

As duas fronteiras: **nada é gravado antes da confirmação**, e **o laço não
sobe degrau sozinho com o jogo aberto** (R-04).

Cada teste diz o que MORDE — o que ele vê reprovar quando a cura é arrancada.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon import launch_env as le
from hefesto_dualsense4unix.daemon.subsystems import hotkey as hotkey_sub
from hefesto_dualsense4unix.integrations import ponte_escada as pe
from hefesto_dualsense4unix.integrations import ponte_tentativa as pt
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import ponte_confirmada_do_appid
from hefesto_dualsense4unix.profiles.schema import (
    CONFIRMADA_POR_SILENCIO,
    MatchCriteria,
    PonteConfirmada,
    Profile,
    ProfileModeConfig,
)

APPID = 2497900
EPOCH = 1000


def _marker(tmp_path: Path, *, appid: int = APPID, epoch: int = EPOCH) -> Path:
    (tmp_path / "last_run").write_text(
        f"appid={appid}\nepoch={epoch}\npid=1\n", encoding="utf-8"
    )
    return tmp_path


def _perfil(
    mode: ProfileModeConfig | None = None,
    *,
    ponte: PonteConfirmada | None = None,
    nome: str = "dont-scream",
) -> Profile:
    return Profile(
        name=nome,
        match=MatchCriteria(window_class=[f"steam_app_{APPID}"]),
        priority=80,
        mode=mode,
        ponte=ponte,
    )


class _DaemonFalso:
    """Mesa em `dualsense`/uhid — o estado em que o primeiro degrau CONVERGE."""

    def __init__(
        self, flavor: str = "dualsense", *, authority: str = "unknown"
    ) -> None:
        self.aplicados: list[tuple[Any, Any, str]] = []
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=True, gamepad_flavor=flavor
        )
        self._gamepad_device = SimpleNamespace(backend="uhid", flavor=flavor)
        self._coop_manager = None
        self.controller = SimpleNamespace()
        self.display_authority = authority

    def is_native_mode(self) -> bool:
        return False

    def apply_profile_mode(
        self, mode: Any, *, profile: Any = None, origin: str = "autoswitch"
    ) -> str:
        self.aplicados.append((mode, profile, origin))
        if getattr(mode, "kind", None) == "gamepad":
            self.config.gamepad_flavor = mode.gamepad_flavor
            self._gamepad_device = SimpleNamespace(
                backend="uhid", flavor=mode.gamepad_flavor
            )
        return "aplicado"


@pytest.fixture
def env_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "materialize_launch_env", lambda daemon: None)
    monkeypatch.setattr(le, "steam_input_appids", lambda path=None: set())
    return tmp_path


class TestNoLancamento:
    def test_jogo_com_carimbo_nao_ve_escada_nenhuma(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A regressão que dói: a escada mexendo no que JÁ funcionava."""
        _marker(env_dir)
        perfil = _perfil(ponte=PonteConfirmada(kind="gamepad", gamepad_flavor="xbox"))
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])
        daemon = _DaemonFalso(flavor="xbox")

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["escada"] == pt.COMECO_PRODUTO_JA_SABE
        assert pt.em_curso(daemon) is None, "escada aberta em jogo confirmado"
        assert resultado["ponte_do_carimbo"] is True

    def test_jogo_sem_carimbo_e_sem_modo_comeca_no_primeiro_degrau(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O ramo que era "nada a armar" — o buraco que este laço fecha."""
        _marker(env_dir)
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, _perfil())])
        daemon = _DaemonFalso(flavor="xbox")

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["armado"] is True
        assert resultado["ponte"] == pe.ESCADA[0].ponte.chave == "gamepad/dualsense"
        tentativa = pt.em_curso(daemon)
        assert tentativa is not None
        assert tentativa.appid == APPID and tentativa.epoch == EPOCH
        assert tentativa.degrau == pe.ESCADA[0]

    def test_perfil_com_modo_manda_e_a_escada_abre_parada_nele(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A regra mais velha da casa: não trocar o modo de um jogo do usuário."""
        _marker(env_dir)
        perfil = _perfil(ProfileModeConfig(kind="gamepad", gamepad_flavor="xbox"))
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, perfil)])
        daemon = _DaemonFalso(flavor="xbox")

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["escada"] == pt.COMECO_PERFIL_MANDA
        assert resultado["ponte_da_escada"] is False
        assert [m.gamepad_flavor for m, _p, _o in daemon.aplicados] == ["xbox"]
        tentativa = pt.em_curso(daemon)
        assert tentativa is not None
        assert tentativa.degrau.ponte.mascara == "xbox", "o degrau DELA, não o 0"

    def test_com_jogo_vivo_o_lancamento_nao_arma_sozinho(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """R-04: recriar o vpad com jogo aberto arranca o controle da mão do usuário."""
        _marker(env_dir)
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, _perfil())])
        daemon = _DaemonFalso(flavor="xbox", authority="game")

        resultado = le.arm_launch_profile(daemon, base_dir=env_dir, now=1001.0)

        assert resultado is not None
        assert resultado["armado"] is False
        assert resultado["escada"] == pt.COMECO_JOGO_VIVO
        assert daemon.aplicados == [], "a escada pagou o R-04 sem ela pedir"
        assert pt.em_curso(daemon) is None

    def test_o_lancamento_nao_carimba_nada(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Armar não é confirmar. Carimbar aqui seria gravar "funciona" sobre"""
        _marker(env_dir)
        save_profile(_perfil(), origem="teste")
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, _perfil())])

        le.arm_launch_profile(_DaemonFalso(), base_dir=env_dir, now=1001.0)

        assert ponte_confirmada_do_appid(APPID) is None


class _FakeDevice:
    def __init__(self, flavor: str) -> None:
        self.flavor = flavor


class _FakeStore:
    def __init__(self) -> None:
        self.native_mode_active = False
        self.bumps: list[str] = []

    def bump(self, chave: str) -> None:
        self.bumps.append(chave)


class _DaemonDoGesto:
    """AJUSTADO À REGRA DE PRODUTO — MODO-DE-CONEXAO-01, 13/09/2026."""

    def __init__(self, *, flavor: str = "dualsense", aplica: bool = True) -> None:
        self.controller = SimpleNamespace()
        self.store = _FakeStore()
        self.display_authority = "game"
        self.config = SimpleNamespace(gamepad_caminho=None)
        self._mascara = flavor
        self._gamepad_device: Any = _FakeDevice(flavor)
        self._aplica = aplica
        self.pedidos: list[tuple[bool, str | None, str, str | None]] = []

    async def _run_blocking(self, fn: Any, *args: Any) -> Any:
        return fn(*args)

    def set_gamepad_emulation(
        self,
        enabled: bool,
        flavor: str | None = None,
        *,
        origin: str = "manual",
        caminho: str | None = None,
        grava_o_modo: Any = False,
    ) -> bool:
        self.pedidos.append((enabled, flavor, origin, caminho))
        if not self._aplica:
            return False
        if enabled:
            self.config.gamepad_caminho = caminho or self.config.gamepad_caminho
            self._gamepad_device = _FakeDevice(flavor or self._mascara)
        else:
            self._gamepad_device = None
        return True

    def set_mouse_emulation(self, enabled: bool, *, origin: str = "profile") -> bool:
        return enabled

    def set_keyboard_emulation(self, enabled: bool) -> bool:
        return enabled

    def set_emulation_suppressed(self, value: bool | None = None) -> bool:
        return bool(value)


@pytest.fixture(autouse=True)
def _sem_espera(monkeypatch: pytest.MonkeyPatch) -> None:
    """Zera a lightbar: estes testes medem DECISÃO, não relógio."""
    monkeypatch.setattr(hotkey_sub, "PULSO_SEG", 0.0)


def _abrir_tentativa(daemon: Any, degrau: pe.Degrau, *, agora: float = 0.0) -> None:
    daemon._ponte_tentativa = pt.Tentativa(
        appid=APPID, epoch=EPOCH, degrau=degrau, ultimo_gesto=agora, viu_o_jogo=True
    )


class TestOGesto:
    @pytest.mark.asyncio
    async def test_com_tentativa_o_gesto_segue_a_escada(self) -> None:
        """O gesto passa a ter o dado por trás: a ordem justificada no mapa."""
        d = _DaemonDoGesto(flavor="dualsense")
        _abrir_tentativa(d, pe.ESCADA[0])

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(True, None, "manual", "xbox")]
        tentativa = pt.em_curso(d)
        assert tentativa is not None
        assert tentativa.degrau == pe.ESCADA[1], "a escada não avançou"
        assert tentativa.gestos == 1

    @pytest.mark.asyncio
    async def test_sem_tentativa_o_gesto_faz_o_de_sempre(self) -> None:
        """Jogo COM ponte confirmada: o gesto TROCA do mesmo jeito."""
        d = _DaemonDoGesto(flavor="dualsense")
        assert pt.em_curso(d) is None

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert d.pedidos == [(True, None, "manual", "xbox")], "o gesto tem de obedecer"

    @pytest.mark.asyncio
    async def test_a_escada_nao_avanca_quando_a_mascara_nao_sobe(self) -> None:
        """MASCARA-01: o retorno do applier não prova nada; o aparelho prova."""
        d = _DaemonDoGesto(flavor="dualsense", aplica=False)
        _abrir_tentativa(d, pe.ESCADA[0])

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        tentativa = pt.em_curso(d)
        assert tentativa is not None
        assert tentativa.degrau == pe.ESCADA[0], "avançou sobre uma ponte caída"

    @pytest.mark.asyncio
    async def test_degrau_caro_avisa_guarda_e_nao_cai_no_ciclo_no_mesmo_gesto(
        self,
    ) -> None:
        """O terceiro degrau (`native`) não alcança um processo já rodando."""
        d = _DaemonDoGesto(flavor="xbox")
        _abrir_tentativa(d, pe.ESCADA[1])

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert pe.ESCADA[2].exige_reabrir_jogo is True, "premissa do teste"
        assert hotkey_sub.proxima_ponte("xbox") == hotkey_sub.PONTE_MOUSE_TECLADO, (
            "premissa: depois de `xbox`, o ciclo livre é `mouse_teclado`"
        )
        assert d.pedidos == [(False, None, "manual", None)], (
            "o aperto dela foi comido, ou o gesto entrou em Modo Nativo"
        )
        assert pt.em_curso(d) is None, "a tentativa tinha de ser encerrada"
        guardado = pt.gesto_em_curso(d)
        assert guardado is not None, "o degrau de pé evaporou com a tentativa"
        assert guardado.ponte == pe.ESCADA[1].ponte
        assert guardado.a_registrar is True, "não vai chegar ao perfil"

    @pytest.mark.asyncio
    async def test_a_porta_de_volta_pelo_controle_nao_custa_aperto_nenhum(
        self,
    ) -> None:
        """Do degrau caro em diante, cada aperto anda uma casa do ciclo livre."""
        d = _DaemonDoGesto(flavor="xbox")
        _abrir_tentativa(d, pe.ESCADA[1])
        gesto = hotkey_sub.build_next_bridge_callback(d)

        await gesto()  # type: ignore[operator]
        await gesto()  # type: ignore[operator]

        assert d.pedidos == [
            (False, None, "manual", None),
            (True, None, "manual", "dualsense"),
        ], "ficou presa no degrau caro, ou comeu um aperto"

    @pytest.mark.asyncio
    async def test_no_ultimo_degrau_a_escada_acaba_e_o_gesto_segue(self) -> None:
        """Voltar ao primeiro degrau faria um laço eterno — e um laço de"""
        assert pe.ESCADA[-1].ponte.steam_input is True, "premissa do teste"
        d = _DaemonDoGesto(flavor="dualsense")
        _abrir_tentativa(d, pe.ESCADA[-1])

        await hotkey_sub.build_next_bridge_callback(d)()  # type: ignore[arg-type]

        assert pt.em_curso(d) is None
        assert d.pedidos == [(True, None, "manual", "xbox")], "o gesto tem de obedecer"

    def test_o_degrau_do_steam_input_nunca_e_subido_pelo_gesto(self) -> None:
        """Ele exige fechar a Steam, reabrir a Steam e reabrir o jogo — e
        `_aplicar_ponte` não sabe fazer nada disso. Prometer aqui seria o
        gesto dizendo que ligou o Steam Input, que NENHUMA linha deste
        repositório liga.

        O invariante não mudou em 30/08; mudou o nome do desfecho. Antes o
        laço PARAVA nele (`PASSO_PAROU`); agora o PULA e a escada acaba —
        `caminho is None` nos dois casos, que é o que garante que o gesto
        nunca aplica Steam Input. (O campo do `Passo` chamava-se `mascara` até
        a MODO-DE-CONEXAO-01, 13/09/2026: o gesto anda por caminhos.)
        """
        d = _DaemonDoGesto(flavor="dualsense")
        _abrir_tentativa(d, pe.ESCADA[2])

        passo = pt.avancar_por_gesto(d, jogo_vivo=True, agora=1.0)

        assert passo is not None
        assert passo.caminho is None, "o gesto ia aplicar o Steam Input"
        assert passo.motivo == pt.PASSO_ESCADA_ACABOU
        assert [d.ponte.chave for d in passo.pulados] == [
            "gamepad/dualsense+steam_input"
        ], "o degrau do Steam Input não foi anunciado como pulado"

    def test_o_gesto_nunca_carimba(self) -> None:
        """O gesto é o CONTRÁRIO de uma confirmação: é o sinal de que o degrau"""
        d = _DaemonDoGesto()
        _abrir_tentativa(d, pe.ESCADA[0])

        pt.avancar_por_gesto(d, jogo_vivo=True, agora=10.0)

        assert ponte_confirmada_do_appid(APPID) is None

    def test_o_gesto_reinicia_o_relogio_do_silencio(self) -> None:
        """O usuário reclamou: os três minutos recomeçam. MORDE a linha"""
        d = _DaemonDoGesto(flavor="dualsense")
        _abrir_tentativa(d, pe.ESCADA[0], agora=0.0)

        pt.avancar_por_gesto(d, jogo_vivo=True, agora=1000.0)

        tentativa = pt.em_curso(d)
        assert tentativa is not None
        assert tentativa.ultimo_gesto == 1000.0
        assert (
            pt.silencio_confirma(
                d, jogo_vivo=True, agora=1000.0 + pe.SILENCIO_CONFIRMA_SEC - 1
            )
            is None
        )


class TestOSilencio:
    def test_o_relogio_comeca_quando_o_jogo_aparece(self) -> None:
        """Não no lançamento: launch→janela chega a 15 minutos (Proton na 1ª"""
        d = _DaemonDoGesto()
        d._ponte_tentativa = pt.Tentativa(
            appid=APPID, epoch=EPOCH, degrau=pe.ESCADA[0], ultimo_gesto=0.0
        )
        assert pt.tique(d, jogo_vivo=False, agora=600.0).carimbar is None
        tentativa = pt.em_curso(d)
        assert tentativa is not None and tentativa.viu_o_jogo is False

        pt.tique(d, jogo_vivo=True, agora=600.0)
        tentativa = pt.em_curso(d)
        assert tentativa is not None
        assert tentativa.viu_o_jogo is True and tentativa.ultimo_gesto == 600.0
        assert (
            pt.tique(
                d, jogo_vivo=True, agora=600.0 + pe.SILENCIO_CONFIRMA_SEC - 1
            ).carimbar
            is None
        )

    def test_jogo_fechado_no_meio_da_escada_nao_carimba_nada(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ninguém confirmou nada. Silêncio com o jogo fechado não é ela"""
        save_profile(_perfil(), origem="teste")
        d = _DaemonFalso()
        _abrir_tentativa(d, pe.ESCADA[1], agora=0.0)

        assert pt.silencio_confirma(d, jogo_vivo=False, agora=10_000.0) is None

        fim = le.tique_da_escada(d, agora=10_000.0)

        assert fim == pt.FIM_JOGO_FECHOU
        assert pt.em_curso(d) is None
        assert ponte_confirmada_do_appid(APPID) is None, "carimbou sem ninguém ver"

    def test_passado_o_silencio_com_o_jogo_vivo_o_produto_carimba(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """*"Se ela para de apertar, a ponte atual é a que pegou."*"""
        save_profile(_perfil(), origem="teste")
        d = _DaemonFalso(authority="game")
        _abrir_tentativa(d, pe.ESCADA[1], agora=0.0)

        fim = le.tique_da_escada(d, agora=pe.SILENCIO_CONFIRMA_SEC + 1)

        assert fim == pt.FIM_CONFIRMADA
        ponte = ponte_confirmada_do_appid(APPID)
        assert ponte is not None
        assert (ponte.kind, ponte.gamepad_flavor) == ("gamepad", "xbox")
        assert ponte.confirmada_por == CONFIRMADA_POR_SILENCIO

    def test_carimba_uma_vez_so(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Recarimbar a cada volta do laço apagaria a data — a única"""
        save_profile(_perfil(), origem="teste")
        d = _DaemonFalso(authority="game")
        _abrir_tentativa(d, pe.ESCADA[0], agora=0.0)

        assert le.tique_da_escada(d, agora=1000.0) == pt.FIM_CONFIRMADA
        primeiro = ponte_confirmada_do_appid(APPID)
        assert primeiro is not None
        assert le.tique_da_escada(d, agora=2000.0) is None
        assert ponte_confirmada_do_appid(APPID) == primeiro

    def test_depois_de_confirmada_a_escada_nunca_mais_roda_naquele_jogo(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O fim da história dela: *"nunca mais precisa fazer isso NESSE"""
        save_profile(_perfil(), origem="teste")
        d = _DaemonFalso(authority="game")
        _abrir_tentativa(d, pe.ESCADA[1], agora=0.0)
        le.tique_da_escada(d, agora=1000.0)
        carimbo = ponte_confirmada_do_appid(APPID)
        assert carimbo is not None

        _marker(env_dir, epoch=EPOCH + 1)
        perfil_com_carimbo = _perfil(ponte=carimbo)
        monkeypatch.setattr(
            le, "_steam_profiles", lambda dd: [(APPID, perfil_com_carimbo)]
        )
        outro = _DaemonFalso(flavor="xbox")

        resultado = le.arm_launch_profile(outro, base_dir=env_dir, now=1002.0)

        assert resultado is not None
        assert resultado["escada"] == pt.COMECO_PRODUTO_JA_SABE
        assert pt.em_curso(outro) is None
        assert resultado["ponte_do_carimbo"] is True
        assert resultado["ponte"] == "gamepad/xbox", "o carimbo é que arma"


class TestAsFronteiras:
    def test_a_tentativa_e_estado_vivo_e_nao_toca_o_disco(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A tentativa mora num atributo do daemon, e o disco só recebe o"""
        save_profile(_perfil(), origem="teste")
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, _perfil())])
        _marker(env_dir)
        d = _DaemonFalso()

        le.arm_launch_profile(d, base_dir=env_dir, now=1001.0)

        assert isinstance(getattr(d, pt.ATRIBUTO_DA_TENTATIVA), pt.Tentativa)
        assert pt.em_curso(_DaemonFalso()) is None
        assert ponte_confirmada_do_appid(APPID) is None

    def test_nenhum_relogio_sobe_degrau_sozinho(self) -> None:
        """O DESENHO, declarado: a escada avança em dois pontos só — o"""
        d = _DaemonDoGesto()
        _abrir_tentativa(d, pe.ESCADA[0], agora=0.0)

        for instante in (1.0, 60.0, 120.0, 179.0):
            pt.tique(d, jogo_vivo=True, agora=instante)

        tentativa = pt.em_curso(d)
        assert tentativa is not None
        assert tentativa.degrau == pe.ESCADA[0]
        assert d.pedidos == [], "algum relógio recriou o vpad dela sozinho"

    def test_sem_perfil_nao_carimba_e_nao_inventa_arquivo(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`confirmar_ponte` devolve None quando o jogo não tem perfil: criar"""
        d = _DaemonFalso(authority="game")
        _abrir_tentativa(d, pe.ESCADA[0], agora=0.0)

        assert le.tique_da_escada(d, agora=1000.0) == pt.FIM_CONFIRMADA
        assert ponte_confirmada_do_appid(APPID) is None
        assert pt.em_curso(d) is None

    def test_o_tique_anda_no_relogio_do_arming_e_antes_de_todo_return(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A fiação, que é o defeito inteiro desta frente."""
        chamadas: list[Any] = []
        monkeypatch.setattr(
            le, "tique_da_escada", lambda d, **kw: chamadas.append(d) or None
        )
        d = _DaemonFalso()

        assert le.arm_launch_profile(d, base_dir=env_dir, now=1001.0) is None
        assert chamadas == [d], "o tique parou de andar fora do lançamento"

        _marker(env_dir)
        monkeypatch.setattr(le, "_steam_profiles", lambda dd: [(APPID, _perfil())])
        le.arm_launch_profile(d, base_dir=env_dir, now=1001.0)
        assert chamadas == [d, d]

    def test_uma_tentativa_por_vez(
        self, env_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Outro lançamento mata a tentativa velha SEM carimbar. Duas escadas"""
        _marker(env_dir)
        monkeypatch.setattr(le, "_steam_profiles", lambda d: [(APPID, _perfil())])
        d = _DaemonFalso()
        le.arm_launch_profile(d, base_dir=env_dir, now=1001.0)
        primeira = pt.em_curso(d)
        assert primeira is not None

        _marker(env_dir, epoch=EPOCH + 1)
        le.arm_launch_profile(d, base_dir=env_dir, now=1002.0)

        segunda = pt.em_curso(d)
        assert segunda is not None and segunda is not primeira
        assert segunda.epoch == EPOCH + 1
        assert ponte_confirmada_do_appid(APPID) is None
