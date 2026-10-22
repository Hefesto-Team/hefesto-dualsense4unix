"""O tema da extensão escolhe o lado dos botões da janela
(O-TEMA-DA-EXTENSAO-ESCOLHE-O-LADO-DOS-BOTOES-DA-JANELA-01).

Medido em 22/10/2026: os três botões da barra saíam SEMPRE à esquerda, para todo usuário
(`pack_start` no `montar_a_barra`), e o bloco `tema` do manifesto só trocava cores. Agora o produto
segue o lado do sistema (no COSMIC, à direita: minimizar, maximizar, fechar) e o bloco `tema`
pode dizer `botoes` (`esquerda`: fechar, maximizar, minimizar). Cor e lado se ligam, cada um, a
uma opção `ligado` da extensão (`cor_pela_opcao`, `botoes_pela_opcao`).

A barra montada aqui é a do produto, num `Gtk.OffscreenWindow` sob a tela de mentira, e a posição é
a alocação que o GTK dá; o registro, os dados e o código da extensão ficam num `XDG_*` de mentira.

MORDIDAS (executadas em 22/10/2026):
- com o `botoes=` do `tema_da_casa` arrancado (sempre vazio), `test_o_lado_da_extensao_vale_...`
  e a fase «extensão» da sonda reprovam;
- com o `por_os_botoes_no_lado` empacotando sempre com `pack_start`, a fase «sem extensão» da
  sonda reprova (os três saem na esquerda no COSMIC);
- sem o vínculo `botoes_pela_opcao` lido (`_opcao_ligada` sempre verdadeira), desligar a opção
  não devolve o lado do sistema e `test_cada_escolha_se_liga_a_sua_opcao` reprova.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.mods import instalador, opcoes
from hefesto_dualsense4unix.mods import tema as tm
from hefesto_dualsense4unix.mods.manifesto import Manifesto
from tests.conftest import skip_sem_gi_real

#: O tema claro de fundos, textos e acentos, na régua de contraste da casa.
TEMA_CLARO = (":root{--app-bg:#eef0f5;--panel:#ffffff;--elevated:#f5f6fa;--fg:#1c1e29;"
              "--texto-suave:#383c4c;--texto-mudo:#545a70;--comment:#4a5486;"
              "--fundo-da-pagina:#dde1ea;--green:#1d7a3c;--cyan:#006d85;--purple:#6a3dc2;"
              "--orange:#a35200;--pink:#ad2f6c;--red:#c01f2e;--yellow:#7a6400}")

OPCOES = [
    {"id": "cores_claras", "rotulo": "Cores claras", "tipo": "ligado",
     "padrao": True},  # (noqa-acento)
    {"id": "botoes_a_esquerda", "rotulo": "Botões à esquerda", "tipo": "ligado",
     "padrao": True},  # (noqa-acento)
]
BLOCO = {"arquivo": "tema.css", "botoes": "esquerda", "cor_pela_opcao": "cores_claras",
         "botoes_pela_opcao": "botoes_a_esquerda"}

BASE = {"id": "tema-x", "nome": "Tema X", "api": ">=2,<3", "licenca": "MIT",
        "versao": "1.0.0",  # (noqa-acento)
        "tipos": ["tema"],
        "permissoes": ["tema"]}  # (noqa-acento)


def _lugares(raiz: Path) -> instalador.Lugares:
    return instalador.Lugares(codigo=raiz / "codigo",  # (noqa-acento)
                              dados=raiz / "dados",
                              registro=raiz / "mods.json", estado=raiz / "estado.json")


def _instalada(lg: instalador.Lugares, mod_id: str, bloco: dict[str, Any], *,
               opcoes_do_manifesto: list[dict[str, Any]] | None = None, ligada: bool = True,
               ligada_em: str = "2026-10-22T10:00:00") -> None:
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "tema.css").write_text(TEMA_CLARO, encoding="utf-8")
    opcoes_dele = OPCOES if opcoes_do_manifesto is None else opcoes_do_manifesto
    manifesto = {**BASE, "id": mod_id, "nome": f"Tema {mod_id}", "tema": bloco,
                 "opcoes": opcoes_dele}  # (noqa-acento)
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[mod_id] = instalador.Entrada(
        id=mod_id, nome=f"Tema {mod_id}", versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=["tema"], ligada=ligada, ligada_em=ligada_em)
    instalador.gravar_registro(lg.registro, registro)


def _escolher(lg: instalador.Lugares, mod_id: str, opcao: str, valor: bool) -> None:
    manifesto = instalador.manifesto_instalado(mod_id, lugares=lg)
    opcoes.guardar(manifesto, opcao, valor, lg)


# --- a régua do manifesto ------------------------------------------------------------------


def _manifesto(bloco: dict[str, Any], opcoes_do_manifesto: list[dict[str, Any]] | None = None
               ) -> Manifesto:
    return Manifesto.model_validate({
        **BASE, "tema": bloco,
        "opcoes": OPCOES if opcoes_do_manifesto is None else opcoes_do_manifesto})  # (noqa-acento)


def test_a_regua_aceita_o_lado_a_cor_e_o_vinculo() -> None:
    assert _manifesto(BLOCO).tema == BLOCO
    assert _manifesto({"botoes": "direita"}).tema == {"botoes": "direita"}
    assert _manifesto({"arquivo": "tema.css"}).tema == {"arquivo": "tema.css"}


@pytest.mark.parametrize("bloco, motivo", [
    ({"botoes": "centro"}, "tema.botoes é esquerda ou direita"),
    ({"botoes": ["esquerda"]}, "tema.botoes é esquerda ou direita"),
    ({"botoes": "esquerda", "botoes_pela_opcao": "nao_existe"}, "que não existe"),
    ({"arquivo": "tema.css", "cor_pela_opcao": "nao_existe"}, "que não existe"),
    ({"botoes": "esquerda", "botoes_pela_opcao": 3}, "que não existe"),
    ({"botoes": "esquerda", "botoes_pela_opcao": "gravidade"}, "precisa ser do tipo ligado"),
    ({"arquivo": "tema.css", "cor_pela_opcao": "gravidade"}, "precisa ser do tipo ligado"),
    ({"arquivo": "tema.css", "botoes_pela_opcao": "botoes_a_esquerda"},
     "liga uma escolha que o bloco tema não faz"),
    ({"botoes": "esquerda", "cor_pela_opcao": "cores_claras"},
     "liga uma escolha que o bloco tema não faz"),
])
def test_a_regua_recusa_lado_invalido_e_vinculo_torto(bloco: dict[str, Any], motivo: str) -> None:
    com_gravidade = [*OPCOES, {"id": "gravidade", "rotulo": "Gravidade", "tipo": "numero"}]
    with pytest.raises(ValueError, match=motivo):
        _manifesto(bloco, com_gravidade)


# --- o tema ligado diz a cor e o lado, cada um pela sua opção ---------------------------------


def test_sem_extensao_nao_ha_lado_do_tema(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    assert tm.tema_da_casa(lg) == tm.TemaDaCasa()
    assert tm.tema_da_casa(lg).botoes == ""


def test_o_lado_da_extensao_vale_com_o_tema_ligado(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "claro", BLOCO)
    agora = tm.tema_da_casa(lg)
    assert agora.botoes == "esquerda" and agora.de == "claro", agora
    assert "--app-bg:#eef0f5 !important" in agora.folha, agora.folha


def test_cada_escolha_se_liga_a_sua_opcao(tmp_path: Path) -> None:
    # D-2210-O-LADO-DOS-BOTOES-E-DO-TEMA.
    lg = _lugares(tmp_path)
    _instalada(lg, "claro", BLOCO)
    _escolher(lg, "claro", "botoes_a_esquerda", False)
    so_cor = tm.tema_da_casa(lg)
    assert so_cor.botoes == "" and so_cor.folha, so_cor
    _escolher(lg, "claro", "botoes_a_esquerda", True)
    _escolher(lg, "claro", "cores_claras", False)
    so_lado = tm.tema_da_casa(lg)
    assert so_lado.botoes == "esquerda" and so_lado.folha == "" and so_lado.de == "claro", so_lado
    _escolher(lg, "claro", "botoes_a_esquerda", False)
    assert tm.tema_da_casa(lg) == tm.TemaDaCasa()


def test_o_bloco_so_com_o_lado_liga_sem_cor_nenhuma(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "so-lado", {"botoes": "esquerda"}, opcoes_do_manifesto=[])
    agora = tm.tema_da_casa(lg)
    assert agora.botoes == "esquerda" and agora.folha == "" and not agora.recusa, agora
    # o «ligar» não pede folha a quem não traz cor
    _instalada(lg, "so-lado", {"botoes": "esquerda"}, opcoes_do_manifesto=[], ligada=False)
    assert instalador.ligar("so-lado", permissoes_vistas=["tema"], lugares=lg).ligada is True


def test_a_extensao_de_so_cor_nao_diz_lado(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "so-cor", {"arquivo": "tema.css"}, opcoes_do_manifesto=[])
    agora = tm.tema_da_casa(lg)
    assert agora.botoes == "" and agora.folha, agora


def test_duas_extensoes_com_lados_diferentes_valem_a_ultima_ligada(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "uma", {"botoes": "esquerda"}, opcoes_do_manifesto=[],
               ligada_em="2026-10-22T10:00:00")
    _instalada(lg, "outra", {"botoes": "direita"}, opcoes_do_manifesto=[],
               ligada_em="2026-10-22T11:00:00")
    agora = tm.tema_da_casa(lg)
    assert agora.botoes == "direita" and agora.de == "outra", agora
    assert agora.avisos == ("«Tema uma» também escolhe o lado dos botões, e vale o da "
                            "«Tema outra».",), agora.avisos


def test_a_extensao_desligada_devolve_o_lado_do_sistema(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "claro", BLOCO)
    assert tm.tema_da_casa(lg).botoes == "esquerda"
    instalador.desligar("claro", lugares=lg)
    assert tm.tema_da_casa(lg) == tm.TemaDaCasa()


def test_o_tema_da_cor_recusado_nao_leva_o_lado_junto_para_baixo(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "claro", BLOCO)
    (lg.codigo / "claro" / "tema.css").write_text(":root{--texto-mudo:#3c3e4c}", encoding="utf-8")
    agora = tm.tema_da_casa(lg)
    assert agora.folha == "" and agora.recusa.startswith("O tema de «Tema claro» não ligou.")
    assert agora.botoes == "esquerda", "a cor reprovada não tira o lado que a pessoa escolheu"


def test_as_opcoes_vigiadas_sao_as_dos_temas_ligados(tmp_path: Path) -> None:
    lg = _lugares(tmp_path)
    _instalada(lg, "claro", BLOCO)
    _instalada(lg, "desligado", BLOCO, ligada=False)
    assert tm.arquivos_de_opcoes_dos_temas(lg) == [opcoes.caminho("claro", lg)]


# --- a barra na tela: o lado do sistema, o da extensão, e a troca sem reabrir -----------------

_SONDA = r"""
import json, os, pathlib, sys, time, types
from hefesto_dualsense4unix.utils.tela_de_mentira import garantir_tela_de_mentira
garantir_tela_de_mentira(anunciar=False)
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk
from types import SimpleNamespace
from hefesto_dualsense4unix.interface import janela
from hefesto_dualsense4unix.mods import instalador, opcoes  # (noqa-acento)

raiz = pathlib.Path(os.environ["SONDA_RAIZ"])
bloco = json.loads(os.environ["SONDA_BLOCO"])
lg = instalador.Lugares.do_xdg()

def girar(segundos=0.4):
    # o relógio de quadros do GTK anda com o tempo: sem esperar, a nova alocação não sai
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(0.01)

def medir(barra, botoes):
    girar()
    largura = barra.get_allocation().width
    x = {g: b.get_allocation().x for g, b in botoes.items()}
    w = {g: b.get_allocation().width for g, b in botoes.items()}
    return {"ordem": sorted(x, key=x.__getitem__),
            "esquerda": all(x[g] + w[g] < largura // 4 for g in x),
            "direita": all(x[g] > largura * 3 // 4 for g in x), "largura": largura}

lado = janela.lado_dos_botoes()
barra, botoes = janela.montar_a_barra("Hefesto", "", lambda *_: None, lado=lado)
tela = Gtk.OffscreenWindow()
tela.set_default_size(janela.LARGURA_DO_DESENHO, 39)
tela.add(barra)
tela.show_all()
fases = {"sem extensao": {"lado": lado, **medir(barra, botoes)}}  # (noqa-acento)

# a barra montada SEM o lado pergunta ao sistema
b2, bt2 = janela.montar_a_barra("Hefesto", "", lambda *_: None)
t2 = Gtk.OffscreenWindow(); t2.set_default_size(janela.LARGURA_DO_DESENHO, 39); t2.add(b2)
t2.show_all()
fases["sem lado dito"] = medir(b2, bt2)

# a extensão entra no registro e o lado vale na MESMA barra, sem reabrir
pasta = lg.codigo / "claro"
pasta.mkdir(parents=True)
(pasta / "tema.css").write_text(os.environ["SONDA_TEMA"], encoding="utf-8")
manifesto = json.loads(os.environ["SONDA_MANIFESTO"])
(pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
registro = {"claro": instalador.Entrada(
    id="claro", nome="Tema claro", versao="1.0.0", origem="local", endereco=str(pasta),
    permissoes_aceitas=["tema"], ligada=True, ligada_em="2026-10-22T10:00:00")}
instalador.gravar_registro(lg.registro, registro)

# os vigias das opções: o arquivo ainda nem existe, e a escolha dele acorda a janela
avisos = []
quem = SimpleNamespace(_vigias_das_opcoes=[],
                       _o_registro_das_extensoes_mudou=lambda *a: avisos.append("cor"),
                       _o_lado_dos_botoes_pode_ter_mudado=lambda *a: avisos.append("lado"))
for nome in ("_vigiar_as_opcoes_dos_temas", "_o_nivel_de_baixo_nasceu"):
    setattr(quem, nome, types.MethodType(getattr(janela.JanelaDaAba, nome), quem))
quem._vigiar_as_opcoes_dos_temas()

def refazer():
    lado = janela.lado_dos_botoes()
    janela.por_os_botoes_no_lado(barra, botoes, lado)
    return {"lado": lado, **medir(barra, botoes)}

fases["extensao"] = refazer()  # (noqa-acento)
m = instalador.manifesto_instalado("claro", lugares=lg)
opcoes.guardar(m, "botoes_a_esquerda", False, lg)
girar()
fases["opcao desligada"] = refazer()  # (noqa-acento)
fases["vigia acordou"] = sorted(set(avisos))
opcoes.guardar(m, "botoes_a_esquerda", True, lg)
fases["opcao ligada"] = refazer()  # (noqa-acento)
instalador.desligar("claro", lugares=lg)
fases["extensao desligada"] = refazer()  # (noqa-acento)
print(json.dumps(fases))
"""


@pytest.fixture(scope="module")
def fases(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Any]:
    raiz = tmp_path_factory.mktemp("lado")
    manifesto = {**BASE, "id": "claro", "nome": "Tema claro", "tema": BLOCO,
                 "opcoes": OPCOES}  # (noqa-acento)
    ambiente = dict(
        os.environ, PYTHONDONTWRITEBYTECODE="1", SONDA_RAIZ=str(raiz),
        SONDA_BLOCO=json.dumps(BLOCO), SONDA_TEMA=TEMA_CLARO,
        SONDA_MANIFESTO=json.dumps(manifesto), XDG_CURRENT_DESKTOP="COSMIC",
        XDG_CONFIG_HOME=str(raiz / "config"), XDG_DATA_HOME=str(raiz / "dados"),
        XDG_STATE_HOME=str(raiz / "estado"))
    filho = subprocess.run([sys.executable, "-c", _SONDA], env=ambiente,
                           capture_output=True, text=True, timeout=180)
    if filho.returncode != 0:
        # só a falta de tela pula; qualquer outro erro da sonda é vermelho, e não silêncio
        if "display" not in filho.stderr.lower():
            pytest.fail(f"a sonda quebrou: {filho.stderr.strip()[-600:]}")
        pytest.skip(f"a barra não subiu na tela de mentira: {filho.stderr.strip()[-400:]}")
    return dict(json.loads(filho.stdout.strip().splitlines()[-1]))


DA_DIREITA = ["minimizar", "maximizar", "fechar"]
DA_ESQUERDA = ["fechar", "maximizar", "minimizar"]


@skip_sem_gi_real
def test_sem_extensao_a_barra_sai_do_lado_do_sistema(fases: dict[str, Any]) -> None:
    """No COSMIC, à direita: minimizar, maximizar, fechar."""
    for chave in ("sem extensao", "sem lado dito"):  # (noqa-acento)
        f = fases[chave]
        assert f["ordem"] == DA_DIREITA and f["direita"] and not f["esquerda"], (chave, f)
    assert fases["sem extensao"]["lado"] == "direita", fases  # (noqa-acento)


@skip_sem_gi_real
def test_com_a_extensao_a_mesma_barra_vai_para_a_esquerda_na_ordem_dela(
        fases: dict[str, Any]) -> None:
    f = fases["extensao"]  # (noqa-acento)
    assert f["lado"] == "esquerda", f
    assert f["ordem"] == DA_ESQUERDA and f["esquerda"] and not f["direita"], f


@skip_sem_gi_real
def test_desligar_a_opcao_ou_a_extensao_devolve_o_lado_sem_reabrir(fases: dict[str, Any]) -> None:
    for chave in ("opcao desligada", "extensao desligada"):  # (noqa-acento)
        f = fases[chave]
        assert f["lado"] == "direita", (chave, f)
        assert f["ordem"] == DA_DIREITA and f["direita"], (chave, f)
    f = fases["opcao ligada"]  # (noqa-acento)
    assert f["lado"] == "esquerda" and f["ordem"] == DA_ESQUERDA, f


@skip_sem_gi_real
def test_a_escolha_da_opcao_acorda_a_janela_sem_o_arquivo_antes(fases: dict[str, Any]) -> None:
    """A opção grava `opcoes.json` por `rename`, e o arquivo nem existia quando a janela abriu."""
    assert fases["vigia acordou"] == ["cor", "lado"], fases["vigia acordou"]


@skip_sem_gi_real
def test_o_lado_do_sistema_fora_do_cosmic_segue_o_button_layout(
        monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import tema_da_sessao as sessao

    for chave in ("XDG_CURRENT_DESKTOP", "XDG_SESSION_DESKTOP", "DESKTOP_SESSION"):
        monkeypatch.delenv(chave, raising=False)
    for layout, esperado in (("close,minimize,maximize:", "esquerda"),
                             ("appmenu:minimize,maximize,close", "direita"),
                             (":minimize,maximize,close", "direita"),
                             ("", "direita"), ("close", "direita")):
        monkeypatch.setattr(sessao, "lado_dos_botoes_na_sessao", lambda dito=layout: dito)
        assert sessao.lado_do_sistema() == esperado, layout
    monkeypatch.setenv("XDG_CURRENT_DESKTOP", "COSMIC")
    monkeypatch.setattr(sessao, "lado_dos_botoes_na_sessao", lambda: "close:")
    assert sessao.lado_do_sistema() == "direita", "no COSMIC a sessão não é consultada"


@skip_sem_gi_real
def test_o_registro_que_muda_leva_os_botoes_ao_lado_novo(monkeypatch: pytest.MonkeyPatch) -> None:
    from hefesto_dualsense4unix.interface import janela

    quem = SimpleNamespace(_lado="direita", _barra=None, _botoes_da_barra={})
    quem.trocar_o_lado = lambda lado: janela.JanelaDaAba.trocar_o_lado(quem, lado)  # type: ignore[attr-defined]
    # o monkeypatch devolve a função: recarregar o módulo trocaria as classes de quem já o importou
    monkeypatch.setattr(janela, "lado_dos_botoes", lambda: "esquerda")
    janela.JanelaDaAba._o_lado_dos_botoes_pode_ter_mudado(quem)  # type: ignore[arg-type]
    assert quem._lado == "esquerda"
