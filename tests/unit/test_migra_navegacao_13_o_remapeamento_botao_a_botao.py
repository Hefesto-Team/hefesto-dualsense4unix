#!/usr/bin/env python3
"""F1-REMAPEAR — a troca botão a botão, da tela ao jogo. 13/09/2026.

O CONTRATO é o da MIGRA-NAVEGACAO-13 com a ROTA CORRIGIDA da F1-REMAPEAR:
o motor puro (`core/remapeamento_de_botao.py`), o campo do perfil omitido
quando vazio, o depósito na ativação, a tradução logo antes dos DOIS
`forward_buttons` (o do primário e o do co-op). A tela "Trocar os botões" mora no mapa do
controle desde 15/10/2026 (`test_a_aba_mapa_do_controle_do_todo.py`).

**ELA LÊ, NÃO DIGITA** o que tem dono: os botões saem de `core.acoes_de_botao.BOTOES` e o
vocabulário do jogo de `core.evdev_reader.EvdevReader.BUTTON_MAP`.

A MORDIDA, e cada uma foi rodada na entrega desta sprint:

- arranque o `if troca:` de `gamepad.dispatch_gamepad` e
  :func:`test_o_primario_passa_pela_troca` reprova — o jogo veria o ✕;
- idem em `coop.CoopManager.forward_all` e
  :func:`test_os_secundarios_passam_pela_troca` reprova;
- aplique o mapa em cadeia em `traduzir` e
  :func:`test_a_troca_dupla_vale_nos_dois_sentidos` reprova;
- tire `remapeamento=self.source_remapeamento` de `DraftConfig.to_profile` e
  :func:`test_o_salvar_da_aba_perfis_nao_apaga_a_troca` reprova.
"""
from __future__ import annotations

import ast
import json
import pathlib
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src"
INTERFACE = SRC / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(SRC), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.core import remapeamento_de_botao as remap

PAGINA = "06-navegacao.html"  # (noqa-acento) nome de arquivo
CHROME = pathlib.Path("/usr/bin/google-chrome")
NOME = "Régua da Troca"


def test_a_troca_dupla_vale_nos_dois_sentidos() -> None:
    """`{✕: ○, ○: ✕}` — apertar ✕ o jogo vê ○, e apertar ○ o jogo vê ✕."""
    mapa = remap.resolver({"cross": "circle", "circle": "cross"})
    assert remap.traduzir(frozenset({"cross"}), 0, 0, mapa)[0] == {"circle"}
    assert remap.traduzir(frozenset({"circle"}), 0, 0, mapa)[0] == {"cross"}, (
        "apertar ○ voltou a ser ○ — a troca foi aplicada em cadeia, e a segunda "
        "leu a primeira")
    assert remap.traduzir(frozenset({"cross", "circle"}), 0, 0, mapa)[0] == {
        "cross", "circle"}


def test_a_cadeia_le_o_retrato_e_nao_e_recusa() -> None:
    """`L1→R1, R1→△` tem um sentido só: cada origem lê o que foi APERTADO."""
    mapa = remap.resolver({"l1": "r1", "r1": "triangle"})
    assert remap.traduzir(frozenset({"l1"}), 0, 0, mapa)[0] == {"r1"}
    assert remap.traduzir(frozenset({"l1", "r1"}), 0, 0, mapa)[0] == {"r1", "triangle"}


def test_a_colisao_e_recusa_nomeando_os_tres() -> None:
    """Dois botões para o mesmo destino: recusa nomeando os dois e o destino."""
    with pytest.raises(remap.RemapeamentoRecusadoError) as recusa:
        remap.resolver({"l1": "r1", "l2": "r1"})
    assert recusa.value.motivo == remap.MOTIVO_COLISAO
    assert recusa.value.botoes == ("l1", "l2", "r1")


@pytest.mark.parametrize("mapa", [{"ps": "cross"}, {"cross": "ps"}])
def test_o_ps_nao_se_troca_em_lado_nenhum(mapa: dict[str, str]) -> None:
    """Os cinco gestos começam no PS: trocá-lo tira a saída de emergência."""
    with pytest.raises(remap.RemapeamentoRecusadoError) as recusa:
        remap.resolver(mapa)
    assert recusa.value.motivo == remap.MOTIVO_PS


@pytest.mark.parametrize("mapa", [
    {"l3_direcao": "r3_direcao"},
    {"cross": remap.DESTINO_TOUCHPAD},
    {"touchpad_left_press": "cross"},
])
def test_o_que_nao_e_botao_do_jogo_fica_fora(mapa: dict[str, str]) -> None:
    with pytest.raises(remap.RemapeamentoRecusadoError) as recusa:
        remap.resolver(mapa)
    assert recusa.value.motivo == remap.MOTIVO_FORA


def test_botao_desconhecido_e_recusa_e_a_troca_por_si_mesmo_some() -> None:
    with pytest.raises(remap.RemapeamentoRecusadoError) as recusa:
        remap.resolver({"botao_que_nao_existe": "cross"})
    assert recusa.value.motivo == remap.MOTIVO_DESCONHECIDO
    assert remap.resolver({"cross": "cross"}) == {}
    assert remap.resolver(None) == {}


def test_os_gatilhos_levam_a_forca_junto() -> None:
    """O gatilho é o bit e o eixo: a troca leva os dois."""
    assert remap.traduzir(frozenset({"cross"}), 0, 0, {"cross": "l2"}) == (
        frozenset({"l2_btn"}), remap.FORCA_CHEIA, 0)
    assert remap.traduzir(frozenset({"l2_btn"}), 180, 0, {"l2": "cross"}) == (
        frozenset({"cross"}), 0, 0)
    assert remap.traduzir(frozenset({"l2_btn"}), 180, 40, {"l2": "r2", "r2": "l2"}) == (
        frozenset({"r2_btn"}), 40, 180)


def test_o_que_nao_esta_no_mapa_passa_intacto() -> None:
    assert remap.traduzir(frozenset({"mic_btn", "cross", "ps"}), 3, 4,
                          {"circle": "square"}) == (
        frozenset({"mic_btn", "cross", "ps"}), 3, 4)


def test_a_lista_do_motor_e_a_do_produto_e_a_do_leitor() -> None:
    """`REMAPEAVEIS` é digitada no motor por custo de import — e é presa aqui."""
    from hefesto_dualsense4unix.core import acoes_de_botao as acoes
    from hefesto_dualsense4unix.core.evdev_reader import EvdevReader

    assert remap.BOTAO_PS == acoes.BOTAO_PS
    assert list(remap.REMAPEAVEIS) == [b for b in acoes.BOTOES if b in remap.REMAPEAVEIS]
    assert set(remap.REMAPEAVEIS) | set(remap.FORA_DO_ALCANCE) | {remap.BOTAO_PS} == (
        set(acoes.BOTOES) | {remap.DESTINO_TOUCHPAD})
    dpad = {"dpad_up", "dpad_down", "dpad_left", "dpad_right"}
    do_jogo = (set(EvdevReader.BUTTON_MAP.values()) - {remap.BOTAO_PS}) | dpad
    assert {remap.GATILHOS.get(b, b) for b in remap.REMAPEAVEIS} == do_jogo, (
        "a troca e o leitor evdev não falam do mesmo conjunto de botões — uma "
        "linha trocaria um nome que o jogo nunca recebe")


class _Device:
    """O gamepad virtual de mentira: guarda o que o jogo receberia."""

    def __init__(self) -> None:
        self.analog: list[dict[str, int]] = []
        self.buttons: list[frozenset[str]] = []

    def forward_analog(self, **kw: int) -> None:
        self.analog.append(kw)

    def forward_buttons(self, pressed: frozenset[str]) -> None:
        self.buttons.append(pressed)


_ESTADO_DO_CONTROLE = SimpleNamespace(raw_lx=128, raw_ly=128, raw_rx=128,
                                      raw_ry=128, l2_raw=0, r2_raw=0)


def _despachar_o_primario(monkeypatch: pytest.MonkeyPatch, store: Any,
                          apertados: frozenset[str]) -> _Device:
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    dev = _Device()
    gp.dispatch_gamepad(SimpleNamespace(store=store, _gamepad_device=dev),
                        _ESTADO_DO_CONTROLE, apertados)
    return dev


def test_o_primario_passa_pela_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    """✕→○ ativo: o jogo recebe ○ — e o conjunto que o laço tem continua ✕."""
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    remap.definir_ativo(store, {"cross": "circle"})
    apertados = frozenset({"cross"})
    dev = _despachar_o_primario(monkeypatch, store, apertados)
    assert dev.buttons == [frozenset({"circle"})], (
        f"o jogo recebeu {dev.buttons} — a troca do perfil não chegou ao "
        "`forward_buttons` do primário")
    assert apertados == frozenset({"cross"})


def test_sem_troca_o_jogo_recebe_o_mesmo_objeto(monkeypatch: pytest.MonkeyPatch) -> None:
    """A régua de custo: sem troca, o tique não aloca nada — é o MESMO objeto."""
    store = SimpleNamespace(udp_trigger_thresholds=(0, 0))
    for mapa in (None, {}):
        remap.definir_ativo(store, mapa)
        apertados = frozenset({"cross", "l1"})
        dev = _despachar_o_primario(monkeypatch, store, apertados)
        assert dev.buttons[-1] is apertados
    from unittest.mock import MagicMock

    assert remap.ativo(MagicMock()) is None


def test_os_secundarios_passam_pela_troca() -> None:
    """A mesma troca no `forward_all` do co-op — gatilho incluído."""
    from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager, _SecondaryPlayer

    store = SimpleNamespace()
    remap.definir_ativo(store, {"cross": "circle", "l2": "r2"})
    daemon = SimpleNamespace(
        store=store, controller=SimpleNamespace(), identity_registry=None,
        config=SimpleNamespace(coop_enabled=True, gamepad_flavor="dualsense"),
        _gamepad_device=object(), _coop_manager=None)
    mgr = CoopManager(daemon)
    snap = SimpleNamespace(lx=1, ly=2, rx=3, ry=4, l2_raw=90, r2_raw=0,
                           buttons_pressed=frozenset({"cross", "l2_btn"}))
    vpad = _Device()
    leitor = SimpleNamespace(grab_state="held", snapshot=lambda: snap)
    mgr._players["aabbcc000002"] = _SecondaryPlayer(
        identity="aabbcc000002", evdev_path="/dev/input/event9",
        reader=leitor, player_index=2, vpad=vpad)  # type: ignore[arg-type]
    mgr.forward_all()
    assert vpad.buttons == [frozenset({"circle", "r2_btn"})], (
        f"o jogador 2 mandou {vpad.buttons} ao jogo — a troca não chegou ao "
        "`forward_buttons` do co-op")
    assert vpad.analog[-1]["l2"] == 0 and vpad.analog[-1]["r2"] == 90


def _chamadas_da_traducao() -> set[tuple[str, str]]:
    """Onde, em `src/`, alguém chama o `traduzir` do motor — arquivo e função."""
    alvo = "hefesto_dualsense4unix.core.remapeamento_de_botao"
    achados: set[tuple[str, str]] = set()
    for arq in sorted((SRC / "hefesto_dualsense4unix").rglob("*.py")):
        arvore = ast.parse(arq.read_text(encoding="utf-8"))
        nomes: set[str] = set()
        modulos: set[str] = set()
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module == alvo:
                nomes |= {a.asname or a.name for a in no.names if a.name == "traduzir"}
            if isinstance(no, ast.ImportFrom) and no.module == "hefesto_dualsense4unix.core":
                modulos |= {a.asname or a.name for a in no.names
                            if a.name == "remapeamento_de_botao"}
        if not nomes and not modulos:
            continue
        for funcao in ast.walk(arvore):
            if not isinstance(funcao, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for no in ast.walk(funcao):
                if not isinstance(no, ast.Call):
                    continue
                f = no.func
                if (isinstance(f, ast.Name) and f.id in nomes) or (
                        isinstance(f, ast.Attribute) and f.attr == "traduzir"
                        and isinstance(f.value, ast.Name) and f.value.id in modulos):
                    achados.add((arq.relative_to(SRC).as_posix(), funcao.name))
    return achados


def test_a_troca_mora_em_dois_lugares_so() -> None:
    """Só os dois `forward_buttons` traduzem — o PS e o atalho veem o original."""
    assert _chamadas_da_traducao() == {
        ("hefesto_dualsense4unix/daemon/subsystems/gamepad.py", "dispatch_gamepad"),
        ("hefesto_dualsense4unix/daemon/subsystems/coop.py", "forward_all"),
    }


def _perfil(**campos: Any) -> Any:
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile(name=NOME, match={"type": "any"}, **campos)


def test_perfil_sem_troca_nao_grava_a_chave() -> None:
    """Sem a omissão, um binário anterior (`extra="forbid"`) recusaria TODO perfil."""
    from hefesto_dualsense4unix.profiles import loader

    sem = json.loads(loader.save_profile(_perfil()).read_text(encoding="utf-8"))
    assert "remapeamento" not in sem, sem
    assert _perfil(remapeamento={}).remapeamento is None
    assert _perfil(remapeamento={"cross": "cross"}).remapeamento is None
    com = json.loads(loader.save_profile(
        _perfil(remapeamento={"cross": "circle"})).read_text(encoding="utf-8"))
    assert com["remapeamento"] == {"cross": "circle"}
    assert loader.load_profile(NOME).remapeamento == {"cross": "circle"}


def test_o_perfil_recusa_a_troca_que_o_motor_recusa() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="ps"):
        _perfil(remapeamento={"ps": "cross"})


def test_a_ativacao_deposita_a_troca_e_o_perfil_seguinte_a_apaga(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles import manager as gerente

    store = StateStore()
    m = gerente.ProfileManager(controller=SimpleNamespace(), store=store)  # type: ignore[arg-type]
    for nome_do_metodo in ("apply", "apply_keyboard", "apply_button_actions",
                           "apply_emulation"):
        monkeypatch.setattr(m, nome_do_metodo, lambda *a, **k: None)
    monkeypatch.setattr(gerente, "load_profile",
                        lambda nome: _perfil(remapeamento={"cross": "circle"}))
    relatorio: dict[str, str] = {}
    m.activate(NOME, origin="system", relatorio=relatorio)
    assert dict(remap.ativo(store) or {}) == {"cross": "circle"}, (
        "a ativação não depositou a troca no `store` — os dois `forward_buttons` "
        "não teriam o que ler")
    assert relatorio["remapeamento"] == "aplicado"

    monkeypatch.setattr(gerente, "load_profile", lambda nome: _perfil())
    m.activate(NOME, origin="system")
    assert remap.ativo(store) is None, (
        "o perfil sem troca deixou valendo a troca do perfil anterior")


def test_o_salvar_da_aba_perfis_nao_apaga_a_troca() -> None:
    """`to_profile` reconstrói o perfil do zero — sem o transporte, o Salvar zera."""
    from hefesto_dualsense4unix.app.draft_config import DraftConfig

    prof = _perfil(remapeamento={"cross": "circle"})
    rascunho = DraftConfig.from_profile(prof)
    assert rascunho.to_profile(NOME).remapeamento == {"cross": "circle"}
    assert rascunho.to_profile("Outro Nome").remapeamento == {"cross": "circle"}
