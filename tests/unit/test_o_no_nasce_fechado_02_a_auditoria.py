"""O-NO-NASCE-FECHADO-01 — os quatro achados da AUDITORIA de 20/09/2026.

A construção da cura existia e estava boa; ela só não sobrevivia ao mundo
real. O auditor reprovou com quatro achados, três deles bloqueantes, e este
arquivo é a régua de cada um.

  1. **Não sobrevivia a REINICIAR o daemon.** O boot lê o Modo Nativo do disco
     (`load_native_mode`) e escreve direto em `_native_mode` + `store`;
     `set_native_mode()` NÃO é chamado, logo `_exposicao_do_modo_nativo(True)`
     nunca rodava. E religar pela tela não consertava: `set_native_mode` tem
     early-return de idempotência. Rebootar em Modo Nativo deixava o nó
     `0600 root` e o jogo levava `EACCES`.
  2. **Não sobrevivia a um REPLUG.** A lease apontava para um `/dev/hidrawN`
     CONCRETO, e não há notificação udev→broker. Número novo ⇒ lease pendurada
     num nó morto; número igual ⇒ a contabilidade do broker segue dizendo
     «exposto» sobre um nó que o udev acabou de refazer fechado.
  3. **Os pacotes de distro fechavam o nó e NÃO instalavam a porta.** O asset
     (fechado) ia para `/usr/lib/udev/rules.d/` do `.deb`/`.rpm`/Arch/Nix e o
     broker era instalado FORA do pacote. Num `apt install`, o DualSense
     nascia `0600` sem ninguém que o abrisse — **inutilizável**. Bate de
     frente com a ordem dela de 11/09: *o produto é para qualquer usuário*.
  4. **MENOR:** `capture_dualsense_blueprint` abria por `os.open(path)`.

Régua de UNIDADE, como a irmã `test_o_no_nasce_fechado.py`: nada aqui toca
/dev, /sys, o udev vivo, o broker vivo nem o daemon. Os quatro DualSense dela
estão em uso agora.
"""
from __future__ import annotations

import ast
import os
import subprocess
from pathlib import Path
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
LIFECYCLE = RAIZ / "src" / "hefesto_dualsense4unix" / "daemon" / "lifecycle.py"
REGRA = RAIZ / "assets" / "73-hefesto-ps5-controller.rules"
REGRA_ABERTA_SH = RAIZ / "scripts" / "regra_do_no_aberta.sh"
BUILD_DEB = RAIZ / "scripts" / "build_deb.sh"
INSTALL_HOST = RAIZ / "scripts" / "install-host-udev.sh"
PKGBUILD = RAIZ / "packaging" / "arch" / "PKGBUILD"
SPEC = RAIZ / "packaging" / "fedora" / "hefesto-dualsense4unix.spec"
NIX = RAIZ / "packaging" / "nix" / "package.nix"


class ControllerDeMentira:
    """Só o `nos_hidraw_por_uniq`, que é a única coisa que o laço pergunta."""

    def __init__(self, nos: dict[str, str]) -> None:
        self.nos = dict(nos)

    def nos_hidraw_por_uniq(self) -> dict[str, str]:
        return dict(self.nos)


class ClienteDeMentira:
    def __init__(self, atos: list[tuple[str, str]]) -> None:
        self.atos = atos

    def expor(self, no: str, *, entradas: bool = False) -> bool:
        self.atos.append(("expor", no))
        return True

    def desexpor(self, no: str) -> bool:
        self.atos.append(("desexpor", no))
        return True


@pytest.fixture()
def bancada(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Um `Daemon` cru, o cliente do broker desviado, e a lista de atos."""
    from hefesto_dualsense4unix.daemon import lifecycle as mod
    import hefesto_dualsense4unix.integrations.hidraw_broker_client as cli

    atos: list[tuple[str, str]] = []
    monkeypatch.setattr(cli, "broker_client_for", lambda _d: ClienteDeMentira(atos))
    monkeypatch.setattr(
        cli, "broker_call_nonblocking", lambda _d, chamada: chamada()
    )
    daemon = mod.Daemon.__new__(mod.Daemon)
    monkeypatch.setattr(mod.Daemon, "_no_de_fisico_esta_aberto", staticmethod(lambda _n: True))
    return daemon, atos, mod


class TestSobreviveAReiniciar:
    def test_o_modo_lido_do_disco_expoe_sem_ninguem_chamar_set_native_mode(
        self, bancada: Any
    ) -> None:
        """A MORDIDA do bloqueante 1, e ela reproduz o boot LITERALMENTE."""
        daemon, atos, _mod = bancada
        daemon.controller = ControllerDeMentira(
            {"aabbcc000001": "/dev/hidraw3", "aabbcc000002": "/dev/hidraw7"}
        )
        daemon._native_mode = True

        daemon._reconciliar_exposicao_do_modo_nativo()

        assert atos == [("expor", "/dev/hidraw3"), ("expor", "/dev/hidraw7")]

    def test_fora_do_modo_nativo_o_tique_nao_pede_nada(self, bancada: Any) -> None:
        """O laço roda a cada 2 s a vida inteira: fora do modo, custa nada."""
        daemon, atos, _mod = bancada
        daemon.controller = ControllerDeMentira({"aabbcc000001": "/dev/hidraw3"})
        daemon._native_mode = False

        daemon._reconciliar_exposicao_do_modo_nativo()

        assert atos == []

    def test_o_poll_loop_reconcilia_a_exposicao_do_modo_nativo(self) -> None:
        """Arranque a chamada do laço e este teste reprova."""
        arvore = ast.parse(LIFECYCLE.read_text(encoding="utf-8"), filename=str(LIFECYCLE))
        laco = next(
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.AsyncFunctionDef) and no.name == "_poll_loop"
        )
        chamadas = {
            no.func.attr
            for no in ast.walk(laco)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Attribute)
        }
        assert "_reconciliar_exposicao_do_modo_nativo" in chamadas


class TestSobreviveAReplug:
    def test_o_no_que_saiu_e_solto_e_o_que_entrou_e_exposto(
        self, bancada: Any
    ) -> None:
        """Replug com NÚMERO NOVO: a lease velha ficava pendurada num nó morto."""
        daemon, atos, _mod = bancada
        daemon.controller = ControllerDeMentira({"aabbcc000001": "/dev/hidraw3"})
        daemon._native_mode = True
        daemon._reconciliar_exposicao_do_modo_nativo()
        atos.clear()

        daemon.controller.nos = {"aabbcc000001": "/dev/hidraw9"}
        daemon._reconciliar_exposicao_do_modo_nativo()

        assert atos == [("desexpor", "/dev/hidraw3"), ("expor", "/dev/hidraw9")]

    def test_o_no_que_renasceu_fechado_com_o_mesmo_numero_e_reafirmado(
        self, bancada: Any, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A METADE QUE QUASE ESCAPOU, e é a que nenhuma contabilidade pega."""
        daemon, atos, mod = bancada
        daemon.controller = ControllerDeMentira({"aabbcc000001": "/dev/hidraw3"})
        daemon._native_mode = True
        daemon._reconciliar_exposicao_do_modo_nativo()
        atos.clear()

        monkeypatch.setattr(
            mod.Daemon, "_no_de_fisico_esta_aberto", staticmethod(lambda _n: False)
        )
        daemon._reconciliar_exposicao_do_modo_nativo()

        assert atos == [("expor", "/dev/hidraw3")]

    def test_o_no_que_continua_aberto_nao_vira_pedido(self, bancada: Any) -> None:
        """O irmão que mede o contrário — sem ele a régua acima daria verde sempre."""
        daemon, atos, _mod = bancada
        daemon.controller = ControllerDeMentira({"aabbcc000001": "/dev/hidraw3"})
        daemon._native_mode = True
        daemon._reconciliar_exposicao_do_modo_nativo()
        atos.clear()

        daemon._reconciliar_exposicao_do_modo_nativo()

        assert atos == []

    def test_o_controle_que_sai_da_mesa_solta_a_lease(self, bancada: Any) -> None:
        """Com zero controles o alvo é vazio, e a lease não pode sobrar."""
        daemon, atos, _mod = bancada
        daemon.controller = ControllerDeMentira({"aabbcc000001": "/dev/hidraw3"})
        daemon._native_mode = True
        daemon._reconciliar_exposicao_do_modo_nativo()
        atos.clear()

        daemon.controller.nos = {}
        daemon._reconciliar_exposicao_do_modo_nativo()

        assert atos == [("desexpor", "/dev/hidraw3")]

    def test_o_with_transitorio_nao_fecha_o_no_do_modo_nativo(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A lease do broker é por CONEXÃO — e as duas saem do mesmo cliente."""
        from hefesto_dualsense4unix.integrations import hidraw_broker_client as cli

        atos: list[tuple[str, str]] = []

        class DaemonDeMentira:
            def no_exposto_pelo_modo_nativo(self, path: str) -> bool:
                return path == "/dev/hidraw3"

        cliente = cli.HidrawBrokerClient(socket_path="/dev/null/nao-existe")
        cliente.expor = lambda no: atos.append(("expor", no)) or True  # type: ignore[method-assign]
        cliente.desexpor = lambda no: atos.append(("desexpor", no)) or True  # type: ignore[method-assign]
        monkeypatch.setattr(cli, "broker_client_for", lambda _d: cliente)
        fabrica = cli.make_exposicao_factory(DaemonDeMentira())

        with fabrica("/dev/hidraw3") as aberto:
            assert aberto is True
        assert atos == []

        with fabrica("/dev/hidraw9"):
            pass
        assert atos == [("expor", "/dev/hidraw9"), ("desexpor", "/dev/hidraw9")]


def _linhas_efetivas(texto: str) -> list[str]:
    return [
        linha.strip()
        for linha in texto.splitlines()
        if linha.strip() and not linha.strip().startswith("#")
    ]


class TestOsPacotesNaoFechamSemPorta:
    def test_a_transformacao_tem_dono_e_reabre_as_duas_linhas_do_0ce6(
        self, tmp_path: Path
    ) -> None:
        """O `regra_do_no_aberta.sh` roda de verdade, sobre o asset de verdade."""
        destino = tmp_path / "73-hefesto-ps5-controller.rules"
        proc = subprocess.run(
            ["bash", str(REGRA_ABERTA_SH), str(REGRA), str(destino)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0, proc.stderr
        linhas = _linhas_efetivas(destino.read_text(encoding="utf-8"))
        assert not any('TAG-="uaccess"' in linha for linha in linhas)
        abertas = [
            linha
            for linha in linhas
            if "0ce6" in linha.lower() and 'TAG+="uaccess"' in linha
        ]
        assert len(abertas) == 2, abertas
        assert all('MODE="0660"' in linha for linha in abertas)
        edge = [
            linha
            for linha in linhas
            if "0df2" in linha.lower() and "DEVPATH" not in linha
        ]
        assert len(edge) == 2, edge
        assert all('TAG+="uaccess"' in linha for linha in edge)

    def test_o_asset_versionado_continua_fechado(self) -> None:
        """A decisão dela não mudou: o default é o nó nascer fechado."""
        linhas = _linhas_efetivas(REGRA.read_text(encoding="utf-8"))
        fechadas = [linha for linha in linhas if 'TAG-="uaccess"' in linha]
        assert len(fechadas) == 4, fechadas
        assert all('MODE:="0600"' in linha for linha in fechadas)

    def test_a_transformacao_recusa_um_asset_que_ela_nao_alcanca(
        self, tmp_path: Path
    ) -> None:
        """Guarda 2: `sed` que casa ZERO vezes passaria calado pela guarda 1."""
        origem = tmp_path / "renomeada.rules"
        origem.write_text(
            'KERNEL=="hidraw*", SUBSYSTEM=="hidraw", ATTRS{idProduct}=="0aaa", MODE="0600"\n',
            encoding="utf-8",
        )
        destino = tmp_path / "saida.rules"
        proc = subprocess.run(
            ["bash", str(REGRA_ABERTA_SH), str(origem), str(destino)],
            capture_output=True,
            text=True,
        )
        assert proc.returncode != 0
        assert not destino.exists(), "recusou e mesmo assim escreveu o destino"

    @pytest.mark.parametrize(
        ("receita", "diretorio_vivo"),
        [
            (PKGBUILD, "/usr/lib/udev/rules.d/"),
            (SPEC, "%{_udevrulesdir}"),
            (NIX, "$out/lib/udev/rules.d/"),
            (BUILD_DEB, "/usr/lib/udev/rules.d/"),
        ],
        ids=["arch", "fedora", "nix", "deb"],
    )
    def test_o_diretorio_vivo_do_pacote_recebe_a_variante_aberta(
        self, receita: Path, diretorio_vivo: str
    ) -> None:
        """A MORDIDA do bloqueante 3.

        Apague a chamada ao `regra_do_no_aberta.sh` de qualquer uma das quatro
        receitas e ela volta a gravar o asset FECHADO no diretório que o udev
        LÊ — sem instalar o broker, que mora fora do manifesto do pacote. O
        DualSense nasce `0600 root` e ninguém o abre.
        """
        texto = receita.read_text(encoding="utf-8")
        assert diretorio_vivo in texto, "a receita mudou de destino"
        assert "regra_do_no_aberta.sh" in texto, (
            f"{receita.name} grava a regra do nó no diretório vivo sem passar pela "
            "variante aberta — e o pacote não instala o broker"
        )

    def test_o_helper_so_fecha_o_no_quando_instala_o_broker(self) -> None:
        """As duas metades viajam juntas, ou nenhuma viaja."""
        texto = INSTALL_HOST.read_text(encoding="utf-8")
        assert "REGRA_DO_NO_SRC" in texto
        assert 'if [[ "${BROKER_INSTALL_OK}" -ne 1 ]]; then' in texto
        assert "regra_do_no_aberta.sh" in texto

    def test_o_deb_bundla_o_gerador_da_variante_aberta(self) -> None:
        """Sem ele no pacote, o helper cai no fail-safe e não instala a regra do nó."""
        texto = BUILD_DEB.read_text(encoding="utf-8")
        assert (
            "/usr/share/hefesto-dualsense4unix/scripts/regra_do_no_aberta.sh" in texto
        )


class TestOCapturadorEntraPelaPorta:
    def test_capture_dualsense_blueprint_nao_abre_por_os_open(self) -> None:
        """Com o nó nascendo fechado, `os.open(path)` colhe EACCES e devolve None."""
        fonte = (
            RAIZ / "src" / "hefesto_dualsense4unix" / "integrations" / "uhid_gamepad.py"
        ).read_text(encoding="utf-8")
        arvore = ast.parse(fonte)
        funcao = next(
            no
            for no in ast.walk(arvore)
            if isinstance(no, ast.FunctionDef)
            and no.name == "capture_dualsense_blueprint"
        )
        chamadas = {
            f"{no.func.value.id}.{no.func.attr}"
            for no in ast.walk(funcao)
            if isinstance(no, ast.Call)
            and isinstance(no.func, ast.Attribute)
            and isinstance(no.func.value, ast.Name)
        }
        nomes = {
            no.func.id
            for no in ast.walk(funcao)
            if isinstance(no, ast.Call) and isinstance(no.func, ast.Name)
        }
        assert "os.open" not in chamadas
        assert "abrir_hidraw" in nomes

    def test_ela_usa_o_fd_que_a_porta_devolveu(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Prova de COMPORTAMENTO, não de texto: o fd vem do `NoAberto`."""
        from hefesto_dualsense4unix.integrations import hidraw_broker_client as cli
        from hefesto_dualsense4unix.integrations import uhid_gamepad as ug

        # sysfs de mentira: descriptor válido e identidade de DualSense.
        classe = tmp_path / "sys" / "class" / "hidraw" / "hidraw3" / "device"
        classe.mkdir(parents=True)
        (classe / "report_descriptor").write_bytes(b"\x05\x01\x09\x05")
        monkeypatch.setattr(ug, "_is_dualsense", lambda _n: True)
        monkeypatch.setattr(
            ug,
            "open",
            lambda caminho, modo="r": (classe / "report_descriptor").open(modo),
            raising=False,
        )

        marcador = os.open(os.devnull, os.O_RDONLY)
        vistos: list[int] = []
        monkeypatch.setattr(
            cli,
            "abrir_hidraw",
            lambda no, escrita=True: cli.NoAberto(
                fd=marcador, no=no, porta=cli.PORTA_BROKER, motivo="dublê", socket="-"
            ),
        )
        monkeypatch.setattr(
            ug,
            "_hidiocgfeature",
            lambda fd, rid, size: vistos.append(fd) or (b"\x09" + b"\xaa" * 19),
        )

        saida = ug.capture_dualsense_blueprint("/dev/hidraw3")

        assert saida is not None
        assert vistos and set(vistos) == {marcador}
