"""O ANALÓGICO VIRTUAL É UM SÓ — O-ANALOGICO-VIRTUAL-E-UM-SO-COM-O-LADO-ESCOLHIDO-01.

O pedido de 06/10/2026: a «Mira Virtual» vira «Analógico Virtual», e escolher o lado
(esquerdo ou direito) substitui o chip «Inclinação» de cada analógico. Antes, o `ligada`
do `mira.set` cravava o analógico direito, e a inclinação era um interruptor à parte.

O contrato que esta régua mede:

1. `mira.set` ganha `lado`; `ligada: true` liga no lado guardado (o direito para o perfil
   antigo), `lado` sozinho troca o lado e liga, `ligada: false` apaga os dois movimentos;
2. o giro e a inclinação vão ao MESMO lado (a PERGUNTA 1, a recomendada);
3. a 02 e a Calibrar pintam `mira-ligada` e `mira-lado` pelo mesmo leitor, e o gesto
   `analogico-lado` é o mesmo nas duas;
4. o perfil que já existe lê como está escrito, P1 a P4 são quatro opiniões, e o Nativo
   recusa sem gravar.

A MORDIDA (rodada em 08/10/2026 e devolvida): o `destino` cravado de volta no analógico
direito no `_handle_mira_set` (`rota = rot.DESTINO_ANALOGICO_DIREITO`) reprova as réguas
do lado, a do clique pela 02 e a da Calibrar.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot
from hefesto_dualsense4unix.core.virtual_motion import REGISTRO

sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "src" / "hefesto_dualsense4unix" / "interface"))

_P1, _P2, _P3, _P4 = (f"aa:bb:cc:00:00:0{n}" for n in (1, 2, 3, 4))
_TODOS = (_P1, _P2, _P3, _P4)
_CHAVE = {u: u.replace(":", "").upper().lower() for u in _TODOS}
_ESQ, _DIR = rot.DESTINO_ANALOGICO_ESQUERDO, rot.DESTINO_ANALOGICO_DIREITO
_RAIZ = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- 1. o roteador e o perfil


def test_o_perfil_antigo_so_com_ligada_le_o_direito() -> None:
    """O perfil gravado antes desta sprint (o `destino` direito, sem `lado`) não muda."""
    from hefesto_dualsense4unix.profiles.schema import ProfileMovimentoConfig

    secao = ProfileMovimentoConfig.model_validate({"destino": _DIR})
    assert "lado" not in secao.model_dump(), "o lado foi ao disco sem ninguém escrever"
    arranjo = rot.montar(secao)
    assert arranjo.lado == _DIR
    assert rot.lado_do_virtual(arranjo) == _DIR and rot.virtual_aceso(arranjo)
    apagado = rot.montar(ProfileMovimentoConfig.model_validate({}))
    assert rot.lado_do_virtual(apagado) == _DIR and not rot.virtual_aceso(apagado)


def test_inclina_num_lado_e_giro_no_outro_a_tela_acende_o_do_giro() -> None:
    """O perfil da tela velha: o motor segue com os dois como estão; a tela acende o do giro."""
    arranjo = rot.ArranjoDeMovimento(destino=_DIR, acelerometro=_ESQ)
    assert (arranjo.destino, arranjo.acelerometro) == (_DIR, _ESQ)
    assert rot.lado_do_virtual(arranjo) == _DIR and rot.virtual_aceso(arranjo)
    so_inclina = rot.ArranjoDeMovimento(acelerometro=_ESQ)
    assert rot.lado_do_virtual(so_inclina) == _ESQ and rot.virtual_aceso(so_inclina)


def test_o_mouse_conta_como_apagado() -> None:
    """O giro no cursor não é lado de analógico: o Analógico Virtual fica apagado.

    D-0810-O-ANALOGICO-VIRTUAL-E-UM-SO.
    """
    arranjo = rot.ArranjoDeMovimento(destino=rot.DESTINO_MOUSE, lado=_ESQ)
    assert not rot.virtual_aceso(arranjo)
    assert rot.lado_do_virtual(arranjo) == _ESQ, "o lado guardado se perdeu no cursor"


def test_o_lado_desconhecido_e_recusado() -> None:
    with pytest.raises(rot.ArranjoRecusadoError):
        rot.montar(SimpleNamespace(lado="mouse"))


# ---------------------------------------------------------------- 2. o daemon de verdade


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


def _servidor(tmp_path: Path, *, nativo: bool = False, com_perfil: bool = True) -> Any:
    """O `Daemon` e o `IpcServer` do produto, com (ou sem) um perfil ativo no disco."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    controle = FakeController(transport="bt")  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    if nativo:
        daemon.is_native_mode = lambda: True  # type: ignore[method-assign]
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store, profile_manager=gerente,
                         socket_path=tmp_path / "lado.sock", daemon=daemon)
    daemon._ipc_server = servidor
    if com_perfil:
        perfil = Profile(name="Bancada", match=MatchAny(type="any"))
        save_profile(perfil)
        gerente.apply_movimento(perfil)
        servidor.store.set_active_profile(perfil.name)
    return servidor


def _mira_set(servidor: Any, **params: Any) -> dict[str, Any]:
    return asyncio.run(servidor._handlers["mira.set"](params))


def _movimento(uniq: str) -> Any:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    dele = (load_profile("Bancada").controllers or {}).get(_CHAVE[uniq])
    return getattr(dele, "movimento", None)


def _lidos(servidor: Any) -> list[dict[str, Any]]:
    entradas = [{"uniq": u, "transport": "bt", "connected": True, "inputs": {},
                 "audio": {}, "speaker": {}} for u in _TODOS]
    servidor._merge_mira(entradas)
    return entradas


def test_o_ligada_liga_no_lado_guardado_e_os_dois_movimentos_vao_juntos(
        perfis: Path, tmp_path: Path) -> None:
    """`ligada` usa o lado guardado (o direito do perfil antigo); `lado` troca e liga.

    MORDIDA: o `destino` cravado no direito — o lado esquerdo não chega ao giro.

    D-0810-O-ANALOGICO-VIRTUAL-E-UM-SO: os dois movimentos vão juntos para o lado escolhido.
    """
    servidor = _servidor(tmp_path)
    corpo = _mira_set(servidor, uniq=_P2, ligada=True)
    assert corpo["status"] == "ok" and corpo["virtual"] is True and corpo["lado"] == _DIR
    dele = _movimento(_P2)
    assert (dele.destino, dele.acelerometro, dele.lado) == (_DIR, _DIR, _DIR)

    corpo = _mira_set(servidor, uniq=_P2, lado=_ESQ)
    assert corpo["lado"] == _ESQ and corpo["virtual"] is True, corpo
    dele = _movimento(_P2)
    assert (dele.destino, dele.acelerometro, dele.lado) == (_ESQ, _ESQ, _ESQ)

    corpo = _mira_set(servidor, uniq=_P2, ligada=False)
    assert corpo["virtual"] is False and corpo["lado"] == _ESQ, corpo
    dele = _movimento(_P2)
    assert (dele.destino, dele.acelerometro, dele.lado) == (
        rot.DESTINO_NENHUM, rot.DESTINO_NENHUM, _ESQ), "apagar esqueceu o lado"

    corpo = _mira_set(servidor, uniq=_P2, ligada=True)
    assert corpo["lado"] == _ESQ, "religar voltou ao direito em vez do lado guardado"
    p2 = next(e for e in _lidos(servidor) if e["uniq"] == _P2)["mira"]
    assert p2["virtual"] is True and p2["lado"] == _ESQ
    assert p2["destino"] == _ESQ and p2["inclinacao"] == _ESQ


def test_o_lado_sozinho_liga_o_apagado(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    corpo = _mira_set(servidor, uniq=_P3, lado=_ESQ)
    assert corpo["status"] == "ok" and corpo["virtual"] is True and corpo["lado"] == _ESQ


def test_o_primeiro_clique_no_lado_junta_o_perfil_dividido(perfis: Path, tmp_path: Path) -> None:
    """Giro no direito e inclinação no esquerdo: a tela acende o direito; o lado junta os dois."""
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.schema import (
        ControllerOverrides,
        MatchAny,
        Profile,
        ProfileMovimentoConfig,
    )

    servidor = _servidor(tmp_path)
    dividido = ProfileMovimentoConfig(destino=_DIR, acelerometro=_ESQ)
    perfil = Profile(name="Bancada", match=MatchAny(type="any"),
                     controllers={_CHAVE[_P1]: ControllerOverrides(movimento=dividido)})
    save_profile(perfil)
    servidor.profile_manager.apply_movimento(perfil)
    p1 = next(e for e in _lidos(servidor) if e["uniq"] == _P1)["mira"]
    assert (p1["virtual"], p1["lado"], p1["destino"], p1["inclinacao"]) == (True, _DIR, _DIR, _ESQ)

    _mira_set(servidor, uniq=_P1, lado=_DIR)
    dele = _movimento(_P1)
    assert (dele.destino, dele.acelerometro) == (_DIR, _DIR), "o lado não juntou os dois"


def test_ligar_do_cursor_troca_pelo_analogico(tmp_path: Path) -> None:
    """O giro no cursor (sem perfil, o arranjo do store) fica apagado; ligar vai ao analógico."""
    servidor = _servidor(tmp_path, com_perfil=False)
    chave = _CHAVE[_P4]
    rot.definir_da_peca(servidor.store, chave, rot.ArranjoDeMovimento(destino=rot.DESTINO_MOUSE))
    p4 = next(e for e in _lidos(servidor) if e["uniq"] == _P4)["mira"]
    assert p4["ligada"] is True and p4["virtual"] is False
    corpo = _mira_set(servidor, uniq=_P4, ligada=True)
    assert corpo["virtual"] is True and corpo["lado"] == _DIR, corpo
    vale = rot.parametros_da_peca(servidor.store, chave)
    assert vale.destino == _DIR and vale.acelerometro == _DIR


def test_o_lado_do_p2_nao_muda_o_p1_nem_o_p3(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    for uniq in (_P1, _P3):
        _mira_set(servidor, uniq=uniq, ligada=True)
    _mira_set(servidor, uniq=_P2, lado=_ESQ)
    lidos = {e["uniq"]: e["mira"] for e in _lidos(servidor)}
    assert [lidos[u]["lado"] for u in _TODOS] == [_DIR, _ESQ, _DIR, _DIR]
    assert [lidos[u]["virtual"] for u in _TODOS] == [True, True, True, False]
    for uniq in (_P1, _P3):
        dele = _movimento(uniq)
        assert (dele.destino, dele.acelerometro) == (_DIR, _DIR), uniq


def test_o_nativo_recusa_o_lado_e_nada_vai_ao_disco(perfis: Path, tmp_path: Path) -> None:
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor(tmp_path, nativo=True)
    assert _mira_set(servidor, uniq=_P2, lado=_ESQ)["status"] == "nativo"
    assert not load_profile("Bancada").controllers


def test_o_lado_torto_e_recusado(perfis: Path, tmp_path: Path) -> None:
    servidor = _servidor(tmp_path)
    for torto in ("mouse", "nenhum", "", 3):
        with pytest.raises(ValueError, match="lado"):
            _mira_set(servidor, uniq=_P2, lado=torto)


# ---------------------------------------------------------------- 3. o motor, P2 e P3


class _Hub:
    """O `SensorHub` mínimo do motor: o giro e a aceleração de um controle."""

    def __init__(self) -> None:
        self.giro = (0.0, 0.0, 0.0)

    def aceleracao_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return (0.0, 0.0, 9.81)

    def velocidade_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return self.giro

    def angulo_do_movimento(self, _u: str) -> tuple[float, float, float]:
        return (0.0, 0.0, 0.0)


def test_o_motor_move_o_lado_de_cada_controle(
        perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O P2 no esquerdo e o P3 no direito: o mesmo `aplicar_o_movimento` que o `coop` chama.

    MORDIDA: o `destino` cravado no direito — o giro do P2 sai pelo direito.
    """
    from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp

    monkeypatch.setattr(REGISTRO, "estado", lambda _u: SimpleNamespace(
        giroscopio=True, acelerometro=True))
    servidor = _servidor(tmp_path)
    _mira_set(servidor, uniq=_P2, lado=_ESQ)
    _mira_set(servidor, uniq=_P3, lado=_DIR)
    hub = _Hub()
    hub.giro = (0.0, 120.0, 0.0)
    daemon = SimpleNamespace(_garantir_sensor_hub=lambda: hub, store=servidor.store,
                             _mouse_device=None)
    ativo = rot.ativo(servidor.store)
    saida = {u: gp.aplicar_o_movimento(daemon, ativo, uniq=u, lx=128, ly=128, rx=128, ry=128,
                                       botoes=frozenset()) for u in (_P2, _P3)}
    lx, ly, rx, ry = saida[_P2]
    assert (lx, ly) != (128, 128) and (rx, ry) == (128, 128), saida
    lx, ly, rx, ry = saida[_P3]
    assert (lx, ly) == (128, 128) and (rx, ry) != (128, 128), saida


# ---------------------------------------------------------------- 4. a tela: a 02 e a Calibrar


def _ligar_a_ponte_ao_servidor(monkeypatch: pytest.MonkeyPatch, servidor: Any) -> None:
    from hefesto_dualsense4unix.app import ipc_bridge

    def _safe_call(method: str, params: Any = None) -> tuple[bool, Any]:
        return True, asyncio.run(servidor._handlers[method](dict(params or {})))

    monkeypatch.setattr(ipc_bridge, "_safe_call", _safe_call)


def _ctx(entradas: list[dict[str, Any]], nativo: bool = False) -> Any:
    import pacotes

    mesa = [{"pref": f"p{i + 1}", "jogador": i + 1, "uniq": e["uniq"], "nome": "DualSense",
             "via": "BT", "transporte": "bt", "conectado": True}
            for i, e in enumerate(entradas)]
    estado = {"native_mode": True} if nativo else {}
    return pacotes.Contexto(state=estado, mesa=mesa, conectados=entradas, estados={})


@pytest.fixture
def com_a_bancada(monkeypatch: pytest.MonkeyPatch) -> None:
    """O pacote filtra pelo publicado; a régua lê a bancada (antes do `--publicar`)."""
    import pacotes.a02_controles as a02
    import pacotes.a11_calibrar_sensores as a11

    from hefesto_dualsense4unix.interface import onde

    doc = onde.pagina("02-controles.html", publicado=False).read_text(encoding="utf-8")
    monkeypatch.setattr(a02, "_ENDERECOS", frozenset(re.findall(r'data-campo="([^"]+)"', doc)))
    monkeypatch.setattr(a11, "_TEM_A_MIRA", True)


def _gesto(pagina: str, nome: str) -> Any:
    import pacotes

    fn = pacotes.gesto_da_pagina(pagina, nome)
    assert fn is not None, f"{pagina}:{nome} não tem dono"
    return fn


def test_o_clique_no_lado_pela_02_e_pela_calibrar(
        perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        com_a_bancada: None) -> None:
    """O «Usar como analógico virtual» da 02 e o «Esquerdo | Direito» da Calibrar: um contrato.

    MORDIDA: o `destino` cravado no direito — o P2 lê o esquerdo e anda pelo direito.
    """
    import pacotes.a02_controles as a02
    import pacotes.a11_calibrar_sensores as a11
    from pacotes import ponte

    servidor = _servidor(tmp_path)
    _ligar_a_ponte_ao_servidor(monkeypatch, servidor)

    _gesto("02-controles.html", "analogico-lado")(
        _ctx(_lidos(servidor)), {"uniq": _P2, "lado": _ESQ}, ponte)
    dele = _movimento(_P2)
    assert (dele.destino, dele.acelerometro, dele.lado) == (_ESQ, _ESQ, _ESQ)
    cards = list(a02.pacote(_ctx(_lidos(servidor)))["cards"].values())
    assert [c["mira-lado"] for c in cards] == ["nenhum", _ESQ, "nenhum", "nenhum"]

    _gesto("calibrar-sensores.html", "analogico-lado")(
        _ctx(_lidos(servidor)), {"uniq": _P2, "lado": _DIR}, ponte)
    colunas = a11.pacote(_ctx(_lidos(servidor)))["colunas"]
    assert (colunas["p2"]["mira-lado"], colunas["p2"]["mira-ligada"]) == (_DIR, a02.SENSOR_LIGADO)
    assert colunas["p1"]["mira-lado"] == "nenhum"

    _gesto("calibrar-sensores.html", "analogico-virtual")(
        _ctx(_lidos(servidor)), {"uniq": _P2}, ponte)
    colunas = a11.pacote(_ctx(_lidos(servidor)))["colunas"]
    assert (colunas["p2"]["mira-lado"], colunas["p2"]["mira-ligada"]) == (
        "nenhum", a02.SENSOR_DESLIGADO)
    assert _movimento(_P2).lado == _DIR, "apagar pela Calibrar esqueceu o lado"


def test_clicar_no_lado_aceso_da_02_desliga_a_mira(
        perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
        com_a_bancada: None) -> None:
    """O «Mira virtual» da 02 liga o lado no apagado e DESLIGA no aceso (todo, 15/10/2026).

    MORDIDA: tire o ramo do lado aceso do `analogico_lado` e o segundo clique volta a ligar.
    """
    from pacotes import ponte

    servidor = _servidor(tmp_path)
    _ligar_a_ponte_ao_servidor(monkeypatch, servidor)
    gesto = _gesto("02-controles.html", "analogico-lado")

    gesto(_ctx(_lidos(servidor)), {"uniq": _P2, "lado": _ESQ}, ponte)
    assert _movimento(_P2).destino == _ESQ
    gesto(_ctx(_lidos(servidor)), {"uniq": _P2, "lado": _ESQ}, ponte)
    dele = _movimento(_P2)
    assert dele.destino != _ESQ and dele.acelerometro != _ESQ, "o clique no aceso não desligou"
    assert dele.lado == _ESQ, "desligar esqueceu o lado"


class _Ponte:
    """O dublê ESTRITO da ponte: amarra o pedido à assinatura da função real."""

    def __init__(self, corpo: dict[str, Any] | None) -> None:
        self.corpo = corpo
        self.chamadas: list[dict[str, Any]] = []

    def mira_set_detalhado(self, **kw: Any) -> dict[str, Any] | None:
        from hefesto_dualsense4unix.app import ipc_bridge

        inspect.signature(ipc_bridge.mira_set_detalhado).bind(**kw)
        self.chamadas.append(kw)
        return self.corpo


@pytest.mark.parametrize("tela", ["02-controles.html", "calibrar-sensores.html"])
def test_o_gesto_do_lado_recusa_no_nativo_e_o_lado_torto(tela: str) -> None:
    import pacotes.a02_controles as a02

    entrada = [{"uniq": _P2, "mira": {"virtual": False, "lado": _DIR}}]
    p = _Ponte({"status": "ok"})
    with pytest.raises(RuntimeError) as erro:
        _gesto(tela, "analogico-lado")(_ctx(entrada, nativo=True), {"uniq": _P2, "lado": _ESQ}, p)
    assert str(erro.value) == a02.MIRA_CINZA_NO_NATIVO and p.chamadas == []
    with pytest.raises(RuntimeError) as erro:
        _gesto(tela, "analogico-lado")(_ctx(entrada), {"uniq": _P2, "lado": _ESQ},
                                         _Ponte({"status": "nativo"}))
    assert str(erro.value) == a02.MIRA_CINZA_NO_NATIVO
    for torto in ("mouse", "nenhum", ""):
        with pytest.raises(ValueError):
            _gesto(tela, "analogico-lado")(_ctx(entrada), {"uniq": _P2, "lado": torto}, p)
    assert p.chamadas == []
    _gesto(tela, "analogico-lado")(_ctx(entrada), {"uniq": _P2, "lado": _ESQ}, p)
    assert p.chamadas == [{"lado": _ESQ, "uniq": _P2}]


def test_nenhuma_pagina_emite_o_gesto_inclinacao() -> None:
    """O chip «Inclinação» aposentou: nenhuma página da bancada o emite, e o pacote não o atende."""
    import pacotes

    paginas = sorted((_RAIZ / "mockup").glob("*.html"))
    assert len(paginas) >= 11, "a bancada sumiu — régua cega"
    emitem = [p.name for p in paginas if 'data-gesto="inclinacao"' in p.read_text("utf-8")]
    assert emitem == [], emitem
    assert pacotes.gesto_da_pagina("02-controles.html", "inclinacao") is None
    for pagina in ("02-controles.html", "calibrar-sensores.html"):
        doc = (_RAIZ / "mockup" / pagina).read_text("utf-8")
        lados = re.findall(r'data-campo="mira-lado"[^>]*>\s*<button[^>]*'
                           r'data-gesto="analogico-lado" data-lado="([^"]+)"', doc)
        assert lados and set(lados) == {_ESQ, _DIR}, (pagina, lados)
