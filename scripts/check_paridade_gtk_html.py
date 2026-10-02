#!/usr/bin/env python3
"""O TERCEIRO NÚMERO — a paridade entre a janela GTK e a interface em HTML."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prosa_do_codigo

RAIZ = Path(__file__).resolve().parents[1]
CSV = RAIZ / "docs" / "data" / "paridade-gtk-html.csv"
DOC = RAIZ / "docs" / "method" / "2026-09-03-O-TERCEIRO-NUMERO-a-paridade-com-a-gtk.md"
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

#: pasta: ``interface/sistema_viva.py`` importa ``interface.sistema``,
COMPARTILHADOS = frozenset({
    "src/hefesto_dualsense4unix/interface/sistema.py",
    "src/hefesto_dualsense4unix/interface/conexoes.py",
    "src/hefesto_dualsense4unix/app/actions/perfis_web.py",
})

SUFIXOS = {".py", ".html", ".glade", ".css", ".js"}

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

ENDERECO_DE_TELA = re.compile(r'data-[a-z-]+="[^"]+"')

# paridade é um símbolo do código (``rumble_ff``, ``data-volume="microfone"``);

PONTES: dict[tuple[str, str], str] = {
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
    ("02-controles", "Microfone — o gesto do mudo (mic.set)"):
        "audio.microfone.mudo@dualsense",
    ("08-conexoes", "Microfone — quanto ele custa de rádio (a frase da capacidade)"):
        "audio.microfone@dualsense",
    ("08-conexoes", "Microfone — a trava no cabo e sem endereço"):
        "audio.microfone@dualsense",
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

PISO_DAS_PONTES = 26

LADOS_DO_MAPA = ("cabo", "radio")

PALAVRA_DO_LADO = {"cabo": ("cabo",), "radio": ("radio", "radios")}

CAUSA_ATRASADA = "nao-medido"

VEREDITOS_QUE_AFIRMAM = ("IGUAL", "DIFERENTE")

def sem_acento(texto: str) -> str:
    """`Rádio` e `radio` são a mesma palavra para esta régua."""
    decomposto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in decomposto if unicodedata.category(c) != "Mn").lower()


def diz_o_transporte(linha: dict[str, str]) -> set[str]:
    """Que transportes a linha do CSV NOMEIA, em palavra inteira."""
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
    ``interface/sistema.py`` apareceria como "chegou ao HTML" sem ninguém ter
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
        """O símbolo é USADO — citá-lo na prosa não conta."""
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
    """Regra 9: arquivo declarado APOSENTADO não pode estar de volta na árvore."""
    falhas: list[str] = []
    for caminho, razao in APOSENTADOS.items():
        alvo = RAIZ / caminho
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

        # O lado GTK é registro desde 02/10/2026: a sobra da janela saiu do pacote, e
        # `gtk_onde` diz onde a capacidade morava, não onde ela abre hoje.
        for coluna, lista, esperado in (("html_onde", html, "html"),):
            for e in lista:
                caminho, _, numero = e.partition(":")
                p = RAIZ / caminho
                razao = aposentado(caminho)
                if razao is not None:
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

        if not gtk and not html:
            falhas.append(f"sem-endereco: {onde}\n    a linha não cita um endereço sequer.")
        if l["sinal_espera"] == "PRESENTE" and not html:
            falhas.append(
                f"sem-endereco: {onde}\n"
                f"    o veredito {l['veredito']} afirma que o lado HTML TEM isto, "
                "e `html_onde` está vazio.")

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
    return falhas


def conferir_o_documento(linhas: list[dict[str, str]]) -> list[str]:
    """Regra 8: a tabela publicada é a contagem do CSV, linha por linha."""
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
    """O mapa de canais, indexado pelo `id` (`chave@controle`)."""
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
    """Regras 10, 11 e 12. Devolve `(falhas, avisos)`."""
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
