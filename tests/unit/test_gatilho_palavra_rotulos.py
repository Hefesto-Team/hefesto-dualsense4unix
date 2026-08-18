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

   **NOTA DATADA — 07/08/2026, remedido.** O 22 continua sendo o TETO que
   ninguém pode furar, mas deixou de ser garantia de uma linha só. Medido nesta
   árvore, com a fonte +3 que ela aceitou (resposta 8 do painel de 07/08) e com
   os DOIS lados da aba montados, como o produto monta:

   | | medição de 29/07 | remedição de 07/08 |
   |---|---|---|
   | largura do botão no piso | 157px | **152px** |
   | maior rótulo de uma linha | 22 caracteres | **19 caracteres** |
   | rótulos que quebram | 1 (`Custom`) | 3 |

   Os três que quebram na árvore de 07/08 têm **20** caracteres cada: "Arma
   semi-automática", "Vibração por posição" e — depois da decisão dela — "Arco
   de flecha (Bow)". Baixar o limite para 19 reprovaria dois rótulos que ela
   nunca foi convidada a rever e um que ela **acabou de decidir**, então o
   número fica em 22 e a verdade fica escrita aqui.

   Três armadilhas de medição pagas em 07/08, para ninguém repagar:

   - **quebrar é por PALAVRA, não por caractere.** O corte em caracteres é
     proxy: "Disparo (Weapon)" (16) cabe e "Arco de flecha (Bow)" (20) não,
     porque o que estoura é a palavra mais longa, não a contagem;
   - **medir um lado só mente.** Com um `SegmentedSelector` só na aba, o botão
     ganha 212px e NADA quebra — inclusive os 24 caracteres do rótulo antigo;
   - **`apply_theme` compounda.** Ele lê o `gtk-font-name` atual e soma o delta
     (`app/theme.py:154`): duas configurações medidas no mesmo processo não são
     comparáveis, porque a segunda mede uma fonte maior. Uma medição por
     processo. (E o seletor injetado depois do `show_all()` só é alocado depois
     de um `janela.check_resize()`: sem ele mede 1x1, e drenar o laço não
     basta.)

   O que a troca custou em geometria, medido: o mínimo da grade sobe de 332px
   para 348px e o da aba Gatilhos de 602px para 618px — e o mínimo do
   `GtkNotebook` **não se move** (779x1125px antes e depois), porque a página
   mais alta é outra. Nenhuma barra de rolagem nova.

3. O rótulo não repete o `name` em inglês entre parênteses. Dos cinco que
   repetiam, três estão só em português; "Bow" e "Weapon" seguem com o termo,
   agora por DECISÃO DELA de 07/08 ("Arco de flecha (Bow)" e "Disparo
   (Weapon)"), e não mais por pendência.

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

# A isenção `PENDENCIA_DE_LARGURA = {"Custom"}` morava AQUI, e SAIU em
# 07/08/2026. Ela existia por um motivo honesto — "Personalizado (avançado)"
# tinha 24 caracteres, não cabia, e escolher a palavra nova era decisão dela.
# Ela decidiu ("Montar do zero", 14 caracteres, resposta 5 do painel), o rótulo
# passou a caber, e isenção sem motivo é buraco: qualquer rótulo novo do `name`
# `Custom` passaria a se esconder nela sem ninguém notar. Tirar a isenção é
# parte da entrega, e não faxina.

# "Feedback" é nome da função `feedback()` em `core/trigger_effects.py:203` que
# vazou para a tela: é a única palavra em inglês da grade que não serve para
# achar o modo em guia de jogo nenhum.
PALAVRA_QUE_VAZOU = "Feedback"

# Os cinco `name` que também eram lidos na tela, entre parênteses, ao lado do
# português. O `name` segue em inglês porque é contrato; o rótulo é texto de
# tela e fica na língua dela.
TERMOS_DO_DSX = ("Rigid", "Bow", "Galloping", "Machine", "Weapon")

# Os dois rótulos que seguem carregando o termo em inglês. Até 06/08 isso era
# PENDÊNCIA — "Arco" é ambíguo em português (arco de círculo, arco elétrico) e
# "Arma" não separava de "Arma automática" nem de "Arma semi-automática".
#
# NOTA DATADA — 07/08/2026: deixou de ser pendência e virou DECISÃO DELA
# (resposta 6 do painel): "Arco de flecha (Bow)" e "Disparo (Weapon)". O termo
# em inglês FICA nos dois, de propósito, para ela reconhecer o modo num guia de
# jogo em inglês. O nome da constante é preservado porque é o que a sprint e as
# páginas de processo citam; o que mudou é o dono da escolha.
PENDENCIA_DE_PALAVRA = frozenset({"Bow", "Weapon"})


def test_os_dezenove_names_sao_exatamente_os_de_hoje() -> None:
    """Contrato: renomear um `name` faz o perfil dela parar de abrir."""
    assert tuple(spec.name for spec in PRESETS) == NOMES_CONTRATADOS


def test_nenhum_rotulo_passa_de_vinte_e_dois_caracteres() -> None:
    """Passar de 22 no piso quebra a linha e sobe o mínimo da grade.

    SEM ISENÇÃO NENHUMA desde 07/08/2026: os dezenove respondem pelo mesmo
    limite. Devolver "Personalizado (avançado)" (24) ao `Custom` reprova aqui —
    é essa a mordida da decisão dela.
    """
    estourando = {
        spec.name: (spec.label, len(spec.label))
        for spec in PRESETS
        if len(spec.label) > LIMITE_DE_CARACTERES
    }
    assert estourando == {}, (
        "rótulo de gatilho quebra a linha no piso de 1040px "
        f"(limite {LIMITE_DE_CARACTERES}): {estourando}"
    )


def test_nenhum_rotulo_esta_dispensado_do_limite() -> None:
    """A isenção saiu em 07/08, e não pode voltar por dentro deste arquivo.

    Enquanto ela existia, um rótulo novo com o `name` `Custom` herdava a
    dispensa sem que ninguém percebesse. O portão agora conta os dezenove: se
    alguém reintroduzir uma lista de dispensados, a contagem denuncia.
    """
    dispensados = {
        nome for nome in globals() if nome.startswith("PENDENCIA_DE_LARGURA")
    }
    assert dispensados == set(), (
        f"voltou uma isenção de largura: {sorted(dispensados)}. Rótulo que não "
        "cabe é palavra a decidir com ela, não exceção a esconder no teste"
    )
    cabem = [spec for spec in PRESETS if len(spec.label) <= LIMITE_DE_CARACTERES]
    assert len(cabem) == len(NOMES_CONTRATADOS), (
        "os dezenove rótulos têm de passar pelo mesmo limite"
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
    """São DUAS, nomeadas — e desde 07/08 é decisão dela que elas fiquem.

    O portão continua estreito pelo mesmo motivo de antes: acrescentar um nome
    aqui dispensa um rótulo de estar em português sem ninguém decidir nada.
    """
    assert sorted(PENDENCIA_DE_PALAVRA) == ["Bow", "Weapon"], (
        "só 'Bow' e 'Weapon' carregam o termo em inglês no rótulo, por decisão "
        "dela de 07/08; acrescentar nome aqui é abrir buraco no portão"
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
