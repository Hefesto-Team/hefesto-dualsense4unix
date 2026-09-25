"""ESQUECER-OS-CONTROLES-01 — o produto esquece os controles e os devolve.

A régua do comando num lar de mentira: HOME, XDG, o ``/var/lib`` do produto, o
do BlueZ e a raiz do sistema desviados, com a guarda de ensaio ligada (qualquer
raiz de verdade faz o dono RECUSAR). Nada aqui toca no disco dela, no daemon
dela, no BlueZ ou na Steam de verdade.

AS DUAS PERGUNTAS QUE ELA MORDE:

1. **Todo lugar do inventário entra no comando.** A árvore de mentira é
   PLANTADA lendo o :data:`INVENTARIO` do dono (não uma lista digitada aqui):
   um lugar que o comando deixasse de mover fica no lugar depois do esquecer, e
   reprova.
2. **Todo arquivo que o produto grava no lar está classificado.** A varredura
   lê o código (os nomes de arquivo que o ``src/`` grava) e exige que cada um
   esteja no inventário ou na :data:`CLASSIFICACAO`, com a razão. Um arquivo
   novo com endereço de controle não nasce fora do comando sem alguém decidir.

E o ciclo da casa inteira (guardar → uninstall → «limpa?» → install →
devolver) contra uma máquina de mentira com Steam, Heroic e Lutris, com os
arquivos na forma que os donos do código escrevem — o uninstall e o install
são REPRODUZIDOS pelo que ``uninstall.sh`` e ``install.sh`` fazem (lido lá),
nunca rodados.
"""
from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.utils import memoria_dos_controles as m

RAIZ = Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"
SCRIPT_DA_CASA = RAIZ / "scripts" / "guardar-e-devolver-a-casa.py"

#: A faixa FORJADA da casa (``aa:bb:cc``), nas duas grafias.
ADAPTADOR_A = "AA:BB:CC:00:00:A1"
ADAPTADOR_B = "AA:BB:CC:00:00:B2"
FONE = "AA:BB:CC:00:00:77"
_TAB = "\t"


def _controle(i: int) -> str:
    return f"AA:BB:CC:00:00:0{i}"


def _chave(mac: str) -> str:
    return mac.replace(":", "").lower()


# ─── o lar de mentira ─────────────────────────────────────────────────────


@pytest.fixture
def raizes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> m.Raizes:
    lar = tmp_path / "lar"
    r = m.Raizes(
        lar=lar,
        config=lar / ".config",
        estado=lar / ".local/state",
        dados=lar / ".local/share",
        cache=lar / ".cache",
        execucao=tmp_path / "run",
        bluez=tmp_path / "var/lib/bluetooth",
        varlib=tmp_path / "var/lib/hefesto-dualsense4unix",
        guardado_do_root=tmp_path / "var/lib/hefesto-memoria-guardada",
        sistema=tmp_path / "sistema",
        repositorio=RAIZ,
    )
    for nome, valor in (("HOME", lar), ("XDG_CONFIG_HOME", r.config),
                        ("XDG_STATE_HOME", r.estado), ("XDG_DATA_HOME", r.dados),
                        ("XDG_CACHE_HOME", r.cache), ("XDG_RUNTIME_DIR", r.execucao),
                        ("HEFESTO_MEMORIA_BLUEZ", r.bluez),
                        ("HEFESTO_MEMORIA_VARLIB", r.varlib),
                        ("HEFESTO_MEMORIA_GUARDADO_ROOT", r.guardado_do_root),
                        ("HEFESTO_MEMORIA_SISTEMA", r.sistema)):
        monkeypatch.setenv(nome, str(valor))
    monkeypatch.setenv(m.ENV_ENSAIO, "1")
    lar.mkdir(parents=True)
    return r


class SistemaDeMentira(m.Sistema):
    """O daemon e a Steam do lar de mentira; o root roda no processo."""

    def __init__(self, daemon_de_pe: bool = True) -> None:
        self.de_pe = daemon_de_pe
        self.chamadas: list[str] = []
        self.bluetooth: list[m.Bluetooth] = []

    def daemon_ativo(self) -> bool:
        return self.de_pe

    def parar_daemon(self) -> None:
        self.chamadas.append("parar")
        self.de_pe = False

    def subir_daemon(self) -> None:
        self.chamadas.append("subir")
        self.de_pe = True

    def steam_aberta(self) -> bool:
        return False

    def rodar_parte_do_root(self, raizes: m.Raizes, verbo: str, pasta_root: Path | None,
                            seco: bool) -> dict[str, Any]:
        assert raizes.raizes_do_root_desviadas, "a régua nunca fala com o root de verdade"
        bt = m.Bluetooth(raizes)
        assert not bt.de_verdade
        self.bluetooth.append(bt)
        return m.executar_parte_do_root(raizes, verbo, pasta_root, seco=seco, bluetooth=bt)


def _info(classe: str, chave: str) -> str:
    return (f"[General]\nName=Aparelho\nClass={classe}\nTrusted=true\n\n"
            f"[LinkKey]\nKey={chave}\nType=4\nPINLength=0\n")


def _plantar_pareamento(r: m.Raizes, adaptador: str, aparelho: str, classe: str,
                        chave: str = "00112233445566778899AABBCCDDEEFF") -> None:
    pasta = r.bluez / adaptador / aparelho
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "info").write_text(_info(classe, chave), encoding="utf-8")
    (pasta / "attributes").write_text("[1]\nUUID=x\n", encoding="utf-8")
    cache = r.bluez / adaptador / "cache"
    cache.mkdir(exist_ok=True)
    (cache / aparelho).write_text(
        "[General]\nName=Aparelho\n\n[ServiceRecords]\n0x00010000=3601\n", encoding="utf-8")
    (r.bluez / adaptador / "settings").write_text("[General]\nAlias=Sala\n", encoding="utf-8")


def _perfil(nome: str, macs: list[str]) -> dict[str, Any]:
    dado: dict[str, Any] = {"name": nome, "priority": 5, "lightbar": {"r": 1, "g": 2, "b": 3}}
    if macs:
        dado["controllers"] = {_chave(mac): {"mic": {"muted": True}} for mac in macs}
    return dado


def _concreto(padrao: str) -> str:
    """Um caminho que o curinga do inventário casa — nome de mentira."""
    return padrao.replace("*", "de-mentira")


def plantar_a_mesa(r: m.Raizes, n: int, transporte: str, com_ajustes: bool) -> list[str]:
    """Planta a memória de ``n`` controles lendo o INVENTÁRIO do dono.

    ``transporte``: ``usb`` (nenhum pareamento), ``bt`` (todos pareados) ou
    ``misto`` (metade). Devolve os endereços dos controles.
    """
    macs = [_controle(i) for i in range(1, n + 1)]
    no_radio = {"usb": [], "bt": macs, "misto": macs[: max(1, n // 2)]}[transporte]
    fila = {"version": 3, "order": [
        {"addr": _chave(mac), "kind": "dualsense", "rank": i} for i, mac in enumerate(macs)]}
    for lugar in m.lugares(m.CONTROLES):
        if lugar.ato == m.PAREAMENTOS:
            for mac in no_radio:
                _plantar_pareamento(r, ADAPTADOR_A, mac, "0x002508")
            # O fone e o teclado Bluetooth dela NÃO são controle: ficam.
            _plantar_pareamento(r, ADAPTADOR_A, FONE, "0x240404")
            _plantar_pareamento(r, ADAPTADOR_B, "AA:BB:CC:00:00:78", "0x002540")
            continue
        base: Path = getattr(r, lugar.raiz)
        alvo = base / _concreto(lugar.caminho)
        alvo.parent.mkdir(parents=True, exist_ok=True)
        if lugar.ato == m.TIRAR_A_CHAVE:
            texto = json.dumps(_perfil("corrida", macs if com_ajustes else []),
                               indent=2, ensure_ascii=False) + "\n"
            alvo.write_text(texto, encoding="utf-8")
            (alvo.parent / "neutro.json").write_text(
                json.dumps(_perfil("neutro", []), indent=2) + "\n", encoding="utf-8")
        elif lugar.caminho.endswith(("bt-bonds", ".historico")) or "pre-uninstall" in lugar.caminho:
            for mac in no_radio or macs[:1]:
                f = alvo / "20260925-120000" / ADAPTADOR_A / mac / "info"
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(_info("0x002508", "AB" * 16), encoding="utf-8")
        else:
            alvo.write_text(json.dumps({"fila": fila, "lugar": lugar.chave}) + "\n",
                            encoding="utf-8")
    # Os irmãos que NÃO são memória de controle: têm de ficar onde estão.
    cfg = r.config / m.SLUG
    (cfg / "session.json").write_text('{"last_profile": "corrida"}', encoding="utf-8")
    (cfg / "paused.flag").write_text("", encoding="utf-8")
    (r.estado / m.SLUG / "gabinete.json").write_text("{}", encoding="utf-8")
    return macs


def _fora_das_pastas_guardadas(retrato: dict[str, str]) -> dict[str, str]:
    return {k: v for k, v in retrato.items()
            if m.NOME_DO_GUARDADO not in k and "hefesto-memoria-guardada" not in k}


def _arvore(tmp_path: Path) -> dict[str, str]:
    return _fora_das_pastas_guardadas(m.retrato(tmp_path))


# ─── 1. o inventário é o dos donos ────────────────────────────────────────


def test_o_inventario_aponta_para_onde_os_donos_gravam(raizes: m.Raizes) -> None:
    """Os caminhos do inventário são os que o código do produto resolve."""
    from hefesto_dualsense4unix.daemon.subsystems import (
        conexoes,
        external_identity,
        external_mask,
        identity,
    )
    from hefesto_dualsense4unix.integrations import bluez_dbus, diario_do_radio
    from hefesto_dualsense4unix.utils import maquina, xdg_paths

    def caminho(chave: str) -> Path:
        lugar = next(lg for lg in m.INVENTARIO if lg.chave == chave)
        return getattr(raizes, lugar.raiz) / lugar.caminho

    assert caminho("fila-dos-numeros") == identity.ControllerIdentityRegistry._path()
    assert caminho("fila-dos-numeros") == external_identity.ExternalIdentityRegistry._path()
    assert caminho("mascaras-por-aparelho") == external_mask.ExternalMaskRegistry._path()
    assert caminho("declaracao-da-mesa") == maquina.caminho_da_maquina()
    assert caminho("lugares-dos-adaptadores") == bluez_dbus._memoria_dos_lugares()
    assert caminho("conexao-zumbi") == conexoes.caminho_do_diario()
    assert (raizes.config / m.SLUG / "profiles") == xdg_paths.profiles_dir()
    assert raizes.varlib.name == diario_do_radio.DIARIO_DO_ROOT.parent.name
    assert diario_do_radio.DIARIO_DO_ROOT.parent == m.VARLIB_DO_PRODUTO
    diario = next(lg for lg in m.INVENTARIO if lg.chave == "diario-do-radio")
    assert fnmatch.fnmatch(diario_do_radio.NOME_DO_DIARIO, Path(diario.caminho).name)
    assert fnmatch.fnmatch(diario_do_radio.NOME_DO_DIARIO + ".1", Path(diario.caminho).name)


def test_as_raizes_seguem_a_regra_do_platformdirs(raizes: m.Raizes) -> None:
    from hefesto_dualsense4unix.utils import xdg_paths

    do_ambiente = m.Raizes.do_ambiente()
    assert do_ambiente.config / m.SLUG == xdg_paths.config_dir()
    assert do_ambiente.estado / m.SLUG == xdg_paths.state_dir()
    assert do_ambiente.dados / m.SLUG == xdg_paths.data_dir()
    assert do_ambiente.cache / m.SLUG == xdg_paths.cache_dir()
    assert xdg_paths._DIRS.appname == m.SLUG


def test_os_espelhos_sao_os_dos_donos() -> None:
    from hefesto_dualsense4unix.daemon.launch_env import ENV_ALLOWLIST
    from hefesto_dualsense4unix.integrations import camadas_vulkan, cura_por_estrada
    from hefesto_dualsense4unix.profiles import loader

    assert m.VARIAVEIS_DO_PRODUTO == ENV_ALLOWLIST
    assert m.PASTAS_DO_HEROIC == camadas_vulkan._CONFIG_DO_HEROIC
    assert cura_por_estrada.CHAVE_DO_HEROIC == "enviromentOptions"
    historico = next(lg for lg in m.INVENTARIO if lg.chave == "versoes-antigas-dos-perfis")
    assert historico.caminho.endswith(loader.HISTORICO_DIR_NAME)
    estilos = next(lg for lg in m.INVENTARIO if lg.chave == "ajustes-por-controle-dos-estilos")
    assert f"/{loader.ESTILOS_DE_JOGO_DIR_NAME}/" in estilos.caminho
    uninstall = (RAIZ / "uninstall.sh").read_text(encoding="utf-8")
    for app_id in m.IDS_DE_FLATPAK_DO_HEFESTO:
        assert f'"{app_id}"' in uninstall


def test_o_heroic_e_o_mesmo_que_a_cura_por_estrada_acha(raizes: m.Raizes) -> None:
    from hefesto_dualsense4unix.integrations import cura_por_estrada

    for rel in m.PASTAS_DO_HEROIC:
        pasta = raizes.lar / rel
        pasta.mkdir(parents=True)
        (pasta / "config.json").write_text("{}", encoding="utf-8")
        achada = cura_por_estrada._pasta_do_heroic(raizes.lar)
        assert achada is not None
        assert achada / "config.json" in m._achar_heroic(raizes)


# ─── 2. todo arquivo que o produto grava tem classificação ────────────────

_EXT = r"(?:json|jsonl|flag|txt|conf|log|boot|lock|env|pid|ini|toml|state|dat)"
_JUNTADO = re.compile(
    r"\b(?:config_dir|state_dir|data_dir|cache_dir|profiles_dir|launch_env_dir|runtime_dir)"
    r'\([^()]*\)\s*/\s*"([^"]+)"')
_CONSTANTE = re.compile(
    r'^\s*_?[A-Z][A-Z0-9_]*\s*(?::[^=\n]+)?=\s*"([\w./-]+\.' + _EXT + r')"', re.M)


def nomes_que_o_codigo_grava() -> dict[str, str]:
    """Todo nome de arquivo que o ``src/`` junta a uma pasta do lar, ou guarda
    numa constante — ``{nome: primeiro endereço}``."""
    achados: dict[str, str] = {}
    for arq in sorted(SRC.rglob("*.py")):
        texto = arq.read_text(encoding="utf-8")
        for padrao in (_JUNTADO, _CONSTANTE):
            for achado in padrao.finditer(texto):
                linha = texto.count("\n", 0, achado.start()) + 1
                achados.setdefault(achado.group(1), f"{arq.relative_to(RAIZ)}:{linha}")
    return achados


def test_todo_arquivo_que_o_produto_grava_esta_classificado() -> None:
    faltando = {n: onde for n, onde in nomes_que_o_codigo_grava().items()
                if n not in m.CLASSIFICACAO}
    assert not faltando, (
        "arquivos que o produto grava e que ninguém decidiu se são memória de "
        "controle — ponha cada um no INVENTARIO (se guarda endereço, número, cor, "
        f"nome, máscara ou adaptador) ou na CLASSIFICACAO, com a razão: {faltando}"
    )


def test_a_classificacao_nao_tem_nome_morto() -> None:
    vivos = nomes_que_o_codigo_grava()
    mortos = sorted(set(m.CLASSIFICACAO) - set(vivos))
    assert not mortos, f"nomes na CLASSIFICACAO que o código não grava mais: {mortos}"


def test_a_memoria_de_controle_classificada_tem_lugar_no_inventario() -> None:
    chaves = {lg.chave: lg for lg in m.INVENTARIO}
    for nome, (classe, razao) in m.CLASSIFICACAO.items():
        if classe != m.CONTROLES:
            continue
        chave = razao.split(" ", 1)[0]
        assert chave in chaves, f"{nome}: a razão tem de nomear o lugar ({razao!r})"
        lugar = chaves[chave]
        assert lugar.alcance == m.CONTROLES
        assert Path(nome).name in lugar.caminho or fnmatch.fnmatch(
            Path(nome).name, Path(lugar.caminho).name), (nome, lugar.caminho)


# ─── 3. o que é controle no BlueZ ─────────────────────────────────────────


@pytest.mark.parametrize(
    ("info", "e_controle"),
    [
        ("[General]\nClass=0x002508\n", True),       # DualSense, DS4, Pro, 8BitDo
        ("[General]\nClass=0x002504\n", True),       # joystick
        ("[General]\nClass=0x240404\n", False),      # fone de ouvido
        ("[General]\nClass=0x002540\n", False),      # teclado
        ("[General]\nClass=0x002580\n", False),      # mouse
        ("[General]\nClass=0x0025C8\n", False),      # combo teclado+apontador
        ("[General]\nAppearance=0x03c4\n", True),    # gamepad só-LE
        ("[General]\nAppearance=0x03c2\n", False),   # mouse só-LE
        ("[General]\nName=Wireless Controller\n", False),  # sem classe: não adivinha
        ("lixo sem seção", False),
    ],
)
def test_so_aparelho_com_classe_de_controle_e_esquecido(info: str, e_controle: bool) -> None:
    assert m.e_controle_pelo_info(info) is e_controle


# ─── 4. esquecer e devolver: a árvore volta idêntica ──────────────────────


@pytest.mark.parametrize("n", [1, 2, 3, 4])
@pytest.mark.parametrize("transporte", ["usb", "bt", "misto"])
@pytest.mark.parametrize("com_ajustes", [True, False], ids=["com-ajustes", "sem-ajustes"])
def test_esquecer_e_devolver_devolvem_a_arvore_identica(
    raizes: m.Raizes, tmp_path: Path, n: int, transporte: str, com_ajustes: bool
) -> None:
    macs = plantar_a_mesa(raizes, n, transporte, com_ajustes)
    antes = _arvore(tmp_path)
    sistema = SistemaDeMentira()

    relato = m.guardar(raizes, m.CONTROLES, sistema)

    # Nada de memória de controle ficou onde estava — lido do INVENTÁRIO.
    for lugar in m.lugares(m.CONTROLES, m.USUARIO):
        for caminho in m.achar(raizes, lugar):
            if lugar.ato == m.TIRAR_A_CHAVE:
                dado = json.loads(caminho.read_text(encoding="utf-8"))
                assert m.CHAVE_DOS_AJUSTES_POR_CONTROLE not in dado, caminho
            else:
                pytest.fail(f"{lugar.chave}: {caminho} ficou no lugar depois do esquecer")
    for lugar in m.lugares(m.CONTROLES, m.ROOT):
        if lugar.ato == m.PAREAMENTOS:
            assert m.pareamentos_de_controle(raizes.bluez) == []
        else:
            assert not list(raizes.varlib.glob(lugar.caminho)), lugar.chave
    # O resto do perfil, o fone, o teclado e os irmãos ficaram.
    perfil = json.loads((raizes.config / m.SLUG / "profiles/de-mentira.json")
                        .read_text(encoding="utf-8"))
    assert perfil["lightbar"] == {"r": 1, "g": 2, "b": 3}
    assert (raizes.bluez / ADAPTADOR_A / FONE / "info").is_file()
    assert (raizes.bluez / ADAPTADOR_A / "cache" / FONE).is_file()
    assert (raizes.bluez / ADAPTADOR_B / "AA:BB:CC:00:00:78" / "info").is_file()
    assert (raizes.config / m.SLUG / "session.json").is_file()
    assert (raizes.estado / m.SLUG / "gabinete.json").is_file()
    # O daemon parou e voltou; o bluetoothd só foi parado se havia pareamento.
    assert sistema.chamadas == ["parar", "subir"]
    esquecido = [bt for bt in sistema.bluetooth if bt.chamadas]
    if transporte == "usb":
        assert esquecido == []
    else:
        assert esquecido[0].chamadas == [
            "mask --runtime bluetooth.service",
            "stop --job-mode=replace-irreversibly bluetooth.service",
            "unmask --runtime bluetooth.service",
            "start bluetooth.service",
            "reset-failed hefesto-bt-agent.service",
            "start hefesto-bt-agent.service",
        ]
    assert relato.pasta is not None and relato.pasta.parent == raizes.guardado

    m.devolver(raizes, sistema)

    assert _arvore(tmp_path) == antes, "o devolver não devolveu byte a byte"
    assert len(macs) == n
    # O devolver também para o daemon (ninguém regrava o que volta) e o sobe.
    assert sistema.chamadas == ["parar", "subir", "parar", "subir"]


def test_o_seco_nao_toca_em_nada(raizes: m.Raizes, tmp_path: Path) -> None:
    plantar_a_mesa(raizes, 4, "misto", True)
    antes = m.retrato(tmp_path)
    sistema = SistemaDeMentira()
    relato = m.guardar(raizes, m.CONTROLES, sistema, seco=True)
    assert m.retrato(tmp_path) == antes
    assert sistema.chamadas == []
    assert any("controllers.json" in linha for linha in relato.linhas)
    assert any("pareamento do controle" in linha for linha in relato.linhas)


def test_o_devolver_nao_planta_chave_velha_sobre_pareamento_vivo(
    raizes: m.Raizes, tmp_path: Path
) -> None:
    """Pareado de novo durante o teste (outro adaptador, chave nova): o vivo fica."""
    plantar_a_mesa(raizes, 2, "bt", True)
    sistema = SistemaDeMentira()
    m.guardar(raizes, m.CONTROLES, sistema)
    novo = raizes.bluez / ADAPTADOR_B / _controle(1)
    _plantar_pareamento(raizes, ADAPTADOR_B, _controle(1), "0x002508",
                        chave="FFEEDDCCBBAA99887766554433221100")
    vivo = m.retrato(novo)

    relato = m.devolver(raizes, sistema)

    assert m.retrato(novo) == vivo, "o pareamento vivo foi tocado"
    assert not (raizes.bluez / ADAPTADOR_A / _controle(1)).exists(), (
        "a chave velha voltou ao lado da viva: o controle teria casa em dois adaptadores"
    )
    assert (raizes.bluez / ADAPTADOR_A / _controle(2) / "info").is_file()
    assert any("já está pareado de novo" in linha for linha in relato.linhas)


def test_o_teste_que_produziu_arquivos_nao_perde_nada(raizes: m.Raizes) -> None:
    """O que o teste gravou vai para depois-do-teste, e não some."""
    plantar_a_mesa(raizes, 1, "usb", True)
    sistema = SistemaDeMentira()
    relato = m.guardar(raizes, m.CONTROLES, sistema)
    fila_nova = raizes.config / m.SLUG / "controllers.json"
    fila_nova.write_text('{"version": 3, "order": []}', encoding="utf-8")
    m.devolver(raizes, sistema)
    assert relato.pasta is not None
    guardadas = list((relato.pasta / "depois-do-teste").rglob("controllers.json"))
    assert len(guardadas) == 1
    assert guardadas[0].read_text(encoding="utf-8") == '{"version": 3, "order": []}'


def test_o_que_o_teste_criou_onde_nao_havia_nada_sai_no_devolver(
    raizes: m.Raizes, tmp_path: Path
) -> None:
    """«Exatamente como estava» inclui o que NÃO estava.

    Antes do esquecer: sem máscaras, sem versões antigas, sem declaração, e um
    perfil sem ajuste por controle. O teste cria os três, grava um perfil novo e
    põe um ajuste por controle no perfil que não tinha nenhum (é o que o botão
    do mic faz). O devolver deixa a árvore como estava, e o que o teste criou
    fica em ``depois-do-teste``.
    """
    plantar_a_mesa(raizes, 2, "misto", True)
    cfg = raizes.config / m.SLUG
    for rel in ("controller_masks.json", "maquina.json"):
        (cfg / rel).unlink()
    import shutil

    shutil.rmtree(cfg / "profiles/.historico")
    diario_novo = raizes.estado / m.SLUG / "radio-diario.jsonl.1"
    assert not diario_novo.exists()
    antes = _arvore(tmp_path)
    sistema = SistemaDeMentira()
    relato = m.guardar(raizes, m.CONTROLES, sistema)
    assert relato.pasta is not None

    # o teste
    (cfg / "controller_masks.json").write_text('{"aa:bb:cc:00:00:01": "xbox"}',
                                              encoding="utf-8")
    (cfg / "maquina.json").write_text('{"versao": 1}', encoding="utf-8")
    (cfg / "profiles/.historico/neutro").mkdir(parents=True)
    (cfg / "profiles/.historico/neutro/1.json").write_text("{}", encoding="utf-8")
    (cfg / "profiles/novo.json").write_text(json.dumps(_perfil("novo", [])), encoding="utf-8")
    neutro = cfg / "profiles/neutro.json"
    neutro.write_text(json.dumps(_perfil("neutro", [_controle(1)]), indent=2) + "\n",
                      encoding="utf-8")
    diario_novo.write_text('{"ev": "novo"}\n', encoding="utf-8")

    relato2 = m.devolver(raizes, sistema)

    assert _arvore(tmp_path) == antes, "o que o teste criou ficou no lugar"
    depois = relato.pasta / "depois-do-teste"
    for nome in ("controller_masks.json", "maquina.json", "novo.json", "neutro.json",
                 "radio-diario.jsonl.1", "1.json"):
        assert list(depois.rglob(nome)), f"{nome} não foi guardado em depois-do-teste"
    assert str(cfg / "profiles/novo.json") in relato2.tirados


def test_o_devolver_a_seco_nao_toca_em_nada(raizes: m.Raizes, tmp_path: Path) -> None:
    """O passo em que ela LÊ o que vai ser sobrescrito não pode sobrescrever."""
    plantar_a_mesa(raizes, 3, "misto", True)
    sistema = SistemaDeMentira()
    m.guardar(raizes, m.CONTROLES, sistema)
    cfg = raizes.config / m.SLUG
    (cfg / "controllers.json").write_text('{"order": []}', encoding="utf-8")
    (cfg / "profiles/novo.json").write_text("{}", encoding="utf-8")
    _plantar_pareamento(raizes, ADAPTADOR_B, _controle(1), "0x002508", chave="12" * 16)
    antes = m.retrato(tmp_path)
    chamadas = list(sistema.chamadas)

    relato = m.devolver(raizes, sistema, seco=True)

    assert m.retrato(tmp_path) == antes, "o devolver a seco mexeu no disco"
    assert sistema.chamadas == chamadas, "o devolver a seco parou o daemon"
    texto = "\n".join(relato.linhas)
    assert f"devolver por cima        {cfg / 'controllers.json'}" in texto
    assert f"tirar (não existia)      {cfg / 'profiles/novo.json'}" in texto
    assert "já está pareado de novo" in texto
    assert "gravaria a lápide" in texto


def test_o_devolver_enterra_a_chave_velha_para_o_autorestore(
    raizes: m.Raizes, tmp_path: Path
) -> None:
    """O acervo que volta traz a chave VELHA do controle pareado de novo.

    O ``bt_bonds_autorestore.sh`` só confere o MESMO adaptador: com o controle
    vivo no B e a cópia velha no A, a próxima morte do ``bluetoothd`` plantaria
    a chave velha no A. O devolver grava a lápide que o autorestore respeita
    (``<epoch> <adaptador> <controle>``), no adaptador antigo.
    """
    plantar_a_mesa(raizes, 2, "bt", True)
    sistema = SistemaDeMentira()
    m.guardar(raizes, m.CONTROLES, sistema)
    _plantar_pareamento(raizes, ADAPTADOR_B, _controle(1), "0x002508", chave="34" * 16)

    m.devolver(raizes, sistema)

    lapides = raizes.varlib / "bt-bonds" / ".lapides"
    linhas = lapides.read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1, linhas
    quando, adaptador, controle = linhas[0].split()
    assert int(quando) > 0 and (adaptador, controle) == (ADAPTADOR_A, _controle(1))
    assert oct(lapides.stat().st_mode & 0o777) == oct(0o600)
    # O controle que não foi pareado de novo voltou, e não ganhou lápide.
    assert (raizes.bluez / ADAPTADOR_A / _controle(2) / "info").is_file()


def test_a_parte_do_root_que_cai_no_meio_deixa_o_manifesto(
    raizes: m.Raizes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Uma queda no meio da parte do root não pode deixar pareamento órfão.

    O manifesto do root nasce antes do primeiro mover e cresce a cada um: o
    devolver acha o que já saiu, devolve, e a árvore volta como estava — sem
    tirar do lugar o que o guardar interrompido nunca moveu.
    """
    plantar_a_mesa(raizes, 2, "bt", True)
    antes = _arvore(tmp_path)
    sistema = SistemaDeMentira()
    real = m.mover
    contador = {"n": 0}

    def mover_que_cai(origem: Path, destino: Path) -> None:
        contador["n"] += 1
        if contador["n"] == 2:
            raise OSError(28, "disco cheio")
        real(origem, destino)

    monkeypatch.setattr(m, "mover", mover_que_cai)
    with pytest.raises(OSError):
        m.guardar(raizes, m.CONTROLES, sistema)
    monkeypatch.setattr(m, "mover", real)
    assert sistema.chamadas == ["parar", "subir"], "o daemon ficou parado depois da queda"

    m.devolver(raizes, sistema)

    assert _arvore(tmp_path) == antes


def test_sem_privilegio_nada_se_move(raizes: m.Raizes, tmp_path: Path) -> None:
    """Sem privilégio a parte do root recusa — e ANTES de um byte sair."""

    class SemPrivilegio(SistemaDeMentira):
        def rodar_parte_do_root(self, raizes: m.Raizes, verbo: str, pasta_root: Path | None,
                                seco: bool) -> dict[str, Any]:
            raise m.RecusaError("sudo: a password is required")

    plantar_a_mesa(raizes, 2, "misto", True)
    antes = m.retrato(tmp_path)
    sistema = SemPrivilegio()
    for alcance in m.ALCANCES:
        with pytest.raises(m.RecusaError):
            m.guardar(raizes, alcance, sistema)
    assert m.retrato(tmp_path) == antes
    assert not raizes.guardado.exists(), "a recusa deixou uma pasta vazia"
    assert sistema.chamadas == [], "a recusa parou o daemon"


def test_com_a_steam_aberta_a_casa_recusa(raizes: m.Raizes, tmp_path: Path) -> None:
    """A Steam regrava o ``localconfig.vdf`` ao sair: guardar ou devolver com
    ela aberta produziria uma cópia velha, ou seria desfeito por ela."""

    class ComSteam(SistemaDeMentira):
        aberta = True

        def steam_aberta(self) -> bool:
            return self.aberta

    plantar_a_mesa(raizes, 1, "usb", True)
    instalar_de_mentira(raizes)
    antes = m.retrato(tmp_path)
    sistema = ComSteam()
    with pytest.raises(m.RecusaError, match="Steam"):
        m.guardar(raizes, m.CASA, sistema)
    assert m.retrato(tmp_path) == antes and sistema.chamadas == []
    sistema.aberta = False
    m.guardar(raizes, m.CASA, sistema)
    sistema.aberta = True
    depois_do_guardar = m.retrato(tmp_path)
    with pytest.raises(m.RecusaError, match="Steam"):
        m.devolver(raizes, sistema)
    assert m.retrato(tmp_path) == depois_do_guardar


# ─── 5. as guardas ────────────────────────────────────────────────────────


def test_a_guarda_do_ensaio_recusa_o_lar_de_verdade(
    raizes: m.Raizes, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pwd

    real = Path(pwd.getpwuid(os.getuid()).pw_dir)
    com_lar_real = m.Raizes(**{**raizes.__dict__, "lar": real})
    with pytest.raises(m.RecusaError):
        m.conferir_o_ensaio(com_lar_real)
    com_config_real = m.Raizes(**{**raizes.__dict__, "config": real / ".config"})
    with pytest.raises(m.RecusaError):
        m.conferir_o_ensaio(com_config_real)
    com_bluez_real = m.Raizes(**{**raizes.__dict__, "bluez": m.BLUEZ_REAL})
    with pytest.raises(m.RecusaError):
        m.guardar(com_bluez_real, m.CONTROLES, SistemaDeMentira())


def test_raizes_do_root_meio_desviadas_recusam(raizes: m.Raizes) -> None:
    meio = m.Raizes(**{**raizes.__dict__, "bluez": m.BLUEZ_REAL})
    with pytest.raises(m.RecusaError):
        m.Sistema().rodar_parte_do_root(meio, "esquecer",
                                        meio.guardado_do_root / "20260925-120000-controles",
                                        seco=True)


def test_a_pasta_do_root_fora_da_forma_recusa(raizes: m.Raizes) -> None:
    for pasta in (raizes.guardado_do_root / "../../etc", Path("/etc"),
                  raizes.guardado_do_root / "qualquer-nome"):
        with pytest.raises(m.RecusaError):
            m.executar_parte_do_root(raizes, "esquecer", pasta, seco=True)


def test_o_sistema_de_verdade_e_inerte_no_ensaio(raizes: m.Raizes) -> None:
    """No ensaio, o daemon e a Steam de que ele falaria são os DELA: nada."""
    s = m.Sistema()
    assert s.ensaio
    assert s.daemon_ativo() is False
    assert s.steam_aberta() is False
    assert s._systemctl_do_usuario("stop", m.UNIT_DO_DAEMON) == 3


# ─── 6. a casa inteira: guardar → uninstall → limpa? → install → devolver ──


def _localconfig(appids: list[str]) -> str:
    blocos = "".join(
        f'{_TAB * 5}"{a}"\n{_TAB * 5}{{\n{_TAB * 6}"LaunchOptions"{_TAB * 2}'
        f'"VKD3D_CONFIG=dxr %command%"\n{_TAB * 6}"playtime"{_TAB * 2}"42"\n{_TAB * 5}}}\n'
        for a in appids)
    return ('"UserLocalConfigStore"\n{\n'
            f'{_TAB}"Software"\n{_TAB}{{\n{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
            f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n{_TAB * 4}"apps"\n{_TAB * 4}{{\n'
            f"{blocos}{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n")


def _config_vdf() -> str:
    return ('"InstallConfigStore"\n{\n'
            f'{_TAB}"Software"\n{_TAB}{{\n{_TAB * 2}"Valve"\n{_TAB * 2}{{\n'
            f'{_TAB * 3}"Steam"\n{_TAB * 3}{{\n{_TAB * 4}"CompatToolMapping"\n{_TAB * 4}{{\n'
            f"{_TAB * 4}}}\n{_TAB * 3}}}\n{_TAB * 2}}}\n{_TAB}}}\n}}\n")


AMBIENTE_DA_PONTE = {
    "SDL_GAMECONTROLLER_IGNORE_DEVICES": "0x054c/0x0ce6",
    "PROTON_DISABLE_HIDRAW": "0x054C/0x0CE6",
}


def instalar_de_mentira(r: m.Raizes) -> None:
    """O que o ``install.sh`` e o daemon escrevem, pelos DONOS do código.

    O atalho nas Opções de Inicialização (``apply_wrapper_vdf_text``, o que o
    install roda sem flag), o Proton pinado (``build_compat_tool_mapping`` + o
    registro que o ``--lock`` grava), o ambiente da ponte no Heroic e no
    Flatpak do Lutris (``cura_por_estrada``, a carona do daemon) e os
    artefatos do lar e do sistema que o install copia.
    """
    from hefesto_dualsense4unix.integrations import cura_por_estrada, proton_pin
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    steam = r.lar / ".steam/steam"
    (steam / "steamapps").mkdir(parents=True, exist_ok=True)
    (steam / "steam.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    vdf = steam / "userdata/12345/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True, exist_ok=True)
    texto = vdf.read_text(encoding="utf-8") if vdf.is_file() else _localconfig(["100", "200"])
    novo, _aplicados, _ = slo.apply_wrapper_vdf_text(texto)
    vdf.write_text(novo, encoding="utf-8")
    cfg = steam / "config/config.vdf"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    base = cfg.read_text(encoding="utf-8") if cfg.is_file() else _config_vdf()
    nome = proton_pin.parse_pin_conf(
        (RAIZ / "assets/proton-pin.conf").read_text(encoding="utf-8"))["name"]
    travado, mudancas = proton_pin.build_compat_tool_mapping(
        base, tool_name=nome, appids=["100", "200"])
    cfg.write_text(travado, encoding="utf-8")
    estado = r.estado / m.SLUG
    estado.mkdir(parents=True, exist_ok=True)
    (estado / "proton-pin-lock.json").write_text(
        json.dumps({"tool_name": nome, "changes": mudancas}), encoding="utf-8")
    heroic = r.lar / ".config/heroic/config.json"
    heroic.parent.mkdir(parents=True, exist_ok=True)
    if not heroic.is_file():
        heroic.write_text(json.dumps({"defaultSettings": {"enviromentOptions": [
            {"key": "MANGOHUD", "value": "1"}]}}), encoding="utf-8")
    cura_por_estrada._escrever_no_heroic(heroic, dict(AMBIENTE_DA_PONTE))
    override = r.dados / "flatpak/overrides/net.lutris.Lutris"
    override.parent.mkdir(parents=True, exist_ok=True)
    if not override.is_file():
        override.write_text("[Context]\ndevices=all;\n", encoding="utf-8")
    cura_por_estrada._escrever_no_override(override, dict(AMBIENTE_DA_PONTE))
    # O que o install copia para o lar (``install.sh``, passos 4-5) e para o
    # sistema (``scripts/lib/camada_de_maquina.sh``, ``install_udev.sh``).
    for rel in (".config/systemd/user/hefesto-dualsense4unix.service",
                ".config/autostart/hefesto-dualsense4unix.desktop",
                ".local/bin/hefesto-dualsense4unix",
                ".local/share/hefesto-dualsense4unix/bin/hefesto-launch",
                ".config/wireplumber/wireplumber.conf.d/"
                "51-hefesto-dualsense-no-default-source.conf"):
        (r.lar / rel).parent.mkdir(parents=True, exist_ok=True)
        (r.lar / rel).write_text("# do install\n", encoding="utf-8")
    (estado / "gabinete.json").write_text("{}", encoding="utf-8")
    (r.config / m.SLUG / "profiles").mkdir(parents=True, exist_ok=True)
    (r.config / m.SLUG / "profiles/fallback.json").write_text(
        json.dumps(_perfil("fallback", []), indent=2) + "\n", encoding="utf-8")
    for rel in ("etc/udev/rules.d/73-hefesto-ps5-controller.rules",
                "etc/modprobe.d/hefesto-dualsense-storm.conf",
                "etc/systemd/system/hefesto-hidraw-broker.service",
                "usr/local/lib/hefesto-dualsense4unix/bt_bonds_snapshot.sh"):
        (r.sistema / rel).parent.mkdir(parents=True, exist_ok=True)
        (r.sistema / rel).write_text("# do install\n", encoding="utf-8")
    (r.sistema / "etc/kernelstub").mkdir(parents=True, exist_ok=True)
    (r.sistema / "etc/kernelstub/configuration").write_text(
        '{"user": {"kernel_options": ["usbcore.quirks=054c:0ce6:gn,054c:0df2:gn"]}}',
        encoding="utf-8")
    r.varlib.mkdir(parents=True, exist_ok=True)


def desinstalar_de_mentira(r: m.Raizes, monkeypatch: pytest.MonkeyPatch) -> None:
    """O que o ``uninstall.sh --purge-config`` faz no lar, lido lá, reproduzido.

    - o strip das Opções de Inicialização (``steam_launch_options --strip``,
      que é ``transform_vdf_text(texto, "strip")``) e o destravar do Proton
      (``proton_pin --unlock``), pelos donos;
    - apaga ``~/.config/<slug>`` (com o backup ``.backup-<ts>`` ao lado), a
      pasta de dados, o cache e os arquivos de estado que ele NOMEIA
      (``launch_env``, ``wrapper-visto.json``, ``gabinete.json``,
      ``lugares-dos-adaptadores.json``, os diários, ``kernel.log``,
      ``camadas-vulkan.json``), tenta o ``rmdir`` da pasta de estado;
    - tira as units, o atalho, o binário, o drop-in do WirePlumber;
    - do lado do sistema, o que ele remove com sudo; o quirk do boot FICA sem
      ``--remove-usb-quirk``;
    - NÃO toca no ``config.json`` do Heroic nem nos ``overrides`` do Flatpak (o
      ``uninstall.sh`` não os cita), nem no ``conexao-zumbi.json``.
    """
    import shutil

    from hefesto_dualsense4unix.integrations import proton_pin
    from hefesto_dualsense4unix.integrations import steam_launch_options as slo

    for vdf in slo.discover_vdfs(r.lar):
        limpo, _mudadas = slo.transform_vdf_text(vdf.read_text(encoding="utf-8"), "strip")
        vdf.write_text(limpo, encoding="utf-8")
    monkeypatch.setattr(proton_pin, "_steam_gate", lambda: None)
    feito = proton_pin.unlock_games_from_pinned_proton(home=r.lar)
    assert feito["status"] == "unlocked", feito
    estado = r.estado / m.SLUG
    for nome in ("launch_env", "wrapper-visto.json", "teclado-na-tela.conf", "gabinete.json",
                 "lugares-dos-adaptadores.json", "radio-diario.jsonl", "radio-diario.jsonl.1",
                 "kernel.log", "kernel-watch.boot", "camadas-vulkan.json"):
        alvo = estado / nome
        if alvo.is_dir():
            shutil.rmtree(alvo)
        elif alvo.exists():
            alvo.unlink()
    with pytest.raises(OSError):  # ``rmdir ... || true``: o zumbi segura a pasta
        estado.rmdir()
    backup = r.config / f"{m.SLUG}.backup-1790000000"
    backup.mkdir()
    for pasta in (r.config / m.SLUG, r.dados / m.SLUG, r.cache / m.SLUG):
        if pasta.is_dir():
            shutil.copytree(pasta, backup / pasta.name, dirs_exist_ok=True)
            shutil.rmtree(pasta)
    for rel in (".config/systemd/user/hefesto-dualsense4unix.service",
                ".config/autostart/hefesto-dualsense4unix.desktop",
                ".local/bin/hefesto-dualsense4unix",
                ".config/wireplumber/wireplumber.conf.d/"
                "51-hefesto-dualsense-no-default-source.conf"):
        (r.lar / rel).unlink(missing_ok=True)
    for rel in ("etc/udev/rules.d/73-hefesto-ps5-controller.rules",
                "etc/modprobe.d/hefesto-dualsense-storm.conf",
                "etc/systemd/system/hefesto-hidraw-broker.service"):
        (r.sistema / rel).unlink()
    shutil.rmtree(r.sistema / "usr/local/lib/hefesto-dualsense4unix")
    if r.varlib.is_dir():
        shutil.rmtree(r.varlib)


def test_a_casa_inteira_da_a_volta_completa(
    raizes: m.Raizes, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    r = raizes
    plantar_a_mesa(r, 4, "misto", True)
    instalar_de_mentira(r)
    (r.estado / m.SLUG / "camadas-vulkan.json").write_text(json.dumps(
        {"100": {"EOSOverlay.json": {"feito": "religada", "escolha": "manter"}}}),
        encoding="utf-8")
    antes = _arvore(tmp_path)
    sistema = SistemaDeMentira()

    # 1. guardar: copia a casa (os originais FICAM para o uninstall ler) e
    #    esquece os pareamentos dos controles.
    relato = m.guardar(r, m.CASA, sistema)
    assert relato.pasta is not None
    assert (r.estado / m.SLUG / "proton-pin-lock.json").is_file()
    assert (r.config / m.SLUG / "controllers.json").is_file()
    assert m.pareamentos_de_controle(r.bluez) == []
    manifesto = m.Manifesto.ler(relato.pasta)
    guardados = {i.chave for i in manifesto.itens}
    assert {"configuracao-inteira", "steam-opcoes-e-entrada", "steam-proton-pinado",
            "heroic-ambiente", "flatpak-ambiente", "conexao-zumbi",
            "camadas-vulkan"} <= guardados
    # O que o install recria NÃO vai para a pasta.
    origens = " ".join(i.origem for i in manifesto.itens)
    assert "proton-pin-lock.json" not in origens and "gabinete.json" not in origens

    # 2. o uninstall, reproduzido.
    desinstalar_de_mentira(r, monkeypatch)

    # 3. «a máquina está limpa?» — o que sobrar e não é de propósito é defeito
    #    do uninstall. Na máquina de mentira sobram EXATAMENTE os três que o
    #    uninstall.sh não visita.
    rastros = m.conferir_a_casa(r)
    defeitos = sorted(x.onde.replace(str(tmp_path), "") for x in rastros if not x.de_proposito)
    assert defeitos == [
        "/lar/.config/heroic/config.json",
        "/lar/.local/share/flatpak/overrides/net.lutris.Lutris",
        f"/lar/.local/state/{m.SLUG}",
    ], defeitos
    de_proposito = {x.o_que for x in rastros if x.de_proposito}
    assert "o backup que o uninstall faz" in de_proposito
    assert any("quirk usbcore" in o for o in de_proposito)

    # 4. o install de novo, e o teste — que grava coisas novas.
    instalar_de_mentira(r)
    (r.config / m.SLUG / "controllers.json").write_text('{"order": []}', encoding="utf-8")
    _plantar_pareamento(r, ADAPTADOR_A, _controle(1), "0x002508", chave="99" * 16)

    # 5. devolver: por cima do install novo, com o daemon parado.
    relato2 = m.devolver(r, sistema)
    depois = _arvore(tmp_path)
    for chave_do_lugar in ("configuracao-inteira", "steam-opcoes-e-entrada",
                           "steam-proton-pinado", "heroic-ambiente", "flatpak-ambiente"):
        for item in (i for i in manifesto.itens if i.chave == chave_do_lugar):
            assert m.retrato(Path(item.origem)) == item.retrato, item.origem
    # O que é do install novo ficou (o registro do pino do install novo, o censo).
    assert (r.estado / m.SLUG / "proton-pin-lock.json").is_file()
    # O controle pareado de novo durante o teste manteve a chave nova.
    assert "99" * 16 in (r.bluez / ADAPTADOR_A / _controle(1) / "info").read_text(
        encoding="utf-8")
    # Os que não foram pareados de novo voltaram, byte a byte.
    for i in (2,):
        rel = f"var/lib/bluetooth/{ADAPTADOR_A}/{_controle(i)}/info"
        assert depois[rel] == antes[rel]
    # A escolha «manter» da camada é dita pelo nome.
    assert any("EOSOverlay.json" in linha for linha in relato2.linhas)
    assert relato2.sobrescritos, "o devolver tem de dizer o que sobrescreveu"


def test_o_limpa_ve_o_device_ks_num_prefixo(raizes: m.Raizes) -> None:
    compat = raizes.lar / ".steam/steam/steamapps/compatdata/100/pfx"
    compat.mkdir(parents=True)
    (raizes.lar / ".steam/steam/steam.sh").write_text("", encoding="utf-8")
    (compat / "system.reg").write_text(
        "WINE REGISTRY Version 2\n[System\\\\CurrentControlSet\\\\Enum\\\\USB\\\\"
        f"VID_054C&PID_0CE6\\\\{m.MARCA_DO_DEVICE_KS}&1&2&0] 1\n", encoding="utf-8")
    rastros = m.conferir_a_casa(raizes)
    assert any("device de áudio KS" in r.o_que for r in rastros)


@pytest.fixture
def bluez_so_do_root(raizes: m.Raizes) -> Iterator[Path]:
    """O armazenamento do BlueZ como numa máquina de verdade: ``700`` do root.

    Como pessoa, ``iterdir`` levanta — é o que o «limpa?» encontra na máquina
    dela, e o que a régua não via com um BlueZ de mentira legível.
    """
    _plantar_pareamento(raizes, ADAPTADOR_A, _controle(1), "0x002508")
    (raizes.bluez / ADAPTADOR_A / "settings").write_text(
        "[General]\nAlias=Nintendo Sala\n", encoding="utf-8")
    os.chmod(raizes.bluez, 0o000)
    try:
        yield raizes.bluez
    finally:
        os.chmod(raizes.bluez, 0o755)


@pytest.mark.skipif(os.geteuid() == 0, reason="como root o 700 não fecha nada")
def test_o_limpa_sem_privilegio_diz_nao_sei_e_nao_sobrou(
    raizes: m.Raizes, bluez_so_do_root: Path
) -> None:
    """Sem privilégio, o BlueZ é «não sei» — nem «sobrou», nem «limpa».

    Antes: ``os pareamentos só se olham com root`` saía como SOBROU, e o
    ``limpa`` de toda máquina de verdade terminava em 1 — a pergunta «está
    limpa?» nunca tinha «sim» como resposta.
    """
    rastros = m.conferir_a_casa(raizes, m.Sistema())
    do_bluez = [r for r in rastros if r.onde.startswith(str(bluez_so_do_root))]
    assert len(do_bluez) == 1 and do_bluez[0].nao_sei, do_bluez
    assert not do_bluez[0].de_proposito
    assert "SUDO_ASKPASS" in do_bluez[0].o_que

    script = _carregar_o_script_da_casa()
    assert script.principal(["limpa"]) == 3


def test_o_limpa_com_privilegio_ve_o_controle_e_o_nome_do_adaptador(
    raizes: m.Raizes, bluez_so_do_root: Path
) -> None:
    """Com privilégio, a pergunta vai à parte do root (o verbo ``olhar``)."""

    class ComPrivilegio(SistemaDeMentira):
        def olhar_o_bluez(self, raizes: m.Raizes) -> dict[str, Any] | None:
            os.chmod(raizes.bluez, 0o755)
            try:
                return super().olhar_o_bluez(raizes)
            finally:
                os.chmod(raizes.bluez, 0o000)

    rastros = m.conferir_a_casa(raizes, ComPrivilegio())
    sobras = {r.onde: r for r in rastros if not r.de_proposito and not r.nao_sei}
    assert str(bluez_so_do_root / ADAPTADOR_A / _controle(1)) in sobras
    nome = sobras[str(bluez_so_do_root / ADAPTADOR_A / "settings")]
    assert "Nintendo Sala" in nome.o_que
    assert not any(r.nao_sei for r in rastros)


def test_o_verbo_olhar_do_root_so_le(raizes: m.Raizes, tmp_path: Path) -> None:
    plantar_a_mesa(raizes, 2, "bt", True)
    antes = m.retrato(tmp_path)
    dado = m.executar_parte_do_root(raizes, "olhar", None, seco=False)
    assert m.retrato(tmp_path) == antes
    assert sorted(tuple(p) for p in dado["pareamentos"]) == [
        (ADAPTADOR_A, _controle(1)), (ADAPTADOR_A, _controle(2))]
    with pytest.raises(m.RecusaError):
        m.executar_parte_do_root(raizes, "esquecer", None, seco=True)


def test_o_limpa_diz_as_copias_do_vdf_como_de_proposito(raizes: m.Raizes) -> None:
    instalar_de_mentira(raizes)
    vdf = raizes.lar / ".steam/steam/userdata/12345/config/localconfig.vdf"
    copia = vdf.with_name(vdf.name + ".bak.hefesto-launch-1790000000")
    copia.write_text("x", encoding="utf-8")
    rastros = {r.onde: r for r in m.conferir_a_casa(raizes)}
    assert rastros[str(copia.resolve())].de_proposito


def _carregar_o_script_da_casa() -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location("_script_da_casa", SCRIPT_DA_CASA)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ─── 6b. o que é do root também é do inventário ──────────────────────────


def test_todo_caminho_do_root_que_o_produto_grava_esta_no_inventario() -> None:
    """A régua do lado do root lê os SCRIPTS, não o inventário.

    Plantar a mesa a partir do :data:`INVENTARIO` mede a própria saída: um
    lugar do root que saísse dele (as cópias de pareamento, o diário do root)
    deixaria de ser plantado E de ser movido, e a volta idêntica passaria.
    Aqui a lista vem de quem grava — todo caminho sob ``/var/lib/<slug>`` que
    os scripts, o install, o uninstall e o ``src/`` escrevem — e cada um tem de
    caber num lugar do root do inventário.
    """
    padrao = re.compile(re.escape(str(m.VARLIB_DO_PRODUTO)) + r"/([A-Za-z0-9_.*-]+)")
    fontes = [RAIZ / "install.sh", RAIZ / "uninstall.sh",
              *sorted((RAIZ / "scripts").glob("*.sh")), *sorted(SRC.rglob("*.py"))]
    achados: dict[str, str] = {}
    for fonte in fontes:
        if fonte.name == "memoria_dos_controles.py":
            continue
        for achado in padrao.finditer(fonte.read_text(encoding="utf-8", errors="replace")):
            achados.setdefault(achado.group(1).rstrip("."), str(fonte.relative_to(RAIZ)))
    assert achados, "a varredura não achou nada — o padrão está cego"
    do_root = [lg.caminho for lg in m.INVENTARIO if lg.raiz == "varlib"]
    fora = {nome: onde for nome, onde in achados.items()
            if not any(fnmatch.fnmatch(nome, p) for p in do_root)}
    assert not fora, f"caminhos do root fora do inventário: {fora}"


def test_os_overrides_moram_onde_os_donos_escrevem(raizes: m.Raizes, tmp_path: Path) -> None:
    """O ``cura_por_estrada`` escreve (e o ``sandbox_dos_lancadores`` lê) no LAR,
    e não no ``XDG_DATA_HOME``: com os dois separados, o guardar tem de achar o
    override onde o dono o escreveu."""
    from hefesto_dualsense4unix.integrations import cura_por_estrada, sandbox_dos_lancadores

    r = m.Raizes(**{**raizes.__dict__, "dados": tmp_path / "dados-em-outro-lugar"})
    usuario, _sistema = sandbox_dos_lancadores._raizes(r.lar, None)
    override = usuario / "overrides" / "net.lutris.Lutris"
    override.parent.mkdir(parents=True)
    override.write_text("[Context]\ndevices=all;\n", encoding="utf-8")
    cura_por_estrada._escrever_no_override(override, dict(AMBIENTE_DA_PONTE))
    assert m._achar_overrides(r) == [override]


# ─── 7. o script da casa roda sem o pacote ────────────────────────────────


def test_o_script_da_casa_roda_com_o_python_do_sistema(raizes: m.Raizes) -> None:
    """Depois do uninstall a ``.venv`` não existe: o script carrega o dono
    pelo caminho. ``-I -S`` tira o ``PYTHONPATH`` E o ``site-packages`` — o
    pacote não é importável, como no ``python3`` do sistema depois do uninstall."""
    plantar_a_mesa(raizes, 2, "bt", True)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    r = subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT_DA_CASA), "guardar", "--seco"],
        env=env, capture_output=True, text=True, check=False, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    assert "controllers.json" in r.stdout or "hefesto-dualsense4unix" in r.stdout
    assert "pareamento do controle" in r.stdout
    limpa = subprocess.run(
        [sys.executable, "-I", "-S", str(SCRIPT_DA_CASA), "limpa"],
        env=env, capture_output=True, text=True, check=False, timeout=60,
    )
    assert limpa.returncode == 1, "com a casa inteira de pé, a máquina NÃO está limpa"
    assert "SOBROU" in limpa.stdout


def test_a_cli_esquece_e_devolve(raizes: m.Raizes, tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from hefesto_dualsense4unix.cli.app import app

    plantar_a_mesa(raizes, 2, "misto", True)
    antes = _arvore(tmp_path)
    runner = CliRunner()
    r1 = runner.invoke(app, ["esquecer-controles"])
    assert r1.exit_code == 0, r1.output
    assert not (raizes.config / m.SLUG / "controllers.json").exists()
    r2 = runner.invoke(app, ["esquecer-controles", "--restaurar"])
    assert r2.exit_code == 0, r2.output
    assert _arvore(tmp_path) == antes
    r3 = runner.invoke(app, ["esquecer-controles", "qualquer"])
    assert r3.exit_code == 2
