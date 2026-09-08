"""A mesa do co-op não pergunta por qual fio o controle chegou — e isso é medido.

O PEDIDO DELA, 03/09/2026: *"a ideia é ver o que no código tá setado pra
funcionar só via cabo e não BT"*. Este arquivo é a resposta da área da MESA
(arranjo, ordens, co-op e slots), e ele guarda um achado NEGATIVO — o tipo que
some sozinho se ninguém o defender.

O ACHADO
--------
`daemon/subsystems/coop.py` são 2.004 linhas cuja razão de existir é *"dois na
mesa não é um"*: um leitor evdev com grab por controle físico, um gamepad
virtual por jogador, o LED de jogador de cada um, o espelho de giroscópio e o
rumble roteado por MAC. **Nenhuma delas compara transporte.** Medido por AST em
03/09/2026: das 146 constantes de texto que sobrevivem fora de docstring, zero
é `usb`, `bt`, `bluetooth`, `cabo` ou `radio`, e nenhum atributo ou chave se
chama `transport`.

Os gates que existem lá dentro são de FAMÍLIA e de IDENTIDADE, nunca de fio:

* `identity.startswith("path:")` — controle sem MAC legível não tem alvo estável;
* `discover_dualsense_evdevs()` — fechada em `DUALSENSE_VENDOR`/`DUALSENSE_PIDS`,
  é o que mantém 8BitDo e Nintendo fora da mesa (8BIT-02);
* `vpad.backend != "uhid"` — o uinput é evdev puro e não tem `forward_motion`.

E as duas rotas que o co-op usa para SAIR no aparelho já são as cegas ao fio, de
propósito e com a razão escrita no dono de cada uma:

* `core/sysfs_leds.py:7-8` — a rota sysfs existe porque o report de saída difere
  entre USB e Bluetooth (no rádio precisa de `seq_tag` e CRC-32), *"por isso
  essa rota acende a cor IGUAL em USB e BT"*;
* `core/physical_report_reader.py:396-407` (`_struct_base`) — o espelho de
  movimento aceita o `0x01` de 64 B (base 1) E o `0x31` de 78 B (base 2, com
  CRC-32 conferido).

POR QUE ISTO PRECISA DE PORTÃO
-------------------------------
Porque a forma do defeito que esta casa mais paga é o filtro NOSSO: o aparelho
aceita, e quem recusa é uma linha de código nossa. Em 02/09/2026 a
ONDA-CONEXOES-11 arrancou dois desses da leitura de identidade e `P2 · Não sei ·
BT` virou `P2 · Galactic Purple · BT`; a CANAL-POR-CONTROLE-01 achou outros dois
no microfone. Um `if` de transporte que entrasse no co-op amanhã ficaria mudo do
mesmo jeito — o sintoma é a AUSÊNCIA de dado, não um erro.

Este arquivo é a rede: se alguém escrever um gate de transporte em `coop.py`, ou
apagar o caminho do rádio que a área escreveu em `docs/data/mapa-controles.csv`,
a suíte reprova e diz por quê.
"""

from __future__ import annotations

import ast
import csv
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
COOP = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "subsystems" / "coop.py"
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"

#: As palavras que só um gate de TRANSPORTE escreveria. Comparação por igualdade
#: exata e em minúsculas, nunca por substring: `uhid` é backend, `held` é estado
#: de grab e `path:` é identidade — nenhum dos três fala de fio, e uma régua por
#: substring os acusaria.
PALAVRAS_DE_TRANSPORTE = frozenset(
    {
        "usb",
        "bt",
        "bluetooth",
        "cabo",
        "radio",
        "rádio",
        "wired",
        "wireless",
        "bus_usb",
        "bus_bluetooth",
    }
)

#: Um nome de atributo, argumento ou chave que decidiria por fio.
NOMES_DE_TRANSPORTE = frozenset({"transport", "transporte", "bustype", "bus"})

#: `arquivo.py:N` ou `arquivo.py:N-M`, com o CAMINHO obrigatório — a mesma forma
#: que o `scripts/validar-citacoes-de-linha.py` reconhece dentro de célula.
ENDERECO_DE_COOP = re.compile(
    r"(?<![A-Za-z0-9_./-])`?(?P<arq>[A-Za-z0-9_./-]*coop\.py):(?P<a>\d+)"
    r"(?:-(?P<b>\d+))?`?"
)

#: `(`SIMBOLO`)` logo depois do endereço — a forma que o portão de citações usa
#: para conferir que a faixa contém o que promete.
NOME_DEPOIS = re.compile(r"\s*\(`(?P<nome>[A-Za-z_][A-Za-z0-9_]{2,})`\)")


def _docstrings(arvore: ast.AST) -> set[int]:
    """`id()` dos nós `Constant` que são docstring — prosa, não decisão."""
    fora: set[int] = set()
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(
            no, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
        ):
            continue
        if (
            corpo
            and isinstance(corpo[0], ast.Expr)
            and isinstance(corpo[0].value, ast.Constant)
            and isinstance(corpo[0].value.value, str)
        ):
            fora.add(id(corpo[0].value))
    return fora


def gates_de_transporte(fonte: str) -> list[str]:
    """As decisões por FIO que este módulo toma. Vazio é a promessa desta área.

    Lê por AST e não por `grep` de propósito: o `coop.py` fala de USB e de BT em
    comentário e em docstring o tempo todo (a medição do `_CALIB_PRAZO_S`, o
    ESPELHO-QUE-NAO-NASCEU-01), e uma régua de texto cru acusaria a PROSA. O que
    decide é código, e é só ele que entra aqui.
    """
    arvore = ast.parse(fonte)
    docs = _docstrings(arvore)
    achados: list[str] = []
    for no in ast.walk(arvore):
        if (
            isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docs
            and no.value.strip().lower() in PALAVRAS_DE_TRANSPORTE
        ):
            achados.append(f"linha {no.lineno}: o texto {no.value!r}")
        if isinstance(no, ast.Attribute) and no.attr.lower() in NOMES_DE_TRANSPORTE:
            achados.append(f"linha {no.lineno}: o atributo `.{no.attr}`")
        if isinstance(no, ast.Name) and no.id.lower() in NOMES_DE_TRANSPORTE:
            achados.append(f"linha {no.lineno}: o nome `{no.id}`")
    return achados


def test_o_coop_nao_pergunta_o_transporte() -> None:
    """Nenhuma decisão do co-op olha por qual fio o controle chegou."""
    achados = gates_de_transporte(COOP.read_text(encoding="utf-8"))
    assert not achados, (
        "apareceu decisão de TRANSPORTE em daemon/subsystems/coop.py, e a área "
        "da mesa mediu em 03/09/2026 que não havia nenhuma:\n  "
        + "\n  ".join(achados)
        + "\nSe o gate é legítimo, ele precisa da razão escrita no lugar de onde "
        "não saiu — e desta lista, com a medição que o justifica."
    )


def test_a_regua_morde_um_gate_de_transporte() -> None:
    """A MORDIDA: com um gate de fio plantado, a régua tem de acusar.

    Régua que passa com a cura arrancada não mede nada. O código de mentira
    abaixo é a forma exata do filtro nosso que esta casa achou duas vezes em
    02/09/2026 — um `if` de transporte que devolve cedo e emudece o rádio.
    """
    mentira = (
        'def _pode_sentar(self, aparelho):\n'
        '    """Docstring falando de USB e de BT — isto NÃO pode acusar."""\n'
        '    if aparelho.transport == "bt":\n'
        "        return None\n"
        "    return aparelho\n"
    )
    achados = gates_de_transporte(mentira)
    assert achados, "a régua não viu o gate de transporte plantado"
    assert any("'bt'" in a or '"bt"' in a for a in achados), achados
    assert any("`.transport`" in a for a in achados), achados


def test_a_docstring_sozinha_nao_acusa() -> None:
    """E o contrário: falar de USB e de BT em prosa não é decidir por fio.

    É a metade que impede o portão de proibir a explicação — o `coop.py` mede o
    prazo de calibração citando os dois transportes, e essa frase é o que faz a
    próxima pessoa entender o número.
    """
    prosa = (
        'def _prazo():\n'
        '    """No caminho quente (USB, ou BT com o report_thread vivo) volta em '
        '~1ms."""\n'
        "    return 2.0\n"
    )
    assert gates_de_transporte(prosa) == []


def _linhas_do_mapa() -> dict[str, dict[str, str]]:
    with MAPA.open(encoding="utf-8", newline="") as arquivo:
        return {linha["id"]: linha for linha in csv.DictReader(arquivo)}


def test_a_linha_do_slot_no_radio_tem_o_caminho_escrito() -> None:
    """O caminho do rádio do número de jogador não pode voltar a ficar mudo.

    É o mecanismo que ela descreveu: *"quando colocarmos o caminho certo no
    specs o script original vai fazer uso desse place holder"*. A célula
    `radio_aciona` segue MUDA de propósito (só a bancada responde), mas o
    CAMINHO está escrito, e apagá-lo devolve a linha ao estado em que o produto
    não tinha o que ler.
    """
    linha = _linhas_do_mapa()["combinacao.slot_jogador.estabilidade@dualsense"]
    for coluna in ("radio_canal", "radio_comando", "radio_codigo_ref"):
        assert linha[coluna].strip(), f"`{coluna}` ficou muda de novo"
    assert linha["radio_de_onde_sei"] == "inferido-do-codigo"
    assert "numeros_de_jogador" in linha["radio_codigo_ref"], (
        "o caminho do rádio tem de citar quem decide o número que a tela mostra"
    )


def test_toda_citacao_de_coop_py_no_mapa_nomeia_o_simbolo() -> None:
    """Endereço para `coop.py` numa coluna de código tem de dizer o que promete.

    O DEFEITO QUE ISTO PEGA, medido em 03/09/2026: o mapa carregava CINCO faixas
    de `coop.py` que não continham mais nada do que a célula prometia —
    `:857-885` para o espelho de giroscópio (que mora em `:1181-1255`),
    `:590-636` para os sinks de réplica (`:909-955`), `:560-588` para o sink de
    rumble (`:879-907`), `:655-690` para a criação do vpad (`:804-854` e
    `:957-1048`) e `:304-380` para o filtro que só admite DualSense
    (`:679-683`, dentro do `sync`).

    **As cinco passavam VERDES** no `scripts/validar-citacoes-de-linha.py`, e não
    por falha dele: aquele portão só confere o CONTEÚDO de uma faixa quando a
    citação NOMEIA um símbolo entre crases, e nenhuma das cinco nomeava. Ele
    conferia que o arquivo tinha ao menos 885 linhas — e tinha, 2.004.

    A regra que fecha o buraco é de FORMA, e vale só para as colunas de
    endereço: prosa de evidência continua livre.
    """
    faltam: list[str] = []
    for ident, linha in _linhas_do_mapa().items():
        for coluna in ("cabo_codigo_ref", "radio_codigo_ref"):
            texto = linha.get(coluna) or ""
            for achado in ENDERECO_DE_COOP.finditer(texto):
                if not NOME_DEPOIS.match(texto[achado.end() : achado.end() + 80]):
                    faltam.append(f"{ident} · {coluna}: {achado.group(0)}")
    assert not faltam, (
        "citação de daemon/subsystems/coop.py sem o símbolo entre crases logo "
        "depois — é a forma que apodrece calada, porque o portão de citações não "
        "tem o que conferir:\n  " + "\n  ".join(faltam)
    )


@pytest.mark.parametrize(
    ("faixa", "simbolo"),
    [
        ("1677-1735", "numeros_de_jogador"),
        ("1737-1785", "_numero_exibido"),
        ("823-833", "_next_player_index"),
        ("1324-1398", "_start_player_motion_reader"),
        ("1045-1091", "_make_player_replica_sinks"),
        ("1015-1043", "_make_player_rumble_sink"),
        ("940-990", "_spawn_player"),
        ("1093-1191", "_promote_player"),
        ("339-345", "should_be_active"),
        ("628-775", "sync"),
    ],
)
def test_a_faixa_reapontada_ainda_e_a_funcao_prometida(
    faixa: str, simbolo: str
) -> None:
    """Cada endereço que a área reapontou em 03/09/2026 abre na função certa.

    O portão de citações confere isto lendo o CSV; aqui a mesma pergunta é feita
    do lado do CÓDIGO, para que mover uma função em `coop.py` acuse na hora em
    vez de esperar a próxima varredura do mapa.
    """
    inicio, fim = (int(n) for n in faixa.split("-"))
    arvore = ast.parse(COOP.read_text(encoding="utf-8"))
    casou = [
        no
        for no in ast.walk(arvore)
        if isinstance(no, ast.FunctionDef | ast.AsyncFunctionDef)
        and no.name == simbolo
        and no.lineno == inicio
        and no.end_lineno == fim
    ]
    assert casou, (
        f"`{simbolo}` não é mais coop.py:{faixa} — reaponte o "
        "`docs/data/mapa-controles.csv` antes que o endereço apodreça calado"
    )
