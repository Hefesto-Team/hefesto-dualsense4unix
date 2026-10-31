"""O campo do efeito só diz que chegou pelo recibo do daemon, por controle, no cabo e no rádio.

Sprint O-EFEITO-ESCOLHIDO-MOSTRA-QUE-CHEGOU-AO-CONTROLE-01.

Medido em 31/10/2026: as quatro listas de efeito (Gatilhos, Iluminação, Efeito háptico e Padrão dos
motores) mostravam a escolha lida do perfil, o eco do clique, e nada dizia se o controle a recebeu;
com o daemon parado a tela seguia com a mesma escolha. Hoje o daemon publica `controllers[].efeitos`
(`daemon/o_recibo_dos_efeitos.py`, o bloco do gatilho e a cor da barra comparados com o último
report escrito) e cada lista ganha a marca de `interface/a_chegada.py`.

MORDIDAS: `chegada` devolvendo sempre `CHEGOU` reprova `test_daemon_parado_o_campo_nao_diz_chegou`
e as pinturas; um deslocamento errado em `GATILHOS` reprova `test_o_recibo_confere_o_fio`.
"""

from __future__ import annotations

import pathlib
import re
import threading
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.core import ds_output_report as rep
from hefesto_dualsense4unix.daemon import o_recibo_dos_efeitos as recibo
from hefesto_dualsense4unix.interface import a_chegada, pacotes
from hefesto_dualsense4unix.interface.pacotes import a03_gatilhos as a03
from hefesto_dualsense4unix.interface.pacotes import a05_vibracao as a05
from tests.unit.test_a_04_pergunta_ao_daemon_vivo import mesa_de  # noqa: F401

RAIZ = pathlib.Path(__file__).resolve().parents[2]
MOCKUP = RAIZ / "mockup"
UNIQ = "aa:bb:cc:00:00:01"
UNIQ_BT = "aa:bb:cc:00:00:03"
SUFIXOS = {"03-gatilhos.html": a03.CHEGADAS, "04-iluminacao.html": ("luz",),
           "05-vibracao.html": a05.CHEGADAS}


def _handle(via: str = "usb") -> Any:
    from pydualsense.enums import TriggerModes
    from pydualsense.pydualsense import DSAudio, DSLight, DSTrigger

    from hefesto_dualsense4unix.core.backend_pydualsense import _PinnedPyDualSense

    h = _PinnedPyDualSense.__new__(_PinnedPyDualSense)
    h.light, h.audio, h.triggerL, h.triggerR = DSLight(), DSAudio(), DSTrigger(), DSTrigger()
    h.leftMotor = h.rightMotor = 0
    for nome, valor in {"_brilho_das_luzes": 0, "_haptica_de_audio": False,
                        "_vibracao_v2": False, "_raw_trigger_left": None,
                        "_raw_trigger_right": None, "_escala_do_gatilho": 1.0,
                        "_rumble_active": False, "_rumble_stop_pending": False,
                        "_output_muted": False, "connected": True}.items():
        setattr(h, nome, valor)
    h.triggerR.mode = TriggerModes.Rigid
    h.triggerR.setForce(0, 200)
    h.light.TouchpadColor = (10, 20, 30)
    h._via = via
    return h


def _escrever_no_fio(h: Any) -> None:
    comum = h._build_common(rumble_asserted=False)
    feito = rep.build_bt_report(comum) if h._via == "bt" else rep.build_usb_report(comum)
    h._last_out_report = list(feito)


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_recibo_confere_o_fio(via: str) -> None:
    h = _handle(via)
    _escrever_no_fio(h)
    r = recibo.recibo_do_handle(h)
    assert [r[c]["chegou"] for c in ("gatilho_e", "gatilho_d", "luz")] == [True] * 3, r


@pytest.mark.parametrize("via", ["usb", "bt"])
def test_o_que_mudou_e_nao_saiu_fica_a_caminho(via: str) -> None:
    h = _handle(via)
    _escrever_no_fio(h)
    h.triggerR.setForce(0, 90)
    h.light.TouchpadColor = (200, 0, 0)
    r = recibo.recibo_do_handle(h)
    assert r["gatilho_d"] == {"chegou": False, "porque": recibo.A_CAMINHO}
    assert r["luz"]["chegou"] is False
    assert r["gatilho_e"]["chegou"] is True


def test_sem_report_escrito_nada_chegou() -> None:
    r = recibo.recibo_do_handle(_handle())
    assert not any(v["chegou"] for v in r.values()), r


def test_o_bloco_cru_do_jogo_e_do_jogo() -> None:
    h = _handle()
    h._raw_trigger_left = bytes(11)
    _escrever_no_fio(h)
    r = recibo.recibo_do_handle(h)
    assert r["gatilho_e"] == {"chegou": False, "porque": recibo.JOGO}
    assert r["gatilho_d"]["chegou"] is True


@pytest.mark.parametrize("como", ["handle", "controle"])
def test_o_modo_nativo_entrega_tudo_ao_jogo(como: str) -> None:
    h = _handle()
    _escrever_no_fio(h)
    if como == "handle":
        h._output_muted = True
    r = recibo.recibo_do_handle(h, mudo=como == "controle")
    assert {v["porque"] for v in r.values()} == {recibo.JOGO}
    assert not any(v["chegou"] for v in r.values())


@pytest.mark.parametrize("handle", [None, SimpleNamespace(connected=False)])
def test_sem_controle_tudo_fora_do_fio(handle: Any) -> None:
    r = recibo.recibo_do_handle(handle)
    assert set(r) == set(recibo.CAMPOS)
    assert {v["porque"] for v in r.values()} == {recibo.FORA_DO_FIO}


def test_a_haptica_e_os_motores_nunca_dizem_que_chegaram() -> None:
    h = _handle()
    _escrever_no_fio(h)
    for r in (recibo.recibo_do_handle(h), recibo.recibo_do_handle(None),
              recibo.recibo_do_handle(h, mudo=True)):
        assert not any((r.get(c) or {}).get("chegou") for c in ("haptica", "motores")), r


def _controle(h: Any, *, no_no: Any = None, mudo: bool = False) -> Any:
    return SimpleNamespace(_io_lock=threading.RLock(), _handles={"k": h},
                           _key_for_uniq=lambda u: "k" if u == UNIQ else None,
                           _sysfs_written={"k": no_no} if no_no else {}, _output_mute=mudo)


def test_o_recibo_do_controle_le_o_no_de_led_e_a_animacao() -> None:
    h = _handle()
    _escrever_no_fio(h)
    h._last_out_report[1 + 44:1 + 47] = [0, 0, 0]
    sem_no = recibo.recibo_do_controle(SimpleNamespace(), _controle(h), UNIQ)
    assert sem_no["luz"]["chegou"] is False
    pelo_no = recibo.recibo_do_controle(SimpleNamespace(), _controle(h, no_no=(10, 20, 30)), UNIQ)
    assert pelo_no["luz"]["chegou"] is True
    animando = SimpleNamespace(_luz_animada=SimpleNamespace(tocando=frozenset({UNIQ})))
    assert recibo.recibo_do_controle(animando, _controle(h), UNIQ)["luz"]["anima"] is True
    assert recibo.recibo_do_controle(SimpleNamespace(), _controle(h), "outro")["luz"] == {
        "chegou": False, "porque": recibo.FORA_DO_FIO, "anima": False}
    assert recibo.recibo_do_controle(
        SimpleNamespace(), _controle(h, mudo=True), UNIQ)["gatilho_d"]["porque"] == recibo.JOGO


def _entrada(efeitos: Any = None, **mais: Any) -> dict[str, Any]:
    e: dict[str, Any] = {"uniq": UNIQ, "connected": True, **mais}
    if efeitos is not None:
        e["efeitos"] = efeitos
    return e


TUDO_CHEGOU = {c: {"chegou": True, "porque": None} for c in a_chegada.CAMPOS}


@pytest.mark.parametrize("campo", a_chegada.CAMPOS)
def test_daemon_parado_o_campo_nao_diz_chegou(campo: str) -> None:
    for state in ({}, None, {"controllers": None}):
        assert a_chegada.chegada(state, _entrada(TUDO_CHEGOU), campo) == a_chegada.FORA_DO_AR


@pytest.mark.parametrize(("entrada", "esperado"), [
    (None, a_chegada.SEM_CONTROLE),
    (_entrada(TUDO_CHEGOU, connected=False), a_chegada.SEM_CONTROLE),
    (_entrada(), a_chegada.SEM_RECIBO),
    (_entrada({"luz": {"chegou": False, "porque": "jogo"}}), a_chegada.JOGO),
    (_entrada({"luz": {"chegou": False, "porque": "fora_do_fio"}}), a_chegada.SEM_CONTROLE),
    (_entrada({"luz": {"chegou": False, "porque": "a_caminho"}}), a_chegada.A_CAMINHO),
    (_entrada({"luz": {"chegou": "sim"}}), a_chegada.A_CAMINHO),
    (_entrada({"luz": {"chegou": True, "anima": False}}), a_chegada.CHEGOU),
])
def test_o_campo_so_diz_chegou_pelo_recibo(entrada: Any, esperado: str) -> None:
    assert a_chegada.chegada({"controllers": []}, entrada, "luz") == esperado


def test_a_luz_animada_confere_a_animacao() -> None:
    e = _entrada({"luz": {"chegou": True, "porque": None, "anima": False}})
    assert a_chegada.chegada({"controllers": [e]}, e, "luz", anima=True) == a_chegada.A_CAMINHO
    assert a_chegada.chegada({"controllers": [e]}, e, "luz", anima=False) == a_chegada.CHEGOU


@pytest.mark.parametrize("arquivo", sorted(SUFIXOS))
def test_toda_lista_de_efeito_tem_a_marca_no_mockup(arquivo: str) -> None:
    doc = (MOCKUP / arquivo).read_text(encoding="utf-8")
    for sufixo in SUFIXOS[arquivo]:
        marcas = re.findall(
            rf'<i class="chegada" data-campo="chegada-{sufixo}" data-hef-alvo="atributo" '
            rf'data-hef-atributo="data-chegada" data-chegada="([^"]+)" aria-hidden="true">', doc)
        assert len(marcas) == 4, (arquivo, sufixo, marcas)
        celulas = re.findall(
            rf'<(?:div|span) class="[^"]+" data-campo="chegada-dica-{sufixo}" '
            rf'data-hef-alvo="atributo" data-hef-atributo="data-dica" data-dica="[^"]+">'
            rf'(?:(?!</div>).)*?<select\b(?:(?!</div>).)*?class="chegada"', doc, re.S)
        assert len(celulas) == 4, (arquivo, sufixo, len(celulas))
    assert ".chegada{position:absolute" in doc, arquivo


@pytest.fixture
def lar(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "state"))
    monkeypatch.setattr(a05, "_perfil_ativo", lambda _ctx: {})


def _pintado(aba: str, ctx: Any) -> dict[str, dict[str, Any]]:
    carga = pacotes.PACOTES[aba](ctx)
    pacotes.apagar_os_lugares_sem_dono(carga, [m["pref"] for m in ctx.mesa])
    return carga["colunas"]


def _marcas(colunas: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {pref: {k: v for k, v in col.items() if k.startswith(a_chegada.PREFIXO)
                   and not k.startswith(a_chegada.PREFIXO_DA_DICA)}
            for pref, col in colunas.items()}


@pytest.mark.parametrize("aba", sorted(SUFIXOS))
def test_daemon_parado_as_quatro_colunas_dizem_fora_do_ar(aba: str, lar: None) -> None:
    marcas = _marcas(_pintado(aba, pacotes.Contexto(state={})))
    for pref in ("p1", "p2", "p3", "p4"):
        assert marcas[pref] == {f"chegada-{s}": a_chegada.FORA_DO_AR
                                for s in SUFIXOS[aba]}, (pref, marcas[pref])


@pytest.mark.parametrize("aba", sorted(SUFIXOS))
def test_sem_controle_no_lugar_a_marca_diz_sem_controle(aba: str, lar: None) -> None:
    marcas = _marcas(_pintado(aba, pacotes.Contexto(state={"controllers": []})))
    assert {v for m in marcas.values() for v in m.values()} == {a_chegada.SEM_CONTROLE}


def _ctx_de_dois(efeitos: dict[str, Any] | None) -> Any:
    conectados = [
        {"uniq": u, "player": n, "transport": via, "connected": True, "is_primary": n == 1,
         "inputs": {"l2_raw": 0, "r2_raw": 0}, **({"efeitos": efeitos} if efeitos else {})}
        for u, n, via in ((UNIQ, 1, "usb"), (UNIQ_BT, 3, "bt"))]
    mesa = [{"pref": f"p{n}", "jogador": n, "uniq": c["uniq"], "nome": "Régua",
             "via": c["transport"].upper(), "cor": "starlight-blue", "mascara": "DualSense"}
            for n, c in ((1, conectados[0]), (3, conectados[1]))]
    return pacotes.Contexto(state={"controllers": conectados, "active_profile": ""},
                            mesa=mesa, conectados=conectados)


@pytest.mark.parametrize("aba", sorted(SUFIXOS))
def test_cabo_e_radio_dizem_o_recibo_de_cada_um(aba: str, lar: None) -> None:
    efeitos = {**TUDO_CHEGOU, "luz": {"chegou": True, "porque": None, "anima": False}}
    efeitos.pop("haptica")
    efeitos.pop("motores")
    colunas = _pintado(aba, _ctx_de_dois(efeitos))
    marcas = _marcas(colunas)
    for uniq in (UNIQ, UNIQ_BT):
        for sufixo in SUFIXOS[aba]:
            esperado = (a_chegada.SEM_RECIBO if sufixo in ("haptica", "motores")
                        else a_chegada.CHEGOU)
            assert marcas[uniq][f"chegada-{sufixo}"] == esperado, (uniq, marcas[uniq])
    for pref in ("p2", "p4"):
        assert set(marcas[pref].values()) == {a_chegada.SEM_CONTROLE}, (pref, marcas[pref])
    sem = _marcas(_pintado(aba, _ctx_de_dois(None)))
    assert a_chegada.CHEGOU not in {v for m in sem.values() for v in m.values()}, sem


def test_o_state_full_publica_o_recibo_de_cada_controle(mesa_de: Any) -> None:  # noqa: F811
    from tests.unit.test_a_04_pergunta_ao_daemon_vivo import UNIQS

    mesa = mesa_de()
    entradas = [{"uniq": u, "connected": True, "index": i, "is_primary": i == 0}
                for i, u in enumerate(UNIQS)]
    mesa.server._enrich_controllers_per_controller(entradas, None)
    for e in entradas:
        assert set(e["efeitos"]) == {"gatilho_e", "gatilho_d", "luz"}, e["efeitos"]
        assert e["efeitos"]["gatilho_d"]["chegou"] is False, e["efeitos"]

