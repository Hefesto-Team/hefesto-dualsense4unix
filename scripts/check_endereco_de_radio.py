#!/usr/bin/env python3
"""check_endereco_de_radio.py — nenhum endereço de rádio REAL em arquivo versionado.

POR QUE ELE NASCEU, e o que ele NÃO é
--------------------------------------
**Ele não é o primeiro portão de endereço desta casa, e a primeira versão desta
docstring dizia que era.** O autoritativo é
``tests/unit/test_docs_mac_anonimato.py``, de **15/08/2026**, que já cobria as
três formas — separada, colada e **binária**, nas duas ordens de byte. O erro
de diagnóstico foi olhar só os scripts do bloco "Antes de fechar qualquer leva"
do ``GUIA.md`` e não ver o teste.

**Então por que este existe.** As réguas são diferentes, e a diferença foi
medida em 25/08/2026. O irmão só entra em contrato quando os **três primeiros
octetos casam com um OUI real da bancada**, que ele lista. Isso lhe dá um ponto
cego **estrutural**:

    máscara aplicada nos octetos ERRADOS  ->  come um byte do OUI
    o prefixo deixa de casar com a lista  ->  o endereço sai do contrato
    o portão autoritativo fica VERDE      ->  e o sufixo, que é o que
                                              identifica a unidade, fica à mostra

Foi exatamente o que aconteceu com ``scripts/ensaios/README.md``: o endereço
publicado tinha o OUI escondido e o sufixo exposto — o inverso do pretendido —
e passou. **Este portão pega por FORMA, sem consultar OUI nenhum**, e por isso
alcança o que o outro não pode alcançar.

**Duas réguas independentes é o que revela.** É regra desta casa, e aqui ela
está aplicada de propósito: nenhum dos dois é redundante com o outro.

AS DUAS FORMAS, e a segunda é a que ninguém lembra
---------------------------------------------------
1. ``AA:BB:CC:DD:EE:FF``  — o formato MAC
2. ``AABBCCDDEEFF``       — o mesmo endereço como serial USB, que é como
   ``/sys/bus/usb/devices/*/serial`` o publica nos dongles Realtek/TP-Link

A MÁSCARA DA CASA é a exceção: **octetos 4 e 5 zerados**. ``AA:BB:CC:00:00:FF``
e ``AABBCC0000FF`` passam — são a forma segura de escrever.

**Os exemplos acima são o endereço DIDÁTICO da casa, e isso não é detalhe.** A
primeira versão desta docstring trazia o endereço REAL da mantenedora como
"antes" da máscara — e nenhum portão viu, porque este arquivo excluía a SI MESMO
da varredura. Auto-isenção escondendo vazamento é o pior formato que um portão
pode ter. A exclusão continua (senão os exemplos se acusariam), e por isso a
regra aqui é dura: **neste arquivo, só endereço didático.**

O QUE ELE NÃO ACUSA, e cada exceção foi medida contra a árvore de 24/08
------------------------------------------------------------------------
Um portão barulhento treina a pessoa a ignorá-lo, então cada falso positivo
desta árvore virou uma regra escrita, não uma exclusão de caminho:

* **hífen não é separador de MAC aqui.** ``23:16:22-23:16:39`` — um intervalo de
  horas do journal — casa como seis grupos hexadecimais. Nesta casa endereço se
  escreve com ``:``; o hífen produziu falso positivo em cinco arquivos de
  estudo, e saiu.
* **``02:`` é endereço FABRICADO**, não de ninguém: os drivers ``hid-nintendo``
  e ``hid-playstation`` compõem ``02`` + VID + PID + bus quando o aparelho não
  tem endereço próprio. Documentado em ``assets/dkms/*/README.md``.
* **``AA:BB:`` é o MAC didático** dos exemplos, mockups e tooltips.
* **serial que é só dígito não é OUI.** Doze hexadecimais sem uma letra é hash,
  carimbo ou soma — não endereço.

A LISTAGEM é ``git ls-files`` + leitura, NUNCA ``git grep``. E a listagem tem de
levar ``--cached --others --exclude-standard``, senão a troca não resolve nada.

**CORREÇÃO DE FATO (26/08/2026).** Este parágrafo dizia que a cicatriz
ANONIMATO-CEGO-A-ARQUIVO-NOVO-01 estava curada aqui, e ela NÃO estava: a
chamada era ``git ls-files -z`` pelado, que enxerga só o ÍNDICE — exatamente a
mesma cegueira do ``git grep`` que o parágrafo dizia ter evitado. Trocar a
BUSCA pela LISTA não bastava; o que cura é a LISTA trazer o arquivo novo.
Medido nesta árvore, com um endereço de aparência real (a regra deste arquivo
proíbe repeti-lo aqui) num arquivo recém-escrito::

    sem ``git add``   ->  "OK: nenhum endereço de rádio real…"  rc=0
    com ``git add``   ->  "FALHA: 1 endereço(s)…"               rc=1

A cura já estava pronta no irmão desde 15/08 — ``test_docs_mac_anonimato.py``,
``_tracked_files``, cicatriz ANONIMATO-CEGO-A-ARQUIVO-NOVO-02 — e foi copiada
para cá. ``--exclude-standard`` mantém o ``.gitignore`` respeitado.

**``.svg`` NÃO é binário, e saiu do ``EXCLUIR_SUFIXO`` no mesmo dia.** São 49
arquivos versionados, todos texto puro (``file --mime-encoding``: 46 utf-8, 3
us-ascii). Enquanto o sufixo estava na lista, um endereço dentro de um SVG
passava **mesmo já commitado** — não era cegueira a arquivo novo, era um buraco
permanente. A companhia do ``.png`` era analogia, não medição: em PNG doze
hexadecimais são bytes comprimidos casando por acaso; num SVG são caracteres
que alguém digitou.

OS PEDAÇOS DO ACUSADO (O-REGISTRO-COPIADO-NAO-ENTREGA-O-ENDERECO-01, 28/09/2026)
--------------------------------------------------------------------------------
Um endereço que vazou inteiro raramente vazou uma vez só: o mesmo relato traz o
nome do nó, o despejo do report com os bytes invertidos, a janela colada. Por
forma, esta régua não vê esses pedaços — sem o endereço, três octetos soltos
não são nada. Com ele, são: cada endereço acusado aqui tem as suas janelas
(``core/formas_do_endereco.formas_do_endereco``, nas duas ordens e em toda
grafia) procuradas na árvore inteira, e a linha que carrega uma delas sai
acusada junto, sem imprimir o valor. Limpar só a linha do endereço inteiro
deixaria o resto dele para a próxima pessoa achar.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if (RAIZ / "src").is_dir() and str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco

#: Binário e artefato onde doze hexadecimais são ruído, não endereço.
#:
#: ``.svg`` SAIU daqui em 26/08/2026: é XML de texto puro, e o que estava dentro
#: dele nunca foi varrido — nem depois do commit. Ver a docstring do módulo.
EXCLUIR_SUFIXO = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".mo", ".woff", ".woff2", ".zip", ".xz", ".sha256",
}
#: ``.gz`` SAIU daqui em 26/08/2026, e a cura já estava escrita na casa desde
#: 23/08 — no comentário do ``check_anonymity.sh``: *"A cura NÃO é acrescentar
#: '.gz' ao PULA: isso cegaria o portão para um MAC de verdade dentro de um
#: comprimido. A cura é olhar o CONTEÚDO."* O irmão descomprime desde então;
#: este pulava. Medido em 26/08: o mesmo endereço, em texto, dentro de um
#: ``.csv.gz`` versionado saía rc=0; como ``.csv`` cru, rc=1 nomeando o arquivo.
#: E a segunda régua NÃO cobria esta: o ``check_anonymity.sh`` descomprime, mas
#: só procura os oito OUIs da bancada em BYTES CRUS — um MAC em TEXTO dentro de
#: um ``.gz`` não era visto por portão nenhum desta casa. Há cinco ``.csv.gz``
#: versionados hoje (``docs/process/estudos/dados/``); os cinco foram
#: descomprimidos e conferidos: zero endereços. O buraco era LATENTE, e fechou.
#: Caminhos cujo conteúdo é lista de soma — doze hex por linha, de propósito.
EXCLUIR_CAMINHO = {
    "docs/usage/assets/PROVA-DA-FOTO.txt",
    "scripts/check_endereco_de_radio.py",   # este arquivo cita os exemplos
    "scripts/check_o_endereco_dela_em_toda_forma.py",  # cita o exemplo da máscara
    "poetry.lock", "package-lock.json", "flake.lock",
}

MAC = re.compile(r"\b([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}):"
                 r"([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\b")

#: Marcador de FIXTURE DELIBERADO, no molde do `ref-externa` do
#: `validar-referencias-docs.py`. Existe porque há um caso legítimo e medido: a
#: `INFRA-DE-EXECUCAO-01` planta um endereço de aparência real numa entrega
#: dublê **para provar que a costura o RECUSA** — é mordida de segurança, e o
#: endereço tem o OUI de um fabricante com um sufixo inventado (`23:45:67`), o
#: que identifica a marca e ninguém mais.
#:
#: A isenção é de LINHA e exige motivo escrito. Sem ela, a alternativa era
#: excluir o arquivo inteiro — e aí um endereço de verdade entraria por ali sem
#: ninguém ver, que é como um portão vira decoração.
ISENCAO = re.compile(r"<!--\s*endereco-de-mentira\s*:\s*\S")
SERIAL = re.compile(r"(?<![0-9A-Fa-f])([0-9A-Fa-f]{12})(?![0-9A-Fa-f])")

#: Sufixos de GUID PÚBLICO que parecem serial, um por um e com a origem.
#:
#: Não se pula "todo fim de GUID", e o motivo é medido: GUID de versão 1 guarda
#: no último grupo o MAC da máquina que o gerou (o `uuid.uuid1()` do Python faz
#: isso até hoje). O próprio KSCATEGORY_AUDIO é versão 1 (`11D0`) e o
#: `00A0C9` dele é um OUI de verdade — de uma máquina da Microsoft em 1996, não
#: de quem joga. Constante do SDK é pública; o GUID gerado aqui não seria.
CONSTANTES_DE_ESPECIFICACAO = {
    # UUID BASE do Bluetooth SIG (`00001101-0000-1000-8000-00805F9B34FB`),
    # que aparece em todo lugar que fala de perfil BT.
    "00805F9B34FB",
    # KSCATEGORY_AUDIO (`{6994AD04-93EF-11D0-A3CC-00A0C9223196}`), a classe de
    # interface que a RE Engine enumera para achar a háptica do DualSense
    # (`integrations/audio_ks_dualsense.py`).
    "00A0C9223196",
}


def mascarado(o4: str, o5: str) -> bool:
    """A máscara da casa: octetos 4 e 5 zerados."""
    return o4 == "00" and o5 == "00"


def sintetico(octetos: list[str]) -> bool:
    """Endereço que não identifica ninguém: fabricado, didático ou reservado."""
    o1, o2 = octetos[0], octetos[1]
    if o1 == "02":                       # fabricado pelo driver (02+VID+PID+bus)
        return True
    if (o1, o2) == ("AA", "BB"):         # o didático dos exemplos e mockups
        return True
    if all(o == "FF" for o in octetos):  # broadcast — nunca é identidade
        return True
    return all(o == "00" for o in octetos)  # endereço nulo


def acusa_mac(linha: str) -> list[str]:
    achados = []
    for m in MAC.finditer(linha):
        o = [g.upper() for g in m.groups()]
        if mascarado(o[3], o[4]) or sintetico(o):
            continue
        achados.append(m.group(0))
    return achados


def acusa_serial(linha: str) -> list[str]:
    achados = []
    for m in SERIAL.finditer(linha):
        s = m.group(1).upper()
        if s[6:10] == "0000":          # a máscara da casa, sem separador
            continue
        if not re.search(r"[A-F]", s):  # só dígito: hash ou carimbo, não OUI
            continue
        # SHA CURTO DE GIT TEM EXATAMENTE DOZE HEX, e foi o falso positivo que
        # mais apareceu: 85 achados na árvore de 24/08, quase todos hash de
        # commit em patch de DKMS e em relatório de agente. O discriminador
        # medido nesta árvore: os seriais que o kernel publica nos dongles
        # Realtek/TP-Link são MAIÚSCULOS; hash de git é minúsculo por
        # construção (`git rev-parse` nunca devolve maiúscula).
        # HEURÍSTICA, e a limitação está escrita: um serial minúsculo passaria.
        # A forma que importa — a que o /sys entrega e um agente copia — é a
        # maiúscula, e é essa que o portão fecha.
        if m.group(1) != s:            # veio minúsculo: hash, não serial
            continue
        if s[:2] == "02":              # fabricado pelo driver
            continue
        if s[:4] == "AABB":            # o didático
            continue
        if s in CONSTANTES_DE_ESPECIFICACAO:
            continue
        achados.append(m.group(1))
    return achados


#: O-SUFIXO-DO-NO-NAO-ENTREGA-O-ENDERECO-01 (27/09/2026): o nome de nó de som
#: leva os octetos 4, 5 e 6 do controle (`nome_do_sink`). Ao lado do endereço
#: mascarado do mesmo controle, ele devolve o endereço inteiro. A forma da casa
#: é `hefesto_som_0000FF`. Em `tests/`, a fixture sintética pode ter qualquer
#: sufixo; quem pergunta ao dono se ele é dela é o
#: `check_o_endereco_dela_em_toda_forma.py`.
NO_DE_SOM = re.compile(
    r"(?:hefesto_(?:som|mic|haptica|hapt|dualsense_bt)_|HEFESTO)([0-9A-Fa-f]{6})(?![0-9A-Fa-f])"
)


def acusa_no(linha: str) -> list[str]:
    """Nomes de nó de som cujo sufixo não está mascarado (`0000` e o octeto 6)."""
    return [m.group(0) for m in NO_DE_SOM.finditer(linha) if m.group(1)[:4] != "0000"]


#: Uma corrida de três octetos ou mais com o MESMO separador, ou seis hex
#: colados ou mais: onde uma janela de três octetos pode morar.
_CORRIDA = re.compile(
    r"(?i)(?<![0-9a-f])(?:[0-9a-f]{2}([:\-_. ])[0-9a-f]{2}(?:\1[0-9a-f]{2})+|[0-9a-f]{6,})"
    r"(?![0-9a-f])"
)


def octetos_de(achado: str) -> tuple[str, ...] | None:
    """Os seis octetos (minúsculos) de um endereço acusado, em qualquer grafia."""
    hexa = re.sub(r"[^0-9A-Fa-f]", "", achado).lower()
    return tuple(hexa[i:i + 2] for i in range(0, 12, 2)) if len(hexa) == 12 else None


def pedacos_dos_acusados(acusados: list[tuple[str, ...]]) -> dict[str, str]:
    """As janelas de cada endereço acusado, pelo dono → o rótulo (`A<n>`), sem valor."""
    pedacos: dict[str, str] = {}
    for n, octetos in enumerate(acusados):
        for pedaco in formas_do_endereco(octetos):
            pedacos.setdefault(pedaco.lower(), f"A{n}")
    return pedacos


def acusa_pedaco(linha: str, pedacos: dict[str, str]) -> list[str]:
    """Os rótulos dos acusados que têm uma janela nesta linha.

    A corrida colada se alinha pelo começo dela, como a do dono.
    """
    rotulos = []
    for m in _CORRIDA.finditer(linha):
        separador = m.group(1) or ""
        corrida = m.group(0).lower()
        octetos = (corrida.split(separador) if separador
                   else [corrida[i:i + 2] for i in range(0, len(corrida) - 1, 2)])
        for i in range(len(octetos) - 2):
            rotulo = pedacos.get(separador.join(octetos[i:i + 3]))
            if rotulo:
                rotulos.append(rotulo)
    return rotulos


def arquivos_versionados() -> list[Path]:
    try:
        saida = subprocess.run(
            # `--cached --others --exclude-standard`: o rastreado E o novo, sem
            # o ignorado. Sem os três, `git ls-files` lê só o ÍNDICE e o portão
            # cala no arquivo que ninguém revisou ainda — ver a docstring do
            # módulo (ANONIMATO-CEGO-A-ARQUIVO-NOVO-01, curada aqui em 26/08).
            ["git", "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            cwd=RAIZ, check=True,
            capture_output=True, text=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return sorted(p for p in RAIZ.rglob("*") if p.is_file())
    fora = []
    for nome in saida.split("\0"):
        if not nome:
            continue
        if nome in EXCLUIR_CAMINHO:
            continue
        p = RAIZ / nome
        if p.suffix.lower() in EXCLUIR_SUFIXO:
            continue
        fora.append(p)
    return fora


def _texto_de(p: Path) -> str | None:
    """O texto do arquivo — e o de DENTRO dele, quando é comprimido.

    Espelha o ``_conteudo()`` do ``check_anonymity.sh``, que faz isto desde
    23/08/2026. Um ``.gz`` ilegível ou que não seja texto devolve ``None`` em
    vez de levantar: portão que morre no primeiro arquivo estranho é portão que
    alguém desliga, e a varredura tem de chegar ao fim.
    """
    if p.suffix.lower() == ".gz":
        import gzip
        try:
            return gzip.decompress(p.read_bytes()).decode("utf-8", errors="strict")
        except (OSError, EOFError, UnicodeDecodeError, gzip.BadGzipFile):
            return None
    return p.read_text(encoding="utf-8", errors="strict")


def main() -> int:
    achados: list[str] = []
    acusados: list[tuple[str, ...]] = []
    lidos: list[Path] = []
    for p in arquivos_versionados():
        try:
            texto = _texto_de(p)
        except (UnicodeDecodeError, OSError):
            continue                    # binário ou ilegível: não é nosso caso
        if texto is None:
            continue
        rel = p.relative_to(RAIZ)
        lidos.append(p)
        for n, linha in enumerate(texto.splitlines(), 1):
            if ISENCAO.search(linha):
                continue
            for a in acusa_mac(linha):
                achados.append(f"{rel}:{n}: MAC real    {a}")
                acusados.append(octetos_de(a) or ())
            for a in acusa_serial(linha):
                achados.append(f"{rel}:{n}: serial USB  {a}")
                acusados.append(octetos_de(a) or ())
            if not str(rel).startswith("tests/"):
                for a in acusa_no(linha):
                    achados.append(f"{rel}:{n}: nó de som   {a}")

    pedacos = pedacos_dos_acusados([o for o in dict.fromkeys(acusados) if o])
    ja = {a.split(": ", 1)[0] for a in achados}
    for p in lidos if pedacos else ():
        rel = p.relative_to(RAIZ)
        for n, linha in enumerate((_texto_de(p) or "").splitlines(), 1):
            if f"{rel}:{n}" in ja or ISENCAO.search(linha):
                continue
            for rotulo in sorted(set(acusa_pedaco(linha, pedacos))):
                achados.append(f"{rel}:{n}: pedaço do endereço acusado {rotulo}")

    if achados:
        print(f"FALHA: {len(achados)} endereço(s) de rádio REAL em arquivo versionado.\n")
        for a in achados[:40]:
            print("  " + a)
        if len(achados) > 40:
            print(f"  … e mais {len(achados) - 40}.")
        print("\nA máscara da casa zera os octetos 4 e 5:")
        print("  AA:BB:CC:DD:EE:FF  ->  AA:BB:CC:00:00:FF")
        print("  AABBCCDDEEFF       ->  AABBCC0000FF")
        print("  hefesto_som_DDEEFF ->  hefesto_som_0000FF")
        print("\nSe o achado NÃO for endereço (hash, carimbo, UUID), acrescente o")
        print("caminho a EXCLUIR_CAMINHO neste arquivo, com o motivo escrito ao lado.")
        return 1

    print("OK: nenhum endereço de rádio real em arquivo versionado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
