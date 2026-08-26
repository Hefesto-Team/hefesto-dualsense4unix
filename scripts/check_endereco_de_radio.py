#!/usr/bin/env python3
"""check_endereco_de_radio.py — nenhum endereço de rádio REAL em arquivo versionado.

POR QUE ELE NASCEU, e o que ele NÃO é
--------------------------------------
**Ele não é o primeiro portão de endereço desta casa, e a primeira versão desta
docstring dizia que era.** O autoritativo é
``tests/unit/test_docs_mac_anonimato.py``, de **15/08/2026**, que já cobria as
três formas — separada, colada e **binária**, nas duas ordens de byte. O erro
de diagnóstico foi olhar só os scripts do bloco "Antes de fechar qualquer leva"
do ``CLAUDE.md`` e não ver o teste.

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
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

#: Binário e artefato onde doze hexadecimais são ruído, não endereço.
#:
#: ``.svg`` SAIU daqui em 26/08/2026: é XML de texto puro, e o que estava dentro
#: dele nunca foi varrido — nem depois do commit. Ver a docstring do módulo.
EXCLUIR_SUFIXO = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf",
    ".mo", ".woff", ".woff2", ".zip", ".gz", ".xz", ".sha256",
}
#: Caminhos cujo conteúdo é lista de soma — doze hex por linha, de propósito.
EXCLUIR_CAMINHO = {
    "docs/usage/assets/PROVA-DA-FOTO.txt",
    "scripts/check_endereco_de_radio.py",   # este arquivo cita os exemplos
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
        # `00805F9B34FB` é o sufixo do UUID BASE do Bluetooth SIG
        # (`00001101-0000-1000-8000-00805F9B34FB`), que aparece em todo lugar
        # que fala de perfil BT. É constante da especificação, não endereço.
        if s == "00805F9B34FB":
            continue
        achados.append(m.group(1))
    return achados


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


def main() -> int:
    achados: list[str] = []
    for p in arquivos_versionados():
        try:
            texto = p.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue                    # binário ou ilegível: não é nosso caso
        rel = p.relative_to(RAIZ)
        for n, linha in enumerate(texto.splitlines(), 1):
            if ISENCAO.search(linha):
                continue
            for a in acusa_mac(linha):
                achados.append(f"{rel}:{n}: MAC real    {a}")
            for a in acusa_serial(linha):
                achados.append(f"{rel}:{n}: serial USB  {a}")

    if achados:
        print(f"FALHA: {len(achados)} endereço(s) de rádio REAL em arquivo versionado.\n")
        for a in achados[:40]:
            print("  " + a)
        if len(achados) > 40:
            print(f"  … e mais {len(achados) - 40}.")
        print("\nA máscara da casa zera os octetos 4 e 5:")
        print("  AA:BB:CC:DD:EE:FF  ->  AA:BB:CC:00:00:FF")
        print("  AABBCCDDEEFF       ->  AABBCC0000FF")
        print("\nSe o achado NÃO for endereço (hash, carimbo, UUID), acrescente o")
        print("caminho a EXCLUIR_CAMINHO neste arquivo, com o motivo escrito ao lado.")
        return 1

    print("OK: nenhum endereço de rádio real em arquivo versionado.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
