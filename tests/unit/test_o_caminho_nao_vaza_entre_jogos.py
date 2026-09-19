"""O CAMINHO DE UM JOGO NÃO VAZA PARA O SEGUINTE — O-CAMINHO-NAO-VAZA-01.

Decisão dela, 17/09/2026, ao ver a causa: *"puts aqui é fogo kkkkkkkkkkk,
deveria ficar só pra aquele jogo do perfil não? mas ótima descoberta"*.

A QUEIXA, e ela é de quem estava jogando: *"joguei um jogo com controle por
movimento e na hora do vamos ver o controle não deu resposta (pragmata)"*.

O DEFEITO, medido no disco dela em 17/09/2026 — três perfis opinam um caminho
(`dont_scream.json` e `future_knight.json` pedem `"xbox"`,
`sackboytm_a_big_adventure.json` pede `"dualsense"`), o `pragmata.json` não tem
sequer seção `mode`, e o `gamepad_caminho.flag` diz `dualsense`. Ela nunca
escolheu xbox como regra da casa: escolheu para UM jogo. Mas o apply do perfil
carimbava esse `"xbox"` em `config.gamepad_caminho` e o start seguinte — o do
jogo que NÃO opina — herdava dali. O PRAGMATA abria em uinput, e com o canal
uinput vão embora as dez linhas do mapa que só existem no caminho DualSense, a
IMU entre elas: `virtual_pad.quer_uhid` devolve False, `start_motion_reader` sai
na primeira linha e o jogo recebe giroscópio neutro para sempre, sem erro e sem
uma linha de log que explique.

A CURA são DOIS SLOTS onde havia um, e cada régua abaixo morde um pedaço dela:

- `config.gamepad_caminho_global` — a escolha DELA, a que vale em todo jogo. Só
  o gesto manual escreve, e o boot a relê de `gamepad_caminho.flag`. É o ÚNICO
  lugar de onde um start sem opinião herda (`gamepad._caminho_a_herdar`).
- `config.gamepad_caminho` — o caminho DESTA sessão. Acompanha todo start,
  inclusive limpando quando ninguém opina, e é dele que vivem a tela, as envs do
  wrapper, o ciclo do PS + R3 e a mesa de co-op.

AS DUAS MORDIDAS, e são o código que estava na árvore até 17/09:

1. `test_a_mordida_...heranca...` repõe a leitura velha em `_caminho_a_herdar`
   (o slot da SESSÃO) e mostra o PRAGMATA voltando a uinput com o motion reader
   mudo.
2. `test_a_mordida_...mesa...` repõe o corpo velho de `_guardar_o_caminho` (que
   retornava cedo quando ninguém opinava, deixando o slot rançoso) e mostra o
   jogador 2 nascendo em uinput atrás de um P1 já em uhid.

POR QUE AS DUAS ASSERÇÕES, e não só o backend: backend certo com reader mudo já
aconteceu nesta casa. Cada régua confere o canal E o espelho de motion de pé.

Bancada hermética: faixa forjada `aa:bb:cc:00:00:*` (regra do anonimato — nada
de MAC real em arquivo versionado), nenhum `/dev/uinput`, nenhum `/dev/uhid`,
nenhum aparelho, nenhum GTK, nenhuma janela.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from hefesto_dualsense4unix.daemon.subsystems import gamepad as gp
from hefesto_dualsense4unix.daemon.subsystems.coop import CoopManager
from hefesto_dualsense4unix.integrations import virtual_pad as vp

#: A mesa forjada da casa (octetos 4 e 5 zerados).
MAC_P1 = "aabbcc000001"
MAC_P2 = "aabbcc000002"

#: O jogo que OPINA — é o `dont_scream.json` dela, que pede `"caminho": "xbox"`.
CAMINHO_DO_JOGO_QUE_OPINA = "xbox"


class _PadFalso:
    """Um vpad com o que o produto lê dele: máscara, canal e caminho de origem.

    O canal NÃO é digitado: sai de `virtual_pad.quer_uhid`, a mesma função que o
    produto usa. Uma régua que cravasse `backend="uhid"` aqui passaria verde com
    o gate do canal quebrado — que é exatamente o defeito sob medição.
    """

    def __init__(self, flavor: str, caminho: str | None) -> None:
        self.flavor = flavor
        self.caminho = vp.caminho_resolvido(caminho, flavor)
        self.backend = "uhid" if vp.quer_uhid(caminho, flavor) else "uinput"
        self.parado = False

    def stop(self) -> None:
        self.parado = True


class _LeitorFalso:
    """`PhysicalReportReader` de mentira: só existe para ser CONTADO."""

    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs

    def start(self) -> bool:
        return True

    def stop(self) -> None: ...


class _EvdevFalso:
    """`EvdevReader` de mentira, já com o grab confirmado (co-op)."""

    def __init__(self, device_path: Any = None, target_uniq: str | None = None) -> None:
        self.device_path = device_path
        self.target_uniq = target_uniq
        self.grab_state = "off"

    def start(self) -> bool:
        return True

    def set_grab(self, grab: bool) -> bool:
        self.grab_state = "held" if grab else "off"
        return True

    def stop(self) -> None: ...

    def snapshot(self) -> Any:  # pragma: no cover - `forward_all` não roda aqui
        raise NotImplementedError


def _daemon(*, escolha_dela: str | None = None) -> Any:
    """Daemon dublado com a máscara DualSense e o backend real liberando uhid.

    `escolha_dela` é `config.gamepad_caminho_global`: o que ELA escolheu para
    valer em todo jogo. ``None`` = ela nunca escolheu, que é o caso da bancada
    do PRAGMATA — o `gamepad_caminho.flag` dela diz `dualsense`, e nenhum dos
    dois valores pode fazer um jogo sem opinião cair em uinput.
    """
    controller = SimpleNamespace(
        primary_uniq=MAC_P1,
        _evdev=SimpleNamespace(_device_path=Path("/dev/input/event5")),
        _desired=SimpleNamespace(player_leds=None),
        set_player_leds=lambda _bits: None,
        hidraw_path=lambda uniq=None: "/dev/hidraw4",
    )
    return SimpleNamespace(
        config=SimpleNamespace(
            gamepad_flavor="dualsense",
            gamepad_emulation_enabled=False,
            gamepad_caminho=None,
            gamepad_caminho_global=escolha_dela,
            coop_enabled=True,
            rumble_active=None,
        ),
        _gamepad_device=None,
        _mouse_device=None,
        _motion_reader=None,
        controller=controller,
        _coop_manager=None,
    )


@pytest.fixture(autouse=True)
def _bancada(monkeypatch: pytest.MonkeyPatch) -> list[_PadFalso]:
    """Nenhum nó de kernel, e a lista de todo vpad que a sessão pediu.

    A suíte desta casa já derrubou a sessão gráfica dela criando 1289 nós uinput
    de verdade num dia (20/08/2026). Esta bateria não cria nenhum.
    """
    nascidos: list[_PadFalso] = []

    def _fabrica(flavor: str | None, **kwargs: Any) -> _PadFalso:
        pad = _PadFalso(flavor or "dualsense", kwargs.get("caminho"))
        nascidos.append(pad)
        return pad

    monkeypatch.setattr(
        "hefesto_dualsense4unix.integrations.virtual_pad.make_virtual_pad", _fabrica
    )
    monkeypatch.setattr(gp, "_set_controller_grab", lambda *_a: None)
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.physical_report_reader.PhysicalReportReader",
        _LeitorFalso,
    )
    return nascidos


@pytest.fixture()
def _mesa_de_dois(monkeypatch: pytest.MonkeyPatch) -> None:
    """Dois DualSense na mesa, sem nenhum aparelho e sem `/dev/input`."""
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.EvdevReader", _EvdevFalso
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.InputDirWatch.poll", lambda self: True
    )
    monkeypatch.setattr(
        "hefesto_dualsense4unix.core.evdev_reader.discover_dualsense_evdevs",
        lambda: {MAC_P1: Path("/dev/input/event5"), MAC_P2: Path("/dev/input/event7")},
    )
    monkeypatch.setattr("hefesto_dualsense4unix.core.sysfs_leds.discover", lambda: {})


def _o_jogo_que_opina(daemon: Any) -> None:
    """O DON'T SCREAM: o perfil pede `xbox` e o produto OBEDECE."""
    gp.start_gamepad_emulation_desfecho(
        daemon, "dualsense", origin="profile", caminho=CAMINHO_DO_JOGO_QUE_OPINA
    )


def _o_jogo_que_nao_opina(daemon: Any) -> None:
    """O PRAGMATA: o perfil não tem seção `mode`, logo `caminho=None`."""
    gp.start_gamepad_emulation_desfecho(daemon, "dualsense", origin="profile")


def _heranca_pelo_slot_da_sessao(daemon: Any) -> str | None:
    """A MORDIDA: `_caminho_a_herdar` como estava até 17/09/2026.

    Uma linha, e é a diferença entre a IMU viva e a IMU morta: herdar do slot da
    SESSÃO é herdar o canal que o jogo anterior deixou de pé.
    """
    return vp.normalizar_caminho(getattr(daemon.config, "gamepad_caminho", None))


def _guardar_sem_limpar(
    daemon: Any, caminho: str | None, *, origin: str, da_sessao: Any = None
) -> None:
    """A MORDIDA da mesa: `_guardar_o_caminho` como estava até 17/09/2026.

    O corpo velho: quem não manda caminho não apaga o que estava. Era certo
    enquanto havia UM slot só (apagar teria apagado a escolha dela junto) e
    virou o vazamento assim que a escolha dela ganhou casa própria.
    """
    escolhido = vp.normalizar_caminho(caminho)
    if escolhido is None:
        return
    daemon.config.gamepad_caminho = escolhido


# ===========================================================================
# R1 — O P1: o jogo que não opina abre no caminho DualSense
# ===========================================================================


class TestOJogoSeguinteNaoHerdaOCanal:
    def test_o_jogo_que_opina_e_obedecido(self) -> None:
        """PRIMEIRO o que NÃO pode regredir: a escolha dela para AQUELE jogo.

        Ela confirmou que escolheu Xbox no DON'T SCREAM e que funcionou. A cura
        do vazamento não pode custar isso — o perfil que opina manda.
        """
        daemon = _daemon()

        _o_jogo_que_opina(daemon)

        assert daemon._gamepad_device.backend == "uinput"
        assert daemon._gamepad_device.caminho == "xbox"
        assert daemon.config.gamepad_caminho == "xbox", (
            "o caminho DESTA sessão é o que o perfil pediu — a tela, as envs do "
            "wrapper e a mesa de co-op leem daqui"
        )

    def test_o_perfil_nao_escreve_a_escolha_global_dela(self) -> None:
        """O apply de um perfil não vira lei sobre os outros 29.

        É a metade da cura que mora em `_guardar_o_caminho`: só o gesto MANUAL
        escreve a escolha dela. Medido no disco dela em 17/09: o
        `gamepad_caminho.flag` diz `dualsense` enquanto dois perfis pedem
        `xbox` — a disciplina já valia para o DISCO e faltava para a memória.
        """
        daemon = _daemon()

        _o_jogo_que_opina(daemon)

        assert daemon.config.gamepad_caminho_global is None, (
            "um perfil escreveu a escolha GLOBAL dela — daqui todo jogo sem "
            "opinião passa a herdar o `xbox` de UM jogo"
        )

    def test_o_jogo_sem_opiniao_abre_em_uhid_com_o_espelho_de_motion_de_pe(
        self, _bancada: list[_PadFalso]
    ) -> None:
        """A QUEIXA DELA, em duas asserções: o canal E o espelho.

        Os dois starts em sequência, que são o DON'T SCREAM e o PRAGMATA na
        mesma sessão do daemon dela. O segundo tem de nascer em `uhid` — e o
        `start_motion_reader` tem de PASSAR do gate, senão o jogo recebe um
        giroscópio neutro a 0 Hz com o backend certo na tela.
        """
        daemon = _daemon()
        _o_jogo_que_opina(daemon)

        _o_jogo_que_nao_opina(daemon)

        assert daemon._gamepad_device.backend == "uhid", (
            "o jogo que não opina herdou o canal do anterior — é o PRAGMATA "
            "abrindo em uinput, sem IMU, sem touchpad e sem gatilhos"
        )
        assert isinstance(daemon._motion_reader, _LeitorFalso), (
            "o vpad ficou em uhid mas `start_motion_reader` não passou do gate: "
            "backend certo com o espelho mudo é a IMU parada do mesmo jeito"
        )
        assert len(_bancada) == 2, "o segundo start tinha de RECRIAR o vpad"

    def test_quem_nao_opina_nasce_dualsense_mesmo_com_o_global_dizendo_xbox(
        self,
    ) -> None:
        """Um start sem opinião nasce DualSense — e não herda de lugar nenhum.

        CAMINHO-CONTAGIO-01, ponto 2 do escopo de 19/09/2026, e é a prova de
        pronto que a sprint escreve: *"perfil sem `mode` sobe em `uhid` com a
        máscara `dualsense`, mesmo com o arquivo global dizendo `xbox`"*.

        NOTA DATADA — 19/09/2026, E ELA CADUCA UMA RÉGUA DE 17/09. Este teste
        chamava-se `test_a_escolha_global_dela_continua_valendo_para_quem_nao_opina`
        e exigia o CONTRÁRIO: com o global em `xbox`, um jogo sem opinião tinha
        de subir em `uinput`. Era certo enquanto a herança fosse a cura — a
        O-CAMINHO-NAO-VAZA-01 mudou a FONTE da herança e o vazamento voltou por
        outra porta, porque o arquivo global é escrito por TODO gesto manual.

        A decisão dela, ao ver a causa:

            *"sim tudo dualsense, tudo ligado mascara dualsense por default mas
            esse vazamento me preocupa"*  <!-- noqa-acento: citação literal dela -->

        Enquanto um start sem opinião herdar de QUALQUER lugar, existe um lugar
        a envenenar. O caminho DualSense é o que tem todas as features, e é o
        default que a ordem dela de 17/09 já pedia.

        O `gamepad_caminho_global` continua existindo e continua sendo escrito
        — é o que a tela mostra como escolha dela. O que mudou é que ninguém
        NASCE dele, e é isso que esta régua mede.
        """
        daemon = _daemon(escolha_dela="xbox")

        _o_jogo_que_nao_opina(daemon)

        assert daemon._gamepad_device.backend == "uhid"
        assert daemon._gamepad_device.caminho == "dualsense"
        # E a escolha dela NÃO foi apagada pelo caminho — ela continua no slot,
        # para a tela ter o que mostrar. Quem a devolve ao default é o boot
        # (`lifecycle._a_escolha_dela_sem_o_vazamento`), uma vez só.
        assert daemon.config.gamepad_caminho_global == "xbox"

    def test_a_mordida_a_heranca_pelo_slot_da_sessao_devolve_o_defeito(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA: a linha de antes de 17/09 reposta, o defeito de volta.

        Regra desta casa: *um teste que passa com a cura arrancada não testa
        nada*. Aqui a cura é UMA função (`_caminho_a_herdar`) e o laço de
        produção inteiro roda por cima dela — a mordida mede o CAMINHO, não o
        método.

        Medido: com a cura, o segundo start dá `uhid` + reader de pé; com ela
        arrancada, `uinput` + reader `None`.
        """
        daemon = _daemon()
        _o_jogo_que_opina(daemon)
        monkeypatch.setattr(gp, "_caminho_a_herdar", _heranca_pelo_slot_da_sessao)

        _o_jogo_que_nao_opina(daemon)

        assert daemon._gamepad_device.backend == "uinput", (
            "a mordida não mordeu: com a herança pelo slot da sessão o PRAGMATA "
            "TEM de voltar a uinput. Se isto é 'uhid', a régua está medindo o "
            "dublê e não o produto — conserte a régua"
        )
        assert daemon._motion_reader is None


# ===========================================================================
# R2 — A MESA DE QUATRO: o mesmo defeito pelo co-op
# ===========================================================================


class TestAMesaNaoHerdaOCanalDoJogoAnterior:
    def test_o_jogador_2_nasce_em_uhid_depois_de_um_jogo_em_xbox(
        self, _mesa_de_dois: None, _bancada: list[_PadFalso]
    ) -> None:
        """*"O modo é um para todos"* — e todos é a mesa de AGORA, não a de ontem.

        Sem esta régua, a cura do P1 deixaria a mesa de quatro amputada e
        ninguém veria: o P1 em uhid com giroscópio, e os três secundários em
        uinput, sem `_start_player_motion_reader`, entregando ~0,4 Hz de motion
        ao jogo contra os 165-196 Hz do jogador 1 (medido em 15/08/2026).
        """
        daemon = _daemon()
        _o_jogo_que_opina(daemon)
        _o_jogo_que_nao_opina(daemon)

        gerente = CoopManager(daemon)
        gerente.sync()

        jogador_2 = gerente._players[MAC_P2]
        assert jogador_2.vpad.backend == "uhid", (
            "o jogador 2 herdou o canal do jogo anterior — a mesa inteira ficou "
            "sem giroscópio atrás de um P1 que tem"
        )
        assert jogador_2.vpad.caminho == "dualsense"

    def test_a_mordida_o_slot_rancoso_devolve_a_mesa_amputada(
        self, _mesa_de_dois: None, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A MORDIDA da mesa: o corpo velho de `_guardar_o_caminho` reposto.

        O co-op lê `config.gamepad_caminho` — e é a leitura CERTA, desde que o
        slot acompanhe a sessão. Com o retorno cedo de antes de 17/09 ele fica
        com o `xbox` do jogo anterior, e o jogador 2 nasce em uinput enquanto o
        P1 já está em uhid: a divergência que ninguém vê, porque a tela mostra
        só o P1.
        """
        daemon = _daemon()
        _o_jogo_que_opina(daemon)
        monkeypatch.setattr(gp, "_guardar_o_caminho", _guardar_sem_limpar)
        _o_jogo_que_nao_opina(daemon)

        gerente = CoopManager(daemon)
        gerente.sync()

        assert daemon._gamepad_device.backend == "uhid", (
            "premissa da mordida: o P1 já está curado — o que se mede aqui é a "
            "mesa ficando para trás"
        )
        assert gerente._players[MAC_P2].vpad.backend == "uinput", (
            "a mordida não mordeu: com o slot rançoso o jogador 2 TEM de nascer "
            "em uinput. Se isto é 'uhid', a régua não mede o co-op"
        )
