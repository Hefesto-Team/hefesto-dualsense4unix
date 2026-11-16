"""O «sim» de ``aparelhos`` mostra o que o autor não escolhe e vale só para o que se aceitou.

1. A linha do «sim» diz o rótulo do autor e, ao lado, a classe, o VID:PID e o nome que o próprio
   aparelho ligado dá.
2. A marca de um controle que o Hefesto gerencia recusa o manifesto; o nó de teclado, de mouse
   ou de controle (pelo descritor HID, ou pela interface HID do USB cru) nunca casa.
3. O registro guarda cada ``classe:vid:pid`` aceito; a montagem e o ``aparelho.abrir`` conferem
   contra ele, e o aparelho novo de uma versão nova volta a pedir o «sim». O «sim» gravado sem a
   lista migra uma vez, com os aparelhos do manifesto instalado.

Tudo num lar de mentira e num ``/sys`` de mentira; nenhum aparelho de verdade se abre.
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from rich.console import Console

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.mods import de_fabrica_por_endereco as fabrica
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods.instalador import (
    InstalacaoRecusadaError,
    Lugares,
    aceitos_de,
    gravar_registro,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
    migrar_os_aparelhos,
)
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    pedidos_do_sim,
    permissoes_novas,
)
from tests.unit.test_a_extensao_de_fabrica_por_endereco_chega_pelo_install import (
    NOVA,
    _lista,
    _repo,
    lg,
)
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import _supervisor, curto, lar

__all__ = ["curto", "lar", "lg"]

E429 = {"classe": "hidraw", "vid": "1a86", "pid": "e429", "nome": "Adaptador"}
ANTIGO = {"classe": "hidraw", "vid": "1915", "pid": "520a", "nome": "Adaptador antigo"}
DA_FABRICANTE = bytes.fromhex("06a0ff0901a1010901150026ff00750895408102c0")
TECLADO = bytes.fromhex("05010906a101050719e029e71500250175019508810295017508810105081901"
                        "2905910295017503910105071900296515002565810075089506810 0c0".replace(
                            " ", ""))
MOUSE = bytes.fromhex("05010902a1010901a10005091901290315002501950375018102c0c0")
CONTROLE = bytes.fromhex("05010905a10185010930093115002600ff750895028102c0")


def _manifesto(aparelhos: list[dict[str, Any]], mod_id: str = "exemplo") -> dict[str, Any]:
    return {
        "id": mod_id, "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": ["aparelhos"], "aparelhos": aparelhos,  # (noqa-acento)
    }


def _hidraw(sys_: Path, no: str, vid: str, pid: str, descritor: bytes | None = DA_FABRICANTE,
            nome: str = "") -> None:
    dispositivo = sys_ / "devices/hid" / no
    dispositivo.mkdir(parents=True)
    linhas = [f"HID_ID=0003:0000{vid.upper()}:0000{pid.upper()}"]
    if nome:
        linhas.append(f"HID_NAME={nome}")
    (dispositivo / "uevent").write_text("\n".join(linhas) + "\n")
    if descritor is not None:
        (dispositivo / "report_descriptor").write_bytes(descritor)
    classe = sys_ / "class/hidraw" / no
    classe.mkdir(parents=True)
    (classe / "device").symlink_to(dispositivo)
    numero = os.stat("/dev/null").st_rdev
    (classe / "dev").write_text(f"{os.major(numero)}:{os.minor(numero)}\n")


def _usb(sys_: Path, nome: str, vid: str, pid: str, interfaces: tuple[str, ...],
         numero: int) -> None:
    pasta = sys_ / "devices/usb3" / nome
    pasta.mkdir(parents=True)
    for arquivo, valor in (("idVendor", vid), ("idProduct", pid), ("busnum", "3"),
                           ("devnum", str(numero)), ("product", "Cabo")):
        (pasta / arquivo).write_text(valor + "\n")
    for ordem, classe in enumerate(interfaces):
        interface = pasta / f"{nome}:1.{ordem}"
        interface.mkdir()
        (interface / "bInterfaceClass").write_text(classe + "\n")
    (sys_ / "bus/usb/devices").mkdir(parents=True, exist_ok=True)
    (sys_ / "bus/usb/devices" / nome).symlink_to(pasta)


def test_a_linha_do_sim_diz_a_classe_o_vid_pid_e_o_nome_do_aparelho(tmp_path: Path) -> None:
    sys_ = tmp_path / "sys"
    _hidraw(sys_, "hidraw4", "1a86", "e429", nome="QinHeng CH9329")
    manifesto = Manifesto.model_validate(_manifesto([E429, ANTIGO]))
    assert pedidos_do_sim(manifesto) == [
        "aparelhos", "aparelho:hidraw:1a86:e429", "aparelho:hidraw:1915:520a"]
    assert sup.frase_do_pedido("aparelho:hidraw:1a86:e429", manifesto, sys_) == (
        "Abrir «Adaptador» (hidraw 1a86:e429, ligado agora: «QinHeng CH9329»).")
    assert sup.frase_do_pedido("aparelho:hidraw:1915:520a", manifesto, sys_) == (
        "Abrir «Adaptador antigo» (hidraw 1915:520a).")
    console = Console(width=200, color_system=None)
    with console.capture() as captura:
        original, cmd_mod.console = cmd_mod.console, console
        try:
            cmd_mod._mostrar_permissoes(pedidos_do_sim(manifesto), manifesto)
        finally:
            cmd_mod.console = original
    assert "aparelho:hidraw:1a86:e429: Abrir «Adaptador» (hidraw 1a86:e429" in captura.get()


@pytest.mark.parametrize("vid, pid", [
    ("054c", "0ce6"), ("054c", "0df2"), ("057e", "2009"), ("2dc8", "6001"), ("045e", "028e")])
def test_a_marca_de_controle_recusa_o_manifesto(vid: str, pid: str) -> None:
    with pytest.raises(ValueError, match="controle que o Hefesto gerencia"):
        Manifesto.model_validate(_manifesto([{**E429, "vid": vid, "pid": pid}]))


def test_o_descritor_diz_a_colecao_de_aplicacao() -> None:
    assert sup.colecoes_de_aplicacao(DA_FABRICANTE) == {(0xFFA0, 0x01)}
    assert sup.colecoes_de_aplicacao(TECLADO) == {(0x01, 0x06)}
    assert sup.colecoes_de_aplicacao(MOUSE) == {(0x01, 0x02)}
    assert sup.colecoes_de_aplicacao(CONTROLE) == {(0x01, 0x05)}


def test_o_no_de_teclado_mouse_ou_controle_nunca_casa(tmp_path: Path) -> None:
    sys_ = tmp_path / "sys"
    _hidraw(sys_, "hidraw1", "1a86", "e429")
    _hidraw(sys_, "hidraw2", "1a86", "e429", TECLADO)
    _hidraw(sys_, "hidraw3", "1a86", "e429", MOUSE)
    _hidraw(sys_, "hidraw5", "1a86", "e429", CONTROLE)
    _hidraw(sys_, "hidraw6", "1a86", "e429", None)
    _usb(sys_, "3-1", "1a86", "e429", ("03", "ff"), 8)
    _usb(sys_, "3-2", "1a86", "7523", ("ff",), 9)
    manifesto = Manifesto.model_validate(_manifesto([
        E429, {**E429, "classe": "usb"}, {**E429, "classe": "usb", "pid": "7523"}]))
    aceitos = pedidos = [p.removeprefix("aparelho:") for p in pedidos_do_sim(manifesto)[1:]]
    assert pedidos == ["hidraw:1a86:e429", "usb:1a86:e429", "usb:1a86:7523"]
    assert sup.aparelhos_que_casam(manifesto, aceitos, sys_) == (
        "/dev/hidraw1", "/dev/bus/usb/003/009")
    assert list(sup.nos_pela_porta(manifesto, aceitos, sys_)) == ["/dev/hidraw1"]
    for no in ("hidraw2", "hidraw3", "hidraw5", "hidraw6"):
        with pytest.raises(ValueError, match="não é de um aparelho aceito"):
            sup.abrir_o_aparelho(manifesto, no, aceitos, sys_, tmp_path / "dev")


def test_so_o_aparelho_aceito_casa_e_abre(tmp_path: Path) -> None:
    sys_ = tmp_path / "sys"
    _hidraw(sys_, "hidraw1", "1a86", "e429")
    _hidraw(sys_, "hidraw2", "1915", "520a")
    manifesto = Manifesto.model_validate(_manifesto([E429, ANTIGO]))
    aceitos = ["hidraw:1a86:e429"]
    assert sup.aparelhos_que_casam(manifesto, aceitos, sys_) == ("/dev/hidraw1",)
    assert list(sup.nos_pela_porta(manifesto, aceitos, sys_)) == ["/dev/hidraw1"]
    with pytest.raises(ValueError, match="não é de um aparelho aceito"):
        sup.abrir_o_aparelho(manifesto, "hidraw2", aceitos, sys_, tmp_path / "dev")


def test_a_porta_confere_contra_o_registro_e_nao_contra_o_manifesto(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sys_ = tmp_path / "sys"
    _hidraw(sys_, "null", "1915", "520a")
    manifesto = Manifesto.model_validate(_manifesto([E429, ANTIGO]))
    entrada = SimpleNamespace(ligada=True, permissoes_aceitas=["aparelhos"],
                              aparelhos_aceitos=["hidraw:1a86:e429"])
    monkeypatch.setattr(sup, "ler_registro", lambda caminho: {"exemplo": entrada})
    real = sup.abrir_o_aparelho
    monkeypatch.setattr(sup, "abrir_o_aparelho",
                        lambda m, no, aceitos: real(m, no, aceitos, sys_, Path("/dev")))
    supervisor = sup.Supervisor.__new__(sup.Supervisor)
    supervisor.lugares = SimpleNamespace(registro=tmp_path / "r.json")  # type: ignore[assignment]
    supervisor._vigiadas = {"exemplo": sup._Vigiada("exemplo", ficha="ficha")}
    abrir = supervisor._abridor_dos_aparelhos(manifesto, "ficha")
    assert abrir is not None
    with pytest.raises(ValueError, match="não é de um aparelho aceito"):
        abrir("null")
    entrada.aparelhos_aceitos = ["hidraw:1a86:e429", "hidraw:1915:520a"]
    os.close(abrir("null"))


def _instalar(lar: Lugares, base: Path, aparelhos: list[dict[str, Any]]) -> None:
    pasta = base / "fonte"
    pasta.mkdir(exist_ok=True)
    (pasta / "hefesto-mod.json").write_text(json.dumps(_manifesto(aparelhos)), encoding="utf-8")
    (pasta / "m.py").write_text("", encoding="utf-8")
    instalar(str(pasta), lugares=lar)


def test_o_aparelho_novo_da_versao_nova_pede_o_sim_de_novo(lar: Lugares, curto: Path) -> None:
    """D-1511-O-SIM-DOS-APARELHOS-VALE-SO-PARA-O-ACEITO."""
    _instalar(lar, curto, [E429])
    with pytest.raises(InstalacaoRecusadaError, match="outras permissões"):
        ligar("exemplo", permissoes_vistas=["aparelhos"], lugares=lar)
    vistas = pedidos_do_sim(manifesto_instalado("exemplo", lugares=lar))
    assert ligar("exemplo", permissoes_vistas=vistas, lugares=lar).aparelhos_aceitos == [
        "hidraw:1a86:e429"]
    _instalar(lar, curto, [E429, ANTIGO])
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.aparelhos_aceitos == ["hidraw:1a86:e429"]
    assert not entrada.ligada, "o aparelho novo desliga até o «sim» de novo"
    novo = manifesto_instalado("exemplo", lugares=lar)
    assert permissoes_novas(aceitos_de(entrada), pedidos_do_sim(novo)) == [
        "aparelho:hidraw:1915:520a"]
    motivo, aberto = _supervisor(lar)._o_que_impede(entrada)
    assert aberto is None and "aparelho:hidraw:1915:520a" in motivo
    ligar("exemplo", permissoes_vistas=pedidos_do_sim(novo), lugares=lar)
    assert ler_registro(lar.registro)["exemplo"].aparelhos_aceitos == [
        "hidraw:1a86:e429", "hidraw:1915:520a"]


def test_o_sim_antigo_migra_uma_vez_com_os_aparelhos_instalados(
        lar: Lugares, curto: Path) -> None:
    _instalar(lar, curto, [E429])
    registro = ler_registro(lar.registro)
    registro["exemplo"].permissoes_aceitas = ["aparelhos"]
    registro["exemplo"].aparelhos_aceitos = None
    gravar_registro(lar.registro, registro)
    bruto = json.loads(lar.registro.read_text(encoding="utf-8"))
    for linha in bruto["mods"]:
        linha.pop("aparelhos_aceitos", None)
    lar.registro.write_text(json.dumps(bruto), encoding="utf-8")
    asyncio.run(_supervisor(lar).reconciliar())
    assert ler_registro(lar.registro)["exemplo"].aparelhos_aceitos == ["hidraw:1a86:e429"]
    (lar.codigo / "exemplo" / "hefesto-mod.json").write_text(
        json.dumps(_manifesto([E429, ANTIGO])), encoding="utf-8")
    registro = ler_registro(lar.registro)
    assert migrar_os_aparelhos(lar, registro) == [], "a migração vale uma vez só"
    assert registro["exemplo"].aparelhos_aceitos == ["hidraw:1a86:e429"]


def test_sem_o_sim_de_aparelhos_a_migracao_nao_aceita_nenhum(lar: Lugares, curto: Path) -> None:
    _instalar(lar, curto, [E429])
    registro = ler_registro(lar.registro)
    registro["exemplo"].aparelhos_aceitos = None
    assert migrar_os_aparelhos(lar, registro) == ["exemplo"]
    assert registro["exemplo"].aparelhos_aceitos == []


def test_a_lovense_publicada_segue_aceita() -> None:
    lovense = _manifesto([
        {**E429, "pela_porta": True}, ANTIGO, {**ANTIGO, "classe": "tty"}], mod_id="intiface")
    manifesto = Manifesto.model_validate(lovense)
    assert [p for p in pedidos_do_sim(manifesto) if p.startswith("aparelho:")] == [
        "aparelho:hidraw:1a86:e429", "aparelho:hidraw:1915:520a", "aparelho:tty:1915:520a"]


def _de_fabrica_com_aparelhos(tmp_path: Path) -> str:
    return _repo(tmp_path, NOVA, tipos=["tema", "processo"],
                 processo={"executar": ["python3", "m.py"]},
                 permissoes=["tema", "aparelhos"], aparelhos=[E429])


def test_a_de_fabrica_com_aparelhos_chega_ligada_com_eles_aceitos(
        lg: Lugares, tmp_path: Path) -> None:
    lista = _lista(tmp_path, {"id": NOVA, "endereco": _de_fabrica_com_aparelhos(tmp_path)})
    feitos = fabrica.trazer(lugares=lg, arquivo=lista)
    assert [(f.id, f.o_que, f.frase) for f in feitos] == [(NOVA, "ligada", "")]
    entrada = ler_registro(lg.registro)[NOVA]
    assert entrada.ligada and entrada.aparelhos_aceitos == ["hidraw:1a86:e429"]


def test_a_de_fabrica_com_aparelhos_que_nasceu_desligada_se_liga_com_eles(
        lg: Lugares, tmp_path: Path) -> None:
    endereco = _de_fabrica_com_aparelhos(tmp_path)
    instalar(endereco, lugares=lg)
    lg.registro.with_name(fabrica.TRAZIDAS).write_text(json.dumps({"trazidas": [NOVA]}))
    feitos = fabrica.trazer(lugares=lg, arquivo=_lista(tmp_path, {"id": NOVA,
                                                                  "endereco": endereco}))
    assert [(f.id, f.o_que, f.frase) for f in feitos] == [(NOVA, "ligada", "")]
    assert ler_registro(lg.registro)[NOVA].aparelhos_aceitos == ["hidraw:1a86:e429"]
