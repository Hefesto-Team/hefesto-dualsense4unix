"""CONFIG-03 — o que ela DECLAROU sobre a mesa sobrevive a fechar a janela.

A aba Configurações pergunta o que o Hefesto não tem como medir (altura da
antena, linha de visada, o que é o rádio vizinho, o modo da chave física, a cor
do plástico quando a leitura falha). Esta bateria vigia as sete propriedades sem
as quais aquela aba mentiria:

1. **todo campo nasce em "não sei"** — e ausência, arquivo truncado, JSON que não
   é objeto e versão desconhecida caem todos no mesmo lugar, sem levantar;
2. **ida e volta** — o que foi declarado volta igual do disco;
3. **a fusão é parcial** — uma seção declarando não apaga o que as outras quatro
   declararam, e ``None`` explícito é escolha ("voltei para 'Não sei'");
4. **arquivo de versão que não é a nossa não é lido NEM sobrescrito** — os BYTES
   do disco continuam idênticos, e a recusa chega à tela;
5. **a chave de controle é MAC de HARDWARE** — a volátil e a sintetizada (octeto
   ``02``) são recusadas pelo schema, e a de rádio é ``vid:pid``;
6. **``extra="forbid"``** — chave que não conhecemos dentro da v1 é recusada, e o
   rótulo ``"máximo"`` não passa por ``"max"``;
7. **o caminho inteiro existe** — o daemon lê no boot, o handler recusa NO CORPO,
   a ponte traduz o motivo e o "Aplicar" do rodapé grava (inclusive quando há
   escolha de modo pendente, que é onde o defeito de ordem se esconderia).

Bancada: nenhum aparelho, nenhum MAC real (faixa forjada ``aa:bb:cc:*``). O
``config_dir`` é o isolado por ``_hefesto_fake_env`` (``tests/conftest.py:1109``),
e a fixture ``arquivo`` prova a cada teste que ele está sob o ``tmp_path`` — sem
essa prova, um defeito de path escreveria no ``~/.config`` dela.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("o rodapé importa gui_dialogs, que puxa Gtk no topo")

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.app import ipc_bridge
from hefesto_dualsense4unix.app.actions.footer_actions import FooterActionsMixin
from hefesto_dualsense4unix.core.controller import ControllerState
from hefesto_dualsense4unix.core.events import EventBus
from hefesto_dualsense4unix.daemon.ipc_handlers import IpcHandlersMixin
from hefesto_dualsense4unix.daemon.ipc_server import IpcServer
from hefesto_dualsense4unix.daemon.lifecycle import Daemon, DaemonConfig
from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.testing import FakeController
from hefesto_dualsense4unix.utils.maquina import (
    MAQUINA_SCHEMA_VERSION,
    MaquinaConfig,
    caminho_da_maquina,
    carregar_maquina,
    fundir_declaracao,
    gravar_maquina,
)

#: Um rosto da faixa forjada, na forma em que a chave vai ao disco: doze hex
#: minúsculos, sem separador (a saída de `ExternalIdentityRegistry._canonical`).
CHAVE_DE_HARDWARE = "aabbcc00beef"

#: O endereço que o `usb_probe_degrade` FORJA: `02` + VID + PID + bus. Dois
#: clones do mesmo modelo recebem este mesmo endereço.
CHAVE_SINTETIZADA = "02057e20090001"[:12]

#: A identidade VOLÁTIL, no formato que `_external_dedup_key` devolve quando não
#: há `uniq` nenhum.
CHAVE_VOLATIL = "dev:0003:057E:2009.0001"


@pytest.fixture
def arquivo(tmp_path: Path) -> Path:
    """O ``maquina.json`` desta bancada — e a prova de que ele não é o dela.

    CANÁRIO: se algum dia o módulo resolver ``config_dir`` no topo (o defeito de
    ``app/gui_prefs.py:21``), o caminho deixa de cair no ``tmp_path`` e esta
    asserção é a única coisa entre a suíte e o ``~/.config`` da mantenedora.
    """
    caminho = caminho_da_maquina()
    assert tmp_path in caminho.parents, f"{caminho} escapou do tmp da bancada"
    return caminho


def _documento(arquivo: Path) -> dict[str, Any]:
    return dict(json.loads(arquivo.read_text(encoding="utf-8")))


class _Servidor(IpcHandlersMixin):
    """O mixin de handlers com o mínimo que o ``machine.declare`` toca."""

    def __init__(self) -> None:
        self.daemon = SimpleNamespace(_maquina=MaquinaConfig())  # type: ignore[assignment]


class _Rodape(FooterActionsMixin):
    """O rodapé com o mínimo que ``on_apply_draft`` toca antes de aplicar."""

    def __init__(self) -> None:
        self.caronas: list[str] = []
        self.aplicou_pendente: list[dict[str, str]] = []
        self.aplicou_agora = 0
        self.avisos: list[str] = []

    def pegar_carona_no_gesto(self, gesto: str) -> None:
        self.caronas.append(gesto)

    def _aplicar_escolha_pendente(self, pendente: dict[str, str]) -> None:
        self.aplicou_pendente.append(pendente)

    def _apply_draft_agora(self) -> None:
        self.aplicou_agora += 1

    def _footer_toast(self, msg: str, context: str = "footer") -> None:
        self.avisos.append(msg)


def _estado() -> ControllerState:
    return ControllerState(
        battery_pct=80, l2_raw=0, r2_raw=0, connected=True,
        transport="usb", buttons_pressed=frozenset(),
    )


def _config_de_daemon() -> DaemonConfig:
    return DaemonConfig(  # type: ignore[arg-type]
        poll_hz=200, auto_reconnect=False, ipc_enabled=False, udp_enabled=False,
        autoswitch_enabled=False, mouse_emulation_enabled=False,
        keyboard_emulation_enabled=False, ps_button_action="none",
        mic_button_toggles_system=False,
    )


# ---------------------------------------------------------------------------
# 1. Todo campo nasce em "não sei"
# ---------------------------------------------------------------------------


def test_sem_arquivo_tudo_em_nao_sei(arquivo: Path) -> None:
    """Instalação nova: nenhum campo tem opinião, e nada levanta.

    Invariante 1 da leva. Um campo com valor de fábrica seria o default entrando
    disfarçado de escolha dela — e a aba mostraria "Balanceado" marcado para
    quem nunca abriu a aba.

    MORDE: dando a ``OrcamentoDeclarado.teto`` o default ``"balanceado"`` —
    ``AssertionError`` na penúltima asserção. (Arrancar o ``return`` da ausência
    NÃO reprova aqui: o ``except Exception`` de ``carregar_maquina`` é a segunda
    camada da mesma promessa, e é ela que o teste do arquivo truncado ataca.)
    """
    assert not arquivo.exists()
    cfg = carregar_maquina()

    assert cfg.version == MAQUINA_SCHEMA_VERSION
    assert cfg.mesa.altura_da_antena is None
    assert cfg.mesa.linha_de_visada is None
    assert cfg.mesa.radios == {}
    assert cfg.controles == {}
    assert cfg.orcamento.teto is None


def test_json_truncado_e_nao_objeto_caem_no_default(arquivo: Path) -> None:
    """Metade de um JSON, e um JSON que é lista: os dois viram "não sei".

    E, mais importante, os dois seguem GRAVÁVEIS: um arquivo que já não diz nada
    não é escolha de ninguém a preservar — o contrário travaria a aba para sempre
    depois de uma escrita interrompida.

    MORDE: tirando ``json.JSONDecodeError`` do ``except`` de ``_ler_documento``
    — ``json.decoder.JSONDecodeError: Expecting ',' delimiter`` sobe da
    gravação, porque ali não há segunda camada que segure (em
    ``carregar_maquina`` há, e é o ``except Exception``).
    """
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text('{"version": 1, "mesa": {"altura_da', encoding="utf-8")
    assert carregar_maquina().mesa.altura_da_antena is None
    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}})
    assert carregar_maquina().mesa.altura_da_antena == "abaixo"

    arquivo.write_text('["nem objeto é"]', encoding="utf-8")
    assert carregar_maquina().mesa.altura_da_antena is None
    assert gravar_maquina({"orcamento": {"teto": "auto"}})
    assert carregar_maquina().orcamento.teto == "auto"

    arquivo.write_text('{"version": 1, "orcamento": {"teto": "plan9"}}', encoding="utf-8")
    assert carregar_maquina().orcamento.teto is None


# ---------------------------------------------------------------------------
# 2 e 3. Ida e volta, e a fusão parcial
# ---------------------------------------------------------------------------


def test_ida_e_volta(arquivo: Path) -> None:
    """O que foi declarado volta igual — e o arquivo só tem o que ela declarou.

    MORDE: trocando ``os.replace(tmp, path)`` por ``os.unlink(tmp)`` em
    ``_escrever`` — ``FileNotFoundError`` na leitura do documento, porque nada
    chegou ao disco.
    """
    assert gravar_maquina(
        {
            "mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"},
            "orcamento": {"teto": "economia"},
            "controles": {CHAVE_DE_HARDWARE: {"modo": "switch", "cor": "Volcanic Red"}},
        }
    )

    cfg = carregar_maquina()
    assert cfg.mesa.altura_da_antena == "acima"
    assert cfg.mesa.linha_de_visada == "livre"
    assert cfg.orcamento.teto == "economia"
    assert cfg.controles[CHAVE_DE_HARDWARE].modo == "switch"
    assert cfg.controles[CHAVE_DE_HARDWARE].cor == "Volcanic Red"

    # O silêncio não vai ao disco: `None` e chave ausente dizem a mesma coisa.
    documento = _documento(arquivo)
    assert documento["version"] == 1
    assert "botoes" not in documento["controles"][CHAVE_DE_HARDWARE]
    assert "radios" not in documento["mesa"]


def test_a_fusao_nao_apaga_o_que_outra_secao_declarou(arquivo: Path) -> None:
    """Cinco seções, um arquivo: a última a gravar não apaga as outras quatro.

    É a propriedade que permite a cada seção mandar SÓ o que mudou. Sem ela,
    declarar o orçamento zeraria a altura da antena — e o gesto que a aba
    oferece (mexer numa coisa) destruiria o resto em silêncio.

    MORDE: trocando o corpo de ``fundir_declaracao`` por ``dict(declaracao)`` —
    a altura da antena volta ``None`` na terceira asserção.
    """
    assert gravar_maquina({"mesa": {"altura_da_antena": "acima"}})
    assert gravar_maquina({"orcamento": {"teto": "max"}})
    assert gravar_maquina({"mesa": {"linha_de_visada": "com_gente"}})
    assert gravar_maquina(
        {"mesa": {"radios": {"046d:c52b": {"tipo": "mouse", "apelido": "Da TV"}}}}
    )

    cfg = carregar_maquina()
    assert cfg.mesa.altura_da_antena == "acima"
    assert cfg.mesa.linha_de_visada == "com_gente"
    assert cfg.orcamento.teto == "max"
    assert cfg.mesa.radios["046d:c52b"].tipo == "mouse"
    assert cfg.mesa.radios["046d:c52b"].apelido == "Da TV"


def test_none_declarado_volta_para_nao_sei(arquivo: Path) -> None:
    """``None`` presente é escolha ("voltei para 'Não sei'"), e sobrescreve.

    Só a AUSÊNCIA da chave preserva. Sem esta metade, a aba teria caminho de ida
    e não de volta: marcar "Acima" por engano seria definitivo.

    MORDE: fazendo ``fundir_declaracao`` pular valores ``None`` — a altura
    continua ``"acima"`` na última asserção.
    """
    assert gravar_maquina(
        {"mesa": {"altura_da_antena": "acima", "linha_de_visada": "livre"}}
    )
    assert gravar_maquina({"mesa": {"altura_da_antena": None}})

    cfg = carregar_maquina()
    assert cfg.mesa.linha_de_visada == "livre"
    assert cfg.mesa.altura_da_antena is None


def test_fundir_declaracao_nao_escreve_no_dicionario_de_origem() -> None:
    """A fusão devolve documento novo até no fundo; ninguém edita o de origem.

    Importa porque as seções da aba acumulam num dicionário VIVO
    (``_maquina_pendente``): se a fusão devolvesse aliases, mexer no resultado
    reescreveria o que a seção ao lado tinha marcado.

    MORDE: trocando o corpo de ``_copia_funda`` por ``dict(no)`` raso — o
    ``radios`` do resultado É o ``radios`` da origem, e a última asserção reprova
    com ``"webcam" != "mouse"``.
    """
    base: dict[str, Any] = {
        "mesa": {"altura_da_antena": "acima", "radios": {"046d:c52b": {"tipo": "mouse"}}}
    }
    fundido = fundir_declaracao(base, {"mesa": {"linha_de_visada": "livre"}})

    assert fundido["mesa"]["altura_da_antena"] == "acima"
    assert fundido["mesa"]["linha_de_visada"] == "livre"
    assert "linha_de_visada" not in base["mesa"]

    fundido["mesa"]["radios"]["046d:c52b"]["tipo"] = "webcam"
    assert base["mesa"]["radios"]["046d:c52b"]["tipo"] == "mouse"


# ---------------------------------------------------------------------------
# 4. Versão que não é a nossa
# ---------------------------------------------------------------------------


def test_versao_desconhecida_nao_e_lida_nem_sobrescrita(arquivo: Path) -> None:
    """Escolha de alguém não se destrói para registrar outra.

    Os BYTES do disco são comparados, não o conteúdo lógico: reescrever o mesmo
    dado com outra formatação já seria ter sobrescrito.

    MORDE: tirando o ``return False`` do ramo de versão em ``gravar_maquina`` —
    a comparação de bytes reprova e o documento da versão 2 vira um documento
    v1 com o campo dela dentro.
    """
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        '{"version": 2, "mesa": {"altura_da_antena": "no_teto"}}', encoding="utf-8"
    )
    antes = arquivo.read_bytes()

    assert gravar_maquina({"mesa": {"altura_da_antena": "abaixo"}}) is False
    assert arquivo.read_bytes() == antes
    # E o que não é nosso também não é LIDO: nada de "no_teto" na tela.
    assert carregar_maquina().mesa.altura_da_antena is None


def test_chave_de_topo_de_uma_versao_futura_sobrevive_ao_save(arquivo: Path) -> None:
    """O save preserva o que não entende — a lição do ``identity.py:951``.

    Um campo de topo que uma versão futura escreveu (num documento que ainda diz
    ``version: 1``) não pode morrer no primeiro save nosso.

    MORDE: trocando o dicionário inicial de ``documento`` por ``{}`` em
    ``gravar_maquina`` — ``KeyError: 'planeta'`` na última asserção.
    """
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps({"version": 1, "ambiente": "gnome", "planeta": {"gravidade": 1}}),
        encoding="utf-8",
    )

    assert gravar_maquina({"orcamento": {"teto": "auto"}})

    documento = _documento(arquivo)
    assert documento["ambiente"] == "gnome"
    assert documento["orcamento"] == {"teto": "auto"}
    assert documento["planeta"] == {"gravidade": 1}


def test_ambiente_de_um_maquina_json_antigo_nao_apaga_a_mesa(arquivo: Path) -> None:
    """T2, CONFIGURAÇÕES-FECHA-01: o campo saiu do esquema — um arquivo antigo
    que ainda o tem não pode perder o resto.

    `ambiente` nunca teve escritor nem leitor (achado da sprint) e saiu de
    `MaquinaConfig`. Quem já tinha um `maquina.json` com ele gravado (a
    mesma máquina desta bancada, antes da migração) precisa continuar
    carregando a `mesa` — `ambiente` vira só mais uma chave que "não é
    nossa", como qualquer campo de versão futura (ver o teste acima).
    """
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps(
            {"version": 1, "ambiente": "gnome", "mesa": {"altura_da_antena": "acima"}}
        ),
        encoding="utf-8",
    )

    cfg = carregar_maquina()

    assert cfg.mesa.altura_da_antena == "acima"
    assert not hasattr(cfg, "ambiente")


def test_campo_invalido_ao_carregar_nao_apaga_o_resto(arquivo: Path) -> None:
    """O resgate campo a campo vale na LEITURA, não só na escrita.

    `gravar_maquina_com_descartes` já isolava o estrago numa subárvore desde
    `9848c41`; `carregar_maquina` ainda tinha `except ValidationError: return
    MaquinaConfig()` — um valor que o schema recusa em UM campo (aqui,
    `orcamento.teto` fora do catálogo) derrubava mesa, controles e orçamento
    juntos, mesmo que só o orçamento estivesse ruim.

    MORDE: trocar o corpo do `except ValidationError` de `carregar_maquina`
    por `return MaquinaConfig()` direto (a forma de antes desta sprint) — a
    asserção da mesa reprova, porque o documento inteiro volta vazio.
    """
    arquivo.parent.mkdir(parents=True, exist_ok=True)
    arquivo.write_text(
        json.dumps(
            {
                "version": 1,
                "mesa": {"altura_da_antena": "acima"},
                "orcamento": {"teto": "generosa"},
            }
        ),
        encoding="utf-8",
    )

    cfg = carregar_maquina()

    assert cfg.mesa.altura_da_antena == "acima"
    assert cfg.orcamento.teto is None


# ---------------------------------------------------------------------------
# 5 e 6. O schema é o portão
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("chave", [CHAVE_SINTETIZADA, CHAVE_VOLATIL, "AABBCC00BEEF"])
def test_chave_de_controle_que_nao_e_mac_de_hardware_e_recusada(
    arquivo: Path, chave: str
) -> None:
    """Sintetizada, volátil e maiúscula: as três ficam fora do disco.

    O ``02`` é o octeto que o ``usb_probe_degrade`` forja, e dois clones do mesmo
    modelo recebem o MESMO endereço — gravá-lo funde dois aparelhos num só. A
    maiúscula é outro defeito: a chave gravada é a SAÍDA de ``_canonical``, e
    aceitar duas grafias faria o mesmo controle ter duas entradas.

    MORDE: tirando o ``field_validator`` de ``controles`` — os três casos gravam,
    e o arquivo passa a ter uma entrada de controle que nunca corresponderá a
    aparelho nenhum.
    """
    with pytest.raises(ValueError):
        gravar_maquina({"controles": {chave: {"cor": "Branco"}}})
    assert not arquivo.exists()


def test_a_faixa_forjada_da_bancada_nao_e_confundida_com_sintese(arquivo: Path) -> None:
    """``aa:bb:cc:*`` tem o bit 0x02 ligado sem ser síntese nossa — e passa.

    O critério é o octeto ``02`` EXATO. Um validador que testasse o BIT
    reprovaria a faixa de teste da casa inteira e todo BLE random-static
    (1º octeto ≥ 0xC0).

    MORDE: trocando ``chave.startswith("02")`` por
    ``int(chave[:2], 16) & 0x02`` — reprova aqui, com a chave da própria
    bancada sendo recusada.
    """
    assert gravar_maquina({"controles": {CHAVE_DE_HARDWARE: {"botoes": "nintendo"}}})
    assert carregar_maquina().controles[CHAVE_DE_HARDWARE].botoes == "nintendo"


def test_chave_de_radio_fora_de_vid_pid_e_recusada(arquivo: Path) -> None:
    """``extra="forbid"`` não protege chave de DICIONÁRIO — o validador protege.

    Sem ele, o disco aceitaria ``{"Fone da TV": {...}}`` como identidade de rádio
    e a próxima versão herdaria lixo que nenhuma enumeração reencontra.

    MORDE: tirando o ``field_validator`` de ``radios`` — a gravação passa e o
    ``pytest.raises`` reprova.
    """
    with pytest.raises(ValueError):
        gravar_maquina({"mesa": {"radios": {"Fone da TV": {"tipo": "outro"}}}})
    with pytest.raises(ValueError):
        gravar_maquina({"mesa": {"radios": {"046D:C52B": {"tipo": "mouse"}}}})
    assert not arquivo.exists()


def test_chave_desconhecida_e_recusada_pelo_forbid(arquivo: Path) -> None:
    """Campo que não conhecemos não entra — nem no topo, nem dentro de uma seção.

    MORDE: trocando ``extra="forbid"`` por ``extra="ignore"`` em
    ``MaquinaConfig`` e ``MesaDeclarada`` — as duas gravações passam, e o dado
    escrito some no primeiro save seguinte sem ninguém saber.
    """
    with pytest.raises(ValueError):
        gravar_maquina({"altura_da_antena": "acima"})
    with pytest.raises(ValueError):
        gravar_maquina({"mesa": {"altura_da_antenna": "acima"}})
    assert not arquivo.exists()


def test_o_rotulo_maximo_e_recusado_e_a_chave_max_e_aceita(arquivo: Path) -> None:
    """A chave é ``max``; ``"Máximo"`` é o rótulo de tela, e não vai ao disco.

    Gravar o rótulo faria o ``extra="forbid"`` recusar o DOCUMENTO INTEIRO, e o
    sintoma na tela seria "não consegui gravar", não "valor inválido" — por isso
    a chave está travada aqui, e não só no mapa de rótulos da aba.

    MORDE: acrescentando ``"máximo"`` ao ``Literal`` de ``teto`` — o
    ``pytest.raises`` reprova, e o disco passa a ter duas grafias para a mesma
    política.
    """
    with pytest.raises(ValueError):
        gravar_maquina({"orcamento": {"teto": "máximo"}})
    assert gravar_maquina({"orcamento": {"teto": "max"}})
    assert carregar_maquina().orcamento.teto == "max"


# ---------------------------------------------------------------------------
# 7. O caminho inteiro
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_o_daemon_le_no_boot(arquivo: Path) -> None:
    """O boot do daemon carrega a declaração do disco, sem exceção.

    Sem esta metade, o arquivo existiria e nenhum consumidor no daemon teria de
    onde lê-lo — o defeito clássico desta casa (a cura escrita e nunca ligada).

    MORDE: tirando a linha ``self._maquina = carregar_maquina()`` do ``run()`` —
    ``_maquina.orcamento.teto`` fica ``None`` e a asserção reprova.
    """
    assert gravar_maquina(
        {"orcamento": {"teto": "economia"}, "mesa": {"altura_da_antena": "acima"}}
    )

    store = StateStore()
    daemon = Daemon(
        controller=FakeController(transport="usb", states=[_estado()]),
        bus=EventBus(), store=store, config=_config_de_daemon(),
    )
    assert daemon._maquina.orcamento.teto is None  # nasce em "não sei"

    tarefa = asyncio.create_task(daemon.run())
    for _ in range(500):
        if store.counter("poll.tick") >= 1:
            break
        await asyncio.sleep(0.01)
    lido = daemon._maquina
    daemon.stop()
    await tarefa

    assert lido.orcamento.teto == "economia"
    assert lido.mesa.altura_da_antena == "acima"


def test_o_metodo_esta_no_dispatcher() -> None:
    """``machine.declare`` está registrado — a metade declarativa.

    MORDE: tirando a linha do dicionário ``_handlers`` — reprova aqui, e a
    janela passaria a receber "método desconhecido" com o handler inteiro vivo.
    """
    servidor = IpcServer(
        controller=FakeController(transport="usb", states=[_estado()]),
        store=StateStore(),
        profile_manager=None,  # type: ignore[arg-type]
    )
    assert servidor._handlers["machine.declare"].__name__ == "_handle_machine_declare"


@pytest.mark.asyncio
async def test_o_handler_grava_e_recusa_no_corpo(arquivo: Path) -> None:
    """Sucesso, recusa por versão e declaração inválida — as três NO CORPO.

    Nenhuma das três pode virar erro JSON-RPC: a ponte da GUI usa ``_safe_call``,
    que colapsa erro de protocolo e daemon morto em ``(False, None)`` — a janela
    diria "daemon offline?" para um daemon vivíssimo.

    MORDE: trocando o ``return {"ok": False, "reason": "declaracao_invalida"}``
    do ``except ValueError`` por ``raise`` — a última asserção reprova com o
    ``ValidationError`` subindo do handler.
    """
    servidor = _Servidor()

    assert await servidor._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "com_gente"}}}
    ) == {"ok": True}
    assert servidor.daemon._maquina.mesa.linha_de_visada == "com_gente"

    arquivo.write_text('{"version": 2}', encoding="utf-8")
    antes = arquivo.read_bytes()
    assert await servidor._handle_machine_declare(
        {"maquina": {"mesa": {"linha_de_visada": "livre"}}}
    ) == {"ok": False, "reason": "versao_desconhecida"}
    assert arquivo.read_bytes() == antes

    assert await servidor._handle_machine_declare({"maquina": {"nao_existe": 1}}) == {
        "ok": False,
        "reason": "declaracao_invalida",
    }
    assert await servidor._handle_machine_declare({"maquina": "texto"}) == {
        "ok": False,
        "reason": "declaracao_invalida",
    }


def test_a_ponte_traduz_o_motivo_e_distingue_daemon_offline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A tela nunca lê ``versao_desconhecida``, e "offline" não é "recusado".

    São duas frases diferentes porque são duas situações diferentes: ligar o
    Hefesto resolve uma e não resolve a outra.

    MORDE: devolvendo ``result.get("reason")`` cru em vez do
    ``_MOTIVOS_MAQUINA`` — a segunda asserção reprova, e a barra de status
    passaria a mostrar identificador de protocolo.
    """
    respostas: list[Any] = []
    monkeypatch.setattr(
        ipc_bridge, "_safe_call", lambda *a, **k: respostas.pop(0)
    )

    respostas.append((True, {"ok": True}))
    assert ipc_bridge.machine_declare({"orcamento": {"teto": "auto"}}) == (True, None)

    respostas.append((True, {"ok": False, "reason": "versao_desconhecida"}))
    ok, motivo = ipc_bridge.machine_declare({"orcamento": {"teto": "auto"}})
    assert ok is False
    assert motivo is not None
    assert "versao_desconhecida" not in motivo
    assert "versão mais nova" in motivo

    respostas.append((False, None))
    assert ipc_bridge.machine_declare({"orcamento": {"teto": "auto"}}) == (False, None)


def test_o_aplicar_grava_e_so_limpa_a_pendencia_quando_o_daemon_confirma(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O botão verde é quem salva a aba diferida — e não perde o que ela marcou.

    Recusa e daemon offline deixam a declaração DE PÉ: as escolhas seguem
    marcadas na aba e clicar de novo tenta de novo.

    MORDE: movendo o ``self._maquina_pendente = None`` para fora do ramo do
    ``ok`` — a última asserção reprova, e uma recusa passaria a apagar em
    silêncio o que ela declarou.
    """
    pedidos: list[dict[str, Any]] = []
    # CONFIG-06 (23/08/2026): o rodapé pede a resposta INTEIRA
    # (`(ok, motivo, descartados)`) — o aviso de campo descartado só existe
    # nela. `machine_declare` segue viva como embrulho de duas pontas.
    resposta: list[tuple[bool, str | None, tuple[str, ...]]] = [(True, None, ())]
    monkeypatch.setattr(
        ipc_bridge,
        "machine_declare_detalhado",
        lambda m: (pedidos.append(m), resposta[0])[1],
    )

    rodape = _Rodape()
    assert rodape._gravar_declaracao_de_maquina() == (True, None)
    assert pedidos == []  # sem declaração, sem chamada

    rodape._maquina_pendente = {"mesa": {"altura_da_antena": "acima"}}
    rodape._gravar_declaracao_de_maquina()
    assert pedidos == [{"mesa": {"altura_da_antena": "acima"}}]
    assert rodape._maquina_pendente is None

    # CONFIG-05 (23/08/2026), achado A3: a frase é DEVOLVIDA, não empurrada na
    # statusbar. Ela era apagada no mesmo tique do GTK pelo toast do
    # `_apply_draft_agora`; quem a mostra agora é o toast FINAL do "Aplicar".
    resposta[0] = (False, "não deu", ())
    rodape._maquina_pendente = {"orcamento": {"teto": "auto"}}
    assert rodape._gravar_declaracao_de_maquina() == (False, "não deu")
    assert rodape.avisos == []
    assert rodape._maquina_pendente == {"orcamento": {"teto": "auto"}}


def test_o_aplicar_com_modo_pendente_tambem_grava(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A armadilha da ordem: ``on_apply_draft`` retorna cedo com modo pendente.

    Pendurar a gravação depois daquele ramo faz o "Aplicar com modo pendente"
    nunca gravar a declaração — e o sintoma seria intermitente, porque depende
    de ela ter mexido na aba Início antes de clicar.

    MORDE: movendo ``self._gravar_declaracao_de_maquina()`` para depois do
    ``if pendente: ... return`` — reprova com ``pedidos == []``, e o outro teste
    do rodapé continua passando (é por isso que este existe separado).
    """
    pedidos: list[dict[str, Any]] = []
    monkeypatch.setattr(
        ipc_bridge,
        "machine_declare_detalhado",
        lambda m: (pedidos.append(m), (True, None, ()))[1],
    )

    rodape = _Rodape()
    rodape._maquina_pendente = {"orcamento": {"teto": "auto"}}
    rodape._escolha_pendente = {"modo": "gamepad"}
    rodape.on_apply_draft()

    assert pedidos == [{"orcamento": {"teto": "auto"}}]
    assert rodape.aplicou_pendente == [{"modo": "gamepad"}]
    assert rodape.aplicou_agora == 0


@pytest.mark.asyncio
async def test_ida_e_volta_pelo_socket_de_verdade(
    tmp_path: Path, arquivo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O caminho inteiro sobre o fio: ponte da GUI → JSON-RPC → daemon → disco.

    Os outros testes provam cada elo em separado, e é justamente isso que os
    deixa cegos ao elo que só existe no fio: a FORMA do payload. Um handler que
    lesse ``params["machine"]`` em vez de ``params["maquina"]``, ou uma ponte que
    mandasse a declaração na raiz dos params, passa em todos eles e falha aqui.

    Socket próprio em ``tmp_path`` e ``XDG_RUNTIME_DIR`` isolado: o daemon VIVO
    da máquina dela nunca é tocado (e ele é mais velho que este código —
    install editable, cura de daemon só vale no próximo start).

    MORDE: trocando ``{"maquina": maquina}`` por ``maquina`` no corpo da ponte —
    a primeira asserção reprova com ``(False, 'O Hefesto não entendeu o que você
    declarou...')``, e nada chega ao disco.
    """
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path / "run"))
    servidor = IpcServer(
        controller=FakeController(transport="usb", states=[_estado()]),
        store=StateStore(),
        profile_manager=None,  # type: ignore[arg-type]
        socket_path=tmp_path / "run" / "hefesto-dualsense4unix" / "e2e.sock",
        daemon=SimpleNamespace(_maquina=MaquinaConfig()),
    )
    monkeypatch.setenv("HEFESTO_DUALSENSE4UNIX_IPC_SOCKET_NAME", "e2e.sock")
    await servidor.start()
    try:
        laco = asyncio.get_running_loop()
        primeira = await laco.run_in_executor(
            None, ipc_bridge.machine_declare, {"mesa": {"altura_da_antena": "acima"}}
        )
        assert primeira == (True, None)
        # A segunda seção manda SÓ o que mudou, e as duas coexistem no disco.
        segunda = await laco.run_in_executor(
            None, ipc_bridge.machine_declare, {"orcamento": {"teto": "economia"}}
        )
        assert segunda == (True, None)
    finally:
        await servidor.stop()

    assert _documento(arquivo) == {
        "version": 1,
        "mesa": {"altura_da_antena": "acima"},
        "orcamento": {"teto": "economia"},
    }
    assert servidor.daemon._maquina.orcamento.teto == "economia"
