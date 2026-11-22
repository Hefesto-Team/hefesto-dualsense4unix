"""O aviso da captura de tela só aparece se a distribuição não trouxe a correção.

O-AVISO-DA-CAPTURA-DE-TELA-SO-APARECE-SE-A-DISTRIBUICAO-NAO-TROUXE-A-CORRECAO-01 (21/11/2026).
O ``BASELINE`` do portal guarda o piso ``PORTAL_DE_CIMA_COM_A_CURA``: a menor versão de cima que o
construtor já conferiu trazendo o cosmic-protocols#92. Versão de cima igual ou maior, na ordem do
``dpkg --compare-versions``, vale sem lista nenhuma; o serviço e o doctor concordam. Nada aqui toca
o ``/etc`` nem o ``/var/lib``: o dpkg-query é de mentira, o ``dpkg --compare-versions`` é o de
verdade (só compara texto) e o HOME é um lar de mentira.
"""

from __future__ import annotations

import shutil
import stat
import subprocess
from collections.abc import Sequence
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import curas_da_casa as cc

BASH = shutil.which("bash") or "/bin/bash"
DPKG = shutil.which("dpkg")
RAIZ = Path(__file__).resolve().parents[2]
BASELINE = RAIZ / "assets" / "portal-cosmic-backport" / "BASELINE"
DOCTOR = RAIZ / "scripts" / "doctor.sh"

pytestmark = pytest.mark.skipif(DPKG is None, reason="sem dpkg para comparar versões")

CHAVE = "PORTAL_DE_CIMA_COM_A_CURA"
PACOTE = "xdg-desktop-portal-cosmic"


def _campos() -> dict[str, str]:
    campos: dict[str, str] = {}
    for linha in BASELINE.read_text(encoding="utf-8").splitlines():
        chave, _, valor = linha.partition("=")
        campos.setdefault(chave, valor)
    return campos


BASE = _campos()
PISO = BASE.get(CHAVE, "1.11.0~1795035856~24.04~7b0864c")
SUFIXO = BASE["SUFIXO"]
MAIOR = "1.11.0~1795035857~24.04~aaaaaaa"
MAIS_NOVA = "1.12.0~1799000000~24.04~bbbbbbb"
MENOR = "1.11.0~1792525517~24.04~f448ddf"
SEM_A_MARCA = b"\x7fELF portal da distribuicao, sem a marca da casa"

CASOS = {
    "a_igual_ao_piso_com_a_preferencia": (PISO, True, cc.VALE),
    "b_maior_com_a_preferencia": (MAIOR, True, cc.VALE),
    "b_de_uma_serie_nova_com_a_preferencia": (MAIS_NOVA, True, cc.VALE),
    "c_menor_com_a_preferencia": (MENOR, True, cc.CAIU),
    "d_da_casa_sem_a_marca": (f"{PISO}{SUFIXO}", True, cc.CAIU),
    "e_menor_sem_a_preferencia": (MENOR, False, cc.NAO_SE_APLICA),
}


def _maquina(base: Path, versao: str, com_a_pref: bool) -> cc.Maquina:
    assets = base / "assets" / "portal-cosmic-backport"
    assets.mkdir(parents=True)
    programa = base / "portal"
    programa.write_bytes(SEM_A_MARCA)
    texto = BASELINE.read_text(encoding="utf-8")
    exec_real = f"PORTAL_EXEC={BASE['PORTAL_EXEC']}\n"
    assert exec_real in texto
    (assets / "BASELINE").write_text(
        texto.replace(exec_real, f"PORTAL_EXEC={programa}\n"), encoding="utf-8")
    apt = base / "apt"
    apt.mkdir()
    if com_a_pref:
        (apt / cc.PREF_DO_PORTAL).write_text(f"Package: {PACOTE}\n", encoding="utf-8")
    pacotes = {PACOTE: versao, "cosmic-comp": "1.0.0"}

    def comando(argv: Sequence[str]) -> str | None:
        if argv[0] == "dpkg-query" and argv[-1] in pacotes:
            return f"ii |{pacotes[argv[-1]]}\n"
        if argv[:2] == ["dpkg", "--compare-versions"]:
            feito = subprocess.run(list(argv), capture_output=True, text=True, check=False)
            return feito.stdout if feito.returncode == 0 else None
        return None

    return cc.Maquina(assets=base / "assets", cache=base / "cache", kernel="7.2.15",
                      comando=comando, preferencias_do_apt=apt)


def _exe(pasta: Path, nome: str, corpo: str) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    alvo = pasta / nome
    alvo.write_text("#!/bin/bash\n" + corpo, encoding="utf-8")
    alvo.chmod(alvo.stat().st_mode | stat.S_IEXEC)


def _doctor(base: Path, versao: str, com_a_pref: bool) -> str:
    fakes = base / "fakes"
    _exe(fakes, "dpkg-query",
         'for a in "$@"; do pkg="$a"; done\n'
         f'case "$pkg" in {PACOTE}) printf "ii |{versao}\\n" ;; '
         'cosmic-comp) printf "ii |1.0.0\\n" ;; *) exit 1 ;; esac\n')
    _exe(fakes, "systemctl", "echo 0\n")
    lar = base / "lar"
    lar.mkdir()
    pref = base / "pref-do-portal"
    if com_a_pref:
        pref.write_text(f"Package: {PACOTE}\n", encoding="utf-8")
    texto = BASELINE.read_text(encoding="utf-8")
    exec_real = f"PORTAL_EXEC={BASE['PORTAL_EXEC']}\n"
    baseline = base / "BASELINE"
    baseline.write_text(
        texto.replace(exec_real, f"PORTAL_EXEC={base / 'sem-portal-oficial'}\n"),
        encoding="utf-8")
    (base / "portal").write_bytes(SEM_A_MARCA)
    env = {
        "PATH": f"{fakes}:/usr/bin:/bin",
        "HOME": str(lar),
        "XDG_CURRENT_DESKTOP": "COSMIC",
        "HEFESTO_DOCTOR_SYSTEMD_DO_SISTEMA": str(base / "sistema-vazio"),
        "HEFESTO_DOCTOR_PORTAL_BASELINE": str(baseline),
        "HEFESTO_DOCTOR_PORTAL_CURADAS": str(base / "curadas.txt"),
        "HEFESTO_DOCTOR_PORTAL_PREF": str(pref),
        "HEFESTO_DOCTOR_PORTAL_COSMIC": str(base / "portal"),
    }
    script = (f'source "{DOCTOR}"\nQUIET=0\nWARNS=0\n'
              "check_o_portal_de_captura_do_cosmic\n"
              'echo "WARNS=${WARNS}"\n')
    r = subprocess.run([BASH, "-c", script], env=env, capture_output=True, text=True,
                       timeout=60, check=False)
    return r.stdout + r.stderr


def test_o_baseline_traz_o_piso_e_ele_nao_e_versao_da_casa() -> None:
    assert CHAVE in BASE, "o BASELINE do portal tem de trazer o piso da versão de cima já curada"
    assert BASE[CHAVE] and "~hefesto" not in BASE[CHAVE], BASE[CHAVE]
    assert BASE[CHAVE] != BASE["SUFIXO"]


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_o_servico_julga_o_portal_pelo_piso_sem_lista_nenhuma(tmp_path: Path, caso: str) -> None:
    """MORDIDA: sem a regra do piso, a distribuição que já trouxe a correção vira queda."""
    versao, com_a_pref, esperado = CASOS[caso]
    maquina = _maquina(tmp_path, versao, com_a_pref)
    cura = cc.portal(maquina)
    assert cura.estado == esperado, (
        f"{caso}: a distribuição que já trouxe a correção não é queda ({cura})")
    if esperado == cc.CAIU:
        assert cura.frase == "A captura de tela voltou à da distribuição, sem a correção do Hefesto"
        assert cura.dica == "Rode o instalador do Hefesto de novo, com --com-tela."
    if esperado != cc.CAIU:
        assert cc.linhas_de_aviso([cura]) == []


@pytest.mark.parametrize("caso", sorted(CASOS))
def test_o_doctor_concorda_com_o_servico_nos_mesmos_casos(tmp_path: Path, caso: str) -> None:
    """MORDIDA: sem a regra do piso no doctor, ele avisa o que o serviço já aprova."""
    versao, com_a_pref, esperado = CASOS[caso]
    saida = _doctor(tmp_path, versao, com_a_pref)
    if esperado == cc.VALE:
        assert "[ OK ] o portal de captura" in saida and "WARNS=0" in saida, saida
    elif esperado == cc.CAIU:
        assert "[WARN] o portal de captura" in saida and "WARNS=1" in saida, saida
        assert "--com-tela" in saida, saida
    else:
        assert "[WARN]" not in saida and "[ OK ]" not in saida and "WARNS=0" in saida, saida


def test_a_lista_de_arquivo_segue_valendo_abaixo_do_piso(tmp_path: Path) -> None:
    maquina = _maquina(tmp_path, MENOR, True)
    assert cc.portal(maquina).estado == cc.CAIU
    lista = tmp_path / "cache" / "portal-cosmic-backport" / "A-ORIGEM-JA-CURA.txt"
    lista.parent.mkdir(parents=True)
    lista.write_text(f"{MENOR}\n", encoding="utf-8")
    assert cc.portal(maquina).estado == cc.VALE


def test_sem_o_piso_no_baseline_a_regra_nao_inventa_versao(tmp_path: Path) -> None:
    maquina = _maquina(tmp_path, MAIS_NOVA, True)
    arquivo = tmp_path / "assets" / "portal-cosmic-backport" / "BASELINE"
    arquivo.write_text(
        "".join(linha + "\n" for linha in arquivo.read_text(encoding="utf-8").splitlines()
                if not linha.startswith(CHAVE)), encoding="utf-8")
    assert cc.portal(maquina).estado == cc.CAIU
