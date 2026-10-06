"""O efeito sonoro chega ao controle CERTO — SFX-POR-CONTROLE-01 (10/09/2026)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as som
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    FONTE_MIX,
    FONTE_PADRAO,
    FONTE_SFX,
)
from tests.unit import bancada_do_som_junto as bancada

_P1 = "aa:bb:cc:00:00:b1"
_P2 = "aa:bb:cc:00:00:b2"


def _perfil_com_fontes(tmp_path: Path, fontes: dict[str, str]) -> str:
    """Escreve um perfil de verdade no lar de mentira e devolve o slug."""
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    pasta = Path(profiles_dir(ensure=True))
    nome = "mesa-de-teste"
    corpo: dict[str, Any] = {
        "name": nome,
        "match": {"type": "any"},
        "controllers": {
            mod._uniq_de_perfil(uniq): {"speaker": {"volume": 180, "fonte": fonte}}
            for uniq, fonte in fontes.items()
        },
    }
    (pasta / f"{nome}.json").write_text(json.dumps(corpo), encoding="utf-8")
    return nome


class _Store:
    def __init__(self, perfil: str | None) -> None:
        self.active_profile = perfil


def _subsystem(perfil: str | None) -> Any:
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._store = _Store(perfil)
    return sub


def test_cada_controle_recebe_a_fonte_do_override_dele(tmp_path: Path) -> None:
    """Item 1 e 4 — e o item 4 é a régua de aceitação DO USUÁRIO."""
    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_MIX, _P2: FONTE_SFX})
    sub = _subsystem(nome)

    assert sub._fonte_do_controle(_P1) == FONTE_MIX
    assert sub._fonte_do_controle(_P2) == FONTE_SFX, (
        "o P2 herdou a fonte do P1 — o áudio do sistema inteiro cairia no "
        "ouvido de quem pediu só os efeitos do jogo"
    )


def test_quem_nao_declarou_fica_com_o_padrao(tmp_path: Path) -> None:
    """Item 2: `None` é *sem opinião*, e não `sfx` escrito por nós."""
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_MIX})
    alvo = Path(profiles_dir(ensure=True)) / f"{nome}.json"
    corpo = json.loads(alvo.read_text(encoding="utf-8"))
    corpo["controllers"][mod._uniq_de_perfil(_P2)] = {"speaker": {"volume": 120}}
    alvo.write_text(json.dumps(corpo), encoding="utf-8")
    sub = _subsystem(nome)

    assert sub._fonte_do_controle(_P2) == FONTE_PADRAO
    assert mod._fontes_por_controle(nome) == {mod._uniq_de_perfil(_P1): FONTE_MIX}, (
        "um controle sem `fonte` entrou no dicionário — `None` virou palpite, "
        "e a diferença entre «ela escolheu efeitos» e «ela não escolheu» "
        "desapareceu"
    )


def test_a_grafia_do_uniq_casa_entre_o_sysfs_e_o_perfil(tmp_path: Path) -> None:
    """Item 3, e é o elo que some em silêncio quando erra."""
    assert mod._uniq_de_perfil("AA:BB:CC:00:00:B1") == "aabbcc0000b1"
    assert mod._uniq_de_perfil("aabbcc0000b1") == "aabbcc0000b1"

    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_MIX})
    sub = _subsystem(nome)
    assert sub._fonte_do_controle(_P1.upper()) == FONTE_MIX


def test_sem_perfil_ativo_a_resposta_e_o_padrao(tmp_path: Path) -> None:
    """Ausência é resposta, e ela não pode virar `mix`."""
    sub = _subsystem(None)
    assert sub._fonte_do_controle(_P1) == FONTE_PADRAO
    assert sub._fontes_do_perfil() == {}


def test_o_perfil_nao_e_relido_a_cada_varredura(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Item 5: a varredura roda a cada 2 s e não pode ir ao disco toda vez."""
    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_MIX})
    sub = _subsystem(nome)
    leituras = {"n": 0}
    real = mod._fontes_por_controle

    def _contando(quem: str) -> dict[str, str]:
        leituras["n"] += 1
        return real(quem)

    monkeypatch.setattr(mod, "_fontes_por_controle", _contando)

    for _ in range(20):
        sub._fonte_do_controle(_P1)
        sub._fonte_do_controle(_P2)

    assert leituras["n"] == 1, (
        f"o perfil foi lido {leituras['n']} vezes em 20 varreduras — o cache "
        "por (nome, mtime) não está segurando"
    )


def test_a_escolha_dela_vale_na_varredura_seguinte(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O outro lado do cache: gravar o perfil TEM de chegar ao NÓ VIVO."""
    pactl = bancada.Pactl()
    monkeypatch.setattr(som, "_rodar", pactl)

    nome = bancada.escrever_perfil({_P1: FONTE_SFX})
    sub, ger = bancada.subsystem_e_gerenciador(
        nome, ponte_do_radio_por_controle=lambda _uniq: (lambda: True)
    )
    ger.reconciliar([bancada.radio(_P1)])
    no = ger.nos[_P1]
    assert pactl.loopbacks == [], "o nó nasceu com o mix sem ela ter pedido"

    bancada.ela_clica(_P1, FONTE_MIX)
    ger.reconciliar([bancada.radio(_P1)])

    assert pactl.loopbacks == [(f"{bancada.HDMI}.monitor", no.nome)], (
        "ela salvou e o nó VIVO continuou com a fonte de antes — "
        f"loopbacks de pé: {pactl.loopbacks}"
    )
    assert sub._fonte_do_controle(_P1) == FONTE_MIX


def test_o_gerenciador_de_producao_recebe_a_fonte_por_controle() -> None:
    """Item 6 — sem esta linha, tudo acima é peça que ninguém liga."""
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])

    class _Ctx:
        controller = None
        store = _Store(None)

    try:
        asyncio.run(sub.start(_Ctx()))
        ger = sub._gerenciador
        assert ger._fonte_por_controle is not None, (
            "o gerenciador de produção nasceu sem saber a fonte de cada "
            "controle — o `speaker.fonte` do perfil dela não chega ao nó"
        )
        assert ger._fonte_do_no("nao-existe") == FONTE_PADRAO
    finally:
        asyncio.run(sub.stop())
