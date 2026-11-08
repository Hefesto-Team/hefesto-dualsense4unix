#!/usr/bin/env python3
"""A rodada do Proton candidato: a prova dinâmica, só numa VM ou no CI.

Lança `sonda.exe` (assets/sonda-proton/sonda.c) sob a candidata, num prefixo
novo e sem a Steam, em cada caso da matriz, e julga as três provas (háptica,
gatilho e microfone) e a contagem do que o jogo vê. Escreve a linha do recibo
(`docs/data/proton-qualificacao.csv`). Na máquina de quem joga o ensaio RECUSA: o
kernel é um só, e o vpad de prova apareceria para os jogos.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import os
import subprocess
import sys
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Protocol

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))

from hefesto_dualsense4unix.integrations import qualificar_proton as qp

APPID_DO_RUNTIME = "4183110"

RC_FORA_DA_VM = 3
RC_SONDA_SEM_PINO = 4

ECO_MINIMO_DA_HAPTICA = 0.5
FRACAO_MINIMA_DO_TOM = 0.5

MASCARAS = ("dualsense", "xbox", "nintendo")


@dataclass(frozen=True)
class Caso:
    vpads: int
    transporte: str
    mascara: str
    wayland: bool

    def nome(self) -> str:
        w = "wayland" if self.wayland else "x11"
        return f"{self.vpads}vpad-{self.transporte}-{self.mascara}-{w}"


def matriz() -> list[Caso]:
    """Um e quatro vpads, cabo e rádio, as três máscaras, com e sem Wayland."""
    return [
        Caso(n, t, m, w)
        for n, t, m, w in itertools.product((1, 4), ("cabo", "radio"), MASCARAS, (False, True))
    ]


def na_vm_ou_no_ci(
    env: dict[str, str] | None = None,
    detectar: Sequence[str] = ("systemd-detect-virt", "--vm"),
) -> bool:
    """Verdadeiro só no CI (`CI=true`) ou numa máquina virtual medida."""
    env = dict(os.environ) if env is None else env
    if env.get("CI", "").lower() == "true":
        return True
    try:
        saida = subprocess.run(list(detectar), capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return False
    return saida.returncode == 0 and saida.stdout.strip() not in ("", "none")


def ler_sonda(saida: str) -> dict[str, dict[str, object]]:
    """As linhas JSON da sonda, por prova."""
    provas: dict[str, dict[str, object]] = {}
    for linha in saida.splitlines():
        linha = linha.strip()
        if not linha.startswith("{"):
            continue
        try:
            obj = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and isinstance(obj.get("prova"), str):
            provas[obj["prova"]] = obj
    return provas


@dataclass(frozen=True)
class MedidaDoOutroLado:
    """O que a máquina de teste da VM mediu do lado do Linux enquanto a sonda rodava."""

    eco_rl_rr: float
    bytes_no_uhid: str
    tom_posto: bool


def julgar(caso: Caso, sonda: dict[str, dict[str, object]], lado: MedidaDoOutroLado) -> list[str]:
    """As provas que reprovaram neste caso; vazio é «passou»."""
    falhas: list[str] = []
    if "fim" not in sonda:
        return [f"{caso.nome()}: a sonda não terminou"]
    h = sonda.get("haptica", {})
    if not (h.get("achou") and int(str(h.get("canais", 0))) >= 4 and h.get("tocou")):
        falhas.append(f"{caso.nome()}: háptica sem endpoint de quatro canais pelo ContainerId")
    elif lado.eco_rl_rr < ECO_MINIMO_DA_HAPTICA:
        falhas.append(f"{caso.nome()}: háptica não chegou aos canais 3-4 do nó")
    g = sonda.get("gatilho", {})
    if not g.get("escreveu"):
        falhas.append(f"{caso.nome()}: gatilho sem HID para escrever o report 0x02")
    elif str(g.get("bytes", "")) != lado.bytes_no_uhid:
        falhas.append(f"{caso.nome()}: gatilho chegou diferente ao uhid do vpad")
    m = sonda.get("microfone", {})
    if not (lado.tom_posto and m.get("achou")
            and float(str(m.get("fracao_no_tom", 0))) >= FRACAO_MINIMA_DO_TOM):
        falhas.append(f"{caso.nome()}: microfone não capturou o tom da fonte vestida")
    c = sonda.get("contagem", {})
    if caso.mascara == "dualsense" and c.get("hid_sony") != caso.vpads:
        falhas.append(f"{caso.nome()}: o jogo vê {c.get('hid_sony')} HID Sony, e não {caso.vpads}")
    ks = c.get("ks_por_container", {})
    if isinstance(ks, dict):
        container = str(sonda["fim"].get("container_sony", ""))
        if container and ks.get(container, 0) != 1:
            falhas.append(f"{caso.nome()}: {ks.get(container, 0)} devices KS no ContainerId do vpad")
    return falhas


class Ensaio(Protocol):
    """A máquina de teste da VM ou do runner: o vpad, o endpoint e a fonte vestidos.

    ``sustenta`` devolve ``None`` quando a perna se mede ali, ou o motivo de não se medir.
    """

    def sustenta(self, caso: Caso) -> str | None: ...
    def montar(self, caso: Caso) -> dict[str, str]: ...
    def medir(self) -> MedidaDoOutroLado: ...
    def desmontar(self) -> None: ...


def comando_da_sonda(proton: Path, sonda: Path, runtime: Path | None) -> list[str]:
    """`proton run sonda.exe`, por dentro do Steam Linux Runtime quando há a pasta dele."""
    if runtime is None:
        return [str(proton / "proton"), "run", str(sonda)]
    return [
        str(runtime / "_v2-entry-point"), "--verb=waitforexitandrun", "--",
        str(proton / "proton"), "waitforexitandrun", str(sonda),
    ]


def rodar_a_sonda(
    proton: Path, sonda: Path, env_do_lancamento: dict[str, str], runtime: Path | None = None,
) -> str:
    """A sonda num prefixo novo, sem a Steam."""
    with tempfile.TemporaryDirectory(prefix="hefesto-rodada-") as prefixo:
        env = dict(os.environ)
        env.update(env_do_lancamento)
        env.update({
            "STEAM_COMPAT_DATA_PATH": prefixo,
            "STEAM_COMPAT_CLIENT_INSTALL_PATH": prefixo,
            "SteamAppId": "0",
        })
        saida = subprocess.run(
            comando_da_sonda(proton, sonda, runtime),
            capture_output=True, text=True, timeout=300, env=env,
        )
        return saida.stdout


def sha256(caminho: Path) -> str:
    h = hashlib.sha256()
    with caminho.open("rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


@dataclass
class Resultado:
    """O que a matriz deu: as falhas, as pernas não medidas e o que a sonda contou por perna."""

    falhas: list[str]
    nao_medidas: dict[str, str]
    relato: dict[str, dict[str, object]]
    total: int

    def estado(self) -> str:
        """A coluna `rodada` do recibo: «passou» só com toda perna medida e sem falha."""
        if self.falhas:
            return "; ".join(self.falhas)
        if self.nao_medidas:
            motivos = "; ".join(sorted(set(self.nao_medidas.values())))
            return (
                f"{qp.RODADA_NAO_MEDIDA}: {len(self.nao_medidas)} de {self.total} pernas "
                f"({motivos})"
            )
        return qp.VEREDITO_PASSOU


def os_casos_da_mascara(caso: Caso, sonda: dict[str, dict[str, object]]) -> dict[str, object]:
    """Os casos (a) e (b) da máscara DualSense, como a sonda os viu nesta perna.

    (b) é o jogo só XInput: o controle aparece se há uma vaga XInput por vpad. (a) é o jogo que
    lê o nativo: a sonda de hoje conta as vagas antes de abrir o HID, e o caso fica sem medida.
    """
    if caso.mascara != "dualsense":
        return {}
    c = sonda.get("contagem", {})
    vagas = int(str(c.get("vagas_xinput", 0) or 0))
    return {
        "vagas_xinput": vagas,
        "ordem_xinput": c.get("ordem_xinput", ""),
        "b_so_xinput_ve_o_controle": vagas >= caso.vpads,
        "a_le_o_nativo": "não medido: a sonda conta as vagas antes de abrir o HID",
    }


def rodada(
    proton: Path, sonda: Path, ensaio: Ensaio, casos: Iterable[Caso] | None = None,
    runtime: Path | None = None,
) -> Resultado:
    """A matriz inteira: a perna que o ensaio não sustenta fica «não medida», nunca «passou»."""
    lista = list(casos if casos is not None else matriz())
    resultado = Resultado([], {}, {}, len(lista))
    for caso in lista:
        motivo = ensaio.sustenta(caso)
        if motivo is not None:
            resultado.nao_medidas[caso.nome()] = motivo
            continue
        env = ensaio.montar(caso)
        try:
            lida = ler_sonda(rodar_a_sonda(proton, sonda, env, runtime))
            resultado.falhas.extend(julgar(caso, lida, ensaio.medir()))
            resultado.relato[caso.nome()] = os_casos_da_mascara(caso, lida)
        finally:
            ensaio.desmontar()
    return resultado


def buildid_do_runtime(runtime: Path | None) -> str:
    """O buildid do Steam Linux Runtime instalado em ``runtime`` (o ``force_install_dir``)."""
    from hefesto_dualsense4unix.daemon.subsystems.identidade_do_jogo import buildid_do_appid

    if runtime is None:
        return ""
    return buildid_do_appid(int(APPID_DO_RUNTIME), [runtime / "steamapps"]) or ""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("proton", type=Path, help="a pasta do Proton candidato")
    parser.add_argument("--fixada", type=Path, default=None)
    parser.add_argument("--sonda", type=Path, required=True, help="o sonda.exe")
    parser.add_argument("--tarball-sha256", required=True)
    parser.add_argument("--compilar", action="store_true",
                        help="aceita a sonda compilada aqui, quando o pino diz «a-medir»")
    parser.add_argument("--runtime", type=Path, default=None,
                        help="a pasta do Steam Linux Runtime (a do _v2-entry-point)")
    parser.add_argument("--medida", type=Path, default=None,
                        help="a sonda.txt do banco de prova, que diz o que o runner sustenta")
    parser.add_argument("--saida", type=Path, default=None, help="onde gravar a linha")
    parser.add_argument("--relato", type=Path, default=None,
                        help="onde gravar o JSON dos casos (a) e (b) por perna")
    args = parser.parse_args(argv)

    if not na_vm_ou_no_ci():
        print("a rodada só roda numa VM ou no CI: o vpad de prova apareceria aos jogos",
              file=sys.stderr)
        return RC_FORA_DA_VM
    pino = (RAIZ / "assets/sonda-proton/pino.txt").read_text(encoding="utf-8")
    conf = dict(
        linha.split("=", 1)
        for linha in pino.splitlines()
        if "=" in linha and not linha.lstrip().startswith("#")
    )
    if conf.get("sha256") != sha256(args.sonda) and not (
        args.compilar and conf.get("sha256") == "a-medir"
    ):
        print("o sonda.exe não bate com assets/sonda-proton/pino.txt", file=sys.stderr)
        return RC_SONDA_SEM_PINO

    hoje = date.today().isoformat()
    buildid = buildid_do_runtime(args.runtime)
    f = qp.ficha(args.proton, args.fixada)
    if not f.passou:
        linha = qp.linha_do_recibo(f, args.tarball_sha256, qp.RODADA_NAO_RODOU, hoje, buildid)
        resultado = Resultado([], {}, {}, 0)
    else:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from ensaio_da_vm import EnsaioDaVm

        resultado = rodada(args.proton, args.sonda, EnsaioDaVm(args.medida),
                           runtime=args.runtime)
        linha = qp.linha_do_recibo(
            f, args.tarball_sha256, resultado.estado(), hoje, buildid
        )
    print(linha)
    if args.saida is not None:
        args.saida.write_text(linha + "\n", encoding="utf-8")
    if args.relato is not None:
        args.relato.write_text(json.dumps(
            {"nao_medidas": resultado.nao_medidas, "casos": resultado.relato},
            ensure_ascii=False, indent=1,
        ) + "\n", encoding="utf-8")
    return 0 if f.passou and resultado.estado() == qp.VEREDITO_PASSOU else 1


if __name__ == "__main__":
    raise SystemExit(main())
