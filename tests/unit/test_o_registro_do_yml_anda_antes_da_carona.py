"""O-REGISTRO-DO-YML-ANDA-ANTES-DA-CARONA-01 — as réguas.

A carona só toca o `.yml` de um jogo excluído do Lutris depois de o registro da volta
acompanhar; o registro já velho se cura só com prova byte a byte; e a recusa calada
(a ordem de 13/09) tem a linha dela no CSV, com uma régua que a sustenta.
"""

from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest
import structlog
import yaml

from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe
from hefesto_dualsense4unix.integrations import lista_de_exclusao as lx
from tests.unit.test_a_exclusao_mora_na_camada_do_jogo import (
    _JANELA,
    _PONTE,
    _SO_SUPORTADAS,
    _YML_DO_JOGO,
    _XALIA,
    _carona,
    _env_do_yml,
    _lutris_flatpak,
    _o_xalia_do,
)
from tests.unit import a_exclusao_de_antes as antiga


@pytest.fixture(autouse=True)
def _as_extensoes_de_caixa_ligadas(monkeypatch: pytest.MonkeyPatch) -> None:
    """O Lutris, o RetroArch, o Dolphin e o mGBA viraram extensão: aqui elas estão ligadas."""
    from tests.unit.as_caixas_das_extensoes import ligar

    ligar(monkeypatch)

RAIZ = Path(__file__).resolve().parents[2]
_EVENTO = "carona_nao_anotou_o_yml"


@pytest.fixture(autouse=True)
def _lar(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    lar = tmp_path / "lar"
    lar.mkdir()
    monkeypatch.setenv("HOME", str(lar))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(lar / ".config"))
    monkeypatch.setenv("XDG_STATE_HOME", str(lar / ".local" / "state"))
    monkeypatch.setenv("XDG_DATA_HOME", str(lar / ".local" / "share"))
    from hefesto_dualsense4unix.utils.xdg_paths import launch_env_dir

    amb = launch_env_dir(ensure=True)
    (amb / "default.env").write_text("".join(f"{k}={v}\n" for k, v in _PONTE.items()))
    return lar


def _sha(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _excluido_sem_o_xalia(lar: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, str]:
    """O jogo pelo Proton excluído quando a carona ainda não punha o par do Xalia."""
    yml = _lutris_flatpak(lar)
    antes = yml.read_text()
    _carona(lar)
    with monkeypatch.context() as m:
        m.setattr(cpe, "_pelo_proton_do_yml", lambda _alvo, _lar=None: False)
        assert antiga.adicionar(_JANELA, lancador="lutris", nome="Recettear",
                                lar=lar) == "adicionado"
    assert _o_xalia_do(yml) == {}, yml.read_text()
    return yml, antes


def _o_registro() -> cpe.YmlDoJogo:
    return lx.ler()[0].lutris[0]


def _com_o_xalia_no_disco(yml: Path, valor: str = "1") -> None:
    """O que a carona velha escrevia: os dois pares do Xalia, e nada no registro."""
    dado = yaml.safe_load(yml.read_text())
    dado["system"]["env"].update({_XALIA: valor, _SO_SUPORTADAS: "1"})
    yml.write_text(yaml.safe_dump(dado, default_flow_style=False))


@pytest.mark.parametrize("como", ["erro", "excecao"])
def test_a_anotacao_que_falha_deixa_o_yml_como_estava(
        _lar: Path, monkeypatch: pytest.MonkeyPatch, como: str) -> None:
    """A carona não grava o `.yml` se o registro não anotou, e o diário diz por quê."""
    yml, _ = _excluido_sem_o_xalia(_lar, monkeypatch)
    registro_antes = _o_registro()
    disco_antes = yml.read_bytes()

    def _disco_cheio(*_a: object, **_k: object) -> None:
        raise OSError("disco cheio")

    with monkeypatch.context() as m:
        m.setattr(lx, "_gravar" if como == "erro" else "anotar_os_ymls", _disco_cheio)
        with structlog.testing.capture_logs() as diario:
            _carona(_lar)
    assert yml.read_bytes() == disco_antes, (
        f"a carona gravou o `.yml` sem o registro ter anotado:\n{yml.read_text()}")
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert len(linhas) == 1, diario
    assert linhas[0]["status"] == como
    assert linhas[0]["arquivos"] == 1 and linhas[0]["quem"] == cpe.QUEM_SERVICO, linhas
    assert _o_registro() == registro_antes

    _carona(_lar)  # o disco volta ao normal: a passada seguinte põe o par e anota
    assert _o_xalia_do(yml) == {_XALIA: "1", _SO_SUPORTADAS: "1"}, yml.read_text()
    assert {k for k, _ in _o_registro().pares} >= {_XALIA, _SO_SUPORTADAS}


def test_a_gravacao_que_falha_depois_da_anotacao_nao_perde_o_antes(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `.yml` que não se grava devolve o registro ao que era, e a volta acha o `antes`.

    O comentário do Lutris só sobrevive se a volta usar o `antes` byte a byte; a
    remoção por valor passa pelo `safe_dump` e o perde.
    """
    yml = _lutris_flatpak(_lar, yml="# escrito pelo Lutris\n" + _YML_DO_JOGO)
    antes = yml.read_text()
    _carona(_lar)
    with monkeypatch.context() as m:
        m.setattr(cpe, "_pelo_proton_do_yml", lambda _alvo, _lar=None: False)
        assert antiga.adicionar(_JANELA, lancador="lutris", nome="Recettear",
                                lar=_lar) == "adicionado"
    sem_o_xalia = yml.read_text()
    registro_antes = _o_registro()
    escrever = cpe._escrever_atomico

    def _so_o_yml_falha(alvo: Path, texto: str) -> None:
        if Path(alvo).resolve() == yml.resolve():
            raise OSError("disco cheio")
        escrever(alvo, texto)

    with monkeypatch.context() as m:
        m.setattr(cpe, "_escrever_atomico", _so_o_yml_falha)
        _carona(_lar)
    assert yml.read_text() == sem_o_xalia
    assert _o_registro() == registro_antes, "o registro ficou com o que o disco não tem"

    _carona(_lar)
    assert _o_xalia_do(yml) == {_XALIA: "1", _SO_SUPORTADAS: "1"}, yml.read_text()
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert yml.read_text() == antes


def test_a_lista_sem_o_yml_nao_grava_nem_vira_rastro(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`"nada"` (a lista não tem o `.yml`): sem registro não se grava, e não é falha."""
    yml, _ = _excluido_sem_o_xalia(_lar, monkeypatch)
    disco_antes = yml.read_bytes()
    monkeypatch.setattr(lx, "anotar_os_ymls", lambda *_a, **_k: "nada")
    with structlog.testing.capture_logs() as diario:
        _carona(_lar)
    assert yml.read_bytes() == disco_antes, yml.read_text()
    assert not [x for x in diario if x.get("event") == _EVENTO], diario


def test_a_janela_tambem_diz_quem_desistiu(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O `quem=` acompanha o prazo de quem chamou a carona."""
    _excluido_sem_o_xalia(_lar, monkeypatch)
    monkeypatch.setattr(lx, "anotar_os_ymls", lambda *_a, **_k: "ocupada")
    with structlog.testing.capture_logs() as diario:
        cpe.curar_todas_as_estradas(lar=_lar, raiz_sistema=_lar.parent / "sistema",
                                    espera=2.0)
    linhas = [x for x in diario if x.get("event") == _EVENTO]
    assert [(x["status"], x["quem"]) for x in linhas] == [("ocupada", cpe.QUEM_JANELA)]


def test_a_anotacao_de_pe_acompanha_o_disco_e_a_volta_devolve_o_arquivo(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    yml, antes = _excluido_sem_o_xalia(_lar, monkeypatch)
    _carona(_lar)
    assert _o_xalia_do(yml) == {_XALIA: "1", _SO_SUPORTADAS: "1"}, yml.read_text()
    registro = _o_registro()
    assert {_XALIA, _SO_SUPORTADAS} <= {k for k, _ in registro.pares}
    assert registro.depois == _sha(yml.read_text())
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert yml.read_text() == antes


def test_o_registro_velho_sem_o_xalia_se_cura_pela_prova_byte_a_byte(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """O disco é exatamente a carona sobre o `antes`: o par é nosso e o registro o anota."""
    yml, antes = _excluido_sem_o_xalia(_lar, monkeypatch)
    _com_o_xalia_no_disco(yml)
    escrito = yml.read_text()
    assert {_XALIA, _SO_SUPORTADAS}.isdisjoint(k for k, _ in _o_registro().pares)
    _carona(_lar)
    assert yml.read_text() == escrito, "a cura do registro não reescreve o arquivo"
    registro = _o_registro()
    assert {_XALIA, _SO_SUPORTADAS} <= {k for k, _ in registro.pares}
    assert registro.depois == _sha(escrito) and registro.antes == antes
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    assert yml.read_text() == antes
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in _env_do_yml(yml)


def test_o_xalia_posto_por_ela_com_outro_valor_nao_vira_nosso(
        _lar: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Sem a prova byte a byte o par segue como dela: ninguém reanota, a volta o deixa."""
    yml, _ = _excluido_sem_o_xalia(_lar, monkeypatch)
    _com_o_xalia_no_disco(yml, valor="0")
    escrito = yml.read_text()
    registro_antes = _o_registro()
    _carona(_lar)
    assert yml.read_text() == escrito
    assert _o_registro() == registro_antes
    assert lx.tirar(_JANELA, lar=_lar) == "removido"
    env = _env_do_yml(yml)
    assert env.get(_XALIA) == "0", f"a volta apagou o valor dela:\n{yml.read_text()}"
    assert "SDL_GAMECONTROLLER_IGNORE_DEVICES" not in env


# D-1309-A-RECUSA-SO-PISCA-E-A-FRASE-VAI-AO-DIARIO


def _o_que_a_recusa_faz(fonte: str) -> list[str]:
    """Os nomes que `_recusou_dizendo` chama: a recusa tem de ficar só no `print`."""
    chamadas: list[str] = []
    for no in ast.walk(ast.parse(fonte)):
        if isinstance(no, ast.FunctionDef) and no.name == "_recusou_dizendo":
            for filho in ast.walk(no):
                if isinstance(filho, ast.Call):
                    chamadas.append(ast.unparse(filho.func))
    return chamadas


def test_a_recusa_so_pisca_e_a_frase_vai_ao_diario() -> None:
    """D-1309-A-RECUSA-SO-PISCA-E-A-FRASE-VAI-AO-DIARIO: nenhuma frase de recusa chega à tela.

    O piloto só imprime no diário: o gesto levanta `RuntimeError` com a frase (que é o que
    chega ao diário), e nenhuma outra porta a leva ao cartão.
    """
    piloto = (RAIZ / "src/hefesto_dualsense4unix/interface/hefesto_vivo.py").read_text("utf-8")
    assert _o_que_a_recusa_faz(piloto) == ["print"], _o_que_a_recusa_faz(piloto)


def test_a_regua_da_recusa_morde() -> None:
    """Uma recusa que fala com a tela (um `escrever`, um recado) reprova a régua acima."""
    com_recado = (
        "class V:\n"
        "    def _recusou_dizendo(self, p, nome, uniq, erro):\n"
        "        print(erro)\n"
        "        self._dizer_na_tela(erro)\n"
        "        return False\n")
    assert _o_que_a_recusa_faz(com_recado) == ["print", "self._dizer_na_tela"]
