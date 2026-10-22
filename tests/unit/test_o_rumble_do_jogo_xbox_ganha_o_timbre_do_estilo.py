"""O rumble do jogo Xbox ganha o timbre do estilo (O-RUMBLE-DO-JOGO-XBOX-GANHA-O-TIMBRE-01).

A classe sai da linha do tempo do par; o pad guarda a onda do ``FF_PERIODIC``; o tocador toca
cada classe no timbre do estilo e da forma do controle; a energia nunca cai abaixo do seno de
hoje; sem estilo, o bloco é o de hoje, byte a byte. Nenhum processo de som sobe aqui.
"""
from __future__ import annotations

import json
import math
import sys
from array import array
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import classe_do_rumble as classes
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from hefesto_dualsense4unix.integrations.uinput_gamepad import UinputGamepad
from hefesto_dualsense4unix.profiles import formas_de_haptica as formas
from hefesto_dualsense4unix.profiles.estilos_de_jogo import ESTILOS

_RAIZ = Path(__file__).resolve().parents[2]
_ACAO = "acao"  # (noqa-acento): chave do estilo
_QUATRO = ("aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02", "aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")


class _Relogio:
    def __init__(self) -> None:
        self.agora = 100.0

    def __call__(self) -> float:
        return self.agora


def _tocador(marca: str = "prova", relogio: _Relogio | None = None) -> eh.TocadorDoRumble:
    """O tocador real sem processo: nenhum ``pw-cat`` sobe (``argv`` vazio recusa)."""

    def _nao_lanca(*_a: Any, **_k: Any) -> Any:
        raise AssertionError("o teste não sobe processo de som")

    return eh.TocadorDoRumble(
        marca, argv_de=lambda _s, _r: [], lancar=_nao_lanca, relogio=relogio or _Relogio()
    )


def _canais(bloco: bytes) -> tuple[list[float], list[float]]:
    quadros = array("f")
    quadros.frombytes(bloco)
    return list(quadros[2::4]), list(quadros[3::4])


def _rms(valores: list[float]) -> float:
    return math.sqrt(sum(v * v for v in valores) / len(valores))


# --- a classe, pela linha do tempo -------------------------------------------------------------


def test_pulsos_curtos_saem_golpe_e_um_segundo_de_forte_sai_continuo_grave() -> None:
    linha = classes.LinhaDoTempo()
    t = 0.0
    for _ in range(5):  # cinco pulsos de 40 ms com 60 ms de silêncio: tiros
        linha.anotar(t, 120, 200)
        linha.anotar(t + 0.040, 0, 0)
        t += 0.100
    assert linha.contagem[classes.GOLPE] == 5
    linha.anotar(t, 40, 220)
    assert linha.classe(t + 0.05, 40, 220) == classes.GOLPE, "a subida nasce golpe"
    assert linha.classe(t + 0.30, 40, 220) == classes.MEDIO
    assert linha.classe(t + 0.60, 40, 220) == classes.CONTINUO_GRAVE
    assert linha.anotar(t + 1.0, 0, 0) == classes.CONTINUO_GRAVE
    linha.anotar(t + 2.0, 230, 30)
    assert linha.anotar(t + 3.0, 0, 0) == classes.CONTINUO_FINO
    assert [x[0] for x in linha.ultimos][-2:] == [classes.CONTINUO_GRAVE, classes.CONTINUO_FINO]


# --- o pad guarda a onda do FF_PERIODIC --------------------------------------------------------


class _Periodico:
    """Um ``ff_effect`` periódico do kernel, só com o que o parser lê."""

    def __init__(self, ident: int, onda: int, magnitude: int, duracao_ms: int = 1000) -> None:
        from evdev import ecodes

        envelope = SimpleNamespace(
            attack_length=20, attack_level=0x7FFF, fade_length=100, fade_level=0
        )
        self.id = ident
        self.type = ecodes.FF_PERIODIC
        self.ff_replay = SimpleNamespace(length=duracao_ms, delay=0)
        self.u = SimpleNamespace(
            ff_periodic_effect=SimpleNamespace(
                waveform=onda, period=25, magnitude=magnitude, envelope=envelope
            )
        )


@pytest.fixture
def vpad_xbox() -> UinputGamepad:
    from evdev import ecodes

    pad = UinputGamepad.for_flavor("xbox")
    relogio = _Relogio()
    pad.rumble_sink = lambda _w, _s: None
    pad.time_fn = relogio
    pad._ff_supported = True
    pad._ecodes = ecodes
    pad.relogio = relogio  # type: ignore[attr-defined]
    return pad


def test_o_ff_periodic_quadrado_chega_ao_tocador_como_quadrado(vpad_xbox: UinputGamepad) -> None:
    """MORDE: com o ``_parse_ff_effect`` antigo a forma some e o tocador toca o seno."""
    from evdev import ecodes

    from hefesto_dualsense4unix.daemon.subsystems import gamepad

    efeito = vpad_xbox._parse_ff_effect(_Periodico(3, ecodes.FF_SQUARE, 0x6000))
    vpad_xbox._ff_effects[3] = efeito
    vpad_xbox._start_ff_effect(3, repeats=1)
    vpad_xbox._refresh_ff()
    assert vpad_xbox.onda_do_periodico == classes.QUADRADA
    pedidos: list[dict[str, Any]] = []

    def _levar(uniq: str, fraco: int, forte: int, **kw: Any) -> bool:
        pedidos.append({"uniq": uniq, "par": (fraco, forte), **kw})
        return True

    daemon = SimpleNamespace(_alto_falante_subsystem=SimpleNamespace(levar_o_rumble=_levar))
    par = vpad_xbox.ff_last_sent
    gamepad._levar_a_haptica_fina(daemon, vpad_xbox, _QUATRO[0], *par)
    assert pedidos and pedidos[-1].get("onda") == classes.QUADRADA, pedidos
    relogio = _Relogio()
    tocador = _tocador(relogio=relogio)
    tocador.levar(*par, sink="", dono=_QUATRO[0], estilo=_ACAO, forma=formas.IMPACTO,
                  onda=pedidos[-1]["onda"])
    assert tocador.timbre_de_agora() == "periodico:quadrada"
    forte, fraco = _canais(tocador.proximo_bloco(tocador.nivel, tocador.nivel, 0))
    for canal, nivel in ((forte, par[1]), (fraco, par[0])):
        amplitude = nivel / 255.0
        assert all(abs(abs(v) - amplitude) < 1e-4 for v in canal if v), "não é quadrada"
    tocador.parar()


def test_o_pad_conta_as_classes_e_guarda_a_forma_no_upload(vpad_xbox: UinputGamepad) -> None:
    from evdev import ecodes

    upload = SimpleNamespace(effect=_Periodico(5, ecodes.FF_TRIANGLE, 0x4000), retval=None)
    vpad_xbox._device = SimpleNamespace(begin_upload=lambda _v: upload, end_upload=lambda _u: None)
    vpad_xbox._handle_ff_event(
        SimpleNamespace(type=ecodes.EV_UINPUT, code=ecodes.UI_FF_UPLOAD, value=1)
    )
    forma = vpad_xbox.ff_forma_do_periodico
    assert forma is not None and forma["onda"] == classes.TRIANGULO and forma["periodo_ms"] == 25
    vpad_xbox._start_ff_effect(5, repeats=1)
    vpad_xbox._refresh_ff()
    vpad_xbox.relogio.agora += 2.0  # type: ignore[attr-defined]
    vpad_xbox._refresh_ff()
    assert vpad_xbox.ff_por_classe[classes.PERIODICO] == 1
    assert vpad_xbox.ff_ultimos_trechos[-1][0] == classes.PERIODICO
    vpad_xbox._device = None


# --- a energia nunca cai, e sem estilo nada muda ---------------------------------------------


def _timbres_possiveis() -> set[str]:
    chaves: set[str] = set()
    for estilo in [e.chave for e in ESTILOS]:
        for escolha in formas.ESCOLHAS:
            forma = formas.forma_que_vale(escolha, estilo)
            for classe in classes.CLASSES:
                for onda in (None, *classes.ONDAS):
                    chave = formas.timbre_do_rumble(estilo, forma, classe, onda)
                    if chave is not None:
                        chaves.add(chave)
    return chaves


def test_para_cada_timbre_e_cada_par_a_energia_nao_cai_abaixo_do_seno() -> None:
    """MORDE: o timbre a meia amplitude, sem a guarda, fica abaixo do seno e reprova."""
    timbres = _timbres_possiveis()
    assert {"corpo", "grao", "golpe:impacto", "golpe:eco", "periodico:quadrada"} <= timbres
    abaixo: list[tuple[str, tuple[int, int], int]] = []
    for timbre in sorted(timbres):
        for nivel in range(1, 256):
            for par in ((nivel, nivel), (nivel, 0), (0, nivel)):
                fases = (0, 480, 960, 1440, 1920) if nivel % 32 == 1 else (0,)
                for fase in fases:
                    hoje = _canais(eh.bloco_da_haptica(*par, fase=fase))
                    novo = _canais(eh.bloco_com_timbre(*par, timbre, fase=fase))
                    for h, n in zip(hoje, novo, strict=True):
                        if _rms(n) + 1e-6 < _rms(h):
                            abaixo.append((timbre, par, fase))
    assert not abaixo, abaixo[:5]


def test_par_zero_da_o_bloco_mudo_e_a_rampa_tambem_nao_perde() -> None:
    for timbre in _timbres_possiveis():
        assert eh.bloco_com_timbre(0, 0, timbre) == eh.bloco_da_haptica(0, 0)
        hoje = _canais(eh.bloco_da_haptica(200, 30, antes=(0, 0)))
        novo = _canais(eh.bloco_com_timbre(200, 30, timbre, antes=(0, 0)))
        assert all(_rms(n) + 1e-6 >= _rms(h) for h, n in zip(hoje, novo, strict=True)), timbre


@pytest.mark.parametrize("estilo", [None, "nativo", "personalizado", "retro"])
def test_sem_estilo_nativo_personalizado_e_retro_o_bloco_e_o_de_hoje(estilo: str | None) -> None:
    relogio = _Relogio()
    tocador = _tocador(relogio=relogio)
    forma = formas.forma_que_vale(None, estilo)
    for classe in classes.CLASSES:
        assert formas.timbre_do_rumble(estilo, forma, classe, classes.QUADRADA) is None
    tocador.levar(90, 180, sink="", dono="prova", estilo=estilo, forma=forma)
    for passo in (0.0, 0.2, 0.6):
        relogio.agora = 100.0 + passo
        for fase in (0, 480, 960):
            assert tocador.proximo_bloco((90, 180), (90, 180), fase) == eh.bloco_da_haptica(
                90, 180, fase=fase
            )
    tocador.parar()


def test_cada_classe_toca_o_timbre_do_estilo() -> None:
    relogio = _Relogio()
    tocador = _tocador(relogio=relogio)
    tocador.levar(40, 220, sink="", dono="prova", estilo=_ACAO, forma=formas.IMPACTO)
    assert tocador.timbre_de_agora() == "golpe:impacto"
    relogio.agora += 0.6
    assert tocador.timbre_de_agora() == "corpo"
    tocador.levar(0, 0, sink="", dono="prova", estilo=_ACAO, forma=formas.IMPACTO)
    tocador.levar(230, 20, sink="", dono="prova", estilo=_ACAO, forma=formas.IMPACTO)
    relogio.agora += 0.6
    assert tocador.timbre_de_agora() == "grao"  # (noqa-acento): chave
    tocador.parar()
    assert formas.timbre_do_rumble("souls", formas.ECO, classes.GOLPE) == "golpe:eco"
    assert formas.timbre_do_rumble("luta", formas.IMPACTO, classes.CONTINUO_GRAVE) is None


# --- os quatro controles, cada um com a forma dele ---------------------------------------------


def test_quatro_controles_recebem_timbres_diferentes_no_mesmo_tique(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.core.sysfs_leds import norm_mac
    from hefesto_dualsense4unix.daemon.subsystems import tato_vivo
    from hefesto_dualsense4unix.daemon.subsystems.alto_falante import AltoFalanteSubsystem

    escolhas = dict(zip(
        (norm_mac(u) for u in _QUATRO),
        (formas.TOQUE, formas.IMPACTO, formas.ESTALO, formas.ECO),
        strict=True,
    ))
    monkeypatch.setattr(tato_vivo, "escolhas_ativas", lambda _d: escolhas)
    monkeypatch.setattr(tato_vivo, "estilo_ativo", lambda _d: _ACAO)
    sub = object.__new__(AltoFalanteSubsystem)
    sub._daemon = None
    relogio = _Relogio()
    blocos: list[bytes] = []
    timbres: list[str | None] = []
    for i, uniq in enumerate(_QUATRO):
        estilo, forma = sub._o_vestido_do_rumble(uniq)
        tocador = _tocador(f"marca-{i}", relogio)
        tocador.levar(150, 150, sink="", dono=uniq, estilo=estilo, forma=forma)
        timbres.append(tocador.timbre_de_agora())
        blocos.append(tocador.proximo_bloco((150, 150), (150, 150), 0))
        tocador.parar()
    assert timbres == ["golpe:toque", "golpe:impacto", "golpe:estalo", "golpe:eco"]
    assert len(set(blocos)) == 4


# --- o instrumento -----------------------------------------------------------------------------


def test_o_instrumento_conta_classes_ondas_duracoes_e_rota(tmp_path: Path, capsys: Any) -> None:
    sys.path.insert(0, str(_RAIZ / "scripts" / "ensaios"))
    try:
        import contar_o_rumble_do_jogo_xbox as instrumento
    finally:
        sys.path.pop(0)
    base = {"uniq": _QUATRO[0], "player": 1, "ff_forma_do_periodico": None}
    linhas = [
        {"t": 0.0, "per_vpad": [{**base, "ff_play_count": 10, "ff_nao_nulo_count": 4,
                                 "ff_por_classe": {"golpe": 1}, "ff_ultimos_trechos": [],
                                 "ff_rota": {"rota": "motores_do_hid", "porque": "ganho_zero"}}]},
        {"t": 2.0, "per_vpad": [{**base, "ff_play_count": 30, "ff_nao_nulo_count": 14,
                                 "ff_por_classe": {"golpe": 6, "continuo_grave": 1},
                                 "ff_forma_do_periodico": {"onda": "quadrada"},
                                 "ff_ultimos_trechos": [["golpe", 40, 90, 200],
                                                        ["continuo_grave", 900, 10, 230]],
                                 "ff_rota": {"rota": "motores_do_hid", "porque": "ganho_zero"}}]},
    ]
    gravacao = tmp_path / "g.jsonl"
    gravacao.write_text("".join(json.dumps(x) + "\n" for x in linhas), encoding="utf-8")
    assert instrumento.main(["--ler", str(gravacao)]) == 0
    saida = capsys.readouterr().out
    assert "20 plays (10.0/s)" in saida
    assert "golpe 5" in saida and "continuo_grave 1" in saida
    assert "quadrada" in saida
    assert "continuo_grave: 1 subidas, 900 a 900 ms" in saida
    assert "motores_do_hid (ganho_zero) 100%" in saida
