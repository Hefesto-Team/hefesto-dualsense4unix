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
        if pacote in por_kernel:
            nomes = sorted(p.name for p in (origem / "patch").glob("*.patch"))
        else:
            nomes = ck._serie_da_raiz(ck._linhas_do_baseline(pacote))
        _desfaz([origem / "patch" / n for n in nomes], destino, list(arquivos))
    return destino


RTW88 = "drivers/net/wireless/realtek/rtw88"
PASTA_7_2_6 = "7.2.6-76070206"


def _fonte_do_rtw88(destino: Path, build: str | None = None, rx_h: bytes | None = None) -> Path:
    """O fonte de fábrica do rtw88: o da raiz (7.0.11) ou o da pasta de `build`.

    A pasta guarda o `usb.c` patchado e o `rx.h` dele; o `usb.h` é o da raiz, patchado.
    Desfaz a série de quem guarda o arquivo, sem passar por nada do script.
    """
    pacote = DKMS / "rtw88-usb"
    pasta = pacote / "fonte-por-kernel" / build if build else pacote
    arvore = destino / RTW88
    arvore.mkdir(parents=True)
    for nome in ("usb.c", "usb.h", "rx.h"):
        origem = pasta / nome if (pasta / nome).is_file() else pacote / nome
        shutil.copyfile(origem, arvore / nome)
    if build:
        nomes = sorted(p.name for p in (pasta / "patch").glob("*.patch"))
    else:
        nomes = ck._serie_da_raiz(ck._linhas_do_baseline("rtw88-usb"))
    arquivos = [f"{RTW88}/usb.c", f"{RTW88}/usb.h"]
    _desfaz([pasta / "patch" / n for n in nomes], destino, arquivos)
    if rx_h is not None:
        (arvore / "rx.h").write_bytes(rx_h)
    return destino


@pytest.fixture
def dkms_de_mentira(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Um `assets/dkms` num tmp_path só com o rtw88: cópia do real, que o teste pode mexer."""
    dkms = tmp_path / "assets" / "dkms"
    pacote = dkms / "rtw88-usb"
    pacote.mkdir(parents=True)
    for nome in ("usb.c", "usb.h", "rx.h"):
        shutil.copyfile(DKMS / "rtw88-usb" / nome, pacote / nome)
    for pasta in ("patch", "fonte-por-kernel"):
        shutil.copytree(DKMS / "rtw88-usb" / pasta, pacote / pasta)
    monkeypatch.setattr(ck, "DKMS", dkms)
    monkeypatch.setattr(ck, "PACOTES", {"rtw88-usb": ck.PACOTES["rtw88-usb"]})
    return dkms


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


def test_o_7_2_6_do_rtw88_confere_pela_pasta_dele(tmp_path: Path) -> None:
    """O verde falso medido em 17/10: o `usb.c` e o `rx.h` do 7.2.6 já estão na pasta dele."""
    fonte = _fonte_do_rtw88(tmp_path / "linux", PASTA_7_2_6)
    resposta = ck.conferir("rtw88-usb", fonte)
    assert resposta.veredito == ck.CONFERE, resposta
    assert resposta.base == f"fonte-por-kernel/{PASTA_7_2_6}"
    raiz = ck.conferir("rtw88-usb", fonte, so_a_raiz=True)
    assert raiz.veredito == ck.PEDE_REBASE, raiz
    assert raiz.mudou == [f"{RTW88}/rx.h"]


def test_o_de_fabrica_da_raiz_do_rtw88_confere_pela_raiz(tmp_path: Path) -> None:
    resposta = ck.conferir("rtw88-usb", _fonte_do_rtw88(tmp_path / "linux"))
    assert (resposta.veredito, resposta.base) == (ck.CONFERE, "da raiz")


def test_o_de_fabrica_do_7_1_5_confere_pela_raiz(tmp_path: Path) -> None:
    """No 7.1.5 o `0001` já está no kernel: desfeito só o `0002`, o `usb.c` é a chave `_7_1_5`."""
    fonte = _fonte_do_rtw88(tmp_path / "linux")
    pacote = DKMS / "rtw88-usb"
    nomes = ck._serie_da_raiz(ck._linhas_do_baseline("rtw88-usb"))
    fonte_715 = tmp_path / "linux715"
    shutil.copytree(fonte, fonte_715)
    for nome in ("usb.c", "usb.h"):
        shutil.copyfile(pacote / nome, fonte_715 / RTW88 / nome)
    _desfaz([pacote / "patch" / nomes[1]], fonte_715, [f"{RTW88}/usb.c", f"{RTW88}/usb.h"])
    resposta = ck.conferir("rtw88-usb", fonte_715)
    assert (resposta.veredito, resposta.base) == (ck.CONFERE, "da raiz"), resposta
    assert resposta.shas[f"{RTW88}/usb.c"] != ck.conferir("rtw88-usb", fonte).shas[f"{RTW88}/usb.c"]


def test_rx_h_mudado_pede_rebase_mesmo_com_a_serie_limpa(
    tmp_path: Path, dkms_de_mentira: Path
) -> None:
    """O `usb.c` é o que a raiz patcha limpo, mas o `rx.h` não é de base nenhuma."""
    fonte = _fonte_do_rtw88(tmp_path / "linux")
    rx = fonte / RTW88 / "rx.h"
    rx.write_bytes(rx.read_bytes() + b"/* o kernel novo mudou a assinatura */\n")
    series = ck._series("rtw88-usb")
    assert set(ck._experimenta(series[0], fonte, list(ck.PACOTES["rtw88-usb"])).values()) <= {
        "entra",
        "já está no kernel",
    }
    resposta = ck.conferir("rtw88-usb", fonte)
    assert resposta.veredito == ck.PEDE_REBASE, resposta
    assert resposta.mudou == [f"{RTW88}/rx.h"]
    assert "mudou: rx.h" in resposta.linha()


def test_rx_h_mudado_no_7_2_6_tambem_pede_rebase(tmp_path: Path) -> None:
    """As duas séries empatam no `rx.h`; a linha aponta a da pasta, a base mais perto."""
    fonte = _fonte_do_rtw88(tmp_path / "linux", PASTA_7_2_6)
    rx = fonte / RTW88 / "rx.h"
    rx.write_bytes(rx.read_bytes() + b"/* mais uma mudanca */\n")
    resposta = ck.conferir("rtw88-usb", fonte)
    assert resposta.veredito == ck.PEDE_REBASE, resposta
    assert resposta.mudou == [f"{RTW88}/rx.h"]
    assert resposta.serie == f"de fonte-por-kernel/{PASTA_7_2_6}", resposta


def test_pasta_por_kernel_so_com_o_0002_nao_levanta_excecao(tmp_path: Path) -> None:
    pasta = DKMS / "rtw88-usb" / "fonte-por-kernel" / PASTA_7_2_6 / "patch"
    assert [p.name[:4] for p in pasta.glob("*.patch")] == ["0002"]
    series = {s.nome: s.patches for s in ck._series("rtw88-usb")}
    assert [n[:4] for n in series[f"de fonte-por-kernel/{PASTA_7_2_6}"]] == ["0002"]
    fonte = _fonte_do_rtw88(tmp_path / "linux", PASTA_7_2_6)
    usb = fonte / RTW88 / "usb.c"
    usb.write_bytes(usb.read_bytes().replace(b"int rtw_usb_probe", b"int  rtw_usb_probe", 1))
    resposta = ck.conferir("rtw88-usb", fonte)
    assert resposta.veredito in (ck.APLICA_LIMPA, ck.PEDE_REBASE), resposta
    assert resposta.serie == f"de fonte-por-kernel/{PASTA_7_2_6}", resposta
    assert all(nome.startswith("0002") for nome in resposta.por_patch), resposta


def test_chave_nova_no_baseline_vira_base_sem_tocar_o_script(
    tmp_path: Path, dkms_de_mentira: Path
) -> None:
    fonte = _fonte_do_rtw88(tmp_path / "linux")
    usb = fonte / RTW88 / "usb.c"
    usb.write_bytes(usb.read_bytes().replace(b"int rtw_usb_probe", b"int  rtw_usb_probe", 1))
    antes = ck.conferir("rtw88-usb", fonte)
    assert antes.veredito == ck.APLICA_LIMPA, antes
    baseline = dkms_de_mentira / "rtw88-usb" / "patch" / "BASELINE"
    novo = hashlib.sha256(usb.read_bytes()).hexdigest()
    with baseline.open("a", encoding="utf-8") as arquivo:
        arquivo.write(f"SHA256_VANILLA_C_7_3_0={novo}\n")
    depois = ck.conferir("rtw88-usb", fonte)
    assert (depois.veredito, depois.base) == (ck.CONFERE, "da raiz"), depois


def test_chave_de_kernel_que_tem_pasta_nao_serve_a_raiz(dkms_de_mentira: Path) -> None:
    """A `SHA256_VANILLA_C_7_2_6` é da pasta do 7.2.6: o `usb.c` dele não é de fábrica da raiz."""
    linhas = ck._linhas_do_baseline("rtw88-usb")
    chave = next(ln for ln in linhas if ln.startswith("SHA256_VANILLA_C_7_2_6=")).split("=")[1]
    usb = f"{RTW88}/usb.c"
    bases = dict(ck._bases("rtw88-usb"))
    assert chave not in bases["da raiz"][usb]
    assert chave in bases[f"fonte-por-kernel/{PASTA_7_2_6}"][usb]
