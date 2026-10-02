"""O-SOM-DO-SISTEMA-E-O-DA-TELA-01 — o servidor de som avisa e alguém escuta."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from hefesto_dualsense4unix.core.events import EventTopic
from hefesto_dualsense4unix.daemon.subsystems import ouvinte_do_som as ods

LISTA_MEDIDA = """
Sink #551
\tName: alsa_output.usb-Sony_..._Controller-00.HiFi__Speaker__sink
\tDescription: DualSense wireless controller (PS5) Controller speaker
Sink #593
\tName: hefesto_som_000003
\tDescription: Alto-falante do Controle 1
Sink #56923
\tName: alsa_output.pci-0000_0a_00.1.hdmi-stereo
\tDescription: HDA NVidia Estéreo digital (HDMI)
"""


@pytest.mark.parametrize("linha", [
    "Event 'change' on server #0",
    "Event 'new' on sink #66580",
    "Event 'remove' on source #12",
])
def test_o_que_importa_rele_o_padrao(linha: str) -> None:
    assert ods.tipo_do_evento(linha) in ods._TIPOS_DO_PADRAO


@pytest.mark.parametrize(("linha", "tipo"), [
    ("Event 'change' on sink-input #4211", "sink-inputs"),
    ("Event 'new' on client #66347", None),
    ("Event 'change' on source-output #9", "source-outputs"),
    ("", None),
    ("lixo", None),
])
def test_o_que_nao_importa_nao_rele_o_padrao(linha: str, tipo: str | None) -> None:
    """`sink-input` CONTÉM `sink`, e é o stream de qualquer app tocando som."""
    assert ods.tipo_do_evento(linha) == tipo
    assert ods.tipo_do_evento(linha) not in ods._TIPOS_DO_PADRAO


def _retrato_com(saidas: str, padrao_da_saida: str = "") -> Any:
    """O retrato do som, vivo, alimentado com a saída dada — sem servidor nenhum."""
    from hefesto_dualsense4unix.integrations import retrato_do_som as rs

    respostas = {
        ("pactl", "list", "sinks"): saidas,
        ("pactl", "info"): f"Default Sink: {padrao_da_saida}\nDefault Source: \n",
    }
    retrato = rs.RetratoDoSom(ler=lambda argv: respostas.get(tuple(argv), ""))
    assert retrato.carregar()
    retrato.assumir()
    return retrato


def test_a_descricao_sai_do_formato_longo_medido(monkeypatch: pytest.MonkeyPatch) -> None:
    """O padrão publicado leva o nome do painel dela, pelo caminho do produto."""
    from hefesto_dualsense4unix.integrations import retrato_do_som as rs

    retrato = _retrato_com(LISTA_MEDIDA, padrao_da_saida="hefesto_som_000003")
    monkeypatch.setattr(rs, "RETRATO", retrato)
    som = ods._o_padrao_do_retrato()
    assert som.saida == "hefesto_som_000003"
    assert som.saida_nome == "Alto-falante do Controle 1"
    assert retrato.descricoes()["alsa_output.pci-0000_0a_00.1.hdmi-stereo"] == (
        "HDA NVidia Estéreo digital (HDMI)")


def test_um_no_sem_descricao_nao_entra() -> None:
    """Melhor o nome cru na tela que um par errado."""
    mapa = _retrato_com("\tName: so_o_nome\nSink #2\n\tName: outro\n"
                        "\tDescription: Outro\n").descricoes()
    assert "so_o_nome" not in mapa
    assert mapa["outro"] == "Outro"


def test_a_leitura_prende_o_idioma() -> None:
    """O `pactl` desta casa responde em português; um leitor que dependa do"""
    ambiente = ods._ambiente()
    assert ambiente["LC_ALL"] == "C"
    assert ambiente["LANG"] == "C"


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
    """Sem ela a tela ficaria sem resposta até a primeira mudança — que pode"""
    daemon = _DaemonDeMentira()
    inicial = ods.SomDoSistema(saida="hdmi", entrada="mic")

    _correr(daemon, [], [inicial], monkeypatch)

    assert daemon.bus.publicados == [
        (EventTopic.SOM_DO_SISTEMA, inicial.como_dicionario())]
    assert daemon.som_do_sistema == inicial


def test_o_evento_que_nao_muda_nada_nao_repinta(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Um nó que nasce emite evento e não troca padrão nenhum."""
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
    """CONTRATO: ele lê, compara e publica. Quem elege microfone é o dono."""
    import ast

    with open(ods.__file__ or "", encoding="utf-8") as arquivo:
        arvore = ast.parse(arquivo.read())
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


# 4 — O `state_full` E A LINHA DO EXAME
def test_o_payload_sem_ouvinte_e_nao_sei_e_nao_nao_ha() -> None:
    """Dois campos vazios. Afirmar "não há" faria a pessoa parar de procurar."""
    assert ods.som_do_sistema_payload(object()) == {
        "saida": "", "entrada": "", "saida_nome": "", "entrada_nome": ""}


def test_a_linha_do_exame_diz_os_nomes_do_painel_dela() -> None:
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    linha = a09.linha_do_som_do_sistema({"som_do_sistema": {
        "saida": "alsa_output.pci-0000_0a_00.1.hdmi-stereo",
        "entrada": "hefesto_mic_000003",
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
    """Uma linha de exame que diz "não sei" sobre som ensina que há algo errado"""
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


def test_sem_pactl_o_ouvinte_espera_calado_e_volta_quando_ele_aparece(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem o `pactl` não há o que ouvir, e isso não é queda (30/09/2026)."""
    presente = iter([None, None, None, "/usr/bin/pactl"])
    tentativas: list[tuple[Any, ...]] = []
    linhas: list[str] = []

    def _which(nome: str) -> str | None:
        assert nome == "pactl"
        return next(presente, "/usr/bin/pactl")

    async def _uma_volta(_daemon: Any) -> None:
        tentativas.append(("subscribe",))
        raise asyncio.CancelledError

    async def _dormir(_s: float) -> None:
        return None

    class _Log:
        def info(self, evento: str, **_k: Any) -> None:
            linhas.append(evento)

        def warning(self, evento: str, **_k: Any) -> None:
            linhas.append(evento)

    monkeypatch.setattr(ods.shutil, "which", _which)
    monkeypatch.setattr(ods, "_uma_volta", _uma_volta)
    monkeypatch.setattr(ods.asyncio, "sleep", _dormir)
    monkeypatch.setattr(ods, "logger", _Log())

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(ods.ouvinte_do_som_loop(_DaemonDeMentira()))

    assert linhas == ["ouvinte_do_som_sem_pactl", "ouvinte_do_som_achou_o_pactl"]
    assert tentativas == [("subscribe",)], "só tenta ouvir quando o pactl existe"
