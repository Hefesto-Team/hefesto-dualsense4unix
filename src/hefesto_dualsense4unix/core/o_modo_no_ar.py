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

LIMITE_DO_NASCIMENTO_S = 2.0

FOLGA_DO_DIARIO_S = 0.1

_BACKENDS = ("uhid", "uinput")
_NENHUM = "nenhum"

_NOME_DO_MODO = {
    "dualsense": "modo DualSense",
    "xbox": "modo Xbox",
    "nativo": "Conexão Nativa",
    "desligado": "emulação desligada",
}
_PEDIDO = {"nativo": "pedida", "desligado": "pedida"}

_NOME_DA_MASCARA = {"dualsense": "DualSense", "xbox": "Xbox", "nintendo": "Nintendo"}


@dataclass(frozen=True)
class ModoDoJogador:
    """Uma linha por jogador: o modo pedido, o canal que ele dá e o do ar."""

    jogador: int
    pedido: str | None
    no_ar: str
    esperado: str | None
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
    """``{jogador: backend}`` dos pads no ar."""
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


_ISO = re.compile(
    r"(?P<a>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})[T ](?P<h>\d{2}):(?P<mi>\d{2}):(?P<s>\d{2})"
    r"(?:[.,](?P<f>\d{1,9}))?(?P<tz>Z|[+-]\d{2}:?\d{2})?"
)
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
    """``depois - antes``. Um dos dois sem fuso: compara o relógio de parede."""
    if (depois.tzinfo is None) != (antes.tzinfo is None):
        depois, antes = depois.replace(tzinfo=None), antes.replace(tzinfo=None)
    return (depois - antes).total_seconds()


@dataclass(frozen=True)
class _Registro:
    evento: str
    quando: datetime
    nome: str | None
    mascara: str | None
    recebido: datetime | None = None


def _registro_do_daemon(linha: str) -> _Registro | None:
    """O evento, a hora e o pad de uma linha do diário do daemon."""
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

    mascara: str | None
    hora: str
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
    """O atraso de cada pad `uinput` registrado desde o último `daemon_starting`."""
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
