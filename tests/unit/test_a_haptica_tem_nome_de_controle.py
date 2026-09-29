"""A-HAPTICA-TEM-NOME-DE-CONTROLE-01 — a saída de háptica diz o controle, não o endereço.

A conferência da A-FORJA-VALIDA-O-SOM-01 achou: o endpoint de háptica aparecia
na lista de saídas de som do sistema como «DualSense <hex6> (háptica)», com o
rabo do endereço do controle no rótulo — e, com o P3 e o P4 no BT, a célula
``mapa-audio.saida_dedicada.payload_do_degrau-cabo`` da bancada contava quatro
placas DualSense onde pede duas.

A DECISÃO, por delegação dela e pelo padrão dela (a forma A de 23/09 vale para
tudo que o Hefesto publica; nada de endereço na tela), está DIGITADA aqui de
propósito: «Háptica do Controle N (DualSense Wireless Controller)». A régua lê
a decisão, não o dono: mude o dono sem mudar a decisão e ela reprova.

O QUE CADUCOU EM 28/09/2026 (A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01): o
endpoint era um por CONTROLE no rádio, e o N era o assento daquele controle,
republicado quando o assento andava — com as guardas do jogo aberto, da ponte
em modo háptica, do servidor mudo e do rótulo ilegível do nó herdado. O
endpoint passou a ser um por LUGAR, de pé desde o primeiro DualSense, e o N é
o do lugar, fixo: quem anda é o controle, e o que troca é a ponte ou o laço,
nunca o endpoint. Aquelas réguas mediam a renovação, que saiu inteira; as
mordidas 3, 4, 5, 8, 9, 10, 11 e 12 abaixo caducaram com ela. No lugar delas,
a seção 4 mede o que a renovação protegia: nenhum nó renasce quando o assento
anda, com ou sem jogo aberto.

O QUE O JOGO LÊ NÃO PODE MUDAR, e a medição está na seção 3: os casamentos do
GE-Proton11-7 sobre o ``drv_id`` do endpoint (a descrição), transcritos do
fonte com os 182 patches ``proton-ds5-haptic`` aplicados, dão o mesmo
resultado para o rótulo velho e para o novo. A identidade (nome do nó, VID,
PID, âncora) é a mesma — e é o USB ``054c:0ce6`` dela que faz o nome que o jogo
lê ser o do produto, com qualquer rótulo.

Nada aqui toca o servidor de som de ninguém: o ``pactl`` é um dublê com estado,
MAIS estrito que o ``pactl`` de mentira da bancada de tela (aquele aceita tudo
calado); os ``uniq`` são da faixa sintética ``aa:bb:cc``.

AS MORDIDAS, uma por afirmação, e cada uma foi vista reprovar:

1. devolva ``device.description='DualSense {marca} (háptica)'`` em
   ``propriedades_do_endpoint`` → o endereço volta ao rótulo e a bancada conta
   quatro;
2. tire ``*campos_do_nome()`` de ``propriedades_do_endpoint`` → o ``drv_id``
   do monitor fica com 64 caracteres, sem nome de reserva;
3. (28/09) devolva a republicação: derrube o endpoint do lugar cujo ocupante
   mudou, e a volta seguinte o recarrega → o assento que anda vira hotplug de
   endpoint Sony debaixo do jogo;
6. devolva o passo da bancada que só nomeia «Alto-falante do Controle» → a
   conta volta a dar quatro;
7. tire o ``device.product.id`` de ``propriedades_do_endpoint`` → o gravador do
   device KS (``audio_ks_dualsense.endpoints_de_mentira``) deixa de achar o
   endpoint, com o rótulo, o nome e a âncora todos certos.
"""

from __future__ import annotations

import re
import shlex
import sys
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

import pytest

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod
from hefesto_dualsense4unix.integrations import alto_falante_bt as som
from hefesto_dualsense4unix.integrations import audio_ks_dualsense as ks
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as mic
from hefesto_dualsense4unix.integrations import endpoint_de_haptica as eh

RAIZ = Path(__file__).resolve().parents[2]

#: A DECISÃO — digitada, não lida do dono.
_SONY = " (DualSense Wireless Controller)"
_HAPTICA = "Háptica do Controle"

#: O teto do Wine (``MAX_DEVICE_NAME_LEN``, ``winepulse.drv/pulse.c``): acima
#: dele o ``get_device_name`` troca a frase inteira pelo ``device.product.name``.
_TETO_DO_WINE = 62
_MONITOR_DE = "Monitor of "

#: A mesa de quatro: P1 e P2 no USB, P3 e P4 no BT. Faixa sintética; o rabo tem
#: LETRAS de propósito, para o «nenhum hex do endereço» não passar por sorte.
_P1, _P2, _P3, _P4 = (f"aa:bb:cc:5e:a3:c{n}" for n in (1, 2, 3, 4))
_ASSENTO = {_P1: 1, _P2: 2, _P3: 3, _P4: 4}

#: A placa de som de um DualSense no USB, como o servidor a descreve — medido
#: em 21/09/2026 (A-FORJA-VALIDA-O-SOM-01, §1.2). As duas placas têm o mesmo
#: nome, e é por isso que o Hefesto publica os nós com número.
_PLACA_DESCRICAO = "DualSense wireless controller (PS5) Controller speaker and haptic motors"
_PLACAS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.HiFi__Speaker__sink",
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_Controller-00.2.HiFi__Speaker__sink",
)

#: A célula da bancada que é a régua desta sprint.
_CELULA = "mapa-audio.saida_dedicada.payload_do_degrau-cabo"


def _ancora(i: int) -> eh.Ancora:
    return eh.Ancora(
        syspath=f"/devices/pci0000:00/usb3/3-{i}",
        declarado=f"/devices/pci0000:00/usb3/3-{i}/3-{i}:1.0",
    )


_ANCORAS = [_ancora(i) for i in range(4)]

#: O numerador de mentira: ``uniq`` → o número do jogador (``None`` = não sei).
_Assentos = dict[str, int | None]


@pytest.fixture
def assentos() -> Iterator[_Assentos]:
    """O numerador de assento, respondendo pelo dicionário — e o de antes volta."""
    tabela: dict[str, int | None] = dict(_ASSENTO)
    anterior = mic.registrar_numerador_de_assento(lambda u: tabela.get(u))
    try:
        yield tabela
    finally:
        mic.registrar_numerador_de_assento(anterior)


# ---------------------------------------------------------------------------
# O servidor de som de mentira
# ---------------------------------------------------------------------------


def _como_o_servidor_le(argumento: str) -> dict[str, str]:
    """O ``sink_properties=`` como o ``pipewire-pulse`` o lê.

    COM as aspas duplas de fora, o miolo se parte respeitando as simples. SEM
    elas, o servidor corta no primeiro espaço e só a primeira propriedade chega
    — o defeito de 06/09/2026, que a régua que lia o argv cru deu verde.
    """
    valor = argumento.split("=", 1)[1]
    if len(valor) >= 2 and valor.startswith('"') and valor.endswith('"'):
        miolo = valor[1:-1]
    else:
        miolo = valor.split(" ", 1)[0]
    campos: dict[str, str] = {}
    for pedaco in shlex.split(miolo):
        nome, igual, resto = pedaco.partition("=")
        if igual:
            campos[nome] = resto
    return campos


class _Servidor:
    """Um ``pipewire-pulse`` de mentira, com memória — e nunca mais frouxo que o real.

    O ``pactl`` de mentira da bancada de tela responde ``rc=0`` calado a tudo
    que não é ``list sinks short``. Este guarda os módulos que carregou, com as
    propriedades lidas como o servidor as lê, e devolve cada nó em
    ``list sinks`` com a ``Description`` que a lista de som da pessoa mostra.
    Nome acima de 127 caracteres é recusado, como no real.
    """

    def __init__(self) -> None:
        #: índice do sink -> {"nome", "props", "canais", "mid"}
        self.sinks: dict[str, dict[str, Any]] = {}
        #: module_id -> o argumento, como o ``pactl`` o repassa (argv juntado)
        self.argumentos: dict[str, str] = {}
        self.cargas: list[str] = []
        self.quedas: list[str] = []
        #: Quantos ``load-module`` seguidos o servidor recusa.
        self.recusar_cargas = 0
        #: nomes de sink com um stream de JOGO tocando (sink-input)
        self.jogo_em: set[str] = set()
        #: O servidor que não responde sobre os streams (prazo estourado): o
        #: ``pactl`` sai com erro, e quem pergunta recebe ``None`` — «não sei».
        self.mudo_nos_streams = False
        self._proximo = 500

    # -- o estado de partida -------------------------------------------------

    def _novo_indice(self) -> str:
        self._proximo += 1
        return str(self._proximo)

    def sink_de_fora(self, nome: str, descricao: str, canais: int) -> None:
        """Um sink que não é módulo desta volta: a placa do USB, o nó do som."""
        self.sinks[self._novo_indice()] = {
            "nome": nome,
            "props": {"device.description": descricao},
            "canais": canais,
            "mid": None,
        }

    def modulo_herdado(self, argv: list[str]) -> str:
        """Um endpoint que um processo ANTERIOR do daemon deixou de pé."""
        resposta = self(["pactl", "load-module", *argv])
        assert resposta, "o servidor de mentira recusou o módulo herdado"
        self.cargas.clear()
        return resposta.strip()

    # -- as leituras da régua -----------------------------------------------

    def do_nome(self, nome: str) -> list[dict[str, Any]]:
        return [s for s in self.sinks.values() if s["nome"] == nome]

    def descricao(self, s: dict[str, Any]) -> str:
        props = s["props"]
        return str(props.get("device.description") or props.get("node.nick") or s["nome"])

    def saidas(self) -> list[str]:
        """O que a lista de saídas das configurações de Som mostra: as descrições."""
        return [self.descricao(s) for s in self.sinks.values()]

    # -- o pactl --------------------------------------------------------------

    def __call__(self, argv: list[str]) -> str | None:
        if argv[:2] == ["pactl", "load-module"]:
            return self._carregar(argv)
        if argv[:2] == ["pactl", "unload-module"]:
            mid = argv[2]
            if mid not in self.argumentos:
                return None
            del self.argumentos[mid]
            self.sinks = {i: s for i, s in self.sinks.items() if s["mid"] != mid}
            self.quedas.append(mid)
            return ""
        if argv[:4] == ["pactl", "list", "short", "modules"]:
            return "\n".join(
                f"{mid}\tmodule-null-sink\t{arg}\t" for mid, arg in self.argumentos.items()
            )
        if argv[:4] == ["pactl", "list", "short", "sinks"]:
            return "\n".join(
                f"{i}\t{s['nome']}\tPipeWire\tfloat32le {s['canais']}ch 48000Hz\tSUSPENDED"
                for i, s in self.sinks.items()
            )
        if argv[:4] == ["pactl", "list", "short", "sink-inputs"]:
            if self.mudo_nos_streams:
                return None
            return "\n".join(
                f"9{i}\t{i}\t12\tprotocol-native.c\tfloat32le 4ch 48000Hz"
                for i, s in self.sinks.items()
                if s["nome"] in self.jogo_em
            )
        if argv[:3] == ["pactl", "list", "sinks"]:
            blocos = []
            for i, s in self.sinks.items():
                props = "\n".join(f'\t\t{k} = "{v}"' for k, v in s["props"].items())
                blocos.append(
                    f"Sink #{i}\n\tState: SUSPENDED\n\tName: {s['nome']}\n"
                    f"\tDescription: {self.descricao(s)}\n\tDriver: PipeWire\n"
                    f"\tSample Specification: float32le {s['canais']}ch 48000Hz\n"
                    f"\tProperties:\n{props}"
                )
            return "\n\n".join(blocos)
        # O resto (set-sink-volume…) o real aceita calado, como o de mentira.
        return ""

    def _carregar(self, argv: list[str]) -> str | None:
        if argv[2:3] != ["module-null-sink"]:
            return None
        if self.recusar_cargas > 0:
            self.recusar_cargas -= 1
            return None
        nome = next((a.split("=", 1)[1] for a in argv if a.startswith("sink_name=")), "")
        if not nome or len(nome) > eh.MAX_NOME:
            return None
        canais = int(next((a.split("=", 1)[1] for a in argv if a.startswith("channels=")), "2"))
        props = next(
            (_como_o_servidor_le(a) for a in argv if a.startswith("sink_properties=")), {}
        )
        mid = self._novo_indice()
        self.argumentos[mid] = " ".join(argv[3:])
        self.sinks[self._novo_indice()] = {
            "nome": nome, "props": props, "canais": canais, "mid": mid,
        }
        self.cargas.append(nome)
        return f"{mid}\n"


# ---------------------------------------------------------------------------
# 1. O RÓTULO — a forma A, com o número do jogador, e sem endereço
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("numero", [1, 2, 3, 4, None])
def test_o_rotulo_e_a_forma_a_com_o_numero_do_jogador(numero: int | None) -> None:
    """O número é o do LUGAR, e sem número não se inventa número."""
    sufixo = "" if numero is None else f" {numero}"
    assert eh.rotulo_da_haptica(numero) == f"{_HAPTICA}{sufixo}{_SONY}"


def _campos_de_gente(props: dict[str, str]) -> dict[str, str]:
    """Os campos que alguém LÊ numa lista de som — onde o endereço não entra."""
    return {k: v for k, v in props.items() if k in (
        "device.description", "node.nick", "device.product.name", "device.vendor.name")}


@pytest.mark.parametrize("lugar", [1, 2, 3, 4])
def test_nenhum_hex_do_endereco_chega_ao_rotulo(lugar: int) -> None:
    """Nem os seis do rabo, nem par nenhum de endereço, em campo que alguém lê.

    MORDIDA 1: devolva ``'DualSense {marca} (háptica)'`` e o rabo volta.
    """
    props = _como_o_servidor_le(eh.propriedades_do_endpoint(lugar, _ANCORAS[0]))
    for uniq in (_P1, _P2, _P3, _P4):
        pares = [p for p in uniq.lower().split(":") if re.search(r"[a-f]", p)]
        for chave, valor in _campos_de_gente(props).items():
            baixa = valor.lower()
            assert eh.marca_do_controle(uniq) not in baixa, f"{chave}={valor!r}"
            assert not re.search(r"\b[0-9a-f]{6}\b", baixa), f"{chave}={valor!r}"
            for par in pares:
                assert not re.search(rf"\b{par}\b", baixa), f"{chave}={valor!r} leva {par!r}"
    assert props["device.description"] == f"{_HAPTICA} {lugar}{_SONY}"


def test_o_rotulo_cabe_no_teto_e_o_monitor_tem_reserva() -> None:
    """O rótulo cabe nos 62 do Wine; o monitor passa, e o ``product.name`` o salva.

    O ``pipewire-pulse`` chama o monitor de «Monitor of <descrição>»: com a
    forma A isso dá 64. Acima do teto o ``get_device_name`` monta o ``drv_id``
    a partir do ``device.product.name`` — sem ele, o comprido fica inteiro ali.
    O nome que o JOGO lê não passa por aqui: é o do produto, pelo USB
    ``054c:0ce6`` (:func:`test_a_identidade_do_no_fica_intacta`).

    MORDIDA 2: tire ``*campos_do_nome()`` de ``propriedades_do_endpoint``.
    """
    for lugar in eh.LUGARES:
        rotulo = eh.rotulo_da_haptica(lugar)
        assert len(rotulo) <= _TETO_DO_WINE, (len(rotulo), rotulo)
        assert len(_MONITOR_DE + rotulo) > _TETO_DO_WINE
        props = _como_o_servidor_le(eh.propriedades_do_endpoint(lugar, _ANCORAS[0]))
        reserva = props.get("device.product.name", "")
        assert reserva, "o monitor do endpoint fica sem nome de reserva no Wine"
        assert len(_MONITOR_DE + reserva) <= _TETO_DO_WINE


def test_a_identidade_do_no_fica_intacta() -> None:
    """A identidade que o jogo lê — e o NOME é o do lugar desde 28/09/2026.

    O id do endpoint no Wine sai do nome do sink, e o ``ContainerId`` que a RE
    Engine casa com o device KS sai do ``sysfs.path``. Nenhum dos dois muda por
    causa de um rótulo. E o USB ``054c:0ce6`` é o que faz o
    ``find_product_name_override`` do ``mmdevapi`` dar ao endpoint o nome do
    produto — o rótulo nunca chega ao nome que o jogo lê.
    """
    ancora = _ANCORAS[2]
    props = _como_o_servidor_le(eh.propriedades_do_endpoint(3, ancora))
    assert props["device.bus"] == "usb"
    assert props["device.vendor.id"] == "054c"
    assert props["device.product.id"] == "0ce6"
    assert props["sysfs.path"] == ancora.declarado
    assert props["device.vendor.name"] == "Sony Interactive Entertainment"
    assert props["priority.session"] == "0", "o endpoint não pode virar a saída padrão"
    assert eh.nome_do_endpoint(3) == eh.MOLDE_DO_NOME.format(marca=eh.marca_do_lugar(3))


def test_o_no_publicado_diz_o_lugar() -> None:
    """O que a lista de som MOSTRA, lido do servidor depois do ``load-module``."""
    servidor = _Servidor()
    no = eh.EndpointDeHaptica(lugar=4, ancora=_ANCORAS[1], runner=servidor)
    assert no.iniciar() is True
    (publicado,) = servidor.do_nome(eh.nome_do_endpoint(4))
    assert servidor.descricao(publicado) == f"{_HAPTICA} 4{_SONY}"
    assert publicado["props"]["sysfs.path"] == _ANCORAS[1].declarado
    assert publicado["canais"] == 4


# ---------------------------------------------------------------------------
# 2. O NÓ ADOTADO — a posse se lê do argumento do módulo
# ---------------------------------------------------------------------------


def test_a_posse_do_no_adotado_se_le_do_argumento_do_modulo() -> None:
    """A linha real do ``pactl list short modules``, com espaço e acento no rótulo.

    O rótulo do nó adotado deixou de ser lido em 28/09/2026: ele é o do lugar,
    e não envelhece. A posse (nome e âncora) segue saindo desta linha.
    """
    nome = eh.nome_do_endpoint(3)
    linha = (
        f"536870913\tmodule-null-sink\tsink_name={nome} format=float32le rate=48000 "
        "channels=4 channel_map=front-left,front-right,rear-left,rear-right "
        'sink_properties="device.bus=usb device.vendor.id=054c device.product.id=0ce6 '
        f"sysfs.path={_ANCORAS[0].declarado} device.vendor.name='Sony Interactive "
        "Entertainment' device.description='Háptica do Controle 3 (DualSense Wireless "
        "Controller)' priority.session=0 device.icon_name=audio-speakers\"\t"
    )
    assert eh.endpoints_de_pe(lambda _a: linha) == {
        nome: [("536870913", _ANCORAS[0].declarado)]
    }


# ---------------------------------------------------------------------------
# 3. O QUE O JOGO CASA NÃO MUDOU — a medição, transcrita do GE
# ---------------------------------------------------------------------------
#
# GE-Proton11-7 (`proton-hefesto/fonte`, commit `c191f35`), com os 182 patches de
# `patches/proton-ds5-haptic/` aplicados em ordem sobre o `wine` dele — 179
# entram limpos; 0022, 0109 e 0150 falham em trechos de formato e de include,
# longe do nome. A descrição do nó chega ao `mmdevapi` como o `drv_id`
# (`get_device_name` → `MMDevice.drv_id`). O `DEVPKEY_Device_FriendlyName` que
# o jogo lê NÃO sai dela: o nó declara USB `054c:0ce6`, e o
# `find_product_name_override` troca o nome por «Speakers (DualSense Wireless
# Controller)», com o rótulo velho e com o novo. Os predicados que LEEM o
# `drv_id`, de `dlls/mmdevapi/devenum.c`, transcritos um a um:


def _ge_dualsense(n: str) -> bool:  # is_dualsense_endpoint_name (e o 0187)
    return any(s in n for s in ("DualSense", "DualShock", "Wireless Controller"))


def _ge_mono(n: str) -> bool:  # is_dualsense_mono_endpoint_name
    if "DualShock" in n and ("Internal Mono Speaker" in n or "Analog Stereo" in n):
        return True
    return ("DualSense" in n or "Wireless Controller" in n) and "Internal Mono Speaker" in n


def _ge_direct(n: str) -> bool:  # is_sony_direct_render_name
    return _ge_dualsense(n) and "Direct Wireless Controller" in n


def _ge_audioendpoint(n: str) -> bool:  # is_dualsense_audioendpoint_name
    return _ge_mono(n) or any(s in n for s in (
        "Wireless Controller Speaker", "DualShock 4 Wireless Controller Speaker",
        "DualSense Wireless Controller Speaker", "DualSense Edge Wireless Controller Speaker"))


def _ge_sony_persistente(n: str) -> bool:  # is_persistent_sony_audioendpoint_name
    return _ge_audioendpoint(n) or "DualSense" in n or "DualShock" in n


_CASAMENTOS_DO_GE: tuple[Callable[[str], bool], ...] = (
    _ge_dualsense, _ge_mono, _ge_direct, _ge_audioendpoint, _ge_sony_persistente)


def _o_que_o_ge_ve(nome_amigavel: str) -> list[tuple[str, tuple[bool, ...]]]:
    """Os cinco resultados sobre o ``drv_id`` cru — e, por folga, sobre «Speakers (…)»."""
    formas = (nome_amigavel, f"Speakers ({nome_amigavel})")
    return [(f, tuple(p(f) for p in _CASAMENTOS_DO_GE)) for f in formas]


@pytest.mark.parametrize("numero", [1, 2, 3, 4, None])
def test_os_casamentos_do_ge_dao_o_mesmo_resultado(numero: int | None) -> None:
    """O rótulo novo cai em cada casamento do GE exatamente como o velho caía.

    Se uma forma futura do rótulo ganhar «Speaker» (e virar o alto-falante mono
    que o GE esconde e remove) ou perder «DualSense» (e sair do 0187, que
    preserva o endpoint ativo de cada controle), esta régua reprova antes de a
    háptica que já vibra parar.
    """
    velho = f"DualSense {eh.marca_do_controle(_P3)} (háptica)"
    novo = eh.rotulo_da_haptica(numero)
    assert [r for _f, r in _o_que_o_ge_ve(novo)] == [r for _f, r in _o_que_o_ge_ve(velho)]
    # e o monitor: com o nome de reserva, que é o que o Wine usa acima do teto
    props = _como_o_servidor_le(eh.propriedades_do_endpoint(3, _ANCORAS[0]))
    reserva = props["device.product.name"]
    for monitor in (_MONITOR_DE + reserva, reserva):
        assert _ge_dualsense(monitor) is True
        assert _ge_audioendpoint(f"Microphone ({monitor})") is False


def test_a_transcricao_do_ge_morde() -> None:
    """Os predicados transcritos distinguem o que o GE distingue — senão mediriam nada."""
    assert _ge_audioendpoint("DualSense Wireless Controller Speaker") is True
    assert _ge_mono("DualSense wireless controller (PS5) Internal Mono Speaker") is True
    assert _ge_direct("Direct Wireless Controller") is True
    assert _ge_dualsense("Alto-falante do Controle 1") is False
    assert _ge_sony_persistente("Speakers (Built-in Audio)") is False


# ---------------------------------------------------------------------------
# 4. A VOLTA DO RÁDIO — o rótulo acompanha o assento, e só sem jogo aberto
# ---------------------------------------------------------------------------


class _PonteDeMentira:
    criadas: ClassVar[list[Any]] = []

    def __init__(self, **kw: Any) -> None:
        self.uniq = kw["uniq"]
        self.desceu = False
        self.motivo = ""
        _PonteDeMentira.criadas.append(self)

    def subir(self) -> bool:
        return True

    def descer(self, **_: Any) -> bool:
        self.desceu = True
        return True

    def esta_de_pe(self) -> bool:
        return not self.desceu


@dataclass
class _Controle:
    uniq: str
    transporte: str
    caminho: str = "/dev/hidraw9"


@dataclass
class _Mesa:
    sub: Any
    servidor: _Servidor

    def volta(self) -> None:
        """Uma volta do daemon com a mesa de quatro: P1 e P2 no USB, P3 e P4 no BT."""
        self.sub._casar_as_pontes([
            _Controle(_P1, "usb"), _Controle(_P2, "usb"),
            _Controle(_P3, "bt"), _Controle(_P4, "bt"),
        ])

    def rotulo(self, lugar: int) -> str:
        (no,) = self.servidor.do_nome(eh.nome_do_endpoint(lugar))
        return self.servidor.descricao(no)

    def ancora(self, lugar: int) -> str:
        (no,) = self.servidor.do_nome(eh.nome_do_endpoint(lugar))
        return str(no["props"]["sysfs.path"])


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, assentos: _Assentos) -> _Mesa:
    from hefesto_dualsense4unix.integrations import hidraw_broker_client as broker

    _PonteDeMentira.criadas = []
    servidor = _Servidor()
    for placa in _PLACAS:
        servidor.sink_de_fora(placa, _PLACA_DESCRICAO, canais=4)
    for uniq in (_P1, _P2, _P3, _P4):
        servidor.sink_de_fora(som.nome_do_sink(uniq), som.descricao_do_alto_falante(uniq), canais=2)
    monkeypatch.setattr(eh, "rodar_pactl", servidor)
    monkeypatch.setattr(som, "rodar_pactl", servidor)
    monkeypatch.setattr(eh, "ancoras", lambda *a, **k: list(_ANCORAS))
    monkeypatch.setattr(
        som, "fonte_do_monitor_do_no", lambda no, **kw: ((lambda _n: b""), f"gravador:{no}", "")
    )
    monkeypatch.setattr(som, "PonteDeSomPorRadio", _PonteDeMentira)
    monkeypatch.setattr(broker, "abrir_hidraw", lambda no, **_: type("N", (), {"fd": 7})())
    # Nenhum jogo LENDO controle — a volta não sobe ponte de háptica sozinha.
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_quem_o_jogo_le", lambda self, c: set())

    class _Ger:
        def reconciliar(self, *_a: Any, **_k: Any) -> None:
            return None

        def dormir(self, _s: float) -> bool:
            return False

        def parar(self) -> None:
            return None

    # O laço do cabo não é desta régua: a placa não se procura aqui.
    monkeypatch.setattr(som, "sink_do_controle", lambda *_a, **_k: "")
    # O número do jogador vem do DONO (o numerador de mentira), como no produto.
    monkeypatch.setattr(
        mod.AltoFalanteSubsystem, "numero_do_assento", lambda self, u: assentos.get(u)
    )
    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=list)
    return _Mesa(sub=sub, servidor=servidor)


def _o_que_o_ks_le(servidor: _Servidor) -> list[tuple[int, str]]:
    """Os endpoints que o gravador do device KS acha — pelo leitor DELE, não por uma cópia.

    ``audio_ks_dualsense.endpoints_de_mentira`` é quem acha cada endpoint para
    gravar no prefixo o device KS que a RE Engine casa pelo ``ContainerId``. Ele
    lê o VID, o PID e o ``sysfs.path`` do nó, e nunca a descrição.
    """
    return sorted(ks.endpoints_de_mentira(servidor))


def test_os_quatro_lugares_ganham_a_haptica_no_cabo_e_no_radio(mesa: _Mesa) -> None:
    """FATO QUE CAIU (28/09/2026): «no USB a vibração viaja pela placa; o endpoint é só do BT».

    O endpoint é do LUGAR, e os quatro sobem com a mesa, cabo e rádio
    misturados; o cabo passa pelo lugar por um laço (``haptica_do_cabo``).
    """
    mesa.volta()
    for lugar in eh.LUGARES:
        assert mesa.rotulo(lugar) == f"{_HAPTICA} {lugar}{_SONY}"
    assert len(_o_que_o_ks_le(mesa.servidor)) == 4, "o gravador do device KS não achou os quatro"


def test_o_assento_que_anda_nao_mexe_no_endpoint(mesa: _Mesa, assentos: _Assentos) -> None:
    """P3 e P4 trocam de lugar: nenhum nó renasce, e o que o jogo lê fica igual.

    É o que a renovação do rótulo protegia com quatro guardas (o jogo aberto,
    a ponte em modo háptica, o servidor mudo, o rótulo ilegível): republicar
    é hotplug de endpoint Sony debaixo do jogo. Com o endpoint do lugar, o
    assento que anda troca a ponte, e nunca o nó.

    MORDIDA 3: derrube o endpoint do lugar cujo ocupante mudou.
    MORDIDA 7: tire o ``device.product.id`` do nó.
    """
    mesa.volta()
    antes = {n: (mesa.ancora(n), mesa.rotulo(n)) for n in eh.LUGARES}
    o_ks_antes = _o_que_o_ks_le(mesa.servidor)
    cargas = list(mesa.servidor.cargas)
    assentos[_P3], assentos[_P4] = 4, 3
    mesa.volta()
    assentos[_P3] = None  # o numerador que pisca também não mexe em nada
    mesa.volta()
    assert {n: (mesa.ancora(n), mesa.rotulo(n)) for n in eh.LUGARES} == antes
    assert mesa.servidor.quedas == [], "um nó renasceu porque o assento andou"
    assert mesa.servidor.cargas == cargas
    assert _o_que_o_ks_le(mesa.servidor) == o_ks_antes


def test_o_no_herdado_com_o_nome_de_antes_cai_uma_vez(mesa: _Mesa) -> None:
    """Depois do install, o endpoint por controle que o daemon anterior deixou sai.

    O nome pelo rabo do endereço não é de lugar nenhum, e a varredura de
    órfãos o derruba na primeira volta; os quatro lugares sobem no lugar
    dele. Uma volta a mais não recarrega nada.
    """
    for uniq, ancora in ((_P3, _ANCORAS[2]), (_P4, _ANCORAS[3])):
        mesa.servidor.modulo_herdado([
            "module-null-sink",
            f"sink_name={eh.MOLDE_DO_NOME.format(marca=eh.marca_do_controle(uniq))}",
            "format=float32le", "rate=48000", "channels=4",
            "channel_map=front-left,front-right,rear-left,rear-right",
            'sink_properties="device.bus=usb device.vendor.id=054c device.product.id=0ce6 '
            f"sysfs.path={ancora.declarado} device.vendor.name='Sony Interactive Entertainment' "
            f"device.description='DualSense {eh.marca_do_controle(uniq)} (háptica)' "
            'priority.session=0 device.icon_name=audio-speakers"',
        ])
    mesa.volta()
    assert len(mesa.servidor.quedas) == 2, "o endpoint de antes do install ficou de pé"
    assert [d for d in mesa.servidor.saidas() if d.startswith("DualSense ")] == []
    for lugar in eh.LUGARES:
        assert mesa.rotulo(lugar) == f"{_HAPTICA} {lugar}{_SONY}"
    cargas = len(mesa.servidor.cargas)
    mesa.volta()
    assert len(mesa.servidor.cargas) == cargas


# ---------------------------------------------------------------------------
# 5. A BANCADA — a célula que é a régua desta sprint fecha com duas
# ---------------------------------------------------------------------------


def _o_passo_que_conta() -> str:
    sys.path.insert(0, str(RAIZ / "scripts"))
    import mesa_de_medicao as med

    campos = dict(med.como_do_mapa()[_CELULA])
    passos = [p.strip() for p in campos["os passos"].split("\n") if p.strip()]
    (conta,) = [p for p in passos if p.startswith("Conte as saídas")]
    return str(conta)


def test_a_bancada_conta_duas_placas(mesa: _Mesa) -> None:
    """A conta que a célula pede, feita sobre a lista que o servidor publica.

    Lê o passo da célula no arquivo dono do gesto — os começos de nome que ela
    manda descontar, entre «» — e aplica a conta às saídas da mesa de quatro:
    as duas placas do USB, os quatro «Alto-falante do Controle N» e os QUATRO
    endpoints de háptica, um por lugar (desde 28/09/2026 eram dois, só do BT).

    MORDIDA 1 (de novo): com o rótulo de antes, a conta dá quatro.
    MORDIDA 6: devolva o passo que só nomeia «Alto-falante do Controle».
    """
    mesa.volta()
    conta = _o_passo_que_conta()
    assert "têm de ser duas" in conta, conta
    do_hefesto = re.findall(r"«([^»]+)»", conta)
    assert do_hefesto, f"o passo não diz que começos descontar: {conta!r}"
    contadas = [
        d for d in mesa.servidor.saidas()
        if "DualSense" in d and not any(d.startswith(c) for c in do_hefesto)
    ]
    assert contadas == [_PLACA_DESCRICAO, _PLACA_DESCRICAO], contadas
    # E os quatro endpoints de háptica estão NA lista — descontados, não ausentes.
    haptica = [d for d in mesa.servidor.saidas() if d.startswith(_HAPTICA)]
    assert sorted(haptica) == [f"{_HAPTICA} {n}{_SONY}" for n in eh.LUGARES]


#: O rótulo citado nos dois arquivos do gesto, com o número (ou o N genérico).
_CITADO = re.compile(r"«(Háptica do Controle ([1-4N]))([^»]*)»")
#: Quem cita pelo COMEÇO não depende da forma — é a leitura certa para contar.
_PELO_COMECO = re.compile(r"(começa com|começam com|outra com|nem com|ou com) $")


def test_o_gesto_cita_a_haptica_como_a_lista_mostra() -> None:
    """O irmão de ``test_a_bancada_fala_a_forma_a`` para o terceiro nó do controle.

    Um gesto que manda achar «Háptica do Controle 3» pelo nome inteiro tem de
    citar o nome que a lista MOSTRA, e o nome sai do dono
    (:func:`endpoint_de_haptica.rotulo_da_haptica`); quem cita pelo começo só
    precisa ser o começo dele.
    """
    arquivos = (
        RAIZ / "docs/method/2026-09-07-O-COMO-DO-MAPA-o-gesto-das-178-celulas.md",
        RAIZ / "docs/method/2026-09-07-O-COMO-DAS-21-o-gesto-exato-de-cada-linha.md",
    )
    citacoes = []
    for arquivo in arquivos:
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            for m in _CITADO.finditer(linha):
                numero = m.group(2)
                esperado = eh.rotulo_da_haptica(int(numero) if numero.isdigit() else None)
                pelo_comeco = bool(_PELO_COMECO.search(linha[: m.start()]))
                citado = m.group(1) + m.group(3)
                citacoes.append((arquivo.name[:30], n, citado, esperado, pelo_comeco))
    assert len(citacoes) >= 3, f"só {len(citacoes)} citações — a régua ficou cega"
    erradas = [
        c for c in citacoes
        if not (c[3].startswith(c[2]) if c[4] else c[2] == c[3])
    ]
    assert not erradas, "\n".join(
        f"{arq}:{n}: o gesto cita «{citado}» e a lista mostra «{esperado}»"
        for arq, n, citado, esperado, _c in erradas
    )
