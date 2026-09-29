#!/usr/bin/env python3
"""Os endpoints de háptica — o laudo do que o GE-Proton leria, e o que cada canal toca.

**O NOME MUDOU EM 28/09/2026** (O-BASICO-MEDIDO-01, A5 do protocolo do
básico): este ensaio se chamava ``o_endpoint_de_mentira.py``, e o nome
enganava. Sem argumento ele nunca listou só o endpoint de mentira: o
``status`` lê TODO sink com ``HEFESTO`` no nome, e isso inclui os endpoints do
PRODUTO (``integrations/endpoint_de_haptica.py``, que usa o mesmo molde). Sem
argumento, então, ele é a leitura do produto: um laudo por endpoint vivo, que o
``o_basico.py retrato`` pede com ``--json``. Montar um de mentira continua
existindo, atrás de ``--montar --marca``; o ``--desmontar`` derruba só o que
ele mesmo montou, e nunca um endpoint do produto.

**OS ENDPOINTS DO PRODUTO SÃO POR LUGAR DESDE 28/09/2026**
(A-HAPTICA-CHEGA-A-QUEM-ENTRA-DEPOIS-01): quatro nós, ``…HEFESTOLUGAR1-00…`` a
``…LUGAR4…``, de pé desde o primeiro DualSense da mesa, nos dois transportes. O
laudo lê os quatro, e o que o curador vai gravar sai do dono da lista
(``audio_ks_dualsense.controles_do_registro``).

**A GRAVAÇÃO POR CANAL** (``--gravar SEGUNDOS``) nasce aqui, versionada: o
``medidas/grava_endpoints.sh`` que a auditoria de 27/09 e a
A-HAPTICA-DO-RADIO citam morava no ``/tmp`` e não existe mais (procurado em
28/09). Ela lê o monitor de cada endpoint ao mesmo tempo e diz o RMS de cada
um dos quatro canais — a frente é o alto-falante, os traseiros são os motores
—, que é como se vê, sem a mão dela, se o jogo espelha a vibração nos quatro
lugares ou manda a cada um a sua. Ler o monitor não escreve nada em lugar
nenhum.

O desenho abaixo é o de HAPTICA-POR-RADIO-01, P3, que o ensaio mediu em 18/09.

PELO CABO o jogo acha a háptica porque existe uma placa de áudio de verdade no
controle. PELO RÁDIO não existe: o DualSense não publica endpoint nenhum, e o
jogo não tem onde tocar os canais 3 e 4. Este ensaio monta o endpoint que falta
— um ``module-null-sink`` do PipeWire vestido de DualSense — e MEDE, campo a
campo, o que o GE-Proton leria dele.

POR QUE ISTO BASTA (lido no fonte, 18/09/2026)
-----------------------------------------------
``wine/dlls/winepulse.drv/pulse.c``:

* ``fill_device_info`` (:668) lê barramento, fabricante e produto **do proplist
  do sink** — ``device.bus``, ``device.vendor.id``, ``device.product.id``. Não
  pergunta ao sysfs;
* ``get_container_id`` (:608) só é chamado quando o proplist traz
  ``sysfs.path``; ele sobe ao pai ``usb_device`` no udev e compõe o GUID com
  ``PRODUCT``, ``BUSNUM``, ``DEVNUM`` e ``USEC_INITIALIZED`` **daquele pai**.
  Sem pai USB, devolve ``GUID_NULL``.

Patches ``proton-ds5-haptic``:

* ``is_dualsense_audio_device`` (0063): ``bus == usb && vid == 0x054c && pid in
  (0x0ce6, 0x0df2)`` — tudo do proplist;
* ``is_dualsense_haptic_format`` (0063): ``eRender``, ``FLOAT32LE``, 48 kHz,
  **4 canais**;
* ``pulse_name_looks_like_dualsense_speaker_sink`` (0060): o NOME tem de conter
  ``alsa_output.usb-Sony_Interactive_Entertainment_``, ``Wireless_Controller``
  e ``Speaker__sink``;
* ``is_dualsense_backend_name`` (mmdevapi): ``Sony_Interactive_Entertainment``
  no nome.

**Nada disso pergunta pelo transporte do CONTROLE.** O que o GE inspeciona é o
SINK — e um sink é coisa que o PipeWire monta sem root, sem módulo de kernel e
sem gadget USB. É por isso que o gadget (``usbip-vudc``) deixa de ser
necessário: ele existia para produzir estes mesmos campos.

A ÂNCORA, E POR QUE NÃO SE DEIXA O ``ContainerId`` ZERADO
----------------------------------------------------------
Zerado *funciona* do ponto de vista do casamento — basta o device KS do
prefixo declarar zero também. Mas zero **não é único**: toda saída que não é
USB tem o ``ContainerId`` zerado, e um device KS declarando zero casaria também
com a caixa de som da pessoa. O jogo abriria a háptica no aparelho errado.

Então o sink aponta o ``sysfs.path`` para um ``usb_device`` REAL que não tem
placa de som — uma ÂNCORA. O GUID que sai dali é real, é único e é calculável
dos dois lados: aqui, e no ``audio_ks_dualsense.py``, que grava o device KS.
A âncora é só um endereço de onde tirar quatro números; nada é escrito nela.

O QUE ESTE ENSAIO NÃO DECIDE
-----------------------------
Se a RE Engine ACEITA este endpoint. Isso é medida de bancada, com o jogo
aberto e o controle no rádio, e está escrita na sprint. Aqui se mede só o que é
medível sem o jogo: que os campos chegam ao nó como o GE os lê.
"""

from __future__ import annotations

import argparse
import array
import math
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]
if str(_RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(_RAIZ / "src"))

from hefesto_dualsense4unix.core.formas_do_endereco import mascarar
from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl
from hefesto_dualsense4unix.integrations.audio_ks_dualsense import (
    container_id,
    controles_do_registro,
    variantes_de_data4,
)
from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
    MARCA_DO_ENSAIO as _MARCA_DO_ENSAIO_DO_PRODUTO,
)

#: O VID/PID que o GE exige NO PROPLIST — não no aparelho.
VID_SONY = "054c"
PID_DUALSENSE = "0ce6"

#: O nome tem de carregar as TRÊS agulhas dos patches, e um discriminador por
#: controle: dois controles com o mesmo nome viram um endpoint só (patch 0186,
#: `is_shared_sony_mono_backend_name`).
_MOLDE_DO_NOME = (
    "alsa_output.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller_HEFESTO{marca}-00.HiFi__Speaker__sink"
)
_AGULHAS = (
    "alsa_output.usb-Sony_Interactive_Entertainment_",
    "Wireless_Controller",
    "Speaker__sink",
)
#: `PA_NAME_MAX` é 128 com o `\0`; um nome maior é recusado pelo servidor.
_MAX_NOME = 127

TAXA = 48000
CANAIS = 4

#: O nó não pode virar a saída padrão da máquina. Mesma razão e mesmo valor do
#: nó do alto-falante (`alto_falante_bt.PRIORIDADE_SESSAO_DO_SOM`).
_PRIORIDADE = 0

#: A marca que só o endpoint montado por ESTE ensaio carrega. O ``--desmontar``
#: derruba só os módulos que a trazem: o produto monta endpoints com o mesmo
#: molde de nome, e derrubá-los tiraria a háptica de quem joga. O dono é o
#: produto desde 28/09/2026: a varredura de órfãos dele pula o que traz a
#: marca, e duas grafias dela divergiriam no dia em que uma mudasse.
MARCA_DO_ENSAIO = _MARCA_DO_ENSAIO_DO_PRODUTO


@dataclass(frozen=True)
class Ancora:
    """Um ``usb_device`` de onde o ``winepulse`` tira o ``ContainerId``.

    **O nó declara o FILHO, e o GUID sai do PAI.** O
    ``udev_device_get_parent_with_subsystem_devtype`` devolve um ancestral,
    nunca o próprio device: declarar a âncora nua faz o Wine subir ao hub raiz
    e todos os controles do mesmo barramento casarem com o mesmo container.
    Medido no jogo em 18/09/2026 — o endpoint saiu com o GUID do `1d6b:0002`.
    Por isso :attr:`declarado` é a interface (``<bus>-<porta>:1.0``), que é a
    forma de uma placa de som de verdade: o caminho dela é o do ``sound/card``,
    cujo pai é o aparelho.
    """

    syspath: str
    #: O que vai no ``sysfs.path`` do nó: um filho de :attr:`syspath`.
    declarado: str
    vid: int
    pid: int
    bus: int
    dev: int
    usec: int
    nome: str

    def container_id(self) -> str:
        """A conta do ``create_usb_dev_container_id`` (pulse.c:597).

        ``Data1 = MAKELONG(vid, pid)`` — e a ordem é essa mesmo: o campo BAIXO
        é o ``vid``. ``Data4`` são os 8 bytes little-endian do
        ``USEC_INITIALIZED``.

        **O `& 0xFF` no barramento e no device não é zelo:** na origem os dois
        são ``uint8_t`` (``create_usb_dev_container_id``), e um `devnum` acima
        de 255 — que acontece em host cheio — dobra ali. Sem a máscara, esta
        conta e a do Wine divergiriam exatamente nos casos raros, que são os
        piores de diagnosticar.
        """
        data1 = ((self.pid & 0xFFFF) << 16) | (self.vid & 0xFFFF)
        d4 = (self.usec & 0xFFFFFFFFFFFFFFFF).to_bytes(8, "little")
        bus, dev = self.bus & 0xFF, self.dev & 0xFF
        return f"{{{data1:08x}-{bus:04x}-{dev:04x}-{d4[:2].hex()}-{d4[2:].hex()}}}"


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="ascii", errors="replace").strip()
    except OSError:
        return ""


def _usec(dev: Path, udev_data: Path) -> int:
    majmin = _ler(dev / "dev")
    if ":" not in majmin:
        return 0
    for linha in _ler(udev_data / f"c{majmin}").splitlines():
        if linha.startswith("I:"):
            try:
                return int(linha[2:])
            except ValueError:
                return 0
    return 0


def ancoras(
    sysfs: Path = Path("/sys"), udev_data: Path = Path("/run/udev/data")
) -> list[Ancora]:
    """Os ``usb_device`` que servem de âncora, na ordem do barramento.

    **Fora ficam os que têm placa de som**: o ``ContainerId`` de um deles já é o
    de um endpoint de verdade, e reusá-lo faria dois endpoints dizerem ser o
    mesmo aparelho.
    """
    raiz = sysfs / "bus" / "usb" / "devices"
    achadas: list[Ancora] = []
    try:
        entradas = sorted(raiz.iterdir())
    except OSError:
        return achadas
    for dev in entradas:
        vendor, produto = _ler(dev / "idVendor"), _ler(dev / "idProduct")
        bus, num = _ler(dev / "busnum"), _ler(dev / "devnum")
        if not (vendor and produto and bus.isdigit() and num.isdigit()):
            continue
        if any(dev.glob("*/sound/card*")):
            continue
        # A interface que o nó vai declarar. Sem nenhuma, o aparelho não está
        # configurado e não serve de âncora: o Wine subiria ao hub raiz.
        interface = next((i for i in sorted(dev.glob(f"{dev.name}:*")) if (i / "uevent").is_file()), None)
        if interface is None:
            continue
        try:
            vid, pid = int(vendor, 16), int(produto, 16)
        except ValueError:
            continue
        raiz_txt = str(sysfs.resolve())
        achadas.append(
            Ancora(
                syspath=str(dev.resolve()).replace(raiz_txt, "", 1),
                declarado=str(interface.resolve()).replace(raiz_txt, "", 1),
                vid=vid,
                pid=pid,
                bus=int(bus),
                dev=int(num),
                usec=_usec(dev, udev_data),
                nome=_ler(dev / "product") or f"{vendor}:{produto}",
            )
        )
    return achadas


def nome_do_endpoint(marca: str) -> str:
    """``marca`` são os seis hex do rabo do ``uniq`` — a identidade do controle."""
    nome = _MOLDE_DO_NOME.format(marca=marca)
    if len(nome) > _MAX_NOME:
        raise ValueError(f"nome de {len(nome)} bytes; o servidor recusa acima de {_MAX_NOME}")
    return nome


def propriedades(ancora: Ancora, marca: str) -> str:
    """O ``sink_properties=``, ENTRE ASPAS DUPLAS.

    As aspas são a cura conhecida desta casa: sem elas o parser do
    ``pipewire-pulse`` corta o valor no primeiro espaço e só a primeira
    propriedade chega — com a régua dando verde por ler o argv, não o nó.
    """
    campos = (
        "device.bus=usb",
        f"device.vendor.id={VID_SONY}",
        f"device.product.id={PID_DUALSENSE}",
        f"sysfs.path={ancora.declarado}",
        "device.vendor.name='Sony Interactive Entertainment'",
        f"device.description='DualSense {marca} (háptica pelo rádio)'",
        f"priority.session={_PRIORIDADE}",
        "device.icon_name=audio-speakers",
        MARCA_DO_ENSAIO,
    )
    return 'sink_properties="' + " ".join(campos) + '"'


# -- o que o servidor responde ------------------------------------------------


def _blocos_de_sinks(saida: str) -> list[str]:
    blocos, atual = [], []
    for linha in saida.splitlines():
        if re.match(r"^Sink #\d+", linha):
            if atual:
                blocos.append("\n".join(atual))
            atual = [linha]
        elif atual:
            atual.append(linha)
    if atual:
        blocos.append("\n".join(atual))
    return blocos


def _campo(bloco: str, chave: str) -> str:
    m = re.search(rf'^\s*{re.escape(chave)} = "(.*)"\s*$', bloco, re.M)
    return m.group(1) if m else ""


def nossos_sinks() -> list[dict[str, str]]:
    saida = rodar_pactl(["pactl", "list", "sinks"]) or ""
    achados = []
    for bloco in _blocos_de_sinks(saida):
        m = re.search(r"^\tName: (.+)$", bloco, re.M)
        if not m or "HEFESTO" not in m.group(1):
            continue
        espec = re.search(r"^\tSample Specification: (.+)$", bloco, re.M)
        achados.append(
            {
                "nome": m.group(1),
                "espec": espec.group(1) if espec else "",
                "bus": _campo(bloco, "device.bus"),
                "vid": _campo(bloco, "device.vendor.id"),
                "pid": _campo(bloco, "device.product.id"),
                "sysfs": _campo(bloco, "sysfs.path"),
                "canais": _campo(bloco, "audio.channels"),
                "id": re.search(r"^Sink #(\d+)", bloco, re.M).group(1),
            }
        )
    return achados


def _laudo(sink: dict[str, str]) -> list[tuple[bool, str]]:
    """As perguntas do GE, uma linha por pergunta. Nenhuma delas é opinião."""
    nome = sink["nome"]
    return [
        (sink["bus"] == "usb", f'device.bus == "usb"  (é "{sink["bus"]}")'),
        (sink["vid"].lower() == VID_SONY, f"device.vendor.id == {VID_SONY}  (é {sink['vid']})"),
        (sink["pid"].lower() == PID_DUALSENSE, f"device.product.id == {PID_DUALSENSE}  (é {sink['pid']})"),
        (sink["canais"] == str(CANAIS), f"audio.channels == {CANAIS}  (é {sink['canais']})"),
        (all(a in nome for a in _AGULHAS), "o nome tem as três agulhas dos patches"),
        (bool(sink["sysfs"]), f"sysfs.path presente → ContainerId real  ({sink['sysfs'] or 'AUSENTE: sairia zerado'})"),
    ]


# -- os verbos ----------------------------------------------------------------


def _default_sink() -> str:
    return (rodar_pactl(["pactl", "get-default-sink"]) or "").strip()


def montar(marca: str, ancora: Ancora) -> int:
    nome = nome_do_endpoint(marca)
    antes = _default_sink()
    saida = rodar_pactl(
        [
            "pactl",
            "load-module",
            "module-null-sink",
            f"sink_name={nome}",
            "format=float32le",
            f"rate={TAXA}",
            f"channels={CANAIS}",
            "channel_map=front-left,front-right,rear-left,rear-right",
            propriedades(ancora, marca),
        ]
    )
    linhas = [ln.strip() for ln in (saida or "").splitlines() if ln.strip()]
    if not linhas or not linhas[-1].isdigit():
        _dizer(f"NÃO MONTOU: {saida!r}")
        return 1
    print(f"montado  module #{linhas[-1]}")
    _dizer(f"nome     {nome}")
    print(f"âncora   {ancora.nome}  {ancora.syspath}")
    print(f"declara  {ancora.declarado}   ← o pai DISTO é a âncora")
    print(f"Container{ancora.container_id()}   ← é ISTO que o device KS tem de declarar")
    depois = _default_sink()
    if depois != antes and antes:
        rodar_pactl(["pactl", "set-default-sink", antes])
        _dizer(f"a saída padrão tinha mudado para {depois}; devolvida a {antes}")
    return 0


def desmontar() -> int:
    """Derruba só o que ESTE ensaio montou (a :data:`MARCA_DO_ENSAIO`)."""
    saida = rodar_pactl(["pactl", "list", "short", "modules"]) or ""
    ids = [
        ln.split("\t", 1)[0]
        for ln in saida.splitlines()
        if "module-null-sink" in ln and MARCA_DO_ENSAIO in ln
    ]
    for mid in ids:
        rodar_pactl(["pactl", "unload-module", mid])
    print(f"removidos: {len(ids)} módulo(s) montados por este ensaio")
    return 0


def _dizer(texto: str) -> None:
    """Toda linha pelo dono da máscara: o nome do endpoint carrega o rabo do endereço."""
    print(mascarar(texto))


def leitura() -> dict[str, object]:
    """O laudo de cada endpoint vivo, na forma que o ``o_basico.py`` lê (``--json``)."""
    endpoints = []
    for sink in nossos_sinks():
        laudo = _laudo(sink)
        endpoints.append({
            "nome": mascarar(sink["nome"]),
            "espec": sink["espec"],
            "laudo": [[ok, mascarar(frase)] for ok, frase in laudo],
            "completo": all(ok for ok, _frase in laudo),
        })
    completos = sum(1 for e in endpoints if e["completo"])
    return {
        "veredito": f"{completos} de {len(endpoints)} endpoint(s) com o laudo inteiro",
        "alvos_inicio": [e["nome"] for e in endpoints],
        "alvos_fim": [e["nome"] for e in endpoints],
        "mexeu": [],
        "medidas": {"endpoints": len(endpoints), "completos": completos},
        "endpoints": endpoints,
    }


def status() -> int:
    """A leitura do produto: um laudo por endpoint vivo, o do produto e o de mentira."""
    achados = nossos_sinks()
    if not achados:
        _dizer("nenhum endpoint de háptica no servidor de som")
        return 0
    for sink in achados:
        _dizer(f"\nSink #{sink['id']}  {sink['nome']}")
        _dizer(f"  {sink['espec']}")
        for ok, frase in _laudo(sink):
            _dizer(f"  [{'x' if ok else ' '}] {frase}")
    # O FECHO DO CÍRCULO: o que o curador vai gravar sai da MESMA função que
    # ele lê — o dono da lista, os lugares e o cabo que nenhum lugar serve. Se
    # estas linhas não aparecerem, o device KS não sairá — e foi assim que o
    # erro de um nível na árvore do USB se escondeu.
    for controle in controles_do_registro():
        guids = " · ".join(container_id(controle, d4) for d4 in variantes_de_data4(controle, []))
        _dizer(f"\n  o device KS vai declarar: {guids}")
    return 0 if all(all(ok for ok, _f in _laudo(s)) for s in achados) else 1


# -- a gravação por canal -----------------------------------------------------

#: A latência do gravador. **Explícita**, e o número é o dos gravadores desta
#: casa: sem ela o servidor escolhe um buffer generoso e a leitura chega dois
#: segundos atrasada (a memória «gravador sem latência atrasa dois segundos»).
_LATENCIA_MS = 40


def rms_por_canal(pcm: bytes, canais: int = CANAIS) -> list[float]:
    """O RMS de cada canal de um PCM ``float32le`` intercalado. Função pura.

    O resto que não fecha um quadro inteiro (``4 × canais`` bytes) sai: um
    gravador interrompido no meio de um quadro não pode deslocar os canais.
    """
    amostras = array.array("f")
    inteiro = len(pcm) - len(pcm) % (4 * canais)
    amostras.frombytes(pcm[:inteiro])
    if sys.byteorder != "little":
        amostras.byteswap()
    quadros = len(amostras) // canais
    if quadros == 0:
        return [0.0] * canais
    return [
        math.sqrt(sum(x * x for x in amostras[c::canais]) / quadros) for c in range(canais)
    ]


def argv_da_gravacao(nome: str) -> list[str]:
    """O ``parec`` que lê o monitor de um endpoint, em quatro canais.

    ``parec`` pelo NOME do ``.monitor``, e não o ``pw-record`` pelo nome: o
    ``pw-record --target=<nome>.monitor`` caiu na fonte padrão em 16/09/2026
    (SOM-ECO-02, a tabela em ``alto_falante_bt.argv_do_gravador``), e o
    ``parec`` acertou pelo nome.
    """
    return [
        "parec", f"--device={nome}.monitor", "--format=float32le", f"--rate={TAXA}",
        f"--channels={CANAIS}", f"--latency-msec={_LATENCIA_MS}", "--raw",
    ]


def gravar(segundos: float) -> dict[str, object]:
    """Grava o monitor de TODOS os endpoints ao mesmo tempo e diz o RMS de cada canal."""
    if shutil.which("parec") is None:
        return {"veredito": "sem parec: não há como ler o monitor", "endpoints": []}
    sinks = nossos_sinks()
    gravadores = []
    for sink in sinks:
        try:
            proc = subprocess.Popen(  # argv fixo, sem shell
                argv_da_gravacao(sink["nome"]),
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            continue
        gravadores.append((sink, proc))
    time.sleep(max(0.1, segundos))
    endpoints = []
    for sink, proc in gravadores:
        proc.terminate()
        try:
            pcm, _erro = proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            pcm, _erro = proc.communicate()
        rms = rms_por_canal(pcm or b"")
        endpoints.append({
            "nome": mascarar(sink["nome"]),
            "quadros": len(pcm or b"") // (4 * CANAIS),
            "rms": {"frente": [round(v, 5) for v in rms[:2]], "motores": [round(v, 5) for v in rms[2:]]},
        })
    com_motor = sum(1 for e in endpoints if any(v > 0 for v in e["rms"]["motores"]))  # type: ignore[index]
    return {
        "veredito": f"{com_motor} de {len(endpoints)} endpoint(s) com sinal nos motores em {segundos:g} s",
        "medidas": {"segundos": segundos, "endpoints": len(endpoints), "com_motor": com_motor},
        "endpoints": endpoints,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--montar", action="store_true", help="sobe o endpoint")
    p.add_argument("--desmontar", action="store_true", help="derruba os nossos")
    p.add_argument("--marca", default="", help="os seis hex do rabo do uniq do controle (exigido no --montar)")
    p.add_argument("--json", action="store_true", help="a leitura, na forma que o o_basico.py lê")
    p.add_argument("--gravar", type=float, default=0.0, metavar="SEGUNDOS",
                   help="grava o monitor dos endpoints e diz o RMS de cada canal")
    p.add_argument("--ancora", default="", help="syspath do usb_device âncora (o padrão é o primeiro)")
    p.add_argument("--ancoras", action="store_true", help="lista as âncoras candidatas")
    args = p.parse_args(argv)

    disponiveis = ancoras()
    if args.ancoras:
        for a in disponiveis:
            print(f"{a.syspath:36s} {a.nome[:34]:34s} {a.container_id()}")
        return 0
    if args.desmontar:
        return desmontar()
    if args.montar:
        if not re.fullmatch(r"[0-9A-Fa-f]{6}", args.marca or ""):
            print("RECUSO: o --montar exige a --marca (os seis hex do rabo do uniq)")
            return 2
        if not disponiveis:
            print("sem âncora: nenhum usb_device sem placa de som neste host")
            return 1
        escolhida = next((a for a in disponiveis if a.syspath == args.ancora), disponiveis[0])
        rc = montar(args.marca, escolhida)
        return rc or status()
    if args.gravar > 0:
        import json

        gravado = gravar(args.gravar)
        if args.json:
            print(json.dumps(gravado, ensure_ascii=False, indent=1))
        else:
            _dizer(str(gravado["veredito"]))
            for e in gravado["endpoints"]:  # type: ignore[attr-defined]
                _dizer(f"  {e['nome']}  frente {e['rms']['frente']}  motores {e['rms']['motores']}")
        return 0 if gravado["endpoints"] else 1
    if args.json:
        import json

        dado = leitura()
        print(json.dumps(dado, ensure_ascii=False, indent=1))
        return 0 if dado["endpoints"] and all(e["completo"] for e in dado["endpoints"]) else 1
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
