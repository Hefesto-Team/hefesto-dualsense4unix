"""A TRAVA MANUAL SAIU — o perfil aplica tudo, para qualquer jogo.

DECISÃO DELA, 14/09/2026 (`D-1409-A-TRAVA-MANUAL-SAI-O-PERFIL-APLICA-TUDO`),
com estas palavras, em três mensagens seguidas:

    *"eu tinha pedido pra remover todas as travas manuais pra esse jogo, madjack  # noqa-acento: citação literal dela
     e pro pragmata e pro wokong"*
    *"e pra qualquer outro jogo"*
    *"isso nao faz sentido mais."*  # noqa-acento: citação literal dela

O QUE ESTE ARQUIVO MEDIA ANTES, e por que ele mudou de pergunta em vez de sumir:
ele era a régua da A-TRAVA-QUE-NINGUÉM-SOLTA-01 (29/08/2026), que mediu o teto de
ociosidade de seis horas — a única porta de saída de `led` e de `audio`, as duas
categorias que armavam e que gesto nenhum soltava. Aquela medição continua certa
sobre o que mediu; o que caducou é o mecanismo inteiro que ela vigiava. Um
arquivo apagado deixaria a próxima pessoa reintroduzindo a trava sem encontrar
uma linha sobre o preço dela — então ele fica, medindo a AUSÊNCIA.

O SINTOMA QUE FECHOU A DECISÃO, medido no journal dela em 14/09 às 22:58:34, com
o Sackboy abrindo e o perfil do jogo entrando:

    launch_perfil_ativado  appid=1599660  profile='Sackboy™: A Big Adventure'
      secoes={'trigger': 'ignorado_trava_manual', 'led': 'ignorado_trava_manual',
              'mode': 'aplicado', 'rumble_policy': 'aplicado', …}

Ela tinha ajustado luz e gatilho pela interface às 22:56 — e o perfil foi SALVO
com os dois, três vezes, `origem=interface-nova` no diário da janela. Dois
minutos depois o jogo abriu e o produto pulou exatamente as duas seções que ela
acabara de gravar. Para ela isso se lê como *"ao iniciar o jogo ele não carrega o
perfil do jogo"* e *"os gatilhos tambem nao tao aplicando"*, e nenhuma das duas  # noqa-acento: citação literal dela
frases fala em trava — porque a trava nunca chegou à tela.

POR QUE A TRAVA DEIXOU DE FAZER SENTIDO, e a razão é a que sustenta a decisão:
ela protegia o ajuste da mão dela CONTRA o perfil, num mundo em que o ajuste não
ia para o perfil. A interface nova grava a cada gesto (decisão dela, *"clicar já
aplica e já grava"*), então o que ela ajusta já está no arquivo — e o perfil
aplicando é exatamente o que respeita o ajuste dela. A trava passou a proteger o
ajuste contra quem o guarda.

O QUE ESTA RÉGUA MORDE, e são as duas direções:

1. **o comportamento** — o `ProfileManager.apply` escreve gatilho e luz mesmo com
   um store que afirme qualquer coisa sobre trava, e o relatório da ativação não
   traz a palavra `ignorado_trava_manual` para seção nenhuma;
2. **a volta do mecanismo** — nenhuma linha de `src/` chama `mark_*`/`clear_*`
   nem lê `manual_override_categories`, e o `StateStore` não tem os métodos.

A SEGUNDA É A QUE IMPEDE A REINTRODUÇÃO EM PEDAÇOS, que é como ela voltaria: um
`mark_` num handler novo não muda nenhum teste de comportamento no dia em que é
escrito — ele só cobra o preço meses depois, num jogo que ela abre.

O QUE SAIU JUNTO, e está escrito aqui para quem procurar os arquivos:

* `tests/unit/test_toda_categoria_de_trava_tem_par.py` (06/09/2026, 12 testes) —
  ele varria `src/` por AST e cobrava que toda categoria de
  `MANUAL_OVERRIDE_CATEGORIES` tivesse quem a armasse E quem a soltasse. Nasceu
  da A-TRAVA-DO-LED-NÃO-SOLTA-01, e media o mecanismo inteiro: sem ele, não sobra
  o que medir. **O censo que o motivou fica no topo deste arquivo.**
* `tests/unit/test_onda_u_trava_por_categoria.py` (20 testes) — a quebra do
  booleano único em quatro categorias, para que o fim do "Testar motores" não
  apagasse um gatilho deliberado de outra aba (ONDA-U/F1).
* `tests/unit/test_onda_u_causa_a_trava_manual.py` (11 testes) — os caminhos que
  armavam sem passar pelo `trigger.set`: o "Aplicar" da janela e os handlers de
  luz e vibração (ONDA-U, Causa A).
* `tests/unit/test_trava_que_solta_tarde_01.py` (7 testes) — a ORDEM entre soltar
  a trava e aplicar o perfil, medida ao vivo em 05/08/2026 na máquina dela: os
  dois gestos explícitos estavam invertidos e o perfil entrava antes de a trava
  sair.
* `tests/unit/test_perfil_respeita_trava_manual.py` (6 testes) — **o par exato
  desta decisão.** Ele guardava o pedido dela de 23/07/2026, *"o sackboy deveria
  ser trava manual também"*, que é o pedido que ela revogou hoje, pelo mesmo
  jogo. Os dois lados do mesmo assunto, com sete semanas entre eles.
* `TestTravaManualAudio`, em `test_som_02_devolucao_da_posse.py` (6 testes) — a
  quarta categoria, a do `speaker.set`.
* `test_relatorio_registra_as_categorias_travadas_na_mao`, em
  `test_perfil_reescrito_na_partida_01.py` — virou o teste da ausência, no mesmo
  arquivo.

O QUE **NÃO** SAIU, e a régua o afirma para ninguém removê-lo junto:
`mark_manual_profile_lock` / `manual_profile_lock_active`
(`state_store.MANUAL_PROFILE_LOCK_SEC`, 30 s). É outro mecanismo — guarda a
escolha manual de PERFIL contra uma troca de janela no segundo seguinte —, expira
sozinho e nunca silenciou seção nenhuma.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from hefesto_dualsense4unix.daemon.state_store import StateStore
from hefesto_dualsense4unix.profiles.manager import ProfileManager
from hefesto_dualsense4unix.profiles.schema import (
    LedsConfig,
    MatchCriteria,
    Profile,
    TriggerConfig,
    TriggersConfig,
)
from hefesto_dualsense4unix.testing import FakeController

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SRC = RAIZ / "src" / "hefesto_dualsense4unix"

#: Os nomes do mecanismo que saiu. Procurados como CHAMADA (`nome(`) e como
#: acesso de atributo (`.nome`), nunca como substring solta: a prosa desta casa
#: cita o mecanismo em dezenas de comentários datados, e uma régua que contasse
#: citação reprovaria o registro histórico que ela mesma pede que se escreva.
MORTOS = ("mark_manual_trigger_active", "clear_manual_trigger_active",
          "manual_override_categories", "manual_trigger_active")

#: O irmão que FICA. Ele entra na régua para que "limpar o que sobrou da trava"
#: não o leve junto num varrer de arquivo.
VIVO = "manual_profile_lock_active"


class _ControleQueAnota(FakeController):
    """O `FakeController` da casa, com o `OutputSpec` guardado.

    O dublê da suíte não guarda o spec — ele tem `last_led` e `last_player_leds`,
    que são o resultado dos setters individuais, e a trava agia UM andar acima
    deles: ela mandava `None` no campo do `OutputSpec`, e um `None` nunca chega a
    setter nenhum. Medir pelo `last_led` diria "a luz não mudou" tanto para a
    trava viva quanto para um perfil sem cor — dois fatos com a mesma cara, que é
    o que esta casa persegue. O spec é o único lugar onde os dois se separam.
    """

    def __init__(self, *a: object, **k: object) -> None:
        super().__init__(*a, **k)  # type: ignore[arg-type]
        self.specs: list[object] = []

    def apply_output_defaults(self, spec: object) -> None:
        self.specs.append(spec)


def _perfil_com_gatilho_e_luz() -> Profile:
    """Um perfil de jogo, com as duas seções que a trava silenciava."""
    return Profile(
        name="jogo-de-prova",
        match=MatchCriteria(window_class=["steam_app_1599660"]),
        priority=80,
        triggers=TriggersConfig(
            left=TriggerConfig(mode="Rigid", params=[5, 200]),
            right=TriggerConfig(mode="Rigid", params=[5, 200]),
        ),
        leds=LedsConfig(lightbar=(255, 0, 128)),
    )


def _codigo_de_producao() -> list[tuple[pathlib.Path, str]]:
    return [(p, p.read_text(encoding="utf-8")) for p in sorted(SRC.rglob("*.py"))]


def _linhas_de_codigo(texto: str) -> list[tuple[int, str]]:
    """As linhas que são CÓDIGO: fora de comentário e fora de docstring.

    A varredura é grosseira de propósito — ela não precisa de um parser, precisa
    não confundir prosa com chamada. Toda linha cujo primeiro caractere não-branco
    é `#` sai; o resto é olhado por `nome(` e `.nome`, que é a forma que uma
    chamada tem e uma citação em prosa não.
    """
    dentro = False
    fora: list[tuple[int, str]] = []
    for n, linha in enumerate(texto.splitlines(), 1):
        aspas = linha.count('"""') + linha.count("'''")
        if dentro:
            if aspas:
                dentro = False
            continue
        if aspas % 2:
            dentro = True
            continue
        if linha.lstrip().startswith("#"):
            continue
        fora.append((n, linha))
    return fora


# ---------------------------------------------------------------------------
# 1. O COMPORTAMENTO — o perfil escreve gatilho e luz, e não pula seção
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("origem", ["launch", "autoswitch", "manual", "boot"])
def test_o_perfil_aplica_gatilho_e_luz_em_toda_origem(origem: str) -> None:
    """A queixa dela era com `origin="launch"`; a decisão é para todas.

    As quatro origens entram porque a trava não distinguia nenhuma delas — ela
    silenciava a seção, viesse o perfil de onde viesse. Uma régua só com `launch`
    deixaria a reintrodução passar pelo caminho do autoswitch, que é por onde o
    perfil entra quando ela troca de janela.
    """
    fc = _ControleQueAnota()
    manager = ProfileManager(controller=fc, store=StateStore())
    relatorio: dict[str, str] = {}

    manager.apply(_perfil_com_gatilho_e_luz(), origin=origem, relatorio=relatorio)

    assert fc.specs, (
        "a ativação não chamou `apply_output_defaults` — o perfil não escreveu nada"
    )
    spec = fc.specs[-1]
    assert spec.trigger_left is not None and spec.trigger_right is not None, (
        f"a seção `triggers` do perfil não chegou ao controle na origem {origem!r}: "
        f"é o `ignorado_trava_manual` de volta, e é a queixa dela de 14/09 — "
        f"*«os gatilhos tambem nao tao aplicando»*"  # noqa-acento: citação literal dela
    )
    assert spec.led is not None, (
        f"a seção `leds` do perfil não chegou ao controle na origem {origem!r}"
    )
    assert "ignorado_trava_manual" not in relatorio.values(), (
        f"o relatório da ativação voltou a dizer `ignorado_trava_manual`: "
        f"{relatorio!r}. Nenhuma seção é silenciada por trava desde 14/09/2026"
    )
    for secao in ("trigger", "led"):
        assert relatorio.get(secao) not in (None, "ignorado_trava_manual"), (
            f"a seção {secao!r} sumiu do relatório da ativação — a ausência de "
            f"notícia lida como 'não entrou' é o ELO-MUDO-01, e ela custou uma sprint"
        )


def test_o_store_nao_sabe_mais_travar() -> None:
    """O dono da trava não a tem, e o irmão de 30 s continua lá.

    MORDIDA: devolver `mark_manual_trigger_active` ao `StateStore` reprova aqui
    antes de qualquer outro teste, que é onde a reintrodução começaria.
    """
    store = StateStore()
    for morto in MORTOS:
        assert not hasattr(store, morto), (
            f"`StateStore.{morto}` voltou. A trava manual saiu inteira em "
            f"14/09/2026 por decisão dela — ver o topo deste arquivo"
        )
    assert hasattr(store, VIVO), (
        f"`StateStore.{VIVO}` sumiu. Ele NÃO é a trava manual: é o lock de 30 s "
        f"da escolha manual de perfil, e a decisão dela não o alcança"
    )


# ---------------------------------------------------------------------------
# 2. A VOLTA DO MECANISMO — nenhuma linha de produção o chama
# ---------------------------------------------------------------------------

def test_nenhuma_linha_de_producao_arma_a_trava() -> None:
    """A régua que impede a volta em pedaços.

    Ela olha CHAMADA e ACESSO (`nome(` e `.nome`), e nunca a prosa: os
    comentários datados que contam por que a trava saiu citam os quatro nomes de
    propósito, e reprová-los seria a régua proibindo o registro que esta casa
    exige. É a armadilha que já pegou esta casa três vezes em três dias — *um
    comentário que descreve o padrão proibido vira a primeira ocorrência dele*.
    """
    achados: list[str] = []
    for caminho, texto in _codigo_de_producao():
        for numero, linha in _linhas_de_codigo(texto):
            for morto in MORTOS:
                if f"{morto}(" in linha or f".{morto}" in linha:
                    rel = caminho.relative_to(RAIZ).as_posix()
                    achados.append(f"  {rel}:{numero}  {linha.strip()[:90]}")
    assert not achados, (
        "a trava manual voltou ao código de produção:\n"
        + "\n".join(achados)
        + "\n\nEla saiu inteira em 14/09/2026 por decisão dela — *«e pra qualquer "
          "outro jogo»*, *«isso nao faz sentido mais»*. Se um caminho novo precisa "  # noqa-acento: citação literal dela
          "proteger um ajuste dela contra o perfil, a pergunta a fazer é outra: "
          "por que o ajuste não está NO perfil?"
    )


def test_as_constantes_da_trava_nao_voltaram() -> None:
    """As duas constantes que descreviam o mecanismo, e o teto que o prorrogava."""
    texto = (SRC / "daemon" / "state_store.py").read_text(encoding="utf-8")
    for numero, linha in _linhas_de_codigo(texto):
        for constante in ("MANUAL_OVERRIDE_CATEGORIES", "MANUAL_OVERRIDE_STALE_AFTER_SEC"):
            assert not re.match(rf"\s*{constante}\s*[:=]", linha), (
                f"`{constante}` voltou a `state_store.py:{numero}`. Ela declarava "
                f"as categorias da trava e o teto de seis horas que era a única "
                f"porta de saída de `led` e `audio` — as duas saíram com o "
                f"mecanismo em 14/09/2026"
            )
    assert "MANUAL_PROFILE_LOCK_SEC" in texto, (
        "`MANUAL_PROFILE_LOCK_SEC` sumiu do `state_store.py`. Ele é o lock de 30 s "
        "da escolha manual de perfil, e fica"
    )
