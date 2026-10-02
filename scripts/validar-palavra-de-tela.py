#!/usr/bin/env python3
"""Portão da palavra de tela: a tela fala a língua de quem joga.

PALAVRA-01 / E5, seção "E5. Um gate, para não voltar" de
`docs/process/sprints/arquivados/2026-07-27-PALAVRA-01-a-janela-fala-a-lingua-de-quem-joga.md`.
A sprint pede um portão que reprove quando:

- um rótulo visível contém termo da lista de jargão banido — regra dos DOIS
  corpos de texto.

A REGRA DA MINÚSCULA MORREU COM A JANELA — 06/09/2026, sprint `GTK-3`
----------------------------------------------------------------------

Ela era "regra do `.glade`, e só dele", e o porquê continua escrito acima de
`DIVIDA_DA_PALAVRA_01_PY`: no XML, `<property name="label">` era sempre um
rótulo INTEIRO, e "começa em maiúscula?" tinha resposta. Nos DOIS corpos que
sobram — Python e HTML — o mesmo lugar recebe PEDAÇO, e a pergunta só é
respondível depois que os pedaços viram um rótulo. Quem a responde é
`tests/unit/test_config_a_palavra_de_tela_da_aba_montada.py`, que monta a aba
de verdade. Com o `gui/main.glade` fora da árvore não sobrou um só corpo de
texto onde a regra 1 fosse respondível, e ela saiu com o arquivo que a
sustentava — junto com `EXCECOES_DE_MINUSCULA`, que só listava rótulos dele.

O ALCANCE, declarado: DOIS corpos de texto de tela.

1. as PÁGINAS PUBLICADAS da interface nova
   (`src/hefesto_dualsense4unix/interface/paginas/*.html`), onde mora o texto
   DECLARATIVO da tela que ela abre — o herdeiro direto do `.glade`;
2. o texto de tela MONTADO EM PYTHON em `src/hefesto_dualsense4unix/app/`,
   lido por AST — nunca por expressão regular sobre a linha.

O ITEM 1 TROCOU DE CORPO EM 06/09/2026, e a conta está medida
--------------------------------------------------------------

Até este dia o item 1 era o `gui/main.glade`. A `GTK-3` o apagou por decisão
dela (`D-0609-GTK-LEVA-INTEIRA`: *"a ideia sempre foi reaproveitar o que fiz no
gtk e não apontar nada mais pra lá mas pro html"*), e um portão que perde o
arquivo que lê não fica verde — ele reprova nomeando o que sumiu
(`conferir_html` devolve "arquivo de interface não encontrado" do mesmo jeito
que o antecessor devolvia). Trocar o corpo, e não só apagá-lo, é o que devolve
o alcance:

    do `gui/main.glade`, que morreu        219 rótulos
    das dez páginas publicadas             6.541 rótulos e atributos de tela
    achados na estreia                     ZERO

**Zero na estreia não é régua verde sobre nada, e há duas travas contra isso:**
`conferir_html` reprova se achar menos de dez páginas (o caminho mudou) e a
mordida está escrita em `tests/unit/test_a_palavra_de_tela_da_interface_nova.py`
— pôr um termo banido numa página faz este portão reprovar nomeando arquivo e
linha.

**E ESTE PORTÃO NÃO SUBSTITUI A RÉGUA IRMÃ, nem ela a ele.** Aqui a leitura é
ESTÁTICA e roda na camada `--rapido`, sem navegador, a cada fechamento de leva;
lá (`test_a_palavra_de_tela_da_interface_nova.py`) a página é ABERTA e o DOM é
lido depois dos cliques, que é o único lugar onde o texto escrito por
`<script>` aparece — em 05/09/2026 uma varredura estática de
`mapa-das-portas.html` contou ZERO e a página tinha CATORZE, todas dentro do
`<script>`. Cada uma alcança o que a outra não vê, e a lista de termos é UMA
SÓ: `JARGAO_BANIDO`, aqui, importado por ela.

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
atributo (`moldura_de_secao(secao.TITULO, secao.DICA)`, `config/mixin.py:28`).
O portão aprende esses nomes do próprio código, e não de uma lista escrita à
mão: ele varre o corpo inteiro de `app/` atrás de `alguma_coisa.NOME` em
posição de texto de tela, e daí em diante toda constante de módulo com esse
nome conta como texto de tela. Hoje isso resolve para exatamente dois nomes —
`TITULO` e `DICA` — e é o contrato que `config/secoes.py:14` já escrevia em
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
import re
import sys
from collections.abc import Iterator
from html.parser import HTMLParser
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
PAGINAS = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # (noqa-acento)  (nome de pasta no disco)
APP = RAIZ / "src" / "hefesto_dualsense4unix" / "app"

ETIQUETAS_MUDAS = frozenset({"script", "style", "template"})

ATRIBUTOS_DE_TELA = ("title", "aria-label", "placeholder", "alt")

JARGAO_BANIDO: dict[str, str] = {
    "daemon offline": "O Hefesto está desligado",
    "daemon pausado": "O Hefesto está em pausa",
    "uinput disponível": "Pronto para usar como mouse",
    "Restaurar Default": "Voltar ao padrão",
    "Travar Proton validado": "Fixar a versão que funciona",
    "Aplicar correções": "Consertar problemas conhecidos",
    "Testar criação de device virtual": "Testar o controle virtual",
    "Gamepads:": "Controles detectados:",
    "devpath": "diga a entrada USB: 'Entrada 4 do hub'",
    "vid:pid": "o código do fabricante não é palavra de tela — põe na dica",
    "mesa": "o termo é 'objeto' ou o sinônimo que couber: escrivaninha, arranjo, "
            "'os controles ligados'",
}

_A_PALAVRA_QUE_ESPERA_A_LEX_6 = "barramento"

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


class _ColheitaDaPagina(HTMLParser):
    """Colhe o que a pessoa LÊ numa página publicada, com a linha de cada item."""

    def __init__(self, caminho: Path) -> None:
        super().__init__(convert_charrefs=True)
        self.caminho = caminho
        self.rotulos: list[Rotulo] = []
        self._pilha: list[tuple[str, bool]] = []
        self._mudo = 0
        self._nota = 0

    def _calado(self) -> bool:
        return bool(self._mudo or self._nota)

    def _atributos(self, atributos: list[tuple[str, str | None]]) -> None:
        if self._calado():
            return
        como_dicionario = dict(atributos)
        for nome in ATRIBUTOS_DE_TELA:
            valor = (como_dicionario.get(nome) or "").strip()
            if valor:
                self.rotulos.append(Rotulo(self.caminho, self.getpos()[0], nome, valor))

    def handle_starttag(self, tag: str, atributos: list[tuple[str, str | None]]) -> None:
        self._atributos(atributos)
        e_nota = tag == "div" and "nota" in (dict(atributos).get("class") or "").split()
        if tag in ETIQUETAS_MUDAS:
            self._mudo += 1
        if e_nota:
            self._nota += 1
        self._pilha.append((tag, e_nota))

    def handle_startendtag(self, tag: str, atributos: list[tuple[str, str | None]]) -> None:
        self._atributos(atributos)

    def handle_endtag(self, tag: str) -> None:
        for indice in range(len(self._pilha) - 1, -1, -1):
            aberta, _ = self._pilha[indice]
            if aberta != tag:
                continue
            for descartada, era_nota in self._pilha[indice:]:
                if descartada in ETIQUETAS_MUDAS:
                    self._mudo -= 1
                if era_nota:
                    self._nota -= 1
            del self._pilha[indice:]
            return

    def handle_data(self, dados: str) -> None:
        if self._calado():
            return
        texto = dados.strip()
        if texto:
            self.rotulos.append(Rotulo(self.caminho, self.getpos()[0], "texto", texto))


def rotulos_da_pagina(caminho: Path) -> list[Rotulo]:
    """Todo texto de tela da página, com a linha em que ele começa."""
    colheita = _ColheitaDaPagina(caminho)
    colheita.feed(caminho.read_text(encoding="utf-8"))
    colheita.close()
    return colheita.rotulos


def regua_do_termo(termo: str) -> re.Pattern[str]:
    return re.compile(r"(?<![\wÀ-ÿ])" + re.escape(termo) + r"s?(?![\wÀ-ÿ])", re.IGNORECASE)


def jargao_em(texto: str) -> str | None:
    """O primeiro termo banido que aparece no rótulo, ou None."""
    achatado = texto.lower()
    for termo in JARGAO_BANIDO:
        if termo.lower() in achatado:
            return termo
    return None


def jargao_na_frase(texto: str) -> str | None:
    """O primeiro termo banido que aparece na frase, com borda de palavra."""
    for termo in JARGAO_BANIDO:
        if regua_do_termo(termo).search(texto):
            return termo
    return None


def paginas_publicadas(raiz: Path = PAGINAS) -> list[Path]:
    """As páginas que o produto abre — as `.dc.html` são desenho, não produto."""
    return sorted(p for p in raiz.glob("*.html") if not p.name.endswith(".dc.html"))


def conferir_html(raiz: Path = PAGINAS) -> list[str]:
    """As reprovações das páginas publicadas, em ordem de arquivo e linha."""
    if not raiz.is_dir():
        return [f"{raiz}: pasta de interface não encontrada"]

    paginas = paginas_publicadas(raiz)
    if len(paginas) < 10:
        return [
            f"{raiz}: achei {len(paginas)} página(s) publicada(s), e a interface "
            "tem DEZ abas. Ou o caminho mudou, ou a publicação quebrou — nos "
            "dois casos este portão passaria a medir menos tela em silêncio."
        ]

    achados: list[str] = []
    presentes: set[str] = set()
    for pagina in paginas:
        for rotulo in rotulos_da_pagina(pagina):
            if not rotulo.texto:
                continue
            presentes.add(rotulo.texto)
            termo = jargao_na_frase(rotulo.texto)
            if termo is not None and rotulo.texto not in DIVIDA_DA_PALAVRA_01:
                achados.append(
                    f"{rotulo.arquivo}:{rotulo.linha}: o rótulo "
                    f"{rotulo.texto[:140]!r} ({rotulo.propriedade}) contém o "
                    f"jargão {termo!r}, aposentado pela E3 da PALAVRA-01.\n"
                    f"    Diga {JARGAO_BANIDO[termo]!r}. Quem joga não é "
                    "obrigado a saber o que é um daemon.\n"
                    "    A página é GERADA: conserte em "
                    "`src/hefesto_dualsense4unix/interface/` e republique."
                )

    for rotulo_declarado in DIVIDA_DA_PALAVRA_01:
        if rotulo_declarado not in presentes:
            achados.append(
                f"{raiz}: a dívida {rotulo_declarado!r} não existe mais nesta "
                "tela — o rótulo foi trocado, e é uma boa notícia. APAGUE a "
                "entrada de `DIVIDA_DA_PALAVRA_01`."
            )

    return achados


#: sai com: A-TELA-SEM-O-QUE-A-REGUA-ACEITA-01
DIVIDA_DA_PALAVRA_01_PY: dict[str, str] = {}

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
    "moldura_de_secao": 2,
    "rotulo_de_apoio": 1,
}

ESCOADOUROS_DE_RECIBO: dict[str, tuple[int, ...]] = {
    "_status_toast": (1,),
    "_toast_do_relancar": (0,),
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

DIVIDA_DO_RECIBO: dict[str, str] = {}

CONSTRUTORES_COM_TEXTO = frozenset(
    {"Label", "Button", "CheckButton", "RadioButton", "MenuItem", "ToggleButton", "LinkButton"}
)

NOMEADOS_DE_TELA = frozenset(
    {"label", "text", "title", "tooltip_text", "placeholder_text", "titulo", "dica", "texto"}
)


def _posicoes_do_nome(nome: str) -> tuple[int, ...] | None:
    """As posições de texto de tela deste nome de chamada, ou None."""
    if nome in ESCOADOUROS:
        return tuple(range(ESCOADOUROS[nome]))
    return ESCOADOUROS_DE_RECIBO.get(nome)


def _escoadouro_de(no: ast.Call) -> tuple[int, ...] | None:
    """Que posições desta chamada são texto de tela, ou None."""
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


BURACO = "{}"


def _texto_reconstruido(no: ast.expr) -> str | None:
    """A expressão remontada como a pessoa a lê, ou None se não for texto."""
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
    """Os nomes de constante que ATRAVESSAM módulo até um escoadouro."""
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
    """Todo texto de tela ESTÁTICO do módulo, com a linha em que ele mora."""
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
    """A varredura inteira de `app/`, com a checagem de lista envelhecida."""
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
    paginas = paginas_publicadas()
    print(f"  HTML varrido: {PAGINAS.relative_to(RAIZ)}/*.html ({len(paginas)} páginas)")
    print("    o que conta como tela: todo texto fora de "
          f"{'/'.join(sorted(ETIQUETAS_MUDAS))} e de `div.nota`,")
    print(f"    mais os atributos {', '.join(ATRIBUTOS_DE_TELA)}.")
    print("    o que ele NÃO alcança: o texto que o `<script>` escreve no DOM "
          "e o que\n    só nasce depois de um clique — quem lê isso é "
          "tests/unit/test_a_palavra_de_tela_da_interface_nova.py.")
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
    print("Regra 1 (minúscula) MORREU COM A JANELA em 06/09/2026: ela era do")
    print("  `.glade`, onde o rótulo era inteiro. Em Python e em HTML o texto")
    print("  chega em PEDAÇO, e quem confere maiúscula no rótulo COMPOSTO é")
    print("  tests/unit/test_config_a_palavra_de_tela_da_aba_montada.py.")
    print()
    print("Regra 2 — nenhum rótulo contém jargão aposentado:")
    for termo, vira in JARGAO_BANIDO.items():
        print(f"  {termo!r} -> {vira!r}")
    print()
    print("Dívida declarada nas páginas publicadas (rótulos ainda não trocados):")
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
            "Portão da palavra de tela: reprova jargão nas páginas publicadas "
            "da interface e no texto de tela montado em Python."
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
        achados.extend(conferir_html())
        achados.extend(conferir_app())
    else:
        nomes_de_tela: set[str] | None = None
        for alvo in alvos:
            if alvo.suffix == ".html" and not alvo.name.endswith(".dc.html"):
                for rotulo in rotulos_da_pagina(alvo):
                    termo = jargao_na_frase(rotulo.texto)
                    if termo is not None and rotulo.texto not in DIVIDA_DA_PALAVRA_01:
                        achados.append(
                            f"{rotulo.arquivo}:{rotulo.linha}: o rótulo "
                            f"{rotulo.texto[:140]!r} ({rotulo.propriedade}) "
                            f"contém o jargão {termo!r}, aposentado pela E3 da "
                            f"PALAVRA-01.\n    Diga {JARGAO_BANIDO[termo]!r}."
                        )
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
