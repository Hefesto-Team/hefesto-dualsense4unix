"""O daemon do Flatpak alcança o BlueZ e o diário do root — O-FLATPAK-ALCANCA-O-BLUEZ-01."""

from __future__ import annotations

import ast
import contextlib
import re
import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import diario_do_radio, faixa_do_wifi
from hefesto_dualsense4unix.integrations.agente_de_pareamento import CAMINHO_DO_AGENTE
from tests.unit import bluez_de_mentira as bm
from tests.unit.test_o_flatpak_alcanca_o_broker import (
    BARRAMENTO_DE_SISTEMA,
    MANIFESTO,
    PACOTE,
    PAGINA,
)

DISPOSITIVO = bm.no_de(bm.CONTROLE)

_POLITICAS = {"--system-talk-name=": "--talk=", "--system-own-name=": "--own="}


def _finish_args() -> list[str]:
    return list(yaml.safe_load(MANIFESTO.read_text(encoding="utf-8"))["finish-args"])


def nomes_de_sistema() -> list[str]:
    """Os argumentos de proxy que o manifesto pede: ``["--talk=org.bluez", …]``."""
    return [
        proxy + arg.removeprefix(linha)
        for arg in _finish_args()
        for linha, proxy in _POLITICAS.items()
        if arg.startswith(linha)
    ]


def test_o_barramento_de_sistema_e_so_do_dono_do_bluez() -> None:
    """Controle: quem abre o barramento de sistema é o ``bluez_dbus``, e só ele."""
    assert BARRAMENTO_DE_SISTEMA, "o varredor não achou o `BusType.SYSTEM`: a régua ficou cega"
    fora = [
        onde for onde in BARRAMENTO_DE_SISTEMA if not onde.startswith("integrations/bluez_dbus.py:")
    ]
    assert not fora, (
        f"o barramento de sistema se abre fora do `bluez_dbus` ({fora}): diga no "
        "manifesto com que nome esse código fala, e aqui"
    )


def test_o_manifesto_abre_o_barramento_de_sistema_so_para_o_bluez() -> None:
    args = _finish_args()
    assert "--socket=system-bus" not in args, (
        "o `--socket=system-bus` dá ao sandbox o barramento de sistema inteiro, sem "
        "proxy; o código só fala com o `org.bluez`"
    )
    esperados = [f"--talk={bd.SERVICO}", f"--talk={faixa_do_wifi.SERVICO}"]
    assert nomes_de_sistema() == esperados, (
        f"o manifesto pede {nomes_de_sistema()} no barramento de sistema, e o daemon "
        f"fala com o {bd.SERVICO} e com o {faixa_do_wifi.SERVICO}, e só com eles: sem a "
        "primeira, o Flatpak não pareia, não reconecta e não move de adaptador pelo "
        "Hefesto; sem a segunda, a faixa do Wi-Fi não se lê"
    )


def test_o_diario_do_root_se_monta_so_de_leitura() -> None:
    """A PASTA, e ``:ro``: o diário gira por renomeação e pode nascer depois."""
    pasta = str(diario_do_radio.DIARIO_DO_ROOT.parent)
    alcancam = (pasta, str(diario_do_radio.DIARIO_DO_ROOT), "host", "host-os", "/var", "/var/lib")
    linhas = [
        arg.removeprefix("--filesystem=")
        for arg in _finish_args()
        if arg.startswith("--filesystem=")
        and arg.removeprefix("--filesystem=").partition(":")[0].rstrip("/") in alcancam
    ]
    assert linhas == [f"{pasta}:ro"], (
        f"o diário dos serviços do sistema monta como {linhas}, e o decidido é a pasta "
        f"`{pasta}:ro`: o daemon só LÊ o diário do root, e escrita ali é dar mais do "
        "que o código usa"
    )


class _Usos(ast.NodeVisitor):
    """Cada uso de um nome, com a função MAIS DE DENTRO que o contém."""

    def __init__(self, nome: str) -> None:
        self.nome = nome
        self.pilha = ["<módulo>"]
        self.achadas: list[str] = []

    def _funcao(self, no: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.pilha.append(no.name)
        self.generic_visit(no)
        self.pilha.pop()

    visit_FunctionDef = _funcao  # noqa: N815
    visit_AsyncFunctionDef = _funcao  # noqa: N815

    def visit_Name(self, no: ast.Name) -> None:
        if no.id == self.nome and isinstance(no.ctx, ast.Load):
            self.achadas.append(self.pilha[-1])

    def visit_Attribute(self, no: ast.Attribute) -> None:
        if no.attr == self.nome:
            self.achadas.append(self.pilha[-1])
        self.generic_visit(no)


def _referencias(nome: str) -> list[tuple[str, str]]:
    """``[(arquivo, função)]`` de cada uso de ``nome`` no pacote (fora do broker)."""
    achadas: list[tuple[str, str]] = []
    for arquivo in sorted(PACOTE.rglob("*.py")):
        relativo = arquivo.relative_to(PACOTE)
        if relativo.parts[0] == "broker":
            continue
        usos = _Usos(nome)
        usos.visit(ast.parse(arquivo.read_text(encoding="utf-8")))
        achadas.extend((str(relativo), funcao) for funcao in usos.achadas)
    return achadas


def _textos_com(trecho: str) -> list[str]:
    """``["arquivo:linha"]`` de cada texto do pacote com ``trecho`` (fora das"""
    achados: list[str] = []
    for arquivo in sorted(PACOTE.rglob("*.py")):
        relativo = arquivo.relative_to(PACOTE)
        if relativo.parts[0] == "broker":
            continue
        arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
        docstrings = {
            id(no.value)
            for no in ast.walk(arvore)
            if isinstance(no, ast.Expr) and isinstance(no.value, ast.Constant)
        }
        achados.extend(
            f"{relativo}:{no.lineno}"
            for no in ast.walk(arvore)
            if isinstance(no, ast.Constant)
            and isinstance(no.value, str)
            and id(no) not in docstrings
            and trecho in no.value
        )
    return achados


def test_o_daemon_so_le_o_diario_do_root() -> None:
    """É o que sustenta o ``:ro``: o caminho do root só serve ao ``ler``."""
    pasta = str(diario_do_radio.DIARIO_DO_ROOT.parent)
    escrito = _textos_com(pasta)
    assert len(escrito) == 1 and escrito[0].startswith("integrations/diario_do_radio.py:"), (
        f"a pasta do diário do root está escrita à mão em {escrito}: fora do "
        "`DIARIO_DO_ROOT`, um segundo dono do caminho escapa da régua abaixo, e se "
        "ele escrever ali a montagem `:ro` volta EROFS no Flatpak"
    )
    donos = set(_referencias("caminho_do_diario_do_root"))
    assert donos == {("integrations/diario_do_radio.py", "ler")}, (
        f"o caminho do diário do root é usado em {sorted(donos)}: se alguém passou a "
        "escrever nele, a montagem `:ro` volta EROFS no Flatpak (e o DAC do root "
        "recusa fora dele)"
    )
    assert set(_referencias("DIARIO_DO_ROOT")) == {
        ("integrations/diario_do_radio.py", "caminho_do_diario_do_root")
    }


def _secao(pagina: str, titulo: str) -> str:
    assert titulo in pagina, f"a docs/usage/flatpak.md perdeu a seção {titulo!r}"
    return re.split(r"\n(?:---|## |### )", pagina.split(titulo, 1)[1], maxsplit=1)[0]


def test_a_pagina_diz_as_duas_linhas_e_o_que_segue_sem_alcancar() -> None:
    pagina = PAGINA.read_text(encoding="utf-8")
    args = _finish_args()
    tabela = [linha for linha in pagina.splitlines() if linha.startswith("| `--")]
    for linha in (
        f"--system-talk-name={bd.SERVICO}",
        f"--system-talk-name={faixa_do_wifi.SERVICO}",
        f"--filesystem={diario_do_radio.DIARIO_DO_ROOT.parent}:ro",
    ):
        na_tabela = any(celula.startswith(f"| `{linha}`") for celula in tabela)
        assert na_tabela == (linha in args), (
            f"a tabela de permissões e o manifesto discordam sobre `{linha}`: mude os dois juntos"
        )
    secao = _secao(pagina, "### O BlueZ e o diário dos serviços do sistema")
    assert "continua sem alcançar" in secao, "a página perdeu o que o Flatpak não alcança"
    sem_alcancar = secao.split("continua sem alcançar", 1)[1]
    assert "bt_ponte_privilegiada.sh" in sem_alcancar, (
        "a ponte do root (sudo) não existe no sandbox, e a página deixou de dizer"
    )
    for alcancado in ("BlueZ", "/var/lib/hefesto-dualsense4unix"):
        assert alcancado not in sem_alcancar, (
            f"a página diz que o Flatpak não alcança {alcancado}, e o manifesto o dá"
        )


def test_a_pasta_de_execucao_e_a_mesma_do_host() -> None:
    """Medido: ``xdg-run/<nome>`` monta a pasta do host no mesmo caminho."""
    assert "--filesystem=xdg-run/hefesto-dualsense4unix:create" in _finish_args()
    pagina = PAGINA.read_text(encoding="utf-8")
    linha = next(
        (
            linha
            for linha in pagina.splitlines()
            if linha.startswith("| `$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`")
        ),
        None,
    )
    assert linha is not None, "a tabela «Localização» perdeu a linha da pasta de execução"
    dentro = linha.split("|")[2]
    assert "`$XDG_RUNTIME_DIR/hefesto-dualsense4unix/`" in dentro and "app/" not in dentro, (
        f"a tabela diz que, no Flatpak, a pasta de execução vira {dentro.strip()}; a "
        "linha xdg-run a monta no MESMO caminho do host"
    )


def _ha_proxy() -> bool:
    return shutil.which("xdg-dbus-proxy") is not None and bm.ha_dbus_daemon()


pede_o_proxy = pytest.mark.skipif(
    not _ha_proxy(), reason="sem xdg-dbus-proxy, dbus-daemon ou Gio nesta máquina"
)


@pytest.fixture(autouse=True)
def _trava_e_diario_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))


@contextlib.contextmanager
def _pelo_proxy(bluez: bm.BluezParticular, raiz: Path, filtros: list[str]) -> Iterator[str]:
    """Um ``xdg-dbus-proxy`` com ``--filter`` e os ``filtros``; entrega o endereço."""
    soquete = raiz / "proxy"
    processo = subprocess.Popen(
        ["xdg-dbus-proxy", bluez.endereco, str(soquete), "--filter", *filtros],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        assert bm.esperar(soquete.exists, teto=5.0), "o xdg-dbus-proxy não abriu o soquete"
        yield f"unix:path={soquete}"
    finally:
        processo.terminate()
        try:
            processo.wait(timeout=5)
        except subprocess.TimeoutExpired:
            processo.kill()
            processo.wait(timeout=5)


def _dono(endereco: str) -> bd.DonoVivo:
    barramento = bd.BarramentoGio(endereco)
    assert barramento.abrir(), barramento.erro
    dono = bd.DonoVivo(barramento, kernel=lambda: {}, lugares=lambda: {})
    assert dono.ligar()
    return dono


@pede_o_proxy
def test_o_agente_proprio_atravessa_o_proxy_do_flatpak(tmp_path: Path) -> None:
    """``RegisterAgent`` e ``Pair`` saem com o mesmo remetente, e o BlueZ chama o"""
    with (
        bm.BluezParticular(tmp_path) as bluez,
        _pelo_proxy(bluez, tmp_path, nomes_de_sistema()) as endereco,
    ):
        dono = _dono(endereco)
        try:
            assert dono.caminhos() is not None, (
                "o dono não vê o BlueZ pelo proxy: o manifesto perdeu o "
                f"--system-talk-name={bd.SERVICO}"
            )
            escrita = dono.parear(DISPOSITIVO)
            assert escrita.feita, escrita
            assert bluez.o_padrao_atendeu == [], (
                "quem atendeu o Pair foi o agente padrão: o remetente do Pair não "
                "casou com o do RegisterAgent do outro lado do proxy"
            )
            assert ("RequestConfirmation", True) in list(dono._agente.historico), (
                "o RequestConfirmation do BlueZ não chegou ao agente pelo proxy"
            )
            assert bm.esperar(
                lambda: dono.propriedade(DISPOSITIVO, bd.APARELHO, "Paired") is True
            ), "o PropertiesChanged do BlueZ não atravessou o proxy"
            assert bluez.mesa[DISPOSITIVO][bd.APARELHO]["Trusted"] is True
        finally:
            dono.fechar()


@pede_o_proxy
def test_o_bluetoothd_que_reinicia_chega_de_novo_pelo_proxy(tmp_path: Path) -> None:
    """O ``NameOwnerChanged`` do ``org.bluez`` atravessa o proxy: o agente passa"""
    with (
        bm.BluezParticular(tmp_path) as bluez,
        _pelo_proxy(bluez, tmp_path, nomes_de_sistema()) as endereco,
    ):
        dono = _dono(endereco)
        try:
            assert dono.parear(DISPOSITIVO).feita
            velho = bluez.nome_do_bluez
            assert dono.dono_do_bluez() == velho
            bluez.reiniciar()
            novo = bluez.nome_do_bluez
            assert novo != velho
            assert bm.esperar(lambda: dono.dono_do_bluez() == novo, teto=5.0), (
                "o NameOwnerChanged do org.bluez não atravessou o proxy: o agente segue "
                f"esperando {dono.dono_do_bluez()!r}, e o bluetoothd novo é {novo!r}"
            )
            escrita = dono.parear(bm.no_de(bm.OUTRO))
            assert escrita.feita, escrita
            assert bluez.o_padrao_atendeu == []
            assert list(dono._agente.historico).count(("RequestConfirmation", True)) == 2
        finally:
            dono.fechar()


@pede_o_proxy
def test_sem_a_linha_o_proxy_esconde_o_bluez(tmp_path: Path) -> None:
    """Controle da régua acima: o proxy filtra de fato, e sem o ``--talk`` o dono"""
    with (
        bm.BluezParticular(tmp_path) as bluez,
        _pelo_proxy(bluez, tmp_path, []) as endereco,
    ):
        dono = _dono(endereco)
        try:
            assert dono.caminhos() is None
            assert not dono.parear(DISPOSITIVO).feita
            assert bluez.o_padrao_atendeu == []
        finally:
            dono.fechar()


@pede_o_proxy
def test_o_intruso_chega_ao_agente_e_o_agente_recusa(tmp_path: Path) -> None:
    """O proxy entrega ao agente a chamada de QUALQUER remetente (medido): quem"""
    with (
        bm.BluezParticular(tmp_path) as bluez,
        _pelo_proxy(bluez, tmp_path, nomes_de_sistema()) as endereco,
    ):
        dono = _dono(endereco)
        try:
            agente = dono._agente_pronto()
            assert agente is not None and agente.registrado
            intruso = bluez.outro_cliente()
            with agente.esperando(DISPOSITIVO):
                try:
                    intruso.chamar(
                        dono._barramento.nome_unico(),
                        CAMINHO_DO_AGENTE,
                        bd.AGENTE,
                        "RequestAuthorization",
                        intruso.GLib.Variant("(o)", (DISPOSITIVO,)),
                    )
                    recusa = ""
                except intruso.GLib.Error as erro:
                    recusa = intruso.Gio.DBusError.get_remote_error(erro) or erro.message
            assert recusa == bd.ERRO_REJEITADO, (
                f"o intruso chamou o agente e recebeu {recusa!r}: o agente aceitou um "
                "remetente que não é o bluetoothd, ou o proxy mudou de comportamento"
            )
            assert ("RequestAuthorization", False) in list(agente.historico)
        finally:
            dono.fechar()
