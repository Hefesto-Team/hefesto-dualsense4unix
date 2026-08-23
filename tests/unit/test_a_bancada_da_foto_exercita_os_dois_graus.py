"""A bancada de mentira da foto exercita os DOIS casos da coluna "O que é".

POR QUE ESTE PORTÃO EXISTE. A seção "A mesa" é fotografada com um sysfs
inventado, e não com o barramento dela — a foto entra em `docs/usage/assets/`
sem revisão humana e nenhum portão desta casa varre imagem. A bancada é, então,
a única coisa que decide o que a documentação mostra daquela seção.

Uma bancada em que todo aparelho se declara faria a foto esconder metade da
tela: sumiriam o seletor, o `▲` e a única linha que precisa dela. Uma bancada
em que nenhum se declara mostraria a tela ANTIGA — sete botões em toda linha —
como se fosse a de hoje, e é assim que uma foto mente sem ninguém mexer no
produto.

É a lição de 22/08/2026, que esta casa pagou quatro vezes num dia: **o
instrumento mente mais que o produto.** A quarta foi neste mesmo arquivo — o
retrato montava a aba Gatilhos diferente do produto, e ela decidiu a fila de
interface olhando aquele vazio.

O QUE ELE COBRA:

1. **os dois graus na mesma foto** — pelo menos um rádio vizinho que o
   barramento classificou e pelo menos um que ele não classificou;
2. **as duas leituras casam** — todo rádio da tabela é achável no censo pelo
   `no`. Se as duas bancadas divergirem, a coluna cai em "não sei" por defeito
   do instrumento e a foto acusa o produto;
3. **o nome do adaptador aparece, e o prefixo NÃO** — a foto tem de mostrar o
   que a costura faz: alias `"Nintendo Extra"`, tela `"Extra"`;
4. **nada disso é dado dela** — endereços forjados, e a leitura viva do BlueZ
   não é chamada.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "gui-captura" / "retratar_abas.py"


def _retrato() -> Any:
    """O script importado como módulo — ele tem hífen na pasta, não no nome.

    **A leitura é do FONTE, e não pelo `exec_module`, e o motivo é medido.**
    O carregador de arquivo do Python guarda bytecode em `__pycache__` e o
    invalida por `(mtime, tamanho)`. Uma mordida que troque `("ff", "ff", "ff")`
    por `("03", "01", "01")` — o mesmo número de bytes — dentro do mesmo segundo
    reaproveita o bytecode ANTIGO, e o teste passa a medir a versão anterior do
    arquivo. Aconteceu em 22/08/2026, ao morder este próprio portão: a mordida
    reprovou o teste errado, e a conclusão convincente teria sido "o portão não
    morde".

    É a família do dia: o instrumento mente mais que o produto. Compilar o
    texto lido agora não tem cache nenhum por onde errar.
    """
    fonte = SCRIPT.read_text(encoding="utf-8")
    spec = importlib.util.spec_from_file_location("_retrato_da_bancada", SCRIPT)
    assert spec is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules["_retrato_da_bancada"] = modulo
    exec(compile(fonte, str(SCRIPT), "exec"), modulo.__dict__)
    return modulo


def _graus() -> dict[str, list[str]]:
    """`{grau: [vid:pid]}` dos rádios vizinhos da bancada, pelo censo dela."""
    retrato = _retrato()
    mesa = retrato._mesa_de_mentira()
    censo = retrato._censo_de_mentira()
    achados: dict[str, list[str]] = {}
    for radio in mesa.radios:
        aparelho = censo.aparelho(radio.no)
        grau = "ausente" if aparelho is None else aparelho.grau
        achados.setdefault(grau, []).append(f"{radio.vid}:{radio.pid}")
    return achados


def test_a_bancada_tem_aparelho_que_o_barramento_classifica() -> None:
    """Sem isto a foto mostra a tela velha: sete botões em toda linha.

    Mordida: trocar a classe de todas as interfaces de `_MESA_INTERFACES` por
    `("ff", "ff", "ff")`.
    """
    from hefesto_dualsense4unix.integrations.censo_do_barramento import GRAU_LIDO

    graus = _graus()
    assert graus.get(GRAU_LIDO), (
        "nenhum rádio vizinho da bancada é classificado pelo barramento. A "
        "foto mostraria a coluna 'O que é' inteira em 'não sei' — a tela de "
        f"antes desta leva. Graus: {graus}"
    )


def test_a_bancada_tem_aparelho_que_ninguem_classifica() -> None:
    """Sem isto somem da foto o seletor, o `▲` e a linha que precisa dela.

    Na bancada dela é o Wi-Fi Realtek, que sai como classe `ff` — de quatro
    linhas de rádio vizinho, é a única que pede resposta.

    Mordida: dar uma classe conhecida à interface do `1-2.2`.
    """
    from hefesto_dualsense4unix.integrations.censo_do_barramento import (
        GRAU_DESCONHECIDO,
    )

    graus = _graus()
    assert graus.get(GRAU_DESCONHECIDO), (
        "todo aparelho da bancada se declara. A foto esconderia o seletor e o "
        f"aviso — metade do que esta coluna sabe desenhar. Graus: {graus}"
    )


def test_as_duas_bancadas_falam_do_mesmo_aparelho() -> None:
    """Todo rádio da tabela tem de ser achável no censo, pelo `no`.

    Duas bancadas separadas divergiriam calado: a tabela mostraria o rádio e a
    coluna diria "não sei" — a foto acusando o produto de um defeito do
    instrumento.

    Mordida: dar ao `_censo_de_mentira` uma raiz USB diferente da do
    `_mesa_de_mentira`.
    """
    graus = _graus()
    assert not graus.get("ausente"), (
        "estes rádios estão na tabela e não existem no censo da mesma "
        f"bancada: {graus.get('ausente')}"
    )


def test_a_foto_mostra_o_nome_do_adaptador_e_esconde_o_prefixo() -> None:
    """O que a costura faz tem de aparecer na documentação.

    Mordida: tirar o `hospeda_nintendo=True` do segundo dongle — o alias e o
    nome passam a ser a mesma coisa, e a foto deixa de mostrar que existe uma
    costura.
    """
    dongles = _retrato()._dongles_de_mentira()

    assert dongles, "a bancada perdeu os adaptadores nomeados"
    escondendo = [d for d in dongles if d.nome != d.alias]
    assert escondendo, (
        "nenhum adaptador da bancada carrega o prefixo Nintendo por dentro. A "
        "foto não mostra a única coisa que o produto faz sozinho aqui: o alias "
        "guardado é 'Nintendo Extra' e a tela diz 'Extra'."
    )
    assert all(d.nome for d in dongles), (
        "adaptador de bancada sem nome nenhum: a coluna sairia vazia na foto"
    )


def test_a_bancada_nao_usa_endereco_de_verdade() -> None:
    """A premissa de tudo acima: o endereço é forjado.

    Mordida: pôr um BD Address real em `_MESA_DONGLES`.
    """
    for dongle in _retrato()._dongles_de_mentira():
        assert dongle.endereco.upper().startswith(("AA:", "00:", "02:")), (
            f"o adaptador de bancada usa {dongle.endereco!r}, que não parece "
            "forjado. O retrato publica em docs/usage/assets/."
        )
