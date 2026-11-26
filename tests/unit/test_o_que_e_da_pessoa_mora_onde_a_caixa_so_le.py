"""O que é da pessoa mora onde a caixa só lê (O-QUE-E-DA-PESSOA-MORA-ONDE-A-CAIXA-SO-LE-01).

Medido em 25/11/2026 (lar de mentira, ``medir_css_plantado.py`` da leva): a extensão de tema com
processo plantou ``{"meu_css": true}`` e um ``meu.css`` em ``<dados>/<id>``, a pasta que a caixa
escreve, e ``tema_da_casa()`` devolveu ``body > *{visibility:hidden !important;}``; a extensão só de
processo deixou os dois, e a de tema que a substitui os herdou no instalar. O ``opcoes.json``, o
``meu.css`` e os importados passam a morar em ``<config>/mods/<id>``, que a caixa recebe com
``--ro-bind``; a extensão com processo lê uma cópia na pasta do usuário, que a janela nunca lê.

MORDIDAS (25/11/2026, executadas sobre a cura e devolvidas):

- ``meu_css.caminho`` e ``opcoes.caminho`` de volta a ``<dados>``:
  ``test_o_css_plantado_em_dados_nao_veste_a_janela``;
- a pasta da pessoa com ``--bind`` na linha do ``bwrap``:
  ``test_a_caixa_recebe_o_que_e_da_pessoa_so_de_leitura`` e
  ``test_de_dentro_da_caixa_escrever_no_que_e_da_pessoa_falha``;
- a mudança levando o ``meu.css`` da extensão com processo:
  ``test_a_mudanca_nao_leva_o_css_da_extensao_com_processo``.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador, meu_css, opcoes
from hefesto_dualsense4unix.mods import supervisor as sup
from hefesto_dualsense4unix.mods import tema as tm
from hefesto_dualsense4unix.mods.instalador import Lugares
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import exigir_caixa_do_bwrap
from tests.unit.test_as_modificacoes_rodam_fora_do_daemon import curto
from tests.unit.test_o_tema_por_escolha_importa_e_personaliza import _manifesto, _pasta

__all__ = ["curto"]

HOSTIL = "body > *{visibility:hidden}\n.permissoes{display:none}\n"
DA_PESSOA = ".a{color:#123456}\n"
CHAVE_DA_VERSAO = "versao"  # (noqa-acento)


@pytest.fixture
def lg(tmp_path: Path) -> Lugares:
    return Lugares(codigo=tmp_path / "codigo", dados=tmp_path / "dados",  # (noqa-acento)
                   registro=tmp_path / "config" / "mods.json", estado=tmp_path / "estado.json")


def _ligada(lg: Lugares, pasta: Path) -> Manifesto:
    resultado = instalador.instalar(str(pasta), lugares=lg)
    instalador.ligar(resultado.entrada.id, permissoes_vistas=resultado.manifesto.permissoes,
                     lugares=lg)
    return instalador.manifesto_instalado(resultado.entrada.id, lugares=lg)


def _com_processo(raiz: Path, mod_id: str, **mais: Any) -> Path:
    pasta = _pasta(raiz, _manifesto(mod_id, tipos=["tema", "processo"],
                                    processo={"executar": ["sh", "x.sh"]}, **mais))
    (pasta / "x.sh").write_text("exit 0\n", encoding="utf-8")
    return pasta


def _nova_versao(lg: Lugares, fonte: Path, manifesto: dict[str, Any]) -> None:
    (fonte / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    instalador.instalar(str(fonte), lugares=lg)


def _plantar(lg: Lugares, mod_id: str, opcoes_json: dict[str, Any], css: str) -> None:
    pasta = lg.dados / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "opcoes.json").write_text(json.dumps(opcoes_json), encoding="utf-8")
    (pasta / "meu.css").write_text(css, encoding="utf-8")


def test_o_que_e_da_pessoa_mora_ao_lado_do_registro(lg: Lugares) -> None:
    assert lg.da_pessoa == lg.registro.parent / "mods"
    assert Lugares.do_xdg().da_pessoa == instalador.xdg_paths.mods_da_pessoa_dir()
    assert meu_css.caminho("x", lg) == lg.da_pessoa / "x" / "meu.css"
    assert opcoes.caminho("x", lg) == lg.da_pessoa / "x" / "opcoes.json"
    assert not meu_css.caminho("x", lg).is_relative_to(lg.dados)


def test_o_css_plantado_em_dados_nao_veste_a_janela(lg: Lugares, tmp_path: Path) -> None:
    """Depois da mudança, o que a caixa planta em ``<dados>/<id>`` não chega à janela."""
    _ligada(lg, _com_processo(tmp_path, "tema-proc"))
    assert tm.tema_da_casa(lg).css == ""
    _plantar(lg, "tema-proc", {"meu_css": True}, HOSTIL)
    casa = tm.tema_da_casa(lg)
    assert casa.css == "" and not casa.recusa_do_css


def test_a_mudanca_nao_leva_o_css_da_extensao_com_processo(lg: Lugares, tmp_path: Path) -> None:
    """O plantado antes da primeira leitura: o ``opcoes.json`` muda sem o CSS ligado, e o
    ``meu.css`` fica para trás."""
    _ligada(lg, _com_processo(tmp_path, "tema-proc"))
    marca = lg.da_pessoa / instalador.MARCA_DA_MUDANCA_DA_PESSOA
    shutil.rmtree(lg.da_pessoa, ignore_errors=True)
    _plantar(lg, "tema-proc", {"meu_css": True, "tema": "Claro"}, HOSTIL)
    assert tm.tema_da_casa(lg).css == ""
    assert marca.exists()
    guardado = json.loads(opcoes.caminho("tema-proc", lg).read_text(encoding="utf-8"))
    assert guardado == {"tema": "Claro"}
    assert not meu_css.caminho("tema-proc", lg).exists()


def test_a_mudanca_nao_confia_na_extensao_que_ja_teve_processo(
        lg: Lugares, tmp_path: Path) -> None:
    """A versão de agora é só tema, mas a anterior guardada tinha processo: o que está em
    ``<dados>/<id>`` pode ter sido escrito pela caixa, e o ``meu.css`` fica para trás."""
    _ligada(lg, _pasta(tmp_path, _manifesto("tema-ex")))
    guarda = lg.codigo / ".tema-ex.anterior"
    guarda.mkdir(parents=True)
    (guarda / "hefesto-mod.json").write_text(json.dumps(_manifesto(
        "tema-ex", tipos=["tema", "processo"], processo={"executar": ["sh", "x.sh"]})),
        encoding="utf-8")
    shutil.rmtree(lg.da_pessoa, ignore_errors=True)
    _plantar(lg, "tema-ex", {"meu_css": True, "tema": "Claro"}, HOSTIL)
    assert tm.tema_da_casa(lg).css == ""
    assert not meu_css.caminho("tema-ex", lg).exists()
    guardado = json.loads(opcoes.caminho("tema-ex", lg).read_text(encoding="utf-8"))
    assert guardado == {"tema": "Claro"}


def test_a_marca_de_quem_ja_teve_processo_segura_a_mudanca_duas_versoes_depois(
        lg: Lugares, tmp_path: Path) -> None:
    """D-2611-A-MUDANCA-NAO-CONFIA-EM-QUEM-JA-TEVE-PROCESSO: instalada com processo e atualizada
    duas vezes sem processo, a versão guardada já não o mostra; a marca do registro, que a
    atualização nunca apaga, deixa para trás o ``meu.css`` plantado em ``<dados>/<id>``."""
    fonte = _com_processo(tmp_path, "tema-ex", **{CHAVE_DA_VERSAO: "1.0.0"})
    _ligada(lg, fonte)
    assert instalador.ler_registro(lg.registro)["tema-ex"].ja_teve_processo
    for numero in ("1.1.0", "1.2.0"):
        _nova_versao(lg, fonte, _manifesto("tema-ex", **{CHAVE_DA_VERSAO: numero}))
    assert instalador.ler_registro(lg.registro)["tema-ex"].ja_teve_processo
    guardada = json.loads((lg.codigo / ".tema-ex.anterior" / "hefesto-mod.json").read_text(
        encoding="utf-8"))
    assert guardada[CHAVE_DA_VERSAO] == "1.1.0"
    assert "processo" not in guardada
    shutil.rmtree(lg.da_pessoa, ignore_errors=True)
    shutil.rmtree(lg.dados / "tema-ex", ignore_errors=True)
    _plantar(lg, "tema-ex", {"meu_css": True, "tema": "Claro"}, HOSTIL)
    assert tm.tema_da_casa(lg).css == ""
    assert not meu_css.caminho("tema-ex", lg).exists()
    guardado = json.loads(opcoes.caminho("tema-ex", lg).read_text(encoding="utf-8"))
    assert guardado == {"tema": "Claro"}


def test_quem_nunca_teve_processo_nasce_sem_a_marca_e_leva_o_que_e_seu(
        lg: Lugares, tmp_path: Path) -> None:
    """A extensão só de tema, em versão nenhuma com processo, não ganha a marca na atualização."""
    fonte = _pasta(tmp_path, _manifesto("tema-puro", **{CHAVE_DA_VERSAO: "1.0.0"}))
    _ligada(lg, fonte)
    _nova_versao(lg, fonte, _manifesto("tema-puro", **{CHAVE_DA_VERSAO: "1.1.0"}))
    assert not instalador.ler_registro(lg.registro)["tema-puro"].ja_teve_processo


def test_a_extensao_com_preparo_conta_como_quem_escreveu_nos_dados(
        lg: Lugares, tmp_path: Path) -> None:
    so_tema = Manifesto.model_validate(_manifesto("t"))
    com_preparo = Manifesto.model_validate(_manifesto("t", preparar=["sh", "p.sh"]))
    entrada = instalador.Entrada(id="t", nome="T", versao="1.0.0", origem="local",
                                 endereco=str(tmp_path))
    assert not instalador._escreveu_nos_dados(lg, "t", so_tema, entrada)
    assert instalador._escreveu_nos_dados(lg, "t", com_preparo, entrada)
    aceito = entrada.model_copy(update={"preparo_aceito": ["sh", "p.sh"]})
    assert instalador._escreveu_nos_dados(lg, "t", so_tema, aceito)
    marcada = entrada.model_copy(update={"ja_teve_processo": True})
    assert instalador._escreveu_nos_dados(lg, "t", so_tema, marcada)


def test_o_css_herdado_pelo_substitui_nao_veste_a_janela(lg: Lugares, tmp_path: Path) -> None:
    antiga = {"id": "aa", "nome": "A", "versao": "1.0.0", "api": ">=2,<3",  # (noqa-acento)
              "licenca": "MIT", "tipos": ["processo"], "permissoes": [],  # (noqa-acento)
              "processo": {"executar": ["sh", "x.sh"]},
              "opcoes": [{"id": "meu_css", "rotulo": "CSS", "tipo": "ligado",  # (noqa-acento)
                          "padrao": False}]}  # (noqa-acento)
    pasta = _pasta(tmp_path, antiga)
    (pasta / "x.sh").write_text("exit 0\n", encoding="utf-8")
    _ligada(lg, pasta)
    opcoes.ler(instalador.manifesto_instalado("aa", lugares=lg), lg)
    _plantar(lg, "aa", {"meu_css": True}, HOSTIL)
    _ligada(lg, _pasta(tmp_path, _manifesto("bb", substitui=["aa"])))
    assert tm.tema_da_casa(lg).css == ""
    assert not meu_css.caminho("bb", lg).exists()


def test_o_css_da_pessoa_segue_valendo_depois_da_mudanca(lg: Lugares, tmp_path: Path) -> None:
    """A extensão de tema sem processo: o ``meu.css`` e a opção ligada mudam de pasta e valem."""
    nova = _ligada(lg, _pasta(tmp_path, _manifesto("tema-so")))
    shutil.rmtree(lg.da_pessoa, ignore_errors=True)
    _plantar(lg, "tema-so", {"meu_css": True}, DA_PESSOA)
    assert tm.tema_da_casa(lg).css == ".a{color:#123456 !important;}"
    assert meu_css.caminho("tema-so", lg).read_text(encoding="utf-8") == DA_PESSOA
    meu_css.caminho("tema-so", lg).write_text(".b{color:#654321}\n", encoding="utf-8")
    assert tm.tema_da_casa(lg).css == ".b{color:#654321 !important;}"
    opcoes.guardar(nova, "meu_css", False, lg)
    assert tm.tema_da_casa(lg).css == ""
    assert json.loads((lg.dados / "tema-so" / "opcoes.json").read_text(encoding="utf-8")) == {
        "meu_css": True}, "a extensão sem processo não ganha cópia"


def test_a_extensao_com_processo_le_a_copia_que_a_janela_nunca_le(
        lg: Lugares, tmp_path: Path) -> None:
    manifesto = _ligada(lg, _com_processo(tmp_path, "tema-proc"))
    opcoes.guardar(manifesto, "tema", "Claro", lg)
    copia = opcoes.copia_da_extensao("tema-proc", lg)
    assert copia.read_bytes() == opcoes.caminho("tema-proc", lg).read_bytes()
    copia.write_text(json.dumps({"tema": "Escuro", "meu_css": True}), encoding="utf-8")
    assert opcoes.ler(manifesto, lg)["tema"] == "Claro"
    assert opcoes.ler(manifesto, lg)["meu_css"] is False


def test_remover_deixa_so_o_meu_css_da_pessoa(lg: Lugares, tmp_path: Path) -> None:
    nova = _ligada(lg, _pasta(tmp_path, _manifesto("tema-so")))
    opcoes.guardar(nova, "meu_css", True, lg)
    meu_css.garantir("tema-so", lg)
    (lg.dados / "tema-so").mkdir(parents=True, exist_ok=True)
    assert instalador.remover("tema-so", lugares=lg, prazo=0.1) == []
    assert sorted(p.name for p in (lg.da_pessoa / "tema-so").iterdir()) == ["meu.css"]
    assert not (lg.dados / "tema-so").exists()
    assert instalador.o_css_que_fica("tema-so", lugares=lg) == meu_css.caminho("tema-so", lg)


def _manifesto_de_processo() -> Manifesto:
    return Manifesto.model_validate({
        "id": "exemplo", "nome": "Exemplo", "versao": "0.1.0", "api": ">=1,<3",  # (noqa-acento)
        "licenca": "MIT", "tipos": ["processo"], "processo": {"executar": ["python3", "m.py"]},
        "permissoes": [],  # (noqa-acento)
    })


def _linha(base: Path, comando: list[str]) -> tuple[list[str], Path, Path]:
    fonte, dados, casa, pessoa = base / "fonte", base / "dados", base / "casa", base / "pessoa"
    for pasta in (fonte, dados, casa, pessoa):
        pasta.mkdir(exist_ok=True)
    porta = base / "porta.sock"
    porta.touch()
    argv = sup.comando_na_caixa(bwrap=shutil.which("bwrap") or "bwrap", comando=comando,
                                codigo=fonte, dados=dados, da_pessoa=pessoa, porta=porta,
                                manifesto=_manifesto_de_processo(), casa=casa, execucao=())
    return argv, dados, pessoa


def test_a_caixa_recebe_o_que_e_da_pessoa_so_de_leitura(curto: Path) -> None:
    argv, dados, pessoa = _linha(curto, ["true"])
    pares = list(zip(argv, argv[1:], argv[2:], strict=False))
    assert ("--ro-bind", str(pessoa), sup.OPCOES_NA_CAIXA) in pares
    assert not any(a in ("--bind", "--bind-try") and b == str(pessoa) for a, b, _ in pares)
    assert ("--bind", str(dados), str(dados)) in pares


_ESCREVER = """
import json, sys
fora = {}
for alvo in sys.argv[1:]:
    try:
        with open(alvo, "w") as arquivo:
            arquivo.write("x")
        fora[alvo] = "gravou"
    except OSError as e:
        fora[alvo] = e.__class__.__name__
print(json.dumps(fora))
"""


def test_de_dentro_da_caixa_escrever_no_que_e_da_pessoa_falha(curto: Path) -> None:
    exigir_caixa_do_bwrap()
    alvo_da_pessoa = Path(sup.OPCOES_NA_CAIXA) / "opcoes.json"
    alvo_dos_dados = curto / "dados" / "opcoes.json"
    argv, _dados, pessoa = _linha(curto, [sys.executable, "-c", _ESCREVER,
                                          str(alvo_da_pessoa), str(alvo_dos_dados)])
    (pessoa / "opcoes.json").write_text("{}", encoding="utf-8")
    feito = subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)
    assert feito.returncode == 0, feito.stderr
    visto = json.loads(feito.stdout)
    assert visto[str(alvo_da_pessoa)] != "gravou", visto
    assert visto[str(alvo_dos_dados)] == "gravou", visto
    assert (pessoa / "opcoes.json").read_text(encoding="utf-8") == "{}"
