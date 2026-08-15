"""Guarda de anonimato de hardware: MAC real NUNCA sai inteiro no repo.

Corretor final (interação entre ondas, achado #4): o desenho da Onda S vazou
os 6 octetos REAIS do adaptador BT e de um controle, quebrando a convenção que
todas as outras ondas seguiram — MAC de hardware real é citado com os 3
últimos octetos mascarados (forma ``OUI:00:00:NN``; nenhum exemplo literal
aqui de propósito — o irmão test_anonimato_de_fixtures proíbe MAC-forma em
tests/ fora das faixas forjadas).
O ``check_anonymity.sh`` era cego a MAC (só caçava menções a provedores de IA,
e exclui ``docs/process/**``), e por isso este teste nasceu como o gate que
faltava. **Correção de fato — 15/08/2026:** ele deixou de ser inteiramente
cego. Ganhou uma varredura de MAC em BINÁRIO, nas duas ordens de byte, quando a
casa passou a versionar captura de rádio (ver o portão de bytes no fim deste
arquivo). Em TEXTO ele segue cego a MAC, e é aqui que a regra mora: este
arquivo continua sendo o portão autoritativo das três formas — separada,
colada e binária.

O contrato: qualquer MAC completo (6 octetos) cujo prefixo seja um OUI de
hardware REAL desta bancada precisa ter os octetos 4 e 5 zerados (a máscara).
Os OUIs em si já são públicos no repo (docs mascarados citam todos) — o que
identifica o aparelho é o SUFIXO, e é ele que este teste bloqueia.
MACs forjados (``aa:bb:cc:*``, ``02:fe:*`` do vpad) ficam fora do contrato.

O QUE ESTE PORTÃO NÃO VÊ, E NUNCA VIU: O HISTÓRICO
--------------------------------------------------

NOTA DATADA — 07/08/2026. **GRAU: MEDIDO.**

Este portão lê a **árvore de trabalho**: ``git ls-files`` mais o disco. É a
regra desta casa, e ela é correta para tudo — menos para isto. **Nenhum portão
do projeto varre o histórico do ``git``**, e o histórico é público.

Medido nesta árvore em 07/08, com o critério escrito para poder ser refeito:
varridas as **linhas adicionadas** de todos os **655** commits alcançáveis a
partir do ``HEAD``, procurando a forma completa de um MAC cujo prefixo esteja
em ``_OUIS_REAIS_OCTETOS`` e cujos octetos 4 e 5 **não** sejam a máscara,
**16** commits casam — nas duas grafias, com separador e colada. E os dois
testes deste arquivo passam **verdes** no mesmo instante, porque a árvore de
hoje está limpa. O portão não está mentindo: ele está respondendo outra
pergunta.

O piso desses 16 é confiável e o teto não — a varredura é por FORMA, como a que
achou o BURACO-DO-PORTAO-01. A
``2026-08-06-RELOGIO-NAO-E-ASSERCAO-01`` registra a mesma classe com outra
régua (*"três commits publicados os carregam"*, contados sobre o que está em
``origin/main``); os dois números medem coisas diferentes e nenhum substitui o
outro.

**O que segue SEM PROVA, e por isso não se decide aqui:** se uma nova purga
paga o custo. Já houve uma, em 20/07, os endereços **voltaram** depois dela, e
sobraram **438** ``replace refs`` ativos que ninguém recontou. A ``CLEAN-ROOM``
nomeia o ``filter-repo`` como a ferramenta certa e diz que neste caso a
exposição **é** o dano. **É decisão dela**, não de portão: reescrever histórico
publicado é destrutivo e não desfaz o que já foi clonado.

**O que seria um portão viável também segue SEM PROVA:** ninguém desenhou. A
única forma barata que já foi sugerida — varrer só os commits **novos** de cada
leva, e não o histórico inteiro — nunca foi escrita nem medida.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

#: OUIs de hardware REAL desta bancada (adaptador BT, DualSense, 8BitDo,
#: Nintendo, roteador) — prefixos já públicos nos docs mascarados.
#:
#: NOTA DATADA — 06/08/2026: entrou `14:3a:9a`, o OUI do SEGUNDO DualSense da
#: bancada. A ausência dele estava registrada como buraco desde 29/07 e o
#: endereço daquele controle circulou no repositório esse tempo todo.
#:
#: NOTA DATADA — 15/08/2026. **GRAU: MEDIDO.** Entraram `d4:2f:4b` e
#: `44:46:48`, o TERCEIRO e o QUARTO DualSense — os dois que chegaram na mesa
#: 2+2 e que esta lista nunca conheceu. Medido na árvore de 15/08: **17**
#: documentos versionados citam `d4:2f:4b` e **18** citam `44:46:48`, todos com
#: a máscara da casa, aplicada À MÃO. Enquanto os OUIs faltavam aqui, essa
#: máscara era disciplina de quem escrevia, não portão: um dos dois voltando
#: CRU — do `controllers.json`, do journal ou de um dump de `sysfs` colado sem
#: revisar — deixava o teste VERDE. É a mesma família do BURACO-DO-PORTAO-01
#: (06/08), que entrou pelo mesmo motivo: o portão só reprova o que ele lista.
#:
#: A regra que evita a terceira vez: **controle novo na bancada, OUI novo
#: aqui, no mesmo commit** — antes de o endereço dele aparecer em documento.
_OUIS_REAIS_OCTETOS = (
    ("d8", "44", "89"),
    ("a0", "fa", "9c"),
    ("e4", "17", "d8"),
    ("e0", "f6", "b5"),
    ("48", "b2", "5d"),
    ("14", "3a", "9a"),
    ("d4", "2f", "4b"),
    ("44", "46", "48"),
)

#: Compatibilidade: a forma com separador, que é como os documentos citam.
OUIS_REAIS = tuple("[:_-]".join(o) for o in _OUIS_REAIS_OCTETOS)

#: A forma COLADA (12 hex seguidos), que é como o endereço sai do
#: `controllers.json`, do journal e de `bluetoothctl`.
_OUIS_COLADOS = tuple("".join(o) for o in _OUIS_REAIS_OCTETOS)

# BURACO-DO-PORTAO-01 (06/08/2026) — MEDIDO: o regex exigia separador entre os
# octetos, então `d8:44:89:xx:xx:xx` reprovava e `d84489xxxxxx` PASSAVA. A forma
# colada é justamente a que o produto gera: é assim que o endereço aparece no
# `controllers.json` (chave `addr`), no journal (`uniq=`) e na saída do
# `bluetoothctl`. Resultado medido em 06/08: 20 linhas em 7 arquivos versionados
# publicavam o endereço de rádio dos aparelhos da casa, com o portão VERDE — e
# uma delas remontava os dois endereços do 8BitDo numa página de usuária.
#
# Num projeto que vai para a comunidade isso é vazamento de privacidade: o
# endereço de rádio identifica o aparelho, e o repositório é público.
#
# Os dois formatos passam a reprovar. A máscara continua sendo a mesma da casa —
# octetos 4 e 5 zerados — nas duas grafias.
# BURACO-DO-PORTAO-03 (15/08/2026) — MEDIDO, e é o `\b` das PONTAS:
# o regex abria e fechava em `\b`, que exige que o vizinho NÃO seja caractere
# de palavra. Só que a fonte mais rica de endereço cru desta casa é o `uevent`
# do sysfs, e nele os campos vêm CONCATENADOS, sem separador nenhum:
#
#   HID_PHYS=d8:44:89:xx:xx:xxHID_UNIQ=44:46:48:xx:xx:xxMODALIAS=hid:...
#
# Depois do último octeto vem um `H` e um `M` — caractere de palavra dos dois
# lados, logo `\b` não existe ali, logo os DOIS endereços passavam VERDES. O
# mesmo vale para o nome do nó de bateria
# (`...battery-44:46:48:xx:xx:xxPOWER_SUPPLY_TYPE=`), que é como o endereço
# aparece 57 vezes num único dump de `sysfs`. Achado ao mascarar os brutos do
# estudo PAREADO: o mascarador, que usava a mesma régua, deixou 4 endereços
# crus por trás nos dois arquivos.
#
# A cura é trocar a fronteira de PALAVRA pela fronteira de HEXADECIMAL: o que
# não pode encostar num MAC é outro dígito hexadecimal (senão o casamento seria
# um pedaço de um número maior, como um sha256). Letra fora de `a-f`, `=`,
# `/`, espaço — tudo isso pode encostar, e agora reprova.
#
# Medido na árvore de 15/08/2026: com a fronteira de hexadecimal, ZERO
# reprovações novas em todos os arquivos rastreados e novos. A troca não custa
# ruído; só fecha o buraco.
#
# Para arrancar e ver morder: devolva `\b` no lugar dos dois lookarounds e rode
# `test_o_mac_colado_na_chave_seguinte_do_uevent_reprova`.
_NAO_HEX_ANTES = r"(?<![0-9a-f])"
_NAO_HEX_DEPOIS = r"(?![0-9a-f])"
MAC_COMPLETO_RE = re.compile(
    r"(?i)" + _NAO_HEX_ANTES + r"(?:"
    # forma com separador: d8:44:89:xx:xx:xx
    r"(?P<oui_sep>" + "|".join(OUIS_REAIS) + r")"
    r"[:_-](?P<a>[0-9a-f]{2})[:_-](?P<b>[0-9a-f]{2})[:_-](?P<c>[0-9a-f]{2})"
    r"|"
    # forma colada: d84489xxxxxx
    r"(?P<oui_col>" + "|".join(_OUIS_COLADOS) + r")"
    r"(?P<a2>[0-9a-f]{2})(?P<b2>[0-9a-f]{2})(?P<c2>[0-9a-f]{2})"
    r")" + _NAO_HEX_DEPOIS
)


def _partes(m: re.Match[str]) -> tuple[str, str, str]:
    """Devolve (oui, octeto4, octeto5) de qualquer uma das duas grafias."""
    if m.group("oui_sep") is not None:
        return m.group("oui_sep"), m.group("a"), m.group("b")
    return m.group("oui_col"), m.group("a2"), m.group("b2")

#: Extensões binárias/geradas — sem texto a auditar.
_SKIP_SUFFIXES = {".png", ".svg", ".mo", ".ico", ".gif", ".jpg", ".jpeg"}


def _tracked_files(repo_root: Path) -> list[Path]:
    """A LISTA do git: o rastreado E o novo, sem o ignorado.

    ANONIMATO-CEGO-A-ARQUIVO-NOVO-02 (15/08/2026). Aqui era `git ls-files -z`
    puro, que só enxerga o ÍNDICE — o mesmo defeito que o
    ``check_anonymity.sh`` curou em 13/08 e que este portão herdou sem que
    ninguém notasse. A regra da casa ("portões são cegos a arquivo novo: rode-os
    depois do `git add`") existia justamente para contornar isto à mão, e
    contorno à mão falha no dia em que alguém esquece — que é o dia em que um
    dump de `sysfs` recém-colado entra sem revisão.

    `--others --exclude-standard` traz o arquivo novo e continua respeitando o
    `.gitignore`. Medido em 15/08 nesta árvore: nenhuma reprovação nova.
    """
    out = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return [
        repo_root / nome
        for nome in out.split("\0")
        if nome and Path(nome).suffix.lower() not in _SKIP_SUFFIXES
    ]


def test_nenhum_mac_real_completo_sem_mascara_no_repo() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        try:
            texto = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):  # deletado no working tree etc.
            continue
        for num, linha in enumerate(texto.splitlines(), start=1):
            for m in MAC_COMPLETO_RE.finditer(linha):
                oui, oct4, oct5 = _partes(m)
                # Máscara da casa: octetos 4 e 5 zerados (OUI:00:00:NN).
                if oct4 == "00" and oct5 == "00":
                    continue
                violacoes.append(
                    f"{path.relative_to(repo_root)}:{num}: "
                    f"MAC real sem máscara ({oui}:xx:xx:xx)"
                )
    assert not violacoes, (
        "MAC de hardware REAL com sufixo exposto — mascare os 3 últimos "
        "octetos (convenção OUI:00:00:NN dos estudos):\n" + "\n".join(violacoes)
    )


#: A forma ELIDIDA: `...:1c:99:83`. O OUI foi omitido, mas o que identifica o
#: aparelho é justamente o sufixo — e o OUI costuma estar na mesma frase, porque
#: é público e a explicação precisa dele.
MAC_ELIDIDO_RE = re.compile(
    r"(?i)\.\.\.[:_-]?"
    r"(?P<a>[0-9a-f]{2})[:_-](?P<b>[0-9a-f]{2})[:_-](?P<c>[0-9a-f]{2})\b"
)


def test_nenhum_sufixo_de_mac_real_com_o_oui_elidido() -> None:
    """Omitir o OUI não é máscara — o sufixo é o que identifica o aparelho.

    BURACO-DO-PORTAO-01, segunda metade (06/08/2026). MEDIDO: a página
    ``docs/usage/troubleshooting-8bitdo.md`` escrevia, numa frase só, os dois
    sufixos do 8BitDo E o OUI dele. Cada pedaço passava pelo portão porque eles
    estavam em símbolos separados; remontar os dois endereços completos era
    juntar as pontas da mesma linha. E a página é de USUÁRIA — publicada.

    A máscara da casa continua a mesma nas três grafias: octetos 4 e 5 zerados.
    Na forma elidida isso é ``...:00:00:NN``.

    Para arrancar e ver morder: devolva um sufixo real a qualquer documento na
    forma ``...:xx:yy:zz`` com ``xx``/``yy`` diferentes de ``00``.
    """
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        # O próprio portão cita a forma no texto — senão ele se acusaria.
        if path.name == Path(__file__).name:
            continue
        try:
            texto = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, IsADirectoryError):
            continue
        for num, linha in enumerate(texto.splitlines(), start=1):
            for m in MAC_ELIDIDO_RE.finditer(linha):
                if m.group("a") == "00" and m.group("b") == "00":
                    continue
                violacoes.append(
                    f"{path.relative_to(repo_root)}:{num}: "
                    "sufixo de MAC com o OUI elidido — omitir o OUI não "
                    "mascara nada (use ...:00:00:NN)"
                )
    assert not violacoes, (
        "sufixo de MAC real exposto com o OUI omitido:\n" + "\n".join(violacoes)
    )


# ===========================================================================
# O PORTÃO DE BYTES — MAC-BINARIO-EM-LITTLE-ENDIAN-01 (15/08/2026)
# ===========================================================================
#
# GRAU: MEDIDO. Os dois testes acima leem TEXTO: `read_text`, linha a linha,
# procurando hexadecimal escrito. Um endereço de rádio que nunca vira texto
# passa por eles sem tocá-los — e é exatamente essa a forma em que ele viaja
# numa captura de HCI.
#
# O caso que abriu o buraco: a dona decidiu versionar o lastro BINÁRIO do
# estudo PAREADO (`docs/data/ensaios-brutos/2026-08-15-PAREADO-hci.btsnoop`,
# 238451 B). O `btmon` grava `BD_ADDR` como seis bytes crus e em ordem
# INVERTIDA — `d8:44:89:xx:xx:xx` aparece no arquivo como
# `xx xx xx 89 44 d8`. Medido naquele arquivo: DUAS ocorrências, ambas em
# little-endian, nenhuma em big-endian, e nenhum portão desta casa as via.
#
# A régua que este portão impõe a si mesmo: **procurar nas DUAS ordens de
# byte**. Procurar numa só produz um verde convincente e falso — foi o que
# aconteceu duas vezes em 15/08, e é por isso que a busca big-endian fica aqui
# mesmo tendo dado zero: o zero é resultado declarado, não busca esquecida.
#
# Por que ele NÃO importa nada de `scripts/mascarar_btsnoop.py`, que faz a
# mesma varredura: portão não pode depender da ferramenta que ele fiscaliza —
# um defeito na ferramenta apagaria o portão junto. As duas listas de OUI são
# comparadas por `tests/unit/test_mascarar_btsnoop.py`, que reprova a
# divergência.
#
# O que ele NÃO varre é o mesmo `_SKIP_SUFFIXES` dos irmãos: imagem e catálogo
# `.mo` compilado. Não é frouxidão, é a lição da
# ANONIMATO-BINARIO-FALSO-POSITIVO-01 (01/08) — três bytes casam por acaso em
# dado comprimido, e um PNG que MUDA a cada `retratar_abas.py` produziria
# reprovação intermitente e incorrigível. Medido em 15/08: com esse recorte, a
# árvore inteira dá ZERO ocorrências acidentais.


def _mac_de_seis_octetos(dados: bytes, inicio: int) -> bytes:
    return dados[inicio : inicio + 6]


def _ocorrencias_binarias(dados: bytes) -> list[tuple[int, str, str]]:
    """(offset, ordem, mac) de todo MAC de OUI real CRU dentro de ``dados``.

    Cru = octetos 4 e 5 fora da máscara da casa. Devolve as duas ordens de
    byte, porque procurar numa só é o defeito que este portão existe para
    impedir.
    """
    achados: list[tuple[int, str, str]] = []
    for octetos in _OUIS_REAIS_OCTETOS:
        oui_be = bytes(int(o, 16) for o in octetos)
        oui_le = oui_be[::-1]

        # BIG-ENDIAN: o OUI abre o campo; os octetos 4 e 5 vêm logo depois.
        pos = dados.find(oui_be)
        while pos != -1:
            campo = _mac_de_seis_octetos(dados, pos)
            if len(campo) == 6 and not (campo[3] == 0 and campo[4] == 0):
                achados.append((pos, "big-endian", campo.hex(":")))
            pos = dados.find(oui_be, pos + 1)

        # LITTLE-ENDIAN: o OUI FECHA o campo; os octetos 4 e 5 são os dois
        # bytes imediatamente anteriores a ele.
        pos = dados.find(oui_le)
        while pos != -1:
            inicio = pos - 3
            if inicio >= 0:
                campo = _mac_de_seis_octetos(dados, inicio)
                if not (campo[1] == 0 and campo[2] == 0):
                    # Impresso na ordem HUMANA, que é a inversa da gravada.
                    achados.append((inicio, "little-endian", campo[::-1].hex(":")))
            pos = dados.find(oui_le, pos + 1)
    return sorted(achados)


def test_nenhum_mac_real_em_bytes_no_repo() -> None:
    """Nenhum arquivo versionado carrega MAC real em BINÁRIO, em ordem nenhuma.

    Para arrancar e ver morder: grave um `.btsnoop` (ou qualquer arquivo) com
    os seis bytes de um endereço real em little-endian dentro de
    `docs/data/ensaios-brutos/`. O teste
    ``tests/unit/test_mascarar_btsnoop.py::test_o_portao_de_bytes_morde_o_mac_em_little_endian``
    faz exatamente isso, num arquivo temporário, e confere a reprovação.
    """
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        try:
            dados = path.read_bytes()
        except (OSError, IsADirectoryError):  # deletado no working tree etc.
            continue
        for offset, ordem, mac in _ocorrencias_binarias(dados):
            violacoes.append(
                f"{path.relative_to(repo_root)}: offset {offset} ({ordem}): "
                f"MAC real em bytes, sem máscara ({mac})"
            )
    assert not violacoes, (
        "MAC de hardware REAL gravado em BINÁRIO. Nenhum portão de texto o vê. "
        "Passe o arquivo por `scripts/mascarar_btsnoop.py` (captura HCI) ou "
        "zere os octetos 4 e 5 dos seis bytes apontados:\n" + "\n".join(violacoes)
    )


def test_o_mac_colado_na_chave_seguinte_do_uevent_reprova() -> None:
    """BURACO-DO-PORTAO-03: `\\b` não existe entre um octeto e uma letra.

    O `uevent` do sysfs concatena os campos sem separador, e era assim que dois
    endereços por linha escapavam. A régua agora é fronteira de HEXADECIMAL.

    Para arrancar e ver morder: troque os dois lookarounds de
    ``MAC_COMPLETO_RE`` de volta por ``\\b``.

    Os endereços de exemplo são MONTADOS a partir de ``_OUIS_REAIS_OCTETOS``
    com sufixo inventado (``11:22:33``), e nunca escritos por extenso: este
    arquivo é varrido pelo próprio portão, e a regra da casa é que não há
    exemplo literal de MAC real dentro de ``tests/``.
    """
    primeiro = ":".join(_OUIS_REAIS_OCTETOS[0])
    segundo = ":".join(_OUIS_REAIS_OCTETOS[-1])
    sufixo_cru = ":".join(("11", "22", "33"))
    sufixo_mascarado = ":".join(("00", "00", "33"))
    linha = (
        "uevent|DRIVER=playstation"
        f"HID_PHYS={primeiro}:{sufixo_cru}HID_UNIQ={segundo}:{sufixo_cru}"
        "MODALIAS=hid:b0005g0000v0000054Cp00000CE6"
    )
    achados = [_partes(m) for m in MAC_COMPLETO_RE.finditer(linha)]
    assert len(achados) == 2, (
        "o portão tem de ver os DOIS endereços colados na mesma linha de "
        f"uevent, e viu {len(achados)}: {achados}"
    )
    assert all(oct4 != "00" or oct5 != "00" for _, oct4, oct5 in achados)

    # E a mesma linha, mascarada, tem de passar.
    mascarada = linha.replace(sufixo_cru, sufixo_mascarado)
    encontrados = [_partes(m) for m in MAC_COMPLETO_RE.finditer(mascarada)]
    assert len(encontrados) == 2
    assert all((oct4, oct5) == ("00", "00") for _, oct4, oct5 in encontrados)


def test_o_regex_nao_confunde_pedaco_de_hexadecimal_maior() -> None:
    """A fronteira de hexadecimal é fronteira nos DOIS sentidos.

    Um sha256 que por acaso contenha um OUI real no meio não é um MAC, e
    reprová-lo transformaria o portão em gerador de ruído — que é como portão
    morre.
    """
    oui_colado = "".join(_OUIS_REAIS_OCTETOS[0])
    sha_falso = "9f" + oui_colado + "112233" + "ab" * 24
    assert not list(MAC_COMPLETO_RE.finditer(sha_falso))
