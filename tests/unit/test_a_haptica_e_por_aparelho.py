"""A-HAPTICA-E-POR-APARELHO-01 — a háptica é por aparelho (e toda feature também).

A palavra dela de 29/09, ~21h55, à pergunta da háptica de P1 a P4: *«todas as
features são um por aparelho. sempre.»* De 28/09 a 02/10 o endpoint de quatro
canais era um por LUGAR (a ``D-2909-A-HAPTICA-TEM-UM-ENDPOINT-POR-LUGAR``, que
ela revogou): o número que andava trocava a ponte e o laço de quem se sentava
ali. Agora é um por DualSense da mesa, nos dois transportes, com o nome, a
âncora e o rótulo DELE; a marca do nome é um resumo da chave do controle, e não
o rabo do endereço.

AS CINCO RÉGUAS DA SPRINT, e nenhuma mede a própria saída:

1. o endpoint segue o aparelho quando a mesa se renumera (e quando ele passa do
   cabo ao rádio);
2. o nome não tem endereço, pelas réguas de forma da casa;
3. os três nós de um controle dizem o mesmo aparelho, no que o servidor guarda;
4. o registro do lançamento é dos aparelhos: três na mesa, três blocos;
5. quem entra com o jogo aberto é dito no diário, uma vez.

O mundo é o da régua da A-HAPTICA-CHEGA (o servidor de som com memória, o
``/sys`` no ``tmp_path``, os laços de mentira), com o ``EndpointDeHaptica`` de
verdade. Os ``uniq`` são da faixa sintética.

LIMITE DECLARADO: é fiação e conta. Se o Wine aceita o rótulo renovado com o
fluxo aberto, se o registro de um aparelho ausente quebra algum jogo, e a
vibração na mão de quem troca de número com o jogo aberto são o passo 0 da
sprint, de bancada, e são dela.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
import structlog

from hefesto_dualsense4unix.core.formas_do_endereco import formas_do_endereco
from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh
from tests.unit.test_a_haptica_chega_a_quem_entra_depois import (  # noqa: F401
    _P1,
    _P2,
    _P3,
    _P4,
    _chave,
    _Controle,
    _instancias,
    _Mesa,
    _no_cabo,
    mesa,
)

RAIZ = Path(__file__).resolve().parents[2]


def _o_no(m: _Mesa, uniq: str) -> dict[str, Any]:
    (no,) = m.servidor.do_nome(eh.nome_do_endpoint(uniq))
    return no


def _identidade(m: _Mesa, uniq: str) -> tuple[str, str, str]:
    """``(nome, módulo, âncora)`` do nó do aparelho, como o servidor o guarda."""
    no = _o_no(m, uniq)
    return (str(no["nome"]), str(no["mid"]), str(no["props"]["sysfs.path"]))


# ---------------------------------------------------------------------------
# 1. O endpoint segue o aparelho
# ---------------------------------------------------------------------------


def test_renumerar_a_mesa_nao_troca_o_endpoint_a_ponte_nem_o_laco(
    mesa: _Mesa,  # noqa: F811
) -> None:
    """O P2 sai com o jogo aberto, e o P3 passa a ser o «Controle 2».

    O P1 no cabo, o P2 e o P3 no rádio, o jogo tocando nos três e os três com
    o controle na mão. Depois da renumeração, o endpoint do P3 é o MESMO nó
    (nome, módulo e âncora), a ponte dele não desce e segue lendo o endpoint
    dele, e o laço do P1 não se religa. O nó do P2 fica de pé enquanto o jogo
    toca nele: nó que some quebra o jogo que o escolheu.

    MORDIDA: em ``AltoFalanteSubsystem._aparelhos_da_mesa``, chaveie pelo
    número (``marca_do_aparelho(f"00:00:00:00:00:0{self.numero_do_assento(uniq)}")``)
    — o nó do P3 não é mais o do aparelho dele, e reprova.
    """
    p1 = _no_cabo(mesa, _P1, 1, "3-8", 28)
    p2, p3 = _Controle(_P2, "bt", "/dev/hidraw2"), _Controle(_P3, "bt", "/dev/hidraw3")
    mesa.assentos.update({_P2: 2, _P3: 3})
    mesa.servidor.jogo_em.update(eh.nome_do_endpoint(u) for u in (_P1, _P2, _P3))
    mesa.jogando.update({_P1, _P2, _P3})
    mesa.volta(p1, p2, p3)
    antes = _identidade(mesa, _P3)
    ponte_do_p3 = mesa.sub._pontes[_P3]
    assert mesa.sub._endpoint_da_ponte[_P3] == eh.nome_do_endpoint(_P3)
    ligacoes = list(mesa.lacos.ligacoes)
    # O P2 sai; o dono renumera, e o P3 vira o 2.
    mesa.assentos[_P3] = 2
    mesa.volta(p1, p3)
    mesa.volta(p1, p3)
    assert _identidade(mesa, _P3) == antes, "o endpoint do P3 mudou com o número"
    assert mesa.sub._pontes[_P3] is ponte_do_p3 and not ponte_do_p3.desceu, (
        "a ponte do P3 desceu porque o número andou"
    )
    assert mesa.sub._endpoint_da_ponte[_P3] == eh.nome_do_endpoint(_P3)
    assert mesa.lacos.ligacoes == ligacoes, "o laço do P1 se religou"
    assert mesa.servidor.quedas == [], "um nó caiu com o jogo aberto"
    assert eh.nome_do_endpoint(_P2) in mesa.servidor.nossos(), (
        "o nó do P2 sumiu debaixo do jogo"
    )


def test_o_aparelho_que_passa_do_cabo_ao_radio_fica_com_o_endpoint(
    mesa: _Mesa,  # noqa: F811
) -> None:
    """A MATRIZ, última linha: o P1 sai do cabo e volta pelo rádio com o jogo aberto.

    O endpoint é o mesmo nó; o laço do cabo dá lugar à ponte do rádio, que lê o
    mesmo endpoint.

    MORDIDA: em ``_aparelhos_da_mesa``, chaveie pelo transporte e pelo
    ``uniq`` (``marca_do_aparelho(uniq + transporte)``) — o rádio ganha outro
    nó, e reprova.
    """
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_P1))
    mesa.jogando.add(_P1)
    mesa.volta(_no_cabo(mesa, _P1, 1, "3-8", 28))
    antes = _identidade(mesa, _P1)
    assert _chave(_P1) in mesa.lacos.vivos
    mesa.volta(_Controle(_P1, "bt", "/dev/hidraw7"))
    assert _identidade(mesa, _P1) == antes
    assert _chave(_P1) not in mesa.lacos.vivos, "o laço do cabo ficou de pé no rádio"
    assert (eh.nome_do_endpoint(_P1), "haptica") in mesa.lidos
    assert mesa.servidor.quedas == []


# ---------------------------------------------------------------------------
# 2. O nome não tem endereço
# ---------------------------------------------------------------------------

#: Endereços da faixa forjada com os octetos 4 e 5 NÃO nulos: as formas do
#: endereço existem, e a régua tem o que procurar.
_COM_FORMA = ("aa:bb:cc:12:34:56", "aa:bb:cc:ab:cd:ef", "02:fe:00:5e:a3:c9")


def _o_portao_das_formas() -> ModuleType:
    """O ``scripts/check_endereco_de_radio.py`` da casa, carregado do disco."""
    caminho = RAIZ / "scripts" / "check_endereco_de_radio.py"
    spec = importlib.util.spec_from_file_location("check_endereco_de_radio", caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.mark.parametrize("uniq", _COM_FORMA)
def test_o_nome_do_endpoint_nao_carrega_pedaco_do_endereco(uniq: str) -> None:
    """Nenhuma janela de três octetos, nenhum rabo de seis hex, nada que o portão acuse.

    MORDIDA: em ``nome_do_endpoint``, devolva o nome pelo rabo
    (``MOLDE_DO_NOME.format(marca=marca_do_controle(uniq))``) — o portão de
    forma acusa o nó, e reprova.
    """
    portao = _o_portao_das_formas()
    nome = eh.nome_do_endpoint(uniq)
    assert nome and all(agulha in nome for agulha in eh.AGULHAS), nome
    baixo = nome.lower()
    pedacos = formas_do_endereco(uniq)
    assert pedacos, "a régua ficou cega: o endereço de teste não tem forma"
    assert not [p for p in pedacos if p.lower() in baixo], nome
    assert eh.marca_do_controle(uniq) not in baixo
    assert portao.acusa_no(nome) == []
    assert portao.acusa_serial(nome) == [] and portao.acusa_mac(nome) == []
    # E o mesmo aparelho tem o mesmo nome em qualquer grafia do endereço.
    assert eh.nome_do_endpoint(uniq.upper().replace(":", "")) == nome


def test_quatro_aparelhos_quatro_nomes() -> None:
    """Nome igual vira UM endpoint (patch 0186): a marca separa os quatro da mesa."""
    nomes = {eh.nome_do_endpoint(u) for u in (_P1, _P2, _P3, _P4, *_COM_FORMA)}
    assert len(nomes) == 7 and "" not in nomes


# ---------------------------------------------------------------------------
# 3. Os três nós de um controle dizem o mesmo aparelho
# ---------------------------------------------------------------------------


class ServidorQueGuarda:
    """O ``pipewire-pulse`` de mentira que guarda o que o NÓ recebeu.

    O argumento ``sink_properties=``/``source_properties=`` é lido como o real
    o lê (``_props_do_argumento`` da irmã de 28/09): entre aspas duplas vale
    inteiro, sem elas o valor morre no primeiro espaço. Quem é lido é o nó, e
    não o argv. Todo o resto responde vazio, como um comando que deu certo.
    """

    def __init__(self) -> None:
        self.nos: dict[str, dict[str, str]] = {}
        self._id = 500

    def __call__(self, argv: list[str]) -> str | None:
        from tests.unit.test_a_haptica_chega_a_quem_entra_depois import _props_do_argumento

        a = list(argv)
        if a[:2] != ["pactl", "load-module"]:
            return ""
        nome = next(
            (x.split("=", 1)[1] for x in a if x.startswith(("sink_name=", "source_name="))), ""
        )
        self.nos[nome] = next(
            (
                _props_do_argumento(x)
                for x in a
                if x.startswith(("sink_properties=", "source_properties="))
            ),
            {},
        )
        self._id += 1
        return f"{self._id}\n"


#: O dono do assento desta régua: nenhum número é a posição do controle na lista.
_MESA = tuple(f"aa:bb:cc:00:00:2{i}" for i in range(1, 5))
_ASSENTOS = dict(zip(_MESA, (3, 1, 4, 2), strict=True))


@pytest.mark.parametrize("uniq", _MESA)
def test_os_tres_nos_do_controle_dizem_o_aparelho(
    uniq: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O alto-falante, o microfone do rádio e a háptica: ``hefesto.controle=<marca>``.

    A marca é a do aparelho (a mesma nos três), e o número de agora fica no
    rótulo. Era ``hefesto.lugar=N`` de 29/09 a 02/10.

    MORDIDA: tire ``*campo_do_controle(...)`` de um dos três
    (``propriedades_do_sink``, ``propriedades_da_source`` ou
    ``propriedades_do_endpoint``) — aquele nó chega ao servidor sem o aparelho.
    """
    from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as dba

    servidor = ServidorQueGuarda()
    monkeypatch.setattr(dba, "_NUMERADOR_DE_ASSENTO", _ASSENTOS.get)
    monkeypatch.setattr(dba, "_rodar", servidor)
    monkeypatch.setattr(af, "_o_servidor_atende", lambda *_a, **_k: True)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(canal, "_DE_PE", {})

    assert af.SinkVirtualPipeWire(uniq=uniq, runner=servidor).iniciar()
    canal.abrir(uniq, dba.descricao_do_microfone(uniq))
    endpoint = eh.EndpointDeHaptica(
        uniq=uniq, ancora=eh.Ancora(syspath="/d/1", declarado="/d/1/i:1.0"), runner=servidor
    )
    assert endpoint.iniciar()

    marca = eh.marca_do_aparelho(uniq)
    nos = {
        "alto-falante": af.nome_do_sink(uniq),
        "microfone": canal.nome_do_canal(uniq),
        "háptica": eh.nome_do_endpoint(uniq),
    }
    for papel, nome in nos.items():
        assert nome in servidor.nos, f"o nó do {papel} não foi publicado"
        props = servidor.nos[nome]
        assert props.get("hefesto.controle") == marca, (
            f"o nó do {papel} não diz o aparelho {marca}: {props}"
        )
        assert "hefesto.lugar" not in props, f"o nó do {papel} ainda diz o lugar"
        assert f" {_ASSENTOS[uniq]}" in props["device.description"], props
    # O rótulo continua o dele: a propriedade nova não comeu o que vinha antes.
    assert servidor.nos[nos["alto-falante"]]["device.description"] == (
        af.descricao_do_alto_falante(uniq)
    )


def test_o_microfone_do_radio_pelo_caminho_de_volta_tambem_diz_o_aparelho(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """O canal recusa e a ponte publica o nó de sempre: ele também diz o aparelho.

    MORDIDA: tire o ``controle=self.no.uniq`` do ``SourceVirtualPipeWire`` de
    reserva em ``PonteMicBluetooth.iniciar`` — o nó chega sem o aparelho.
    """
    from hefesto_dualsense4unix.integrations import canal_do_microfone as canal
    from hefesto_dualsense4unix.integrations import dualsense_bt_audio as dba

    servidor = ServidorQueGuarda()
    monkeypatch.setattr(dba, "_NUMERADOR_DE_ASSENTO", _ASSENTOS.get)
    monkeypatch.setattr(dba, "_rodar", servidor)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    monkeypatch.setattr(canal, "abrir", lambda *_a, **_k: None)

    class _SourceQuePublicaEPara(dba.SourceVirtualPipeWire):
        """Publica o nó de verdade no servidor de mentira e recusa depois: a
        régua lê o NÓ, e não quer uma thread de áudio girando na suíte."""

        def iniciar(self) -> bool:
            super().iniciar()
            return False

    monkeypatch.setattr(dba, "SourceVirtualPipeWire", _SourceQuePublicaEPara)
    leitura, escrita = os.pipe()
    os.close(escrita)
    uniq = _MESA[2]
    no = dba.NoDualSenseBT(caminho="/dev/hidraw9", uniq=uniq, produto=0x0CE6)
    ponte = dba.PonteMicBluetooth(no, opener=lambda _c: leitura, decodificador=object())
    assert ponte.iniciar() is False
    nome = ponte._nome_source
    assert nome in servidor.nos, "o nó de reserva do microfone não foi publicado"
    assert servidor.nos[nome].get("hefesto.controle") == eh.marca_do_aparelho(uniq), (
        servidor.nos[nome]
    )


# ---------------------------------------------------------------------------
# 4. O registro do lançamento é dos aparelhos
# ---------------------------------------------------------------------------


def test_tres_na_mesa_tres_blocos_no_registro(mesa: _Mesa) -> None:  # noqa: F811
    """O curador grava um bloco por endpoint vivo: três controles, três blocos.

    O P1 no cabo e o P3 e o P4 no rádio. Cada bloco é o da âncora do endpoint
    do aparelho (o cabo com endpoint sai da lista pela placa servida).

    MORDIDA: em ``AltoFalanteSubsystem._aparelhos_de_pe``, devolva os quatro
    lugares de volta (complete ``de_pe`` até quatro com marcas de
    ``f"00:00:00:00:00:0{n}"``) — o registro ganha um quarto bloco, e reprova.
    """
    mesa.volta(
        _no_cabo(mesa, _P1, 1, "3-8", 28),
        _Controle(_P3, "bt", "/dev/hidraw3"),
        _Controle(_P4, "bt", "/dev/hidraw4"),
    )
    assert mesa.servidor.nossos() == sorted(eh.nome_do_endpoint(u) for u in (_P1, _P3, _P4))
    instancias = _instancias(mesa.registro())
    assert len(instancias) == 3, instancias
    ancoras = {_o_no(mesa, u)["props"]["sysfs.path"].split("/")[-2] for u in (_P1, _P3, _P4)}
    devnums = {
        int((mesa.sysfs / "bus" / "usb" / "devices" / a / "devnum").read_text()) for a in ancoras
    }
    assert instancias == {f"HEFESTOKS&003&{d:03d}&0" for d in devnums}


# ---------------------------------------------------------------------------
# 5. Quem entra com o jogo aberto é dito
# ---------------------------------------------------------------------------


def _sem_registro(registros: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [r for r in registros if r["event"] == "haptica_aparelho_sem_registro_no_jogo"]


def test_quem_chega_com_o_jogo_aberto_e_dito_uma_vez(mesa: _Mesa) -> None:  # noqa: F811
    """O P4 chega com a partida aberta: o endpoint dele nasce, e o diário diz por quê.

    É o preço que ela aceitou na pergunta [27]: o registro se grava no
    lançamento, e o jogo não conhece o endpoint que nasce depois. Uma linha por
    aparelho e partida; e sem partida, nenhuma.

    MORDIDA: tire a chamada a ``_avisar_quem_o_jogo_nao_conhece`` de
    ``_casar_as_pontes`` — o P4 fica sem háptica sem rastro, e reprova.
    """
    dois = [_Controle(_P1, "bt", "/dev/hidraw1"), _Controle(_P2, "bt", "/dev/hidraw2")]
    with structlog.testing.capture_logs() as antes_do_jogo:
        mesa.volta(*dois)
    assert _sem_registro(antes_do_jogo) == [], "sem partida, ninguém ficou sem registro"
    mesa.servidor.jogo_em.update(eh.nome_do_endpoint(u) for u in (_P1, _P2))
    # A partida da volta: o jogo (o cliente 42 do servidor) toca nos endpoints.
    mesa.sub._donos_da_volta = frozenset({"42"})
    quatro = _Controle(_P4, "bt", "/dev/hidraw4")
    with structlog.testing.capture_logs() as registros:
        mesa.volta(*dois, quatro)
        mesa.volta(*dois, quatro)
    linhas = _sem_registro(registros)
    assert len(linhas) == 1, linhas
    assert linhas[0]["controle"] == eh.marca_do_aparelho(_P4)
    assert eh.nome_do_endpoint(_P4) in mesa.servidor.nossos()
    # A partida fecha: a mesma chegada, numa partida nova, é dita de novo.
    mesa.sub._donos_da_volta = frozenset()
    mesa.volta(*dois)
    mesa.servidor.jogo_em.clear()
    mesa.volta(*dois)
    mesa.sub._donos_da_volta = frozenset({"43"})
    with structlog.testing.capture_logs() as de_novo:
        mesa.volta(*dois, quatro)
    assert len(_sem_registro(de_novo)) == 1, de_novo
