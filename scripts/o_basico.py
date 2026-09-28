#!/usr/bin/env python3
"""o_basico.py — o protocolo do básico: a conferência do APARELHO.

O-BASICO-MEDIDO-01 (28/09/2026), a ação 8 da auditoria de 27/09. A meta é a
dela: *qualquer pessoa com um COSMIC, rádio, cabo e DualSense reproduz isso*.
Por isso ele é versionado, o pacote o leva, e nenhum caminho que ele mesmo lê
ou escreve fica sob a pasta de estudos (que o git ignora).

Orquestra os instrumentos de ``scripts/ensaios/`` sem reescrevê-los. Todo
subcomando segue o MESMO contrato:

1. **abre a sessão:** a pasta de saída, o ``daemon.state_full`` e a fotografia
   dos arquivos dela (``sha256`` e a cópia byte a byte numa pasta privada,
   0700, fora da pasta de saída quando ela é outra);
2. **mira por ``uniq`` e fala por jogador:** a tela e os arquivos dizem ``P1`` a
   ``P4``, nunca o endereço;
3. **declara o que mexe**, com o antes e o depois;
4. **relista a mesa no fim** (os ``uniq``, o transporte, o adaptador e os pads)
   e sai com ``rc=2`` se ela mudou no meio;
5. **confere a volta:** os ``sha256`` e os campos do estado que um passo que
   escreve pode deixar para trás. Diferença é ``rc=2``;
6. **toda saída vai para arquivo por UM mascarador**, o dono da casa
   (``core/formas_do_endereco.mascarar``), com os endereços e os seriais da
   mesa como conhecidos;
7. **grava o ``caderno-proposto.csv``** nas colunas de ``docs/data/ensaios.csv``.

rc: ``0`` verde · ``1`` vermelho · ``2`` recusado (a mesa mudou, o estado não
voltou, a bancada está tomada, falta um pré-requisito) · ``3`` não sei (algum
«não medido», ou nada verde nem vermelho).

O QUE ELE NUNCA FAZ: abrir janela, jogo ou Steam; ``pkill``; pausar o daemon;
``strace``, ``py-spy`` ou ``SIGSTOP`` no daemon.

Uso::

    o_basico.py retrato                  # só lê
    o_basico.py sessao [--bpftrace]      # só lê (a sonda pede sudo)  # (noqa-acento: o nome do subcomando é o do protocolo)
    o_basico.py eixos [--trocar-modo dualsense|xbox]
    o_basico.py entrada | movimento      # só leem
    o_basico.py saidas | som | haptica   # ESCREVEM; exigem a bancada; devolvem
    o_basico.py tudo-junto
    o_basico.py --veredito [PASTA]
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import csv
import dataclasses
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parents[1]
#: Os instrumentos que ele orquestra, e as sondas do kernel. Os dois ficam no
#: lugar em que o pacote os põe (``share/hefesto-dualsense4unix/scripts/``), e
#: nunca na pasta de estudos: ela é ignorada pelo git e não viaja.
ENSAIOS = RAIZ / "scripts" / "ensaios"
SONDAS = RAIZ / "scripts" / "sondas"
_SRC = RAIZ / "src"
if (_SRC / "hefesto_dualsense4unix").is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from hefesto_dualsense4unix.core.formas_do_endereco import mascarar
from hefesto_dualsense4unix.core.o_modo_no_ar import (
    AVISO,
    FALHA,
    LIMITE_DO_NASCIMENTO_S,
    OK,
    hora_do_pad,
    modo_contra_o_ar,
)

# ---------------------------------------------------------------------------
# O que ele chama, dito uma vez: a régua dos pacotes lê daqui
# ---------------------------------------------------------------------------

#: Os instrumentos de ``scripts/ensaios/`` que algum subcomando roda. A régua
#: 8 de ``tests/unit/test_o_basico_o_contrato.py`` confere que cada um (e cada
#: módulo que ele importa desta pasta) está em cada empacotamento.
ENSAIOS_CHAMADOS: tuple[str, ...] = (
    "quem_e_quem.py",
    "os_nos_de_som_por_controle.py",
    "os_endpoints_de_haptica.py",
    "entrada_em_repouso.py",
    "taxa_no_hidraw.py",
    "giro_e_buraco.py",
    "imu_no_cabo.py",
    "a_entrada_que_nasce_sozinha.py",
    "o_jogo_para_de_ver_o_giro.py",
    "microfone_no_cabo.py",
    "o_caminho_do_mic_no_cabo.py",
)
#: As sondas do kernel, todas atrás de ``--bpftrace``.
SONDAS_DO_BASICO: tuple[str, ...] = (
    "trava-por-pad.bt",
    "nucleo-por-processo.bt",
    "uhid-raw-request.bt",
)

#: Os arquivos dela que a volta confere (01 A7), relativos à config do Hefesto.
ARQUIVOS_DELA: tuple[str, ...] = (
    "profiles/*.json",
    "controller_masks.json",
    "gamepad_caminho.flag",
    "gamepad_emulation.flag",
    "session.json",
    "active_profile.txt",
    "maquina.json",
)

#: Os campos do estado que um passo que escreve pode deixar para trás (01 A7).
#: Por jogador, a chave é ``P<n>.<campo>``, nunca o endereço.
CAMPOS_DA_VOLTA: tuple[str, ...] = (
    "output_target_index",
    "rumble_active",
    "gamepad_emulation.caminho",
    "gamepad_emulation.por_aparelho",
    "controllers[].lightbar_rgb",
    "controllers[].brilho_da_barra",
    "controllers[].speaker.rota",
    "controllers[].speaker.volume",
    "controllers[].audio.canal_ativo",
    "controllers[].audio.mic_mudo",
    "controllers[].camada_da_usuaria",
)

ORDEM: tuple[str, ...] = (
    "retrato", "sessao", "eixos", "entrada", "saidas", "som", "haptica",  # (noqa-acento: o nome do subcomando é o do protocolo)
    "movimento", "tudo-junto",
)
#: O que precisa da bancada reservada: tudo o que escreve (01 §3.2).
ESCREVEM: frozenset[str] = frozenset({"saidas", "som", "haptica", "tudo-junto"})
#: Um vermelho só para o que depende do alvo dele (01 A11): o 1a vermelho tira
#: o alvo de quem mede por jogador; o 1b (o boot) não tira nada de agora.
DEPENDE_DO_1A: frozenset[str] = frozenset({"entrada", "saidas", "movimento", "tudo-junto"})

# Os vereditos de uma linha.
VERDE = "verde"
VERMELHO = "vermelho"
NAO_SEI = "nao_sei"
NAO_COBERTO = "nao_coberto"
NAO_SE_APLICA = "nao_se_aplica"
REGISTRO = "registro"
#: Os que decidem o rc. Registro, «não se aplica» e «não coberto» aparecem e
#: não reprovam: é o que uma máquina com um controle só mostra.
VEREDITOS_QUE_CONTAM: frozenset[str] = frozenset({VERDE, VERMELHO, NAO_SEI})

RC_VERDE, RC_VERMELHO, RC_RECUSADO, RC_NAO_SEI = 0, 1, 2, 3

#: Os eventos do diário que NÃO absolvem uma divergência entre o modo pedido e
#: o do ar. O R-04 (`vpad_recriacao_bloqueada_por_jogo`) recusa recriar o pad
#: com o jogo vivo: é a razão de o jogo rodar no modo que o perfil dele NÃO
#: pediu (o L2 de 27/09, o PRAGMATA no Xbox). A interface dela é soberana; um
#: motivo que explica a desobediência não a torna obediência.
MOTIVOS_QUE_NAO_ABSOLVEM: tuple[str, ...] = ("vpad_recriacao_bloqueada_por_jogo",)

#: A janela do boot, contada do `daemon_starting`. Os sete pads de 27/09
#: nasceram em 5,3 s; uma troca de modo pedida depois disto não é o boot.
JANELA_DO_BOOT_S = 60.0
#: A espera de um pedido de vibração: 5 ms é o prazo da régua da cura, 50 ms o
#: teto da prova no aparelho (O-PAD-VIRTUAL-ATENDE-A-VIBRACAO-DESDE-QUE-NASCE-01).
PRAZO_DA_ESPERA_US = 5_000
TETO_DA_ESPERA_US = 50_000
#: Um intervalo de entrada acima disto é um quadro perdido a 30 Hz.
INTERVALO_DE_BURACO_MS = 33.0

# As colunas de `docs/data/ensaios.csv`, na ordem dele.
COLUNAS_DO_CADERNO: tuple[str, ...] = (
    "id", "linha_id", "transporte", "degrau", "ponte", "quando", "suspeito",
    "presente", "resultado", "resultado_da_feature", "observado_por", "fonte",
    "nota", "linha_id_v1",
)
_RESULTADO_DO_VEREDITO = {VERDE: "obedece", VERMELHO: "não obedece", NAO_SEI: "inconclusivo"}


class Recusa(Exception):
    """O subcomando não pode seguir sem mentir: sai com rc=2 e o porquê."""


# ---------------------------------------------------------------------------
# Um passo: uma linha da tabela
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class Passo:
    """Uma linha medida: por subcomando, jogador, transporte e modo."""

    sub: str
    linha: str
    jogador: str
    transporte: str
    modo: str
    veredito: str
    porque: str
    comando: str = ""
    mexe: list[str] = dataclasses.field(default_factory=list)
    antes: dict[str, Any] = dataclasses.field(default_factory=dict)
    medida: dict[str, Any] = dataclasses.field(default_factory=dict)
    depois: dict[str, Any] = dataclasses.field(default_factory=dict)


def rc_dos_passos(passos: Sequence[Passo], recusas: Sequence[str]) -> int:
    """O rc de uma corrida: recusado > vermelho > não sei > verde.

    «Não sei» em qualquer linha pedida tira o verde (01 §4.10: o rc=0 só vale
    com zero vermelho e zero «não sei»). Sem nenhuma linha que conte, é
    «não sei»: nada verde nem vermelho.
    """
    if recusas:
        return RC_RECUSADO
    contam = [p.veredito for p in passos if p.veredito in VEREDITOS_QUE_CONTAM]
    if VERMELHO in contam:
        return RC_VERMELHO
    if NAO_SEI in contam or not contam:
        return RC_NAO_SEI
    return RC_VERDE


# ---------------------------------------------------------------------------
# Leituras puras (o dublê da régua passa texto, e o real passa o do aparelho)
# ---------------------------------------------------------------------------

_ISO = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2}):(\d{2})(?:[.,](\d{1,9}))?"
)


def _segundos_do_dia(achado: re.Match[str]) -> float:
    """O instante de um carimbo ISO, em segundos desde uma origem fixa.

    Só serve para DIFERENÇAS entre linhas do mesmo diário: o dia entra como
    número de dias desde o ano zero, sem fuso.
    """
    a, m, d, hh, mi, ss = (int(achado.group(i)) for i in range(1, 7))
    fracao = float("0." + (achado.group(7) or "0"))
    dias = a * 372 + m * 31 + d
    return dias * 86400 + hh * 3600 + mi * 60 + ss + fracao


def _instante_do_registro(linha: str) -> float | None:
    """O carimbo do structlog (o segundo ISO da linha do journal) ou o primeiro."""
    achados = list(_ISO.finditer(linha))
    if not achados:
        return None
    return _segundos_do_dia(achados[1] if len(achados) > 1 else achados[0])


def _desde_o_ultimo_boot(linhas: Sequence[str]) -> list[str]:
    """As linhas do diário do daemon desde o último `daemon_starting`, ele incluso."""
    inicio = 0
    for i, linha in enumerate(linhas):
        if "daemon_starting" in linha:
            inicio = i
    return list(linhas[inicio:])


def pads_no_boot(linhas_do_daemon: Sequence[str], janela_s: float = JANELA_DO_BOOT_S) -> int | None:
    """Quantos pads o daemon criou no boot: da `daemon_starting` até ``janela_s``.

    ``None`` quando o diário não tem o `daemon_starting` (não medido). É a
    linha 1b (01 A11): o multiplicador do boot, e não os pads de agora.
    """
    desde = _desde_o_ultimo_boot(linhas_do_daemon)
    if not desde or "daemon_starting" not in desde[0]:
        return None
    zero = _instante_do_registro(desde[0])
    total = 0
    for linha in desde[1:]:
        if "uhid_device_created" not in linha and "uinput_device_created" not in linha:
            continue
        quando = _instante_do_registro(linha)
        if zero is not None and quando is not None and quando - zero > janela_s:
            continue
        total += 1
    return total


_MOTIVO_DO_BLOQUEIO = re.compile(r"motivo=['\"]?troca_de_caminho:(?P<caminho>\w+)")


def bloqueios_por_jogo(linhas_do_daemon: Sequence[str]) -> list[str]:
    """Os caminhos que o R-04 recusou com o jogo vivo, desde o último boot."""
    achados: list[str] = []
    for linha in _desde_o_ultimo_boot(linhas_do_daemon):
        if not any(evento in linha for evento in MOTIVOS_QUE_NAO_ABSOLVEM):
            continue
        motivo = _MOTIVO_DO_BLOQUEIO.search(linha)
        if motivo is None:
            with contextlib.suppress(ValueError):
                dado = json.loads(linha[linha.find("{"):])
                motivo_json = str(dado.get("motivo") or "")
                if motivo_json.startswith("troca_de_caminho:"):
                    achados.append(motivo_json.split(":", 1)[1])
                    continue
            achados.append("?")
            continue
        achados.append(motivo.group("caminho"))
    return achados


@dataclasses.dataclass(frozen=True)
class PadNoKernel:
    """Um nó principal de pad do produto em `/proc/bus/input/devices`."""

    nome: str
    vendor: str
    product: str
    phys: str
    uniq: str
    sysfs: str
    handlers: str
    backend: str
    jogador: int | None


_MARCA_DO_UHID = re.compile(r"\(Hefesto P(\d+)\)\s*$")


def _nomes_dos_pads_uinput() -> dict[str, tuple[str, str, str]]:
    """``{nome: (máscara, vendor, product)}`` das máscaras do `uinput`, lidos do produto."""
    try:
        from hefesto_dualsense4unix.integrations.uinput_gamepad import FLAVORS
    except Exception:  # sem o evdev no interpretador: a leitura segue sem eles
        return {}
    return {
        str(dados["name"]): (mascara, f"{int(dados['vendor']):04x}", f"{int(dados['product']):04x}")
        for mascara, dados in FLAVORS.items()
    }


def pads_do_produto(texto: str, nomes_uinput: Mapping[str, Any] | None = None) -> list[PadNoKernel]:
    """Os pads do produto em `/proc/bus/input/devices` — só os nós PRINCIPAIS.

    O pad `uhid` se reconhece pelo nome carimbado (``(Hefesto Pn)``); os nós de
    movimento e de toque dele têm um sufixo depois do carimbo e ficam de fora.
    O pad `uinput` se reconhece pelo nome de uma das máscaras do produto E por
    não ter pai HID (mora direto em ``/devices/virtual/input/``): um DualSense
    Edge de verdade tem o mesmo nome, e mora sob o HID dele.
    """
    uinput = _nomes_dos_pads_uinput() if nomes_uinput is None else nomes_uinput
    pads: list[PadNoKernel] = []
    for bloco in re.split(r"\n\s*\n", texto):
        campos: dict[str, str] = {}
        for linha in bloco.splitlines():
            if len(linha) < 3 or linha[1] != ":":
                continue
            letra, resto = linha[0], linha[3:]
            if letra == "I":
                for par in resto.split():
                    if "=" in par:
                        chave, valor = par.split("=", 1)
                        campos[chave.lower()] = valor.lower()
            elif letra in "NPSUH":
                chave, _, valor = resto.partition("=")
                campos[chave.strip().lower()] = valor.strip().strip('"')
        nome = campos.get("name", "")
        if not nome:
            continue
        sysfs = campos.get("sysfs", "")
        marca = _MARCA_DO_UHID.search(nome)
        if marca is not None:
            backend, jogador = "uhid", int(marca.group(1))
        elif nome in uinput and re.fullmatch(r"/devices/virtual/input/input\d+", sysfs):
            backend, jogador = "uinput", None
        else:
            continue
        pads.append(
            PadNoKernel(
                nome=nome,
                vendor=campos.get("vendor", ""),
                product=campos.get("product", ""),
                phys=campos.get("phys", ""),
                uniq=campos.get("uniq", ""),
                sysfs=sysfs,
                handlers=campos.get("handlers", ""),
                backend=backend,
                jogador=jogador,
            )
        )
    return pads


#: A chave do `@hw` que o resumo espera na sonda: sem o `pid` o jogo e a Steam
#: não se separam (C2 da contraprova).
_CHAVE_DO_HW = re.compile(r"@hw\[(?P<chave>[^\]]+)\]\s*=")


def ordem_da_chave_do_hw(sonda: str) -> list[str]:
    """Os campos da chave do `@hw` na sonda, na ordem em que ela os grava."""
    achado = _CHAVE_DO_HW.search(sonda)
    if achado is None:
        return []
    ordem: list[str] = []
    for termo in achado.group("chave").split(","):
        termo = termo.strip()
        if termo == "pid":
            ordem.append("pid")
        elif termo == "comm":
            ordem.append("comm")
        elif "i_rdev" in termo:
            ordem.append("minor")
        elif termo in ("arg2", "size"):
            ordem.append("bytes")
        else:
            ordem.append(termo)
    return ordem


def escritas_por_dono(
    saida_da_sonda: str,
    ordem: Sequence[str],
    dono_do_pid: Callable[[int], str],
) -> Counter[tuple[str, str, int, int]]:
    """``(dono, fio, minor, bytes) -> vezes`` de cada `hidraw_write`.

    O dono vem do PROCESSO (o `pid` da chave), casado pela árvore: o jogo, a
    Steam, o daemon, o teclado na tela. Sem o `pid` na chave o dono é «?», e
    o fio de mesmo nome da Steam e do jogo cai na mesma conta — é o que a
    régua 9 morde.
    """
    contagem: Counter[tuple[str, str, int, int]] = Counter()
    for achado in re.finditer(r"@hw\[(?P<chave>[^\]]+)\]:\s*(?P<n>\d+)", saida_da_sonda):
        partes = [p.strip() for p in achado.group("chave").split(", ")]
        if len(partes) != len(ordem):
            continue
        campo = dict(zip(ordem, partes, strict=True))
        dono = "?"
        if "pid" in campo and campo["pid"].isdigit():
            dono = dono_do_pid(int(campo["pid"]))
        with contextlib.suppress(ValueError):
            contagem[(dono, campo.get("comm", "?"), int(campo.get("minor", "-1")),
                      int(campo.get("bytes", "-1")))] += int(achado.group("n"))
    return contagem


def dono_pela_arvore(
    processos: Mapping[int, tuple[int, str]],
    *,
    jogo: Iterable[int] = (),
    daemon: Iterable[int] = (),
    teclado: Iterable[int] = (),
) -> Callable[[int], str]:
    """O dono de um pid, subindo pela árvore: jogo, steam, daemon, teclado na tela."""
    papeis: dict[int, str] = {}
    for papel, pids in (("jogo", jogo), ("daemon", daemon), ("teclado_na_tela", teclado)):
        for pid in pids:
            papeis.setdefault(int(pid), papel)

    def dono(pid: int) -> str:
        vistos: set[int] = set()
        atual = pid
        while atual and atual not in vistos:
            if atual in papeis:
                return papeis[atual]
            pai, comm = processos.get(atual, (0, ""))
            if comm in ("steam", "steamwebhelper"):
                return "steam"
            vistos.add(atual)
            atual = pai
        return "outro" if pid in processos else "?"

    return dono


def _hex12(valor: object) -> str | None:
    """Os doze hex de um endereço em qualquer grafia (minúsculos), ou None."""
    if not isinstance(valor, str):
        return None
    limpo = re.sub(r"[:\-_. ]", "", valor.strip()).lower()
    return limpo if re.fullmatch(r"[0-9a-f]{12}", limpo) else None


def chave_mascarada(valor: object) -> str | None:
    """O endereço na máscara da casa, com dois-pontos: a chave de casar sem expor.

    O instrumento imprime o endereço já mascarado, e o estado traz o cru; os
    dois lados passam por aqui e casam pelo que sobra (o fabricante e o último
    octeto). Dois controles que colidem nessa chave viram «não sei», nunca um
    palpite.
    """
    doze = _hex12(valor)
    if doze is None:
        return None
    return str(mascarar(":".join(doze[i : i + 2] for i in range(0, 12, 2))))


_ENDERECO_EM_TEXTO = re.compile(
    r"(?<![0-9A-Fa-f])(?:[0-9A-Fa-f]{2}[:\-_]){5}[0-9A-Fa-f]{2}(?![0-9A-Fa-f])"
    r"|(?<![0-9A-Za-z])[0-9A-Fa-f]{12}(?![0-9A-Za-z])"
)


def enderecos_em(dado: object) -> set[str]:
    """Todo endereço de aparelho que aparece num JSON (valores e chaves).

    Os cartões por controle dos perfis e o `maquina.json` são chaveados pelo
    endereço, e o estado o traz em vários campos: tudo vira conhecido do
    mascarador, que assim pega até a forma invertida com espaço.
    """
    achados: set[str] = set()
    pilha: list[object] = [dado]
    while pilha:
        atual = pilha.pop()
        if isinstance(atual, Mapping):
            for chave, valor in atual.items():
                pilha.append(chave)
                pilha.append(valor)
        elif isinstance(atual, (list, tuple, set)):
            pilha.extend(atual)
        elif isinstance(atual, str) and len(atual) <= 4096:
            for achado in _ENDERECO_EM_TEXTO.finditer(atual):
                achados.add(achado.group(0))
    return achados


def _dict(valor: object) -> dict[str, Any]:
    return dict(valor) if isinstance(valor, Mapping) else {}


def _lista(valor: object) -> list[dict[str, Any]]:
    return [dict(x) for x in valor if isinstance(x, Mapping)] if isinstance(valor, list) else []


def _textos(valor: object) -> list[str]:
    return [str(x) for x in valor] if isinstance(valor, list) else []


def controles_na_mesa(estado: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Os controles conectados com número de jogador, em ordem de jogador."""
    fora = [
        c for c in _lista(estado.get("controllers"))
        if c.get("connected") is not False and isinstance(c.get("player"), int)
    ]
    return sorted(fora, key=lambda c: int(c["player"]))


def transporte_de(controle: Mapping[str, Any]) -> str:
    return {"usb": "cabo", "bt": "radio"}.get(str(controle.get("transport") or ""), "?")


def modo_de(estado: Mapping[str, Any]) -> str:
    if estado.get("native_mode") is True:
        return "nativo"
    emulacao = _dict(estado.get("gamepad_emulation"))
    if emulacao.get("enabled") is not True:
        return "desligado"
    return str(emulacao.get("caminho") or "?")


def mesa_de(estado: Mapping[str, Any], dispositivos: str) -> dict[str, Any]:
    """A mesa: os controles por endereço, os pads por jogador, os pads no kernel."""
    controles = {
        str(c.get("uniq")): {
            "jogador": c.get("player"),
            "transporte": c.get("transport"),
            "adaptador": c.get("adaptador"),
        }
        for c in controles_na_mesa(estado)
        if c.get("uniq")
    }
    per_vpad = _lista(_dict(estado.get("rumble_ff")).get("per_vpad"))
    pads = sorted([p.get("player"), p.get("backend")] for p in per_vpad)
    no_kernel = sorted(p.backend for p in pads_do_produto(dispositivos))
    return {"controles": controles, "pads": pads, "pads_no_kernel": no_kernel}


def diferencas_da_mesa(inicio: Mapping[str, Any], fim: Mapping[str, Any]) -> list[str]:
    """O que mudou na mesa entre o começo e o fim, por jogador e sem endereço."""
    difs: list[str] = []
    a, b = _dict(inicio.get("controles")), _dict(fim.get("controles"))
    for uniq in sorted(set(a) | set(b)):
        if uniq not in b:
            difs.append(f"o P{a[uniq].get('jogador')} saiu da mesa")
        elif uniq not in a:
            difs.append(f"um controle entrou na mesa como P{b[uniq].get('jogador')}")
        elif a[uniq] != b[uniq]:
            mudou = sorted(k for k in a[uniq] if a[uniq].get(k) != b[uniq].get(k))
            difs.append(f"o P{a[uniq].get('jogador')} mudou de {', '.join(mudou)}")
    if inicio.get("pads") != fim.get("pads"):
        difs.append(f"os pads do daemon eram {inicio.get('pads')} e são {fim.get('pads')}")
    if inicio.get("pads_no_kernel") != fim.get("pads_no_kernel"):
        difs.append(
            f"os pads no kernel eram {inicio.get('pads_no_kernel')} e são {fim.get('pads_no_kernel')}"
        )
    return difs


def campos_da_volta(estado: Mapping[str, Any]) -> dict[str, Any]:
    """Os :data:`CAMPOS_DA_VOLTA` do estado, por jogador."""
    emulacao = _dict(estado.get("gamepad_emulation"))
    fora: dict[str, Any] = {
        "output_target_index": estado.get("output_target_index"),
        "rumble_active": estado.get("rumble_active"),
        "gamepad_emulation.caminho": emulacao.get("caminho"),
        "gamepad_emulation.por_aparelho": dict(sorted(_dict(emulacao.get("por_aparelho")).items())),
    }
    for c in controles_na_mesa(estado):
        p = f"P{c['player']}"
        fora[f"{p}.lightbar_rgb"] = c.get("lightbar_rgb")
        fora[f"{p}.brilho_da_barra"] = c.get("brilho_da_barra")
        fora[f"{p}.speaker.rota"] = _dict(c.get("speaker")).get("rota")
        fora[f"{p}.speaker.volume"] = _dict(c.get("speaker")).get("volume")
        fora[f"{p}.audio.canal_ativo"] = _dict(c.get("audio")).get("canal_ativo")
        fora[f"{p}.audio.mic_mudo"] = _dict(c.get("audio")).get("mic_mudo")
        if "camada_da_usuaria" in c:
            fora[f"{p}.camada_da_usuaria"] = c.get("camada_da_usuaria")
    return fora


def perfis_por_nome(copias: Mapping[str, bytes]) -> dict[str, dict[str, Any]]:
    """``{nome do perfil: perfil}`` das cópias de `profiles/*.json`."""
    fora: dict[str, dict[str, Any]] = {}
    for rel, dado in copias.items():
        if not rel.startswith("profiles/") or not rel.endswith(".json"):
            continue
        with contextlib.suppress(ValueError, UnicodeDecodeError):
            perfil = json.loads(dado.decode("utf-8"))
            if isinstance(perfil, dict) and isinstance(perfil.get("name"), str):
                fora[perfil["name"]] = perfil
    return fora


def caminho_do_perfil(perfil: Mapping[str, Any] | None) -> str | None:
    caminho = _dict(_dict(perfil).get("mode")).get("caminho")
    return caminho if caminho in ("dualsense", "xbox") else None


# ---------------------------------------------------------------------------
# A máquina: o mundo, lido (o dublê da régua troca ESTA classe inteira)
# ---------------------------------------------------------------------------


class Maquina:
    """Tudo o que o protocolo lê ou escreve fora dele mesmo.

    O dublê das réguas é uma subclasse que troca estes métodos, e publica o
    que eles publicam: o ``state_full`` no formato do daemon, o diário no
    formato do ``journalctl -o short-iso-precise``, o ``/proc/bus/input/devices``
    como o kernel o escreve.
    """

    TETO_DO_IPC_S = 8.0

    # -- o daemon -------------------------------------------------------------

    def chamar(self, metodo: str, params: Mapping[str, Any] | None = None) -> Any:
        from hefesto_dualsense4unix.cli.ipc_client import IpcClient

        async def _uma() -> Any:
            async with IpcClient.connect(timeout=2.0) as cliente:
                return await cliente.call(metodo, dict(params or {}), timeout=self.TETO_DO_IPC_S)

        return asyncio.run(_uma())

    def estado(self) -> dict[str, Any] | None:
        try:
            estado = self.chamar("daemon.state_full")
        except Exception:
            return None
        return estado if isinstance(estado, dict) else None

    # -- os diários -----------------------------------------------------------

    def _journal(self, *argv: str) -> list[str]:
        rc, texto = self.rodar(["journalctl", "--no-pager", "-o", "short-iso-precise", *argv], 30.0)
        return texto.splitlines() if rc == 0 else []

    def diario_do_daemon(self) -> list[str]:
        return self._journal("--user", "-u", "hefesto-dualsense4unix", "-b")

    def diario_do_kernel(self) -> list[str]:
        return self._journal("-k", "-b")

    def diario_do_sistema_desde(self, epoca: float) -> list[str]:
        return self._journal("-b", "--since", f"@{int(epoca)}")

    def kernel_desde(self, epoca: float) -> list[str]:
        return self._journal("-k", "--since", f"@{int(epoca)}")

    # -- o kernel, o /proc e o /sys --------------------------------------------

    def ler(self, caminho: str | Path) -> str:
        try:
            return Path(caminho).read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def dispositivos_de_entrada(self) -> str:
        return self.ler("/proc/bus/input/devices")

    def processos(self) -> dict[int, tuple[int, str]]:
        """``{pid: (ppid, comm)}`` pelo `/proc`, sem `pgrep` (que casa o próprio shell)."""
        fora: dict[int, tuple[int, str]] = {}
        with contextlib.suppress(OSError):
            for nome in os.listdir("/proc"):
                if not nome.isdigit():
                    continue
                stat = self.ler(f"/proc/{nome}/stat")
                achado = re.match(r"\d+ \((?P<comm>.*)\) \S (?P<ppid>\d+)", stat)
                if achado:
                    fora[int(nome)] = (int(achado.group("ppid")), achado.group("comm"))
        return fora

    def pids_do_jogo(self, appid: int | str) -> list[int]:
        """Os pids com ``SteamAppId=<appid>`` no ambiente (a árvore do jogo)."""
        alvo = f"SteamAppId={appid}".encode()
        fora: list[int] = []
        for pid in self.processos():
            with contextlib.suppress(OSError):
                if alvo in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
                    fora.append(pid)
        return fora

    def fds_de(self, pid: int) -> list[str]:
        fora: list[str] = []
        with contextlib.suppress(OSError):
            for fd in os.listdir(f"/proc/{pid}/fd"):
                with contextlib.suppress(OSError):
                    fora.append(os.readlink(f"/proc/{pid}/fd/{fd}"))
        return fora

    def baterias(self) -> dict[str, tuple[str, str]]:
        """``{12 hex: (capacidade, estado)}`` das baterias que o kernel publica."""
        fora: dict[str, tuple[str, str]] = {}
        base = Path("/sys/class/power_supply")
        with contextlib.suppress(OSError):
            for entrada in sorted(base.iterdir()):
                if not entrada.name.startswith("ps-controller-battery-"):
                    continue
                doze = _hex12(entrada.name.removeprefix("ps-controller-battery-"))
                if doze:
                    fora[doze] = (
                        self.ler(entrada / "capacity").strip(),
                        self.ler(entrada / "status").strip(),
                    )
        return fora

    def adaptadores(self) -> list[dict[str, str]]:
        """O chip de cada adaptador de rádio: ``vendor:product`` e o driver."""
        fora: list[dict[str, str]] = []
        base = Path("/sys/class/bluetooth")
        with contextlib.suppress(OSError):
            for hci in sorted(base.iterdir()):
                if not re.fullmatch(r"hci\d+", hci.name):
                    continue
                dispositivo = (hci / "device").resolve()
                driver = ""
                with contextlib.suppress(OSError):
                    driver = (dispositivo / "driver").resolve().name
                usb = dispositivo
                while usb != usb.parent and not (usb / "idVendor").exists():
                    usb = usb.parent
                par = ""
                if (usb / "idVendor").exists():
                    par = f"{self.ler(usb / 'idVendor').strip()}:{self.ler(usb / 'idProduct').strip()}"
                fora.append({"hci": hci.name, "chip": par or "?", "driver": driver or "?"})
        return fora

    def secure_boot(self) -> str:
        base = Path("/sys/firmware/efi/efivars")
        with contextlib.suppress(OSError):
            for arquivo in base.glob("SecureBoot-*"):
                dado = arquivo.read_bytes()
                return "ligado" if dado and dado[-1] == 1 else "desligado"
        return "sem EFI" if not base.exists() else "não lido"

    # -- a config dela --------------------------------------------------------

    def config_dela(self) -> Path:
        from hefesto_dualsense4unix.utils.xdg_paths import config_dir

        return Path(config_dir())

    # -- o servidor de som ------------------------------------------------------

    def pactl(self, *argv: str) -> str | None:
        """Uma leitura do `pactl` em C, pelo leitor do produto; None se não respondeu."""
        from hefesto_dualsense4unix.integrations.retrato_do_som import ler_do_servidor

        try:
            resposta = ler_do_servidor(["pactl", *argv])
            return resposta if isinstance(resposta, str) else None
        except Exception:
            return None

    # -- processos filhos -------------------------------------------------------

    def rodar(
        self, argv: Sequence[str], teto_s: float, ambiente: Mapping[str, str] | None = None
    ) -> tuple[int, str]:
        """Roda um comando e devolve ``(rc, stdout+stderr)``. Nunca levanta."""
        env = {**os.environ, "LC_ALL": "C", **dict(ambiente or {})}
        try:
            feito = subprocess.run(
                list(argv), capture_output=True, text=True, timeout=teto_s, check=False, env=env
            )
        except FileNotFoundError:
            return 127, f"{argv[0]}: não existe nesta máquina"
        except subprocess.TimeoutExpired as erro:
            saida = (erro.stdout or "") if isinstance(erro.stdout, str) else ""
            return 124, saida + f"\n(estourou o teto de {teto_s:g} s)"
        except OSError as erro:
            return 126, str(erro)
        return feito.returncode, (feito.stdout or "") + (feito.stderr or "")

    def existe(self, programa: str) -> bool:
        return shutil.which(programa) is not None

    def subir(self, argv: Sequence[str]) -> Any:
        """Um processo em segundo plano (uma sonda, um tocador); ``colher`` o termina."""
        return subprocess.Popen(
            list(argv), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            env={**os.environ, "LC_ALL": "C"},
        )

    def colher(self, processo: Any, teto_s: float) -> str:
        try:
            saida, _ = processo.communicate(timeout=teto_s)
        except subprocess.TimeoutExpired:
            processo.kill()
            saida, _ = processo.communicate()
        return saida or ""

    def regra_do_input_remapper(self) -> bool:
        return Path("/usr/lib/udev/rules.d/60-input-remapper-daemon.rules").exists()

    # -- o aparelho: o que escreve ----------------------------------------------

    def leitor_dos_fisicos(self) -> LeitorDosFisicos:
        leitor = LeitorDosFisicos()
        leitor.abrir()
        return leitor

    def hidraw_do_pad_uhid(self, jogador: int) -> str | None:
        base = Path("/sys/class/hidraw")
        with contextlib.suppress(OSError):
            for no in sorted(base.iterdir()):
                uevent = (no / "device" / "uevent").read_text(encoding="utf-8", errors="replace")
                if f"(Hefesto P{jogador})" in uevent:
                    return f"/dev/{no.name}"
        return None

    def escrever_no_pad(self, caminho: str, dados: bytes) -> bool:
        """Um relatório de saída no hidraw do pad — o que um jogo mandaria."""
        try:
            fd = os.open(caminho, os.O_WRONLY)
        except OSError:
            return False
        try:
            os.write(fd, dados)
        except OSError:
            return False
        finally:
            os.close(fd)
        return True

    def pulso_de_ff(self, pad: PadNoKernel, segundos: float) -> bool:
        """Um efeito FF_RUMBLE no evdev do pad, por ``segundos``, e o efeito apagado."""
        evento = next((h for h in pad.handlers.split() if h.startswith("event")), None)
        if evento is None:
            return False
        try:
            import evdev
            from evdev import ecodes, ff
        except ImportError:
            return False
        try:
            dispositivo = evdev.InputDevice(f"/dev/input/{evento}")
        except OSError:
            return False
        try:
            efeito = ff.Effect(
                ecodes.FF_RUMBLE, -1, 0, ff.Trigger(0, 0), ff.Replay(int(segundos * 1000), 0),
                ff.EffectType(ff_rumble_effect=ff.Rumble(strong_magnitude=0xC000, weak_magnitude=0xC000)),
            )
            numero = dispositivo.upload_effect(efeito)
            dispositivo.write(ecodes.EV_FF, numero, 1)
            time.sleep(segundos)
            dispositivo.write(ecodes.EV_FF, numero, 0)
            dispositivo.erase_effect(numero)
            return True
        except OSError:
            return False
        finally:
            dispositivo.close()

    def gravar_som(self, fonte: str, segundos: float) -> list[int]:
        """Amostras mono de ``fonte``, com latência explícita (sem ela o gravador atrasa 2 s)."""
        if not self.existe("parec"):
            return []
        try:
            feito = subprocess.run(
                ["timeout", f"{segundos:g}", "parec", f"--device={fonte}", "--latency-msec=50",
                 "--format=s16le", "--rate=48000", "--channels=1", "--raw"],
                capture_output=True, timeout=segundos + 5.0, check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return []
        dado = feito.stdout
        return [int.from_bytes(dado[i : i + 2], "little", signed=True) for i in range(0, len(dado) - 1, 2)]

    def tocar(self, sink: str, wav: Path) -> Any:
        if not self.existe("paplay"):
            return None
        return subprocess.Popen(
            ["paplay", f"--device={sink}", "--latency-msec=50", str(wav)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def esperar(self, processo: Any, teto_s: float) -> None:
        if processo is None:
            return
        with contextlib.suppress(subprocess.TimeoutExpired):
            processo.wait(timeout=teto_s)
        if processo.poll() is None:
            processo.terminate()

    # -- o relógio --------------------------------------------------------------

    def agora(self) -> float:
        return time.time()

    def dormir(self, segundos: float) -> None:
        time.sleep(max(0.0, segundos))


def pasta_privada() -> Path:
    """``${XDG_STATE_HOME:-~/.local/state}/hefesto-dualsense4unix/o-basico``."""
    from hefesto_dualsense4unix.utils.xdg_paths import state_dir

    return Path(state_dir()) / "o-basico"


def caminhos_que_ele_mesmo_abre() -> dict[str, Path]:
    """Todo caminho fixo que o protocolo lê ou escreve por conta própria.

    A régua 7 confere que nenhum fica sob a pasta de estudos (ignorada pelo
    git). O ``--saida`` é de quem chama, e não entra aqui.
    """
    fora: dict[str, Path] = {"ensaios": ENSAIOS, "sondas": SONDAS, "saida_padrao": pasta_privada()}
    for nome in SONDAS_DO_BASICO:
        fora[f"sonda:{nome}"] = SONDAS / nome
    for nome in ENSAIOS_CHAMADOS:
        fora[f"ensaio:{nome}"] = ENSAIOS / nome
    return fora


def _pasta_segura(caminho: Path) -> Path:
    caminho.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):
        os.chmod(caminho, 0o700)
    return caminho


# ---------------------------------------------------------------------------
# A sessão: o contrato comum
# ---------------------------------------------------------------------------


class Sessao:
    """Uma corrida de um subcomando, com o contrato do 01 §3."""

    def __init__(
        self,
        maquina: Maquina,
        sub: str,
        *,
        saida: Path | None = None,
        comando: str = "",
        jogadores: str = "todos",
    ) -> None:
        self.maquina = maquina
        self.sub = sub
        self.comando = comando
        self.carimbo = time.strftime("%Y-%m-%dT%H%M%S", time.localtime(maquina.agora()))
        self.privada = _pasta_segura(pasta_privada() / self.carimbo)
        self.saida = _pasta_segura(Path(saida)) if saida else self.privada
        self.jogadores = jogadores
        self.passos: list[Passo] = []
        self.recusas: list[str] = []
        self.mexeu: list[dict[str, Any]] = []
        self.conhecidos: set[str] = set()
        self.estado_inicio: dict[str, Any] = {}
        self.mesa_inicio: dict[str, Any] = {}
        self.sha_antes: dict[str, str] = {}
        self.copias: dict[str, bytes] = {}
        self.volta_antes: dict[str, Any] = {}
        self.bancada_reservada = False
        self.reiniciar_o_daemon_no_fim = False

    # -- o mascarador: UM, na saída de tudo ------------------------------------

    def conhecer(self, *dados: object) -> None:
        for dado in dados:
            self.conhecidos.update(enderecos_em(dado))
            if isinstance(dado, Mapping):
                for c in _lista(dado.get("controllers")):
                    serial = c.get("serial")
                    if isinstance(serial, str) and serial.strip():
                        self.conhecidos.add(serial.strip())

    def mascarado(self, texto: str) -> str:
        return str(mascarar(texto, sorted(self.conhecidos)))

    def dizer(self, texto: str) -> None:
        print(self.mascarado(texto), flush=True)

    def gravar(self, rel: str, texto: str) -> Path:
        caminho = self.saida / rel
        _pasta_segura(caminho.parent)
        caminho.write_text(self.mascarado(texto), encoding="utf-8")
        with contextlib.suppress(OSError):
            os.chmod(caminho, 0o600)
        return caminho

    def gravar_json(self, rel: str, dado: object) -> Path:
        return self.gravar(rel, json.dumps(dado, ensure_ascii=False, indent=1, default=str) + "\n")

    # -- abrir: o estado, a mesa, a fotografia ----------------------------------

    def abrir(self) -> bool:
        estado = self.maquina.estado()
        if estado is None:
            self.recusar("o daemon não responde ao daemon.state_full")
            return False
        self.estado_inicio = estado
        self.conhecer(estado)
        self.conhecer({"baterias": list(self.maquina.baterias())})
        self.mesa_inicio = mesa_de(estado, self.maquina.dispositivos_de_entrada())
        self.sha_antes = self.fotografar(copiar=True)
        for dado in self.copias.values():
            with contextlib.suppress(ValueError, UnicodeDecodeError):
                self.conhecer(json.loads(dado.decode("utf-8")))
        self.volta_antes = self.campos_da_volta_agora(estado)
        self.gravar_json("antes/estado.json", estado)
        self.gravar_json("antes/mesa.json", self.mesa_inicio)
        self.gravar_json("antes/volta.json", self.volta_antes)
        self.gravar("antes/sha256.txt", "".join(f"{h}  {rel}\n" for rel, h in sorted(self.sha_antes.items())))
        for rel, dado in sorted(self.copias.items()):
            self.gravar(f"antes/arquivos-mascarados/{rel}", dado.decode("utf-8", errors="replace"))
        return True

    def fotografar(self, *, copiar: bool = False) -> dict[str, str]:
        """O ``sha256`` dos arquivos dela; com ``copiar``, a cópia byte a byte na pasta privada.

        A cópia crua tem os endereços (os cartões por controle são chaveados
        por eles): ela mora na pasta privada, 0700, e nunca na de saída quando
        a de saída é outra (C11 da contraprova). Na de saída ficam o ``sha256``
        e a cópia mascarada.
        """
        base = self.maquina.config_dela()
        achados: dict[str, str] = {}
        for padrao in ARQUIVOS_DELA:
            for arquivo in sorted(base.glob(padrao)):
                if not arquivo.is_file():
                    continue
                try:
                    dado = arquivo.read_bytes()
                except OSError:
                    continue
                rel = arquivo.relative_to(base).as_posix()
                achados[rel] = hashlib.sha256(dado).hexdigest()
                if copiar:
                    self.copias[rel] = dado
                    copia = self.privada / "antes" / "copia" / rel
                    _pasta_segura(copia.parent)
                    copia.write_bytes(dado)
                    with contextlib.suppress(OSError):
                        os.chmod(copia, 0o600)
        return achados

    def campos_da_volta_agora(self, estado: Mapping[str, Any]) -> dict[str, Any]:
        fora = campos_da_volta(estado)
        fora["som.saida_padrao"] = (self.maquina.pactl("get-default-sink") or "").strip() or None
        fora["som.fonte_padrao"] = (self.maquina.pactl("get-default-source") or "").strip() or None
        return fora

    # -- o fecho: a relistagem e a volta ----------------------------------------

    def relistar_e_conferir(self) -> None:
        """A mesa do fim contra a do começo. Mudou no meio: rc=2, sem verde."""
        estado = self.maquina.estado()
        if estado is None:
            self.recusar("o daemon não respondeu na relistagem do fim")
            return
        self.conhecer(estado)
        fim = mesa_de(estado, self.maquina.dispositivos_de_entrada())
        self.gravar_json("depois/mesa.json", fim)
        difs = diferencas_da_mesa(self.mesa_inicio, fim)
        if difs:
            self.recusar("a mesa mudou no meio da medida: " + "; ".join(difs))

    def conferir_a_volta(self) -> list[str]:
        """Os ``sha256`` e os :data:`CAMPOS_DA_VOLTA` contra o começo."""
        difs: list[str] = []
        depois = self.fotografar()
        for rel in sorted(set(self.sha_antes) | set(depois)):
            if self.sha_antes.get(rel) != depois.get(rel):
                if rel not in depois:
                    difs.append(f"o arquivo {rel} sumiu")
                elif rel not in self.sha_antes:
                    difs.append(f"o arquivo {rel} nasceu")
                else:
                    difs.append(f"o arquivo {rel} mudou")
        estado = self.maquina.estado()
        if estado is None:
            difs.append("o daemon não respondeu para a volta")
        else:
            agora = self.campos_da_volta_agora(estado)
            for chave in sorted(set(self.volta_antes) | set(agora)):
                if self.volta_antes.get(chave) != agora.get(chave):
                    difs.append(f"{chave}: era {self.volta_antes.get(chave)!r}, ficou {agora.get(chave)!r}")
        self.gravar("depois/sha256.txt", "".join(f"{h}  {rel}\n" for rel, h in sorted(depois.items())))
        self.gravar_json("depois/volta.json", difs)
        return difs

    # -- os passos --------------------------------------------------------------

    def recusar(self, porque: str) -> None:
        self.recusas.append(porque)
        self.dizer(f"RECUSO: {porque}")

    def anotar(self, passo: Passo) -> None:
        pedidos = {x.strip().upper() for x in self.jogadores.split(",")}
        if self.jogadores != "todos" and passo.jogador.startswith("P") and passo.jogador not in pedidos:
            return
        self.passos.append(passo)
        marca = {VERDE: "VERDE", VERMELHO: "VERMELHO", NAO_SEI: "NÃO SEI", REGISTRO: "registro",
                 NAO_SE_APLICA: "não se aplica", NAO_COBERTO: "não coberto"}.get(passo.veredito, passo.veredito)
        self.dizer(f"  [{marca:>13}] {passo.sub} · {passo.linha} · {passo.jogador} · {passo.porque}")
        caminho = self.saida / "passos.jsonl"
        with caminho.open("a", encoding="utf-8") as arquivo:
            arquivo.write(self.mascarado(json.dumps(dataclasses.asdict(passo), ensure_ascii=False, default=str)) + "\n")

    def declarar(self, o_que: str, antes: object, depois: object = None, voltou: bool | None = None) -> None:
        """O que o passo mexeu, com o antes e o depois (01 §3.4)."""
        self.mexeu.append({"o_que": o_que, "antes": antes, "depois": depois, "voltou": voltou})

    # -- os ensaios ---------------------------------------------------------------

    def rodar_ensaio(self, nome: str, *args: str, teto_s: float = 120.0) -> tuple[int, str]:
        """Roda ``scripts/ensaios/<nome>``, grava a saída MASCARADA e a devolve crua em memória.

        A crua nunca toca o disco: ela serve só para ler o ``--json`` do
        ensaio. O arquivo e o terminal recebem o texto mascarado.
        """
        ambiente = {}
        if (_SRC / "hefesto_dualsense4unix").is_dir():
            ambiente["PYTHONPATH"] = os.pathsep.join(
                [str(_SRC), *(p for p in [os.environ.get("PYTHONPATH", "")] if p)]
            )
        rc, texto = self.maquina.rodar([sys.executable, str(ENSAIOS / nome), *args], teto_s, ambiente)
        base = nome.removesuffix(".py")
        self.gravar(f"ensaios/{base}.txt", f"$ {nome} {' '.join(args)}\nrc={rc}\n{texto}")
        return rc, texto

    # -- a bancada ------------------------------------------------------------------

    def reservar_a_bancada(self) -> None:
        """Reserva a bancada antes de escrever (01 §3.2); ocupada é recusa, nunca contorno."""
        bancada = RAIZ / "scripts" / "bancada.sh"
        if not bancada.is_file():
            self.dizer("  (esta instalação não tem o semáforo da bancada: sigo sem reserva, declarado)")
            return
        rc, texto = self.maquina.rodar(["bash", str(bancada), "exigir"], 10.0)
        if rc != 0:
            raise Recusa("a bancada está tomada: " + texto.strip().splitlines()[-1] if texto.strip() else "a bancada está tomada")
        rc, texto = self.maquina.rodar(
            ["bash", str(bancada), "reservar", f"o_basico {self.sub}", "--horas", "1"],
            10.0,
            {"HEFESTO_BANCADA_PID": str(os.getpid())},
        )
        if rc != 0:
            raise Recusa("não consegui reservar a bancada: " + texto.strip())
        self.bancada_reservada = True

    def liberar_a_bancada(self) -> None:
        if self.bancada_reservada:
            self.maquina.rodar(["bash", str(RAIZ / "scripts" / "bancada.sh"), "liberar"], 10.0)
            self.bancada_reservada = False

    # -- fechar ------------------------------------------------------------------------

    def fechar(self) -> int:
        self.liberar_a_bancada()
        rc = rc_dos_passos(self.passos, self.recusas)
        self.gravar("caderno-proposto.csv", caderno(self.passos, self.carimbo, self.comando))
        contagem = Counter(p.veredito for p in self.passos)
        self.gravar_json(
            "resumo.json",
            {
                "sub": self.sub,
                "rc": rc,
                "carimbo": self.carimbo,
                "comando": self.comando,
                "recusas": self.recusas,
                "mexeu": self.mexeu,
                "contagem": dict(contagem),
                "modo": modo_de(self.estado_inicio) if self.estado_inicio else "?",
            },
        )
        self.dizer(
            f"\n{self.sub}: rc={rc} · "
            + " · ".join(f"{k}={v}" for k, v in sorted(contagem.items()))
            + (f" · recusas={len(self.recusas)}" if self.recusas else "")
        )
        self.dizer(f"gravado em {self.saida}")
        return rc


def caderno(passos: Sequence[Passo], carimbo: str, comando: str) -> str:
    """O ``caderno-proposto.csv``: uma linha por medida, nas colunas do caderno da casa."""
    saida = io.StringIO()
    escritor = csv.writer(saida, lineterminator="\n")
    escritor.writerow(COLUNAS_DO_CADERNO)
    for i, p in enumerate(passos):
        if p.veredito not in VEREDITOS_QUE_CONTAM:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", f"{p.sub} {p.linha} {p.jogador}".lower()).strip("-")
        escritor.writerow(
            [
                f"o-basico-{slug}-{carimbo}-{i}",
                "",
                p.transporte,
                "",
                "",
                carimbo,
                p.linha,
                "sim" if p.veredito != NAO_SEI else "não",
                _RESULTADO_DO_VEREDITO[p.veredito],
                _RESULTADO_DO_VEREDITO[p.veredito],
                "instrumento:o_basico",
                p.comando or f"o_basico.py {p.sub}",
                f"{p.porque} — {comando}",
                "",
            ]
        )
    return saida.getvalue()


# ---------------------------------------------------------------------------
# Ajudas de linha
# ---------------------------------------------------------------------------


def _passo(s: Sessao, linha: str, jogador: str, transporte: str, veredito: str, porque: str,
           **extra: Any) -> None:
    s.anotar(
        Passo(
            sub=s.sub,
            linha=linha,
            jogador=jogador,
            transporte=transporte,
            modo=extra.pop("modo", modo_de(s.estado_inicio)),
            veredito=veredito,
            porque=porque,
            **extra,
        )
    )


def _json_do_ensaio(texto: str) -> Any:
    """O primeiro objeto JSON inteiro da saída de um ensaio, ou None."""
    inicio = min((i for i in (texto.find("{"), texto.find("[")) if i >= 0), default=-1)
    if inicio < 0:
        return None
    with contextlib.suppress(ValueError):
        return json.JSONDecoder().raw_decode(texto[inicio:])[0]
    return None


def _resumo_do_ensaio(texto: str) -> str:
    achado = re.search(r"RESUMO:\s*(.+)", texto)
    return achado.group(1).strip() if achado else (texto.strip().splitlines() or ["sem saída"])[-1]


def _por_chave(itens: Iterable[Mapping[str, Any]], campo: str) -> dict[str, list[dict[str, Any]]]:
    fora: dict[str, list[dict[str, Any]]] = {}
    for item in itens:
        chave = chave_mascarada(item.get(campo))
        if chave:
            fora.setdefault(chave, []).append(dict(item))
    return fora


def _jogo_vivo(estado: Mapping[str, Any]) -> bool:
    return _dict(estado.get("game_signal")).get("authority") == "game"


def _pid_do_compositor(maquina: Maquina) -> int | None:
    pids = [pid for pid, (_pai, comm) in maquina.processos().items() if comm == "cosmic-comp"]
    return min(pids) if pids else None


# ---------------------------------------------------------------------------
# retrato (§4.1): só lê
# ---------------------------------------------------------------------------


def sub_retrato(s: Sessao, a: argparse.Namespace) -> None:
    e = s.estado_inicio
    mesa = controles_na_mesa(e)
    emulacao = _dict(e.get("gamepad_emulation"))
    por_aparelho = _dict(emulacao.get("por_aparelho"))
    s.gravar_json("retrato/estado.json", e)
    for c in mesa:
        medida = {
            "transporte": c.get("transport"),
            "adaptador": c.get("adaptador"),
            "vpad_backend": c.get("vpad_backend"),
            "vpad_motivo": c.get("vpad_motivo"),
            "mascara": por_aparelho.get(str(c.get("uniq"))),
            "bateria": c.get("battery_pct"),
            "hz_movimento": c.get("hz_movimento"),
            "hz_voz": c.get("hz_voz"),
            "luz": [c.get("lightbar_source"), c.get("lightbar_disputada")],
            "microfone": [_dict(c.get("audio")).get("canal_ativo"), _dict(c.get("audio")).get("mic_mudo")],
            "cor_do_plastico": c.get("modelo"),
        }
        _passo(s, "a mesa e as variáveis", f"P{c['player']}", transporte_de(c), REGISTRO,
               "é registro", comando="daemon.state_full", medida=medida)

    if a.esperado:
        _conferir_o_esperado(s, a.esperado, mesa)

    _linha_do_led(s, mesa)
    _linha_dos_nos_de_som(s, mesa)
    _linha_dos_endpoints(s, mesa)

    dispositivos = s.maquina.dispositivos_de_entrada()
    s.gravar("retrato/input-devices.txt", dispositivos)
    pads = pads_do_produto(dispositivos)
    _passo(s, "os pads no kernel", "todos", "—", REGISTRO,
           f"{len(pads)} pad(s) do produto: " + ", ".join(sorted(f"{p.backend} {p.vendor}:{p.product}" for p in pads)),
           comando="/proc/bus/input/devices")

    _linha_da_bateria(s, mesa)
    _linhas_da_maquina(s)
    _passo(s, "os arquivos dela", "todos", "—", REGISTRO,
           f"{len(s.sha_antes)} arquivo(s) fotografados (sha256 e cópia privada)",
           comando="sha256 de ~/.config/hefesto-dualsense4unix")


def _conferir_o_esperado(s: Sessao, esperado: str, mesa: Sequence[Mapping[str, Any]]) -> None:
    achado = re.fullmatch(r"\s*(\d+)\s*cabo\s*\+\s*(\d+)\s*r[aá]dio\s*", esperado.lower())
    if achado is None:
        raise Recusa(f"não entendi o --esperado {esperado!r} (a forma é 2cabo+2radio)")
    cabo = sum(1 for c in mesa if c.get("transport") == "usb")
    radio = sum(1 for c in mesa if c.get("transport") == "bt")
    if (cabo, radio) != (int(achado.group(1)), int(achado.group(2))):
        raise Recusa(f"a mesa é {cabo} no cabo + {radio} no rádio, e o pedido foi {esperado}")


def _linha_do_led(s: Sessao, mesa: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """O LED de jogador aceso no sysfs contra o `player` do estado (dois donos)."""
    rc, texto = s.rodar_ensaio("quem_e_quem.py", "--json", teto_s=60.0)
    dado = _json_do_ensaio(texto)
    fisicos = _por_chave(_lista(_dict(dado).get("fisicos")), "uniq") if isinstance(dado, Mapping) else {}
    numeros = Counter(f[0].get("led_jogador") for f in fisicos.values() if len(f) == 1)
    for c in mesa:
        jogador = f"P{c['player']}"
        chave = chave_mascarada(c.get("uniq"))
        achados = fisicos.get(chave or "", [])
        if not isinstance(dado, Mapping):
            _passo(s, "o LED contra o jogador", jogador, transporte_de(c), NAO_SEI,
                   f"o quem_e_quem não respondeu em JSON (rc={rc})", comando="quem_e_quem.py --json")
            continue
        if len(achados) != 1:
            _passo(s, "o LED contra o jogador", jogador, transporte_de(c), NAO_SEI,
                   "o físico não se separa pelo endereço mascarado" if achados else "o físico não apareceu no sysfs",
                   comando="quem_e_quem.py --json")
            continue
        fisico = achados[0]
        led = fisico.get("led_jogador")
        desenho = fisico.get("led_desenho")
        if desenho in (None, "-", "00000"):
            veredito, porque = NAO_SEI, f"as luzes de número não se leem (desenho {desenho!r})"
        elif led == c.get("player") and numeros[led] == 1:
            veredito, porque = VERDE, f"o LED aceso ({desenho}) diz {jogador}, como o estado"
        else:
            veredito, porque = VERMELHO, f"o LED aceso ({desenho}) diz P{led}, e o estado diz {jogador}"
        _passo(s, "o LED contra o jogador", jogador, transporte_de(c), veredito, porque,
               comando="quem_e_quem.py --json", medida={"desenho": desenho, "transporte_no_sysfs": fisico.get("transporte")})
    return {k: v[0] for k, v in fisicos.items() if len(v) == 1}


def _linha_dos_nos_de_som(s: Sessao, mesa: Sequence[Mapping[str, Any]]) -> None:
    rc, texto = s.rodar_ensaio("os_nos_de_som_por_controle.py", "--json", teto_s=60.0)
    dado = _json_do_ensaio(texto)
    nos = _por_chave(_lista(dado), "mac") if isinstance(dado, list) else {}
    for c in mesa:
        jogador = f"P{c['player']}"
        achados = nos.get(chave_mascarada(c.get("uniq")) or "", [])
        if not isinstance(dado, list) or len(achados) != 1:
            _passo(s, "os nós de som", jogador, transporte_de(c), NAO_SEI,
                   f"o censo não separou este controle (rc={rc})", comando="os_nos_de_som_por_controle.py --json")
            continue
        no = achados[0]
        faltas = [str(f) for f in no.get("faltas") or []]
        if faltas:
            _passo(s, "os nós de som", jogador, transporte_de(c), VERMELHO, "falta: " + "; ".join(faltas),
                   comando="os_nos_de_som_por_controle.py --json")
        else:
            _passo(s, "os nós de som", jogador, transporte_de(c), VERDE,
                   "um nó de saída e um de entrada do produto", comando="os_nos_de_som_por_controle.py --json")


def _linha_dos_endpoints(s: Sessao, mesa: Sequence[Mapping[str, Any]]) -> None:
    rc, texto = s.rodar_ensaio("os_endpoints_de_haptica.py", "--json", teto_s=60.0)
    dado = _json_do_ensaio(texto)
    endpoints = _lista(_dict(dado).get("endpoints")) if isinstance(dado, Mapping) else []
    try:
        from hefesto_dualsense4unix.integrations.endpoint_de_haptica import nome_do_endpoint
    except Exception:
        nome_do_endpoint = None
    for c in mesa:
        jogador = f"P{c['player']}"
        if c.get("transport") != "bt":
            _passo(s, "o endpoint de háptica", jogador, transporte_de(c), NAO_SE_APLICA,
                   "no cabo a háptica é a placa do próprio controle")
            continue
        if not isinstance(dado, Mapping) or nome_do_endpoint is None:
            _passo(s, "o endpoint de háptica", jogador, transporte_de(c), NAO_SEI,
                   f"o ensaio dos endpoints não respondeu em JSON (rc={rc})",
                   comando="os_endpoints_de_haptica.py --json")
            continue
        esperado = s.mascarado(nome_do_endpoint(str(c.get("uniq") or "")))
        achados = [ep for ep in endpoints if s.mascarado(str(ep.get("nome") or "")) == esperado]
        if len(achados) != 1:
            veredito = VERMELHO if not achados else NAO_SEI
            porque = "o controle no rádio sem endpoint de háptica" if not achados else "dois endpoints com o mesmo nome mascarado"
        else:
            faltam = [frase for ok, frase in achados[0].get("laudo") or [] if not ok]
            veredito = VERMELHO if faltam else VERDE
            porque = ("o laudo falha em: " + "; ".join(faltam)) if faltam else "o endpoint com o laudo inteiro"
        _passo(s, "o endpoint de háptica", jogador, transporte_de(c), veredito, porque,
               comando="os_endpoints_de_haptica.py --json")


def _linha_da_bateria(s: Sessao, mesa: Sequence[Mapping[str, Any]]) -> None:
    baterias = s.maquina.baterias()
    for c in mesa:
        jogador = f"P{c['player']}"
        doze = _hex12(c.get("uniq"))
        lida = baterias.get(doze or "")
        estado = c.get("battery_pct")
        if lida is None or not lida[0].isdigit() or not isinstance(estado, int):
            _passo(s, "a bateria (sysfs contra o estado)", jogador, transporte_de(c), NAO_SEI,
                   "o kernel ou o estado não publicam a bateria deste controle",
                   comando="/sys/class/power_supply")
            continue
        diferenca = abs(int(lida[0]) - estado)
        _passo(s, "a bateria (sysfs contra o estado)", jogador, transporte_de(c),
               VERDE if diferenca <= 10 else VERMELHO,
               f"o kernel diz {lida[0]}% ({lida[1]}), o estado diz {estado}%",
               comando="/sys/class/power_supply")


def _linhas_da_maquina(s: Sessao) -> None:
    """As variáveis que mudam o resultado de uma medida de sessão e de vibração.

    O pai do `cosmic-osk` (ele é de toda sessão COSMIC, C19), a regra 60 do
    `input-remapper` (roda em todo nó de entrada novo, inclusive nos pads), a
    GPU, as unidades pessoais que reagem à Steam, o compositor contra o pacote,
    o grupo `input`, o Secure Boot e o chip de cada adaptador. Todas são
    registro: dizem de que máquina o resultado veio.
    """
    processos = s.maquina.processos()
    osk = [pid for pid, (_p, comm) in processos.items() if comm == "cosmic-osk"]
    pai = processos.get(processos.get(osk[0], (0, ""))[0], (0, "?"))[1] if osk else None
    registros: dict[str, object] = {
        "compositor": _pid_do_compositor(s.maquina),
        "teclado_na_tela": f"de pé (pai: {pai})" if osk else "ausente",
        "steam": "aberta" if any(comm == "steam" for _p, comm in processos.values()) else "fechada",
        "regra_60_do_input_remapper": s.maquina.regra_do_input_remapper(),
        "secure_boot": s.maquina.secure_boot(),
        "adaptadores": s.maquina.adaptadores(),
    }
    if s.maquina.existe("lspci"):
        _rc, texto = s.maquina.rodar(["lspci"], 10.0)
        registros["gpu"] = [ln for ln in texto.splitlines() if re.search(r"VGA|3D controller", ln)]
    if s.maquina.existe("dpkg"):
        _rc, texto = s.maquina.rodar(["dpkg", "-V", "cosmic-comp"], 30.0)
        registros["compositor_contra_o_pacote"] = texto.strip() or "igual ao pacote"
    _rc, grupos = s.maquina.rodar(["id", "-nG"], 5.0)
    registros["grupo_input"] = "input" in grupos.split()
    if s.maquina.existe("systemctl"):
        _rc, texto = s.maquina.rodar(["systemctl", "--user", "list-units", "--all", "--no-legend", "--plain"], 15.0)
        registros["unidades_que_reagem_a_steam"] = [
            ln.split()[0] for ln in texto.splitlines()
            if ln.split() and re.search(r"steam|heroic|meow|aurora|input-remapper", ln.split()[0])
        ]
    s.gravar_json("retrato/maquina.json", registros)
    for chave, valor in registros.items():
        _passo(s, f"a máquina: {chave.replace('_', ' ')}", "todos", "—", REGISTRO,
               json.dumps(valor, ensure_ascii=False, default=str)[:200])


# ---------------------------------------------------------------------------
# a sessão (§4.2): só lê; o --boot e o --bpftrace são declarados
# ---------------------------------------------------------------------------


def sub_sessao(s: Sessao, a: argparse.Namespace) -> None:
    e = s.estado_inicio
    jogadores = len(controles_na_mesa(e))
    compositor_antes = _pid_do_compositor(s.maquina)
    inicio = s.maquina.agora()

    if a.boot:
        _reiniciar_o_daemon(s, "o --boot da sessão")

    sondas = _subir_as_sondas(s, a, ("trava-por-pad.bt", "uhid-raw-request.bt"), a.segundos)
    fim = inicio + (a.segundos if (a.bpftrace or a.boot) else 0.0)
    pids_do_compositor = {compositor_antes}
    while s.maquina.agora() < fim:
        s.maquina.dormir(min(5.0, max(0.0, fim - s.maquina.agora())))
        pids_do_compositor.add(_pid_do_compositor(s.maquina))

    diario = s.maquina.diario_do_daemon()
    kernel = s.maquina.diario_do_kernel()
    s.gravar("sessao/diario-do-daemon.txt", "\n".join(_desde_o_ultimo_boot(diario)) + "\n")

    # A hora do pad (01 A9): o dono é o mesmo do doctor.
    horas = hora_do_pad(kernel, diario)
    if not horas:
        _passo(s, "a hora do pad", "todos", "—", NAO_SE_APLICA,
               "nenhum pad uinput registrado desde que o daemon subiu", comando="journalctl -k/--user")
    for h in horas:
        veredito = {OK: VERDE, FALHA: VERMELHO}.get(h.veredito, NAO_SEI)
        _passo(s, "a hora do pad", "todos", "—", veredito, h.frase(),
               comando="journalctl -k -b × journalctl --user -u hefesto-dualsense4unix -b",
               medida={"atraso_s": h.atraso_s, "limite_s": LIMITE_DO_NASCIMENTO_S})

    # 1b, os pads no boot (01 A11). NÃO se conta os pads de agora: o
    # multiplicador do boot some depois que os pads sobrando morrem.
    no_boot = pads_no_boot(diario)
    if no_boot is None:
        _passo(s, "1b, os pads no boot", "todos", "—", NAO_SEI,
               "o diário deste boot não tem o daemon_starting")
    else:
        _passo(s, "1b, os pads no boot", "todos", "—",
               VERDE if no_boot == jogadores else VERMELHO,
               f"{no_boot} pad(s) criados no boot para {jogadores} jogador(es)",
               comando="journalctl --user -u hefesto-dualsense4unix -b",
               medida={"pads_no_boot": no_boot, "jogadores": jogadores})

    # O compositor: o mesmo PID e nenhum pânico novo.
    if compositor_antes is None:
        _passo(s, "o compositor", "todos", "—", NAO_SE_APLICA, "a sessão não é COSMIC (sem cosmic-comp)")
    else:
        panicos = sum(1 for ln in s.maquina.diario_do_sistema_desde(inicio) if "encoded >= 0xf001" in ln)
        pids_do_compositor.add(_pid_do_compositor(s.maquina))
        mesmo = pids_do_compositor == {compositor_antes}
        _passo(s, "o compositor", "todos", "—", VERDE if mesmo and not panicos else VERMELHO,
               f"o compositor {'é o mesmo' if mesmo else 'trocou de PID'} e {panicos} pânico(s) novos",
               comando="/proc (cosmic-comp) e journalctl -b")

    fila = sum(1 for ln in s.maquina.kernel_desde(inicio) if "Output queue is full" in ln)
    _passo(s, "a fila do uhid", "todos", "—", REGISTRO, f"{fila} «Output queue is full» na janela",
           comando="journalctl -k")

    _ler_as_sondas_da_espera(s, sondas)


def _reiniciar_o_daemon(s: Sessao, motivo: str) -> None:
    """Reinicia o daemon (mexe, declarado): nunca com jogo aberto."""
    estado = s.maquina.estado() or {}
    if _jogo_vivo(estado):
        raise Recusa(f"{motivo}: há jogo aberto, e o reinício recriaria os pads no meio da partida")
    rc, texto = s.maquina.rodar(["systemctl", "--user", "restart", "hefesto-dualsense4unix"], 60.0)
    s.declarar(f"o daemon reiniciado ({motivo})", "de pé", "reiniciado" if rc == 0 else texto.strip())
    if rc != 0:
        raise Recusa(f"o reinício do daemon falhou: {texto.strip()}")
    prazo = s.maquina.agora() + 60.0
    jogadores = len(controles_na_mesa(s.estado_inicio))
    while s.maquina.agora() < prazo:
        s.maquina.dormir(2.0)
        novo = s.maquina.estado()
        if novo is not None and len(controles_na_mesa(novo)) >= jogadores:
            pads = _lista(_dict(novo.get("rumble_ff")).get("per_vpad"))
            if len(pads) >= jogadores:
                return
    raise Recusa("o daemon não assentou em 60 s depois do reinício")


def _subir_as_sondas(
    s: Sessao, a: argparse.Namespace, nomes: Sequence[str], segundos: float
) -> dict[str, Any]:
    """Sobe as sondas pedidas com ``sudo -n`` (sem senha na tela). Sem sudo: «não medido»."""
    if not getattr(a, "bpftrace", False):
        return dict.fromkeys(nomes, "não medido (sem --bpftrace)")
    if not s.maquina.existe("bpftrace"):
        return dict.fromkeys(nomes, "não medido (sem o bpftrace nesta máquina)")
    rc, _texto = s.maquina.rodar(["sudo", "-n", "true"], 10.0)
    if rc != 0:
        return dict.fromkeys(nomes, "não medido (sem sudo)")
    return {
        nome: s.maquina.subir(
            ["sudo", "-n", "timeout", "-s", "INT", str(int(segundos)), "bpftrace", str(SONDAS / nome)]
        )
        for nome in nomes
    }


def _colher_sonda(s: Sessao, processo: Any, segundos: float) -> str | None:
    """A saída de uma sonda; None quando ela não subiu (a razão é o texto dela)."""
    if isinstance(processo, str):
        return None
    return s.maquina.colher(processo, segundos + 30.0)


def _ler_as_sondas_da_espera(s: Sessao, sondas: Mapping[str, Any]) -> None:
    for nome, linha in (("trava-por-pad.bt", "a espera da vibração"),
                        ("uhid-raw-request.bt", "a espera do GET/SET no uhid")):
        processo = sondas.get(nome, "não medido (sem --bpftrace)")
        texto = _colher_sonda(s, processo, 60.0)
        if texto is None:
            _passo(s, linha, "todos", "—", NAO_SEI, str(processo))
            continue
        s.gravar(f"sessao/{nome.removesuffix('.bt')}.txt", texto)
        maiores = [int(m.group(1)) for m in re.finditer(r"@maior_us\[[^\]]*\]:\s*(\d+)", texto)]
        esperas = [ln for ln in texto.splitlines() if ln.startswith(("ESPERA ", "ESPERA_UHID "))]
        if not maiores:
            _passo(s, linha, "todos", "—", NAO_SEI, "a sonda não registrou pedido nenhum na janela")
            continue
        maior = max(maiores)
        if maior < PRAZO_DA_ESPERA_US:
            veredito = VERDE
        elif maior >= TETO_DA_ESPERA_US:
            veredito = VERMELHO
        else:
            veredito = NAO_SEI
        _passo(s, linha, "todos", "—", veredito,
               f"a maior espera foi {maior / 1000:.2f} ms; {len(esperas)} acima de 5 ms, com a hora no arquivo",
               comando=f"bpftrace scripts/sondas/{nome}",
               medida={"maior_us": maior, "acima_de_5ms": len(esperas)})


# ---------------------------------------------------------------------------
# eixos (§4.3): só lê; o --trocar-modo mexe na sessão do daemon (A8)
# ---------------------------------------------------------------------------


def sub_eixos(s: Sessao, a: argparse.Namespace) -> None:
    _medir_os_eixos(s, s.estado_inicio, rotulo=None)
    if a.trocar_modo:
        _trocar_o_modo_e_voltar(s, a.trocar_modo)


def linha_do_perfil_contra_o_ar(
    estado: Mapping[str, Any],
    perfis: Mapping[str, Mapping[str, Any]],
    diario: Sequence[str],
    *,
    pedido_pela_sessao: str | None = None,
) -> tuple[str, str, dict[str, Any]]:
    """O modo que o perfil ativo pede contra o do ar, também com o jogo aberto.

    Devolve ``(veredito, porque, medida)``. É a linha que o L2 de 27/09 pediu:
    o PRAGMATA pediu o DualSense, o R-04 recusou recriar os pads com o jogo
    vivo, e a partida inteira correu no Xbox. Um motivo em
    :data:`MOTIVOS_QUE_NAO_ABSOLVEM` explica, e não absolve.
    """
    perfil = perfis.get(str(estado.get("active_profile") or ""))
    pedido = pedido_pela_sessao or caminho_do_perfil(perfil)
    no_ar = _dict(estado.get("gamepad_emulation")).get("caminho")
    medida = {"perfil": estado.get("active_profile"), "pedido": pedido, "no_ar": no_ar,
              "jogo_vivo": _jogo_vivo(estado)}
    if estado.get("native_mode") is True or _dict(estado.get("gamepad_emulation")).get("enabled") is not True:
        return NAO_SE_APLICA, "a emulação não está ligada (Conexão Nativa ou desligada)", medida
    if pedido is None:
        return NAO_SE_APLICA, "o perfil ativo não pede modo", medida
    if pedido == no_ar:
        origem = "pela sessão do o_basico" if pedido_pela_sessao else f"pelo perfil {medida['perfil']}"
        return VERDE, f"o modo pedido {origem} ({pedido}) é o do ar", medida
    bloqueios = [c for c in bloqueios_por_jogo(diario) if c in (pedido, "?")]
    medida["bloqueios"] = bloqueios
    if bloqueios:
        return (VERMELHO,
                f"o jogo roda no modo que o perfil dele não pediu: pediu {pedido}, está em {no_ar}"
                f" ({MOTIVOS_QUE_NAO_ABSOLVEM[0]} no diário)", medida)
    return VERMELHO, f"o perfil pede {pedido} e o ar está em {no_ar}, sem motivo dito", medida


def _medir_os_eixos(s: Sessao, estado: Mapping[str, Any], *, rotulo: str | None,
                    pedido_pela_sessao: str | None = None) -> None:
    modo = modo_de(estado)
    sufixo = f" ({rotulo})" if rotulo else ""
    mesa = controles_na_mesa(estado)
    diario = s.maquina.diario_do_daemon()
    por_numero = {int(c["player"]): c for c in mesa}

    # O modo pedido contra o do ar, por jogador (o dono é o do doctor).
    for linha in modo_contra_o_ar(estado):
        controle = por_numero.get(linha.jogador, {})
        if linha.veredito == OK:
            veredito = VERDE
        elif linha.veredito == AVISO and linha.pedido is None:
            veredito = NAO_SEI
        elif linha.veredito == AVISO and linha.motivo not in MOTIVOS_QUE_NAO_ABSOLVEM:
            veredito = VERDE
        else:
            veredito = VERMELHO
        _passo(s, "o modo contra o ar" + sufixo, f"P{linha.jogador}", transporte_de(controle), veredito,
               linha.frase(), modo=modo, comando="o_modo_no_ar.modo_contra_o_ar(state_full)")

    perfis = perfis_por_nome(s.copias)
    veredito, porque, medida = linha_do_perfil_contra_o_ar(
        estado, perfis, diario, pedido_pela_sessao=pedido_pela_sessao
    )
    _passo(s, "o modo do perfil contra o ar, também com o jogo aberto" + sufixo, "todos", "—",
           veredito, porque, modo=modo, medida=medida, comando="perfil ativo × state_full × diário")

    dispositivos = s.maquina.dispositivos_de_entrada()
    pads = pads_do_produto(dispositivos)
    _linha_da_mascara_contra_o_pad(s, estado, pads, sufixo, modo)
    _linha_1a(s, estado, pads, sufixo, modo)

    # O movimento declarado (A14): o booleano, não as linhas.
    emulacao = _dict(estado.get("gamepad_emulation"))
    fora_do_uhid = any(c.get("vpad_backend") != "uhid" for c in mesa)
    sem_imu = emulacao.get("canal_sem_imu")
    if emulacao.get("enabled") is not True:
        _passo(s, "o movimento declarado" + sufixo, "todos", "—", NAO_SE_APLICA, "a emulação está desligada", modo=modo)
    elif not isinstance(sem_imu, bool):
        _passo(s, "o movimento declarado" + sufixo, "todos", "—", NAO_SEI,
               "o daemon não publica o canal_sem_imu", modo=modo)
    else:
        _passo(s, "o movimento declarado" + sufixo, "todos", "—",
               VERDE if sem_imu == fora_do_uhid else VERMELHO,
               f"canal_sem_imu={sem_imu} com {'algum' if fora_do_uhid else 'nenhum'} jogador fora do uhid",
               modo=modo, comando="state_full.gamepad_emulation.canal_sem_imu")

    # A conexão, duas réguas: o transporte dito contra o barramento do físico.
    rc, texto = s.rodar_ensaio("quem_e_quem.py", "--json", teto_s=60.0)
    dado = _json_do_ensaio(texto)
    fisicos = _por_chave(_lista(_dict(dado).get("fisicos")), "uniq") if isinstance(dado, Mapping) else {}
    for c in mesa:
        achados = fisicos.get(chave_mascarada(c.get("uniq")) or "", [])
        dito = transporte_de(c)
        if len(achados) != 1:
            _passo(s, "a conexão (dita e medida)" + sufixo, f"P{c['player']}", dito, NAO_SEI,
                   f"o físico não se separou no sysfs (rc={rc})", modo=modo)
            continue
        medido = {"cabo": "cabo", "rádio": "radio"}.get(str(achados[0].get("transporte")), "?")
        _passo(s, "a conexão (dita e medida)" + sufixo, f"P{c['player']}", dito,
               VERDE if medido == dito else VERMELHO,
               f"o estado diz {dito}, o barramento do físico diz {medido}", modo=modo,
               comando="state_full × quem_e_quem.py --json")


def _esperado_do_pad(backend: str, mascara: str, jogador: int, nomes_uinput: Mapping[str, Any]) -> tuple[str, str] | None:
    """``(vendor:product, nome)`` que o jogo deve ver, pela tabela da A3."""
    if backend == "uhid":
        return "054c:0df2", f"(Hefesto P{jogador})"
    for nome, (mascara_do_nome, vendor, product) in nomes_uinput.items():
        if mascara_do_nome == mascara:
            return f"{vendor}:{product}", nome
    return None


def _linha_da_mascara_contra_o_pad(s: Sessao, estado: Mapping[str, Any], pads: Sequence[PadNoKernel],
                                   sufixo: str, modo: str) -> None:
    """A máscara de cada jogador contra o pad que o kernel publica (01 A3).

    O `uhid` casa pelo número no nome. Os pads `uinput` são homônimos (A2):
    casa-se o MULTICONJUNTO — tantos pads daquela máscara quantos jogadores a
    pedem —, e o jogador que falta sai vermelho.
    """
    nomes_uinput = _nomes_dos_pads_uinput()
    emulacao = _dict(estado.get("gamepad_emulation"))
    por_aparelho = _dict(emulacao.get("por_aparelho"))
    per_vpad = {int(p["player"]): p for p in _lista(_dict(estado.get("rumble_ff")).get("per_vpad"))
                if isinstance(p.get("player"), int)}
    sobra = Counter((p.vendor + ":" + p.product, p.nome) for p in pads if p.backend == "uinput")
    for c in controles_na_mesa(estado):
        jogador = int(c["player"])
        backend = str(_dict(per_vpad.get(jogador)).get("backend") or c.get("vpad_backend") or "")
        mascara = str(por_aparelho.get(str(c.get("uniq"))) or emulacao.get("flavor") or "dualsense")
        esperado = _esperado_do_pad(backend, mascara, jogador, nomes_uinput)
        if not backend or esperado is None:
            _passo(s, "a máscara contra o pad" + sufixo, f"P{jogador}", transporte_de(c), NAO_SEI,
                   f"sem pad publicado, ou a máscara {mascara!r} sem nome conhecido", modo=modo)
            continue
        par, nome = esperado
        if backend == "uhid":
            casou = any(p.backend == "uhid" and p.jogador == jogador and f"{p.vendor}:{p.product}" == par
                        for p in pads)
        else:
            casou = sobra[(par, nome)] > 0
            if casou:
                sobra[(par, nome)] -= 1
        _passo(s, "a máscara contra o pad" + sufixo, f"P{jogador}", transporte_de(c),
               VERDE if casou else VERMELHO,
               f"máscara {mascara} no {backend}: {'o kernel tem' if casou else 'o kernel NÃO tem'} {par} «{nome}»",
               modo=modo, comando="/proc/bus/input/devices × state_full")


def _linha_1a(s: Sessao, estado: Mapping[str, Any], pads: Sequence[PadNoKernel], sufixo: str, modo: str) -> None:
    """1a, um pad por jogador AGORA: a contagem e o dono de cada um (01 A11)."""
    jogadores = len(controles_na_mesa(estado))
    per_vpad = _lista(_dict(estado.get("rumble_ff")).get("per_vpad"))
    if len(pads) != jogadores or len(per_vpad) != jogadores:
        veredito = VERMELHO
        porque = f"{len(pads)} pad(s) no kernel e {len(per_vpad)} no daemon para {jogadores} jogador(es)"
    elif any(p.get("evdev") is None for p in per_vpad):
        veredito = NAO_SEI
        porque = f"{jogadores} pads para {jogadores} jogadores, mas o daemon não diz o nó de todos (evdev None, 01 A2)"
    else:
        veredito, porque = VERDE, f"{jogadores} pads para {jogadores} jogadores, cada um com o seu nó"
    _passo(s, "1a, um pad por jogador agora" + sufixo, "todos", "—", veredito, porque, modo=modo,
           comando="/proc/bus/input/devices × per_vpad[]", medida={"pads": len(pads), "per_vpad": len(per_vpad)})


def _trocar_o_modo_e_voltar(s: Sessao, destino: str) -> None:
    """A passada C′: o outro modo SÓ na sessão do daemon, e a volta (01 §6).

    ``gamepad.emulation.set`` sem ``origin`` vira ``origin="profile"``, e o
    flag global dela só se grava com ``origin == "manual"``. Os ``sha256``
    conferidos no fim dizem se a hipótese A8 se sustentou.
    """
    antes = _dict(s.estado_inicio.get("gamepad_emulation")).get("caminho")
    if antes not in ("dualsense", "xbox"):
        raise Recusa(f"o modo de agora é {antes!r}: a troca só vale entre dualsense e xbox")
    if _jogo_vivo(s.estado_inicio):
        raise Recusa("há jogo aberto: a troca recriaria os pads no meio da partida")
    compositor = _pid_do_compositor(s.maquina)
    marco = s.maquina.agora()
    try:
        resposta = s.maquina.chamar("gamepad.emulation.set", {"enabled": True, "caminho": destino})
        s.declarar("gamepad.emulation.set (a sessão; recria os pads)", antes, destino)
        s.dizer(f"  ida: {json.dumps(resposta, ensure_ascii=False, default=str)}")
        novo = _esperar_os_pads(s, destino)
        _conferir_a_hora_da_troca(s, marco, f"modo {destino}")
        if novo is not None:
            _medir_os_eixos(s, novo, rotulo=f"no modo {destino}", pedido_pela_sessao=destino)
    finally:
        marco_da_volta = s.maquina.agora()
        s.maquina.chamar("gamepad.emulation.set", {"enabled": True, "caminho": antes})
        de_volta = _esperar_os_pads(s, str(antes))
        voltou = de_volta is not None and _dict(de_volta.get("gamepad_emulation")).get("caminho") == antes
        if s.mexeu:
            s.mexeu[-1]["voltou"] = voltou
        if not voltou:
            s.recusar(f"o modo não voltou a {antes}")
    _conferir_a_hora_da_troca(s, marco_da_volta, f"de volta ao modo {antes}")
    if compositor is not None and _pid_do_compositor(s.maquina) != compositor:
        _passo(s, "o compositor na troca", "todos", "—", VERMELHO, "o compositor trocou de PID durante a troca")


def _esperar_os_pads(s: Sessao, caminho: str, prazo_s: float = 30.0) -> dict[str, Any] | None:
    """O estado depois da troca, quando o caminho e os pads assentaram."""
    jogadores = len(controles_na_mesa(s.estado_inicio))
    fim = s.maquina.agora() + prazo_s
    while s.maquina.agora() < fim:
        s.maquina.dormir(2.0)
        estado = s.maquina.estado()
        if estado is None:
            continue
        pads = _lista(_dict(estado.get("rumble_ff")).get("per_vpad"))
        if _dict(estado.get("gamepad_emulation")).get("caminho") == caminho and len(pads) == jogadores:
            return estado
    return s.maquina.estado()


def _conferir_a_hora_da_troca(s: Sessao, marco: float, rotulo: str) -> None:
    """Os pads `uinput` que nasceram na troca, cada um em até 2 s (a sessão de pé).

    O diário do kernel entra só desde o marco: os pads do boot ficam sem a
    linha da criação e saem «não medido», e só os nascidos na troca contam.
    Os pads `uhid` não passam pela hora (a trava medida é do `uinput`).
    """
    horas = hora_do_pad(s.maquina.kernel_desde(marco), s.maquina.diario_do_daemon())
    medidos = [h for h in horas if h.veredito != AVISO]
    lentos = [h for h in medidos if h.veredito == FALHA]
    if not medidos:
        _passo(s, f"a hora do pad na troca ({rotulo})", "todos", "—", NAO_SE_APLICA,
               "nenhum pad uinput nasceu na troca")
        return
    _passo(s, f"a hora do pad na troca ({rotulo})", "todos", "—",
           VERMELHO if lentos else VERDE,
           "; ".join(h.frase() for h in lentos) if lentos
           else f"{len(medidos)} pad(s) nascidos, nenhum acima de {LIMITE_DO_NASCIMENTO_S:g} s")


# ---------------------------------------------------------------------------
# A parada que segue a dependência de alvo (01 A11)
# ---------------------------------------------------------------------------


def _parar_se_o_1a_caiu(s: Sessao, a: argparse.Namespace) -> bool:
    """O 1a vermelho tira o alvo de quem mede por jogador: para, a menos que --seguir.

    Devolve True quando o subcomando deve parar. O 1b (o boot) não para nada:
    os pads de agora são os que a relistagem do fim confere.
    """
    estado = s.estado_inicio
    pads = pads_do_produto(s.maquina.dispositivos_de_entrada())
    jogadores = len(controles_na_mesa(estado))
    per_vpad = _lista(_dict(estado.get("rumble_ff")).get("per_vpad"))
    if modo_de(estado) in ("nativo", "desligado"):
        return False
    if len(pads) == jogadores and len(per_vpad) == jogadores:
        return False
    _passo(s, "1a, um pad por jogador agora (a pré-condição)", "todos", "—", VERMELHO,
           f"{len(pads)} pad(s) no kernel e {len(per_vpad)} no daemon para {jogadores} jogador(es)"
           + ("; sigo por --seguir" if a.seguir else "; o resto deste subcomando não tem alvo"))
    return not a.seguir


# ---------------------------------------------------------------------------
# entrada (§4.4): só lê; 30 s parado
# ---------------------------------------------------------------------------


def sub_entrada(s: Sessao, a: argparse.Namespace) -> None:
    if _parar_se_o_1a_caiu(s, a):
        return
    e = s.estado_inicio
    mesa = controles_na_mesa(e)
    segundos = f"{a.segundos:g}"
    no_uinput = [c for c in mesa if c.get("vpad_backend") == "uinput"]

    rc, texto = s.rodar_ensaio("entrada_em_repouso.py", "--segundos", segundos, "--json",
                               teto_s=a.segundos + 90.0)
    dado = _json_do_ensaio(texto)
    pares = {str(p.get("vpad")): p for p in _lista(_dict(_dict(dado).get("medidas")).get("pares"))}
    mao = _dict(_dict(dado).get("medidas")).get("mao_na_janela")
    for c in mesa:
        jogador = f"P{c['player']}"
        if c in no_uinput:
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), NAO_SEI,
                   "o pad uinput não tem hidraw: o par não se casa até a marca phys (01 A2)")
            continue
        par = pares.get(jogador)
        if not isinstance(dado, Mapping):
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), NAO_SEI,
                   f"o entrada_em_repouso não respondeu em JSON (rc={rc})")
        elif mao:
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), NAO_SEI,
                   "uma mão tocou num controle na janela: a medida de repouso não vale")
        elif par is None:
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), NAO_SEI,
                   "o pad deste jogador não entrou no casamento")
        elif not par.get("sem_empate"):
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), VERMELHO,
                   "o par saiu AMBÍGUO: duas unidades com o mesmo centro de stick")
        elif par.get("muda") or par.get("inventa"):
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), VERMELHO,
                   "o pad muda o centro de: " + (", ".join(_textos(par.get("muda"))) or "—")
                   + "; inventa valor em: " + (", ".join(_textos(par.get("inventa"))) or "—"),
                   medida=dict(par))
        else:
            _passo(s, "a entrada por par (repouso)", jogador, transporte_de(c), VERDE,
                   "o pad casou com o físico dele e repete o repouso byte a byte")

    rc, texto = s.rodar_ensaio("taxa_no_hidraw.py", "--segundos", segundos, "--json",
                               teto_s=a.segundos + 90.0)
    dado = _json_do_ensaio(texto)
    pares = {str(p.get("vpad")): p for p in _lista(_dict(_dict(dado).get("medidas")).get("pares"))}
    for c in mesa:
        jogador = f"P{c['player']}"
        if c in no_uinput:
            _passo(s, "os intervalos da entrada (pad contra o físico)", jogador, transporte_de(c), NAO_SEI,
                   "o pad uinput não tem hidraw (01 A2)")
            continue
        par = pares.get(jogador)
        if not isinstance(dado, Mapping) or par is None:
            _passo(s, "os intervalos da entrada (pad contra o físico)", jogador, transporte_de(c), NAO_SEI,
                   f"o par não se casou pelo carimbo do sensor (rc={rc})")
            continue
        novos = int(par.get("intervalos_novos") or 0)
        _passo(s, "os intervalos da entrada (pad contra o físico)", jogador, transporte_de(c),
               VERMELHO if novos else VERDE,
               f"{novos} intervalo(s) acima de {INTERVALO_DE_BURACO_MS:g} ms no pad que o físico não teve"
               f" (o maior: {par.get('maior_novo_ms') or 0} ms)",
               medida=dict(par))

    rc, texto = s.rodar_ensaio("giro_e_buraco.py", "--segundos", segundos,
                               "--csv", str(s.privada / "giro.csv"), teto_s=a.segundos + 90.0)
    _passo(s, "os buracos do rádio (registro)", "todos", "—", REGISTRO, _resumo_do_ensaio(s.mascarado(texto)))

    rc, texto = s.rodar_ensaio("a_entrada_que_nasce_sozinha.py", "--segundos", segundos,
                               teto_s=a.segundos + 60.0)
    _passo(s, "o controle negativo (ninguém mexe)", "todos", "—", NAO_SEI,
           "o ensaio não tem --json; o resumo diz: " + _resumo_do_ensaio(s.mascarado(texto)))

    sondas = _subir_as_sondas(s, a, ("nucleo-por-processo.bt",), a.segundos)
    texto_da_sonda = _colher_sonda(s, sondas["nucleo-por-processo.bt"], a.segundos)
    if texto_da_sonda is None:
        _passo(s, "os buracos por escritor", "todos", "—", NAO_SEI, str(sondas["nucleo-por-processo.bt"]))
    else:
        s.gravar("entrada/nucleo.txt", texto_da_sonda)
        por_fio = Counter(ln.split()[3] for ln in texto_da_sonda.splitlines()
                          if ln.startswith("BURACO ") and len(ln.split()) > 3)
        _passo(s, "os buracos por escritor", "todos", "—", REGISTRO,
               "buracos > 33 ms no uhid_char_write: " + (", ".join(f"{k}={v}" for k, v in por_fio.items()) or "0")
               + " (bluetoothd = a entrada do físico pelo rádio)")


# ---------------------------------------------------------------------------
# O leitor dos físicos (saidas e som): o relatório de ENTRADA, pelo broker
# ---------------------------------------------------------------------------


class LeitorDosFisicos:
    """O relatório de entrada de cada físico, num fio por nó, com a hora de cada quadro.

    Só lê. A porta é a do broker (``comum.abrir_no_hidraw``), porque os
    físicos estão escondidos do jogo e um ``open()`` direto colhe ``EACCES``.
    O acelerômetro do físico é o sensor da vibração (01 §4.5); os bytes de
    estado do gatilho e o bit de áudio moram no mesmo relatório.
    """

    def __init__(self) -> None:
        self.quadros: dict[str, list[tuple[float, bytes]]] = {}
        self.marcas: dict[str, float] = {}
        self.problemas: list[str] = []
        self._fds: list[int] = []
        self._fios: list[Any] = []
        self._parar: Any = None

    def abrir(self) -> None:
        import threading

        self._parar = threading.Event()
        if str(ENSAIOS) not in sys.path:
            sys.path.insert(0, str(ENSAIOS))
        try:
            import comum
        except Exception as erro:  # sem a pasta dos ensaios: nada a ler
            self.problemas.append(f"os ensaios não se importam: {erro}")
            return
        for aparelho in comum.fisicos(comum.descobrir_aparelhos()):
            doze = _hex12(aparelho.mac)
            if doze is None:
                continue
            try:
                no = comum.abrir_no_hidraw(aparelho.caminho_hidraw, escrita=False)
            except (Exception, SystemExit) as erro:
                self.problemas.append(f"um físico não abriu: {erro}")
                continue
            self._fds.append(no.fd)
            self.quadros[doze] = []
            fio = threading.Thread(target=self._ler, args=(no.fd, doze), daemon=True)
            fio.start()
            self._fios.append(fio)

    def _ler(self, fd: int, doze: str) -> None:
        import select

        destino = self.quadros[doze]
        while not self._parar.is_set():
            prontos, _, _ = select.select([fd], [], [], 0.2)
            if not prontos:
                continue
            try:
                dados = os.read(fd, 1024)
            except OSError:
                return
            if dados:
                destino.append((time.monotonic(), dados))

    def marcar(self, nome: str) -> None:
        self.marcas[nome] = time.monotonic()

    def fechar(self) -> None:
        if self._parar is not None:
            self._parar.set()
        for fio in self._fios:
            fio.join(timeout=2.0)
        for fd in self._fds:
            with contextlib.suppress(OSError):
                os.close(fd)


def corpo_do_quadro(quadro: bytes) -> bytes | None:
    """O corpo comum do relatório de entrada: ``data[1:]`` no cabo, ``data[2:]`` no rádio."""
    if len(quadro) >= 64 and quadro[0] == 0x01:
        return quadro[1:64]
    if len(quadro) >= 65 and quadro[0] == 0x31:
        return quadro[2:65]
    return None


def modulo_da_aceleracao(corpo: bytes) -> float:
    """O módulo do acelerômetro, ``corpo[21..26]`` em três ``int16`` little-endian."""
    x, y, z = (int.from_bytes(corpo[i : i + 2], "little", signed=True) for i in (21, 23, 25))
    return math.sqrt(x * x + y * y + z * z)


def _desvio(valores: Sequence[float]) -> float:
    if len(valores) < 2:
        return 0.0
    media = sum(valores) / len(valores)
    return math.sqrt(sum((v - media) ** 2 for v in valores) / len(valores))


def tremor_por_fisico(
    quadros: Mapping[str, Sequence[tuple[float, bytes]]], base: tuple[float, float], janela: tuple[float, float]
) -> dict[str, tuple[float, float]]:
    """``{físico: (desvio na base, desvio na janela)}`` do módulo do acelerômetro."""
    fora: dict[str, tuple[float, float]] = {}
    for doze, lista in quadros.items():
        medidas: dict[str, list[float]] = {"base": [], "janela": []}
        for instante, quadro in lista:
            corpo = corpo_do_quadro(quadro)
            if corpo is None:
                continue
            if base[0] <= instante < base[1]:
                medidas["base"].append(modulo_da_aceleracao(corpo))
            elif janela[0] <= instante < janela[1]:
                medidas["janela"].append(modulo_da_aceleracao(corpo))
        fora[doze] = (_desvio(medidas["base"]), _desvio(medidas["janela"]))
    return fora


def veredito_do_tremor(tremores: Mapping[str, tuple[float, float]], alvo: str) -> tuple[str, str]:
    """Só o alvo treme: ele ≥ 5× a própria base e os vizinhos ≤ 2× (hipótese do limiar).

    Os números de 19/09 foram 2.000 a 3.000 contra 50 a 300.
    """
    if alvo not in tremores:
        return NAO_SEI, "o físico do alvo não se leu"
    def razao(par: tuple[float, float]) -> float:
        return par[1] / max(par[0], 1.0)
    do_alvo = razao(tremores[alvo])
    outros = {d: razao(p) for d, p in tremores.items() if d != alvo}
    tremeram = [d for d, r in outros.items() if r > 2.0]
    if do_alvo >= 5.0 and not tremeram:
        return VERDE, f"só o alvo tremeu ({do_alvo:.1f}× a base)"
    if tremeram:
        return VERMELHO, f"{len(tremeram)} vizinho(s) tremeram junto (o alvo: {do_alvo:.1f}× a base)"
    return VERMELHO, f"o alvo não tremeu ({do_alvo:.1f}× a base)"


def estado_do_gatilho(corpo: bytes) -> tuple[int, int]:
    """Os bytes de estado dos gatilhos direito e esquerdo, ``corpo[41]`` e ``corpo[47]``."""
    return corpo[41], corpo[47]


def gatilho_mudou(quadros: Sequence[tuple[float, bytes]], antes: tuple[float, float],
                  depois: tuple[float, float]) -> bool | None:
    """O estado do gatilho direito mudou entre as duas janelas? None se não há quadro."""
    def moda(janela: tuple[float, float]) -> int | None:
        valores = Counter(
            estado_do_gatilho(c)[0]
            for t, q in quadros if janela[0] <= t < janela[1] and (c := corpo_do_quadro(q)) is not None
        )
        return valores.most_common(1)[0][0] if valores else None

    a, b = moda(antes), moda(depois)
    if a is None or b is None:
        return None
    return a != b


# ---------------------------------------------------------------------------
# saidas (§4.5): ESCREVE; a bancada; devolve
# ---------------------------------------------------------------------------


def sub_saidas(s: Sessao, a: argparse.Namespace) -> None:
    if _parar_se_o_1a_caiu(s, a):
        return
    pedidas = {x.strip() for x in a.so.split(",") if x.strip()}
    e = s.estado_inicio
    mesa = controles_na_mesa(e)
    if "luz" in pedidas:
        _linha_da_luz(s, mesa)
    if not ({"vibracao", "vibracao-do-jogo", "gatilho"} & pedidas):
        return
    if _jogo_vivo(e):
        raise Recusa("há jogo aberto: a vibração e o gatilho do protocolo disputariam o do jogo")
    s.reservar_a_bancada()
    sondas = _subir_as_sondas(s, a, ("nucleo-por-processo.bt",), 120.0)
    leitor = s.maquina.leitor_dos_fisicos()
    try:
        if leitor.problemas:
            s.dizer("  " + "; ".join(leitor.problemas))
        if "vibracao" in pedidas:
            _vibracao_do_produto(s, mesa, leitor)
        if "vibracao-do-jogo" in pedidas:
            _vibracao_que_o_jogo_pede(s, mesa, leitor)
        if "gatilho" in pedidas:
            _o_gatilho(s, mesa, leitor)
        _a_bateria_em_tres_reguas(s, mesa, leitor)
    finally:
        leitor.fechar()
        s.gravar_json("saidas/marcas.json", leitor.marcas)
        if s.reiniciar_o_daemon_no_fim:
            # C10: a camada da usuária é memória do daemon, e o estado ainda não
            # a publica. A volta que não deixa rastro é o reinício, declarado.
            _reiniciar_o_daemon(s, "a volta do gatilho por controle (a camada da usuária, C10)")
    _o_dono_de_cada_escrita(s, sondas)


def _linha_da_luz(s: Sessao, mesa: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """3a, a luz e o número: o estado e o sysfs concordam (dois donos). Só lê.

    ``lightbar_source = "desired"`` quer dizer que o daemon publica o que PEDIU,
    e não o que leu: a linha diz «não sei», nunca verde. O plástico é do olho
    dela.
    """
    rc, texto = s.rodar_ensaio("quem_e_quem.py", "--json", teto_s=60.0)
    dado = _json_do_ensaio(texto)
    fisicos = _por_chave(_lista(_dict(dado).get("fisicos")), "uniq") if isinstance(dado, Mapping) else {}
    for c in mesa:
        jogador = f"P{c['player']}"
        fonte = c.get("lightbar_source")
        achados = fisicos.get(chave_mascarada(c.get("uniq")) or "", [])
        if fonte != "sysfs":
            _passo(s, "3a, a luz e o número", jogador, transporte_de(c), NAO_SEI,
                   f"a luz vem de «{fonte}»: o daemon diz o que pediu, não o que o aparelho mostra")
            continue
        if c.get("lightbar_disputada"):
            _passo(s, "3a, a luz e o número", jogador, transporte_de(c), VERMELHO,
                   "a luz está disputada: outro escritor pinta o mesmo controle")
            continue
        if len(achados) != 1:
            _passo(s, "3a, a luz e o número", jogador, transporte_de(c), NAO_SEI,
                   f"o físico não se separou no sysfs (rc={rc})")
            continue
        fisico = achados[0]
        luz = fisico.get("luz_rgb")
        concorda_a_cor = isinstance(luz, list) and list(luz) == list(c.get("lightbar_rgb") or [])
        concorda_o_numero = fisico.get("led_jogador") == c.get("player")
        if concorda_a_cor and concorda_o_numero:
            veredito, porque = VERDE, "o sysfs e o estado concordam na cor e no número (o plástico é do olho dela)"
        else:
            veredito = VERMELHO
            porque = (f"o sysfs diz {luz} e P{fisico.get('led_jogador')}; o estado diz "
                      f"{c.get('lightbar_rgb')} e {jogador}")
        _passo(s, "3a, a luz e o número", jogador, transporte_de(c), veredito, porque,
               comando="state_full × /sys/class/leds (quem_e_quem.py --json)")
    return {k: v[0] for k, v in fisicos.items() if len(v) == 1}


def _vibracao_do_produto(s: Sessao, mesa: Sequence[Mapping[str, Any]], leitor: LeitorDosFisicos) -> None:
    """3b: o alvo do produto em cada jogador, e só ele treme."""
    alvo_antes = s.estado_inicio.get("output_target_index")
    for c in mesa:
        jogador = f"P{c['player']}"
        doze = _hex12(c.get("uniq"))
        leitor.marcar(f"{jogador}:base")
        s.maquina.dormir(2.0)
        leitor.marcar(f"{jogador}:pedido")
        try:
            s.maquina.chamar("controller.target.set", {"uniq": c.get("uniq")})
            s.maquina.chamar("rumble.set", {"weak": 200, "strong": 200})
            s.maquina.dormir(1.5)
        finally:
            leitor.marcar(f"{jogador}:fim")
            s.maquina.chamar("rumble.set", {"weak": 0, "strong": 0})
            s.maquina.chamar("rumble.passthrough", {"enabled": True})
            s.maquina.chamar("controller.target.set", {"index": alvo_antes})
        s.declarar(f"3b: o alvo e a vibração do produto em {jogador}", {"alvo": alvo_antes},
                   {"alvo": alvo_antes, "rumble": "passthrough"})
        tremores = tremor_por_fisico(
            leitor.quadros,
            (leitor.marcas[f"{jogador}:base"], leitor.marcas[f"{jogador}:pedido"]),
            (leitor.marcas[f"{jogador}:pedido"] + 0.3, leitor.marcas[f"{jogador}:fim"]),
        )
        veredito, porque = veredito_do_tremor(tremores, doze or "")
        if leitor.problemas and veredito == VERDE:
            veredito, porque = NAO_SEI, porque + ", mas nem todo físico se leu"
        _passo(s, "3b, a vibração do produto", jogador, transporte_de(c), veredito, porque,
               comando="controller.target.set + rumble.set 200/200 por 1,5 s",
               mexe=["o alvo de saída", "a vibração"])


def _vibracao_que_o_jogo_pede(s: Sessao, mesa: Sequence[Mapping[str, Any]], leitor: LeitorDosFisicos) -> None:
    """3c: o pedido de vibração entra pelo pad do jogador, como o jogo o faria.

    No `uhid`, um ``0x02`` USB com os motores no hidraw do pad; no `uinput`, um
    efeito FF no evdev do pad, casado por pulso (A2): o jogador cujo
    ``ff_nao_nulo_count`` sobe é o dono do nó. O critério usa o DELTA do
    ``ff_nao_nulo_count`` e nunca o ``ff_play_count``, que o teclado na tela
    sobe vinte vezes por segundo (A13).
    """
    compositor = _pid_do_compositor(s.maquina)
    pads = pads_do_produto(s.maquina.dispositivos_de_entrada())
    uinput = [p for p in pads if p.backend == "uinput"]
    por_jogador = {int(c["player"]): c for c in mesa}
    for c in mesa:
        if c.get("vpad_backend") != "uhid":
            continue
        jogador = f"P{c['player']}"
        caminho = s.maquina.hidraw_do_pad_uhid(int(c["player"]))
        if caminho is None:
            _passo(s, "3c, a vibração que o jogo pede", jogador, transporte_de(c), NAO_SEI,
                   "o hidraw do pad uhid não apareceu no sysfs")
            continue
        leitor.marcar(f"{jogador}:jogo:base")
        s.maquina.dormir(2.0)
        leitor.marcar(f"{jogador}:jogo:pedido")
        escreveu = s.maquina.escrever_no_pad(caminho, relatorio_dos_motores(200))
        s.maquina.dormir(1.5)
        leitor.marcar(f"{jogador}:jogo:fim")
        s.maquina.escrever_no_pad(caminho, relatorio_dos_motores(0))
        s.declarar(f"3c: um 0x02 com os motores no pad de {jogador}", "motores 0", "motores 0")
        if not escreveu:
            _passo(s, "3c, a vibração que o jogo pede", jogador, transporte_de(c), NAO_SEI,
                   "o hidraw do pad não aceitou a escrita (permissão?)")
            continue
        tremores = tremor_por_fisico(
            leitor.quadros,
            (leitor.marcas[f"{jogador}:jogo:base"], leitor.marcas[f"{jogador}:jogo:pedido"]),
            (leitor.marcas[f"{jogador}:jogo:pedido"] + 0.3, leitor.marcas[f"{jogador}:jogo:fim"]),
        )
        veredito, porque = veredito_do_tremor(tremores, _hex12(c.get("uniq")) or "")
        _passo(s, "3c, a vibração que o jogo pede", jogador, transporte_de(c), veredito, porque,
               comando="0x02 USB (build_usb_report) no hidraw do pad", mexe=["os motores, pelo pad"])
    for pad in uinput:
        antes = _nao_nulos_por_jogador(s.maquina.estado() or {})
        leitor.marcar(f"{pad.handlers}:base")
        s.maquina.dormir(2.0)
        leitor.marcar(f"{pad.handlers}:pedido")
        ok = s.maquina.pulso_de_ff(pad, 1.0)
        leitor.marcar(f"{pad.handlers}:fim")
        s.maquina.dormir(0.5)
        depois = _nao_nulos_por_jogador(s.maquina.estado() or {})
        subiram = [j for j in depois if depois[j] > antes.get(j, 0)]
        s.declarar(f"3c: um pulso FF no pad uinput {pad.handlers}", "sem efeito", "efeito apagado")
        if not ok or len(subiram) != 1 or subiram[0] not in por_jogador:
            _passo(s, "3c, a vibração que o jogo pede", "?", "—", NAO_SEI if not ok else VERMELHO,
                   "o pulso não abriu o nó" if not ok
                   else f"o pulso subiu o contador de {len(subiram)} jogador(es), e o certo é um",
                   comando="EV_FF no evdev do pad uinput (casado por pulso, 01 A2)")
            continue
        c = por_jogador[subiram[0]]
        tremores = tremor_por_fisico(
            leitor.quadros,
            (leitor.marcas[f"{pad.handlers}:base"], leitor.marcas[f"{pad.handlers}:pedido"]),
            (leitor.marcas[f"{pad.handlers}:pedido"] + 0.3, leitor.marcas[f"{pad.handlers}:fim"]),
        )
        veredito, porque = veredito_do_tremor(tremores, _hex12(c.get("uniq")) or "")
        _passo(s, "3c, a vibração que o jogo pede", f"P{subiram[0]}", transporte_de(c), veredito, porque,
               comando="EV_FF no evdev do pad uinput (casado por pulso, 01 A2)", mexe=["os motores, pelo pad"])
    if compositor is not None and _pid_do_compositor(s.maquina) != compositor:
        raise Recusa("o compositor trocou de PID durante a vibração pelo pad: paro aqui")
    sem_dono = sum(1 for ln in _desde_o_ultimo_boot(s.maquina.diario_do_daemon()) if "rumble_sem_dono" in ln)
    _passo(s, "3c, rumble_sem_dono no diário", "todos", "—", REGISTRO, f"{sem_dono} linha(s) desde o boot")


def _nao_nulos_por_jogador(estado: Mapping[str, Any]) -> dict[int, int]:
    return {
        int(p["player"]): int(p.get("ff_nao_nulo_count") or 0)
        for p in _lista(_dict(estado.get("rumble_ff")).get("per_vpad"))
        if isinstance(p.get("player"), int)
    }


def relatorio_dos_motores(forca: int) -> bytes:
    """Um ``0x02`` USB com os dois motores em ``forca`` — o que um jogo mandaria ao pad."""
    from hefesto_dualsense4unix.core import ds_output_report as saida

    comum = bytearray(saida.COMMON_LEN)
    comum[0] = saida.VALID_FLAG0_COMPATIBLE_VIBRATION | saida.VALID_FLAG0_HAPTICS_SELECT
    comum[2] = comum[3] = max(0, min(255, forca))
    return bytes(saida.build_usb_report(comum))


def _o_gatilho(s: Sessao, mesa: Sequence[Mapping[str, Any]], leitor: LeitorDosFisicos) -> None:
    """3d: o gatilho por controle muda só no alvo. A volta é o reinício declarado (C10)."""
    for c in mesa:
        jogador = f"P{c['player']}"
        leitor.marcar(f"{jogador}:gatilho:base")
        s.maquina.dormir(1.0)
        leitor.marcar(f"{jogador}:gatilho:pedido")
        s.maquina.chamar("trigger.set", {"side": "right", "mode": "Rigid", "params": [0, 255],
                                         "uniq": c.get("uniq")})
        s.reiniciar_o_daemon_no_fim = True
        s.declarar(f"3d: o gatilho direito Rigid em {jogador} (camada da usuária)", "o do perfil",
                   "o do perfil, pelo reinício do daemon")
        s.maquina.dormir(1.0)
        leitor.marcar(f"{jogador}:gatilho:fim")
        base = (leitor.marcas[f"{jogador}:gatilho:base"], leitor.marcas[f"{jogador}:gatilho:pedido"])
        janela = (leitor.marcas[f"{jogador}:gatilho:pedido"] + 0.3, leitor.marcas[f"{jogador}:gatilho:fim"])
        doze = _hex12(c.get("uniq")) or ""
        mudou = {d: gatilho_mudou(q, base, janela) for d, q in leitor.quadros.items()}
        outros = [d for d, m in mudou.items() if d != doze and m]
        if mudou.get(doze) is None:
            veredito, porque = NAO_SEI, "o físico do alvo não se leu"
        elif outros:
            veredito, porque = VERMELHO, f"o gatilho mudou em {len(outros)} vizinho(s)"
        elif mudou[doze]:
            veredito, porque = VERDE, "o estado do gatilho mudou só no alvo"
        else:
            veredito, porque = VERMELHO, "o estado do gatilho do alvo não mudou"
        _passo(s, "3d, o gatilho", jogador, transporte_de(c), veredito, porque,
               comando='trigger.set {"side":"right","mode":"Rigid","params":[0,255],"uniq":…}',
               mexe=["o gatilho direito, na camada da usuária"])
        # Sem a camada publicada, a mudança do próximo jogador leria a deste.
        s.maquina.chamar("trigger.set", {"side": "right", "mode": "Off", "params": [],
                                         "uniq": c.get("uniq")})


def _a_bateria_em_tres_reguas(s: Sessao, mesa: Sequence[Mapping[str, Any]], leitor: LeitorDosFisicos) -> None:
    if str(ENSAIOS) not in sys.path:
        sys.path.insert(0, str(ENSAIOS))
    try:
        from entrada_em_repouso import STATUS, bateria_do_status
    except Exception:
        return
    baterias = s.maquina.baterias()
    for c in mesa:
        jogador = f"P{c['player']}"
        doze = _hex12(c.get("uniq")) or ""
        quadros = leitor.quadros.get(doze) or []
        corpo = next((cc for _t, q in reversed(quadros) if (cc := corpo_do_quadro(q)) is not None), None)
        do_fio = bateria_do_status(corpo[STATUS[0]])[0] if corpo is not None else None
        do_kernel = baterias.get(doze, ("", ""))[0]
        do_estado = c.get("battery_pct")
        valores = [v for v in (do_fio, int(do_kernel) if do_kernel.isdigit() else None, do_estado)
                   if isinstance(v, int)]
        if len(valores) < 3:
            _passo(s, "a bateria em três réguas", jogador, transporte_de(c), NAO_SEI,
                   f"só {len(valores)} das três réguas se leram")
            continue
        _passo(s, "a bateria em três réguas", jogador, transporte_de(c),
               VERDE if max(valores) - min(valores) <= 10 else VERMELHO,
               f"o fio diz {do_fio}%, o kernel {do_kernel}%, o estado {do_estado}%")


def _o_dono_de_cada_escrita(s: Sessao, sondas: Mapping[str, Any]) -> None:
    texto = _colher_sonda(s, sondas.get("nucleo-por-processo.bt", "não medido"), 120.0)
    if texto is None:
        _passo(s, "o dono de cada escrita", "todos", "—", NAO_SEI,
               str(sondas.get("nucleo-por-processo.bt", "não medido")))
        return
    s.gravar("saidas/nucleo.txt", texto)
    try:
        ordem = ordem_da_chave_do_hw((SONDAS / "nucleo-por-processo.bt").read_text(encoding="utf-8"))
    except OSError:
        ordem = []
    if "pid" not in ordem:
        _passo(s, "o dono de cada escrita", "todos", "—", NAO_SEI,
               "a sonda desta instalação não traz o pid na chave do @hw: o jogo e a Steam não se separam")
        return
    estado = s.maquina.estado() or {}
    appid = _dict(estado.get("jogo_steam")).get("appid")
    processos = s.maquina.processos()
    daemon = [pid for pid, (_p, comm) in processos.items() if comm.startswith("hefesto")]
    teclado = [pid for pid, (_p, comm) in processos.items() if comm == "cosmic-osk"]
    dono = dono_pela_arvore(processos, jogo=s.maquina.pids_do_jogo(appid) if appid else (),
                            daemon=daemon, teclado=teclado)
    escritas = escritas_por_dono(texto, ordem, dono)
    por_dono: Counter[str] = Counter()
    for (quem, *_resto), vezes in escritas.items():
        por_dono[quem] += vezes
    da_steam = por_dono.get("steam", 0)
    _passo(s, "o dono de cada escrita", "todos", "—", VERMELHO if da_steam else REGISTRO,
           (f"a Steam escreveu {da_steam} vez(es) em hidraw; " if da_steam else "")
           + "por dono: " + (", ".join(f"{q}={n}" for q, n in por_dono.most_common()) or "nenhuma escrita"),
           comando="bpftrace scripts/sondas/nucleo-por-processo.bt")


# ---------------------------------------------------------------------------
# som (§4.6): ESCREVE som; a bancada
# ---------------------------------------------------------------------------

#: Um tom por jogador, para a FFT separar quem tocou.
FREQUENCIA_DO_JOGADOR = {1: 700.0, 2: 900.0, 3: 1100.0, 4: 1300.0}


def _tom_em_wav(caminho: Path, frequencia: float, segundos: float = 2.0, taxa: int = 48000) -> Path:
    import struct
    import wave

    with wave.open(str(caminho), "wb") as arquivo:
        arquivo.setnchannels(2)
        arquivo.setsampwidth(2)
        arquivo.setframerate(taxa)
        quadros = bytearray()
        for i in range(int(segundos * taxa)):
            amostra = int(0.3 * 32767 * math.sin(2 * math.pi * frequencia * i / taxa))
            quadros += struct.pack("<hh", amostra, amostra)
        arquivo.writeframes(bytes(quadros))
    return caminho


def potencia_em(amostras: Sequence[int], frequencia: float, taxa: int = 48000) -> float:
    """Goertzel: a potência de ``amostras`` numa frequência só."""
    if not amostras:
        return 0.0
    k = round(len(amostras) * frequencia / taxa)
    w = 2 * math.pi * k / len(amostras)
    coef = 2 * math.cos(w)
    s1 = s2 = 0.0
    for x in amostras:
        s0 = x + coef * s1 - s2
        s2, s1 = s1, s0
    return s1 * s1 + s2 * s2 - coef * s1 * s2


def pico_em_db(amostras: Sequence[int], frequencia: float, taxa: int = 48000) -> float:
    """Quantos dB o pico na frequência pedida fica acima da média de quatro vizinhas."""
    alvo = potencia_em(amostras, frequencia, taxa)
    vizinhas = [potencia_em(amostras, frequencia + d, taxa) for d in (-150.0, -80.0, 80.0, 150.0)]
    ruido = max(sum(vizinhas) / len(vizinhas), 1e-9)
    return 10 * math.log10(max(alvo, 1e-9) / ruido)


def sub_som(s: Sessao, a: argparse.Namespace) -> None:
    e = s.estado_inicio
    mesa = controles_na_mesa(e)
    if _jogo_vivo(e):
        raise Recusa("há jogo aberto: o tom do protocolo tocaria por cima do jogo")
    s.reservar_a_bancada()
    rc, texto = s.rodar_ensaio("os_nos_de_som_por_controle.py", "--json", teto_s=60.0)
    dado = _json_do_ensaio(texto)
    nos = _por_chave(_lista(dado), "mac") if isinstance(dado, list) else {}
    ouvidos = [n[0].get("fonte_fisica") for n in nos.values() if len(n) == 1 and n[0].get("fonte_fisica")]
    try:
        from hefesto_dualsense4unix.integrations.alto_falante_bt import nome_do_sink
    except Exception:
        nome_do_sink = None
    for c in mesa:
        jogador = f"P{c['player']}"
        frequencia = FREQUENCIA_DO_JOGADOR.get(int(c["player"]), 1500.0)
        wav = _tom_em_wav(s.privada / f"tom-{jogador}.wav", frequencia)
        no = (nos.get(chave_mascarada(c.get("uniq")) or "") or [{}])[0]
        if c.get("transport") == "bt":
            sink = nome_do_sink(str(c.get("uniq") or "")) if nome_do_sink else ""
            linha = "4a, o alto-falante no rádio"
        else:
            sink = str(no.get("sink_fisico") or "")
            linha = "4a, o alto-falante no cabo"
        if not sink:
            _passo(s, linha, jogador, transporte_de(c), NAO_SEI, "o nó de saída deste controle não se achou")
            continue
        ouvido = next((o for o in ouvidos if o != no.get("fonte_fisica")), None)
        tocador = s.maquina.tocar(sink, wav)
        s.declarar(f"4a: um tom de {frequencia:g} Hz em {jogador}", "silêncio", "silêncio")
        pontes: list[dict[int, Any]] = []
        amostras: list[int] = []
        if ouvido:
            amostras = s.maquina.gravar_som(str(ouvido), 1.5)
        for _ in range(3):
            s.maquina.dormir(0.4)
            estado = s.maquina.estado() or {}
            pontes.append({int(x["player"]): x.get("ponte_do_radio") for x in controles_na_mesa(estado)})
        s.maquina.esperar(tocador, 5.0)
        if tocador is None:
            _passo(s, linha, jogador, transporte_de(c), NAO_SEI, "sem paplay nesta máquina")
            continue
        partes: list[str] = []
        veredito = VERDE
        if c.get("transport") == "bt":
            numero = int(c["player"])
            com_som = {j for p in pontes for j, v in p.items() if v == "som"}
            if numero not in com_som:
                veredito = VERMELHO
                partes.append("a ponte do rádio não abriu no alvo")
            if com_som - {numero}:
                veredito = VERMELHO
                partes.append(f"a ponte abriu em {sorted(com_som - {numero})}")
        if amostras:
            db = pico_em_db(amostras, frequencia)
            partes.append(f"o microfone do cabo ouviu {db:.1f} dB acima do ruído")
            if db < 20.0 and veredito == VERDE:
                veredito = VERMELHO
        elif veredito == VERDE:
            veredito = NAO_SEI
            partes.append("sem um microfone no cabo para ouvir o tom")
        _passo(s, linha, jogador, transporte_de(c), veredito, "; ".join(partes) or "o tom saiu só no alvo",
               comando=f"paplay --device=<nó de {jogador}> tom de {frequencia:g} Hz", mexe=["um tom de 2 s"])

    for c in mesa:
        jogador = f"P{c['player']}"
        audio = _dict(c.get("audio"))
        hz = c.get("hz_voz")
        if c.get("transport") != "bt":
            continue
        if audio.get("canal_ativo") is not True or audio.get("mic_mudo") is True:
            veredito = VERMELHO if isinstance(hz, (int, float)) and hz > 0 else NAO_SE_APLICA
            porque = f"o canal está desligado ou mudo e o fluxo é {hz}"
        elif isinstance(hz, (int, float)):
            veredito = VERDE if hz >= 90 else VERMELHO
            porque = f"hz_voz={hz} com o canal ligado"
        else:
            veredito, porque = NAO_SEI, "o daemon não publica o hz_voz"
        _passo(s, "4b, o microfone no rádio (o fluxo)", jogador, transporte_de(c), veredito, porque,
               comando="state_full.controllers[].hz_voz")

    if any(c.get("transport") == "usb" for c in mesa):
        _rc, texto = s.rodar_ensaio("microfone_no_cabo.py", "--segundos", "5",
                                    "--csv", str(s.privada / "mic_cabo.csv"), teto_s=90.0)
        _passo(s, "4b, o microfone no cabo", "todos", "cabo", NAO_SEI,
               "o ensaio não tem --json; o resumo diz: " + _resumo_do_ensaio(s.mascarado(texto)))
        _rc, texto = s.rodar_ensaio("o_caminho_do_mic_no_cabo.py", "--censo", teto_s=60.0)
        _passo(s, "4b, a cadeia do microfone no cabo", "todos", "cabo", REGISTRO,
               _resumo_do_ensaio(s.mascarado(texto)))

    if s.maquina.existe("forja-speak"):
        rc, texto = s.maquina.rodar(["forja-speak", "--list"], 30.0)
        s.gravar("som/forja-speak.txt", texto)
        _passo(s, "4a, o jogo acha o alto-falante (a Forja)", "todos", "—",
               VERDE if rc == 0 else VERMELHO, f"forja-speak --list rc={rc}")
    else:
        _passo(s, "4a, o jogo acha o alto-falante (a Forja)", "todos", "—", NAO_SEI,
               "não medido (sem a Forja nesta máquina)")


# ---------------------------------------------------------------------------
# haptica (§4.7) e tudo-junto (§4.9): fecham depois da parte 1 da A-HAPTICA
# ---------------------------------------------------------------------------

_ESPERA_A_HAPTICA = (
    "não medido: espera a parte 1 da A-HAPTICA-DO-RADIO-OBEDECE-AO-SINAL-DO-JOGO-01 "
    "(sem ela o portão do evdev fecha a ponte sem jogo; 01 §9)"
)


def sub_haptica(s: Sessao, a: argparse.Namespace) -> None:
    for c in controles_na_mesa(s.estado_inicio):
        _passo(s, "5, a háptica", f"P{c['player']}", transporte_de(c), NAO_SEI, _ESPERA_A_HAPTICA)


def sub_tudo_junto(s: Sessao, a: argparse.Namespace) -> None:
    _passo(s, "tudo no mesmo controle", "todos", "—", NAO_SEI,
           _ESPERA_A_HAPTICA + "; a exclusividade som/vibração pelo rádio é o vermelho sabido")


# ---------------------------------------------------------------------------
# movimento (§4.8): só lê; o touchpad com o dedo é da mão dela
# ---------------------------------------------------------------------------


def sub_movimento(s: Sessao, a: argparse.Namespace) -> None:
    if _parar_se_o_1a_caiu(s, a):
        return
    e = s.estado_inicio
    mesa = controles_na_mesa(e)
    for nome in ("giro_e_buraco.py", "imu_no_cabo.py"):
        _rc, texto = s.rodar_ensaio(nome, "--segundos", "10", teto_s=90.0)
        _passo(s, f"o físico ({nome.removesuffix('.py')})", "todos", "—", NAO_SEI,
               "o ensaio não tem --json; o resumo diz: " + _resumo_do_ensaio(s.mascarado(texto)))
    no_uhid = [c for c in mesa if c.get("vpad_backend") == "uhid"]
    if no_uhid:
        args = ["--so-medir", "--segundos", "3"]
        for lib in a.lib or ():
            args += ["--lib", lib]
        rc, texto = s.rodar_ensaio("o_jogo_para_de_ver_o_giro.py", *args, teto_s=90.0)
        _passo(s, "o pad pelo SDL (a linha do jogo nativo)", "todos", "—",
               {0: VERDE, 1: VERMELHO}.get(rc, NAO_SEI),
               f"o_jogo_para_de_ver_o_giro --so-medir rc={rc} (o SDL pelo evdev; no Proton é a posse, C5)")
    per_vpad = {int(p["player"]): p for p in _lista(_dict(e.get("rumble_ff")).get("per_vpad"))
                if isinstance(p.get("player"), int)}
    emulacao = _dict(e.get("gamepad_emulation"))
    for c in mesa:
        jogador = f"P{c['player']}"
        pad = per_vpad.get(int(c["player"]), {})
        if c.get("vpad_backend") == "uhid":
            hz = float(pad.get("motion_hz") or 0.0)
            _passo(s, "o movimento chega ao pad", jogador, transporte_de(c),
                   VERDE if pad.get("motion_streaming") and hz >= 200 else VERMELHO,
                   f"motion_streaming={pad.get('motion_streaming')} a {hz:.0f} Hz")
        else:
            # Ordem dela de 27/09: no modo Xbox, tudo funciona. A ausência
            # declarada não é mais o verde com ressalva do 01 §4.8.
            _passo(s, "o movimento chega ao pad", jogador, transporte_de(c), VERMELHO,
                   f"o pad {c.get('vpad_backend')} não leva movimento (canal_sem_imu="
                   f"{emulacao.get('canal_sem_imu')}); no modo Xbox tudo funciona (NO-MODO-XBOX-TUDO-FUNCIONA-01)")
    if _jogo_vivo(e):
        _a_posse_do_jogo(s, mesa, per_vpad)
    else:
        _passo(s, "o pad no Proton (a posse)", "todos", "—", NAO_SE_APLICA, "sem jogo aberto")
    _passo(s, "o touchpad com o dedo", "todos", "—", NAO_COBERTO, "é da mão dela: um deslizar por controle")


def _a_posse_do_jogo(s: Sessao, mesa: Sequence[Mapping[str, Any]], per_vpad: Mapping[int, Mapping[str, Any]]) -> None:
    """C5: o jogo no Proton lê o giro pelo `hidraw` do pad; a posse dele e o `motion_hz`."""
    appid = _dict(s.estado_inicio.get("jogo_steam")).get("appid")
    abertos: set[str] = set()
    for pid in s.maquina.pids_do_jogo(appid) if appid else ():
        abertos.update(Path(alvo).name for alvo in s.maquina.fds_de(pid) if alvo.startswith("/dev/hidraw"))
    for c in mesa:
        jogador = f"P{c['player']}"
        caminho = s.maquina.hidraw_do_pad_uhid(int(c["player"]))
        tem = caminho is not None and Path(caminho).name in abertos
        hz = float(_dict(per_vpad.get(int(c["player"]))).get("motion_hz") or 0.0)
        _passo(s, "o pad no Proton (a posse)", jogador, transporte_de(c),
               VERDE if tem and hz > 0 else VERMELHO,
               f"a árvore do jogo {'tem' if tem else 'NÃO tem'} o hidraw do pad; motion_hz={hz:.0f}")


# ---------------------------------------------------------------------------
# --veredito (§4.10)
# ---------------------------------------------------------------------------


def sessoes_em(pasta: Path) -> list[Path]:
    """As pastas de sessão (as que têm ``passos.jsonl``) sob ``pasta``, em ordem."""
    if (pasta / "passos.jsonl").is_file():
        return [pasta]
    return sorted(p.parent for p in pasta.rglob("passos.jsonl"))


def veredito(pasta: Path | None) -> int:
    """A matriz subcomando × jogador × transporte × modo, e a tabela «mexeu e voltou».

    ``rc=0`` só com zero vermelho, zero «não sei» e nenhuma recusa (a volta
    inteira). «Não coberto» aparece e não reprova.
    """
    if pasta is None:
        base = pasta_privada()
        todas = sorted(p for p in base.iterdir() if p.is_dir()) if base.is_dir() else []
        sessoes = sessoes_em(todas[-1]) if todas else []
    else:
        sessoes = sessoes_em(pasta)
    if not sessoes:
        print("nenhuma sessão do o_basico para ler")
        return RC_RECUSADO
    passos: list[dict[str, Any]] = []
    recusas: list[str] = []
    mexeu: list[dict[str, Any]] = []
    for sessao in sessoes:
        for linha in (sessao / "passos.jsonl").read_text(encoding="utf-8").splitlines():
            with contextlib.suppress(ValueError):
                passos.append(json.loads(linha))
        with contextlib.suppress(OSError, ValueError):
            resumo = json.loads((sessao / "resumo.json").read_text(encoding="utf-8"))
            recusas += [f"{resumo.get('sub')}: {r}" for r in resumo.get("recusas") or []]
            mexeu += [dict(m, sub=resumo.get("sub")) for m in resumo.get("mexeu") or []]
    colunas = sorted({(p["jogador"], p["transporte"], p["modo"]) for p in passos})
    linhas = sorted({(p["sub"], p["linha"]) for p in passos}, key=lambda x: (ORDEM.index(x[0]) if x[0] in ORDEM else 99, x[1]))
    celula = {(p["sub"], p["linha"], p["jogador"], p["transporte"], p["modo"]): p["veredito"] for p in passos}
    curto = {VERDE: "verde", VERMELHO: "VERMELHO", NAO_SEI: "não sei", REGISTRO: "reg.",
             NAO_SE_APLICA: "n/a", NAO_COBERTO: "não coberto"}
    print("A MATRIZ — subcomando · linha × jogador · transporte · modo")
    print("  " + " | ".join(f"{j} {t} {m}" for j, t, m in colunas))
    for sub, linha in linhas:
        valores = [curto.get(celula.get((sub, linha, *col), ""), "—") for col in colunas]
        print(f"  {sub} · {linha}: " + " | ".join(valores))
    print("\nMEXEU E VOLTOU")
    for m in mexeu:
        print(f"  {m.get('sub')}: {m.get('o_que')} — antes {m.get('antes')!r}, depois {m.get('depois')!r},"
              f" voltou={m.get('voltou')}")
    if not mexeu:
        print("  nada foi mexido")
    if recusas:
        print("\nRECUSAS")
        for r in recusas:
            print(f"  {r}")
    contam = [p["veredito"] for p in passos if p["veredito"] in VEREDITOS_QUE_CONTAM]
    rc = RC_RECUSADO if recusas else RC_VERMELHO if VERMELHO in contam else (
        RC_NAO_SEI if NAO_SEI in contam or not contam else RC_VERDE)
    print(f"\nveredito: rc={rc} ({len(sessoes)} sessão(ões), {len(passos)} linha(s))")
    return rc


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

SUBCOMANDOS: dict[str, Callable[[Sessao, argparse.Namespace], None]] = {
    "retrato": sub_retrato,
    "sessao": sub_sessao,  # (noqa-acento: o nome do subcomando é o do protocolo)
    "eixos": sub_eixos,
    "entrada": sub_entrada,
    "saidas": sub_saidas,
    "som": sub_som,
    "haptica": sub_haptica,
    "movimento": sub_movimento,
    "tudo-junto": sub_tudo_junto,
}


def analisador() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="o_basico.py", description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--saida", type=Path, help="a pasta de um estudo (padrão: o estado do Hefesto)")
    ap.add_argument("--jogadores", default="todos", help="P1,P3 | todos")
    ap.add_argument("--esperado", help="ex.: 2cabo+2radio — o retrato recusa (rc=2) se a mesa não for essa")
    ap.add_argument("--seguir", action="store_true", help="não para no 1a vermelho (o veredito segue vermelho)")
    ap.add_argument("--veredito", nargs="?", const="*", metavar="PASTA",
                    help="a sessão mais nova, ou toda sessão sob PASTA")
    sub = ap.add_subparsers(dest="sub")
    for nome in ORDEM:
        p = sub.add_parser(nome)
        if nome == "sessao":  # (noqa-acento: o nome do subcomando é o do protocolo)
            p.add_argument("--segundos", type=float, default=60.0)
            p.add_argument("--boot", action="store_true", help="reinicia o daemon (mexe; nunca com jogo)")
            p.add_argument("--bpftrace", action="store_true", help="as sondas de scripts/sondas/ (sudo)")
        if nome == "eixos":
            p.add_argument("--trocar-modo", choices=("dualsense", "xbox"))
        if nome == "entrada":
            p.add_argument("--segundos", type=float, default=30.0)
            p.add_argument("--bpftrace", action="store_true")
        if nome == "saidas":
            p.add_argument("--so", default="luz,vibracao,vibracao-do-jogo,gatilho")
            p.add_argument("--bpftrace", action="store_true")
        if nome == "movimento":
            p.add_argument("--lib", action="append")
        if nome == "tudo-junto":
            p.add_argument("--minutos", type=float, default=10.0)
    return ap


def executar(argv: Sequence[str], maquina: Maquina | None = None) -> int:
    """O contrato inteiro de uma corrida. ``maquina`` é o dublê das réguas."""
    a = analisador().parse_args(list(argv))
    if a.veredito:
        return veredito(None if a.veredito == "*" else Path(a.veredito))
    nome = a.sub or "retrato"
    for chave, padrao in (("seguir", False), ("esperado", None), ("bpftrace", False),
                          ("boot", False), ("trocar_modo", None), ("segundos", 30.0), ("lib", None)):
        if not hasattr(a, chave):
            setattr(a, chave, padrao)
    maquina = maquina or Maquina()
    saida = a.saida / f"{time.strftime('%Y-%m-%dT%H%M%S', time.localtime(maquina.agora()))}-{nome}" if a.saida else None
    s = Sessao(maquina, nome, saida=saida, comando="o_basico.py " + " ".join(argv), jogadores=a.jogadores)
    if not s.abrir():
        return s.fechar()
    try:
        SUBCOMANDOS[nome](s, a)
    except Recusa as recusa:
        s.recusar(str(recusa))
    finally:
        s.liberar_a_bancada()
        s.relistar_e_conferir()
        for diferenca in s.conferir_a_volta():
            s.recusar(f"não voltou: {diferenca}")
    return s.fechar()


def main() -> int:
    return executar(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
