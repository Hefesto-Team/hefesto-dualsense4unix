"""O-BROKER-SO-ENTREGA-O-ACIONADOR-AUTORIZADO-01 — o broker serve só o aparelho da lista do root.

A chave do acionador sai inteira do ``/sys``, que todo processo lê: conferir a chave não prova que a
pessoa escolheu o aparelho. O broker só serve a chave que está na lista do root
(``/var/lib/hefesto-dualsense4unix/acionadores/autorizados``), e a chave só entra na lista pelo
``pkexec`` do ajudante, com a senha de administrador. Tirar da lista não pede senha.

MORDIDAS: arranque a conferência da lista em ``_cmd_open_acionador`` e o teclado fora da lista
sai do broker; troque o ``st_mode & 0o022`` de ``acionadores_autorizados`` e a lista que outro
escreve vale; tire o ``AcionadorNaoAutorizadoError`` do clique e a senha nunca é pedida.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import evdev
import pytest

from hefesto_dualsense4unix.broker import hidraw_broker as hb
from hefesto_dualsense4unix.core import evdev_reader
from hefesto_dualsense4unix.integrations.hidraw_broker_client import HidrawBrokerClient
from hefesto_dualsense4unix.utils import maquina
from tests.unit import test_o_acionador_le_o_aparelho_declarado_sem_o_grupo_input as leitura
from tests.unit import test_os_acionadores_usb_entram_como_botoes as usb

RAIZ = Path(__file__).resolve().parents[2]
AJUDANTE = RAIZ / "scripts" / "hefesto_acionador_raiz.sh"
POLITICA = RAIZ / "assets" / "polkit" / "org.hefesto.dualsense4unix.acionador.policy"
UNIDADE = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service"
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
CHAVE = leitura.CHAVE
OUTRA = "046d:c31c:0123abcd"


def _lista(caminho: Path, *chaves: str, modo: int = 0o644) -> Path:
    caminho.write_text("".join(f"{c}\n" for c in chaves), encoding="ascii")
    caminho.chmod(modo)
    return caminho


def _broker(mesa: Any, lista: Path) -> hb.BrokerState:
    broker = mesa.broker()
    broker._acionadores_path = str(lista)
    return broker


def test_o_teclado_fora_da_lista_nao_sai_do_broker(tmp_path: Path) -> None:
    mesa = leitura._Mesa(tmp_path)
    no = mesa.no("event3")
    for lista in (tmp_path / "nao-existe", _lista(tmp_path / "vazia"),
                  _lista(tmp_path / "outra", OUTRA)):
        resposta, fd = leitura._pedir(_broker(mesa, lista), no, CHAVE)
        assert fd is None, f"o broker serviu o teclado fora da lista {lista.name}"
        assert resposta["error"] == "reject_nao_autorizado", resposta

    resposta, fd = leitura._pedir(_broker(mesa, _lista(tmp_path / "com", OUTRA, CHAVE)), no, CHAVE)
    assert resposta["ok"] and fd is not None, resposta
    os.close(fd)


@pytest.mark.parametrize("estrago", ["escrita-dos-outros", "escrita-do-grupo", "link"])
def test_a_lista_que_outro_pode_escrever_vale_vazia(tmp_path: Path, estrago: str) -> None:
    mesa = leitura._Mesa(tmp_path)
    no = mesa.no("event3")
    lista = _lista(tmp_path / "autorizados", CHAVE)
    if estrago == "escrita-dos-outros":
        lista.chmod(0o646)
    elif estrago == "escrita-do-grupo":
        lista.chmod(0o664)
    else:
        lista = tmp_path / "pelo-link"
        lista.symlink_to(tmp_path / "autorizados")
    assert hb.acionadores_autorizados(str(lista)) == frozenset()
    resposta, fd = leitura._pedir(_broker(mesa, lista), no, CHAVE)
    assert fd is None and resposta["error"] == "reject_nao_autorizado", resposta


def test_as_recusas_de_antes_seguem_antes_da_lista(tmp_path: Path) -> None:
    """A lista não abre nada que a conferência do ``/sys`` recusava: o controle segue recusado."""
    mesa = leitura._Mesa(tmp_path)
    controle = mesa.no("event4", vendor="054c", nome="Wireless Controller")
    chave = maquina.chave_do_acionador("054c", "abcd", "Wireless Controller", leitura.FISICO)
    resposta, fd = leitura._pedir(_broker(mesa, _lista(tmp_path / "l", chave)), controle, chave)
    assert fd is None and resposta["error"] == "reject_controle_de_jogo", resposta


def test_retirar_tira_da_lista_sem_senha_e_o_broker_para_de_servir(tmp_path: Path) -> None:
    mesa = leitura._Mesa(tmp_path)
    no = mesa.no("event3")
    lista = _lista(tmp_path / "autorizados", OUTRA, CHAVE)
    broker = _broker(mesa, lista)

    pedido = json.dumps({"cmd": "acionador_retirar", "acionador": CHAVE}).encode()
    resposta, fd = broker.handle_line(1, leitura.UID, pedido)
    assert resposta["ok"] and fd is None, resposta
    assert lista.read_text(encoding="ascii") == f"{OUTRA}\n"
    assert lista.stat().st_mode & 0o777 == 0o644

    resposta, fd = leitura._pedir(broker, no, CHAVE)
    assert fd is None and resposta["error"] == "reject_nao_autorizado"

    torto = json.dumps({"cmd": "acionador_retirar", "acionador": "nada"}).encode()
    assert not broker.handle_line(1, leitura.UID, torto)[0]["ok"]
    assert lista.read_text(encoding="ascii") == f"{OUTRA}\n"


def test_o_cliente_pede_a_retirada_pela_chave(monkeypatch: pytest.MonkeyPatch) -> None:
    pedidos: list[dict[str, Any]] = []

    def responder(_self: Any, pedido: dict[str, Any]) -> dict[str, Any]:
        pedidos.append(pedido)
        return {"ok": True, "cmd": "acionador_retirar"}

    monkeypatch.setattr(HidrawBrokerClient, "_request", responder)
    assert HidrawBrokerClient("/nao/existe.sock").retirar_acionador(CHAVE)
    assert pedidos == [{"cmd": "acionador_retirar", "acionador": CHAVE}]


def test_o_broker_pode_gravar_a_pasta_da_lista_e_mais_nenhuma() -> None:
    gravaveis = [linha.split("=", 1)[1] for linha in UNIDADE.read_text().splitlines()
                 if linha.startswith("ReadWritePaths=")]
    assert "-/var/lib/hefesto-dualsense4unix/acionadores" in gravaveis
    assert not any(g.rstrip("/") in ("-/var/lib/hefesto-dualsense4unix", "/var/lib")
                   for g in gravaveis)


def _ajudante(pasta: Path, verbo: str, entrada: str,
              **amb: str) -> subprocess.CompletedProcess[str]:
    ambiente = {"PATH": os.environ["PATH"], "HEFESTO_ACIONADOR_PASTA": str(pasta), **amb}
    return subprocess.run(["bash", str(AJUDANTE), verbo], input=entrada, text=True,
                          capture_output=True, env=ambiente, check=False, timeout=30)


@pytest.mark.skipif(os.geteuid() == 0, reason="o ajudante como root escreve no /var/lib real")
def test_o_ajudante_autoriza_uma_chave_por_vez_e_nunca_duplica(tmp_path: Path) -> None:
    pasta = tmp_path / "acionadores"
    lista = pasta / "autorizados"
    assert _ajudante(pasta, "autorizar", f"{CHAVE}\n").returncode == 0
    assert _ajudante(pasta, "autorizar", f"{CHAVE}\n").returncode == 0
    assert _ajudante(pasta, "autorizar", OUTRA).returncode == 0
    assert lista.read_text(encoding="ascii").splitlines() == sorted([CHAVE, OUTRA])
    assert lista.stat().st_mode & 0o777 == 0o644
    assert hb.acionadores_autorizados(str(lista)) == {CHAVE, OUTRA}

    for torta in ("nada\n", "1234:abcd:0123abc\n", f"{CHAVE.upper()}\n", "\n", ""):
        feito = _ajudante(pasta, "autorizar", torta)
        assert feito.returncode == 2, (torta, feito.stderr)
    assert lista.read_text(encoding="ascii").splitlines() == sorted([CHAVE, OUTRA])
    assert sorted(p.name for p in pasta.iterdir()) == ["autorizados"]


@pytest.mark.skipif(os.geteuid() == 0, reason="o ajudante como root escreve no /var/lib real")
def test_semear_so_cria_a_lista_na_migracao(tmp_path: Path) -> None:
    pasta = tmp_path / "acionadores"
    lista = pasta / "autorizados"
    assert _ajudante(pasta, "semear", f"{CHAVE}\nlixo\n{OUTRA}\n").returncode == 0
    assert lista.read_text(encoding="ascii").splitlines() == sorted([CHAVE, OUTRA])
    _lista(lista, CHAVE)
    assert _ajudante(pasta, "semear", f"{OUTRA}\n").returncode == 0
    assert lista.read_text(encoding="ascii") == f"{CHAVE}\n", "o segundo install semeou de novo"

    vazia = tmp_path / "vazia"
    assert _ajudante(vazia, "semear", "").returncode == 0
    assert (vazia / "autorizados").read_text(encoding="ascii") == ""


@pytest.mark.skipif(os.geteuid() == 0, reason="como root o ajudante usa o /var/lib real")
def test_sem_root_e_sem_pasta_o_ajudante_recusa() -> None:
    feito = subprocess.run(["bash", str(AJUDANTE), "autorizar"], input=f"{CHAVE}\n", text=True,
                           capture_output=True, env={"PATH": os.environ["PATH"]}, check=False,
                           timeout=30)
    assert feito.returncode == 2


def test_a_politica_pede_a_senha_de_administrador_e_aponta_o_ajudante() -> None:
    acao = ET.parse(POLITICA).getroot().find("action")
    assert acao is not None and acao.get("id") == "org.hefesto.dualsense4unix.acionador.autorizar"
    defaults = acao.find("defaults")
    assert defaults is not None
    padroes = {p.tag: p.text for p in defaults}
    assert padroes == {"allow_any": "no", "allow_inactive": "auth_admin",
                       "allow_active": "auth_admin"}
    anotado = {a.get("key"): a.text for a in acao.findall("annotate")}
    assert anotado["org.freedesktop.policykit.exec.path"] == maquina.AJUDANTE_DO_ACIONADOR
    assert acao.findtext("message") == "O Hefesto vai ler todas as teclas deste aparelho."


def _funcao(nome: str) -> str:
    texto = CAMADA.read_text(encoding="utf-8")
    inicio = texto.index(f"{nome}() {{")
    return texto[inicio:texto.index("\n}\n", inicio) + 3]


def test_o_install_semeia_as_chaves_declaradas_e_instala_antes_do_broker_subir(
        tmp_path: Path) -> None:
    casa = tmp_path / "casa"
    conf = casa / ".config" / "hefesto-dualsense4unix"
    conf.mkdir(parents=True)
    (conf / "maquina.json").write_text(json.dumps({"acionadores": {
        CHAVE: {"controle": "aabbcc000001"}, OUTRA: {"controle": "aabbcc000002"}}}))
    nome = "_chaves_dos_acionadores_declarados"
    roteiro = f"{_funcao(nome)}\n{nome}\n"
    feito = subprocess.run(["bash", "-c", roteiro], capture_output=True, text=True, check=False,
                           env={"PATH": os.environ["PATH"], "HOME": str(casa)}, timeout=30)
    assert sorted(feito.stdout.split()) == sorted([CHAVE, OUTRA]), feito.stderr

    corpo = _funcao("install_broker_host")
    assert corpo.index("_instalar_o_acionador_raiz") < corpo.index("enable --now"), (
        "a lista tem de existir antes do broker novo subir, ou o pedal declarado some")
    instalar = _funcao("_instalar_o_acionador_raiz")
    assert "semear" in instalar and "/usr/share/polkit-1/actions/" in instalar
    assert "NOPASSWD" not in CAMADA.read_text(encoding="utf-8").split(
        "_instalar_o_acionador_raiz() {", 1)[1].split("\n}\n", 1)[0]


def test_o_aparelho_fora_da_lista_diz_que_falta_autorizar(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A recusa vem do broker de verdade, pela conexão do cliente, e não da leitura da lista."""
    mesa = leitura._Mesa(tmp_path)
    no = mesa.no("event3")
    monkeypatch.setattr(maquina, "RAIZ_DAS_ENTRADAS", str(mesa.sys))
    monkeypatch.setattr(evdev, "InputDevice", leitura._recusar)
    broker = _broker(mesa, _lista(tmp_path / "autorizados", OUTRA))

    def pelo_cliente(_self: Any, pedido: dict[str, Any]) -> tuple[dict[str, Any], list[int]]:
        no_da_mesa = {**pedido, "node": str(pedido["node"]).replace("/dev/input", str(mesa.dev))}
        resposta, fd = broker.handle_line(1, leitura.UID, json.dumps(no_da_mesa).encode())
        return dict(resposta), [] if fd is None else [fd]

    monkeypatch.setattr(HidrawBrokerClient, "_request_with_fds", pelo_cliente)
    with pytest.raises(maquina.AcionadorNaoAutorizadoError) as recusa:
        maquina.abrir_o_aparelho_de_entrada("event3")
    assert isinstance(recusa.value, maquina.SemPermissaoDeLerError)
    assert str(recusa.value) == maquina.FRASE_O_APARELHO_NAO_FOI_AUTORIZADO
    assert recusa.value.filename == "/dev/input/event3" and no.endswith("/event3")

    monkeypatch.setattr(maquina, "_pedir_o_acionador_ao_broker", lambda _n, _c: (
        None, "o broker não respondeu"))
    with pytest.raises(maquina.SemPermissaoDeLerError) as recusa:
        maquina.abrir_o_aparelho_de_entrada("event3")
    assert not isinstance(recusa.value, maquina.AcionadorNaoAutorizadoError)
    assert str(recusa.value) == maquina.FRASE_SEM_PERMISSAO_DE_LER


def test_autorizar_passa_a_chave_pelo_stdin_do_pkexec(tmp_path: Path) -> None:
    ajudante = tmp_path / "acionador-raiz"
    ajudante.write_text("#!/bin/sh\n")
    ajudante.chmod(0o755)
    chamadas: list[tuple[list[str], str]] = []

    def rodar(rc: int) -> Any:
        def dentro(argv: list[str], **kw: Any) -> Any:
            chamadas.append((argv, kw["input"]))
            return SimpleNamespace(returncode=rc)
        return dentro

    assert maquina.autorizar_o_acionador(
        CHAVE, pkexec="/usr/bin/pkexec", ajudante=str(ajudante), rodar=rodar(0)) is None
    assert chamadas == [(["/usr/bin/pkexec", str(ajudante), "autorizar"], f"{CHAVE}\n")]
    assert maquina.autorizar_o_acionador(
        CHAVE, pkexec="/usr/bin/pkexec", ajudante=str(ajudante),
        rodar=rodar(126)) == maquina.FRASE_A_SENHA_NAO_VEIO
    assert maquina.autorizar_o_acionador(
        "nada; rm -rf /", pkexec="/usr/bin/pkexec", ajudante=str(ajudante),
        rodar=rodar(0)) == maquina.FRASE_O_APARELHO_NAO_ABRE
    assert len(chamadas) == 2


def test_sem_pkexec_a_aba_diz_que_falta_o_polkit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _nome: None)
    assert maquina.autorizar_o_acionador(CHAVE) == maquina.FRASE_FALTA_O_POLKIT


@pytest.mark.parametrize("senha", ["dada", "negada"])
def test_o_clique_pede_a_senha_uma_vez_e_segue_esperando_a_tecla(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, senha: str) -> None:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    usb._cena(a08, monkeypatch, usb._declarado())
    monkeypatch.setattr(a08, "_RAIZ_DAS_ENTRADAS", str(usb._sys_de_mentira(tmp_path / "input")))
    pedidos: list[str] = []
    abertos: list[str] = []
    autorizada = {"sim": False}

    def abrir(evento: str) -> Any:
        abertos.append(evento)
        if not autorizada["sim"]:
            raise maquina.AcionadorNaoAutorizadoError(
                13, maquina.FRASE_O_APARELHO_NAO_FOI_AUTORIZADO, f"/dev/input/{evento}")
        return SimpleNamespace(fd=-1, close=lambda: None)

    def autorizar(chave: str) -> str | None:
        pedidos.append(chave)
        autorizada["sim"] = senha == "dada"
        return None if autorizada["sim"] else maquina.FRASE_A_SENHA_NAO_VEIO

    monkeypatch.setattr(a08, "_ABRIR_O_EVENTO", abrir)
    monkeypatch.setattr(maquina, "autorizar_o_acionador", autorizar)
    monkeypatch.setattr(a08.fios, "soltar", lambda *_a: None)
    a08.usar_como_botoes(None, {"alvo": usb.CHAVE}, None)
    if senha == "dada":
        assert a08.acionador_nova_tecla(None, {}, None) == {"armou": True}
        assert a08._RASCUNHO.esperando
        assert abertos == ["event7", "event7"]
    else:
        with pytest.raises(RuntimeError) as recusa:
            a08.acionador_nova_tecla(None, {}, None)
        assert str(recusa.value) == maquina.FRASE_A_SENHA_NAO_VEIO
        assert not a08._RASCUNHO.esperando
        assert abertos == ["event7"]
    assert pedidos == [usb.CHAVE]


def test_guardar_sem_tecla_nenhuma_retira_da_lista(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08

    usb._cena(a08, monkeypatch, usb._declarado())
    retirados: list[str] = []
    monkeypatch.setattr(a08, "_RETIRAR_O_ACIONADOR", retirados.append)
    monkeypatch.setattr(a08, "_declarar_o_acionador", lambda _p, _d: None)
    a08.usar_como_botoes(None, {"alvo": usb.CHAVE}, None)
    with a08._TRAVA_DO_RASCUNHO:
        for linha in a08._RASCUNHO.teclas:
            linha[2] = None
    a08.acionador_guardar(None, {"forma": {"acionador-quem": usb.UNIQS[1]}}, None)
    assert retirados == [usb.CHAVE]

    usb._cena(a08, monkeypatch, usb._declarado())
    a08.usar_como_botoes(None, {"alvo": usb.CHAVE}, None)
    a08.acionador_guardar(None, {"forma": {"acionador-quem": usb.UNIQS[1]}}, None)
    assert retirados == [usb.CHAVE], "guardar com tecla não retira a autorização"


@pytest.mark.parametrize("mascara", usb.MASCARAS)
@pytest.mark.parametrize("jogador", range(4))
@pytest.mark.parametrize("autorizado", [True, False])
def test_o_acionador_autorizado_chega_a_cada_jogador_da_mesa_mista(
        monkeypatch: pytest.MonkeyPatch, tmp_path: Path, mascara: str, jogador: int,
        autorizado: bool) -> None:
    """Quatro controles, cabo e rádio alternados, nas duas máscaras: o autorizado aperta o botão do
    controle escolhido; o de fora da lista não chega a controle nenhum."""
    mesa = usb._Mesa(monkeypatch, tmp_path, mascara, usb.UNIQS[jogador])
    lista = _lista(tmp_path / "autorizados", *([usb.CHAVE] if autorizado else [OUTRA]))
    monkeypatch.setattr(maquina, "RAIZ_DAS_ENTRADAS", str(tmp_path / "input"))
    monkeypatch.setattr(evdev, "InputDevice", leitura._recusar)
    monkeypatch.setattr(evdev_reader, "_input_device_do_fd", lambda fd, _c: (
        os.close(fd), mesa.acionador)[1])

    def broker(_no: str, chave: str) -> tuple[int | None, str]:
        if chave in hb.acionadores_autorizados(str(lista)):
            return os.open(os.devnull, os.O_RDONLY), ""
        return None, "o broker recusou: reject_nao_autorizado"

    mesa.ponte._abrir = lambda evento: maquina.abrir_o_aparelho_de_entrada(
        evento, pedir_ao_broker=broker)
    try:
        mesa.tique()
        mesa.acionador.apertar(usb.TECLA_1)
        mesa.tique()
        esperado = [autorizado and n == jogador for n in range(4)]
        assert mesa.com_a_cruz() == esperado
    finally:
        mesa.ponte.parar()
