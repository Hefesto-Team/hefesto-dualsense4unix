"""A extensão instalada pelo Hefesto roda o preparo dela.

A sprint é a A-EXTENSAO-INSTALADA-PELO-HEFESTO-RODA-O-PREPARO-DELA-01: o campo ``preparar``
do manifesto é um comando, relativo à pasta da extensão, que o instalador roda fora da caixa,
como quem usa, depois de trocar o código e antes de ligar. Tudo num lar de mentira (``HOME`` e
``XDG_*`` em pasta temporária), com uma extensão de mentira cujo preparo grava um arquivo na
pasta de dados: nenhuma prova fala com o serviço dela, com a rede nem com extensão de verdade.

MORDIDAS (24/10/2026, executadas sobre a cura e devolvidas):

- o preparo só na instalação nova (``and anterior is None`` no ``if manifesto.preparar``
  do ``instalar``, o que o ``atualizar`` deixa de fazer) reprova
  ``test_atualizar_para_a_versao_nova_roda_o_preparo_de_novo``;
- o preparo novo tirado do ``_o_que_segura_a_atualizacao`` reprova
  ``test_o_preparo_novo_numa_atualizacao_sozinha_espera_o_atualizar``;
- a falha que não desliga (``entrada.ligada = False`` tirado do ``_rodar_o_preparo``) reprova
  ``test_o_preparo_que_falha_deixa_a_extensao_desligada_com_o_motivo``.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.instalador import (
    DIARIO_DO_PREPARO,
    InstalacaoRecusadaError,
    Lugares,
    atualizar,
    instalar,
    ler_registro,
    ligar,
    manifesto_instalado,
)
from hefesto_dualsense4unix.mods.manifesto import ManifestoRecusadoError, ler_manifesto

#: O preparo de mentira: faz o que o arquivo ``modo`` da pasta manda, e grava na pasta de dados
#: a casa, a pasta de trabalho e o ambiente que recebeu.
_O_PREPARO = """#!/bin/sh
modo=$(cat modo)
echo "preparando"
case "$modo" in
  falha) echo "faltou a rede"; exit 3 ;;
  demora) echo $$ > "$HEFESTO_MOD_DADOS/pid"; exec sleep 60 ;;
esac
printf '%s\\n%s\\n' "$HOME" "$PWD" > "$HEFESTO_MOD_DADOS/preparado"
env > "$HEFESTO_MOD_DADOS/ambiente"
"""

_PREPARAR = ["sh", "prepara.sh"]


@pytest.fixture
def lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Lugares:
    casa, execucao = tmp_path / "casa", tmp_path / "run"
    for pasta in (casa, execucao):
        pasta.mkdir(mode=0o700)
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(execucao))
    for chave, pasta in (("XDG_CONFIG_HOME", ".config"), ("XDG_DATA_HOME", ".local/share"),
                         ("XDG_STATE_HOME", ".local/state"), ("XDG_CACHE_HOME", ".cache")):
        monkeypatch.setenv(chave, str(casa / pasta))
    monkeypatch.setenv("SEGREDO_DA_SESSAO", "nao-vaza")
    lugares = Lugares.do_xdg()
    for caminho in (lugares.codigo, lugares.dados, lugares.registro, lugares.estado):
        assert str(caminho).startswith(str(tmp_path)), caminho
    return lugares


def _fonte(base: Path, versao: str = "0.1.0", modo: str = "fica", **mais: Any) -> Path:
    """A pasta da extensão de mentira; chamar de novo reescreve a mesma pasta."""
    pasta = base / "fonte-exemplo"
    pasta.mkdir(parents=True, exist_ok=True)
    corpo: dict[str, Any] = {
        "id": "exemplo", "nome": "Exemplo", "versao": versao,  # (noqa-acento): contrato ASCII
        "api": ">=1,<3", "licenca": "MIT", "tipos": ["processo"],
        "processo": {"executar": ["python3", "mod.py"]},
        "permissoes": [],  # (noqa-acento): contrato ASCII
        "preparar": _PREPARAR,
    }
    corpo.update(mais)
    corpo = {k: v for k, v in corpo.items() if v is not None}
    (pasta / "hefesto-mod.json").write_text(json.dumps(corpo), encoding="utf-8")
    (pasta / "mod.py").write_text("import time\nwhile True:\n    time.sleep(1)\n", encoding="utf-8")
    (pasta / "prepara.sh").write_text(_O_PREPARO, encoding="utf-8")
    (pasta / "modo").write_text(modo, encoding="utf-8")
    return pasta


def _preparado(lar: Lugares) -> Path:
    return lar.dados / "exemplo" / "preparado"


def _entrada(lar: Lugares) -> instalador.Entrada:
    return ler_registro(lar.registro)["exemplo"]


def _ligar(lar: Lugares, aviso: str = "") -> None:
    ligar("exemplo", permissoes_vistas=manifesto_instalado("exemplo", lugares=lar).permissoes,
          aviso_visto=aviso, lugares=lar)


# -- o manifesto ---------------------------------------------------------------


@pytest.mark.parametrize(("preparar", "pedaco"), [
    ([], "lista vazia"),
    (["/bin/sh", "x"], "fora da pasta"),
    (["../fora.sh"], "fora da pasta"),
    (["  "], "começa vazio"),
])
def test_o_preparar_fora_da_pasta_e_recusado(
    tmp_path: Path, preparar: list[str], pedaco: str
) -> None:
    with pytest.raises(ManifestoRecusadoError, match=pedaco):
        ler_manifesto(_fonte(tmp_path, preparar=preparar))


def test_o_manifesto_sem_preparar_segue_valendo(tmp_path: Path) -> None:
    assert ler_manifesto(_fonte(tmp_path, preparar=None)).preparar is None


# -- os quatro casos da sprint ----------------------------------------------------


def test_instalar_roda_o_preparo_fora_da_caixa_como_quem_usa(lar: Lugares, tmp_path: Path) -> None:
    feito = instalar(str(_fonte(tmp_path)), lugares=lar)

    casa, pasta = _preparado(lar).read_text(encoding="utf-8").splitlines()
    assert casa == os.environ["HOME"], "o preparo roda na casa de quem usa, não na caixa"
    assert Path(pasta) == lar.codigo / "exemplo", "a pasta de trabalho é a do código"
    ambiente = (lar.dados / "exemplo" / "ambiente").read_text(encoding="utf-8")
    assert f"HEFESTO_MOD_DADOS={lar.dados / 'exemplo'}" in ambiente.splitlines()
    assert "HEFESTO_MOD_ID=exemplo" in ambiente.splitlines()
    assert "SEGREDO_DA_SESSAO" not in ambiente, "o preparo não herda a sessão inteira"
    assert "preparando" in (lar.dados / "exemplo" / DIARIO_DO_PREPARO).read_text(encoding="utf-8")
    entrada = _entrada(lar)
    assert entrada.preparada_em == entrada.instalada_em == feito.entrada.instalada_em
    assert entrada.preparo_aceito == _PREPARAR and entrada.motivo_do_preparo == ""


def test_atualizar_para_a_versao_nova_roda_o_preparo_de_novo(
    lar: Lugares, tmp_path: Path
) -> None:
    """O defeito da 2.2.0: a cópia na pasta de dados sumiu, e atualizar a devolve."""
    fonte = _fonte(tmp_path)
    instalar(str(fonte), lugares=lar)
    _ligar(lar)
    _preparado(lar).unlink()

    _fonte(tmp_path, versao="0.2.0")
    feito = atualizar("exemplo", lugares=lar)

    assert _preparado(lar).is_file(), "atualizar não rodou o preparo"
    entrada = _entrada(lar)
    assert feito.entrada.versao == entrada.versao == "0.2.0"
    assert entrada.ligada, "a que seguia ligada volta ligada depois do preparo"
    assert entrada.preparada_em == entrada.instalada_em


def test_o_preparo_que_falha_deixa_a_extensao_desligada_com_o_motivo(
    lar: Lugares, tmp_path: Path
) -> None:
    fonte = _fonte(tmp_path)
    instalar(str(fonte), lugares=lar)
    _ligar(lar)

    _fonte(tmp_path, versao="0.2.0", modo="falha")
    with pytest.raises(InstalacaoRecusadaError, match="faltou a rede") as recusa:
        atualizar("exemplo", lugares=lar)

    assert "ficou desligada" in recusa.value.frase
    entrada = _entrada(lar)
    assert entrada.versao == "0.2.0", "a extensão fica instalada"
    assert not entrada.ligada, "a extensão nunca liga sem o que precisa"
    assert "código 3" in entrada.motivo_do_preparo and entrada.preparada_em == ""

    # A chave tenta de novo: o preparo que falhou roda no «ligar», e a falha recusa o ligar.
    with pytest.raises(InstalacaoRecusadaError, match="faltou a rede"):
        _ligar(lar)
    assert not _entrada(lar).ligada
    (lar.codigo / "exemplo" / "modo").write_text("fica", encoding="utf-8")
    _ligar(lar)
    entrada = _entrada(lar)
    assert entrada.ligada and entrada.motivo_do_preparo == "" and _preparado(lar).is_file()


def test_o_preparo_novo_numa_atualizacao_sozinha_espera_o_atualizar(
    lar: Lugares, tmp_path: Path
) -> None:
    fonte = _fonte(tmp_path, preparar=None)
    instalar(str(fonte), lugares=lar)
    _ligar(lar)

    _fonte(tmp_path, versao="0.2.0")
    feito = instalar(str(fonte), lugares=lar, sozinha=True)

    assert not feito.trocou
    entrada = _entrada(lar)
    assert entrada.versao == "0.1.0" and entrada.ligada
    assert entrada.versao_esperando == "0.2.0"
    assert entrada.motivo_da_espera == "A versão 0.2.0 traz um preparo novo."
    assert not _preparado(lar).exists(), "o preparo novo rodou sem o «sim»"

    # O «Atualizar» é o «sim»: o preparo roda e a extensão segue ligada.
    atualizar("exemplo", lugares=lar)
    entrada = _entrada(lar)
    assert _preparado(lar).is_file() and entrada.ligada and entrada.versao == "0.2.0"

    # A versão seguinte com o mesmo preparo já não espera: atualiza sozinha e prepara de novo.
    _preparado(lar).unlink()
    _fonte(tmp_path, versao="0.3.0")
    assert instalar(str(fonte), lugares=lar, sozinha=True).trocou
    assert _preparado(lar).is_file() and _entrada(lar).versao_esperando == ""


# -- o «sim» antes do preparo -------------------------------------------------------


def test_o_preparo_espera_o_aviso_e_as_permissoes_e_roda_no_ligar(
    lar: Lugares, tmp_path: Path
) -> None:
    """Nada da extensão roda fora da caixa antes do «sim» ao aviso e às permissões."""
    aviso = "Conteúdo de teste."
    instalar(str(_fonte(tmp_path, aviso=aviso, permissoes=["ler:estado"])), lugares=lar)

    assert not _preparado(lar).exists(), "o preparo rodou antes do «sim»"
    assert not _entrada(lar).ligada and _entrada(lar).preparada_em == ""

    _ligar(lar, aviso=aviso)
    entrada = _entrada(lar)
    assert _preparado(lar).is_file() and entrada.ligada
    assert entrada.preparada_em == entrada.instalada_em


def test_o_preparo_que_passa_do_prazo_e_parado_pelo_pid(
    lar: Lugares, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(instalador, "PRAZO_DO_PREPARO_S", 0.5)
    with pytest.raises(InstalacaoRecusadaError, match="passou de"):
        instalar(str(_fonte(tmp_path, modo="demora")), lugares=lar)

    pid = int((lar.dados / "exemplo" / "pid").read_text(encoding="utf-8"))
    fim = time.monotonic() + 5.0
    while time.monotonic() < fim and Path(f"/proc/{pid}").exists():
        time.sleep(instalador.CADENCIA_DA_ESPERA_S)
    assert not Path(f"/proc/{pid}").exists(), "o preparo passou do prazo e ficou vivo"
    assert not _entrada(lar).ligada
