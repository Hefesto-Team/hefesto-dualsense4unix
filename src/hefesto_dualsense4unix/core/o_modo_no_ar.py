"""O modo pedido contra o pad no ar, e a hora em que cada pad nasceu.

O-DOCTOR-PERGUNTA-O-MODO-E-A-HORA-DO-PAD-01 (27/09/2026). Duas perguntas que o
`doctor` faz depois do install, e que o fecho de 27/09 não fazia:

* **O modo.** Às 16h16 o fecho foi «pads no `uhid` e nenhum `vpad_degradado`»,
  com o Freestyle dela no modo Xbox: os pads deviam estar no `uinput`. O
  `degraded` e o `dedup_ok` diziam íntegro, porque respondem outra pergunta
  («o canal caiu sem ela pedir?»). :func:`modo_contra_o_ar` compara, por
  jogador, o canal que o modo pedido dá com o backend do pad no ar.
* **A hora.** Na noite de 27/09 os pads `uinput` levaram de 28,7 a 30,3 s entre
  o kernel criar o nó e o daemon registrar (`uinput_device_created`), com o
  `cosmic-osk` de pé, e o compositor caiu duas vezes na esteira. A cura entrou
  às 13h07; :func:`hora_do_pad` é o instrumento que acusa se a trava voltar.

O CANAL QUE O MODO PEDE TEM UM DONO, e ele é perguntado, não reescrito:
`virtual_pad.quer_uhid(caminho, máscara)`. A máscara entra só como a segunda
metade dessa pergunta, porque com uma máscara que o `uhid` não veste os dois
modos dão o mesmo aparelho no `uinput` (é a mesma regra de
`external_mask.vpad_ficou_para_tras`). Sem ela, o modo DualSense com o cartão
em Xbox 360 sairia FALHA, e o PRAGMATA de 27/09 (a sessão em DualSense, o pad
renascido no Xbox com a máscara DualSense) sairia OK.

Funções puras: recebem o que o daemon publica e o texto do diário, não abrem
nó, não falam com o daemon e não leem disco. Quem lê é o `doctor.sh`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from hefesto_dualsense4unix.app.fala_do_mapa import formata_pt_br

OK = "ok"
AVISO = "aviso"
FALHA = "falha"

#: Acima disto o pad nasceu preso. Os da noite de 27/09 deram de +28,7 a
#: +30,3 s; sem o `cosmic-osk`, de +0,1 a +0,7 s; depois da cura (151 pads,
#: de 13h07 de 27/09 a 03h27 de 28/09), menos de 4 ms. O número de corte é
#: hipótese pelos números da noite, e a prova no aparelho o confirma.
LIMITE_DO_NASCIMENTO_S = 2.0

#: A linha do kernel chega ao diário pelo journald, que a carimba quando a
#: RECEBE, não quando o kernel a escreveu. Medido nos 162 pads `uinput` do boot
#: de 27 a 28/09: no normal ela chega menos de 2 ms depois do registro do
#: daemon; duas vezes chegou 0,11 s e 1,85 s depois, com o journald parado, e
#: nas duas a linha do PRÓPRIO registro do daemon chegou no mesmo instante.
#: Esta folga deixa a criação casar com o registro que veio antes dela; a
#: parada do journald se resolve pela chegada da linha do daemon (ver
#: :func:`hora_do_pad`), nunca alargando esta folga, porque na noite de 27/09
#: o pad seguinte nasceu de 0,3 a 0,9 s depois do registro do lento.
FOLGA_DO_DIARIO_S = 0.1

_BACKENDS = ("uhid", "uinput")
_NENHUM = "nenhum"

_NOME_DO_MODO = {
    "dualsense": "modo DualSense",
    "xbox": "modo Xbox",
    "nativo": "Conexão Nativa",
    "desligado": "emulação desligada",
}
#: A concordância do «pedido» com o nome do modo.
_PEDIDO = {"nativo": "pedida", "desligado": "pedida"}

_NOME_DA_MASCARA = {"dualsense": "DualSense", "xbox": "Xbox", "nintendo": "Nintendo"}


@dataclass(frozen=True)
class ModoDoJogador:
    """Uma linha por jogador: o modo pedido, o canal que ele dá e o do ar."""

    jogador: int
    #: ``dualsense`` · ``xbox`` · ``nativo`` · ``desligado`` · ``None`` (o
    #: daemon não publicou o modo).
    pedido: str | None
    #: ``uhid`` · ``uinput`` · ``nenhum``.
    no_ar: str
    #: O backend que o pedido dá para este jogador; ``None`` quando não se sabe.
    esperado: str | None
    #: O motivo de queda que o daemon pendurou, quando há.
    motivo: str | None
    veredito: str

    def frase(self) -> str:
        """Só o jogador, o modo e o backend: nenhum nó, nenhum endereço."""
        modo = _NOME_DO_MODO.get(self.pedido or "", "modo não publicado")
        pad = "sem pad" if self.no_ar == _NENHUM else f"pad {self.no_ar}"
        if self.pedido is None:
            return f"P{self.jogador}: {pad}, e o daemon não diz o modo (não medido)"
        if self.veredito == OK:
            return f"P{self.jogador}: {modo}, {pad}"
        if self.veredito == AVISO:
            return f"P{self.jogador}: {modo}, {pad} (queda dita: {self.motivo})"
        pedido = _PEDIDO.get(self.pedido, "pedido")
        return f"P{self.jogador}: {modo} {pedido}, {pad} no ar, sem queda dita"


def _dict(valor: object) -> Mapping[str, Any]:
    return valor if isinstance(valor, Mapping) else {}


def _lista(valor: object) -> list[Mapping[str, Any]]:
    if not isinstance(valor, list):
        return []
    return [item for item in valor if isinstance(item, Mapping)]


def _jogador(valor: object) -> int | None:
    if isinstance(valor, int) and not isinstance(valor, bool) and valor > 0:
        return valor
    return None


def _backend(valor: object) -> str | None:
    return valor if isinstance(valor, str) and valor in _BACKENDS else None


def _texto(valor: object) -> str | None:
    return valor if isinstance(valor, str) and valor else None


def _caminho(valor: object) -> str | None:
    if isinstance(valor, str) and valor.strip().lower() in ("dualsense", "xbox"):
        return valor.strip().lower()
    return None


def _pads_no_ar(estado: Mapping[str, Any]) -> dict[int, str]:
    """``{jogador: backend}`` dos pads no ar.

    O `rumble_ff.per_vpad[].backend` é a fonte (o contrato da onda de 28/09 o
    congela); a `coop.mesa` completa quem não está lá, com ``nenhum`` para o
    jogador registrado sem pad; o `gamepad_emulation.backend` fala pelo P1
    quando nenhuma das duas veio.
    """
    pads: dict[int, str] = {}
    for bloco in _lista(_dict(estado.get("rumble_ff")).get("per_vpad")):
        numero = _jogador(bloco.get("player"))
        if numero is not None and numero not in pads:
            pads[numero] = _backend(bloco.get("backend")) or _NENHUM
    for item in _lista(_dict(estado.get("coop")).get("mesa")):
        numero = _jogador(item.get("player"))
        if numero is not None and numero not in pads:
            pads[numero] = _backend(item.get("vpad_backend")) or _NENHUM
    if not pads:
        backend = _backend(_dict(estado.get("gamepad_emulation")).get("backend"))
        if backend is not None:
            pads[1] = backend
    return pads


def _controle_do_jogador(estado: Mapping[str, Any], numero: int) -> Mapping[str, Any]:
    """O controle físico do jogador ``numero`` (o primário, se houver empate)."""
    candidatos = [
        c
        for c in _lista(estado.get("controllers"))
        if c.get("connected") is not False and _jogador(c.get("player")) == numero
    ]
    for controle in candidatos:
        if controle.get("is_primary") is True:
            return controle
    return candidatos[0] if candidatos else {}


def _item_da_mesa(estado: Mapping[str, Any], numero: int) -> Mapping[str, Any]:
    for item in _lista(_dict(estado.get("coop")).get("mesa")):
        if _jogador(item.get("player")) == numero:
            return item
    return {}


def _numero_do_primario(estado: Mapping[str, Any]) -> int:
    for item in _lista(_dict(estado.get("coop")).get("mesa")):
        if item.get("is_primary") is True and _jogador(item.get("player")):
            return int(item["player"])
    for controle in _lista(estado.get("controllers")):
        if controle.get("is_primary") is True and _jogador(controle.get("player")):
            return int(controle["player"])
    return 1


def _veredito(no_ar: str, esperado: str, motivo: str | None) -> str:
    if no_ar == esperado:
        return OK
    return AVISO if motivo else FALHA


def modo_contra_o_ar(estado: Mapping[str, Any]) -> list[ModoDoJogador]:
    """Por jogador, o modo pedido contra o backend do pad no ar.

    ``estado`` é o `daemon.state_full`. Divergência sem motivo de queda é
    FALHA; com motivo, AVISO com o motivo; a Conexão Nativa (ou a emulação
    desligada) sem pad é OK. A máscara não é comparada com nada: ela só entra
    como a metade da pergunta ao dono do canal (`quer_uhid`).
    """
    emulacao = _dict(estado.get("gamepad_emulation"))
    pads = _pads_no_ar(estado)

    if estado.get("native_mode") is True or emulacao.get("enabled") is not True:
        pedido = "nativo" if estado.get("native_mode") is True else "desligado"
        numeros = set(pads) | {
            n
            for c in _lista(estado.get("controllers"))
            if c.get("connected") and (n := _jogador(c.get("player"))) is not None
        }
        return [
            ModoDoJogador(
                jogador=n,
                pedido=pedido,
                no_ar=pads.get(n, _NENHUM),
                esperado=_NENHUM,
                motivo=None,
                veredito=OK if pads.get(n, _NENHUM) == _NENHUM else FALHA,
            )
            for n in sorted(numeros)
        ]

    from hefesto_dualsense4unix.integrations.virtual_pad import quer_uhid

    caminho = _caminho(emulacao.get("caminho"))
    por_aparelho = _dict(emulacao.get("por_aparelho"))
    mascara_da_sessao = _texto(emulacao.get("flavor")) or "dualsense"
    primario = _numero_do_primario(estado)
    linhas: list[ModoDoJogador] = []
    for numero in sorted(pads or {primario: _NENHUM}):
        no_ar = pads.get(numero, _NENHUM)
        controle = _controle_do_jogador(estado, numero)
        item = _item_da_mesa(estado, numero)
        motivo = _texto(controle.get("vpad_motivo"))
        if motivo is None and numero == primario and emulacao.get("degraded") is True:
            motivo = _texto(emulacao.get("degraded_motivo")) or "sem_uhid"
        if motivo is None and no_ar == _NENHUM and item.get("aguardando_grab") is True:
            motivo = "aguardando_grab"
        if caminho is None:
            linhas.append(ModoDoJogador(numero, None, no_ar, None, motivo, AVISO))
            continue
        uniq = _texto(controle.get("uniq")) or _texto(item.get("uniq"))
        mascara = _texto(por_aparelho.get(uniq)) if uniq else None
        esperado = "uhid" if quer_uhid(caminho, mascara or mascara_da_sessao) else "uinput"
        linhas.append(
            ModoDoJogador(
                jogador=numero,
                pedido=caminho,
                no_ar=no_ar,
                esperado=esperado,
                motivo=motivo,
                veredito=_veredito(no_ar, esperado, motivo),
            )
        )
    return linhas


# ---------------------------------------------------------------------------
# A hora do pad
# ---------------------------------------------------------------------------

_ISO = re.compile(
    r"(?P<a>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})[T ](?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})"
    r"(?:[.,](?P<f>\d{1,9}))?(?P<tz>Z|[+-]\d{2}:?\d{2})?"
)
#: O carimbo do structlog vem colado ao nível: ``<iso> [info     ] <evento>``.
_CONSOLE = re.compile(_ISO.pattern + r"\s+\[\s*\w+\s*\]\s+(?P<evento>\w+)(?P<resto>.*)$")
_NOME = re.compile(r"\bname=(?P<q>['\"])(?P<nome>.*?)(?P=q)(?=\s|$)")
_MASCARA = re.compile(r"\bflavor=(?P<m>['\"]?)(?P<mascara>\w+)(?P=m)")
_KERNEL = re.compile(r"input: (?P<nome>.+?) as /devices/virtual/input/input\d+\s*$")


def _instante(achado: re.Match[str]) -> datetime:
    """O carimbo ISO do achado, com ou sem fuso (o `datetime` de 3.10 não lê todos)."""
    fracao = (achado.group("f") or "0")[:6].ljust(6, "0")
    fuso = None
    tz = achado.group("tz")
    if tz == "Z":
        fuso = timezone.utc
    elif tz:
        sinal = -1 if tz[0] == "-" else 1
        digitos = tz[1:].replace(":", "")
        fuso = timezone(sinal * timedelta(hours=int(digitos[:2]), minutes=int(digitos[2:])))
    return datetime(
        int(achado.group("a")),
        int(achado.group("m")),
        int(achado.group("d")),
        int(achado.group("h")),
        int(achado.group("mi")),
        int(achado.group("s")),
        int(fracao),
        tzinfo=fuso,
    )


def _segundos(depois: datetime, antes: datetime) -> float:
    """``depois - antes``. Um dos dois sem fuso: compara o relógio de parede.

    O structlog do daemon carimba a hora local sem fuso, e o journalctl imprime
    a do kernel na hora local com fuso: os dois relógios são o mesmo.
    """
    if (depois.tzinfo is None) != (antes.tzinfo is None):
        depois, antes = depois.replace(tzinfo=None), antes.replace(tzinfo=None)
    return (depois - antes).total_seconds()


@dataclass(frozen=True)
class _Registro:
    evento: str
    #: O carimbo do structlog: o instante do registro.
    quando: datetime
    nome: str | None
    mascara: str | None
    #: O carimbo do journald (a chegada da linha ao diário), quando a linha o traz.
    recebido: datetime | None = None


def _registro_do_daemon(linha: str) -> _Registro | None:
    """O evento, a hora e o pad de uma linha do diário do daemon.

    O carimbo que vale é o do structlog (o instante do registro), e não o do
    journald, que chega depois quando o journald para. O do journald, quando a
    linha o traz na frente (``journalctl -o short-iso-precise``), vai junto em
    ``recebido``: é ele que resolve a linha do kernel que chegou atrasada. Lê
    os dois formatos do daemon, console e JSON.
    """
    inicio = linha.find('{"')
    if inicio >= 0:
        try:
            dado = json.loads(linha[inicio:])
        except ValueError:
            dado = None
        if isinstance(dado, dict) and isinstance(dado.get("event"), str):
            achado = _ISO.search(str(dado.get("timestamp") or ""))
            if achado is None:
                return None
            return _Registro(
                dado["event"],
                _instante(achado),
                _texto(dado.get("name")),
                _texto(dado.get("flavor")),
                _chegada(linha[:inicio]),
            )
    achado = _CONSOLE.search(linha)
    if achado is None:
        return None
    resto = achado.group("resto")
    nome = _NOME.search(resto)
    mascara = _MASCARA.search(resto)
    return _Registro(
        achado.group("evento"),
        _instante(achado),
        nome.group("nome") if nome else None,
        mascara.group("mascara") if mascara else None,
        _chegada(linha[: achado.start()]),
    )


def _chegada(prefixo: str) -> datetime | None:
    """O carimbo do journald na frente da linha, se houver."""
    achado = _ISO.search(prefixo)
    return _instante(achado) if achado is not None else None


def _criacao_no_kernel(linha: str) -> tuple[datetime, str] | None:
    """``(hora, nome)`` de um ``input: <nome> as /devices/virtual/input/inputN``."""
    achado = _KERNEL.search(linha)
    carimbo = _ISO.search(linha)
    if achado is None or carimbo is None or carimbo.start() > achado.start():
        return None
    return _instante(carimbo), achado.group("nome")


@dataclass(frozen=True)
class HoraDoPad:
    """Um pad `uinput` registrado desde que o daemon subiu, e quanto ele levou."""

    #: A máscara do pad, como o daemon a registrou (``xbox``, ``dualsense``…).
    mascara: str | None
    #: A hora do nascimento (a do kernel; sem ela, a do registro), ``HH:MM:SS``.
    hora: str
    #: Segundos entre o kernel criar o nó e o daemon registrar. ``None`` =
    #: não medido.
    atraso_s: float | None
    veredito: str

    def frase(self) -> str:
        """Só a máscara, a hora e o número: nenhum nó, nenhum endereço."""
        pad = f"o pad {_NOME_DA_MASCARA.get(self.mascara or '', 'virtual')} das {self.hora}"
        if self.atraso_s is None:
            return f"{pad} não foi medido: o diário do kernel não tem a criação dele"
        numero = formata_pt_br(self.atraso_s)
        if self.veredito == FALHA:
            return (
                f"{pad} levou {numero} s para nascer: algo pediu vibração antes de "
                "ele estar de pé"
            )
        return f"{pad} nasceu em {numero} s"


def hora_do_pad(
    linhas_do_kernel: Iterable[str], linhas_do_daemon: Iterable[str]
) -> list[HoraDoPad]:
    """O atraso de cada pad `uinput` registrado desde o último `daemon_starting`.

    Casa, pelo nome do pad, cada ``uinput_device_created`` do daemon com a
    criação mais recente do mesmo nome no kernel, ainda livre, entre o
    `daemon_starting` e o registro (mais a :data:`FOLGA_DO_DIARIO_S`). Acima de
    :data:`LIMITE_DO_NASCIMENTO_S` é FALHA; sem a linha do kernel, AVISO («não
    medido»), nunca OK.

    O JOURNALD PARADO. Sem criação livre antes do registro, vale a que chegou
    ao diário JUNTO com a linha do próprio registro (até a folga depois dela ou
    até :data:`LIMITE_DO_NASCIMENTO_S` antes, e nunca mais de
    :data:`LIMITE_DO_NASCIMENTO_S` depois do registro): as duas ficaram presas
    no mesmo journald, e o atraso é a distância entre as duas chegadas, no
    mesmo relógio. Fora disso as duas chegadas não contam a mesma parada, e o
    pad sai «não medido». Medido no boot de 27 a 28/09 (a nota de
    :data:`FOLGA_DO_DIARIO_S`): sem isto, dois pads de 162, sãos, saíam
    «não medido».
    """
    registros = [r for r in map(_registro_do_daemon, linhas_do_daemon) if r is not None]
    partidas = [i for i, r in enumerate(registros) if r.evento == "daemon_starting"]
    desde = registros[partidas[-1]].quando if partidas else None
    pads = [
        r
        for r in registros[(partidas[-1] + 1 if partidas else 0) :]
        if r.evento == "uinput_device_created"
    ]
    criacoes = [c for c in map(_criacao_no_kernel, linhas_do_kernel) if c is not None]
    if desde is not None:
        criacoes = [c for c in criacoes if _segundos(c[0], desde) >= 0]
    livres = list(range(len(criacoes)))
    medidas: list[HoraDoPad] = []
    for pad in pads:
        do_nome = [i for i in livres if criacoes[i][1] == pad.nome]
        casados = [
            i for i in do_nome if _segundos(criacoes[i][0], pad.quando) <= FOLGA_DO_DIARIO_S
        ]
        chegou = pad.recebido
        juntos = (
            [
                i
                for i in do_nome
                if -LIMITE_DO_NASCIMENTO_S
                <= _segundos(criacoes[i][0], chegou)
                <= FOLGA_DO_DIARIO_S
                and _segundos(criacoes[i][0], pad.quando) <= LIMITE_DO_NASCIMENTO_S
            ]
            if chegou is not None
            else []
        )
        if casados:
            escolhido = max(casados, key=lambda i: _segundos(criacoes[i][0], pad.quando))
            nasceu = criacoes[escolhido][0]
            atraso = max(0.0, _segundos(pad.quando, nasceu))
        elif juntos and chegou is not None:
            # A hora do kernel chegou presa com a do registro: o nascimento é o
            # registro menos a distância entre as duas chegadas.
            escolhido = min(juntos, key=lambda i: _segundos(criacoes[i][0], chegou))
            atraso = max(0.0, _segundos(chegou, criacoes[escolhido][0]))
            nasceu = pad.quando - timedelta(seconds=atraso)
        else:
            medidas.append(
                HoraDoPad(pad.mascara, pad.quando.strftime("%H:%M:%S"), None, AVISO)
            )
            continue
        livres.remove(escolhido)
        medidas.append(
            HoraDoPad(
                pad.mascara,
                nasceu.strftime("%H:%M:%S"),
                atraso,
                FALHA if atraso > LIMITE_DO_NASCIMENTO_S else OK,
            )
        )
    return medidas


__all__ = [
    "AVISO",
    "FALHA",
    "FOLGA_DO_DIARIO_S",
    "LIMITE_DO_NASCIMENTO_S",
    "OK",
    "HoraDoPad",
    "ModoDoJogador",
    "hora_do_pad",
    "modo_contra_o_ar",
]
