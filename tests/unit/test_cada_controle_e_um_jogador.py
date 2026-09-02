#!/usr/bin/env python3
"""A RÉGUA DO FUNDAMENTO: cada controle é um jogador, e isso não se ajusta.

DECISÃO DELA, 02/09/2026, com estas palavras:

    "isso não é escolha de interface. Ninguem que conecta 2 controles quer usar
     ambos pra controlar o mesmo personagem. quer usar 2 controles pra ambos
     serem diferentes e usáveis. Remove ele aqui e impeça que isso retorne de
     alguma forma. Isso é sempre true. sempre."

<!-- noqa-acento: citação literal dela -->

O QUE ESTA RÉGUA GUARDA: não existe interruptor de co-op em perfil nenhum.
Quem liga dois controles quer dois jogadores — e o produto não pergunta, não
grava e não lê nada a respeito.

O DONO ÚNICO DO FATO é `DaemonConfig.coop_enabled`, que nasce `True`. Um
segundo dono em `ProfileModeConfig` faria a mesma pergunta duas vezes, com duas
respostas possíveis — e é assim que um perfil passa a desligar, pelas costas,
algo que ninguém pediu.

AS QUATRO COISAS QUE ELA COBRA:

1. **O esquema do perfil não tem campo de co-op.** Nem esse nome, nem outro.
2. **Nada no mundo de perfis LÊ um co-op de perfil.** Um leitor sem campo é o
   caminho de volta pronto: basta alguém acrescentar o campo e ele acorda.
3. **A tela não oferece a escolha.** Nem no gerador, nem no HTML publicado.
4. **O dono único continua nascendo ligado.**

A MORDIDA: acrescente `coop: bool = True` ao `ProfileModeConfig` e o caso 1
reprova; faça qualquer arquivo de `profiles/` ler `mode.coop` e o caso 2
reprova; ponha um `data-campo="coop"` numa aba e o caso 3 reprova.
"""
from __future__ import annotations

import pathlib
import re
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

#: As grafias que um campo de co-op poderia assumir. Não é lista de nomes
#: proibidos por superstição: é a pergunta "existe um interruptor para isto?",
#: e ela tem de ser respondida NÃO em qualquer grafia.
_GRAFIAS = ("coop", "co_op", "cooperativo", "multiplayer_local", "jogador_unico")


def test_o_esquema_do_perfil_nao_tem_interruptor_de_coop() -> None:
    from hefesto_dualsense4unix.profiles.schema import Profile, ProfileModeConfig

    for cls in (ProfileModeConfig, Profile):
        campos = set(getattr(cls, "model_fields", {}) or {})
        achados = sorted(c for c in campos if any(g in c.lower() for g in _GRAFIAS))
        assert not achados, (
            f"`{cls.__name__}` ganhou {achados} — um interruptor de co-op em "
            f"perfil. Quem liga dois controles quer dois jogadores; o produto "
            f"não pergunta. O dono do fato é `DaemonConfig.coop_enabled`."
        )


def test_nada_no_mundo_de_perfis_le_um_coop_de_perfil() -> None:
    """Um leitor sem campo é o caminho de volta já pavimentado."""
    culpados: list[str] = []
    padrao = re.compile(r'(mode\.coop|mode\.get\(\s*["\']coop|\.coop\b)')
    for py in sorted((RAIZ / "src" / "hefesto_dualsense4unix" / "profiles").glob("*.py")):
        texto = py.read_text(encoding="utf-8", errors="ignore")
        for n, linha in enumerate(texto.splitlines(), 1):
            nua = linha.strip()
            if nua.startswith("#") or nua.startswith("*") or nua.startswith('"'):
                continue
            if padrao.search(linha):
                culpados.append(f"{py.name}:{n}: {nua[:80]}")
    assert not culpados, (
        "alguém em `profiles/` voltou a ler um co-op de perfil:\n"
        + "\n".join(f"  - {c}" for c in culpados)
    )


def test_a_tela_nao_oferece_a_escolha() -> None:
    """Nem no gerador, nem no HTML que ela clica."""
    from hefesto_dualsense4unix.interface import onde

    culpados: list[str] = []
    alvos = list(onde.PUBLICADO.glob("*.html"))
    alvos += list((RAIZ / "src" / "hefesto_dualsense4unix" / "interface").glob("aba*.py"))
    for f in alvos:
        texto = f.read_text(encoding="utf-8", errors="ignore")
        for attr in ("data-campo", "data-gesto", "name", "id"):
            for valor in re.findall(rf'{attr}="([^"]+)"', texto):
                if any(g in valor.lower() for g in _GRAFIAS):
                    culpados.append(f"{f.name}: {attr}={valor}")
    assert not culpados, (
        "a tela voltou a oferecer a escolha de co-op:\n"
        + "\n".join(f"  - {c}" for c in culpados)
        + "\nNão é escolha de interface — é fundamento do produto."
    )


def test_o_dono_unico_nasce_ligado() -> None:
    """Se ele nascer desligado, dois controles viram um jogador — calado."""
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    assert DaemonConfig().coop_enabled is True, (
        "`DaemonConfig.coop_enabled` deixou de nascer ligado. É o ÚNICO dono "
        "do fato, e desligado ele faz dois controles moverem o mesmo "
        "personagem — o oposto do que quem pluga dois controles quer."
    )


@pytest.mark.parametrize("kind", ["native", "gamepad", "desktop"])
def test_um_mode_de_qualquer_tipo_nao_aceita_coop(kind: str) -> None:
    """`extra="forbid"` é o que faz a proibição valer no DISCO, não só no código.

    Um perfil que trouxesse `"coop"` seria recusado na validação — e é assim
    que o campo não volta por um arquivo escrito à mão.
    """
    from pydantic import ValidationError

    from hefesto_dualsense4unix.profiles.schema import ProfileModeConfig

    ProfileModeConfig(kind=kind)  # o caminho normal segue funcionando
    with pytest.raises(ValidationError):
        ProfileModeConfig(kind=kind, coop=True)
