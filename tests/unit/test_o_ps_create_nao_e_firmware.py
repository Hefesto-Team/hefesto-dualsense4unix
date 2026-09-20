"""O-PS-CREATE-NAO-E-FIRMWARE-01 — a porta que está aberta e a prosa dizia fechada.

Em 19/09/2026 esta casa afirmou que pôr o DualSense em modo de pareamento «é
firmware, não há verbo, D-Bus nem sysfs que faça isso». A conclusão prática
está certa — hoje a mão dela é necessária. **A razão está errada**, e é a razão
que a próxima pessoa lê.

O feature report `0x0A` «Set Bluetooth Pairing» grava host + link key no
controle POR CABO, e está documentado nesta árvore desde antes. Quem ler «é
firmware, não dá» fecha uma porta aberta.

Regra desta casa: *fato errado se SUBSTITUI, e sai de TODOS os lugares onde
aparece.* Estas réguas guardam os dois lugares.
"""

from __future__ import annotations

import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
USO = RAIZ / "docs" / "usage" / "bluetooth.md"
GUIA = RAIZ / "GUIA-RADIO-DA-SALA.md"
PROTOCOLO = RAIZ / "docs" / "protocol" / "dualsense-plataforma-e-identidade.md"


def test_o_protocolo_ainda_documenta_o_report_0a() -> None:
    # A correção INTEIRA se apoia neste documento. Se ele mudar de forma, a
    # prosa dos outros dois vira ponteiro morto — e um grau de confiança sem
    # endereço desce de nível nesta casa.
    texto = PROTOCOLO.read_text(encoding="utf-8")
    assert "Set Bluetooth Pairing" in texto, (
        "o «Set Bluetooth Pairing» saiu do documento de protocolo, e as duas "
        "correções de prosa que apontam para ele viraram ponteiro morto."
    )
    assert "0x0A" in texto


def _corrido(arquivo: Path) -> str:
    """O texto com as quebras de linha da prosa desfeitas.

    Uma frase de markdown atravessa a coluna 79 e vira duas linhas. Procurar a
    frase literal no arquivo cru falha por causa disso — e uma régua que
    reprova por quebra de linha ensina a próxima pessoa a escrever pior.
    """
    return re.sub(r"\s+", " ", arquivo.read_text(encoding="utf-8"))


def test_a_prosa_de_uso_diz_a_razao_certa() -> None:
    texto = _corrido(USO)
    assert "ninguém construiu a alternativa" in texto, (
        "a razão certa não está em docs/usage/bluetooth.md"
    )
    assert "0x0A" in texto, "a prosa afirma sem dar o endereço da porta"


def test_a_prosa_de_uso_traz_as_tres_ressalvas() -> None:
    # Sem as ressalvas, a correção vira convite: alguém implementa o 0x0A
    # achando que é caminho pronto. Ele nunca foi medido no aparelho, não está
    # implementado, e o próprio documento de protocolo desaconselha a escrita.
    texto = USO.read_text(encoding="utf-8")
    for agulha, porque in (
        ("afirmado-no-doc", "o grau de confiança: nenhum byte saiu para o aparelho"),
        ("não está implementado", "não há uma linha de código que escreva o 0x0A"),
        ("desaconselha", "mal formado, o 0x0A reescreve o pareamento de um controle em uso"),
    ):
        assert agulha in texto, f"falta a ressalva sobre {porque}"


def test_o_guia_do_radio_tambem_foi_corrigido() -> None:
    # Correção pela metade deixa as duas versões vivas — que é o defeito que a
    # regra existe para matar.
    texto = GUIA.read_text(encoding="utf-8")
    assert "NINGUÉM CONSTRUIU" in texto, (
        "o §6.3 do guia ainda deixa o PS + Create sem razão — e é ele que quem "
        "move um controle entre adaptadores lê."
    )
    assert "0x0A" in texto


def test_a_afirmacao_errada_nao_voltou() -> None:
    proibido = ("é firmware", "e firmware,")
    for arquivo in (USO, GUIA):
        texto = arquivo.read_text(encoding="utf-8")
        for linha in texto.splitlines():
            baixa = linha.lower()
            if any(p in baixa for p in proibido) and "ps + create" in baixa:
                # A frase só pode aparecer dizendo que ela está ERRADA.
                assert "errada" in baixa or "engano" in baixa, (
                    f"{arquivo.name}: a afirmação derrubada voltou:\n  {linha}"
                )
