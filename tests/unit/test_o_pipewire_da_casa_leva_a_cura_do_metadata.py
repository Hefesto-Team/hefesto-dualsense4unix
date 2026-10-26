"""O PipeWire da casa leva a cura do metadata, e o doctor diz quando falta.

O-PIPEWIRE-DA-CASA-LEVA-A-CURA-DO-METADATA-01 (15/10/2026). Até a 1.6.8, o
cliente que faz bind num metadata enquanto o WirePlumber sai fica preso para
sempre, e a Steam não fecha (``docs/protocol/o-wpctl-pendurado-pelo-metadata.md``).
A receita da casa é a 1.6.9 do upstream com o ``debian/`` do Pop!_OS
(``assets/pipewire-backport/``, ``scripts/construir_pipewire_backport.sh``).

Nada aqui baixa, compila ou instala: o ``BASELINE`` se confere contra o que foi
medido, a pergunta da cura roda sobre um ``metadata.c`` de mentira, e o doctor
roda com um ``dpkg-query`` de mentira no PATH.
"""

from __future__ import annotations

import hashlib
import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / "assets" / "pipewire-backport"
BASELINE = ASSETS / "BASELINE"
SCRIPT = ROOT / "scripts" / "construir_pipewire_backport.sh"
DOCTOR = ROOT / "scripts" / "doctor.sh"

MEDIDOS = {
    "PW_FONTE_SHA256": "0cde58c124825bad462b32ab79f9aa286ee7b113cc73a5cda923a4365e752657",
    "PW_EMPACOTAMENTO_SHA256": "5f19cae7f9ad7e6c1206ff7d7f197f71feec97e1919016a5a82eab50a82f405f",
    "WP_FONTE_SHA256": "0c2ea30a7b3bb4ecad456bb27e2c283defda59bb53d97df6917a495f12887e33",
    "WP_EMPACOTAMENTO_SHA256": "5fdff117f1dea4297383a3fe4c5441f9bba58f65990f9e5dc68d6cf39f204dc5",
    "PW_TAG_COMMIT": "8fa27cabdc6c0c1350c69c026af5850ef0af1e26",
    "WP_TAG_COMMIT": "81606cbb32d29df20147d1b68b662c1082654d81",
}

UNBIND_169 = """\
static void global_unbind(void *data)
{
\tstruct resource_data *d = data;
\tremove_pending(d);
\tif (d->resource) {
\t        spa_hook_remove(&d->resource_listener);
\t}
}
"""
UNBIND_168 = UNBIND_169.replace("\tremove_pending(d);\n", "")
REMOVE_PENDING = """\
static void remove_pending(struct resource_data *d)
{
\tif (d->pong_seq != 0) {
\t\tpw_impl_client_set_busy(pw_resource_get_client(d->resource), false);
\t}
}

"""

PW_DO_POP = "1.6.8-1pop1~1787688714~24.04~fdff050"


def _baseline() -> dict[str, str]:
    valores: dict[str, str] = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        if linha and not linha.startswith("#") and "=" in linha:
            chave, valor = linha.split("=", 1)
            valores[chave] = valor
    return valores


def _sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def _entrada(changelog: Path) -> tuple[str, dict[str, str]]:
    """A versão da primeira entrada e as linhas que se leem por máquina."""
    linhas = changelog.read_text(encoding="utf-8").splitlines()
    versao = linhas[0].split("(", 1)[1].split(")", 1)[0]
    campos = {}
    for linha in linhas:
        texto = linha.strip().removeprefix("* ")
        for chave in ("Upstream", "Empacotamento"):
            if texto.startswith(f"{chave}: "):
                campos[chave] = texto.split(": ", 1)[1]
    return versao, campos


class TestOBaseline:
    def test_os_hashes_das_fontes_sao_os_medidos(self) -> None:
        valores = _baseline()
        for chave, medido in MEDIDOS.items():
            assert valores[chave] == medido, chave

    def test_as_urls_sao_das_versoes_do_baseline(self) -> None:
        v = _baseline()
        assert v["PW_FONTE_URL"].endswith(
            f"/{v['PW_VERSAO_UPSTREAM']}/pipewire-{v['PW_VERSAO_UPSTREAM']}.tar.bz2"
        )
        assert v["WP_FONTE_URL"].endswith(
            f"/{v['WP_VERSAO_UPSTREAM']}/wireplumber-{v['WP_VERSAO_UPSTREAM']}.tar.bz2"
        )
        assert v["PW_EMPACOTAMENTO_URL"].endswith(
            f"/pipewire_{v['PW_EMPACOTAMENTO_VERSAO']}.tar.xz"
        )
        assert v["WP_EMPACOTAMENTO_URL"].endswith(
            f"/wireplumber_{v['WP_EMPACOTAMENTO_VERSAO']}.tar.xz"
        )

    def test_a_versao_alvo_tem_a_cura(self) -> None:
        v = _baseline()
        alvo = tuple(int(x) for x in v["PW_VERSAO_UPSTREAM"].split("."))
        assert alvo >= (1, 6, 9)
        assert v["PW_REVISAO"].startswith(f"{v['PW_VERSAO_UPSTREAM']}-0~hefesto24.04.")
        assert v["WP_REVISAO"].startswith(f"{v['WP_VERSAO_UPSTREAM']}-0~hefesto24.04.")

    def test_cada_patch_da_serie_confere_pelo_hash(self) -> None:
        v = _baseline()
        serie = v["PW_PATCHES"].split()
        assert serie, "a série do PipeWire está vazia"
        for nome in serie:
            arquivo = ASSETS / "patches" / nome
            assert arquivo.is_file(), nome
            assert _sha(arquivo) == v[f"PATCH_{nome}"], nome
        presentes = {p.name for p in (ASSETS / "patches").iterdir()}
        assert presentes == set(serie), "patch no diretório sem estar na série, ou o contrário"

    def test_a_versao_e_a_do_upstream_e_nao_a_do_pop(self) -> None:
        """D-1510-A-VERSAO-MAIS-RECENTE-DE-TUDO: o alvo é a tag do upstream, o Pop dá o debian/."""
        v = _baseline()
        assert v["PW_VERSAO_UPSTREAM"] != v["PW_EMPACOTAMENTO_VERSAO"].split("-")[0]
        assert v["WP_VERSAO_UPSTREAM"] != v["WP_EMPACOTAMENTO_VERSAO"].split("-")[0]
        assert "/archive/" in v["PW_FONTE_URL"] and "/archive/" in v["WP_FONTE_URL"]

    def test_o_cve_do_debian_vai_na_serie(self) -> None:
        """D-1510-O-PIPEWIRE-DA-CASA-LEVA-O-CVE-DO-DEBIAN: a correção que o Debian leva entra."""
        assert "debian-0001-CVE-2026-14330.patch" in _baseline()["PW_PATCHES"].split()

    def test_o_libcamera_sai_do_build_e_dos_pacotes(self) -> None:
        """D-1510-O-PIPEWIRE-DA-CASA-SEM-LIBCAMERA: o noble tem a 0.2.0, a 1.6.9 pede a 0.6.0."""
        texto = SCRIPT.read_text(encoding="utf-8")
        assert "-Dlibcamera=disabled" in texto
        assert "libspa-0\\.2-libcamera|pipewire-libcamera" in texto

    def test_as_duas_obras_pedem_o_mesmo_meson(self) -> None:
        """O meson-1.5 e o meson-1.7 do noble conflitam: o WirePlumber vai ao do PipeWire."""
        texto = SCRIPT.read_text(encoding="utf-8")
        assert "s/^([[:space:]]+)meson-1\\.5,$/\\1meson-1.7,/" in texto

    def test_os_simbolos_novos_conferem_pelo_hash(self) -> None:
        novos = ASSETS / "debian" / "libwireplumber-0.5-0.symbols.novos"
        assert _sha(novos) == _baseline()["WP_SIMBOLOS_NOVOS_SHA256"]
        linhas = novos.read_text(encoding="utf-8").splitlines()
        assert linhas and all(
            linha.startswith(" wp_") and "@Base 0.5." in linha for linha in linhas
        )

    def test_o_tarball_no_cache_confere_quando_existe(self) -> None:
        cache = os.environ.get("HEFESTO_PIPEWIRE_CACHE")
        if not cache:
            pytest.skip("sem HEFESTO_PIPEWIRE_CACHE: o tarball não foi baixado aqui")
        v = _baseline()
        for chave in ("PW", "WP"):
            tarball = Path(cache) / "pipewire-fontes" / v[f"{chave}_FONTE_URL"].rsplit("/", 1)[1]
            if tarball.is_file():
                assert _sha(tarball) == v[f"{chave}_FONTE_SHA256"]


class TestOChangelog:
    @pytest.mark.parametrize("prefixo,nome", [("PW", "pipewire"), ("WP", "wireplumber")])
    def test_a_revisao_e_as_origens_sao_as_do_baseline(self, prefixo: str, nome: str) -> None:
        v = _baseline()
        versao, campos = _entrada(ASSETS / "debian" / f"changelog.{nome}.hefesto")
        assert versao == v[f"{prefixo}_REVISAO"]
        assert (
            campos["Upstream"] == f"{v[f'{prefixo}_VERSAO_UPSTREAM']} {v[f'{prefixo}_TAG_COMMIT']}"
        )
        assert campos["Empacotamento"] == v[f"{prefixo}_EMPACOTAMENTO_VERSAO"]


class TestACura:
    def _conferir(self, tmp_path: Path, unbind: str) -> subprocess.CompletedProcess[str]:
        metadata = tmp_path / "metadata.c"
        metadata.write_text(REMOVE_PENDING + unbind, encoding="utf-8")
        return subprocess.run(
            ["bash", str(SCRIPT), "--conferir-metadata", str(metadata)],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def test_o_global_unbind_da_169_chama_o_remove_pending(self, tmp_path: Path) -> None:
        res = self._conferir(tmp_path, UNBIND_169)
        assert res.returncode == 0, res.stderr

    def test_o_da_168_reprova(self, tmp_path: Path) -> None:
        res = self._conferir(tmp_path, UNBIND_168)
        assert res.returncode == 6
        assert "sem a cura do metadata" in res.stderr

    def test_o_remove_pending_fora_do_global_unbind_nao_conta(self, tmp_path: Path) -> None:
        res = self._conferir(
            tmp_path, UNBIND_168 + "\nstatic void outra(void)\n{\n\tremove_pending(d);\n}\n"
        )
        assert res.returncode == 6


def _bin(pasta: Path, nome: str, corpo: str) -> None:
    alvo = pasta / nome
    alvo.write_text(f"#!/usr/bin/env bash\n{corpo}\n", encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)


def _doctor(tmp_path: Path, pipewire: str, wireplumber: str = "", binario: str = "") -> str:
    fake = tmp_path / "fakebin"
    fake.mkdir(exist_ok=True)
    _bin(fake, "pipewire", f'printf "%s\\n" "{binario}"' if binario else "exit 1")
    _bin(
        fake,
        "dpkg-query",
        'case "$*" in\n'
        f'  *libpipewire-0.3-modules*) printf "%s" "{pipewire}" ;;\n'
        f'  *wireplumber*) printf "%s" "{wireplumber}" ;;\n'
        "  *) exit 1 ;;\n"
        "esac",
    )
    res = subprocess.run(
        ["bash", "-c", 'set --; source "$DOCTOR_SH"; check_pipewire_cura_do_metadata; true'],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
        env={"PATH": f"{fake}:/usr/bin:/bin", "DOCTOR_SH": str(DOCTOR), "HOME": str(tmp_path)},
    )
    assert res.returncode == 0, res.stderr
    return res.stdout


class TestODoctor:
    def test_o_do_pop_avisa_e_aponta_a_receita(self, tmp_path: Path) -> None:
        saida = _doctor(tmp_path, PW_DO_POP, "0.5.12-2pop1~1766191027~24.04~d4bf441")
        assert saida.startswith("[WARN]"), saida
        assert "a Steam não fecha" in saida
        assert "receita-backport-pipewire.md" in saida
        assert "o da distro" in saida

    @pytest.mark.parametrize("numero", ["1.6.9-0~hefesto24.04.1", "1.6.9", "1.7.0", "1:1.6.10-1"])
    def test_da_169_em_diante_passa(self, tmp_path: Path, numero: str) -> None:
        saida = _doctor(tmp_path, numero, "0.5.18-0~hefesto24.04.1")
        assert saida.startswith("[ OK ]"), saida
        assert "o WirePlumber é o 0.5.18-0~hefesto24.04.1, o da casa" in saida

    def test_sem_pipewire_nao_avisa(self, tmp_path: Path) -> None:
        saida = _doctor(tmp_path, "")
        assert "[WARN]" not in saida
        assert "não achei o PipeWire" in saida

    def test_fora_do_dpkg_pergunta_ao_binario(self, tmp_path: Path) -> None:
        texto = "pipewire\nCompiled with libpipewire 1.6.8\nLinked with libpipewire 1.6.8"
        saida = _doctor(tmp_path, "", binario=texto)
        assert saida.startswith("[WARN] o PipeWire 1.6.8 não tem a cura"), saida

    def test_o_check_roda_no_bloco_do_audio(self) -> None:
        """A linha do PipeWire sai sob o cabeçalho do som, não sob o do rádio."""
        linhas = DOCTOR.read_text(encoding="utf-8").splitlines()
        alvo = "    check_pipewire_cura_do_metadata"
        chamadas = [n for n, linha in enumerate(linhas) if linha == alvo]
        assert len(chamadas) == 1, chamadas
        cabecalhos = [
            (n, linha.strip())
            for n, linha in enumerate(linhas)
            if linha.startswith("    hdr ") and n < chamadas[0]
        ]
        assert cabecalhos and cabecalhos[-1][1] == 'hdr "áudio (microfone)"', cabecalhos[-1:]
