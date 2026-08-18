"""GATILHO-PALAVRA-01/E2: o portão que faltava nos rótulos dos gatilhos.

Nada na suíte cobrava as duas regras medidas na sprint
`docs/process/sprints/2026-07-29-GATILHO-PALAVRA-01-os-dezenove-modos-em-portugues.md`,
e por isso as duas já estavam violadas em produção — "Feedback" era rótulo de
tela e "Personalizado (avançado)" já quebrava a linha no piso da janela.

1. O `name` de cada preset é CHAVE SERIALIZADA, não texto: ele está no perfil
   no disco dela (`triggers.left.mode`, validado contra `PRESET_FACTORIES` em
   `profiles/schema.py:161`), no IPC (comando `trigger.set`) e no protocolo DSX
   (`daemon/udp_server.py`). Trocar um `name` faz `acao.json`, `corrida.json`,
   `esportes.json` e `pragmata.json` pararem de abrir com `ValueError`. Este
   arquivo trava os dezenove nomes, na ordem em que aparecem na tela.

2. O `label` é só texto de tela, e cabe em 22 caracteres. Medido com a grade
   real alocada numa `Gtk.OffscreenWindow` no piso de 1040px
   (`gui/main.glade:321`): o botão tem 157px, sobram 139px de texto, e 22
   caracteres passam onde 23 quebram. Quando um rótulo quebra, a linha da grade
   sai de 32px para 42px e o mínimo da grade sobe de 306px para 357px — que é
   exatamente o mecanismo da barra de rolagem descrito em
   `app/widgets/segmented_selector.py:168-180`, porque o `GtkNotebook` adota o
   maior mínimo entre as páginas.

3. O rótulo não repete o `name` em inglês entre parênteses. Dos cinco que
   repetiam, três já estão só em português; "Bow" e "Weapon" seguem nomeados em
   `PENDENCIA_DE_PALAVRA` porque "Arco" e "Arma" sozinhos não servem.

Não importa `gi` de propósito: tudo aqui é dado puro de `trigger_specs`, então
o portão roda no CI headless sem GTK nenhum.
"""
from __future__ import annotations

from hefesto_dualsense4unix.app.actions.trigger_specs import PRESETS

# Medido no piso de 1040px com a grade de três colunas. Se um dia o piso passar
# a ter quatro colunas, este número tem de ser REMEDIDO, não deduzido.
LIMITE_DE_CARACTERES = 22

# A ordem é a da tela, e o conteúdo é contrato de disco/IPC/DSX.
NOMES_CONTRATADOS = (
    "Off",
    "Rigid",
    "SimpleRigid",
    "Pulse",
    "PulseA",
    "PulseB",
    "Resistance",
    "Bow",
    "Galloping",
    "SemiAutoGun",
    "AutoGun",
    "Machine",
    "Feedback",
    "Weapon",
    "Vibration",
    "SlopeFeedback",
    "MultiPositionFeedback",
    "MultiPositionVibration",
    "Custom",
)

# Rótulo que JÁ estoura o limite e que esta rodada não corta: escolher palavra é
# dela. "Personalizado (avançado)" tem 24 caracteres e quebra a linha no piso; a
# sprint recomenda "Montar do zero" (14), com o aviso "avançado" descendo para a
# descrição. Enquanto ela não decide, a exceção fica AQUI, nomeada e cobrada:
# o teste abaixo reprova tanto se a lista crescer quanto se ela envelhecer (um
# `name` que já cabe não pode continuar dispensado).
PENDENCIA_DE_LARGURA = frozenset({"Custom"})

# "Feedback" é nome da função `feedback()` em `core/trigger_effects.py:203` que
# vazou para a tela: é a única palavra em inglês da grade que não serve para
# achar o modo em guia de jogo nenhum.
PALAVRA_QUE_VAZOU = "Feedback"

# Os cinco `name` que também eram lidos na tela, entre parênteses, ao lado do
# português. O `name` segue em inglês porque é contrato; o rótulo é texto de
# tela e fica na língua dela.
TERMOS_DO_DSX = ("Rigid", "Bow", "Galloping", "Machine", "Weapon")

# Os dois rótulos que seguem repetindo o termo, porque a palavra sozinha não
# serve e escolher a nova é dela: "Arco" é ambíguo em português (arco de
# círculo, arco elétrico) e "Arma" não separa de "Arma automática" nem de "Arma
# semi-automática". A sprint GATILHO-PALAVRA-01 traz três opções para cada um.
PENDENCIA_DE_PALAVRA = frozenset({"Bow", "Weapon"})


def test_os_dezenove_names_sao_exatamente_os_de_hoje() -> None:
    """Contrato: renomear um `name` faz o perfil dela parar de abrir."""
    assert tuple(spec.name for spec in PRESETS) == NOMES_CONTRATADOS


def test_nenhum_rotulo_passa_de_vinte_e_dois_caracteres() -> None:
    """Passar de 22 no piso quebra a linha e sobe o mínimo da grade."""
    estourando = {
        spec.name: (spec.label, len(spec.label))
        for spec in PRESETS
        if spec.name not in PENDENCIA_DE_LARGURA
        and len(spec.label) > LIMITE_DE_CARACTERES
    }
    assert estourando == {}, (
        "rótulo de gatilho quebra a linha no piso de 1040px "
        f"(limite {LIMITE_DE_CARACTERES}): {estourando}"
    )


def test_a_pendencia_de_largura_nao_cresce_nem_envelhece() -> None:
    """A exceção é UMA, conhecida, e cai fora sozinha quando for curada."""
    assert sorted(PENDENCIA_DE_LARGURA) == ["Custom"], (
        "só 'Custom' está dispensado do limite, e por decisão dela pendente; "
        "acrescentar nome aqui é abrir buraco no portão"
    )
    por_nome = {spec.name: spec.label for spec in PRESETS}
    ainda_curtos = {
        nome: por_nome[nome]
        for nome in PENDENCIA_DE_LARGURA
        if nome in por_nome and len(por_nome[nome]) <= LIMITE_DE_CARACTERES
    }
    assert ainda_curtos == {}, (
        "rótulo já cabe no limite: tire o nome de PENDENCIA_DE_LARGURA para o "
        f"portão voltar a cobrá-lo: {ainda_curtos}"
    )


def test_nenhum_rotulo_nem_descricao_de_gatilho_ainda_diz_feedback() -> None:
    """E1: os três rótulos que carregavam a palavra da função interna."""
    culpados = [
        (spec.name, spec.label, spec.description)
        for spec in PRESETS
        if PALAVRA_QUE_VAZOU in spec.label or PALAVRA_QUE_VAZOU in spec.description
    ]
    assert culpados == [], (
        f"'{PALAVRA_QUE_VAZOU}' é nome de função, não texto de tela: {culpados}"
    )


def test_nenhum_rotulo_repete_na_tela_o_nome_do_modo_em_ingles() -> None:
    """Mordida: devolver "(Rigid)", "(Galloping)" ou "(Machine)" ao rótulo reprova.

    O par `name`/`label` tem donos diferentes: o `name` é a chave em inglês e
    fica; o rótulo é a palavra dela. Os dois campos são lidos aqui, e só o
    segundo é cobrado.
    """
    culpados = [
        (spec.name, spec.label, termo)
        for spec in PRESETS
        if spec.name not in PENDENCIA_DE_PALAVRA
        for termo in TERMOS_DO_DSX
        if termo in spec.label or termo in spec.description
    ]
    assert culpados == [], (
        "rótulo de tela carregando o nome do modo em inglês: "
        f"{culpados}. O termo em inglês mora no `name`."
    )


def test_a_pendencia_de_palavra_nao_cresce_nem_envelhece() -> None:
    """A exceção são DUAS, nomeadas, e caem fora sozinhas quando ela decidir."""
    assert sorted(PENDENCIA_DE_PALAVRA) == ["Bow", "Weapon"], (
        "só 'Bow' e 'Weapon' seguem com o termo em inglês no rótulo, à espera "
        "da palavra dela; acrescentar nome aqui é abrir buraco no portão"
    )
    por_nome = {spec.name: spec.label for spec in PRESETS}
    ja_curados = {
        nome: por_nome[nome]
        for nome in PENDENCIA_DE_PALAVRA
        if nome in por_nome
        and not any(termo in por_nome[nome] for termo in TERMOS_DO_DSX)
    }
    assert ja_curados == {}, (
        "o rótulo já está em português: tire o nome de PENDENCIA_DE_PALAVRA "
        f"para o portão voltar a cobrá-lo: {ja_curados}"
    )


def test_cada_um_dos_dezenove_tem_rotulo_e_descricao() -> None:
    """Botão sem texto e itálico vazio são falhas visíveis e silenciosas."""
    vazios = [spec.name for spec in PRESETS if not spec.label.strip()]
    assert vazios == [], f"preset sem rótulo visível: {vazios}"
    sem_descricao = [spec.name for spec in PRESETS if not spec.description.strip()]
    assert sem_descricao == [], f"preset sem a linha em itálico: {sem_descricao}"
