"""BTMGMT-QUE-NAO-VOLTA-01: nenhuma chamada a `btmgmt` pode ficar sem teto.

O defeito, medido em 19/08/2026: numa máquina sem adaptador Bluetooth o
`btmgmt` fala com o socket de management do kernel e espera uma resposta que
nunca vem. Não devolve erro, não devolve saída vazia — não devolve nada. O
`2>/dev/null` não ajuda (não há erro na saída de erro) e o `|| true` não ajuda
(o comando nunca termina para ter código de saída).

O sintoma no produto: `install.sh` trava para sempre no passo 8 de 11, sem uma
linha dizendo por quê, na máquina de qualquer pessoa que instale sem Bluetooth.
Foi assim que o job do Arch morreu no teto de 30 min do CI — e ele foi o único
a pegar porque é o único que instala `bluez-utils`: onde o `btmgmt` não existe,
o `command -v` pula o bloco e o defeito fica invisível.

**Este teste MORDE:** tire o `timeout` de qualquer um dos quatro pontos e ele
reprova nomeando arquivo e linha. É um portão de forma, e de propósito: o único
jeito honesto de provar "não trava" seria rodar sem adaptador, e a máquina de
quem desenvolve tem um.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]

#: Todo arquivo de shell versionado. A busca é por conteúdo, não por lista fixa:
#: uma chamada nova num arquivo novo tem de cair neste portão sozinha.
ARQUIVOS = sorted(
    p
    for p in [*RAIZ.rglob("*.sh"), RAIZ / "install.sh", RAIZ / "uninstall.sh"]
    if p.is_file() and ".git" not in p.parts and "node_modules" not in p.parts
)

#: Uma invocação de `btmgmt` em POSIÇÃO DE COMANDO — não a palavra solta numa
#: frase. A primeira versão desta régua casava o "Nem btmgmt nem bluetoothctl a
#: substituem" de uma mensagem do doctor: um portão que acusa prosa treina quem
#: lê a ignorar. Só conta se vier logo depois de um separador de comando.
#: `command -v btmgmt` é a guarda de existência e nunca bloqueia.
INVOCACAO = re.compile(r"(?:^|[(|;&]|\$\()\s*btmgmt\s+\w")
JA_TEM_TETO = re.compile(r"timeout\s+[\d.]+\s+btmgmt\s")


def test_toda_chamada_a_btmgmt_tem_teto_de_tempo() -> None:
    nuas: list[str] = []
    for arq in ARQUIVOS:
        for n, linha in enumerate(arq.read_text(encoding="utf-8").splitlines(), 1):
            sem_comentario = linha.split("#", 1)[0]
            if "command -v btmgmt" in sem_comentario:
                continue
            if not INVOCACAO.search(sem_comentario):
                continue
            if JA_TEM_TETO.search(sem_comentario):
                continue
            nuas.append(f"{arq.relative_to(RAIZ)}:{n}: {linha.strip()}")

    assert not nuas, (
        "chamada a `btmgmt` SEM teto de tempo — numa máquina sem adaptador ela "
        "não volta, e o install trava para sempre sem dizer por quê:\n  "
        + "\n  ".join(nuas)
        + "\n\nUse `timeout 5 btmgmt ...`. Ver BTMGMT-QUE-NAO-VOLTA-01."
    )


def test_o_portao_enxerga_os_quatro_pontos_conhecidos() -> None:
    """Guarda contra o portão ficar cego — o defeito mais caro desta casa.

    Se um `rglob` mudar, ou a regex parar de casar, o teste acima passaria com
    zero achados e ninguém saberia. Este conta o que ele DEVERIA estar olhando.
    """
    com_teto = sum(
        len(JA_TEM_TETO.findall(arq.read_text(encoding="utf-8"))) for arq in ARQUIVOS
    )
    assert com_teto >= 4, (
        f"o portão só enxerga {com_teto} chamada(s) com teto, e a migração do "
        "BlueZ deixou 4 (bt_active_mode duas vezes, uninstall, doctor). Portão que não "
        "vê nada passa sempre."
    )
