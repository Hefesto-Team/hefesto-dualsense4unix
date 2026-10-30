"""O estilo Adulto só aparece com a extensão que o pede, instalada e ligada.

O-ESTILO-ADULTO-SO-APARECE-COM-A-EXTENSAO-QUE-O-PEDE-01 (30/10/2026). O manifesto ganha
``estilos: [chave]`` e o catálogo marca o estilo que só aparece quando pedido
(``so_quando_pedido``). A tela (a lista do «Estilo de jogo» da Perfis e os moldes da Navegação e
do Mapa do controle) oferece esse estilo só com uma extensão ligada que o pede; desligada esconde
igual a desinstalada. O perfil que já guarda o estilo carrega sem erro, o motor segue o arquivo e
o editor desse perfil o mostra escolhido (D-3010-O-ESTILO-PEDIDO-SO-APARECE-COM-A-EXTENSAO-LIGADA,
D-3010-O-PERFIL-QUE-GUARDA-O-ESTILO-PEDIDO-O-MANTEM).

MORDIDAS (30/10/2026, executadas sobre a cura e devolvidas):

- o ``estilos_a_vista`` que devolve o catálogo inteiro reprova a lista sem extensão;
- o ``estilos_pedidos`` sem o ``if not entrada.ligada`` reprova a extensão desligada;
- o gesto sem a recusa do estilo fora da vista grava o Adulto sem extensão;
- o ``estilos_a_vista`` sem o guardado tira o Adulto do perfil que já o tem;
- cada recusa do manifesto arrancada reprova o seu caso;
- o ``moldes_a_vista`` que devolve todos reprova o molde do Mapa e o da Navegação;
- o gesto da Navegação sem a recusa grava o molde sem a extensão;
- o gesto da Navegação que ignora o pedido recusa o molde com a extensão ligada;
- o Mapa sem o molde que a Navegação guarda abre em «Navegar» e recusa o seu molde;
- o ``estilos_a_vista`` que esconde só o Adulto pelo nome reprova o outro estilo pedido;
- a marca dos pedidos fixa (a lista que não muda com a janela aberta) reprova oito casos;
- o leitor do manifesto sem a recusa por valor derruba o pedido da extensão vizinha.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.interface.pacotes import Contexto, a06_navegacao, a10_perfis
from hefesto_dualsense4unix.interface.pacotes import a13_mapa_do_controle as a13
from hefesto_dualsense4unix.mods import instalador
from hefesto_dualsense4unix.mods.manifesto import (
    Manifesto,
    ManifestoRecusadoError,
    estilos_pedidos,
    ler_manifesto,
)
from hefesto_dualsense4unix.profiles import estilos_de_jogo, loader
from hefesto_dualsense4unix.profiles.schema import MatchCriteria, Profile

ADULTO = "adulto"
ROTULO = "Adulto"
NOITE = "Noite"
TARDE = "Tarde"
BASE: dict[str, Any] = {"id": "pede", "nome": "Pede", "api": ">=2,<3", "tipos": ["tema"],
                        "tema": {}}
BASE["versao"] = "1.0.0"  # (noqa-acento)
BASE["licenca"] = "MIT"  # (noqa-acento)


class PonteDeMentira:
    def profile_switch(self, nome: str) -> bool:
        return True

    def profile_reaplicar(self, nome: str, *, prender: bool = False) -> bool:
        return True

    def chamar(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return True

    def resultado(self, metodo: str, *a: Any, **kw: Any) -> Any:
        return {}


@pytest.fixture
def lg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> instalador.Lugares:
    lugares = instalador.Lugares(codigo=tmp_path / "codigo",  # (noqa-acento)
                                 dados=tmp_path / "dados", registro=tmp_path / "mods.json",
                                 estado=tmp_path / "estado.json")
    monkeypatch.setattr(instalador.Lugares, "do_xdg", classmethod(lambda cls: lugares))
    for nome, valor in (("_ESCOLHIDO", ""), ("_ARMADO", None), ("_PROCURA", ""),
                        ("_PINTADO_PARA", ""), ("_ULTIMO_TIQUE", 0.0),
                        ("_RECUSA_DO_JOGO", ("", ""))):
        monkeypatch.setattr(a10_perfis, nome, valor, raising=False)
    monkeypatch.setattr(a13, "_EDITANDO", {}, raising=False)
    return lugares


def _instalada(lg: instalador.Lugares, *, estilos: list[str] | None = None,
               ligada: bool = True, mod_id: str = "pede") -> None:
    pasta = lg.codigo / mod_id
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto = {**BASE, "id": mod_id, "estilos": [ADULTO] if estilos is None else estilos}
    (pasta / "hefesto-mod.json").write_text(json.dumps(manifesto), encoding="utf-8")
    registro = instalador.ler_registro(lg.registro)
    registro[mod_id] = instalador.Entrada(
        id=mod_id, nome="Pede", versao="1.0.0", origem="local", endereco=str(pasta),
        permissoes_aceitas=[], ligada=ligada, ligada_em="2026-10-30T10:00:00")
    instalador.gravar_registro(lg.registro, registro)


def _ctx() -> Contexto:
    return Contexto(state={"active_profile": NOITE}, mesa=[], conectados=[], estados={})


def _o_disco() -> None:
    loader.save_profile(Profile(name=NOITE, match=MatchCriteria(window_class=["noite"]),
                                estilo=ADULTO), origem="régua")
    loader.save_profile(Profile(name=TARDE, match=MatchCriteria(window_class=["tarde"])),
                        origem="régua")


def _opcoes_do_estilo(nome: str) -> list[tuple[str, str]]:
    a10_perfis.selecionar(_ctx(), {"hefPerfil": nome}, PonteDeMentira())
    bloco = a10_perfis.pacote(_ctx())["blocos"][a10_perfis.SELETOR_DOS_ESTILOS]
    return re.findall(r"<option([^>]*)>([^<]*)</option>", bloco)


def _rotulos(opcoes: list[tuple[str, str]]) -> list[str]:
    return [texto for _atr, texto in opcoes]


def _escolhido(opcoes: list[tuple[str, str]]) -> list[str]:
    return [texto for atr, texto in opcoes if "selected" in atr]


def test_o_manifesto_aceita_o_estilo_que_se_pede() -> None:
    assert Manifesto.model_validate({**BASE, "estilos": [ADULTO]}).estilos == [ADULTO]
    assert Manifesto.model_validate(BASE).estilos == [], "sem o campo, nenhum pedido"


@pytest.mark.parametrize(("estilos", "frase"), [
    (["boliche"], "«boliche» não é um estilo de jogo"),
    (["fps"], "o estilo «fps» aparece sempre e não se pede"),
    ([ADULTO, ADULTO], "estilo repetido"),
])
def test_o_manifesto_recusa(tmp_path: Path, estilos: list[str], frase: str) -> None:
    (tmp_path / "hefesto-mod.json").write_text(json.dumps({**BASE, "estilos": estilos}),
                                               encoding="utf-8")
    with pytest.raises(ManifestoRecusadoError, match=re.escape(frase)):
        ler_manifesto(tmp_path)


def test_so_a_extensao_ligada_pede(lg: instalador.Lugares) -> None:
    """D-3010-O-ESTILO-PEDIDO-SO-APARECE-COM-A-EXTENSAO-LIGADA."""
    assert estilos_pedidos() == frozenset(), "sem extensão, nada se pede"
    _instalada(lg, ligada=False)
    assert estilos_pedidos() == frozenset(), "a desligada esconde igual à desinstalada"
    _instalada(lg)
    assert estilos_pedidos() == {ADULTO}
    _instalada(lg, estilos=[])
    assert estilos_pedidos() == frozenset(), "o manifesto novo, sem o pedido, esconde de novo"


def test_o_manifesto_que_nao_abre_nao_pede(lg: instalador.Lugares) -> None:
    _instalada(lg)
    (lg.codigo / "pede" / "hefesto-mod.json").write_text("{", encoding="utf-8")
    assert estilos_pedidos() == frozenset()


def test_o_catalogo_marca_so_o_adulto_e_o_motor_segue_com_ele() -> None:
    assert {ADULTO} == estilos_de_jogo.PEDIVEIS
    assert ROTULO not in [e.rotulo for e in estilos_de_jogo.estilos_a_vista()]
    assert ROTULO in [e.rotulo for e in estilos_de_jogo.estilos_a_vista({ADULTO})]
    assert ROTULO in [e.rotulo for e in estilos_de_jogo.estilos_a_vista(guardado=ADULTO)]
    assert estilos_de_jogo.estilo_que_pinta(ADULTO) is estilos_de_jogo.POR_CHAVE[ADULTO]


def test_sem_extensao_a_lista_nao_oferece_o_adulto(lg: instalador.Lugares) -> None:
    _o_disco()
    opcoes = _opcoes_do_estilo(TARDE)
    assert ROTULO not in _rotulos(opcoes)
    assert _rotulos(opcoes)[:2] == ["—", "Nativo"] and _rotulos(opcoes)[-1] == "Personalizado"
    assert _escolhido(opcoes) == ["—"], "sem estilo guardado, o travessão abre a lista"
    assert 'data-dica="O jogo decide"' in opcoes[1][0]


def test_com_a_extensao_ligada_a_lista_oferece_e_desligada_esconde(
        lg: instalador.Lugares) -> None:
    """D-3010-O-ESTILO-PEDIDO-SO-APARECE-COM-A-EXTENSAO-LIGADA."""
    _o_disco()
    _instalada(lg)
    assert ROTULO in _rotulos(_opcoes_do_estilo(TARDE))
    _instalada(lg, ligada=False)
    assert ROTULO not in _rotulos(_opcoes_do_estilo(TARDE))


def test_o_perfil_que_guarda_o_adulto_carrega_e_o_mostra(lg: instalador.Lugares) -> None:
    """D-3010-O-PERFIL-QUE-GUARDA-O-ESTILO-PEDIDO-O-MANTEM."""
    _o_disco()
    assert loader.load_profile(NOITE).estilo == ADULTO, "a escolha de quem usa não se apaga"
    opcoes = _opcoes_do_estilo(NOITE)
    assert _escolhido(opcoes) == [ROTULO], "a tela diz o estilo que o perfil guarda"
    assert ROTULO not in _rotulos(_opcoes_do_estilo(TARDE)), "o Adulto vazou para outro perfil"


def test_o_gesto_recusa_o_adulto_sem_a_extensao(lg: instalador.Lugares) -> None:
    _o_disco()
    a10_perfis.selecionar(_ctx(), {"hefPerfil": TARDE}, PonteDeMentira())
    with pytest.raises(RuntimeError, match="só aparece com a extensão"):
        a10_perfis.editor_estilo(_ctx(), {"valor": ROTULO}, PonteDeMentira())
    assert loader.load_profile(TARDE).estilo is None


def test_o_gesto_grava_o_adulto_com_a_extensao(lg: instalador.Lugares) -> None:
    _o_disco()
    _instalada(lg)
    a10_perfis.selecionar(_ctx(), {"hefPerfil": TARDE}, PonteDeMentira())
    a10_perfis.editor_estilo(_ctx(), {"valor": ROTULO}, PonteDeMentira())
    assert loader.load_profile(TARDE).estilo == ADULTO


def test_trocar_o_estilo_do_perfil_sem_a_extensao_tira_o_adulto_da_lista(
        lg: instalador.Lugares) -> None:
    """D-3010-O-PERFIL-QUE-GUARDA-O-ESTILO-PEDIDO-O-MANTEM."""
    _o_disco()
    a10_perfis.selecionar(_ctx(), {"hefPerfil": NOITE}, PonteDeMentira())
    a10_perfis.editor_estilo(_ctx(), {"valor": "Terror"}, PonteDeMentira())
    assert loader.load_profile(NOITE).estilo == "terror"
    opcoes = _opcoes_do_estilo(NOITE)
    assert ROTULO not in _rotulos(opcoes) and _escolhido(opcoes) == ["Terror"]


def _moldes(html: str) -> list[str]:
    grupo = re.search(r'<optgroup label="Moldes">(.*?)</optgroup>', html, flags=re.S)
    return re.findall(r">([^<]+)</option>", grupo.group(1) if grupo else html)


def test_o_molde_do_mapa_so_aparece_com_a_extensao(lg: instalador.Lugares) -> None:
    ctx = _ctx()
    assert ROTULO not in _moldes(a13._opcoes_do_perfil(ctx))
    assert not a13._chave_valida(ctx, f"{a13.MOLDE}{ADULTO}")
    _instalada(lg)
    assert ROTULO in _moldes(a13._opcoes_do_perfil(ctx))
    assert a13._chave_valida(ctx, f"{a13.MOLDE}{ADULTO}")


def test_o_molde_da_navegacao_so_aparece_com_a_extensao_ou_escolhido(
        lg: instalador.Lugares) -> None:
    molde = f"{a06_navegacao.PREFIXO_DO_MOLDE}{ADULTO}"
    outro = f"{a06_navegacao.PREFIXO_DO_MOLDE}point_and_click"
    assert ROTULO not in _moldes(a06_navegacao._opcoes_dos_moldes(outro))
    assert ROTULO in _moldes(a06_navegacao._opcoes_dos_moldes(molde)), (
        "o molde já escolhido sumiu da lista")
    with pytest.raises(ValueError, match="só aparece com a extensão"):
        a06_navegacao.point_and_click_perfil(Contexto(state={}, mesa=[], conectados=[],
                                                      estados={}),
                                             {"valor": molde}, PonteDeMentira())
    _instalada(lg)
    assert ROTULO in _moldes(a06_navegacao._opcoes_dos_moldes(outro))
    a06_navegacao.point_and_click_perfil(Contexto(state={}, mesa=[], conectados=[], estados={}),
                                         {"valor": molde}, PonteDeMentira())
    a06_navegacao._A_MAQUINA = None
    assert a06_navegacao._o_point_and_click_de_hoje() == molde


def test_o_mapa_abre_no_molde_que_a_navegacao_guarda_sem_a_extensao(
        lg: instalador.Lugares, monkeypatch: pytest.MonkeyPatch) -> None:
    """D-3010-O-PERFIL-QUE-GUARDA-O-ESTILO-PEDIDO-O-MANTEM: o molde escolhido na Navegação segue
    na lista do Mapa, que é a página que o «Point and click» da Navegação abre."""
    molde = f"{a13.MOLDE}{ADULTO}"
    monkeypatch.setattr(a06_navegacao, "_o_point_and_click_de_hoje",
                        lambda ativo=None: molde)
    ctx = _ctx()
    assert a13._chave_do_point_and_click(ctx) == molde, "o Mapa abriu em outro perfil"
    assert ROTULO in _moldes(a13._opcoes_do_perfil(ctx))
    a13.mapa_perfil(ctx, {"valor": molde}, PonteDeMentira())
    monkeypatch.setattr(a06_navegacao, "_o_point_and_click_de_hoje",
                        lambda ativo=None: f"{a13.MOLDE}point_and_click")
    a13._EDITANDO.clear()
    assert ROTULO not in _moldes(a13._opcoes_do_perfil(ctx))
    with pytest.raises(RuntimeError, match="não conheço o perfil"):
        a13.mapa_perfil(ctx, {"valor": molde}, PonteDeMentira())


@pytest.fixture
def terror_se_pede(monkeypatch: pytest.MonkeyPatch) -> str:
    """O catálogo com um segundo estilo que só aparece quando pedido: a régua é genérica."""
    import dataclasses

    novo = dataclasses.replace(estilos_de_jogo.POR_CHAVE["terror"], so_quando_pedido=True)
    estilos = tuple(novo if e.chave == "terror" else e for e in estilos_de_jogo.ESTILOS)
    monkeypatch.setattr(estilos_de_jogo, "ESTILOS", estilos)
    monkeypatch.setattr(estilos_de_jogo, "POR_CHAVE", {**estilos_de_jogo.POR_CHAVE, "terror": novo})
    monkeypatch.setattr(estilos_de_jogo, "POR_ROTULO", {e.rotulo: e for e in estilos})
    monkeypatch.setattr(estilos_de_jogo, "PEDIVEIS", frozenset({ADULTO, "terror"}))
    return novo.rotulo


def test_outro_estilo_pedido_por_outra_extensao_funciona_igual(
        lg: instalador.Lugares, terror_se_pede: str) -> None:
    _o_disco()
    assert terror_se_pede not in _rotulos(_opcoes_do_estilo(TARDE))
    _instalada(lg, estilos=["terror"], mod_id="outra")
    assert estilos_pedidos() == {"terror"}
    rotulos = _rotulos(_opcoes_do_estilo(TARDE))
    assert terror_se_pede in rotulos and ROTULO not in rotulos
    a10_perfis.editor_estilo(_ctx(), {"valor": terror_se_pede}, PonteDeMentira())
    assert loader.load_profile(TARDE).estilo == "terror"
    _instalada(lg, estilos=["terror"], mod_id="outra", ligada=False)
    a10_perfis.selecionar(_ctx(), {"hefPerfil": NOITE}, PonteDeMentira())
    with pytest.raises(RuntimeError, match="só aparece com a extensão"):
        a10_perfis.editor_estilo(_ctx(), {"valor": terror_se_pede}, PonteDeMentira())


def test_dois_pedidos_do_mesmo_estilo_nao_duplicam(lg: instalador.Lugares) -> None:
    _o_disco()
    _instalada(lg, mod_id="pede")
    _instalada(lg, mod_id="segunda")
    assert estilos_pedidos() == {ADULTO}
    assert _rotulos(_opcoes_do_estilo(TARDE)).count(ROTULO) == 1
    assert _moldes(a13._opcoes_do_perfil(_ctx())).count(ROTULO) == 1
    _instalada(lg, mod_id="pede", ligada=False)
    assert ROTULO in _rotulos(_opcoes_do_estilo(TARDE)), "a outra ligada ainda pede"
    _instalada(lg, mod_id="segunda", ligada=False)
    assert ROTULO not in _rotulos(_opcoes_do_estilo(TARDE))


def test_o_estilo_que_nao_existe_recusa_so_aquela_extensao(lg: instalador.Lugares) -> None:
    _o_disco()
    _instalada(lg, estilos=["boliche"], mod_id="torta")
    with pytest.raises(ManifestoRecusadoError, match="«boliche» não é um estilo de jogo"):
        ler_manifesto(lg.codigo / "torta")
    assert estilos_pedidos() == frozenset()
    assert ROTULO not in _rotulos(_opcoes_do_estilo(TARDE))
    _instalada(lg, mod_id="pede")
    assert estilos_pedidos() == {ADULTO}, "a extensão torta derrubou o pedido da outra"
    assert ROTULO in _rotulos(_opcoes_do_estilo(TARDE))


def test_o_perfil_de_antes_com_a_marca_adulto_carrega_sem_a_extensao(
        lg: instalador.Lugares) -> None:
    """D-3010-O-PERFIL-QUE-GUARDA-O-ESTILO-PEDIDO-O-MANTEM, no arquivo de antes dos estilos."""
    _o_disco()
    arquivo = loader.profiles_dir() / "antigo.json"
    arquivo.write_text(json.dumps({"name": "Antigo", "match": {"type": "criteria",
                                   "window_class": ["antigo"]}, "marcas": [ADULTO]}),
                       encoding="utf-8")
    perfil = loader.load_profile("Antigo")
    assert perfil.estilo == ADULTO
    assert estilos_de_jogo.estilo_que_pinta(perfil.estilo) is estilos_de_jogo.POR_CHAVE[ADULTO]
    assert _escolhido(_opcoes_do_estilo("Antigo")) == [ROTULO]


def test_o_cli_guarda_o_estilo_do_json_sem_a_extensao(
        lg: instalador.Lugares, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `profile apply --file` é o arquivo do perfil: guarda o estilo, como a decisão manda."""
    from typer.testing import CliRunner

    import hefesto_dualsense4unix.app.ipc_bridge as ponte
    from hefesto_dualsense4unix.cli.app import app

    monkeypatch.setattr(ponte, "_run_call", lambda *a, **kw: {"active_profile": "Noite JSON"})
    corpo = tmp_path / "noite.json"
    corpo.write_text(json.dumps({"name": "Noite JSON", "match": {"type": "manual"},
                                 "estilo": ADULTO}), encoding="utf-8")
    saida = CliRunner().invoke(app, ["profile", "apply", "--file", str(corpo)])
    assert saida.exit_code == 0, saida.output
    assert loader.load_profile("Noite JSON").estilo == ADULTO
    assert _escolhido(_opcoes_do_estilo("Noite JSON")) == [ROTULO]
