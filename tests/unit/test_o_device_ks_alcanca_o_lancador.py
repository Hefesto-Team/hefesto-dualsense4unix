"""LANCADOR-AGNOSTICO-01 — a háptica nativa chega a quem não tem wrapper.

**O QUE FALTAVA, medido no disco dela em 21/09/2026.** O device KS (o que a RE
Engine acha pelo `KSCATEGORY_AUDIO`) mora no `system.reg` do prefixo, e quem o
escreve nos jogos da STEAM é o wrapper `hefesto-launch`, no lançamento:

    três prefixos da Steam ....... 24, 36 e 42 ocorrências de `HEFESTOKS`
    o prefixo do Heroic .......... ZERO

**O Heroic não passa por wrapper nenhum.** A leva de 21/09 abriu a ENUMERAÇÃO
(`camadas_vulkan.raizes_de_prefixo` passou a somar os prefixos dos lançadores
aos `compatdata`), e isso já alcança o uninstall e o censo de camadas — mas
ninguém ESCREVIA o device naquele prefixo.

A cura é a carona: `materialize_launch_env` já roda a cada transição de
controle, e o que muda o device KS é exatamente o conjunto de controles.
"""

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

    fora = launch_env._device_ks_nos_lancadores()

    assert fora == {"escritos": 1, "ocupados": 0, "prefixos": 1}
    texto = (_lar / "pfx" / "system.reg").read_text(encoding="utf-8")
    assert "HEFESTOKS" in texto, (
        "o device KS não chegou ao prefixo do lançador — a háptica nativa "
        "continua só nos jogos da Steam")


def test_a_segunda_volta_nao_reescreve(_lar, monkeypatch):
    """Idempotente: o mesmo conjunto de controles não toca o arquivo de novo.

    Rodar a cada transição de controle não pode acumular bloco nem trocar a
    data do `system.reg` por nada.

    MORDIDA: tire o `_mesmos_blocos` do `aplicar`. A segunda volta conta uma
    escrita, e esta régua reprova.
    """
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    monkeypatch.setattr(
        ks, "controles_no_cabo",
        lambda *a, **k: [ks.Controle(pid=0x0CE6, bus=1, dev=7, usec=42)])
    monkeypatch.setattr(ks, "controles_no_radio", lambda *a, **k: [])

    launch_env._device_ks_nos_lancadores()
    fora = launch_env._device_ks_nos_lancadores()

    assert fora["escritos"] == 0, "a segunda volta reescreveu o registro"


def test_o_prefixo_ocupado_e_pulado_e_contado(_lar, monkeypatch):
    """Escrever por baixo de um jogo aberto é o defeito que a guarda impede.

    **É O ESTADO REAL DA MÁQUINA DELA EM 21/09**, às 06:20: o `wineserver` do
    prefixo do Guardiões da Galáxia continuava vivo desde as 03:01, e a
    tentativa respondeu `ocupado`. O número vai ao log para que isso se leia
    como *"adiado"*, e nunca como *"não rodou"*.

    MORDIDA: faça `_device_ks_nos_lancadores` ignorar o motivo. O contador
    mente e o adiamento vira silêncio.
    """
    from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks

    monkeypatch.setattr(ks, "controles_no_cabo", lambda *a, **k: [])
    monkeypatch.setattr(ks, "controles_no_radio", lambda *a, **k: [])
    monkeypatch.setattr(ks, "wineserver_do_prefixo_vivo", lambda *a, **k: True)

    fora = launch_env._device_ks_nos_lancadores()

    assert fora == {"escritos": 0, "ocupados": 1, "prefixos": 1}
    assert "HEFESTOKS" not in (
        _lar / "pfx" / "system.reg").read_text(encoding="utf-8")


def test_sem_lancador_nao_ha_o_que_fazer(monkeypatch):
    """A máquina de quem só tem Steam: zero prefixos, zero varredura.

    O wrapper continua sendo quem serve a Steam, e varrer os 32 `compatdata`
    dela aqui seria pagar de novo o que ele já paga.
    """
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv

    monkeypatch.setattr(cv, "prefixos_dos_lancadores", lambda *a, **k: [])

    assert launch_env._device_ks_nos_lancadores() == {
        "escritos": 0, "ocupados": 0, "prefixos": 0}


def test_a_carona_vai_dentro_do_try_da_materializacao():
    """Uma escrita que levanta não pode derrubar o start da emulação.

    MORDIDA: mova a chamada para fora do `try`. Um disco hostil passa a
    derrubar a materialização inteira — o contrato que a docstring daquela
    função promete.
    """
    fonte = pathlib.Path(
        "src/hefesto_dualsense4unix/daemon/launch_env.py"
    ).read_text(encoding="utf-8")
    corpo = fonte[fonte.index("def materialize_launch_env("):]
    corpo = corpo[: corpo.index("\n    except Exception:")]
    assert "_device_ks_nos_lancadores()" in corpo, (
        "a carona do device KS saiu do `try` da materialização")


def test_o_numero_vai_ao_log(monkeypatch):
    """Sem o número, «rodou e não tinha o que fazer» lê-se como «não rodou».

    MORDIDA: tire o `device_ks=` do `logger.info`.
    """
    fonte = pathlib.Path(
        "src/hefesto_dualsense4unix/daemon/launch_env.py"
    ).read_text(encoding="utf-8")
    assert "device_ks=ks," in fonte
