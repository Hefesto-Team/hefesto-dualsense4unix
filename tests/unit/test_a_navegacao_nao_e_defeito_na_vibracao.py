"""A-NAVEGACAO-NAO-E-DEFEITO-NA-VIBRACAO-01 — na Navegação a aba Vibração não acusa defeito.

``D-2909-A-NAVEGACAO-NAO-E-AVISO-NA-VIBRACAO`` (dela, 29/09/2026 ~21h45, *«1, ok
pode ser.»*): na Navegação nenhum jogo recebe gamepad (``D-1409``) e a
intensidade escolhida fica guardada e vale no primeiro pedido de um jogo com
gamepad. A faixa laranja e o ``rumble_sem_dono`` do diário ficam só para a
FALHA do sistema: emulação ligada e nenhum gamepad virtual.

O predicado ``sem_dono_do_rumble`` envelheceu em 14/09 e a tela e o diário
herdaram o erro. A cura é um dono só para a pergunta.

AS MORDIDAS (executadas na implementação):

* tire o ``emulacao and`` do predicado → a faixa volta na Navegação
  (``test_na_navegacao_a_faixa_cala``) e o diário volta a acusar
  (``test_o_diario_so_acusa_a_falha``);
* apague o ``if sem_dono_do_rumble(...)`` de ``rumble_actions`` →
  ``test_no_vpad_que_nao_subiu_a_faixa_fica`` reprova;
* passe ``emulacao=True`` fixo no chamador do ``launch_env`` →
  ``test_o_diario_so_acusa_a_falha`` reprova nos casos de Navegação;
* escreva ``not native and not backends`` à mão no ``launch_env`` →
  ``test_um_dono_so_para_a_pergunta`` reprova nomeando o arquivo;
* devolva a causa «Navegação» ao texto →
  ``test_nenhuma_frase_da_tela_fala_da_navegacao_como_causa`` reprova.
"""
from __future__ import annotations

import ast
import pathlib
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `app.actions.rumble_actions`, que carrega o GTK")

from hefesto_dualsense4unix.app.actions import rumble_actions as _ra
from hefesto_dualsense4unix.app.telas import vibracao as _tela

SRC = pathlib.Path(__file__).resolve().parents[2] / "src" / "hefesto_dualsense4unix"
DONO = "daemon/subsystems/rumble.py"


def _estado(*, enabled: bool | None, vpads: int, native: bool = False) -> dict[str, Any]:
    """O ``state_full`` mínimo; ``enabled=None`` = daemon velho, sem o bloco."""
    estado: dict[str, Any] = {
        "rumble_policy": "balanceado",
        "rumble_mult_applied": 1.0,
        "native_mode": native,
        "rumble_ff": {"plays": 0, "nao_nulos": 0, "vpads": vpads},
    }
    if enabled is not None:
        estado["gamepad_emulation"] = {"enabled": enabled}
    return estado


@pytest.fixture(autouse=True)
def _sem_orcamento_da_maquina(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(_tela, "_orcamento_da_maquina", lambda: None)


def _alertas(estado: dict[str, Any]) -> list[str]:
    return [f for tom, f in _tela.textos_do_estado(estado) if tom == _tela.ALERTA]


# 1 ----------------------------------------------------------------------------
def test_na_navegacao_a_faixa_cala() -> None:
    """Navegação: emulação desligada, nenhum vpad. O estado é da mesa inteira.

    A Navegação desmonta os jogadores (`mode_transition`), então `vpads` é zero
    para os quatro controles, no cabo e no rádio; o `state_full` não traz nada
    por controle, e a mesma resposta vale de um a quatro.
    """
    estado = _estado(enabled=False, vpads=0)
    assert _ra.texto_do_alcance_da_intensidade(estado) is None
    assert _alertas(estado) == []


# 2 ----------------------------------------------------------------------------
def test_no_vpad_que_nao_subiu_a_faixa_fica() -> None:
    estado = _estado(enabled=True, vpads=0)
    texto = _ra.texto_do_alcance_da_intensidade(estado)
    assert texto is not None
    assert texto.startswith(_ra._ALCANCE_O_QUE_ACONTECE)
    assert _alertas(estado) == [texto]


def test_sem_o_bloco_da_emulacao_a_resposta_e_nao_sei() -> None:
    """Daemon velho: nem a Navegação nem a falha se afirmam."""
    assert _ra.texto_do_alcance_da_intensidade(_estado(enabled=None, vpads=0)) is None


# 3 ----------------------------------------------------------------------------
class _RegistroDeLog:
    def __init__(self) -> None:
        self.eventos: list[tuple[str, str]] = []

    def __getattr__(self, nivel: str) -> Any:
        def _log(evento: str, **_kw: Any) -> None:
            self.eventos.append((nivel, evento))

        return _log


class _DaemonFalso:
    """O mínimo que ``_snapshot`` toca: Nativo, emulação e vpads."""

    def __init__(self, *, emulacao: bool, vpad: bool) -> None:
        self.config = SimpleNamespace(
            gamepad_emulation_enabled=emulacao,
            gamepad_flavor="dualsense",
            rumble_active=None,
        )
        self._gamepad_device: Any = (
            SimpleNamespace(backend="uhid", flavor="dualsense") if vpad else None
        )
        self._coop_manager = None
        self.controller = SimpleNamespace(set_rumble=lambda **_k: None)

    def is_native_mode(self) -> bool:
        return False

    def parar_a_emulacao(self) -> None:
        """O que o desligar do serviço faz antes de sair."""
        self.config.gamepad_emulation_enabled = False
        self._gamepad_device = None


@pytest.fixture()
def _borda(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> _RegistroDeLog:
    from hefesto_dualsense4unix.daemon import launch_env as le

    registro = _RegistroDeLog()
    monkeypatch.setattr(le, "logger", registro)
    monkeypatch.setattr(le, "launch_env_dir", lambda ensure=False: tmp_path)
    monkeypatch.setattr(le, "_steam_profiles", lambda daemon: [])
    monkeypatch.setattr(le, "_load_profiles", lambda daemon: [])
    return registro


def _avisos(registro: _RegistroDeLog) -> list[str]:
    return [e for n, e in registro.eventos if n == "warning"]


@pytest.mark.parametrize("fisicos", [1, 2, 3, 4])
def test_o_diario_so_acusa_a_falha(
    fisicos: int, _borda: _RegistroDeLog, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.daemon import launch_env as le

    monkeypatch.setattr(le, "_fisicos_na_mesa", lambda daemon: fisicos)

    # a troca para a Navegação: emulação desligada, nenhum vpad
    le.materialize_launch_env(_DaemonFalso(emulacao=False, vpad=False))  # type: ignore[arg-type]
    assert "rumble_sem_dono" not in _avisos(_borda), "a Navegação foi chamada de «sem dono»"

    # o desligar do serviço: a emulação para um instante antes de sair
    daemon = _DaemonFalso(emulacao=True, vpad=True)
    daemon.parar_a_emulacao()
    le.materialize_launch_env(daemon)  # type: ignore[arg-type]
    assert "rumble_sem_dono" not in _avisos(_borda), "o desligar do serviço foi acusado"

    # a falha: emulação ligada e o gamepad virtual não subiu
    le.materialize_launch_env(_DaemonFalso(emulacao=True, vpad=False))  # type: ignore[arg-type]
    assert "rumble_sem_dono" in _avisos(_borda), "a falha do vpad deixou de ser acusada"


# 4 ----------------------------------------------------------------------------
def _chamadas_do_predicado() -> list[tuple[str, ast.Call]]:
    achadas = []
    for arq in sorted(SRC.rglob("*.py")):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.Call):
                f = no.func
                nome = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
                if nome == "sem_dono_do_rumble":
                    achadas.append((arq.relative_to(SRC).as_posix(), no))
    return achadas


def _conta_a_mao(arvore: ast.AST) -> bool:
    """``not native and not backends`` escrito à mão, em qualquer ordem."""
    for no in ast.walk(arvore):
        if isinstance(no, ast.BoolOp) and isinstance(no.op, ast.And):
            negados = {
                v.operand.id
                for v in no.values
                if isinstance(v, ast.UnaryOp)
                and isinstance(v.op, ast.Not)
                and isinstance(v.operand, ast.Name)
            }
            if {"native", "backends"} <= negados:
                return True
    return False


def test_um_dono_so_para_a_pergunta() -> None:
    chamadas = _chamadas_do_predicado()
    arquivos = sorted({a for a, _ in chamadas})
    assert arquivos == ["app/actions/rumble_actions.py", "daemon/launch_env.py"], (
        f"o predicado mudou de chamadores: {arquivos}"
    )
    for arquivo, no in chamadas:
        assert "emulacao" in {k.arg for k in no.keywords}, (
            f"{arquivo}:{no.lineno} chama o predicado sem `emulacao=` pelo nome"
        )
    fora = [
        arq.relative_to(SRC).as_posix()
        for arq in sorted(SRC.rglob("*.py"))
        if arq.relative_to(SRC).as_posix() != DONO
        and _conta_a_mao(ast.parse(arq.read_text(encoding="utf-8")))
    ]
    assert fora == [], f"a conta do predicado foi reescrita à mão em: {fora}"


def test_o_parametro_e_obrigatorio() -> None:
    from hefesto_dualsense4unix.daemon.subsystems.rumble import sem_dono_do_rumble

    with pytest.raises(TypeError):
        sem_dono_do_rumble(native=False, backends=())  # type: ignore[call-arg]


# 5 ----------------------------------------------------------------------------
ESTADOS = {
    "navegação": _estado(enabled=False, vpads=0),
    "gamepad de pé": _estado(enabled=True, vpads=1),
    "vpad não subiu": _estado(enabled=True, vpads=0),
    "nativo": _estado(enabled=False, vpads=0, native=True),
    "daemon sem o bloco": _estado(enabled=None, vpads=0),
}


@pytest.mark.parametrize("nome", sorted(ESTADOS))
def test_nenhuma_frase_da_tela_fala_da_navegacao_como_causa(nome: str) -> None:
    texto = _ra.texto_do_alcance_da_intensidade(ESTADOS[nome])
    if texto is not None:
        assert "Navegação" not in texto, f"«{nome}»: {texto!r}"
