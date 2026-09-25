#!/usr/bin/env python3
"""A RÉGUA DA O-PERFIL-ATIVO-ACHA-O-ARQUIVO-COMO-O-DAEMON-01: a tela acha o arquivo como o daemon.

O DEFEITO, achado na conferência da A-ABA-GATILHOS-DIZ-O-QUE-VAI-AO-CONTROLE-01
e medido num lar de mentira em 25/09/2026: `perfil.ativo` procurava o arquivo
do perfil só pelo nome e pelo slug. O `load_profile` do daemon tem mais duas
pernas, a varredura por `name` e a subpasta dos Estilos de Jogo, e o perfil
achado só por elas virava `{}` na tela. Com um perfil sem `triggers`, a aba 03
dizia «Desligado» e o daemon mandava o Rígido; a 04 perdia o brilho, a 05 e a
08 o teto do P2, a 06 os atalhos, e a dica do Salvar a promessa. O perfil cujo
arquivo sumiu com ele valendo caía no mesmo `{}`.

AS TRÊS FORMAS: o arquivo de outro nome, o Estilo de Jogo na subpasta, e o
arquivo apagado depois de o daemon aplicar o perfil e a tela o ler.

O ORÁCULO É O DAEMON, e não um modo digitado:

* o GÊMEO — o mesmo conteúdo gravado no nome canônico. O daemon carrega o
  MESMO `Profile` nas duas casas (a régua confere), e toda aba tem de dizer, na
  forma, exatamente o que diz no gêmeo;
* a 03 contra o `ProfileManager.apply` real, lado a lado e controle a
  controle, como a régua da A-ABA-GATILHOS mede;
* a 04 e a 06 contra o `Profile` que o `load_profile` devolve (o brilho e os
  atalhos).

A MORDIDA, arrancada antes deste arquivo entrar: com `perfil.ativo` de volta às
duas pernas, as formas «outro nome» e «estilo» reprovam com «Desligado» na 03;
com a lembrança do último arquivo lido arrancada, o «apagado» reprova igual; com
a assinatura da pasta cega, a memória reprova; com o «Exportar» de volta à
cópia das duas pernas, ele reprova com «não achei o arquivo».
"""
from __future__ import annotations

import json
import os
import pathlib
import re
import sys
from collections.abc import Callable, Iterator
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: As abas que leem `perfil.ativo`, e a dica do Salvar do rodapé das dez.
PAGINAS = ("03-gatilhos.html", "04-iluminacao.html", "05-vibracao.html",
           "06-navegacao.html", "08-conexoes.html")
DICA_DO_SALVAR = "rodape.salvar"

#: A mesa da matriz: P1 e P2 no USB, P3 e P4 no BT. MACs da faixa sintética da
#: casa — há dois portões de anonimato nesta árvore e eles não perdoam.
MACS = {1: "aa:bb:cc:00:00:01", 2: "aa:bb:cc:00:00:02",
        3: "aa:bb:cc:00:00:03", 4: "aa:bb:cc:00:00:04"}
TRANSPORTE = {1: "usb", 2: "usb", 3: "bt", 4: "bt"}
LADOS = {"e": "left", "d": "right"}


def _cru(nome: str) -> dict[str, Any]:
    """O perfil da régua, na forma do disco.

    SEM `triggers` de propósito: o daemon manda o nascimento do esquema, e a
    tela que não acha o arquivo diz «Desligado». O brilho, o teto do P2 e os
    atalhos são o que as abas 04, 05/08 e 06 mostram do perfil.
    """
    return {
        "name": nome, "version": 1, "priority": 50,
        "match": {"type": "manual"},
        "leds": {"lightbar": [10, 200, 30], "player_leds": [True] * 5,
                 "lightbar_brightness": 0.4},
        "rumble": {"passthrough": True, "policy": "max"},
        "key_bindings": {"cross": ["KEY_ENTER"], "circle": ["KEY_ESC"]},
        "controllers": {"aabbcc000002": {"rumble": {"policy": "economia"}}},
    }


def _controle(n: int) -> dict[str, Any]:
    """Um controle com a forma do `state_full` (o `uniq` na grafia do daemon)."""
    return {
        "uniq": MACS[n].replace(":", ""), "player": n, "player_slot": n,
        "index": n - 1, "connected": True, "is_primary": n == 1,
        "battery_pct": 80, "transport": TRANSPORTE[n], "vpad_backend": "uhid",
        "lightbar_rgb": [0, 0, 255], "lightbar_on": True,
        "inputs": {"lx": 128, "ly": 128, "rx": 128, "ry": 128,
                   "l2_raw": 0, "r2_raw": 0, "buttons": []},
    }


def _ctx(nome: str | None) -> Any:
    """O `Contexto` do tique, montado como o piloto o monta (`_contexto`)."""
    import mesa_viva
    from pacotes import Contexto

    controles = [_controle(n) for n in (1, 2, 3, 4)]
    state: dict[str, Any] = {"controllers": controles, "output_target_index": None,
                             "active_profile": nome, "rumble_policy": "balanceado"}
    return Contexto(state=state, mesa=mesa_viva.mesa_do_estado(state, {}),
                    conectados=controles, estados={})


@pytest.fixture(autouse=True)
def _memoria_limpa() -> Iterator[None]:
    """A memória do `perfil` e o rascunho da 03 são de MÓDULO: nenhum teste herda."""
    from pacotes import a03_gatilhos, perfil

    perfil._ONDE_ACHOU.clear()
    perfil._LIDO.clear()
    a03_gatilhos.esquecer_o_rascunho()
    yield
    perfil._ONDE_ACHOU.clear()
    perfil._LIDO.clear()
    a03_gatilhos.esquecer_o_rascunho()


@pytest.fixture
def pasta() -> pathlib.Path:
    """A pasta de perfis do lar de mentira que o `conftest` já isola.

    A MESMA para os dois leitores: `pacotes.perfil.pasta()` e o `loader`
    perguntam a `xdg_paths.profiles_dir()` na chamada.
    """
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    return profiles_dir(ensure=True)


def _gravar(alvo: pathlib.Path, cru: dict[str, Any]) -> pathlib.Path:
    alvo.parent.mkdir(parents=True, exist_ok=True)
    alvo.write_text(json.dumps(cru), encoding="utf-8")
    return alvo


def _canonico(pasta: pathlib.Path, nome: str) -> pathlib.Path:
    from hefesto_dualsense4unix.profiles.slug import slugify

    return pasta / f"{slugify(nome)}.json"


def _estilo(pasta: pathlib.Path, nome: str) -> pathlib.Path:
    from hefesto_dualsense4unix.profiles.loader import ESTILOS_DE_JOGO_DIR_NAME
    from hefesto_dualsense4unix.profiles.slug import slugify

    return pasta / ESTILOS_DE_JOGO_DIR_NAME / f"{slugify(nome)}.json"


#: AS TRÊS FORMAS: `nome do perfil -> onde o arquivo mora`. O «apagado» mora
#: no nome canônico até a tela o ler e o daemon o aplicar.
FORMAS: dict[str, tuple[str, Callable[[pathlib.Path, str], pathlib.Path]]] = {
    "outro-nome": ("Perfil Da Varredura",
                   lambda p, _n: p / "arquivo-de-outro-nome.json"),
    "estilo": ("Corrida Da Régua", _estilo),
    "apagado": ("Perfil Apagado", _canonico),
}


def _pintura(nome: str) -> dict[str, Any]:
    """O que as cinco abas e a dica do Salvar dizem, com `nome` valendo."""
    from pacotes import _dica_do_salvar, pacote_da_pagina

    fora: dict[str, Any] = {pag: pacote_da_pagina(pag, _ctx(nome)) for pag in PAGINAS}
    fora[DICA_DO_SALVAR] = _dica_do_salvar(nome)
    return fora


def _achatar(x: Any, pre: str = "") -> dict[str, Any]:
    if isinstance(x, dict):
        fora: dict[str, Any] = {}
        for k, v in x.items():
            fora.update(_achatar(v, f"{pre}/{k}"))
        return fora
    if isinstance(x, list):
        fora = {}
        for i, v in enumerate(x):
            fora.update(_achatar(v, f"{pre}[{i}]"))
        return fora
    return {pre: x}


def _diferencas(gemeo: Any, forma: Any) -> list[str]:
    a, b = _achatar(gemeo), _achatar(forma)
    return [f"{k}: gêmeo {str(a.get(k, '<ausente>'))[:90]!r} · forma "
            f"{str(b.get(k, '<ausente>'))[:90]!r}"
            for k in sorted(set(a) | set(b)) if a.get(k, "<ausente>") != b.get(k, "<ausente>")]


class _Camadas:
    """O backend de mentira: grava as duas camadas que a ativação publica.

    `efetivo` é o `_merge_desired` do backend real reduzido ao gatilho — o mesmo
    de `test_a_aba_gatilhos_diz_o_que_vai_ao_controle.py`.
    """

    def __init__(self) -> None:
        from hefesto_dualsense4unix.core.controller import OutputSpec
        from hefesto_dualsense4unix.testing.fake_controller import FakeController

        class Gravador(FakeController):
            def __init__(self) -> None:
                super().__init__()
                self.padrao = OutputSpec()
                self.do_perfil: dict[str, Any] = {}

            def apply_output_defaults(self, spec: Any) -> Any:
                self.padrao = spec
                return "escreveu"

            def reset_profile_overrides(self, overrides: Any,
                                        procedencias: Any = None) -> None:
                self.do_perfil = dict(overrides or {})

        self.controlador = Gravador()

    def efetivo(self, uniq: str, disco: str) -> Any:
        campo = f"trigger_{disco}"
        dele = self.controlador.do_perfil.get(uniq.replace(":", "").lower())
        if dele is not None and getattr(dele, campo) is not None:
            return getattr(dele, campo)
        return getattr(self.controlador.padrao, campo)


def _o_daemon_aplica(prof: Any) -> _Camadas:
    from hefesto_dualsense4unix.profiles.manager import ProfileManager

    camadas = _Camadas()
    ProfileManager(controller=camadas.controlador).apply(prof, origin="auto", relatorio={})
    return camadas


def _a_03_mente(pintura: dict[str, Any], ctx: Any, manda: _Camadas) -> list[str]:
    """Os lados em que a coluna da 03 diz outra coisa que o controle recebe."""
    from hefesto_dualsense4unix.core.trigger_effects import build_from_name

    r = pintura["03-gatilhos.html"]
    pref_de = {str(m["uniq"]): str(m["pref"]) for m in ctx.mesa}
    mentiras = []
    for c in ctx.conectados:
        uniq = str(c["uniq"])
        for sig, disco in LADOS.items():
            col = r["colunas"][uniq]
            caixa = r["blocos"][f'[data-controle="{pref_de[uniq]}"] .ajustes.{sig}']
            ajustes = [int(v) for v in re.findall(
                rf'data-campo="aj-val-{sig}-\d+">(-?\d+)<', caixa)]
            diz = build_from_name(str(col[f"modo-chave-{sig}"]), ajustes)
            vai = manda.efetivo(uniq, disco)
            if diz != vai:
                mentiras.append(
                    f"P{c['player']} ({c['transport'].upper()}) "
                    f"{'L2' if sig == 'e' else 'R2'}: a coluna diz "
                    f"«{col[f'modo-{sig}']}» {ajustes} e o controle recebe {vai}")
    return mentiras


def _medir(pasta: pathlib.Path, forma: str) -> tuple[str, Any, dict[str, Any], dict[str, Any]]:
    """`(nome, o Profile que o daemon aplica, pintura do gêmeo, pintura da forma)`."""
    from pacotes import a03_gatilhos, perfil

    from hefesto_dualsense4unix.profiles import loader

    nome, onde = FORMAS[forma]
    cru = _cru(nome)

    # O GÊMEO: o mesmo conteúdo no nome canônico, que a tela de ontem já achava.
    gemeo = _gravar(_canonico(pasta, nome), cru)
    pintura_do_gemeo = _pintura(nome)
    do_gemeo = loader.load_profile(nome)
    gemeo.unlink()
    # A MEMÓRIA DO GÊMEO NÃO PODE VAZAR para a forma: ela é a cura do «apagado»
    # e mascararia as outras duas.
    perfil._ONDE_ACHOU.clear()
    perfil._LIDO.clear()
    a03_gatilhos.esquecer_o_rascunho()

    alvo = _gravar(onde(pasta, nome), cru)
    prof = loader.load_profile(nome)
    assert prof == do_gemeo, (
        f"o daemon carrega outro perfil na forma {forma!r} — a régua mediria o "
        f"conteúdo, não o caminho")
    if forma == "apagado":
        # A janela está aberta: a tela lê o perfil num tique, o daemon já o
        # aplicou, e o arquivo some do disco.
        _pintura(nome)
        alvo.unlink()
        with pytest.raises(FileNotFoundError):
            loader.load_profile(nome)
    return nome, prof, pintura_do_gemeo, _pintura(nome)


@pytest.mark.parametrize("forma", list(FORMAS))
def test_cada_aba_diz_o_mesmo_que_no_nome_canonico(pasta: pathlib.Path, forma: str) -> None:
    """As cinco abas e a dica do Salvar dizem, na forma, o que dizem no gêmeo."""
    _nome, _prof, gemeo, agora = _medir(pasta, forma)
    for pag in (*PAGINAS, DICA_DO_SALVAR):
        linhas = _diferencas(gemeo[pag], agora[pag])
        assert not linhas, (
            f"[{forma}] a {pag} diz outra coisa que diria com o mesmo perfil no "
            f"nome canônico — ela não achou o arquivo que o daemon lê "
            f"({len(linhas)} campos):\n  " + "\n  ".join(linhas[:12]))


@pytest.mark.parametrize("forma", list(FORMAS))
def test_a_03_diz_o_gatilho_que_o_daemon_manda(pasta: pathlib.Path, forma: str) -> None:
    """Os oito lados da mesa, nos dois transportes, casam com o `ProfileManager.apply`."""
    nome, prof, _gemeo, agora = _medir(pasta, forma)
    mentiras = _a_03_mente(agora, _ctx(nome), _o_daemon_aplica(prof))
    assert not mentiras, (
        f"[{forma}] a aba 03 mente sobre o gatilho em {len(mentiras)} de 8 "
        f"lados:\n  " + "\n  ".join(mentiras))


@pytest.mark.parametrize("forma", list(FORMAS))
def test_a_04_e_a_06_dizem_o_brilho_e_os_atalhos_do_perfil_que_o_daemon_le(
        pasta: pathlib.Path, forma: str) -> None:
    """O brilho da 04 e os atalhos da 06 são os do `Profile` do `load_profile`."""
    _nome, prof, _gemeo, agora = _medir(pasta, forma)
    brilho = round(float(prof.leds.lightbar_brightness) * 100)
    for uniq, col in agora["04-iluminacao.html"]["colunas"].items():
        assert col.get("brilho-pct") == brilho, (
            f"[{forma}] a 04 diz brilho {col.get('brilho-pct')!r} no {uniq} e o "
            f"perfil que o daemon lê tem {brilho}")
    atalhos = {k: list(v) for k, v in (prof.key_bindings or {}).items()}
    na_tela = agora["06-navegacao.html"]["mesa"].get("gestos-lista")
    assert na_tela == atalhos, (
        f"[{forma}] a 06 diz os atalhos {na_tela!r} e o perfil que o daemon lê "
        f"tem {atalhos!r}")


def test_sem_lembranca_a_tela_nao_inventa_perfil(pasta: pathlib.Path) -> None:
    """A janela que abre depois de o arquivo sumir não pinta um perfil de mentira.

    O que o daemon aplicou não está em lugar nenhum que a tela alcance: nem no
    disco, nem no que ela leu. A resposta é `{}`, e nunca o nascimento do
    esquema nem o conteúdo de outro perfil.
    """
    from pacotes import perfil

    outro = _gravar(_canonico(pasta, "Outro Perfil"), _cru("Outro Perfil"))
    assert perfil.ativo("Outro Perfil")["name"] == "Outro Perfil"
    _gravar(_canonico(pasta, "Sumiu Antes"), _cru("Sumiu Antes")).unlink()
    assert perfil.ativo("Sumiu Antes") == {}
    assert perfil.ativo("Nunca Existiu") == {}
    assert outro.exists()


def test_a_lembranca_devolve_um_dicionario_novo_a_cada_vez(pasta: pathlib.Path) -> None:
    """Quem mexe no que recebeu não mexe no que o próximo tique vai ler."""
    from pacotes import perfil

    alvo = _gravar(_canonico(pasta, "Mexido"), _cru("Mexido"))
    perfil.ativo("Mexido")
    alvo.unlink()
    primeiro = perfil.ativo("Mexido")
    primeiro["leds"]["lightbar_brightness"] = 0.99
    assert perfil.ativo("Mexido")["leds"]["lightbar_brightness"] == 0.4


@pytest.mark.parametrize("forma", ["outro-nome", "estilo"])
def test_o_exportar_leva_o_arquivo_que_o_daemon_le(
        pasta: pathlib.Path, forma: str, tmp_path: pathlib.Path) -> None:
    """O «Exportar» do rodapé copia o arquivo que o daemon lê, byte a byte."""
    from pacotes import gesto_da_pagina

    nome, onde = FORMAS[forma]
    alvo = _gravar(onde(pasta, nome), _cru(nome))
    destino = tmp_path / "exportado.json"

    class Ponte:
        def salvar_arquivo(self, titulo: str, sugestao: str = "", **_: Any) -> str:
            return str(destino)

    exportar = gesto_da_pagina("03-gatilhos.html", "exportar")
    assert exportar is not None
    exportar(_ctx(nome), {}, Ponte())
    assert destino.read_bytes() == alvo.read_bytes()


def test_a_tela_pergunta_ao_mesmo_dono_que_o_daemon(pasta: pathlib.Path) -> None:
    """`perfil.arquivo` e `load_profile` acham o MESMO arquivo, na ordem do daemon.

    O canônico vence a varredura, e a varredura vence a subpasta dos Estilos:
    é a ordem de `loader.arquivo_do_perfil`, e a tela não tem outra.
    """
    from pacotes import perfil

    from hefesto_dualsense4unix.profiles import loader

    nome = "Ordem Das Pernas"
    estilo = _gravar(_estilo(pasta, nome), {**_cru(nome), "priority": 1})
    assert perfil.arquivo(nome) == estilo
    varrido = _gravar(pasta / "zz-outro-nome.json", {**_cru(nome), "priority": 2})
    assert perfil.arquivo(nome) == varrido
    assert loader.load_profile(nome).priority == 2
    canonico = _gravar(_canonico(pasta, nome), {**_cru(nome), "priority": 3})
    assert perfil.arquivo(nome) == canonico
    assert loader.load_profile(nome).priority == 3
    assert perfil.ativo(nome)["priority"] == 3


def test_a_memoria_cai_quando_a_pasta_muda(pasta: pathlib.Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """A resposta guardada cai assim que um arquivo nasce na pasta.

    O limiar vai a zero para que TODA resposta entre na memória (com uma pasta
    de dois arquivos a varredura não chega a 1 ms). O `utime` só garante que o
    carimbo da pasta ande num sistema de arquivos de relógio grosso; o
    nascimento do arquivo já o muda num de relógio fino.
    """
    from pacotes import perfil

    monkeypatch.setattr(perfil, "CUSTO_QUE_SE_GUARDA_S", 0.0)
    nome, onde = FORMAS["outro-nome"]
    _gravar(onde(pasta, nome), _cru(nome))
    assert perfil.ativo(nome)["leds"]["lightbar_brightness"] == 0.4
    _gravar(_canonico(pasta, nome), {**_cru(nome),
                                     "leds": {**_cru(nome)["leds"], "lightbar_brightness": 0.9}})
    carimbo = pasta.stat().st_mtime_ns
    os.utime(pasta, ns=(carimbo, carimbo + 2_000_000_000))
    assert perfil.ativo(nome)["leds"]["lightbar_brightness"] == 0.9, (
        "o arquivo canônico nasceu e a tela seguiu no de outro nome: a memória "
        "não olhou a pasta")


def test_a_varredura_nao_roda_a_cada_tique(pasta: pathlib.Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    """Com um Estilo de Jogo ativo, cinco tiques da 03 perguntam ao loader uma vez.

    O espião DELEGA ao loader de verdade: ele conta, não responde.
    """
    from pacotes import perfil

    from hefesto_dualsense4unix.profiles import loader

    monkeypatch.setattr(perfil, "CUSTO_QUE_SE_GUARDA_S", 0.0)
    for i in range(8):
        _gravar(pasta / f"p{i}.json", _cru(f"P{i}"))
    nome, onde = FORMAS["estilo"]
    _gravar(onde(pasta, nome), _cru(nome))
    # O DAEMON JÁ LEU A PASTA na máquina de verdade, e a leitura dele deixa um
    # `.lock` ao lado de cada perfil (o `FileLock` não os apaga). Sem isto, a
    # primeira varredura da tela é quem os cria, a pasta muda debaixo da
    # memória e o segundo tique pergunta de novo — medido, e não acontece
    # onde o daemon está de pé.
    loader.load_all_profiles()
    real = loader.arquivo_do_perfil
    perguntas: list[str] = []

    def espiao(identifier: str, directory: pathlib.Path | None = None) -> Any:
        perguntas.append(identifier)
        return real(identifier, directory)

    monkeypatch.setattr(loader, "arquivo_do_perfil", espiao)
    from pacotes import pacote_da_pagina

    for _ in range(5):
        pacote_da_pagina("03-gatilhos.html", _ctx(nome))
    assert perguntas == [nome], (
        f"cinco tiques da 03 perguntaram ao loader {len(perguntas)} vezes — a "
        f"varredura inteira roda a cada tique no laço do GTK")
