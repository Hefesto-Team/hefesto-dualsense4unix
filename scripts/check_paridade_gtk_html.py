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

AS OITO REGRAS
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

A MORDIDA (arranque a cura, veja reprovar, devolva)
---------------------------------------------------
  - apague o ``html_onde`` de uma linha ``IGUAL``:  ``sem-endereco``;
  - troque uma linha citada por um número maior que o arquivo: ``endereco-morto``;
  - crie, no lado HTML, o símbolo que uma linha ``FALTA_NO_HTML`` diz faltar:
    ``divida-fechada`` — e é essa que prova que o número não envelhece calado.

Uso:
    scripts/check_paridade_gtk_html.py            confere (rc=1 no primeiro achado)
    scripts/check_paridade_gtk_html.py --tabela   imprime o número por aba
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
DOC = RAIZ / "docs" / "process" / "2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md"

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
        for p in arquivos:
            if alvo in self.texto(p):
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
            achado = arvore.ocorre(sinal, arvore.html)
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
    args = ap.parse_args()

    linhas, falhas = ler_csv()
    if args.tabela:
        print(tabela(linhas))
        return 0
    if linhas:
        falhas += conferir(linhas, Arvore())
        falhas += conferir_o_documento(linhas)

    if falhas:
        print(f"FALHA: {len(falhas)} achado(s) em {CSV.relative_to(RAIZ)}.\n")
        for f in falhas[:30]:
            print("  " + f)
        if len(falhas) > 30:
            print(f"\n  … e mais {len(falhas) - 30}.")
        print("\nO CSV é o DONO do fato; este script é a régua. Quem consertar uma")
        print("divergência mexe na linha do CSV, com o endereço novo lido no código —")
        print("nunca afrouxando a regra aqui.")
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
