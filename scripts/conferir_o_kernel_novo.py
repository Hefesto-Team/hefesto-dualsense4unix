#!/usr/bin/env python3
"""Confere um kernel novo contra os drivers patchados do Hefesto, antes de ele chegar.

O passo 1 do ritual de cada `assets/dkms/<pacote>/patch/BASELINE` é perguntar se o
arquivo de fábrica do kernel novo é a base da série. Este script responde por pacote:

- «confere»: o sha256 do arquivo de fábrica é o de uma base conhecida (a raiz do pacote
  ou uma pasta de `fonte-por-kernel/`); falta só o build contra os headers;
- «aplica limpa»: o sha muda, e a série aplica sem fuzz (`patch -F0`); o rebase é uma
  pasta nova em `fonte-por-kernel/` com a série sobre o arquivo novo;
- «pede rebase à mão»: algum patch deixa pedaços de fora, ou um arquivo que o build lê e
  o patch não toca (o `rx.h` do rtw88) mudou; a saída diz qual.

As bases saem do que o pacote guarda no disco: a raiz e cada pasta de `fonte-por-kernel/`
valem pelos arquivos de fábrica dela (o que ela guarda, com a série dela desfeita), mais as
chaves `SHA256_VANILLA_C|H[_<kernel>]` do BASELINE; build novo no BASELINE não pede edição aqui.

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

PACOTES: dict[str, dict[str, tuple[str, ...]]] = {
    "hid-playstation": {"drivers/hid/hid-playstation.c": ("SHA256_VANILLA_C",)},
    "hid-nintendo": {"drivers/hid/hid-nintendo.c": ("SHA256_VANILLA_C",)},
    "uhid": {"drivers/hid/uhid.c": ("SHA256_VANILLA_C",)},
    "usb-f-hid": {"drivers/usb/gadget/function/f_hid.c": ("SHA256_VANILLA_C",)},
    "rtw88-usb": {
        "drivers/net/wireless/realtek/rtw88/usb.c": ("SHA256_VANILLA_C",),
        "drivers/net/wireless/realtek/rtw88/usb.h": ("SHA256_VANILLA_H",),
        "drivers/net/wireless/realtek/rtw88/rx.h": (),
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
    base: str = ""


@dataclass
class Resposta:
    pacote: str
    veredito: str
    base: str = ""
    serie: str = ""
    shas: dict[str, str] = field(default_factory=dict)
    por_patch: dict[str, str] = field(default_factory=dict)
    mudou: list[str] = field(default_factory=list)

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
            partes = [f"{nome[:4]} {estado}" for nome, estado in self.por_patch.items()]
            if self.mudou:
                partes.append(f"mudou: {', '.join(Path(c).name for c in self.mudou)}")
            detalhe = f"série {self.serie}: " + "; ".join(partes)
        elif self.veredito == SEM_ARQUIVO:
            detalhe = ", ".join(c for c, s in self.shas.items() if not s)
        shas = " ".join(f"{Path(c).name}={s[:8] or '-'}" for c, s in self.shas.items())
        return f"  {self.pacote:<16} {self.veredito:<18} {shas}  {detalhe}".rstrip()


def _linhas_do_baseline(pacote: str) -> list[str]:
    return (DKMS / pacote / "patch" / "BASELINE").read_text(encoding="utf-8").splitlines()


_CHAVE_DE_FABRICA = re.compile(
    r"(?P<nome>SHA256_VANILLA_[CH])(?:_(?P<kernel>\d+(?:_\d+)*))?=(?P<sha>[0-9a-f]{64})"
)


def _chaves_de_fabrica(linhas: list[str], prefixos: tuple[str, ...]) -> list[tuple[str, str]]:
    """As chaves de fábrica do BASELINE pelo padrão: `(kernel, sha)`, com kernel vazio na da raiz."""
    saida: list[tuple[str, str]] = []
    for linha in linhas:
        achado = _CHAVE_DE_FABRICA.fullmatch(linha.strip())
        if achado and achado["nome"] in prefixos:
            saida.append((achado["kernel"] or "", achado["sha"]))
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


def _pastas_por_kernel(pacote: str) -> list[Path]:
    por_kernel = DKMS / pacote / "fonte-por-kernel"
    if not por_kernel.is_dir():
        return []
    return sorted(p for p in por_kernel.iterdir() if p.is_dir())


def _serie_da_pasta(pasta: Path) -> list[str]:
    """Os patches que a pasta guarda em `patch/`, na ordem do nome (o número manda)."""
    return sorted(p.name for p in (pasta / "patch").glob("*.patch"))


def _kernel_da_chave(pasta: Path, kernel: str) -> bool:
    """A chave `..._7_2_6` é da pasta `7.2.6-76070206`: o kernel da chave abre o nome dela."""
    nome = re.sub(r"[.-]", "_", pasta.name)
    return nome == kernel or nome.startswith(kernel + "_")


def _comando_do_patch(texto: str, arvore: Path, arquivos: list[str]) -> list[str]:
    comando = ["patch", "-F0", "--no-backup-if-mismatch", "-r", "-"]
    if re.search(r"^\+\+\+ b/", texto, re.M):
        return [*comando, "-p1", "-d", str(arvore)]
    return [*comando, str(arvore / arquivos[0])]


def _fabrica_dos_arquivos(pacote: str, pastas: list[Path], serie: Serie) -> dict[str, str]:
    """O sha de fábrica de cada arquivo: o que as pastas guardam, com a série desfeita.

    O arquivo vem da primeira pasta que o guarda (a do kernel, depois a raiz): o `usb.h` do
    7.2.6 é o da raiz. Com a série impossível de desfazer, só os arquivos que ela não toca
    (as chaves vazias do PACOTES) entram, porque os outros já não se sabem de fábrica.
    """
    arquivos = list(PACOTES[pacote])
    with tempfile.TemporaryDirectory(prefix="conferir-base-") as tmp:
        arvore = Path(tmp)
        for caminho in arquivos:
            origem = next(
                (p / Path(caminho).name for p in pastas if (p / Path(caminho).name).is_file()),
                None,
            )
            if origem is None:
                continue
            destino = arvore / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origem, destino)
        desfeita = True
        for nome in reversed(serie.patches):
            texto = (serie.pasta / nome).read_text(encoding="utf-8", errors="replace")
            feito = subprocess.run(
                [*_comando_do_patch(texto, arvore, arquivos), "-R", "-s"],
                input=texto,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            if feito.returncode != 0:
                desfeita = False
                break
        return {
            caminho: _sha(arvore / caminho)
            for caminho in arquivos
            if (desfeita or not PACOTES[pacote][caminho]) and (arvore / caminho).is_file()
        }


def _bases(pacote: str) -> list[tuple[str, dict[str, set[str]]]]:
    """As bases conhecidas: a da raiz e uma por pasta de `fonte-por-kernel/`.

    Cada uma vale pelos arquivos de fábrica que o disco guarda (a série dela desfeita) e pelas
    chaves de fábrica do BASELINE. Uma chave `_<kernel>` de pasta que existe é da pasta, nunca
    da raiz: a raiz construída num kernel que mudou é o verde falso que esta régua cura.
    """
    linhas = _linhas_do_baseline(pacote)
    arquivos = PACOTES[pacote]
    raiz_dir = DKMS / pacote
    pastas = _pastas_por_kernel(pacote)

    def com_chaves(base: dict[str, set[str]], pasta: Path | None) -> None:
        for caminho, prefixos in arquivos.items():
            for kernel, sha in _chaves_de_fabrica(linhas, prefixos):
                dona = next((p for p in pastas if kernel and _kernel_da_chave(p, kernel)), None)
                if dona == pasta:
                    base.setdefault(caminho, set()).add(sha)

    nomes_da_raiz = _serie_da_raiz(linhas)
    serie_da_raiz = Serie("da raiz", raiz_dir / "patch", nomes_da_raiz, "da raiz")
    raiz = {c: {s} for c, s in _fabrica_dos_arquivos(pacote, [raiz_dir], serie_da_raiz).items()}
    com_chaves(raiz, None)
    bases = [("da raiz", raiz)]
    for pasta in pastas:
        serie = Serie(pasta.name, pasta / "patch", _serie_da_pasta(pasta), pasta.name)
        base = {c: {s} for c, s in _fabrica_dos_arquivos(pacote, [pasta, raiz_dir], serie).items()}
        com_chaves(base, pasta)
        bases.append((f"fonte-por-kernel/{pasta.name}", base))
    return bases


def _series(pacote: str) -> list[Serie]:
    """A série da raiz (a do BASELINE) e a de cada pasta por kernel (a que ela guarda)."""
    nomes = _serie_da_raiz(_linhas_do_baseline(pacote))
    series = [Serie("da raiz", DKMS / pacote / "patch", nomes, "da raiz")]
    for pasta in _pastas_por_kernel(pacote):
        if (pasta / "patch").is_dir():
            nome = f"fonte-por-kernel/{pasta.name}"
            series.append(Serie(f"de {nome}", pasta / "patch", _serie_da_pasta(pasta), nome))
    return series


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest() if caminho.is_file() else ""


def _aplica(patch: Path, arvore: Path, arquivos: list[str]) -> str:
    """Aplica um patch na cópia, sem fuzz, e diz o que aconteceu com ele."""
    texto = patch.read_text(encoding="utf-8", errors="replace")
    comando = [*_comando_do_patch(texto, arvore, arquivos), "--forward"]
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
    bases = _bases(pacote)
    if so_a_raiz:
        bases = bases[:1]
    for nome, esperado in bases:
        if all(shas[c] in esperado.get(c, set()) for c in arquivos):
            resposta.veredito, resposta.base = CONFERE, nome
            return resposta
    lidos = [c for c, chaves in PACOTES[pacote].items() if not chaves]
    conhecidas = dict(bases)
    melhor: tuple[tuple[int, int], Serie, dict[str, str], list[str]] | None = None
    series = _series(pacote)[:1] if so_a_raiz else _series(pacote)
    for serie in series:
        estados = _experimenta(serie, fonte, arquivos)
        ruins = sum(1 for e in estados.values() if e not in ("entra", "já está no kernel"))
        base = conhecidas[serie.base]
        mudou = [c for c in lidos if shas[c] not in base.get(c, set())]
        casam = sum(1 for c in arquivos if shas[c] in base.get(c, set()))
        if ruins == 0 and not mudou:
            resposta.veredito, resposta.serie, resposta.por_patch = (
                APLICA_LIMPA,
                serie.nome,
                estados,
            )
            return resposta
        nota = (ruins + len(mudou), -casam)
        if melhor is None or nota < melhor[0]:
            melhor = (nota, serie, estados, mudou)
    assert melhor is not None
    _, serie, estados, mudou = melhor
    resposta.veredito, resposta.serie, resposta.por_patch = PEDE_REBASE, serie.nome, estados
    resposta.mudou = mudou
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
