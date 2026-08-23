"""A documentação de USO não pode contradizer o código nem o mapa de canais.

POR QUE ESTE ARQUIVO EXISTE
===========================
Em 22/08/2026 a auditoria da luz achou o mesmo byte descrito de duas maneiras
opostas na MESMA árvore: `core/lightbar_reset.py:12-16` chama o `0x08` de
*"A CURA da lightbar por Bluetooth"*, e `core/backend_pydualsense.py:2380-2389`
o chama de *"o CULPADO"*, com 7 eventos de correlação perfeita. O código está
coerente com a decisão de 04/08 — quem não está coerente é o texto.

A regra da casa é que fato errado se SUBSTITUI. O problema é que substituir não
impede a volta: a frase certa de hoje envelhece calada no dia em que o código
mudar. Por isso cada frase corrigida aqui fica presa a uma **fonte viva** — o
código ou o mapa de canais —, nunca a outro texto. Molde:
`tests/unit/test_metricas_a_doc_nao_mente.py`.

O QUE ELE VIGIA, E DE ONDE VEM A VERDADE DE CADA UM
====================================================

1. **O `0x08` (`RELEASE_LEDS`) é instrumento, não cura automática.**
   `docs/usage/cli.md` afirma que o envio automático saiu do produto. A fonte
   viva é o `src/`: `send_release_leds` só pode ser chamado de UM lugar, o
   `enviar_release_leds` — o método sob demanda, cujo próprio docstring diz
   *"NÃO é chamado por caminho automático nenhum"*. Se alguém rearmar a adoção,
   a frase da página vira mentira **no mesmo commit**, e este teste é quem avisa.

2. **O áudio do controle por Bluetooth não é "fora de escopo".**
   `docs/usage/bluetooth.md` dizia, até 22/08/2026, que fone E microfone sem fio
   *"usam protocolo proprietário e continuam fora de escopo"*. O mapa de canais
   já dizia o contrário sobre metade da frase: `audio.microfone@dualsense` tem
   `radio_aciona = parcial`, `medido` — o microfone por rádio está implementado
   por inteiro e nasce em opt-in. A fonte viva aqui é
   `docs/data/mapa-controles.csv`: enquanto ele disser que aciona, a página não
   pode dizer que está fora de escopo.

MORDIDAS (aplicadas uma a uma em 22/08/2026, todas reprovaram)
===============================================================
1. Acrescentar uma segunda chamada de `send_release_leds` em
   `core/backend_pydualsense.py`, dentro do bloco de adoção:
   `test_o_release_leds_so_sai_sob_demanda` reprova nomeando arquivo e linha.
2. Devolver o parágrafo *"Áudio do DualSense por Bluetooth … continua fora de
   escopo"* ao `bluetooth.md`: `test_a_pagina_do_bluetooth_nao_poe_o_audio_fora_de_escopo`
   reprova citando o parágrafo e a célula do mapa que o derruba.
3. Trocar a régua do item 2 por uma leitura do próprio texto (procurar
   "microfone" na página em vez de ler o CSV):
   `test_a_regua_do_audio_le_o_mapa_e_nao_a_pagina` reprova — a página e a régua
   seriam a mesma fonte, e o portão aprovaria a si mesmo.
"""

from __future__ import annotations

import ast
import csv
import io
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
CLI = RAIZ / "docs" / "usage" / "cli.md"
BLUETOOTH = RAIZ / "docs" / "usage" / "bluetooth.md"

#: O escritor cru do `0x08`. Quem o chama está mandando o byte.
ESCRITOR = "send_release_leds"

#: O ÚNICO método de produção autorizado a chamá-lo, e o motivo está no
#: docstring dele: "NÃO é chamado por caminho automático nenhum: se um dia o
#: reset voltar à adoção, ele volta lá, com a sua própria decisão e o seu
#: próprio teste". Este teste é o "próprio teste" da frase.
SOB_DEMANDA = "enviar_release_leds"

#: A célula do mapa que responde pelo microfone no rádio.
LINHA_DO_MICROFONE = "audio.microfone@dualsense"
COLUNA_DO_MICROFONE = "radio_aciona"
ACIONA = frozenset({"sim", "parcial"})

FORA_DE_ESCOPO = "fora de escopo"
PALAVRAS_DE_AUDIO = ("microfone", "áudio", "audio")


def _modulos_do_produto() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def _chamadas(caminho: Path, nome: str) -> list[tuple[int, str | None]]:
    """Onde `nome` é CHAMADO, e dentro de qual função — por AST, não por grep.

    Grep contaria o `import`, o `__all__` e cada linha de comentário que cita o
    nome (são nove neste arquivo), e a régua ficaria vermelha para sempre por
    causa de prosa. O que importa é a CHAMADA.
    """
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    dono: dict[int, str] = {}
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef):
            fim = getattr(no, "end_lineno", no.lineno) or no.lineno
            for linha in range(no.lineno, fim + 1):
                # a função mais interna vence
                dono[linha] = no.name

    achadas: list[tuple[int, str | None]] = []
    for no in ast.walk(arvore):
        if not isinstance(no, ast.Call):
            continue
        alvo = no.func
        chamado = (
            alvo.id
            if isinstance(alvo, ast.Name)
            else alvo.attr
            if isinstance(alvo, ast.Attribute)
            else None
        )
        if chamado == nome:
            achadas.append((no.lineno, dono.get(no.lineno)))
    return achadas


def _paragrafos(caminho: Path) -> list[str]:
    return [p.strip() for p in caminho.read_text(encoding="utf-8").split("\n\n") if p.strip()]


def _celula_do_mapa(ident: str, coluna: str) -> str:
    texto = MAPA.read_text(encoding="utf-8")
    for linha in csv.DictReader(io.StringIO(texto)):
        if (linha.get("id") or "").strip() == ident:
            return (linha.get(coluna) or "").strip()
    raise AssertionError(
        f"o mapa de canais não tem mais a linha {ident!r} — a régua deste teste "
        "perdeu a fonte viva e tem de ser reescrita, não desligada"
    )


# ── 1. o 0x08 ───────────────────────────────────────────────────────────────


def test_o_release_leds_so_sai_sob_demanda() -> None:
    """A frase de `cli.md` só é verdadeira enquanto o `src/` for este."""
    fora: list[str] = []
    total = 0
    for modulo in _modulos_do_produto():
        for numero, funcao in _chamadas(modulo, ESCRITOR):
            total += 1
            if funcao != SOB_DEMANDA:
                relativo = modulo.relative_to(RAIZ)
                fora.append(f"{relativo}:{numero} (dentro de {funcao or '<módulo>'})")

    assert total, (
        f"nenhuma chamada de `{ESCRITOR}` em src/ — se o instrumento foi removido, "
        f"{CLI.relative_to(RAIZ)} ainda documenta o comando `lightbar-reset` e "
        "precisa ser reescrito no mesmo gesto"
    )
    assert not fora, (
        f"`{ESCRITOR}` (o `0x08`) voltou a ser chamado fora do caminho sob "
        f"demanda: {', '.join(fora)}. Isso torna FALSA a frase de "
        f"{CLI.relative_to(RAIZ)} — 'o envio automático saiu do produto em "
        "`108b711` (04/08/2026)' — e reabre a LIGHTBAR-BT-CULPADO-01, que "
        "correlacionou 7 de 7 o byte dentro da janela de ~3,4 s com a barra "
        "travada até o power-off"
    )


def test_a_pagina_do_cli_nao_promete_a_cura_automatica() -> None:
    """A página tem de dizer que o envio automático saiu — não que ele cura."""
    texto = CLI.read_text(encoding="utf-8")
    assert "lightbar-reset" in texto, "a página perdeu a seção do instrumento"
    assert "108b711" in texto, (
        f"{CLI.relative_to(RAIZ)} descreve o `lightbar-reset` sem dizer que o "
        "envio automático do `0x08` saiu do produto. Sem essa frase a página "
        "volta a ser a metade da árvore que chama o byte de 'cura', enquanto a "
        "outra metade o chama de culpado"
    )


# ── 2. o áudio por Bluetooth ────────────────────────────────────────────────


def test_a_pagina_do_bluetooth_nao_poe_o_audio_fora_de_escopo() -> None:
    """Enquanto o MAPA disser que o microfone por rádio aciona, a página não pode negar."""
    aciona = _celula_do_mapa(LINHA_DO_MICROFONE, COLUNA_DO_MICROFONE)
    if aciona not in ACIONA:
        return  # o mapa mudou de ideia: a página deixa de estar errada

    culpados = [
        p
        for p in _paragrafos(BLUETOOTH)
        if FORA_DE_ESCOPO in p.lower()
        and any(palavra in p.lower() for palavra in PALAVRAS_DE_AUDIO)
    ]
    assert not culpados, (
        f"{BLUETOOTH.relative_to(RAIZ)} põe o áudio do controle sem fio 'fora de "
        f"escopo', e o mapa de canais diz `{COLUNA_DO_MICROFONE} = {aciona}` em "
        f"`{LINHA_DO_MICROFONE}` — o microfone por rádio está implementado por "
        "inteiro e nasce em opt-in "
        "(HEFESTO_DUALSENSE4UNIX_BT_MIC=1). Parágrafo: "
        + repr(re.sub(r"\s+", " ", culpados[0])[:160])
    )


def test_a_regua_do_audio_le_o_mapa_e_nao_a_pagina() -> None:
    """A régua tem de mudar de resposta quando o MAPA muda — não quando a página muda.

    Sem isto, o teste acima seria a página conferindo a si mesma: bastaria
    apagar a palavra para ficar verde, e a contradição com o mapa seguiria viva.
    """
    origem = Path(__file__).read_text(encoding="utf-8")
    corpo = origem.split("def test_a_pagina_do_bluetooth_nao_poe_o_audio_fora_de_escopo")[1]
    corpo = corpo.split("\ndef ")[0]
    assert "_celula_do_mapa(" in corpo, (
        "a régua do áudio parou de consultar o mapa de canais — sem a fonte "
        "viva, este arquivo vira dois textos concordando entre si"
    )
    assert _celula_do_mapa(LINHA_DO_MICROFONE, COLUNA_DO_MICROFONE) in ACIONA, (
        f"o mapa passou a dizer que `{LINHA_DO_MICROFONE}` NÃO aciona no rádio. "
        f"Se isso for verdade, {BLUETOOTH.relative_to(RAIZ)} precisa voltar a "
        "dizê-lo — e esta régua, a ser reescrita com a medição nova"
    )
