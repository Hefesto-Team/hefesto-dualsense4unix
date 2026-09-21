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


class TestOTrilhoDoGanhoNaLinhaQueElaAprovou:
    """**A RÉGUA MEDIA O ARRANJO QUE ELA RECUSOU — invertida em 21/09/2026.**

    O arranjo D (trilho na linha do rótulo, bloco próprio) foi escolhido pelo
    PREÇO: a §3 da sprint mediu +22,00px para a linha nova, +5px para o `.vol`,
    e ZERO para a linha do rótulo — e o cartão tinha 0,37px de folga.

    **Ela recusou, em 20/09**, e o produto foi para a linha própria: um segundo
    `.vol` embaixo do volume, com o rótulo «Ganho» ao lado. A lição desta casa
    está escrita: *implemente a imagem aprovada e pague a conta de altura
    depois, medindo*. Um arranjo escolhido pelo preço não é o desenho dela.

    O que estas réguas passam a medir é o arranjo DELA — e o preço continua
    tendo dono: `scripts/check_a_altura_do_cartao.py`, que é portão.
    """

    def test_o_ganho_e_uma_linha_propria_como_o_volume(self) -> None:
        """Ele é um `.vol`, e herda dele o `flex`, o `gap` e a altura.

        MORDIDA: devolva `class="ganho"` sozinho ao container. O trilho perde
        as regras `.vol .trilho` e desenha invisível — que é o defeito que a
        troca de arranjo tinha de não trazer de volta.
        """
        from hefesto_dualsense4unix.interface import aba02

        assert 'class="vol ganho"' in aba02.MIOLO, (
            "o bloco do ganho deixou de ser uma `.vol` — sem ela o trilho não "
            "herda regra nenhuma e desenha invisível")
        # E O QUE ELE TEM A MAIS CONTINUA NA FOLHA: a unidade, o número de
        # quatro caracteres e o cinza do fora de alcance.
        css = aba02.CSS
        for filho in (".ganho .un", ".ganho .n", ".ganho.sem-ganho .trilho"):
            assert filho in css, f"falta `{filho}` na folha"

    def test_o_rotulo_do_ganho_esta_na_linha_dele(self) -> None:
        """A linha do ganho diz «Ganho», senão os dois trilhos ficam iguais.

        MORDIDA: tire o `<span class="rot-vol">{ROTULO_LINHA_GANHO}</span>` e a
        pessoa vê dois trilhos idênticos empilhados, sem saber qual é qual.
        """
        from hefesto_dualsense4unix.interface import aba02

        bloco = re.search(r'<div class="vol ganho"(.*?)</div>',
                          aba02.MIOLO, re.S)
        assert bloco, "o bloco do ganho sumiu do desenho"
        assert "rot-vol" in bloco.group(1), (
            "a linha do ganho perdeu o rótulo — os dois trilhos do microfone "
            "viram dois trilhos iguais")

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

    def test_o_radio_entra_com_chave_e_o_cabo_nao_e_chutado(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`_ler_o_ganho` responde por TODO controle da mesa, inclusive o mudo.

        **O QUE A MORDIDA ARRANCA:** faça `_ler_o_ganho` devolver `{}` quando
        nenhum controle tem nó nativo (em vez de `{uniq: None}`) e este teste
        reprova — a aba deixa de distinguir *ainda não perguntei* de *perguntei
        e não há*, e o cinza do rádio nunca acende.

        Quem diz que o rádio não publica nó nativo é o DONO da resposta
        (`eleicao_de_microfone.fonte_nativa_do_controle`), e é ele que está
        dublado aqui — digitar «rádio → sem ganho» dentro do `_ler_o_ganho`
        seria a segunda régua sobre o mesmo fato.
        """
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
        """`pactl` calado é *não sei*, e "não sei" fica de FORA do dicionário.

        **O TERCEIRO ESTADO É O QUE SE PERDE PRIMEIRO.** O cinza do trilho
        carrega uma razão que AFIRMA — *"pelo rádio o microfone chega como som
        já digitalizado… Ligue o cabo e ele acende"*. Acendê-lo porque o
        servidor de som não respondeu é dizer «não há» quando a verdade é «não
        consegui perguntar», e quem está com o cabo na mão lê uma ordem para
        ligar o cabo.

        **O QUE A MORDIDA ARRANCA:** faça `_ler_o_ganho` escrever
        `fora[uniq] = None` também quando `fonte_nativa_do_controle` devolve
        `None` (ou faça essa função colapsar `None` em `""`) e este teste
        reprova — a chave aparece, `ganho_fora_de_alcance` acende o cinza, e a
        razão passa a mandar ligar um cabo sobre uma ignorância nossa.
        """
        from hefesto_dualsense4unix.integrations import eleicao_de_microfone
        from hefesto_dualsense4unix.interface.pacotes import a02_controles as a02

        mudo = ("aa:bb:cc:00:00:05", "aa:bb:cc:00:00:06")
        # O `_rodar` da eleição devolve `(127, "")` quando o `pactl` não está
        # lá — é o mesmo desfecho de um servidor de som que não responde.
        monkeypatch.setattr(eleicao_de_microfone, "_rodar",
                            lambda argv: (127, ""))
        lido = a02._ler_o_ganho(mudo)
        assert lido == {}, (
            f"com o `pactl` mudo nenhuma chave pode sair; saiu {lido!r} — e "
            "cada chave dessas acende o cinza com a razão do cabo"
        )
        # E a tela, com o dicionário assim, não apaga nada.
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

        **O ARRANJO DIFÍCIL, E ELE É A MESA DELA DE 20/09/2026.** A primeira
        redação desta sprint resolvia a placa pelo `canal_fonte` que o daemon
        publica, filtrando por `alsa_input.`. Medido na mesa dela, com UM
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
        # O QUE O DAEMON ELEGEU para os DOIS é o nó da nossa ponte — inclusive
        # para o do cabo. É esta linha que a redação antiga lia.
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
        # O CENSO DE `/sys` É O ÚNICO PEDAÇO QUE UM TESTE NÃO PODE RODAR. O
        # casamento em si roda de verdade: `casar` compara os dois mapas.
        monkeypatch.setattr(
            eleicao_de_microfone, "casamento_usb_agora",
            lambda uniqs: CasamentoUSB(por_uniq={cabo: "3-2", radio: ""},
                                       por_no={nativo: "3-2"}))
        monkeypatch.setattr(
            a02.audio_saida, "rodar_leitura",
            lambda argv: longa if argv[0] == "pactl" else amixer)

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

    def test_o_pacote_nao_emite_o_ganho_antes_de_ela_publicar(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Enquanto a página publicada não tiver o trilho, o campo não sai.

        **O QUE A MORDIDA ARRANCA, E A PRIMEIRA REDAÇÃO NÃO ARRANCAVA NADA:**
        esta régua comparava `A_PAGINA_TEM_O_GANHO` com o mesmo arquivo de que
        a constante nasce — tautologia, e ela passava VERDE com a guarda
        removida da emissão (medido em 20/09/2026, trocando a condição por
        `if True`). Quem pergunta é o PACOTE, e é a ele que se pergunta agora:
        com a guarda baixa as três chaves não saem, com ela alta saem. Tire o
        `if A_PAGINA_TEM_O_GANHO else {}` e o primeiro bloco reprova nomeando
        as chaves que vazaram.

        A razão da guarda é que **publicar é ato dela**: emitir antes põe as
        três chaves em `orfaos` no casamento das dez, e o pacote passa a se
        reportar pintando o que não pinta.
        """
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

