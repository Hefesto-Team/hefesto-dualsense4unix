#!/usr/bin/env python3
"""check_so_a_primeira_letra.py — só a primeira letra da frase é maiúscula.

A REGRA É DE PRODUTO (09/10/2026, escolha no chat: «Só a 1ª maiúscula»), e repete a de
08/10 no ESCOLHAS.md: *toda frase começa com maiúscula e o resto em minúscula*.
Rótulo de botão, título e cartão saíam em Title Case, à inglesa — «Salvar
Perfil», «Gestão de Controles», «Modo Automático», «Perfil de Bateria», «Modo
Nativo». A régua da caixa alta (`check_a_maiuscula_decorativa.py`) pega a
palavra INTEIRA em maiúscula; esta pega a INICIAL maiúscula no meio da frase.

O QUE ELA LÊ
------------
O texto que a pessoa lê nas dez abas — a leitura do produto é a de
`frases_que_ela_baniu.texto_visivel_no_produto`, com o `<style>`, o `<script>`,
os comentários e o `<title>` do documento fora (o recorte é o da régua da caixa
alta, `_so_a_tela`) — nas páginas publicadas e, com `--bancada`, no `mockup/`.
E lê também os três mapas que as abas abrem (`MAPAS`: o das portas, o do controle e
o do rádio), que até 09/10/2026 ficavam fora: o das portas carregou de 26/09 a
05/10 um JS que punha maiúscula em TODA palavra na hora da pintura, e o texto
parado da página não o mostra. Por isso a régua também reprova o mapa que volte a
trazer esse JS (`TITULO_EM_TODA_PALAVRA`).
Entra o `title`, o `aria-label`, o `placeholder` e o `alt`, cada um como uma
frase própria.

ONDE UMA FRASE COMEÇA
---------------------
No começo de cada bloco (toda etiqueta que não é de ênfase dentro da frase:
`b`, `strong`, `i`, `em`, `code`, `kbd`, `small`, `abbr`, `sup`, `sub`, `u`,
`mark`, `q`, `s`), no começo de cada atributo lido, e dentro do texto depois de
`.`, `!`, `?`, `…`, `:`, `;`, da abertura de aspas e parêntese, e dos
separadores de rótulo (`—`, `·`, `•`, `●`, `|`, `→`, `/`, `+`). O `span` conta
como bloco: o desenho o usa como caixa, e lê-lo como texto corrido daria
vermelho sobre dois rótulos vizinhos. É a leitura que erra para o lado verde,
de propósito — e é a que a régua do WebKit
(`test_todo_texto_que_abre_uma_linha_comeca_com_maiuscula.py`) completa.

O QUE PODE TER MAIÚSCULA NO MEIO
--------------------------------
Nome próprio e marca, nas listas abaixo, cada uma com o nome do que guarda:
`MARCAS`, `TECLAS` (o que está escrito na tecla ou no botão do aparelho),
`UNIDADES`, os nomes de cor do `docs/data/cores-do-dualsense.csv` (lidos do dono),
os nomes das dez abas (lidos da fita de abas da própria página), `NOMES_DO_DESENHO`
(o dado de exemplo do gerador, que o produto troca pelo nome que a pessoa deu),
`DESIGNADORES` (a palavra seguida do número que a nomeia: «Entrada 4») e
`ROTULOS_CITADOS` (o nome de um controle da tela citado no meio da frase, letra
por letra — a régua confere que o rótulo existe). A palavra inteira em caixa
alta é da régua irmã, e a que tem maiúscula por dentro («RetroArch»,
«PipeWire») é marca pela forma.

Uso::

    scripts/check_so_a_primeira_letra.py              # as páginas publicadas
    scripts/check_so_a_primeira_letra.py --bancada    # o `mockup/`
    scripts/check_so_a_primeira_letra.py --lista      # só o inventário, rc=0
"""
from __future__ import annotations

import csv
import html
import pathlib
import re
import sys

RAIZ = pathlib.Path(__file__).resolve().parents[1]
PUBLICADO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas"  # noqa-acento: nome de PASTA
BANCADA = RAIZ / "mockup"
CORES_CSV = RAIZ / "docs" / "data" / "cores-do-dualsense.csv"
PECAS_CSV = RAIZ / "docs" / "data" / "pecas-do-dualsense.csv"
E_ABA = re.compile(r"^\d\d-[a-z]+\.html$")
MAPAS = ("mapa-das-portas.html", "mapa-do-controle.html", "mapa-do-radio.html")

#: A marca do JS de 26/09/2026 que punha maiúscula em toda palavra do mapa na hora da
#: pintura (o `emTitulo` da `pagina_do_mapa`). O texto parado não o mostra: a régua
#: o procura no HTML inteiro, com o `<script>`.
TITULO_EM_TODA_PALAVRA = re.compile(r"function\s+emTitulo\b|TODA PALAVRA COM MAI[UÚ]SCULA")

sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "scripts"))

MARCAS = frozenset({
    "DualSense", "DualSense4Unix", "Hefesto", "Steam", "Linux", "Unix", "Proton",
    "Xbox", "Freestyle", "Nintendo", "Pro", "Sony", "PlayStation", "Windows",
    "Wi-Fi", "Bluetooth", "Vulkan", "Big", "Picture", "Input", "Ryujinx",
    "Lutris", "Heroic", "Wayland", "AppImage", "Flatpak", "Xiaomi", "Edge",
})

TECLAS = frozenset({
    "Alt", "Tab", "Shift", "Ctrl", "Super", "Enter", "Esc",
    "Create", "Options", "Share", "Start", "Select", "Menu",
})

UNIDADES = frozenset({"MHz", "GHz", "Hz", "kHz", "dB", "dBm", "mA", "ms"})

#: O dado de exemplo dos geradores: os donos dos controles da mesa do desenho
#: (`monta.MESA`, `aba08`), os jogos da lista de perfis (`aba10.PERFIS`), os
#: aparelhos do rádio (o `Alias` do BlueZ, que nasce da classe: «Caixa de som»)
#: e as entradas que o usuário nomeou na mesa de exemplo (Esquerda, Meio, Direita). O
#: produto troca cada um pelo nome que a pessoa deu ou que o jogo tem; nome de
#: gente, de jogo, de aparelho e de entrada é próprio.
NOMES_DO_DESENHO = (
    "Vitória", "Ana", "Pedro", "Rafa", "Davi", "Lia",
    "Mortal Kombat", "Elden Ring", "Don't Scream", "Wendigo Blue",
    "Orpheus: To Hell and Back", "Mina the Hollower",
    "Xiaomi Scale S400", "Xiaomi Band 9",
    "Teclado", "Mouse", "Caixa de som", "Fone", "Celular", "Relógio", "Acessório",
    "Esquerda", "Meio", "Direita",
)

#: A palavra que, seguida do número, é o nome de um lugar: «Entrada 4».
DESIGNADORES = frozenset({"Entrada", "Canal", "Player", "Controle"})

#: O nome de um controle da tela citado no meio da frase, como a tela o escreve
#: («quando clicar em Salvar perfil»). A régua confere que cada um É rótulo de
#: alguma página: o nome que some da tela sai daqui.
ROTULOS_CITADOS: tuple[str, ...] = (
    "Aplicar", "Salvar perfil", "Conectar", "Parar",
    "Padrão", "Economia", "Máximo", "Sensor háptico",
    "Interna", "Definições controle e mouse", "Teclas do teclado", "Trocar os botões",
    "Atrás do gabinete", "Gestão de controles", "Rádio e adaptadores", "Mapa das conexões",
    "Personalizado", "Universal",
)

#: A régua lê `+` como separador de tecla («Alt + Tab»).
_INICIO = re.compile(r"(?:^|[.!?…:;]\s+|[«“\"(\[]\s*|\s[—–·•●|→+]\s+|/)$")
_PALAVRA = re.compile(r"[^\W\d_][^\W_]*(?:[-'’][^\W_]+)*")
_TAG = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9-]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*)>", re.S)
_ATRIBUTO_LIDO = re.compile(
    r"\b(?:title|placeholder|aria-label|alt)\s*=\s*(\"[^\"]*\"|'[^']*')", re.I)
_DA_FRASE = frozenset({
    "b", "strong", "i", "em", "code", "kbd", "small", "abbr", "sup", "sub",
    "u", "mark", "q", "s", "wbr",
})
#: O valor do selo da linha (a 08: «Visto como <b>Xbox 360</b>», «Analógico virtual
#: <b>Apagado</b>») é peça própria: o `.gc-est .est` é `display:flex`, o `<b>` vira item do
#: flex e abre bloco, e a régua irmã (test_todo_texto_que_abre_uma_linha_comeca_com_maiuscula)
#: exige a maiúscula ali. As duas réguas leem o mesmo corte.
_VALOR_DO_SELO = re.compile(r'<span class="est(?: [^"]*)?"[^>]*>[^<]*(<b>)')
_ABA_DA_FITA = re.compile(r'<a class="aba[^"]*" href="\d\d-[^"]+">([^<]+)</a>')


def _de_um_csv(caminho: pathlib.Path, coluna: str) -> set[str]:
    linhas = [linha for linha in caminho.read_text(encoding="utf-8").splitlines()
              if linha.strip() and not linha.lstrip().startswith("#")]
    return {(r.get(coluna) or "").strip() for r in csv.DictReader(linhas)} - {""}


def nomes_de_cor() -> set[str]:
    """Os nomes de cor, lidos do CSV que é dono deles."""
    return _de_um_csv(CORES_CSV, "nome")


def nomes_das_abas(paginas: list[pathlib.Path]) -> set[str]:
    """Os nomes das dez abas, lidos da fita de abas das próprias páginas."""
    nomes: set[str] = set()
    for p in paginas:
        nomes |= {html.unescape(n).strip() for n in _ABA_DA_FITA.findall(
            p.read_text(encoding="utf-8"))}
    return nomes


def frases(pagina: str) -> list[tuple[int, str]]:
    """`(linha, frase)` de cada trecho que a pessoa lê, cortado onde um rótulo começa."""
    import check_a_maiuscula_decorativa as irma
    from hefesto_dualsense4unix.interface.frases_que_ela_baniu import (
        texto_visivel_no_produto,
    )

    tela = irma._so_a_tela(pagina)
    lido = texto_visivel_no_produto(tela)
    cortes: set[int] = set()
    for t in _TAG.finditer(tela):
        if t.group(2).lower() not in _DA_FRASE:
            cortes.add(t.start())
        for a in _ATRIBUTO_LIDO.finditer(t.group(0)):
            cortes.add(t.start() + a.start(1) + 1)
            cortes.add(t.start() + a.end(1) - 1)
    cortes.update(m.start(1) for m in _VALOR_DO_SELO.finditer(tela))
    fora: list[tuple[int, str]] = []
    inicio = 0
    for fim in sorted(cortes | {len(lido)}):
        trecho = " ".join(html.unescape(lido[inicio:fim]).split())
        if trecho:
            fora.append((tela.count("\n", 0, inicio) + 1, trecho))
        inicio = fim
    return fora


def _mascarar(frase: str, nomes: list[str]) -> str:
    """A frase com cada nome permitido trocado por espaço do mesmo tamanho."""
    for nome in nomes:
        frase = re.sub(rf"(?<![\w]){re.escape(nome)}(?![\w])",
                       lambda m: " " * len(m.group(0)), frase)
    return frase


def maiusculas_no_meio(frase: str, nomes: list[str]) -> list[str]:
    """As palavras desta frase com inicial maiúscula fora do começo, e sem licença."""
    limpa = _mascarar(frase, nomes)
    achadas: list[str] = []
    for m in _PALAVRA.finditer(limpa):
        p = m.group(0)
        if not p[0].isupper() or p.isupper() or any(c.isupper() for c in p[1:]):
            continue
        if p in MARCAS or p in TECLAS or p in UNIDADES:
            continue
        antes = limpa[:m.start()]
        if not antes.strip() or _INICIO.search(antes) or not re.search(r"[^\W\d_]", antes):
            continue
        if p in DESIGNADORES and re.match(r"\s+\d", limpa[m.end():]):
            continue
        achadas.append(p)
    return achadas


def licencas(paginas: list[pathlib.Path]) -> list[str]:
    """Os nomes que podem ter maiúscula no meio, o mais longo primeiro."""
    nomes = (nomes_de_cor() | nomes_das_abas(paginas) | set(NOMES_DO_DESENHO)
             | set(ROTULOS_CITADOS) | set(DIVIDA))
    return sorted(nomes, key=len, reverse=True)


def censo(paginas: list[pathlib.Path]) -> list[tuple[str, int, str, str]]:
    """`(página, linha, palavra, frase)` de cada maiúscula no meio sem licença."""
    nomes = licencas(paginas)
    achados = []
    for p in paginas:
        for linha, frase in frases(p.read_text(encoding="utf-8")):
            for palavra in maiusculas_no_meio(frase, nomes):
                achados.append((p.name, linha, palavra, frase))
    return achados


def rotulos_fantasmas(paginas: list[pathlib.Path]) -> list[str]:
    """Os `ROTULOS_CITADOS` que nenhuma página mostra inteiros, como rótulo ou opção."""
    fonte = "\n".join(html.unescape(p.read_text(encoding="utf-8")) for p in paginas)
    return [r for r in ROTULOS_CITADOS
            if not re.search(rf"[>\"]\s*{re.escape(r)}\s*[<\"]", fonte)]


def dividas_mortas(paginas: list[pathlib.Path]) -> list[str]:
    """As entradas da `DIVIDA` que nenhuma página escreve mais: a cura chegou, e a linha sai."""
    lido = " ".join(" ".join(f for _, f in frases(p.read_text(encoding="utf-8")))
                    for p in paginas)
    return [d for d in DIVIDA if not re.search(rf"(?<!\w){re.escape(d)}(?!\w)", lido)]


#: O que ainda sai com maiúscula no meio, e a origem não é desta régua.
DIVIDA: dict[str, str] = {}


def titulo_em_toda_palavra(paginas: list[pathlib.Path]) -> list[str]:
    """As páginas que trazem o JS que põe maiúscula em toda palavra na pintura."""
    return [p.name for p in paginas
            if TITULO_EM_TODA_PALAVRA.search(p.read_text(encoding="utf-8"))]


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    alvo = BANCADA if "--bancada" in argv else PUBLICADO
    abas = sorted(p for p in alvo.glob("*.html") if E_ABA.match(p.name))
    if len(abas) != 10:
        print(f"achei {len(abas)} abas em {alvo} — o caminho mudou?", file=sys.stderr)
        return 2
    faltam = [m for m in MAPAS if not (alvo / m).exists()]
    if faltam:
        print(f"faltam os mapas {faltam} em {alvo} — o caminho mudou?", file=sys.stderr)
        return 2
    mapas = [alvo / m for m in MAPAS]
    paginas = abas + mapas

    achados = censo(paginas)
    em_toda_palavra = titulo_em_toda_palavra(paginas)
    fantasmas = rotulos_fantasmas(paginas)
    mortas = dividas_mortas(paginas)
    por_palavra: dict[str, list[str]] = {}
    for nome, linha, palavra, frase in achados:
        por_palavra.setdefault(palavra, []).append(f"{nome}:{linha}  «{frase[:110]}»")

    for palavra in sorted(por_palavra, key=lambda k: (-len(por_palavra[k]), k)):
        lugares = por_palavra[palavra]
        print(f"  {palavra:<16} {len(lugares):>4}  {lugares[0]}")
    for r in fantasmas:
        print(f"  ROTULOS_CITADOS: «{r}» não é rótulo de página nenhuma — tire da lista.")
    for d in mortas:
        print(f"  DIVIDA: «{d}» não aparece mais em página nenhuma — a linha sai da lista.")
    for nome in em_toda_palavra:
        print(f"  {nome}: traz o JS que põe maiúscula em toda palavra na pintura — tire-o.")

    if "--lista" in argv:
        return 0
    if achados or fantasmas or mortas or em_toda_palavra:
        print(f"\nREPROVADO — {len(achados)} maiúscula(s) no meio da frase em "
              f"{alvo.relative_to(RAIZ)}.\n"
              "A regra dela (09/10/2026): só a primeira letra da frase ou do rótulo é\n"
              "maiúscula. Escreva em minúscula; se for nome próprio ou marca, declare\n"
              "na lista que tem o nome do que ela guarda, no topo desta régua.",
              file=sys.stderr)
        return 1
    print(f"OK: {len(abas)} abas e {len(mapas)} mapas de {alvo.relative_to(RAIZ)}, nenhuma maiúscula "
          "no meio da frase fora de nome próprio e marca.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
