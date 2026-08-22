"""O retrato das abas usa o MÉTODO DE PRODUÇÃO, nunca uma cópia dele.

O DEFEITO, medido em 22/08/2026, e ele custou uma decisão dela.

O `retratar_abas.py` montava os 19 modos da aba Gatilhos À MÃO — um
`SegmentedSelector(wrap=True)` criado ali mesmo e empacotado com
`slot.pack_start(sel, True, True, 0)`. O `expand=True` daquele `pack_start`
**não existe no produto**, e por causa dele a moldura saía esticada até o pé da
página: 1016px de 1040, com uns 640px de vazio entre a grade e o "Aplicar em L2".

Ela decidiu a fila de interface OLHANDO ESSA FOTO. A dúvida da decisão 1 do
`DECISOES.md` — *"o vazio dos Gatilhos não sumiu, mudou de lado"* — nasceu de um
vazio que era do INSTRUMENTO, não do produto. Com o método de produção a mesma
moldura mede 482px.

E a ironia estava escrita no próprio arquivo: o docstring da função dizia, sobre
os RÓTULOS, que *"uma lista copiada aqui viraria um segundo dono, e a foto
passaria a mentir no dia em que um deles mudasse"*. A regra estava certa e foi
aplicada só à metade — os rótulos vinham da fonte única, o LAYOUT era cópia.

É a família que esta casa mais paga: **o instrumento mente mais que o produto**.
Três medições falsas num único dia em 07/08, e esta é a quarta.

O QUE ESTE PORTÃO COBRA: toda aba que o retrato monta em código chama o método
de produção. A régua é a IMPORTAÇÃO do mixin — não o texto do docstring, que é
justamente o que estava certo enquanto o código estava errado.
"""
from __future__ import annotations

import ast
import inspect
from pathlib import Path

_RETRATO = (
    Path(__file__).resolve().parents[2] / "scripts" / "gui-captura" / "retratar_abas.py"
)

#: Os mixins que montam aba em código, e que o retrato TEM de chamar em vez de
#: reimplementar. Cada entrada é `(módulo do produto, o que a foto perderia)`.
#:
#: A lista cresce quando uma aba nova passa a ser montada em código. Ela NÃO é a
#: régua sozinha — o teste também cobra que ninguém construa widget de aba à mão
#: (ver `test_o_retrato_nao_monta_widget_de_aba_a_mao`), que é o que pega a aba
#: que ainda não está aqui.
MIXINS_DE_ABA: dict[str, str] = {
    "TriggersActionsMixin": "os 19 modos de gatilho e a área de parâmetros",
    "ProfilesActionsMixin": 'o "Aplica a", o "Modo" e a lista do Steam Input',
    "ConfigActionsMixin": "as cinco seções da aba Configurações",
}


def _arvore() -> ast.Module:
    return ast.parse(_RETRATO.read_text(encoding="utf-8"))


def _nomes_usados() -> set[str]:
    """Todo nome que o retrato CITA — importado direto ou por atributo.

    As DUAS formas contam, e a segunda não é detalhe: o retrato importa a aba
    Perfis como `profiles_actions as _pa` e usa `_pa.ProfilesActionsMixin`.
    A primeira versão desta régua só olhava o import direto e reprovou uma aba
    que estava CERTA — portão que acusa quem fez a coisa certa ensina a próxima
    pessoa a desligá-lo, e esta casa já pagou por isso em 13/08.
    """
    nomes: set[str] = set()
    for no in ast.walk(_arvore()):
        if isinstance(no, ast.ImportFrom):
            nomes.update(a.asname or a.name for a in no.names)
        elif isinstance(no, ast.Import):
            nomes.update((a.asname or a.name).split(".")[0] for a in no.names)
        elif isinstance(no, ast.Attribute):
            nomes.add(no.attr)
    return nomes


def test_o_retrato_chama_o_mixin_de_cada_aba_montada_em_codigo() -> None:
    """Mordida: trocar a chamada de `install_triggers_tab` por uma montagem à mão."""
    citados = _nomes_usados()
    faltando = {
        mixin: perda
        for mixin, perda in MIXINS_DE_ABA.items()
        if mixin not in citados
    }
    assert not faltando, (
        "o retrato deixou de usar o método de produção destas abas: "
        + "; ".join(f"{m} (a foto perde {p})" for m, p in faltando.items())
        + ". Montar à mão faz a foto mentir sobre o layout, e é olhando a foto "
        "que ela decide."
    )


def test_o_retrato_nao_monta_widget_de_aba_a_mao() -> None:
    """A régua que pega a aba que ainda não está em `MIXINS_DE_ABA`.

    Construir um `SegmentedSelector` no retrato é o sintoma: ele é o widget que
    as abas usam para os seus seletores, e o produto sempre o cria dentro de um
    mixin. Uma construção aqui é uma segunda montagem por definição.

    **A BANCADA DE MENTIRA CONTINUA PERMITIDA, e a diferença é o que separa
    este portão de um estorvo:** injetar DADO (controles de mentira, uma mesa de
    rádio inventada, jogos que não existem) é o trabalho deste script e é o que
    protege a privacidade dela. O que ele não pode é injetar LAYOUT.

    Mordida: acrescentar um `SegmentedSelector(...)` a qualquer função do
    retrato.
    """
    construcoes: list[str] = []
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        nome = (
            alvo.id
            if isinstance(alvo, ast.Name)
            else alvo.attr
            if isinstance(alvo, ast.Attribute)
            else None
        )
        if nome == "SegmentedSelector":
            construcoes.append(f"linha {no.lineno}")

    assert not construcoes, (
        "o retrato voltou a construir widget de aba à mão "
        f"({', '.join(construcoes)}). O layout tem de vir do mixin de produção; "
        "só DADO pode ser injetado aqui."
    )


def test_a_regua_deste_portao_nao_confere_a_si_mesma() -> None:
    """A trava contra o defeito que este arquivo existe para pegar.

    Um portão que lê o próprio docstring do alvo, ou que itera a mesma lista que
    deveria conferir, passa com a cura arrancada. Aconteceu TRÊS vezes nesta casa
    em 22/08/2026.

    Aqui a régua é a árvore de sintaxe do retrato, e a lista `MIXINS_DE_ABA` é
    conferida contra o PRODUTO: cada mixin nomeado tem de existir de verdade em
    `app/actions/`, senão a lista poderia ser preenchida com nomes inventados e
    o primeiro teste passaria por acidente.
    """
    from hefesto_dualsense4unix.app.actions import (
        profiles_actions,
        triggers_actions,
    )
    from hefesto_dualsense4unix.app.actions import config as config_pkg

    vivos = set()
    for modulo in (triggers_actions, profiles_actions, config_pkg):
        vivos.update(
            nome
            for nome, obj in vars(modulo).items()
            if inspect.isclass(obj) and nome.endswith("Mixin")
        )

    fantasmas = set(MIXINS_DE_ABA) - vivos
    assert not fantasmas, (
        f"a lista deste portão nomeia mixin que não existe no produto: "
        f"{sorted(fantasmas)}. Régua que aponta para o vazio aprova qualquer coisa."
    )
