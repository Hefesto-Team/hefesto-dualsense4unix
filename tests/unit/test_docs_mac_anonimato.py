"""Guarda de anonimato de hardware: MAC e SERIAL reais NUNCA saem inteiros.

**NOTA DATADA — 15/08/2026.** O nome do arquivo diz "mac" e o conteúdo já não
diz só isso: no fim dele mora agora o PORTÃO DE SERIAL DE FÁBRICA
(``SERIAL-DE-FABRICA-01``), que nasceu no dia em que um serial real de 17
caracteres entrou na árvore com todos os portões verdes. O arquivo não foi
renomeado de propósito — renomear portão quebra as referências que o CI, os
índices de sprint e os outros testes fazem a ele. O que identifica um aparelho
desta bancada, seja endereço de rádio ou número de etiqueta, é auditado AQUI.

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


# ===========================================================================
# O PORTÃO DE SERIAL — SERIAL-DE-FABRICA-01 (15/08/2026)
# ===========================================================================
#
# GRAU: MEDIDO. Terceira vez da MESMA família nesta casa, e a auditoria de hoje
# escreveu a frase: *"senão a terceira vez acontece"*. As duas primeiras foram
# o BURACO-DO-PORTAO-01 (06/08, a forma colada do MAC) e o
# MAC-BINARIO-EM-LITTLE-ENDIAN-01 (15/08, os bytes crus). A família é sempre a
# mesma: **o portão só reprova a forma que ele conhece.**
#
# O que aconteceu hoje: um SERIAL DE FÁBRICA real, dos 17 caracteres, entrou na
# docstring de `mascarar_serial()` em `scripts/ensaios/cor_do_plastico.py` — a
# própria função que mascara serial vazou um — e o arquivo foi para o índice com
# `scripts/check_anonymity.sh` VERDE. Motivo, medido: aquele portão caça a forma
# de um MAC e menções a provedores de IA; `grep -i serial` nele devolvia ZERO
# linhas, e este arquivo aqui também nunca disse a palavra.
#
# O serial identifica a unidade dela tão bem quanto o MAC — melhor, até: é o
# número impresso na etiqueta, o que a Sony usa para garantia e o que liga o
# aparelho à compra. A regra desta casa é sobre ARQUIVO VERSIONADO, não sobre a
# palavra "MAC".
#
# A MÁSCARA DA CASA PARA SERIAL: 6 caracteres públicos + 11 `#`
# -------------------------------------------------------------
# `A12B34###########` (prefixo FORJADO: nem exemplo mascarado precisa carregar
# o prefixo de um aparelho dela). Ela nasceu em `mascarar_serial()`
# (`CARACTERES_PUBLICOS_DO_SERIAL = 6`) e existia só como disciplina de quem
# escreve. Preserva exatamente o que os ensaios precisam provar — os caracteres
# 5 e 6, onde mora o CÓDIGO DA COR (é o que o ensaio E7 mede) — e apaga o resto.
# Daqui em diante ela é portão.
#
# A FORMA, E A CORREÇÃO DE FATO QUE A MEDIÇÃO IMPÔS
# --------------------------------------------------
# A forma que circulava de boca era `[A-Z]\d{2}[A-Z]\d{2}[A-Z]\d{10}`. Ela está
# ERRADA, e o lastro versionado prova: dos dois seriais que o E7 leu do
# aparelho, `docs/data/ensaios-brutos/2026-08-15-E7-cor-do-plastico.csv` traz
# `M65A05###########` (hidraw4, Starlight Blue) e `E55704###########` (hidraw5,
# Galactic Purple). No segundo, o caractere 4 é o dígito `7`, e não uma letra —
# aquele padrão NÃO casaria com ele. Um portão que não vê metade dos aparelhos
# da bancada é pior que nenhum, porque devolve verde convincente.
#
# O que está MEDIDO, e é só isto, nos dois aparelhos que responderam:
#
#     caractere 1 ...... letra          (`M`, `E`)
#     caracteres 2-3 ... dígitos        (`65`, `55`)
#     caractere 4 ...... letra OU dígito (`A`, `7`)  <- o que derrubou o padrão
#     caracteres 5-6 ... dígitos        (`05`, `04`) — o CÓDIGO DA COR
#     caracteres 7-17 .. NÃO MEDIDOS: os 11 que a máscara come
#
# O regex abaixo exige exatamente isso e nada além: os 11 finais são
# `[A-Z0-9]`, porque afirmar a forma deles seria inventar. A regra que evita a
# quarta vez é a mesma da lista de OUIs lá em cima: **aparelho novo medido,
# prefixo conferido AQUI, no mesmo commit.**
#
# O FALSO POSITIVO, MEDIDO ANTES DE ENTREGAR
# -------------------------------------------
# 17 alfanuméricos maiúsculos é forma barata: casa com hash, chave, id e
# palavra comprida. Medido na árvore de 15/08 (rastreados + novos, imagens de
# fora), varrendo os arquivos INTEIROS:
#
#   `[A-Z0-9]{17}` solto ............................. 12 reprovações, 8 arquivos
#       (contadas ANTES desta seção existir; refazer a conta hoje dá 29 em 10,
#       porque o texto abaixo cita as palavras de ruído por extenso — o número
#       que importa é o da árvore que o portão herdou)
#       e as 12 são ruído: `MICROCASSYVOLTAGE` e `MICROCASSYCURRENT` (os dois
#       `hid-ids.h` do DKMS), `INDEPENDENTEMENTE` (mapa-controles.csv e
#       specs.html), `PROGRAMATICAMENTE` (transcrito de agente),
#       `REDIMENSIONAMENTO` x3 (retratar_abas.py), mais os DOIS forjados
#       legítimos — `AB1C05D1234567890` (o exemplo da docstring de
#       `mascarar_serial`) e `ZZ9Y02Q0000000000`
#       (test_cor_do_plastico_recusa_o_alvo_errado.py).
#   o regex desta seção ..................................... ZERO reprovações
#
# O que eliminou as 12: exigir DÍGITO nas posições 2, 3, 5 e 6. Nenhuma palavra
# de língua nenhuma tem dígito, e os dois forjados também não têm dígito onde o
# serial real tem — `AB1C05...` põe uma letra na posição 2, `ZZ9Y02Q...` põe
# letra na 2 e na 3. Os dois passam, como têm de passar, e passam por MEDIDA da
# forma, não por lista de exceção: lista de exceção é o que apodrece.
#
# Não há aqui a contrapartida das faixas forjadas do MAC (`aa:bb:cc`, `02:fe`):
# serial não tem faixa reservada. Quem precisar de um exemplo forjado que se
# pareça com o real tem de montá-lo por concatenação, como os testes de mordida
# desta seção fazem — nunca escrevê-lo por extenso.

#: Os 6 primeiros caracteres são o que a máscara da casa preserva.
#: ESPELHO de `CARACTERES_PUBLICOS_DO_SERIAL` em scripts/ensaios/cor_do_plastico.py.
CARACTERES_PUBLICOS_DO_SERIAL = 6

#: A forma do serial de fábrica do DualSense, como MEDIDA nos aparelhos da
#: bancada. ESPELHO do padrão embutido em `scripts/check_anonymity.sh`; o teste
#: `test_o_check_anonymity_usa_o_mesmo_padrao_de_serial` reprova a divergência.
PADRAO_DE_SERIAL = (
    r"(?<![A-Z0-9])"
    r"[A-Z][0-9]{2}[A-Z0-9][0-9]{2}"
    r"[A-Z0-9]{11}"
    r"(?![A-Z0-9])"
)
SERIAL_DE_FABRICA_RE = re.compile(PADRAO_DE_SERIAL)

#: Um par hexadecimal SOLTO — o vizinho não pode ser outro dígito hexadecimal.
#: É essa fronteira que faz a coluna de offset de um hexdump (`0000`, `0010`) e
#: um `0x00001111` serem PULADOS sem precisar entender o formato do dump.
_PAR_HEX_SOLTO = re.compile(rb"(?<![0-9A-Fa-f])([0-9A-Fa-f]{2})(?![0-9A-Fa-f])")

#: Uma corrida hexadecimal COLADA, de 17 bytes para cima: os 34 dígitos
#: hexadecimais do serial, sem separador nenhum entre eles. Nenhum exemplo
#: literal aqui — o hexadecimal de um prefixo REAL tem 12 dígitos e casa a
#: forma COLADA de um MAC, e foi assim que `test_anonimato_de_fixtures` me
#: reprovou ao primeiro rascunho desta seção. O portão irmão estava certo.
_CORRIDA_HEX_COLADA = re.compile(
    rb"(?<![0-9A-Fa-f])((?:[0-9A-Fa-f]{2}){17,})(?![0-9A-Fa-f])"
)


def mascarar_para_relatorio(serial: str) -> str:
    """A máscara da casa, aplicada à MENSAGEM DE ERRO do próprio portão.

    O portão de MAC imprime o endereço que achou. Este NÃO imprime o serial:
    a saída de portão vai para log de CI, que é público, e um portão que
    republica o segredo para avisar que o segredo vazou não resolveu nada —
    só mudou o vazamento de lugar. Os 6 públicos bastam para achar a linha.
    """
    if len(serial) <= CARACTERES_PUBLICOS_DO_SERIAL:
        return serial
    return serial[:CARACTERES_PUBLICOS_DO_SERIAL] + "#" * (
        len(serial) - CARACTERES_PUBLICOS_DO_SERIAL
    )


def _fluxo_de_hexdump(dados: bytes) -> bytes:
    """Remonta a carga de um hexdump: todo par hexadecimal solto, decodificado.

    A SEGUNDA FORMA, e ela já cobrou o preço uma vez: em 15/08 dois seriais
    reais escaparam de um `grep` porque estavam escritos como BYTES num
    hexdump — pares hexadecimais separados por espaço, um byte ASCII por
    caractere do serial. É a mesma família do resto deste arquivo: a régua
    aplicada numa forma só.

    Remontar o fluxo INTEIRO, e não linha a linha, não é capricho: num dump de
    16 bytes por linha o serial de 17 caracteres ATRAVESSA a quebra, e é
    exatamente o que acontece em
    `docs/data/ensaios-brutos/2026-08-15-E7-cor-do-plastico.txt` (6 caracteres
    numa linha, os 11 da máscara repartidos entre ela e a seguinte).
    """
    return bytes(int(par, 16) for par in _PAR_HEX_SOLTO.findall(dados))


def _ocorrencias_de_serial(dados: bytes) -> list[tuple[str, str]]:
    """(forma, serial mascarado) de todo serial de fábrica CRU em ``dados``.

    Três formas, porque duas já não bastaram nesta casa:

    * ``texto`` — o serial escrito como texto, inclusive dentro de arquivo
      binário (a leitura é por BYTES, então não há binário cego aqui);
    * ``hexdump`` — o serial em pares hexadecimais, atravessando linhas;
    * ``hex colado`` — o serial numa corrida hexadecimal sem separador.
    """
    achados: list[tuple[str, str]] = []
    texto = dados.decode("latin-1")
    for m in SERIAL_DE_FABRICA_RE.finditer(texto):
        achados.append(("texto", mascarar_para_relatorio(m.group(0))))
    for m in SERIAL_DE_FABRICA_RE.finditer(
        _fluxo_de_hexdump(dados).decode("latin-1")
    ):
        achados.append(("hexdump", mascarar_para_relatorio(m.group(0))))
    for corrida in _CORRIDA_HEX_COLADA.finditer(dados):
        bruto = bytes.fromhex(corrida.group(1).decode("ascii")).decode("latin-1")
        for m in SERIAL_DE_FABRICA_RE.finditer(bruto):
            achados.append(("hex colado", mascarar_para_relatorio(m.group(0))))
    return achados


def test_nenhum_serial_de_fabrica_real_no_repo() -> None:
    """Nenhum arquivo versionado carrega serial de fábrica sem a máscara da casa.

    Para arrancar e ver morder: escreva um serial na forma real (monte-o por
    concatenação, nunca por extenso) em qualquer arquivo da árvore e rode este
    teste.

    E para ver o LADO OPOSTO — que o aperto contra falso positivo é o que
    segura o portão de pé — afrouxe os quatro `[0-9]` do `PADRAO_DE_SERIAL`
    para `[A-Z0-9]`: o padrão vira `[A-Z][A-Z0-9]{16}` e as palavras compridas
    do repositório passam a reprovar. Afrouxar SÓ as posições 2-3 não basta
    para produzi-las: as posições 5-6 sozinhas já barram toda palavra.
    """
    repo_root = Path(__file__).resolve().parents[2]
    violacoes: list[str] = []
    for path in _tracked_files(repo_root):
        try:
            dados = path.read_bytes()
        except (OSError, IsADirectoryError):
            continue
        for forma, mascarado in _ocorrencias_de_serial(dados):
            violacoes.append(
                f"{path.relative_to(repo_root)} ({forma}): "
                f"SERIAL DE FÁBRICA real, sem máscara ({mascarado})"
            )
    assert not violacoes, (
        "SERIAL DE FÁBRICA de aparelho REAL em arquivo versionado. Ele "
        "identifica a unidade tão bem quanto o MAC. Máscara da casa: os "
        f"{CARACTERES_PUBLICOS_DO_SERIAL} primeiros caracteres e o resto em "
        "'#' (a COR, nos caracteres 5 e 6, fica preservada):\n"
        + "\n".join(violacoes)
    )


def _serial_forjado_na_forma_real() -> str:
    """Um serial FORJADO que tem a forma real — montado, nunca escrito.

    Este arquivo é varrido pelo portão que ele mesmo define. Um exemplo na
    forma real escrito por extenso aqui reprovaria a suíte inteira, e a saída
    seria alguém afrouxar o regex para caber o exemplo — que é como portão
    morre. O prefixo é inventado de propósito: NÃO é o de nenhum dos quatro
    aparelhos da bancada.
    """
    return "Q" + "88" + "X" + "77" + "K" + "9876543210"


def test_o_serial_de_fabrica_em_texto_reprova_e_a_mascara_passa() -> None:
    """A mordida da forma 1: texto puro."""
    forjado = _serial_forjado_na_forma_real()
    assert len(forjado) == 17
    achados = _ocorrencias_de_serial(f"  SERIAL ... {forjado}\n".encode())
    assert achados == [("texto", "Q88X77###########")], achados

    mascarado = forjado[:CARACTERES_PUBLICOS_DO_SERIAL] + "#" * 11
    assert not _ocorrencias_de_serial(f"  SERIAL ... {mascarado}\n".encode())


def _como_hexdump(carga: bytes) -> bytes:
    """A carga escrita como o E7 a escreve: offset, 16 bytes por linha.

    É o formato exato de
    `docs/data/ensaios-brutos/2026-08-15-E7-cor-do-plastico.txt`, e é o que
    faz o serial de 17 caracteres ATRAVESSAR a quebra de linha.
    """
    linhas = []
    for offset in range(0, len(carga), 16):
        pares = " ".join(f"{b:02x}" for b in carga[offset : offset + 16])
        linhas.append(f"    {offset:04x}  {pares}")
    return ("\n".join(linhas) + "\n").encode("ascii")


def test_o_serial_de_fabrica_em_hexdump_reprova_atravessando_a_linha() -> None:
    """A mordida da forma 2: bytes num hexdump, repartidos em duas linhas.

    Reproduz o dump do E7 byte por byte — 16 bytes por linha, coluna de offset
    na frente — com o serial forjado no lugar do real. Se a varredura fosse
    linha a linha, ou se a coluna de offset entrasse no fluxo, isto passaria.

    Para arrancar e ver morder: troque `_fluxo_de_hexdump` por uma varredura
    que quebre a entrada em linhas.
    """
    forjado = _serial_forjado_na_forma_real().encode("ascii")
    carga = bytes([0x81, 0x01, 0x13, 0x02]) + forjado

    formas = [forma for forma, _ in _ocorrencias_de_serial(_como_hexdump(carga))]
    assert "hexdump" in formas, (
        "o serial em hexdump tem de reprovar; o portão viu " + repr(formas)
    )

    # E o mesmo dump, com a máscara aplicada EM HEXADECIMAL (0x23 = '#'),
    # que é o que `cor_do_plastico.py` grava, tem de passar.
    carga_mascarada = carga[: 4 + CARACTERES_PUBLICOS_DO_SERIAL] + b"#" * 11
    assert not _ocorrencias_de_serial(_como_hexdump(carga_mascarada))


def test_o_serial_de_fabrica_em_hexadecimal_colado_reprova() -> None:
    """A mordida da forma 3: a corrida hexadecimal sem separador nenhum."""
    forjado = _serial_forjado_na_forma_real().encode("ascii")
    colado = ("payload=" + forjado.hex() + "\n").encode("ascii")
    formas = [forma for forma, _ in _ocorrencias_de_serial(colado)]
    assert "hex colado" in formas, formas


def test_o_portao_de_serial_nao_reprova_palavra_comprida_nem_forjado() -> None:
    """O aperto contra falso positivo, exercido nos casos que ele custou medir.

    As 12 reprovações que `[A-Z0-9]{17}` solto produzia na árvore de 15/08,
    reduzidas aos seus representantes. Enquanto as quatro posições de DÍGITO
    (2, 3, 5 e 6) estiverem no padrão, nenhuma delas casa — MEDIDO: basta UMA
    das quatro de pé para barrar toda palavra da lista, porque nenhuma tem
    dígito em posição nenhuma. Este teste cai no dia em que alguém as afrouxar
    todas, antes de o ruído chegar a quem roda o portão.
    """
    ruido = (
        "MICROCASSYVOLTAGE",  # assets/dkms/*/hid-ids.h
        "MICROCASSYCURRENT",
        "INDEPENDENTEMENTE",  # docs/data/mapa-controles.csv, specs.html
        "PROGRAMATICAMENTE",  # transcrito de agente
        "REDIMENSIONAMENTO",  # scripts/gui-captura/retratar_abas.py
        "AB1C05D1234567890",  # forjado da docstring de mascarar_serial()
        "ZZ9Y02Q0000000000",  # forjado de test_cor_do_plastico_recusa_o_alvo_errado
    )
    for palavra in ruido:
        assert len(palavra) == 17, palavra
        assert not SERIAL_DE_FABRICA_RE.search(palavra), (
            f"{palavra} não é serial de fábrica e o portão não pode reprová-la"
        )

    # E um sha256 maiúsculo que por acaso contenha a forma no meio: a fronteira
    # alfanumérica das duas pontas é o que impede o portão de picotá-lo.
    sha_falso = "AB" + _serial_forjado_na_forma_real() + "CD" * 20
    assert not SERIAL_DE_FABRICA_RE.search(sha_falso)


def test_o_check_anonymity_usa_o_mesmo_padrao_de_serial() -> None:
    """As duas cópias do padrão têm de ser a MESMA — divergência é buraco.

    `scripts/check_anonymity.sh` é a segunda linha, para quem roda só o script;
    este arquivo é o portão autoritativo. Se as duas réguas divergirem, uma
    delas devolve verde onde a outra reprova, e a próxima pessoa acredita na
    que falou primeiro. Mesmo desenho de
    `tests/unit/test_mascarar_btsnoop.py`, que compara as listas de OUI.
    """
    repo_root = Path(__file__).resolve().parents[2]
    script = (repo_root / "scripts" / "check_anonymity.sh").read_text(
        encoding="utf-8"
    )
    assert "SERIAL" in script, (
        "o check_anonymity.sh voltou a ser cego a serial de fábrica"
    )
    # O padrão vive lá quebrado em pedaços, um por linha, como aqui. A
    # comparação é entre os VALORES remontados, e não entre os textos: exigir
    # a mesma quebra de linha nas duas cópias seria um portão sobre estilo.
    bloco = re.search(r"^PADRAO = \((.*?)^\)$", script, re.S | re.M)
    assert bloco, "não achei a atribuição `PADRAO = (...)` no check_anonymity.sh"
    remontado = "".join(re.findall(r'r"([^"]*)"', bloco.group(1)))
    assert remontado == PADRAO_DE_SERIAL, (
        "o padrão de serial do script divergiu do deste arquivo.\n"
        f"  script: {remontado}\n"
        f"  aqui:   {PADRAO_DE_SERIAL}"
    )
