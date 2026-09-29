"""O-MUDO-E-DO-CONTROLE-01 — o mudo do microfone é do controle, e vale em todo jogo.

**A DECISÃO É DELA** (resposta 9 da noite de 27/09,
``docs/process/estudos/2026-09-27-as-respostas-dela-da-noite.md``). O relatório
04 da auditoria (A2) mediu o defeito que ela cura: o mudo tinha TRÊS cópias — o
perfil (``controllers[k].mic.muted``), a sessão do daemon (a memória do último
ato, que vencia um perfil «mais velho» na reconexão) e o aparelho —, e DOIS
escritores no mesmo clique (o daemon e o ``_lembrar_do_som`` da aba 02, que
relia o perfil e gravava de novo).

O QUE SE AFIRMA, E A MORDIDA DE CADA UM
------------------------------------------------------------------------------
1. **Um dono:** o mudo mora no ``maquina.json``
   (``controles[k].microfone_mudo``), pela API do ``utils/maquina.py``.
2. **Um escritor:** o 🎙 da tela não lê nem grava o perfil — quem grava é o
   ato, no daemon. MORDIDA: devolver ao gesto ``mudo`` a gravação do mudo pelo
   ``_lembrar_do_som``. E o rascunho do «Salvar» não escreve o mudo. MORDIDA:
   devolver o ramo do ``muted`` ao ``DraftConfig.with_controller_mic``.
3. **A troca de perfil não mexe no mudo**, a automática e a explícita.
   MORDIDA: a ativação explícita voltar a levar o ``muted`` do perfil
   (``apply_mic``).
4. **O restart devolve o mudo do dono.** MORDIDA: ler o mudo de uma memória que
   morre com o daemon (``_mudo_do_controle`` devolvendo ``None``).
5. **A migração, uma vez:** o ``mic.muted`` do perfil ativo vira o mudo de cada
   controle, e sai de todos os perfis com a versão de antes no histórico;
   nenhum outro campo muda.
6. **O 🎙 sobre uma posse velha escreve** (o que a conferência da O-BOTAO
   deixou para cá). MORDIDA: tirar a pergunta à posse de ``_metade_do_firmware``.

Tudo nos quatro jogadores e nos dois transportes. A cena é a do produto: os
laços do botão, o ato, o ``ProfileManager``, o gancho de conexão e o applier
do daemon são os REAIS, e os dublês do aparelho e do PipeWire são os da régua
irmã (``test_o_botao_do_mic_grava_no_perfil.py``), que têm a posse do backend.

Os endereços são da faixa FORJADA de fixture (``aa:bb:cc``), nunca da bancada.
"""

from __future__ import annotations

import json
import pathlib
import sys
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.app.draft_config import DraftConfig
from hefesto_dualsense4unix.daemon.subsystems import hotkey
from hefesto_dualsense4unix.profiles import loader
from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
from hefesto_dualsense4unix.utils import maquina
from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir
from tests.unit.test_o_botao_do_mic_grava_no_perfil import (
    FREESTYLE,
    JOGO,
    OS_QUATRO,
    P1,
    P2,
    P3,
    P4,
    _apertar,
    _ativar,
    _derrubar,
    _reconectar,
    casa,  # noqa: F401 — a fixture da cena, a mesma da régua irmã
)

RAIZ = pathlib.Path(__file__).resolve().parents[2]

#: Os dois transportes, na ordem de P1 a P4: cabo e rádio intercalados, para
#: que todo controle da cena seja medido nos dois quando o parâmetro gira.
TRANSPORTES = {
    "cabo-primeiro": ("usb", "bt", "usb", "bt"),
    "radio-primeiro": ("bt", "usb", "bt", "usb"),
}


# ===========================================================================
# 3. A TROCA DE PERFIL NÃO MEXE NO MUDO
# ===========================================================================


class TestATrocaDePerfilNaoMexeNoMudo:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("origem", ["manual", "autoswitch"])
    @pytest.mark.parametrize("calado", OS_QUATRO)
    async def test_o_controle_calado_segue_calado_depois_da_troca(
        self, casa: Any, origem: str, calado: str  # noqa: F811
    ) -> None:
        """Ela cala UM pelo botão; o perfil do jogo diz «no ar» para todos.

        O perfil do jogo carrega um `muted: false` de antes da migração, no
        global e na peça. A troca — automática ou escolhida na mão — não
        escreve o mudo, e a reconexão seguinte lê o dono.

        MORDIDA: `apply_mic` voltar a deixar o `muted` atravessar a troca
        explícita (`origin == "manual"`).
        """
        casa.perfil(FREESTYLE)
        casa.perfil(JOGO, mic={"muted": False},
                    por_peca={u: {"mic": {"muted": False}} for u in OS_QUATRO})
        daemon = casa.daemon(OS_QUATRO, transportes=TRANSPORTES["cabo-primeiro"])
        for u in OS_QUATRO:
            assert await hotkey.nascer_no_ar(daemon, u) is True
        await _apertar(daemon, calado)
        assert daemon.controller.mudo_no_firmware(calado) is True, "a cena não calou"
        daemon.controller.escritas_do_mudo.clear()

        _ativar(daemon, JOGO, origin=origem)

        assert daemon.controller.escritas_do_mudo == [], (
            f"a troca {origem} escreveu o mudo no aparelho: "
            f"{daemon.controller.escritas_do_mudo}"
        )
        assert daemon.controller.mudo_no_firmware(calado) is True, (
            f"a troca {origem} abriu o microfone que ela calou"
        )
        for u in OS_QUATRO:
            no_ar = await _reconectar(daemon, u)
            assert no_ar is (u != calado), (
                f"depois da troca {origem}, a reconexão do {u} leu o perfil "
                "do jogo e não o dono"
            )

    @pytest.mark.asyncio
    @pytest.mark.parametrize("origem", ["manual", "autoswitch"])
    async def test_o_controle_no_ar_segue_no_ar_diante_do_perfil_que_cala(
        self, casa: Any, origem: str  # noqa: F811
    ) -> None:
        """O contrário: ela liga pelo botão; o perfil do jogo diz calado."""
        casa.perfil(FREESTYLE)
        casa.perfil(JOGO, mic={"muted": True},
                    por_peca={P2: {"mic": {"muted": True}}})
        casa.calar_no_dono(P2)
        daemon = casa.daemon((P2,), transportes=("bt",))
        assert await _reconectar(daemon, P2) is False
        await _apertar(daemon, P2)
        assert daemon.controller.mudo_no_firmware(P2) is False, "a cena não ligou"
        daemon.controller.escritas_do_mudo.clear()

        _ativar(daemon, JOGO, origin=origem)
        assert await _reconectar(daemon, P2) is True, (
            f"a troca {origem} para o perfil que cala desfez o ato dela"
        )
        assert True not in daemon.controller.mudos_escritos(P2)


# ===========================================================================
# 4. O RESTART DEVOLVE O MUDO DO DONO — a prova dela, em mentira
# ===========================================================================


class TestORestartDevolveODono:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("arranjo", sorted(TRANSPORTES))
    async def test_calar_o_p3_abrir_um_jogo_fechar_e_reiniciar(
        self, casa: Any, arranjo: str  # noqa: F811
    ) -> None:
        """A prova no aparelho da sprint, com os quatro na mesa.

        Calar o P3 pelo botão, abrir um jogo com outro perfil, fechar,
        reiniciar o daemon: o P3 segue calado, e os outros três seguem abertos.

        MORDIDA: `_mudo_do_controle` lendo uma memória que morre com o daemon
        (devolvendo `None` depois do restart).
        """
        transportes = TRANSPORTES[arranjo]
        casa.perfil(FREESTYLE)
        casa.perfil(JOGO, por_peca={P3: {"mic": {"muted": False}}})
        daemon = casa.daemon(OS_QUATRO, transportes=transportes)
        for u in OS_QUATRO:
            assert await hotkey.nascer_no_ar(daemon, u) is True
        await _apertar(daemon, P3)
        _ativar(daemon, JOGO, origin="autoswitch")    # o jogo abre
        _ativar(daemon, FREESTYLE, origin="autoswitch")  # o jogo fecha
        await _derrubar(daemon)

        novo = casa.daemon(OS_QUATRO, ativo=JOGO, transportes=transportes)
        for u in OS_QUATRO:
            no_ar = await _reconectar(novo, u)
            assert no_ar is (u != P3), f"o restart mudou o microfone do {u}"
        assert novo.controller.mudos_escritos(P3) == [True], (
            "o restart não devolveu ao firmware do P3 o silêncio que ela pediu"
        )
        for u in (P1, P2, P4):
            assert novo.controller.mudos_escritos(u) == [], (
                f"o restart escreveu o mudo no {u}, que ela não calou"
            )


# ===========================================================================
# 2. UM ESCRITOR: o 🎙 da tela e o rascunho do «Salvar»
# ===========================================================================


def _pacotes() -> Any:
    sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))
    import pacotes
    import pacotes.a02_controles  # importar é registrar o gesto

    return pacotes


class _PonteQueGravaComoODaemon:
    """O daemon de papel que CONFIRMA o ato e grava como o daemon grava.

    O `mic.canal.set` do daemon é `hotkey.ligar_o_microfone`, que grava o mudo
    no dono (`utils.maquina.gravar_o_mudo_do_microfone`). Aqui a ponte faz a
    MESMA gravação, pelo mesmo escritor — sem ela, uma régua que conta
    gravações contaria só as da tela.
    """

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def mic_canal_set_detalhado(self, ligado: bool, uniq: str | None = None) -> dict[str, Any]:
        self.chamadas.append("mic_canal_set_detalhado")
        assert maquina.gravar_o_mudo_do_microfone(str(uniq), not ligado)
        return {"status": "ok", "uniq": uniq, "ligado": ligado, "canal_feito": True,
                "canal_motivo": "", "firmware_pedido": True, "firmware_motivo": "",
                "ativo": None, "motivo": ""}


class TestUmEscritor:
    @pytest.mark.parametrize("uniq", ["aa:bb:cc:00:00:11", "aa:bb:cc:00:00:44"])
    @pytest.mark.parametrize("transporte", ["usb", "bt"])
    def test_um_clique_no_microfone_grava_uma_vez_no_dono(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uniq: str, transporte: str
    ) -> None:
        """Um clique no 🎙 = UMA gravação, no dono; o perfil nem é lido.

        MORDIDA: devolver ao gesto `mudo` a gravação do mudo pelo
        `_lembrar_do_som` — ele lê o perfil ativo para gravar o mesmo clique.
        """
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        profiles_dir(ensure=True)
        loader.save_profile(Profile(name="Bancada", match=MatchManual()), origem="regua")
        antes = (profiles_dir() / "bancada.json").read_bytes()
        leituras: list[str] = []
        gravacoes: list[str] = []
        real_load, real_gravar = loader.load_profile, maquina.gravar_maquina
        monkeypatch.setattr(loader, "load_profile",
                            lambda n: leituras.append(n) or real_load(n))
        monkeypatch.setattr(maquina, "gravar_maquina",
                            lambda d: gravacoes.append("maquina") or real_gravar(d))
        pacotes = _pacotes()
        dele = {"uniq": uniq, "transport": transporte, "connected": True, "inputs": {},
                "audio": {"mic_mudo": False}, "speaker": {"volume": 100, "muted": False}}
        ctx = pacotes.Contexto(state={"active_profile": "Bancada"}, mesa=[],
                               conectados=[dele], estados={})
        ponte = _PonteQueGravaComoODaemon()

        fn = pacotes.gesto_da_pagina("02-controles.html", "mudo")
        fn(ctx, {"uniq": uniq, "mudo": "microfone"}, ponte)

        assert ponte.chamadas == ["mic_canal_set_detalhado"]
        assert gravacoes == ["maquina"], f"o clique gravou {len(gravacoes)} vezes no dono"
        assert leituras == [], (
            "o 🎙 leu o perfil ativo para gravar o mudo — o segundo escritor "
            "do mesmo clique voltou"
        )
        assert (profiles_dir() / "bancada.json").read_bytes() == antes
        assert maquina.mudo_do_microfone(uniq) is True

    def test_o_rascunho_nao_escreve_o_mudo(self) -> None:
        """O «Salvar» da tela não é escritor do mudo: nem cria, nem apaga.

        MORDIDA: devolver o ramo do `muted` ao `with_controller_mic`.
        """
        chave = "aabbcc000033"
        draft = DraftConfig.from_profile(Profile(name="x", match=MatchManual()))
        pedido = draft.effective_mic_for(chave).model_copy(update={"muted": True})

        depois = draft.with_controller_mic(chave, pedido)

        assert depois.controller_override(chave) is None, (
            "o rascunho escreveu o mudo do microfone num override do perfil"
        )
        assert "muted" not in (depois.with_mic(volume=40, muted=True).to_ipc_dict()["mic"] or {})

    def test_o_mudo_de_antes_da_migracao_atravessa_o_rascunho(self) -> None:
        """Um `muted` que a peça ainda carregue no disco não some num «Salvar».

        O rascunho não é dono do mudo: ele não o escreve nem o apaga. Apagar
        antes de a migração o levar ao dono perderia o silêncio dela.
        """
        chave = "aabbcc000033"
        perfil = Profile(name="x", match=MatchManual(),
                         controllers={chave: {"mic": {"muted": True}}})
        draft = DraftConfig.from_profile(perfil)
        pedido = draft.effective_mic_for(chave).model_copy(update={"volume": 40})

        salvo = draft.with_controller_mic(chave, pedido).to_profile("x", priority=0)

        mic = salvo.controllers[chave].mic
        assert mic is not None and mic.muted is True and mic.volume == 40


# ===========================================================================
# 1. UM DONO: o `maquina.json`, pela API do `utils/maquina.py`
# ===========================================================================


class TestODono:
    @pytest.mark.parametrize("uniq", OS_QUATRO)
    def test_nada_mudou_nada_grava(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uniq: str
    ) -> None:
        """Apertar duas vezes para o mesmo lado não reescreve o arquivo.

        MORDIDA: tirar a pergunta ao disco do começo de
        `gravar_o_mudo_do_microfone` — a segunda chamada grava de novo.
        """
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        gravacoes: list[dict[str, Any]] = []
        real = maquina.gravar_maquina
        monkeypatch.setattr(maquina, "gravar_maquina",
                            lambda d: gravacoes.append(d) or real(d))

        assert maquina.gravar_o_mudo_do_microfone(uniq, True)
        assert maquina.gravar_o_mudo_do_microfone(uniq, True)

        assert len(gravacoes) == 1, f"o mesmo mudo gravou {len(gravacoes)} vezes"
        assert maquina.mudo_do_microfone(uniq) is True
        assert maquina.gravar_o_mudo_do_microfone(uniq, False)
        assert len(gravacoes) == 2 and maquina.mudo_do_microfone(uniq) is False

    def test_o_endereco_sintetizado_nao_grava(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O vpad (`02fe…`) não é peça de plástico: não ganha mudo no dono."""
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

        assert maquina.gravar_o_mudo_do_microfone("02:fe:00:00:00:01", True) is False
        assert maquina.mudo_do_microfone("02:fe:00:00:00:01") is None
        assert not (maquina.carregar_maquina().controles or {})


# ===========================================================================
# 5. A MIGRAÇÃO, UMA VEZ
# ===========================================================================


def _grava_cru(pasta: Path, arquivo: str, dados: dict[str, Any]) -> None:
    (pasta / arquivo).write_text(json.dumps(dados, indent=2, ensure_ascii=False) + "\n",
                                 encoding="utf-8")


def _cru(pasta: Path, arquivo: str) -> dict[str, Any]:
    lido: dict[str, Any] = json.loads((pasta / arquivo).read_text(encoding="utf-8"))
    return lido


class TestAMigracao:
    @pytest.fixture
    def pasta(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        return profiles_dir(ensure=True)

    def _o_ativo(self, pasta: Path) -> dict[str, Any]:
        dados = {
            "name": "Freestyle", "version": 1, "priority": 0,
            "match": {"type": "any"},
            "mic": {"button_toggles_system": True, "muted": True, "volume": 70},
            "controllers": {
                "aabbcc000011": {"mic": {"muted": False, "volume": 40},
                                 "leds": {"lightbar": [1, 2, 3]}},
                "aabbcc000022": {"mic": {"muted": True}},
            },
        }
        _grava_cru(pasta, "freestyle.json", dados)
        return dados

    def _o_do_jogo(self, pasta: Path) -> dict[str, Any]:
        dados = {
            "name": "Jogo", "version": 1, "priority": 80,
            "match": {"type": "criteria", "window_class": ["steam_app_42"]},
            "controllers": {"aabbcc000044": {"mic": {"muted": True}}},
        }
        _grava_cru(pasta, "jogo.json", dados)
        return dados

    def test_o_mudo_do_ativo_vai_para_o_dono(self, pasta: Path) -> None:
        """A peça vence o global; o global vale para os controles conhecidos.

        O P3 é conhecido pelo `maquina.json` (ela deu nome a ele) e não tem
        peça no perfil: herda o global calado. O P4 só aparece no perfil do
        JOGO, que não é o ativo: a peça de lá não conta, mas ele é um controle
        conhecido, e herda o global calado do ativo — o mesmo que o boot de
        antes da migração faria com ele ao conectar.
        """
        self._o_ativo(pasta)
        self._o_do_jogo(pasta)
        assert maquina.gravar_o_nome_do_controle(P3, "Controle da sala")

        levados = loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle")

        assert levados == {P1: False, P2: True, P3: True, P4: True}
        assert maquina.mudo_do_microfone(P1) is False
        assert maquina.mudo_do_microfone(P2) is True
        assert maquina.mudo_do_microfone(P3) is True
        assert maquina.mudo_do_microfone(P4) is True
        assert maquina.carregar_maquina().controles[P3].nome == "Controle da sala"

    def test_o_global_calado_alcanca_o_controle_de_outro_perfil(self, pasta: Path) -> None:
        """O controle que só um perfil de jogo conhece herda o global calado do ativo.

        Antes da migração, o `mic.muted: true` global do ativo calava TODO
        controle que conectasse (o replug e o nascimento liam o global). O P4
        não está no `maquina.json` e só tem, no perfil do jogo, um volume —
        nenhuma opinião sobre o mudo. Ficar fora da lista o poria no ar.

        MORDIDA: contar como conhecidos só os controles do ativo e do
        `maquina.json` — o P4 volta a `None`, e nasce no ar.
        """
        self._o_ativo(pasta)
        _grava_cru(pasta, "jogo.json", {
            "name": "Jogo", "version": 1, "priority": 80,
            "match": {"type": "criteria", "window_class": ["steam_app_42"]},
            "controllers": {"aabbcc000044": {"mic": {"volume": 55}}},
        })

        levados = loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle")

        assert (levados or {}).get(P4) is True
        assert maquina.mudo_do_microfone(P4) is True
        assert _cru(pasta, "jogo.json")["controllers"]["aabbcc000044"] == {
            "mic": {"volume": 55}}, "a migração mexeu num perfil que não tinha mudo"

    def test_o_mudo_sai_de_todo_perfil_e_nada_mais_muda(self, pasta: Path) -> None:
        """Só o `muted` sai; a versão de antes fica no histórico.

        MORDIDA: não tirar o `muted` dos perfis (ou tirar a seção inteira).
        """
        ativo = self._o_ativo(pasta)
        jogo = self._o_do_jogo(pasta)

        loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle")

        esperado_ativo = json.loads(json.dumps(ativo))
        del esperado_ativo["mic"]["muted"]
        del esperado_ativo["controllers"]["aabbcc000011"]["mic"]["muted"]
        del esperado_ativo["controllers"]["aabbcc000022"]
        assert _cru(pasta, "freestyle.json") == esperado_ativo
        esperado_jogo = {k: v for k, v in jogo.items() if k != "controllers"}
        assert _cru(pasta, "jogo.json") == esperado_jogo
        for nome, original in (("freestyle", ativo), ("jogo", jogo)):
            guardadas = loader.listar_historico(nome)
            assert [json.loads(v.read_text(encoding="utf-8")) for v in guardadas] == [
                original], f"a versão de antes de {nome} não ficou no histórico"
        for arquivo in ("freestyle.json", "jogo.json"):
            loader.load_profile(arquivo.removesuffix(".json"))  # continua válido

    def test_roda_uma_vez_so(self, pasta: Path) -> None:
        """A marca impede a segunda corrida — e o dono de depois não é pisado."""
        self._o_ativo(pasta)
        assert loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle")
        assert maquina.gravar_o_mudo_do_microfone(P2, False)  # ela ligou depois
        self._o_ativo(pasta)  # um perfil de antes, restaurado à mão

        assert loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle") is None
        assert maquina.mudo_do_microfone(P2) is False

    def test_o_dono_que_ja_diz_nao_e_pisado(self, pasta: Path) -> None:
        """O controle que já tem o mudo no dono fica como está."""
        self._o_ativo(pasta)
        assert maquina.gravar_o_mudo_do_microfone(P2, False)

        levados = loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle")

        assert P2 not in (levados or {})
        assert maquina.mudo_do_microfone(P2) is False

    def test_o_dono_que_recusa_nao_tira_o_mudo_dos_perfis(
        self, pasta: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Sem gravar no dono, nada sai dos perfis e não há marca.

        O silêncio dela não pode se perder no meio do caminho: a próxima
        subida tenta de novo.
        """
        ativo = self._o_ativo(pasta)
        real = maquina.gravar_o_mudo_do_microfone
        monkeypatch.setattr(maquina, "gravar_o_mudo_do_microfone", lambda *_a: False)

        assert loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle") is None

        assert _cru(pasta, "freestyle.json") == ativo
        monkeypatch.setattr(maquina, "gravar_o_mudo_do_microfone", real)
        assert loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle")

    def test_a_copia_de_fabrica_fica_como_veio(self, pasta: Path) -> None:
        """O Freestyle recém-semeado não é reescrito, e o `muted` dele não vai ao dono.

        O asset traz `"muted": false`, que não é escolha dela. Reescrevê-lo
        faria a fábrica deixar de ser fábrica em TODA máquina nova — a
        `o_freestyle_de_fabrica_nasce_ligado` e o install comparam os bytes.

        MORDIDAS: tirar o `_e_copia_de_fabrica` do laço dos perfis (o arquivo
        muda), ou do perfil ativo (o P3 ganha uma opinião que ela não deu).
        """
        asset = loader._seed_source_file(loader.ARQUIVO_DO_PADRAO)
        assert asset is not None
        bruto = asset.read_bytes()
        assert "muted" in json.loads(bruto)["mic"], (
            "o asset perdeu o `muted`: esta régua perdeu o objeto e pode sair")
        (pasta / loader.ARQUIVO_DO_PADRAO).write_bytes(bruto)
        assert maquina.gravar_o_nome_do_controle(P3, "Controle da sala")

        assert loader.o_mudo_do_microfone_vai_para_o_controle(ativo="Freestyle") == {}

        assert (pasta / loader.ARQUIVO_DO_PADRAO).read_bytes() == bruto
        assert maquina.mudo_do_microfone(P3) is None
        assert loader.listar_historico("Freestyle") == []

    def test_o_ativo_e_o_que_o_boot_restaura(self, pasta: Path) -> None:
        """Sem `ativo`, a migração pergunta ao boot (`resolve_boot_profile`)."""
        from hefesto_dualsense4unix.utils.session import save_last_profile

        self._o_ativo(pasta)
        self._o_do_jogo(pasta)
        save_last_profile("Jogo")

        assert loader.o_mudo_do_microfone_vai_para_o_controle() == {P4: True}


# ===========================================================================
# 6. O 🎙 SOBRE UMA POSSE VELHA
# ===========================================================================


class TestAPosseVelha:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("uniq", OS_QUATRO)
    async def test_o_microfone_da_tela_escreve_sobre_a_posse_que_desdiz(
        self, casa: Any, uniq: str  # noqa: F811
    ) -> None:
        """O bit está no ar por um instante, e a posse do Hefesto diz calado.

        O defeito do item 2 da O-BOTAO pelo lado da tela: sem a pergunta à
        posse, o 🎙 pulava a escrita, respondia «feito», e o report seguinte do
        Hefesto calava o controle de novo.

        MORDIDA: tirar `_a_posse_nao_desdiz` de `_metade_do_firmware`.
        """
        casa.perfil(FREESTYLE)
        daemon = casa.daemon(OS_QUATRO, transportes=TRANSPORTES["cabo-primeiro"])
        kernel = daemon.controller
        assert kernel.set_microphone_mute(True, uniq=uniq)  # a posse velha: calado
        kernel._firmware_mudo[uniq] = False                 # o bit, livre por um instante

        ato = await hotkey.ligar_o_microfone(daemon, uniq, ligado=True)
        kernel.report(uniq)
        await _derrubar(daemon)

        assert ato.firmware.feita
        assert kernel.mudo_no_firmware(uniq) is False, (
            "o report seguinte do Hefesto calou de novo o microfone que o 🎙 ligou"
        )

    @pytest.mark.asyncio
    async def test_sem_posse_o_microfone_do_plastico_segue_do_kernel(
        self, casa: Any  # noqa: F811
    ) -> None:
        """A posse do kernel (`None`) e o bit no lugar: nada se escreve."""
        casa.perfil(FREESTYLE)
        daemon = casa.daemon((P1,))
        daemon.controller._firmware_mudo[P1] = True

        await hotkey.ligar_o_microfone(daemon, P1, ligado=False)
        await _derrubar(daemon)

        assert daemon.controller.escritas_do_mudo == [], (
            "o ato escreveu o bit que o kernel já tinha posto — e tomou do "
            "botão dela a posse"
        )
