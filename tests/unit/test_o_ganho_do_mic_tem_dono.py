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

BASH = shutil.which("bash") or "/bin/bash"
RAIZ = Path(__file__).resolve().parents[2]
DOCTOR = RAIZ / "scripts" / "doctor.sh"
UCM = RAIZ / "assets" / "ucm" / "DualSense-HiFi.conf"
FIXTURES = RAIZ / "tests" / "fixtures" / "mic-cabo"

#: O elemento de ganho de captura que a placa do DualSense tem. **Não é um
#: literal de conveniência:** é o que o `amixer scontents` gravado em
#: `tests/fixtures/mic-cabo/` imprime, e os testes abaixo o CONFEREM contra a
#: resposta do decisor do doctor antes de usá-lo em qualquer asserção.
ELEMENTO = "Headset"


def _secao_do_mic(texto: str) -> str:
    """O `SectionDevice."Mic"` inteiro, do jeito que o doctor o recorta.

    É a mesma fatia que `_definicao_da_porta_de_captura` entrega ao decisor
    quando a porta ativa é `[In] Mic`: da linha do `SectionDevice` até a
    primeira chave de fechamento na coluna zero.
    """
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
        f' "{FIXTURES / "sources-cabo-2026-09-20.txt"}"'
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
        """A fatia que o doctor lê é o `SectionDevice."Mic"`, e só ele.

        **O QUE A MORDIDA ARRANCA:** se `_secao_do_mic` devolvesse o arquivo
        inteiro, o teste acima passaria com as duas linhas dentro do
        `SectionDevice."Speaker"` — um lugar onde elas não valem nada. Esta
        régua fecha essa porta, e é a razão de o recorte existir.
        """
        secao = _secao_do_mic(UCM.read_text(encoding="utf-8"))
        assert 'SectionDevice."Mic"' in secao
        assert 'SectionDevice."Speaker"' not in secao, (
            "o recorte pegou a seção do alto-falante junto — a régua deixaria "
            "de distinguir onde as duas linhas moram"
        )
        assert "CaptureVolume" in secao and "CaptureMixerElem" in secao

    def test_o_mudo_nao_ganha_um_terceiro_dono(self) -> None:
        """Nenhum `CaptureSwitch` entra: o mudo já tem dois donos e chega.

        **O QUE A MORDIDA ARRANCA:** acrescente `CaptureSwitch` ao
        `SectionDevice."Mic"` e este teste reprova. O mudo desta casa é do
        firmware (`mic.set`, que apaga a luz vermelha) e da rota do
        WirePlumber; um terceiro caminho seria a terceira verdade sobre o mesmo
        botão, que é a família de defeito que a camada 1 do doctor existe para
        acusar.
        """
        secao = _secao_do_mic(UCM.read_text(encoding="utf-8"))
        assert "CaptureSwitch" not in secao, (
            "o `CaptureSwitch` liga o mudo da porta ao elemento de hardware e "
            "cria um terceiro dono para o mudo do microfone"
        )


class TestOTrilhoDoGanhoNaLinhaDoRotulo:
    """O arranjo D: o trilho na linha do rótulo, em bloco PRÓPRIO.

    §3 da sprint, medido no DOM a 1120, 1180 e 1440px: a linha nova embaixo do
    volume (arranjo A) custa +22,00px e o cartão tem 0,37px de folga; o mesmo
    trilho embrulhado num `.vol` custa +5px, porque `.vol` tem `height:22px`
    FIXA e a linha do rótulo tem 17. O bloco próprio custa ZERO.
    """

    def test_o_bloco_do_ganho_nao_e_um_vol(self) -> None:
        """O trilho do ganho tem classe própria, e ela não declara altura fixa.

        **O QUE A MORDIDA ARRANCA:** troque `class="ganho"` por `class="vol"`
        no gerador e o cartão vai de 327,63 para 332,63px — o
        `scripts/check_a_altura_do_cartao.py` reprova por 5px. Esta régua pega
        o mesmo defeito sem abrir navegador, e por isso roda na suíte.
        """
        from hefesto_dualsense4unix.interface import aba02

        css = aba02.CSS
        assert ".ganho{" in css, (
            "o bloco `.ganho` não está na folha — sem ele o trilho desenha "
            "INVISÍVEL, porque as regras do trilho são `.vol .trilho`"
        )
        regra = css.split(".ganho{", 1)[1].split("}", 1)[0]
        assert "height:" not in regra, (
            f"o `.ganho` declarou altura fixa ({regra!r}) — é exatamente os "
            "5px que o `.vol` cobra e que o arranjo D existe para não pagar"
        )
        for filho in (".ganho .trilho", ".ganho .cheio", ".ganho .n"):
            assert filho in css, (
                f"falta `{filho}`: fora de um `.vol` o trilho não herda regra "
                "nenhuma e desenha invisível"
            )

    def test_o_trilho_mora_na_linha_do_rotulo_do_microfone(self) -> None:
        """Ele nasce DENTRO do `.rot-linha`, à direita de «Microfone · ATIVO».

        **O QUE A MORDIDA ARRANCA:** mova o bloco para depois do
        `{linha_de_volume(...)}` (o arranjo A) e esta régua reprova — o trilho
        deixa de estar dentro da linha do rótulo, que é o único lugar desta
        moldura que custa ZERO altura.
        """
        from hefesto_dualsense4unix.interface import aba02

        pagina = aba02.MIOLO
        rotulo = re.search(
            r'<div class="rot rot-linha">Microfone(.*?)</div>', pagina, re.S)
        assert rotulo, "a linha do rótulo do Microfone sumiu do desenho"
        assert 'class="ganho"' in rotulo.group(1), (
            "o trilho do ganho não está na linha do rótulo — é o arranjo D "
            "que a §3 mediu em 0,00px, e qualquer outro lugar cobra pixel"
        )

    def test_os_dois_enderecos_do_ganho_existem_na_pagina(self) -> None:
        """A barra e o número têm `data-campo`, senão o desenho congela.

        **O QUE A MORDIDA ARRANCA:** tire o `data-campo="mic-ganho-barra"` do
        `.cheio` e o produto mostra para sempre o `+48` do DESENHO — que é,
        letra por letra, o defeito que o volume do microfone teve até 12/09.
        """
        from hefesto_dualsense4unix.interface import aba02

        pagina = aba02.MIOLO
        # O `\s+` e não um espaço: a marcação quebra linha entre os dois
        # atributos, e uma régua que exige o espaço literal reprova por
        # FORMATAÇÃO — que é dar vermelho sobre outra coisa que não o endereço.
        #
        # O NÚMERO NÃO DECLARA ALVO, e isso é o contrato do piloto, não
        # descuido: sem `data-hef-alvo` ele escreve TEXTO, que é o que o
        # `mic-num` do volume — o vizinho e o molde — já faz. A barra declara
        # `largura` porque largura não é o padrão.
        esperado = len(aba02.MESA)
        barra = re.findall(
            r'data-campo="mic-ganho-barra"\s+data-hef-alvo="largura"', pagina)
        assert len(barra) == esperado, (
            f"o campo `mic-ganho-barra` (alvo `largura`) aparece {len(barra)} "
            f"vez(es) e a mesa tem {esperado} lugares"
        )
        num = re.findall(r'data-campo="mic-ganho-num"(?!\s+data-hef-alvo)',
                         pagina)
        assert len(num) == esperado, (
            f"o campo `mic-ganho-num` aparece {len(num)} vez(es) sem alvo "
            f"declarado e a mesa tem {esperado} lugares"
        )

    def test_a_pergunta_carrega_a_unidade_e_a_diferenca(self) -> None:
        """§6.4: o `?` diz a unidade e separa ganho de volume.

        **O QUE A MORDIDA ARRANCA:** tire a palavra `amplifica` (ou a palavra
        `entrega`) da dica e esta régua reprova. Sem as duas, o número sai como
        `+48` sem unidade visível, a dois trilhos de distância do volume, e a
        tela deixa a pessoa adivinhar qual dos dois ela acabou de mexer.
        """
        from hefesto_dualsense4unix.interface import aba02

        dica = aba02.DICA_GANHO_MIC.lower()
        assert "db" in dica, "a dica não diz a unidade do ganho"
        assert "amplifica" in dica, (
            "a dica não diz o que o GANHO é — «o quanto o aparelho amplifica "
            "o que entra»"
        )
        assert "entrega" in dica, (
            "a dica não diz o que o VOLUME é — «o quanto disso o produto "
            "entrega» —, e sem o contraste ela explica um trilho só"
        )
        assert aba02.DICA_GANHO_MIC in aba02.MIOLO, (
            "a dica tem dono no gerador mas não chegou à página"
        )


#: O Chrome do sistema, o mesmo dos três portões de Playwright desta casa.
#: `launch()` sem `headless=False` não abre janela nenhuma na tela dela.
CHROME = Path("/usr/bin/google-chrome")


@pytest.mark.skipif(not CHROME.exists(), reason="Chrome do sistema ausente")
class TestOCinzaDoRadioNaoCobraAltura:
    """O estado do RÁDIO custa 17px de LARGURA e zero de altura — medido.

    **POR QUE ELE PRECISA DE RÉGUA PRÓPRIA:** o
    `scripts/check_a_altura_do_cartao.py` mede a página PARADA, e nela o `?` do
    ganho está escondido (as duas regras `:has(.dica:empty)`/`:has(.nada)` da
    folha comum). No rádio ele aparece — e a §3 da sprint mediu o arranjo D
    **sem** ele. Esta régua mede o estado que a mesa dela tem de verdade.
    """

    def test_com_o_cinza_e_o_ponto_de_interrogacao_o_cartao_nao_cresce(
        self, tmp_path: Path
    ) -> None:
        """Aciona o cinza nas quatro molduras e mede o cartão nas três larguras.

        **O QUE A MORDIDA ARRANCA:** dê altura ao `.ganho` (ou ponha o `?` numa
        linha própria) e o cartão passa de 327,63px, estourando os 0,37px de
        folga contra `PARA_O_CARD`. E se o `?` não acender — `acionados == 0` —
        a régua reprova também: ela não pode dar verde medindo uma tela em que
        o estado que ela testa não chegou a existir.
        """
        playwright = pytest.importorskip("playwright.sync_api")
        from hefesto_dualsense4unix.interface import aba02, onde
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        pagina = onde.pagina("02-controles.html")
        if not pagina.exists():  # pragma: no cover - árvore sem bancada
            pytest.skip(f"a bancada não está no disco — {pagina}")
        medir = """(razao) => {
          const alto = () => Math.max(...[...document.querySelectorAll(
              '.ctl.card:not(.off)')].map(
              c => Math.round(c.getBoundingClientRect().height * 100) / 100));
          let n = 0;
          for (const g of document.querySelectorAll('.ganho')) {
            g.classList.add('sem-ganho');
            const q = g.parentElement.querySelector(
              '[data-campo="mic-ganho-fora"][data-hef-alvo="html"]');
            if (q) { q.innerHTML = razao; n++; }
          }
          return {altura: alto(), acionados: n,
                  transborda: document.documentElement.scrollWidth >
                              document.documentElement.clientWidth};
        }"""
        with playwright.sync_playwright() as pw:
            nav = pw.chromium.launch(executable_path=str(CHROME),
                                     args=["--no-sandbox"])
            try:
                for larg in (1120, 1180, 1440):
                    pg = nav.new_page(viewport={"width": larg, "height": 1080},
                                      device_scale_factor=1)
                    pg.goto(pagina.as_uri())
                    pg.wait_for_load_state("networkidle")
                    pg.wait_for_timeout(250)
                    visto = pg.evaluate(medir, a02.RAZAO_DO_GANHO_FORA)
                    pg.close()
                    assert visto["acionados"] == len(aba02.MESA), (
                        f"{larg}px: o cinza foi acionado em "
                        f"{visto['acionados']} moldura(s) de {len(aba02.MESA)} "
                        "— régua que acha zero é ERRO, não silêncio"
                    )
                    assert visto["altura"] <= aba02.PARA_O_CARD, (
                        f"{larg}px: com o `?` do ganho aceso o cartão mede "
                        f"{visto['altura']}px e a caixa reserva "
                        f"{aba02.PARA_O_CARD} — no rádio a aba passa a rolar"
                    )
                    assert not visto["transborda"], (
                        f"{larg}px: a página passou a transbordar na horizontal"
                    )
            finally:
                nav.close()


class TestODonoDoNumeroPerguntaAoAparelho:
    """O valor vem do `amixer`, e os três estados de "não sei" são distintos.

    A §8 da sprint escreve a regra com o comando: *pergunte ao **aparelho**
    (`amixer … sget`), nunca ao número que a tela escreveu*.
    """

    def test_o_ganho_sai_da_gravacao_do_aparelho(self) -> None:
        """O leitor tira `(por cento, dB)` do `scontents` REAL da bancada.

        **O QUE A MORDIDA ARRANCA:** troque o `(\\d+)%` por um literal (ou faça
        o leitor devolver `GANHO_PADRAO_PCT` quando não achar) e este teste
        reprova — porque o esperado NÃO é montado com as constantes que a
        função lê: ele vem do arquivo que o `amixer` cuspiu no controle dela,
        `tests/fixtures/mic-cabo/scontents-dualsense-2026-09-20.txt`.
        """
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        bruto = (FIXTURES / "scontents-dualsense-2026-09-20.txt").read_text(
            encoding="utf-8")
        lido = a02._ganho_do_scontents(bruto)
        assert lido is not None, (
            "o leitor não achou elemento de ganho na gravação do aparelho"
        )
        pct, db = lido
        # O ESPERADO É LIDO DA MESMA GRAVAÇÃO, por um caminho INDEPENDENTE do
        # da função: aqui casa-se a linha inteira do `amixer`, lá caminha-se
        # pelas capacidades. Montar o esperado com as constantes da função
        # seria tautologia, e passaria mesmo com ela quebrada.
        esperada = re.search(r"Capture \d+ \[(\d+)%\] \[(-?[\d.]+)dB\]", bruto)
        assert esperada, "a gravação do aparelho mudou de forma"
        assert (pct, db) == (int(esperada.group(1)), float(esperada.group(2)))
        assert (pct, db) == (100, 48.0), (
            "o aparelho estava no TOPO da faixa quando isto foi gravado — se "
            "este número mudou, quem mudou foi a gravação"
        )

    def test_placa_sem_ganho_de_captura_nao_inventa_zero(self) -> None:
        """Sem elemento de captura a resposta é `None`, nunca `0`.

        **O QUE A MORDIDA ARRANCA:** faça o leitor devolver `(0, 0.0)` no fim e
        este teste reprova. Zero pintaria «ganho no mínimo» sobre uma placa que
        não tem ganho nenhum — que é, letra por letra, a «cura» de 26/07 que
        emudeceu o microfone de quem a rodou.
        """
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
        # SINTÉTICO, e declarado: é a FORMA que o `amixer` usa para um controle
        # simples que mistura saída e chave de entrada. O que ancora a forma no
        # real é o `Front Mic Boost` da placa de bordo desta bancada, que
        # declara `Playback channels` e `Capture channels` no mesmo elemento.
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
        """O de saída vem ANTES na gravação real, e mesmo assim não vence.

        **O QUE A MORDIDA ARRANCA:** faça o leitor pegar o primeiro elemento
        que tiver qualquer volume e ele devolve o `PCM` — que é o volume do
        alto-falante do controle, não o ganho do microfone dela.
        """
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        bruto = (FIXTURES / "scontents-dualsense-2026-09-20.txt").read_text(
            encoding="utf-8")
        assert bruto.index("'PCM'") < bruto.index("'Headset'"), (
            "o elemento de SAÍDA tem de vir ANTES na gravação; se vier depois, "
            "a régua passa mesmo com o leitor pegando o primeiro que achar"
        )
        assert a02._ganho_do_scontents(bruto) == (100, 48.0)

    def test_os_tres_estados_do_cinza(self) -> None:
        """Ausente = não sei · `None` = não alcança · tupla = alcança.

        **O QUE A MORDIDA ARRANCA:** colapse os dois primeiros (por exemplo,
        `return "" if uniq in _GANHO else RAZAO_DO_GANHO_FORA`) e o primeiro
        `assert` reprova — o trilho acenderia cinza nos ~2 s que a thread da
        camada 1 demora a dar a primeira volta, sobre uma ignorância que dura
        dois segundos.
        """
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
        """A poda do cache conhece a quinta leitura — CACHE-SEM-PODA-01.

        **O QUE A MORDIDA ARRANCA:** tire o `_GANHO` de `_POR_CONTROLE` e este
        teste reprova. O `uniq` é o MAC e volta igual: sem a poda, o controle
        que reconecta veria o ganho da placa que o PipeWire já destruiu — que é
        exatamente a queixa dela de 20/09 renascendo num cache novo.
        """
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

    def test_o_radio_entra_com_chave_e_o_cabo_nao_e_chutado(self) -> None:
        """`_ler_o_ganho` responde por TODO controle da mesa, inclusive o mudo.

        **O QUE A MORDIDA ARRANCA:** faça `_ler_o_ganho` devolver `{}` quando
        não há fonte ALSA (em vez de `{uniq: None}`) e este teste reprova — a
        aba deixa de distinguir *ainda não perguntei* de *perguntei e não há*,
        e o cinza do rádio nunca acende.

        Não abre subprocesso: sem `alsa_input.*` na mesa a função responde
        antes de chamar comando nenhum, que é a razão de o atalho existir.
        """
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        so_radio = {"aa:bb:cc:00:00:03": "hefesto_mic_000003",
                    "aa:bb:cc:00:00:04": ""}
        lido = a02._ler_o_ganho(so_radio)
        assert lido == {u: None for u in so_radio}, (
            f"a mesa só de rádio tem de sair com chave e `None`; saiu {lido!r}"
        )
        assert a02._ler_o_ganho({}) == {}, (
            "mesa vazia é mesa vazia — não há sobre o que responder"
        )

    def test_o_default_do_ganho_esta_escrito_e_e_o_topo_da_faixa(self) -> None:
        """§6.3: nenhum campo nasce sem opinião, e esta está justificada.

        **O QUE A MORDIDA ARRANCA:** baixe `GANHO_PADRAO_PCT` e este teste
        reprova. A razão de não baixar é medida e é dela — *o único microfone
        dela é o do DualSense*, e ele já vive no topo: escolher outro número
        faria o microfone dela ficar mais baixo do que está hoje, numa sprint
        cujo nome é «ter dono», não «mudar o som».
        """
        from hefesto_dualsense4unix.interface import aba02
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        assert a02.GANHO_PADRAO_PCT == 100, (
            "o default do ganho é o TOPO da faixa, que é o que o firmware "
            "entrega — ver a docstring da constante"
        )
        assert aba02.GANHO_PADRAO_PCT == a02.GANHO_PADRAO_PCT, (
            "o desenho e o produto discordam sobre o default; dois números "
            "para a mesma opinião é como eles divergem"
        )
        assert aba02.sinal_do_ganho(a02.GANHO_PADRAO_PCT) == "+48", (
            "o desenho parado tem de dizer o topo da faixa que o aparelho "
            "mediu (+48 dB)"
        )
        assert aba02.sinal_do_ganho(0) == "+0"

    def test_o_pacote_nao_emite_o_ganho_antes_de_ela_publicar(self) -> None:
        """Enquanto a página publicada não tiver o trilho, o campo não sai.

        **O QUE A MORDIDA ARRANCA:** tire a guarda `A_PAGINA_TEM_O_GANHO` da
        emissão e as três chaves entram em `orfaos` no casamento das dez — o
        pacote passa a se reportar pintando o que não pinta. É a mesma guarda
        que o `mic-nativo-fora` e o «Ouvir junto» já têm, e a razão é que
        **publicar é ato dela**.
        """
        from hefesto_dualsense4unix.interface import onde
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        publicado = onde.pagina(a02.PAGINA, publicado=True).read_text(
            encoding="utf-8")
        tem = 'data-campo="mic-ganho-barra"' in publicado
        assert a02.A_PAGINA_TEM_O_GANHO is tem, (
            "a guarda não está respondendo sobre a página PUBLICADA — é ela "
            "que o piloto abre, não a bancada"
        )

