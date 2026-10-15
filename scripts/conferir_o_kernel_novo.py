#!/usr/bin/env python3
"""Confere um kernel novo contra os drivers patchados do Hefesto, antes de ele chegar.

O passo 1 do ritual de cada `assets/dkms/<pacote>/patch/BASELINE` é perguntar se o
arquivo de fábrica do kernel novo é a base da série. Este script responde por pacote:

- «confere»: o sha256 do arquivo de fábrica é o de uma base conhecida (a raiz do pacote
  ou uma pasta de `fonte-por-kernel/`); falta só o build contra os headers;
- «aplica limpa»: o sha muda, e a série aplica sem fuzz (`patch -F0`); o rebase é uma
  pasta nova em `fonte-por-kernel/` com a série sobre o arquivo novo;
- «pede rebase à mão»: algum patch deixa pedaços de fora, e a saída diz quais.

O fonte é um diretório com a árvore do kernel ou `--pop <commit>`, que baixa só os
arquivos que os pacotes patcham, de `raw.githubusercontent.com/pop-os/linux`, para um
diretório temporário vazio. Sai com 0 só quando todos os pacotes conferem. Nunca
escreve em `assets/`, nos BASELINE nem no sistema: a série roda em cópias temporárias.

    scripts/conferir_o_kernel_novo.py /caminho/para/linux
    scripts/conferir_o_kernel_novo.py --pop 8b969b992b134ea1103abf368be2dc3913d677a7
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
DKMS = RAIZ / "assets" / "dkms"
URL_DO_POP = "https://raw.githubusercontent.com/pop-os/linux/{commit}/{caminho}"

#: O arquivo do kernel que cada pacote patcha e as chaves do BASELINE que guardam o
#: sha256 dele de fábrica. Pacote novo em `assets/dkms/` entra aqui, e uma régua cobra.
PACOTES: dict[str, dict[str, tuple[str, ...]]] = {
    "hid-playstation": {"drivers/hid/hid-playstation.c": ("SHA256_VANILLA_C",)},
    "hid-nintendo": {"drivers/hid/hid-nintendo.c": ("SHA256_VANILLA_C",)},
    "uhid": {"drivers/hid/uhid.c": ("SHA256_VANILLA_C",)},
    "usb-f-hid": {"drivers/usb/gadget/function/f_hid.c": ("SHA256_VANILLA_C",)},
    "rtw88-usb": {
        "drivers/net/wireless/realtek/rtw88/usb.c": (
            "SHA256_VANILLA_C",
            "SHA256_VANILLA_C_7_0_11",
            "SHA256_VANILLA_C_7_1_5",
        ),
        "drivers/net/wireless/realtek/rtw88/usb.h": ("SHA256_VANILLA_H",),
    },
}

CONFERE = "confere"
APLICA_LIMPA = "aplica limpa"
PEDE_REBASE = "pede rebase à mão"
SEM_ARQUIVO = "o fonte não tem o arquivo"


@dataclass
class Serie:
    nome: str
    pasta: Path
    patches: list[str]


@dataclass
class Resposta:
    pacote: str
    veredito: str
    base: str = ""
    serie: str = ""
    shas: dict[str, str] = field(default_factory=dict)
    por_patch: dict[str, str] = field(default_factory=dict)

    def linha(self) -> str:
        detalhe = ""
        if self.veredito == CONFERE:
            detalhe = f"o de fábrica é a base {self.base}"
        elif self.veredito == APLICA_LIMPA:
            detalhe = f"a série {self.serie} entra sem fuzz"
            ja = [nome[:4] for nome, estado in self.por_patch.items() if estado != "entra"]
            if ja:
                detalhe += f" ({', '.join(ja)} já está no kernel)"
        elif self.veredito == PEDE_REBASE:
            detalhe = f"série {self.serie}: " + "; ".join(
                f"{nome[:4]} {estado}" for nome, estado in self.por_patch.items()
            )
        elif self.veredito == SEM_ARQUIVO:
            detalhe = ", ".join(c for c, s in self.shas.items() if not s)
        shas = " ".join(f"{Path(c).name}={s[:8] or '-'}" for c, s in self.shas.items())
        return f"  {self.pacote:<16} {self.veredito:<18} {shas}  {detalhe}".rstrip()


def _linhas_do_baseline(pacote: str) -> list[str]:
    return (DKMS / pacote / "patch" / "BASELINE").read_text(encoding="utf-8").splitlines()


def _chaves(linhas: list[str]) -> dict[str, str]:
    saida: dict[str, str] = {}
    for linha in linhas:
        if linha.startswith("#") or "=" not in linha or linha.startswith("POR_KERNEL="):
            continue
        chave, _, valor = linha.partition("=")
        saida.setdefault(chave.strip(), valor.strip())
    return saida


def _serie_da_raiz(linhas: list[str]) -> list[str]:
    """`PATCH=` na ordem do arquivo, ou `PATCH_<n>=` na ordem do número (o rtw88)."""
    simples = [ln.partition("=")[2].strip() for ln in linhas if ln.startswith("PATCH=")]
    numeradas = sorted(
        (int(m.group(1)), m.group(2).strip())
        for ln in linhas
        if (m := re.match(r"PATCH_(\d+)=(.+)", ln))
    )
    return simples + [nome for _, nome in numeradas]


def _bases(pacote: str) -> list[tuple[str, dict[str, set[str]]]]:
    """As bases conhecidas: a da raiz e uma por linha `POR_KERNEL` do BASELINE."""
    linhas = _linhas_do_baseline(pacote)
    chaves = _chaves(linhas)
    arquivos = PACOTES[pacote]
    raiz = {
        caminho: {chaves[k] for k in nomes if chaves.get(k)} for caminho, nomes in arquivos.items()
    }
    bases = [("da raiz", raiz)]
    principal = next(iter(arquivos))
    for linha in linhas:
        if linha.startswith("POR_KERNEL="):
            campos = dict(par.split("=", 1) for par in linha.split())
            if len(arquivos) == 1:
                bases.append(
                    (
                        f"fonte-por-kernel/{campos['POR_KERNEL']}",
                        {principal: {campos["SHA256_VANILLA_C"]}},
                    )
                )
    return bases


def _series(pacote: str) -> list[Serie]:
    linhas = _linhas_do_baseline(pacote)
    nomes = _serie_da_raiz(linhas)
    series = [Serie("da raiz", DKMS / pacote / "patch", nomes)]
    por_kernel = DKMS / pacote / "fonte-por-kernel"
    if por_kernel.is_dir():
        for pasta in sorted(p for p in por_kernel.iterdir() if (p / "patch").is_dir()):
            series.append(Serie(f"de fonte-por-kernel/{pasta.name}", pasta / "patch", nomes))
    return series


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest() if caminho.is_file() else ""


def _aplica(patch: Path, arvore: Path, arquivos: list[str]) -> str:
    """Aplica um patch na cópia, sem fuzz, e diz o que aconteceu com ele."""
    texto = patch.read_text(encoding="utf-8", errors="replace")
    comando = ["patch", "-F0", "--forward", "--no-backup-if-mismatch", "-r", "-"]
    if re.search(r"^\+\+\+ b/", texto, re.M):
        comando += ["-p1", "-d", str(arvore)]
    else:
        comando += [str(arvore / arquivos[0])]
    resultado = subprocess.run(
        comando, input=texto, capture_output=True, text=True, timeout=60, check=False
    )
    saida = resultado.stdout + resultado.stderr
    if "Reversed (or previously applied) patch detected" in saida:
        return "já está no kernel"
    falhos = re.findall(r"Hunk #(\d+) FAILED", saida)
    if falhos:
        return f"{len(falhos)} pedaço(s) de fora (#{', #'.join(falhos)})"
    if resultado.returncode != 0:
        return f"não aplica (rc={resultado.returncode})"
    return "entra"


def _experimenta(serie: Serie, fonte: Path, arquivos: list[str]) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="conferir-kernel-") as tmp:
        arvore = Path(tmp)
        for caminho in arquivos:
            destino = arvore / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(fonte / caminho, destino)
        return {nome: _aplica(serie.pasta / nome, arvore, arquivos) for nome in serie.patches}


def conferir(pacote: str, fonte: Path, *, so_a_raiz: bool = False) -> Resposta:
    arquivos = list(PACOTES[pacote])
    shas = {caminho: _sha(fonte / caminho) for caminho in arquivos}
    resposta = Resposta(pacote, SEM_ARQUIVO, shas=shas)
    if not all(shas.values()):
        return resposta
    bases = _bases(pacote)[:1] if so_a_raiz else _bases(pacote)
    for nome, esperado in bases:
        if all(shas[c] in esperado.get(c, set()) for c in arquivos):
            resposta.veredito, resposta.base = CONFERE, nome
            return resposta
    melhor: tuple[int, Serie, dict[str, str]] | None = None
    series = _series(pacote)[:1] if so_a_raiz else _series(pacote)
    for serie in series:
        estados = _experimenta(serie, fonte, arquivos)
        ruins = sum(1 for e in estados.values() if e not in ("entra", "já está no kernel"))
        if ruins == 0:
            resposta.veredito, resposta.serie, resposta.por_patch = (
                APLICA_LIMPA,
                serie.nome,
                estados,
            )
            return resposta
        if melhor is None or ruins < melhor[0]:
            melhor = (ruins, serie, estados)
    assert melhor is not None
    resposta.veredito, resposta.serie, resposta.por_patch = PEDE_REBASE, melhor[1].nome, melhor[2]
    return resposta


def baixar_do_pop(commit: str, destino: Path) -> None:
    """Baixa só os arquivos que os pacotes patcham, do `pop-os/linux` naquele commit."""
    if not re.fullmatch(r"[0-9a-f]{7,40}", commit):
        raise ValueError(f"commit inválido: {commit!r}")
    for arquivos in PACOTES.values():
        for caminho in arquivos:
            alvo = destino / caminho
            alvo.parent.mkdir(parents=True, exist_ok=True)
            url = URL_DO_POP.format(commit=commit, caminho=caminho)
            with urllib.request.urlopen(url, timeout=60) as resposta:
                alvo.write_bytes(resposta.read())


def pacotes_com_baseline() -> list[str]:
    return sorted(p.parent.parent.name for p in DKMS.glob("*/patch/BASELINE"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("fonte", nargs="?", type=Path, help="a árvore do kernel")
    origem.add_argument("--pop", metavar="COMMIT", help="um commit de pop-os/linux")
    parser.add_argument(
        "--so-a-raiz",
        action="store_true",
        help="ignora as bases de fonte-por-kernel/ (mede a série da raiz contra o kernel)",
    )
    parser.add_argument("--json", action="store_true", help="a resposta em JSON")
    args = parser.parse_args(argv)

    sem_mapa = [p for p in pacotes_com_baseline() if p not in PACOTES]
    if sem_mapa:
        print(f"pacote com BASELINE sem mapa neste script: {', '.join(sem_mapa)}", file=sys.stderr)
        return 2

    with tempfile.TemporaryDirectory(prefix="conferir-kernel-pop-") as tmp:
        if args.pop:
            fonte = Path(tmp)
            try:
                baixar_do_pop(args.pop, fonte)
            except (OSError, ValueError) as erro:
                print(f"não consegui baixar o fonte do Pop: {erro}", file=sys.stderr)
                return 2
            rotulo = f"pop-os/linux {args.pop}"
        else:
            fonte = args.fonte.resolve()
            if not fonte.is_dir():
                print(f"{fonte} não é um diretório", file=sys.stderr)
                return 2
            rotulo = str(fonte)
        respostas = [conferir(p, fonte, so_a_raiz=args.so_a_raiz) for p in PACOTES]

    if args.json:
        print(json.dumps([r.__dict__ for r in respostas], ensure_ascii=False, indent=2))
    else:
        print(f"kernel: {rotulo}")
        for resposta in respostas:
            print(resposta.linha())
    return 0 if all(r.veredito == CONFERE for r in respostas) else 1


if __name__ == "__main__":
    raise SystemExit(main())
