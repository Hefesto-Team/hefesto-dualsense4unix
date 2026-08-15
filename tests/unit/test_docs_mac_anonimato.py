"""Guarda de anonimato de hardware: MAC real NUNCA sai inteiro no repo.

Corretor final (interação entre ondas, achado #4): o desenho da Onda S vazou
os 6 octetos REAIS do adaptador BT e de um controle, quebrando a convenção que
todas as outras ondas seguiram — MAC de hardware real é citado com os 3
últimos octetos mascarados (forma ``OUI:00:00:NN``; nenhum exemplo literal
aqui de propósito — o irmão test_anonimato_de_fixtures proíbe MAC-forma em
tests/ fora das faixas forjadas).
O ``check_anonymity.sh`` é cego a MAC (só caça menções a provedores de IA e
exclui ``docs/process/**``), então este teste é o gate que faltava.

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
_SEP = r"(?P<sep>[:_-])"
MAC_COMPLETO_RE = re.compile(
    r"(?i)\b(?:"
    # forma com separador: d8:44:89:xx:xx:xx
    r"(?P<oui_sep>" + "|".join(OUIS_REAIS) + r")"
    r"[:_-](?P<a>[0-9a-f]{2})[:_-](?P<b>[0-9a-f]{2})[:_-](?P<c>[0-9a-f]{2})"
    r"|"
    # forma colada: d84489xxxxxx
    r"(?P<oui_col>" + "|".join(_OUIS_COLADOS) + r")"
    r"(?P<a2>[0-9a-f]{2})(?P<b2>[0-9a-f]{2})(?P<c2>[0-9a-f]{2})"
    r")\b"
)


def _partes(m: re.Match[str]) -> tuple[str, str, str]:
    """Devolve (oui, octeto4, octeto5) de qualquer uma das duas grafias."""
    if m.group("oui_sep") is not None:
        return m.group("oui_sep"), m.group("a"), m.group("b")
    return m.group("oui_col"), m.group("a2"), m.group("b2")

#: Extensões binárias/geradas — sem texto a auditar.
_SKIP_SUFFIXES = {".png", ".svg", ".mo", ".ico", ".gif", ".jpg", ".jpeg"}


def _tracked_files(repo_root: Path) -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
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
