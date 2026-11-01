"""Portão das licenças: o LICENSE é a GPL-3.0 canônica, o NOTICE é dono da ressalva, e o"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
_P = "e" + "la"

LICENSE = REPO / "LICENSE"
NOTICE = REPO / "NOTICE"
LICENSES = REPO / "LICENSES"

SHA256_GPL2 = "8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643"
SHA256_GPL3 = "3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986"

LICENCA_DO_HEFESTO = "GPL-3.0-or-later"

DECLARACOES_DA_LICENCA = [
    ("pyproject.toml", r'^license = "([^"]+)"$', LICENCA_DO_HEFESTO),
    (
        "pyproject.toml",
        r'^\s*"(License :: [^"]+)",?$',
        "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
    ),
    ("packaging/arch/PKGBUILD", r"^license=\((.+)\)$", f"'{LICENCA_DO_HEFESTO}'"),
    (
        "packaging/fedora/hefesto-dualsense4unix.spec",
        r"^License:\s+(\S.*?)\s*$",
        LICENCA_DO_HEFESTO,
    ),
    ("packaging/nix/package.nix", r"^\s*license = (.+?);$", "licenses.gpl3Plus"),
    (
        "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.metainfo.xml",
        r"<project_license>([^<]*)</project_license>",
        LICENCA_DO_HEFESTO,
    ),
]

MANIFESTOS_DE_FABRICA = REPO / "src" / "hefesto_dualsense4unix" / "mods" / "de_fabrica"

ALVOS_QUE_COPIAM_DKMS = [
    "scripts/build_deb.sh",
    "packaging/arch/PKGBUILD",
    "packaging/fedora/hefesto-dualsense4unix.spec",
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml",
]


COPIA_DE_LICENSES = re.compile(
    r"\b(?:cp|install|rsync)\b[^\n]*?(?<![\w./-])LICENSES(?:/\S*)?\s+(\S+)"
)

COMENTARIO = re.compile(r"(?<!\S)#.*$")

CONTINUACAO = re.compile(r"\\\n\s*")


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _linhas_executaveis(texto: str) -> list[str]:
    """As linhas que a máquina executa: continuações juntadas, comentário fora."""
    inteiro = CONTINUACAO.sub(" ", texto)
    linhas = []
    for linha in inteiro.splitlines():
        sem_comentario = COMENTARIO.sub("", linha)
        if sem_comentario.strip():
            linhas.append(sem_comentario)
    return linhas


def test_license_comeca_na_gpl3_sem_nada_antes() -> None:
    """A primeira linha do LICENSE é o título da GPL-3.0, sem nada antes dele."""
    linhas = _texto(LICENSE).splitlines()
    assert linhas, "LICENSE vazio"
    assert linhas[0].strip() == "GNU GENERAL PUBLIC LICENSE", (
        f"a primeira linha do LICENSE é {linhas[0]!r}, e tinha de ser o título da GPL. "
        "Decisão de produto de 07/08/2026 (resposta 4): nada antes do texto da licença. "
        "Ressalva de escopo vai para o NOTICE, seção 'ESCOPO DESTE ARQUIVO'."
    )


def test_license_nao_carrega_mais_bloco_de_escopo() -> None:
    """Nenhuma ressalva de escopo pode voltar para o LICENSE."""
    texto = _texto(LICENSE)
    for proibido in ("ESCOPO", "assets/dkms", "SPDX", "GPL-2.0"):
        assert proibido not in texto, (
            f"o LICENSE voltou a citar {proibido!r}. A ressalva de escopo tem dono "
            "desde 07/08/2026, e é o NOTICE."
        )


def test_license_e_a_gpl3_canonica_byte_a_byte() -> None:
    """O LICENSE é o texto da GPL-3.0 da FSF, sem resumo, tradução nem edição."""
    digest = hashlib.sha256(LICENSE.read_bytes()).hexdigest()
    assert digest == SHA256_GPL3, (
        f"o LICENSE tem SHA-256 {digest}, e a GPL-3.0 canônica é {SHA256_GPL3} "
        "(/usr/share/common-licenses/GPL-3, gnu.org/licenses/gpl-3.0.txt)."
    )
    assert "Version 3, 29 June 2007" in _texto(LICENSE)


@pytest.mark.parametrize(("arquivo", "padrão", "esperado"), DECLARACOES_DA_LICENCA)
def test_toda_declaracao_da_licenca_do_hefesto_diz_gpl3(
    arquivo: str, padrão: str, esperado: str
) -> None:
    """Cada empacotamento declara a licença do Hefesto num lugar só, e é a GPL-3.0."""
    achados = re.findall(padrão, _texto(REPO / arquivo), flags=re.MULTILINE)
    assert achados, f"{arquivo} não declara mais a licença do Hefesto ({padrão!r})"
    assert set(achados) == {esperado}, (
        f"{arquivo} declara {achados}, e a licença do Hefesto é {esperado!r}"
    )


def test_todo_manifesto_de_fabrica_diz_gpl3() -> None:
    """A lista sai do disco: um manifesto de fábrica novo entra na régua sozinho."""
    manifestos = sorted(MANIFESTOS_DE_FABRICA.glob("*/hefesto-mod.json"))
    assert len(manifestos) >= 3, f"a leitura de {MANIFESTOS_DE_FABRICA} parou de achar manifestos"
    errados = {
        str(m.relative_to(REPO)): licenca
        for m in manifestos
        if (licenca := json.loads(_texto(m)).get("licenca")) != LICENCA_DO_HEFESTO
    }
    assert not errados, f"manifestos de fábrica fora da licença do Hefesto: {errados}"


def test_o_readme_diz_gpl3_no_selo_e_na_secao() -> None:
    readme = _texto(REPO / "README.md")
    selo = re.search(r"\[!\[Licença\]\(https://img\.shields\.io/badge/([^)]+)\)\]", readme)
    assert selo and "GPL--3.0--or--later" in selo.group(1) and "MIT" not in selo.group(1), (
        f"o selo de licença do README não diz GPL-3.0-or-later: {selo and selo.group(1)!r}"
    )
    secao = readme.split("## Licença", 1)[1].lstrip()
    assert secao.startswith(LICENCA_DO_HEFESTO), (
        f"a seção Licença do README não abre com {LICENCA_DO_HEFESTO}: {secao[:60]!r}"
    )


def test_o_notice_diz_o_or_later_e_guarda_a_origem_mit() -> None:
    """O LICENSE não diz versão; o "or later" e o aviso MIT de origem moram no NOTICE."""
    texto = _texto(NOTICE)
    for trecho in (
        "either version 3 of the License, or",
        "(at your option) any later version.",
        "A origem MIT",
        "até a 0.9.5.1 saíram sob a licença MIT",
        "Copyright (c) 2026 Hefesto Contributors",
        "Permission is hereby granted, free of charge",
        "The above copyright notice and this permission notice shall be included",
        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
    ):
        assert trecho in texto, f"o NOTICE perdeu {trecho!r}"


def test_notice_tem_a_secao_de_escopo() -> None:
    texto = _texto(NOTICE)
    assert "ESCOPO DESTE ARQUIVO" in texto, (
        "o NOTICE perdeu a seção 'ESCOPO DESTE ARQUIVO'. A seção é a dona da ressalva "
        "desde 07/08/2026, e sem a seção a ressalva sumiu do repositório inteiro."
    )


@pytest.mark.parametrize(
    ("módulo", "licença"),
    [
        ("assets/dkms/hid-nintendo/", "GPL-2.0-or-later"),
        ("assets/dkms/hid-playstation/", "GPL-2.0-or-later"),
        ("assets/dkms/rtw88-usb/", "GPL-2.0 OR BSD-3-Clause"),
        ("assets/dkms/uhid/", "GPL-2.0-or-later"),
    ],
)
def test_notice_nomeia_cada_módulo_com_a_licença_dele(módulo: str, licença: str) -> None:
    """Cada linha que o bloco do LICENSE dizia tem de estar no NOTICE."""
    texto = _texto(NOTICE)
    assert módulo in texto, f"o NOTICE não nomeia {módulo}"
    janela = texto[texto.index(módulo) : texto.index(módulo) + 200]
    assert licença in janela, (
        f"o NOTICE nomeia {módulo} mas não diz {licença!r} junto dele. "
        "A licença e o diretório não podem se separar."
    )


_SPDX_DO_FONTE = re.compile(r"SPDX-License-Identifier:\s*(.+?)\s*(?:\*/)?\s*$")


def _spdx_normalizado(expressao: str) -> str:
    """`GPL-2.0+` é a grafia antiga de `GPL-2.0-or-later`; o NOTICE usa a nova."""
    return re.sub(r"\bGPL-2\.0\+", "GPL-2.0-or-later", expressao.strip())


def _modulos_de_assets_dkms() -> dict[str, set[str]]:
    """Cada diretório de `assets/dkms/`, com as licenças SPDX dos `.c` dele."""
    modulos: dict[str, set[str]] = {}
    for pasta in sorted((REPO / "assets" / "dkms").iterdir()):
        if not pasta.is_dir():
            continue
        licencas = set()
        for fonte in sorted(pasta.glob("*.c")):
            primeira = fonte.read_text(encoding="utf-8").splitlines()[0]
            achado = _SPDX_DO_FONTE.search(primeira)
            if achado:
                licencas.add(_spdx_normalizado(achado.group(1)))
        modulos[pasta.name] = licencas
    return modulos


def test_notice_e_o_readme_declaram_todo_modulo_de_assets_dkms() -> None:
    """A lista sai do disco, e não de uma tabela digitada: um módulo novo em"""
    modulos = _modulos_de_assets_dkms()
    assert len(modulos) >= 4 and all(modulos.values()), (
        f"a leitura de assets/dkms/ parou de achar módulos ou SPDX: {modulos}"
    )
    notice = _texto(NOTICE)
    readme = _texto(REPO / "README.md")
    assert "## Licença" in readme, "o README perdeu a seção de licença"
    licenca_do_readme = readme.split("## Licença", 1)[1]

    faltas = []
    for nome, licencas in modulos.items():
        endereco = f"assets/dkms/{nome}/"
        if endereco not in notice:
            faltas.append(f"o NOTICE não nomeia {endereco}")
        else:
            inicio = notice.index(endereco)
            janela = notice[inicio : inicio + 200]
            faltas += [
                f"o NOTICE nomeia {endereco} sem a licença {licenca!r} do fonte"
                for licenca in sorted(licencas)
                if licenca not in janela
            ]
        if f"`{nome}`" not in licenca_do_readme:
            faltas.append(f"a seção Licença do README não nomeia `{nome}`")
    assert not faltas, "\n".join(faltas)


def test_notice_diz_que_o_spdx_nao_pode_ser_removido() -> None:
    """A frase que sustenta a licitude do uso não pode ter ficado para trás."""
    texto = _texto(NOTICE)
    assert "não podem" in texto and "SPDX" in texto, (
        "o NOTICE perdeu a afirmação de que os cabeçalhos SPDX valem como licença "
        "e não podem ser removidos"
    )


_DIARIO_NO_NOTICE = re.compile(
    r"nota datada|decis[ãa]o d" + _P + r"|docs/process|d" + _P + r"|sprints?"
    r"|\b[A-Z]{2,}(?:-[A-Z0-9]+)*-[0-9]{2}\b",
    re.IGNORECASE,
)


def test_notice_so_carrega_a_atribuicao() -> None:
    """O NOTICE é lido por quem redistribui: ele diz o que é de terceiros, de"""
    achados = [
        f"{numero}: {linha.strip()}"
        for numero, linha in enumerate(_texto(NOTICE).splitlines(), start=1)
        if _DIARIO_NO_NOTICE.search(linha)
    ]
    assert not achados, (
        "o NOTICE voltou a carregar diário em vez de atribuição:\n  "
        + "\n  ".join(achados)
    )


def test_gpl2_existe_e_e_byte_a_byte_o_canonico() -> None:
    """O texto da GPL-2.0 não pode ter sido reescrito, resumido nem traduzido."""
    alvo = LICENSES / "GPL-2.0.txt"
    assert alvo.is_file(), (
        "LICENSES/GPL-2.0.txt sumiu. A GPL-2.0, seção 1, exige que a cópia do "
        "texto acompanhe o fonte, e cinco alvos de empacotamento distribuem "
        "assets/dkms/."
    )
    digest = hashlib.sha256(alvo.read_bytes()).hexdigest()
    assert digest == SHA256_GPL2, (
        f"LICENSES/GPL-2.0.txt tem SHA-256 {digest}, e o canônico é {SHA256_GPL2}. "
        "O arquivo foi modificado — texto de licença não se edita."
    )


def test_gpl2_e_mesmo_a_versao_2() -> None:
    texto = _texto(LICENSES / "GPL-2.0.txt")
    assert "GNU GENERAL PUBLIC LICENSE" in texto
    assert "Version 2, June 1991" in texto


def test_bsd3_existe_com_as_tres_clausulas_e_o_disclaimer() -> None:
    """O rtw88-usb é licença DUPLA; mandar só a GPL cobre metade da escolha."""
    alvo = LICENSES / "BSD-3-Clause.txt"
    assert alvo.is_file(), (
        "LICENSES/BSD-3-Clause.txt sumiu — e com ele metade da licença dupla do "
        "assets/dkms/rtw88-usb/"
    )
    texto = _texto(alvo)
    for clausula in (
        "1. Redistributions of source code must retain",
        "2. Redistributions in binary form must reproduce",
        "3. Neither the name of the copyright holder nor the names of its contributors",
        "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS",
    ):
        assert clausula in texto, f"BSD-3-Clause.txt perdeu: {clausula!r}"


def test_readme_das_licencas_declara_procedencia_de_cada_texto() -> None:
    """Texto de licença sem procedência é texto que ninguém pode conferir."""
    texto = _texto(LICENSES / "README.md")
    assert SHA256_GPL2 in texto, "o LICENSES/README.md não registra o SHA-256 da GPL-2.0"
    assert "/usr/share/common-licenses/GPL-2" in texto, (
        "o LICENSES/README.md não diz de ONDE o texto da GPL-2.0 veio"
    )
    assert "BSD-3-Clause" in texto


def test_notice_aponta_para_os_textos_das_licencas() -> None:
    """O NOTICE é a porta de entrada: ele tem de dizer onde os textos moram."""
    texto = _texto(NOTICE)
    for caminho in ("LICENSES/GPL-2.0.txt", "LICENSES/BSD-3-Clause.txt"):
        assert caminho in texto, f"o NOTICE não aponta para {caminho}"


@pytest.mark.parametrize("alvo", ALVOS_QUE_COPIAM_DKMS)
def test_alvo_que_copia_dkms_copia_licenses_junto(alvo: str) -> None:
    """Quem leva o fonte GPL leva o texto da licença junto, ou não leva nada."""
    conteudo = _texto(REPO / alvo)
    assert "assets/dkms/" in conteudo, (
        f"{alvo} não copia mais assets/dkms/ — se isso é intencional, esta "
        "entrada tem de sair da lista ALVOS_QUE_COPIAM_DKMS junto"
    )

    copias = [
        (linha, achado)
        for linha in _linhas_executaveis(conteudo)
        if (achado := COPIA_DE_LICENSES.search(linha))
    ]
    assert copias, (
        f"{alvo} copia os fontes GPL de assets/dkms/ mas NÃO copia LICENSES/. "
        "A GPL-2.0, seção 1, exige que a cópia da licença acompanhe o fonte. "
        "Citar LICENSES em comentário não conta: o portão cobra um comando de "
        "cópia com LICENSES na origem e um destino depois dele."
    )
    for linha, achado in copias:
        destino = achado.group(1)
        assert "/" in destino, (
            f"{alvo} tem uma cópia de LICENSES sem destino de instalação "
            f"reconhecível: {linha.strip()!r}. O texto da licença tem de pousar "
            "dentro do pacote, junto do fonte que ele cobre."
        )


def _o_que_o_sdist_leva() -> list[str] | None:
    """As entradas do `only-include` do sdist, ou None sem a lista (o hatchling"""
    pyproject = _texto(REPO / "pyproject.toml")
    marca = "[tool.hatch.build.targets.sdist]"
    if marca not in pyproject:
        return None
    secao = pyproject.split(marca, 1)[1].split("\n[", 1)[0]
    lista = re.search(r"only-include\s*=\s*\[([^\]]*)\]", secao)
    return re.findall(r'"([^"]+)"', lista.group(1)) if lista else None


def _o_sdist_leva_assets_dkms() -> bool:
    entradas = _o_que_o_sdist_leva()
    if entradas is None:
        return True
    return any("assets/dkms/".startswith(e.rstrip("/") + "/") for e in entradas)


def test_sdist_carrega_licenses_sem_precisar_de_linha() -> None:
    """O sdist que levar os fontes GPL de `assets/dkms/` leva `LICENSES/` junto."""
    entradas = _o_que_o_sdist_leva()
    if _o_sdist_leva_assets_dkms():
        assert entradas is None or "LICENSES" in entradas, (
            "o sdist leva assets/dkms/ e o only-include não nomeia LICENSES/: "
            "o fonte GPL viajaria sem o texto da licença."
        )
    for arquivo in ("GPL-2.0.txt", "BSD-3-Clause.txt", "README.md"):
        assert (LICENSES / arquivo).is_file(), (
            f"LICENSES/{arquivo} não existe — o sdist não tem o que incluir"
        )


def test_o_notice_diz_se_o_sdist_leva_os_fontes_gpl() -> None:
    """O NOTICE afirma quais artefatos não levam `assets/dkms/`, e o dono do"""
    frase = next(
        (
            paragrafo
            for paragrafo in _texto(NOTICE).split("\n\n")
            if "não carregam fonte de assets/dkms/" in paragrafo
        ),
        None,
    )
    assert frase is not None, (
        "o NOTICE perdeu a frase que diz quais artefatos não levam assets/dkms/"
    )
    if _o_sdist_leva_assets_dkms():
        assert "sdist" not in frase, (
            "o sdist leva assets/dkms/ (o only-include do pyproject) e o NOTICE "
            f"diz que não: {frase.strip()!r}"
        )
    else:
        assert "sdist" in frase, (
            "o only-include do pyproject deixa assets/dkms/ fora do sdist, e o "
            f"NOTICE não diz: {frase.strip()!r}"
        )


def test_notice_declara_cc0_nas_curvas_proprias() -> None:
    """Onde as curvas vão viver, está escrito que saem em CC0."""
    texto = _texto(NOTICE)
    assert "CC0-1.0" in texto, (
        "o NOTICE não declara a licença das curvas próprias. Pela decisão de "
        "07/08/2026 (resposta 2): CC0-1.0 nas curvas, separada da do código."
    )
    assert "docs/protocol/curvas-proprias.md" in texto, (
        "o NOTICE declara a CC0 mas não diz ONDE as curvas vão viver"
    )


def test_notice_nao_confunde_a_licenca_do_codigo_com_a_das_curvas() -> None:
    """As duas licenças convivem, e a distinção tem de estar escrita."""
    texto = _texto(NOTICE)
    frase = f"{LICENCA_DO_HEFESTO} no código, CC0-1.0 nas curvas"
    assert frase in texto, (
        f"o NOTICE não diz, na mesma frase, que o código segue {LICENCA_DO_HEFESTO} "
        "e as curvas saem em CC0-1.0"
    )
