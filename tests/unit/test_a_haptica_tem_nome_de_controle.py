"""A-HAPTICA-TEM-NOME-DE-CONTROLE-01 — a saída de háptica diz o controle, não o endereço.

A conferência da A-FORJA-VALIDA-O-SOM-01 achou: o endpoint de háptica aparecia
na lista de saídas de som do sistema como «DualSense <hex6> (háptica)», com o
rabo do endereço do controle no rótulo — e, com o P3 e o P4 no BT, a célula
``mapa-audio.saida_dedicada.payload_do_degrau-cabo`` da bancada contava quatro
placas DualSense onde pede duas.

A DECISÃO, por delegação dela e pelo padrão dela (a forma A de 23/09 vale para
tudo que o Hefesto publica; nada de endereço na tela), está DIGITADA aqui de
propósito: «Háptica do Controle N (DualSense Wireless Controller)», com o
número do jogador, republicado quando o número muda. A régua lê a decisão, não
o dono: mude o dono sem mudar a decisão e ela reprova.

O QUE O JOGO LÊ NÃO PODE MUDAR, e a medição está na seção 3: os casamentos do
GE-Proton11-7 sobre o nome amigável do endpoint, transcritos do fonte com os
182 patches ``proton-ds5-haptic`` aplicados, dão o mesmo resultado para o
rótulo velho e para o novo. A identidade (nome do nó, VID, PID, âncora) é a
mesma.

Nada aqui toca o servidor de som de ninguém: o ``pactl`` é um dublê com estado,
MAIS estrito que o ``pactl`` de mentira da bancada de tela (aquele aceita tudo
calado); os ``uniq`` são da faixa sintética ``aa:bb:cc``.

AS MORDIDAS, uma por afirmação, e cada uma foi vista reprovar:

1. devolva ``device.description='DualSense {marca} (háptica)'`` em
   ``propriedades_do_endpoint`` → o endereço volta ao rótulo e a bancada conta
   quatro;
2. tire ``*campos_do_nome()`` de ``propriedades_do_endpoint`` → o monitor
   chega ao Wine com 64 caracteres e sem nome de reserva;
3. tire a chamada a ``_renovar_o_rotulo_da_haptica`` da volta do rádio → o
   número fica o de quando o nó nasceu;
4. tire ``self._ha_jogo_aberto()`` de ``_a_haptica_esta_em_uso`` → o endpoint
   renasce debaixo de um jogo aberto;
5. tire a leitura de ``rotulo_no_ar`` da adoção → o nó que o restart herdou
   nunca perde o nome de antes;
6. devolva o passo da bancada que só nomeia «Alto-falante do Controle» → a
   conta volta a dar quatro.
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


@pytest.fixture
def assentos() -> Iterator[dict[str, int | None]]:
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
def test_o_rotulo_e_a_forma_a_com_o_numero_do_jogador(assentos, numero: int | None) -> None:
    """O número vem do DONO (o numerador), e sem número não se inventa número."""
    assentos[_P3] = numero
    sufixo = "" if numero is None else f" {numero}"
    assert eh.descricao_da_haptica(_P3) == f"{_HAPTICA}{sufixo}{_SONY}"


def _campos_de_gente(props: dict[str, str]) -> dict[str, str]:
    """Os campos que alguém LÊ numa lista de som — onde o endereço não entra."""
    return {k: v for k, v in props.items() if k in (
        "device.description", "node.nick", "device.product.name", "device.vendor.name")}


@pytest.mark.parametrize("uniq", [_P1, _P2, _P3, _P4])
def test_nenhum_hex_do_endereco_chega_ao_rotulo(assentos, uniq: str) -> None:
    """Nem os seis do rabo, nem par nenhum do endereço, em campo que alguém lê.

    MORDIDA 1: devolva ``'DualSense {marca} (háptica)'`` e o rabo volta.
    """
    props = _como_o_servidor_le(eh.propriedades_do_endpoint(uniq, _ANCORAS[0]))
    pares = [p for p in uniq.lower().split(":") if re.search(r"[a-f]", p)]
    for chave, valor in _campos_de_gente(props).items():
        baixa = valor.lower()
        assert eh.marca_do_controle(uniq) not in baixa, f"{chave}={valor!r}"
        assert not re.search(r"\b[0-9a-f]{6}\b", baixa), f"{chave}={valor!r}"
        for par in pares:
            assert not re.search(rf"\b{par}\b", baixa), f"{chave}={valor!r} leva {par!r}"
    assert props["device.description"] == f"{_HAPTICA} {_ASSENTO[uniq]}{_SONY}"


def test_o_rotulo_cabe_no_teto_e_o_monitor_tem_reserva(assentos) -> None:
    """O rótulo cabe nos 62 do Wine; o monitor passa, e o ``product.name`` o salva.

    O ``pipewire-pulse`` chama o monitor de «Monitor of <descrição>»: com a
    forma A isso dá 64. Acima do teto o Wine monta o nome a partir do
    ``device.product.name`` — sem ele, o comprido chega inteiro ao jogo.

    MORDIDA 2: tire ``*campos_do_nome()`` de ``propriedades_do_endpoint``.
    """
    for numero in (1, 2, 3, 4):
        assentos[_P3] = numero
        rotulo = eh.descricao_da_haptica(_P3)
        assert len(rotulo) <= _TETO_DO_WINE, (len(rotulo), rotulo)
        assert len(_MONITOR_DE + rotulo) > _TETO_DO_WINE
        props = _como_o_servidor_le(eh.propriedades_do_endpoint(_P3, _ANCORAS[0]))
        reserva = props.get("device.product.name", "")
        assert reserva, "o monitor do endpoint chega ao Wine sem nome de reserva"
        assert len(_MONITOR_DE + reserva) <= _TETO_DO_WINE


def test_a_identidade_do_no_fica_intacta(assentos) -> None:
    """O NOME segue pela marca e a identidade é a de antes — é o que o jogo lê.

    O id do endpoint no Wine sai do nome do sink, e o ``ContainerId`` que a RE
    Engine casa com o device KS sai do ``sysfs.path``. Nenhum dos dois pode
    mudar por causa de um rótulo.
    """
    ancora = _ANCORAS[2]
    props = _como_o_servidor_le(eh.propriedades_do_endpoint(_P3, ancora))
    assert props["device.bus"] == "usb"
    assert props["device.vendor.id"] == "054c"
    assert props["device.product.id"] == "0ce6"
    assert props["sysfs.path"] == ancora.declarado
    assert props["device.vendor.name"] == "Sony Interactive Entertainment"
    assert props["priority.session"] == "0", "o endpoint não pode virar a saída padrão"
    assert eh.nome_do_endpoint(_P3) == eh.MOLDE_DO_NOME.format(marca=eh.marca_do_controle(_P3))


def test_o_no_publicado_diz_o_controle(assentos) -> None:
    """O que a lista de som MOSTRA, lido do servidor depois do ``load-module``."""
    servidor = _Servidor()
    no = eh.EndpointDeHaptica(uniq=_P4, ancora=_ANCORAS[1], runner=servidor)
    assert no.iniciar() is True
    (publicado,) = servidor.do_nome(eh.nome_do_endpoint(_P4))
    assert servidor.descricao(publicado) == f"{_HAPTICA} 4{_SONY}"
    assert publicado["props"]["sysfs.path"] == _ANCORAS[1].declarado
    assert publicado["canais"] == 4
    assert no.rotulo == f"{_HAPTICA} 4{_SONY}", "o nó não lembra o rótulo que publicou"


# ---------------------------------------------------------------------------
# 2. O NÓ ADOTADO — o rótulo de quando ele nasceu se lê do servidor
# ---------------------------------------------------------------------------


def test_o_rotulo_do_no_adotado_se_le_do_argumento_do_modulo() -> None:
    """A linha real do ``pactl list short modules``, com espaço e acento no rótulo."""
    nome = eh.nome_do_endpoint(_P3)
    linha = (
        f"536870913\tmodule-null-sink\tsink_name={nome} format=float32le rate=48000 "
        "channels=4 channel_map=front-left,front-right,rear-left,rear-right "
        'sink_properties="device.bus=usb device.vendor.id=054c device.product.id=0ce6 '
        f"sysfs.path={_ANCORAS[0].declarado} device.vendor.name='Sony Interactive "
        "Entertainment' device.description='DualSense 5ea3c3 (háptica)' "
        'priority.session=0 device.icon_name=audio-speakers"\t'
    )
    assert eh.endpoints_de_pe(lambda _a: linha) == {
        nome: [("536870913", _ANCORAS[0].declarado)]
    }
    assert eh.rotulo_no_ar("536870913", lambda _a: linha) == "DualSense 5ea3c3 (háptica)"
    assert eh.rotulo_no_ar("1", lambda _a: linha) == ""
    assert eh.rotulo_no_ar("536870913", lambda _a: None) == ""


# ---------------------------------------------------------------------------
# 3. O QUE O JOGO CASA NÃO MUDOU — a medição, transcrita do GE
# ---------------------------------------------------------------------------
#
# GE-Proton11-7 (`proton-hefesto/fonte`, commit `c191f35`), com os 182 patches de
# `patches/proton-ds5-haptic/` aplicados em ordem sobre o `wine` dele — 179
# entram limpos; 0022, 0109 e 0150 falham em trechos de formato e de include,
# longe do nome. A descrição do nó chega ao `mmdevapi` como o nome amigável
# (`get_device_name` → `MMDevice.drv_id`, e `L"%ls (%ls)"` com «Speakers» ou
# «Microphone» no `DEVPKEY_Device_FriendlyName`). Os predicados que LEEM esse
# nome, de `dlls/mmdevapi/devenum.c`, transcritos um a um:


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
    """Cada forma do nome que um predicado do GE lê, com os cinco resultados."""
    formas = (nome_amigavel, f"Speakers ({nome_amigavel})")
    return [(f, tuple(p(f) for p in _CASAMENTOS_DO_GE)) for f in formas]


@pytest.mark.parametrize("numero", [1, 2, 3, 4, None])
def test_os_casamentos_do_ge_dao_o_mesmo_resultado(assentos, numero: int | None) -> None:
    """O rótulo novo cai em cada casamento do GE exatamente como o velho caía.

    Se uma forma futura do rótulo ganhar «Speaker» (e virar o alto-falante mono
    que o GE esconde e remove) ou perder «DualSense» (e sair do 0187, que
    preserva o endpoint ativo de cada controle), esta régua reprova antes de a
    háptica que já vibra parar.
    """
    assentos[_P3] = numero
    velho = f"DualSense {eh.marca_do_controle(_P3)} (háptica)"
    novo = eh.descricao_da_haptica(_P3)
    assert [r for _f, r in _o_que_o_ge_ve(novo)] == [r for _f, r in _o_que_o_ge_ve(velho)]
    # e o monitor: com o nome de reserva, que é o que o Wine usa acima do teto
    props = _como_o_servidor_le(eh.propriedades_do_endpoint(_P3, _ANCORAS[0]))
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
    jogo_aberto: bool = False

    def volta(self) -> None:
        """Uma volta do daemon com a mesa de quatro: P1 e P2 no USB, P3 e P4 no BT."""
        self.sub._casar_as_pontes([
            _Controle(_P1, "usb"), _Controle(_P2, "usb"),
            _Controle(_P3, "bt"), _Controle(_P4, "bt"),
        ])

    def rotulo(self, uniq: str) -> str:
        (no,) = self.servidor.do_nome(eh.nome_do_endpoint(uniq))
        return self.servidor.descricao(no)

    def ancora(self, uniq: str) -> str:
        (no,) = self.servidor.do_nome(eh.nome_do_endpoint(uniq))
        return str(no["props"]["sysfs.path"])


@pytest.fixture
def mesa(monkeypatch: pytest.MonkeyPatch, assentos) -> _Mesa:
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

    sub = mod.AltoFalanteSubsystem(gerenciador=_Ger(), fonte_de_controles=list)
    m = _Mesa(sub=sub, servidor=servidor)
    # O `/proc` da máquina que roda a suíte não decide nada aqui: a régua diz
    # se há jogo aberto (memória "régua que depende de app aberto mede a máquina").
    monkeypatch.setattr(mod.AltoFalanteSubsystem, "_ha_jogo_aberto", lambda self: m.jogo_aberto)
    return m


def test_so_os_controles_do_bt_ganham_a_haptica(mesa: _Mesa) -> None:
    """No USB a vibração viaja pela placa do controle; o endpoint é só do BT."""
    mesa.volta()
    assert mesa.rotulo(_P3) == f"{_HAPTICA} 3{_SONY}"
    assert mesa.rotulo(_P4) == f"{_HAPTICA} 4{_SONY}"
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(_P1)) == []
    assert mesa.servidor.do_nome(eh.nome_do_endpoint(_P2)) == []


def test_o_rotulo_segue_o_assento_e_nada_que_o_jogo_le_muda(mesa: _Mesa, assentos) -> None:
    """P3 e P4 trocam de lugar: os dois rótulos seguem, o nome e a âncora não.

    MORDIDA 3: tire a chamada a ``_renovar_o_rotulo_da_haptica`` da volta.
    """
    mesa.volta()
    antes = {u: (mesa.ancora(u), eh.nome_do_endpoint(u)) for u in (_P3, _P4)}
    assentos[_P3], assentos[_P4] = 4, 3
    mesa.volta()
    assert mesa.rotulo(_P3) == f"{_HAPTICA} 4{_SONY}"
    assert mesa.rotulo(_P4) == f"{_HAPTICA} 3{_SONY}"
    assert {u: (mesa.ancora(u), eh.nome_do_endpoint(u)) for u in (_P3, _P4)} == antes
    # E uma volta a mais não mexe em nada: o rótulo certo não envelhece.
    quedas = list(mesa.servidor.quedas)
    mesa.volta()
    assert mesa.servidor.quedas == quedas, "o nó renasceu sem o assento ter andado"


def test_com_jogo_aberto_o_rotulo_espera(mesa: _Mesa, assentos) -> None:
    """Republicar é hotplug de endpoint Sony: com jogo aberto, o nome espera.

    MORDIDA 4: tire ``self._ha_jogo_aberto()`` de ``_a_haptica_esta_em_uso``.
    """
    mesa.volta()
    assentos[_P3] = 1
    mesa.jogo_aberto = True
    mesa.volta()
    assert mesa.rotulo(_P3) == f"{_HAPTICA} 3{_SONY}", "o endpoint renasceu com o jogo aberto"
    assert mesa.servidor.quedas == []
    mesa.jogo_aberto = False
    mesa.volta()
    assert mesa.rotulo(_P3) == f"{_HAPTICA} 1{_SONY}"


def test_com_o_jogo_tocando_no_no_o_rotulo_espera(mesa: _Mesa, assentos) -> None:
    """Um stream no endpoint (sink-input) segura o nó — mesmo sem jogo reconhecido."""
    mesa.volta()
    assentos[_P4] = 2
    mesa.servidor.jogo_em.add(eh.nome_do_endpoint(_P4))
    mesa.volta()
    assert mesa.rotulo(_P4) == f"{_HAPTICA} 4{_SONY}"
    mesa.servidor.jogo_em.clear()
    mesa.volta()
    assert mesa.rotulo(_P4) == f"{_HAPTICA} 2{_SONY}"


def test_perder_o_numero_nao_republica(mesa: _Mesa, assentos) -> None:
    """O numerador que pisca (subsystem descendo, mesa vazia por uma volta) não conta."""
    mesa.volta()
    assentos[_P3] = None
    mesa.volta()
    assert mesa.rotulo(_P3) == f"{_HAPTICA} 3{_SONY}"
    assert mesa.servidor.quedas == []


def test_o_no_herdado_com_o_nome_de_antes_renasce_uma_vez(mesa: _Mesa) -> None:
    """Depois do install, o endpoint que o daemon anterior deixou muda UMA vez.

    O restart adota o nó (não recarrega um nó vivo), lembra o rótulo que o
    servidor diz, e a volta seguinte, sem jogo aberto, o renova. A âncora e o
    nome ficam; e a forma A igual a si mesma não envelhece, senão o nó
    renasceria em laço.

    MORDIDA 5: tire ``self.rotulo = rotulo_no_ar(...)`` da adoção.
    """
    for uniq, ancora in ((_P3, _ANCORAS[2]), (_P4, _ANCORAS[3])):
        mesa.servidor.modulo_herdado([
            "module-null-sink", f"sink_name={eh.nome_do_endpoint(uniq)}",
            "format=float32le", "rate=48000", "channels=4",
            "channel_map=front-left,front-right,rear-left,rear-right",
            'sink_properties="device.bus=usb device.vendor.id=054c device.product.id=0ce6 '
            f"sysfs.path={ancora.declarado} device.vendor.name='Sony Interactive Entertainment' "
            f"device.description='DualSense {eh.marca_do_controle(uniq)} (háptica)' "
            'priority.session=0 device.icon_name=audio-speakers"',
        ])
    mesa.volta()
    assert mesa.servidor.cargas == [], "o restart recarregou um nó vivo em vez de adotá-lo"
    assert mesa.rotulo(_P3) == f"DualSense {eh.marca_do_controle(_P3)} (háptica)"
    mesa.volta()
    assert mesa.rotulo(_P3) == f"{_HAPTICA} 3{_SONY}"
    assert mesa.rotulo(_P4) == f"{_HAPTICA} 4{_SONY}"
    assert mesa.ancora(_P3) == _ANCORAS[2].declarado
    assert mesa.ancora(_P4) == _ANCORAS[3].declarado
    cargas = len(mesa.servidor.cargas)
    mesa.volta()
    assert len(mesa.servidor.cargas) == cargas


def test_o_rotulo_novo_que_nao_sobe_devolve_o_velho(assentos) -> None:
    """Um rótulo velho é melhor que endpoint nenhum — a ordem do nó do som."""
    servidor = _Servidor()
    no = eh.EndpointDeHaptica(uniq=_P3, ancora=_ANCORAS[0], runner=servidor)
    assert no.iniciar() is True
    assentos[_P3] = 2
    servidor.recusar_cargas = 1
    assert no.renovar_o_rotulo() is False
    assert no.module_id is not None, "o endpoint sumiu por causa do NOME"
    assert no.rotulo == f"{_HAPTICA} 3{_SONY}"
    (publicado,) = servidor.do_nome(eh.nome_do_endpoint(_P3))
    assert servidor.descricao(publicado) == f"{_HAPTICA} 3{_SONY}"
    # e na volta seguinte, com o servidor atendendo, o nome segue o assento
    assert no.renovar_o_rotulo() is True
    assert no.rotulo == f"{_HAPTICA} 2{_SONY}"


# ---------------------------------------------------------------------------
# 5. A BANCADA — a célula que é a régua desta sprint fecha com duas
# ---------------------------------------------------------------------------


def _o_passo_que_conta() -> str:
    sys.path.insert(0, str(RAIZ / "scripts"))
    import mesa_de_medicao as med

    campos = dict(med.como_do_mapa()[_CELULA])
    passos = [p.strip() for p in campos["os passos"].split("\n") if p.strip()]
    (conta,) = [p for p in passos if p.startswith("Conte as saídas")]
    return conta


def test_a_bancada_conta_duas_placas(mesa: _Mesa) -> None:
    """A conta que a célula pede, feita sobre a lista que o servidor publica.

    Lê o passo da célula no arquivo dono do gesto — os começos de nome que ela
    manda descontar, entre «» — e aplica a conta às saídas da mesa de quatro:
    as duas placas do USB, os quatro «Alto-falante do Controle N» e os dois
    endpoints de háptica que a volta do rádio publica para o P3 e o P4.

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
    # E os dois endpoints de háptica estão NA lista — descontados, não ausentes.
    haptica = [d for d in mesa.servidor.saidas() if d.startswith(_HAPTICA)]
    assert sorted(haptica) == [f"{_HAPTICA} 3{_SONY}", f"{_HAPTICA} 4{_SONY}"]


#: O rótulo citado nos dois arquivos do gesto, com o número (ou o N genérico).
_CITADO = re.compile(r"«(Háptica do Controle ([1-4N]))([^»]*)»")
#: Quem cita pelo COMEÇO não depende da forma — é a leitura certa para contar.
_PELO_COMECO = re.compile(r"(começa com|começam com|outra com|nem com|ou com) $")


def test_o_gesto_cita_a_haptica_como_a_lista_mostra(assentos) -> None:
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
