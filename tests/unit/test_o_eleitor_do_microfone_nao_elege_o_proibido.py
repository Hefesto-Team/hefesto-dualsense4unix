#!/usr/bin/env python3
"""A RÉGUA DO ELEITOR: ele não pode eleger o que a régua ao lado proíbe.

O DEFEITO, medido em 01/09/2026 no log do `install.sh` da máquina dela:

    [wp-fix] fonte padrão reeleita para …DualSense…iec958-stereo
             (porta usável, critério do doctor)
    [wp-fix] FALHA: o MIC (alsa_input) do DualSense ainda é o ativo,
             com outra fonte disponível (drop-in não aplicou?)

Três passos do MESMO gesto se contradizendo: ele elege o DualSense, e reprova
porque o DualSense está eleito — acusando o drop-in, que estava certo.

O MECANISMO, e ele tem três camadas. Vale escrever as três, porque a segunda e
a terceira só apareceram depois de a primeira ser curada:

1. **O fallback do ranqueador.** `doctor.sh:_melhor_source_de_captura`, com
   `prefere=0`, faz ``escolha = (outro != "") ? outro : ds``. Com a webcam
   desconectada e a entrada analógica da placa-mãe filtrada por falta de porta
   usável, `outro` fica vazio — e ele cai no DualSense. O eleitor herdava esse
   fallback. **A cura é tirar o DualSense da lista ANTES de perguntar.**
2. **A lista não significava o próprio nome.** Com o item 1 curado, a lista
   ainda devolvia `…hdmi-stereo.monitor` e `…iec958-stereo.monitor`, porque
   quem descartava monitor era o ranqueador, lá na frente. O eleitor ficava
   certo; a régua `other_source_available`, que lê a lista CRUA, passava a
   contar dois monitores como "outras fontes disponíveis" e voltava a acusar o
   drop-in. **Uma lista vira duas verdades assim que ganha o segundo leitor.**
3. **O veredicto dependia do relógio.** `verify_active_not_dualsense` roda logo
   depois de `restart_wireplumber` e o laço dele só esperava o DualSense sair —
   qualquer outra resposta o interrompia, inclusive o `auto_null`, que é o nó
   que o PipeWire cria enquanto NADA está pronto. Medido: `--install` dizia
   "FALHA: a fonte padrão é um MONITOR (auto_null.monitor)"; cinco segundos
   depois a resposta era outra. **Mesmo estado, dois veredictos.**

O QUE ESTA RÉGUA COBRA, e ela cobra a FORMA para valer no próximo caso:

- o eleitor e a régua leem a MESMA lista (`fontes_elegiveis`);
- essa lista já exclui o DualSense e os monitores — quem a lê não precisa
  lembrar de filtrar;
- o laço de assentamento espera o `auto_null` passar;
- os três desfechos bons (eleito / só o DualSense / nem microfone) são
  DISTINTOS na tela do instalador. Dizer "fonte padrão reeleita" sobre uma
  eleição que não houve é a mentira que o `INSTALADOR-QUE-APROVOU-O-MONITOR-01`
  já tinha custado uma vez.

A MORDIDA: devolva o `_melhor_source_de_captura 0` cru ao eleitor, ou tire o
descarte de monitor da lista, ou encurte o laço — cada um reprova um caso.
"""
from __future__ import annotations

import pathlib
import re
import subprocess

import pytest

#: O nome REAL do nó do mic do DualSense no PipeWire, quebrado só para caber na
#: régua de 100 colunas. É dado de máquina, não texto: encurtá-lo faria o dublê
#: medir um nome que o produto nunca vê.
NO_DO_MIC = (
    "alsa_input.usb-Sony_Interactive_Entertainment_"
    "DualSense_Wireless_Controller-00.iec958-stereo"
)
#: A webcam dela — a fonte que o filtro TEM de deixar passar.
NO_DA_WEBCAM = "alsa_input.usb-046d_HD_Pro_Webcam_C920-02.analog-stereo"

RAIZ = pathlib.Path(__file__).resolve().parents[2]
FIX = RAIZ / "scripts" / "fix_wireplumber_default_source.sh"
DOCTOR = RAIZ / "scripts" / "doctor.sh"
INSTALL = RAIZ / "install.sh"


def _corpo(fonte: str, nome: str) -> str:
    """O corpo de uma função de bash, do `nome() {` até o `}` na coluna 0."""
    i = fonte.index(f"\n{nome}() {{")
    j = fonte.index("\n}", i)
    return fonte[i:j]


@pytest.fixture(scope="module")
def fix() -> str:
    return FIX.read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# 1. O eleitor não pode herdar o fallback do ranqueador
# --------------------------------------------------------------------------
def test_o_ranqueador_do_doctor_ainda_tem_o_fallback(fix: str) -> None:
    """A premissa desta régua, medida no código do doctor.

    Se um dia o `_melhor_source_de_captura` deixar de cair no DualSense, os
    casos abaixo continuam corretos mas param de ser necessários — e é bom que
    alguém saiba disso em vez de descobrir relendo tudo.
    """
    corpo = _corpo(DOCTOR.read_text(encoding="utf-8"), "_melhor_source_de_captura")
    assert 'escolha = (outro != "") ? outro : ds' in corpo, (
        "o fallback do ranqueador mudou de forma — releia esta régua inteira: "
        "ela existe porque `prefere=0` cai no DualSense quando não há outra"
    )


def test_a_lista_de_elegiveis_exclui_o_dualsense(fix: str) -> None:
    corpo = _corpo(fix, "fontes_elegiveis")
    assert "dualsense" in corpo.lower(), (
        "`fontes_elegiveis` não exclui o DualSense. Sem isso o ranqueador o "
        "elege por fallback, e o gesto passa a eleger o que ele mesmo proíbe."
    )


def test_a_lista_de_elegiveis_exclui_monitores(fix: str) -> None:
    corpo = _corpo(fix, "fontes_elegiveis")
    assert ".monitor" in corpo, (
        "`fontes_elegiveis` não descarta monitor. O ranqueador descarta lá na "
        "frente, então o ELEITOR fica certo — e a régua que lê a lista crua "
        "passa a contar monitor como fonte disponível."
    )


def test_o_eleitor_le_a_lista_e_nao_o_pactl_cru(fix: str) -> None:
    corpo = _corpo(fix, "pick_target_source_name")
    assert "fontes_elegiveis" in corpo, (
        "o eleitor voltou a montar a própria lista — é assim que ela diverge "
        "da que a régua lê"
    )


def test_a_regua_le_a_mesma_lista_do_eleitor(fix: str) -> None:
    corpo = _corpo(fix, "other_source_available")
    assert "fontes_elegiveis" in corpo, (
        "`other_source_available` voltou a contar linha de `wpctl status`. Isso "
        "inclui fonte SEM porta usável, e é o que fazia o gesto acusar o "
        "drop-in de não ter aplicado quando ele tinha aplicado."
    )


# --------------------------------------------------------------------------
# 2. O veredicto não pode depender do relógio
# --------------------------------------------------------------------------
def test_o_laco_espera_o_auto_null_passar(fix: str) -> None:
    corpo = _corpo(fix, "verify_active_not_dualsense")
    assert "e_o_nada_do_pipewire" in corpo, (
        "o laço de assentamento não conhece o `auto_null` — ele vai julgar o "
        "grafo antes de o WirePlumber reeleger, e o mesmo estado vai dar "
        "veredictos diferentes conforme a hora em que se olhou"
    )


def test_o_auto_null_e_reconhecido_pelo_prefixo(fix: str) -> None:
    """`auto_null` é o nome do nó; `auto_null.monitor` é o monitor dele.

    Os dois significam a mesma coisa aqui — "nada está pronto" —, e por isso a
    checagem é por PREFIXO. Casar só o nome exato deixaria o `.monitor` passar,
    que foi justamente a forma que apareceu na tela dela.
    """
    corpo = _corpo(fix, "e_o_nada_do_pipewire")
    assert "auto_null*" in corpo, (
        "a checagem do `auto_null` deixou de ser por prefixo — o "
        "`auto_null.monitor` volta a passar"
    )


def test_o_orcamento_do_laco_cobre_o_restart(fix: str) -> None:
    """~2s não cobria o WirePlumber reeleger depois de um restart. Medido: ~5s."""
    corpo = _corpo(fix, "verify_active_not_dualsense")
    voltas = re.search(r"seq 1 (\d+)", corpo)
    assert voltas is not None, "o laço deixou de declarar quantas voltas dá"
    assert int(voltas.group(1)) >= 20, (
        f"o laço caiu para {voltas.group(1)} voltas (~{int(voltas.group(1)) * 0.25:.1f}s). "
        "Medido em 01/09: o WirePlumber leva ~5s para reeleger depois do restart, "
        "e julgar antes disso lê o `auto_null` transitório."
    )


# --------------------------------------------------------------------------
# 3. O instalador tem de distinguir os desfechos
# --------------------------------------------------------------------------
def test_o_instalador_distingue_escassez_de_eleicao() -> None:
    """Dizer "fonte padrão reeleita" sobre uma eleição que não houve é mentira."""
    fonte = INSTALL.read_text(encoding="utf-8")
    # O chamador que RELATA o desfecho — o que imprime as frases do drop-in.
    # Há mais de um `--install` no instalador; os outros são cobertos pelo caso
    # seguinte, que cobra o tratamento do rc em TODOS.
    i = fonte.index("drop-in do WirePlumber instalado")
    trecho = fonte[max(0, i - 1500) : i + 1500]
    assert 'case "${rc:-0}" in' in trecho, (
        "o instalador voltou a tratar todo rc não-1 como sucesso de eleição — "
        "o rc 2 (o DualSense é a única fonte) cairia no `else` e a tela diria "
        "'fonte padrão reeleita'"
    )
    assert "ÚNICA fonte" in trecho, "o desfecho de escassez não tem frase própria"


def test_escassez_nao_manda_ela_rodar_o_mesmo_comando_de_novo() -> None:
    """rc 2 e rc 3 são o ESTADO da máquina, não falha do gesto.

    Mandar rodar de novo um comando que fará exatamente o mesmo é o laço que
    esta leva curou.
    """
    fonte = INSTALL.read_text(encoding="utf-8")
    for m in re.finditer(r'fix_wireplumber_default_source\.sh" --install', fonte):
        trecho = fonte[max(0, m.start() - 600) : m.start() + 900]
        assert "-ne 1" in trecho or "-eq 1" in trecho, (
            "um chamador do `--install` voltou a usar `||`, que trata rc 2 e 3 "
            "como falha e manda ela repetir o comando à toa"
        )


# --------------------------------------------------------------------------
# 4. A prova de COMPORTAMENTO: mesma entrada, mesma saída
# --------------------------------------------------------------------------
def test_o_filtro_de_verdade_exclui_o_que_promete(tmp_path) -> None:
    """Roda a `fontes_elegiveis` REAL contra um `pactl` de mentira.

    Medir uma cópia do filtro escrita aqui provaria só que eu sei copiar. O
    dublê troca as duas coisas de fora — o `pactl` e o doctor — e deixa a
    função do produto rodar inteira.

    E mede IDEMPOTÊNCIA no que dá para medir sem tocar no áudio dela: mesma
    entrada, três execuções, uma resposta só.
    """
    curta = (
        "1021\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\ts32le 2ch\tSUSPENDED\n"
        f"1027\t{NO_DO_MIC}\tPipeWire\ts32le 2ch\tSUSPENDED\n"
        f"1030\t{NO_DA_WEBCAM}\tPipeWire\ts16le 2ch\tSUSPENDED\n"
    )
    falso_bin = tmp_path / "bin"
    falso_bin.mkdir()
    (falso_bin / "pactl").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *short* ]]; then cat "$PACTL_CURTA"; else echo "(longo)"; fi\n',
        encoding="utf-8",
    )
    (falso_bin / "pactl").chmod(0o755)
    # O doctor de mentira: `_sources_com_porta_usavel` passa tudo adiante, para
    # que o que sobrar seja exatamente o que ESTA função exclui.
    doutor = tmp_path / "doctor.sh"
    doutor.write_text("_sources_com_porta_usavel() { cat; }\n", encoding="utf-8")
    entrada = tmp_path / "curta.txt"
    entrada.write_text(curta, encoding="utf-8")

    roteiro = tmp_path / "roda.sh"
    roteiro.write_text(
        "set -uo pipefail\n"
        f'DOCTOR_SH="{doutor}"\n'
        f'export PATH="{falso_bin}:$PATH" PACTL_CURTA="{entrada}"\n'
        f"source <(sed -n '/^fontes_elegiveis()/,/^}}/p' '{FIX}')\n"
        "fontes_elegiveis\n",
        encoding="utf-8",
    )

    saidas = set()
    for _ in range(3):
        r = subprocess.run(["bash", str(roteiro)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        saidas.add(r.stdout)
    assert len(saidas) == 1, f"a função devolveu {len(saidas)} respostas para a mesma entrada"
    (unica,) = saidas
    assert "C920" in unica, (
        f"a webcam — a única elegível desta entrada — sumiu do filtro: {unica!r}"
    )
    assert "DualSense" not in unica, f"o DualSense passou: {unica!r}"
    assert ".monitor" not in unica, f"um monitor passou: {unica!r}"


def test_sem_elegivel_a_funcao_devolve_vazio_e_nao_erro(tmp_path) -> None:
    """Vazio COM exit 0 é "consultei e não há". É o que o chamador espera.

    Se ela devolvesse erro, o `pick_target_source_name` cairia no caminho antigo
    do `wpctl` — o que não filtra porta — e o defeito voltaria por baixo.
    """
    curta = (
        f"1027\t{NO_DO_MIC}\tPipeWire\ts32le\tSUSPENDED\n"
        "1021\talsa_output.pci-0000_0a_00.1.hdmi-stereo.monitor\tPipeWire\ts32le\tSUSPENDED\n"
    )
    falso_bin = tmp_path / "bin"
    falso_bin.mkdir()
    (falso_bin / "pactl").write_text(
        "#!/usr/bin/env bash\n"
        'if [[ "$*" == *short* ]]; then cat "$PACTL_CURTA"; else echo "(longo)"; fi\n',
        encoding="utf-8",
    )
    (falso_bin / "pactl").chmod(0o755)
    doutor = tmp_path / "doctor.sh"
    doutor.write_text("_sources_com_porta_usavel() { cat; }\n", encoding="utf-8")
    entrada = tmp_path / "curta.txt"
    entrada.write_text(curta, encoding="utf-8")
    roteiro = tmp_path / "roda.sh"
    roteiro.write_text(
        "set -uo pipefail\n"
        f'DOCTOR_SH="{doutor}"\n'
        f'export PATH="{falso_bin}:$PATH" PACTL_CURTA="{entrada}"\n'
        f"source <(sed -n '/^fontes_elegiveis()/,/^}}/p' '{FIX}')\n"
        "fontes_elegiveis\n",
        encoding="utf-8",
    )
    r = subprocess.run(["bash", str(roteiro)], capture_output=True, text=True)
    assert r.returncode == 0, f"devolveu erro em vez de vazio: {r.stderr}"
    assert r.stdout.strip() == "", f"sobrou algo que não devia: {r.stdout!r}"
