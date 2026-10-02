"""O volume do microfone vai para o controle NOMEADO, nunca para o vizinho.

O DEFEITO, e ele estava declarado pelo próprio esquema em vez de curado:
``ControllerMicOverride`` RECUSA o campo ``volume`` por peça, na borda, com a
razão escrita — ``Daemon.apply_profile_mic`` resolvia a fonte de captura com
``fonte_de_captura_do_controle()``, que devolve a PRIMEIRA fonte da lista.

**Com dois DualSense no cabo há DUAS placas de som** (MIC-DA-MESA-CHEIA-01,
20/08/2026), cada uma pendurada no seu dispositivo USB. A rota global mandaria
o volume de um controle ao microfone do outro.

A CURA É A COSTURA QUE O ESQUEMA PEDE, e o texto dele a nomeia: *"quando o
applier passar a chamar `fonte_de_captura_do_uniq`, o campo entra aqui"*. A
função já existe e já foi curada em 03/09 para resolver também o controle no
RÁDIO — antes ela devolvia ``None`` para qualquer um sem placa de som própria.

**A METADE QUE IMPORTA É NÃO CAIR PARA A ROTA GLOBAL.** Se o ``uniq`` não
resolve, escrever na primeira fonte da lista é exatamente o estrago que a linha
existe para impedir — e é o erro fácil de cometer escrevendo um ``or``.

A MORDIDA: troque a escolha por ``fonte_de_captura_do_controle()`` incondicional
em ``lifecycle.apply_profile_mic`` e :func:`test_o_volume_vai_para_a_fonte_do_uniq`
reprova, mostrando o volume chegando à fonte do vizinho.
"""

from __future__ import annotations

from typing import Any

import pytest

EU = "aabbcc0000ff"
O_VIZINHO = "aabbcc0000ee"

MINHA_FONTE = "alsa_input.usb-Sony_DualSense-00.mono-fallback"
FONTE_DO_VIZINHO = "alsa_input.usb-Sony_DualSense-01.mono-fallback"


@pytest.fixture
def daemon(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Um `Daemon` cru, com só o que `apply_profile_mic` toca."""
    from hefesto_dualsense4unix.daemon.lifecycle import Daemon

    return Daemon.__new__(Daemon)


@pytest.fixture
def escritas(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, str]]:
    """Registra `(volume, fonte)` de cada escrita, sem tocar no PulseAudio."""
    from hefesto_dualsense4unix.integrations import audio_control

    fora: list[tuple[int, str]] = []

    def _definir(volume: int, *, fonte: str) -> bool:
        fora.append((int(volume), fonte))
        return True

    def _do_uniq(uniq: str) -> str | None:
        return {EU: MINHA_FONTE, O_VIZINHO: FONTE_DO_VIZINHO}.get(uniq)

    monkeypatch.setattr(audio_control, "definir_volume_da_captura", _definir)
    monkeypatch.setattr(audio_control, "fonte_de_captura_do_uniq", _do_uniq)
    monkeypatch.setattr(audio_control, "fonte_de_captura_do_controle",
                        lambda: FONTE_DO_VIZINHO)
    return fora


def test_o_volume_vai_para_a_fonte_do_uniq(
        daemon: Any, escritas: list[tuple[int, str]]) -> None:
    """Com `uniq`, escreve na placa DAQUELE controle."""
    daemon.apply_profile_mic(volume=42, uniq=EU, origin="teste")
    assert escritas == [(42, MINHA_FONTE)], (
        "o volume não chegou à fonte do controle nomeado — na mesa cheia isso "
        f"é mexer no microfone do vizinho. Escritas: {escritas}")


def test_sem_uniq_a_rota_global_continua(
        daemon: Any, escritas: list[tuple[int, str]]) -> None:
    """A seção GLOBAL `mic` do perfil não tem dono, e continua pela rota antiga."""
    daemon.apply_profile_mic(volume=7, origin="teste")
    assert escritas == [(7, FONTE_DO_VIZINHO)]


def test_uniq_sem_fonte_nao_cai_para_a_global(
        daemon: Any, escritas: list[tuple[int, str]]) -> None:
    """Se o controle nomeado não tem fonte, ninguém escreve."""
    resultado = daemon.apply_profile_mic(volume=99, uniq="nao-existe",
                                         origin="teste")
    assert escritas == [], f"escreveu no vizinho: {escritas}"
    assert resultado != "APLICADO", (
        "disse `APLICADO` sem ter escrito em lugar nenhum")


def test_o_esquema_abriu_o_volume_por_peca_e_o_dia_foi_deliberado() -> None:
    """A borda ABRIU — 03/09/2026, e o dia foi deliberado, como este fio pedia."""
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import ControllerMicOverride

    assert ControllerMicOverride.model_validate({"volume": 50}).volume == 50
    for fora in (-1, 101, 999):
        with pytest.raises(ValidationError):
            ControllerMicOverride.model_validate({"volume": fora})
