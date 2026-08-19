"""LOADER-SVG-NOS-EMPACOTAMENTOS-01 — o `.deb`, o `.rpm`, o Arch e o Nix
declaram o loader SVG do gdk-pixbuf.

O DEFEITO, medido em 18/08/2026 e ainda vivo na manhã de 19/08:

    grep -rn "rsvg" packaging/ | grep -c "Depends\\|Requires\\|depends"  ->  0

Nenhum dos empacotamentos declarava o loader. E a interface DEPENDE dele em
execução, em dois lugares:

* ``gui/widgets/button_glyph.py`` carrega **38 glifos SVG** por
  ``GdkPixbuf.Pixbuf.new_from_file_at_scale`` (``ls assets/glyphs/*.svg | wc
  -l`` -> 38);
* ``app/tray.py`` pede o ícone simbólico da bandeja, que é SVG.

Sem o loader o pixbuf sai ``None`` **em silêncio** — e o estrago já está
escrito, com todas as letras, no próprio código que convive com ele
(``app/main.py``, BUG-TRAY-ICONE-INVISIVEL-01, 18/08/2026): *"o ícone some da
barra"* e *"qualquer SVG da interface cai junto"*. O install nativo passou a
garantir o pacote (DEPS-UNIVERSAIS-01); o ``.deb`` não garantia. A diferença
aparecia como ícone invisível — um sintoma que ninguém liga à causa.

ARMADILHA DE NOME, e ela já mordeu o CI desta casa: o pacote de EXECUÇÃO é o
**loader** (``librsvg2-common`` no Debian, o módulo
``libpixbufloader_svg.so``). O ``librsvg2-bin`` é o ``rsvg-convert``,
ferramenta de BUILD — é esse que o CI instala, e é o ERRADO para execução.
Por isso este arquivo não se contenta com "a palavra rsvg aparece": cobra o
nome certo, no campo certo, e REPROVA o nome de build no campo de execução.

E olha só o campo que o gerenciador de pacotes de fato LÊ — mesma lição do
portão do teclado na tela (10/08/2026): a primeira régua daquela seção
procurava a palavra no arquivo inteiro e passava VERDE com a dependência
arrancada, porque a palavra continuava viva na PROSA da ``Description``. Aqui
a prosa da ``Description`` do ``.deb`` de fato explica o porquê (em
``DEBIAN/control`` não existe comentário: o ``#`` faz o ``dpkg-deb`` ABORTAR
com *"campo de nome '#' precisa ser seguido de vírgula"*, medido em
19/08/2026) — então a régua tinha de ser de campo, ou nasceria decorativa.

PROVA DE QUE MORDE (19/08/2026), seis mutações — a saída literal, abreviada só
no meio da mensagem, que é a mesma nas quatro primeiras::

    1) `librsvg2-common` fora do Depends (a Description continua explicando!)
       E  AssertionError: packaging/debian/control não declara o loader SVG no
          campo que o gerenciador lê (esperado: librsvg2-common). [...]
       1 failed, 10 passed
    2) `Requires: librsvg2` fora do .spec (o comentário que o explica fica)
       E  AssertionError: packaging/fedora/hefesto-dualsense4unix.spec não
          declara o loader SVG no campo que o gerenciador lê [...]
       1 failed, 10 passed
    3) `'librsvg'` fora do depends do PKGBUILD
       E  AssertionError: packaging/arch/PKGBUILD não declara [...]
       1 failed, 10 passed
    4) `librsvg` fora dos buildInputs do Nix (o argumento continua declarado)
       E  AssertionError: packaging/nix/package.nix não declara [...]
       1 failed, 10 passed
    5) ARMADILHA DE NOME — Depends com `librsvg2-bin` no lugar do loader
       FAILED [...]::test_cada_empacotamento_declara_o_loader_svg[.../control]
       FAILED [...]::test_nenhum_empacotamento_pede_a_ferramenta_de_build[...]
       2 failed, 9 passed
    6) loader rebaixado de Depends para Recommends
       FAILED [...]::test_cada_empacotamento_declara_o_loader_svg[.../control]
       FAILED [...]::test_o_loader_e_dependencia_dura_e_nao_fraca
       2 failed, 9 passed

A mutação 1 é a que vale por todas: a explicação do porquê continuou inteira
na ``Description`` e o teste reprovou assim mesmo. É a régua de campo fazendo
o que a régua de arquivo inteiro não fazia.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]

#: O nome do loader em cada empacotamento. NÃO é o mesmo nome em toda parte, e
#: essa é justamente a armadilha: no Debian o pacote está partido em dois
#: (``librsvg2-common`` desenha, ``librsvg2-bin`` converte), no Fedora o
#: módulo vem no ``librsvg2`` (o ``librsvg2-tools`` é o ``rsvg-convert``) e no
#: Arch o ``librsvg`` traz as duas coisas. Mesma tabela do ``install.sh``.
LOADER = {
    "packaging/debian/control": "librsvg2-common",
    "packaging/fedora/hefesto-dualsense4unix.spec": "librsvg2",
    "packaging/arch/PKGBUILD": "librsvg",
    "packaging/nix/package.nix": "librsvg",
}

#: Os nomes de BUILD, que não podem aparecer no campo de execução de nenhum
#: empacotamento. Instalar o ``rsvg-convert`` no lugar do loader dá um verde
#: convincente e um ícone invisível.
FERRAMENTAS_DE_BUILD = ("librsvg2-bin", "librsvg2-tools")


def _campo_deb(texto: str, campo: str) -> str:
    """Devolve UM campo do ``DEBIAN/control``, com as continuações.

    Deb822: a continuação é a linha que começa com espaço. Parar no primeiro
    campo seguinte é o que mantém a ``Description`` (que é um campo como outro
    qualquer) FORA do resultado — sem isso a prosa satisfaria a régua.
    """
    linhas = texto.splitlines()
    coletando = False
    pedacos: list[str] = []
    for linha in linhas:
        if coletando:
            if linha.startswith((" ", "\t")):
                pedacos.append(linha.strip())
                continue
            break
        if linha.startswith(f"{campo}:"):
            coletando = True
            pedacos.append(linha.split(":", 1)[1].strip())
    return " ".join(pedacos)


def _sem_comentarios(texto: str, marca: str = "#") -> str:
    """Tira as linhas de comentário — um comentário que EXPLICA a regra não
    pode ser o que a satisfaz."""
    return "\n".join(
        linha
        for linha in texto.splitlines()
        if not linha.lstrip().startswith(marca)
    )


def _bloco(texto: str, abertura: str, fechamento: str) -> str:
    """Recorta o bloco entre ``abertura`` e o primeiro ``fechamento``.

    Os comentários saem ANTES do recorte, e isso não é zelo: o comentário que
    explica esta dependência cita ``new_from_file_at_scale)`` — um parêntese
    fechado que cortava o ``depends=(`` do PKGBUILD no meio e escondia o
    ``'librsvg'`` da régua. O primeiro rascunho deste arquivo reprovou por
    isso, com a dependência declarada.
    """
    limpo = _sem_comentarios(texto)
    inicio = limpo.find(abertura)
    if inicio < 0:
        return ""
    fim = limpo.find(fechamento, inicio)
    return limpo[inicio : fim if fim >= 0 else len(limpo)]


def _campo_de_execucao(caminho: str) -> str:
    """O trecho que o gerenciador de pacotes LÊ como dependência dura.

    Um por formato, porque a sintaxe é de cada um — e porque ler o arquivo
    inteiro é exatamente o erro que esta casa já pagou.
    """
    texto = (RAIZ / caminho).read_text(encoding="utf-8")
    if caminho.endswith("debian/control"):
        return _campo_deb(texto, "Depends")
    if caminho.endswith(".spec"):
        return "\n".join(
            linha
            for linha in _sem_comentarios(texto).splitlines()
            if linha.startswith("Requires:")
        )
    if caminho.endswith("PKGBUILD"):
        return _bloco(texto, "depends=(", ")")
    if caminho.endswith("package.nix"):
        return _bloco(texto, "buildInputs = [", "];")
    raise AssertionError(f"formato sem régua: {caminho}")


@pytest.mark.parametrize(("caminho", "pacote"), sorted(LOADER.items()))
def test_cada_empacotamento_declara_o_loader_svg(caminho: str, pacote: str) -> None:
    """Os quatro declaram o loader — no campo, não na prosa nem no comentário.

    MORDE: tirar ``librsvg2-common`` do ``Depends`` (deixando a explicação na
    ``Description``, que continua lá) reprova este teste.
    """
    campo = _campo_de_execucao(caminho)
    assert re.search(rf"(?<![\w-]){re.escape(pacote)}(?![\w-])", campo), (
        f"{caminho} não declara o loader SVG no campo que o gerenciador lê "
        f"(esperado: {pacote}). Sem ele o ícone da bandeja some e os 38 glifos "
        f"SVG da interface caem junto — BUG-TRAY-ICONE-INVISIVEL-01."
    )


@pytest.mark.parametrize("caminho", sorted(LOADER))
def test_nenhum_empacotamento_pede_a_ferramenta_de_build(caminho: str) -> None:
    """O ``rsvg-convert`` não é dependência de execução.

    Trocar ``librsvg2-common`` por ``librsvg2-bin`` no ``Depends`` instala o
    conversor e deixa o gdk-pixbuf sem loader: o pacote instala, a interface
    abre, e o ícone continua invisível.
    """
    campo = _campo_de_execucao(caminho)
    for ferramenta in FERRAMENTAS_DE_BUILD:
        assert not re.search(rf"(?<![\w-]){re.escape(ferramenta)}(?![\w-])", campo), (
            f"{caminho} pede {ferramenta} como dependência de EXECUÇÃO — esse é "
            f"o rsvg-convert, ferramenta de build. Quem desenha na tela é "
            f"{LOADER[caminho]}."
        )


def test_o_loader_e_dependencia_dura_e_nao_fraca() -> None:
    """Nada de ``Recommends``/``Suggests``/``optdepends`` para o loader.

    Diferente do teclado na tela, o produto NÃO funciona sem: a interface
    inteira perde os glifos e a bandeja perde o ícone. Dependência fraca aqui
    seria o mesmo verde mentiroso de antes, com mais texto.
    """
    control = (RAIZ / "packaging/debian/control").read_text(encoding="utf-8")
    for campo in ("Recommends", "Suggests"):
        assert "librsvg" not in _campo_deb(control, campo), (
            f"packaging/debian/control declara o loader SVG em {campo} — "
            "é dependência dura: sem ele a interface fica sem 38 glifos."
        )

    spec = _sem_comentarios(
        (RAIZ / "packaging/fedora/hefesto-dualsense4unix.spec").read_text(
            encoding="utf-8"
        )
    )
    assert not re.search(r"^(Recommends|Suggests):\s*librsvg", spec, re.MULTILINE), (
        "o .spec declara o loader SVG como dependência fraca — no RPM a fraca é "
        "IGNORADA em silêncio quando o pacote não está nos repositórios "
        "habilitados, e o defeito volta calado."
    )

    pkgbuild = (RAIZ / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
    assert "librsvg" not in _bloco(pkgbuild, "optdepends=(", ")"), (
        "o PKGBUILD declara o loader SVG em optdepends — é dependência dura."
    )


def test_flatpak_se_salva_pelo_runtime_e_isso_fica_registrado() -> None:
    """O Flatpak NÃO declara o loader, e está certo: o runtime já o traz.

    MEDIDO em 19/08/2026, no runtime que o manifesto fixa::

        $ R=~/.local/share/flatpak/runtime/org.gnome.Platform/x86_64/47/active/files
        $ ls $R/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders/ | grep svg
        libpixbufloader_svg.so
        $ grep -n svg $R/lib/x86_64-linux-gnu/gdk-pixbuf-2.0/2.10.0/loaders.cache
        46:".../loaders/libpixbufloader_svg.so"
        47:"svg" 6 "gdk-pixbuf" "Scalable Vector Graphics" "LGPL"

    O ``org.freedesktop.Platform`` (24.08 e 25.08) também o traz — medido no
    mesmo dia. Por isso a régua aceita os DOIS e só reprova um runtime de
    terceiro: aí a isenção deixa de estar medida e alguém tem de medir de novo
    antes de confiar nela.
    """
    manifesto = RAIZ / "flatpak/br.andrefarias.Hefesto.yml"
    texto = _sem_comentarios(manifesto.read_text(encoding="utf-8"))
    casamento = re.search(r"^runtime:\s*(\S+)", texto, re.MULTILINE)
    assert casamento, "o manifesto Flatpak não declara runtime"
    runtime = casamento.group(1).strip("\"'")
    assert runtime in ("org.gnome.Platform", "org.freedesktop.Platform"), (
        f"o Flatpak passou a usar o runtime {runtime}, e a isenção do loader "
        "SVG estava medida contra org.gnome.Platform//47 e "
        "org.freedesktop.Platform (19/08/2026). Meça o novo — "
        "`ls .../gdk-pixbuf-2.0/2.10.0/loaders/ | grep svg` — ou bundle o "
        "loader como módulo, do jeito que o wvkbd é bundlado."
    )


def test_o_nome_do_loader_casa_o_do_install_nativo() -> None:
    """Os empacotamentos e o instalador nativo pedem o MESMO pacote.

    Divergir aqui é o defeito de sempre com outra roupa: o install cura a
    máquina dela, o ``.deb`` cura a de outra pessoa, e as duas discordam sem
    ninguém ver. A tabela do ``install.sh`` (DEPS-UNIVERSAIS-01) é a fonte.
    """
    install = (RAIZ / "install.sh").read_text(encoding="utf-8")
    bloco = _bloco(install, '_apt="librsvg2-common"', "\n\n")
    assert bloco, (
        "install.sh não tem mais a linha do loader SVG na tabela de pacotes — "
        "se a tabela mudou de forma, esta régua tem de mudar junto, e não sumir."
    )
    esperado = {
        "_apt": LOADER["packaging/debian/control"],
        "_dnf": LOADER["packaging/fedora/hefesto-dualsense4unix.spec"],
        "_pacman": LOADER["packaging/arch/PKGBUILD"],
    }
    for variavel, pacote in esperado.items():
        casamento = re.search(rf'{variavel}="([^"]*)"', bloco)
        assert casamento and casamento.group(1) == pacote, (
            f"install.sh instala {casamento.group(1) if casamento else 'nada'} "
            f"para {variavel} e o empacotamento declara {pacote} — o instalador "
            "nativo e o pacote têm de pedir a mesma coisa."
        )
