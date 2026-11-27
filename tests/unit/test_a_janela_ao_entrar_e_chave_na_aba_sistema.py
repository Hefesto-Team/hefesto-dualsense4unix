"""A janela no início da sessão é uma chave da aba Sistema.

Sprint A-JANELA-AO-ENTRAR-E-CHAVE-NA-ABA-SISTEMA-01.

A unit que abre a janela quando a sessão começa só se ligava e desligava pelo terminal, e nada na
janela dizia se estava ligada. A régua cobra o dono da escolha (o link do systemd de usuário), o
gesto da aba, o campo que pinta a pílula e o lugar da pílula no desenho e na página publicada.

NENHUM ATO REAL: o `systemctl` é um dublê que cria e apaga o link numa pasta de mentira.
"""
from __future__ import annotations

import inspect
import pathlib
import re
import sys
from types import SimpleNamespace
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

PAGINA = "09-sistema.html"
GESTO = "janela-ao-entrar"
ROTULO = "Abrir a janela ao entrar"
DICA = "Abre a janela do Hefesto quando a sessão começa"
AS_DUAS = (RAIZ / "mockup" / PAGINA,
           RAIZ / "src/hefesto_dualsense4unix/interface/paginas" / PAGINA)


@pytest.fixture
def dono(monkeypatch, tmp_path):
    """O dono da escolha num lar de mentira: nenhuma pasta de verdade do systemd é lida."""
    from hefesto_dualsense4unix.app.actions import janela_ao_entrar as mod

    from hefesto_dualsense4unix.daemon import service_install

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setattr(service_install, "SYSTEM_UNIT_DIRS", [tmp_path / "usr", tmp_path / "etc"])
    return mod


def _link(mod) -> pathlib.Path:
    return mod.links_da_escolha()[0]


def _do_sistema(mod) -> pathlib.Path:
    return mod.links_da_escolha()[1].parents[1]


def _instalar(mod, pasta: pathlib.Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / mod.UNIT_DA_JANELA_AO_ENTRAR).write_text("[Unit]\n", encoding="utf-8")


def _systemctl_de_mentira(mod, chamadas: list[list[str]], rc: int = 0, obedece: bool = True):
    def rodar(argv, **_kw: Any):
        chamadas.append(list(argv))
        link = _link(mod)
        if obedece and rc == 0 and argv[2] == "enable":
            link.parent.mkdir(parents=True, exist_ok=True)
            link.symlink_to(mod.pasta_do_usuario() / mod.UNIT_DA_JANELA_AO_ENTRAR)
        if obedece and rc == 0 and argv[2] == "disable":
            link.unlink(missing_ok=True)
        return SimpleNamespace(returncode=rc, stderr="recusado pelo dublê" if rc else "")

    return rodar


def test_sem_link_a_escolha_esta_desligada(dono):
    assert dono.ligada() is False


def test_o_link_da_conta_liga_a_escolha(dono):
    _link(dono).parent.mkdir(parents=True)
    _link(dono).symlink_to("/não/importa")

    assert dono.ligada() is True


def test_o_link_do_sistema_tambem_liga(dono):
    do_sistema = dono.links_da_escolha()[1]
    do_sistema.parent.mkdir(parents=True)
    do_sistema.symlink_to("/não/importa")

    assert dono.ligada() is True


def test_ligar_com_a_unit_instalada_so_habilita(dono):
    _instalar(dono, dono.pasta_do_usuario())
    chamadas: list[list[str]] = []

    dono.escolher_a_janela_ao_entrar(True, rodar=_systemctl_de_mentira(dono, chamadas))

    assert chamadas == [["systemctl", "--user", "enable", dono.UNIT_DA_JANELA_AO_ENTRAR]]
    assert dono.ligada() is True


def test_a_unit_do_pacote_conta_como_instalada(dono):
    _instalar(dono, _do_sistema(dono))
    chamadas: list[list[str]] = []

    dono.escolher_a_janela_ao_entrar(True, rodar=_systemctl_de_mentira(dono, chamadas))

    assert [c[2] for c in chamadas] == ["enable"]
    assert not (dono.pasta_do_usuario() / dono.UNIT_DA_JANELA_AO_ENTRAR).exists()


def test_ligar_sem_a_unit_copia_o_modelo_e_recarrega_antes(dono):
    chamadas: list[list[str]] = []

    dono.escolher_a_janela_ao_entrar(True, rodar=_systemctl_de_mentira(dono, chamadas))

    copiada = dono.pasta_do_usuario() / dono.UNIT_DA_JANELA_AO_ENTRAR
    modelo = RAIZ / "assets" / dono.UNIT_DA_JANELA_AO_ENTRAR
    assert copiada.read_text(encoding="utf-8") == modelo.read_text(encoding="utf-8")
    assert [c[2] for c in chamadas] == ["daemon-reload", "enable"]
    assert dono.ligada() is True


def test_desligar_desabilita_e_nao_copia_nada(dono):
    _link(dono).parent.mkdir(parents=True)
    _link(dono).symlink_to("/não/importa")
    chamadas: list[list[str]] = []

    dono.escolher_a_janela_ao_entrar(False, rodar=_systemctl_de_mentira(dono, chamadas))

    assert chamadas == [["systemctl", "--user", "disable", dono.UNIT_DA_JANELA_AO_ENTRAR]]
    assert dono.ligada() is False
    assert not (dono.pasta_do_usuario() / dono.UNIT_DA_JANELA_AO_ENTRAR).exists()


def test_a_recusa_do_systemd_vira_frase(dono):
    _instalar(dono, dono.pasta_do_usuario())

    with pytest.raises(RuntimeError, match="recusado pelo dublê") as erro:
        dono.escolher_a_janela_ao_entrar(True, rodar=_systemctl_de_mentira(dono, [], rc=1))

    assert str(erro.value).startswith(dono.NAO_MUDOU)
    assert dono.ligada() is False


def test_a_escolha_que_nao_pegou_nao_passa_por_feita(dono):
    _instalar(dono, dono.pasta_do_usuario())

    with pytest.raises(RuntimeError, match=re.escape(dono.NAO_MUDOU)):
        dono.escolher_a_janela_ao_entrar(True, rodar=_systemctl_de_mentira(dono, [], obedece=False))


def test_o_systemctl_que_nao_existe_vira_frase(dono):
    _instalar(dono, dono.pasta_do_usuario())

    def sem_systemctl(argv, **_kw: Any):
        raise FileNotFoundError(2, "No such file or directory", argv[0])

    with pytest.raises(RuntimeError, match=re.escape(dono.NAO_MUDOU)):
        dono.escolher_a_janela_ao_entrar(True, rodar=sem_systemctl)


@pytest.fixture
def a09():
    from pacotes import a09_sistema as mod

    return mod


@pytest.mark.parametrize("lido", [True, False])
def test_o_gesto_manda_o_contrario_do_que_leu(a09, monkeypatch, lido):
    from hefesto_dualsense4unix.app.actions import janela_ao_entrar as mod

    pedidos: list[bool] = []
    monkeypatch.setattr(mod, "ligada", lambda: lido)
    monkeypatch.setattr(mod, "escolher_a_janela_ao_entrar", pedidos.append)

    a09.janela_ao_entrar(None, {}, None)

    assert pedidos == [not lido]


def test_o_campo_da_pilula_vem_do_dono(a09, monkeypatch):
    from hefesto_dualsense4unix.app.actions import janela_ao_entrar as mod

    monkeypatch.setattr(mod, "ligada", lambda: True)
    assert a09._da_janela_ao_entrar() == {GESTO: True}
    monkeypatch.setattr(mod, "ligada", lambda: False)
    assert a09._da_janela_ao_entrar() == {GESTO: False}


def test_o_pacote_pinta_o_campo_nos_dois_caminhos(a09):
    """O caminho de sempre e o do erro da camada levam o campo; sem ele a pílula não acende."""
    fonte = inspect.getsource(inspect.unwrap(a09.pacote))

    assert fonte.count("_da_janela_ao_entrar()") == 2


def test_a_prova_botao_a_botao_nao_clica_a_chave(a09):
    import pacotes

    assert (PAGINA, GESTO) in pacotes.perigosos()
    assert GESTO in a09.SEM_ECO


def test_o_contrato_da_aba_conhece_o_endereco_e_o_gesto():
    from hefesto_dualsense4unix.interface import sistema

    assert GESTO in sistema.ENDERECOS
    assert GESTO in sistema.GESTOS


@pytest.mark.parametrize("arquivo", AS_DUAS, ids=["desenho", "publicada"])
def test_a_pilula_fica_no_topo_antes_da_bandeja_e_nasce_desligada(arquivo):
    """D-2611-A-JANELA-AO-ENTRAR-E-CHAVE-NA-ABA-SISTEMA: a chave fica no topo e nasce desligada."""
    texto = arquivo.read_text(encoding="utf-8")
    topo = texto[texto.index('<div class="quadro-topo">'):texto.index('<div class="quadro-corpo">')]
    pilulas = re.findall(r'<button class="(cadeado[^"]*)"[^>]*data-gesto="([^"]+)"[^>]*>'
                         r'<span class="p"></span>([^<]*)</button>', topo)

    as_do_canto = [(g, r) for _, g, r in pilulas[-2:]]
    assert as_do_canto == [(GESTO, ROTULO), ("bandeja", "Ícone na bandeja")]
    classe = next(c for c, g, _ in pilulas if g == GESTO)
    assert classe == "cadeado"
    tag = re.search(r'<button class="cadeado"[^>]*data-gesto="' + GESTO + r'"[^>]*>', topo)
    assert tag is not None
    for exigido in (f'data-dica="{DICA}"', f'data-campo="{GESTO}"', 'data-hef-alvo="classe"',
                    'data-hef-classe="ligada"'):
        assert exigido in tag.group(0)
