"""O efeito sonoro chega ao controle CERTO — SFX-POR-CONTROLE-01 (10/09/2026).

A CENA, com as palavras dela
-----------------------------
    *"o canal de som sfx (a cada tiro dado o som do tiro efeito sonoro sai pra
    cada controle) … De forma que cada user de dualsense tenha a mesma
    experiência ao mesmo tempo."*

E a régua de aceitação, também dela: *"se cada user escolher desativar uma
delas, vai conseguir sem impactar os demais."*

O DEFEITO, e é a MESMA FAMÍLIA que a A1 fechou de manhã
--------------------------------------------------------
`GerenciadorDeNosDeSom` aceita `fonte_por_controle` desde que nasceu, e
**ninguém o injetava**. O campo `speaker.fonte` existe no perfil, a aba o
grava, e todo nó nascia com `FONTE_PADRAO`: a escolha dela morria no disco.

As duas fontes não são detalhe:

* `sfx` — o nó fica livre para a corrente que o jogo mandar (o tiro daquele
  jogador). É o padrão;
* `mix` — o monitor da SAÍDA PADRÃO cai também neste nó. É o «HDMI completo»
  dela: o que a TV recebe, o controle recebe junto.

Numa mesa de quatro, um nó que ignora a escolha entrega a mesma coisa aos
quatro — e o `mix` publicado em quem não pediu põe o áudio do sistema inteiro
no ouvido daquele jogador.

O QUE ESTE ARQUIVO TRAVA
-------------------------
1. a fonte de CADA controle vem do override DAQUELE controle;
2. quem não declarou fica com o padrão — `None` é *"sem opinião"*, não `sfx`;
3. a grafia do `uniq` casa: o sysfs dá `aa:bb:…` e o perfil guarda `aabb…`;
4. o `mix` de um NÃO vira `mix` do vizinho — é o «sem impactar os demais»;
5. o perfil não é relido a cada varredura, e a escolha dela vale na varredura
   seguinte ao "Salvar" (cache por `(nome, mtime)`);
6. e o `start()` de produção injeta o callable — sem isso nada acima existe.

A MORDIDA: tire `fonte_por_controle=` do `start()` e o teste 6 reprova; troque
o `_uniq_de_perfil` por `uniq` cru e o 3 reprova; devolva `FONTE_SFX` no lugar
do `None` em `_fontes_por_controle` e o 2 reprova.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations.alto_falante_bt import (
    FONTE_MIX,
    FONTE_PADRAO,
    FONTE_SFX,
)

#: MACs FORJADOS, da faixa sintética que o portão de fixtures permite.
_P1 = "aa:bb:cc:00:00:b1"
_P2 = "aa:bb:cc:00:00:b2"


def _perfil_com_fontes(tmp_path: Path, fontes: dict[str, str]) -> str:
    """Escreve um perfil de verdade no lar de mentira e devolve o slug."""
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    pasta = Path(profiles_dir(ensure=True))
    nome = "mesa-de-teste"
    corpo: dict[str, Any] = {
        "name": nome,
        # `match` é OBRIGATÓRIO no schema, e omiti-lo aqui fazia o perfil ser
        # recusado pelo pydantic — `_fontes_por_controle` devolvia `{}` pelo
        # `except` (que é o comportamento CERTO do produto) e a régua média o
        # dublê inválido em vez da fiação. `{"type": "any"}` é o que o
        # `assets/profiles_default/personalizado.json` usa.
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
    """Item 1 e 4 — e o item 4 é a régua de aceitação DELA."""
    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_MIX, _P2: FONTE_SFX})
    sub = _subsystem(nome)

    assert sub._fonte_do_controle(_P1) == FONTE_MIX
    assert sub._fonte_do_controle(_P2) == FONTE_SFX, (
        "o P2 herdou a fonte do P1 — o áudio do sistema inteiro cairia no "
        "ouvido de quem pediu só os efeitos do jogo"
    )


def test_quem_nao_declarou_fica_com_o_padrao(tmp_path: Path) -> None:
    """Item 2: `None` é *sem opinião*, e não `sfx` escrito por nós.

    A diferença importa: enquanto ninguém declara, o padrão pode mudar sem
    reescrever perfil nenhum. Se gravássemos `sfx` na ausência, a escolha
    passada de quem nunca escolheu ficaria congelada no disco.
    """
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_MIX})
    # O P2 ganha override de alto-falante **sem** `fonte`: é o caso que a
    # mordida precisa para existir. Com só o P1 no perfil, trocar o `if fonte:`
    # por `if True:` não muda resultado nenhum — a mordida passava, e uma
    # mordida que passa não mede nada.
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
    """Item 3, e é o elo que some em silêncio quando erra.

    O sysfs entrega `aa:bb:cc:…` e o `Profile.controllers` é chaveado por
    `aabbcc…` — o schema recusa a outra forma. Chave que não bate devolve
    `None` sem erro nenhum, e a escolha dela desaparece sem sintoma.
    """
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
    """Item 5: a varredura roda a cada 2 s e não pode ir ao disco toda vez.

    É a tempestade de syscalls que o mapa de motores do `gamepad.py` já pagou
    uma vez — e aqui ela seria por CONTROLE, não por varredura.
    """
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
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O outro lado do cache: gravar o perfil TEM de chegar ao nó.

    Um cache que nunca invalida é pior que ler sempre — a escolha dela ficaria
    presa até o daemon reiniciar, que é o defeito-mãe desta casa (*a escolha
    gravada no disco e nenhum efeito na mesa*).
    """
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    nome = _perfil_com_fontes(tmp_path, {_P1: FONTE_SFX})
    sub = _subsystem(nome)
    assert sub._fonte_do_controle(_P1) == FONTE_SFX

    alvo = Path(profiles_dir(ensure=True)) / f"{nome}.json"
    corpo = json.loads(alvo.read_text(encoding="utf-8"))
    corpo["controllers"][mod._uniq_de_perfil(_P1)]["speaker"]["fonte"] = FONTE_MIX
    alvo.write_text(json.dumps(corpo), encoding="utf-8")
    # O carimbo é `mtime_ns`; duas escritas no mesmo nanossegundo não existem
    # nesta máquina, mas a régua não pode depender disso.
    import os

    agora = alvo.stat().st_mtime_ns + 1_000_000
    os.utime(alvo, ns=(agora, agora))

    assert sub._fonte_do_controle(_P1) == FONTE_MIX, (
        "ela salvou e o nó continuou com a fonte de antes"
    )


def test_o_gerenciador_de_producao_recebe_a_fonte_por_controle() -> None:
    """Item 6 — sem esta linha, tudo acima é peça que ninguém liga.

    É a mesma prova que a A1 escreveu para a ponte, e pela mesma razão: o
    `fonte_por_controle` passou meses como parâmetro sem chamador.
    """
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
