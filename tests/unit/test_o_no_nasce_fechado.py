"""O-NO-NASCE-FECHADO-01 — o nó nasce `0600 root` e o Hefesto abre sob pedido.

Decisão dela, 20/09/2026, e ela tem três partes:

    «Nossa udev não deveria garantir isso? Por mim caminho um e lembrando que
     o Hefesto tem que ter prioridade em tudo e isso deveria estar no install
     por default»

O DEFEITO que isto fecha: a Steam aberta ANTES de o controle conectar pelo
rádio abre o `/dev/hidraw` do FÍSICO na janela em que o udev deu `uaccess` e o
broker ainda não tirou — e **tirar a ACL não fecha descritor já aberto**. A
barra de luz fica apagada e não volta nem fechando a Steam. Medido em quatro
noites: 5 de 9 conexões em 10/09, 3 de 3 em 13/09, 8 de 8 em 17/09.

Esta régua é de UNIDADE, e é de propósito: os quatro DualSense dela estão em
uso agora, e um teste que rodasse `udevadm` desfaria o que o produto fez. Nada
aqui toca /dev, /sys, o udev vivo, o broker vivo nem o daemon — as operações de
fs são dublê, o validador é injetado, e a regra udev é lida do asset como
TEXTO.

Cobre as quatro pontas da cura, e cada uma tem a sua mordida escrita no teste:
  1. a regra udev do asset fecha o 0ce6 e ordena ANTES do `73-seat-late`;
  2. o broker abre sob pedido, com lease, refcount e EOF;
  3. o repouso: `restore` deixa de ABRIR o que a regra fechou;
  4. o caminho que só sabe `open(path)` — o `hidapi.Device(path=…)` do handle
     de controle, e o Modo Nativo — passa a pedir exposição.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from hefesto_dualsense4unix.broker.hidraw_broker import (
    NO_NASCE_FECHADO_ENV,
    BrokerState,
    fechar_todo_fisico,
)

RAIZ = Path(__file__).resolve().parents[2]
REGRA = RAIZ / "assets" / "70-ps5-controller.rules"
UNIT = RAIZ / "assets" / "systemd" / "hefesto-hidraw-broker.service"
INSTALL = RAIZ / "install.sh"
CAMADA = RAIZ / "scripts" / "lib" / "camada_de_maquina.sh"
INSTALL_UDEV = RAIZ / "scripts" / "install_udev.sh"

UID = 1000

#: Os dois casamentos do DualSense standard (054c:0ce6) — USB e Bluetooth. São
#: ESTES que a cura fecha. O Edge (0df2) fica de fora de propósito: é o PID do
#: nosso vpad uhid, e fechá-lo pela mesma linha calaria o controle que o
#: Hefesto ENTREGA ao jogo.
CASAMENTOS_DO_FISICO = ('ATTRS{idProduct}=="0ce6"', 'KERNELS=="0005:054C:0CE6.*"')


def linhas_de_regra() -> list[str]:
    """As linhas EFETIVAS do asset (sem comentário e sem linha vazia)."""
    return [
        linha.strip()
        for linha in REGRA.read_text(encoding="utf-8").splitlines()
        if linha.strip() and not linha.lstrip().startswith("#")
    ]


def linha_do_casamento(casamento: str) -> str:
    achadas = [linha for linha in linhas_de_regra() if casamento in linha]
    assert len(achadas) == 1, f"esperava UMA linha com {casamento}, achei {len(achadas)}"
    return achadas[0]


# ---------------------------------------------------------------------------
# 1. A REGRA UDEV — o nó nasce fechado, e antes do 73
# ---------------------------------------------------------------------------


class TestARegraFechaONo:
    @pytest.mark.parametrize("casamento", CASAMENTOS_DO_FISICO)
    def test_o_fisico_perde_a_tag_uaccess(self, casamento: str) -> None:
        """A MORDIDA: troque `TAG-=` por `TAG+=` no asset e isto reprova.

        O `TAG-=` não é enfeite nem sinônimo de omitir o `TAG+=`: o pacote
        `steam-devices` marca o DualSense com `uaccess` num arquivo 60-*, que
        corre ANTES deste. Sem a REMOÇÃO explícita, a TAG de terceiro
        sobrevive e o `73-seat-late` a transforma em ACL — a janela continua
        aberta e a cura não cura nada.
        """
        linha = linha_do_casamento(casamento)
        assert 'TAG-="uaccess"' in linha, linha
        assert 'TAG+="uaccess"' not in linha, linha

    @pytest.mark.parametrize("casamento", CASAMENTOS_DO_FISICO)
    def test_o_fisico_nasce_0600_de_root(self, casamento: str) -> None:
        """Tirar a TAG sem fechar o MODE deixaria o nó `0660 root:root`.

        O grupo importa: `0660` com `GROUP="input"` (ou qualquer grupo em que
        a usuária esteja) abriria o nó por outra porta, e a régua da TAG
        passaria verde sobre um nó aberto.
        """
        linha = linha_do_casamento(casamento)
        assert 'MODE="0600"' in linha, linha
        assert 'OWNER="root"' in linha, linha
        assert 'GROUP="root"' in linha, linha

    def test_o_vpad_continua_aberto(self) -> None:
        """Fechar o vpad seria fechar a porta que a cura existe para proteger.

        O `0003:054C:0DF2` é o DualSense Edge VIRTUAL do daemon — o controle
        que o Hefesto ENTREGA ao jogo. O broker recusa escondê-lo por desenho;
        a regra udev tem de concordar.
        """
        linha = linha_do_casamento('KERNELS=="0003:054C:0DF2.*"')
        assert 'TAG+="uaccess"' in linha, linha
        assert 'MODE="0660"' in linha, linha

    def test_o_arquivo_corre_antes_do_73_seat_late(self) -> None:
        """Quem transforma a TAG em ACL é o `73-seat-late.rules`.

        Renumerar este asset para cima de 73 faria o `TAG-=` rodar DEPOIS de
        a ACL já ter sido escrita — e aí ele não tira nada. O número é parte
        da cura, não organização de pasta.
        """
        numero = int(REGRA.name.split("-", 1)[0])
        assert numero < 73, REGRA.name

    def test_o_comentario_carrega_a_decisao_e_a_volta(self) -> None:
        """Regra udev sem o porquê é regra que a próxima pessoa apaga.

        Três coisas, e as três foram pedidas: a decisão dela datada, a causa
        (descritor já aberto não fecha com a ACL) e como reverter.
        """
        texto = REGRA.read_text(encoding="utf-8")
        assert "20/09/2026" in texto
        assert "Hefesto tem que ter prioridade em tudo" in texto
        assert "não fecha descritor já aberto" in texto
        assert "--no-fechar-o-no" in texto


# ---------------------------------------------------------------------------
# 2. O BROKER ABRE SOB PEDIDO
# ---------------------------------------------------------------------------


class OpsDeMentira:
    """Dublê de fs que MODELA o estado do nó, em vez de só gravar chamadas.

    Um dublê que sempre responde «exposto» é mais frouxo que o produto e
    esconderia justamente o defeito que esta suíte procura: o `_fs_restore`
    verifica com `is_exposed_to` antes de responder ok, e um `is_exposed_to`
    constante faria um restore que não restaurou passar por restaurado.
    """

    def __init__(self, *, fechados: set[str] | None = None) -> None:
        self.chamadas: list[tuple[Any, ...]] = []
        self.fechados: set[str] = set(fechados or ())

    def hide(self, node: str, base: str) -> None:
        self.chamadas.append(("hide", node, base))
        self.fechados.add(node)

    def restore(self, node: str, base: str, uid: int) -> None:
        self.chamadas.append(("restore", node, base, uid))
        self.fechados.discard(node)

    def is_exposed_to(self, node: str, uid: int) -> bool:
        return node not in self.fechados

    def open_node(self, node: str, base: str) -> int:  # pragma: no cover
        raise AssertionError("open_node não pertence a esta suíte")


def _validador(node: str) -> str | None:
    base = node.rsplit("/", 1)[-1]
    return base if base in {"hidraw3", "hidraw7"} else None


def estado(**kw: Any) -> tuple[BrokerState, OpsDeMentira]:
    ops = kw.pop("ops", OpsDeMentira())
    st = BrokerState(
        allowed_uid=UID,
        ops=ops,
        validator=_validador,
        log=lambda *a, **k: None,
        sleep_fn=lambda _s: None,
        **kw,
    )
    return st, ops


def pedir(st: BrokerState, conn: int, payload: Any, uid: int = UID) -> dict[str, Any]:
    resposta, fd = st.handle_line(conn, uid, json.dumps(payload).encode())
    assert fd is None
    return dict(resposta)


class TestOBrokerAbreSobPedido:
    def test_expose_poe_a_acl_num_no_fechado(self) -> None:
        """O `cmd expose` é a porta — e ela abre um nó que nasceu fechado."""
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        resposta = pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True
        assert resposta["state"] == "exposed"
        assert ("restore", "/dev/hidraw3", "hidraw3", UID) in ops.chamadas
        assert "/dev/hidraw3" not in ops.fechados

    def test_unexpose_fecha_de_volta(self) -> None:
        """A MORDIDA da lease: sem o `unexpose` fechar, sair do Modo Nativo
        deixaria o nó aberto e a Steam voltaria a pegá-lo no próximo replug.
        """
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        resposta = pedir(st, 1, {"cmd": "unexpose", "node": "/dev/hidraw3"})
        assert resposta["ok"] is True
        assert resposta["state"] == "fechado"
        assert "/dev/hidraw3" in ops.fechados

    def test_duas_leases_e_o_refcount(self) -> None:
        """Dois pedidos, um `unexpose`: o nó SEGUE aberto.

        É a mesma aritmética do `hide`, e pela mesma razão: quem soltou não é
        dono do nó, é dono do PEDIDO dele.
        """
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        pedir(st, 2, {"cmd": "expose", "node": "/dev/hidraw3"})
        assert pedir(st, 1, {"cmd": "unexpose", "node": "/dev/hidraw3"})["state"] == "exposed"
        assert "/dev/hidraw3" not in ops.fechados
        assert pedir(st, 2, {"cmd": "unexpose", "node": "/dev/hidraw3"})["state"] == "fechado"
        assert "/dev/hidraw3" in ops.fechados

    def test_eof_da_lease_fecha_o_que_ela_expos(self) -> None:
        """O daemon morreu no Modo Nativo: o físico não pode ficar aberto.

        Sem isto, um crash no meio da partida deixaria o nó exposto até o
        próximo boot — e a Steam o pegaria na reconexão seguinte.
        """
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        assert "/dev/hidraw3" not in ops.fechados
        st.on_conn_closed(1)
        assert "/dev/hidraw3" in ops.fechados
        assert st.expostos == {}

    def test_expose_recusa_o_que_nao_e_dualsense_fisico(self) -> None:
        """Abrir sob pedido não pode virar «abra qualquer hidraw».

        O `expose` é uma primitiva de ROOT que solta permissão: sem o
        validador, um cliente do mesmo uid pediria a ACL de um teclado BT.
        """
        st, _ = estado(no_nasce_fechado=True)
        resposta = pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw9"})
        assert resposta["ok"] is False
        assert resposta["error"] == "reject_not_physical_dualsense"

    def test_o_hide_cede_a_lease_de_exposicao(self) -> None:
        """«O Hefesto tem que ter prioridade em tudo» — e a ordem interna também.

        Um pedido EXPLÍCITO de exposição (o Modo Nativo) vence um hide
        implícito que chegue fora de ordem. A lease do hide fica registrada,
        para que o último `unexpose` encontre o nó e o feche.
        """
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        resposta = pedir(st, 2, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert resposta["state"] == "exposed"
        assert "/dev/hidraw3" not in ops.fechados
        pedir(st, 1, {"cmd": "unexpose", "node": "/dev/hidraw3"})
        assert "/dev/hidraw3" in ops.fechados

    def test_status_conta_o_que_esta_aberto_e_a_regra_vigente(self) -> None:
        """Um status honesto diz as DUAS coisas — quem está aberto e por quê."""
        st, _ = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        resposta = pedir(st, 1, {"cmd": "status"})
        assert resposta["expostos"] == ["/dev/hidraw3"]
        assert resposta["no_nasce_fechado"] is True


# ---------------------------------------------------------------------------
# 3. O REPOUSO — o restore deixa de ABRIR o que a regra fechou
# ---------------------------------------------------------------------------


class TestORepousoSegueARegra:
    def test_restore_de_no_nao_rastreado_fecha_com_a_cura(self) -> None:
        """A MORDIDA mais fina da leva, e ela pega a cura pela metade.

        O `restore` do ungrab (`gamepad.py::_broker_sync_grab`) chega aqui
        pelo ramo «não rastreado». Com o nó nascendo fechado, ABRIR aqui
        recriaria exatamente a janela que a Steam usa — e o faria por
        ACIDENTE, não por desenho. Troque `_repouso` de volta por
        `_fs_restore` no produto e este teste reprova.
        """
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        resposta = pedir(st, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["state"] == "fechado"
        assert "/dev/hidraw3" in ops.fechados

    def test_sem_a_cura_o_restore_continua_abrindo(self) -> None:
        """A máquina SEM a regra instalada não pode mudar de comportamento.

        É o outro lado da mordida: a cura não pode vazar para quem não a
        instalou (`--no-fechar-o-no`, ou um install antigo). Ali o repouso
        do nó é ABERTO, e o `restore` de sempre é o certo.
        """
        st, ops = estado(no_nasce_fechado=False, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        resposta = pedir(st, 1, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["state"] == "exposed"
        assert "/dev/hidraw3" not in ops.fechados

    def test_restore_com_lease_de_exposicao_viva_mantem_aberto(self) -> None:
        """Um `restore` de ungrab no meio do Modo Nativo não pode fechar."""
        st, ops = estado(no_nasce_fechado=True, ops=OpsDeMentira(fechados={"/dev/hidraw3"}))
        pedir(st, 1, {"cmd": "expose", "node": "/dev/hidraw3"})
        resposta = pedir(st, 2, {"cmd": "restore", "node": "/dev/hidraw3"})
        assert resposta["state"] == "exposed"
        assert "/dev/hidraw3" not in ops.fechados

    def test_o_desligamento_do_broker_abre_mesmo_com_a_cura(self) -> None:
        """O piso de recuperação, e é a única exceção ao repouso.

        Broker fora do ar é broker que deixou de ser a porta: um nó `0600`
        sem porta só volta com sudo, e isto é um app de acessibilidade. O
        `ExecStartPre` re-fecha no próximo start.
        """
        st, ops = estado(no_nasce_fechado=True)
        pedir(st, 1, {"cmd": "hide", "node": "/dev/hidraw3"})
        assert "/dev/hidraw3" in ops.fechados
        st.restore_everything()
        assert "/dev/hidraw3" not in ops.fechados

    def test_fechar_todo_fisico_e_o_espelho_do_restore_all(self) -> None:
        """O baseline do start com a cura: fecha o que a udev não alcançou.

        O controle que JÁ estava conectado quando a cura foi instalada não
        passou pela regra nova. Sem esta varredura ele ficaria aberto até o
        replug — e o `--restore-all-and-exit` que morava no ExecStartPre
        ABRIRIA os outros junto, desfazendo a cura a cada restart.
        """
        ops = OpsDeMentira()
        fechados = fechar_todo_fisico(
            uid=UID,
            ops=ops,
            dev_root="/dev",
            sys_class_hidraw=str(RAIZ),  # listdir de uma pasta qualquer
            validator=lambda no: "hidraw3" if no.endswith("assets") else None,
            log=lambda *a, **k: None,
        )
        assert fechados == ["/dev/assets"]
        assert ("hide", "/dev/assets", "assets") in ops.chamadas


# ---------------------------------------------------------------------------
# 4. QUEM SÓ SABE `open(path)` — o hidapi e o Modo Nativo
# ---------------------------------------------------------------------------


class TestQuemAbrePorCaminhoPede:
    def test_open_one_abre_dentro_da_exposicao(self) -> None:
        """O ÚNICO bloqueador real da cura, e ele é nosso.

        `hidapi.Device(path=…)` não aceita fd, e reabrir por `/proc/self/fd/N`
        refaz a checagem de permissão no inode. Com o nó `0600 root` o handle
        de controle do daemon — barra, rumble, gatilhos, mic, bateria — volta
        `EACCES` para TODOS os controles. A ORDEM é o que o teste crava:
        expor, abrir, desexpor. Arranque o `with` do `_open_one` e a ordem
        vira só «abrir», o que reprova aqui.
        """
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

        ordem: list[str] = []

        class Exposicao:
            def __init__(self, no: str) -> None:
                self._no = no

            def __enter__(self) -> bool:
                ordem.append(f"expor:{self._no}")
                return True

            def __exit__(self, *_exc: object) -> None:
                ordem.append(f"desexpor:{self._no}")

        ctl = PyDualSenseController.__new__(PyDualSenseController)
        ctl._exposicao_do_no = Exposicao  # type: ignore[assignment]
        ctl._abrir_handle_pinado = (  # type: ignore[method-assign]
            lambda path, *, is_edge: ordem.append("abrir") or "handle"
        )
        assert ctl._open_one(b"/dev/hidraw3", is_edge=False) == "handle"
        assert ordem == ["expor:/dev/hidraw3", "abrir", "desexpor:/dev/hidraw3"]

    def test_open_one_sem_fabrica_abre_como_sempre(self) -> None:
        """Sem broker (CLI, dublê, máquina sem a cura) nada muda."""
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

        ctl = PyDualSenseController.__new__(PyDualSenseController)
        ctl._abrir_handle_pinado = (  # type: ignore[method-assign]
            lambda path, *, is_edge: "handle"
        )
        assert ctl._exposicao_do_no is None
        assert ctl._open_one(b"/dev/hidraw3", is_edge=False) == "handle"

    def test_open_one_desexpoe_mesmo_com_erro(self) -> None:
        """Exposição que vaza é a janela que a Steam usa — e ela vazaria no
        caminho de erro, que é onde ninguém olha.
        """
        from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

        ordem: list[str] = []

        class Exposicao:
            def __init__(self, no: str) -> None:
                self._no = no

            def __enter__(self) -> bool:
                ordem.append("expor")
                return True

            def __exit__(self, *_exc: object) -> None:
                ordem.append("desexpor")

        def explode(path: bytes, *, is_edge: bool) -> Any:
            raise OSError("USB transitório")

        ctl = PyDualSenseController.__new__(PyDualSenseController)
        ctl._exposicao_do_no = Exposicao  # type: ignore[assignment]
        ctl._abrir_handle_pinado = explode  # type: ignore[method-assign]
        with pytest.raises(OSError):
            ctl._open_one(b"/dev/hidraw3", is_edge=False)
        assert ordem == ["expor", "desexpor"]

    def test_o_contexto_do_cliente_nunca_desexpoe_o_que_nao_expos(self) -> None:
        """Desexpor o que não se expôs decrementaria a lease de OUTRO pedido."""
        from hefesto_dualsense4unix.integrations.hidraw_broker_client import (
            HidrawBrokerClient,
        )

        cliente = HidrawBrokerClient(socket_path="/dev/null/nao-existe")
        chamadas: list[str] = []
        cliente.expor = lambda no: chamadas.append("expor") or False  # type: ignore[method-assign]
        cliente.desexpor = lambda no: chamadas.append("desexpor") or True  # type: ignore[method-assign]
        with cliente.exposicao("/dev/hidraw3") as aberto:
            assert aberto is False
        assert chamadas == ["expor"]


class TestOModoNativoPede:
    def test_ligar_e_desligar_pedem_expose_e_unexpose(self) -> None:
        """Até 20/09 a exposição no nativo vinha DE CARONA, pelo ungrab.

        Funcionava por acidente. Com o nó nascendo fechado aquele ramo passa a
        FECHAR — e é este pedido explícito que o substitui. Sem ele, o jogo
        no Modo Nativo encontra a porta trancada, que é o «zero controles»
        que esta casa já relatou ao vivo.
        """
        from hefesto_dualsense4unix.daemon import lifecycle as mod

        atos: list[tuple[str, str]] = []

        class ClienteDeMentira:
            def expor(self, no: str) -> bool:
                atos.append(("expor", no))
                return True

            def desexpor(self, no: str) -> bool:
                atos.append(("desexpor", no))
                return True

        class ControllerDeMentira:
            def nos_hidraw_por_uniq(self) -> dict[str, str]:
                return {"aabbcc000001": "/dev/hidraw3", "aabbcc000002": "/dev/hidraw7"}

        daemon = mod.Daemon.__new__(mod.Daemon)
        daemon.controller = ControllerDeMentira()  # type: ignore[assignment]

        import hefesto_dualsense4unix.integrations.hidraw_broker_client as cli

        antigo_cliente = cli.broker_client_for
        antigo_call = cli.broker_call_nonblocking
        cli.broker_client_for = lambda _d: ClienteDeMentira()  # type: ignore[assignment]
        cli.broker_call_nonblocking = lambda _d, chamada: chamada()  # type: ignore[assignment]
        try:
            daemon._exposicao_do_modo_nativo(True)
            daemon._exposicao_do_modo_nativo(False)
        finally:
            cli.broker_client_for = antigo_cliente  # type: ignore[assignment]
            cli.broker_call_nonblocking = antigo_call  # type: ignore[assignment]

        assert atos == [
            ("expor", "/dev/hidraw3"),
            ("expor", "/dev/hidraw7"),
            ("desexpor", "/dev/hidraw3"),
            ("desexpor", "/dev/hidraw7"),
        ]


# ---------------------------------------------------------------------------
# 5. NO INSTALL, POR DEFAULT — ordem dela, literal
# ---------------------------------------------------------------------------


class TestNoInstallPorDefault:
    def test_a_unit_declara_o_env_da_cura(self) -> None:
        """As duas metades têm de concordar: a udev decide o NASCIMENTO do nó,
        e o broker precisa saber qual é o REPOUSO para onde devolve o nó.
        """
        texto = UNIT.read_text(encoding="utf-8")
        assert f"Environment={NO_NASCE_FECHADO_ENV}=__NO_NASCE_FECHADO__" in texto

    def test_o_start_fecha_e_o_stop_abre(self) -> None:
        """Os dois lados são ASSIMÉTRICOS de propósito — ver a nota datada em
        `test_hidraw_broker_assets.py`.
        """
        texto = UNIT.read_text(encoding="utf-8")
        assert re.search(r"^ExecStartPre=.*--fechar-tudo-e-sair$", texto, re.MULTILINE)
        assert re.search(r"^ExecStopPost=.*--restore-all-and-exit$", texto, re.MULTILINE)

    def test_o_install_nasce_com_a_cura_ligada(self) -> None:
        """A MORDIDA da ordem dela: «no install por default».

        Troque o `ABRIR_O_NO=0` por `=1` e isto reprova. Um default invertido
        faria toda máquina nova nascer com a janela aberta, em silêncio — que
        é exatamente o estado que a decisão de 20/09 veio encerrar.
        """
        texto = INSTALL.read_text(encoding="utf-8")
        assert re.search(r"^ABRIR_O_NO=0$", texto, re.MULTILINE)
        assert re.search(r"^\s*--no-fechar-o-no\)\s+ABRIR_O_NO=1 ;;$", texto, re.MULTILINE)

    def test_o_render_do_broker_default_e_fechado(self) -> None:
        """Sem o default 1 aqui, a metade de cima da cura (a udev) ficaria sem
        a de baixo (o broker): nó fechado que ninguém abre.
        """
        texto = CAMADA.read_text(encoding="utf-8")
        assert 'local fechado="${6:-1}"' in texto
        assert "__NO_NASCE_FECHADO__" in texto

    def test_o_opt_out_viaja_para_as_duas_metades(self) -> None:
        """Uma flag que mudasse só o broker deixaria as metades em desacordo."""
        assert "--no-fechar-o-no" in INSTALL_UDEV.read_text(encoding="utf-8")
        assert "_udev_args+=(--no-fechar-o-no)" in CAMADA.read_text(encoding="utf-8")

    def test_set_native_mode_chama_as_duas_pontas_na_ordem_certa(self) -> None:
        """A régua do CALL SITE, e a ordem é parte da cura.

        Ligar: o pedido de exposição vai ANTES do release, porque o release
        desce até o `restore` do ungrab — e com o nó nascendo fechado esse
        caminho FECHA. Pedir depois seria abrir, fechar, e deixar o jogo
        achar a porta trancada.

        Desligar: solta DEPOIS de o grab voltar, para não abrir uma fresta
        entre o nó fechar e o daemon reassumir.

        Roda o método REAL do `lifecycle.Daemon`; só a borda é dublê.
        """
        from types import SimpleNamespace

        from hefesto_dualsense4unix.daemon import lifecycle as mod

        ordem: list[str] = []
        daemon = mod.Daemon.__new__(mod.Daemon)
        daemon._native_mode = False
        daemon._mode_from_profile = None
        daemon._native_emu_stash = {}
        daemon._emu_manual_ts = 0.0
        daemon.config = SimpleNamespace(rumble_active=None, rumble_active_uniq=None)
        daemon.controller = SimpleNamespace()
        daemon.store = SimpleNamespace(
            set_native_mode_active=lambda *a, **k: None,
            active_profile=None,
        )
        daemon._mascara_viva = lambda: None  # type: ignore[method-assign]
        daemon._exposicao_do_modo_nativo = (  # type: ignore[method-assign]
            lambda ligar: ordem.append("expor" if ligar else "desexpor")
        )
        daemon._release_controller_to_game = (  # type: ignore[method-assign]
            lambda: ordem.append("release")
        )
        daemon._zero_rumble_motors = lambda: ordem.append("zera")  # type: ignore[method-assign]
        daemon._reapply_last_profile = (  # type: ignore[method-assign]
            lambda: ordem.append("perfil")
        )
        daemon._restore_emulation_from_stash = (  # type: ignore[method-assign]
            lambda: ordem.append("stash")
        )
        daemon.set_mouse_emulation = lambda *a, **k: None  # type: ignore[method-assign]
        daemon.set_gamepad_emulation = lambda *a, **k: None  # type: ignore[method-assign]

        daemon.set_native_mode(True, origin="manual")
        daemon.set_native_mode(False, origin="manual")

        assert ordem.index("expor") < ordem.index("release")
        assert ordem.index("desexpor") > ordem.index("stash")
        assert ordem.count("expor") == 1
        assert ordem.count("desexpor") == 1
