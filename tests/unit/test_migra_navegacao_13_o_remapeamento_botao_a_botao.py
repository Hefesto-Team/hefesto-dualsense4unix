#!/usr/bin/env python3
"""F1-REMAPEAR — a troca botão a botão, da tela ao jogo. 13/09/2026.

O CONTRATO é o da MIGRA-NAVEGACAO-13 com a ROTA CORRIGIDA da F1-REMAPEAR:
o motor puro (`core/remapeamento_de_botao.py`), o campo do perfil omitido
quando vazio, o depósito na ativação, a tradução logo antes dos DOIS
`forward_buttons` (o do primário e o do co-op), e a tela "Trocar os botões" com
dono nos seus quatro gestos.

**ELA LÊ, NÃO DIGITA** o que tem dono: os botões saem de
`core.acoes_de_botao.BOTOES`, o vocabulário do jogo de
`core.evdev_reader.EvdevReader.BUTTON_MAP`, e as linhas da tela da PÁGINA
PUBLICADA.

A MORDIDA, e cada uma foi rodada na entrega desta sprint:

- arranque o `if troca:` de `gamepad.dispatch_gamepad` e
  :func:`test_o_primario_passa_pela_troca` reprova — o jogo veria o ✕;
- idem em `coop.CoopManager.forward_all` e
  :func:`test_os_secundarios_passam_pela_troca` reprova;
- aplique o mapa em cadeia em `traduzir` e
  :func:`test_a_troca_dupla_vale_nos_dois_sentidos` reprova;
- tire a trava do apagador de `guardar_remapeamento` e
  :func:`test_o_guardar_nao_apaga_o_que_a_tela_nao_mostrou` reprova;
- tire `remapeamento=self.source_remapeamento` de `DraftConfig.to_profile` e
  :func:`test_o_salvar_da_aba_perfis_nao_apaga_a_troca` reprova.
"""
from __future__ import annotations

import ast
import json
import pathlib
import re
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


# ---------------------------------------------------------------------------
# 1. O MOTOR
# ---------------------------------------------------------------------------
def test_a_troca_dupla_vale_nos_dois_sentidos() -> None:
    """`{✕: ○, ○: ✕}` — apertar ✕ o jogo vê ○, e apertar ○ o jogo vê ✕.

    É o erro clássico de permutação aplicada em ordem: a segunda troca leria o
    resultado da primeira e o botão voltaria a si mesmo. Só a troca DUPLA o vê.
    """
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


# ---------------------------------------------------------------------------
# 2. O CAMINHO QUENTE — os dois `forward_buttons`
# ---------------------------------------------------------------------------
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

    # A reconciliação de launch e o aviso de modo não são o que se mede aqui.
    monkeypatch.setattr(gp, "_reconciliar_launch", lambda d: None)
    monkeypatch.setattr(gp, "_avisar_troca_de_modo", lambda d: None)
    dev = _Device()
    gp.dispatch_gamepad(SimpleNamespace(store=store, _gamepad_device=dev),
                        _ESTADO_DO_CONTROLE, apertados)
    return dev


def test_o_primario_passa_pela_troca(monkeypatch: pytest.MonkeyPatch) -> None:
    """✕→○ ativo: o jogo recebe ○ — e o conjunto que o laço tem continua ✕.

    O MESMO objeto `buttons_pressed` segue, no laço do daemon, para o PS, os
    gestos, o atalho e o teclado emulado. Ele ser intocado é a metade da prova
    de que eles continuam vendo o ✕; a outra é
    :func:`test_a_troca_mora_em_dois_lugares_so`.
    """
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
    # E UM MOCK QUE RESPONDE QUALQUER ATRIBUTO não liga troca nenhuma.
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
    """Só os dois `forward_buttons` traduzem — o PS e o atalho veem o original.

    Se a tradução aparecesse no leitor de evdev, no teclado, no mouse ou no
    `hotkey`, a troca passaria a valer para o desktop e para os cinco gestos —
    e o PS trocado levaria a saída de emergência junto.
    """
    assert _chamadas_da_traducao() == {
        ("hefesto_dualsense4unix/daemon/subsystems/gamepad.py", "dispatch_gamepad"),
        ("hefesto_dualsense4unix/daemon/subsystems/coop.py", "forward_all"),
    }


# ---------------------------------------------------------------------------
# 3. O PERFIL, A ATIVAÇÃO E O SALVAR
# ---------------------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# 4. A TELA — os quatro gestos, a pintura e a página publicada
# ---------------------------------------------------------------------------
class _PonteMuda:
    """Aceita tudo e não fala com daemon nenhum — mesma do irmão da 06."""

    def __getattr__(self, _nome: str) -> Any:
        return lambda *a, **k: True


UNIQ = "aa:bb:cc:00:00:01"
FALSO = {"uniq": UNIQ, "player": 1, "connected": True, "transport": "bt",
         "battery_pct": 95, "is_primary": True, "inputs": {}, "audio": {},
         "speaker": {}}
MESA = [{"pref": "p1", "jogador": 1, "uniq": UNIQ, "nome": "Régua",
         "via": "BT", "cor": "starlight-blue", "mascara": "DualSense"}]
ESTADO = {
    "active_profile": NOME,
    "mouse_emulation": {"enabled": False, "speed": 6, "scroll_speed": 1,
                        "bloqueio": "desligada", "despachando": False},
    "keyboard_emulation": {"enabled": True, "osk_disponivel": True},
    "controllers": [FALSO],
}


@pytest.fixture
def aba(monkeypatch: pytest.MonkeyPatch) -> Any:
    """O pacote da 06 com a trava limpa antes e depois."""
    from pacotes import a06_navegacao

    a06_navegacao._TROCANDO.clear()
    yield a06_navegacao
    a06_navegacao._TROCANDO.clear()


@pytest.fixture
def ctx() -> Any:
    import pacotes

    return pacotes.Contexto(state=ESTADO, mesa=MESA, conectados=[FALSO], estados={})


@pytest.fixture
def disco(monkeypatch: pytest.MonkeyPatch) -> tuple[dict[str, Any], list[Any]]:
    """Um disco de mentira: o `load_profile` lê daqui, o `save_profile` guarda."""
    from hefesto_dualsense4unix.profiles import loader

    estado: dict[str, Any] = {}
    gravados: list[Any] = []
    monkeypatch.setattr(loader, "load_profile", lambda n: estado[n])
    monkeypatch.setattr(loader, "save_profile",
                        lambda prof, **_: gravados.append(prof))
    return estado, gravados


def _forma(**trocas: str) -> dict[str, str]:
    """As 22 linhas como a tela as manda, mais o endereço de uma dica."""
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES
    from pacotes.a06_navegacao import SEM_TROCA

    forma = {b: SEM_TROCA for b in BOTOES}
    forma.update(trocas)
    forma["quem-navega"] = "P1 Régua BT"
    return forma


def test_o_x_passa_a_ser_bolinha_da_tela_ao_jogo(
    aba: Any, ctx: Any, disco: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mordida da ROTA CORRIGIDA, de ponta a ponta, com dublê nos dois pontos.

    A tela manda «✕ passa a ser ○» → o "Guardar" grava → a ativação deposita →
    o `forward_buttons` do primário e o do co-op recebem ○.
    """
    from hefesto_dualsense4unix.daemon.state_store import StateStore
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    estado, gravados = disco
    estado[NOME] = _perfil()
    aba.guardar_remapeamento(ctx, {"forma": _forma(cross="Círculo")}, _PonteMuda())
    assert [g.remapeamento for g in gravados] == [{"cross": "circle"}]
    assert gravados[0].model_dump().get("button_actions") is None

    store = StateStore()
    ProfileManager(controller=SimpleNamespace(), store=store  # type: ignore[arg-type]
                   ).apply_remapeamento(gravados[0])
    dev = _despachar_o_primario(monkeypatch, store, frozenset({"cross"}))
    assert dev.buttons == [frozenset({"circle"})]


def test_o_guardar_nao_apaga_o_que_a_tela_nao_mostrou(
    aba: Any, ctx: Any, disco: Any,
) -> None:
    """A tela no desenho (tudo sem troca) com o perfil guardando troca: RECUSA."""
    estado, gravados = disco
    estado[NOME] = _perfil(remapeamento={"cross": "circle"})
    with pytest.raises(RuntimeError, match="não guardei"):
        aba.guardar_remapeamento(ctx, {"forma": _forma()}, _PonteMuda())
    assert not gravados, "o Guardar apagou a troca que a tela ainda não mostrava"


def test_zerar_de_proposito_grava(
    aba: Any, ctx: Any, disco: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Com a linha que ELA mexeu na trava, tudo sem troca é pedido legítimo."""
    from pacotes import perfil
    from pacotes.a06_navegacao import SEM_TROCA

    estado, gravados = disco
    estado[NOME] = _perfil(remapeamento={"cross": "circle"})
    monkeypatch.setattr(perfil, "ativo",
                        lambda nome: {"remapeamento": {"cross": "circle"}})
    aba.linha_de_troca(ctx, {"linha": "cross", "valor": SEM_TROCA}, _PonteMuda())
    aba.guardar_remapeamento(ctx, {"forma": _forma()}, _PonteMuda())
    assert [g.remapeamento for g in gravados] == [None]


def test_a_colisao_e_o_ps_nao_gravam_e_dizem_o_nome(
    aba: Any, ctx: Any, disco: Any,
) -> None:
    estado, gravados = disco
    estado[NOME] = _perfil()
    with pytest.raises(RuntimeError, match="Cruz e Quadrado"):
        aba.guardar_remapeamento(
            ctx, {"forma": _forma(cross="Círculo", square="Círculo")}, _PonteMuda())
    with pytest.raises(RuntimeError, match="PS"):
        aba.guardar_remapeamento(ctx, {"forma": _forma(ps="Cruz")}, _PonteMuda())
    with pytest.raises(RuntimeError, match="PS"):
        aba.linha_de_troca(ctx, {"linha": "cross", "valor": "PS"}, _PonteMuda())
    with pytest.raises(RuntimeError, match="fora da troca"):
        aba.linha_de_troca(ctx, {"linha": "l3_direcao", "valor": "Cruz"}, _PonteMuda())
    assert not gravados and not aba._TROCANDO


def test_igual_ao_perfil_recusa_dizendo(aba: Any, ctx: Any, disco: Any) -> None:
    estado, gravados = disco
    estado[NOME] = _perfil(remapeamento={"cross": "circle"})
    with pytest.raises(RuntimeError, match="não havia o que guardar"):
        aba.guardar_remapeamento(ctx, {"forma": _forma(cross="Círculo")}, _PonteMuda())
    assert not gravados


def test_o_padrao_zera_so_a_troca(aba: Any, ctx: Any, disco: Any) -> None:
    """A pergunta diz que as Definições não são tocadas — e não são."""
    estado, gravados = disco
    estado[NOME] = _perfil(remapeamento={"cross": "circle"},
                           button_actions={"cross": "KEY_ESC"})
    volta = aba.padrao_remapeamento(ctx, {}, _PonteMuda())
    assert [g.remapeamento for g in gravados] == [None]
    assert gravados[0].button_actions == {"cross": "KEY_ESC"}
    assert set(volta["mesa"].values()) == {aba.SEM_TROCA}
    estado[NOME] = gravados[0]
    with pytest.raises(RuntimeError, match="não havia o que voltar"):
        aba.padrao_remapeamento(ctx, {}, _PonteMuda())
    assert len(gravados) == 1


def test_a_pintura_mostra_o_perfil_e_concorda_com_quem_mexe(
    aba: Any, ctx: Any, monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pacotes import perfil

    monkeypatch.setattr(perfil, "ativo",
                        lambda nome: {"remapeamento": {"cross": "circle"}})
    mesa = aba.pacote(ctx)["mesa"]
    trocas = {k: v for k, v in mesa.items() if k.startswith(aba.PREFIXO_DA_TROCA)}
    assert len(trocas) == len(remap.REMAPEAVEIS)
    assert trocas["troca-cross"] == "Círculo"
    assert trocas["troca-circle"] == aba.SEM_TROCA

    aba.linha_de_troca(ctx, {"linha": "cross", "valor": "Quadrado"}, _PonteMuda())
    assert aba.pacote(ctx)["mesa"]["troca-cross"] == "Quadrado", (
        "o tique desfez a escolha dela antes do Guardar")
    fechou = aba.fechar_troca(ctx, {}, _PonteMuda())
    assert fechou["mesa"]["troca-cross"] == "Círculo"
    assert aba.pacote(ctx)["mesa"]["troca-cross"] == "Círculo"


def test_os_dois_gestos_sairam_do_sem_gesto(aba: Any) -> None:
    import pacotes

    for nome in ("guardar-remapeamento", "padrao-remapeamento",
                 "linha-de-troca", "fechar-troca"):
        assert nome not in aba.SEM_GESTO
        assert nome in aba.SEM_ECO
        assert (PAGINA, nome) in pacotes.GESTOS
    assert pacotes.GESTOS_QUE_MEXEM[(PAGINA, "guardar-remapeamento")] == "gravar_e_reaplicar"


def _tela_publicada() -> str:
    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8")
    return doc.split('id="remapeamento"', 1)[1].split('class="tela-nova"', 1)[0]


def test_a_pagina_publicada_da_endereco_as_linhas(aba: Any) -> None:
    """Lida da PÁGINA: 22 linhas, 16 falando e pintadas, e toda opção traduzível."""
    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES

    tela = _tela_publicada()
    listas = re.findall(r"<select([^>]*)>(.*?)</select>", tela, re.S)
    assert len(listas) == len(BOTOES)
    # A ORDEM É DO DESENHO (o touchpad sai esquerdo, direito, central) e o
    # conjunto é do produto — por isso a conta é por conjunto e sem repetição.
    linhas = [re.search(r'data-linha="([^"]+)"', a).group(1)  # type: ignore[union-attr]
              for a, _ in listas]
    assert len(set(linhas)) == len(linhas) and set(linhas) == set(BOTOES)
    # SÓ AS DEZESSEIS QUE A TROCA ALCANÇA FALAM — 13/09/2026, F1-REMAPEAR-02. As
    # seis de fora nascem apagadas e sem gesto; quem as confere é
    # `test_as_seis_linhas_fora_da_troca_ficam_apagadas.py`.
    falando = [linha for (a, _), linha in zip(listas, linhas, strict=True)
               if 'data-gesto="linha-de-troca"' in a]
    assert sorted(falando) == sorted(remap.REMAPEAVEIS), falando
    pintadas = [m.group(1) for m in
                (re.search(r'data-campo="troca-([^"]+)"', a) for a, _ in listas) if m]
    assert len(pintadas) == len(remap.REMAPEAVEIS)
    assert set(pintadas) == set(remap.REMAPEAVEIS)
    for _, opcoes in listas:
        for rotulo in re.findall(r"<option[^>]*>(.*?)</option>", opcoes):
            assert rotulo == aba.SEM_TROCA or rotulo in aba.ROTULOS_DA_TROCA, rotulo
    assert tela.count('data-gesto="fechar-troca"') == 2
    assert "navega o PC" not in tela, (
        "a dica da troca voltou a dizer que ela vale só para quem navega o PC — "
        "ela vale nos quatro controles")


def _bootstrap() -> str:
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    m = re.search(r'BOOTSTRAP = r"""(.*?)"""', fonte, re.S)
    assert m, "não achei o BOOTSTRAP no piloto"
    return m.group(1)


@pytest.mark.skipif(not CHROME.exists(), reason="sem o Chrome do sistema")
def test_o_clique_na_pagina_publicada_chega_ao_disco(
    aba: Any, ctx: Any, disco: Any,
) -> None:
    """A página publicada num Chrome, com o BOOTSTRAP do piloto: o clique real.

    Escolher ○ na linha do ✕ manda `linha-de-troca`; o "Guardar" manda a
    `forma` com as 22 linhas; e essa forma, entregue ao gesto, grava
    `{"cross": "circle"}`. O Chrome mede o contrato do bootstrap; o WebKitGTK é
    o motor do produto, e a prova nele é de quem roda o piloto.
    """
    from playwright.sync_api import sync_playwright

    from hefesto_dualsense4unix.core.acoes_de_botao import BOTOES
    from hefesto_dualsense4unix.interface import onde

    pagina = onde.pagina(PAGINA, publicado=True)
    with sync_playwright() as pw:
        navegador = pw.chromium.launch(executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg = navegador.new_page(viewport={"width": 1180, "height": 900})
            pg.goto(pagina.as_uri() + "#remapeamento")
            pg.evaluate("""
                window.__recebido = [];
                window.webkit = {messageHandlers: {hefesto: {
                    postMessage: function(s){ window.__recebido.push(s); }}}};
            """)
            pg.evaluate(_bootstrap())
            pg.eval_on_selector(
                '#remapeamento select[data-linha="cross"]',
                "el => { el.value = 'Círculo';"
                " el.dispatchEvent(new Event('change', {bubbles: true})); }")
            pg.eval_on_selector('[data-gesto="guardar-remapeamento"]', "el => el.click()")
            crus = [json.loads(s) for s in pg.evaluate("window.__recebido")]
        finally:
            navegador.close()
    linha = [o for o in crus if o.get("gesto") == "linha-de-troca"]
    assert linha and linha[-1].get("linha") == "cross" and linha[-1].get("valor") == "Círculo", crus
    guardar = [o for o in crus if o.get("gesto") == "guardar-remapeamento"]
    assert guardar, crus
    forma = guardar[-1]["forma"]
    assert set(BOTOES) <= set(forma) and forma["cross"] == "Círculo"

    estado, gravados = disco
    estado[NOME] = _perfil()
    aba.guardar_remapeamento(ctx, {"forma": forma}, _PonteMuda())
    assert [g.remapeamento for g in gravados] == [{"cross": "circle"}]
