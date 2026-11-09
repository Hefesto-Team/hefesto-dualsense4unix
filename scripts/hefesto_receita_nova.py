#!/usr/bin/env python3
"""A receita do backport da casa sobre a versão nova publicada, para o atualizador.

Lê a cópia das receitas (``scripts/construir_*_backport.sh`` e ``assets/*-backport``), acha a
versão mais nova publicada, baixa o fonte conferido na origem e tria a série da casa sobre ele
antes de construir pela receita. O BlueZ só passa com a assinatura da release (o ``.tar.sign`` do
kernel.org) conferida pelo ``gpgv`` contra o chaveiro da casa e as digitais fixadas no BASELINE.
O PipeWire e o WirePlumber não assinam a tag: a versão nova só passa com a soma que a casa revisou
e fixou em ``SOMAS-REVISADAS``; sem a soma, a casa precisa revisar a versão nova. Cada patch que aplica sem fuzz fica; o que só aplica ao contrário o
upstream já traz e sai da série; o que não aplica de nenhum jeito, ou um patch da casa que o
upstream levou, para tudo: a casa precisa revisar os patches.

Uso: ``hefesto_receita_nova.py construir --peca bluez|pipewire|portal --receitas DIR --obra DIR``.
Saídas: 0 entregue em ``<obra>/entrega``; 3 faltam dependências de build; 9 nada a construir
(a versão de cima já traz a cura); 10 a casa precisa revisar os patches ou a versão nova; 4 a
fonte não confere.
"""
from __future__ import annotations

import argparse
import hashlib
import base64
import json
import lzma
import os
import re
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

RC_DEPS = 3
RC_FONTE = 4
RC_NADA = 9
RC_REVISAR = 10
PRAZO_S = 120
TETO_DO_TAR = 512 * 1024 * 1024
CHAVEIRO_DO_BLUEZ = "chaves-de-release.asc"
SOMAS_REVISADAS = "SOMAS-REVISADAS"
INDICE_DO_BLUEZ = "https://www.kernel.org/pub/linux/bluetooth/"
API_DO_GITLAB = "https://gitlab.freedesktop.org/api/v4/projects/pipewire%2F{}/releases?per_page=40"
ARQUIVO_DO_GITLAB = "https://gitlab.freedesktop.org/pipewire/{0}/-/archive/{1}/{0}-{1}.tar.bz2"
SCRIPTS = {"bluez": "construir_bluez_backport.sh", "pipewire": "construir_pipewire_backport.sh",
           "portal": "construir_portal_cosmic_backport.sh"}
ASSETS = {"bluez": "bluez-backport", "pipewire": "pipewire-backport",
          "portal": "portal-cosmic-backport"}
CACHE = {"bluez": "HEFESTO_BLUEZ_CACHE", "pipewire": "HEFESTO_PIPEWIRE_CACHE",
         "portal": "HEFESTO_PORTAL_CACHE"}
SAIDA = {"bluez": "bluez-backport", "pipewire": "pipewire-backport",
         "portal": "portal-cosmic-backport"}
ASSINATURA = "Hefesto DualSense4Unix Project <hefesto-dualsense4unix@users.noreply.github.com>"


class Revisar(Exception):
    """A série da casa não cabe na versão nova sem alguém olhar."""

    def __init__(self, porque: str, o_que: str = "os patches") -> None:
        super().__init__(porque)
        self.o_que = o_que


class FonteNaoConfere(Exception):
    """O que se baixou não é o que se publicou."""


def ordem(versao: str) -> tuple[int, ...]:
    return tuple(int(p) for p in re.findall(r"\d+", versao))


def ler_baseline(texto: str) -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in texto.splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores.setdefault(chave, valor)
    return valores


def baseline_com(texto: str, novos: dict[str, str]) -> str:
    linhas = texto.splitlines()
    faltam = dict(novos)
    for i, linha in enumerate(linhas):
        chave = linha.split("=", 1)[0] if "=" in linha and not linha.startswith("#") else ""
        if chave in faltam:
            linhas[i] = f"{chave}={faltam.pop(chave)}"
    linhas += [f"{chave}={valor}" for chave, valor in faltam.items()]
    return "\n".join(linhas) + "\n"


def ultima_do_bluez(indice: str) -> str | None:
    versoes = set(re.findall(r"bluez-(\d+\.\d+)\.tar\.xz", indice))
    return max(versoes, key=ordem) if versoes else None


def somas_revisadas(texto: str) -> dict[tuple[str, str], str]:
    somas: dict[tuple[str, str], str] = {}
    for linha in texto.splitlines():
        partes = linha.split()
        if len(partes) == 3 and re.fullmatch(r"[0-9a-f]{64}", partes[2]):
            somas.setdefault((partes[0], partes[1]), partes[2])
    return somas


def desarmar(texto: str) -> bytes:
    """O chaveiro em ASCII armor vira o binário que o ``gpgv`` lê."""
    blocos: list[bytes] = []
    linhas: list[str] | None = None
    corpo = False
    for linha in texto.splitlines():
        linha = linha.strip()
        if linha == "-----BEGIN PGP PUBLIC KEY BLOCK-----":
            linhas, corpo = [], False
        elif linha == "-----END PGP PUBLIC KEY BLOCK-----" and linhas is not None:
            blocos.append(base64.b64decode("".join(linhas), validate=True))
            linhas = None
        elif linhas is not None and not corpo:
            corpo = linha == ""
        elif linhas is not None and not linha.startswith("="):
            linhas.append(linha)
    if not blocos:
        raise FonteNaoConfere("o chaveiro da casa não traz chave nenhuma")
    return b"".join(blocos)


def conferir_assinatura(assinatura: Path, dado: Path, chaveiro: Path, digitais: set[str],
                        pasta: Path) -> str:
    """A digital primária de quem assinou ``dado``, conferida só contra o chaveiro e as fixadas."""
    gpgv = shutil.which("gpgv")
    if gpgv is None:
        raise FonteNaoConfere("sem o gpgv, a assinatura do upstream não se confere")
    if not digitais:
        raise FonteNaoConfere("o BASELINE não fixa as digitais de quem assina a release")
    lar = pasta / "gpgv"
    shutil.rmtree(lar, ignore_errors=True)
    lar.mkdir(parents=True, mode=0o700)
    anel = lar / "chaveiro.gpg"
    try:
        anel.write_bytes(desarmar(chaveiro.read_text(encoding="utf-8")))
    except (OSError, ValueError) as erro:
        raise FonteNaoConfere(f"o chaveiro da casa não se lê: {erro}") from erro
    feito = subprocess.run(
        [gpgv, "--homedir", str(lar), "--keyring", str(anel), "--status-fd", "1",
         str(assinatura), str(dado)],
        capture_output=True, timeout=PRAZO_S, check=False,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
    status = feito.stdout.decode("utf-8", "replace").splitlines()
    validas = [linha.split()[-1] for linha in status if linha.startswith("[GNUPG:] VALIDSIG ")]
    if feito.returncode != 0 or not validas:
        sem_chave = any(linha.startswith("[GNUPG:] NO_PUBKEY ") for linha in status)
        porque = "a chave que assinou não está no chaveiro da casa" if sem_chave else \
            "a assinatura não confere"
        raise FonteNaoConfere(f"{dado.name}: {porque}")
    fora = [digital for digital in validas if digital not in digitais]
    if fora:
        raise FonteNaoConfere(f"{dado.name}: assinado por {fora[0]}, fora das digitais fixadas")
    return validas[0]


def _descomprimir(dado: bytes, destino: Path) -> None:
    descompressor = lzma.LZMADecompressor()
    escritos = 0
    with destino.open("wb") as saida:
        pedaco = descompressor.decompress(dado, max_length=1024 * 1024)
        while True:
            escritos += len(pedaco)
            if escritos > TETO_DO_TAR:
                raise FonteNaoConfere(f"{destino.name} passa do teto")
            saida.write(pedaco)
            if descompressor.eof or (descompressor.needs_input and not pedaco):
                break
            pedaco = descompressor.decompress(b"", max_length=1024 * 1024)
    if not descompressor.eof:
        raise FonteNaoConfere(f"{destino.name} chegou cortado")


def ultima_da_serie(lancamentos: object, serie: tuple[int, ...]) -> str | None:
    versoes = []
    for item in lancamentos if isinstance(lancamentos, list) else []:
        tag = str(item.get("tag_name", "")) if isinstance(item, dict) else ""
        if re.fullmatch(r"\d+\.\d+\.\d+", tag) and ordem(tag)[:len(serie)] == serie:
            versoes.append(tag)
    return max(versoes, key=ordem) if versoes else None


@dataclass
class Triagem:
    manter: list[str] = field(default_factory=list)
    sairam: list[str] = field(default_factory=list)
    revisar: list[str] = field(default_factory=list)


def _patch(arvore: Path, arquivo: Path, *extra: str) -> bool:
    feito = subprocess.run(["patch", "-p1", "-F0", "-N", "-s", *extra], cwd=arvore,
                           input=arquivo.read_bytes(), capture_output=True, timeout=PRAZO_S,
                           check=False)
    return feito.returncode == 0


def triar(arvore: Path, serie: list[tuple[str, Path, bool]]) -> Triagem:
    """Aplica a série em ordem sobre ``arvore``: a que aplica fica (e se aplica de verdade)."""
    triagem = Triagem()
    for nome, arquivo, da_casa in serie:
        if _patch(arvore, arquivo, "--dry-run"):
            _patch(arvore, arquivo)
            triagem.manter.append(nome)
        elif not da_casa and _patch(arvore, arquivo, "-R", "--dry-run"):
            triagem.sairam.append(nome)
        else:
            triagem.revisar.append(nome)
    return triagem


def _rede() -> Path | None:
    valor = os.environ.get("HEFESTO_RECEITA_REDE", "")
    return Path(valor) if valor else None


def ler(url: str) -> bytes:
    falsa = _rede()
    if falsa is not None:
        return (falsa / urllib.parse.quote(url, safe="")).read_bytes()
    pedido = urllib.request.Request(url, headers={"User-Agent": "hefesto-dualsense4unix"})
    with urllib.request.urlopen(pedido, timeout=PRAZO_S) as resposta:
        return bytes(resposta.read())


def _sha(dado: bytes) -> str:
    return hashlib.sha256(dado).hexdigest()


def _extrair(tarball: Path, destino: Path) -> Path:
    shutil.rmtree(destino, ignore_errors=True)
    destino.mkdir(parents=True)
    with tarfile.open(tarball) as tar:
        tar.extractall(destino, filter="data")
    raizes = [p for p in destino.iterdir() if p.is_dir()]
    if len(raizes) != 1:
        raise FonteNaoConfere(f"{tarball.name} não abre numa pasta só")
    return raizes[0]


def _copiar_a_receita(receitas: Path, obra: Path, peca: str) -> Path:
    receita = obra / "receita"
    shutil.rmtree(receita, ignore_errors=True)
    (receita / "scripts").mkdir(parents=True)
    shutil.copy2(receitas / "scripts" / SCRIPTS[peca], receita / "scripts" / SCRIPTS[peca])
    shutil.copytree(receitas / "assets" / ASSETS[peca], receita / "assets" / ASSETS[peca])
    return receita


def _entrada_do_changelog(pacote: str, versao: str, linhas: list[str]) -> str:
    data = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime())
    corpo = "".join(f"  * {linha}\n" for linha in linhas)
    return f"{pacote} ({versao}) noble; urgency=medium\n\n{corpo}\n -- {ASSINATURA}  {data}\n\n"


def _antepor(arquivo: Path, entrada: str) -> None:
    arquivo.write_text(entrada + arquivo.read_text(encoding="utf-8"), encoding="utf-8")


def receita_do_bluez(receita: Path, fontes: Path) -> str:
    """Leva a receita do BlueZ à última publicada. Devolve a versão que vai construir."""
    assets = receita / "assets" / ASSETS["bluez"]
    texto = (assets / "BASELINE").read_text(encoding="utf-8")
    base = ler_baseline(texto)
    nova = ultima_do_bluez(ler(INDICE_DO_BLUEZ).decode("utf-8", "replace"))
    if nova is None or ordem(nova) <= ordem(base["VERSAO_UPSTREAM"]):
        return base["VERSAO_UPSTREAM"]
    nome = f"bluez-{nova}.tar.xz"
    dado = ler(INDICE_DO_BLUEZ + nome)
    fontes.mkdir(parents=True, exist_ok=True)
    tar = fontes / f"bluez-{nova}.tar"
    assinatura = fontes / f"bluez-{nova}.tar.sign"
    assinatura.write_bytes(ler(INDICE_DO_BLUEZ + assinatura.name))
    try:
        _descomprimir(dado, tar)
    except (lzma.LZMAError, EOFError) as erro:
        raise FonteNaoConfere(f"o {nome} não abre: {erro}") from erro
    conferir_assinatura(assinatura, tar, assets / CHAVEIRO_DO_BLUEZ,
                        set(base.get("CHAVES_DE_RELEASE", "").split()), fontes)
    arvore = _extrair(tar, fontes / "triagem")
    if arvore.name != f"bluez-{nova}":
        raise FonteNaoConfere(f"o {nome} assinado abre {arvore.name}, não bluez-{nova}")
    esperado = _sha(dado)
    vanilla = _sha((arvore / "profiles" / "input" / "device.c").read_bytes())
    revisao = int(base["REVISAO_ULTIMA"])
    serie = []
    for patch in base[f"PATCHES_R{revisao}"].split():
        curto = "-".join(patch.split("-")[:2])
        serie.append((patch, assets / "patches" / patch, f"MARCA_{curto}" in base))
    triagem = triar(arvore, serie)
    if triagem.revisar:
        raise Revisar(f"{', '.join(triagem.revisar)} não aplica sem fuzz no {nova}")
    nova_revisao = revisao + 1
    (assets / "BASELINE").write_text(baseline_com(texto, {
        "VERSAO_UPSTREAM": nova, "FONTE_UPSTREAM_URL": INDICE_DO_BLUEZ + nome,
        "FONTE_UPSTREAM_SHA256": esperado, "VERSAO_BASE": f"{nova}-0ubuntu0.1",
        "REVISAO_ULTIMA": str(nova_revisao), f"PATCHES_R{nova_revisao}": " ".join(triagem.manter),
        "SHA256_DEVICE_C_VANILLA": vanilla,
        f"SHA256_DEVICE_C_R{nova_revisao}": _sha(
            (arvore / "profiles" / "input" / "device.c").read_bytes()),
    }), encoding="utf-8")
    linhas = [f"A base sobe para o upstream {nova}, pelo atualizador."]
    if triagem.sairam:
        linhas.append(f"Saem da série, porque o {nova} já os traz: {' '.join(triagem.sairam)}.")
    cobre = re.search(r"Cobre a segurança da distro até: (\S+)",
                      (assets / "debian" / "changelog.hefesto").read_text(encoding="utf-8"))
    if cobre:
        linhas.append(f"Cobre a segurança da distro até: {cobre.group(1)}")
    _antepor(assets / "debian" / "changelog.hefesto", _entrada_do_changelog(
        "bluez", f"{nova}-0ubuntu0.1~hefesto24.04.{nova_revisao}", linhas))
    return nova


def _arquivo_da_tag(projeto: str, versao: str, fontes: Path, revisada: str) -> Path:
    url = ARQUIVO_DO_GITLAB.format(projeto, versao)
    dado = ler(url)
    if _sha(dado) != revisada:
        raise FonteNaoConfere(f"o {projeto} {versao} baixado não tem a soma que a casa revisou")
    fontes.mkdir(parents=True, exist_ok=True)
    destino = fontes / url.rsplit("/", 1)[1]
    destino.write_bytes(dado)
    return destino


def _commit_da_tag(tarball: Path) -> str:
    try:
        with tarfile.open(tarball) as tar:
            comentario = getattr(tar, "pax_headers", {}).get("comment", "")
    except tarfile.TarError:
        comentario = ""
    return comentario if re.fullmatch(r"[0-9a-f]{40}", comentario or "") else ""


def receita_do_pipewire(receita: Path, fontes: Path) -> str:
    assets = receita / "assets" / ASSETS["pipewire"]
    texto = (assets / "BASELINE").read_text(encoding="utf-8")
    base = ler_baseline(texto)
    novos: dict[str, str] = {}
    try:
        revisadas = somas_revisadas((assets / SOMAS_REVISADAS).read_text(encoding="utf-8"))
    except OSError:
        revisadas = {}
    for prefixo, projeto in (("PW", "pipewire"), ("WP", "wireplumber")):
        atual = base[f"{prefixo}_VERSAO_UPSTREAM"]
        lancamentos = json.loads(ler(API_DO_GITLAB.format(projeto)).decode("utf-8"))
        nova = ultima_da_serie(lancamentos, ordem(atual)[:2])
        if nova is None or ordem(nova) <= ordem(atual):
            continue
        sha = revisadas.get((projeto, nova))
        if sha is None:
            raise Revisar(f"o {projeto} {nova} não assina a tag, e a casa ainda não fixou a soma "
                          "dele", o_que="a versão nova")
        tarball = _arquivo_da_tag(projeto, nova, fontes, sha)
        novos.update({
            f"{prefixo}_VERSAO_UPSTREAM": nova, f"{prefixo}_FONTE_SHA256": sha,
            f"{prefixo}_FONTE_URL": ARQUIVO_DO_GITLAB.format(projeto, nova),
            f"{prefixo}_TAG_COMMIT": _commit_da_tag(tarball) or base[f"{prefixo}_TAG_COMMIT"],
            f"{prefixo}_REVISAO": f"{nova}-0~hefesto24.04.1",
        })
        if prefixo == "PW":
            arvore = _extrair(tarball, fontes / "triagem")
            metadata = arvore / "src" / "modules" / "module-metadata" / "metadata.c"
            novos["PW_SHA256_METADATA_C"] = _sha(metadata.read_bytes())
            serie = [(p, assets / "patches" / p, False) for p in base["PW_PATCHES"].split()]
            triagem = triar(arvore, serie)
            if triagem.revisar:
                raise Revisar(f"{', '.join(triagem.revisar)} não aplica sem fuzz no {nova}")
            novos["PW_PATCHES"] = " ".join(triagem.manter)
        linhas = [f"O upstream {nova}, pelo atualizador, sobre o mesmo empacotamento.",
                  f"Upstream: {nova} {novos[f'{prefixo}_TAG_COMMIT']}",
                  f"Empacotamento: {base[f'{prefixo}_EMPACOTAMENTO_VERSAO']}"]
        _antepor(assets / "debian" / f"changelog.{projeto}.hefesto",
                 _entrada_do_changelog(projeto, novos[f"{prefixo}_REVISAO"], linhas))
    if novos:
        (assets / "BASELINE").write_text(baseline_com(texto, novos), encoding="utf-8")
    return novos.get("PW_VERSAO_UPSTREAM", base["PW_VERSAO_UPSTREAM"])


def construir(peca: str, receitas: Path, obra: Path, versao_do_portal: str = "") -> int:
    obra.mkdir(parents=True, exist_ok=True)
    receita = _copiar_a_receita(receitas, obra, peca)
    fontes = obra / "fontes-da-triagem"
    try:
        if peca == "bluez":
            versao = receita_do_bluez(receita, fontes)
        elif peca == "pipewire":
            versao = receita_do_pipewire(receita, fontes)
        else:
            versao = versao_do_portal
    except Revisar as erro:
        print(f"a casa precisa revisar {erro.o_que}: {erro}")
        return RC_REVISAR
    except (FonteNaoConfere, OSError, ValueError, KeyError) as erro:
        print(f"a fonte não confere: {erro}")
        return RC_FONTE
    finally:
        shutil.rmtree(fontes, ignore_errors=True)
    cache = obra / "cache"
    ambiente = {"PATH": "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
                "HOME": str(obra), "LC_ALL": "C.UTF-8", CACHE[peca]: str(cache)}
    if peca == "portal" and versao:
        ambiente["HEFESTO_PORTAL_VERSAO"] = versao
    feito = subprocess.run(["bash", str(receita / "scripts" / SCRIPTS[peca])], env=ambiente,
                           check=False)
    if feito.returncode == RC_DEPS:
        print("faltam dependências de build: rode o install, que as lista")
        return RC_DEPS
    if feito.returncode == RC_NADA:
        print("a versão de cima já traz a cura")
        return RC_NADA
    if feito.returncode != 0:
        print(f"a casa precisa revisar os patches: a receita parou no {versao} "
              f"(código {feito.returncode})")
        return RC_REVISAR
    entrega = obra / "entrega"
    shutil.rmtree(entrega, ignore_errors=True)
    shutil.copytree(cache / SAIDA[peca], entrega)
    print(f"entregue: {peca} {versao}")
    return 0


def main(argv: list[str] | None = None) -> int:
    leitor = argparse.ArgumentParser(prog="hefesto_receita_nova.py")
    sub = leitor.add_subparsers(dest="verbo", required=True)
    c = sub.add_parser("construir")
    c.add_argument("--peca", choices=sorted(SCRIPTS), required=True)
    c.add_argument("--receitas", type=Path, required=True)
    c.add_argument("--obra", type=Path, required=True)
    c.add_argument("--portal-do-apt", default="")
    args = leitor.parse_args(argv)
    if args.portal_do_apt and not re.fullmatch(r"[0-9A-Za-z.+:~-]+", args.portal_do_apt):
        print("versão do portal inválida")
        return 2
    return construir(args.peca, args.receitas, args.obra, args.portal_do_apt)


if __name__ == "__main__":
    sys.exit(main())
