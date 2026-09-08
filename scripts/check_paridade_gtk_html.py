#!/usr/bin/env python3
"""O TERCEIRO NÚMERO — a paridade entre a janela GTK e a interface em HTML.

Os outros dois números desta casa medem a INTERFACE NOVA contra si mesma: a
régua de tela conta campos escritos, a régua do mockup compara o publicado com
o desenho aprovado. Nenhum dos dois responde *"o que a GTK faz e o HTML ainda
não faz"* — que é a pergunta da qual sai a fila de trabalho.

Este portão responde essa. A fonte é ``docs/data/paridade-gtk-html.csv``: 396
features medidas feature a feature em 03/09/2026, cada uma com o endereço dos
DOIS lados e um veredito.

O QUE ELE MEDE, e o que ele NÃO mede
------------------------------------
MEDE: se o CSV continua descrevendo o CÓDIGO DE HOJE. Cada linha carrega um
``sinal`` — um símbolo literal — e o que se espera dele no código. Quem lê é
esta régua, no fonte, agora.

NÃO MEDE: se a feature FUNCIONA. Nada aqui abre janela, clica ou toca aparelho.
Um botão que existe nos dois lados e está quebrado nos dois passa aqui sorrindo
— quem morde isso é a ponte JS do piloto (``--prova-gesto``), que roda com o
daemon vivo. Dito na cara porque a casa já pagou por régua que promete mais do
que alcança.

POR QUE O SINAL EXISTE, e é a decisão de projeto deste arquivo
--------------------------------------------------------------
Uma régua que compara o CSV com ele mesmo não mede nada — é a família de
defeito que esta casa mais pagou, e uma frente de 03/09 pegou uma régua
comparando o produto CONTRA ELE MESMO, concordando com a semente errada dos
dois lados.

Então o veredito de cada linha vira uma AFIRMAÇÃO SOBRE O CÓDIGO, verificável
sem o CSV:

  veredito                              sinal_espera   o que a régua lê
  IGUAL · DIFERENTE · SO_NO_HTML        PRESENTE       o símbolo TEM de estar
  NAO_DA_PARA_SABER                                    no arquivo do lado HTML
  FALTA_NO_HTML                         AUSENTE        o símbolo da GTK NÃO pode
                                                       aparecer no lado HTML

A segunda metade é a que envelhece o número de propósito. Quando alguém fechar
uma dívida — o lado HTML passar a chamar a função da GTK que a carregava —, o
símbolo aparece, esta régua REPROVA, e o CSV tem de ser atualizado. Sem isso o
"14% de paridade" vira propaganda no dia seguinte à primeira cura.

AS DOZE REGRAS
--------------
1. ``integridade``      cabeçalho, veredito fora do domínio, aba desconhecida,
                        par (aba, feature) repetido, CSV vazio.
2. ``endereco-morto``   ``caminho:linha`` cujo arquivo não existe, ou cuja linha
                        passa do fim do arquivo. É o "os endereços ABREM no que
                        prometem".
3. ``lado-trocado``     endereço da GTK na coluna do HTML, ou o contrário. É o
                        que impede este portão de virar a régua que compara o
                        produto contra ele mesmo.
4. ``sem-endereco``     linha sem endereço nenhum, ou linha que afirma
                        ``PRESENTE`` e não diz ONDE, no lado HTML.
5. ``sinal-sumiu``      ``PRESENTE`` cujo símbolo não está mais no escopo. Uma
                        feature ``IGUAL`` pode ter sido removida sem ninguém ver.
6. ``divida-fechada``   ``AUSENTE`` cujo símbolo APARECEU no lado HTML. O caso
                        BOM: alguém trabalhou e o dado ficou velho.
7. ``sinal-morto``      ``AUSENTE`` cujo símbolo não pode aparecer: não existe
                        no lado GTK **e** não tem forma de endereço de tela
                        (``data-algo="valor"``). Regra desligada em silêncio é
                        pior que regra nenhuma — um símbolo que não existe em
                        lugar nenhum e que ninguém vai escrever nunca APARECE,
                        e aquela linha nunca morderia.
                        As duas formas legítimas são as duas maneiras de a
                        dívida fechar: ou o HTML passa a chamar a função da GTK
                        que carregava a feature (símbolo do lado GTK), ou a
                        página ganha o endereço que lhe faltava
                        (``data-campo="fragil"``, e o pintor passa a alcançá-lo).
8. ``numero-publicado`` a tabela do documento diverge da contagem do CSV. O
                        número que ela lê para decidir sai do mesmo dado que a
                        régua confere, ou o documento vira folheto.
9. ``aposentado-vivo``  arquivo declarado em ``APOSENTADOS`` que voltou à árvore.

AS TRÊS DO CRUZAMENTO COM O MAPA DE CANAIS (06/09/2026, PARIDADE-CRUZA-O-MAPA-01)

10. ``ponte-morta``     uma ponta de ``PONTES`` não existe mais: o par
                        ``(aba, feature)`` saiu do CSV, ou o ``id`` saiu do mapa.
11. ``transporte-nao-declarado``
                        a linha AFIRMA paridade (``IGUAL``/``DIFERENTE``) e o
                        mapa restringe um transporte do canal embaixo dela — e a
                        linha não diz ``cabo`` nem ``rádio`` em lugar nenhum.
12. ``ponte-encolheu``  ``PONTES`` tem menos entradas que ``PISO_DAS_PONTES``.

E O QUE NÃO É REGRA, e é decisão dela: ``AVISO``. Todo lado restrito cuja causa
é ``nao-medido`` sai impresso e **não muda o rc**
(``D-0609-O-MAPA-INFORMA-NUNCA-VETA``): a célula está ATRASADA, não fechada, e
quem a remede é a bancada. O mapa INFORMA, nunca VETA.

**E A ORDEM DA SAÍDA É PARTE DO CONTRATO:** a FALHA fala primeiro e declara ser
o ``rc=1``; o AVISO fala por último e declara não ser. Impresso na ordem
inversa — como estava até 06/09/2026 — um portão honesto se LÊ como um portão
que reprova pelo próprio aviso, e foi assim que ele foi diagnosticado. Aviso
avisa, reprovação reprova, e nenhum dos dois se lê pelo lugar do outro.

A MORDIDA (arranque a cura, veja reprovar, devolva)
---------------------------------------------------
  - apague o ``html_onde`` de uma linha ``IGUAL``:  ``sem-endereco``;
  - troque uma linha citada por um número maior que o arquivo: ``endereco-morto``;
  - crie, no lado HTML, o símbolo que uma linha ``FALTA_NO_HTML`` diz faltar:
    ``divida-fechada`` — e é essa que prova que o número não envelhece calado;
  - apague a palavra ``cabo`` do ``porque`` de *Alto-falante — o som de
    confirmação*: ``transporte-nao-declarado``;
  - troque ``CAUSA_ATRASADA``: as três linhas do brilho da barra passam de AVISO
    a FALHA, e é essa que prova que o escape do ``nao-medido`` está vivo.

Uso:
    scripts/check_paridade_gtk_html.py              confere (rc=1 no primeiro achado)
    scripts/check_paridade_gtk_html.py --tabela     imprime o número por aba
    scripts/check_paridade_gtk_html.py --cruzamento imprime a ponte com o mapa
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prosa_do_codigo  # o irmão nesta pasta

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
DOC = RAIZ / "docs" / "process" / "2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

COLUNAS = [
    "aba", "feature", "veredito",
    "sinal", "sinal_espera", "sinal_escopo",
    "gtk_onde", "html_onde",
    "gtk_faz", "html_faz", "porque",
]

VEREDITOS = {
    "IGUAL": "PRESENTE",
    "DIFERENTE": "PRESENTE",
    "SO_NO_HTML": "PRESENTE",
    "NAO_DA_PARA_SABER": "PRESENTE",
    "FALTA_NO_HTML": "AUSENTE",
}

ABAS = (
    "01-jogar", "02-controles", "03-gatilhos", "04-iluminacao", "05-vibracao",
    "06-navegacao", "07-lancadores", "08-conexoes", "09-sistema", "10-perfis",
)

# ---------------------------------------------------------------------------
# OS DOIS LADOS, por pasta. Quem não está em nenhuma das duas listas é COMUM
# (o `core`, o `daemon`, o `profiles`) e pode ser citado dos dois lados: são as
# camadas que os dois consomem.
# ---------------------------------------------------------------------------
SO_GTK = (
    "src/hefesto_dualsense4unix/gui/",
    "src/hefesto_dualsense4unix/app/actions/",
    "src/hefesto_dualsense4unix/app/widgets/",
)
SO_HTML = (
    "src/hefesto_dualsense4unix/interface/",
    "src/hefesto_dualsense4unix/app/telas/",
    "mockup/",
)

#: MORAM NA GTK E SERVEM AO HTML — e isso é medido pelos imports, não pela
#: pasta: ``interface/sistema_viva.py`` importa ``gui.aba_sistema``,
#: ``interface/aba08.py`` importa ``gui.aba_conexoes``, e ``perfis_web`` é a
#: fonte da lista de perfis da aba 10. Tratá-los como exclusivos da GTK faria a
#: regra 3 acusar quem está certo.
COMPARTILHADOS = frozenset({
    "src/hefesto_dualsense4unix/gui/aba_sistema.py",
    "src/hefesto_dualsense4unix/gui/aba_conexoes.py",
    "src/hefesto_dualsense4unix/app/actions/perfis_web.py",
})

#: Onde a régua procura um sinal cujo escopo é o lado inteiro.
SUFIXOS = {".py", ".html", ".glade", ".css", ".js"}

#: OS ARQUIVOS QUE A CASA APOSENTOU POR DECISÃO — 06/09/2026, sprint `GTK-3`.
#:
#: Um endereço num deles NÃO é endereço morto: é endereço HISTÓRICO. A coluna
#: `gtk_onde` responde *"onde a GTK fazia isto"*, e essa pergunta continua tendo
#: resposta depois de o arquivo sair — a resposta é o git. Tratar as 126
#: citações como defeito obrigaria a apagá-las, e apagar o endereço apagaria a
#: única prova de que a feature EXISTIU do lado GTK, que é o que faz o
#: `FALTA_NO_HTML` desta planilha ser dívida e não opinião.
#:
#: **A LISTA NÃO PODE APODRECER, e há régua para isso:** um caminho declarado
#: aqui que VOLTE a existir na árvore reprova, nomeando. A declaração é sobre um
#: arquivo que saiu, não uma licença para não conferir endereço.
#:
#: E ela só vale para `gtk_onde`. Endereço histórico no lado HTML seria a régua
#: medindo a tela contra um arquivo que não abre — que é o defeito inteiro.
APOSENTADOS: dict[str, str] = {
    "src/hefesto_dualsense4unix/gui/main.glade": (
        "a janela GTK, aposentada em 06/09/2026 por decisão dela "
        "(D-0609-GTK-LEVA-INTEIRA): *\"a ideia sempre foi reaproveitar o que fiz "
        "no gtk e não apontar nada mais pra lá mas pro html\"*"
    ),
    "src/hefesto_dualsense4unix/app/app.py": (
        "o `HefestoApp`, que montava a janela — mesma decisão, mesmo dia"
    ),
    "src/hefesto_dualsense4unix/app/main.py": (
        "o entry point da janela — mesma decisão. O que nele NÃO montava janela "
        "mudou de casa para `app/arranque.py`"
    ),
    "scripts/gui-captura/": (
        "o retratista das ONZE abas da janela — mesma decisão. Quem fotografa as "
        "DEZ é `src/hefesto_dualsense4unix/interface/olhar.py --todas "
        "--publicado --doc`"
    ),
}


def aposentado(caminho: str) -> str | None:
    """A razão de o arquivo ter sido aposentado, ou None se ele não foi."""
    for prefixo, razao in APOSENTADOS.items():
        if caminho == prefixo or caminho.startswith(prefixo):
            return razao
    return None

#: O vocabulário de endereço da interface nova (``data-campo``, ``data-gesto``,
#: ``data-hef-alvo``…). Um sinal ``AUSENTE` com esta forma é legítimo mesmo sem
#: existir hoje em lugar nenhum: é O ENDEREÇO QUE A PÁGINA VAI GANHAR quando a
#: dívida fechar, e é assim que a metade "leitura ao vivo" desta medição fecha.
ENDERECO_DE_TELA = re.compile(r'data-[a-z-]+="[^"]+"')

# ===========================================================================
# O CRUZAMENTO COM O MAPA DE CANAIS — regras 10, 11 e 12
# ===========================================================================
#
# O ACHADO QUE ISTO FECHA (A-TELA-NOVA-ENTRA-NA-REGUA-DO-MAPA-01, §5.4,
# 06/09/2026): ``paridade-gtk-html.csv`` e ``mapa-controles.csv`` eram lidos
# juntos por DOIS arquivos do produto (``interface/aba02.py`` e
# ``interface/mesa_viva.py``) e por **portão nenhum**. Uma linha podia dizer
# ``IGUAL`` — a tela nova faz o que a janela fazia — enquanto o mapa dizia que
# o CANAL embaixo dela só aciona num transporte. Os dois números concordavam
# consigo mesmos e ninguém perguntava ao outro.
#
# E ELE INFORMA, NUNCA VETA (``D-0609-O-MAPA-INFORMA-NUNCA-VETA``). Palavra
# dela, 06/09/2026: *"Esse mapa é funcional e real. tá desatualizado no sentido
# de não ter sido medido. foi e tudo funciona."*  Uma célula em ``aciona=não``
# quer dizer **ninguém remediu**, não *o aparelho recusa* — por isso a causa
# ``nao-medido`` vira AVISO impresso, jamais ``rc=1``. Quem recolhe os avisos e
# marca a célula é a SPECS-A-PROCEDENCIA-01; este portão só põe a fila na mesa.
#
# POR QUE A PONTE É DECLARADA, e por que isso não é "a régua digitando o que
# devia ler": as duas planilhas não têm UMA palavra em comum. O ``sinal`` da
# paridade é um símbolo do código (``rumble_ff``, ``data-volume="microfone"``);
# a ``chave`` do mapa é o endereço de um canal do aparelho
# (``audio.microfone.mudo``). Medido em 06/09/2026: **zero** dos 396 ``sinal``
# contém uma das 110 ``chave``, em qualquer forma. Alguém tem de dizer que a
# fatia de tela X anda sobre o canal Y — e o que este portão NÃO deixa ser
# digitado é o VEREDITO: ele lê ``aciona`` e a causa do mapa a cada execução, e
# nunca guarda "esta feature é só no cabo". A ponte é o endereço; o fato é do
# mapa. As três travas que impedem a lista de apodrecer estão nas regras 10 e
# 12 — as duas pontas mortas reprovam, e a lista só pode CRESCER.

#: A ponte: ``(aba, feature)`` da paridade → ``id`` do mapa (``chave@controle``).
#: Uma entrada só entra aqui quando a fatia de tela ANDA SOBRE aquele canal —
#: nunca por parecença de nome.
PONTES: dict[tuple[str, str], str] = {
    # ── o alto-falante: o volume tem canal nos dois transportes; o SOM, não ──
    ("02-controles", "Alto-falante — o controle deslizante de volume"):
        "audio.alto_falante.volume@dualsense",
    ("02-controles", "Alto-falante — o número e a barra do bloco"):
        "audio.alto_falante.volume@dualsense",
    ("02-controles", "Alto-falante — o valor do volume em texto"):
        "audio.alto_falante.volume@dualsense",
    ("02-controles", "Alto-falante — o som de confirmação"):
        "audio.alto_falante@dualsense",
    ('02-controles', 'Alto-falante — "Todo o som do PC"'):
        "audio.alto_falante@dualsense",
    # ── o microfone ────────────────────────────────────────────────────────
    ("02-controles", "Microfone — o gesto do mudo (mic.set)"):
        "audio.microfone.mudo@dualsense",
    ("08-conexoes", "Microfone — quanto ele custa de rádio (a frase da capacidade)"):
        "audio.microfone@dualsense",
    ("08-conexoes", "Microfone — a trava no cabo e sem endereço"):
        "audio.microfone@dualsense",
    # ── a barra de luz ─────────────────────────────────────────────────────
    ("02-controles", "Barra de luz — o código hexadecimal da cor"):
        "luz.lightbar.cor@dualsense",
    ("02-controles", "Barra de luz — o retângulo colorido"):
        "luz.lightbar.cor@dualsense",
    ("04-iluminacao", "Apagar a barra (a cor vai a preto)"):
        "luz.lightbar.cor@dualsense",
    ("04-iluminacao", "O BRILHO viaja junto com a cor"):
        "luz.lightbar.brilho@dualsense",
    ("04-iluminacao", "Ajustar o brilho da barra (0–100%)"):
        "luz.lightbar.brilho@dualsense",
    ("04-iluminacao", "Mostrar o brilho corrente"):
        "luz.lightbar.brilho@dualsense",
    ('08-conexoes', '"A luz não acende" — derrubar o controle do rádio'):
        "luz.lightbar.release_leds@dualsense",
    ('08-conexoes', '"A luz não acende" — a trava no cabo'):
        "luz.lightbar.release_leds@dualsense",
    # ── o que a mesa lê do aparelho ────────────────────────────────────────
    ("01-jogar", "A bateria de cada controle no cartão"):
        "energia.bateria.percentual@dualsense",
    ("02-controles", "Bateria — o número"):
        "energia.bateria.percentual@dualsense",
    ("08-conexoes", "Bateria de cada controle na linha do acordeão"):
        "energia.bateria.percentual@dualsense",
    ("02-controles", "Giroscópio — os três eixos (número e barra bipolar)"):
        "movimento.giroscopio@dualsense",
    ("02-controles", "Acelerômetro — os três eixos"):
        "movimento.acelerometro@dualsense",
    ('02-controles', 'Touchpad — a palavra ("Sem toque" / "1 toque")'):
        "toque.touchpad@dualsense",
    ("02-controles", "Touchpad — o pontinho e a POSIÇÃO do dedo"):
        "toque.touchpad@dualsense",
    ("02-controles", "Gatilhos — a barra e o número (N / 255) de L2 e R2"):
        "gatilho.analogico@dualsense",
    ("03-gatilhos",
     "Escolher o modo do gatilho, por lado (L2/R2), entre os 19 do produto"):
        "gatilho.adaptativo@dualsense",
    ("05-vibracao", "A contagem de pedidos de vibração do JOGO (`rumble_ff`)"):
        "vibracao.rumble.ff@dualsense",
}

#: A CATRACA (regra 12). A ponte só CRESCE: quem apagar uma linha para calar um
#: achado é barrado, nomeando o piso. É a forma provada da casa
#: (``PISO_DA_REGUA``, de 06/09/2026) — comparação por ``>=``, para que
#: acrescentar uma ponte nunca seja punido.
PISO_DAS_PONTES = 26

#: Os dois lados do mapa, e o nome deles nas colunas do CSV.
LADOS_DO_MAPA = ("cabo", "radio")

#: A palavra que a linha da paridade tem de trazer para cada lado. É o glossário
#: da casa (cabo/rádio, nunca usb/bt) — e é por isso que o `usb` NÃO conta.
PALAVRA_DO_LADO = {"cabo": ("cabo",), "radio": ("radio", "radios")}

#: A causa que quer dizer *"ninguém remediu"*, e por isso nunca veta.
CAUSA_ATRASADA = "nao-medido"

#: Só o veredito que AFIRMA paridade é cobrado. `FALTA_NO_HTML` é dívida
#: declarada — cobrar transporte de quem já diz que não fez seria acusar duas
#: vezes; `SO_NO_HTML` e `NAO_DA_PARA_SABER` não afirmam paridade nenhuma.
VEREDITOS_QUE_AFIRMAM = ("IGUAL", "DIFERENTE")

def sem_acento(texto: str) -> str:
    """`Rádio` e `radio` são a mesma palavra para esta régua.

    Sem isto a linha que escreve certo (com acento, que é a regra da casa)
    escaparia da cobrança — o defeito que a casa chama de *a régua desliga
    exatamente quando alguém escreve bem*.
    """
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").lower()


def diz_o_transporte(linha: dict[str, str]) -> set[str]:
    """Que transportes a linha do CSV NOMEIA, em palavra inteira.

    Varre a linha inteira (a feature, o que cada lado faz e o porquê): a
    declaração pode estar em qualquer um deles, e exigir uma coluna certa seria
    inventar uma regra de forma sobre 396 linhas escritas antes dela.
    """
    texto = sem_acento(" ".join(
        linha.get(c, "") for c in ("feature", "gtk_faz", "html_faz", "porque")))
    achados = set()
    for lado, palavras in PALAVRA_DO_LADO.items():
        if any(re.search(rf"\b{p}\b", texto) for p in palavras):
            achados.add(lado)
    return achados


def lado_de(caminho: str) -> str:
    if caminho in COMPARTILHADOS:
        return "comum"
    if caminho.startswith(SO_GTK):
        return "gtk"
    if caminho.startswith(SO_HTML):
        return "html"
    return "comum"


def arquivos_do_lado(prefixos: tuple[str, ...]) -> list[Path]:
    """Os arquivos de um lado.

    Os COMPARTILHADOS ficam de FORA dos dois, e é de propósito: um símbolo de
    ``gui/aba_sistema.py`` apareceria como "chegou ao HTML" sem ninguém ter
    escrito uma linha de interface, e a regra 6 acusaria quem está certo. Para
    ENDEREÇO eles são comuns (ninguém é acusado por citá-los); para PROCURAR
    SINAL, o lado HTML é ``interface/`` mais ``app/telas/``, e só.
    """
    saida: list[Path] = []
    for pre in prefixos:
        base = RAIZ / pre
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*")):
            if p.is_file() and p.suffix in SUFIXOS and "__pycache__" not in p.parts:
                if p.relative_to(RAIZ).as_posix() in COMPARTILHADOS:
                    continue
                saida.append(p)
    return saida


class Arvore:
    """O código lido UMA vez. A régua reprova por leitura, nunca por `grep`."""

    def __init__(self) -> None:
        self._texto: dict[Path, str] = {}
        self._linhas: dict[Path, int] = {}
        self.html = arquivos_do_lado(SO_HTML)
        self.gtk = arquivos_do_lado(SO_GTK)

    def texto(self, p: Path) -> str:
        if p not in self._texto:
            try:
                self._texto[p] = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                self._texto[p] = ""
        return self._texto[p]

    def quantas_linhas(self, p: Path) -> int:
        if p not in self._linhas:
            self._linhas[p] = self.texto(p).count("\n") + 1
        return self._linhas[p]

    def ocorre(self, alvo: str, arquivos: list[Path]) -> Path | None:
        """O símbolo APARECE, prosa incluída — e aqui isso é de propósito.

        NÃO CONFUNDIR COM :meth:`usa`. **Muitos sinais deste CSV são citações
        por desenho**: a linha 19 vigia ``test_os_donos_de_fato.py`` (um nome de
        arquivo de teste) e a linha 2 vigia
        ``app/actions/mode_transition.plan_mode_transition`` (um caminho de
        módulo) — os dois só podem viver num comentário, e é assim que aquelas
        linhas mordem. Exigir USO aqui derruba 82 linhas legítimas (medido).

        A borda de palavra, essa sim, é ganho puro, e revelou um defeito: a
        linha 66 vigiava ``player_slot``, que não existe sozinho na página — só
        dentro de ``player_slot_color``. Aquela linha nunca mordeu.
        """
        for p in arquivos:
            if prosa_do_codigo.agulha(alvo).search(self.texto(p)):
                return p
        return None

    def usa(self, alvo: str, arquivos: list[Path]) -> Path | None:
        """O símbolo é USADO — citá-lo na prosa não conta.

        SÓ A REGRA ``divida-fechada`` CHAMA ESTA, e a razão é a assimetria:
        ``PRESENTE`` pergunta *"isto ainda está aqui?"* e uma citação basta;
        ``AUSENTE`` afirma *"o lado HTML NÃO faz isto"*, e citar a função alheia
        num comentário não é fazer.

        O DEFEITO QUE ELA MATA MORDEU TRÊS VEZES. Em 03/09/2026 as linhas 315 e
        343 foram promovidas a ``DIFERENTE`` porque o símbolo "apareceu" no lado
        HTML — era um COMENTÁRIO citando a função da GTK — e foram devolvidas no
        mesmo dia. Em 06/09/2026 a mesma linha 315 caiu de novo, agora por uma
        DOCSTRING que explicava o que a janela antiga fazia. E o mesmo defeito,
        no mesmo dia, mordeu ``check_donos_de_comportamento.py``.

        A separação tem dono único (``scripts/prosa_do_codigo.py``): a regra
        desta casa é que a cura cobre TODOS os chamadores. O portão dos donos
        resolve a mesma pergunta por outro caminho — ele coleta os NOMES que o
        ``ast`` aponta —, e é o certo lá: naquele CSV o dono é sempre um
        símbolo. Aqui não dá: **o sinal pode ser uma cadeia**
        (``"restaurar-de-fabrica"`` é o nome de um gesto), e coletar só nomes
        derrubaria essas linhas. Duas perguntas parecidas, dois instrumentos, a
        mesma decisão declarada nos dois lugares.
        """
        for p in arquivos:
            if prosa_do_codigo.usa(p, alvo):
                return p
        return None


def enderecos(celula: str) -> list[str]:
    return [e for e in (celula or "").split(" · ") if e.strip()]


def ler_csv() -> tuple[list[dict[str, str]], list[str]]:
    """As linhas do CSV, e o que já está errado no formato."""
    falhas: list[str] = []
    if not CSV.is_file():
        return [], [f"integridade: {CSV.relative_to(RAIZ)} não existe."]
    with CSV.open(encoding="utf-8", newline="") as fh:
        leitor = csv.DictReader(fh)
        cabecalho = list(leitor.fieldnames or [])
        linhas = list(leitor)
    if cabecalho != COLUNAS:
        falhas.append(
            "integridade: o cabeçalho do CSV mudou.\n"
            f"    esperado: {','.join(COLUNAS)}\n"
            f"    achado:   {','.join(cabecalho)}")
        return [], falhas
    if not linhas:
        falhas.append("integridade: o CSV não tem uma linha de dado.")
    vistos: set[tuple[str, str]] = set()
    for n, l in enumerate(linhas, 2):
        onde = f"{CSV.name}:{n}"
        if l["aba"] not in ABAS:
            falhas.append(f"integridade: {onde}: aba '{l['aba']}' não é uma das dez.")
        if l["veredito"] not in VEREDITOS:
            falhas.append(f"integridade: {onde}: veredito '{l['veredito']}' fora do domínio.")
            continue
        esperado = VEREDITOS[l["veredito"]]
        if l["sinal_espera"] != esperado:
            falhas.append(
                f"integridade: {onde}: veredito {l['veredito']} pede "
                f"sinal_espera={esperado}, e o CSV diz '{l['sinal_espera']}'.")
        chave = (l["aba"], l["feature"])
        if chave in vistos:
            falhas.append(f"integridade: {onde}: a feature '{l['feature']}' já apareceu em {l['aba']}.")
        vistos.add(chave)
    return linhas, falhas


def conferir_a_lista_de_aposentados() -> list[str]:
    """Regra 9: arquivo declarado APOSENTADO não pode estar de volta na árvore.

    Lista de exceção que envelhece calada vira paisagem — é regra desta casa, e
    aqui o preço seria alto: um `gui/main.glade` que voltasse a existir teria os
    endereços dele deixados de conferir para sempre, e a régua daria verde sobre
    linha que ninguém mais abre.
    """
    falhas: list[str] = []
    for caminho, razao in APOSENTADOS.items():
        alvo = RAIZ / caminho
        # A CASCA VAZIA NÃO É A COISA DE VOLTA — medido em 08/09/2026, na
        # árvore DELA, depois do install. O commit `f5311616` apagou os
        # arquivos de `scripts/gui-captura/` corretamente; o que sobrou foi o
        # DIRETÓRIO, vazio. Git não rastreia diretório vazio, então
        # `git status` fica limpo, o CI fica verde e uma worktree de agente
        # nunca reproduz — e a árvore dela carregava o único vermelho dos 49,
        # mandando a próxima pessoa caçar uma remoção desfeita que não
        # aconteceu.
        #
        # A pergunta desta regra é *"o que a decisão dela mandou apagar voltou?"*
        # Uma pasta sem nada dentro não é a coisa de volta. Um diretório só
        # reprova se tiver CONTEÚDO; arquivo reprova sempre.
        if alvo.is_dir() and not any(alvo.iterdir()):
            continue
        if alvo.exists():
            falhas.append(
                f"aposentado-vivo: {caminho} está declarado em `APOSENTADOS`\n"
                f"    ({razao})\n"
                "    e o arquivo EXISTE nesta árvore. Ou a remoção foi desfeita — e a\n"
                "    linha sai daqui, para os endereços voltarem a ser conferidos —, ou\n"
                "    alguém recriou o que a decisão dela mandou apagar.")
    return falhas


def conferir(linhas: list[dict[str, str]], arvore: Arvore) -> list[str]:
    falhas: list[str] = conferir_a_lista_de_aposentados()
    for n, l in enumerate(linhas, 2):
        onde = f"{CSV.name}:{n}  [{l['aba']}] {l['feature'][:64]}"
        gtk, html = enderecos(l["gtk_onde"]), enderecos(l["html_onde"])

        # --- regra 2 e 3: os endereços abrem, e cada um no seu lado ---------
        for coluna, lista, esperado in (("gtk_onde", gtk, "gtk"), ("html_onde", html, "html")):
            for e in lista:
                caminho, _, numero = e.partition(":")
                p = RAIZ / caminho
                razao = aposentado(caminho)
                if razao is not None:
                    # Endereço HISTÓRICO, não morto — ver `APOSENTADOS`. Só no
                    # lado GTK: no lado HTML seria a régua medindo a tela contra
                    # um arquivo que não abre.
                    if coluna != "gtk_onde":
                        falhas.append(
                            f"endereco-morto: {onde}\n"
                            f"    {coluna}: {e} — o arquivo foi APOSENTADO ({razao}),\n"
                            "    e endereço aposentado só vale em `gtk_onde`. O lado HTML "
                            "tem de\n    apontar para arquivo que abre.")
                    continue
                if not p.is_file():
                    falhas.append(f"endereco-morto: {onde}\n    {coluna}: {e} — o arquivo não existe.")
                    continue
                if numero:
                    total = arvore.quantas_linhas(p)
                    if not numero.isdigit() or int(numero) < 1 or int(numero) > total:
                        falhas.append(
                            f"endereco-morto: {onde}\n"
                            f"    {coluna}: {e} — o arquivo tem {total} linhas.")
                achado = lado_de(caminho)
                if achado != "comum" and achado != esperado:
                    falhas.append(
                        f"lado-trocado: {onde}\n"
                        f"    {coluna} cita {e}, que é do lado {achado.upper()}.\n"
                        "    Endereço no lado errado é a régua comparando o produto contra ele mesmo.")

        # --- regra 4: quem afirma tem de dizer onde -------------------------
        if not gtk and not html:
            falhas.append(f"sem-endereco: {onde}\n    a linha não cita um endereço sequer.")
        if l["sinal_espera"] == "PRESENTE" and not html:
            falhas.append(
                f"sem-endereco: {onde}\n"
                f"    o veredito {l['veredito']} afirma que o lado HTML TEM isto, "
                "e `html_onde` está vazio.")

        # --- regras 5, 6 e 7: o sinal contra o código -----------------------
        sinal, escopo = l["sinal"], l["sinal_escopo"]
        if not sinal:
            falhas.append(f"sem-endereco: {onde}\n    a linha não tem `sinal`: nada nela é conferível.")
            continue
        if l["sinal_espera"] == "PRESENTE":
            if escopo == "LADO-HTML":
                alvos = arvore.html
            else:
                p = RAIZ / escopo
                if not p.is_file():
                    falhas.append(f"endereco-morto: {onde}\n    sinal_escopo: {escopo} — não existe.")
                    continue
                if lado_de(escopo) == "gtk":
                    falhas.append(
                        f"lado-trocado: {onde}\n"
                        f"    sinal_escopo aponta {escopo}, que é do lado GTK.")
                    continue
                alvos = [p]
            if arvore.ocorre(sinal, alvos) is None:
                falhas.append(
                    f"sinal-sumiu: {onde}\n"
                    f"    o sinal {sinal!r} não está mais em {escopo}.\n"
                    f"    O CSV diz {l['veredito']}: ou a feature saiu do HTML, ou o sinal mudou de nome.\n"
                    "    Confira a feature e atualize a linha — não troque o sinal por outro que só passe.")
        else:
            achado = arvore.usa(sinal, arvore.html)
            if achado is not None:
                falhas.append(
                    f"divida-fechada: {onde}\n"
                    f"    o sinal {sinal!r} APARECEU em {achado.relative_to(RAIZ)}.\n"
                    "    O CSV diz FALTA_NO_HTML e o lado HTML passou a ter o símbolo.\n"
                    "    Se a dívida fechou, o veredito desta linha mudou: meça-a de novo e reescreva-a.")
            elif not ENDERECO_DE_TELA.fullmatch(sinal) and arvore.ocorre(sinal, arvore.gtk) is None:
                falhas.append(
                    f"sinal-morto: {onde}\n"
                    f"    o sinal {sinal!r} não existe no lado GTK e não tem forma de\n"
                    "    endereço de tela (data-algo=\"valor\"): ninguém vai escrevê-lo,\n"
                    "    então esta linha nunca morderia.")
    return falhas


def conferir_o_documento(linhas: list[dict[str, str]]) -> list[str]:
    """Regra 8: a tabela publicada é a contagem do CSV, linha por linha.

    O documento carrega a tabela dentro de um bloco ``<!-- TABELA-DA-PARIDADE
    -->``…``<!-- /TABELA-DA-PARIDADE -->``. Quem mexer no CSV e não regerar o
    documento é barrado aqui, nomeando a aba que divergiu.
    """
    if not DOC.is_file():
        return [f"numero-publicado: {DOC.relative_to(RAIZ)} não existe. "
                "O documento é metade desta entrega."]
    texto = DOC.read_text(encoding="utf-8")
    inicio = texto.find("<!-- TABELA-DA-PARIDADE -->")
    fim = texto.find("<!-- /TABELA-DA-PARIDADE -->")
    if inicio < 0 or fim < 0 or fim < inicio:
        return [f"numero-publicado: {DOC.name} perdeu o bloco "
                "<!-- TABELA-DA-PARIDADE --> … <!-- /TABELA-DA-PARIDADE -->."]
    publicado: dict[str, tuple[int, ...]] = {}
    for linha in texto[inicio:fim].splitlines():
        partes = [p.strip() for p in linha.strip().strip("|").split("|")]
        if len(partes) != 8 or partes[0] not in (*ABAS, "TODAS"):
            continue
        try:
            publicado[partes[0]] = tuple(int(p.rstrip("%")) for p in partes[1:])
        except ValueError:
            return [f"numero-publicado: {DOC.name}: a linha de '{partes[0]}' "
                    "tem célula que não é número."]
    falhas: list[str] = []
    for aba in (*ABAS, "TODAS"):
        deste = linhas if aba == "TODAS" else [l for l in linhas if l["aba"] == aba]
        c = Counter(l["veredito"] for l in deste)
        medido = (len(deste), c["IGUAL"], c["DIFERENTE"], c["FALTA_NO_HTML"],
                  c["SO_NO_HTML"], c["NAO_DA_PARA_SABER"],
                  round(100 * c["IGUAL"] / len(deste)) if deste else 0)
        if aba not in publicado:
            falhas.append(f"numero-publicado: {DOC.name} não publica a linha de '{aba}'.")
        elif publicado[aba] != medido:
            falhas.append(
                f"numero-publicado: {DOC.name}, linha '{aba}':\n"
                f"    publicado: {publicado[aba]}\n"
                f"    no CSV:    {medido}\n"
                "    (feats · IGUAL · DIFERENTE · FALTA_NO_HTML · SO_NO_HTML · ? · paridade%)")
    return falhas


def ler_mapa() -> tuple[dict[str, dict[str, str]], list[str]]:
    """O mapa de canais, indexado pelo `id` (`chave@controle`).

    O mapa é `nao_toca` desta frente: aqui ele só é LIDO. Ausência dele é falha
    de integridade e não silêncio — uma régua que se desliga sozinha quando a
    fonte some é a régua que dá verde sobre nada.
    """
    if not MAPA.is_file():
        return {}, [f"integridade: {MAPA.name} não existe, e o cruzamento com o "
                    "mapa de canais é metade deste portão."]
    with MAPA.open(encoding="utf-8", newline="") as fh:
        linhas = list(csv.DictReader(fh))
    if not linhas:
        return {}, [f"integridade: {MAPA.name} não tem uma linha de dado."]
    faltando = [c for c in ("id", "cabo_aciona", "radio_aciona",
                            "cabo_por_que_nao_aciona", "radio_por_que_nao_aciona")
                if c not in linhas[0]]
    if faltando:
        return {}, [f"integridade: {MAPA.name} não tem a(s) coluna(s) "
                    f"{', '.join(faltando)} — o cruzamento não tem o que ler."]
    return {l["id"]: l for l in linhas if l.get("id")}, []


def cruzar_com_o_mapa(
    linhas: list[dict[str, str]],
    mapa: dict[str, dict[str, str]],
    pontes: dict[tuple[str, str], str] | None = None,
    piso: int | None = None,
) -> tuple[list[str], list[str]]:
    """Regras 10, 11 e 12. Devolve `(falhas, avisos)`.

    10. ``ponte-morta``            uma ponta da ponte não existe mais — o par
                                   ``(aba, feature)`` sumiu do CSV da paridade,
                                   ou o ``id`` sumiu do mapa.
    11. ``transporte-nao-declarado`` a linha AFIRMA paridade (``IGUAL`` /
                                   ``DIFERENTE``) e o mapa restringe um dos dois
                                   transportes do canal embaixo dela — e a linha
                                   não nomeia transporte nenhum.
    12. ``ponte-encolheu``         a ponte tem menos entradas que o piso.

    O AVISO (nunca ``rc=1``): todo lado restrito cuja causa é ``nao-medido``. A
    célula está ATRASADA, não fechada — e quem a remede é a bancada, com o
    relatório de quem passou por ela. Se um lado restrito é só ``nao-medido``, a
    linha não deve nada: o mapa ainda não tem o que cobrar.
    """
    pontes = PONTES if pontes is None else pontes
    piso = PISO_DAS_PONTES if piso is None else piso
    falhas: list[str] = []
    avisos: list[str] = []

    if len(pontes) < piso:
        falhas.append(
            f"ponte-encolheu: a ponte com o mapa tem {len(pontes)} entrada(s) e o "
            f"piso é {piso}.\n"
            "    Apagar uma ponte é calar o achado dela, não resolvê-lo. Se a "
            "feature\n    saiu do CSV, a ponte sai junto E o piso desce, no mesmo "
            "commit e com a razão escrita.")

    por_chave = {(l["aba"], l["feature"]): l for l in linhas}
    for (aba, feature), ident in sorted(pontes.items()):
        onde = f"[{aba}] {feature[:64]}"
        linha = por_chave.get((aba, feature))
        if linha is None:
            falhas.append(
                f"ponte-morta: {onde}\n"
                f"    a ponte aponta para {ident}, e este par (aba, feature) não "
                "está mais no CSV\n    da paridade. Renomeou a feature? A ponte "
                "acompanha.")
            continue
        celula = mapa.get(ident)
        if celula is None:
            falhas.append(
                f"ponte-morta: {onde}\n"
                f"    a ponte aponta para o id {ident!r}, que não existe em "
                f"{MAPA.name}.\n    O mapa é o DNA do aparelho: quem muda a chave "
                "de lugar traz a ponte junto.")
            continue
        if linha["veredito"] not in VEREDITOS_QUE_AFIRMAM:
            continue

        cobra: list[str] = []
        for lado in LADOS_DO_MAPA:
            aciona = celula.get(f"{lado}_aciona", "")
            if aciona == "sim":
                continue
            causa = celula.get(f"{lado}_por_que_nao_aciona", "")
            if causa == CAUSA_ATRASADA:
                avisos.append(
                    f"{ident}  [{lado}]  aciona={aciona or '(vazio)'} "
                    f"causa=nao-medido\n"
                    f"    a tela AFIRMA paridade em {onde}\n"
                    "    e a célula não foi medida. Não é veto: é a fila da "
                    "bancada (SPECS-A-PROCEDENCIA-01).")
                continue
            cobra.append(f"{lado}={aciona or '(vazio)'}"
                         + (f" ({causa})" if causa else ""))
        if not cobra:
            continue
        if diz_o_transporte(linha):
            continue
        falhas.append(
            f"transporte-nao-declarado: {onde}\n"
            f"    veredito {linha['veredito']}, e o mapa restringe o canal "
            f"{ident}: {' · '.join(cobra)}.\n"
            "    A linha não diz 'cabo' nem 'rádio' em lugar nenhum — então ela "
            "afirma\n    paridade sem dizer ONDE ela vale. Escreva o transporte "
            "no `porque`.\n"
            "    (Se o aparelho contradiz o mapa, o APARELHO ganha: meça, escreva "
            "aqui o\n    que viu, e relate a célula para a SPECS-A-PROCEDENCIA-01 "
            "remedi-la.)")
    return falhas, avisos


def tabela_do_cruzamento(
    linhas: list[dict[str, str]], mapa: dict[str, dict[str, str]]
) -> str:
    """A ponte inteira, com o que o mapa diz de cada canal. Relatório, não régua."""
    por_chave = {(l["aba"], l["feature"]): l for l in linhas}
    saida = [f"{'id do mapa':46}{'cabo':10}{'rádio':10}{'ver.':11}feature"]
    for (aba, feature), ident in sorted(PONTES.items(), key=lambda kv: kv[1]):
        c = mapa.get(ident, {})
        linha = por_chave.get((aba, feature), {})
        saida.append(
            f"{ident:46}{c.get('cabo_aciona', '?'):10}"
            f"{c.get('radio_aciona', '?'):10}"
            f"{linha.get('veredito', '?'):11}[{aba}] {feature[:48]}")
    return "\n".join(saida)


def tabela(linhas: list[dict[str, str]]) -> str:
    saida = [f"{'aba':<15}{'feats':>6}{'IGUAL':>7}{'DIFER':>7}{'FALTA':>7}"
             f"{'SO_HTML':>9}{'?':>4}{'paridade':>10}"]
    for aba in (*ABAS, "TODAS"):
        deste = linhas if aba == "TODAS" else [l for l in linhas if l["aba"] == aba]
        if not deste:
            continue
        c = Counter(l["veredito"] for l in deste)
        pct = round(100 * c["IGUAL"] / len(deste))
        saida.append(
            f"{aba:<15}{len(deste):>6}{c['IGUAL']:>7}{c['DIFERENTE']:>7}"
            f"{c['FALTA_NO_HTML']:>7}{c['SO_NO_HTML']:>9}{c['NAO_DA_PARA_SABER']:>4}{pct:>9}%")
    return "\n".join(saida)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tabela", action="store_true",
                    help="imprime o número por aba e sai (rc=0)")
    ap.add_argument("--cruzamento", action="store_true",
                    help="imprime a ponte com o mapa de canais e sai (rc=0)")
    args = ap.parse_args()

    linhas, falhas = ler_csv()
    if args.tabela:
        print(tabela(linhas))
        return 0
    mapa, falhas_do_mapa = ler_mapa()
    if args.cruzamento:
        print(tabela_do_cruzamento(linhas, mapa))
        return 0
    falhas += falhas_do_mapa
    avisos: list[str] = []
    if linhas:
        falhas += conferir(linhas, Arvore())
        falhas += conferir_o_documento(linhas)
        do_cruzamento, avisos = cruzar_com_o_mapa(linhas, mapa)
        falhas += do_cruzamento

    # A REPROVAÇÃO VEM PRIMEIRO, e a ordem é a cura de um defeito medido —
    # 06/09/2026, A-CURA-DOS-DOIS-PORTOES-01.
    #
    # Até aqui o AVISO era impresso ANTES da FALHA, e a segunda linha dele diz
    # *"isto NÃO é rc=1"*. Num dia em que as duas coisas aconteceram juntas, o
    # `portoes.sh` mostrou `paridade-gtk-html VERMELHO rc=1` seguido, na linha
    # de baixo, do aviso que se declara inofensivo — e a FALHA que de fato
    # reprovava ficava vinte e cinco linhas abaixo. A leitura óbvia, e a que foi
    # feita e escrita, é que *o portão reprova pelo próprio aviso que ele diz
    # não ser reprovação*. O código nunca fez isso: `avisos` nunca tocou o `rc`.
    # Era a ORDEM DA SAÍDA mentindo sobre o código.
    #
    # Então: quem reprova fala primeiro, quem informa fala por último, e cada
    # bloco declara o que faz com o rc. Aviso avisa, reprovação reprova, e a
    # linha final diz de onde o rc veio — sem isso a próxima pessoa remede o
    # mesmo defeito, que é o que esta casa mais paga.
    if falhas:
        print(f"FALHA: {len(falhas)} achado(s) em {CSV.relative_to(RAIZ)}.")
        print("       ISTO é o rc=1 deste portão.\n")
        for f in falhas[:30]:
            print("  " + f)
        if len(falhas) > 30:
            print(f"\n  … e mais {len(falhas) - 30}.")
        print("\nO CSV é o DONO do fato; este script é a régua. Quem consertar uma")
        print("divergência mexe na linha do CSV, com o endereço novo lido no código —")
        print("nunca afrouxando a regra aqui.")

    if avisos:
        if falhas:
            print()
        print(f"AVISO: {len(avisos)} célula(s) do mapa que a tela AFIRMA e a "
              "bancada ainda não mediu.")
        print("       O mapa INFORMA, nunca VETA (D-0609-O-MAPA-INFORMA-NUNCA-VETA): "
              "isto NÃO é rc=1.")
        print("       Nenhuma linha abaixo entra no rc deste portão.\n")
        for a in avisos:
            print("  " + a)

    if falhas:
        print(f"\nrc=1 por {len(falhas)} FALHA(s)"
              + (f"; os {len(avisos)} AVISO(s) acima não contam." if avisos else "."))
        return 1

    c = Counter(l["veredito"] for l in linhas)
    print(f"OK: {len(linhas)} features conferidas contra o código — "
          f"{c['IGUAL']} IGUAL · {c['DIFERENTE']} DIFERENTE · "
          f"{c['FALTA_NO_HTML']} FALTA_NO_HTML · {c['SO_NO_HTML']} SO_NO_HTML · "
          f"{c['NAO_DA_PARA_SABER']} NAO_DA_PARA_SABER "
          f"({round(100 * c['IGUAL'] / len(linhas))}% de paridade).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
