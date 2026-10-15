"""O kernel novo se confere por script, sem rede, contra o fonte de fábrica reconstruído."""

from __future__ import annotations

import hashlib
import importlib.util
import re
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "scripts" / "conferir_o_kernel_novo.py"
DKMS = RAIZ / "assets" / "dkms"

pytestmark = pytest.mark.skipif(shutil.which("patch") is None, reason="sem o patch(1)")


def _modulo() -> ModuleType:
    spec = importlib.util.spec_from_file_location("conferir_o_kernel_novo", SCRIPT)
    assert spec and spec.loader
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = modulo
    spec.loader.exec_module(modulo)
    return modulo


ck = _modulo()


def _desfaz(serie: list[Path], arvore: Path, arquivos: list[str]) -> None:
    for patch in reversed(serie):
        texto = patch.read_text(encoding="utf-8")
        if re.search(r"^\+\+\+ b/", texto, re.M):
            comando = ["patch", "-R", "-p1", "-F0", "-s", "-d", str(arvore)]
        else:
            comando = ["patch", "-R", "-F0", "-s", str(arvore / arquivos[0])]
        feito = subprocess.run(
            comando, input=texto, capture_output=True, text=True, timeout=60, check=False
        )
        assert feito.returncode == 0, (patch.name, feito.stdout, feito.stderr)


def _fonte_de_fabrica(destino: Path, por_kernel: dict[str, str] | None = None) -> Path:
    """A árvore do kernel com o arquivo de fábrica de cada pacote, pela série desfeita.

    `por_kernel` troca, para um pacote, a raiz pela pasta `fonte-por-kernel/<build>/`.
    O rtw88 só tem a raiz, que desfeita inteira dá o de fábrica do 7.0.11.
    """
    por_kernel = por_kernel or {}
    for pacote, arquivos in ck.PACOTES.items():
        origem = DKMS / pacote
        if pacote in por_kernel:
            origem = origem / "fonte-por-kernel" / por_kernel[pacote]
        for caminho in arquivos:
            alvo = destino / caminho
            alvo.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(origem / Path(caminho).name, alvo)
        nomes = ck._serie_da_raiz(ck._linhas_do_baseline(pacote))
        _desfaz([origem / "patch" / n for n in nomes], destino, list(arquivos))
    return destino


def _hashes_dos_assets() -> dict[str, str]:
    return {
        str(p.relative_to(DKMS)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(DKMS.rglob("*"))
        if p.is_file()
    }


def test_todo_pacote_com_baseline_tem_mapa_no_script() -> None:
    assert ck.pacotes_com_baseline(), "nenhum pacote com BASELINE: a régua não mede nada"
    assert set(ck.pacotes_com_baseline()) == set(ck.PACOTES)


def test_o_de_fabrica_de_hoje_confere_em_todos(tmp_path: Path) -> None:
    fonte = _fonte_de_fabrica(tmp_path / "linux")
    respostas = {p: ck.conferir(p, fonte) for p in ck.PACOTES}
    assert {p: r.veredito for p, r in respostas.items()} == dict.fromkeys(ck.PACOTES, ck.CONFERE)
    assert ck.main([str(fonte)]) == 0


def test_um_byte_trocado_no_playstation_nao_confere(tmp_path: Path) -> None:
    """A mordida da sprint: um sha que não é o da base nunca diz «confere»."""
    fonte = _fonte_de_fabrica(tmp_path / "linux")
    alvo = fonte / "drivers/hid/hid-playstation.c"
    alvo.write_bytes(alvo.read_bytes().replace(b"Sony", b"S0ny", 1))
    resposta = ck.conferir("hid-playstation", fonte)
    assert resposta.veredito == ck.APLICA_LIMPA, resposta
    assert resposta.serie == "da raiz"
    assert ck.main([str(fonte)]) == 1


def test_contexto_quebrado_pede_rebase_e_nomeia_o_patch(tmp_path: Path) -> None:
    fonte = _fonte_de_fabrica(tmp_path / "linux")
    alvo = fonte / "drivers/hid/uhid.c"
    texto = alvo.read_text(encoding="utf-8")
    patch = next((DKMS / "uhid" / "patch").glob("0001-*.patch"))
    contexto = next(
        linha[1:]
        for linha in patch.read_text(encoding="utf-8").splitlines()
        if linha.startswith(" ") and len(linha.strip()) > 20
    )
    assert contexto in texto
    alvo.write_text(texto.replace(contexto, contexto + " /* mexido */", 1), encoding="utf-8")
    resposta = ck.conferir("uhid", fonte)
    assert resposta.veredito == ck.PEDE_REBASE, resposta
    assert any("de fora" in estado for estado in resposta.por_patch.values()), resposta


def test_o_7_2_6_confere_pela_pasta_dele_e_a_raiz_pede_rebase(tmp_path: Path) -> None:
    """O caso medido em 13/10: no 7.2.6 a série da raiz do nintendo deixa dois pedaços de fora."""
    fonte = _fonte_de_fabrica(
        tmp_path / "linux",
        por_kernel={"hid-nintendo": "7.2.6-76070206", "hid-playstation": "7.2.6-76070206"},
    )
    nintendo = ck.conferir("hid-nintendo", fonte)
    assert nintendo.veredito == ck.CONFERE
    assert nintendo.base == "fonte-por-kernel/7.2.6-76070206"
    so_a_raiz = ck.conferir("hid-nintendo", fonte, so_a_raiz=True)
    assert so_a_raiz.veredito == ck.PEDE_REBASE
    leds, usb = (
        "0002-HID-nintendo-register-leds-even-when-initial-set-fai.patch",
        "0003-HID-nintendo-pad-USB-commands-and-survive-no-dev-inf.patch",
    )
    assert so_a_raiz.por_patch[leds] == "entra"
    assert "de fora" in so_a_raiz.por_patch[usb]
    playstation = ck.conferir("hid-playstation", fonte, so_a_raiz=True)
    assert playstation.veredito == ck.APLICA_LIMPA


def test_sem_o_arquivo_nao_confere(tmp_path: Path) -> None:
    fonte = _fonte_de_fabrica(tmp_path / "linux")
    (fonte / "drivers/usb/gadget/function/f_hid.c").unlink()
    assert ck.conferir("usb-f-hid", fonte).veredito == ck.SEM_ARQUIVO
    assert ck.main([str(fonte)]) == 1


def test_nunca_escreve_em_assets(tmp_path: Path) -> None:
    antes = _hashes_dos_assets()
    fonte = _fonte_de_fabrica(tmp_path / "linux")
    (fonte / "drivers/hid/hid-nintendo.c").write_bytes(b"/* outro kernel */\n")
    ck.main([str(fonte)])
    assert _hashes_dos_assets() == antes


def test_commit_invalido_nao_vai_a_rede() -> None:
    assert ck.main(["--pop", "nao-e-commit"]) == 2
