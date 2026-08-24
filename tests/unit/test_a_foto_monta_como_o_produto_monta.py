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

#: Os NOMES citados pela documentação — cópia por VALOR do `NOMES` do
#: retrato, lida por AST em `_nomes_da_documentacao()` para não depender de
#: `gi` neste arquivo. A ORDEM não importa aqui; o que importa é o conjunto.
#:
#: Z0-2 (24/08/2026), §2.2/M2 da sprint Z0-01: até aqui `MIXINS_DE_ABA` listava
#: "as três abas que já deram problema" — três mixins soltos, sem ligação com
#: nome de foto nenhum — e o retrato já monta DEZ em código. Início, Status e
#: No jogo não tinham régua nenhuma: nenhuma linha aqui, nenhuma na tabela do
#: F14 (`test_p10_...`), nenhuma no AST do `main` (`test_o_main_monta_...`).
#:
#: Agora a chave é o NOME DA FOTO (`NOMES`), uma linha por aba, e o valor é
#: `(mixin de produção que a monta, o que a foto perderia sem ele)`. Duas abas
#: — Status e No jogo — compartilham o mesmo mixin (`StatusActionsMixin` monta
#: as duas, `status_actions.py`), e é assim mesmo: o retrato usa o MESMO método
#: de produção duas vezes, não uma cópia.
MIXINS_DE_ABA: dict[str, tuple[str, str]] = {
    "readme_inicio": (
        "HomeActionsMixin",
        "a mesa de jogadores (Modo Nativo/co-op, quem é primário, bateria)",
    ),
    "readme_status": (
        "StatusActionsMixin",
        "o card do controle — sem ele a aba mais densa da janela sai vazia",
    ),
    "readme_no_jogo": (
        "StatusActionsMixin",
        "os painéis por jogador e o aviso do perfil que não entrou",
    ),
    "readme_gatilhos": (
        "TriggersActionsMixin",
        "os 19 modos de gatilho e a área de parâmetros",
    ),
    "readme_lightbar": (
        "LightbarActionsMixin",
        "a prévia de cor e a frase de quem acendeu o desenho",
    ),
    "readme_rumble": (
        "RumbleActionsMixin",
        "o estado da vibração e quem a controla (jogo ou janela)",
    ),
    "readme_perfis": (
        "ProfilesActionsMixin",
        'o "Aplica a", o "Modo" e a lista do Steam Input',
    ),
    "readme_sistema": (
        "DaemonActionsMixin",
        "o diagnóstico e a resposta a \"o Hefesto está funcionando?\"",
    ),
    "readme_emulacao": (
        "EmulationActionsMixin",
        "o cartão do aparelho, o VID:PID e o do atalho",
    ),
    "readme_navegacao_dsx": (
        "InputActionsMixin",
        "as duas colunas e a legenda de atalhos em português",
    ),
    "readme_configuracoes": (
        "ConfigActionsMixin",
        "as cinco seções da aba Configurações",
    ),
}


def _arvore() -> ast.Module:
    return ast.parse(_RETRATO.read_text(encoding="utf-8"))


def _nomes_da_documentacao() -> tuple[str, ...]:
    """Os valores literais de `NOMES`, lidos por AST — sem importar o script.

    Nunca importa `retratar_abas.py` (que puxa `gi`): este arquivo mede o
    TEXTO-FONTE, e a régua de Z0-2 (`test_toda_aba_de_nomes_tem_mixin_declarado`)
    não pode depender de GTK estar instalado para rodar.
    """
    for no in ast.walk(_arvore()):
        if not isinstance(no, ast.Assign):
            continue
        if not any(isinstance(t, ast.Name) and t.id == "NOMES" for t in no.targets):
            continue
        valor = no.value
        assert isinstance(valor, ast.Tuple), "`NOMES` deixou de ser uma tupla literal"
        return tuple(
            elt.value
            for elt in valor.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        )
    raise AssertionError("`NOMES` sumiu do `retratar_abas.py`")


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
    mixins_declarados = {mixin for mixin, _perda in MIXINS_DE_ABA.values()}
    faltando = {
        mixin: perda
        for aba, (mixin, perda) in MIXINS_DE_ABA.items()
        if mixin not in citados
    }
    assert not faltando, (
        "o retrato deixou de usar o método de produção destas abas: "
        + "; ".join(f"{m} (a foto perde {p})" for m, p in faltando.items())
        + ". Montar à mão faz a foto mentir sobre o layout, e é olhando a foto "
        "que ela decide."
    )
    assert mixins_declarados, "MIXINS_DE_ABA ficou vazio — a régua parou de medir"


def test_toda_aba_de_nomes_tem_mixin_declarado() -> None:
    """O portão novo do aceite da Z0-01: `NOMES` sem linha em `MIXINS_DE_ABA`.

    Até 24/08/2026 a lista cobria 3 das 11 abas (§2.2/M2 da sprint Z0-01) —
    Início, Status e No jogo ficavam sem régua nenhuma, e nada acusava.

    Mordida: tire `HomeActionsMixin` (ou a linha `readme_inicio`) da lista e
    este teste reprova nomeando `readme_inicio`.
    """
    nomes = _nomes_da_documentacao()
    assert nomes, "`NOMES` saiu vazio — nada para conferir"
    sem_regua = [nome for nome in nomes if nome not in MIXINS_DE_ABA]
    assert not sem_regua, (
        "estas abas de `NOMES` não têm linha em `MIXINS_DE_ABA`, e por isso "
        "podem perder o host de produção sem que nada acuse: "
        + ", ".join(sem_regua)
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
        daemon_actions,
        emulation_actions,
        home_actions,
        input_actions,
        lightbar_actions,
        profiles_actions,
        rumble_actions,
        status_actions,
        triggers_actions,
    )
    from hefesto_dualsense4unix.app.actions import config as config_pkg

    vivos = set()
    for modulo in (
        triggers_actions,
        profiles_actions,
        config_pkg,
        home_actions,
        status_actions,
        lightbar_actions,
        rumble_actions,
        daemon_actions,
        emulation_actions,
        input_actions,
    ):
        vivos.update(
            nome
            for nome, obj in vars(modulo).items()
            if inspect.isclass(obj) and nome.endswith("Mixin")
        )

    mixins_declarados = {mixin for mixin, _perda in MIXINS_DE_ABA.values()}
    fantasmas = mixins_declarados - vivos
    assert not fantasmas, (
        f"a lista deste portão nomeia mixin que não existe no produto: "
        f"{sorted(fantasmas)}. Régua que aponta para o vazio aprova qualquer coisa."
    )
