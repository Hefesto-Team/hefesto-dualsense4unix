#!/usr/bin/env python3
"""O som de cada pad no Wine — O-SOM-DE-CADA-PAD-NA-ORDEM-DO-HIDRAW-01 (09/10/2026).

A PERGUNTA
----------
Com dois e com quatro pads no gadget, em que ORDEM os nós de háptica estão na
lista do servidor de som, cada nó sobe ao gadget do pad dele (o contêiner que o
``winepulse`` lê do ``sysfs.path``), e em qual nó cada fluxo do jogo toca. O
Wine dá o identificador canônico da Sony ao primeiro DualSense da lista (patch
0187), e o nosso nó não tem ``alsa.card`` para o 0189 reordenar: a ordem da
lista é a variável.

O QUE ELE LÊ, E O QUE NUNCA FAZ
-------------------------------
Lê: ``pactl --format=json list sinks`` e ``list sink-inputs`` (a lista, nunca
um ``load``/``unload``/``set``), ``/sys/class/hidraw`` (quais pads moram no
gadget) e, com ``--log-do-wine``, o arquivo que o ``WINEDEBUG=+mmdevapi,+hid``
do jogo de prova escreveu. Não escreve no aparelho, no servidor de som nem no
daemon. O endereço nunca sai: cada nó sai como «controle N», o número do
rótulo «Háptica do Controle N» que o daemon publicou.

A TRAVA
-------
Sem ``--medir`` ele não pergunta nada ao servidor de som: com o daemon no ar
RECUSA (rc=2), sem daemon mostra o plano. Com ``--medir``, sem pad no gadget
recusa também (rc=2), a menos que ``--sem-gadget`` peça a medida de contraste
com os pads no ``uhid``. ``--sinks-json`` e ``--entradas-json`` leem listas
gravadas antes, sem servidor nenhum.

AS VARIÁVEIS (uma linha por variável no fim)
--------------------------------------------
- a ordem dos nós no daemon: ``HEFESTO_DUALSENSE4UNIX_ORDEM_DOS_NOS`` no
  ambiente do daemon (``assento``, ``assento-sem-refazer`` ou ``endereco``),
  lida do ``/proc`` dele;
- a ordem medida: a lista do servidor bate com os assentos, ou não;
- a âncora: quantos nós sobem ao gadget, e se algum contêiner se repete;
- o jogo: em qual controle cada fluxo toca;
- o Wine: a ordem em que os nós aparecem no log.

O protocolo da bancada e a tabela das medidas estão em
``docs/process/estudos/2026-10-08-o-som-de-cada-pad/MEDIDAS.md``.
"""

from __future__ import annotations

import argparse
import os
import re
import socket
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(os.path.dirname(os.path.dirname(_AQUI)), "src")
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from hefesto_dualsense4unix.integrations import pad_usb, porta_do_som
from hefesto_dualsense4unix.integrations.dualsense_bt_audio import (
    PREFIXO_DA_MARCA_DO_APARELHO,
    TAMANHO_DA_MARCA_DO_APARELHO,
)
from hefesto_dualsense4unix.integrations.endpoint_de_haptica import (
    INTERRUPTOR_DA_ORDEM_DOS_NOS,
    MARCA_DO_NOME,
    NOME_DA_HAPTICA_DO_CONTROLE,
)

RC_RECUSADO = 2

_ASSENTO_NO_ROTULO = re.compile(re.escape(NOME_DA_HAPTICA_DO_CONTROLE) + r" (\d+)")
_MARCA_NO_NOME = re.compile(
    re.escape(MARCA_DO_NOME)
    + "("
    + re.escape(PREFIXO_DA_MARCA_DO_APARELHO)
    + f"[A-Za-z]{{{TAMANHO_DA_MARCA_DO_APARELHO}}})"
)


@dataclass(frozen=True)
class NoDoJogo:
    """Um nó de háptica desta casa, como a lista do servidor o mostra."""

    posicao: int
    indice: int
    nome: str
    assento: int | None
    conteiner: str
    no_gadget: bool


def _assento_do_rotulo(descricao: str) -> int | None:
    achado = _ASSENTO_NO_ROTULO.search(descricao or "")
    return int(achado.group(1)) if achado else None


def nos_de_haptica(nos: Iterable[porta_do_som.NoDeSom]) -> list[NoDoJogo]:
    """Os nós desta casa, na ordem da lista do servidor (a do índice). Função pura."""
    nossos = sorted(
        (n for n in nos if MARCA_DO_NOME in n.nome and _MARCA_NO_NOME.search(n.nome)),
        key=lambda n: n.indice,
    )
    fora: list[NoDoJogo] = []
    for posicao, no in enumerate(nossos, start=1):
        caminho = str(no.propriedades.get("sysfs.path", ""))
        fora.append(
            NoDoJogo(
                posicao=posicao,
                indice=no.indice,
                nome=no.nome,
                assento=_assento_do_rotulo(no.descricao),
                conteiner=pad_usb.usb_device_do_caminho(caminho),
                no_gadget=pad_usb.sob_o_vhci(caminho),
            )
        )
    return fora


def rotulo(no: NoDoJogo) -> str:
    """«controle N», ou «nó k sem número»: nunca o nome, que carrega a marca."""
    return f"controle {no.assento}" if no.assento else f"nó {no.posicao} sem número"


def veredito_da_ordem(nos: Sequence[NoDoJogo]) -> str:
    """``assento`` quando a lista do servidor é a ordem dos assentos; senão ``outra``."""
    numeros = [n.assento for n in nos]
    if not numeros or any(a is None for a in numeros):
        return "não sei (nó sem número)"
    return "assento" if numeros == sorted(numeros) else "outra"


def conteineres_repetidos(nos: Sequence[NoDoJogo]) -> list[str]:
    """Os nós que dividem o contêiner com outro (o par que o Wine confundiria)."""
    vistos: dict[str, list[str]] = {}
    for no in nos:
        if no.conteiner:
            vistos.setdefault(no.conteiner, []).append(rotulo(no))
    return [" e ".join(r) for r in vistos.values() if len(r) > 1]


def fluxos_por_controle(
    nos: Sequence[NoDoJogo], fluxos: Iterable[porta_do_som.Fluxo]
) -> list[str]:
    """«<programa> → controle N» de cada fluxo que toca num nó desta casa."""
    por_indice = {str(n.indice): n for n in nos}
    linhas: list[str] = []
    for fluxo in sorted(fluxos, key=lambda f: f.indice):
        no = por_indice.get(str(fluxo.alvo))
        if no is None:
            continue
        programa = (
            fluxo.propriedades.get("application.process.binary")
            or fluxo.propriedades.get("application.name")
            or "?"
        )
        linhas.append(f"{programa} → {rotulo(no)}")
    return linhas


def ordem_no_log_do_wine(texto: str, nos: Sequence[NoDoJogo]) -> list[str]:
    """Os nós na ordem em que o log do Wine os cita pela primeira vez. Função pura."""
    por_marca: dict[str, NoDoJogo] = {}
    for no in nos:
        achado = _MARCA_NO_NOME.search(no.nome)
        if achado:
            por_marca[achado.group(1)] = no
    ordem: list[str] = []
    for achado in _MARCA_NO_NOME.finditer(texto):
        no = por_marca.get(achado.group(1))
        nome = rotulo(no) if no is not None else "nó fora da lista"
        if nome not in ordem:
            ordem.append(nome)
    return ordem


def pads_no_gadget(raiz_class_hidraw: str = "/sys/class/hidraw") -> int:
    """Quantos ``hidraw`` são pads do Hefesto morando no gadget (sob o ``vhci_hcd``)."""
    try:
        nomes = sorted(os.listdir(raiz_class_hidraw))
    except OSError:
        return 0
    quantos = 0
    for nome in nomes:
        caminho = os.path.realpath(os.path.join(raiz_class_hidraw, nome, "device"))
        if pad_usb.sob_o_vhci(caminho) and pad_usb.e_hidraw_de_pad_nosso(
            nome, raiz_class_hidraw=raiz_class_hidraw
        ):
            quantos += 1
    return quantos


def ha_daemon(env: dict[str, str], uid: int) -> bool:
    """Algum socket do daemon aceita conexão? Só conecta e fecha: nada vai ao daemon."""
    nome = env.get("HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME", "").strip()
    if not nome or "/" in nome:
        nome = "hefesto-dualsense4unix.sock"
    pastas = [Path(f"/run/user/{uid}") / "hefesto-dualsense4unix"]
    if env.get("XDG_RUNTIME_DIR", "").strip():
        pastas.insert(0, Path(env["XDG_RUNTIME_DIR"]) / "hefesto-dualsense4unix")
    for pasta in pastas:
        caminho = pasta / nome
        if not caminho.exists():
            continue
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as conexao:
                conexao.settimeout(0.5)
                conexao.connect(str(caminho))
        except (ConnectionRefusedError, FileNotFoundError):
            continue
        except OSError:
            return True
        return True
    return False


def ordem_pedida_ao_daemon(raiz_proc: str = "/proc") -> str:
    """O valor do interruptor da ordem no ambiente do daemon, lido do ``/proc``."""
    try:
        pids = [p for p in os.listdir(raiz_proc) if p.isdigit()]
    except OSError:
        return "não sei"
    for pid in pids:
        try:
            linha = Path(raiz_proc, pid, "cmdline").read_bytes().replace(b"\0", b" ")
        except OSError:
            continue
        if b"hefesto" not in linha or b"daemon" not in linha or b"start" not in linha:
            continue
        try:
            ambiente = Path(raiz_proc, pid, "environ").read_bytes().split(b"\0")
        except OSError:
            return "não sei (ambiente do daemon ilegível)"
        chave = INTERRUPTOR_DA_ORDEM_DOS_NOS.encode() + b"="
        for item in ambiente:
            if item.startswith(chave):
                return item[len(chave):].decode(errors="replace") or "padrão (vazio)"
        return "padrão (sem o interruptor)"
    return "não sei (daemon não achado)"


def _ler_arquivo(caminho: str) -> str:
    return Path(caminho).read_text(encoding="utf-8", errors="replace")


def relatorio(
    nos: Sequence[NoDoJogo],
    fluxos: Sequence[porta_do_som.Fluxo],
    *,
    log_do_wine: str | None,
    ordem_pedida: str,
    pads: int | None,
) -> list[str]:
    """As linhas do relatório: a tabela e, no fim, uma linha por variável."""
    linhas = ["posição  índice  controle            contêiner", "-" * 60]
    conteineres = sorted({n.conteiner for n in nos if n.conteiner})
    for no in nos:
        k = conteineres.index(no.conteiner) + 1 if no.conteiner else 0
        onde = "gadget" if no.no_gadget else "emprestada"
        linhas.append(
            f"{no.posicao:>7}  {no.indice:>6}  {rotulo(no):<18}  usb {k} ({onde})"
        )
    tocando = fluxos_por_controle(nos, fluxos)
    linhas.extend(["", *(tocando or ["nenhum fluxo tocando num nó desta casa"])])
    ordem_wine = ordem_no_log_do_wine(log_do_wine, nos) if log_do_wine is not None else None
    repetidos = conteineres_repetidos(nos)
    no_gadget = sum(1 for n in nos if n.no_gadget)
    linhas.extend(
        [
            "",
            f"VARIÁVEL ordem pedida ao daemon: {ordem_pedida}",
            f"VARIÁVEL ordem na lista do servidor: {veredito_da_ordem(nos)} "
            f"({', '.join(rotulo(n) for n in nos) or 'nenhum nó'})",
            f"VARIÁVEL âncora: {no_gadget} de {len(nos)} no gadget"
            + (f"; pads no gadget: {pads}" if pads is not None else "")
            + (f"; contêiner REPETIDO: {'; '.join(repetidos)}" if repetidos else ""),
            f"VARIÁVEL jogo: {'; '.join(tocando) if tocando else 'sem fluxo'}",
            "VARIÁVEL Wine: "
            + (
                "sem log"
                if ordem_wine is None
                else (", ".join(ordem_wine) or "nenhum nó citado no log")
            ),
        ]
    )
    return linhas


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="A ordem dos nós de háptica e o controle de cada fluxo do jogo (só leitura)."
    )
    p.add_argument("--medir", action="store_true", help="lê o servidor de som agora")
    p.add_argument("--sem-gadget", action="store_true",
                   help="mede mesmo sem pad no gadget (o contraste com o uhid)")
    p.add_argument("--sinks-json", default="", help="lista de sinks gravada (pactl --format=json)")
    p.add_argument("--entradas-json", default="", help="lista de sink-inputs gravada")
    p.add_argument("--log-do-wine", default="", help="o log do WINEDEBUG=+mmdevapi,+hid")
    return p


def main(
    argv: Sequence[str] | None = None,
    *,
    env: dict[str, str] | None = None,
    ler_pactl: Callable[[list[str]], str | None] | None = None,
    contar_pads: Callable[[], int] = pads_no_gadget,
    daemon_no_ar: Callable[[dict[str, str], int], bool] = ha_daemon,
) -> int:
    args = _parser().parse_args(argv)
    ambiente = dict(os.environ) if env is None else env
    gravado = bool(args.sinks_json)
    print("o som de cada pad no Wine: só leitura, o endereço sai como «controle N»")
    if not args.medir and not gravado:
        if daemon_no_ar(ambiente, os.getuid()):
            print("RECUSADO: o daemon está no ar e faltou --medir (nada foi lido)")
            return RC_RECUSADO
        print("SEM --medir: nada foi lido. Plano: a lista de sinks e de sink-inputs, "
              "o gadget dos pads e o log do Wine, com dois e com quatro pads.")
        return 0
    pads: int | None = None
    if gravado:
        nos_brutos = porta_do_som.nos_do_texto(_ler_arquivo(args.sinks_json))
        fluxos = (
            porta_do_som.fluxos_do_texto(_ler_arquivo(args.entradas_json))
            if args.entradas_json else ()
        )
    else:
        pads = contar_pads()
        if pads == 0 and not args.sem_gadget:
            print("RECUSADO: nenhum pad no gadget (use --sem-gadget para o contraste com o uhid)")
            return RC_RECUSADO
        if ler_pactl is None:
            from hefesto_dualsense4unix.integrations.alto_falante_bt import rodar_pactl

            ler_pactl = rodar_pactl
        nos_lidos = porta_do_som.ler_nos("sinks", ler_pactl)
        if nos_lidos is None:
            print("SEM MEDIÇÃO: o servidor de som não respondeu à lista de sinks")
            return 1
        nos_brutos = nos_lidos
        fluxos = porta_do_som.ler_fluxos("sink-inputs", ler_pactl) or ()
    log = _ler_arquivo(args.log_do_wine) if args.log_do_wine else None
    nos = nos_de_haptica(nos_brutos)
    ordem_pedida = "lista gravada" if gravado else ordem_pedida_ao_daemon()
    for linha in relatorio(nos, fluxos, log_do_wine=log, ordem_pedida=ordem_pedida, pads=pads):
        print(linha)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
