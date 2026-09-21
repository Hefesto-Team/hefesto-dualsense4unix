"""O-SOM-DO-SISTEMA-E-O-DA-TELA-01 — o servidor de som avisa e alguém escuta.

**Pedido dela, 21/09/2026**, com o painel de som do COSMIC aberto ao lado da
janela do Hefesto:

    *"outra coisa que precisamos ter é sincronia com os canais de saida de som
    e entrada de som do sistema operacional. isso é importante."*
    <!-- noqa-acento: citação literal dela -->

**O QUE ESTAVA MEDIDO:** o produto só ESCREVIA. Zero `pactl subscribe` e zero
`pw-mon` em `src/` — havia escrita (`set-default-sink`/`set-default-source`) e
leitura sob demanda (`get-default-sink`), e nada que ficasse sabendo quando ela
trocava a saída no painel do sistema.

**NENHUM TESTE DESTE ARQUIVO TOCA O SERVIDOR DE SOM DELA.** As funções que
decidem são puras (`interessa`, `descricoes_da_lista`,
`linha_do_som_do_sistema`) e o laço é medido com um `pactl` de mentira.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

#: A SAÍDA REAL DE `pactl list sinks` NA MÁQUINA DELA, em 21/09/2026, cortada
#: nos dois campos que importam. É o oráculo de `descricoes_da_lista`: uma
#: régua escrita contra um formato inventado mede a invenção.
LISTA_MEDIDA = """
Sink #551
\tName: alsa_output.usb-Sony_..._Controller-00.HiFi__Speaker__sink
\tDescription: DualSense wireless controller (PS5) Controller speaker
Sink #593
\tName: hefesto_som_e64203
\tDescription: Alto-falante do Controle 1
Sink #56923
\tName: alsa_output.pci-0000_0a_00.1.hdmi-stereo
\tDescription: HDA NVidia Estéreo digital (HDMI)
"""


# ---------------------------------------------------------------------------
# 1 — O FILTRO, e o `sink-input` que o derrubaria
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("linha", [
    "Event 'change' on server #0",
    "Event 'new' on sink #66580",
    "Event 'remove' on source #12",
])
def test_o_que_importa_acorda_o_lacos(linha: str) -> None:
    assert ods.interessa(linha) is True


@pytest.mark.parametrize("linha", [
    "Event 'change' on sink-input #4211",
    "Event 'new' on client #66347",
    "Event 'change' on source-output #9",
    "",
    "lixo",
])
def test_o_que_nao_importa_nao_acorda(linha: str) -> None:
    """`sink-input` CONTÉM `sink`, e é o stream de qualquer app tocando som.

    MORDE: troque o `partes[3] in EVENTOS_QUE_IMPORTAM` por um `in linha` e
    esta régua reprova — o laço passaria a reler o padrão a cada frame de
    áudio de qualquer programa aberto.
    """
    assert ods.interessa(linha) is False


# ---------------------------------------------------------------------------
# 2 — OS NOMES SÃO OS DO PAINEL DELA
# ---------------------------------------------------------------------------
def test_a_descricao_sai_do_formato_longo_medido() -> None:
    mapa = ods.descricoes_da_lista(LISTA_MEDIDA)
    assert mapa["hefesto_som_e64203"] == "Alto-falante do Controle 1"
    assert mapa["alsa_output.pci-0000_0a_00.1.hdmi-stereo"] == (
        "HDA NVidia Estéreo digital (HDMI)")


def test_um_no_sem_descricao_nao_entra() -> None:
    """Melhor o nome cru na tela que um par errado."""
    mapa = ods.descricoes_da_lista("\tName: so_o_nome\nSink #2\n\tName: outro\n"
                                   "\tDescription: Outro\n")
    assert "so_o_nome" not in mapa
    assert mapa["outro"] == "Outro"


def test_a_leitura_prende_o_idioma() -> None:
    """O `pactl` desta casa responde em português; um leitor que dependa do
    idioma da máquina já respondeu "não há" sobre aparelho de pé duas vezes."""
    ambiente = ods._ambiente()
    assert ambiente["LC_ALL"] == "C"
    assert ambiente["LANG"] == "C"


# ---------------------------------------------------------------------------
# 3 — O LAÇO: só publica o que MUDOU
# ---------------------------------------------------------------------------
class _BusDeMentira:
    def __init__(self) -> None:
        self.publicados: list[tuple[str, Any]] = []

    def publish(self, topico: str, carga: Any) -> None:
        self.publicados.append((topico, carga))


class _DaemonDeMentira:
    def __init__(self) -> None:
        self.bus = _BusDeMentira()
        self._tasks: list[Any] = []


class _ProcDeMentira:
    """Um `pactl subscribe` que entrega as linhas dadas e depois acaba."""

    def __init__(self, linhas: list[str]) -> None:
        self.stdout = self._linhas(linhas)
        self.returncode = 0

    @staticmethod
    async def _linhas(linhas: list[str]) -> Any:
        for x in linhas:
            yield (x + "\n").encode()

    def kill(self) -> None:
        pass

    async def wait(self) -> int:
        return 0


def _correr(daemon: Any, linhas: list[str], padroes: list[ods.SomDoSistema],
            monkeypatch: pytest.MonkeyPatch) -> None:
    """Uma volta do laço, com o `subscribe` e as leituras de mentira."""
    lidas = iter(padroes)

    async def _ler() -> ods.SomDoSistema:
        try:
            return next(lidas)
        except StopIteration:
            return padroes[-1]

    async def _abrir(*_a: Any, **_k: Any) -> Any:
        return _ProcDeMentira(linhas)

    monkeypatch.setattr(ods, "ler_o_padrao", _ler)
    monkeypatch.setattr(asyncio, "create_subprocess_exec", _abrir)
    asyncio.run(ods._uma_volta(daemon))


def test_a_primeira_leitura_vem_antes_do_subscribe(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem ela a tela ficaria sem resposta até a primeira mudança — que pode
    ser nunca.

    MORDE: tire a leitura de abertura de `_uma_volta` e a régua reprova com
    zero publicações.
    """
    daemon = _DaemonDeMentira()
    inicial = ods.SomDoSistema(saida="hdmi", entrada="mic")

    _correr(daemon, [], [inicial], monkeypatch)

    assert daemon.bus.publicados == [
        (EventTopic.SOM_DO_SISTEMA, inicial.como_dicionario())]
    assert daemon.som_do_sistema == inicial


def test_o_evento_que_nao_muda_nada_nao_repinta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Um nó que nasce emite evento e não troca padrão nenhum.

    MORDE: tire o `if agora == anterior: continue` e a régua reprova com uma
    publicação a mais — que na tela é uma repintura por nada, o defeito medido
    em 05/09/2026 (80 repinturas em 80 tiques).
    """
    daemon = _DaemonDeMentira()
    mesmo = ods.SomDoSistema(saida="hdmi", entrada="mic")

    _correr(daemon, ["Event 'new' on sink #1"], [mesmo, mesmo], monkeypatch)

    assert len(daemon.bus.publicados) == 1


def test_a_troca_de_padrao_chega_na_hora(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """O caso dela: trocar a saída no painel do COSMIC."""
    daemon = _DaemonDeMentira()
    antes = ods.SomDoSistema(saida="hdmi", entrada="mic", saida_nome="TV")
    depois = ods.SomDoSistema(saida="fone", entrada="mic", saida_nome="Fone")

    _correr(daemon, ["Event 'change' on server #0"], [antes, depois], monkeypatch)

    assert [c for _t, c in daemon.bus.publicados] == [
        antes.como_dicionario(), depois.como_dicionario()]
    assert daemon.som_do_sistema == depois


def test_o_ouvinte_nao_escreve_no_servidor_de_som() -> None:
    """CONTRATO: ele lê, compara e publica. Quem elege microfone é o dono.

    **A RÉGUA LÊ A ÁRVORE, NÃO O TEXTO — e isso é medição desta casa, não
    preciosismo.** A primeira versão procurava o verbo no TEXTO do arquivo e
    reprovou na hora: o CABEÇALHO do módulo cita os dois verbos para explicar
    o defeito que ele cura. *Um comentário que descreve o padrão proibido vira
    a primeira ocorrência dele* — já aconteceu três vezes nesta casa, e uma
    delas derrubou treze testes com `Unexpected token`.

    Aqui só contam as strings que o INTERPRETADOR carrega: literais fora de
    docstring. Prosa pode dizer o nome do veneno; código, não.

    MORDE: chame um `set-default-source` daqui e a régua reprova.
    """
    import ast

    with open(ods.__file__ or "", encoding="utf-8") as arquivo:
        arvore = ast.parse(arquivo.read())
    # OS NÓS QUE SÃO DOCSTRING, por IDENTIDADE de nó: o primeiro `Expr` de um
    # módulo, classe ou função cujo valor é uma string. Comparar pelo TEXTO
    # tiraria também um literal de código que por acaso repetisse a frase.
    docs: set[int] = set()
    for n in ast.walk(arvore):
        if not isinstance(n, (ast.Module, ast.ClassDef,
                              ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        corpo = getattr(n, "body", None) or []
        if (corpo and isinstance(corpo[0], ast.Expr)
                and isinstance(corpo[0].value, ast.Constant)
                and isinstance(corpo[0].value.value, str)):
            docs.add(id(corpo[0].value))
    literais = [
        n.value for n in ast.walk(arvore)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and id(n) not in docs
    ]
    for proibido in ("set-default-sink", "set-default-source", "set-sink-volume"):
        for texto in literais:
            assert proibido not in texto, (
                f"o ouvinte escreveu {proibido!r} em código — ele só observa")


# ---------------------------------------------------------------------------
# 4 — O `state_full` E A LINHA DO EXAME
# ---------------------------------------------------------------------------
def test_o_payload_sem_ouvinte_e_nao_sei_e_nao_nao_ha() -> None:
    """Dois campos vazios. Afirmar "não há" faria a pessoa parar de procurar."""
    assert ods.som_do_sistema_payload(object()) == {
        "saida": "", "entrada": "", "saida_nome": "", "entrada_nome": ""}


def test_a_linha_do_exame_diz_os_nomes_do_painel_dela() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    linha = a09.linha_do_som_do_sistema({"som_do_sistema": {
        "saida": "alsa_output.pci-0000_0a_00.1.hdmi-stereo",
        "entrada": "hefesto_mic_e64203",
        "saida_nome": "HDA NVidia Estéreo digital (HDMI)",
        "entrada_nome": "Microfone do Controle 1"}})

    assert linha is not None
    selo, texto = linha
    assert selo == a09.SELO_INFORMATIVO
    assert "HDA NVidia" in texto
    assert "Microfone do Controle 1" in texto
    assert "alsa_output" not in texto, (
        "o nome CRU chegou à tela — e ele não é o que o painel dela mostra")


def test_sem_o_bloco_a_linha_nao_aparece() -> None:
    """Uma linha de exame que diz "não sei" sobre som ensina que há algo errado
    com o som.

    MORDE: devolva uma linha com travessão quando o bloco falta e a régua
    reprova.
    """
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    assert a09.linha_do_som_do_sistema(None) is None
    assert a09.linha_do_som_do_sistema({}) is None
    assert a09.linha_do_som_do_sistema({"som_do_sistema": {}}) is None


def test_o_nome_cru_serve_de_reserva() -> None:
    """Sem `Description` a tela mostra o nome cru — longo e feio, mas verdade."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    linha = a09.linha_do_som_do_sistema(
        {"som_do_sistema": {"saida": "alsa_output.x"}})
    assert linha is not None
    assert "alsa_output.x" in linha[1]
