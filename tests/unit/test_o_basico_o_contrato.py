"""O-BASICO-MEDIDO-01 — o contrato do protocolo do básico, em nove réguas.

O ``scripts/o_basico.py`` é a conferência do APARELHO que qualquer pessoa com
um COSMIC, rádio, cabo e DualSense roda. Estas réguas o dirigem por uma
máquina de mentira (uma subclasse da ``Maquina`` dele, que troca o mundo
inteiro: o ``state_full``, o diário, o ``/proc/bus/input/devices``, os
ensaios), e nenhuma toca o daemon, o ``/sys``, o ``/dev`` ou o ``~/.config``
de verdade. Os endereços são da faixa forjada ``02:00:1a`` (o bit localmente
administrado, que fabricante nenhum recebe).

AS NOVE, e a mordida de cada uma (arrancada à mão, vista reprovar, devolvida):

1. sete pads no boot para quatro jogadores: a linha 1b sai vermelha. Mordida:
   contar os pads de AGORA em vez dos do boot;
2. o perfil pede DualSense, o pad é ``uinput`` e o diário diz
   ``vpad_recriacao_bloqueada_por_jogo``: o ``eixos`` sai vermelho. Mordida:
   tratar o motivo como absolvição;
3. um ``sha256`` diferente no fim: ``rc=2``. Mordida: tirar a conferência da
   volta;
4. a mesa relistada sem um controle: ``rc=2``, dizendo quem saiu. Mordida:
   tirar a relistagem;
5. ``lightbar_source="desired"``: «não sei», nunca verde. Mordida: aceitar o
   ``desired`` como leitura;
6. a saída de um ensaio com as seis formas de endereço: nenhuma janela de três
   octetos com o 4º ou o 5º sobra. Mordida: tirar a sexta forma do dono;
7. nenhum caminho que ele mesmo abre fica sob a pasta de estudos. Mordida:
   apontar uma sonda para lá;
8. todo arquivo que ele chama está em cada empacotamento. Mordida: tirar um
   ensaio do PKGBUILD;
9. o resumo da sonda ``nucleo-por-processo.bt`` separa a escrita da árvore do
   jogo da do cliente Steam de mesmo nome de fio. Mordida: tirar o ``pid`` da
   chave do ``@hw`` na sonda.

As réguas 3, 4 e 6 trazem a mordida também dentro do arquivo, porque ela se
faz sem editar código: um ``monkeypatch`` arranca a cura, e a régua mostra
que depende dela.
"""

from __future__ import annotations

import ast
import copy
import importlib.util
import json
import re
import sys
from collections.abc import Callable, Iterator, Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts"

#: O nome do subcomando que lê a sessão do daemon, como o protocolo o escreve.
SUB_DA_SESSAO = "sessao"  # (noqa-acento: o nome do subcomando é o do protocolo)

#: A mesa de mentira: dois no cabo, dois no rádio. Faixa forjada, 4º e 5º
#: octetos diferentes de zero de propósito (é o que a máscara tem de comer).
UNIQS = tuple(f"02:00:1a:4b:5c:0{n}" for n in range(1, 5))

#: O endereço que NINGUÉM conhece (nem o estado, nem os arquivos): só a
#: camada da forma o pega. Octetos soltos, para a régua gerar as formas.
DESCONHECIDO = ("02", "00", "1a", "6d", "7e", "9f")

APPID_DO_JOGO = 3050


# ---------------------------------------------------------------------------
# O protocolo, carregado do arquivo (ele mora em scripts/, fora do pacote)
# ---------------------------------------------------------------------------


def _carregar(nome: str, caminho: Path) -> ModuleType:
    if str(caminho.parent) not in sys.path:
        sys.path.insert(0, str(caminho.parent))
    spec = importlib.util.spec_from_file_location(nome, caminho)
    assert spec is not None and spec.loader is not None
    modulo = importlib.util.module_from_spec(spec)
    sys.modules[nome] = modulo
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture(scope="module")
def ob() -> ModuleType:
    return _carregar("o_basico_da_regua", SCRIPTS / "o_basico.py")


@pytest.fixture(autouse=True)
def _estado_no_berco(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A pasta privada do protocolo (``$XDG_STATE_HOME/.../o-basico``) vai para o tmp."""
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "estado"))


# ---------------------------------------------------------------------------
# A máquina de mentira
# ---------------------------------------------------------------------------


class Sonda:
    """Um processo de sonda já terminado: o ``colher`` devolve o texto dele."""

    def __init__(self, texto: str) -> None:
        self.texto = texto


def fazer_maquina(ob: ModuleType, estado: dict[str, Any], config: Path, **extra: Any) -> Any:
    """Uma ``Maquina`` que responde do que a régua escreveu, e de nada mais."""

    class MaquinaDeMentira(ob.Maquina):  # type: ignore[name-defined]
        def __init__(self) -> None:
            self.estado_de_agora = copy.deepcopy(estado)
            self.config = config
            self.diario: list[str] = list(extra.get("diario", ()))
            self.kernel: list[str] = list(extra.get("kernel", ()))
            self.dispositivos: str = extra.get("dispositivos", "")
            self.ensaios: dict[str, str] = dict(extra.get("ensaios", {}))
            self.processos_de_mentira: dict[int, tuple[int, str]] = dict(extra.get("processos", {}))
            self.jogo: list[int] = list(extra.get("jogo", ()))
            self.ao_rodar: Callable[[Sequence[str], Any], None] | None = extra.get("ao_rodar")
            self.chamados: list[tuple[str, Any]] = []
            self.rodados: list[list[str]] = []
            self.relogio = 1_790_000_000.0

        def chamar(self, metodo: str, params: Any = None) -> Any:
            self.chamados.append((metodo, params))
            if metodo == "daemon.state_full":
                return copy.deepcopy(self.estado_de_agora)
            return {"ok": True}

        def estado(self) -> dict[str, Any] | None:
            return copy.deepcopy(self.estado_de_agora)

        def diario_do_daemon(self) -> list[str]:
            return list(self.diario)

        def diario_do_kernel(self) -> list[str]:
            return list(self.kernel)

        def diario_do_sistema_desde(self, epoca: float) -> list[str]:
            return []

        def kernel_desde(self, epoca: float) -> list[str]:
            return []

        def ler(self, caminho: Any) -> str:
            return ""

        def dispositivos_de_entrada(self) -> str:
            return self.dispositivos

        def processos(self) -> dict[int, tuple[int, str]]:
            return dict(self.processos_de_mentira)

        def pids_do_jogo(self, appid: Any) -> list[int]:
            return list(self.jogo)

        def fds_de(self, pid: int) -> list[str]:
            return []

        def baterias(self) -> dict[str, tuple[str, str]]:
            return {}

        def adaptadores(self) -> list[dict[str, str]]:
            return []

        def secure_boot(self) -> str:
            return "sem EFI"

        def config_dela(self) -> Path:
            return self.config

        def pactl(self, *argv: str) -> str | None:
            return None

        def rodar(
            self, argv: Sequence[str], teto_s: float, ambiente: Any = None
        ) -> tuple[int, str]:
            self.rodados.append(list(argv))
            if self.ao_rodar is not None:
                self.ao_rodar(argv, self)
            nome = Path(argv[1]).name if len(argv) > 1 else ""
            if nome in self.ensaios:
                return 0, self.ensaios[nome]
            return 127, f"{argv[0]}: não existe nesta máquina de mentira"

        def existe(self, programa: str) -> bool:
            return False

        def subir(self, argv: Sequence[str]) -> Any:
            raise AssertionError(f"a régua não sobe processo: {argv}")

        def colher(self, processo: Any, teto_s: float) -> str:
            return str(processo.texto)

        def regra_do_input_remapper(self) -> bool:
            return False

        def leitor_dos_fisicos(self) -> Any:
            raise AssertionError("a régua não abre o hidraw de ninguém")

        def hidraw_do_pad_uhid(self, jogador: int) -> str | None:
            return None

        def escrever_no_pad(self, caminho: str, dados: bytes) -> bool:
            raise AssertionError("a régua não escreve em pad nenhum")

        def pulso_de_ff(self, pad: Any, segundos: float) -> bool:
            raise AssertionError("a régua não manda efeito para pad nenhum")

        def gravar_som(self, fonte: str, segundos: float) -> list[int]:
            return []

        def tocar(self, sink: str, wav: Path) -> Any:
            return None

        def esperar(self, processo: Any, teto_s: float) -> None:
            return None

        def agora(self) -> float:
            return self.relogio

        def dormir(self, segundos: float) -> None:
            self.relogio += max(0.0, segundos)

    return MaquinaDeMentira()


# ---------------------------------------------------------------------------
# A mesa, o diário e o kernel de mentira
# ---------------------------------------------------------------------------


def estado_da_mesa(
    *, caminho: str = "dualsense", backend: str = "uhid", fonte_da_luz: str = "sysfs",
    perfil: str = "Freestyle", jogo: bool = False,
) -> dict[str, Any]:
    controles = []
    for n, uniq in enumerate(UNIQS, start=1):
        controles.append({
            "uniq": uniq,
            "player": n,
            "connected": True,
            "transport": "usb" if n <= 2 else "bt",
            "adaptador": None if n <= 2 else "hci0",
            "vpad_backend": backend,
            "vpad_motivo": None,
            "lightbar_source": fonte_da_luz,
            "lightbar_disputada": False,
            "lightbar_rgb": [0, 0, 255],
            "battery_pct": 80,
            "audio": {"canal_ativo": True, "mic_mudo": False},
            "speaker": {"rota": 2, "volume": 50},
        })
    return {
        "controllers": controles,
        "gamepad_emulation": {
            "enabled": True,
            "caminho": caminho,
            "flavor": caminho,
            "backend": backend,
            "por_aparelho": dict.fromkeys(UNIQS, caminho),
            "canal_sem_imu": backend != "uhid",
        },
        "rumble_ff": {
            "per_vpad": [
                {"player": n, "backend": backend, "evdev": f"/dev/input/event{20 + n}",
                 "ff_nao_nulo_count": 0}
                for n in range(1, 5)
            ]
        },
        "coop": {"mesa": [{"player": n, "uniq": u} for n, u in enumerate(UNIQS, start=1)]},
        "game_signal": {"authority": "game" if jogo else "none"},
        "jogo_steam": {"appid": APPID_DO_JOGO if jogo else None},
        "active_profile": perfil,
        "native_mode": False,
        "output_target_index": 0,
        "rumble_active": False,
    }


def pads_uhid(quantos: int = 4) -> str:
    return "\n".join(
        f"I: Bus=0003 Vendor=054c Product=0df2 Version=8111\n"
        f'N: Name="DualSense Wireless Controller (Hefesto P{n})"\n'
        f"P: Phys=hefesto-vpad\n"
        f"S: Sysfs=/devices/virtual/misc/uhid/0003:054C:0DF2.00{n}0/input/input{50 + n}\n"
        f"U: Uniq=02:fe:00:00:00:0{n}\n"
        f"H: Handlers=event{20 + n} js{n}\n"
        for n in range(1, quantos + 1)
    )


def pads_uinput_xbox(ob: ModuleType, quantos: int = 4) -> str:
    from hefesto_dualsense4unix.integrations.uinput_gamepad import XBOX360_NAME

    return "\n".join(
        f"I: Bus=0003 Vendor=045e Product=028e Version=0110\n"
        f'N: Name="{XBOX360_NAME}"\n'
        f"P: Phys=py-evdev-uinput\n"
        f"S: Sysfs=/devices/virtual/input/input{60 + n}\n"
        f"U: Uniq=\n"
        f"H: Handlers=event{20 + n} js{n}\n"
        for n in range(1, quantos + 1)
    )


def linha_do_diario(segundos: float, texto: str) -> str:
    """Uma linha no formato do ``journalctl -o short-iso-precise`` com o structlog dentro."""
    s = f"{segundos:09.6f}"
    return (f"2026-09-27T22:10:{s}-0300 maquina hefesto-dualsense4unix[4242]: "
            f"2026-09-27T22:10:{s}Z [info     ] {texto}")


def quem_e_quem_json(ob: ModuleType, estado: dict[str, Any]) -> str:
    """O ``quem_e_quem.py --json`` que concorda com o estado (a luz, o número, o transporte)."""
    from hefesto_dualsense4unix.core.formas_do_endereco import mascarar

    fisicos = [
        {
            "uniq": mascarar(c["uniq"]),
            "transporte": "cabo" if c["transport"] == "usb" else "rádio",
            "hidraw": f"hidraw{c['player']}",
            "led_desenho": "00100",
            "led_jogador": c["player"],
            "luz_rgb": list(c["lightbar_rgb"]),
            "luz_brilho": 255,
            "bateria": c["battery_pct"],
        }
        for c in estado["controllers"]
    ]
    return json.dumps({"veredito": "ok", "alvos_inicio": [], "alvos_fim": [], "mexeu": [],
                       "medidas": {}, "fisicos": fisicos, "vpads": []})


def config_com_perfil(raiz: Path, nome: str, caminho: str) -> Path:
    config = raiz / "config"
    (config / "profiles").mkdir(parents=True, exist_ok=True)
    (config / "profiles" / f"{nome.lower()}.json").write_text(
        json.dumps({"name": nome, "mode": {"caminho": caminho}}), encoding="utf-8"
    )
    (config / "active_profile.txt").write_text(nome + "\n", encoding="utf-8")
    return config


def sessoes(saida: Path) -> list[Path]:
    return sorted(p.parent for p in saida.rglob("passos.jsonl"))


def passos(saida: Path) -> list[dict[str, Any]]:
    fora: list[dict[str, Any]] = []
    for sessao in sessoes(saida):
        for linha in (sessao / "passos.jsonl").read_text(encoding="utf-8").splitlines():
            fora.append(json.loads(linha))
    return fora


def resumo(saida: Path) -> dict[str, Any]:
    (sessao,) = sessoes(saida)
    return dict(json.loads((sessao / "resumo.json").read_text(encoding="utf-8")))


def da_linha(saida: Path, linha: str) -> list[dict[str, Any]]:
    return [p for p in passos(saida) if p["linha"] == linha]


# ---------------------------------------------------------------------------
# Régua 1 — o boot de sete pads para quatro jogadores
# ---------------------------------------------------------------------------


def test_regua_1_sete_pads_no_boot_para_quatro_jogadores_e_vermelho(
    ob: ModuleType, tmp_path: Path
) -> None:
    """Os sete pads de 27/09 nasceram em 5,3 s e três morreram depois.

    Agora há quatro, e a linha 1b tem de ler o BOOT: contar os pads de agora
    daria verde sobre o multiplicador que derrubou a sessão.
    """
    diario = [linha_do_diario(1.0, "daemon_starting version=3")]
    diario += [
        linha_do_diario(1.5 + 0.6 * i, f"uhid_device_created name='(Hefesto P{i % 4 + 1})'")
        for i in range(7)
    ]
    diario += [linha_do_diario(40.0, "uhid_device_destroyed name='DualSense (Hefesto P1)'")]
    estado = estado_da_mesa()
    maquina = fazer_maquina(
        ob, estado, tmp_path / "config", diario=diario, dispositivos=pads_uhid(4)
    )

    saida = tmp_path / "saida"
    rc = ob.executar(["--saida", str(saida), SUB_DA_SESSAO], maquina)

    (linha,) = da_linha(saida, "1b, os pads no boot")
    assert linha["veredito"] == ob.VERMELHO, linha
    assert linha["medida"] == {"pads_no_boot": 7, "jogadores": 4}
    assert rc == ob.RC_VERMELHO


def test_regua_1_a_troca_de_modo_depois_do_boot_nao_conta(ob: ModuleType) -> None:
    """Um pad criado 90 s depois do ``daemon_starting`` é troca de modo, não boot."""
    diario = [linha_do_diario(1.0, "daemon_starting")]
    diario += [linha_do_diario(2.0 + i, "uhid_device_created") for i in range(4)]
    assert ob.pads_no_boot(diario) == 4
    assert ob.pads_no_boot([*diario, linha_do_diario(59.0, "uinput_device_created")]) == 5
    fora = [linha_do_diario(1.0, "daemon_starting")] + [
        f"2026-09-27T22:11:3{i}.000000-0300 m h[1]: "
        f"2026-09-27T22:11:3{i}.000000Z [info] uinput_device_created"
        for i in range(3)
    ]
    assert ob.pads_no_boot(fora) == 0
    assert ob.pads_no_boot(["sem o começo do daemon"]) is None


# ---------------------------------------------------------------------------
# Régua 2 — o jogo no modo que o perfil dele não pediu
# ---------------------------------------------------------------------------


def test_regua_2_o_motivo_dito_explica_e_nao_absolve(ob: ModuleType, tmp_path: Path) -> None:
    """O L2 de 27/09: o PRAGMATA pediu o DualSense e a partida correu no Xbox.

    O R-04 recusou recriar os pads com o jogo vivo e disse por quê no diário.
    O motivo é verdade e a desobediência também: a linha é vermelha.
    """
    estado = estado_da_mesa(caminho="xbox", backend="uinput", perfil="PRAGMATA", jogo=True)
    config = config_com_perfil(tmp_path, "PRAGMATA", "dualsense")
    diario = [
        linha_do_diario(1.0, "daemon_starting"),
        linha_do_diario(
            30.0,
            "vpad_recriacao_bloqueada_por_jogo motivo='troca_de_caminho:dualsense' appid=3050",
        ),
    ]
    maquina = fazer_maquina(
        ob, estado, config, diario=diario, dispositivos=pads_uinput_xbox(ob),
        ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)},
    )

    saida = tmp_path / "saida"
    rc = ob.executar(["--saida", str(saida), "eixos"], maquina)

    (linha,) = da_linha(saida, "o modo do perfil contra o ar, também com o jogo aberto")
    assert linha["veredito"] == ob.VERMELHO, linha
    assert "não pediu" in linha["porque"]
    assert linha["medida"]["bloqueios"] == ["dualsense"]
    assert rc == ob.RC_VERMELHO
    # O resto da mesa estava certo: o vermelho é dessa linha, e não de um dublê torto.
    vermelhos = [p["linha"] for p in passos(saida) if p["veredito"] == ob.VERMELHO]
    assert vermelhos == ["o modo do perfil contra o ar, também com o jogo aberto"]


def test_regua_2_o_modo_pedido_que_esta_no_ar_e_verde(ob: ModuleType) -> None:
    """O controle positivo: o perfil pede o Xbox e o ar está no Xbox."""
    estado = estado_da_mesa(caminho="xbox", backend="uinput", perfil="Freestyle")
    veredito, _porque, _medida = ob.linha_do_perfil_contra_o_ar(
        estado, {"Freestyle": {"name": "Freestyle", "mode": {"caminho": "xbox"}}}, []
    )
    assert veredito == ob.VERDE


# ---------------------------------------------------------------------------
# Régua 3 — o sha256 que não voltou
# ---------------------------------------------------------------------------


def _mexer_no_perfil(argv: Sequence[str], maquina: Any) -> None:
    if len(argv) > 1 and Path(argv[1]).name == "quem_e_quem.py":
        alvo = maquina.config / "profiles" / "freestyle.json"
        alvo.write_text(alvo.read_text(encoding="utf-8") + " ", encoding="utf-8")


def _rodar_com_perfil_mexido(ob: ModuleType, tmp_path: Path, nome: str) -> tuple[int, Path]:
    estado = estado_da_mesa()
    config = config_com_perfil(tmp_path / nome, "Freestyle", "dualsense")
    maquina = fazer_maquina(ob, estado, config, dispositivos=pads_uhid(4),
                            ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)},
                            ao_rodar=_mexer_no_perfil)
    saida = tmp_path / nome / "saida"
    return ob.executar(["--saida", str(saida), "retrato"], maquina), saida


def test_regua_3_o_arquivo_dela_que_mudou_recusa(ob: ModuleType, tmp_path: Path) -> None:
    rc, saida = _rodar_com_perfil_mexido(ob, tmp_path, "cura")
    assert rc == ob.RC_RECUSADO
    assert any("profiles/freestyle.json mudou" in r for r in resumo(saida)["recusas"])


def test_regua_3_a_mordida_sem_a_volta_o_arquivo_passa_calado(
    ob: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ob.Sessao, "conferir_a_volta", lambda self: [])
    rc, saida = _rodar_com_perfil_mexido(ob, tmp_path, "mordida")
    assert rc != ob.RC_RECUSADO
    assert not any("freestyle.json" in r for r in resumo(saida)["recusas"])


# ---------------------------------------------------------------------------
# Régua 4 — a mesa que mudou no meio
# ---------------------------------------------------------------------------


def _o_p2_sai(argv: Sequence[str], maquina: Any) -> None:
    if len(argv) > 1 and Path(argv[1]).name == "quem_e_quem.py":
        maquina.estado_de_agora["controllers"] = [
            c for c in maquina.estado_de_agora["controllers"] if c["player"] != 2
        ]


def _rodar_com_o_p2_saindo(ob: ModuleType, tmp_path: Path, nome: str) -> tuple[int, Path]:
    estado = estado_da_mesa()
    maquina = fazer_maquina(ob, estado, tmp_path / nome / "config", dispositivos=pads_uhid(4),
                            ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)},
                            ao_rodar=_o_p2_sai)
    saida = tmp_path / nome / "saida"
    return ob.executar(["--saida", str(saida), "retrato"], maquina), saida


def test_regua_4_o_controle_que_saiu_da_mesa_recusa_dizendo_quem(
    ob: ModuleType, tmp_path: Path
) -> None:
    rc, saida = _rodar_com_o_p2_saindo(ob, tmp_path, "cura")
    assert rc == ob.RC_RECUSADO
    recusas = resumo(saida)["recusas"]
    assert any(
        "a mesa mudou no meio da medida" in r and "o P2 saiu da mesa" in r for r in recusas
    ), recusas
    # A recusa fala por jogador, nunca pelo endereço.
    assert not any(u in json.dumps(recusas) for u in UNIQS)


def test_regua_4_a_mordida_sem_a_relistagem_ninguem_diz_quem_saiu(
    ob: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ob.Sessao, "relistar_e_conferir", lambda self: None)
    _rc, saida = _rodar_com_o_p2_saindo(ob, tmp_path, "mordida")
    assert not any("saiu da mesa" in r for r in resumo(saida)["recusas"])


# ---------------------------------------------------------------------------
# Régua 5 — a luz que o daemon PEDIU não é a que o aparelho mostra
# ---------------------------------------------------------------------------


def test_regua_5_a_luz_desejada_e_nao_sei_e_nunca_verde(ob: ModuleType, tmp_path: Path) -> None:
    """O sysfs de mentira concorda com o estado em tudo: só a fonte da luz é «desired»."""
    estado = estado_da_mesa(fonte_da_luz="desired")
    maquina = fazer_maquina(ob, estado, tmp_path / "config", dispositivos=pads_uhid(4),
                            ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)})
    saida = tmp_path / "saida"
    rc = ob.executar(["--saida", str(saida), "saidas", "--so", "luz"], maquina)

    linhas = da_linha(saida, "3a, a luz e o número")
    assert [p["jogador"] for p in linhas] == ["P1", "P2", "P3", "P4"]
    assert {p["veredito"] for p in linhas} == {ob.NAO_SEI}
    assert rc == ob.RC_NAO_SEI
    # Nada foi escrito: a luz só lê, e a bancada nem foi pedida.
    assert [m for m, _p in maquina.chamados if m != "daemon.state_full"] == []


def test_regua_5_o_controle_positivo_a_luz_lida_do_sysfs_e_verde(
    ob: ModuleType, tmp_path: Path
) -> None:
    estado = estado_da_mesa(fonte_da_luz="sysfs")
    maquina = fazer_maquina(ob, estado, tmp_path / "config", dispositivos=pads_uhid(4),
                            ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)})
    saida = tmp_path / "saida"
    assert ob.executar(["--saida", str(saida), "saidas", "--so", "luz"], maquina) == ob.RC_VERDE
    assert {p["veredito"] for p in da_linha(saida, "3a, a luz e o número")} == {ob.VERDE}


# ---------------------------------------------------------------------------
# Régua 6 — as seis formas do endereço, pelo dono da máscara
# ---------------------------------------------------------------------------

_SEPARADORES = (":", "-", "_", ".", " ", "")


def _janelas_que_vazam(texto: str, octetos: Sequence[str]) -> list[str]:
    """Todo pedaço de três octetos seguidos que carrega o 4º ou o 5º, nas duas ordens."""
    baixo = texto.lower()
    achados = []
    for ordem in (list(octetos), list(reversed(octetos))):
        for i in range(len(ordem) - 2):
            janela = ordem[i : i + 3]
            if octetos[3] not in janela and octetos[4] not in janela:
                continue
            for sep in _SEPARADORES:
                pedaco = sep.join(janela).lower()
                if pedaco in baixo:
                    achados.append(pedaco)
    return achados


def _as_seis_formas(octetos: Sequence[str], *, conhecido: bool) -> list[str]:
    seis = "".join(octetos[3:])
    formas = [
        ":".join(octetos),                              # 1, a separada (e as outras grafias)
        "-".join(octetos).upper(),
        "dev_" + "_".join(octetos).upper(),             # o caminho do BlueZ
        "".join(octetos),                               # 2, a colada
        f"hefesto_som_{seis}",                          # 3, o sufixo do nó
        f"HEFESTO{seis.upper()}",                       # 4, o endpoint da háptica
        f"hefesto-ponte-{seis}",                        # 6, o rótulo do gravador
    ]
    if conhecido:
        formas.append(" ".join(reversed(octetos)))      # 5, a invertida com espaço
    return formas


def _rodar_com_as_formas(ob: ModuleType, tmp_path: Path, nome: str) -> tuple[Path, list[str]]:
    estado = estado_da_mesa()
    conhecido = UNIQS[0].split(":")
    despejo = "\n".join(
        [f"conhecido: {f}" for f in _as_seis_formas(conhecido, conhecido=True)]
        + [f"desconhecido: {f}" for f in _as_seis_formas(DESCONHECIDO, conhecido=False)]
    )
    maquina = fazer_maquina(ob, estado, tmp_path / nome / "config", dispositivos=pads_uhid(4),
                            ensaios={"quem_e_quem.py": despejo})
    saida = tmp_path / nome / "saida"
    ob.executar(["--saida", str(saida), "retrato"], maquina)
    textos = [
        p.read_text(encoding="utf-8", errors="replace") for p in saida.rglob("*") if p.is_file()
    ]
    return saida, textos


def test_regua_6_nenhuma_janela_com_o_quarto_ou_o_quinto_octeto_sobra(
    ob: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    saida, textos = _rodar_com_as_formas(ob, tmp_path, "cura")
    tela = capsys.readouterr().out
    (sessao,) = sessoes(saida)
    gravado = sessao / "ensaios" / "quem_e_quem.txt"
    assert gravado.is_file()
    # O ensaio chegou ao arquivo (a régua não mede um arquivo vazio).
    assert "desconhecido: hefesto-ponte-" in gravado.read_text(encoding="utf-8")
    for texto in [*textos, tela]:
        assert _janelas_que_vazam(texto, UNIQS[0].split(":")) == []
        assert _janelas_que_vazam(texto, DESCONHECIDO) == []


def test_regua_6_a_mordida_sem_a_sexta_forma_o_rotulo_do_gravador_vaza(
    ob: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from hefesto_dualsense4unix.core import formas_do_endereco

    # Os dois grupos ficam (a substituição do dono os cita); o padrão nunca casa.
    monkeypatch.setattr(formas_do_endereco, "_ROTULO_DO_GRAVADOR", re.compile(r"(?!x)(x)(x)"))
    _saida, textos = _rodar_com_as_formas(ob, tmp_path, "mordida")
    assert any(_janelas_que_vazam(texto, DESCONHECIDO) for texto in textos)


# ---------------------------------------------------------------------------
# Régua 7 — nada sob a pasta de estudos
# ---------------------------------------------------------------------------


def test_regua_7_nenhum_caminho_dele_mora_na_pasta_de_estudos(
    ob: ModuleType, tmp_path: Path
) -> None:
    estudos = (RAIZ / "docs" / "process").resolve()
    caminhos = ob.caminhos_que_ele_mesmo_abre()
    assert {"ensaios", "sondas", "saida_padrao"} <= set(caminhos)
    for nome, caminho in caminhos.items():
        assert not Path(caminho).resolve().is_relative_to(estudos), f"{nome} mora em {caminho}"
    # E todos existem no que o git carrega: o pacote os leva, o clone limpo os tem.
    for nome, caminho in caminhos.items():
        if nome.startswith(("sonda:", "ensaio:")):
            assert Path(caminho).is_file(), f"{nome}: {caminho} não existe"

    # Sem --saida, a sessão inteira vai para o estado do Hefesto (aqui, o berço).
    estado = estado_da_mesa()
    maquina = fazer_maquina(ob, estado, tmp_path / "config", dispositivos=pads_uhid(4))
    sessao = ob.Sessao(maquina, "retrato")
    assert sessao.saida.resolve().is_relative_to((tmp_path / "estado").resolve())
    assert not sessao.saida.resolve().is_relative_to(estudos)


# ---------------------------------------------------------------------------
# Régua 8 — os pacotes levam o protocolo inteiro
# ---------------------------------------------------------------------------

#: Os formatos, e como cada um escreve o caminho de origem. O `.spec` escreve
#: duas vezes: no %install e no %files (sem o segundo, o rpmbuild aborta).
FORMATOS: dict[str, tuple[str, ...]] = {
    "packaging/arch/PKGBUILD": ("{rel}",),
    "scripts/build_deb.sh": ("{rel}",),
    "packaging/fedora/hefesto-dualsense4unix.spec": ("{rel}", "%{{_datadir}}/%{{app_id}}/{rel}"),
    "flatpak/io.github.hefesto_team.hefesto_dualsense4unix.yml": ("{rel}",),
    "scripts/build_appimage.sh": ('"$HERE/{rel}"',),
    "scripts/build_appimage_gui.sh": ('"$HERE/{rel}"',),
}

#: O formato que espera a sprint dona do arquivo, com a razão. A régua abaixo
#: reprova quando ele passar a levar o protocolo — a isenção caducou.
FORA_POR_POSSE = {"packaging/nix/package.nix": "O-NIX-LEVA-AS-REGRAS-DO-HOST-01"}


def _importados_locais(arquivo: Path) -> set[Path]:
    """Os módulos de ``scripts/`` e ``scripts/ensaios/`` que ``arquivo`` importa."""
    arvore = ast.parse(arquivo.read_text(encoding="utf-8"))
    fora: set[Path] = set()
    for no in ast.walk(arvore):
        nomes: list[str] = []
        if isinstance(no, ast.Import):
            nomes = [a.name.split(".")[0] for a in no.names]
        elif isinstance(no, ast.ImportFrom) and no.module and no.level == 0:
            nomes = [no.module.split(".")[0]]
        for nome in nomes:
            for pasta in (arquivo.parent, SCRIPTS / "ensaios", SCRIPTS):
                candidato = pasta / f"{nome}.py"
                if candidato.is_file():
                    fora.add(candidato)
                    break
    return fora


def arquivos_do_protocolo(ob: ModuleType) -> list[str]:
    """O ``o_basico.py``, os ensaios que ele chama, o que eles importam, e as sondas."""
    fila = [SCRIPTS / "o_basico.py"] + [SCRIPTS / "ensaios" / n for n in ob.ENSAIOS_CHAMADOS]
    vistos: set[Path] = set()
    while fila:
        atual = fila.pop()
        if atual in vistos:
            continue
        vistos.add(atual)
        fila.extend(_importados_locais(atual) - vistos)
    rels = {p.relative_to(RAIZ).as_posix() for p in vistos}
    rels |= {f"scripts/sondas/{n}" for n in ob.SONDAS_DO_BASICO}
    return sorted(rels)


def _linhas_de_codigo(texto: str) -> Iterator[str]:
    for linha in texto.splitlines():
        if not linha.lstrip().startswith("#"):
            yield linha


def test_regua_8_cada_formato_leva_cada_arquivo_do_protocolo(ob: ModuleType) -> None:
    exigidos = arquivos_do_protocolo(ob)
    # O controle positivo da própria régua: o fecho dos imports alcança o dono comum.
    assert {"scripts/o_basico.py", "scripts/ensaios/comum.py", "scripts/identidade_do_vpad.py",
            "scripts/sondas/nucleo-por-processo.bt"} <= set(exigidos)
    faltas = []
    for formato, grafias in FORMATOS.items():
        codigo = "\n".join(_linhas_de_codigo((RAIZ / formato).read_text(encoding="utf-8")))
        for rel in exigidos:
            for grafia in grafias:
                if grafia.format(rel=rel) not in codigo:
                    faltas.append(f"{formato}: {grafia.format(rel=rel)}")
    assert faltas == [], "\n".join(faltas)


def test_regua_8_a_isencao_do_nix_caduca_quando_ele_levar_o_protocolo() -> None:
    for formato, dona in FORA_POR_POSSE.items():
        texto = (RAIZ / formato).read_text(encoding="utf-8")
        assert "scripts/o_basico.py" not in texto, (
            f"{formato} já leva o protocolo: a isenção da {dona} caducou — "
            "tire-o de FORA_POR_POSSE e ponha em FORMATOS"
        )


# ---------------------------------------------------------------------------
# Régua 9 — o jogo e a Steam, com o mesmo nome de fio, separados pelo processo
# ---------------------------------------------------------------------------

PID_DA_STEAM = 100
PID_DO_JOGO = 300
FIO = "HIDAPI Rumble"


def _saida_da_sonda(ordem: Sequence[str], escritas: Sequence[tuple[int, int]]) -> str:
    """O ``print(@hw)`` do bpftrace, montado NA ORDEM que a sonda versionada grava."""
    linhas = ["=== 30 s"]
    for pid, vezes in escritas:
        valores = {"pid": str(pid), "comm": FIO, "minor": "5", "bytes": "48"}
        chave = ", ".join(valores.get(campo, "0") for campo in ordem)
        linhas.append(f"@hw[{chave}]: {vezes}")
    return "\n".join(linhas) + "\n"


def test_regua_9_o_resumo_separa_o_jogo_da_steam_pelo_processo(
    ob: ModuleType, tmp_path: Path
) -> None:
    sonda = (SCRIPTS / "sondas" / "nucleo-por-processo.bt").read_text(encoding="utf-8")
    ordem = ob.ordem_da_chave_do_hw(sonda)
    texto = _saida_da_sonda(ordem, [(PID_DA_STEAM, 12), (PID_DO_JOGO, 30)])
    processos = {
        1: (0, "systemd"),
        PID_DA_STEAM: (1, "steam"),
        250: (1, "reaper"),
        PID_DO_JOGO: (250, "PRAGMATA.exe"),
    }

    dono = ob.dono_pela_arvore(processos, jogo=[PID_DO_JOGO])
    escritas = ob.escritas_por_dono(texto, ordem, dono)
    assert escritas == {("steam", FIO, 5, 48): 12, ("jogo", FIO, 5, 48): 30}

    # E o resumo do saidas, de ponta a ponta, com a sessão do protocolo aberta.
    estado = estado_da_mesa(jogo=True)
    maquina = fazer_maquina(ob, estado, tmp_path / "config", dispositivos=pads_uhid(4),
                            processos=processos, jogo=[PID_DO_JOGO])
    sessao = ob.Sessao(maquina, "saidas", saida=tmp_path / "saida")
    assert sessao.abrir()
    ob._o_dono_de_cada_escrita(sessao, {"nucleo-por-processo.bt": Sonda(texto)})
    (linha,) = [p for p in sessao.passos if p.linha == "o dono de cada escrita"]
    assert linha.veredito == ob.VERMELHO
    assert "a Steam escreveu 12 vez(es)" in linha.porque
    assert "jogo=30" in linha.porque and "steam=12" in linha.porque


# ---------------------------------------------------------------------------
# O pad uinput de toda máscara é nosso (o L2 de 27/09 saía «NÃO SONDADO»)
# ---------------------------------------------------------------------------


def _no_de_entrada(raiz: Path, evento: str, nome: str, morada: str) -> Path:
    dir_input = raiz / "devices" / morada
    dir_input.mkdir(parents=True, exist_ok=True)
    (dir_input / "name").write_text(nome + "\n", encoding="utf-8")
    classe = raiz / "class" / "input" / evento
    classe.mkdir(parents=True, exist_ok=True)
    (classe / "device").symlink_to(dir_input, target_is_directory=True)
    return classe / "device"


def test_o_pad_uinput_da_mascara_dualsense_e_nosso_e_o_edge_de_verdade_nao(tmp_path: Path) -> None:
    identidade = _carregar("identidade_do_vpad_da_regua", SCRIPTS / "identidade_do_vpad.py")
    from hefesto_dualsense4unix.integrations.uinput_gamepad import DUALSENSE_EDGE_NAME, FLAVORS

    nomes = identidade.nomes_do_pad_uinput()
    assert nomes == {str(d["name"]) for d in FLAVORS.values()}
    nosso = _no_de_entrada(tmp_path, "event30", DUALSENSE_EDGE_NAME, "virtual/input/input1499")
    edge = _no_de_entrada(
        tmp_path, "event31", DUALSENSE_EDGE_NAME,
        "pci0000:00/0000:00:14.0/usb1/1-2/1-2:1.3/0003:054C:0DF2.0009/input/input77",
    )
    espelho = _no_de_entrada(
        tmp_path, "event32", "Microsoft X-Box 360 pad 0", "virtual/input/input1500"
    )

    assert identidade.e_pad_uinput_do_hefesto(DUALSENSE_EDGE_NAME, str(nosso), nomes)
    assert not identidade.e_pad_uinput_do_hefesto(DUALSENSE_EDGE_NAME, str(edge), nomes)
    assert not identidade.e_pad_uinput_do_hefesto("Microsoft X-Box 360 pad 0", str(espelho), nomes)


# ---------------------------------------------------------------------------
# O comando da CLI acha o protocolo, ou diz que ele não veio
# ---------------------------------------------------------------------------


def test_o_comando_da_cli_sem_o_protocolo_na_instalacao_e_nao_sei(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from hefesto_dualsense4unix.cli import cmd_basico

    monkeypatch.setattr(cmd_basico, "encontrar_arquivo_do_repo", lambda rel: None)
    assert cmd_basico.basico_cmd(["retrato"]) == cmd_basico.RC_NAO_SEI
    assert "não veio nesta instalação" in capsys.readouterr().err


def test_o_comando_da_cli_passa_os_argumentos_e_o_rc_inteiros(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from hefesto_dualsense4unix.cli import cmd_basico

    pedidos: list[list[str]] = []

    class Feito:
        returncode = 2

    def rodar(argv: list[str], check: bool) -> Feito:
        pedidos.append(argv)
        return Feito()

    monkeypatch.setattr(cmd_basico.subprocess, "run", rodar)
    assert cmd_basico.basico_cmd(["eixos", "--trocar-modo", "xbox"]) == 2
    (argv,) = pedidos
    assert argv[0] == sys.executable
    assert Path(argv[1]) == SCRIPTS / "o_basico.py"
    assert argv[2:] == ["eixos", "--trocar-modo", "xbox"]


# ---------------------------------------------------------------------------
# O que a conferência de 28/09 achou: o subcomando que cai não é vermelho
# ---------------------------------------------------------------------------


def test_o_subcomando_que_cai_no_meio_e_recusa_e_nunca_vermelho(
    ob: ModuleType, tmp_path: Path
) -> None:
    """Um erro do IPC no meio da troca de modo saía como traceback e rc=1.

    O rc=1 do Python se lê como «o aparelho reprovou», e o resumo e o caderno
    nem saíam. Mordida: tirar o ``except Exception`` do ``executar`` — a
    exceção atravessa e esta régua cai.
    """
    estado = estado_da_mesa(caminho="xbox", backend="uinput")
    maquina = fazer_maquina(
        ob, estado, tmp_path / "config", dispositivos=pads_uinput_xbox(ob),
        ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado), "bancada.sh": ""},
    )
    original = maquina.chamar

    def chamar(metodo: str, params: Any = None) -> Any:
        if metodo == "gamepad.emulation.set":
            raise RuntimeError("o daemon recusou o pedido")
        return original(metodo, params)

    maquina.chamar = chamar
    saida = tmp_path / "saida"
    rc = ob.executar(["--saida", str(saida), "eixos", "--trocar-modo", "dualsense"], maquina)

    assert rc == ob.RC_RECUSADO
    recusas = resumo(saida)["recusas"]
    assert any("caiu no meio" in r and "RuntimeError" in r for r in recusas), recusas


def test_a_queda_dita_explica_e_nao_absolve_o_modo_contra_o_ar(
    ob: ModuleType, tmp_path: Path
) -> None:
    """O modo DualSense pedido, o P2 no ``uinput`` com ``vpad_motivo`` pendurado.

    A tabela corrigida da sprint diz que verde é o pedido IGUAL ao do ar. O
    motivo explica a queda e não devolve o giro a quem perdeu. Mordida:
    devolver o ramo que dava verde a toda queda com motivo — o P2 sai verde.
    """
    estado = estado_da_mesa()
    estado["controllers"][1]["vpad_backend"] = "uinput"
    estado["controllers"][1]["vpad_motivo"] = "sem_uhid"
    estado["rumble_ff"]["per_vpad"][1]["backend"] = "uinput"
    maquina = fazer_maquina(
        ob, estado, tmp_path / "config", dispositivos=pads_uhid(4),
        ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)},
    )
    saida = tmp_path / "saida"
    rc = ob.executar(["--saida", str(saida), "eixos"], maquina)

    por_jogador = {p["jogador"]: p for p in da_linha(saida, "o modo contra o ar")}
    assert por_jogador["P2"]["veredito"] == ob.VERMELHO, por_jogador["P2"]
    assert "sem_uhid" in por_jogador["P2"]["porque"]
    assert {por_jogador[j]["veredito"] for j in ("P1", "P3", "P4")} == {ob.VERDE}
    assert rc == ob.RC_VERMELHO


def _estado_sem_pad(modo: str) -> dict[str, Any]:
    """A mesa na Conexão Nativa (``nativo``) ou na Navegação (``desligado``): nenhum pad."""
    estado = estado_da_mesa()
    estado["native_mode"] = modo == "nativo"
    estado["gamepad_emulation"]["enabled"] = False
    estado["rumble_ff"]["per_vpad"] = []
    for c in estado["controllers"]:
        c["vpad_backend"] = None
    return estado


@pytest.mark.parametrize("modo", ["nativo", "desligado"])
def test_o_modo_sem_pad_nao_sai_vermelho_por_nao_ter_pad(
    ob: ModuleType, tmp_path: Path, modo: str
) -> None:
    """Toda linha que conta pad vale em todo modo, não só nos dois que criam pad.

    Na Conexão Nativa e na Navegação o jogo lê o físico: zero pad é o certo, e
    o dono do modo (``modo_contra_o_ar``) já diz OK. O ``eixos`` dava o 1a
    vermelho, a máscara «não sei», o ``movimento`` vermelho em todo jogador e o
    1b vermelho. Mordida: tirar o ``_sem_pad_por_desenho`` de uma das linhas.
    """
    estado = _estado_sem_pad(modo)
    diario = [linha_do_diario(1.0, "daemon_starting")]
    maquina = fazer_maquina(
        ob, estado, tmp_path / "config", diario=diario, dispositivos="",
        ensaios={"quem_e_quem.py": quem_e_quem_json(ob, estado)},
    )
    saida = tmp_path / "saida"
    assert ob.executar(["--saida", str(saida / "e"), "eixos"], maquina) == ob.RC_VERDE
    assert [p["linha"] for p in passos(saida / "e") if p["veredito"] == ob.VERMELHO] == []
    (um_a,) = da_linha(saida / "e", "1a, um pad por jogador agora")
    assert um_a["veredito"] == ob.NAO_SE_APLICA

    ob.executar(["--saida", str(saida / "s"), SUB_DA_SESSAO], maquina)
    (um_b,) = da_linha(saida / "s", "1b, os pads no boot")
    assert um_b["veredito"] == ob.NAO_SE_APLICA

    ob.executar(["--saida", str(saida / "m"), "movimento"], maquina)
    movimento = da_linha(saida / "m", "o movimento chega ao pad")
    assert {p["veredito"] for p in movimento} == {ob.NAO_SE_APLICA}


def test_o_1b_com_menos_pads_que_jogadores_e_nao_sei_e_nunca_vermelho(
    ob: ModuleType, tmp_path: Path
) -> None:
    """O vermelho do 1b é o multiplicador. Um controle que chegou depois do boot é «não sei»."""
    diario = [linha_do_diario(1.0, "daemon_starting")]
    diario += [linha_do_diario(2.0 + i, "uhid_device_created") for i in range(3)]
    maquina = fazer_maquina(ob, estado_da_mesa(), tmp_path / "config", diario=diario,
                            dispositivos=pads_uhid(4))
    saida = tmp_path / "saida"
    ob.executar(["--saida", str(saida), SUB_DA_SESSAO], maquina)
    (linha,) = da_linha(saida, "1b, os pads no boot")
    assert linha["veredito"] == ob.NAO_SEI, linha


def test_a_celula_da_matriz_mostra_o_pior_dos_passos_dela(
    ob: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A hora de cada pad cai na MESMA célula («todos»): um vermelho no meio sumia da matriz.

    Mordida: voltar ao dicionário em que o último passo da célula vence — a
    matriz diz «verde» sobre o pad que levou 30 s.
    """
    sessao = tmp_path / "sessao"
    sessao.mkdir()
    comum = {"sub": SUB_DA_SESSAO, "linha": "a hora do pad", "jogador": "todos",
             "transporte": "—", "modo": "xbox"}
    linhas = [dict(comum, veredito=ob.VERMELHO), dict(comum, veredito=ob.VERDE)]
    (sessao / "passos.jsonl").write_text(
        "".join(json.dumps(p) + "\n" for p in linhas), encoding="utf-8"
    )
    assert ob.veredito(sessao) == ob.RC_VERMELHO
    (linha,) = [ln for ln in capsys.readouterr().out.splitlines() if "a hora do pad" in ln]
    assert linha.rstrip().endswith("VERMELHO"), linha
