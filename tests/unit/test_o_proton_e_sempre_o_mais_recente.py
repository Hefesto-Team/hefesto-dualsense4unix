"""O Proton é sempre o mais recente que passa na ficha.

O-PROTON-E-SEMPRE-O-MAIS-RECENTE-QUE-PASSA-NA-FICHA-01, 22/10/2026. Escolha do usuário: «é sempre a
versão mais recente do próton desde que ele tenha os pré-requisitos e usaremos apenas a nova. As
demais são excluídas». Os pré-requisitos são a ficha (D-1610-O-PROTON-NOVO-SO-ENTRA-COM-A-FICHA).
Revoga a parte da D-1610-O-PROTON-QUE-SOBRA-CONTA-O-USO-DE-TODO-LANCADOR que mantinha a versão
citada por um jogo: todo jogo passa para a nova e a velha sai; o que não dá para repontar
(o Lutris, que é extensão, e o jogo nomeado em `jogos_fora_do_pino.txt`) mantém a versão dele.

TUDO É DE MENTIRA: casa, Steam, Heroic e Lutris são pastas em `tmp_path`; as pastas do Proton
nascem do `_proton_de_mentira` da régua da ficha; a Steam viva e o Heroic vivo não decidem nada.

AS MORDIDAS (feitas na sprint, com a cura devolvida e o md5 conferido): o `pino_que_vale` que volta
ao pino do conf (ou à mínima) reprova o caso da mais recente; o que aceita a nova sem a ficha
reprova o caso da que reprova; o lock que usa o nome do conf reprova o caso do fluxo inteiro; o
`apontar_o_heroic_para` que não escreve, ou o que escreve com o Heroic aberto, reprova os casos
do Heroic; o «mantém a citada» da Steam de volta (a sobra que não espera o lock) reprova o caso
do fluxo.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from hefesto_dualsense4unix.integrations import censo_dos_lancadores as censo
from hefesto_dualsense4unix.integrations import proton_pin as pp
from tests.unit.test_o_fixar_proton_desinstala_as_que_sobram import _vdf
from tests.unit.test_o_proton_novo_so_entra_se_passar import _proton_de_mentira
from tests.unit.test_o_proton_que_sobra_conta_o_uso_de_todo_lancador import (
    DO_HEROIC,
    _extensao_que_le,
    _jogo_do_heroic,
    _jogo_do_lutris,
    _yml,
)

VELHA = "GE-Proton11-7-x86_64"
NOVA = "GE-Proton11-8-x86_64"
REPROVA = "GE-Proton11-9-x86_64"
CONF = {"name": VELHA, "url": "u", "sha256": "a" * 64}
SEM_A_STRING = "x86_64-windows/mmdevapi.dll:PROTON_ENABLE_MHWILDS_USB_AUDIO"


@pytest.fixture(autouse=True)
def _a_steam_e_o_heroic_vivos_nao_decidem(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pp, "_steam_gate", lambda: None)
    monkeypatch.setattr(censo, "heroic_aberto", lambda: False)


@pytest.fixture
def casa(tmp_path: Path) -> Path:
    """A casa com uma Steam nativa e o Proton do conf instalado."""
    lar = tmp_path / "casa"
    raiz = lar / ".steam" / "steam"
    (raiz / "config").mkdir(parents=True)
    (raiz / "steamapps").mkdir()
    _proton_de_mentira(raiz / "compatibilitytools.d" / VELHA)
    return lar


def _compat(lar: Path) -> Path:
    return lar / ".steam" / "steam" / "compatibilitytools.d"


def _instalar(lar: Path, nome: str, *, sem: str = "") -> None:
    _proton_de_mentira(_compat(lar) / nome, sem=sem)


def _config_vdf(lar: Path) -> Path:
    return lar / ".steam" / "steam" / "config" / "config.vdf"


def _mapa(lar: Path, mapeamento: dict[str, str]) -> None:
    _config_vdf(lar).write_text(_vdf(mapeamento), encoding="utf-8")


def _jogos(lar: Path) -> dict[str, str]:
    return pp.extract_compat_tool_mapping(_config_vdf(lar).read_text(encoding="utf-8"))


def _travar(lar: Path) -> dict[str, object]:
    return pp.lock_proton_for_all_games(
        conf=CONF, home=lar, config_vdf=_config_vdf(lar),
        state_path=lar / "lock.json", todos=True, compat_dir=_compat(lar))


def _nomes(sobras: list[pp.VersaoQueSobra]) -> set[str]:
    return {s.pasta.name for s in sobras}


def test_entre_as_instaladas_que_passam_vale_a_mais_recente(casa: Path) -> None:
    """Prova da D-2210-O-PROTON-E-SEMPRE-O-MAIS-RECENTE-QUE-PASSA."""
    _instalar(casa, NOVA)
    assert pp.pino_que_vale(CONF, _compat(casa)) == NOVA


def test_sem_nenhuma_mais_nova_vale_a_do_conf(casa: Path) -> None:
    assert pp.pino_que_vale(CONF, _compat(casa)) == VELHA


def test_a_mais_nova_que_reprova_na_ficha_nao_entra(casa: Path) -> None:
    """MORDIDA: aceitar a nova sem a ficha faz a 11-9, sem a string do mmdevapi, valer."""
    _instalar(casa, REPROVA, sem=SEM_A_STRING)
    assert pp.pino_que_vale(CONF, _compat(casa)) == VELHA


def test_a_que_reprova_nao_tira_a_que_passa(casa: Path) -> None:
    """A 11-8 passa e a 11-9 reprova: vale a 11-8, a mais recente que passa."""
    _instalar(casa, NOVA)
    _instalar(casa, REPROVA, sem=SEM_A_STRING)
    assert pp.pino_que_vale(CONF, _compat(casa)) == NOVA


def test_versao_mais_velha_que_a_do_conf_nunca_vale(casa: Path) -> None:
    _instalar(casa, "GE-Proton11-6-x86_64")
    assert pp.pino_que_vale(CONF, _compat(casa)) == VELHA


def test_pasta_que_nao_e_proton_valido_nao_conta(casa: Path) -> None:
    (_compat(casa) / "GE-Proton11-9-x86_64").mkdir()
    assert pp.pino_que_vale(CONF, _compat(casa)) == VELHA


def test_o_conf_que_vale_leva_o_nome_novo_e_diz_que_foi_instalada(casa: Path) -> None:
    _instalar(casa, NOVA)
    vale = pp.conf_que_vale(CONF, _compat(casa))
    assert vale["name"] == NOVA and vale["instalada"] == "1"
    assert pp.conf_que_vale(CONF, _compat(casa) / "nao-existe") == CONF


def test_o_lock_aponta_todo_jogo_para_a_nova(casa: Path) -> None:
    """MORDIDA: o lock que usa o nome do conf deixa os jogos na 11-7."""
    _instalar(casa, NOVA)
    _mapa(casa, {"0": VELHA, "1": VELHA, "2": "proton_11"})
    resultado = _travar(casa)
    assert resultado["tool"] == NOVA
    assert set(_jogos(casa).values()) == {NOVA}


def test_o_fluxo_inteiro_deixa_so_a_mais_nova(casa: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Steam, Heroic e Lutris na velha: Steam e Heroic vão para a nova, e a velha só sai quando
    ninguém mais a cita. Aqui o Lutris (extensão) não cita nada; sai."""
    _instalar(casa, NOVA)
    _mapa(casa, {"0": VELHA, "1": VELHA, "2": VELHA})
    _jogo_do_heroic(casa, VELHA)
    antes = pp.versoes_que_sobram(casa)
    assert VELHA not in _nomes(antes), "o lock ainda não rodou: a velha segue em uso"

    _travar(casa)
    assert pp.apontar_os_lancadores_para_o_pino(casa, conf=CONF) == 1

    sobras = pp.versoes_que_sobram(casa)
    assert _nomes(sobras) == {VELHA}
    saiu, recusadas = pp.desinstalar_as_que_sobram(
        sobras, em_uso=lambda _p: False, steam_barra=lambda: None)
    assert [s.pasta.name for s in saiu] == [VELHA] and recusadas == {}
    assert sorted(p.name for p in _compat(casa).iterdir()) == [NOVA]
    assert set(_jogos(casa).values()) == {NOVA}


def test_o_heroic_passa_a_apontar_para_a_nova_e_guarda_a_copia(casa: Path) -> None:
    """MORDIDA: sem a escrita, o JSON do Heroic fica na velha."""
    _instalar(casa, NOVA)
    _jogo_do_heroic(casa, VELHA)
    _yml(casa, DO_HEROIC, "config.json", json.dumps({"defaultSettings": {"wineVersion": {
        "bin": f"{_compat(casa)}/{VELHA}/proton", "name": VELHA, "type": "proton"}}}))
    feito = censo.apontar_o_heroic_para(
        NOVA, _compat(casa), frozenset({VELHA}), lar=casa, aberto=lambda: False)
    assert feito.reescritas == 2
    jogo = json.loads((casa / DO_HEROIC / "GamesConfig" / "abc123.json").read_text())
    assert jogo["abc123"]["wineVersion"]["name"] == NOVA
    assert jogo["abc123"]["wineVersion"]["bin"] == f"{_compat(casa)}/{NOVA}/proton"
    assert jogo["abc123"]["winePrefix"] == "/p" and jogo["version"] == "v0"
    padrao = json.loads((casa / DO_HEROIC / "config.json").read_text())
    assert padrao["defaultSettings"]["wineVersion"]["name"] == NOVA
    assert list((casa / DO_HEROIC).glob("**/*.bak.hefesto-proton-*"))
    assert censo.proton_em_uso(casa).versoes == frozenset({NOVA})


def test_o_heroic_aberto_nao_e_escrito(casa: Path) -> None:
    """MORDIDA: escrever com o Heroic aberto perderia a edição quando ele regravasse ao sair."""
    _jogo_do_heroic(casa, VELHA)
    arquivo = casa / DO_HEROIC / "GamesConfig" / "abc123.json"
    antes = arquivo.read_bytes()
    feito = censo.apontar_o_heroic_para(
        NOVA, _compat(casa), frozenset({VELHA}), lar=casa, aberto=lambda: True)
    assert feito.reescritas == 0 and "aberto" in feito.recusa
    assert arquivo.read_bytes() == antes


def test_o_heroic_so_troca_o_proton_do_pino_e_deixa_o_resto(casa: Path) -> None:
    """O Wine do próprio Heroic e um Proton de fora da pasta do pino não são do pino."""
    _instalar(casa, NOVA)
    _yml(casa, DO_HEROIC, "GamesConfig/wine.json", json.dumps({"w": {"wineVersion": {
        "bin": "/opt/heroic/wine/bin/wine64", "name": VELHA, "type": "wine"}}}))
    _yml(casa, DO_HEROIC, "GamesConfig/fora.json", json.dumps({"f": {"wineVersion": {
        "bin": f"/outro/lugar/{VELHA}/proton", "name": VELHA, "type": "proton"}}}))
    feito = censo.apontar_o_heroic_para(
        NOVA, _compat(casa), frozenset({VELHA}), lar=casa, aberto=lambda: False)
    assert feito.reescritas == 0


def test_o_json_do_heroic_que_nao_se_le_fica_como_esta(casa: Path) -> None:
    _yml(casa, DO_HEROIC, "GamesConfig/quebrado.json", "{nao e json")
    feito = censo.apontar_o_heroic_para(
        NOVA, _compat(casa), frozenset({VELHA}), lar=casa, aberto=lambda: False)
    assert feito.reescritas == 0
    assert (casa / DO_HEROIC / "GamesConfig" / "quebrado.json").read_text() == "{nao e json"


def test_o_lutris_da_extensao_que_cita_a_velha_a_mantem(
        casa: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A extensão só se lê: o jogo do usuário segue na velha, e a velha não sai debaixo dele."""
    _instalar(casa, NOVA)
    _mapa(casa, {"0": VELHA, "1": VELHA})
    _jogo_do_lutris(casa, VELHA)
    _extensao_que_le(monkeypatch, VELHA)
    _travar(casa)
    assert set(_jogos(casa).values()) == {NOVA}
    assert VELHA not in _nomes(pp.versoes_que_sobram(casa))


def test_o_jogo_nomeado_fora_do_pino_mantem_a_versao_dele(casa: Path) -> None:
    """`jogos_fora_do_pino.txt` é escolha do usuário: o jogo fica, e a versão dele não sai."""
    _instalar(casa, NOVA)
    _mapa(casa, {"0": VELHA, "1": VELHA, "2": VELHA})
    arquivo = pp.fora_do_pino_path(casa)
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text("2\n", encoding="utf-8")
    _travar(casa)
    mapa = _jogos(casa)
    assert mapa["2"] == VELHA and mapa["1"] == NOVA
    assert VELHA not in _nomes(pp.versoes_que_sobram(casa))


def test_a_nova_que_reprova_nao_muda_jogo_nenhum_e_nada_sai(casa: Path) -> None:
    """A 11-9 reprova: o pino segue a 11-7, os jogos ficam, e a 11-7 (em uso) não sai."""
    _instalar(casa, REPROVA, sem=SEM_A_STRING)
    _mapa(casa, {"0": VELHA, "1": VELHA})
    antes = _config_vdf(casa).read_text(encoding="utf-8")
    resultado = _travar(casa)
    assert resultado["tool"] == VELHA
    assert set(_jogos(casa).values()) == {VELHA}
    assert _config_vdf(casa).read_text(encoding="utf-8") == antes
    assert VELHA not in _nomes(pp.versoes_que_sobram(casa))


def test_sem_nada_a_apontar_o_heroic_nao_e_tocado(casa: Path) -> None:
    """Só uma versão instalada: não há outra para trocar, e o JSON fica byte a byte."""
    _jogo_do_heroic(casa, VELHA)
    arquivo = casa / DO_HEROIC / "GamesConfig" / "abc123.json"
    antes = arquivo.read_bytes()
    assert pp.apontar_os_lancadores_para_o_pino(casa, conf=CONF) == 0
    assert arquivo.read_bytes() == antes


def test_o_ensure_nao_baixa_o_do_conf_quando_ha_uma_mais_nova(
        casa: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Sem isto o install baixaria a velha a cada vez que a varredura a apagasse."""
    _instalar(casa, NOVA)
    shutil_rmtree = __import__("shutil").rmtree
    shutil_rmtree(_compat(casa) / VELHA)
    conf = casa / "proton-pin.conf"
    conf.write_text(
        f"name={VELHA}\nurl=https://exemplo.invalido/x.tar.gz\nsha256={'a' * 64}\n",
        encoding="utf-8")
    rc = pp.main(["--ensure", "--conf", str(conf), "--compat-dir", str(_compat(casa)),
                  "--cache-dir", str(casa / "cache"), "--offline"])
    saida = capsys.readouterr().out
    assert rc == 0 and NOVA in saida and "não baixo" in saida
    assert not re.search(r"unavailable|checksum", saida)
    assert not (_compat(casa) / VELHA).exists()


def _o_duplo_clique_com(monkeypatch: pytest.MonkeyPatch, fixado: bool) -> tuple[str, list[str]]:
    """O `_reaplicar_as_correcoes` só com o Proton vivo; devolve o recibo e o que ele fez."""
    from hefesto_dualsense4unix.interface.pacotes import a09_sistema as a09

    feito: list[str] = []

    class _Pino:
        @staticmethod
        def apontar_os_lancadores_para_o_pino() -> int:
            feito.append("heroic")
            return 0

    def _travar(**_k: object) -> dict[str, object]:
        feito.append("lock")
        return {"status": "noop"}

    daemon = a09._daemon  # type: ignore[attr-defined]
    monkeypatch.setattr(daemon, "medir_jogos_com_steam_input", lambda: [])
    monkeypatch.setattr(a09, "_rodar_os_consertos", lambda jogos: {
        "ran": 0, "missing": 0, "steam_input": None, "steam_input_jogos": jogos})
    monkeypatch.setattr(daemon, "format_fix_safe_result", lambda _r: "")
    monkeypatch.setattr(a09, "_o_pino", lambda: (_Pino, _travar))
    monkeypatch.setattr(a09, "_porque_o_proton_nao_trava", lambda *_a: None)
    monkeypatch.setattr(a09, "proton_fixado", lambda: fixado)
    def _sobras() -> list[object]:
        feito.append("sobras")
        return []

    monkeypatch.setattr(a09, "_versoes_que_sobram", _sobras)
    from hefesto_dualsense4unix.integrations import camadas_vulkan as cv
    from hefesto_dualsense4unix.integrations import cura_por_estrada as cpe

    monkeypatch.setattr(cv, "gravar_camadas_da_steam_fora", lambda _ligar: None)
    monkeypatch.setattr(cv, "frase_do_ato", lambda _ligar: "")
    monkeypatch.setattr(cpe, "curar_todas_as_estradas", lambda **_k: [])
    monkeypatch.setattr(cpe, "frase_das_estradas", lambda _r: "")
    return a09._reaplicar_as_correcoes(), feito


def test_o_duplo_clique_trava_de_novo_mesmo_com_o_pino_velho_ja_fixado(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """MORDIDA: o `if not proton_fixado()` de volta não trava, e a nova nunca leva os jogos."""
    _recibo, feito = _o_duplo_clique_com(monkeypatch, fixado=True)
    assert feito == ["lock", "heroic", "sobras"]
