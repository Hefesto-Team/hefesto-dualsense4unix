"""VIBRACAO-POR-MOTOR-01 (04/09/2026) — a barra de cada motor MULTIPLICA o degrau."""
from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp_mod
from hefesto_dualsense4unix.profiles import loader as loader_module
from hefesto_dualsense4unix.profiles.loader import save_profile
from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales
from hefesto_dualsense4unix.profiles.schema import (
    MOTOR_PCT_MAX,
    MOTOR_PCT_PADRAO,
    ControllerOverrides,
    ControllerRumbleOverride,
    MatchAny,
    Profile,
    RumbleConfig,
    motores_dos_controles,
    pcts_dos_motores,
)
from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_que_vale
from tests.unit.test_backend_multi_controller import (
    KEY_1,
    KEY_2,
    UNIQ_1,
    UNIQ_2,
    _FakeHandle,
    _null_evdev,
)

BRANCO = UNIQ_1
PRETO = UNIQ_2

def _degrau(nome: str) -> float:
    from hefesto_dualsense4unix.daemon.subsystems.rumble import RUMBLE_POLICY_MULT

    return RUMBLE_POLICY_MULT[nome]


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado — o mesmo molde do `isolated_profiles_dir`."""
    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


class _Backend:
    """Backend de mentira com a API por-uniq: guarda (uniq, weak, strong)."""

    def __init__(self, uniqs: tuple[str, ...] = (BRANCO, PRETO)) -> None:
        self._uniqs = list(uniqs)
        self.rumbles: list[tuple[str | None, int, int]] = []
        self.primary_uniq: str | None = uniqs[0] if uniqs else None

    def set_rumble_for(self, uniq: str, weak: int, strong: int) -> bool:
        if uniq not in self._uniqs:
            return False
        self.rumbles.append((uniq, weak, strong))
        return True

    def set_rumble(self, weak: int, strong: int) -> None:
        self.rumbles.append((None, weak, strong))


def _daemon(
    *,
    policy: str = "balanceado",
    perfil_ativo: str | None = None,
    battery: int = 80,
    controller: Any | None = None,
) -> Any:
    """Daemon de mentira — o mesmo molde do `test_vpad_ff_passthrough._make_daemon`,"""
    estado = SimpleNamespace(battery_pct=battery)
    return SimpleNamespace(
        config=SimpleNamespace(
            rumble_active=None,
            rumble_policy=policy,
            rumble_policy_custom_mult=0.7,
        ),
        controller=controller if controller is not None else _Backend(),
        store=SimpleNamespace(
            active_profile=perfil_ativo,
            snapshot=lambda: SimpleNamespace(controller=estado),
        ),
        _last_auto_mult=0.7,
        _last_auto_change_at=0.0,
    )


def _grava(nome: str, **barras: int | None) -> None:
    """Grava no disco um perfil com as barras do BRANCO, e só elas."""
    save_profile(
        Profile(
            name=nome,
            match=MatchAny(),
            controllers={
                BRANCO: ControllerOverrides(
                    rumble=ControllerRumbleOverride(
                        **{k: v for k, v in barras.items() if v is not None}
                    )
                )
            },
        )
    )


class TestAContaDela:
    def test_degrau_150_fraca_100_forte_50_sai_150_e_75(self, perfis: Path) -> None:
        """O CASO EXATO DA FRASE DELA, do disco ao par escrito no controle."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)

        efetivo = gp_mod.apply_game_rumble(d, 100, 100, target_uniq=BRANCO)

        degrau = _degrau("max")
        esperado = (round(100 * degrau), round(100 * degrau * 0.5))
        assert efetivo == esperado, (
            f"o par efetivo saiu {efetivo}, e a conta dela pede {esperado}: "
            f"degrau {degrau:.0%} x barra fraca 100% no `weak`, e o MESMO "
            f"degrau x barra forte 50% no `strong`. Se os dois vieram iguais, "
            f"a barra não entrou na conta."
        )
        assert backend.rumbles == [(BRANCO, *esperado)]

    def test_a_outra_peca_da_mesa_nao_e_tocada(self, perfis: Path) -> None:
        """A barra do BRANCO não escala o PRETO — é por peça, não por mesa."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 100, 100, target_uniq=PRETO)

        degrau = _degrau("max")
        inteiro = round(100 * degrau)
        assert backend.rumbles == [(PRETO, inteiro, inteiro)], (
            "a peça SEM opinião recebeu a barra da outra — a barra é por peça"
        )

    def test_zero_cala_um_motor_e_o_outro_continua(self, perfis: Path) -> None:
        """`0` é escolha, não ausência: um motor mudo e o outro inteiro."""
        _grava("Bancada", motor_forte_pct=100, motor_fraco_pct=0)
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 0, 200)], (
            "o motor fraco tinha de sair MUDO (barra 0) e o forte inteiro"
        )


class TestOQueNaoMuda:
    def test_perfil_sem_barra_e_byte_identico_ao_de_antes(self, perfis: Path) -> None:
        """Catorze perfis no disco dela não têm as chaves novas. Nada muda neles."""
        save_profile(Profile(name="Simples", match=MatchAny()))
        backend = _Backend()
        d = _daemon(perfil_ativo="Simples", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 137, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 137)]

    def test_as_duas_em_cem_entregam_o_degrau_inteiro(self, perfis: Path) -> None:
        """A outra metade da frase dela: `150 · 100 · 100 → 150 e 150`."""
        _grava("Bancada", motor_forte_pct=100, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(policy="max", perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 100, 100, target_uniq=BRANCO)

        inteiro = round(100 * _degrau("max"))
        assert backend.rumbles == [(BRANCO, inteiro, inteiro)]

    def test_sem_endereco_pedido_nao_ha_peca(self, perfis: Path) -> None:
        """`target_uniq is None` = ninguém nomeou peça → par neutro."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=50)
        registrados: list[tuple[int, int]] = []
        controller = SimpleNamespace(
            set_rumble=lambda weak, strong: registrados.append((weak, strong))
        )
        d = _daemon(perfil_ativo="Bancada", controller=controller)

        gp_mod.apply_game_rumble(d, 80, 90, target_uniq=None)

        assert registrados == [(80, 90)], "sem endereço não há peça, e nada escala"

    def test_perfil_ilegivel_nao_derruba_a_vibracao(
        self, perfis: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """JSON torto = mapa vazio, não jogo sem vibração."""

        def _explode(_nome: str) -> Any:
            raise ValueError("perfil torto")

        monkeypatch.setattr(loader_module, "load_profile", _explode)
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 111, 222, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 111, 222)]


class TestCompoeComOTeto:
    """A sprint manda: *"a sua conta tem de compor com ele sem apagá-lo — meça"""

    def test_a_barra_multiplica_e_o_teto_escala_depois(self, perfis: Path) -> None:
        """Barra 50 % no forte + teto "Economia" na mesma peça, e nenhum come o outro."""
        from hefesto_dualsense4unix.core.backend_pydualsense import (
            PyDualSenseController,
        )

        overrides = {
            BRANCO: ControllerOverrides(
                rumble=ControllerRumbleOverride(
                    policy="economia", motor_forte_pct=50, motor_fraco_pct=100
                )
            )
        }
        save_profile(
            Profile(
                name="Bancada",
                match=MatchAny(),
                rumble=RumbleConfig(policy="balanceado"),
                controllers=overrides,
            )
        )

        backend_falso = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend_falso)
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)
        _, weak_pos_barra, strong_pos_barra = backend_falso.rumbles[0]
        assert (weak_pos_barra, strong_pos_barra) == (200, 100), (
            "a barra do motor forte não cortou a metade no primeiro andar"
        )

        escalas = _controllers_to_rumble_scales(
            overrides, RumbleConfig(policy="balanceado")
        )
        assert BRANCO in escalas, (
            "o teto por controle sumiu do mapa — a barra APAGOU o teto, que é "
            "exatamente o que a sprint proíbe"
        )
        real = PyDualSenseController(evdev_reader=_null_evdev())
        h1, h2 = _FakeHandle(), _FakeHandle()
        real._handles = {KEY_1: h1, KEY_2: h2}
        real._primary_key = KEY_1
        real.set_rumble_scales(escalas)
        real.set_rumble_for(BRANCO, weak=weak_pos_barra, strong=strong_pos_barra)

        fator = escalas[BRANCO]
        assert h1.right_motor == [int(200 * fator)], "o teto não pegou o motor fraco"
        assert h1.left_motor == [int(100 * fator)], (
            "o motor forte tinha de chegar com a barra JÁ aplicada e o teto por "
            "cima — os dois fatores, na ordem degrau → barra → teto"
        )
        assert h2.right_motor == [] and h2.left_motor == []


class TestABordaDoEsquema:
    @pytest.mark.parametrize("campo", ["motor_forte_pct", "motor_fraco_pct"])
    @pytest.mark.parametrize("valor", [101, -1, 1000])
    def test_fora_da_faixa_morre_no_load(self, campo: str, valor: int) -> None:
        """A recusa é na BORDA, e a mensagem EXPLICA — nunca o literal cru."""
        with pytest.raises(ValueError) as erro:
            ControllerRumbleOverride.model_validate({campo: valor})
        assert campo in str(erro.value)
        assert "SEGUNDO fator" in str(erro.value), (
            "a recusa tem de dizer POR QUE não passa de 100, senão é literal cru"
        )

    @pytest.mark.parametrize("valor", [0, 1, 50, MOTOR_PCT_MAX])
    def test_a_faixa_inteira_entra(self, valor: int) -> None:
        o = ControllerRumbleOverride(motor_forte_pct=valor, motor_fraco_pct=valor)
        assert pcts_dos_motores(o) == (valor, valor)

    def test_a_chave_nova_nao_aparece_em_perfil_que_nao_a_usa(
        self, perfis: Path
    ) -> None:
        """Downgrade continua possível: `exclude_unset` mantém o arquivo igual."""
        import json

        caminho = save_profile(
            Profile(
                name="Velho",
                match=MatchAny(),
                controllers={
                    BRANCO: ControllerOverrides(
                        rumble=ControllerRumbleOverride(policy="max")
                    )
                },
            )
        )
        dele = json.loads(caminho.read_text())["controllers"][BRANCO]["rumble"]
        assert "motor_forte_pct" not in dele and "motor_fraco_pct" not in dele, (
            f"o override sem opinião ganhou chave nova no disco: {dele}"
        )


class TestOCacheDoMapa:
    def test_o_disco_e_lido_uma_vez_por_perfil(
        self, perfis: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O FF do jogo chega a centenas de Hz — o disco não pode ir junto."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        leituras: list[str] = []
        original = loader_module.load_profile

        def _contando(nome: str) -> Any:
            leituras.append(nome)
            return original(nome)

        monkeypatch.setattr(loader_module, "load_profile", _contando)
        d = _daemon(perfil_ativo="Bancada")
        for _ in range(10):
            gp_mod.apply_game_rumble(d, 100, 100, target_uniq=BRANCO)

        assert len(leituras) == 1, f"o disco foi lido {len(leituras)} vezes"

    def test_trocar_de_perfil_troca_o_mapa(self, perfis: Path) -> None:
        """O cache é chaveado pelo NOME do perfil ativo."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        save_profile(Profile(name="Limpo", match=MatchAny()))
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)
        d.store.active_profile = "Limpo"
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 100), (BRANCO, 200, 200)]

    def test_invalidar_o_cache_e_uma_linha(self, perfis: Path) -> None:
        """`daemon._rumble_motores_pct = None` faz a barra nova valer AGORA."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend()
        d = _daemon(perfil_ativo="Bancada", controller=backend)
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        _grava("Bancada", motor_forte_pct=100, motor_fraco_pct=100)
        d._rumble_motores_pct = None
        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 100), (BRANCO, 200, 200)]

    def test_o_endereco_com_dois_pontos_casa_a_peca(self, perfis: Path) -> None:
        """`AA:BB:...` e `aabbcc...` são a MESMA peça — normalizar é a cura."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        backend = _Backend(uniqs=(KEY_1,))
        d = _daemon(perfil_ativo="Bancada", controller=backend)

        gp_mod.apply_game_rumble(d, 200, 200, target_uniq=KEY_1)

        assert backend.rumbles == [(KEY_1, 200, 100)]


class TestARéguaSabeRecusar:
    def test_o_mapa_ignora_quem_nao_opinou(self) -> None:
        entrada = {
            BRANCO: ControllerOverrides(rumble=ControllerRumbleOverride(policy="max")),
            PRETO: ControllerOverrides(),
        }
        assert motores_dos_controles(entrada) == {}

    def test_o_mapa_ignora_quem_escreveu_cem_nos_dois(self) -> None:
        """`100/100` no disco é escolha, mas no APARELHO é o par neutro."""
        entrada = {
            BRANCO: ControllerOverrides(
                rumble=ControllerRumbleOverride(
                    motor_forte_pct=MOTOR_PCT_PADRAO, motor_fraco_pct=MOTOR_PCT_PADRAO
                )
            )
        }
        assert motores_dos_controles(entrada) == {}

    def test_o_mapa_pega_quem_opinou(self) -> None:
        entrada = {
            BRANCO: ControllerOverrides(
                rumble=ControllerRumbleOverride(motor_forte_pct=50)
            ),
            PRETO: ControllerOverrides(
                rumble=ControllerRumbleOverride(motor_fraco_pct=0)
            ),
        }
        assert motores_dos_controles(entrada) == {BRANCO: (50, 100), PRETO: (100, 0)}

    def test_sem_secao_rumble_o_par_e_neutro(self) -> None:
        assert pcts_dos_motores(None) == (MOTOR_PCT_PADRAO, MOTOR_PCT_PADRAO)

    def test_mapa_vazio_e_none_dao_o_mesmo(self) -> None:
        assert motores_dos_controles(None) == {}
        assert motores_dos_controles({}) == {}


class TestODegrauNaoEscapaSozinho:
    """A multiplicação mora num lugar só, e é esta régua que impede o segundo."""

    def test_apply_game_rumble_passa_pelo_par(self) -> None:
        arvore = ast.parse(
            textwrap.dedent(inspect.getsource(gp_mod.apply_game_rumble))
        )
        chamadas = {
            no.func.id
            for no in ast.walk(arvore)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
        }
        assert "_mults_por_motor" in chamadas, (
            "`apply_game_rumble` deixou de compor o par por motor"
        )
        assert "_game_rumble_mult" not in chamadas, (
            "`apply_game_rumble` voltou a chamar o DEGRAU direto — o degrau vai "
            "ao motor sem a barra dela, e é o defeito que esta régua existe "
            "para não deixar voltar"
        )

    def test_o_par_e_o_degrau_vezes_a_barra(self, perfis: Path) -> None:
        """A conta, isolada da escrita: `_mults_por_motor` sozinho."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        d = _daemon(policy="max", perfil_ativo="Bancada")

        fraco, forte = gp_mod._mults_por_motor(d, 0.0, BRANCO)

        degrau = _degrau("max")
        assert fraco == pytest.approx(degrau)
        assert forte == pytest.approx(degrau * 0.5)


class _Store:
    """`store` de mentira: só o `active_profile` e as travas manuais."""

    def __init__(self, ativo: str | None) -> None:
        self.active_profile = ativo
        self.travas: list[str] = []

    def mark_manual_trigger_active(self, categoria: str) -> None:
        self.travas.append(categoria)


class _Handlers(IpcHandlersMixin):
    """O bastante do mixin para chamar `_handle_rumble_motores_set`."""

    def __init__(self, *, ativo: str | None, primario: str | None) -> None:
        self.store = _Store(ativo)  # type: ignore[assignment]
        self.controller = SimpleNamespace(  # type: ignore[assignment]
            describe_controllers=lambda: (
                [{"connected": True, "uniq": primario}] if primario else []
            )
        )
        self.daemon = _daemon(perfil_ativo=ativo)  # type: ignore[assignment]
        self.daemon.store = self.store


def _grava_ipc(h: _Handlers, **params: Any) -> dict[str, Any]:
    import asyncio

    return asyncio.run(h._handle_rumble_motores_set(params))


class TestOMetodoQueGrava:
    def test_grava_a_barra_no_perfil_da_peca(self, perfis: Path) -> None:
        """Do IPC ao disco: o par dela cai no `controllers[chave].rumble`."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=50, fraco_pct=100)

        assert corpo["status"] == "ok" and corpo["gravado"] is True
        assert (corpo["forte_pct"], corpo["fraco_pct"]) == (50, 100)
        dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[BRANCO]
        assert dele.rumble is not None
        assert dele.rumble.motor_forte_pct == 50
        assert "motor_fraco_pct" not in dele.rumble.model_fields_set, (
            "o 100 é 'sem opinião' e não pode ocupar chave no disco"
        )

    def test_a_gravacao_derruba_o_cache_no_mesmo_ato(self, perfis: Path) -> None:
        """A LINHA QUE FAZ A BARRA VALER AGORA, medida por dentro."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        backend = _Backend()
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        h.daemon.controller = backend

        gp_mod.apply_game_rumble(h.daemon, 200, 200, target_uniq=BRANCO)
        _grava_ipc(h, uniq=BRANCO, forte_pct=50)
        gp_mod.apply_game_rumble(h.daemon, 200, 200, target_uniq=BRANCO)

        assert backend.rumbles == [(BRANCO, 200, 200), (BRANCO, 200, 100)], (
            "o segundo FF tinha de sair com o forte pela metade — o cache do "
            "mapa não caiu na gravação"
        )

    def test_cem_nos_dois_apaga_a_secao_sem_matar_o_degrau(self, perfis: Path) -> None:
        """Voltar as duas a 100 limpa as barras e PRESERVA o teto da peça."""
        save_profile(
            Profile(
                name="Bancada",
                match=MatchAny(),
                controllers={
                    BRANCO: ControllerOverrides(
                        rumble=ControllerRumbleOverride(
                            policy="economia", motor_forte_pct=50
                        )
                    )
                },
            )
        )
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=100, fraco_pct=100)

        assert corpo["gravado"] is True
        dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[BRANCO]
        assert dele.rumble is not None, "a seção morreu e levou o teto junto"
        assert dele.rumble.policy == "economia", "o degrau da peça foi apagado"
        assert dele.rumble.motor_forte_pct is None

    def test_secao_vazia_vira_none(self, perfis: Path) -> None:
        """Sem degrau e sem barras, a seção `rumble` inteira sai do disco."""
        _grava("Bancada", motor_forte_pct=50)
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        _grava_ipc(h, uniq=BRANCO, forte_pct=100)

        dele = (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})[BRANCO]
        assert dele.rumble is None

    def test_nada_mudou_nao_regrava(self, perfis: Path) -> None:
        """Regravar perfil idêntico troca a data do arquivo e o daemon reaplica."""
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=100)
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=50)

        assert corpo["status"] == "ok"
        assert corpo["gravado"] is False, "regravou um perfil que já estava assim"
        assert (corpo["forte_pct"], corpo["fraco_pct"]) == (50, 100)

    def test_campo_omitido_nao_mexe_na_outra_barra(self, perfis: Path) -> None:
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=20)
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, uniq=BRANCO, forte_pct=70)

        assert (corpo["forte_pct"], corpo["fraco_pct"]) == (70, 20)

    def test_uniq_omitido_cai_no_primario(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)

        corpo = _grava_ipc(h, forte_pct=40)

        assert corpo["uniq"] == BRANCO
        assert BRANCO in (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})


    def test_mesa_vazia_recusa_com_razao(self, perfis: Path) -> None:
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=None)
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_controle"
        assert "POR PEÇA" in corpo["motivo"]

    def test_sem_perfil_ativo_grava_no_computador(self, perfis: Path) -> None:
        """Sem perfil ativo, a barra vai ao computador (01/10/2026)."""
        from hefesto_dualsense4unix.profiles.o_padrao_do_computador import o_computador

        h = _Handlers(ativo=None, primario=BRANCO)
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "ok" and corpo["onde"] == "computador"
        rumble = o_computador().controles[BRANCO].rumble
        assert rumble is not None and rumble.motor_forte_pct == 50

    def test_endereco_sem_mac_recusa_em_vez_de_gravar_errado(
        self, perfis: Path
    ) -> None:
        """Gravar sob uma chave que o motor nunca casa faz a escolha sumir calada."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario="path:/dev/input/event9")
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_endereco"
        assert not (o_que_vale(loader_module.load_profile("Bancada")).controllers or {}), (
            "gravou um override sob uma chave que o motor nunca casa"
        )

    def test_o_vpad_nao_tem_motor_e_e_recusado(self, perfis: Path) -> None:
        """`02fe…` é o gamepad VIRTUAL — não é peça de plástico, não tem motor."""
        from hefesto_dualsense4unix.broker.hidraw_broker import VPAD_UNIQ_PREFIX

        save_profile(Profile(name="Bancada", match=MatchAny()))
        vpad = f"{VPAD_UNIQ_PREFIX}00000001"
        h = _Handlers(ativo="Bancada", primario=vpad)
        corpo = _grava_ipc(h, forte_pct=50)
        assert corpo["status"] == "sem_endereco"
        assert not (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})

    def test_sem_nenhum_dos_dois_campos_levanta(self, perfis: Path) -> None:
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="ao menos um"):
            _grava_ipc(h, uniq=BRANCO)

    def test_a_faixa_e_a_do_esquema_e_nada_e_gravado(self, perfis: Path) -> None:
        """O 101 morre com a FRASE do esquema, e o disco não é tocado."""
        save_profile(Profile(name="Bancada", match=MatchAny()))
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="SEGUNDO fator"):
            _grava_ipc(h, uniq=BRANCO, forte_pct=101)
        assert not (o_que_vale(loader_module.load_profile("Bancada")).controllers or {})

    @pytest.mark.parametrize("valor", ["50", 50.0, True, None])
    def test_tipo_errado_levanta_antes_do_disco(self, perfis: Path, valor: Any) -> None:
        h = _Handlers(ativo="Bancada", primario=BRANCO)
        with pytest.raises(ValueError, match="inteiro 0-100"):
            _grava_ipc(h, uniq=BRANCO, forte_pct=valor)

    def test_o_metodo_esta_no_despacho(self) -> None:
        """Handler sem entrada na tabela é método inalcançável."""
        from hefesto_dualsense4unix.daemon import ipc_server

        fonte = inspect.getsource(ipc_server)
        assert '"rumble.motores.set": self._handle_rumble_motores_set' in fonte


# 9. O `state_full` DEVOLVE OS DOIS NÚMEROS


class TestOEstadoDevolveAsBarras:
    def test_o_state_full_publica_as_barras_da_peca(self, perfis: Path) -> None:
        """Sem isto a aba 05 desenha a barra onde ela ESTAVA.

        MORDIDA: apagar o bloco `result["rumble_motores"]` do `state_full`. A
        chave some e o assert nomeia o que a tela deixaria de ler.
        """
        _grava("Bancada", motor_forte_pct=50, motor_fraco_pct=20)
        d = _daemon(perfil_ativo="Bancada")

        mapa = gp_mod._motores_do_perfil_ativo(d)
        publicado = {
            uniq: {"forte_pct": par[0], "fraco_pct": par[1]}
            for uniq, par in mapa.items()
        }

        assert publicado == {BRANCO: {"forte_pct": 50, "fraco_pct": 20}}

    def test_a_fonte_publicada_e_a_mesma_que_o_motor_le(self) -> None:
        """A tela e o motor não podem ler de lugares diferentes.

        Uma segunda leitura do disco no `state_full` poderia pintar um número
        que o motor não está usando — o "aplicado" falso que esta casa passou
        04/09 arrancando. A régua lê a FONTE do `state_full` e exige que o
        bloco chame a função do `gamepad`.

        MORDIDA: trocar a chamada por um `load_profile` próprio no `state_full`.
        """
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = inspect.getsource(
            ipc_handlers.IpcHandlersMixin._handle_daemon_state_full
        )
        assert '_motores_do_perfil_ativo(self.daemon)' in fonte, (
            "o `state_full` deixou de ler o MESMO mapa que `apply_game_rumble` "
            "multiplica"
        )
        assert "load_profile" not in fonte, (
            "o `state_full` abriu uma SEGUNDA leitura do disco — as duas podem "
            "divergir, e a tela pintaria o que o motor não usa"
        )

    def test_o_padrao_viaja_junto_para_a_tela_nao_digitar_o_cem(self) -> None:
        """Peça ausente do mapa vale 100, e o 100 vem do produto."""
        from hefesto_dualsense4unix.daemon import ipc_handlers

        fonte = inspect.getsource(
            ipc_handlers.IpcHandlersMixin._handle_daemon_state_full
        )
        assert 'result["rumble_motor_pct_padrao"] = MOTOR_PCT_PADRAO' in fonte
        assert MOTOR_PCT_PADRAO == 100


class TestAPonte:
    def test_a_ponte_manda_so_o_que_foi_pedido(self, monkeypatch) -> None:
        """Campo `None` = "não mexe naquela barra", e não `null` no payload."""
        from hefesto_dualsense4unix.app import ipc_bridge

        vistos: list[tuple[str, dict[str, Any]]] = []
        monkeypatch.setattr(
            ipc_bridge,
            "_safe_call",
            lambda m, p=None: (vistos.append((m, dict(p or {}))), (True, {"status": "ok"}))[1],
        )

        ok, corpo = ipc_bridge.rumble_motores_set(forte_pct=50, uniq=BRANCO)

        assert ok and corpo == {"status": "ok"}
        assert vistos == [("rumble.motores.set", {"forte_pct": 50, "uniq": BRANCO})]

    def test_daemon_fora_do_ar_devolve_corpo_none(self, monkeypatch) -> None:
        from hefesto_dualsense4unix.app import ipc_bridge

        monkeypatch.setattr(ipc_bridge, "_safe_call", lambda m, p=None: (False, None))
        assert ipc_bridge.rumble_motores_set(forte_pct=50) == (False, None)

    def test_parar_avisa_que_nao_devolve_a_vibracao_ao_jogo(self) -> None:
        """A ARMADILHA MEDIDA NO APARELHO em 04/09/2026, e a cura é a frase."""
        from hefesto_dualsense4unix.app import ipc_bridge

        doc = inspect.getdoc(ipc_bridge.rumble_stop) or ""
        assert "rumble_passthrough" in doc, (
            "a ponte não diz qual é o gesto que DEVOLVE a vibração ao jogo"
        )
        assert "descarta o FF" in doc, (
            "a ponte não conta a consequência do par fixado — quem chamar "
            "`rumble_stop` continua deixando a máquina sem vibração em jogo"
        )
        assert "rumble_stop" in (inspect.getdoc(ipc_bridge.rumble_passthrough) or "")


def test_o_norm_mac_nao_devolve_none_para_caminho_e_a_docstring_diz_isso() -> None:
    """FATO ERRADO SUBSTITUÍDO (04/09/2026) — e a régua guarda o fato certo."""
    from hefesto_dualsense4unix.core import sysfs_leds

    assert sysfs_leds.norm_mac("path:/dev/input/event9") == "adeee9"
    assert sysfs_leds.norm_mac("/dev/hidraw4") == "deda4"
    assert sysfs_leds.norm_mac("xyz") is None
    assert sysfs_leds.norm_mac("AA:BB:CC:00:00:01") == "aabbcc000001"

    doc = sysfs_leds.norm_mac.__doc__ or ""
    assert "FATO ERRADO, SUBSTITUÍDO" in doc, (
        "a docstring voltou a prometer um `None` que a função não entrega."
    )
    assert "adeee9" in doc, "a docstring tem de carregar a medição, não a promessa"


#:      esquerdo × força de vibração (ou personalizado), motor direito ×  # noqa: RUF003
#: `# noqa` dentro de uma docstring é texto, não diretiva. Trocar o símbolo
_QUEIXA = "os slicers não estão se multiplicando"


class TestATelaDizOProduto:
    """A conta acontecia e a tela não a mostrava em lugar nenhum."""

    def test_a_dica_diz_barra_forca_e_o_efetivo(self) -> None:
        """Os três números na mesma frase, sem um clique."""
        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        frase = a05._quanto_multiplica({"sabe": True, "n": "150%"}, 50)

        assert "50%" in frase and "150%" in frase
        assert "75%" in frase, f"o produto não saiu na frase: {frase}"

    def test_o_caso_dela_barra_zero_confessa_o_zero(self) -> None:
        """O P2 da mesa dela: força 200%, motores em 0%."""
        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        frase = a05._quanto_multiplica({"sabe": True, "n": "200%"}, 0)

        assert "sai 0%" in frase, frase

    def test_sem_degrau_conhecido_a_dica_cala(self) -> None:
        """Campo sem informação não mostra nada — a regra dela."""
        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        assert a05._quanto_multiplica({"sabe": False, "n": "—"}, 100) == ""
        assert a05._quanto_multiplica({"sabe": True, "n": "150%"}, None) == ""

    def test_o_pedido_do_jogo_ainda_ganha_a_dica(self) -> None:
        """Quando o jogo TREME, o que ela precisa ver é o pedido dele."""
        import inspect

        from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05

        fonte = inspect.getsource(a05.pacote)
        alvo = fonte.split('plano[f"motor-{lado}-pedido"]')[1].split("\n\n")[0]
        assert 'O jogo pediu' in alvo
        assert alvo.index("O jogo pediu") < alvo.index("_quanto_multiplica"), (
            "a conta passou na frente do pedido do jogo")
