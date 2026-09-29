"""NO-MODO-XBOX-TUDO-FUNCIONA-01 — os chips do toque e da inclinação na aba 02.

A resposta dela de 28/09/2026 (~16h50): o touchpad move o cursor ou vira
botões em zonas, e a inclinação move um analógico, um chip por controle, como a
Mira Virtual. A página publicada ganhou os chips em 29/09 (a «Inclinação»
embaixo de cada analógico e o «Cursor | Botões» no pé do touchpad) SEM gesto no
pacote: clicar neles não fazia nada. Esta régua mede as três pernas:

1. **o gesto** (`inclinacao`, `toque`): lê o destino que o daemon publica,
   alterna (o chip aceso apaga, o outro troca), manda UM campo ao `mira.set`,
   e recusa no Nativo e sem leitura, P1 a P4;
2. **a ponte** (`ipc_bridge.mira_set_detalhado`): leva os dois campos, e os
   chamadores de hoje (a Mira, a Calibrar) mandam o mesmo corpo de antes;
3. **a pintura** (`inclinacao-destino`, `toque-modo`): o valor do daemon, que
   acende o chip certo pelo `data-hef-quando` da página publicada.

E a volta inteira com o `IpcServer` de verdade: o clique chega ao disco e ao
`state_full`, e a tela lê de volta o que acabou de gravar.

Endereços de rádio: a faixa SINTÉTICA da casa (``aa:bb:cc``), nunca um OUI real.
"""

from __future__ import annotations

import asyncio
import inspect
import re
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.core import roteador_de_movimento as rot

#: Os `pacotes` e o `mesa_viva` moram na pasta da interface, como no piloto.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]
                       / "src" / "hefesto_dualsense4unix" / "interface"))

_P1, _P2, _P3, _P4 = (
    "aa:bb:cc:00:00:01",
    "aa:bb:cc:00:00:02",
    "aa:bb:cc:00:00:03",
    "aa:bb:cc:00:00:04",
)
_TODOS = (_P1, _P2, _P3, _P4)

_PAGINA = "02-controles.html"

#: Os dois chips: o gesto, o atributo do botão na página, o campo do `mira.set`
#: e da leitura, o endereço da pintura, e os destinos que a tela oferece.
_CHIPS = (
    ("inclinacao", "destino", "inclinacao", "inclinacao-destino",
     (rot.DESTINO_ANALOGICO_ESQUERDO, rot.DESTINO_ANALOGICO_DIREITO)),
    ("toque", "toque", "toque", "toque-modo",
     (rot.TOQUE_CURSOR, rot.TOQUE_ZONAS)),
)


class _Ponte:
    """O dublê ESTRITO da ponte: amarra o pedido à assinatura da função real.

    Com `**kw` solto, um gesto que mandasse um nome que a ponte não conhece
    passaria aqui e levantaria `TypeError` no produto.
    """

    def __init__(self, corpo: dict[str, Any] | None) -> None:
        self.corpo = corpo
        self.chamadas: list[dict[str, Any]] = []

    def mira_set_detalhado(self, **kw: Any) -> dict[str, Any] | None:
        from hefesto_dualsense4unix.app import ipc_bridge

        inspect.signature(ipc_bridge.mira_set_detalhado).bind(**kw)
        self.chamadas.append(kw)
        return self.corpo


_OK = {"status": "ok", "alcance": {"tique": "aplicado"}, "ressalva": None}


def _controle(uniq: str, transporte: str, **mira: Any) -> dict[str, Any]:
    dele: dict[str, Any] = {"uniq": uniq, "transport": transporte,
                            "connected": True, "inputs": {}, "audio": {},
                            "speaker": {}}
    if mira:
        dele["mira"] = {"ligada": False, "destino": rot.DESTINO_NENHUM, **mira}
    return dele


def _ctx(*controles: dict[str, Any], nativo: bool = False) -> Any:
    import pacotes

    estado = {"native_mode": True} if nativo else {}
    return pacotes.Contexto(state=estado, mesa=[], conectados=list(controles),
                            estados={})


def _o_gesto(nome: str) -> Any:
    import pacotes

    fn = pacotes.gesto_da_pagina(_PAGINA, nome)
    assert fn is not None, f"{_PAGINA}:{nome} não tem dono"
    return fn


# ---------------------------------------------------------------------------
# 1. O GESTO
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("gesto, atributo, campo, _pintura, oferece", _CHIPS)
def test_o_chip_alterna_pelo_que_o_daemon_diz(
    gesto: str, atributo: str, campo: str, _pintura: str,
    oferece: tuple[str, str],
) -> None:
    """Apagado acende, aceso apaga, e o outro do grupo troca — um campo só.

    MORDIDA: mande o `pedido` sempre (sem o `nenhum` do chip aceso) e o
    segundo caso reprova.
    """
    um, outro = oferece
    for agora, esperado in ((rot.DESTINO_NENHUM, um), (um, rot.DESTINO_NENHUM),
                            (outro, um)):
        p = _Ponte(_OK)
        _o_gesto(gesto)(_ctx(_controle(_P1, "usb", **{campo: agora})),
                        {"uniq": _P1, atributo: um}, p)
        assert p.chamadas == [{campo: esperado, "uniq": _P1}], (agora, p.chamadas)


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("gesto, atributo, campo, _pintura, oferece", _CHIPS)
def test_cada_controle_le_o_seu_e_grava_o_seu(
    gesto: str, atributo: str, campo: str, _pintura: str,
    oferece: tuple[str, str], transporte: str,
) -> None:
    """P1 a P4, no cabo e no rádio: o clique no cartão de um não lê o de outro.

    O P3 tem o chip aceso e os outros não: o clique no P3 apaga, e o clique
    em cada um dos outros acende — o `uniq` do cartão é o endereço dos dois
    lados.
    """
    um = oferece[0]
    controles = [
        _controle(u, transporte, **{campo: um if u == _P3 else rot.DESTINO_NENHUM})
        for u in _TODOS
    ]
    for uniq in _TODOS:
        p = _Ponte(_OK)
        _o_gesto(gesto)(_ctx(*controles), {"uniq": uniq, atributo: um}, p)
        esperado = rot.DESTINO_NENHUM if uniq == _P3 else um
        assert p.chamadas == [{campo: esperado, "uniq": uniq}], (uniq, p.chamadas)


@pytest.mark.parametrize("gesto, atributo, campo, _pintura, oferece", _CHIPS)
def test_no_nativo_o_chip_recusa_sem_pedir(
    gesto: str, atributo: str, campo: str, _pintura: str,
    oferece: tuple[str, str],
) -> None:
    """No Nativo o chip é cinza e o clique não chega à ponte.

    MORDIDA: tire o `if _nativo(ctx)` do `_alternar_o_chip` e a ponte é
    chamada.
    """
    import pacotes.a02_controles as a02

    cinza = {"inclinacao": a02.INCLINACAO_CINZA_NO_NATIVO,
             "toque": a02.TOQUE_CINZA_NO_NATIVO}[gesto]
    p = _Ponte(_OK)
    with pytest.raises(RuntimeError) as erro:
        _o_gesto(gesto)(
            _ctx(_controle(_P2, "bt", **{campo: rot.DESTINO_NENHUM}), nativo=True),
            {"uniq": _P2, atributo: oferece[0]}, p)
    assert str(erro.value) == cinza
    assert p.chamadas == []
    # e o daemon que recusa pelo Nativo (o tique de antes) diz a mesma frase
    with pytest.raises(RuntimeError) as erro:
        _o_gesto(gesto)(_ctx(_controle(_P2, "bt", **{campo: rot.DESTINO_NENHUM})),
                        {"uniq": _P2, atributo: oferece[0]},
                        _Ponte({"status": "nativo", "motivo": "texto do daemon"}))
    assert str(erro.value) == cinza


@pytest.mark.parametrize("gesto, atributo, campo, _pintura, oferece", _CHIPS)
def test_sem_leitura_ou_sem_resposta_o_chip_recusa(
    gesto: str, atributo: str, campo: str, _pintura: str,
    oferece: tuple[str, str],
) -> None:
    """Sem o bloco `mira`, alternar é chutar; sem `ok`, não é «aplicado»."""
    import pacotes.a02_controles as a02

    p = _Ponte(_OK)
    with pytest.raises(RuntimeError) as erro:
        _o_gesto(gesto)(_ctx(_controle(_P1, "usb")),
                        {"uniq": _P1, atributo: oferece[0]}, p)
    assert str(erro.value) == a02.SEM_LEITURA_DO_CHIP
    assert p.chamadas == []

    with pytest.raises(RuntimeError) as erro:
        _o_gesto(gesto)(_ctx(_controle(_P1, "usb", **{campo: rot.DESTINO_NENHUM})),
                        {"uniq": _P1, atributo: oferece[0]},
                        _Ponte({"status": "sem_controle", "motivo": "texto do daemon"}))
    assert str(erro.value) == a02.CHIP_SEM_O_CONTROLE

    with pytest.raises(RuntimeError):
        _o_gesto(gesto)(_ctx(_controle(_P1, "usb", **{campo: rot.DESTINO_NENHUM})),
                        {"uniq": _P1, atributo: oferece[0]}, _Ponte(None))


@pytest.mark.parametrize("gesto, atributo, campo, _pintura, oferece", _CHIPS)
def test_o_clique_sem_destino_ou_sem_controle_recusa(
    gesto: str, atributo: str, campo: str, _pintura: str,
    oferece: tuple[str, str],
) -> None:
    """O `nenhum` não é chip, e um destino que a tela não tem não vira pedido."""
    ctx = _ctx(_controle(_P1, "usb", **{campo: rot.DESTINO_NENHUM}))
    for torto in (rot.DESTINO_NENHUM, "", "mouse"):
        p = _Ponte(_OK)
        with pytest.raises(ValueError):
            _o_gesto(gesto)(ctx, {"uniq": _P1, atributo: torto}, p)
        assert p.chamadas == []
    with pytest.raises(ValueError):
        _o_gesto(gesto)(ctx, {atributo: oferece[0]}, _Ponte(_OK))


# ---------------------------------------------------------------------------
# 2. A PONTE
# ---------------------------------------------------------------------------


def _ponte_que_anota(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, Any]]:
    from hefesto_dualsense4unix.app import ipc_bridge

    pedidos: list[tuple[str, Any]] = []

    def _safe_call(method: str, params: Any = None) -> tuple[bool, Any]:
        pedidos.append((method, params))
        return True, {"status": "ok"}

    monkeypatch.setattr(ipc_bridge, "_safe_call", _safe_call)
    return pedidos


def test_a_ponte_leva_os_dois_campos(monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: tire o `payload["toque"]` da ponte e o segundo caso reprova."""
    from hefesto_dualsense4unix.app import ipc_bridge

    pedidos = _ponte_que_anota(monkeypatch)
    ipc_bridge.mira_set_detalhado(inclinacao="analogico_direito", uniq=_P4)
    ipc_bridge.mira_set_detalhado(toque="zonas", uniq=_P2)
    ipc_bridge.mira_set_detalhado(toque="nenhum", uniq=_P2)
    assert pedidos == [
        ("mira.set", {"inclinacao": "analogico_direito", "uniq": _P4}),
        ("mira.set", {"toque": "zonas", "uniq": _P2}),
        ("mira.set", {"toque": "nenhum", "uniq": _P2}),
    ]


def test_os_chamadores_de_hoje_mandam_o_mesmo_corpo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A Mira e a Calibrar não mandam os campos novos sem pedir."""
    from hefesto_dualsense4unix.app import ipc_bridge

    pedidos = _ponte_que_anota(monkeypatch)
    ipc_bridge.mira_set_detalhado(ligada=True, uniq=_P1)
    ipc_bridge.mira_set_detalhado(sensibilidade=9, uniq=_P1)
    assert ipc_bridge.mira_set_detalhado(uniq=_P1) is None
    assert pedidos == [
        ("mira.set", {"ligada": True, "uniq": _P1}),
        ("mira.set", {"sensibilidade": 9, "uniq": _P1}),
    ]
    padrao = inspect.signature(ipc_bridge.mira_set_detalhado).parameters
    assert padrao["inclinacao"].default is None
    assert padrao["toque"].default is None


# ---------------------------------------------------------------------------
# 3. A PINTURA
# ---------------------------------------------------------------------------


def _cards(*controles: dict[str, Any], nativo: bool = False) -> dict[str, Any]:
    import pacotes.a02_controles as a02

    cards: dict[str, Any] = a02.pacote(_ctx(*controles, nativo=nativo))["cards"]
    assert cards, "o pacote não montou card nenhum — régua cega"
    return cards


def test_a_pintura_e_o_destino_do_daemon_por_controle() -> None:
    """Cada cartão pinta o SEU destino; sem leitura, o travessão.

    Usa o `_so_se_a_pagina_tiver` de verdade: a página publicada tem os dois
    endereços, e é nela que o piloto pinta.

    MORDIDA: pinte o `campo` do P1 em todos e o P3 reprova.
    """
    import mesa_viva

    controles = [
        _controle(_P1, "usb", inclinacao=rot.DESTINO_ANALOGICO_ESQUERDO,
                  toque=rot.TOQUE_CURSOR),
        _controle(_P2, "bt", inclinacao=rot.DESTINO_NENHUM, toque=rot.TOQUE_ZONAS),
        _controle(_P3, "usb", inclinacao=rot.DESTINO_ANALOGICO_DIREITO,
                  toque=rot.DESTINO_NENHUM),
        _controle(_P4, "bt"),
    ]
    cards = list(_cards(*controles).values())
    assert len(cards) == 4, f"quatro controles, {len(cards)} cartões"
    vistos = [(c["inclinacao-destino"], c["toque-modo"]) for c in cards]
    assert vistos == [
        (rot.DESTINO_ANALOGICO_ESQUERDO, rot.TOQUE_CURSOR),
        (rot.DESTINO_NENHUM, rot.TOQUE_ZONAS),
        (rot.DESTINO_ANALOGICO_DIREITO, rot.DESTINO_NENHUM),
        (mesa_viva.SEM_LEITOR, mesa_viva.SEM_LEITOR),
    ]


def test_no_nativo_o_cinza_vem_junto_e_o_aceso_fica() -> None:
    """O Nativo acende o `mira-fora` dos botões e não apaga o que o daemon diz."""
    import pacotes.a02_controles as a02

    card = next(iter(_cards(
        _controle(_P1, "usb", inclinacao=rot.DESTINO_ANALOGICO_ESQUERDO,
                  toque=rot.TOQUE_ZONAS), nativo=True).values()))
    assert card["mira-fora"] == a02.MIRA_NO_NATIVO
    assert card["inclinacao-destino"] == rot.DESTINO_ANALOGICO_ESQUERDO
    assert card["toque-modo"] == rot.TOQUE_ZONAS


# ---------------------------------------------------------------------------
# 4. A PÁGINA PUBLICADA E O PACOTE FALAM A MESMA LÍNGUA
# ---------------------------------------------------------------------------


def _publicada() -> str:
    from hefesto_dualsense4unix.interface import onde

    return onde.pagina(_PAGINA, publicado=True).read_text(encoding="utf-8")


@pytest.mark.parametrize("gesto, atributo, _campo, pintura, oferece", _CHIPS)
def test_todo_chip_da_pagina_tem_o_destino_que_o_gesto_aceita(
    gesto: str, atributo: str, _campo: str, pintura: str,
    oferece: tuple[str, str],
) -> None:
    """Quatro cartões, cada um com os dois do grupo; o `data-hef-quando` do
    invólucro é o valor que o botão pede, e o botão tem o cinza da Mira."""
    doc = _publicada()
    botoes = re.findall(
        r'<span[^>]*data-campo="' + re.escape(pintura) + r'"[^>]*'
        r'data-hef-quando="([^"]+)"[^>]*>\s*<button([^>]*)>', doc)
    assert len(botoes) == 8, f"{pintura}: esperava 8 chips, vi {len(botoes)}"
    for quando, attrs in botoes:
        assert f'data-gesto="{gesto}"' in attrs, attrs
        assert f'data-{atributo}="{quando}"' in attrs, (quando, attrs)
        assert quando in oferece, quando
        assert 'data-campo="mira-fora"' in attrs, attrs
    assert sorted({q for q, _ in botoes}) == sorted(oferece)


# ---------------------------------------------------------------------------
# 5. A VOLTA INTEIRA — o clique, o `mira.set` de verdade e o `state_full`
# ---------------------------------------------------------------------------


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


def _servidor(tmp_path: Path, transporte: str, nativo: bool = False) -> Any:
    """O `Daemon` e o `IpcServer` do produto, com um perfil ativo no disco."""
    from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon
    from hefesto_dualsense4unix.profiles.loader import save_profile
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.profiles.schema import MatchAny, Profile
    from hefesto_dualsense4unix.testing import FakeController

    perfil = Profile(name="Bancada", match=MatchAny(type="any"))
    save_profile(perfil)
    controle = FakeController(transport=transporte)  # type: ignore[arg-type]
    controle.primary_uniq = _P1  # type: ignore[attr-defined]
    daemon = Daemon(controller=controle)
    if nativo:
        daemon.is_native_mode = lambda: True  # type: ignore[method-assign]
    gerente = ProfileManager(controller=controle, store=daemon.store)
    servidor = IpcServer(controller=controle, store=daemon.store,
                         profile_manager=gerente,
                         socket_path=tmp_path / "chips.sock", daemon=daemon)
    daemon._ipc_server = servidor
    gerente.apply_movimento(perfil)
    servidor.store.set_active_profile(perfil.name)
    return servidor


def _ligar_a_ponte_ao_servidor(monkeypatch: pytest.MonkeyPatch, servidor: Any) -> None:
    from hefesto_dualsense4unix.app import ipc_bridge

    def _safe_call(method: str, params: Any = None) -> tuple[bool, Any]:
        return True, asyncio.run(servidor._handlers[method](dict(params or {})))

    monkeypatch.setattr(ipc_bridge, "_safe_call", _safe_call)


def _lidos(servidor: Any, transporte: str) -> list[dict[str, Any]]:
    entradas = [{"uniq": u, "transport": transporte, "connected": True,
                 "inputs": {}, "audio": {}, "speaker": {}} for u in _TODOS]
    servidor._merge_mira(entradas)
    return entradas


@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize("gesto, atributo, campo, pintura, oferece", _CHIPS)
def test_o_clique_chega_ao_disco_e_a_tela_le_de_volta(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    gesto: str, atributo: str, campo: str, pintura: str,
    oferece: tuple[str, str], transporte: str,
) -> None:
    """Acende no P3, só no P3; o segundo clique no mesmo chip apaga.

    A ponte é a de verdade (`pacotes.ponte` → `ipc_bridge`), e só o soquete é
    trocado pela chamada direta ao handler do `IpcServer` do produto.
    """
    from pacotes import ponte

    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor(tmp_path, transporte)
    _ligar_a_ponte_ao_servidor(monkeypatch, servidor)
    schema = {"inclinacao": "acelerometro", "toque": "toque"}[campo]
    um = oferece[0]

    _o_gesto(gesto)(_ctx(*_lidos(servidor, transporte)), {"uniq": _P3, atributo: um},
                    ponte)
    dele = (load_profile("Bancada").controllers or {})["aabbcc000003"].movimento
    assert dele is not None and getattr(dele, schema) == um
    cards = list(_cards(*_lidos(servidor, transporte)).values())
    assert [c[pintura] for c in cards] == [
        um if u == _P3 else rot.DESTINO_NENHUM for u in _TODOS]

    _o_gesto(gesto)(_ctx(*_lidos(servidor, transporte)), {"uniq": _P3, atributo: um},
                    ponte)
    dele = (load_profile("Bancada").controllers or {})["aabbcc000003"].movimento
    assert dele is not None and getattr(dele, schema) == rot.DESTINO_NENHUM
    cards = list(_cards(*_lidos(servidor, transporte)).values())
    assert all(c[pintura] == rot.DESTINO_NENHUM for c in cards)


@pytest.mark.parametrize("gesto, atributo, campo, _pintura, oferece", _CHIPS)
def test_o_daemon_no_nativo_nao_grava(
    perfis: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    gesto: str, atributo: str, campo: str, _pintura: str,
    oferece: tuple[str, str],
) -> None:
    """A tela leu um tique antes do Nativo: o daemon recusa e nada vai ao disco."""
    from pacotes import ponte

    import pacotes.a02_controles as a02
    from hefesto_dualsense4unix.profiles.loader import load_profile

    servidor = _servidor(tmp_path, "usb", nativo=True)
    _ligar_a_ponte_ao_servidor(monkeypatch, servidor)
    cinza = {"inclinacao": a02.INCLINACAO_CINZA_NO_NATIVO,
             "toque": a02.TOQUE_CINZA_NO_NATIVO}[gesto]
    with pytest.raises(RuntimeError) as erro:
        _o_gesto(gesto)(_ctx(*_lidos(servidor, "usb")),
                        {"uniq": _P2, atributo: oferece[0]}, ponte)
    assert str(erro.value) == cinza
    assert not load_profile("Bancada").controllers
