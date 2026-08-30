"""A rede da linha ``identidade.cor_do_aparelho@dualsense`` do mapa de canais.

POR QUE ESTE ARQUIVO EXISTE
---------------------------

Até 22/08/2026 a linha 111 de ``docs/data/mapa-controles.csv`` dizia
``cabo_aciona = não`` e ``cabo_codigo_ref = "zero linhas no produto"``. Isso
CADUCOU na leva da aba Configurações: a leitura saiu de ``scripts/ensaios/`` e
entrou em ``src/hefesto_dualsense4unix/integrations/cor_do_plastico.py``
(``ler_pelo_cabo``), e é ela que pinta a borda de cada card
(``app/actions/config/secao_controles.py::_perguntar_as_cores``).

Virar a célula para ``sim`` sem rede seria exatamente o defeito-mãe que o
``scripts/check_paridade_transporte.py`` existe para pegar (regra 1,
``sem-mordida``): afirmação forte sem teste que morda. Este arquivo é a rede — e
o caminho do CABO não tinha teste nenhum antes dele
(``grep -rn 'ler_pelo_cabo\\|no_do_controle' tests/`` voltava vazio em 22/08).

O QUE ELE MORDE, E POR QUÊ CADA UM
-----------------------------------

* **os três filtros de ``no_do_controle``**. Não são zelo: por rádio o
  ``SET_FEATURE 0x80`` foi MEDIDO devolvendo EIO (E7, 15/08/2026), o comando é da
  família de fábrica da Sony e mandá-lo a outro fabricante é escrever às cegas, e
  o nosso vpad FORJA VID/PID/bus de DualSense no cabo — sem o filtro o produto
  pediria o serial de fábrica à própria saída;
* **o pedido que sai é o único autorizado**. A família ``0x80`` é a mesma em que
  ``[1,1]`` RESETA o controle e ``[12,1]`` grava calibração na NVS. Um teste que
  só olhasse a cor de volta deixaria essa trava sem guarda;
* **a leitura nunca levanta**. ``None`` vira "Não sei" na tela, que é resposta
  válida em toda a aba; uma exceção derrubaria a janela;
* **o mapa e o produto não podem divergir de novo**. Se o produto perder
  ``ler_pelo_cabo``, a célula tem de voltar para ``não`` no mesmo commit.

NADA AQUI ENCOSTA EM APARELHO. O transporte entra por ``perguntar``, que é o
ponto de injeção que o módulo declara justamente para uma suíte distraída não
mandar comando de fábrica para os quatro controles dela.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import cor_do_plastico
from hefesto_dualsense4unix.integrations.cor_do_plastico import (
    FEATURE_RESPOSTA,
    TAMANHO_DO_FEATURE,
    conferir_pedido,
    ler_pelo_cabo,
    montar_pedido,
    no_do_controle,
)

RAIZ = Path(__file__).resolve().parents[2]
MAPA = RAIZ / "docs" / "data" / "mapa-controles.csv"
ID_DA_LINHA = "identidade.cor_do_aparelho@dualsense"

#: MACs FORJADOS na faixa que o portão de anonimato reconhece como sintética
#: (`aa:bb:cc`), e o prefixo `02:fe` que é o do nosso vpad.
_UNIQ_NO_CABO = "aa:bb:cc:00:00:d5"
_UNIQ_DE_OUTRO = "aa:bb:cc:00:00:e9"
_UNIQ_DO_VPAD = "02:fe:00:00:00:01"

#: Serial FORJADO: 17 caracteres com a cor `05` (Starlight Blue) nos caracteres
#: 5 e 6, e uma LETRA na posição 2 de propósito — é o que o tira da forma do
#: serial de fábrica de verdade e o faz passar pelo `check_anonymity.sh`.
_SERIAL_FORJADO = "ZZ9Y05Q0000000000"

_DUALSENSE_NO_CABO = {
    "HID_ID": "0003:0000054C:00000CE6",
    "HID_UNIQ": _UNIQ_NO_CABO,
    "HID_PHYS": "usb-0000:00:14.0-3/input0",
}
_DUALSENSE_NO_RADIO = {**_DUALSENSE_NO_CABO, "HID_ID": "0005:0000054C:00000CE6"}
_OUTRO_FABRICANTE = {
    **_DUALSENSE_NO_CABO,
    "HID_ID": "0003:0000057E:00002009",
    "HID_UNIQ": _UNIQ_DE_OUTRO,
}
_NOSSO_VPAD = {
    "HID_ID": "0003:0000054C:00000CE6",
    "HID_UNIQ": _UNIQ_DO_VPAD,
    "HID_PHYS": "hefesto-vpad",
}


def _bancada(nos: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Um ``/sys/class/hidraw`` de mentira, sem encostar no de verdade."""

    def listar(raiz: str) -> list[str]:
        return sorted(nos)

    def ler(caminho: str) -> str:
        no = Path(caminho).parts[-3]
        return "\n".join(f"{chave}={valor}" for chave, valor in nos.get(no, {}).items())

    return {"listar": listar, "ler": ler}


def _resposta_boa(serial: str = _SERIAL_FORJADO) -> bytes:
    """O ``0x81`` como o firmware o devolveu no E7: eco certo e 17 caracteres."""
    buffer = bytearray(TAMANHO_DO_FEATURE)
    buffer[0] = FEATURE_RESPOSTA
    buffer[1] = 1
    buffer[2] = 19
    buffer[3] = 2
    buffer[4 : 4 + len(serial)] = serial.encode("ascii")
    return bytes(buffer)


@pytest.fixture(scope="module")
def linha_do_mapa() -> dict[str, str]:
    with MAPA.open(newline="", encoding="utf-8") as arquivo:
        for linha in csv.DictReader(arquivo):
            if linha["id"] == ID_DA_LINHA:
                return linha
    pytest.fail(f"o mapa perdeu a linha {ID_DA_LINHA}")


class TestOsTresFiltrosDoNo:
    def test_acha_o_dualsense_no_cabo_pelo_endereco(self) -> None:
        bancada = _bancada({"hidraw3": _OUTRO_FABRICANTE, "hidraw4": _DUALSENSE_NO_CABO})
        assert no_do_controle(_UNIQ_NO_CABO, **bancada) == "/dev/hidraw4"

    def test_o_mesmo_controle_no_radio_nao_vira_alvo(self) -> None:
        """Medido no E7: por rádio o SET_FEATURE 0x80 volta EIO. Não se tenta."""
        bancada = _bancada({"hidraw4": _DUALSENSE_NO_RADIO})
        assert no_do_controle(_UNIQ_NO_CABO, **bancada) is None

    def test_aparelho_de_outro_fabricante_nao_vira_alvo(self) -> None:
        bancada = _bancada({"hidraw4": _OUTRO_FABRICANTE})
        assert no_do_controle(_UNIQ_DE_OUTRO, **bancada) is None

    def test_o_nosso_vpad_nao_vira_alvo(self) -> None:
        """Ele forja VID/PID/bus de DualSense no cabo — sem o filtro, o produto
        pediria o serial de fábrica à própria saída."""
        bancada = _bancada({"hidraw4": _NOSSO_VPAD})
        assert no_do_controle(_UNIQ_DO_VPAD, **bancada) is None

    def test_sem_endereco_nao_ha_alvo(self) -> None:
        bancada = _bancada({"hidraw4": _DUALSENSE_NO_CABO})
        assert no_do_controle("", **bancada) is None


class TestOProdutoLeACorPeloCabo:
    def test_a_cor_volta_do_serial_que_o_aparelho_respondeu(self) -> None:
        bancada = _bancada({"hidraw4": _DUALSENSE_NO_CABO})
        vistos: list[tuple[str, bytes]] = []

        def perguntar(caminho: str, pedido: bytes) -> bytes:
            vistos.append((caminho, pedido))
            return _resposta_boa()

        cor = ler_pelo_cabo(_UNIQ_NO_CABO, perguntar=perguntar, **bancada)
        assert cor is not None
        assert (cor.codigo, cor.nome) == ("05", "Starlight Blue")
        assert cor.tom, "a cor lida tem de trazer o tom que pinta a borda do card"
        assert [caminho for caminho, _ in vistos] == ["/dev/hidraw4"]

    def test_o_pedido_que_sai_e_o_unico_que_a_trava_autoriza(self) -> None:
        """A família 0x80 é a mesma em que `[1,1]` RESETA e `[12,1]` grava NVS."""
        bancada = _bancada({"hidraw4": _DUALSENSE_NO_CABO})
        capturado: list[bytes] = []

        def perguntar(caminho: str, pedido: bytes) -> bytes:
            capturado.append(pedido)
            return _resposta_boa()

        ler_pelo_cabo(_UNIQ_NO_CABO, perguntar=perguntar, **bancada)
        assert capturado == [montar_pedido()]
        conferir_pedido(capturado[0])

    def test_eco_errado_nao_vira_cor_inventada(self) -> None:
        bancada = _bancada({"hidraw4": _DUALSENSE_NO_CABO})
        torto = bytearray(_resposta_boa())
        torto[2] = 20  # `num` que ninguém pediu
        assert ler_pelo_cabo(
            _UNIQ_NO_CABO, perguntar=lambda _c, _p: bytes(torto), **bancada
        ) is None

    def test_sem_aparelho_a_resposta_e_nao_sei_e_nao_excecao(self) -> None:
        assert ler_pelo_cabo(_UNIQ_NO_CABO, **_bancada({})) is None

    def test_transporte_que_explode_nao_derruba_a_janela(self) -> None:
        bancada = _bancada({"hidraw4": _DUALSENSE_NO_CABO})

        def explode(_caminho: str, _pedido: bytes) -> bytes:
            raise OSError(5, "EIO")

        assert ler_pelo_cabo(_UNIQ_NO_CABO, perguntar=explode, **bancada) is None


def _abre_o_no_pela_porta_do_broker() -> bool:
    """`_perguntar_ao_hidraw` pede o fd ao broker, ou abre o nó na unha?

    Lido por AST do fonte, nunca por chamada: chamar a função de verdade
    encostaria no `/dev/hidraw` dela. `os.open` direto morre com EACCES enquanto
    o BROKER-01 estiver instalado — e ele é DEFAULT em todo formato.
    """
    import ast

    #: RÉGUA FALSA, CORRIGIDA EM 29/08/2026 — e ela mentiu no primeiro uso.
    #: A primeira versão desta função olhava só o ALVO das chamadas
    #: (`ast.unparse(filho.func)`) procurando "abrir_hidraw". Quando a cura
    #: entrou, ela entrou pela forma que esta casa usa em todo lugar — o
    #: transporte injetável: `porta = abrir if abrir is not None else
    #: abrir_hidraw`, e depois `porta(caminho, escrita=True)`. O alvo da chamada
    #: passou a ser `porta`, e a régua devolveu "não curado" com a cura no
    #: disco, deixando a célula do mapa em `não` com o produto lendo.
    #: Instrumento que confunde o NOME DA VARIÁVEL com o ATO — a mesma família
    #: das réguas que esta casa já pegou. Agora ela varre TODO identificador do
    #: corpo, não só o alvo da chamada.
    fonte = Path(cor_do_plastico.__file__).read_text(encoding="utf-8")
    for no in ast.walk(ast.parse(fonte)):
        if not (isinstance(no, ast.FunctionDef) and no.name == "_perguntar_ao_hidraw"):
            continue
        nomes: set[str] = set()
        for filho in ast.walk(no):
            if isinstance(filho, ast.Name):
                nomes.add(filho.id)
            elif isinstance(filho, ast.Attribute):
                nomes.add(ast.unparse(filho))
            elif isinstance(filho, ast.alias):
                nomes.add(filho.name)
        pela_porta = any("abrir_hidraw" in nome for nome in nomes)
        na_unha = "os.open" in nomes
        assert pela_porta != na_unha, (
            "`_perguntar_ao_hidraw` tem de usar UMA das duas portas, e esta "
            f"régua vê {sorted(n for n in nomes if 'open' in n or 'abrir' in n)}. "
            "As duas juntas (ou nenhuma) deixam a régua sem sinal, que é como "
            "ela mentiu em 29/08/2026."
        )
        return pela_porta
    raise AssertionError("`_perguntar_ao_hidraw` sumiu do módulo da cor")


class TestOMapaEOProdutoNaoDivergem:
    """A célula do cabo tem de seguir o CÓDIGO, e nos dois sentidos.

    SUBSTITUÍDO em 29/08/2026. Esta classe exigia `cabo_aciona == "sim"` desde
    22/08, quando a leitura entrou no produto. A afirmação era verdadeira sobre
    o ENSAIO e falsa sobre o PRODUTO: `_perguntar_ao_hidraw` abre o nó com
    `os.open` DIRETO, e o BROKER-01 — que é DEFAULT no `install.sh` — deixa os
    nós dos DualSense `0600 root:root` para escondê-los do jogo. Medido em
    29/08/2026 na máquina dela, com o broker no ar: `PermissionError 13 EACCES`
    nos dois controles, e `ler_pelo_cabo` devolvendo `None` — que é "Não sei" na
    tela.

    Uma régua que só travasse o `não` novo repetiria o defeito ao contrário: no
    dia em que alguém trocar o `os.open` pela porta do broker
    (`A-COR-PELA-PORTA-DO-BROKER-01`), a cura passaria com a célula mentindo
    `não`. Por isso a asserção é BICONDICIONAL — ela lê o código e exige que a
    célula diga a mesma coisa, em qualquer das duas direções.
    """

    def test_a_celula_do_cabo_segue_a_porta_que_o_produto_usa(
        self, linha_do_mapa: dict[str, str]
    ) -> None:
        pela_porta_certa = _abre_o_no_pela_porta_do_broker()
        esperado = "sim" if pela_porta_certa else "não"
        assert linha_do_mapa["cabo_aciona"] == esperado, (
            f"`_perguntar_ao_hidraw` "
            f"{'pede o fd ao broker' if pela_porta_certa else 'abre o nó com os.open direto'}"
            f", logo `cabo_aciona` tem de ser {esperado!r} — está "
            f"{linha_do_mapa['cabo_aciona']!r}. Com o BROKER-01 no ar (DEFAULT), "
            "`os.open` no nó de um DualSense devolve EACCES e a cor vira 'Não sei'."
        )
        assert linha_do_mapa["cabo_de_onde_sei"] == "medido"

    def test_a_divida_do_cabo_tem_causa_declarada(
        self, linha_do_mapa: dict[str, str]
    ) -> None:
        """`aciona=não` + `medido` sem causa é a regra 16 do portão de paridade."""
        if _abre_o_no_pela_porta_do_broker():
            pytest.skip("a cura entrou: não há dívida a declarar no cabo")
        assert linha_do_mapa["cabo_por_que_nao_aciona"] == "divida", (
            "a causa é NOSSA — o nosso broker esconde o nó e o nosso leitor não "
            "usa a porta dele. Culpar o aparelho aqui seria a mentira que a "
            "correção de 29/08/2026 desfez do lado do rádio"
        )

    def test_a_referencia_de_codigo_do_cabo_aponta_para_o_produto(
        self, linha_do_mapa: dict[str, str]
    ) -> None:
        """A caducidade de 22/08 foi exatamente esta célula dizer `zero linhas`."""
        referencia = linha_do_mapa["cabo_codigo_ref"]
        assert "integrations/cor_do_plastico.py" in referencia
        assert "config/secao_controles.py" in referencia
        assert "zero linhas no produto" not in referencia

    def test_o_radio_nao_acusa_mais_o_aparelho(
        self, linha_do_mapa: dict[str, str]
    ) -> None:
        """O `o-aparelho-recusa` de 23/08 foi REFUTADO em 27/08: era o nosso CRC.

        O produto continua sem ler por rádio — três portões nossos recusam antes
        de o byte sair —, mas a causa é dívida, não recusa do firmware. Esta
        asserção existe para a lápide não voltar: enquanto a `ONDA-CONEXOES-11`
        não fechar, alguém relendo a captura de 23/08 pode reescrevê-la.
        """
        assert linha_do_mapa["radio_aciona"] == "não"
        assert linha_do_mapa["radio_por_que_nao_aciona"] == "divida", (
            "a semente do CRC no sentido de ESCRITA é `0x53`, não `0xA3` — "
            "medido em 27/08/2026, com o aparelho devolvendo o serial por rádio. "
            "`o-aparelho-recusa` aqui é acusar o controle dela pelo nosso bug"
        )
        assert linha_do_mapa["assimetria_declarada"].strip(), (
            "a assimetria entre o que o ENSAIO lê e o que o PRODUTO lê tem de "
            "ficar declarada — é a forma exata da regressão que o mapa pega"
        )
