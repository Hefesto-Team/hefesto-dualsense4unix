#!/usr/bin/env python3
"""A RÉGUA DA 01-JOGAR: lugar sem aparelho não oferece gesto — e o cheio oferece.

A DECISÃO É DE PRODUTO, 31/08/2026: *um lugar sem aparelho não oferece gesto nenhum*.
Um chip clicável numa coluna sem controle ou não faz nada — e mente — ou faz
alguma coisa no controle errado, que é pior.

O DEFEITO, achado por um conferente adversarial em 07/09/2026 e CONFIRMADO aqui
em Chrome de verdade, na página PUBLICADA, com `elementFromPoint` no centro de
cada ``[data-gesto]``::

    p1 (cheio)  3 gestos · 3 com caixa > 0 · 3 CLICÁVEIS
    p2 (cheio)  3 gestos · 3 com caixa > 0 · 3 CLICÁVEIS
    p3 (VAZIO)  3 gestos · 3 com caixa > 0 · 3 CLICÁVEIS   ← e ninguém pediu
    p4 (VAZIO)  3 gestos · 3 com caixa > 0 · 3 CLICÁVEIS   ← idem

POR QUE A REDE DA CASA NÃO OS PEGAVA, e não é falha dela: a S-04 da folha das
dez abas (``monta.py:544``) mira ``button, input, select, textarea,
[contenteditable]``, e o chip de máscara desta aba é um ``<span>`` — nenhum dos
cinco. A ``aba01.py`` tinha, sobre o lugar vazio, meia cura de 30/08: tirava o
``cursor`` e o ``:hover`` do chip e chamava isso de *"não se clicam"*. TINTA, e
não ATO — a caixa continuava lá e o clique continuava chegando.

**POR QUE ESTA RÉGUA VIVE EM ``tests/unit/`` E NÃO NA AUTO-CHECAGEM DA ABA.** A
``aba01.py`` já tem quinze ``exigir()`` no ``_conferir``, e eles só rodam com
``python aba01.py`` — quem não regenerar a página não roda nenhum. Uma régua que
depende de alguém lembrar de a chamar não protege ninguém; foi exatamente o que
o mesmo conferente derrubou na aba 04. Esta entra na tabela do
``scripts/portoes.sh`` (``gesto-em-lugar-vazio``) e roda na integração.

**ELA LÊ, NÃO DIGITA.** Nenhum seletor de CSS está afirmado aqui. A régua gera a
página pelo gerador de verdade, abre no Chrome e pergunta ao MOTOR o que ele
desenha. Uma regra digitada aqui mediria este arquivo, e não a tela — é a
família de defeito que esta casa pagou onze vezes em 26/08.

**OS DOIS SENTIDOS, e é o par que nenhuma metade sozinha prova:**

1. **ESCONDIDO NO VAZIO** — ``data-conectado="nao"``: nenhum ``[data-gesto]``
   com caixa maior que zero, nenhum recebendo clique.
2. **VISÍVEL NO CHEIO** — ``data-conectado="sim"``: TODOS com caixa e TODOS
   recebendo clique. E não só como o arquivo nasce: a régua faz o que o piloto
   faz no passo ``1c`` (``hefesto_vivo.py:1133``) — vira a marca para ``"sim"``
   **sem recarregar a página** — e cobra que os três chips do P3 e do P4 voltem
   no mesmo tique. É o estado da bancada, que está com os quatro DualSense
   agora; o piloto vira marca e escreve campo, ele não materializa widget.

E O PASSO ``1b`` TAMBÉM (``hefesto_vivo.py:1108``): a régua esvazia o P1 ao vivo
e cobra que os gestos dele sumam. Sem isto a cura poderia ser um estado inicial
sortudo em vez de uma regra que segue a mesa.

**O ENDEREÇO NÃO PODE SUMIR**, e é a terceira metade: curar apagando o
``data-gesto`` do lugar vazio faria o chip voltar MUDO quando o controle
chegasse — o defeito que a `_chips_de_mascara` fechou em 03/09. Um teste sem
navegador cobra os doze chips no HTML.

NOTA DATADA, 28/10/2026 (A-JOGAR-SE-PUBLICA-COM-OS-CONTROLES-E-A-02-SAI-01): o cartão
com os chips de máscara saiu da Jogar, e os lugares dela são os da seção Controles, a que
morava na 02. A régua mede os gestos de cada lugar com a gaveta dele aberta (`#c-pN`), porque
só a gaveta aberta mostra os gestos do miolo; o endereço que o HTML guarda é o do touchpad.

A MORDIDA (28/10/2026): são duas camadas, e só as duas juntas devolvem o gesto ao vazio. Na
página publicada, troque o `display:none` da folha S-04 (`CSS_FOLHA` da `monta.py`) e apague as
regras do `_fechado_de_vez` da `aba02.py`: reprovam o lugar vazio, o desenho e o passo `1b`.
Uma camada só não morde, e é a outra que segura.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE), str(RAIZ / "scripts")):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

import chrome_sem_rede

CHROME = pathlib.Path("/usr/bin/google-chrome")

PAGINA = "01-jogar.html"


def _gerar(destino: pathlib.Path) -> pathlib.Path:
    """A página da aba 01 que o produto renderiza, copiada para um lar de mentira."""
    import onde

    alvo = destino / PAGINA
    alvo.write_text(onde.pagina(PAGINA, publicado=True).read_text(encoding="utf-8"),
                    encoding="utf-8")
    return alvo


O_QUE_O_NAVEGADOR_DESENHA = r"""
(() => {
  const medir = () => {
    const saida = {};
    for (const bloco of document.querySelectorAll('.quadro.estica [data-controle]')) {
      const quem = bloco.dataset.controle || '';
      if (!/^p[0-9]+$/.test(quem)) continue;  // (noqa-acento) `data-controle` é atributo HTML
      const gaveta = document.getElementById('c-' + quem);
      if (gaveta) gaveta.checked = true;
      const gestos = [];
      for (const el of bloco.querySelectorAll('[data-gesto]')) {
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        const caixa = r.width > 0 && r.height > 0;
        let pega = false;
        if (caixa) {
          const em = document.elementFromPoint(r.x + r.width / 2,
                                               r.y + r.height / 2);
          pega = !!em && (em === el || el.contains(em));
        }
        gestos.push({
          gesto: el.dataset.gesto,
          rotulo: (el.textContent || '').trim().slice(0, 30),
          largura: +r.width.toFixed(1), altura: +r.height.toFixed(1),
          caixa: caixa,
          desenhado: caixa && cs.visibility !== 'hidden',
          oferecido: caixa && pega && cs.visibility !== 'hidden'
                     && cs.pointerEvents !== 'none',
        });
      }
      saida[quem] = {conectado: bloco.dataset.conectado || '', gestos: gestos};
    }
    return saida;
  };
  // O PASSO 1c DO PILOTO, letra por letra (`hefesto_vivo.py:1133`): a marca
  // vira e a classe sai. NENHUM nó é criado — é justamente o ponto.
  const encher = (quem) => {
    for (const el of document.querySelectorAll('[data-controle="' + quem + '"]')) {
      el.dataset.conectado = 'sim';
      el.classList.remove('off');
    }
  };
  // E O PASSO 1b (`hefesto_vivo.py:1108`), que é o simétrico.
  const esvaziar = (quem) => {
    for (const el of document.querySelectorAll('[data-controle="' + quem + '"]')) {
      el.dataset.conectado = 'nao';  // (noqa-acento) o valor, não a palavra
      el.classList.add('off');
    }
  };
  const comoNasce = medir();
  encher('p3'); encher('p4');
  const depoisDo1c = medir();
  esvaziar('p1');
  const depoisDo1b = medir();
  return {como_nasce: comoNasce, depois_do_1c: depoisDo1c,
          depois_do_1b: depoisDo1b};
})()
"""


def abrir_e_medir(arquivo: pathlib.Path) -> dict:
    """Abre a página SEM a rede e devolve o que o Chrome desenha nos três estados."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(
            executable_path=str(CHROME), args=["--no-sandbox"])
        try:
            pg, _recusadas = chrome_sem_rede.abrir_sem_rede(
                navegador, arquivo.as_uri(), largura=1280, altura=900)
            saida = pg.evaluate(O_QUE_O_NAVEGADOR_DESENHA)
        finally:
            navegador.close()
    return dict(saida)


@pytest.fixture(scope="module")
def medido(tmp_path_factory: pytest.TempPathFactory) -> dict:
    """O que o Chrome desenha, nos três estados — uma abertura para todos."""
    if not CHROME.exists():
        pytest.skip("sem o Chrome do sistema — a régua não tem motor")
    return abrir_e_medir(_gerar(tmp_path_factory.mktemp("jogar")))


def _lugares(estado: dict, marca: str) -> dict:
    """Os lugares de um estado cuja marca de conexão é `marca` (o cheio nasce sem ela)."""
    if marca == "sim":
        return {q: d for q, d in estado.items() if d["conectado"] in ("sim", "")}
    return {q: d for q, d in estado.items() if d["conectado"] == marca}


def _acusar(quem: str, g: dict) -> str:
    return (f'{quem} · gesto `{g["gesto"]}` ("{g["rotulo"]}") continua com '
            f'caixa {g["largura"]}x{g["altura"]} e RECEBE clique num lugar '
            f"sem aparelho")


def test_a_pagina_tem_os_quatro_lugares_e_gestos_em_todos(medido: dict) -> None:
    """Quatro lugares, e nenhum deles sem gesto — senão a régua mede o vazio."""
    nasce = medido["como_nasce"]
    assert sorted(nasce) == ["p1", "p2", "p3", "p4"], sorted(nasce)
    vazios = _lugares(nasce, "nao")  # (noqa-acento)
    assert len(vazios) == 2, "a mesa do desenho tem 2 lugares vazios"
    assert len(_lugares(nasce, "sim")) == 2, "a mesa do desenho tem 2 cheios"
    for quem, d in nasce.items():
        assert d["gestos"], (
            f"{quem} não tem um único `data-gesto` — ou a régua está medindo "
            f"outra coisa, ou o endereço do gesto sumiu do HTML e o chip vai "
            f"voltar MUDO quando o controle chegar")


def test_o_lugar_vazio_nao_oferece_gesto(medido: dict) -> None:
    """Um lugar sem aparelho não oferece gesto nenhum. Nem um."""
    culpados = [
        _acusar(quem, g)
        for quem, d in _lugares(medido["como_nasce"], "nao").items()  # (noqa-acento)
        for g in d["gestos"] if g["oferecido"]
    ]
    assert not culpados, (
        "DECISÃO DELA DESFEITA (31/08/2026) — um chip clicável numa coluna sem "
        "controle ou não faz nada, e mente, ou faz alguma coisa no controle "
        "errado:\n  - " + "\n  - ".join(culpados))


def test_o_lugar_vazio_nem_desenha_o_gesto(medido: dict) -> None:
    """E não é só o clique: o chip não se desenha."""
    desenhados = [
        f'{quem} · `{g["gesto"]}` ("{g["rotulo"]}") em {g["largura"]}x{g["altura"]}'
        for quem, d in _lugares(medido["como_nasce"], "nao").items()  # (noqa-acento)
        for g in d["gestos"] if g["desenhado"]
    ]
    assert not desenhados, (
        "o gesto do lugar vazio está DESENHADO — inerte é melhor que clicável e "
        "pior que ausente, porque a caixa continua prometendo uma escolha:\n  - "
        + "\n  - ".join(desenhados))


def test_o_lugar_cheio_oferece_o_gesto(medido: dict) -> None:
    """No lugar COM aparelho, todo gesto tem caixa e recebe clique."""
    mudos = [
        f'{quem} · `{g["gesto"]}` ("{g["rotulo"]}") '
        f'caixa={g["largura"]}x{g["altura"]} oferecido={g["oferecido"]}'
        for quem, d in _lugares(medido["como_nasce"], "sim").items()
        for g in d["gestos"] if not g["oferecido"]
    ]
    assert not mudos, (
        "a cura do lugar vazio comeu o gesto de um lugar que TEM controle — a "
        "cena que ela aprovou tem os dois lugares cheios com os gestos na gaveta:\n"
        "  - " + "\n  - ".join(mudos))


def test_o_passo_1c_do_piloto_devolve_o_gesto_sem_recarregar(medido: dict) -> None:
    """Ela está com os QUATRO na mesa: o P3 chega e o chip volta no mesmo tique."""
    depois = medido["depois_do_1c"]
    for quem in ("p3", "p4"):
        assert depois[quem]["conectado"] == "sim", depois[quem]
        mudos = [f'`{g["gesto"]}` ("{g["rotulo"]}")'
                 for g in depois[quem]["gestos"] if not g["oferecido"]]
        assert not mudos, (
            f"{quem} recebeu um controle (passo `1c` do piloto) e os gestos "
            f"continuam sem caixa ou sem clique, sem recarregar a página: "
            + ", ".join(mudos))
        assert len(depois[quem]["gestos"]) == len(
            medido["como_nasce"][quem]["gestos"]), (
            f"{quem} mudou de número de gestos ao encher — a marca não pode "
            f"criar nem destruir endereço")


def test_o_passo_1b_do_piloto_recolhe_o_gesto_sem_recarregar(medido: dict) -> None:
    """E o simétrico: quem SAI da mesa deixa de oferecer, ao vivo."""
    depois = medido["depois_do_1b"]
    assert depois["p1"]["conectado"] == "nao", depois["p1"]  # (noqa-acento)
    culpados = [_acusar("p1", g) for g in depois["p1"]["gestos"] if g["oferecido"]]
    assert not culpados, (
        "o P1 perdeu o controle ao vivo e continua oferecendo gesto:\n  - "
        + "\n  - ".join(culpados))


def test_o_endereco_do_gesto_continua_no_html(tmp_path: pathlib.Path) -> None:
    """O touchpad de cada lugar continua no arquivo, cheio ou vazio."""
    import monta

    corpo = _gerar(tmp_path).read_text()
    esperado = len(monta.MESA)
    achado = corpo.count('data-gesto="touchpad"')
    assert achado == esperado, (
        f"o HTML tem {achado} interruptores de touchpad com endereço e devia ter "
        f"{esperado}, um por lugar. Quem esconde o gesto do lugar vazio é o CSS, pela marca "
        f"`data-conectado`; apagar o endereço faz o gesto voltar mudo quando o controle chegar")
