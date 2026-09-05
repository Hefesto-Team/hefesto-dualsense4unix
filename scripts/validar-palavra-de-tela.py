#!/usr/bin/env python3
"""Portão da palavra de tela: a janela fala a língua de quem joga.

PALAVRA-01 / E5, seção "E5. Um gate, para não voltar" de
`docs/process/sprints/2026-07-27-PALAVRA-01-a-janela-fala-a-lingua-de-quem-joga.md`.
A sprint pede um portão que reprove quando:

- um texto de tela começa com letra minúscula, **com lista de exceções
  explícita e justificada, não implícita** — regra do `.glade`, e só dele;
  o porquê está acima de `DIVIDA_DA_PALAVRA_01_PY`;
- um rótulo visível contém termo da lista de jargão banido — regra dos DOIS
  corpos de texto.

O ALCANCE, declarado: DOIS corpos de texto de tela.

1. o `main.glade`, onde mora o texto DECLARATIVO da janela;
2. o texto de tela MONTADO EM PYTHON em `src/hefesto_dualsense4unix/app/`,
   lido por AST — nunca por expressão regular sobre a linha.

O item 2 entrou em 23/08/2026, e ele é o conserto de um buraco MEDIDO. Até
aqui o portão lia um arquivo só, e o docstring dizia que rótulo montado em
Python ficava de fora "de propósito, porque varrer código produz falso
positivo". A premissa era verdadeira e a conclusão parou de ser no dia em que
uma aba inteira nasceu em código: a aba Configurações tem 4.605 linhas de
Python com CEM POR CENTO do texto de tela fora do XML. Medido nesta árvore:
o portão via 212 rótulos do `.glade` e ZERO de `app/`, e havia CINCO rótulos
com jargão banido em `app/` com o portão verde — entre eles um literal
`"Daemon offline"` (`compact_window.py`), que é a palavra que a E3 da
PALAVRA-01 aposentou primeiro.

COMO O FALSO POSITIVO É EVITADO, e esta é a regra que decide se o portão
sobrevive. A pergunta "esta string aparece na tela?" NÃO é respondida pela
forma da string, nem pelo nome da variável, nem por estar em MAIÚSCULA. É
respondida por FLUXO: uma string é texto de tela quando ela CHEGA A UM
ESCOADOURO DE TELA — argumento de `set_label`/`set_text`/`set_markup`/
`set_tooltip_text`/`set_title`/`add_button`, de `_()` (gettext), de um
construtor de widget com texto (`Gtk.Label(label=...)`), ou de um dos ajudantes
de tela desta casa (`moldura_de_secao`, `rotulo_de_apoio`), ou de um dos
ajudantes de TOAST (`_toast_profile`, `_status_toast`, ...).

O TOAST entrou em 26/08/2026 (BG-TOAST-02), e ele conserta outra fresta medida.
O toast é a ÚNICA frase que a pessoa lê depois de clicar, e era o único pedaço
da tela sem régua: nenhum dos treze nomes de `ESCOADOUROS` continha "toast", e
das 170 chamadas de toast de `app/` havia 163 carregando texto que régua nenhuma
lia. Foi por essa fresta que `"Falha (daemon offline?)"` sobreviveu num toast
com o portão verde, dias depois de o mesmo termo ser banido no rótulo. Ligar
`ESCOADOUROS_DE_RECIBO` levou o alcance de `app/` de 344 rótulos (288 únicos)
para 420 (363).

Consequência, e é ela que mantém o portão calado sobre o que não é tela:
chave de dicionário, id de widget, nome de sinal, valor de enum, caminho de
`/dev`, nome de variável e mensagem de log NÃO chegam a escoadouro nenhum, e o
portão nunca os vê. `MODE_DESKTOP = "desktop"`, `UINPUT_DEV = "/dev/uinput"` e
`TRAY_APP_ID = "hefesto-dualsense4unix"` moram em `app/` e são invisíveis para
ele — de graça, sem lista de exceção.

Duas afinações que a medição pediu, cada uma matando uma família de falso
positivo que a primeira versão da regra produziu:

- **a posição do argumento importa**. `add_button("Fechar", Gtk.ResponseType.CLOSE)`
  só tem texto de tela na posição 0. Sem esse corte, `ResponseType.CANCEL` e
  `ResponseType.OK` entravam como "nome alimentado por escoadouro" e
  promoviam a texto de tela toda constante chamada `CANCEL` ou `OK` da árvore;
- **`new` genérico NÃO é escoadouro**. `indicator_cls.new(TRAY_APP_ID, ...)` do
  ícone de bandeja parecia construtor de widget e arrastava o id do aplicativo
  para dentro do portão. Só `new_with_label` e `new_with_mnemonic` entram.

A CONSTANTE QUE ATRAVESSA MÓDULO. A aba Configurações declara o título e a dica
de cada seção como constante de módulo (`TITULO`, `DICA`) e quem monta lê por
atributo (`moldura_de_secao(secao.TITULO, secao.DICA)`, `config/mixin.py:46`).
O portão aprende esses nomes do próprio código, e não de uma lista escrita à
mão: ele varre o corpo inteiro de `app/` atrás de `alguma_coisa.NOME` em
posição de texto de tela, e daí em diante toda constante de módulo com esse
nome conta como texto de tela. Hoje isso resolve para exatamente dois nomes —
`TITULO` e `DICA` — e é o contrato que `config/secoes.py:23` já escrevia em
comentário.

POR QUE ELE NASCE COM DÍVIDA DECLARADA. A sprint previa que o portão entrasse
JUNTO com a troca dos 24 rótulos (E1 a E4). A troca não veio: MEDIDO em
13/08/2026 nesta árvore, quatro rótulos ainda carregam jargão da tabela E3, e
os três `window_class:` / `title_regex:` / `process_name:` ainda começam em
minúscula. Havia duas saídas ruins e uma boa:

- nascer VERMELHO e derrubar o CI por um trabalho de redação que é dela: não;
- nascer com a lista de jargão vazia, "para não incomodar": isso é decoração
  com nome de portão, e é o defeito-mãe desta casa (PORTÃO-VIVO-01);
- nascer com cada sobrevivente ESCRITO, um a um, com o que ele vira e por que
  ainda não virou. É esta.

A dívida declarada não envelhece calada: se um rótulo declarado aqui sumir ou
mudar, o portão reprova pedindo que a entrada seja APAGADA. E o portão morde
onde a sprint pediu que ele mordesse — "reintroduzir `daemon offline` num
rótulo tem de reprovar de novo": um rótulo NOVO com jargão não está em lista
nenhuma, e reprova.

Uso:
    scripts/validar-palavra-de-tela.py --all
    scripts/validar-palavra-de-tela.py --check-file caminho/arquivo.glade
    scripts/validar-palavra-de-tela.py --mostrar-criterio

Saída: uma linha por achado, em ``arquivo:linha: motivo``. Código de saída 0 se
limpo, 1 se houver achado.

LACUNAS CONHECIDAS (23/08/2026), escritas para não serem confundidas com
cobertura:

- **texto que só existe em tempo de execução** não é varrido. O portão é
  estático: ele lê literal e constante de módulo. Rótulo que sai de uma tabela
  de dados, de um perfil ou de um `f"{...}"` sem parte literal fica fora. Quem
  cobre esse caso é o portão IRMÃO, de widget montado
  (`tests/unit/test_config_a_palavra_de_tela_da_aba_montada.py`), que monta a
  aba de verdade e anda a árvore — com o limite próprio dele, medido em
  22/08/2026: alcança 175 textos / 101 únicos e LÊ O BARRAMENTO REAL da
  máquina, então num CI sem adaptador o alcance dele encolhe sozinho. Os dois
  se somam, e nenhum substitui o outro;
- **`app/` é o alcance, não `src/` inteiro.** O texto de tela desta casa mora
  em `app/`; `core/`, `integrations/` e `cli/` não falam com a janela;
- os catálogos de tradução (`po/`) não são varridos;
- a maiúscula é conferida no primeiro caractere do rótulo, não frase a frase
  dentro dele.
"""
from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterator
from pathlib import Path
from xml.parsers import expat

RAIZ = Path(__file__).resolve().parents[1]
GLADE = RAIZ / "src" / "hefesto_dualsense4unix" / "gui" / "main.glade"
#: Onde mora o texto de tela montado em Python. Ver "O ALCANCE" no topo:
#: `core/`, `integrations/` e `cli/` não falam com a janela.
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"

#: As propriedades do Glade que viram texto NA TELA. `label` é o grosso; as
#: outras três entram porque a pessoa lê as quatro do mesmo jeito.
PROPRIEDADES_DE_TELA = frozenset({"label", "title", "text", "tooltip_text"})

#: Rótulo que PODE começar em minúscula, com a justificativa ao lado. Explícita
#: e linha a linha, como a E5 exige — uma lista de exceções sem motivo escrito
#: vira o armário onde se guarda o que incomoda.
EXCECOES_DE_MINUSCULA: dict[str, str] = {
    "window_class:": (
        "13/08/2026 — é o nome LITERAL da chave de perfil que a pessoa digita "
        "no campo ao lado, e trocá-lo por `Janela:` (o que a E3 da PALAVRA-01 "
        "propõe) é redação de tela, que é decisão dela e não deste portão."
    ),
    "title_regex:": (
        "13/08/2026 — mesma razão de `window_class:`: chave literal de perfil. "
        "A E3 da PALAVRA-01 propõe `Título:`; a troca é dela."
    ),
    "process_name:": (
        "13/08/2026 — mesma razão de `window_class:`: chave literal de perfil. "
        "A E3 da PALAVRA-01 propõe `Programa:`; a troca é dela."
    ),
}

#: O jargão que a E3 da PALAVRA-01 aposentou, e o que ele vira. A chave é
#: comparada sem diferenciar maiúscula de minúscula.
JARGAO_BANIDO: dict[str, str] = {
    "daemon offline": "O Hefesto está desligado",
    "daemon pausado": "O Hefesto está em pausa",
    "uinput disponível": "Pronto para usar como mouse",
    "Restaurar Default": "Voltar ao padrão",
    "Travar Proton validado": "Fixar a versão que funciona",
    "Aplicar correções": "Consertar problemas conhecidos",
    "Testar criação de device virtual": "Testar o controle virtual",
    "Gamepads:": "Controles detectados:",
    # CONFIGURAÇÕES-O-LÉXICO-01 / LEX-10, dente 2 (25/08/2026). A aba
    # Configurações fala a língua do barramento com quem enxerga um gabinete e
    # um número de entrada. Ela: *"vizinhança das portas, qual porta?"*.
    #
    # ENTRAM SEM DÍVIDA, e a medição é o que autoriza: `devpath` e `vid:pid` não
    # são texto de tela em lugar nenhum desta árvore hoje — aparecem só em
    # docstring e comentário, e o `_texto_reconstruido` remonta
    # `f"Barramento {n}, porta {devpath}"` como `"Barramento {}, porta {}"`, sem
    # a palavra. São, portanto, proibição PREVENTIVA de custo zero: nada fica
    # vermelho, e a próxima frase que tentar pôr o identificador do fabricante
    # na tela reprova.
    "devpath": "diga a entrada USB: 'Entrada 4 do hub'",
    "vid:pid": "o código do fabricante não é palavra de tela — põe na dica",
    # ORDEM DELA, 05/09/2026, e ela veio em duas partes porque a primeira foi
    # cumprida pela metade. Primeiro: *"não é pra ter mesa em nada da
    # interface"*. A leva daquele dia separou dois sentidos e tirou só um — o
    # jargão desta casa, "mesa" = o conjunto de controles ligados — e deixou o
    # outro de pé, "mesa" = a escrivaninha dela, por achar que ali a palavra era
    # a coisa. Então ela corrigiu: *"muda o termo pra objeto e sinônimos nesses
    # casos"*.
    #
    # ENTRA SEM DÍVIDA NENHUMA, e é a medição que autoriza: no dia em que esta
    # linha foi escrita, as DUAS últimas frases de tela do `app/` que diziam a
    # palavra saíram no MESMO commit — `secao_mesa.py:711` ("Reexaminar a mesa"
    # -> "Reexaminar as conexões") e `secao_orcamento.DICA` ("na mesa inteira"
    # -> "em todos os controles"). É exatamente o que a nota do
    # `_A_PALAVRA_QUE_ESPERA_A_LEX_6` logo abaixo manda fazer: colar a linha no
    # commit que troca a última frase, nunca antes.
    #
    # O QUE ELA NÃO ALCANÇA, e por isso há uma segunda régua: este portão lê o
    # `.glade` e o `app/**/*.py` por AST. O texto da interface nova nasce em
    # `interface/abaNN.py` e, pior, em `<script>` que escreve no DOM em tempo de
    # execução — três origens que nenhuma leitura de fonte junta. Quem mede
    # aquele lado é `tests/unit/test_a_palavra_mesa_nao_volta_para_a_tela.py`,
    # que RODA as páginas e lê o DOM. Duas réguas independentes é regra desta
    # casa, e aqui elas nem se sobrepõem: cada uma alcança o que a outra não vê.
    "mesa": "o termo é 'objeto' ou o sinônimo que couber: escrivaninha, arranjo, "
            "'os controles ligados'",
}

#: A TERCEIRA ENTRADA DESTA LISTA AINDA NÃO ESTÁ AQUI, E A AUSÊNCIA É MEDIDA.
#:
#: A LEX-10 pede também::
#:
#:     "barramento": "diga a entrada USB: 'Entrada 4 do hub'",
#:
#: Ela NÃO entra hoje porque cinco frases de tela de
#: `app/actions/config/secao_mesa.py` ainda dizem a palavra — a dica do selo
#: `(lido)` (`:193`), a tabela vazia (`:949`), a dica do hub, a das duas
#: perguntas de rádio (`:486`) e a coluna "Onde está" (`:1604`). Elas saem nas
#: LEX-6 e LEX-11, que moram naquele arquivo, e ele é de outra frente desta leva
#: (R1: quem edita arquivo alheio desfaz o vizinho em silêncio).
#:
#: Pôr a palavra na lista antes da troca deixaria DOIS portões vermelhos — este
#: e o `test_config_a_palavra_de_tela_da_aba_montada.py`, que importa esta lista
#: — e a única saída seria declarar cinco dívidas que nascem para ser apagadas
#: na semana seguinte. Lista de dívida que nasce cheia vira paisagem, e este
#: portão já pagou essa lição em 13/08.
#:
#: **A linha acima é para colar em `JARGAO_BANIDO` no MESMO commit que trocar a
#: última das cinco frases.** Colada antes, ela reprova; colada depois, ela é o
#: que impede a palavra de voltar.
_A_PALAVRA_QUE_ESPERA_A_LEX_6 = "barramento"

#: Os rótulos que AINDA carregam jargão nesta árvore, um a um. Não é perdão: é
#: a dívida da E1-E4 escrita com nome e endereço, para que o portão possa
#: entrar sem derrubar o CI por um trabalho de redação que não é dele. Some
#: daqui no commit que trocar o rótulo — e o portão reprova se alguém esquecer
#: de apagar a entrada.
#:
#: **A LISTA ESTÁ VAZIA DESDE 26/08/2026** (BG-PALAVRA-02), e a vazia vale mais
#: que a cheia: as cinco entradas que moravam aqui — `Aplicar correções`,
#: `Travar Proton validado`, `Gamepads:`, `Restaurar Default` e `VID:PID:` —
#: saíram no commit que trocou os cinco rótulos, que é o que a própria tabela
#: mandava. O `dict` fica de pé porque o mecanismo continua valendo: o próximo
#: rótulo que nascer com jargão declara a dívida aqui ou reprova.
#:
#: CORREÇÃO DE FATO, junto: a entrada de `VID:PID:` dizia que o rótulo morava na
#: aba **Sistema**. Morava na **Emulação** — as etiquetas de aba do
#: `gui/main.glade` são `Sistema` e `Emulação`, e o rótulo ficava dentro do
#: cartão de diagnóstico da segunda, ao lado do `Controles detectados:`. Quem
#: fosse conferir o conserto pela aba errada não o acharia.
DIVIDA_DA_PALAVRA_01: dict[str, str] = {}


class Rotulo:
    """Um texto de tela, com onde ele mora."""

    def __init__(self, arquivo: Path, linha: int, propriedade: str, texto: str) -> None:
        self.arquivo = arquivo
        self.linha = linha
        self.propriedade = propriedade
        self.texto = " ".join(texto.split())

    def __repr__(self) -> str:  # pragma: no cover - conveniência de depuração
        return f"Rotulo({self.arquivo.name}:{self.linha} {self.texto!r})"


def rotulos_do_glade(caminho: Path) -> list[Rotulo]:
    """Todo texto de tela do arquivo, com a linha em que ele começa.

    O `expat` é usado em vez de expressão regular por dois motivos concretos: a
    propriedade pode ocupar várias linhas, e o valor chega com as entidades XML
    já desfeitas (`&amp;` vira `&`) — que é o texto que a pessoa lê de fato.
    """
    achados: list[Rotulo] = []
    aberta: dict[str, object] = {"nome": "", "linha": 0, "pedacos": []}

    def abriu(nome: str, atributos: dict[str, str]) -> None:
        if nome == "property" and atributos.get("name") in PROPRIEDADES_DE_TELA:
            aberta["nome"] = atributos["name"]
            aberta["linha"] = analisador.CurrentLineNumber
            aberta["pedacos"] = []

    def texto(dados: str) -> None:
        if aberta["nome"]:
            aberta["pedacos"].append(dados)  # type: ignore[union-attr]

    def fechou(nome: str) -> None:
        if nome == "property" and aberta["nome"]:
            achados.append(
                Rotulo(
                    caminho,
                    int(aberta["linha"]),  # type: ignore[call-overload]
                    str(aberta["nome"]),
                    "".join(aberta["pedacos"]),  # type: ignore[arg-type]
                )
            )
            aberta["nome"] = ""

    analisador = expat.ParserCreate()
    analisador.StartElementHandler = abriu
    analisador.CharacterDataHandler = texto
    analisador.EndElementHandler = fechou
    analisador.Parse(caminho.read_bytes(), True)
    return achados


def comeca_em_minuscula(texto: str) -> bool:
    """O rótulo abre com letra minúscula?

    Marcação Pango (`<i>`, `<b>`) e pontuação não contam como primeira letra —
    o que interessa é a primeira LETRA que a pessoa lê.
    """
    sem_marcacao = texto
    while sem_marcacao.startswith("<") and ">" in sem_marcacao:
        sem_marcacao = sem_marcacao[sem_marcacao.index(">") + 1 :].lstrip()
    for caractere in sem_marcacao:
        if caractere.isalpha():
            return caractere.islower()
    return False


def jargao_em(texto: str) -> str | None:
    """O primeiro termo banido que aparece no rótulo, ou None."""
    achatado = texto.lower()
    for termo in JARGAO_BANIDO:
        if termo.lower() in achatado:
            return termo
    return None


def conferir(caminho: Path) -> list[str]:
    """As reprovações do arquivo, em ordem de linha."""
    if not caminho.is_file():
        return [f"{caminho}: arquivo de interface não encontrado"]

    achados: list[str] = []
    rotulos = rotulos_do_glade(caminho)

    for rotulo in rotulos:
        if not rotulo.texto:
            continue

        if comeca_em_minuscula(rotulo.texto) and rotulo.texto not in EXCECOES_DE_MINUSCULA:
            achados.append(
                f"{rotulo.arquivo}:{rotulo.linha}: o rótulo "
                f"{rotulo.texto!r} ({rotulo.propriedade}) começa em "
                "minúscula. A janela fala com quem joga: comece com "
                "maiúscula.\n"
                "    Se for exceção de verdade, declare em "
                "`EXCECOES_DE_MINUSCULA` com a razão e a data — a E5 da "
                "PALAVRA-01 exige lista explícita, não implícita."
            )

        termo = jargao_em(rotulo.texto)
        if termo is not None and rotulo.texto not in DIVIDA_DA_PALAVRA_01:
            achados.append(
                f"{rotulo.arquivo}:{rotulo.linha}: o rótulo "
                f"{rotulo.texto!r} ({rotulo.propriedade}) contém o jargão "
                f"{termo!r}, aposentado pela E3 da PALAVRA-01.\n"
                f"    Diga {JARGAO_BANIDO[termo]!r}. Quem joga não é "
                "obrigado a saber o que é um daemon."
            )

    presentes = {rotulo.texto for rotulo in rotulos}
    for rotulo_declarado in EXCECOES_DE_MINUSCULA:
        if rotulo_declarado not in presentes:
            achados.append(
                f"{caminho}: a exceção de minúscula {rotulo_declarado!r} não "
                "existe mais nesta tela. APAGUE a entrada de "
                "`EXCECOES_DE_MINUSCULA` — lista de exceção que envelhece "
                "calada vira paisagem."
            )
    for rotulo_declarado in DIVIDA_DA_PALAVRA_01:
        if rotulo_declarado not in presentes:
            achados.append(
                f"{caminho}: a dívida {rotulo_declarado!r} não existe mais "
                "nesta tela — o rótulo foi trocado, e é uma boa notícia. "
                "APAGUE a entrada de `DIVIDA_DA_PALAVRA_01`."
            )

    return achados


#: POR QUE A REGRA DA MAIÚSCULA NÃO ATRAVESSA PARA `app/`, e ela é a decisão
#: mais importante desta extensão. MEDIDO em 23/08/2026, com a regra ligada
#: sobre os 347 textos de tela de `app/`: **49 reprovações, nenhum defeito.**
#:
#: No `.glade`, `<property name="label">` é sempre um rótulo INTEIRO, e
#: "começa em maiúscula?" tem resposta. Em Python o mesmo escoadouro recebe
#: PEDAÇO, e o portão estático não tem como saber qual é qual:
#:
#: * marcação em volta de um valor de execução — `<span foreground="{}">{}</span>`,
#:   32 das 49. A primeira letra que existe no literal é o `s` de `span`;
#: * contagem — `"{n} controles"`, `"1 externo"`, `"{n} do Hefesto + {ext}"`;
#: * sufixo entre parênteses — `"{} (padrão)"`, `"{} (cópia)"`, `"(nenhum perfil)"`;
#: * oração colada depois de um marcador — `"· %(n)d controles (%(t)s)"`.
#:
#: A pergunta só é respondível depois que os pedaços viram UM rótulo, e aí ela
#: já tem dono: `tests/unit/test_config_a_palavra_de_tela_da_aba_montada.py`
#: monta a aba de verdade e confere a maiúscula no texto COMPOSTO. Dois
#: instrumentos, cada um medindo o que sabe medir — a lição de
#: `portoes-em-serie-enganam` (19/08/2026).
#:
#: O jargão é diferente, e por isso ele atravessa: `"daemon"` dentro de um
#: pedaço continua sendo `"daemon"` na tela, componha-se como se componha.

#: O jargão que sobreviveu em `app/`, um a um, MEDIDO em 23/08/2026 — a
#: primeira varredura de Python que este portão fez. Não é perdão: é a mesma
#: dívida da E1-E4, agora com o endereço em código. Some daqui no commit que
#: trocar a frase, e o portão reprova se alguém esquecer de apagar a entrada.
#:
#: As duas primeiras são jargão PURO, e o conserto é redação de tela — decisão
#: dela, como a E3 da PALAVRA-01 sempre foi. A terceira CITA um rótulo do
#: `.glade`: ela tem de mudar no mesmo commit que o botão, senão a frase manda
#: clicar num botão que não existe mais.
#:
#: 26/08/2026 (BG-NAV-01): as DUAS entradas de `mouse_actions.py` saíram daqui.
#: Elas mandavam clicar em "Aplicar correções" para um defeito de `uinput`, e
#: aquele botão não toca no `uinput` — o ponteiro estava errado no ALVO, não só
#: no nome. As frases agora dão o gesto de atualizar esta instalação, que é o
#: que a aba Emulação já dizia para a mesma condição.
DIVIDA_DA_PALAVRA_01_PY: dict[str, str] = {
    "Daemon offline": (
        "23/08/2026 — `app/compact_window.py`, o rótulo de estado da janela "
        "compacta. Vira `O Hefesto está desligado`. Jargão puro: a janela "
        "compacta é a que fica na tela durante o jogo, e é a última onde a "
        "palavra `daemon` deveria aparecer."
    ),
    "ERRO ao aplicar perfil (daemon offline?).": (
        "23/08/2026 — `app/actions/footer_actions.py`, o aviso de falha ao "
        "aplicar perfil. Vira `Não consegui aplicar o perfil — o Hefesto pode "
        "estar desligado.`"
    ),
    "Asset 'meu_perfil.json' não encontrado — Restaurar Default indisponível.": (
        "23/08/2026 — `app/actions/footer_actions.py`. CITA o botão "
        "`Restaurar Default`, que é dívida do `.glade`; muda junto com ele."
    ),
}

#: Os ESCOADOUROS DE TELA, e quantas posições iniciais de cada um são texto de
#: tela. O número não é decoração: `add_button("Fechar", ResponseType.CLOSE)`
#: tem texto na posição 0 e um valor de enum na 1, e foi essa distinção que
#: impediu `CANCEL`/`OK` de virarem "nome de constante de tela" (ver o topo).
#:
#: `_` é o gettext desta casa (`utils/i18n`), e é o escoadouro mais denso:
#: 237 chamadas em `app/`.
ESCOADOUROS: dict[str, int] = {
    "set_label": 1,
    "set_text": 1,
    "set_markup": 1,
    "set_tooltip_text": 1,
    "set_tooltip_markup": 1,
    "set_title": 1,
    "set_placeholder_text": 1,
    "add_button": 1,
    "new_with_label": 1,
    "new_with_mnemonic": 1,
    "_": 1,
    # Os dois ajudantes de tela da aba Configurações (`app/actions/config/
    # moldura.py`). `moldura_de_secao(titulo, dica)` tem texto nas DUAS.
    "moldura_de_secao": 2,
    "rotulo_de_apoio": 1,
}

#: O RECIBO DO GESTO — os ajudantes de toast desta casa, com a POSIÇÃO exata do
#: argumento que a pessoa lê. Entrou em 26/08/2026 (BG-TOAST-02), e é o conserto
#: de uma fresta MEDIDA: o toast é a única frase que a pessoa lê depois de
#: clicar, e era o único pedaço da tela sem régua. Nenhum dos treze nomes de
#: `ESCOADOUROS` contém "toast"; das 170 chamadas de toast de `app/`, 163
#: carregavam texto que régua nenhuma lia. Foi por essa fresta que dois toasts
#: continuaram dizendo `daemon offline` — a palavra que a E3 da PALAVRA-01
#: aposentou primeiro — com o portão verde.
#:
#: POR QUE UM DICIONÁRIO DE POSIÇÕES, e não o `int` de `ESCOADOUROS`. O
#: `ESCOADOUROS` conta posições INICIAIS, e o ajudante mais usado desta família
#: não cabe nesse molde: `_status_toast(context, msg)` (`actions/base.py:346`)
#: tem o texto na posição **1** e um id de contexto de statusbar (`"daemon"`,
#: `"footer"`, `"profiles"`) na **0**. Contar duas posições iniciais arrastaria
#: esses ids para dentro do portão — e `"daemon"` é justamente o começo de um
#: termo banido. Cada entrada aqui foi lida na assinatura do ajudante.
#:
#: FICA DE FORA, e a ausência é medida:
#:
#: * `_toast_trigger(side, preset_id, ok, *, motivo=..., spec=..., corpo=...)`
#:   (`triggers_actions.py:700`) — nenhum argumento dele é texto de tela; ele
#:   COMPÕE a frase lá dentro, a partir de `motivo` e do preset. O que sai dali
#:   é texto de execução, e quem alcança isso é o portão de widget montado;
#: * `toast_da_escolha`, `toast_do_relancamento` (`relancar.py`),
#:   `reconciliar_toast`, `toast_da_troca_de_mascara` (`home_actions.py`) — os
#:   quatro DEVOLVEM a frase em vez de mostrá-la. Quem mostra é um `_toast_*`
#:   desta lista, e o que chega lá é uma variável (ver a lacuna do texto de
#:   execução no topo do arquivo).
ESCOADOUROS_DE_RECIBO: dict[str, tuple[int, ...]] = {
    # `actions/base.py` — o funil por onde TODOS os outros passam.
    "_status_toast": (1,),
    "_toast_do_relancar": (0,),
    # Um por aba/área, todos com a mesma assinatura `(msg)`.
    "_carona_toast": (0,),
    "_footer_toast": (0,),
    "_toast_camadas": (0,),
    "_toast_daemon": (0,),
    "_toast_de_gravacao": (0,),
    "_toast_emulation": (0,),
    "_toast_input": (0,),
    "_toast_keyboard": (0,),
    "_toast_light": (0,),
    "_toast_mouse": (0,),
    "_toast_profile": (0,),
    "_toast_rumble": (0,),
}

#: O jargão que sobreviveu DENTRO DE UM TOAST, um a um. Mesmo molde e mesmo
#: contrato de `DIVIDA_DA_PALAVRA_01_PY`: não é perdão, é a dívida com nome e
#: endereço, e o portão reprova se a entrada envelhecer sem ser apagada.
#:
#: **A LISTA NASCE VAZIA, E A MEDIÇÃO É O QUE AUTORIZA ISSO.** Nascer vazia
#: "para não incomodar" é o defeito-mãe desta casa (PORTÃO-VIVO-01), escrito no
#: topo deste arquivo — por isso a lista só pode nascer vazia com o número na
#: mão. Ele está aqui, medido em 26/08/2026 nesta árvore: ligar
#: `ESCOADOUROS_DE_RECIBO` levou o alcance de `app/` de **344 rótulos (288
#: únicos) para 420 (363)** — 75 textos que régua nenhuma lia — e o vermelho
#: novo foi de UM só: `profiles_actions.py:3237`, `"Falha (daemon offline?)"`.
#: Ele foi TROCADO no mesmo commit que ampliou o alcance, e é por isso que não
#: há dívida a declarar. Dívida que nasce quando dá para consertar é dívida
#: escolhida.
#:
#: O `dict` fica de pé porque o mecanismo continua valendo, exatamente como o
#: `DIVIDA_DA_PALAVRA_01` do `.glade`: o próximo toast que nascer com jargão
#: declara a dívida aqui — com o endereço e o que a frase vira — ou reprova.
DIVIDA_DO_RECIBO: dict[str, str] = {}

#: Construtores de widget cujo primeiro argumento — ou o `label=` — é texto de
#: tela. Casados pelo NOME DO ATRIBUTO (`Gtk.Label(...)`), que é como o código
#: desta casa os escreve.
CONSTRUTORES_COM_TEXTO = frozenset(
    {"Label", "Button", "CheckButton", "RadioButton", "MenuItem", "ToggleButton", "LinkButton"}
)

#: Argumentos NOMEADOS que carregam texto de tela. Fora desta lista, um `kwarg`
#: é ignorado — `Gtk.Label(name="x")` é id de CSS, não texto.
NOMEADOS_DE_TELA = frozenset(
    {"label", "text", "title", "tooltip_text", "placeholder_text", "titulo", "dica", "texto"}
)


def _posicoes_do_nome(nome: str) -> tuple[int, ...] | None:
    """As posições de texto de tela deste nome de chamada, ou None.

    Os dois dicionários dizem a mesma coisa em molde diferente: `ESCOADOUROS`
    conta posições INICIAIS (`add_button` tem 1, `moldura_de_secao` tem 2) e
    `ESCOADOUROS_DE_RECIBO` dá o índice exato, porque o funil dos toasts
    (`_status_toast(context, msg)`) tem o texto na segunda.
    """
    if nome in ESCOADOUROS:
        return tuple(range(ESCOADOUROS[nome]))
    return ESCOADOUROS_DE_RECIBO.get(nome)


def _escoadouro_de(no: ast.Call) -> tuple[int, ...] | None:
    """Que posições desta chamada são texto de tela, ou None.

    None significa "esta chamada não põe nada na tela" — que é o veredito para
    a esmagadora maioria das chamadas de `app/`, e é por isso que o portão fica
    calado sobre chave de dicionário, nome de sinal e mensagem de log.
    """
    alvo = no.func
    if isinstance(alvo, ast.Name):
        return _posicoes_do_nome(alvo.id)
    if isinstance(alvo, ast.Attribute):
        posicoes = _posicoes_do_nome(alvo.attr)
        if posicoes is not None:
            return posicoes
        if alvo.attr in CONSTRUTORES_COM_TEXTO:
            return (0,)
    return None


def _argumentos_de_tela(no: ast.Call, posicoes: tuple[int, ...]) -> Iterator[ast.expr]:
    """Só o que ocupa posição de texto de tela nesta chamada."""
    for indice in posicoes:
        if indice < len(no.args):
            yield no.args[indice]
    for nomeado in no.keywords:
        if nomeado.arg in NOMEADOS_DE_TELA:
            yield nomeado.value


#: O que ocupa, no texto reconstruído, o lugar de um pedaço que só existe em
#: tempo de execução. Ele PRECISA ser visível: uma f-string remontada sem marca
#: no buraco vira uma frase que ninguém escreveu — `f"{n} controles"` viraria
#: `" controles"`, e o portão reprovaria por minúscula um texto que na tela
#: começa com um número.
BURACO = "{}"


def _texto_reconstruido(no: ast.expr) -> str | None:
    """A expressão remontada como a pessoa a lê, ou None se não for texto.

    A f-string e a soma de literais são remontadas em UMA frase, com `{}` no
    lugar de cada pedaço calculado. Isso não é detalhe de implementação: a
    primeira versão desta função devolvia os pedaços SOLTOS, e o portão nasceu
    com 35 reprovações — 12 delas contra fragmentos como `'<span foreground="'`
    e `'%</span>'`, que são metade de uma marcação Pango partida ao meio por um
    `{cor}`. Nenhuma delas era texto de tela; todas eram a régua quebrando o
    texto no lugar errado.

    Uma chamada aninhada vira `{}` do mesmo jeito: quem a visita é o
    `ast.walk`, e contar o conteúdo dela aqui também duplicaria o achado.
    """
    if isinstance(no, ast.Constant):
        return no.value if isinstance(no.value, str) else None
    if isinstance(no, ast.JoinedStr):
        pedacos: list[str] = []
        for pedaco in no.values:
            if isinstance(pedaco, ast.Constant) and isinstance(pedaco.value, str):
                pedacos.append(pedaco.value)
            else:
                pedacos.append(BURACO)
        return "".join(pedacos)
    if isinstance(no, ast.BinOp) and isinstance(no.op, ast.Add):
        esquerda = _texto_reconstruido(no.left)
        direita = _texto_reconstruido(no.right)
        if esquerda is None and direita is None:
            return None
        return (esquerda or BURACO) + (direita or BURACO)
    return None


def _literais(no: ast.expr) -> list[str]:
    """O texto de tela desta expressão — zero ou um, já remontado."""
    texto = _texto_reconstruido(no)
    if texto is None:
        return []
    return [texto] if texto.replace(BURACO, "").strip() else []


def arquivos_de_python(raiz: Path = APP) -> list[Path]:
    """Os módulos de `app/`, em ordem estável."""
    return [caminho for caminho in sorted(raiz.rglob("*.py")) if "__pycache__" not in caminho.parts]


def nomes_de_constante_de_tela(arvores: dict[Path, ast.Module]) -> set[str]:
    """Os nomes de constante que ATRAVESSAM módulo até um escoadouro.

    O portão não adivinha por nome nem por MAIÚSCULA: ele procura
    `alguma_coisa.NOME` em posição de texto de tela — hoje, o
    `moldura_de_secao(secao.TITULO, secao.DICA)` de `config/mixin.py:46` — e é
    daí que sai a lista. Se a aba Configurações rebatizar o contrato, o portão
    acompanha sozinho.
    """
    nomes: set[str] = set()
    for arvore in arvores.values():
        for no in ast.walk(arvore):
            if not isinstance(no, ast.Call):
                continue
            posicoes = _escoadouro_de(no)
            if posicoes is None:
                continue
            for argumento in _argumentos_de_tela(no, posicoes):
                if isinstance(argumento, ast.Attribute) and argumento.attr.isupper():
                    nomes.add(argumento.attr)
    return nomes


def _constantes_de_modulo(arvore: ast.Module) -> dict[str, tuple[list[str], int]]:
    """As atribuições de nível de módulo que são texto literal."""
    constantes: dict[str, tuple[list[str], int]] = {}
    for no in arvore.body:
        nome: str | None = None
        if isinstance(no, ast.Assign) and len(no.targets) == 1:
            if isinstance(no.targets[0], ast.Name):
                nome = no.targets[0].id
        elif isinstance(no, ast.AnnAssign) and isinstance(no.target, ast.Name):
            nome = no.target.id
        if nome is None or no.value is None:
            continue
        valor = no.value
        # `TITULO = _("Está tudo certo?")` conta como o texto de dentro.
        if isinstance(valor, ast.Call):
            posicoes = _escoadouro_de(valor)
            textos = (
                [t for arg in _argumentos_de_tela(valor, posicoes) for t in _literais(arg)]
                if posicoes is not None
                else []
            )
        else:
            textos = _literais(valor)
        if textos:
            constantes[nome] = (textos, no.lineno)
    return constantes


def rotulos_do_python(caminho: Path, nomes_de_tela: set[str]) -> list[Rotulo]:
    """Todo texto de tela ESTÁTICO do módulo, com a linha em que ele mora.

    Duas fontes, e nenhuma delas é o nome da variável:

    1. literal em posição de texto de tela numa chamada de escoadouro;
    2. constante de módulo que CHEGA a um escoadouro — no próprio arquivo, ou
       por atributo a partir de outro (`nomes_de_tela`).
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"))
    constantes = _constantes_de_modulo(arvore)
    achados: list[Rotulo] = []
    usadas: set[str] = {nome for nome in constantes if nome in nomes_de_tela}

    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        posicoes = _escoadouro_de(no)
        if posicoes is None:
            continue
        for argumento in _argumentos_de_tela(no, posicoes):
            for texto in _literais(argumento):
                if texto.strip():
                    achados.append(Rotulo(caminho, argumento.lineno, "texto de tela", texto))
            if isinstance(argumento, ast.Name) and argumento.id in constantes:
                usadas.add(argumento.id)

    for nome in sorted(usadas):
        textos, linha = constantes[nome]
        for texto in textos:
            if texto.strip():
                achados.append(Rotulo(caminho, linha, f"constante {nome}", texto))

    achados.sort(key=lambda rotulo: rotulo.linha)
    return achados


def conferir_python(caminho: Path, nomes_de_tela: set[str]) -> list[str]:
    """As reprovações de um módulo de `app/`, em ordem de linha."""
    if not caminho.is_file():
        return [f"{caminho}: módulo de interface não encontrado"]

    achados: list[str] = []
    for rotulo in rotulos_do_python(caminho, nomes_de_tela):
        # Só a regra do jargão. A da maiúscula fica de fora, e o porquê está
        # escrito acima de `DIVIDA_DA_PALAVRA_01_PY`: 49 reprovações, nenhum
        # defeito.
        termo = jargao_em(rotulo.texto)
        perdoado = rotulo.texto in DIVIDA_DA_PALAVRA_01_PY or rotulo.texto in DIVIDA_DO_RECIBO
        if termo is not None and not perdoado:
            achados.append(
                f"{rotulo.arquivo}:{rotulo.linha}: o texto de tela "
                f"{rotulo.texto!r} ({rotulo.propriedade}) contém o jargão "
                f"{termo!r}, aposentado pela E3 da PALAVRA-01.\n"
                f"    Diga {JARGAO_BANIDO[termo]!r}. Quem joga não é "
                "obrigado a saber o que é um daemon."
            )
    return achados


def conferir_app(raiz: Path = APP) -> list[str]:
    """A varredura inteira de `app/`, com a checagem de lista envelhecida.

    A pergunta "esta exceção ainda existe?" só tem resposta com o corpo INTEIRO
    na mão — por isso ela mora aqui, e não em `conferir_python`, que também é
    chamado com um arquivo só.
    """
    arquivos = arquivos_de_python(raiz)
    arvores = {
        caminho: ast.parse(caminho.read_text(encoding="utf-8")) for caminho in arquivos
    }
    nomes_de_tela = nomes_de_constante_de_tela(arvores)

    achados: list[str] = []
    presentes: set[str] = set()
    for caminho in arquivos:
        achados.extend(conferir_python(caminho, nomes_de_tela))
        presentes.update(rotulo.texto for rotulo in rotulos_do_python(caminho, nomes_de_tela))

    for lista, nome_da_lista in (
        (DIVIDA_DA_PALAVRA_01_PY, "DIVIDA_DA_PALAVRA_01_PY"),
        (DIVIDA_DO_RECIBO, "DIVIDA_DO_RECIBO"),
    ):
        for declarado in lista:
            if declarado not in presentes:
                achados.append(
                    f"{raiz}: a dívida {declarado!r} não existe mais em `app/` "
                    "— a frase foi trocada, e é uma boa notícia. APAGUE a "
                    f"entrada de `{nome_da_lista}`."
                )
    return achados


def mostrar_criterio() -> None:
    """Imprime o critério, para quem quiser conferir sem ler o código."""
    print("Portão da palavra de tela (PALAVRA-01 / E5)")
    print(f"  XML varrido: {GLADE.relative_to(RAIZ)}")
    print(f"  propriedades: {', '.join(sorted(PROPRIEDADES_DE_TELA))}")
    print(f"  Python varrido: {APP.relative_to(RAIZ)}/**/*.py (por AST)")
    print("  regra de tela do Python: a string CHEGA a um escoadouro de tela.")
    print(f"    escoadouros: {', '.join(sorted(ESCOADOUROS))}")
    print(
        "    recibos do gesto (toast), com a posição do texto: "
        + ", ".join(
            f"{nome}[{','.join(str(i) for i in posicoes)}]"
            for nome, posicoes in sorted(ESCOADOUROS_DE_RECIBO.items())
        )
    )
    print(f"    construtores: {', '.join(sorted(CONSTRUTORES_COM_TEXTO))}")
    print(f"    argumentos nomeados: {', '.join(sorted(NOMEADOS_DE_TELA))}")
    print(
        "    NÃO é texto de tela: chave de dicionário, id de widget, nome de "
        "sinal,\n    valor de enum, nome de variável, mensagem de log — nenhum "
        "chega a escoadouro."
    )
    print()
    print("Regra 1 — nenhum rótulo começa em minúscula. Exceções declaradas:")
    for rotulo, razao in EXCECOES_DE_MINUSCULA.items():
        print(f"  {rotulo!r}: {razao}")
    print()
    print("Regra 2 — nenhum rótulo contém jargão aposentado:")
    for termo, vira in JARGAO_BANIDO.items():
        print(f"  {termo!r} -> {vira!r}")
    print()
    print("Dívida declarada da E1-E4 no .glade (rótulos ainda não trocados):")
    for rotulo, razao in DIVIDA_DA_PALAVRA_01.items():
        print(f"  {rotulo!r}: {razao}")
    print()
    print("Em app/ vale a regra 2 (jargão) e NÃO a regra 1 (maiúscula):")
    print("  o escoadouro de tela recebe PEDAÇO em Python — marcação em volta")
    print("  de um valor, contagem, sufixo entre parênteses. Medido em")
    print("  23/08/2026: a regra 1 ali dava 49 reprovações e nenhum defeito.")
    print("  Quem confere maiúscula no texto COMPOSTO é o portão de widget,")
    print("  tests/unit/test_config_a_palavra_de_tela_da_aba_montada.py.")
    print()
    print("Dívida declarada em app/ (frases ainda não trocadas):")
    for rotulo, razao in DIVIDA_DA_PALAVRA_01_PY.items():
        print(f"  {rotulo!r}: {razao}")
    print()
    print("Dívida declarada no recibo do gesto (toasts ainda não trocados):")
    for rotulo, razao in DIVIDA_DO_RECIBO.items():
        print(f"  {rotulo!r}: {razao}")


def main(argumentos: list[str] | None = None) -> int:
    analisador = argparse.ArgumentParser(
        description=(
            "Portão da palavra de tela: reprova minúscula e jargão no .glade "
            "e no texto de tela montado em Python."
        ),
    )
    analisador.add_argument("--all", action="store_true", help="varre a interface da árvore")
    analisador.add_argument(
        "--check-file", nargs="+", metavar="CAMINHO", help="varre os arquivos indicados"
    )
    analisador.add_argument(
        "--mostrar-criterio", action="store_true", help="imprime o critério e sai"
    )
    analisador.add_argument("arquivos", nargs="*", help="o mesmo que --check-file")
    opcoes = analisador.parse_args(argumentos)

    if opcoes.mostrar_criterio:
        mostrar_criterio()
        return 0

    alvos = [Path(caminho) for caminho in (opcoes.check_file or []) + opcoes.arquivos]
    varredura_completa = opcoes.all or not alvos

    achados: list[str] = []
    if varredura_completa:
        achados.extend(conferir(GLADE))
        achados.extend(conferir_app())
    else:
        # Um arquivo por vez: os nomes que atravessam módulo continuam vindo do
        # corpo INTEIRO — senão `TITULO` e `DICA` sumiriam justamente quando se
        # confere a seção que os declara.
        nomes_de_tela: set[str] | None = None
        for alvo in alvos:
            if alvo.suffix == ".glade":
                achados.extend(conferir(alvo))
            elif alvo.suffix == ".py" and APP in alvo.resolve().parents:
                if nomes_de_tela is None:
                    nomes_de_tela = nomes_de_constante_de_tela(
                        {
                            caminho: ast.parse(caminho.read_text(encoding="utf-8"))
                            for caminho in arquivos_de_python()
                        }
                    )
                achados.extend(conferir_python(alvo.resolve(), nomes_de_tela))

    for achado in achados:
        print(achado)
    if achados:
        print()
        print(f"{len(achados)} reprovação(ões) da palavra de tela.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
