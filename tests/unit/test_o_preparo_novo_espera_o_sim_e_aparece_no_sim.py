"""O preparo novo espera o «sim» e aparece no «sim».

Sprint O-PREPARO-NOVO-ESPERA-O-SIM-E-APARECE-NO-SIM-01.

A identidade do preparo é o código da versão, não a lista do comando: a atualização sozinha de
extensão com ``preparar`` nunca roda o preparo e espera o «Atualizar», mesmo com a lista igual e o
``install.sh`` mudado. O ``mod ligar`` e a lista das permissões dizem que o preparo roda fora da
caixa.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from hefesto_dualsense4unix.cli import cmd_mod
from hefesto_dualsense4unix.mods.instalador import (
    Lugares,
    atualizar,
    frase_do_preparo,
    gravar_registro,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
)
from tests.unit.test_a_extensao_instalada_roda_o_preparo import _fonte, _preparado, lar

__all__ = ["lar"]

_INSTALL = 'printf "%s\\n" "$1" > "$HEFESTO_MOD_DADOS/{marca}"\n'


def _com_install(fonte: Path, marca: str) -> None:
    (fonte / "install.sh").write_text(_INSTALL.format(marca=marca), encoding="utf-8")


def _ligar(lar: Lugares) -> None:
    ligar("exemplo", permissoes_vistas=manifesto_instalado("exemplo", lugares=lar).permissoes,
          lugares=lar)


def test_a_lista_igual_com_o_install_mudado_espera_o_atualizar(
        lar: Lugares, tmp_path: Path) -> None:
    fonte = _fonte(tmp_path, preparar=["bash", "install.sh", "--yes"])
    _com_install(fonte, "v1")
    instalar(str(fonte), lugares=lar)
    _ligar(lar)
    assert (lar.dados / "exemplo" / "v1").is_file(), "o preparo da v1 rodou no ligar"

    _fonte(tmp_path, versao="0.2.0", preparar=["bash", "install.sh", "--yes"])
    _com_install(fonte, "v2")
    feito = instalar(str(fonte), lugares=lar, sozinha=True)

    assert not feito.trocou
    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.versao == "0.1.0" and entrada.ligada
    assert entrada.versao_esperando == "0.2.0"
    assert entrada.motivo_da_espera == "A versão 0.2.0 roda o preparo de novo, fora da caixa."
    assert not (lar.dados / "exemplo" / "v2").exists(), "o preparo novo rodou sem o «sim»"

    atualizar("exemplo", lugares=lar)
    assert (lar.dados / "exemplo" / "v2").is_file(), "o «Atualizar» é o «sim» do preparo"


def test_sem_preparo_a_atualizacao_sozinha_segue_trocando(lar: Lugares, tmp_path: Path) -> None:
    fonte = _fonte(tmp_path, preparar=None)
    instalar(str(fonte), lugares=lar)
    _ligar(lar)
    _fonte(tmp_path, versao="0.2.0", preparar=None)
    assert instalar(str(fonte), lugares=lar, sozinha=True).trocou
    assert not _preparado(lar).exists()


def test_a_frase_do_preparo_diz_o_comando_e_a_pasta_pessoal(lar: Lugares, tmp_path: Path) -> None:
    instalar(str(_fonte(tmp_path, preparar=["bash", "install.sh", "--yes"])), lugares=lar)
    manifesto = manifesto_instalado("exemplo", lugares=lar)
    assert frase_do_preparo(manifesto) == (
        "Roda `bash install.sh --yes` fora da caixa, com acesso à sua pasta pessoal.")


_LISTA_DAS_PERMISSOES = "permissoes"  # (noqa-acento)


@pytest.mark.parametrize("comando", [["ligar", "exemplo"], [_LISTA_DAS_PERMISSOES, "exemplo"]])
def test_a_linha_de_comando_mostra_o_preparo_antes_do_sim(
        lar: Lugares, tmp_path: Path, comando: list[str]) -> None:
    fonte = _fonte(tmp_path, preparar=["bash", "install.sh", "--yes"])
    _com_install(fonte, "v1")
    instalar(str(fonte), lugares=lar)
    saida = CliRunner().invoke(cmd_mod.app, comando, input="n\n").output
    frase = "Roda `bash install.sh --yes` fora da caixa, com acesso à sua pasta pessoal."
    assert frase in saida, saida
    if comando[0] == "ligar":
        assert saida.index(frase) < saida.index("Ligar com estas permissões?")
        assert not (lar.dados / "exemplo" / "v1").exists()


def test_a_tag_que_nao_confere_nao_se_esconde_atras_do_preparo(
        lar: Lugares, tmp_path: Path) -> None:
    fonte = _fonte(tmp_path, preparar=["bash", "install.sh", "--yes"])
    _com_install(fonte, "v1")
    instalar(str(fonte), lugares=lar)
    _ligar(lar)
    registro = ler_registro(lar.registro)
    registro["exemplo"].origem = "oficial"
    gravar_registro(lar.registro, registro)

    _fonte(tmp_path, versao="0.2.0", preparar=["bash", "install.sh", "--yes"])
    _com_install(fonte, "v2")
    assert not instalar(str(fonte), lugares=lar, sozinha=True).trocou

    entrada = ler_registro(lar.registro)["exemplo"]
    assert entrada.motivo_da_espera == "A tag da versão 0.2.0 não confere com a chave oficial."
    assert not (lar.dados / "exemplo" / "v2").exists()
