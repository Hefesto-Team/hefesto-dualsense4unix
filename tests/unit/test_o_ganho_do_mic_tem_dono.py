"""O-GANHO-DO-MIC-TEM-DONO-01 — o ganho de entrada do microfone tem dono.

São DOIS lados, e cada um tem a sua mordida escrita na docstring do teste:

1. **O UCM DESTA CASA LIGA O ELEMENTO.** `assets/ucm/DualSense-HiFi.conf` é a
   definição da porta `[In] Mic`, e até 20/09/2026 ela declarava só
   `CapturePCM`/`CapturePriority` — o `Headset Capture Volume` (0…+48 dB, o
   aparelho no topo) ficava fora do alcance do PipeWire, do produto e dela.
2. **A TELA MOSTRA O GANHO, E ELE TEM DONO.** O trilho mora na linha do rótulo
   (o arranjo D da sprint, medido em 0,00px), o valor vem do APARELHO e não do
   número que a tela escreveu, e o `?` carrega a unidade e a diferença entre
   ganho e volume.

**A RÉGUA NÃO REIMPLEMENTA A REGRA DO UCM.** Quem decide se uma porta liga o
elemento é `_dualsense_porta_de_captura_status`, no `scripts/doctor.sh`, e é a
ele que este arquivo pergunta — com o `amixer scontents` REAL da bancada como
segundo texto. Reescrever aqui a busca por `CaptureVolume` seria a segunda
régua para o mesmo fato, e a divergência entre as duas é o defeito que esta
casa já pagou (o `validar-caducos.py` e o `portao_a_casa_sabe`).
"""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.unit import pactl_json_de_mentira as pj

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
UCM = RAIZ / "assets" / "ucm" / "DualSense-HiFi.conf"
FIXTURES = RAIZ / "tests" / "fixtures" / "mic-cabo"

#: O elemento de ganho de captura que a placa do DualSense tem. **Não é um
ELEMENTO = "Headset"


def _secao_do_mic(texto: str) -> str:
    """O `SectionDevice."Mic"` inteiro, do jeito que o doctor o recorta."""
    fora: list[str] = []
    dentro = False
    for linha in texto.splitlines(keepends=True):
        if linha.startswith('SectionDevice."Mic"'):
            dentro = True
        if dentro:
            fora.append(linha)
            if linha.startswith("}"):
                break
    return "".join(fora)


def _decidir(porta_conf: Path) -> tuple[str, str, str]:
    """`(porta, elemento, fora_de_alcance)` — pergunta ao decisor do doctor."""
    script = (
        f'source "{DOCTOR}" >/dev/null 2>&1 || true\n'
        f"_dualsense_porta_de_captura_status"
        f' "{FIXTURES / "sources-cabo-2026-09-20.json"}"'
        f' "{FIXTURES / "scontents-dualsense-2026-09-20.txt"}"'
        f' "{porta_conf}"\n'
    )
    proc = subprocess.run(
        [BASH, "-c", script],
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C"},
        check=False,
    )
    partes = [*proc.stdout.strip().split("\t"), "", "", ""][:3]
    return (partes[0], partes[1], partes[2])


@pytest.mark.skipif(not DOCTOR.exists(), reason="scripts/doctor.sh ausente")
@pytest.mark.skipif(not FIXTURES.is_dir(), reason="tests/fixtures/mic-cabo ausente")
class TestOUcmLigaOElemento:
    """O `SectionDevice."Mic"` desta casa põe o ganho ao alcance do PipeWire."""

    def test_o_ucm_de_hoje_alcanca_o_ganho(self, tmp_path: Path) -> None:
        """O ARQUIVO REAL, medido pelo decisor do doctor, não deixa ganho fora.

        **O QUE A MORDIDA ARRANCA:** apague as linhas `CaptureVolume` e
        `CaptureMixerElem` de `assets/ucm/DualSense-HiFi.conf` e este teste
        reprova com `fora == "sim"` — que é literalmente o estado de 20/09, o
        defeito que a sprint nomeia. Arrancado e conferido antes de entregar.
        """
        secao = tmp_path / "porta-ucm-mic-de-hoje.txt"
        secao.write_text(_secao_do_mic(UCM.read_text(encoding="utf-8")),
                         encoding="utf-8")
        porta, elemento, fora = _decidir(secao)
        assert porta == "[In] Mic", (
            f"a porta ativa da fixture é a `[In] Mic`; saiu {porta!r}"
        )
        assert elemento == ELEMENTO, (
            f"o elemento de ganho da placa é o `{ELEMENTO}`; saiu {elemento!r} "
            "— se mudou, quem mudou foi o aparelho, e a fixture é que envelheceu"
        )
        assert fora == "não", (
            "o `SectionDevice.\"Mic\"` desta casa tem de LIGAR o "
            f"`{ELEMENTO} Capture Volume`. Com ele fora, o ganho de 0…+48 dB "
            "fica sem dono — nem o PipeWire, nem a tela, nem ela"
        )

    def test_a_secao_recortada_nao_e_o_arquivo_inteiro(self) -> None:
        """A fatia que o doctor lê é o `SectionDevice."Mic"`, e só ele."""
        secao = _secao_do_mic(UCM.read_text(encoding="utf-8"))
        assert 'SectionDevice."Mic"' in secao
        assert 'SectionDevice."Speaker"' not in secao, (
            "o recorte pegou a seção do alto-falante junto — a régua deixaria "
            "de distinguir onde as duas linhas moram"
        )
        assert "CaptureVolume" in secao and "CaptureMixerElem" in secao

    def test_o_mudo_nao_ganha_um_terceiro_dono(self) -> None:
        """Nenhum `CaptureSwitch` entra: o mudo já tem dois donos e chega."""
        secao = _secao_do_mic(UCM.read_text(encoding="utf-8"))
        assert "CaptureSwitch" not in secao, (
            "o `CaptureSwitch` liga o mudo da porta ao elemento de hardware e "
            "cria um terceiro dono para o mudo do microfone"
        )


class TestOGanhoSaiDoDesenhoDoTodo:
    """**O DESENHO DO TODO (15/10/2026) NÃO TEM A LINHA DO GANHO.**

    O microfone fica só com o Volume. O ganho segue com dono no back-end (o gesto `ganho-mic`,
    o aparelho e o UCM), mas sem botão na tela. MORDIDA: ponha o `<div class="vol ganho">` de
    volta no gerador e os dois casos reprovam.
    """

    def test_o_gerador_nao_tem_a_linha_do_ganho(self) -> None:
        from hefesto_dualsense4unix.interface import aba02

        assert 'class="vol ganho"' not in aba02.MIOLO
        assert 'data-gesto="ganho-mic"' not in aba02.MIOLO
        assert "ganho" not in aba02.CSS.lower() or ".ganho .un" not in aba02.CSS

    def test_a_pagina_do_desenho_nao_tem_os_enderecos_do_ganho(self) -> None:
        doc = (RAIZ / "mockup" / "02-controles.html").read_text(encoding="utf-8")
        for campo in ("mic-ganho-barra", "mic-ganho-num", "mic-ganho-fora"):
            assert f'data-campo="{campo}"' not in doc, f"{campo} voltou ao desenho"


class TestODonoDoNumeroPerguntaAoAparelho:
    """O valor vem do `amixer`, e os três estados de "não sei" são distintos."""

    def test_o_ganho_sai_da_gravacao_do_aparelho(self) -> None:
        """O leitor tira `(por cento, dB)` do `scontents` REAL da bancada."""
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        bruto = (FIXTURES / "scontents-dualsense-2026-09-20.txt").read_text(
            encoding="utf-8")
        lido = a02._ganho_do_scontents(bruto)
        assert lido is not None, (
            "o leitor não achou elemento de ganho na gravação do aparelho"
        )
        pct, db = lido
        esperada = re.search(r"Capture \d+ \[(\d+)%\] \[(-?[\d.]+)dB\]", bruto)
        assert esperada, "a gravação do aparelho mudou de forma"
        assert (pct, db) == (int(esperada.group(1)), float(esperada.group(2)))
        assert (pct, db) == (100, 48.0), (
            "o aparelho estava no TOPO da faixa quando isto foi gravado — se "
            "este número mudou, quem mudou foi a gravação"
        )

    def test_placa_sem_ganho_de_captura_nao_inventa_zero(self) -> None:
        """Sem elemento de captura a resposta é `None`, nunca `0`."""
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        bruto = (FIXTURES / "scontents-sem-captura-2026-09-20.txt").read_text(
            encoding="utf-8")
        assert a02._ganho_do_scontents(bruto) is None

    def test_o_elemento_so_de_saida_nao_vira_ganho_de_entrada(self) -> None:
        """Um `pvolume` não é ganho de captura, e a régua tem de separar.

        **O ARRANJO FÁCIL NÃO MORDE, e isto foi medido:** com a gravação do
        DualSense sozinha, arrancar a exigência de `cvolume` **passa** — o
        `PCM` de lá tem `Playback` em toda linha de valor, e o filtro de
        `Capture ` já o descarta. Uma régua que parasse aqui daria verde sobre
        a cura arrancada.

        **O ARRANJO DIFÍCIL é um elemento `pvolume pswitch cswitch`**, cuja
        linha de valor traz o número do PLAYBACK e a palavra `Capture` na mesma
        linha. Ele existe: nesta bancada o `Front Mic Boost` da placa de bordo
        declara canais de Playback **e** de Capture no mesmo controle simples.

        **O QUE A MORDIDA ARRANCA:** tire o `cvolume` e o leitor devolve
        `(100, 0.0)` — o volume de SAÍDA lido como ganho de entrada.
        """
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        assert a02._CAPACIDADE_DE_GANHO == "cvolume", (
            "a capacidade que separa entrada de saída mudou de nome"
        )
        dificil = (
            "Simple mixer control 'Mic',0\n"
            "  Capabilities: pvolume pswitch cswitch\n"
            "  Playback channels: Front Left - Front Right\n"
            "  Capture channels: Front Left - Front Right\n"
            "  Limits: Playback 0 - 31\n"
            "  Front Left: Playback 31 [100%] [0.00dB] [on] Capture [off]\n"
            "  Front Right: Playback 31 [100%] [0.00dB] [on] Capture [off]\n"
            "Simple mixer control 'Headset',0\n"
            "  Capabilities: cvolume cvolume-joined cswitch cswitch-joined\n"
            "  Capture channels: Mono\n"
            "  Limits: Capture 0 - 101\n"
            "  Mono: Capture 77 [76%] [36.50dB] [on]\n"
        )
        assert a02._ganho_do_scontents(dificil) == (76, 36.5), (
            "o leitor pegou o elemento de SAÍDA: a linha dele tem a palavra "
            "`Capture` e um por cento, e sem a exigência de `cvolume` ela casa"
        )

    def test_a_ordem_da_gravacao_nao_decide_qual_elemento_e_o_ganho(self) -> None:
        """O de saída vem ANTES na gravação real, e mesmo assim não vence."""
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        bruto = (FIXTURES / "scontents-dualsense-2026-09-20.txt").read_text(
            encoding="utf-8")
        assert bruto.index("'PCM'") < bruto.index("'Headset'"), (
            "o elemento de SAÍDA tem de vir ANTES na gravação; se vier depois, "
            "a régua passa mesmo com o leitor pegando o primeiro que achar"
        )
        assert a02._ganho_do_scontents(bruto) == (100, 48.0)

    def test_os_tres_estados_do_cinza(self) -> None:
        """Ausente = não sei · `None` = não alcança · tupla = alcança."""
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        uniq = "aa:bb:cc:00:00:01"
        guardado = dict(a02._GANHO)
        try:
            a02._GANHO.clear()
            assert a02.ganho_fora_de_alcance(uniq) == "", (
                "ninguém perguntou ainda, e «não sei» não apaga nada"
            )
            assert a02.ganho_do_microfone(uniq) is None

            a02._GANHO[uniq] = None
            assert a02.ganho_fora_de_alcance(uniq) == a02.RAZAO_DO_GANHO_FORA, (
                "perguntei e não há onde esse ganho exista — é aqui que o "
                "cinza acende, com a razão no `?`"
            )
            assert a02.ganho_do_microfone(uniq) is None

            a02._GANHO[uniq] = (72, 34.5)
            assert a02.ganho_fora_de_alcance(uniq) == ""
            assert a02.ganho_do_microfone(uniq) == (72, 34.5)
        finally:
            a02._GANHO.clear()
            a02._GANHO.update(guardado)

    def test_o_controle_que_sai_nao_deixa_ganho_para_o_que_volta(self) -> None:
        """A poda do cache conhece a quinta leitura — CACHE-SEM-PODA-01."""
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        assert a02._GANHO in a02._POR_CONTROLE, (
            "o cache do ganho não está na tupla que a poda percorre"
        )
        uniq = "aa:bb:cc:00:00:02"
        guardado = dict(a02._GANHO)
        try:
            a02._GANHO[uniq] = (100, 48.0)
            a02._esquecer_o_som_de_quem_saiu(frozenset())
            assert uniq not in a02._GANHO, (
                "o ganho sobreviveu à saída do controle"
            )
        finally:
            a02._GANHO.clear()
            a02._GANHO.update(guardado)

    def test_o_radio_entra_com_chave_e_o_cabo_nao_e_chutado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_ler_o_ganho` responde por TODO controle da mesa, inclusive o mudo."""
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        monkeypatch.setattr(eleicao_de_microfone, "fonte_nativa_do_controle",
                            lambda uniq, conectados: "")
        so_radio = ("aa:bb:cc:00:00:03", "aa:bb:cc:00:00:04")
        lido = a02._ler_o_ganho(so_radio)
        assert lido == {u: None for u in so_radio}, (
            f"a mesa só de rádio tem de sair com chave e `None`; saiu {lido!r}"
        )
        assert a02._ler_o_ganho(()) == {}, (
            "mesa vazia é mesa vazia — não há sobre o que responder"
        )

    def test_o_servidor_de_som_mudo_nao_acende_o_cinza(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`pactl` calado é *não sei*, e "não sei" fica de FORA do dicionário."""
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        mudo = ("aa:bb:cc:00:00:05", "aa:bb:cc:00:00:06")
        monkeypatch.setattr(eleicao_de_microfone, "_rodar",
                            lambda argv: (127, ""))
        lido = a02._ler_o_ganho(mudo)
        assert lido == {}, (
            f"com o `pactl` mudo nenhuma chave pode sair; saiu {lido!r} — e "
            "cada chave dessas acende o cinza com a razão do cabo"
        )
        guardado = dict(a02._GANHO)
        try:
            a02._GANHO.clear()
            a02._GANHO.update(lido)
            assert a02.ganho_fora_de_alcance(mudo[0]) == "", (
                "o cinza acendeu sobre «não sei»"
            )
        finally:
            a02._GANHO.clear()
            a02._GANHO.update(guardado)

    def test_o_ganho_do_cabo_nao_morre_no_no_da_nossa_ponte(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """O controle NO FIO tem ganho, com o daemon elegendo `hefesto_mic_…`.

        **O ARRANJO DIFÍCIL, E ELE É A BANCADA DE 20/09/2026.** A primeira
        redação desta sprint resolvia a placa pelo `canal_fonte` que o daemon
        publica, filtrando por `alsa_input.`. Medido na bancada, com UM
        DualSense no fio e três no ar, o `state_full` respondeu
        `hefesto_mic_<hex6>` **para os quatro** — o nó que o produto ELEGEU
        (regra 0 de `escolher_fonte`), que é da nossa ponte e não tem placa
        ALSA nenhuma. Resultado na tela: o trilho do ganho cinza no controle
        que estava NO CABO, com a razão mandando ligar o cabo.

        A pergunta certa é outra — *qual nó o KERNEL publica para este
        controle* — e ela já tem dono:
        `eleicao_de_microfone.fonte_nativa_do_controle`.

        **O QUE A MORDIDA ARRANCA:** volte a resolver pelo `canal_fonte` (ou
        acrescente um filtro `no.startswith("alsa_input.")` sobre o nó eleito)
        e este teste reprova com `None` no controle do cabo.

        **O QUE É DUBLÊ, E POR QUÊ:** os comandos (`pactl`, `amixer`) e o censo
        de USB, que lê `/sys`. O que roda de verdade é a corrente inteira que
        decide — `fontes_nativas` → `escolher_fonte` → `CasamentoUSB.casar` →
        `alsa.card` → `_ganho_do_scontents`. Os textos são SINTÉTICOS e a forma
        é a da bancada; endereço real não entra em arquivo versionado.
        """
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone
        from hefesto_dualsense4unix.integrations.fontes_de_captura import (
            CasamentoUSB,
        )
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        cabo = "aa:bb:cc:00:00:01"
        radio = "aa:bb:cc:00:00:02"
        nativo = ("alsa_input.usb-Sony_Interactive_Entertainment_DualSense_"
                  "Wireless_Controller-00.HiFi__Mic__source")
        curta = "\n".join([
            f"41\t{nativo}\tPipeWire\ts16le 1ch 48000Hz\tSUSPENDED",
            "42\thefesto_mic_000001\tPipeWire\ts16le 1ch 48000Hz\tRUNNING",
            "43\thefesto_mic_000002\tPipeWire\ts16le 1ch 48000Hz\tRUNNING",
        ])
        longa = "\n".join([
            "Source #41",
            f"\tName: {nativo}",
            "\tProperties:",
            '\t\talsa.card = "2"',
            "\tActive Port: [In] Mic",
            "Source #42",
            "\tName: hefesto_mic_000001",
            "\tProperties:",
            '\t\tdevice.string = "/run/user/1000/hefesto-hefesto_mic_000001.fifo"',
        ])
        amixer = (
            "Simple mixer control 'PCM',0\n"
            "  Capabilities: pvolume pvolume-joined pswitch pswitch-joined\n"
            "  Playback channels: Mono\n"
            "  Limits: Playback 0 - 100\n"
            "  Mono: Playback 100 [100%] [0.00dB] [on]\n"
            "Simple mixer control 'Headset',0\n"
            "  Capabilities: cvolume cvolume-joined cswitch cswitch-joined\n"
            "  Capture channels: Mono\n"
            "  Limits: Capture 0 - 101\n"
            "  Mono: Capture 77 [76%] [36.50dB] [on]\n"
        )
        monkeypatch.setattr(
            eleicao_de_microfone, "_rodar",
            lambda argv: (0, curta) if argv[-1] == "short" else (127, ""))
        monkeypatch.setattr(
            eleicao_de_microfone, "casamento_usb_agora",
            lambda uniqs: CasamentoUSB(por_uniq={cabo: "3-2", radio: ""},
                                       por_no={nativo: "3-2"}))
        monkeypatch.setattr(
            a02.audio_saida, "rodar_leitura",
            lambda argv: pj.json_do_longo(longa) if argv[0] == "pactl" else amixer)

        lido = a02._ler_o_ganho((cabo, radio))
        assert lido[cabo] == (76, 36.5), (
            "o controle NO CABO ficou sem ganho: o nó foi resolvido pelo que o "
            "daemon elegeu (`hefesto_mic_…`, sem placa ALSA) em vez de pelo nó "
            f"nativo que o kernel publica. Saiu {lido[cabo]!r}"
        )
        assert lido[radio] is None, (
            "o controle no rádio não tem placa ALSA e não pode herdar a do "
            f"vizinho; saiu {lido[radio]!r}"
        )

    def test_o_default_do_ganho_esta_escrito_e_e_o_topo_da_faixa(self) -> None:
        """§6.3: nenhum campo nasce sem opinião, e esta está justificada.

        **O QUE A MORDIDA ARRANCA:** baixe `GANHO_PADRAO_PCT` e este teste
        reprova. A razão de não baixar é medida e é do usuário — *o único microfone
        do usuário é o do DualSense*, e ele já vive no topo: escolher outro número
        faria o microfone do usuário ficar mais baixo do que está hoje, numa sprint
        cujo nome é «ter dono», não «mudar o som».
        """
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        assert a02.GANHO_PADRAO_PCT == 100, (
            "o default do ganho é o TOPO da faixa, que é o que o firmware "
            "entrega — ver a docstring da constante"
        )

    def test_o_pacote_nao_emite_o_ganho_antes_de_ela_publicar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Enquanto a página publicada não tiver o trilho, o campo não sai."""
        import pacotes

        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        entrada = {"uniq": "aa:bb:cc:00:00:07", "player": 1, "connected": True,
                   "transport": "usb", "battery_pct": 95, "is_primary": True,
                   "inputs": {}, "audio": {}}
        do_ganho = {"mic-ganho-num", "mic-ganho-barra", "mic-ganho-fora"}

        def um_card() -> dict:
            ctx = pacotes.Contexto(state={}, mesa=[], conectados=[entrada],
                                   estados={})
            return next(iter(a02.pacote(ctx)["cards"].values()))

        monkeypatch.setattr(a02, "A_PAGINA_TEM_O_GANHO", False)
        vazou = do_ganho & set(um_card())
        assert not vazou, (
            f"o pacote emitiu {sorted(vazou)} para uma página que não os tem "
            "— eles entram em `orfaos` no casamento das dez"
        )

        monkeypatch.setattr(a02, "A_PAGINA_TEM_O_GANHO", True)
        faltou = do_ganho - set(um_card())
        assert not faltou, (
            f"publicada a página, o pacote continua sem emitir {sorted(faltou)}"
            " — o trilho desenhado nunca receberia valor"
        )

