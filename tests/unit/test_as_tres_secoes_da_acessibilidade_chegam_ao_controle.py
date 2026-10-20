"""AS TRÊS SEÇÕES DA ACESSIBILIDADE GANHAM IPC, E O TOQUE SEGUE A MÃO.

AS-TRES-SECOES-DA-ACESSIBILIDADE-GANHAM-IPC-E-O-TOQUE-SEGUE-A-MAO-01. Um teste por defeito:

1. `perfil.ativacao.set`, `perfil.analogicos.set` e `perfil.cursor.set` existem no dicionário
   `_handlers`, gravam no perfil (na peça ou no perfil) e depositam no `store` ao vivo;
2. o cursor do touchpad (`CursorDoToque`) segue a precisão, a permanência e o clique travado
   do mesmo `AjusteDoCursor` do cursor dos analógicos;
3. o teclado virtual não recebe o botão da precisão nem o do clique travado;
4. a inclinação vai ao lado que a mão escolhida manda, o mesmo do giro;
5. no co-op o filtro do botão roda na mesma ordem do jogador sozinho (toque, filtro, movimento).

AS MORDIDAS estão no relato da entrega: o registro dos métodos tirado do `_handlers` (1), o
`ajudar` tirado do `aplicar_o_toque` (2), o `botoes_do_cursor` tirado do teclado (3), o
`lado_do_giro` tirado da inclinação (4) e o filtro do co-op passado para depois do movimento (5).

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

import ast
import asyncio
import sys
import types
from pathlib import Path
from types import MethodType, SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import curva_do_analogico
from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.evdev_reader import PontoDeToque, TouchState
from hefesto_dualsense4unix.daemon.lifecycle import Daemon
from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.integrations import uinput_mouse
from hefesto_dualsense4unix.profiles.schema import (
    ProfileAnalogicosConfig,
    ProfileCursorConfig,
    ProfileMovimentoConfig,
)

_P1, _P2 = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02")
_CHAVE = {u: u.replace(":", "").lower() for u in (_P1, _P2)}
_RAIZ = Path(__file__).resolve().parents[2]
_SRC = _RAIZ / "src" / "hefesto_dualsense4unix"


# ---------------------------------------------------------------- 1. o IPC


@pytest.fixture
def perfis(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Diretório de perfis isolado: nada toca o `~/.config` de ninguém."""
    from hefesto_dualsense4unix.profiles import loader as loader_module

    alvo = tmp_path / "profiles"
    alvo.mkdir()

    def _dir(ensure: bool = False) -> Path:
        if ensure:
            alvo.mkdir(parents=True, exist_ok=True)
        return alvo

    monkeypatch.setattr(loader_module, "profiles_dir", _dir)
    return alvo


def _servidor(tmp_path: Path) -> Any:
    """O `Daemon` e o `IpcServer` do produto, com o perfil «Bancada» ativo no disco."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "acess.sock", daemon=daemon)
    daemon._ipc_server = servidor
    perfil = Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    servidor.store.set_active_profile(perfil.name)
    return servidor


def _chama(servidor: Any, metodo: str, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers[metodo](params))


def _do_disco() -> Any:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    return load_profile("Bancada")


def test_os_tres_metodos_estao_no_dicionario_do_servidor(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    for metodo in ("perfil.ativacao.set", "perfil.analogicos.set", "perfil.cursor.set"):
        assert metodo in servidor._handlers, f"`{metodo}` não está no `_handlers`"


def test_a_ativacao_grava_na_peca_e_vale_ao_vivo(perfis: Path, tmp_path: Path) -> None:
    """`uniq` grava na peça; o `store` e o bloco `acessibilidade` do daemon dizem o mesmo."""
    from hefesto_dualsense4unix.core import ativacao_de_botao

    servidor = _servidor(tmp_path)
    corpo = _chama(servidor, "perfil.ativacao.set", uniq=_P2, alternar=["cross"])
    assert corpo["status"] == "ok" and corpo["gravado"] is True, corpo
    assert corpo["alcance"]["tique"] == "aplicado"
    dele = (_do_disco().controllers or {})[_CHAVE[_P2]]
    assert dele.ativacao.alternar == ["cross"]
    assert _do_disco().ativacao is None, "a escolha da peça vazou para o perfil inteiro"
    assert ativacao_de_botao.da_peca(servidor.store, _P2) is not None
    assert ativacao_de_botao.da_peca(servidor.store, _P1) is None
    entradas = [{"uniq": _P1}, {"uniq": _P2}]
    servidor._merge_acessibilidade(entradas)
    dizem = [e["acessibilidade"]["ativacao"] for e in entradas]  # (noqa-acento) chave
    assert dizem == [False, True]


def test_o_campo_omitido_nao_mexe_no_que_ja_esta(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    _chama(servidor, "perfil.ativacao.set", alternar=["cross"])
    _chama(servidor, "perfil.ativacao.set", repetir=["square"])
    ativacao = _do_disco().ativacao
    assert ativacao.alternar == ["cross"] and ativacao.repetir == ["square"]
    repetido = _chama(servidor, "perfil.ativacao.set", repetir=["square"])
    assert repetido["gravado"] is False, "o mesmo pedido regravou o arquivo"


def test_o_pedido_que_o_modelo_recusa_nao_grava(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    antes = (perfis / "bancada.json").read_bytes()
    with pytest.raises(ValueError, match="recusado"):
        _chama(servidor, "perfil.ativacao.set", alternar=["botao_que_nao_existe"])
    with pytest.raises(ValueError, match="não conhece"):
        _chama(servidor, "perfil.cursor.set", velocidade=3)
    with pytest.raises(ValueError, match="do perfil"):
        _chama(servidor, "perfil.cursor.set", uniq=_P1, precisao=50)
    with pytest.raises(ValueError, match="exige ao menos"):
        _chama(servidor, "perfil.analogicos.set")
    assert (perfis / "bancada.json").read_bytes() == antes


def test_os_analogicos_e_o_cursor_valem_ao_vivo(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    corpo = _chama(servidor, "perfil.analogicos.set", uniq=_P1, zona_morta=12, mao="direita")
    mao = corpo["analogicos"]["mao"]  # (noqa-acento) chave
    assert corpo["status"] == "ok" and mao == "direita"
    curva = curva_do_analogico.da_peca(servidor.store, _P1)
    assert curva is not None and curva.mao == "direita"
    assert curva_do_analogico.da_peca(servidor.store, _P2) is None

    corpo = _chama(servidor, "perfil.cursor.set", precisao_botao="l1", precisao=40,
                   permanencia_ms=800)
    assert corpo["status"] == "ok" and _do_disco().cursor.precisao == 40
    ajuste, _ = uinput_mouse.ajuste_ativo(servidor.store)
    assert ajuste is not None and ajuste.precisao_botao == "l1"
    assert ajuste.precisao == pytest.approx(0.4) and ajuste.permanencia_s == pytest.approx(0.8)


def test_sem_perfil_a_resposta_diz_e_nada_grava(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    servidor._perfil_que_grava = lambda: None
    corpo = _chama(servidor, "perfil.cursor.set", precisao=50)
    assert corpo["status"] == "sem_perfil"


# ---------------------------------------------------------------- 2. o toque segue o ajuste


class _NoDeMentira:
    def __init__(self, *_a: Any, **_k: Any) -> None:
        self.emitidos: list[tuple[str, int]] = []
        self.destruido = False

    def emit(self, evento: str, valor: int, syn: bool = True) -> None:
        self.emitidos.append((evento, valor))

    def syn(self) -> None:
        pass

    def destroy(self) -> None:
        self.destruido = True


@pytest.fixture
def _uinput_que_grava(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
    mod = types.ModuleType("uinput")
    mod.REL_X, mod.REL_Y, mod.BTN_LEFT = "REL_X", "REL_Y", "BTN_LEFT"  # type: ignore[attr-defined]
    mod.Device = _NoDeMentira  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "uinput", mod)
    return mod


def _cursor() -> Any:
    cursor = uinput_mouse.CursorDoToque()
    assert cursor.start()
    return cursor


def _soma(cursor: Any, evento: str) -> int:
    return sum(v for e, v in cursor._device.emitidos if e == evento)


def _botao(cursor: Any) -> list[int]:
    return [v for e, v in cursor._device.emitidos if e == "BTN_LEFT"]


def _ajuste(**campos: Any) -> Any:
    return uinput_mouse.montar_o_ajuste(ProfileCursorConfig(**campos))


def test_a_precisao_reduz_o_passo_de_quem_aperta_o_botao(
        _uinput_que_grava: types.ModuleType) -> None:
    """O botão da precisão, apertado POR UMA PEÇA, reduz o passo dela e só dela."""
    cursor = _cursor()
    cursor.definir_ajuste(_ajuste(precisao_botao="cross", precisao=30), 1)
    cursor.ajudar(_P1, frozenset({"cross"}), 0, 0, 1.0)
    cursor.ajudar(_P2, frozenset(), 0, 0, 1.0)
    cursor.mover(100.0, 0.0, peca=_P1, agora=1.0)
    assert _soma(cursor, "REL_X") == 30, "o passo da peça com o botão apertado não encolheu"
    cursor.mover(100.0, 0.0, peca=_P2, agora=1.0)
    assert _soma(cursor, "REL_X") == 130, "a outra peça herdou a precisão de quem apertou"
    cursor.ajudar(_P1, frozenset(), 0, 0, 1.1)
    cursor.mover(100.0, 0.0, peca=_P1, agora=1.1)
    assert _soma(cursor, "REL_X") == 230, "soltar o botão não devolveu o passo inteiro"


def test_o_gatilho_da_precisao_vale_da_metade_do_curso(
        _uinput_que_grava: types.ModuleType) -> None:
    cursor = _cursor()
    cursor.definir_ajuste(_ajuste(precisao_botao="l2", precisao=50), 1)
    cursor.ajudar(_P1, frozenset(), 100, 0, 1.0)
    cursor.mover(100.0, 0.0, peca=_P1, agora=1.0)
    assert _soma(cursor, "REL_X") == 100, "o gatilho a menos da metade reduziu o passo"
    cursor.ajudar(_P1, frozenset(), uinput_mouse.PRECISAO_DO_GATILHO, 0, 1.1)
    cursor.mover(100.0, 0.0, peca=_P1, agora=1.1)
    assert _soma(cursor, "REL_X") == 150


def test_a_permanencia_clica_parado_depois_de_andar(
        _uinput_que_grava: types.ModuleType) -> None:
    cursor = _cursor()
    cursor.definir_ajuste(_ajuste(permanencia_ms=800), 1)
    cursor.conferir(10.0)
    assert _botao(cursor) == [], "clicou sem o cursor ter andado"
    cursor.mover(50.0, 0.0, peca=_P1, agora=10.0)
    cursor.conferir(10.5)
    assert _botao(cursor) == [], "clicou antes da permanência"
    cursor.conferir(10.9)
    assert _botao(cursor) == [1, 0], "parado por 800 ms depois de andar, o clique não saiu"
    cursor.conferir(12.0)
    assert _botao(cursor) == [1, 0], "clicou duas vezes sem andar de novo"


def test_o_clique_travado_prende_solta_e_some_com_o_perfil(
        _uinput_que_grava: types.ModuleType) -> None:
    cursor = _cursor()
    cursor.definir_ajuste(_ajuste(clique_travado="square"), 1)
    cursor.ajudar(_P1, frozenset({"square"}), 0, 0, 1.0)
    cursor.ajudar(_P1, frozenset({"square"}), 0, 0, 1.1)
    assert _botao(cursor) == [1], "o botão segurado travou mais de uma vez"
    cursor.ajudar(_P1, frozenset(), 0, 0, 1.2)
    cursor.ajudar(_P1, frozenset({"square"}), 0, 0, 1.3)
    assert _botao(cursor) == [1, 0], "o segundo toque não soltou o clique"
    cursor.ajudar(_P1, frozenset(), 0, 0, 1.4)
    cursor.ajudar(_P1, frozenset({"square"}), 0, 0, 1.5)
    assert _botao(cursor) == [1, 0, 1]
    cursor.definir_ajuste(None, 2)
    assert _botao(cursor) == [1, 0, 1, 0], "trocar de perfil deixou o clique preso"


def test_o_clique_travado_solta_se_o_controle_some(
        _uinput_que_grava: types.ModuleType) -> None:
    cursor = _cursor()
    cursor.definir_ajuste(_ajuste(clique_travado="square"), 1)
    cursor.ajudar(_P1, frozenset({"square"}), 0, 0, 1.0)
    cursor.conferir(1.0 + uinput_mouse.TRAVA_SEM_NOTICIA_S + 0.1)
    assert _botao(cursor) == [1, 0], "o controle caiu e o clique ficou preso"


def _toque(*dedos: tuple[int, int]) -> TouchState:
    pontos = tuple(
        PontoDeToque(slot=i, x=x, y=y, identidade=10 + i) for i, (x, y) in enumerate(dedos))
    x, y = dedos[0]
    return TouchState(touching=True, x=x, y=y, largura=1920, altura=942, pontos=pontos)


def test_o_aplicar_o_toque_entrega_o_ajuste_ao_cursor(
        _uinput_que_grava: types.ModuleType) -> None:
    """Pelo tique de verdade: com o botão da precisão apertado o dedo anda a fração dele."""
    leituras: list[Any] = []

    class _Hub:
        def toque_da_peca(self, uniq: str) -> Any:
            return leituras.pop(0)

    def _andar(botoes: frozenset[str]) -> int:
        store = SimpleNamespace()
        rot.definir_ativo(store, rot.montar(ProfileMovimentoConfig(toque="cursor")))
        uinput_mouse.definir_ajuste_ativo(
            store, _ajuste(precisao_botao="cross", precisao=25))
        cursor = _cursor()
        daemon = SimpleNamespace(
            _ipc_server=SimpleNamespace(_garantir_sensor_hub=lambda: _Hub()), store=store,
            _gamepad_device=None, _mouse_device=None, _cursor_do_toque=cursor)
        daemon._garantir_sensor_hub = MethodType(Daemon._garantir_sensor_hub, daemon)
        daemon._garantir_cursor_do_toque = MethodType(Daemon._garantir_cursor_do_toque, daemon)
        leituras[:] = [(_toque((200 + 100 * i, 400)), False) for i in range(6)]
        for _ in range(6):
            gp.aplicar_o_toque(
                daemon, rot.ativo(store), uniq=_P2, botoes=botoes, l2=0, r2=0)
        return abs(_soma(cursor, "REL_X"))

    solto = _andar(frozenset())
    apertado = _andar(frozenset({"cross"}))
    assert solto > 20, f"o dedo não andou sem o botão ({solto})"
    assert apertado == pytest.approx(solto * 0.25, abs=3), (
        f"a precisão de 25% não chegou ao toque: {apertado} contra {solto}")


# ---------------------------------------------------------------- 3. o teclado


def test_o_botao_do_cursor_nao_vira_tecla(monkeypatch: pytest.MonkeyPatch) -> None:
    """Com o mouse virtual de pé, a precisão e o clique travado saem do que o teclado recebe."""
    from hefesto_dualsense4unix.daemon.subsystems import keyboard

    store = SimpleNamespace()
    uinput_mouse.definir_ajuste_ativo(
        store, _ajuste(precisao_botao="l1", clique_travado="square"))
    recebidos: list[frozenset[str]] = []
    teclado = SimpleNamespace(dispatch=recebidos.append)
    daemon = SimpleNamespace(_keyboard_device=teclado, _mouse_device=object(), store=store,
                             _touchpad_reader=None)
    keyboard.dispatch_keyboard(daemon, frozenset({"l1", "square", "cross"}))  # type: ignore[arg-type]
    assert recebidos == [frozenset({"cross"})], recebidos
    daemon._mouse_device = None
    keyboard.dispatch_keyboard(daemon, frozenset({"l1", "square", "cross"}))  # type: ignore[arg-type]
    assert recebidos[-1] == frozenset({"l1", "square", "cross"}), (
        "sem o mouse virtual ninguém prende o botão ao cursor")


def test_a_tabela_do_jogo_tambem_cala_o_teclado() -> None:
    fonte = (_SRC / "daemon" / "subsystems" / "mouse.py").read_text(encoding="utf-8")
    assert "botoes_do_cursor(store)" in fonte, "a tabela do jogo entrega tudo ao teclado"


# ---------------------------------------------------------------- 4. a inclinação e a mão


def _inclina(mao: str | None, destino: str) -> tuple[int, int, int, int]:
    """A inclinação de uma peça inclinada para o lado, no `_a_inclinacao` do produto."""
    store = SimpleNamespace()
    if mao is not None:
        curva_do_analogico.definir_ativo(
            store, curva_do_analogico.montar(ProfileAnalogicosConfig(mao=mao)), {})
    arranjo = rot.ArranjoDeMovimento(
        destino=destino, acelerometro=destino, lado=destino, sensibilidade=8)
    hub = SimpleNamespace(
        aceleracao_do_movimento=lambda _u: (0.0, 1.0, 0.0),
        velocidade_do_movimento=lambda _u: (0.0, 0.0, 0.0))
    return gp._a_inclinacao(hub, store, arranjo, _P1, 128, 128, 128, 128)


def test_a_mao_manda_a_inclinacao_para_o_mesmo_lado_do_giro(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem mão a inclinação fica onde foi posta; com a mão, vai ao lado que sobra do olhar.

    (D-2010-A-ACESSIBILIDADE-NAO-TIRA-NADA-DO-PAD-DO-JOGO)
    """
    chamadas: list[str] = []
    monkeypatch.setattr(
        rot, "misturar",
        lambda x, y, dh, dv: (chamadas.append("misturou") or (x + 1, y + 1)))
    monkeypatch.setattr(rot, "deflexao_da_inclinacao", lambda *_a, **_k: (10, 10))
    monkeypatch.setattr(rot, "neutro_da_inclinacao", lambda *_a, **_k: (0.0, 0.0, 0.0))
    monkeypatch.setattr(rot, "inclina_agora", lambda *_a, **_k: True)
    esq, dire = rot.DESTINO_ANALOGICO_ESQUERDO, rot.DESTINO_ANALOGICO_DIREITO

    lx, ly, rx, ry = _inclina(None, esq)
    assert (lx, ly, rx, ry) == (129, 129, 128, 128), "sem mão, o esquerdo continua esquerdo"
    lx, ly, rx, ry = _inclina("esquerda", esq)
    assert (rx, ry) == (129, 129) and (lx, ly) == (128, 128), (
        "a mão esquerda manda o olhar ao direito, como o giro")
    lx, ly, rx, ry = _inclina("direita", dire)
    assert (lx, ly) == (129, 129) and (rx, ry) == (128, 128), (
        "a mão direita troca os lados DEPOIS: a inclinação entra no esquerdo, como o giro")
    assert curva_do_analogico.lado_do_giro(
        SimpleNamespace(), _P1, dire) == dire, "sem curva o destino não muda"


# ---------------------------------------------------------------- 5. o co-op e o jogador sozinho


def _ordem(arquivo: str, funcao: str) -> list[str]:
    """A ordem em que a função chama o toque, o filtro e o movimento."""
    arvore = ast.parse((_SRC / "daemon" / "subsystems" / arquivo).read_text(encoding="utf-8"))
    achadas: list[tuple[int, str]] = []
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == funcao:
            for chamada in ast.walk(no):
                if (isinstance(chamada, ast.Call) and isinstance(chamada.func, ast.Name)
                        and chamada.func.id in ("aplicar_o_toque", "filtrar_o_botao",
                                                "aplicar_o_movimento")):
                    achadas.append((chamada.lineno, chamada.func.id))
    return [nome for _linha, nome in sorted(achadas)]


def test_o_co_op_filtra_na_mesma_ordem_do_jogador_sozinho() -> None:
    """Medido em 20/10: a ordem já é a mesma nos dois caminhos; a régua a trava."""
    sozinho = _ordem("gamepad.py", "dispatch_gamepad")
    coop = _ordem("coop.py", "forward_all")
    assert sozinho == ["aplicar_o_toque", "filtrar_o_botao", "aplicar_o_movimento"], sozinho
    assert coop == sozinho, f"o co-op filtra em outra ordem: {coop}"
