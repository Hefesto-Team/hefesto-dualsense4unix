"""O «Aplicar», o «Salvar Perfil» e o «Importar» do rodapé já atualizam.

O-APLICAR-E-O-SALVAR-JA-ATUALIZAM-01 (02/10/2026). O pedido de 29/09: os
botões do rodapé que mandam ou gravam perfil fazem também o que o «Atualizar»
(aba Sistema) e o «Reconectar controles» (aba Jogar) fazem. A forma é a «versão
leve» que o usuário escolheu (respostas 42, 43 e 44 da sprint): os arquivos que a
Steam lê (`launch_env.refresh`, nunca o `daemon.reload`, que para os atalhos),
o rádio só do elo morto, e a reconciliação com a numeração (`coop.sync` e
`identity.renumber`), a cada Aplicar, Salvar e Importar.

O DEFEITO, MEDIDO ANTES DA CURA (uma ponte que anota, o perfil ativo no lar de
mentira): o «Aplicar» pedia `["profile.reaplicar"]`, o «Salvar» `[]` e o
«Importar» `[]`. O Salvar não falava com o daemon: o arquivo mudava e o
controle seguia com o que tinha, e os arquivos dos jogos só mudavam no próximo
«Atualizar».

A PONTE É UM DUBLÊ QUE ANOTA A ORDEM (`tests/unit/ponte_do_rodape.py`, com as
respostas na forma do daemon), e o rádio é o leitor de mentira da casa (o
`busctl` da máquina nunca é chamado; a suíte não alcança o BlueZ dela).

AS MORDIDAS (medidas na entrega, cada uma reprova a régua que a nomeia):

1. tire a volta do `rodape.salvar`;
2. devolva o `save_profile` direto ao `rodape.salvar`;
3. troque o `launch_env.refresh` da volta pelo `daemon.reload`;
4. tire o filtro do `Connected` em `perfil.o_radio_de_volta`;
5. devolva os dois `p.resultado` ao `a01_jogar.reconectar`;
6. tire o `except` do `coop.sync` da volta;
7. tire a volta do `rodape.importar`.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real
from tests.unit.ponte_do_rodape import PonteDoRodape

exigir_gi_real("importa `interface.pacotes`, que carrega o GTK")

from hefesto_dualsense4unix.integrations import bluez_dbus as bd
from hefesto_dualsense4unix.integrations import conexao_zumbi, diario_do_radio
from hefesto_dualsense4unix.integrations import gesto_de_reconexao as radio
from hefesto_dualsense4unix.interface.pacotes import (
    Contexto,
    a01_jogar,
    perfil,
    ponte,
    rodape,
)
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import Profile
from tests.unit import bluez_de_mentira as bm

NOME = "Auditoria"
OUTRO = "Outro perfil"

A_VOLTA = ["launch_env.refresh", "coop.sync", "identity.renumber"]

NA_MESA = "aa:bb:cc:00:00:01"


@pytest.fixture(autouse=True)
def _o_disco() -> None:
    """Dois perfis no disco do lar de mentira; o primeiro é o que vale."""
    for nome, prioridade in ((NOME, 10), (OUTRO, 20)):
        loader.save_profile(Profile.model_validate(
            {"name": nome, "match": {"type": "any"}, "priority": prioridade}),
            origem="teste")


@pytest.fixture(autouse=True)
def _sem_carona(monkeypatch: pytest.MonkeyPatch) -> None:
    """A carona do atalho da Steam não é desta régua (e já é desligada na suíte)."""
    monkeypatch.setattr(perfil, "com_a_carona", lambda frase="": frase)


@pytest.fixture()
def tocados(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """O rádio de mentira: três DualSense fora da mesa e um dentro.

    O de fora com `Connected` (o elo morto), o de fora desconectado, o de fora
    que não respondeu (`None`), e o da mesa com `Connected`.
    """
    chamados: list[str] = []

    def _lista(**_k: Any) -> list[tuple[str, bool | None]]:
        return [("aa:bb:cc:00:00:0a", True), ("aa:bb:cc:00:00:0b", False),
                ("aa:bb:cc:00:00:0c", None), (NA_MESA, True)]

    def _reconectar(mac: str, **_k: Any) -> Any:
        chamados.append(mac)
        return radio.Resultado(radio.ESTADO_JA_NO_AR, radio.FRASE_JA_NO_AR, mac)

    monkeypatch.setattr(radio, "dualsenses_do_radio", _lista)
    monkeypatch.setattr(radio, "reconectar", _reconectar)
    return chamados


def _ctx(ativo: str = NOME) -> Contexto:
    mesa = [{"uniq": NA_MESA, "jogador": 1}]
    return Contexto(state={"active_profile": ativo, "controllers": mesa},
                    mesa=mesa, conectados=mesa, estados={})


def _o_arquivo(nome: str = NOME) -> dict[str, Any]:
    arquivo = loader.arquivo_do_perfil(nome)
    assert arquivo is not None, f"o perfil {nome!r} não está no disco"
    return json.loads(arquivo.read_text(encoding="utf-8"))


class _PonteDoImportar(PonteDoRodape):
    """O seletor do sistema devolve o arquivo que o usuário escolheu."""

    def __init__(self, escolhido: Path) -> None:
        super().__init__()
        self._escolhido = escolhido

    def escolher_arquivo(self, titulo: str, padrao: str = "*", **_: Any) -> str | None:
        return str(self._escolhido)


def _importar(tmp_path: Path) -> list[str]:
    """Importa um perfil válido e devolve o que a ponte ouviu."""
    escolhido = tmp_path / "de-fora.json"
    escolhido.write_text(json.dumps({"name": "Veio de fora", "match": {"type": "any"}}),
                         encoding="utf-8")
    p = _PonteDoImportar(escolhido)
    rodape.importar(_ctx(), {}, p)
    return p.chamadas


@pytest.mark.parametrize("botao", ["aplicar", "salvar"])
def test_os_dois_botoes_terminam_com_a_volta(botao: str, tocados: list[str]) -> None:
    """A sequência termina em `launch_env.refresh`, `coop.sync` e `identity.renumber`.

    O ato do botão vem antes: o `profile.reaplicar` (o Aplicar; o Salvar do
    perfil que vale).
    """
    p = PonteDoRodape()
    getattr(rodape, botao)(_ctx(), {}, p)
    assert p.chamadas[-3:] == A_VOLTA, (
        f"o «{botao}» não terminou com a volta: {p.chamadas}")
    assert p.chamadas[0] == "profile.reaplicar", (
        f"o «{botao}» não começou pelo ato dele: {p.chamadas}")


def test_o_salvar_reaplica_o_perfil_que_vale_antes_da_volta(tocados: list[str]) -> None:
    """O Salvar passa pelo `gravar_e_reaplicar`: disco, reaplicar, aviso, e a volta."""
    p = PonteDoRodape()
    rodape.salvar(_ctx(), {}, p)
    assert p.chamadas.count("profile.reaplicar") == 1, p.chamadas
    assert p.chamadas.index("profile.reaplicar") < p.chamadas.index("coop.sync"), (
        f"a reaplicação veio depois da volta: {p.chamadas}")
    assert _o_arquivo()["name"] == NOME


def test_o_funil_nao_reaplica_o_perfil_que_nao_vale() -> None:
    """Gravar outro perfil pelo funil (o que a aba Perfis faz) não o manda aos controles."""
    p = PonteDoRodape()
    prof = Profile.model_validate(_o_arquivo(OUTRO))
    perfil.gravar_e_reaplicar(prof, _ctx(), p)
    assert "profile.reaplicar" not in p.chamadas, p.chamadas
    assert p.chamadas == ["launch_env.refresh"], p.chamadas


def test_a_volta_nunca_pede_o_daemon_reload(tmp_path: Path, tocados: list[str]) -> None:
    """O `daemon.reload` para e sobe o leitor dos atalhos: nenhum dos três o pede."""
    pedidos: dict[str, list[str]] = {}
    for botao in ("aplicar", "salvar"):
        p = PonteDoRodape()
        getattr(rodape, botao)(_ctx(), {}, p)
        pedidos[botao] = p.chamadas
    pedidos["importar"] = _importar(tmp_path)
    for botao, chamadas in pedidos.items():
        assert "daemon.reload" not in chamadas, f"o «{botao}» parou os atalhos: {chamadas}"
        assert "launch_env.refresh" in chamadas, f"o «{botao}» não avisou o lançamento"


def test_a_volta_so_chama_o_elo_morto(tocados: list[str]) -> None:
    """Dos três de fora, só o que o BlueZ diz `Connected`; o da mesa nunca."""
    perfil.a_volta_do_perfil(_ctx(), PonteDoRodape())
    assert tocados == ["aa:bb:cc:00:00:0a"], f"a volta chamou {tocados}"


def test_o_reconectar_segue_tentando_todos_os_de_fora(tocados: list[str]) -> None:
    """O botão de origem continua com a volta inteira do rádio."""
    a01_jogar.reconectar(_ctx(), {}, PonteDoRodape())
    assert tocados == ["aa:bb:cc:00:00:0a", "aa:bb:cc:00:00:0b", "aa:bb:cc:00:00:0c"]


@pytest.fixture()
def barramento(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> bm.BarramentoDeMentira:
    """O BlueZ de mentira com dois DualSense `Connected` fora da mesa."""
    monkeypatch.setenv(diario_do_radio.ENV_TRAVA, str(tmp_path / "radio.lock"))
    monkeypatch.setenv(diario_do_radio.ENV_DIARIO, str(tmp_path / "radio-diario.jsonl"))
    b = bm.BarramentoDeMentira()
    b.mesa[bm.no_de(bm.CONTROLE)][bd.APARELHO]["Connected"] = True
    b.mesa[bm.no_de("aa:bb:cc:00:00:44")] = {
        bd.APARELHO: {"Address": "AA:BB:CC:00:00:44", "Alias": "DualSense Wireless Controller",
                      "Paired": True, "Connected": True, "Modalias": "usb:v054Cp0CE6d0100"}}
    dono = bd.DonoVivo(b)
    assert dono.ligar()
    monkeypatch.setattr(bd, "_DONO", dono)
    raiz = tmp_path / "class-hidraw"
    pai = raiz / "hidraw0" / "device"
    pai.mkdir(parents=True)
    (pai / "uevent").write_text(
        "DRIVER=playstation\nHID_ID=0005:0000054C:00000CE6\n"
        f"HID_NAME=DualSense Wireless Controller\nHID_UNIQ={bm.CONTROLE}\n",
        encoding="utf-8")
    monkeypatch.setattr(conexao_zumbi, "RAIZ_HIDRAW", str(raiz))
    return b


def test_o_connected_com_hid_vivo_nao_cai_na_volta(
    barramento: bm.BarramentoDeMentira,
) -> None:
    """A seção de 02/10: o elo morto se pergunta ao kernel."""
    perfil.a_volta_do_perfil(_ctx(), PonteDoRodape())
    quedas = [c for c, _i, m, _a, _t in barramento.chamadas if m == "Disconnect"]
    assert quedas == [bm.no_de("aa:bb:cc:00:00:44")], f"a volta derrubou {quedas}"
    vivo = [m for c, _i, m, _a, _t in barramento.chamadas if c == bm.no_de(bm.CONTROLE)]
    assert vivo == [], f"o controle com HID vivo foi mexido: {vivo}"


def test_o_reconectar_e_a_volta_chegam_ao_mesmo_dono(
    monkeypatch: pytest.MonkeyPatch, tocados: list[str],
) -> None:
    """O `coop.sync` e o `identity.renumber` têm um dono, contado pelo dono."""
    original = perfil.os_jogadores_de_volta
    por_quem: list[str] = []

    def _contado(p: Any) -> tuple[Any, Any]:
        por_quem.append("dono")
        return original(p)

    monkeypatch.setattr(perfil, "os_jogadores_de_volta", _contado)
    p = PonteDoRodape()
    a01_jogar.reconectar(_ctx(), {}, p)
    assert por_quem == ["dono"], "o «Reconectar» tem uma cópia própria dos passos 1 e 2"
    assert p.chamadas == ["coop.sync", "identity.renumber"], p.chamadas
    rodape.salvar(_ctx(), {}, PonteDoRodape())
    assert por_quem == ["dono", "dono"], "a volta do «Salvar» não chegou ao dono"


class _PonteQueFalhaNaVolta(PonteDoRodape):
    """O `coop.sync` levanta, como a ponte real quando o daemon não atende."""

    def chamar(self, metodo: str, timeout: float | None = None, **params: Any) -> bool:
        super().chamar(metodo, timeout, **params)
        return False

    def resultado(self, metodo: str, timeout: float | None = None, **params: Any) -> Any:
        super().resultado(metodo, timeout, **params)
        raise RuntimeError(f"o daemon não respondeu a {metodo}")


def test_a_volta_que_falha_nao_derruba_o_salvar(
    capsys: pytest.CaptureFixture[str], tocados: list[str],
) -> None:
    """O Salvar volta sem levantar, o disco tem o perfil, e o diário diz o passo."""
    arquivo = loader.arquivo_do_perfil(NOME)
    assert arquivo is not None
    arquivo.write_text(json.dumps(_o_arquivo()), encoding="utf-8")
    assert rodape.salvar(_ctx(), {}, _PonteQueFalhaNaVolta()) is None
    assert arquivo.read_text(encoding="utf-8").count("\n") > 1, "o Salvar não gravou"
    diario = capsys.readouterr().err
    assert "[relato] volta do perfil · coop.sync" in diario, diario
    assert "[relato] volta do perfil · launch_env.refresh" in diario, diario


def test_a_volta_que_falha_nao_derruba_o_aplicar(tocados: list[str]) -> None:
    p = _PonteQueFalhaNaVolta()
    assert rodape.aplicar(_ctx(), {}, p) is None
    assert p.chamadas[0] == "profile.reaplicar"


def test_o_importar_termina_com_a_volta(tmp_path: Path, tocados: list[str]) -> None:
    """A resposta 44 dela: todo botão do rodapé que grava perfil termina igual."""
    chamadas = _importar(tmp_path)
    assert loader.arquivo_do_perfil("Veio de fora") is not None, "o Importar não gravou"
    assert chamadas == A_VOLTA, f"o «Importar» não deu a volta: {chamadas}"
    assert tocados == ["aa:bb:cc:00:00:0a"]


def test_o_rodape_declara_o_que_a_volta_usa() -> None:
    """`PONTE` e `METODOS` do rodapé: a ponte tem as funções, o daemon os métodos."""
    from tests.unit import inventario_do_daemon as daemon

    assert {"chamar", "resultado"} <= rodape.PONTE
    assert set(A_VOLTA) <= rodape.METODOS
    for nome in sorted(rodape.PONTE):
        assert hasattr(ponte, nome), f"o rodapé chama `ponte.{nome}` e a ponte não tem"
    assert daemon.confere(rodape.METODOS) == [], daemon.confere(rodape.METODOS)
