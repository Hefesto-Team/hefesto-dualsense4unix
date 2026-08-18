#!/usr/bin/env python3
"""Portão de glifos do Hefesto - Dualsense4Unix: reprova emoji, preserva UI textual.

O critério vem do ADR-011 (``docs/adr/011-glyphs-vs-emojis.md``) e não de uma
lista de faixas escrita à mão:

- **Reprova** todo caractere com a propriedade Unicode ``Emoji_Presentation``
  (UTS #51), isto é, o que o padrão define como "desenha como emoji por
  omissão". Reprova também VARIATION SELECTOR-16 (U+FE0F), que existe só para
  forçar apresentação de emoji sobre um caractere de texto.
- **Preserva** os quatro blocos que o ADR-011 nomeia como UI textual funcional:
  Arrows (U+2190 a U+21FF), Box Drawing (U+2500 a U+257F), Block Elements
  (U+2580 a U+259F) e Geometric Shapes (U+25A0 a U+25FF).

A cláusula de preservação **não é decorativa**: os dois conjuntos se cruzam de
verdade. U+25FD e U+25FE são ``Emoji_Presentation`` **e** moram dentro de
Geometric Shapes. Sem a cláusula, o portão passaria a reprovar caractere que o
ADR-011 manda manter -- que é exatamente a inversão que o higienizador do
ambiente comete (sprint GATE-EMOJI-01).

Este portão **não reescreve arquivo nenhum**. Ele aponta e reprova; quem corrige
é a pessoa. A diferença entre isso e um higienizador é a diferença entre revisar
e ser reescrito.

Uso:
    scripts/validar-glifos.py --all
    scripts/validar-glifos.py --check-file caminho/arquivo.md
    scripts/validar-glifos.py arquivo1.py arquivo2.md
    scripts/validar-glifos.py --mostrar-criterio

Saída: uma linha por achado, no formato ``arquivo:linha:coluna: U+XXXX NOME``.
Código de saída 0 se limpo, 1 se houver achado.
"""
from __future__ import annotations

import argparse
import bisect
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

# ---------------------------------------------------------------------------
# Tabela GERADA, não chutada.
#
# Procedência: propriedade ``Emoji_Presentation`` de
# https://www.unicode.org/Public/UCD/latest/ucd/emoji/emoji-data.txt
# (UTS #51, Version 17.0, arquivo datado de 2025-07-25). São 1219 codepoints
# compactados em 81 faixas contíguas.
#
# Para regerar depois de uma revisão do Unicode:
#
#     curl -sS -o emoji-data.txt \
#       https://www.unicode.org/Public/UCD/latest/ucd/emoji/emoji-data.txt
#     python3 - <<'EOF'
#     cps = set()
#     for ln in open("emoji-data.txt", encoding="utf-8"):
#         ln = ln.split("#", 1)[0].strip()
#         if not ln:
#             continue
#         campo, prop = [x.strip() for x in ln.split(";")]
#         if prop != "Emoji_Presentation":
#             continue
#         if ".." in campo:
#             a, b = campo.split("..")
#             cps.update(range(int(a, 16), int(b, 16) + 1))
#         else:
#             cps.add(int(campo, 16))
#     # compacta em faixas e imprime como tuplas (0xINI, 0xFIM)
#     EOF
#
# Os nomes nos comentários saem de ``unicodedata.name``; onde aparece
# "não nomeado" o codepoint ainda não existia na tabela Unicode embutida no
# Python desta máquina (15.0) -- a faixa continua válida, só não tem nome local.
# ---------------------------------------------------------------------------
FAIXAS_EMOJI_PRESENTATION: tuple[tuple[int, int], ...] = (
    (0x231A, 0x231B),  # WATCH .. HOURGLASS
    (0x23E9, 0x23EC),  # BLACK RIGHT-POINTING DOUBLE TRIANGLE .. (idem, para baixo)
    (0x23F0, 0x23F0),  # ALARM CLOCK
    (0x23F3, 0x23F3),  # HOURGLASS WITH FLOWING SAND
    (0x25FD, 0x25FE),  # WHITE/BLACK MEDIUM SMALL SQUARE -- cruzam Geometric Shapes
    (0x2614, 0x2615),  # UMBRELLA WITH RAIN DROPS .. HOT BEVERAGE
    (0x2648, 0x2653),  # ARIES .. PISCES
    (0x267F, 0x267F),  # WHEELCHAIR SYMBOL
    (0x2693, 0x2693),  # ANCHOR
    (0x26A1, 0x26A1),  # HIGH VOLTAGE SIGN
    (0x26AA, 0x26AB),  # MEDIUM WHITE CIRCLE .. MEDIUM BLACK CIRCLE
    (0x26BD, 0x26BE),  # SOCCER BALL .. BASEBALL
    (0x26C4, 0x26C5),  # SNOWMAN WITHOUT SNOW .. SUN BEHIND CLOUD
    (0x26CE, 0x26CE),  # OPHIUCHUS
    (0x26D4, 0x26D4),  # NO ENTRY
    (0x26EA, 0x26EA),  # CHURCH
    (0x26F2, 0x26F3),  # FOUNTAIN .. FLAG IN HOLE
    (0x26F5, 0x26F5),  # SAILBOAT
    (0x26FA, 0x26FA),  # TENT
    (0x26FD, 0x26FD),  # FUEL PUMP
    (0x2705, 0x2705),  # WHITE HEAVY CHECK MARK -- citado no ADR-011 como proibido
    (0x270A, 0x270B),  # RAISED FIST .. RAISED HAND
    (0x2728, 0x2728),  # SPARKLES
    (0x274C, 0x274C),  # CROSS MARK -- citado no ADR-011 como proibido
    (0x274E, 0x274E),  # NEGATIVE SQUARED CROSS MARK
    (0x2753, 0x2755),  # BLACK QUESTION MARK ORNAMENT .. WHITE EXCLAMATION ORNAMENT
    (0x2757, 0x2757),  # HEAVY EXCLAMATION MARK SYMBOL
    (0x2795, 0x2797),  # HEAVY PLUS SIGN .. HEAVY DIVISION SIGN
    (0x27B0, 0x27B0),  # CURLY LOOP
    (0x27BF, 0x27BF),  # DOUBLE CURLY LOOP
    (0x2B1B, 0x2B1C),  # BLACK LARGE SQUARE .. WHITE LARGE SQUARE
    (0x2B50, 0x2B50),  # WHITE MEDIUM STAR -- o que está vivo no repositório hoje
    (0x2B55, 0x2B55),  # HEAVY LARGE CIRCLE
    (0x1F004, 0x1F004),  # MAHJONG TILE RED DRAGON
    (0x1F0CF, 0x1F0CF),  # PLAYING CARD BLACK JOKER
    (0x1F18E, 0x1F18E),  # NEGATIVE SQUARED AB
    (0x1F191, 0x1F19A),  # SQUARED CL .. SQUARED VS
    (0x1F1E6, 0x1F1FF),  # REGIONAL INDICATOR SYMBOL LETTER A .. LETTER Z
    (0x1F201, 0x1F201),  # SQUARED KATAKANA KOKO
    (0x1F21A, 0x1F21A),  # SQUARED CJK UNIFIED IDEOGRAPH-7121
    (0x1F22F, 0x1F22F),  # SQUARED CJK UNIFIED IDEOGRAPH-6307
    (0x1F232, 0x1F236),  # SQUARED CJK UNIFIED IDEOGRAPH-7981 .. -6709
    (0x1F238, 0x1F23A),  # SQUARED CJK UNIFIED IDEOGRAPH-7533 .. -55B6
    (0x1F250, 0x1F251),  # CIRCLED IDEOGRAPH ADVANTAGE .. ACCEPT
    (0x1F300, 0x1F320),  # CYCLONE .. SHOOTING STAR
    (0x1F32D, 0x1F335),  # HOT DOG .. CACTUS
    (0x1F337, 0x1F37C),  # TULIP .. BABY BOTTLE
    (0x1F37E, 0x1F393),  # BOTTLE WITH POPPING CORK .. GRADUATION CAP
    (0x1F3A0, 0x1F3CA),  # CAROUSEL HORSE .. SWIMMER
    (0x1F3CF, 0x1F3D3),  # CRICKET BAT AND BALL .. TABLE TENNIS PADDLE AND BALL
    (0x1F3E0, 0x1F3F0),  # HOUSE BUILDING .. EUROPEAN CASTLE
    (0x1F3F4, 0x1F3F4),  # WAVING BLACK FLAG
    (0x1F3F8, 0x1F43E),  # BADMINTON RACQUET AND SHUTTLECOCK .. PAW PRINTS
    (0x1F440, 0x1F440),  # EYES
    (0x1F442, 0x1F4FC),  # EAR .. VIDEOCASSETTE
    (0x1F4FF, 0x1F53D),  # PRAYER BEADS .. DOWN-POINTING SMALL RED TRIANGLE
    (0x1F54B, 0x1F54E),  # KAABA .. MENORAH WITH NINE BRANCHES
    (0x1F550, 0x1F567),  # CLOCK FACE ONE OCLOCK .. CLOCK FACE TWELVE-THIRTY
    (0x1F57A, 0x1F57A),  # MAN DANCING
    (0x1F595, 0x1F596),  # dois gestos de mão
    (0x1F5A4, 0x1F5A4),  # BLACK HEART
    (0x1F5FB, 0x1F64F),  # MOUNT FUJI .. PERSON WITH FOLDED HANDS
    (0x1F680, 0x1F6C5),  # ROCKET .. LEFT LUGGAGE
    (0x1F6CC, 0x1F6CC),  # SLEEPING ACCOMMODATION
    (0x1F6D0, 0x1F6D2),  # PLACE OF WORSHIP .. SHOPPING TROLLEY
    (0x1F6D5, 0x1F6D8),  # HINDU TEMPLE .. (parte não nomeada no Unicode 15.0)
    (0x1F6DC, 0x1F6DF),  # WIRELESS .. RING BUOY
    (0x1F6EB, 0x1F6EC),  # AIRPLANE DEPARTURE .. AIRPLANE ARRIVING
    (0x1F6F4, 0x1F6FC),  # SCOOTER .. ROLLER SKATE
    (0x1F7E0, 0x1F7EB),  # LARGE ORANGE CIRCLE .. LARGE BROWN SQUARE
    (0x1F7F0, 0x1F7F0),  # HEAVY EQUALS SIGN
    (0x1F90C, 0x1F93A),  # PINCHED FINGERS .. FENCER
    (0x1F93C, 0x1F945),  # WRESTLERS .. GOAL NET
    (0x1F947, 0x1F9FF),  # FIRST PLACE MEDAL .. NAZAR AMULET
    (0x1FA70, 0x1FA7C),  # BALLET SHOES .. CRUTCH
    (0x1FA80, 0x1FA8A),  # YO-YO .. (parte não nomeada no Unicode 15.0)
    (0x1FA8E, 0x1FAC6),  # (não nomeados no Unicode 15.0)
    (0x1FAC8, 0x1FAC8),  # (não nomeado no Unicode 15.0)
    (0x1FACD, 0x1FADC),  # (não nomeados no Unicode 15.0)
    (0x1FADF, 0x1FAEA),  # (não nomeados no Unicode 15.0)
    (0x1FAEF, 0x1FAF8),  # (parte não nomeada) .. RIGHTWARDS PUSHING HAND
)

# ---------------------------------------------------------------------------
# ADR-011, seção "Decisão", item "Permitidos". São os quatro blocos de UI
# textual funcional. Apagá-los já quebrou a GUI em 21/04/2026 (indicadores de
# estado Pango) e o BatteryMeter da TUI; ver
# docs/history/glyph-strip-regression-2026-04-23.diff.
# ---------------------------------------------------------------------------
BLOCOS_PRESERVADOS_ADR_011: tuple[tuple[int, int, str], ...] = (
    (0x2190, 0x21FF, "Arrows"),
    (0x2500, 0x257F, "Box Drawing"),
    (0x2580, 0x259F, "Block Elements"),
    (0x25A0, 0x25FF, "Geometric Shapes"),
)

# VARIATION SELECTOR-16: não desenha nada sozinho, só força a forma emoji do
# caractere anterior. Quem escreve isso quer emoji, então o portão reprova o
# próprio seletor -- e ele não mora em nenhum dos quatro blocos preservados,
# logo a cláusula de preservação não conflita com esta regra.
VARIATION_SELECTOR_16 = 0xFE0F

_INICIOS = [ini for ini, _fim in FAIXAS_EMOJI_PRESENTATION]
_FINS = [fim for _ini, fim in FAIXAS_EMOJI_PRESENTATION]


def tem_apresentacao_emoji(cp: int) -> bool:
    """True se ``cp`` tem a propriedade Unicode ``Emoji_Presentation``."""
    i = bisect.bisect_right(_INICIOS, cp) - 1
    return i >= 0 and cp <= _FINS[i]


def preservado_pelo_adr_011(cp: int) -> tuple[bool, str]:
    """True se ``cp`` está em um dos quatro blocos que o ADR-011 manda manter."""
    for ini, fim, nome in BLOCOS_PRESERVADOS_ADR_011:
        if ini <= cp <= fim:
            return True, nome
    return False, ""


def e_proibido(cp: int) -> bool:
    """Critério do portão para um único codepoint.

    A ordem importa e é a do ADR-011: a preservação é consultada **antes** da
    proibição, porque os dois conjuntos se cruzam em U+25FD e U+25FE.
    """
    # CLAUSULA-ADR-011-PRESERVA: bloco permitido vence a proibição. Arrancar
    # estas duas linhas faz o portão reprovar U+25FD e U+25FE, que são
    # Geometric Shapes e o ADR-011 manda preservar. O teste
    # tests/unit/test_validar_glifos.py arranca esta cláusula de propósito para
    # provar que ela morde.
    if preservado_pelo_adr_011(cp)[0]:
        return False
    if cp == VARIATION_SELECTOR_16:
        return True
    return tem_apresentacao_emoji(cp)


def nome_do_codepoint(cp: int) -> str:
    """Nome Unicode, com recuo elegante quando a tabela local não conhece."""
    if cp == VARIATION_SELECTOR_16:
        return "VARIATION SELECTOR-16 (força apresentação de emoji)"
    sem_nome = f"sem nome na tabela Unicode do Python ({unicodedata.unidata_version})"
    return unicodedata.name(chr(cp), sem_nome)


# ---------------------------------------------------------------------------
# Paths ignorados. Mesma família de exclusões dos outros portões da casa
# (ver scripts/validar-acentuacao.py), menos as isenções de conteúdo: emoji é
# proibido em qualquer arquivo de texto, inclusive fixture, CHANGELOG e
# registro histórico. Aqui só saem diretórios de máquina e binários.
# ---------------------------------------------------------------------------
PADROES_IGNORADOS: list[str] = [
    r"^\.git/",
    r"^\.venv/",
    r"^venv/",
    r"^node_modules/",
    r"^build/",
    r"^dist/",
    r"(^|/)__pycache__/",
    r"(^|/)\.mypy_cache/",
    r"(^|/)\.pytest_cache/",
    r"(^|/)\.ruff_cache/",
    r"\.pyc$",
    r"\.png$",
    r"\.jpe?g$",
    r"\.gif$",
    r"\.ico$",
    r"\.pdf$",
    r"\.zip$",
    r"\.gz$",
    r"\.xz$",
    r"\.zst$",
    r"\.deb$",
    r"\.bin$",
    r"\.mo$",
    r"\.woff2?$",
    r"\.ttf$",
    r"\.otf$",
    r"\.so$",
    r"\.ko$",
    r"\.o$",
    r"\.AppImage$",
]
_IGNORADOS_RE = [re.compile(p) for p in PADROES_IGNORADOS]

# Arquivo de texto acima disto é quase certamente dado, não prosa. Evita ler
# captura HID gigante para dentro da memória.
LIMITE_BYTES = 8 * 1024 * 1024


def e_ignorado(rel_path: str) -> bool:
    rel = rel_path.replace("\\", "/")
    return any(pat.search(rel) for pat in _IGNORADOS_RE)


def _relativo(path: Path, raiz: Path) -> str:
    try:
        return str(path.resolve().relative_to(raiz))
    except ValueError:
        return str(path)


def checar_arquivo(path: Path, raiz: Path) -> list[tuple[int, int, int]]:
    """Retorna lista de ``(linha, coluna, codepoint)``, ambos 1-based."""
    rel = _relativo(path, raiz)
    if e_ignorado(rel):
        return []
    try:
        if path.stat().st_size > LIMITE_BYTES:
            return []
        dados = path.read_bytes()
    except OSError:
        return []
    # Binário: NUL byte ou não decodifica como UTF-8. Nos dois casos não é
    # texto do projeto e não faz sentido cobrar glifo dele.
    if b"\x00" in dados:
        return []
    try:
        conteudo = dados.decode("utf-8")
    except UnicodeDecodeError:
        return []

    achados: list[tuple[int, int, int]] = []
    # ``split`` e não ``splitlines``: splitlines também quebra em U+000B,
    # U+000C, U+0085, U+2028 e U+2029, o que desloca a numeração das linhas em
    # relação ao que o editor e o git mostram. O mesmo defeito está registrado
    # na sprint GATE-EMOJI-01 sobre o higienizador do ambiente.
    for n, linha in enumerate(conteudo.split("\n"), start=1):
        for col, ch in enumerate(linha, start=1):
            cp = ord(ch)
            if cp < 0x80:
                continue
            if e_proibido(cp):
                achados.append((n, col, cp))
    return achados


def listar_arquivos_git(raiz: Path) -> list[Path]:
    """Lista os arquivos versionados **e** os novos ainda não adicionados.

    ``git ls-files -z`` puro é cego a arquivo novo: o portão passaria verde
    justamente no arquivo que a pessoa acabou de escrever, que é quando o erro
    entra. ``--cached --others --exclude-standard`` cobre rastreado e não
    rastreado, respeitando o ``.gitignore``.
    """
    try:
        out = subprocess.check_output(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=str(raiz),
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []
    arquivos: list[Path] = []
    vistos: set[str] = set()
    for nome in out.split("\x00"):
        if not nome or nome in vistos:
            continue
        vistos.add(nome)
        p = raiz / nome
        if p.is_file():
            arquivos.append(p)
    return arquivos


def descobrir_raiz() -> Path:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
        return Path(out)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd()


def _imprimir_criterio() -> None:
    print("Proibido: propriedade Unicode Emoji_Presentation (UTS #51, 17.0)")
    print(f"  {len(FAIXAS_EMOJI_PRESENTATION)} faixas, "
          f"{sum(f - i + 1 for i, f in FAIXAS_EMOJI_PRESENTATION)} codepoints")
    print(f"  mais U+{VARIATION_SELECTOR_16:04X} {nome_do_codepoint(VARIATION_SELECTOR_16)}")
    print("Preservado (ADR-011): os quatro blocos de UI textual funcional")
    for ini, fim, nome in BLOCOS_PRESERVADOS_ADR_011:
        print(f"  U+{ini:04X} a U+{fim:04X}  {nome}")
    cruzam = [
        cp
        for ini, fim, _ in BLOCOS_PRESERVADOS_ADR_011
        for cp in range(ini, fim + 1)
        if tem_apresentacao_emoji(cp)
    ]
    print("Interseção dos dois conjuntos (a cláusula de preservação existe por eles):")
    for cp in cruzam:
        print(f"  U+{cp:04X} {nome_do_codepoint(cp)}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portão de glifos (ADR-011).")
    grp = parser.add_mutually_exclusive_group()
    grp.add_argument(
        "--all",
        action="store_true",
        help="Varre o repositório inteiro (rastreados e novos ainda não adicionados)",
    )
    grp.add_argument(
        "--check-file",
        metavar="PATH",
        help="Varre um único arquivo (modo pre-commit)",
    )
    grp.add_argument(
        "--mostrar-criterio",
        action="store_true",
        help="Imprime o critério (faixas proibidas, blocos preservados) e sai",
    )
    parser.add_argument("paths", nargs="*", type=Path, help="Arquivos a varrer")
    args = parser.parse_args(argv)

    if args.mostrar_criterio:
        _imprimir_criterio()
        return 0

    raiz = descobrir_raiz()

    if args.check_file:
        alvos = [Path(args.check_file)]
    elif args.all or not args.paths:
        alvos = listar_arquivos_git(raiz)
    else:
        alvos = []
        for p in args.paths:
            if p.is_dir():
                alvos.extend(q for q in p.rglob("*") if q.is_file())
            else:
                alvos.append(p)

    total = 0
    for arq in alvos:
        for linha, coluna, cp in checar_arquivo(arq, raiz):
            rel = _relativo(arq, raiz)
            print(f"{rel}:{linha}:{coluna}: U+{cp:04X} {nome_do_codepoint(cp)}")
            total += 1

    if total:
        print(
            f"\n{total} glifo(s) de apresentação emoji encontrado(s). "
            "O ADR-011 os proíbe; os quatro blocos de UI textual continuam "
            "permitidos. Se o caractere for mesmo necessário em código ou "
            "teste, escreva-o como chr(0x...) para que nenhuma ferramenta o "
            "apague em silêncio.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
