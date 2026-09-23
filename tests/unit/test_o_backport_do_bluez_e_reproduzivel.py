"""BLUETOOTHD-NAO-DERRUBA-01 — o backport do BlueZ se reconstrói do repositório.

O DEFEITO QUE VEM ANTES DO PATCH, medido em 23/09/2026: a máquina dela roda
``5.86-0ubuntu0.1~hefesto24.04.3`` e nem o fonte, nem o patch, nem a receita
estavam no repositório ou no disco. O ``install.sh`` só consumia ``.deb``
prontos de um cache que já não existia. Quem quisesse mudar uma linha do
bluetoothd — e o ``hefesto-0002`` é exatamente isso — não tinha de onde partir.

Esta bancada prova, SEM REDE e sem sudo, que a receita versionada fecha:

- os patches aplicam com fuzz zero no ``device.c`` do tarball
  (``tests/fixtures/bluez-5.86/device.c``, byte a byte) e dão os hashes que o
  ``BASELINE`` fixa;
- o ``scripts/construir_bluez_backport.sh --preparar`` monta a árvore com
  ``dpkg-source`` a partir de fontes sintéticas com os MESMOS nomes, e duas
  corridas dão a mesma árvore;
- com os ``.deb`` da versão alvo no cache, o ``SHA256SUMS`` batendo e o
  ``ORIGEM.txt`` dizendo os patches da árvore, a segunda corrida não baixa nem
  compila — e um ``.deb`` feito com outro patch manda reconstruir;
- a revisão antiga só se reconstrói num cache que NÃO é o do install, medido
  pelo caminho e não pela variável;
- a versão alvo é ``~hefesto24.04.4``;
- a MORDIDA do ``hefesto-0002``: ``assets/bluez-backport/prova/eagain.c`` roda
  as ``hidp_send_*`` recortadas do ``device.c`` contra um ``socketpair`` cheio
  de verdade. O vanilla destrói o aparelho no EAGAIN; o patchado fica, conta o
  descarte e loga com limite de taxa; o erro terminal derruba nos dois;
- o script não instala nada.

AS MORDIDAS, provadas em 23/09/2026 (cada uma arrancada, vista vermelha e
devolvida com md5 conferido):

- tirar ``&& !hidp_send_err_transient(idev->send_err)`` do ``hidp_send_output``
  no ``hefesto-0002`` → ``test_o_patch_aplica_com_fuzz_zero_e_da_o_hash_do_baseline``
  e ``test_a_mordida_o_patchado_fica_no_eagain`` reprovam (o hash muda e o
  aparelho volta a ser destruído mil e uma vezes);
- tirar o ``rm -rf "${OBRA}"`` do ``preparar`` →
  ``test_duas_corridas_do_preparo_dao_a_mesma_arvore`` reprova: a segunda
  corrida acha a série "já aplicada" sobre um ``device.c`` que o tarball
  devolveu ao vanilla, e o hash do ``device.c`` não confere;
- fazer ``ja_construido`` devolver sempre 1 →
  ``test_com_os_debs_no_cache_a_corrida_nao_baixa_nem_compila`` reprova: o
  ``curl`` de mentira é chamado;
- trocar o ``! aead_do_kernel_disponivel`` do test-mesh-crypto por ``true`` →
  ``test_o_unit_do_bluez_so_perdoa_a_falha_que_a_maquina_explica`` reprova;
- acrescentar ``sudo apt-get install`` ao script, nu ou dentro de
  ``bash -c "..."`` → ``test_o_script_nao_instala_nada`` reprova;
- devolver a guarda da revisão antiga que só olhava se ``HEFESTO_BLUEZ_CACHE``
  estava vazia → ``test_revisao_antiga_so_se_reconstroi_fora_do_cache_do_install``
  reprova em três dos quatro jeitos de apontar, com rc=4 (foi baixar);
- tirar a comparação do ``ORIGEM.txt`` do ``ja_construido`` →
  ``test_debs_feitos_com_outro_patch_mandam_reconstruir`` reprova nos dois casos;
- trocar o ``morra`` do laço do ``unit_do_bluez`` por ``continue`` →
  ``test_o_laco_do_unit_so_deixa_passar_o_que_perdoou`` reprova em quatro casos;
  tirar o ``[[ "${tipo}" == "FAIL" ]]`` → reprova o ``error_do_mesh``; tirar o
  ``XPASS`` da conta → reprova o ``xpass_ao_lado``.
"""
from __future__ import annotations

import hashlib
import io
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path

import pytest

from tests.conftest import arvore_congelada

RAIZ_DO_REPO = Path(__file__).resolve().parents[2]
FIXTURE_DEVICE_C = RAIZ_DO_REPO / "tests" / "fixtures" / "bluez-5.86" / "device.c"
ALVO = "5.86-0ubuntu0.1~hefesto24.04.4"
RECEITA = RAIZ_DO_REPO / "docs" / "usage" / "receita-backport-bluez.md"

#: O que o preparo precisa na máquina. Nada disto é dependência de BUILD do
#: BlueZ: é o dpkg-dev que o CI já tem, o gcc e o cabeçalho do uhid.
_FERRAMENTAS = ("dpkg-source", "dpkg-parsechangelog", "patch", "gcc", "tar", "xz")


def _raiz() -> Path:
    """A foto da árvore: o script e os assets que ele lê, congelados na sessão."""
    return arvore_congelada()


def _script() -> Path:
    return _raiz() / "scripts" / "construir_bluez_backport.sh"


def _assets() -> Path:
    return _raiz() / "assets" / "bluez-backport"


def _baseline(caminho: Path | None = None) -> dict[str, str]:
    valores: dict[str, str] = {}
    arquivo = caminho if caminho is not None else _assets() / "BASELINE"
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        valores[chave] = valor
    return valores


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _faltam_ferramentas() -> list[str]:
    faltam = [f for f in _FERRAMENTAS if shutil.which(f) is None]
    if not Path("/usr/include/linux/uhid.h").is_file():
        faltam.append("linux/uhid.h")
    return faltam


precisa_das_ferramentas = pytest.mark.skipif(
    bool(_faltam_ferramentas()),
    reason=f"faltam na máquina: {', '.join(_faltam_ferramentas())}",
)


def _aplicar(device_c: Path, patches: list[str]) -> Path:
    """Aplica a série sobre uma cópia, com fuzz zero, como o dpkg-source faz."""
    raiz = device_c.parent.parent.parent
    for nome in patches:
        proc = subprocess.run(
            ["patch", "-p1", "-F", "0", "-N", "-s"],
            cwd=raiz,
            input=(_assets() / "patches" / nome).read_bytes(),
            capture_output=True,
            timeout=30,
        )
        assert proc.returncode == 0, (
            f"{nome} não aplica com fuzz zero: {proc.stdout!r} {proc.stderr!r}"
        )
    return device_c


def _arvore_do_fixture(tmp_path: Path) -> Path:
    alvo = tmp_path / "fonte" / "profiles" / "input" / "device.c"
    alvo.parent.mkdir(parents=True)
    shutil.copyfile(FIXTURE_DEVICE_C, alvo)
    return alvo


def _cenarios(saida: str) -> dict[str, dict[str, str]]:
    cenarios: dict[str, dict[str, str]] = {}
    for linha in saida.splitlines():
        campos = dict(re.findall(r'(\w+)=("[^"]*"|\S+)', linha))
        if "cenario" in campos:
            cenarios[campos["cenario"]] = campos
    return cenarios


def _morder(device_c: Path) -> dict[str, dict[str, str]]:
    proc = subprocess.run(
        ["bash", str(_script()), "--mordida", str(device_c)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert proc.returncode == 0, proc.stderr
    return _cenarios(proc.stdout)


# ---------------------------------------------------------------------------
# a versão alvo e a série
# ---------------------------------------------------------------------------


def test_a_versao_alvo_e_a_quatro():
    base = _baseline()
    assert f"{base['VERSAO_BASE']}~hefesto24.04.{base['REVISAO_ULTIMA']}" == ALVO
    assert base["PATCHES_R4"].split() == [
        "hefesto-0001-input-keep-bond-on-virtual-cable-unplug.patch",
        "hefesto-0002-input-drop-report-on-eagain.patch",
    ]
    for nome in base["PATCHES_R4"].split():
        assert (_assets() / "patches" / nome).is_file(), nome
    primeira = (_assets() / "debian" / "changelog.hefesto").read_text(
        encoding="utf-8"
    ).splitlines()[0]
    assert primeira.startswith(f"bluez ({ALVO}) noble;"), (
        f"o changelog.hefesto não abre com a versão alvo: {primeira!r}"
    )


def test_o_fixture_e_o_device_c_do_tarball():
    """O vanilla é o do tarball fixado; sem isto as outras réguas medem outra coisa."""
    assert _sha(FIXTURE_DEVICE_C) == _baseline()["SHA256_DEVICE_C_VANILLA"]


@precisa_das_ferramentas
@pytest.mark.parametrize("numero_da_revisao", ["3", "4"])
def test_o_patch_aplica_com_fuzz_zero_e_da_o_hash_do_baseline(tmp_path, numero_da_revisao):
    base = _baseline()
    device_c = _aplicar(_arvore_do_fixture(tmp_path), base[f"PATCHES_R{numero_da_revisao}"].split())
    assert _sha(device_c) == base[f"SHA256_DEVICE_C_R{numero_da_revisao}"], (
        f"a série da revisão {numero_da_revisao} aplicou, mas o device.c não é o que o "
        "BASELINE fixa — o patch mudou sem o BASELINE acompanhar"
    )


# ---------------------------------------------------------------------------
# a mordida do hefesto-0002
# ---------------------------------------------------------------------------


@precisa_das_ferramentas
def test_a_mordida_o_vanilla_destroi_no_eagain(tmp_path):
    """Sem isto, a régua de baixo não mede o defeito: mediria um socket que não enche."""
    cenarios = _morder(_arvore_do_fixture(tmp_path))
    assert int(cenarios["eagain"]["destruido"]) > 0
    assert int(cenarios["set_report_eagain"]["destruido"]) > 0
    assert int(cenarios["get_report_eagain"]["destruido"]) > 0


@precisa_das_ferramentas
def test_a_mordida_o_patchado_fica_no_eagain(tmp_path):
    base = _baseline()
    device_c = _aplicar(_arvore_do_fixture(tmp_path), base["PATCHES_R4"].split())
    cenarios = _morder(device_c)

    eagain = cenarios["eagain"]
    assert eagain["destruido"] == "0", f"o EAGAIN ainda destrói o aparelho: {eagain}"
    assert eagain["descartados"] == "1001", eagain
    # Mil descartes no mesmo segundo e um no seguinte: duas linhas, não 1001.
    assert eagain["linhas"] == "2", f"o log não tem limite de taxa: {eagain}"
    assert eagain["ultima_linha"].startswith('"BT socket write error: '), (
        "o prefixo de sempre sumiu, e quem lê o journal deixa de casar a linha"
    )
    for nome in ("set_report_eagain", "get_report_eagain"):
        assert cenarios[nome]["destruido"] == "0", cenarios[nome]
        # O kernel ainda recebe a resposta de erro daquele pedido.
        assert cenarios[nome]["respostas_de_erro"] == "1", cenarios[nome]


@precisa_das_ferramentas
@pytest.mark.parametrize("cenario", ["epipe", "enotconn", "sem_canal"])
def test_a_mordida_erro_terminal_derruba_com_o_patch(tmp_path, cenario):
    base = _baseline()
    device_c = _aplicar(_arvore_do_fixture(tmp_path), base["PATCHES_R4"].split())
    assert _morder(device_c)[cenario]["destruido"] == "1"


# ---------------------------------------------------------------------------
# o script: reproduzível, idempotente, sem rede na bancada e sem instalar
# ---------------------------------------------------------------------------


def _tar_xz(destino: Path, arquivos: dict[str, bytes]) -> None:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(destino, "w:xz") as tar:
        for nome, conteudo in sorted(arquivos.items()):
            info = tarfile.TarInfo(nome)
            info.size = len(conteudo)
            info.mode = 0o644
            info.mtime = 0
            tar.addfile(info, io.BytesIO(conteudo))


_CONTROL = b"""Source: bluez
Section: admin
Priority: optional
Maintainer: Bancada <bancada@example.invalid>
Standards-Version: 4.6.0

Package: bluez
Architecture: any
Description: bancada do backport
 fonte sintetica para o teste do preparo
"""

_CHANGELOG_RESOLUTE = b"""bluez (5.85-4ubuntu0.1) resolute; urgency=medium

  * bancada: o empacotamento de onde o backport parte.

 -- Bancada <bancada@example.invalid>  Mon, 22 Jun 2026 17:52:31 +0800
"""


@pytest.fixture
def bancada(tmp_path):
    """Um cache com as duas fontes JÁ baixadas, com os nomes do BASELINE.

    O upstream sintético traz só o ``device.c`` do tarball (o fixture); o
    empacotamento traz o mínimo que o ``dpkg-source`` e os três ajustes do
    script exigem. O ``BASELINE`` é o real com os dois hashes de fonte
    trocados — os do ``device.c`` continuam os de verdade.
    """
    base_real = (_assets() / "BASELINE").read_text(encoding="utf-8")
    base = _baseline()
    cache = tmp_path / "cache"
    fontes = cache / "bluez-fontes"
    upstream = fontes / base["FONTE_UPSTREAM_URL"].rsplit("/", 1)[1]
    empacotamento = fontes / base["EMPACOTAMENTO_URL"].rsplit("/", 1)[1]
    raiz_up = f"bluez-{base['VERSAO_UPSTREAM']}"
    _tar_xz(upstream, {f"{raiz_up}/profiles/input/device.c": FIXTURE_DEVICE_C.read_bytes()})
    _tar_xz(
        empacotamento,
        {
            "debian/source/format": b"3.0 (quilt)\n",
            "debian/control": _CONTROL,
            "debian/changelog": _CHANGELOG_RESOLUTE,
            "debian/patches/series": (
                b"0013-transport-Fix-set-volume-failure-with-invalid-device.patch\n"
            ),
            "debian/bluez.manpages": b"usr/share/man/man1/btmgmt.1\n",
        },
    )
    baseline = tmp_path / "BASELINE"
    baseline.write_text(
        base_real.replace(base["FONTE_UPSTREAM_SHA256"], _sha(upstream)).replace(
            base["EMPACOTAMENTO_SHA256"], _sha(empacotamento)
        ),
        encoding="utf-8",
    )

    # Um curl que, se chamado, deixa a marca e falha: a bancada nunca vai à rede.
    binarios = tmp_path / "bin"
    binarios.mkdir()
    marca_curl = tmp_path / "curl-foi-chamado"
    curl = binarios / "curl"
    curl.write_text(f'#!/bin/sh\necho "$@" >> "{marca_curl}"\nexit 99\n', encoding="utf-8")
    curl.chmod(0o755)

    env = dict(os.environ)
    env["PATH"] = f"{binarios}{os.pathsep}{env.get('PATH', '')}"
    env["HEFESTO_BLUEZ_CACHE"] = str(cache)
    env["HEFESTO_BLUEZ_BASELINE"] = str(baseline)
    env["LC_ALL"] = "C.UTF-8"
    return {
        "cache": cache,
        "env": env,
        "marca_curl": marca_curl,
        "arvore": cache / "bluez-obra" / raiz_up,
        "saida": cache / "bluez-backport",
    }


def _rodar(bancada: dict, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(_script()), *args],
        env=bancada["env"],
        capture_output=True,
        text=True,
        timeout=180,
    )


def _retrato(arvore: Path) -> dict[str, str]:
    return {
        str(p.relative_to(arvore)): _sha(p)
        for p in sorted(arvore.rglob("*"))
        if p.is_file() and not p.is_symlink()
    }


@precisa_das_ferramentas
def test_o_preparo_monta_a_arvore_da_versao_alvo(bancada):
    proc = _rodar(bancada, "--preparar")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"árvore pronta: {bancada['arvore']} ({ALVO})" in proc.stdout
    assert "mordida: o vanilla destrói no EAGAIN, o patchado fica" in proc.stdout
    assert not bancada["marca_curl"].exists(), "o preparo foi à rede com as fontes no cache"

    arvore = bancada["arvore"]
    versao = subprocess.run(
        ["dpkg-parsechangelog", "-l", str(arvore / "debian" / "changelog"), "-S", "Version"],
        capture_output=True,
        text=True,
        timeout=30,
    ).stdout.strip()
    assert versao == ALVO
    series = (arvore / "debian" / "patches" / "series").read_text(encoding="utf-8").split()
    assert "0013-transport-Fix-set-volume-failure-with-invalid-device.patch" not in series
    assert series[-2:] == _baseline()["PATCHES_R4"].split()
    assert _sha(arvore / "profiles" / "input" / "device.c") == _baseline()["SHA256_DEVICE_C_R4"]
    # Sem esta ausência o dpkg-buildpackage desfaz a série ao terminar, e o
    # make check recompilaria o bluetoothd sem os patches.
    assert not (arvore / ".pc" / ".dpkg-source-unapply").exists()


@precisa_das_ferramentas
def test_duas_corridas_do_preparo_dao_a_mesma_arvore(bancada):
    primeira = _rodar(bancada, "--preparar")
    assert primeira.returncode == 0, primeira.stdout + primeira.stderr
    retrato = _retrato(bancada["arvore"])
    segunda = _rodar(bancada, "--preparar")
    assert segunda.returncode == 0, segunda.stdout + segunda.stderr
    assert _retrato(bancada["arvore"]) == retrato


def _origem(env: dict[str, str]) -> str:
    """O ORIGEM.txt que a última revisão escreve, lido do BASELINE da bancada."""
    base = _baseline(Path(env["HEFESTO_BLUEZ_BASELINE"]))
    linhas = [
        f"versao={ALVO}",
        f"upstream={base['FONTE_UPSTREAM_URL']} {base['FONTE_UPSTREAM_SHA256']}",
        f"empacotamento={base['EMPACOTAMENTO_URL']} {base['EMPACOTAMENTO_SHA256']}",
        *(
            f"patch={nome} {_sha(_assets() / 'patches' / nome)}"
            for nome in base["PATCHES_R4"].split()
        ),
        "construido_por=scripts/construir_bluez_backport.sh",
    ]
    return "\n".join(linhas) + "\n"


def _cache_pronto(bancada: dict) -> tuple[Path, str]:
    """A saída como o build a deixa: os três .deb, o SHA256SUMS e o ORIGEM.txt."""
    shutil.rmtree(bancada["cache"] / "bluez-fontes")
    saida = bancada["saida"]
    saida.mkdir(parents=True)
    arch = subprocess.run(
        ["dpkg", "--print-architecture"], capture_output=True, text=True, timeout=30
    ).stdout.strip()
    linhas = []
    for pacote in ("libbluetooth3", "bluez", "bluez-cups"):
        deb = saida / f"{pacote}_{ALVO}_{arch}.deb"
        deb.write_bytes(f"deb de mentira de {pacote}\n".encode())
        linhas.append(f"{_sha(deb)}  {deb.name}\n")
    (saida / "SHA256SUMS").write_text("".join(linhas), encoding="utf-8")
    (saida / "ORIGEM.txt").write_text(_origem(bancada["env"]), encoding="utf-8")
    return saida, arch


@precisa_das_ferramentas
@pytest.mark.parametrize("como_envelheceu", ["patch_mudou", "sem_origem"])
def test_debs_feitos_com_outro_patch_mandam_reconstruir(bancada, como_envelheceu):
    """O atalho pergunta também COM O QUE os .deb foram feitos.

    Medido em 23/09/2026: com o ORIGEM.txt dizendo outro hefesto-0002 (ou sem
    ORIGEM.txt nenhum), o script respondia «já construído» — um patch mudado
    sem subir a revisão deixava o .deb velho no cache que o install lê.
    """
    saida, _ = _cache_pronto(bancada)
    origem = saida / "ORIGEM.txt"
    if como_envelheceu == "patch_mudou":
        texto = origem.read_text(encoding="utf-8")
        velho = re.sub(
            r"^(patch=hefesto-0002-\S+) [0-9a-f]{64}$",
            r"\1 " + "0" * 64,
            texto,
            flags=re.M,
        )
        assert velho != texto
        origem.write_text(velho, encoding="utf-8")
    else:
        origem.unlink()

    proc = _rodar(bancada)
    assert "já construído" not in proc.stdout
    # A reconstrução começa pela rede, que aqui é o curl de mentira.
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert bancada["marca_curl"].exists()


@precisa_das_ferramentas
def test_com_os_debs_no_cache_a_corrida_nao_baixa_nem_compila(bancada):
    saida, arch = _cache_pronto(bancada)

    proc = _rodar(bancada)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "já construído" in proc.stdout
    assert not bancada["marca_curl"].exists()
    assert not (bancada["cache"] / "bluez-obra").exists()

    # E o atalho não é cego: um .deb que não confere manda reconstruir — e a
    # reconstrução começa pela rede, que aqui é o curl de mentira.
    (saida / f"bluez_{ALVO}_{arch}.deb").write_bytes(b"adulterado\n")
    proc = _rodar(bancada)
    assert proc.returncode == 4, proc.stdout + proc.stderr
    assert bancada["marca_curl"].exists()


def _cache_do_install(env: dict[str, str]) -> Path:
    """O cache que o install.sh lê: fixo em ``$HOME``, sem variável nenhuma."""
    return Path(env["HOME"]) / ".cache" / "hefesto-dualsense4unix"


@precisa_das_ferramentas
@pytest.mark.parametrize(
    "como_aponta", ["sem_variavel", "o_caminho_escrito", "com_barra_dupla", "por_um_link"]
)
def test_revisao_antiga_so_se_reconstroi_fora_do_cache_do_install(bancada, tmp_path, como_aponta):
    """A guarda pergunta pelo LUGAR, não pela variável.

    Medido em 23/09/2026: ``HEFESTO_BLUEZ_CACHE`` escrito com o próprio caminho
    do install passava pela guarda, e o ``--revisao 3`` seguia para a obra — com
    as fontes no cache, o ``.3`` sobrescreveria o ``SHA256SUMS`` do ``.4``.
    """
    env = dict(bancada["env"])
    do_install = _cache_do_install(env)
    if como_aponta == "sem_variavel":
        del env["HEFESTO_BLUEZ_CACHE"]
    elif como_aponta == "o_caminho_escrito":
        env["HEFESTO_BLUEZ_CACHE"] = str(do_install)
    elif como_aponta == "com_barra_dupla":
        env["HEFESTO_BLUEZ_CACHE"] = f"{env['HOME']}//.cache/hefesto-dualsense4unix/"
    else:
        do_install.mkdir(parents=True, exist_ok=True)
        link = tmp_path / "atalho-para-o-cache"
        link.symlink_to(do_install)
        env["HEFESTO_BLUEZ_CACHE"] = str(link)
    proc = subprocess.run(
        ["bash", str(_script()), "--revisao", "3", "--preparar"],
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "HEFESTO_BLUEZ_CACHE" in proc.stderr
    assert not bancada["marca_curl"].exists(), "passou pela guarda e foi buscar a fonte"
    assert not (do_install / "bluez-obra").exists()


@precisa_das_ferramentas
@pytest.mark.parametrize("jobs", ["0", "quatro", "-2", ""])
def test_numero_de_processos_invalido_para_antes_de_baixar(bancada, jobs):
    env = dict(bancada["env"])
    env["HEFESTO_BLUEZ_JOBS"] = jobs
    shutil.rmtree(bancada["cache"] / "bluez-fontes")
    proc = subprocess.run(
        ["bash", str(_script())], env=env, capture_output=True, text=True, timeout=60
    )
    if jobs == "":
        # Vazio é o padrão: um processo por núcleo. Segue, e a rede é o curl de mentira.
        assert proc.returncode == 4, proc.stdout + proc.stderr
        return
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "HEFESTO_BLUEZ_JOBS" in proc.stderr
    assert not bancada["marca_curl"].exists()


@precisa_das_ferramentas
def test_revisao_antiga_fora_do_cache_do_install_monta_a_arvore_da_tres(bancada):
    """O outro lado da guarda: num cache à parte, o ``.3`` se reconstrói."""
    proc = _rodar(bancada, "--revisao", "3", "--preparar")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert f"árvore pronta: {bancada['arvore']} (5.86-0ubuntu0.1~hefesto24.04.3)" in proc.stdout
    assert "sem mordida a provar" in proc.stdout
    device_c = bancada["arvore"] / "profiles" / "input" / "device.c"
    assert _sha(device_c) == _baseline()["SHA256_DEVICE_C_R3"]


def _perdoa(tmp_path: Path, teste: str, *, aead_disponivel: bool) -> bool:
    """Roda a `falha_explicada_pela_maquina` do script com um python3 de mentira.

    O python3 de mentira responde a pergunta da AF_ALG: sai 0 quando o AEAD do
    kernel está disponível, 1 quando não. Nada é compilado.
    """
    binarios = tmp_path / f"bin-{int(aead_disponivel)}"
    binarios.mkdir(exist_ok=True)
    python3 = binarios / "python3"
    python3.write_text(f"#!/bin/sh\nexit {0 if aead_disponivel else 1}\n", encoding="utf-8")
    python3.chmod(0o755)
    programa = (
        "set -u\n"
        f"eval \"$(sed -n '/^aead_do_kernel_disponivel() {{/,/^}}/p; "
        f"/^falha_explicada_pela_maquina() {{/,/^}}/p' '{_script()}')\"\n"
        f"falha_explicada_pela_maquina '{teste}'\n"
    )
    env = dict(os.environ)
    env["PATH"] = f"{binarios}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(
        ["bash", "-c", programa], env=env, capture_output=True, text=True, timeout=30
    )
    assert proc.returncode in (0, 1), proc.stderr
    return proc.returncode == 0


def test_o_unit_do_bluez_so_perdoa_a_falha_que_a_maquina_explica(tmp_path):
    """O test-mesh-crypto só é perdoado com o AEAD do kernel medido AUSENTE.

    Medido em 23/09/2026: a máquina dela desliga o algif_aead (CVE-2026-31431)
    e o test-mesh-crypto reprova ali, sem ligar nada de profiles/input. Um
    perdão incondicional esconderia a mesma falha numa máquina onde ela é do
    código; um perdão por nome deixaria passar qualquer outro teste.
    """
    assert _perdoa(tmp_path, "unit/test-mesh-crypto", aead_disponivel=False)
    assert not _perdoa(tmp_path, "unit/test-mesh-crypto", aead_disponivel=True)
    assert not _perdoa(tmp_path, "unit/test-hog", aead_disponivel=False)


def _script_sem_main(tmp_path: Path) -> Path:
    """O script inteiro, sem a última linha — as funções DE VERDADE, e nada roda.

    Recortar função por função com ``sed`` por faixas duplica linhas quando uma
    função cabe numa linha só (a ``diga``): a ``morra`` virava uma função
    aninhada que não saía, e o dublê respondia verde sobre o próprio defeito.
    """
    linhas = _script().read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert linhas[-1] == 'main "$@"', (
        f"a última linha do script mudou ({linhas[-1]!r}): carregá-lo rodaria o build"
    )
    destino = tmp_path / "construir_sem_main.sh"
    destino.write_text("\n".join(linhas[:-1]) + "\n", encoding="utf-8")
    return destino


_CABECALHO_DO_LOG = """==================================
   bluez 5.86: ./test-suite.log
==================================

# TOTAL: 38

.. contents:: :depth: 2

"""


def _secao(resultado: str, teste: str) -> str:
    return f"{resultado}: {teste}\n{'=' * (len(resultado) + len(teste) + 2)}\n\nsaída do teste\n\n"


@pytest.mark.parametrize(
    ("caso", "secoes", "aead_disponivel", "rc_do_make", "rc_esperado"),
    [
        ("so_o_mesh_sem_aead", [("FAIL", "unit/test-mesh-crypto")], False, 2, 0),
        ("tudo_passa", [], True, 0, 0),
        ("outro_fail", [("FAIL", "unit/test-mesh-crypto"), ("FAIL", "unit/test-hog")], False, 2, 8),
        ("mesh_com_aead", [("FAIL", "unit/test-mesh-crypto")], True, 2, 8),
        ("error_do_mesh", [("ERROR", "unit/test-mesh-crypto")], False, 2, 8),
        ("xpass_ao_lado", [("FAIL", "unit/test-mesh-crypto"), ("XPASS", "unit/test-x")], False, 2, 8),
        ("sem_log", None, False, 2, 8),
    ],
)
def test_o_laco_do_unit_so_deixa_passar_o_que_perdoou(
    tmp_path, caso, secoes, aead_disponivel, rc_do_make, rc_esperado
):
    """O ``unit_do_bluez`` inteiro, com um ``make`` de mentira.

    A régua de cima prova o PREDICADO; esta prova o LAÇO que o aplica — sem
    ela, trocar o ``morra`` do laço por ``continue`` perdoava qualquer teste
    reprovado e as dezesseis réguas continuavam verdes (medido em 23/09/2026).
    """
    arvore = tmp_path / "arvore"
    obra = tmp_path / "obra"
    binarios = tmp_path / "bin"
    for pasta in (arvore, obra, binarios):
        pasta.mkdir()
    log_sintetico = tmp_path / "test-suite.log"
    if secoes is not None:
        log_sintetico.write_text(
            _CABECALHO_DO_LOG + "".join(_secao(r, t) for r, t in secoes), encoding="utf-8"
        )
    make = binarios / "make"
    make.write_text(
        f"#!/bin/sh\n[ -f '{log_sintetico}' ] && cp '{log_sintetico}' test-suite.log\n"
        f"exit {rc_do_make}\n",
        encoding="utf-8",
    )
    python3 = binarios / "python3"
    python3.write_text(f"#!/bin/sh\nexit {0 if aead_disponivel else 1}\n", encoding="utf-8")
    for exe in (make, python3):
        exe.chmod(0o755)
    programa = (
        f"source '{_script_sem_main(tmp_path)}'\n"
        f"ARVORE='{arvore}'; OBRA='{obra}'; JOBS=1; AMBIENTE_LIMPO=()\n"
        "unit_do_bluez\n"
    )
    env = dict(os.environ)
    env["PATH"] = f"{binarios}{os.pathsep}{env.get('PATH', '')}"
    proc = subprocess.run(
        ["bash", "-c", programa], env=env, capture_output=True, text=True, timeout=30
    )
    assert proc.returncode == rc_esperado, f"{caso}: {proc.stdout}{proc.stderr}"
    if caso == "so_o_mesh_sem_aead":
        assert "NÃO MEDIDO nesta máquina: unit/test-mesh-crypto" in proc.stdout


def _sem_texto_entre_aspas(linha: str) -> str:
    return re.sub(r"'[^']*'|\"[^\"]*\"", "''", linha)


#: Uma linha que só IMPRIME texto para quem lê (o conselho do mk-build-deps
#: com sudo, por exemplo) — e não encadeia comando nenhum depois.
_SO_MENSAGEM = re.compile(r"^\s*(diga|morra|printf|echo)\b")
_ENCADEIA = re.compile(r"\||;|&&|\$\(|`")


def test_o_script_nao_instala_nada():
    """O postinst do bluez reinicia o bluetoothd: instalar é do install.sh.

    O texto entre aspas CONTA, fora das linhas que só imprimem: medido em
    23/09/2026, a régua anterior apagava tudo o que estava entre aspas antes de
    procurar, e ``bash -c "sudo apt-get install -y bluez"`` passava verde.
    """
    proibidos = re.compile(
        r"\bsudo\b|\bpkexec\b|\bdoas\b|\bsystemctl\b|\bapt-get\b"
        r"|\bapt\s+(install|remove|purge)\b|\bmk-build-deps\b"
        r"|\bdpkg\s+(-i|--install|--unpack|-r|--remove|-P|--purge)\b"
    )
    achados = []
    for numero, linha in enumerate(_script().read_text(encoding="utf-8").splitlines(), 1):
        if linha.lstrip().startswith("#"):
            continue
        nua = _sem_texto_entre_aspas(linha)
        if _SO_MENSAGEM.match(nua) and not _ENCADEIA.search(nua):
            continue
        if proibidos.search(linha):
            achados.append(f"{numero}: {linha.strip()}")
    assert not achados, f"o script de build executa instalação: {achados}"


def test_a_receita_diz_como_construir_e_o_que_cada_patch_faz():
    texto = RECEITA.read_text(encoding="utf-8")
    assert "scripts/construir_bluez_backport.sh" in texto
    for nome in _baseline()["PATCHES_R4"].split():
        assert nome in texto, f"a receita não explica o {nome}"
    assert ALVO in texto
