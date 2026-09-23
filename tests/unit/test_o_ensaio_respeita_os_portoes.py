"""O `--dry-run` imprime o plano DAQUELA linha de comando — com as flags dela.

INSTALL-E-UNINSTALL-DO-RADIO-01 (23/09/2026), a dívida que a conferência da
O-QUE-E-DO-HEFESTO-SAI-DO-ZSH-01 achou: o `_ensaio_camada` do `install.sh`
descrevia cada cura de host como se ela fosse rodar, com qualquer flag.
`./install.sh --dry-run --no-wifi-usb` prometia instalar o vigia do Wi-Fi USB;
`--dry-run --no-udev` prometia o `/etc` inteiro; e o uhid com contrapressão,
que é OPT-IN, nem aparecia. O cabeçalho do próprio `install.sh` diz o
contrário: *"o plano que ele imprime é o plano DAQUELA linha de comando"*.

Duas réguas, e a segunda existe porque a primeira lê texto:

1. **Estática, função por função:** as flags de portão que o corpo de cada
   `*_host` da `camada_de_maquina.sh` lê são as MESMAS que o ramo do ensaio
   dela lê. Uma flag nova num `*_host` sem o ramo correspondente reprova
   nomeando as duas. É a que alcança a cura de amanhã.
2. **Pelo ato:** o ensaio de verdade, num lar de mentira com todo binário de
   sistema dublado (a bancada do `test_o_ensaio_do_install_nao_escreve.py`),
   com e sem as flags — e o que se lê é a saída.

A MORDIDA, medida: arrancar o `if [[ "${NO_WIFI_USB}" -eq 1 ]]` do ramo
`wifi-usb` do `_ensaio_camada` reprova as duas réguas; arrancar o do
`COM_UHID_CONTRAPRESSAO` do ramo `dkms-uhid`, idem.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.unit.test_o_ensaio_do_install_nao_escreve import _roda_ensaio

RAIZ = Path(__file__).resolve().parents[2]
INSTALL = (RAIZ / "install.sh").read_text(encoding="utf-8")
CAMADA = (RAIZ / "scripts" / "lib" / "camada_de_maquina.sh").read_text(encoding="utf-8")

#: As variáveis que DESLIGAM ou MUDAM uma cura de host inteira. `AUTO_YES` fica
#: de fora de propósito: ela muda uma pergunta, não o que a cura escreve.
PORTOES = (
    "SKIP_UDEV",
    "NO_OSK",
    "NO_DKMS",
    "NO_UCM",
    "NO_WIFI_USB",
    "COM_UHID_CONTRAPRESSAO",
    "ABRIR_O_NO",
)


def _tabela() -> list[tuple[str, str]]:
    inicio = INSTALL.index("_ENSAIO_CURAS_DE_HOST=(")
    fim = INSTALL.index("\n)\n", inicio)
    return [
        (par.split(":")[0], par.split(":")[1])
        for par in re.findall(r'"([a-z_0-9]+_host:[a-z0-9-]+)"', INSTALL[inicio:fim])
    ]


def _corpo_na_lib(funcao: str) -> str:
    inicio = CAMADA.index(f"\n{funcao}() {{\n")
    fim = CAMADA.index("\n}\n", inicio)
    return CAMADA[inicio:fim]


def _ramo_do_ensaio(rotulo: str) -> str:
    inicio_funcao = INSTALL.index("_ensaio_camada() {")
    fim_funcao = INSTALL.index("\n}\n", inicio_funcao)
    corpo = INSTALL[inicio_funcao:fim_funcao]
    inicio = corpo.index(f"\n        {rotulo})\n")
    fim = corpo.index("\n            ;;\n", inicio)
    return corpo[inicio:fim]


def _portoes_lidos(texto: str) -> set[str]:
    sem_comentario = "\n".join(
        linha for linha in texto.splitlines() if not linha.lstrip().startswith("#")
    )
    return {p for p in PORTOES if re.search(r"\$\{" + p + r"(?::-[^}]*)?\}", sem_comentario)}


@pytest.mark.parametrize(("funcao", "rotulo"), _tabela())
def test_o_ramo_do_ensaio_le_os_mesmos_portoes_da_cura(funcao: str, rotulo: str) -> None:
    na_cura = _portoes_lidos(_corpo_na_lib(funcao))
    no_ensaio = _portoes_lidos(_ramo_do_ensaio(rotulo))
    assert na_cura == no_ensaio, (
        f"`{funcao}` lê os portões {sorted(na_cura)}, e o ramo `{rotulo}` do "
        f"`_ensaio_camada` lê {sorted(no_ensaio)}. O `--dry-run` imprimiria o "
        "plano de OUTRA linha de comando: faltam no ensaio "
        f"{sorted(na_cura - no_ensaio)}, sobram {sorted(no_ensaio - na_cura)}."
    )


def test_a_tabela_nao_esta_vazia() -> None:
    """Controle: sem linhas na tabela, o parametrize acima não mede nada."""
    assert len(_tabela()) >= 14


def _linhas_faria(saida: str) -> str:
    return "\n".join(linha for linha in saida.splitlines() if "FARIA" in linha)


class TestPeloAto:
    def test_sem_flag_o_plano_tem_o_vigia_e_a_trava_e_nao_tem_o_uhid(
        self, tmp_path: Path
    ) -> None:
        resultado, _lar, _diario = _roda_ensaio(tmp_path)
        faria = _linhas_faria(resultado.stdout)
        assert "hefesto-wifi-usb-vigia.timer" in faria, resultado.stdout[-3000:]
        assert "/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf" in faria
        assert "hefesto-uhid" not in faria, (
            "o uhid com contrapressão é OPT-IN, e o ensaio sem a flag o planeja"
        )
        assert "uhid com contrapressão (opt-in: --uhid-contrapressao)" in resultado.stdout

    def test_com_no_wifi_usb_o_vigia_sai_do_plano(self, tmp_path: Path) -> None:
        resultado, _lar, _diario = _roda_ensaio(tmp_path, "--no-wifi-usb")
        faria = _linhas_faria(resultado.stdout)
        assert "hefesto-wifi-usb-vigia" not in faria, (
            "com --no-wifi-usb o ensaio ainda promete o vigia do Wi-Fi USB:\n" + faria
        )
        assert "vigia do Wi-Fi USB (--no-wifi-usb)" in resultado.stdout

    def test_com_no_udev_nada_do_etc_da_camada_entra_no_plano(
        self, tmp_path: Path
    ) -> None:
        resultado, _lar, _diario = _roda_ensaio(tmp_path, "--no-udev")
        faria = _linhas_faria(resultado.stdout)
        for alvo in (
            "/etc/tmpfiles.d/hefesto-dualsense4unix-radio.conf",
            "/etc/systemd/system/hefesto-hidraw-broker.service",
            "hefesto-wifi-usb-vigia.timer",
            "10-hefesto-resilience.conf",
            "hefesto-bt-agent.service",
        ):
            assert alvo not in faria, (
                f"com --no-udev o ensaio ainda promete {alvo}:\n" + faria
            )

    def test_com_a_flag_o_uhid_entra_no_plano(self, tmp_path: Path) -> None:
        resultado, _lar, _diario = _roda_ensaio(tmp_path, "--uhid-contrapressao")
        faria = _linhas_faria(resultado.stdout)
        assert "hefesto-uhid" in faria, resultado.stdout[-3000:]
        assert "/etc/modprobe.d/hefesto-uhid.conf" in faria
