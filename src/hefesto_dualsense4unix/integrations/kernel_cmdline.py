"""Plano de merge do cmdline de kernel para o install (PLAT-03 item 2), e o carregador de boot.

O plano (``plan_tokens``) decide; :func:`ler_o_carregador` e :func:`escrever` são o dono único
de quem lê e de quem escreve no carregador de boot
(O-CMDLINE-DO-DUALSENSE-SO-SE-ESCREVE-NO-KERNELSTUB-01):
o kernelstub do Pop!_OS, o grub (Debian, Ubuntu, Mint, Fedora, Arch) e o systemd-boot pelo
``/etc/kernel/cmdline``. O módulo é 100% biblioteca padrão e roda como script
(``python3 -I kernel_cmdline.py escrever …``), que é como o install, o uninstall e o
``install_usb_quirk.sh`` escrevem como root.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

AUTOSUSPEND_PARAM = "usbcore.autosuspend"
AUTOSUSPEND_TOKEN = "usbcore.autosuspend=-1"
QUIRKS_PARAM = "usbcore.quirks"
HEFESTO_QUIRK_IDS: tuple[str, ...] = ("054c:0ce6:gn",)
#: O que o Hefesto gravou antes e TIRA ao fundir (ADR 018, nota de 14/10/2026):
#: no ``054c:0df2`` do pad virtual o ``n`` espera 200 ms por pedido de controle,
#: e com quatro controles o jogo perde os controles. Sai só a entrada exata.
HEFESTO_QUIRK_IDS_VELHOS: tuple[str, ...] = ("054c:0df2:gn",)

OWNER_HEFESTO = "hefesto"
OWNER_TERCEIRO = "terceiro"
OWNER_COMPARTILHADO = "compartilhado"

OP_NONE = "none"
OP_ADD = "add"
OP_REPLACE = "replace"
OP_PULA = "skip"

NEVER_REINTRODUCE: tuple[str, ...] = (
    "054c:0ce6:k",
    "processor.max_cstate",
    "threadirqs",
)


@dataclass(frozen=True)
class CmdlineAction:
    """Uma decisão do plano para um parâmetro do cmdline."""

    param: str
    op: str
    token: str
    remove_tokens: tuple[str, ...] = ()
    owner: str = OWNER_HEFESTO
    reason: str = ""


def parse_cmdline(cmdline: str) -> list[str]:
    """Tokens do cmdline (split por whitespace; suficiente para nossos params)."""
    return cmdline.split()


def tokens_for_param(tokens: Sequence[str], param: str) -> list[str]:
    """Todos os tokens ``param`` ou ``param=...`` presentes (na ordem)."""
    prefix = param + "="
    return [t for t in tokens if t == param or t.startswith(prefix)]


def _entry_key(entry: str) -> str:
    """Chave VID:PID (minúscula) de uma entrada ``vvvv:pppp:flags`` do quirks."""
    parts = entry.split(":")
    if len(parts) >= 2:
        return f"{parts[0]}:{parts[1]}".lower()
    return entry.lower()


def _quirks_entries(token: str) -> list[str]:
    """Entradas (``vvvv:pppp:flags``) de um token ``usbcore.quirks=...``."""
    if "=" not in token:
        return []
    value = token.split("=", 1)[1]
    return [e for e in value.split(",") if e]


def merge_quirks_token(
    existing_tokens: Sequence[str],
    desired_ids: Sequence[str] = HEFESTO_QUIRK_IDS,
    obsolete_ids: Sequence[str] = HEFESTO_QUIRK_IDS_VELHOS,
) -> tuple[str, bool]:
    """Funde os IDs desejados no token ÚNICO ``usbcore.quirks=``.

    As entradas de ``obsolete_ids`` (as que o Hefesto gravava antes) saem.
    """
    velhos = set(obsolete_ids) - set(desired_ids)
    result: list[str] = []
    keys: dict[str, int] = {}
    changed = len(existing_tokens) > 1
    for token in existing_tokens:
        for entry in _quirks_entries(token):
            if entry in velhos:
                changed = True
                continue
            key = _entry_key(entry)
            if key not in keys:
                keys[key] = len(result)
                result.append(entry)
    for want in desired_ids:
        key = _entry_key(want)
        if key in keys:
            index = keys[key]
            if result[index] != want:
                result[index] = want
                changed = True
        else:
            keys[key] = len(result)
            result.append(want)
            changed = True
    return f"{QUIRKS_PARAM}=" + ",".join(result), changed


def strip_quirks_token(
    existing_token: str,
    ids_to_remove: Sequence[str] = HEFESTO_QUIRK_IDS + HEFESTO_QUIRK_IDS_VELHOS,
) -> tuple[str | None, bool]:
    """Inverso do merge, para o UNINSTALL de um token "compartilhado"."""
    ours = set(ids_to_remove)
    remaining = [e for e in _quirks_entries(existing_token) if e not in ours]
    changed = len(remaining) != len(_quirks_entries(existing_token))
    if not remaining:
        return None, changed
    return f"{QUIRKS_PARAM}=" + ",".join(remaining), changed


def _plan_autosuspend(tokens: Sequence[str], com_bateria: bool = False) -> CmdlineAction:
    present = tokens_for_param(tokens, AUTOSUSPEND_PARAM)
    if com_bateria and AUTOSUSPEND_TOKEN not in present:
        # O autosuspend=-1 vale para TODO aparelho USB da máquina, e a razão
        # medida é de desktop (AMD 400): num computador com bateria ele custa
        # a carga de quem joga fora da tomada. O que já estiver lá (de outra
        # ferramenta ou da pessoa) não é desfeito: a decisão é só não pôr o nosso.
        return CmdlineAction(
            param=AUTOSUSPEND_PARAM,
            op=OP_PULA,
            token=AUTOSUSPEND_TOKEN,
            owner="",
            reason=(
                "este computador tem bateria — USB sem economia custaria a carga; "
                "o usbcore.quirks do DualSense segue"
            ),
        )
    if AUTOSUSPEND_TOKEN in present:
        return CmdlineAction(
            param=AUTOSUSPEND_PARAM,
            op=OP_NONE,
            token=AUTOSUSPEND_TOKEN,
            owner=OWNER_TERCEIRO,
            reason="já provido por terceiro (Aurora/manual) — não tocar; uninstall não remove",
        )
    if present:
        return CmdlineAction(
            param=AUTOSUSPEND_PARAM,
            op=OP_REPLACE,
            token=AUTOSUSPEND_TOKEN,
            remove_tokens=tuple(present),
            owner=OWNER_HEFESTO,
            reason=f"valor divergente ({', '.join(present)}) → -1 (nunca suspender)",
        )
    return CmdlineAction(
        param=AUTOSUSPEND_PARAM,
        op=OP_ADD,
        token=AUTOSUSPEND_TOKEN,
        owner=OWNER_HEFESTO,
        reason="ausente — USB nunca dorme (PLAT-03)",
    )


def _plan_quirks(
    tokens: Sequence[str], desired_ids: Sequence[str]
) -> CmdlineAction:
    present = tokens_for_param(tokens, QUIRKS_PARAM)
    merged, changed = merge_quirks_token(present, desired_ids)
    if not present:
        return CmdlineAction(
            param=QUIRKS_PARAM,
            op=OP_ADD,
            token=merged,
            owner=OWNER_HEFESTO,
            reason="ausente — quirk anti-storm gn (preserva mic/fone)",
        )
    if not changed:
        return CmdlineAction(
            param=QUIRKS_PARAM,
            op=OP_NONE,
            token=present[0],
            owner=OWNER_TERCEIRO,
            reason="token único já contém os IDs do hefesto — não tocar",
        )
    velhos = [
        e for t in present for e in _quirks_entries(t) if e in HEFESTO_QUIRK_IDS_VELHOS
    ]
    if velhos:
        return CmdlineAction(
            param=QUIRKS_PARAM,
            op=OP_REPLACE,
            token=merged,
            remove_tokens=tuple(present),
            owner=OWNER_COMPARTILHADO,
            reason=(
                f"migração: {', '.join(velhos)} sai (o pad virtual esperava 200 ms "
                "por pedido; com 4 controles o jogo perde os controles); "
                "uninstall remove só os IDs do hefesto"
            ),
        )
    return CmdlineAction(
        param=QUIRKS_PARAM,
        op=OP_REPLACE,
        token=merged,
        remove_tokens=tuple(present),
        owner=OWNER_COMPARTILHADO,
        reason=(
            "o kernel respeita SÓ UM token usbcore.quirks= — fundido com o(s) "
            f"existente(s) ({', '.join(present)}); uninstall remove só os IDs do hefesto"
        ),
    )


def plan_tokens(
    tokens: Sequence[str],
    desired_quirk_ids: Sequence[str] = HEFESTO_QUIRK_IDS,
    com_bateria: bool = False,
) -> list[CmdlineAction]:
    """O plano completo (autosuspend + quirks) a partir dos tokens atuais.

    ``com_bateria``: o computador tem bateria ACPI. O autosuspend do USB não
    entra (op ``skip``); o ``usbcore.quirks`` do DualSense entra igual.
    """
    return [
        _plan_autosuspend(tokens, com_bateria),
        _plan_quirks(tokens, desired_quirk_ids),
    ]


def plan_cmdline(
    cmdline: str,
    desired_quirk_ids: Sequence[str] = HEFESTO_QUIRK_IDS,
    com_bateria: bool = False,
) -> list[CmdlineAction]:
    """Como :func:`plan_tokens`, recebendo a string crua (/proc/cmdline)."""
    return plan_tokens(parse_cmdline(cmdline), desired_quirk_ids, com_bateria)


def apply_plan(tokens: Sequence[str], actions: Iterable[CmdlineAction]) -> list[str]:
    """SIMULA o plano sobre os tokens (para testes e para o doctor comparar)."""
    result = list(tokens)
    for action in actions:
        if action.op in (OP_NONE, OP_PULA):
            continue
        result = [t for t in result if t not in action.remove_tokens]
        result.append(action.token)
    return result


def forbidden_reintroductions(actions: Iterable[CmdlineAction]) -> list[str]:
    """Violações da regra "nunca reintroduzir" nos tokens que o plano ADICIONA."""
    violations: list[str] = []
    for action in actions:
        if action.op in (OP_NONE, OP_PULA):
            continue
        for banned in NEVER_REINTRODUCE:
            if banned in action.token:
                violations.append(f"{action.token} contém {banned}")
    return violations


# ---------------------------------------------------------------------------
# O carregador de boot: quem lê e quem escreve (um dono só)
# ---------------------------------------------------------------------------
BACKEND_KERNELSTUB = "kernelstub"
BACKEND_GRUB = "grub"
BACKEND_SYSTEMD_BOOT = "systemd-boot"
BACKEND_NENHUM = "none"
_LINHA_DO_GRUB = "GRUB_CMDLINE_LINUX_DEFAULT="

Which = Callable[[str], "str | None"]
Rodar = Callable[[list[str]], int]


@dataclass(frozen=True)
class Lugares:
    """Os arquivos do carregador de boot a partir de uma raiz (``/`` na máquina)."""

    kernelstub: Path
    grub: Path
    kernel_cmdline: Path
    raiz: Path

    @classmethod
    def da_raiz(cls, raiz: str | Path = "/") -> Lugares:
        r = Path(raiz)
        return cls(
            kernelstub=r / "etc/kernelstub/configuration",
            grub=r / "etc/default/grub",
            kernel_cmdline=r / "etc/kernel/cmdline",
            raiz=r,
        )


@dataclass(frozen=True)
class Carregador:
    """O carregador de boot desta máquina e os tokens que ele guarda para o próximo boot."""

    backend: str
    tokens: tuple[str, ...] = ()
    arquivo: str = ""


@dataclass(frozen=True)
class Escrita:
    """O que :func:`escrever` fez: os tokens novos, os comandos e o que falhou."""

    tokens: tuple[str, ...]
    comandos: tuple[tuple[str, ...], ...] = ()
    falhas: tuple[str, ...] = ()
    avisos: tuple[str, ...] = field(default_factory=tuple)


def _tokens_do_kernelstub(conf: Path) -> list[str]:
    """Os ``kernel_options``. JSON quebrado levanta: cair no grub escreveria no lugar errado."""
    data = json.loads(conf.read_text(encoding="utf-8"))
    user = data.get("user") if isinstance(data, dict) else None
    opcoes = (user or {}).get("kernel_options") if isinstance(user or {}, dict) else None
    return [str(t) for t in (opcoes or [])]


def _valor_do_grub(texto: str) -> str:
    """O valor da ÚLTIMA ``GRUB_CMDLINE_LINUX_DEFAULT=`` (é a que o grub usa); ``""`` sem ela."""
    valor = ""
    for linha in texto.splitlines():
        crua = linha.strip()
        if crua.startswith(_LINHA_DO_GRUB):
            valor = crua.split("=", 1)[1].strip().strip('"').strip("'")
    return valor


def _ler_texto(caminho: Path) -> str | None:
    """O arquivo, ou ``None`` sem ele. Ilegível levanta, pela mesma razão do kernelstub."""
    return caminho.read_text(encoding="utf-8") if caminho.is_file() else None


def carregadores_presentes(
    lugares: Lugares | None = None, which: Which = shutil.which
) -> list[Carregador]:
    """Todo carregador com arquivo aqui, na ordem de :func:`ler_o_carregador`; ilegível levanta."""
    lugares = lugares or Lugares.da_raiz()
    achados: list[Carregador] = []
    if which("kernelstub") and lugares.kernelstub.is_file():
        tokens = _tokens_do_kernelstub(lugares.kernelstub)
        achados.append(Carregador(BACKEND_KERNELSTUB, tuple(tokens), str(lugares.kernelstub)))
    texto = _ler_texto(lugares.grub)
    if texto is not None:
        achados.append(Carregador(BACKEND_GRUB, tuple(_valor_do_grub(texto).split()),
                                  str(lugares.grub)))
    texto = _ler_texto(lugares.kernel_cmdline)
    if texto is not None:
        achados.append(Carregador(BACKEND_SYSTEMD_BOOT, tuple(texto.split()),
                                  str(lugares.kernel_cmdline)))
    return achados


def ler_o_carregador(lugares: Lugares | None = None, which: Which = shutil.which) -> Carregador:
    """O carregador de boot que manda: o kernelstub, o grub ou o ``/etc/kernel/cmdline``.

    Sem nenhum deles, ``backend`` é ``none`` e quem chama diz o token e onde ele iria.
    """
    achados = carregadores_presentes(lugares, which)
    return achados[0] if achados else Carregador(BACKEND_NENHUM)


def trocar_tokens(tokens: Sequence[str], tira: Sequence[str], poe: Sequence[str]) -> list[str]:
    """Os tokens sem ``tira`` e com ``poe``, sem duplicar.

    O que entra ocupa o lugar do primeiro que saiu (a ordem da linha fica); sem saída, vai no fim.
    """
    saem = set(tira)
    fora: list[str] = []
    lugar: int | None = None
    for token in tokens:
        if token in saem:
            if lugar is None:
                lugar = len(fora)
            continue
        fora.append(token)
    novos = [t for t in dict.fromkeys(poe) if t not in fora]
    if lugar is None:
        return fora + novos
    return fora[:lugar] + novos + fora[lugar:]


def _grub_com_tokens(texto: str, tokens: Sequence[str]) -> str:
    """O ``/etc/default/grub`` com a ``GRUB_CMDLINE_LINUX_DEFAULT`` nova; as outras linhas ficam."""
    nova = f'{_LINHA_DO_GRUB}"{" ".join(tokens)}"'
    linhas = texto.splitlines(keepends=True)
    for i in reversed(range(len(linhas))):
        if linhas[i].strip().startswith(_LINHA_DO_GRUB):
            recuo = linhas[i][: len(linhas[i]) - len(linhas[i].lstrip())]
            linhas[i] = recuo + nova + ("\n" if linhas[i].endswith("\n") else "")
            return "".join(linhas)
    if linhas and not linhas[-1].endswith("\n"):
        linhas[-1] += "\n"
    return "".join(linhas) + nova + "\n"


def _gravar(caminho: Path, texto: str) -> None:
    """Grava pelo arquivo ao lado e troca de uma vez, com o modo do original."""
    provisorio = caminho.with_name(caminho.name + ".hefesto-novo")
    provisorio.write_text(texto, encoding="utf-8")
    shutil.copymode(caminho, provisorio)
    provisorio.replace(caminho)


def _comandos_do_grub(
    tira: Sequence[str], poe: Sequence[str], lugares: Lugares, which: Which
) -> list[list[str]]:
    """Quem regenera o grub nesta máquina: o ``grubby`` onde o BLS manda, senão o ``grub.cfg``."""
    grubby = which("grubby")
    if grubby and (lugares.raiz / "boot/loader/entries").is_dir():
        comando = [grubby, "--update-kernel=ALL"]
        if tira:
            comando.append("--remove-args=" + " ".join(tira))
        if poe:
            comando.append("--args=" + " ".join(poe))
        return [comando]
    update = which("update-grub")
    if update:
        return [[update]]
    gerador = which("grub2-mkconfig") or which("grub-mkconfig")
    for cfg in (lugares.raiz / "boot/grub2/grub.cfg", lugares.raiz / "boot/grub/grub.cfg"):
        if gerador and cfg.is_file():
            return [[gerador, "-o", str(cfg)]]
    return []


def _comandos_do_systemd_boot(lugares: Lugares, which: Which) -> list[list[str]]:
    """Um ``kernel-install add`` por kernel: ele leva o ``/etc/kernel/cmdline`` ao boot."""
    instalar = which("kernel-install")
    modulos = lugares.raiz / "usr/lib/modules"
    if not instalar or not modulos.is_dir():
        return []
    return [
        [instalar, "add", pasta.name, str(pasta / "vmlinuz")]
        for pasta in sorted(modulos.iterdir())
        if (pasta / "vmlinuz").is_file()
    ]


def _rodar(comando: list[str]) -> int:
    try:
        return subprocess.run(comando, check=False, stdout=subprocess.DEVNULL).returncode
    except OSError:
        return 127


def escrever(
    carregador: Carregador,
    tira: Sequence[str],
    poe: Sequence[str],
    lugares: Lugares | None = None,
    which: Which = shutil.which,
    rodar: Rodar = _rodar,
) -> Escrita:
    """Tira e põe tokens no carregador de boot, e regenera o que o boot lê. Precisa de root.

    O kernelstub escreve pelos próprios ``--delete-options``/``--add-options``; o grub e o
    systemd-boot pelo arquivo, e depois o comando que esta máquina tem para regenerar.
    """
    lugares = lugares or Lugares.da_raiz()
    novos = trocar_tokens(carregador.tokens, tira, poe)
    if novos == list(carregador.tokens):
        return Escrita(tuple(novos))
    avisos: list[str] = []
    if carregador.backend == BACKEND_KERNELSTUB:
        ks = which("kernelstub") or "kernelstub"
        ficam = [t for t in carregador.tokens if t not in set(tira)]
        comandos = [[ks, "--delete-options", t] for t in tira if t in carregador.tokens]
        comandos += [[ks, "--add-options", t] for t in dict.fromkeys(poe) if t not in ficam]
    elif carregador.backend == BACKEND_GRUB:
        texto = lugares.grub.read_text(encoding="utf-8")
        _gravar(lugares.grub, _grub_com_tokens(texto, novos))
        comandos = _comandos_do_grub(tira, poe, lugares, which)
        if not comandos:
            avisos.append(f"{lugares.grub} gravado; sem update-grub, grub2-mkconfig nem "
                          "grubby nesta máquina: regenere o grub.cfg à mão")
    elif carregador.backend == BACKEND_SYSTEMD_BOOT:
        _gravar(lugares.kernel_cmdline, " ".join(novos) + "\n")
        comandos = _comandos_do_systemd_boot(lugares, which)
        if not comandos:
            avisos.append(f"{lugares.kernel_cmdline} gravado; sem kernel-install nesta máquina: "
                          "leve-o às entradas do systemd-boot à mão")
    else:
        raise ValueError(f"carregador de boot desconhecido: {carregador.backend!r}")
    falhas = tuple(" ".join(c) for c in comandos if rodar(c) != 0)
    return Escrita(tuple(novos), tuple(tuple(c) for c in comandos), falhas, tuple(avisos))


def plano_do_quirk(tokens: Sequence[str], remover: bool = False) -> tuple[list[str], list[str]]:
    """O ``(tira, poe)`` do ``install_usb_quirk.sh``: o mesmo merge do passo 3e, só o quirk."""
    if not remover:
        acao = _plan_quirks(tokens, HEFESTO_QUIRK_IDS)
        if acao.op in (OP_NONE, OP_PULA):
            return [], []
        return list(acao.remove_tokens), [acao.token]
    tira: list[str] = []
    poe: list[str] = []
    for token in tokens_for_param(tokens, QUIRKS_PARAM):
        resto, mudou = strip_quirks_token(token)
        if mudou:
            tira.append(token)
            if resto is not None:
                poe.append(resto)
    return tira, poe


def _lugares_do_argv(args: argparse.Namespace) -> Lugares:
    base = Lugares.da_raiz(args.raiz)
    return Lugares(
        kernelstub=Path(args.kernelstub_conf) if args.kernelstub_conf else base.kernelstub,
        grub=Path(args.grub_conf) if args.grub_conf else base.grub,
        kernel_cmdline=Path(args.kernel_cmdline) if args.kernel_cmdline else base.kernel_cmdline,
        raiz=base.raiz,
    )


def _relatar(escrita: Escrita, carregador: Carregador) -> int:
    for aviso in escrita.avisos:
        print("aviso\t" + aviso)
    for falha in escrita.falhas:
        print("falhou\t" + falha)
    if escrita.comandos or escrita.avisos:
        print(f"escreveu\t{carregador.backend}\t{carregador.arquivo}")
    return 1 if escrita.falhas else 0


def main(argv: Sequence[str] | None = None) -> int:
    """``ler``, ``escrever`` (o passo 3e e o uninstall) e ``quirk`` (o ``install_usb_quirk.sh``)."""
    parser = argparse.ArgumentParser(prog="kernel_cmdline.py")
    parser.add_argument("comando", choices=("ler", "escrever", "quirk-aplicar", "quirk-remover"))
    parser.add_argument("--raiz", default="/")
    parser.add_argument("--kernelstub-conf", default="")
    parser.add_argument("--grub-conf", default="")
    parser.add_argument("--kernel-cmdline", default="")
    parser.add_argument("--backend", default="")
    parser.add_argument("--tira", action="append", default=[])
    parser.add_argument("--poe", action="append", default=[])
    args = parser.parse_args(argv)
    lugares = _lugares_do_argv(args)
    carregador = ler_o_carregador(lugares)
    if args.comando == "ler":
        print(f"backend={carregador.backend}\narquivo={carregador.arquivo}")
        print("tokens=" + " ".join(carregador.tokens))
        return 0
    if args.comando == "escrever":
        presentes = carregadores_presentes(lugares)
        alvo = next((c for c in presentes if c.backend == args.backend), None)
        if alvo is None:
            print(f"falhou\tsem {args.backend} legível nesta máquina (o que manda: "
                  f"{carregador.backend})")
            return 2
        return _relatar(escrever(alvo, args.tira, args.poe, lugares), alvo)
    token = f"{QUIRKS_PARAM}=" + ",".join(HEFESTO_QUIRK_IDS)
    if carregador.backend == BACKEND_NENHUM:
        print("nenhum\tsem kernelstub, grub ou /etc/kernel/cmdline: ponha à mão no cmdline: "
              + token)
        return 0
    rc = 0
    remover = args.comando == "quirk-remover"
    for presente in carregadores_presentes(lugares) if remover else [carregador]:
        tira, poe = plano_do_quirk(presente.tokens, remover=remover)
        if not tira and not poe:
            print(f"no-op\t{presente.backend}\t{presente.arquivo}")
            continue
        print(f"troca\t{presente.backend}\t{' '.join(tira) or '-'}\t{' '.join(poe) or '-'}")
        rc |= _relatar(escrever(presente, tira, poe, lugares), presente)
    return rc


if __name__ == "__main__":
    sys.exit(main())
