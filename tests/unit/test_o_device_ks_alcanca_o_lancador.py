"""LANCADOR-AGNOSTICO-01 — a háptica nativa chega a quem não tem wrapper."""

from __future__ import annotations

import pathlib

import pytest

from hefesto_dualsense4unix.daemon import launch_env


@pytest.fixture
def _lar(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch):
    """Um prefixo de lançador com registro, e a lista apontada para ele."""
    prefixo = tmp_path / "Prefixes" / "Um Jogo"
    (prefixo / "pfx").mkdir(parents=True)
    (prefixo / "pfx" / "system.reg").write_text(
        "WINE REGISTRY Version 2\n\n", encoding="utf-8")
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    monkeypatch.setattr(cv, "prefixos_dos_lancadores", lambda *a, **k: [prefixo])
    return prefixo


def test_o_prefixo_do_lancador_recebe_o_device(_lar, monkeypatch):
    """O caso dela: um prefixo do Heroic, com um DualSense na mesa.

    MORDIDA: tire a chamada de `_device_ks_nos_lancadores` do
    `materialize_launch_env`. O prefixo continua sem device, e a háptica nativa
    não chega ao jogo — o estado medido no disco dela em 21/09.
    """
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    monkeypatch.setattr(
        ks, "controles_no_cabo",
        lambda *a, **k: [ks.Controle(pid=0x0CE6, bus=1, dev=7, usec=42)])
    monkeypatch.setattr(ks, "controles_no_radio", lambda *a, **k: [])
    monkeypatch.setattr(ks, "placas_servidas", lambda *a, **k: [])

    fora = launch_env._device_ks_nos_lancadores()

    assert fora == {"escritos": 1, "ocupados": 0, "prefixos": 1}
    texto = (_lar / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert "HEFESTOKS" in texto, (
        "o device KS não chegou ao prefixo do lançador — a háptica nativa "
        "continua só nos jogos da Steam")


def test_a_segunda_volta_nao_reescreve(_lar, monkeypatch):
    """Idempotente: o mesmo conjunto de controles não toca o arquivo de novo."""
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    monkeypatch.setattr(
        ks, "controles_no_cabo",
        lambda *a, **k: [ks.Controle(pid=0x0CE6, bus=1, dev=7, usec=42)])
    monkeypatch.setattr(ks, "controles_no_radio", lambda *a, **k: [])
    monkeypatch.setattr(ks, "placas_servidas", lambda *a, **k: [])

    launch_env._device_ks_nos_lancadores()
    fora = launch_env._device_ks_nos_lancadores()

    assert fora["escritos"] == 0, "a segunda volta reescreveu o registro"


def test_o_prefixo_ocupado_e_pulado_e_contado(_lar, monkeypatch):
    """Escrever por baixo de um jogo aberto é o defeito que a guarda impede."""
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    monkeypatch.setattr(ks, "controles_no_cabo", lambda *a, **k: [])
    monkeypatch.setattr(ks, "controles_no_radio", lambda *a, **k: [])
    monkeypatch.setattr(ks, "placas_servidas", lambda *a, **k: [])
    monkeypatch.setattr(ks, "wineserver_do_prefixo_vivo", lambda *a, **k: True)

    fora = launch_env._device_ks_nos_lancadores()

    assert fora == {"escritos": 0, "ocupados": 1, "prefixos": 1}
    assert "HEFESTOKS" not in (
        _lar / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_sem_lancador_nao_ha_o_que_fazer(monkeypatch):
    """A máquina de quem só tem Steam: zero prefixos, zero varredura."""
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    monkeypatch.setattr(cv, "prefixos_dos_lancadores", lambda *a, **k: [])

    assert launch_env._device_ks_nos_lancadores() == {
        "escritos": 0, "ocupados": 0, "prefixos": 0}


def test_a_carona_vai_dentro_do_try_da_materializacao():
    """Uma escrita que levanta não pode derrubar o start da emulação."""
    fonte = pathlib.Path(
        "src/hefesto_dualsense4unix/daemon/launch_env.py"
    ).read_text(encoding="utf-8")
    corpo = fonte[fonte.index("def materialize_launch_env("):]
    corpo = corpo[: corpo.index("\n    except Exception:")]
    assert "_device_ks_nos_lancadores()" in corpo, (
        "a carona do device KS saiu do `try` da materialização")


def test_o_numero_vai_ao_log(monkeypatch):
    """Sem o número, «rodou e não tinha o que fazer» lê-se como «não rodou»."""
    fonte = pathlib.Path(
        "src/hefesto_dualsense4unix/daemon/launch_env.py"
    ).read_text(encoding="utf-8")
    assert "device_ks=ks," in fonte


_DO_DONO = [
    ("lugar", 0x0CE6, 3, 11),
    ("cabo", 0x0CE6, 1, 7),
]


def _a_lista_do_dono(monkeypatch: pytest.MonkeyPatch) -> list[object]:
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    lista = [ks.Controle(pid=pid, bus=bus, dev=dev, usec=None) for _q, pid, bus, dev in _DO_DONO]
    monkeypatch.setattr(ks, "controles_do_registro", lambda *a, **k: list(lista))
    monkeypatch.setattr(ks, "controles_no_cabo", lambda *a, **k: [])
    monkeypatch.setattr(ks, "controles_no_radio", lambda *a, **k: [])
    return lista


def test_a_carona_do_daemon_le_o_dono_da_lista(_lar, monkeypatch):
    """O daemon grava o que o dono diz, e não uma soma própria.

    MORDIDA: volte `_device_ks_nos_lancadores` a `controles_no_cabo() +
    controles_no_radio()` — o prefixo fica sem os lugares.
    """
    _a_lista_do_dono(monkeypatch)
    assert launch_env._device_ks_nos_lancadores()["escritos"] == 1
    texto = (_lar / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert "HEFESTOKS&003&011&0" in texto and "HEFESTOKS&001&007&0" in texto


def test_o_curador_do_lancamento_le_o_dono_da_lista(_lar, monkeypatch):
    """O gancho de lançamento roda o `main` do curador: a mesma lista.

    MORDIDA: volte o `main` a somar `controles_no_cabo` e `controles_no_radio`.
    """
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    _a_lista_do_dono(monkeypatch)
    compat = _lar
    assert ks.main(["--prefixo", str(compat)]) == 0
    texto = (compat / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert "HEFESTOKS&003&011&0" in texto and "HEFESTOKS&001&007&0" in texto
