"""O controle que o produto nunca viu tem nome e cor — O-CONTROLE-NUNCA-VISTO-TEM-NOME-E-COR-01.

A cena dela, 25/09/2026, e ela é o aceite desta régua: *«imagina que eu quero
mostrar pra um user que tem um controle desses edição limitada do dualsense. E
quero mostrar que o app reconhece de primeira. aí ele pluga o controle dele e o
app não funciona pq ele tá todo setado pra funcionar só no meu pc.»*  (noqa-acento): dela

O QUE ESTAVA ERRADO, medido antes da cura com o código real (o leitor do
serial, a mesa e os pacotes das dez páginas):

* os códigos ``13``, ``14``, ``15``, ``ZC``, ``ZD``, ``ZE`` e ``ZF`` estão no
  mapa dela (``docs/data/cores-do-dualsense.csv``, 28 modelos) e não estavam na
  tabela DIGITADA do produto (21): o serial voltava inteiro, no cabo e no rádio,
  e a tela escrevia ``Não sei · USB``, ``P2 • Não sei • BT``;
* um código que nem o mapa conhece (uma edição que sair amanhã) saía igual;
* o DualSense Edge (``054C:0DF2``) nunca tinha a cor perguntada: o leitor o
  recusava pelo PID, e a tela dizia «Não sei» sobre um controle que o daemon
  adota, numera e acende.

O QUE A RÉGUA EXIGE, em toda a matriz — um dos sete códigos, um código
inventado, o Edge com código do mapa e com código inventado; no cabo e no
rádio; de P1 a P4: **o cartão diz um nome e uma cor, e nenhum caminho cai.**
«Nome» é o do mapa quando o código está nele e o do MODELO quando não está;
«cor» é o ``id`` do mapa (o ``data-colorway``) ou o neutro, nunca «Não sei».

A LEITURA É A DO PRODUTO, com um dublê do APARELHO que não é mais frouxo que
ele: a trava do pedido roda (``conferir_pedido``), pelo rádio o pedido sem a
assinatura de semente ``0x53`` volta ``None`` (o ``errno 5`` medido em
02/09/2026), e a assinatura é conferida por uma conta escrita AQUI, com
``zlib``, e não pela do produto — senão a régua mediria a conta contra ela
mesma. Nenhum byte vai a aparelho nenhum.
"""
from __future__ import annotations

import ast
import csv
import json
import pathlib
import sys
import zlib
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.mesa_viva` e os pacotes, que carregam o GTK")

for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.integrations import cor_do_plastico as cp
from hefesto_dualsense4unix.interface import mesa_viva
from hefesto_dualsense4unix.interface import pacotes

MAPA_DAS_CORES = RAIZ / "docs" / "data" / "cores-do-dualsense.csv"

#: Os sete que a tabela digitada de 21 não tinha — medidos saindo «Não sei».
OS_SETE = ("13", "14", "15", "ZC", "ZD", "ZE", "ZF")

#: A semente do feature que SAI pelo rádio, escrita aqui de propósito (ver o
#: cabeçalho): é o número que o aparelho aceitou em 27/08 e 02/09/2026.
_SEMENTE_DO_APARELHO = 0x53

_BUS = {"usb": "0003", "bt": "0005"}
_PID = {"ds": "0CE6", "edge": "0DF2"}

#: A palavra que não pode ser o nome de um controle que funciona.
NAO_SEI = mesa_viva.COR_DESCONHECIDA

#: O leitor de verdade, guardado antes de qualquer `monkeypatch` do daemon.
_LER_DE_VERDADE = cp.ler_identidade_pelo_cabo


def _linhas_do_mapa() -> list[dict[str, str]]:
    texto = MAPA_DAS_CORES.read_text(encoding="utf-8")
    return list(csv.DictReader(
        ln for ln in texto.splitlines() if ln.strip() and not ln.startswith("#")))


def _do_mapa(codigo: str) -> tuple[str, str]:
    """``(id, nome)`` que o CSV dela dá a um código — lidos AQUI, não do produto."""
    for linha in _linhas_do_mapa():
        if linha["codigo_da_cor"].strip().upper() == codigo:
            return linha["id"].strip(), linha["nome"].strip()
    raise AssertionError(f"o mapa não tem o código {codigo}")


# ---------------------------------------------------------------------------
# O aparelho de mentira — um sysfs e um firmware tão estritos quanto os reais
# ---------------------------------------------------------------------------
class Aparelhos:
    """Um ``/sys/class/hidraw`` e os controles atrás dele.

    ``controles`` é ``[(uniq, transporte, modelo, código)]``. O nó do NOSSO vpad
    entra sempre, no fim, com a identidade do Edge no cabo: é ele que o leitor
    não pode confundir com o Edge físico. ``bytes_enviados`` conta o que saiu.
    """

    def __init__(self, controles: list[tuple[str, str, str, str]]) -> None:
        self.controles = controles
        self.nos: dict[str, dict[str, str]] = {}
        self.pais: dict[str, str] = {}
        self.por_caminho: dict[str, tuple[str, str]] = {}
        self.bytes_enviados: list[tuple[str, bytes]] = []
        for i, (uniq, transporte, modelo, codigo) in enumerate(controles):
            no = f"hidraw{i}"
            self.nos[no] = {
                "HID_ID": f"{_BUS[transporte]}:0000054C:0000{_PID[modelo]}",
                "HID_UNIQ": uniq,
                "HID_PHYS": uniq if transporte == "bt" else "usb-0000:00:14.0-3/input3",
            }
            # A TOPOLOGIA REAL: pelo rádio, BlueZ >= 5.73 põe o controle sob o
            # uhid (bus 0005); pelo cabo, o pai é USB de verdade.
            self.pais[no] = (
                f"/sys/devices/virtual/misc/uhid/0005:054C:{_PID[modelo]}.00{i}"
                if transporte == "bt"
                else f"/sys/devices/pci0000:00/0000:00:14.0/usb3/3-3/3-3:1.3/"
                f"0003:054C:{_PID[modelo]}.00{i}"
            )
            self.por_caminho[f"/dev/{no}"] = (transporte, codigo)
        vpad = f"hidraw{len(controles)}"
        self.nos[vpad] = {"HID_ID": "0003:0000054C:00000DF2",
                          "HID_UNIQ": "02:fe:00:00:00:01", "HID_PHYS": "hefesto-vpad"}
        self.pais[vpad] = "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.0099"

    def listar(self, _raiz: str) -> list[str]:
        return sorted(self.nos)

    def ler(self, caminho: str) -> str:
        no = pathlib.Path(caminho).parts[-3]
        return "\n".join(f"{k}={v}" for k, v in self.nos.get(no, {}).items())

    def resolver(self, caminho: str) -> str:
        return self.pais[pathlib.Path(caminho).parts[-2]]

    def perguntar(self, caminho: str, pedido: bytes) -> bytes | None:
        cp.conferir_pedido(pedido)  # a MESMA trava que o real roda antes da porta
        self.bytes_enviados.append((caminho, pedido))
        transporte, codigo = self.por_caminho[caminho]
        corte = len(pedido) - cp.TAMANHO_DO_CRC
        assinado = any(pedido[corte:])
        if transporte == "bt":
            crc = zlib.crc32(bytes([_SEMENTE_DO_APARELHO]) + pedido[:corte]) & 0xFFFFFFFF
            if not assinado or pedido[corte:] != crc.to_bytes(4, "little"):
                return None  # errno 5: o firmware recusa o feature sem a assinatura
        elif assinado:
            return None  # o cabo nunca recebeu envelope; a régua não afirma que aceita
        serial = f"AB1C{codigo}Q0000000000"  # serial-de-mentira: prefixo forjado
        resposta = bytearray(cp.TAMANHO_DO_FEATURE)
        resposta[0:4] = bytes([cp.FEATURE_RESPOSTA, 1, 19, 2])
        resposta[4:4 + 17] = serial.encode("ascii")
        return bytes(resposta)

    def identidade(self, uniq: str) -> cp.IdentidadeDeFabrica:
        """O leitor DO PRODUTO, com este sysfs e este firmware."""
        return _LER_DE_VERDADE(
            uniq, raiz="/sys/class/hidraw", listar=self.listar, ler=self.ler,
            perguntar=self.perguntar, resolver=self.resolver)


def _estado(controles: list[tuple[str, str, str, str]]) -> dict[str, Any]:
    """O ``state_full`` que o daemon publica, com o que ele diria da identidade."""
    return {"controllers": [
        {"uniq": uniq, "player": i, "player_slot": i, "index": i - 1, "connected": True,
         "is_primary": i == 1, "battery_pct": 80, "transport": transporte,
         "vpad_backend": "uhid", "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
         "lightbar_source": "perfil",
         "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128, "l2_raw": 0,
                    "r2_raw": 0, "buttons": []}}
        for i, (uniq, transporte, _modelo, _codigo) in enumerate(controles, start=1)
    ], "output_target_index": None}


def _mesa(aparelhos: Aparelhos) -> list[dict[str, Any]]:
    """O tique do piloto, com a pergunta síncrona no lugar da thread."""
    estado = _estado(aparelhos.controles)
    leitor = mesa_viva.LeitorDeCor(leitor=aparelhos.identidade)
    leitor.esquecer_ausentes({c["uniq"] for c in estado["controllers"]})
    for uniq in leitor.pendentes(estado["controllers"]):
        leitor.perguntar(uniq)
    return mesa_viva.mesa_do_estado(estado, leitor.conhecidos())


#: OS CASOS — ``(rótulo, modelo, código, nome esperado, id esperado)``. O nome e
#: o id esperados dos códigos do mapa saem do CSV lido aqui; o do código
#: inventado é o do MODELO.
def _casos() -> list[tuple[str, str, str, str, str]]:
    casos = []
    for codigo in OS_SETE:
        ident, nome = _do_mapa(codigo)
        casos.append((f"codigo-{codigo}", "ds", codigo, nome, ident))
    casos.append(("codigo-inventado", "ds", "Q7", "DualSense", ""))
    ident, nome = _do_mapa("00")
    casos.append(("edge-do-mapa", "edge", "00", nome, ident))
    casos.append(("edge-inventado", "edge", "Q9", "DualSense Edge", ""))
    return casos


#: Os VIZINHOS de mesa, conhecidos: o caso sob teste senta entre eles.
_VIZINHOS = [("ds", "02"), ("ds", "05"), ("ds", "04")]


def _mesa_com(caso_modelo: str, caso_codigo: str, transporte: str, posicao: int) -> Aparelhos:
    controles: list[tuple[str, str, str, str]] = []
    vizinhos = iter(_VIZINHOS)
    for p in range(1, 5):
        uniq = f"aa:bb:cc:00:00:0{p}"
        if p == posicao:
            controles.append((uniq, transporte, caso_modelo, caso_codigo))
        else:
            modelo, codigo = next(vizinhos)
            outro = "bt" if transporte == "usb" else "usb"  # mesa MISTA
            controles.append((uniq, outro, modelo, codigo))
    return Aparelhos(controles)


# ---------------------------------------------------------------------------
# 1 · A MATRIZ — cada caso, nos dois transportes, em cada assento
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("posicao", [1, 2, 3, 4], ids=lambda p: f"P{p}")
@pytest.mark.parametrize("transporte", ["usb", "bt"])
@pytest.mark.parametrize(
    ("rotulo", "modelo", "de_fabrica", "nome", "ident"), _casos(), ids=lambda v: str(v))
def test_o_cartao_diz_um_nome_e_uma_cor(
    rotulo: str, modelo: str, de_fabrica: str, nome: str, ident: str,
    transporte: str, posicao: int,
) -> None:
    aparelhos = _mesa_com(modelo, de_fabrica, transporte, posicao)
    mesa = _mesa(aparelhos)
    assert [m["jogador"] for m in mesa] == [1, 2, 3, 4]
    item = mesa[posicao - 1]
    assert item["uniq"] == f"aa:bb:cc:00:00:0{posicao}"
    assert item["nome"] == nome, (
        f"{rotulo} no {transporte}, P{posicao}: o cartão disse {item['nome']!r}")
    assert item["nome"] != NAO_SEI
    assert item["cor"] == ident, (
        f"{rotulo}: o desenho recebeu {item['cor']!r}, e o mapa dela diz {ident!r}")
    # E a identidade que a fita escreve é a MESMA do cartão — um nome só.
    entrada = next(c for c in _estado(aparelhos.controles)["controllers"]
                   if c["uniq"] == item["uniq"])
    assert pacotes.identidade_de(entrada, mesa) == nome
    # O VPAD, com a identidade do Edge no cabo, não recebeu byte nenhum.
    vpad = f"/dev/hidraw{len(aparelhos.controles)}"
    assert all(caminho != vpad for caminho, _ in aparelhos.bytes_enviados)


# ---------------------------------------------------------------------------
# 2 · NENHUM CAMINHO CAI — as dez páginas, com a mesa inteira de estranhos
# ---------------------------------------------------------------------------
_MESA_DE_ESTRANHOS = {
    "usb-primeiro": [("aa:bb:cc:00:00:01", "usb", "ds", "ZC"),
                     ("aa:bb:cc:00:00:02", "bt", "ds", "13"),
                     ("aa:bb:cc:00:00:03", "usb", "ds", "Q7"),
                     ("aa:bb:cc:00:00:04", "bt", "edge", "Q9")],
    "bt-primeiro": [("aa:bb:cc:00:00:01", "bt", "ds", "ZF"),
                    ("aa:bb:cc:00:00:02", "usb", "ds", "15"),
                    ("aa:bb:cc:00:00:03", "bt", "ds", "ZZ"),
                    ("aa:bb:cc:00:00:04", "usb", "edge", "00")],
}


def _strings(valor: Any) -> list[str]:
    if isinstance(valor, dict):
        return [s for v in valor.values() for s in _strings(v)]
    if isinstance(valor, (list, tuple)):
        return [s for v in valor for s in _strings(v)]
    return [valor] if isinstance(valor, str) else []


@pytest.mark.parametrize("arranjo", sorted(_MESA_DE_ESTRANHOS))
def test_nenhuma_pagina_cai_nem_escreve_nao_sei(arranjo: str) -> None:
    controles = _MESA_DE_ESTRANHOS[arranjo]
    aparelhos = Aparelhos(controles)
    mesa = _mesa(aparelhos)
    estado = _estado(controles)
    ctx = pacotes.Contexto(state=estado, mesa=mesa, conectados=estado["controllers"])
    para_pref = {str(m["uniq"]): m["pref"] for m in mesa}
    nomes = [m["nome"] for m in mesa]
    assert NAO_SEI not in nomes
    paginas = sorted(pacotes.PACOTES)
    assert len(paginas) >= 10, paginas
    alcancados: set[str] = set()
    for pagina in paginas:
        carga = pacotes.normalizar(pacotes.pacote_da_pagina(pagina, ctx) or {}, para_pref)
        carga["mesa"].update(pacotes.topo(ctx))
        textos = _strings(carga)
        com_nao_sei = [t[:120] for t in textos if NAO_SEI in t]
        assert not com_nao_sei, f"{pagina} escreveu «{NAO_SEI}»: {com_nao_sei[:3]}"
        juntos = json.dumps(carga, ensure_ascii=False)
        alcancados |= {n for n in nomes if n in juntos}
    assert alcancados == set(nomes), (
        f"nomes que nenhuma página escreveu: {sorted(set(nomes) - alcancados)}")


@pytest.mark.parametrize("transporte", ["usb", "bt"])
def test_quem_ainda_nao_foi_lido_ja_tem_nome(transporte: str) -> None:
    """O nó que ainda não nasceu, e a leitura desligada: nome da família.

    É o primeiro segundo de todo controle que chega — o daemon já o publica e o
    ``hidraw`` ainda não existe —, e é o estado de quem roda com ``--sem-cor``.
    Nos dois não há modelo lido, e mesmo assim o cartão não diz «Não sei».
    """
    controles = [("aa:bb:cc:00:00:01", transporte, "ds", "02"),
                 ("aa:bb:cc:00:00:02", transporte, "edge", "00")]
    sem_no = Aparelhos(controles)
    sem_no.nos = {}  # nenhum hidraw ainda
    assert [m["nome"] for m in _mesa(sem_no)] == ["DualSense", "DualSense"]

    estado = _estado(controles)
    desligado = mesa_viva.LeitorDeCor(ligado=False)
    for uniq in desligado.pendentes(estado["controllers"]):
        desligado.perguntar(uniq)
    mesa = mesa_viva.mesa_do_estado(estado, desligado.conhecidos())
    assert [(m["nome"], m["cor"]) for m in mesa] == [("DualSense", "")] * 2


# ---------------------------------------------------------------------------
# 3 · UM DONO SÓ DA TRADUÇÃO — o mapa dos 28
# ---------------------------------------------------------------------------
def test_o_produto_conhece_todo_codigo_do_mapa() -> None:
    do_mapa = {linha["codigo_da_cor"].strip().upper() for linha in _linhas_do_mapa()}
    assert len(do_mapa) == 28
    assert set(cp.NOMES_DE_FABRICA) == do_mapa
    for codigo in do_mapa:
        cor = cp.cor_do_codigo(codigo)
        assert cor is not None and (cor.id, cor.nome) == _do_mapa(codigo)


def test_nenhuma_tabela_de_cores_digitada_no_produto() -> None:
    """A mordida estrutural: um dicionário literal com código de fábrica é a volta."""
    fonte = pathlib.Path(cp.__file__).read_text(encoding="utf-8")
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.Dict):
            chaves = {k.value for k in no.keys if isinstance(k, ast.Constant)}
            assert not chaves & {"00", "02", "Z1", "ZB"}, (
                "cor_do_plastico voltou a digitar uma tabela de cores")


def test_sem_o_mapa_nada_cai_e_o_nome_e_o_do_modelo(
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    """Um pacote instalado sem o ``docs/``: tabela vazia, e o produto de pé."""
    assert cp.ler_a_tabela(tmp_path / "nao-existe.csv") == {}
    monkeypatch.setattr(cp, "TABELA", {})
    aparelhos = Aparelhos([("aa:bb:cc:00:00:01", "usb", "ds", "02"),
                           ("aa:bb:cc:00:00:02", "bt", "edge", "02")])
    mesa = _mesa(aparelhos)
    assert [m["nome"] for m in mesa] == ["DualSense", "DualSense Edge"]


# ---------------------------------------------------------------------------
# 4 · O EDGE — perguntado como o DualSense, sem confundir com o vpad
# ---------------------------------------------------------------------------
def test_os_modelos_sao_os_pids_que_o_daemon_adota() -> None:
    from hefesto_dualsense4unix.broker.hidraw_broker import PHYS_PRODUCTS
    from hefesto_dualsense4unix.core.evdev_reader import DUALSENSE_PIDS

    assert set(cp.MODELOS) == set(DUALSENSE_PIDS) == set(PHYS_PRODUCTS)


def test_o_edge_no_cabo_e_perguntado_e_o_vpad_nao() -> None:
    aparelhos = Aparelhos([("aa:bb:cc:00:00:01", "usb", "edge", "Q9")])
    alvo = cp.alvo_do_controle("aa:bb:cc:00:00:01", listar=aparelhos.listar,
                               ler=aparelhos.ler, resolver=aparelhos.resolver)
    assert alvo is not None and (alvo.transporte, alvo.modelo) == (cp.CABO, "DualSense Edge")
    assert cp.alvo_do_controle("02:fe:00:00:00:01", listar=aparelhos.listar,
                               ler=aparelhos.ler, resolver=aparelhos.resolver) is None


def test_o_vpad_com_endereco_de_controle_cai_pela_topologia() -> None:
    """D1 do broker: USB sob o ``uhid`` é forjado, qualquer que seja o ``uniq``.

    Sem a regra inteira do broker, um nó ``0003:054C:0DF2`` sob
    ``/misc/uhid/`` com ``uniq`` e ``phys`` de aparelho passaria pelas marcas
    (D2) e receberia o comando de fábrica — o vpad é o único que nasce ali.
    """
    aparelhos = Aparelhos([("aa:bb:cc:00:00:01", "usb", "edge", "00")])
    aparelhos.pais["hidraw0"] = "/sys/devices/virtual/misc/uhid/0003:054C:0DF2.0042"
    achado = aparelhos.identidade("aa:bb:cc:00:00:01")
    assert achado.cor is None and not achado.respondeu
    assert aparelhos.bytes_enviados == [], "nenhum byte pode ir ao vpad"


def test_o_edge_que_nao_responde_continua_se_chamando_edge() -> None:
    """O modelo vem do sysfs, sem byte nenhum: a falha não o apaga."""
    aparelhos = Aparelhos([("aa:bb:cc:00:00:01", "bt", "edge", "00")])
    aparelhos.perguntar = lambda _c, _p: None  # type: ignore[method-assign]
    achado = aparelhos.identidade("aa:bb:cc:00:00:01")
    assert not achado.definitiva and achado.modelo == "DualSense Edge"
    assert _mesa(aparelhos)[0]["nome"] == "DualSense Edge"


# ---------------------------------------------------------------------------
# 5 · O DAEMON publica o nome do mapa, com a grafia do mapa
# ---------------------------------------------------------------------------
class _FioNaHora:
    def __init__(self, *, target: Any, args: tuple[Any, ...] = (), **_k: Any) -> None:
        self._alvo, self._args = target, args

    def start(self) -> None:
        self._alvo(*self._args)


class _Handler:
    def __init__(self) -> None:
        self.daemon = None
        self._identidade_de_fabrica_cache: dict[str, Any] | None = None
        self._agenda_da_identidade = cp.AgendaDaPergunta()

    def __getattr__(self, nome: str) -> Any:
        from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin

        return getattr(IpcHandlersMixin, nome).__get__(self, type(self))


@pytest.mark.parametrize("de_fabrica", ["ZC", "Z2"])
def test_o_daemon_publica_o_modelo_do_mapa(
    de_fabrica: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    import threading

    monkeypatch.setattr(threading, "Thread", _FioNaHora)
    aparelhos = Aparelhos([("aa:bb:cc:00:00:01", "bt", "ds", de_fabrica)])
    monkeypatch.setattr(cp, "ler_identidade_pelo_cabo",
                        lambda uniq: aparelhos.identidade(uniq))
    handler = _Handler()
    entrada = {"uniq": "aa:bb:cc:00:00:01", "connected": True}
    handler._identidade_de_fabrica("aa:bb:cc:00:00:01", entrada)
    publicado = handler._identidade_de_fabrica("aa:bb:cc:00:00:01", entrada)
    assert publicado["modelo"] == _do_mapa(de_fabrica)[1]
    # E a mesa diz a MESMA grafia — ``Marvel's Spider-Man 2``, não ``Spider-Man 2``.
    assert _mesa(aparelhos)[0]["nome"] == publicado["modelo"]


# ---------------------------------------------------------------------------
# 6 · O EDGE NO JOGO — o dedup é pela topologia, e o 0DF2 nunca entra no VID/PID
# ---------------------------------------------------------------------------
def test_o_0df2_nunca_entra_na_lista_do_jogo() -> None:
    """O vpad é ``054C:0DF2`` em toda máscara DualSense, e a máscara troca DENTRO
    do jogo (PS + L3): um ``0x054c/0x0df2`` no IGNORE esconderia o vpad que
    nasce depois — zero controles, o pior caso desta casa. No DISABLE, o vpad
    perderia o hidraw por onde a háptica e os gatilhos do jogo chegam."""
    from hefesto_dualsense4unix.daemon import launch_env

    for mascara in ("dualsense", "xbox", "nintendo"):
        for backends in (["uhid"], ["uinput"], ["uhid", "uhid"], ["uinput", "uhid"]):
            for fisicos in (0, 1, 2, 4):
                for nativo in (False, True):
                    env = launch_env.compose_env(
                        native_mode=nativo, emulation_enabled=True, flavor=mascara,
                        backends=backends, fisicos=fisicos)
                    for nome in ("SDL_GAMECONTROLLER_IGNORE_DEVICES",
                                 "PROTON_DISABLE_HIDRAW"):
                        assert "0df2" not in env.get(nome, "").lower(), (mascara, env)


def test_o_edge_fisico_nasce_escondido_do_jogo_pela_topologia() -> None:
    """Quem tira o Edge físico do jogo é o nó fechado, e a regra separa o vpad.

    As linhas são as do ``assets/``: o Edge pelo cabo (pai USB real) e pelo
    rádio nascem ``0600 root`` sem ``uaccess``, no hidraw e nos nós de entrada;
    o vpad, que é o MESMO ``0003:054C:0DF2`` sob ``/devices/virtual/``, nasce
    aberto para a sessão.
    """
    hidraw = (RAIZ / "assets/73-hefesto-ps5-controller.rules").read_text(encoding="utf-8")
    entrada = (RAIZ / "assets/72-hefesto-touchpad-motion-uaccess.rules").read_text(
        encoding="utf-8")
    regras = [ln for ln in hidraw.splitlines() if ln and not ln.startswith("#")]
    fechado = 'MODE:="0600", OWNER:="root", GROUP:="root", TAG-="uaccess"'
    assert any('ATTRS{idProduct}=="0df2"' in ln and fechado in ln for ln in regras)
    assert any('KERNELS=="0005:054C:0DF2.*"' in ln and fechado in ln for ln in regras)
    assert any('DEVPATH=="/devices/virtual/misc/uhid/*"' in ln
               and 'KERNELS=="0003:054C:0DF2.*"' in ln and 'TAG+="uaccess"' in ln
               for ln in regras)
    linhas = [ln for ln in entrada.splitlines() if ln and not ln.startswith("#")]
    assert any("0005:054C:0DF2.*" in ln and 'TAG-="uaccess"' in ln for ln in linhas)
    assert any("0003:054C:0DF2.*" in ln and 'DEVPATH!="/devices/virtual/*"' in ln
               and 'TAG-="uaccess"' in ln for ln in linhas)


# ---------------------------------------------------------------------------
# 7 · O RESTO NÃO DEPENDE DO MODELO — medido, e o que dependia foi curado
# ---------------------------------------------------------------------------
def test_nenhuma_funcao_do_controle_depende_da_cor() -> None:
    """Número, barra, microfone, som, vibração e giroscópio não leem a cor.

    Medido em 25/09/2026: fora da tela, quem importa ``cor_do_plastico`` é só o
    daemon que PUBLICA a identidade (``daemon/ipc_handlers.py``). Um controle
    de código desconhecido joga igual a um conhecido porque nada que faz o
    controle funcionar pergunta a edição. A régua reprova quem passar a
    perguntar — o dia em que uma função depender do mapa das cores, o controle
    que ele não conhece para de funcionar.
    """
    raiz = RAIZ / "src" / "hefesto_dualsense4unix"

    def importa_a_cor(arq: pathlib.Path) -> bool:
        # PELO IMPORT, e não pela palavra: um comentário que cita o módulo não
        # é dependência, e uma régua que lesse texto reprovaria o aviso.
        for no in ast.walk(ast.parse(arq.read_text(encoding="utf-8"))):
            if isinstance(no, ast.ImportFrom) and (
                (no.module or "").endswith("cor_do_plastico")
                or any(a.name == "cor_do_plastico" for a in no.names)
            ):
                return True
            if isinstance(no, ast.Import) and any(
                a.name.endswith("cor_do_plastico") for a in no.names
            ):
                return True
        return False

    quem = sorted(
        str(arq.relative_to(raiz))
        for pasta in ("daemon", "core", "broker", "integrations", "profiles", "cli")
        for arq in (raiz / pasta).rglob("*.py")
        if importa_a_cor(arq)
    )
    assert quem == ["daemon/ipc_handlers.py"], quem


#: Um DualSense, um Edge e um receptor qualquer, como o BlueZ os entrega.
_NO_BLUEZ = {
    "/org/bluez/hci0/dev_AA_BB_CC_00_00_01": "usb:v054Cp0CE6d0100",
    "/org/bluez/hci0/dev_AA_BB_CC_00_00_02": "usb:v054Cp0DF2d0100",
    "/org/bluez/hci0/dev_AA_BB_CC_00_00_09": "usb:v046DpC52Bd0100",
}


class _BlueZ:
    """O ``busctl`` de mentira: sabe a árvore e as propriedades, e não chama nada."""

    def __call__(self, argumentos: Any) -> str | None:
        args = list(argumentos)
        if args[0] == "tree":
            return "\n".join(_NO_BLUEZ) + "\n"
        if args[0] == "get-property" and args[-1] == "Connected":
            return "b true"
        if args[0] == "get-property" and args[-1] == "Modalias":
            return f's "{_NO_BLUEZ[args[2]]}"'
        return None


def test_o_reconectar_chama_de_volta_o_edge_pelo_radio() -> None:
    """O «Reconectar controles» achava só o ``0CE6``: o Edge ficava de fora."""
    from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio

    achados = [mac for mac, _ in radio.dualsenses_do_radio(executar=_BlueZ())]
    assert achados == ["aa:bb:cc:00:00:01", "aa:bb:cc:00:00:02"], achados
