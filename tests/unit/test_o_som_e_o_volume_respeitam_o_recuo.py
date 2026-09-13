"""SOM-RECUO-01 — o som e o volume respeitam o recuo do servidor (13/09/2026).

Lido no journal do daemon dela, de 01:53:30 a 02:42:30 de 13/09, com o
``pipewire-pulse`` sem atender ninguém: 291 ``som_load_module_falhou`` a cada
10 s, 232 ``bt_mic_load_module_falhou`` e 715 ``audio_fonte_do_uniq_falhou``. A
MIC-O-CANAL-DO-OUTRO-01 deu recuo ao microfone; o som e o volume continuaram
batendo na mesma porta. Esta régua é das quatro metades da cura:

1. o som (``alto_falante_bt``) anota o prazo e espera o recuo;
2. som, microfone e volume dividem UM recuo — o servidor é um só;
3. ``audio_control`` devolve o «não sei» NA HORA em recuo;
4. a suíte não carrega módulo pelo ``_rodar`` do microfone, e o recuo do
   processo nasce zerado em cada teste.

NENHUM TESTE AQUI FALA COM O SERVIDOR DE SOM DA MÁQUINA: todo ``pactl`` é dublê,
injetado como ``runner`` ou posto no lugar do ``subprocess.run``.

COMO MORDE (exercido em 13/09/2026, as saídas estão na entrega)
----------------------------------------------------------------
* arranque a espera e a sondagem de ``alto_falante_bt._o_servidor_atende`` →
  reprova a seção 1;
* troque o ``dualsense_bt_audio.PACTL`` de ``alto_falante_bt._o_recuo`` e o de
  ``audio_control._rodar_pelo_recuo`` por um recuo próprio → reprova a seção 2;
* arranque o ``if PACTL.mudo()`` de ``_rodar_pelo_recuo`` → reprova a seção 3;
* arranque a guarda do ``dualsense_bt_audio._rodar`` e o ``zerar()`` de
  ``tests/conftest.py`` → reprova a seção 4.

Endereços sintéticos da faixa ``e8:47:3a`` com a máscara da casa.
"""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from typing import Any

import pytest

from hefesto_dualsense4unix.integrations import alto_falante_bt as af
from hefesto_dualsense4unix.integrations import audio_control as ac
from hefesto_dualsense4unix.integrations import dualsense_bt_audio as bt

DELE = "e8:47:3a:00:00:5c"
CANAL_DELE = "hefesto_mic_00005c"


class _Relogio:
    def __init__(self) -> None:
        self.agora = 1000.0

    def __call__(self) -> float:
        return self.agora


@pytest.fixture()
def recuo(monkeypatch: pytest.MonkeyPatch, tmp_path: Any) -> _Relogio:
    """Um recuo PRÓPRIO, com relógio de mentira — nunca o do processo."""
    relogio = _Relogio()
    monkeypatch.setattr(bt, "PACTL", bt.RecuoDoPactl(relogio=relogio))
    monkeypatch.setattr(bt.shutil, "which", lambda _nome: "/usr/bin/pactl")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))
    return relogio


def _nunca(_argv: list[str]) -> bool:
    return False


def _sempre(_argv: list[str]) -> bool:
    return True


def _so_o(palavra: str) -> Callable[[list[str]], bool]:
    return lambda argv: palavra in argv


class _Pactl:
    """`pactl` dublado que sabe as duas respostas: responde, ou estoura o prazo.

    `trava` diz quais perguntas estouram — é assim que o `subprocess.run` real
    se comporta com o servidor mudo, e é o que `RecuoDoPactl.perguntar` lê.
    """

    def __init__(self, *, trava: Callable[[list[str]], bool] = _nunca) -> None:
        self.chamadas: list[list[str]] = []
        self.trava = trava

    def __call__(self, argv: list[str]) -> str | None:
        self.chamadas.append(list(argv))
        if self.trava(argv):
            raise subprocess.TimeoutExpired(argv, 5.0)
        if len(argv) > 1 and argv[1] == "load-module":
            return f"{536870900 + len(self.chamadas)}\n"
        return ""

    def verbos(self) -> list[str]:
        return [argv[1] for argv in self.chamadas if len(argv) > 1]


class _RunDoServidorMudo:
    """`subprocess.run` de um servidor mudo com o prazo encurtado: espera e estoura."""

    def __init__(self, espera_s: float = 1.0) -> None:
        self.chamadas: list[list[str]] = []
        self.espera_s = espera_s

    def __call__(self, argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        self.chamadas.append(list(argv))
        time.sleep(self.espera_s)
        raise subprocess.TimeoutExpired(argv, self.espera_s)


def _resposta(stdout: str, rc: int = 0) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["pactl"], rc, stdout=stdout, stderr="")


# ===========================================================================
# 1. O SOM ANOTA O PRAZO E ESPERA O RECUO
# ===========================================================================


def test_dois_ciclos_com_o_load_module_estourando_fazem_um_load_module(
    recuo: _Relogio,
) -> None:
    """A cadência do journal: um ciclo do som a cada 10 s com o servidor mudo.

    Sem a cura, cada ciclo constrói um nó novo e manda o seu `load-module`. Com
    ela: o primeiro estoura e põe o servidor em recuo; o do ciclo seguinte, ainda
    no recuo, não sai; o de depois, com o recuo vencido, só pergunta a sondagem.
    """
    pactl = _Pactl(trava=_sempre)
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=pactl).iniciar() is False
    assert bt.pactl_mudo() is True
    recuo.agora += 1.0
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=pactl).iniciar() is False
    assert pactl.verbos().count("load-module") == 1, pactl.verbos()

    recuo.agora += 10.0
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=pactl).iniciar() is False
    assert pactl.verbos() == ["load-module", "info"], pactl.verbos()
    assert bt.PACTL.espera_s == 10.0


def test_vencido_o_recuo_a_sondagem_vem_antes_do_load(recuo: _Relogio) -> None:
    pactl = _Pactl(trava=_sempre)
    bt.PACTL.estourou()
    recuo.agora += bt.RECUO_PISO_S
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=pactl).iniciar() is False
    assert pactl.verbos() == ["info"], "o load-module saiu sem a sondagem responder"
    assert bt.PACTL.espera_s == 10.0

    recuo.agora += 10.0
    pactl.trava = _nunca
    no = af.SinkVirtualPipeWire(uniq=DELE, runner=pactl)
    assert no.iniciar() is True
    assert pactl.verbos()[-2:] == ["info", "load-module"]
    assert bt.PACTL.espera_s == 0.0


def test_sem_recuo_nenhum_o_load_module_sai_sem_sondagem(recuo: _Relogio) -> None:
    """O caminho de todo dia não ganha pergunta a mais."""
    pactl = _Pactl()
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=pactl).iniciar() is True
    assert pactl.verbos() == ["load-module"]


def test_estado_com_o_servidor_mudo_responde_nao_sei_sem_perguntar(
    recuo: _Relogio,
) -> None:
    pactl = _Pactl()
    no = af.SinkVirtualPipeWire(uniq=DELE, runner=pactl)
    no._module_id = "77"
    bt.PACTL.estourou()
    assert no.estado() is None
    assert pactl.chamadas == [], "o estado perguntou ao servidor em recuo"
    recuo.agora += bt.RECUO_PISO_S
    no.estado()
    assert pactl.verbos() == ["list"]


def test_o_primeiro_prazo_da_rota_para_a_rota_inteira(recuo: _Relogio) -> None:
    rota = af.RotaDoNo(
        True,
        sink="alsa_output.usb-duble",
        por_onde=af.POR_CABO,
        fonte=af.FONTE_MIX,
        monitor_do_mix="alsa_output.pci-duble.monitor",
    )
    assert len(af.argv_das_rotas(af.nome_do_sink(DELE), rota)) == 2
    pactl = _Pactl(trava=_so_o("module-loopback"))
    # O nó sobe mesmo sem rota — decisão dela de 08/09 (`D-0809-O-NO-DE-SOM-…`).
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=pactl, rota=rota).iniciar() is True
    loopbacks = [argv for argv in pactl.chamadas if "module-loopback" in argv]
    assert len(loopbacks) == 1, "o segundo loopback foi para a fila do servidor mudo"
    assert bt.pactl_mudo() is True


def test_as_leituras_da_rota_esperam_o_servidor(recuo: _Relogio) -> None:
    pactl = _Pactl()
    bt.PACTL.estourou()
    assert af.sink_do_controle(DELE, [DELE], runner=pactl) == ""
    assert af.monitor_da_saida_padrao(runner=pactl) == ""
    rota = af.rota_do_no(DELE, af.TRANSPORTE_CABO, (DELE,), fonte=af.FONTE_MIX, runner=pactl)
    assert rota.tem_rota is False
    assert pactl.chamadas == [], "a rota perguntou ao servidor em recuo"


def test_o_rodar_do_som_anota_o_prazo_e_a_resposta(
    recuo: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """O `_rodar` de produção — o que o daemon usa quando ninguém injeta runner."""
    respostas: list[Any] = [subprocess.TimeoutExpired(["pactl"], 5.0)]

    def _run(argv: list[str], **_kw: Any) -> Any:
        resposta = respostas.pop(0)
        if isinstance(resposta, BaseException):
            raise resposta
        return resposta

    monkeypatch.setattr(subprocess, "run", _run)
    assert af.rodar_pactl(["pactl", "list", "sinks", "short"]) is None
    assert bt.pactl_mudo() is True, "o prazo estourado no `_rodar` do som não entrou no recuo"

    recuo.agora += bt.RECUO_PISO_S
    respostas.append(_resposta("1\thefesto_som_00005c\n"))
    assert af.rodar_pactl(["pactl", "list", "sinks", "short"]) == "1\thefesto_som_00005c\n"
    assert bt.PACTL.espera_s == 0.0


# ===========================================================================
# 2. SOM, MICROFONE E VOLUME DIVIDEM UM RECUO
# ===========================================================================


def test_prazo_estourado_no_som_cala_o_microfone_no_ciclo_seguinte(
    recuo: _Relogio,
) -> None:
    som = _Pactl(trava=_so_o("load-module"))
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=som).iniciar() is False
    mic = _Pactl()
    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=mic)
    assert source.iniciar() is False
    assert mic.chamadas == [], "o microfone perguntou ao servidor que o som acabou de ver mudo"


def test_prazo_estourado_no_microfone_cala_o_som_no_ciclo_seguinte(
    recuo: _Relogio,
) -> None:
    mic = _Pactl(trava=_so_o("load-module"))
    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=mic)
    assert source.iniciar() is False
    som = _Pactl()
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=som).iniciar() is False
    assert som.chamadas == [], "o som perguntou ao servidor que o microfone acabou de ver mudo"


def test_prazo_estourado_no_volume_cala_o_microfone_e_o_som(
    recuo: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(subprocess, "run", _RunDoServidorMudo(espera_s=0.0))
    assert ac.volume_da_captura(fonte=CANAL_DELE) is None
    mic, som = _Pactl(), _Pactl()
    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste", runner=mic)
    assert source.iniciar() is False
    assert af.SinkVirtualPipeWire(uniq=DELE, runner=som).iniciar() is False
    assert mic.chamadas == [], "o microfone perguntou ao servidor que o volume viu mudo"
    assert som.chamadas == [], "o som perguntou ao servidor que o volume viu mudo"


# ===========================================================================
# 3. O VOLUME DEVOLVE O «NÃO SEI» NA HORA
# ===========================================================================


def test_em_recuo_a_fonte_do_uniq_volta_na_hora(
    recuo: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A pergunta de 715 prazos no journal: em recuo, ela não espera nada.

    O dublê demora 1 s e estoura, como um servidor mudo com o prazo encurtado.
    A primeira chamada aquece os imports de dentro da função; a medida é da
    segunda.
    """
    run = _RunDoServidorMudo(espera_s=1.0)
    monkeypatch.setattr(subprocess, "run", run)
    bt.PACTL.estourou()
    ac.fonte_de_captura_do_uniq(DELE)
    comeco = time.monotonic()
    assert ac.fonte_de_captura_do_uniq(DELE) is None
    gasto = time.monotonic() - comeco
    assert gasto < 0.3, f"a fonte do uniq esperou {gasto:.2f} s pelo servidor em recuo"
    assert run.chamadas == [], "a fonte do uniq perguntou ao servidor em recuo"


_PERGUNTAS_DO_VOLUME: list[tuple[str, Callable[[], object], object]] = [
    ("fonte_de_captura_do_uniq", lambda: ac.fonte_de_captura_do_uniq(DELE), None),
    ("fonte_de_captura_do_controle", ac.fonte_de_captura_do_controle, None),
    (
        "definir_volume_da_captura",
        lambda: ac.definir_volume_da_captura(50, fonte=CANAL_DELE),
        False,
    ),
    ("volume_da_captura", lambda: ac.volume_da_captura(fonte=CANAL_DELE), None),
    (
        "AudioControl.fonte_padrao_e_o_controle",
        lambda: ac.AudioControl().fonte_padrao_e_o_controle(),
        False,
    ),
    (
        "AudioControl.toggle_default_source_mute",
        lambda: ac.AudioControl().toggle_default_source_mute(),
        False,
    ),
]


@pytest.mark.parametrize(
    ("nome", "pergunta", "nao_sei"),
    _PERGUNTAS_DO_VOLUME,
    ids=[nome for nome, _p, _n in _PERGUNTAS_DO_VOLUME],
)
def test_em_recuo_toda_pergunta_do_volume_devolve_o_nao_sei_sem_perguntar(
    recuo: _Relogio,
    monkeypatch: pytest.MonkeyPatch,
    nome: str,
    pergunta: Callable[[], object],
    nao_sei: object,
) -> None:
    run = _RunDoServidorMudo(espera_s=1.0)
    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(
        ac.shutil, "which", lambda cmd: "/usr/bin/pactl" if cmd == "pactl" else None
    )
    bt.PACTL.estourou()
    assert pergunta() is nao_sei
    assert run.chamadas == [], f"{nome} perguntou ao servidor em recuo"


def test_o_wpctl_fica_fora_do_recuo(recuo: _Relogio, monkeypatch: pytest.MonkeyPatch) -> None:
    """O recuo é do `pipewire-pulse`; o `wpctl` fala o protocolo nativo do PipeWire."""
    chamadas: list[list[str]] = []

    def _run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        chamadas.append(list(argv))
        return _resposta("node.name = alsa_input.usb-Sony_DualSense")

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(
        ac.shutil, "which", lambda cmd: "/usr/bin/wpctl" if cmd == "wpctl" else None
    )
    bt.PACTL.estourou()
    assert ac.AudioControl().fonte_padrao_e_o_controle() is True
    assert [argv[0] for argv in chamadas] == ["wpctl"]


def test_em_recuo_a_pergunta_segurada_nao_vira_aviso(
    recuo: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    avisos: list[str] = []
    depuracoes: list[str] = []

    class _Logger:
        def warning(self, evento: str, **_kw: Any) -> None:
            avisos.append(evento)

        def debug(self, evento: str, **_kw: Any) -> None:
            depuracoes.append(evento)

    monkeypatch.setattr(ac, "logger", _Logger())
    monkeypatch.setattr(subprocess, "run", _RunDoServidorMudo(espera_s=0.0))
    assert ac.fonte_de_captura_do_controle() is None  # a falha de verdade: o prazo
    assert avisos == ["audio_fonte_do_controle_falhou"]
    assert ac.fonte_de_captura_do_controle() is None  # agora, em recuo
    assert avisos == ["audio_fonte_do_controle_falhou"], "a pergunta segurada virou aviso"
    assert depuracoes == ["audio_fonte_do_controle_falhou"]


def test_vencido_o_recuo_so_a_resposta_de_verdade_zera(
    recuo: _Relogio, monkeypatch: pytest.MonkeyPatch
) -> None:
    respostas: list[subprocess.CompletedProcess[str]] = []

    def _run(_argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        return respostas.pop(0)

    monkeypatch.setattr(subprocess, "run", _run)
    bt.PACTL.estourou()
    recuo.agora += bt.RECUO_PISO_S
    respostas.append(_resposta("", rc=1))
    assert ac.volume_da_captura(fonte=CANAL_DELE) is None
    assert bt.PACTL.espera_s == bt.RECUO_PISO_S, "rc≠0 zerou o recuo sem o servidor responder"
    respostas.append(_resposta("Volume: front-left: 32768 /  50% / -18,06 dB"))
    assert ac.volume_da_captura(fonte=CANAL_DELE) == 50
    assert bt.PACTL.espera_s == 0.0


# ===========================================================================
# 4. A SUÍTE: A GUARDA DO MICROFONE E O RECUO QUE NASCE ZERADO
# ===========================================================================


def test_a_source_sem_runner_nao_carrega_modulo_no_servidor_de_verdade(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Any
) -> None:
    """A guarda do `dualsense_bt_audio._rodar` em `tests/conftest.py`.

    Sem `runner`, `SourceVirtualPipeWire` resolve o `_rodar` do módulo, que chama
    `subprocess.run` — o `pactl` DELA. O dublê aqui é o próprio `subprocess.run`,
    e ele conta: a leitura passa (a guarda deixa ler), o `load-module` e o
    `unload-module` não chegam.
    """
    chegaram: list[list[str]] = []

    def _run(argv: list[str], **_kw: Any) -> subprocess.CompletedProcess[str]:
        chegaram.append(list(argv))
        return _resposta("536870999\n")

    monkeypatch.setattr(subprocess, "run", _run)
    monkeypatch.setattr(bt.shutil, "which", lambda _nome: "/usr/bin/pactl")
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(tmp_path))

    source = bt.SourceVirtualPipeWire(nome=CANAL_DELE, descricao="Teste")
    source.iniciar()
    source._module_id = "536870999"
    source.parar()
    descarregou = bt.descarregar_modulo("536870999")

    escritas = [argv for argv in chegaram if "load-module" in argv or "unload-module" in argv]
    assert escritas == [], f"a suíte carregou ou descarregou módulo no servidor: {escritas}"
    assert descarregou is False
    assert ["pactl", "list", "modules", "short"] in chegaram, "a guarda comeu a LEITURA"


def test_o_recuo_do_processo_fica_sujo_dentro_de_um_teste() -> None:
    """Metade 1 de 2: suja o recuo do PROCESSO, como um prazo real estourado."""
    bt.PACTL.estourou()
    assert bt.pactl_mudo() is True


def test_e_o_teste_seguinte_nasce_com_o_recuo_zerado() -> None:
    """Metade 2 de 2 — só morde rodando DEPOIS da metade 1, no mesmo processo."""
    assert bt.PACTL.espera_s == 0.0, "o recuo sujo do teste anterior chegou a este"
    assert bt.pactl_mudo() is False
