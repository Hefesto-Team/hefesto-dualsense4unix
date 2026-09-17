"""A bancada de mentira do nó de som — o `pactl` que ACEITA, GUARDA e LÊ.

Nascida na SOM-JUNTO-01 (17/09/2026) e compartilhada de propósito: duas réguas
precisam perguntar *"o que ficou CARREGADO no servidor de som depois da
varredura?"*, e um dublê por arquivo é como esta casa fabrica duas verdades
sobre a mesma pergunta. As duas donas são
``test_som_junto_01_a_fonte_chega_ao_no_vivo.py`` e
``test_o_sfx_de_cada_um_e_do_dono.py`` — a segunda porque a régua dela olhava
o CACHE quando prometia olhar o nó.

**NENHUM BYTE VAI A SERVIDOR NENHUM.** Quem desvia é
``monkeypatch.setattr(alto_falante_bt, "_rodar", Pactl())``: ``_rodar`` é o dono
único de todo ``pactl`` daquele módulo — o nó, a rota, o ``sink_do_controle`` e
o ``monitor_da_saida_padrao`` passam por ele —, e é por isso que UM desvio cobre
a cena inteira sem dublar peça por peça.

**O DUBLÊ MANTÉM A LISTA VIVA**, e não é enfeite: ``sink_do_controle`` devolve o
PRÓPRIO ``hefesto_som_<hex6>`` como recuo quando não acha placa da Sony, e só
enxerga esse nó porque ele está na lista de ``pactl list sinks short``. Um dublê
que respondesse lista fixa esconderia a armadilha do nó que vira alvo de si
mesmo — que é justamente o que a cura desta sprint tem de recusar.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from hefesto_dualsense4unix.daemon.subsystems import alto_falante as mod

#: MACs FORJADOS, da faixa sintética que o portão de fixtures permite. Nenhum
#: destes é um controle desta bancada: régua que só passa com os DualSense dela
#: mede a bancada, não a cura.
P1 = "aa:bb:cc:00:00:c1"
P2 = "aa:bb:cc:00:00:c2"

#: A saída padrão do sistema, e a outra para onde ela troca.
HDMI = "alsa_output.pci-0000_0a_00.1.hdmi-stereo"
FONE = "alsa_output.pci-0000_0a_00.3.analog-stereo"

#: A placa USB do P1 no cabo, no formato que o PipeWire publica.
SINK_P1 = (
    "alsa_output.usb-Sony_Interactive_Entertainment_DualSense_Wireless_"
    "Controller-00.analog-surround-40"
)

#: O nome do perfil da bancada. Um só: os testes vivem num lar de mentira
#: (`tests/conftest.py` desvia `HOME` e os quatro `XDG_*`), e reusar o nome
#: deixa cada teste dono do arquivo dele.
PERFIL = "mesa-do-som-junto"


class Pactl:
    """Um ``pactl`` que aceita, guarda o que está carregado, e sabe LER.

    Um dublê que só sabe aceitar não mede religação nenhuma: o que interessa
    aqui não é o argv pedido, é o que continua DE PÉ depois da varredura.
    """

    def __init__(self, *, placas: tuple[str, ...] = ()) -> None:
        self.argvs: list[list[str]] = []
        self.carregados: dict[str, list[str]] = {}
        self.padrao = HDMI
        self._placas = list(placas)
        self._proximo = 500

    def __call__(self, argv: list[str]) -> str | None:
        self.argvs.append(list(argv))
        if argv[:2] == ["pactl", "load-module"]:
            self._proximo += 1
            self.carregados[str(self._proximo)] = list(argv)
            return f"{self._proximo}\n"
        if argv[:2] == ["pactl", "unload-module"]:
            self.carregados.pop(argv[2], None)
            return ""
        if "get-default-sink" in argv:
            return f"{self.padrao}\n"
        if argv[:4] == ["pactl", "list", "sinks", "short"]:
            vivos = [*self._placas, HDMI, FONE, *self.publicados]
            return "".join(
                f"{60 + i}\t{nome}\tPipeWire\ts16le 2ch 48000Hz\tIDLE\n"
                for i, nome in enumerate(vivos)
            )
        return ""

    # -- leitura: o que está CARREGADO agora, nunca o que foi pedido -------

    @property
    def publicados(self) -> list[str]:
        """Os ``sink_name`` dos ``module-null-sink`` de pé."""
        return [
            a[len("sink_name=") :]
            for argv in self.carregados.values()
            if "module-null-sink" in argv
            for a in argv
            if a.startswith("sink_name=")
        ]

    @property
    def loopbacks(self) -> list[tuple[str, str]]:
        """``(source, sink)`` de cada ``module-loopback`` DE PÉ."""
        fios: list[tuple[str, str]] = []
        for argv in self.carregados.values():
            if "module-loopback" not in argv:
                continue
            campos = {a.split("=", 1)[0]: a.split("=", 1)[1] for a in argv if "=" in a}
            fios.append((campos.get("source", ""), campos.get("sink", "")))
        return fios

    @property
    def descarregados(self) -> list[str]:
        """Os ids que passaram por ``unload-module``, na ordem."""
        return [a[2] for a in self.argvs if a[:2] == ["pactl", "unload-module"]]


class Store:
    """O pedacinho do ``StateStore`` que o subsystem pergunta: o perfil ativo."""

    def __init__(self, perfil: str | None) -> None:
        self.active_profile = perfil


def _caminho_do_perfil(nome: str) -> Path:
    from hefesto_dualsense4unix.profiles.loader import profiles_dir

    return Path(profiles_dir(ensure=True)) / f"{nome}.json"


def escrever_perfil(fontes: dict[str, str], nome: str = PERFIL) -> str:
    """Um perfil DE VERDADE no lar de mentira. Devolve o nome."""
    corpo: dict[str, Any] = {
        # `match` é OBRIGATÓRIO no schema, e `volume` também
        # (`ProfileSpeakerConfig`, e a razão está escrita lá): sem os dois o
        # pydantic recusa o perfil inteiro, `_fontes_por_controle` devolve `{}`
        # pelo `except` — que é o comportamento CERTO do produto — e a régua
        # mede um dublê inválido em vez da fiação.
        "name": nome,
        "match": {"type": "any"},
        "controllers": {
            mod._uniq_de_perfil(uniq): {"speaker": {"volume": 180, "fonte": fonte}}
            for uniq, fonte in fontes.items()
        },
    }
    _caminho_do_perfil(nome).write_text(json.dumps(corpo), encoding="utf-8")
    return nome


def ela_clica(uniq: str, fonte: str, nome: str = PERFIL) -> None:
    """O gesto dela nos três botões: grava a fonte no perfil, e o mtime anda.

    O carimbo que invalida o cache é ``mtime_ns``. Duas escritas no mesmo
    nanossegundo não existem nesta máquina, mas a régua não pode depender
    disso — daí o ``utime`` explícito.
    """
    alvo = _caminho_do_perfil(nome)
    corpo = json.loads(alvo.read_text(encoding="utf-8"))
    corpo["controllers"].setdefault(mod._uniq_de_perfil(uniq), {}).setdefault(
        "speaker", {"volume": 180}
    )["fonte"] = fonte
    alvo.write_text(json.dumps(corpo), encoding="utf-8")
    agora = alvo.stat().st_mtime_ns + 1_000_000
    os.utime(alvo, ns=(agora, agora))


def cabo(uniq: str) -> mod.ControleNaLista:
    return mod.ControleNaLista(uniq=uniq, caminho="/dev/hidraw0", transporte="cabo")


def radio(uniq: str) -> mod.ControleNaLista:
    return mod.ControleNaLista(uniq=uniq, caminho="/dev/hidraw1", transporte="rádio")


def subsystem_e_gerenciador(nome: str | None, **kw: Any) -> tuple[Any, Any]:
    """A fiação de PRODUÇÃO: ``fonte_por_controle=sub._fonte_do_controle``.

    É o que ``AltoFalanteSubsystem.start`` monta, e não um ``lambda`` de
    conveniência — medir a fiação é metade do ponto destas réguas. O
    ``fonte_por_controle`` já passou meses como parâmetro sem chamador.
    """
    sub = mod.AltoFalanteSubsystem(fonte_de_controles=lambda: [])
    sub._store = Store(nome)
    return sub, mod.GerenciadorDeNosDeSom(
        fonte_por_controle=sub._fonte_do_controle, **kw
    )
