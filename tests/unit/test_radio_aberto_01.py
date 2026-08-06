"""RADIO-ABERTO-01 — o portão da combinação que anula a autenticação do BT.

Achado em 04/08/2026 por um cético de segurança, numa auditoria que investigava
OUTRA coisa. É o único item da leva do Bluetooth cujo pior caso não é um
controle que não funciona — é alguém ao alcance do rádio digitando na máquina
de quem instalou isto.

A combinação, toda instalada POR PADRÃO e sem flag:

  1. `JustWorksRepairing = always` — o BlueZ aceita re-pareamento de quem já
     tem bond, por Just Works, removendo a ÚLTIMA recusa;
  2. `bt-agent --capability=NoInputNoOutput` — agente padrão do sistema;
     NoInputNoOutput dos dois lados = Just Works = zero proteção contra MITM;
  3. `FastConnectable=true` — page scan agressivo, de propósito.

O caminho: o atacante se apresenta com o BD_ADDR de um controle bondado
(BD_ADDR é escrivível por comando de fabricante em dongles CSR/Realtek comuns),
inicia SSP, cai em Just Works, e o `always` deixa a LinkKey ser sobrescrita sem
nenhuma interação humana. O device sobe HIDP — e **o descritor de relatório quem
escolhe é ele**. Descritor de teclado = injeção de teclas na sessão dela.

**Nenhuma das três peças está errada sozinha.** É a composição — a mesma forma
de defeito que a leva inteira vem encontrando.

O que este arquivo trava (E1 da sprint):

  - nenhum asset de BlueZ desta casa pode voltar a `JustWorksRepairing=always`;
  - o `confirm` tem de estar presente nos três assets, não apenas ausente o
    `always` (um asset que perdesse a chave inteira também "passaria" num teste
    que só procura `always`).

MORDIDA: troque `confirm` por `always` em qualquer um dos três assets e
`test_nenhum_asset_pede_just_works_sempre` fica vermelho, nomeando o arquivo.

O que este arquivo NÃO trava, e é honestidade necessária: o `confirm` sozinho
**não fecha** o buraco. Ele devolve ao BlueZ a decisão de perguntar, mas quem
responde é o agente — e o agente padrão hoje é o `bt-agent` genérico com
`NoInputNoOutput`, que autoriza. **A E2 da sprint (agente próprio, que autoriza
por política e recusa HID de teclado fora de uma janela de pareamento
explícita) continua ABERTA**, e é ela que fecha o cenário. Esta entrega remove
o "sempre aceita, sem nem perguntar"; não substitui a E2.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
ASSETS_BT = REPO_ROOT / "assets" / "bluetooth"

#: Os três assets que carregam a chave — drop-in, bloco legado e bloco unificado.
ASSETS_COM_A_CHAVE = (
    ASSETS_BT / "hefesto-justworks.conf",
    ASSETS_BT / "hefesto-justworks.block",
    ASSETS_BT / "hefesto-bt.block",
)

#: Casa `JustWorksRepairing = always` em linha ATIVA (não comentada), com ou sem
#: espaços à volta do `=` — as duas formas existem na árvore.
_ATIVA_ALWAYS = re.compile(r"^[ \t]*JustWorksRepairing[ \t]*=[ \t]*always[ \t]*$", re.M)
_ATIVA_CONFIRM = re.compile(r"^[ \t]*JustWorksRepairing[ \t]*=[ \t]*confirm[ \t]*$", re.M)


@pytest.mark.parametrize("asset", ASSETS_COM_A_CHAVE, ids=lambda p: p.name)
def test_nenhum_asset_pede_just_works_sempre(asset: Path) -> None:
    """`always` remove a última recusa do BlueZ. Nenhum asset pode pedi-lo."""
    assert asset.exists(), f"asset sumiu: {asset.relative_to(REPO_ROOT)}"
    texto = asset.read_text(encoding="utf-8")
    achado = _ATIVA_ALWAYS.search(texto)
    assert achado is None, (
        f"{asset.name} voltou a pedir JustWorksRepairing=always. Isso remove a "
        "ÚLTIMA recusa do BlueZ ao re-pareamento por Just Works de quem já tem "
        "bond e, com o agente NoInputNoOutput, o caminho termina em injeção de "
        "teclas (RADIO-ABERTO-01). Se uma janela de `always` for mesmo "
        "necessária, ela tem de ser ARMADA POR GESTO E DESARMADA POR TIMER — "
        "nunca um regime permanente instalado por padrão."
    )


@pytest.mark.parametrize("asset", ASSETS_COM_A_CHAVE, ids=lambda p: p.name)
def test_os_assets_declaram_confirm(asset: Path) -> None:
    """Ausência de `always` não basta: a chave tem de estar lá, com `confirm`.

    Sem esta asserção, apagar a chave inteira passaria no teste de cima — e o
    BlueZ cairia no default da distro, que não é decisão desta casa.
    """
    texto = asset.read_text(encoding="utf-8")
    assert _ATIVA_CONFIRM.search(texto) is not None, (
        f"{asset.name} não declara JustWorksRepairing=confirm — o valor tem de "
        "ser explícito, não herdado do default da distro"
    )


def test_a_justificativa_do_always_ficou_registrada() -> None:
    """A decisão anterior era MEDIDA e não se apaga: ganha nota datada.

    Regra da casa (CLAUDE.md): *"Não se apaga decisão medida. Ela ganha uma nota
    datada com o que caducou."* O `always` nasceu para curar a migração do
    backport da ONDA-R — e o que caducou foi o REGIME PERMANENTE, não a
    observação original.
    """
    for asset in ASSETS_COM_A_CHAVE:
        texto = asset.read_text(encoding="utf-8")
        assert "RADIO-ABERTO-01" in texto, (
            f"{asset.name} mudou de valor sem registrar por quê e desde quando"
        )
        assert "always" in texto, (
            f"{asset.name} apagou a memória do valor anterior — a nota datada "
            "precisa dizer o que caducou"
        )
