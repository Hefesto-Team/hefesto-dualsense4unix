"""Portão das licenças: o LICENSE é MIT puro, o NOTICE é dono da ressalva, e o
texto das licenças de terceiros viaja com o fonte.

Cobre três decisões, todas de 07/08/2026, todas grau DECISÃO DELA
(``docs/process/2026-08-07-DECISOES-DELA-as-onze-respostas-do-painel.md``):

- **resposta 4** — o bloco ``ESCOPO`` sai do ``LICENSE`` e o ``NOTICE`` vira
  dono da ressalva. O motivo é medido e só aparece fora da máquina: um
  ``LICENSE`` com texto antes do MIT faz o detector de licença do GitHub
  rotular o repositório como "View license" em vez de "MIT";
- **resposta 2** — MIT no código, CC0-1.0 nas curvas medidas por ela;
- **CR-05, a caixa que ficou aberta em 31/07** — a GPL-2.0, seção 1, exige que
  a cópia do texto da licença acompanhe o fonte, e nenhuma acompanhava.

A MORDIDA — provada em 07/08/2026 arrancando a cura, uma por vez, com a suíte
rodando entre cada arrancada e o arquivo devolvido logo em seguida. Com tudo no
lugar: **21 passaram, 0 reprovaram**.

===================================================  ===========================
cura arrancada                                       testes que reprovaram
===================================================  ===========================
bloco ``ESCOPO`` devolvido ao topo do ``LICENSE``    2
seção "ESCOPO DESTE ARQUIVO" removida do ``NOTICE``  3
``LICENSES/GPL-2.0.txt`` apagado                     3
``LICENSES/BSD-3-Clause.txt`` apagado                2
linha do ``LICENSES`` tirada do ``build_deb.sh``     1
linha do ``LICENSES`` tirada do ``PKGBUILD``         1
linha do ``LICENSES`` tirada do ``.spec``            1
linha do ``LICENSES`` tirada do flatpak ``.yml``     1
bloco da CC0 removido do ``NOTICE``                  2
===================================================  ===========================

Depois do ciclo inteiro, os nove arquivos tocados voltaram com ``SHA-256``
idêntico ao de antes — conferido, não presumido.

NOTA DATADA — 07/08/2026, na passagem dos portões sobre a árvore inteira.
**Quatro linhas da tabela acima caducaram**: as dos quatro empacotadores. A
mordida delas foi medida de novo e **não mordia**. O motivo, MEDIDO:
``test_alvo_que_copia_dkms_copia_licenses_junto`` só perguntava se a palavra
``LICENSES`` aparecia em algum lugar do arquivo — busca de trecho — e os
quatro alvos trazem o COMENTÁRIO "Procedência em ``LICENSES/README.md``" logo
acima da cópia. Duas arrancadas provaram o buraco:

- só a linha ``cp`` fora dos quatro alvos: **21 passaram, 0 reprovaram**;
- ``mkdir`` **e** ``cp`` fora dos quatro, sobrando apenas o comentário — isto
  é, os quatro artefatos distribuindo fonte GPL sem uma linha de licença
  junto, exatamente o que a CR-05 existe para impedir: **21 passaram, 0
  reprovaram**, e o ``check_packaging_parity.sh`` também ficou verde.

O portão passou a cobrar um COMANDO de cópia (``COPIA_DE_LICENSES`` sobre
``_linhas_executaveis``), com ``LICENSES`` na origem e destino depois dele.
Mordida redonda, medida em 07/08/2026: arrancando a linha ``cp`` dos quatro
alvos, **4 reprovaram**; arrancando de um só (o flatpak), **1 reprovou**. Com
tudo no lugar, 21 verdes. Os quatro arquivos voltaram com ``SHA-256`` idêntico.

O resto da tabela — ``LICENSE``, ``NOTICE``, os textos das licenças — continua
valendo: aquelas curas foram rearrancadas e reprovaram como escrito.

Por que este portão não mora no ``check_packaging_parity.sh``: aquele script
cobra unit, ícone, regra udev e broker — coisas de empacotamento. Este aqui
precisa ler o ``LICENSE`` e o ``NOTICE`` também, que não são empacotamento.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

LICENSE = REPO / "LICENSE"
NOTICE = REPO / "NOTICE"
LICENSES = REPO / "LICENSES"

#: SHA-256 do texto canônico da GNU GPL v2, medido em 07/08/2026 sobre
#: ``/usr/share/common-licenses/GPL-2`` (pacote ``base-files``, dono confirmado
#: por ``dpkg -S``). Cópia byte a byte, sem modificação nenhuma.
SHA256_GPL2 = "8177f97513213526df2cf6184d8ff986c675afb514d4e68a404010521b880643"

#: Os alvos de empacotamento que copiam ``assets/dkms/`` e por isso TÊM de
#: copiar ``LICENSES/`` junto. O sdist não está aqui porque nele a inclusão é
#: automática — tem teste próprio, mais abaixo.
ALVOS_QUE_COPIAM_DKMS = [
    "scripts/build_deb.sh",
    "packaging/arch/PKGBUILD",
    "packaging/fedora/hefesto-dualsense4unix.spec",
    "flatpak/br.andrefarias.Hefesto.yml",
]


#: Um comando que COPIA ``LICENSES`` para um destino. O que importa é a forma:
#: um verbo de cópia, ``LICENSES`` como ORIGEM, e um destino depois dele. Cobre
#: as duas escritas em uso — ``cp -a LICENSES/. <destino>`` (deb, Arch, Fedora)
#: e ``cp -a LICENSES <destino>`` (flatpak).
#:
#: Por que não basta procurar a palavra: até 07/08/2026 este portão só olhava
#: se ``LICENSES`` aparecia no arquivo, e os quatro empacotadores trazem um
#: COMENTÁRIO ("Procedência em LICENSES/README.md") logo acima da cópia. No
#: mesmo dia, arrancando ``mkdir`` e ``cp`` dos QUATRO alvos — isto é, com os
#: quatro artefatos distribuindo fonte GPL sem uma linha de licença junto, que
#: é exatamente o que a CR-05 existe para impedir — a suíte seguia com 21
#: verdes. O comentário sozinho satisfazia o portão.
COPIA_DE_LICENSES = re.compile(
    r"\b(?:cp|install|rsync)\b[^\n]*?(?<![\w./-])LICENSES(?:/\S*)?\s+(\S+)"
)

#: Comentário de linha inteira ou de fim de linha. O ``#`` só conta quando vem
#: depois de espaço (ou no começo), para não confundir com ``${VAR#prefixo}``
#: nem com ``$#``.
COMENTARIO = re.compile(r"(?<!\S)#.*$")

#: Continuação de linha por barra invertida. Precisa ser desfeita antes de
#: olhar comando por comando: nos três alvos de shell a origem e o destino da
#: cópia moram em linhas físicas diferentes.
CONTINUACAO = re.compile(r"\\\n\s*")


def _texto(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8")


def _linhas_executaveis(texto: str) -> list[str]:
    """As linhas que a máquina executa: continuações juntadas, comentário fora.

    É o filtro que separa "o empacotador copia" de "o empacotador comenta sobre
    a cópia". Sem ele, prosa vira prova.
    """
    inteiro = CONTINUACAO.sub(" ", texto)
    linhas = []
    for linha in inteiro.splitlines():
        sem_comentario = COMENTARIO.sub("", linha)
        if sem_comentario.strip():
            linhas.append(sem_comentario)
    return linhas


# ---------------------------------------------------------------------------
# Resposta 4 — o LICENSE é MIT canônico, e nada antes dele
# ---------------------------------------------------------------------------


def test_license_comeca_no_mit_sem_nada_antes() -> None:
    """A primeira linha do LICENSE tem de ser ``MIT License``.

    É esta a forma que o detector de licença do GitHub reconhece; qualquer
    coisa antes derruba o rótulo "MIT" para "View license" na vitrine.
    """
    linhas = _texto(LICENSE).splitlines()
    assert linhas, "LICENSE vazio"
    assert linhas[0] == "MIT License", (
        f"a primeira linha do LICENSE é {linhas[0]!r}, e tinha de ser 'MIT License'. "
        "Decisão dela de 07/08/2026 (resposta 4): nada antes do texto MIT. "
        "Ressalva de escopo vai para o NOTICE, seção 'ESCOPO DESTE ARQUIVO'."
    )


def test_license_nao_carrega_mais_bloco_de_escopo() -> None:
    """Nenhuma ressalva de escopo pode voltar para o LICENSE.

    Não basta olhar a primeira linha: um bloco no rodapé também é texto que o
    detector do GitHub não espera, e a decisão dela foi que a ressalva mora no
    NOTICE — não que ela desça de posição.
    """
    texto = _texto(LICENSE)
    for proibido in ("ESCOPO", "assets/dkms", "SPDX", "GPL-2.0"):
        assert proibido not in texto, (
            f"o LICENSE voltou a citar {proibido!r}. A ressalva de escopo tem dono "
            "desde 07/08/2026, e é o NOTICE."
        )


def test_license_tem_o_texto_mit_canonico_inteiro() -> None:
    """As quatro partes do MIT canônico estão todas lá.

    Tirar o bloco de escopo não pode ter levado meia licença junto.
    """
    texto = _texto(LICENSE)
    for trecho in (
        "MIT License",
        "Permission is hereby granted, free of charge",
        "The above copyright notice and this permission notice shall be included",
        'THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND',
    ):
        assert trecho in texto, f"o LICENSE perdeu o trecho canônico {trecho!r}"
    assert re.search(r"Copyright \(c\) \d{4} ", texto), (
        "o LICENSE perdeu a linha de copyright"
    )


# ---------------------------------------------------------------------------
# Resposta 4 — o NOTICE é o dono da ressalva, e ela chegou inteira
# ---------------------------------------------------------------------------


def test_notice_tem_a_secao_de_escopo() -> None:
    texto = _texto(NOTICE)
    assert "ESCOPO DESTE ARQUIVO" in texto, (
        "o NOTICE perdeu a seção 'ESCOPO DESTE ARQUIVO'. Ela é a dona da ressalva "
        "desde 07/08/2026, e sem ela a ressalva sumiu do repositório inteiro."
    )


@pytest.mark.parametrize(
    ("módulo", "licença"),
    [
        ("assets/dkms/hid-nintendo/", "GPL-2.0-or-later"),
        ("assets/dkms/hid-playstation/", "GPL-2.0-or-later"),
        ("assets/dkms/rtw88-usb/", "GPL-2.0 OR BSD-3-Clause"),
    ],
)
def test_notice_nomeia_cada_módulo_com_a_licença_dele(módulo: str, licença: str) -> None:
    """Cada linha que o bloco do LICENSE dizia tem de estar no NOTICE.

    Este é o teste que impede a mudança de endereço de virar perda de conteúdo:
    a ressalva saiu do LICENSE, e o que ela dizia tem de estar aqui, com o
    diretório e a licença juntos na mesma vizinhança.
    """
    texto = _texto(NOTICE)
    assert módulo in texto, f"o NOTICE não nomeia {módulo}"
    janela = texto[texto.index(módulo) : texto.index(módulo) + 200]
    assert licença in janela, (
        f"o NOTICE nomeia {módulo} mas não diz {licença!r} junto dele. "
        "A licença e o diretório não podem se separar."
    )


def test_notice_diz_que_o_spdx_nao_pode_ser_removido() -> None:
    """A frase que sustenta a licitude do uso não pode ter ficado para trás."""
    texto = _texto(NOTICE)
    assert "não podem" in texto and "SPDX" in texto, (
        "o NOTICE perdeu a afirmação de que os cabeçalhos SPDX valem como licença "
        "e não podem ser removidos"
    )


def test_notice_registra_a_mudanca_com_data_e_grau() -> None:
    """Não se apaga decisão medida: a mudança de endereço ganha nota datada."""
    texto = _texto(NOTICE)
    assert "2026-08-07" in texto, "o NOTICE não tem a nota datada de 07/08/2026"
    assert "DECISÃO DELA" in texto, (
        "o NOTICE não declara o grau da mudança. Toda afirmação carrega grau, e "
        "esta é DECISÃO DELA."
    )


# ---------------------------------------------------------------------------
# CR-05 — o texto das licenças de terceiros existe e é canônico
# ---------------------------------------------------------------------------


def test_gpl2_existe_e_e_byte_a_byte_o_canonico() -> None:
    """O texto da GPL-2.0 não pode ter sido reescrito, resumido nem traduzido.

    A conferência é por SHA-256 justamente porque "parece a GPL" não serve:
    licença editada é licença outra.
    """
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
    """O rtw88-usb é licença DUPLA; mandar só a GPL cobre metade da escolha.

    ``assets/dkms/rtw88-usb/usb.c:1`` traz ``GPL-2.0 OR BSD-3-Clause`` e
    ``usb.c:1504`` traz ``MODULE_LICENSE("Dual BSD/GPL")`` — quem redistribui
    escolhe um dos dois termos, e os dois precisam do texto que os sustenta.
    """
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


# ---------------------------------------------------------------------------
# CR-05 — o texto viaja em TODO alvo que carrega os fontes GPL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("alvo", ALVOS_QUE_COPIAM_DKMS)
def test_alvo_que_copia_dkms_copia_licenses_junto(alvo: str) -> None:
    """Quem leva o fonte GPL leva o texto da licença junto, ou não leva nada.

    A medição de 31/07 (CR-05) mostrou que os fontes GPL viajam em cinco dos
    sete artefatos publicados. Isso é lícito — é o que a GPL-2.0 autoriza —
    desde que a cópia da licença vá junto, e é isso que este teste cobra.
    """
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


def test_sdist_carrega_licenses_sem_precisar_de_linha() -> None:
    """No sdist a inclusão é automática — mas só enquanto ninguém a restringir.

    O ``hatchling`` inclui no sdist tudo o que está versionado, e não há
    ``[tool.hatch.build.targets.sdist]`` no ``pyproject.toml``. Este teste
    guarda as DUAS pernas dessa afirmação: se alguém acrescentar a seção sem
    nomear ``LICENSES``, o sdist passa a distribuir fonte GPL sem licença e
    ninguém perceberia.
    """
    pyproject = _texto(REPO / "pyproject.toml")
    if "[tool.hatch.build.targets.sdist]" in pyproject:
        secao = pyproject.split("[tool.hatch.build.targets.sdist]", 1)[1]
        secao = secao.split("\n[", 1)[0]
        assert "LICENSES" in secao, (
            "o pyproject.toml passou a configurar o alvo sdist e não nomeia "
            "LICENSES/. O sdist carrega os 36 arquivos de assets/dkms/ (medido em "
            "31/07), então tem de carregar o texto das licenças também."
        )
    for arquivo in ("GPL-2.0.txt", "BSD-3-Clause.txt", "README.md"):
        assert (LICENSES / arquivo).is_file(), (
            f"LICENSES/{arquivo} não existe — o sdist não tem o que incluir"
        )


# ---------------------------------------------------------------------------
# Resposta 2 — MIT no código, CC0 nas curvas
# ---------------------------------------------------------------------------


def test_notice_declara_cc0_nas_curvas_proprias() -> None:
    """Onde as curvas vão viver, está escrito que elas saem em CC0.

    A decisão foi tomada ANTES de a primeira curva existir, e é de propósito:
    o problema que abriu a série CR foi justamente uma tabela de curva que
    existe sem licença nenhuma.
    """
    texto = _texto(NOTICE)
    assert "CC0-1.0" in texto, (
        "o NOTICE não declara a licença das curvas próprias. Decisão dela de "
        "07/08/2026 (resposta 2): MIT no código, CC0-1.0 nas curvas."
    )
    assert "docs/protocol/curvas-proprias.md" in texto, (
        "o NOTICE declara a CC0 mas não diz ONDE as curvas vão viver"
    )


def test_notice_nao_confunde_a_licenca_do_codigo_com_a_das_curvas() -> None:
    """As duas licenças convivem, e a distinção tem de estar escrita.

    Sem esta frase, "CC0" solto no NOTICE poderia ser lido como troca da
    licença do projeto — que é exatamente o contrário da decisão dela.
    """
    texto = _texto(NOTICE)
    assert "MIT no código" in texto and "CC0-1.0 nas curvas" in texto, (
        "o NOTICE não diz, na mesma frase, que o código segue MIT e as curvas "
        "saem em CC0-1.0"
    )
