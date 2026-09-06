#!/usr/bin/env python3
"""A coluna Atenção: até três, o mais grave em cima, e o `+N` do que não coube.

DECISÃO DELA — 04/09/2026, D-09: *"Até três linhas, o mais grave em cima."*, com
``+N`` se passar. E D-10: *"Todas na coluna Atenção."*, sobre as frases órfãs da
aba Jogar.

**UM FATO DO ENUNCIADO CAIU AQUI, e ele está medido nesta régua.** A D-09 nasceu
de *"a página tem UM par selo/texto e a conta do produto diz 3 avisos"*, e o
coordenador remediu e achou QUATRO. Nenhum dos dois números é o de hoje: a
página publica :data:`a01_jogar.AVISOS_VIVOS` — **seis** —, e as seis já são
endereço vivo desde 03/09. O que faltava não era LUGAR: era

1. **ordem** — a coluna mostrava as fontes na ordem em que o produto as
   declarou, que não é a ordem em que elas doem;
2. **teto** — com seis avisos a coluna crescia seis linhas e reabria o vão de
   38 px que ela reclamou em 31/08;
3. **a sétima fonte** — a linha *"Ponte com o jogo"*, que era a ÚNICA das três
   órfãs da D-10 sem canal nenhum. A PAUSA e o cadeado já estavam na coluna:
   são, respectivamente, a primeira e as duas últimas de
   `painel.AVISOS_DA_TELA`.

**E A SEÇÃO 4 NASCEU EM 06/09/2026 (ONDA5-01-01), com outra palavra dela:**
*"Não me lembro disso acontecer. E não deveria. Mas caso ocorra na coluna
atenção"*. A **cura do travamento do USB** (`storm_doctor.check_snd_quirk`) já
chegava à aba **Sistema** e não chegava à aba **Jogar** — as duas telas
discordando sobre a mesma máquina, e a que fica aberta enquanto o jogo roda era
a que calava. Ela não se lembra do defeito porque na máquina dela a cura está
DE PÉ; o dia em que a linha aparece é o dia em que a cura cai.

AS MORDIDAS, uma por peça — cada teste diz no docstring o que arrancar.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

RAIZ = pathlib.Path(__file__).resolve().parents[2]
INTERFACE = RAIZ / "src" / "hefesto_dualsense4unix" / "interface"
for _caminho in (str(RAIZ / "src"), str(INTERFACE)):
    if _caminho not in sys.path:
        sys.path.insert(0, _caminho)

from hefesto_dualsense4unix.app.actions import home_actions
from hefesto_dualsense4unix.app.actions.jogar import painel
from hefesto_dualsense4unix.integrations import storm_doctor
from pacotes import Contexto
from pacotes import a01_jogar as aba

#: O daemon em **Navegação**: sem gamepad de pé, e é o estado em que a ponte
#: fala. É o mesmo payload da régua irmã (`test_a_aba01_le_o_estado…`).
VIVO_NAVEGACAO: dict[str, Any] = {
    "connected": True,
    "native_mode": False,
    "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
    "paused": False,
    "controllers": [{"uniq": "aa:bb:cc:00:00:01", "connected": True,
                     "player_slot": 1}],
}


def _ctx(state: dict[str, Any]) -> Contexto:
    return Contexto(state=state, mesa=[], conectados=[], estados={})


def _acesas(fora: dict[str, Any]) -> tuple[list[str], list[str]]:
    """As linhas que a coluna ACENDE — as vazias são o apagador, não conteúdo.

    Os três endereços viajam SEMPRE com `AVISOS_VIVOS` entradas (ver a nota do
    `_coluna_de_avisos`): a lista curta some inteira em `pacotes.normalizar`
    quando fica vazia, e é a coluna vazia que precisa apagar o aviso do desenho.
    """
    selos = [s for s in fora["aviso-selo"] if s]
    return selos, fora["aviso-texto"][:len(selos)]


def _so_estes(monkeypatch: Any, avisos: list[dict[str, str]]) -> None:
    """Cala as outras fontes: a régua mede a ORDEM, não quem fala.

    A CURA DO TRAVAMENTO ENTROU AQUI EM 06/09/2026, e não é asseio: ela lê o
    DISCO DESTA MÁQUINA (`/sys/module/snd_usb_audio/…` e `/etc/modprobe.d/…`).
    Sem calá-la, toda régua deste arquivo passaria na máquina dela — onde a cura
    está de pé — e ganharia uma linha a mais na máquina de quem não a instalou:
    verde aqui, vermelho no CI, e nenhum dos dois falando do defeito medido.
    """
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: list(avisos))
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", lambda: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)


#: O ``quirk_flags`` de uma máquina CURADA — a grafia que
#: `storm_doctor._SND_QUIRK_RE` casa, e a mesma que o
#: `scripts/install_snd_quirk.sh` escreve.
QUIRK_DE_PE = "054c:0ce6:ignore_ctl_error|ctl_msg_delay_1m\n"


def _maquina(monkeypatch: Any, quirk_flags: str,
             conf: pathlib.Path) -> tuple[str, str]:
    """Põe a máquina no estado pedido e devolve o que o DONO responde nele.

    **O DUBLÊ É A FUNÇÃO REAL**, e isso é o ponto. `check_snd_quirk` já recebe
    os dois arquivos por parâmetro justamente para ser medida com fixture; o que
    se troca aqui é só o *de onde ela lê*, nunca o *o que ela responde*. Um
    dublê escrito à mão devolveria a frase que EU acho que o produto emite — e
    esta casa já mediu três vezes o preço disso: *o dublê mais frouxo que a
    função real*, que dá verde sobre defeito vivo.
    """
    real = storm_doctor.check_snd_quirk
    monkeypatch.setattr(storm_doctor, "check_snd_quirk",
                        lambda *a, **k: real(quirk_flags, conf))
    return real(quirk_flags, conf)


def _so_a_cura(monkeypatch: Any) -> None:
    """Cala TODAS as fontes menos a cura do travamento."""
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)


# ---------------------------------------------------------------------------
# 1. O MAIS GRAVE EM CIMA
# ---------------------------------------------------------------------------
def test_o_mais_grave_sobe_e_a_ordem_e_a_da_gravidade(monkeypatch: Any) -> None:
    """A PAUSA vem antes do PERFIL, mesmo chegando depois dele.

    A ORDEM DE CHEGADA É A INVERSA DA DE GRAVIDADE de propósito: se o pacote
    devolvesse a lista como a recebeu, este teste passaria por acaso com
    qualquer entrada. Aqui ele só passa se alguém ORDENOU.

    A MORDIDA: troque o `sorted(...)` de `_coluna_de_avisos` por
    `list(avisos)` e a asserção reprova com
    ``['PERFIL', 'RÁDIO', 'GAMEPAD'] != ['GAMEPAD', 'PAUSA'...]`` — medido.
    """
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "cadeado", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "degradado", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert selos == ["GAMEPAD", "RÁDIO", "PERFIL"], (
        f"a coluna não pôs o mais grave em cima: {selos!r}")


def test_a_pausa_vence_tudo_porque_ela_invalida_tudo(monkeypatch: Any) -> None:
    """Com o Hefesto em pausa, nada do resto está acontecendo.

    É o critério declarado em :data:`a01_jogar.ORDEM_DA_GRAVIDADE`: a escada não
    é de cor, é de *o que invalida o quê*. Uma coluna que mostrasse "o rádio
    está frágil" acima de "o Hefesto está em pausa" mandaria ela consertar o
    rádio de um produto que está parado.

    A MORDIDA: tire ``"PAUSA"`` do começo de `ORDEM_DA_GRAVIDADE` e ela cai
    para o fim (o `posto.get(..., fim)` dos não listados), reprovando aqui.
    """
    _so_estes(monkeypatch, [
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "PAUSA", "texto": "em pausa", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert selos[0] == "PAUSA", f"a pausa não subiu: {selos!r}"


def test_a_ordem_e_estavel_entre_iguais(monkeypatch: Any) -> None:
    """Dois avisos do mesmo selo mantêm a ordem em que as fontes falaram.

    Sem estabilidade a linha troca de lugar a cada tique e a coluna "pisca" —
    e a tela que se mexe sozinha é queixa dela desde 31/08.

    A MORDIDA: troque o `sorted` por `sorted(..., key=..., reverse=True)` ou
    ordene por `(posto, texto)` e os dois PERFIL trocam de lugar.
    """
    _so_estes(monkeypatch, [
        {"selo": "PERFIL", "texto": "primeiro", "fonte": "x"},
        {"selo": "PERFIL", "texto": "segundo", "fonte": "y"},
    ])
    _, textos = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert textos == ["primeiro", "segundo"], (
        f"a ordem entre iguais mudou: {textos!r}")


# ---------------------------------------------------------------------------
# 2. O TETO E O `+N`
# ---------------------------------------------------------------------------
def test_com_quatro_avisos_a_coluna_mostra_tres_e_conta_o_quarto(
        monkeypatch: Any) -> None:
    """*"Até três linhas"*, com ``+N`` se passar — e o quarto NÃO some calado.

    O ``+N`` OCUPA A QUARTA LINHA e não sai do teto: somá-lo ao teto faria a
    coluna mostrar três e só avisar a partir do QUINTO, escondendo o quarto sem
    contá-lo — o defeito exato que esta linha existe para fechar.

    A MORDIDA: apague o bloco ``if sobra > 0:`` de `_coluna_de_avisos` e a
    coluna volta a mostrar três de quatro sem uma palavra — reprova na segunda
    asserção.
    """
    _so_estes(monkeypatch, [
        {"selo": "PAUSA", "texto": "a", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "b", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "c", "fonte": "x"},
        {"selo": "PERFIL", "texto": "d", "fonte": "x"},
    ])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["aviso-texto"][:3] == ["a", "b", "c"]
    assert fora["aviso-selo"][3] == "+1", (
        f"o quarto aviso sumiu calado: {fora['aviso-selo']!r}")
    assert "1 aviso" in fora["aviso-texto"][3], (
        f"a linha do `+N` não diz quantos ficaram: {fora['aviso-texto'][3]!r}")
    # E O ACENDEDOR ACOMPANHA: uma linha escrita e não acesa não aparece.
    assert fora["aviso-vivo"] == ["1"] * 4 + [""] * (aba.AVISOS_VIVOS - 4)


def test_com_tres_avisos_nao_nasce_linha_de_mais(monkeypatch: Any) -> None:
    """Exatamente no teto, o ``+N`` não existe — ele não é decoração.

    A MORDIDA: troque `if sobra > 0` por `if sobra >= 0` e a coluna passa a
    escrever "+0" numa máquina com três avisos.
    """
    _so_estes(monkeypatch, [
        {"selo": "PAUSA", "texto": "a", "fonte": "x"},
        {"selo": "GAMEPAD", "texto": "b", "fonte": "x"},
        {"selo": "RÁDIO", "texto": "c", "fonte": "x"},
    ])
    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert len(selos) == aba.AVISOS_NA_COLUNA
    assert not any(s.startswith("+") for s in selos), (
        f"nasceu um `+N` sem nada de fora: {selos!r}")


def test_a_coluna_nunca_escreve_mais_linhas_do_que_a_pagina_publica(
        monkeypatch: Any) -> None:
    """O teto do produto tem de caber no teto da página.

    São dois números diferentes de propósito (`AVISOS_NA_COLUNA` < `AVISOS_
    VIVOS`), e esta régua é o que impede o dia em que alguém subir o primeiro
    sem olhar o segundo: o piloto distribui a lista pelos elementos na ORDEM e
    joga fora o que sobra — sem erro, sem contagem, calado.

    A MORDIDA: ponha `AVISOS_NA_COLUNA = AVISOS_VIVOS` e a linha do `+N` passa
    a ser a sétima, reprovando aqui.
    """
    _so_estes(monkeypatch, [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                            for i in range(20)])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    selos, _ = _acesas(fora)
    assert len(selos) <= aba.AVISOS_VIVOS
    assert len(fora["aviso-selo"]) == len(fora["aviso-texto"]) == len(
        fora["aviso-vivo"]) == aba.AVISOS_VIVOS


def test_a_conta_ao_lado_continua_dizendo_o_total(monkeypatch: Any) -> None:
    """A coluna mostra 3 e a conta diz 10 — e é assim que ela sabe que há mais.

    A MORDIDA: passe `len(selos)` a `texto_da_conta` em vez de `len(avisos)` e
    a tela volta a esconder sete avisos escrevendo "3 avisos".
    """
    _so_estes(monkeypatch, [{"selo": "PAUSA", "texto": str(i), "fonte": "x"}
                            for i in range(10)])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["atencao-conta"] == painel.texto_da_conta(10), (
        f"a conta deixou de dizer o total: {fora['atencao-conta']!r}")


# ---------------------------------------------------------------------------
# 3. O APAGADOR — a coluna vazia tem de APAGAR o aviso do desenho
# ---------------------------------------------------------------------------
def test_a_coluna_sem_aviso_apaga_o_que_o_mockup_cravou(monkeypatch: Any) -> None:
    """Fotografado no DOM vivo em 04/09/2026, e é uma tela se contradizendo.

    Com a máquina dela sem um aviso, a coluna mostrava *"RÁDIO · Dois rádios da
    bancada estão em portas vizinhas"* — a cena do mockup (`aba01.AVISOS`) — ao
    lado de *"nenhum aviso"*, escrito pelo produto no mesmo tique.

    A CAUSA ESTÁ FORA DESTA ABA e vale para todas: `pacotes.normalizar` descarta
    lista VAZIA (`if valor and all(...)`), então os três endereços não chegavam
    ao JS e o piloto **nunca visitava** os seis elementos — medido pelo selo da
    visita, `data-hef-visto` ausente nos seis. A cura daqui é declarar as seis
    linhas sempre, que é certo por si: quem publica seis lugares diz o que cada
    um dos seis mostra.

    A MORDIDA: troque o `vazias = [""] * (...)` por `vazias = []` e a lista volta
    a sair vazia — `normalizar` a come, e o aviso do desenho fica na tela para
    sempre. Reprova nas duas asserções abaixo.
    """
    from pacotes import normalizar

    _so_estes(monkeypatch, [])
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["atencao-conta"] == "nenhum aviso"
    for campo in ("aviso-selo", "aviso-texto", "aviso-vivo"):
        assert fora[campo] == [""] * aba.AVISOS_VIVOS, (
            f"{campo} não sai com as {aba.AVISOS_VIVOS} vazias: {fora[campo]!r}")
        assert campo in normalizar(fora)["mesa"], (
            f"{campo} não sobreviveu ao despachante — o endereço não chega ao "
            "JS, e o aviso que o mockup cravou fica na tela")


# ---------------------------------------------------------------------------
# 4. A CURA DO TRAVAMENTO DO USB — a fonte que faltava (ONDA5-01-01, 06/09/2026)
#
# A PALAVRA DELA, 05/09/2026: *"Não me lembro disso acontecer. E não deveria.
# Mas caso ocorra na coluna atenção"*. As três estão medidas abaixo: o produto
# CONSERTA (por isso ela não se lembra), a cura pode CAIR (por isso a linha
# existe), e quando ela cai a coluna Atenção diz — palavra por palavra do dono.
# ---------------------------------------------------------------------------

#: Um número em milissegundos escrito em prosa: `0,030 ms`, `0.79 ms`, `100 ms`.
_EM_MS = re.compile(r"\b(\d+(?:[.,]\d+)?)\s*ms\b")


def _tique_ms() -> float:
    """O tique do piloto, LIDO do fonte — e o import fica de fora de propósito.

    `interface/hefesto_vivo.py` puxa GTK e WebKit no topo; importá-lo dentro da
    suíte é o caminho que abriu `Gtk.Window` na sessão viva dela em 04/09
    (TELA-DELA-01). O número está numa linha só, e ler a linha basta.
    """
    fonte = (INTERFACE / "hefesto_vivo.py").read_text(encoding="utf-8")
    achado = re.search(r"^TIQUE_MS\s*=\s*(\d+)", fonte, re.MULTILINE)
    assert achado, "`TIQUE_MS` sumiu de `hefesto_vivo.py` — a régua perdeu o alvo"
    return float(achado.group(1))


def test_o_custo_da_cura_esta_medido_no_docstring() -> None:
    """Quanto custa por tique tem de estar ESCRITO, como a 09 escreveu os dela.

    A 09 declara *"`medir_guarda_do_steam_input()` — 2,8 ms, entra aqui;
    `medir_prontuario_dos_jogos()` — 7,1 s, e por isso NÃO entra"*
    (`a09_sistema._achados`). Esta fonte abre DOIS arquivos do sistema a cada
    tique, e o próximo a mexer aqui precisa saber o preço sem remedi-lo — senão
    a medição morre com a sessão de quem a fez.

    A RÉGUA NÃO CONFERE O NÚMERO, confere que ele EXISTE e que CABE: pelo menos
    uma medida menor que o tique, com o tique nomeado ao lado para se comparar
    a alguma coisa. Um docstring que diz "0,030 ms" sem dizer contra o quê não
    responde à pergunta que ele existe para responder.

    A MORDIDA: apague os números de milissegundo do docstring de
    `_aviso_da_cura_do_travamento` e esta régua reprova na primeira asserção.
    """
    doc = aba._aviso_da_cura_do_travamento.__doc__ or ""
    medidos = [float(m.group(1).replace(",", ".")) for m in _EM_MS.finditer(doc)]
    tique = _tique_ms()
    assert medidos, (
        "o docstring de `_aviso_da_cura_do_travamento` não declara quanto ela "
        "custa por tique — a fonte lê dois arquivos do sistema a cada 100 ms")
    assert tique in medidos, (
        f"o docstring não nomeia o tique ({tique:g} ms): um custo sem o teto "
        "ao lado não diz se cabe")
    assert min(medidos) < tique, (
        f"nenhuma medida do docstring é menor que o tique: {medidos!r}")


def test_a_cura_ativa_nao_vira_alarme(monkeypatch: Any, tmp_path: Any) -> None:
    """``[ OK ]`` NÃO entra: boa notícia não é Atenção — e é o estado dela hoje.

    É a mesma disciplina que já deixa os ``certo`` do exame de fora
    (`_do_exame`) e que fez `_aviso_da_ponte` recusar os dois desfechos bons.
    A lição tem foto: em 02/09 o selo ``CERTO`` apareceu sob o cabeçalho
    laranja **Atenção**, com o texto "Economia de energia desligada" — uma boa
    notícia vestida de alarme.

    A MORDIDA: arranque o `if selo == storm_doctor.OK: return None` de
    `_aviso_da_cura_do_travamento` e a coluna passa a acender uma linha
    dizendo que está tudo bem — reprova nas duas asserções.
    """
    _so_a_cura(monkeypatch)
    selo, _ = _maquina(monkeypatch, QUIRK_DE_PE, tmp_path / "nao-existe.conf")
    assert selo == storm_doctor.OK, "o estado montado não é o `[ OK ]` do dono"

    assert aba._aviso_da_cura_do_travamento() is None
    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert fora["atencao-conta"] == "nenhum aviso", (
        f"a cura DE PÉ acendeu a coluna: {fora['aviso-texto']!r}")
    assert fora["aviso-selo"] == [""] * aba.AVISOS_VIVOS


def test_a_cura_ausente_chega_a_coluna(monkeypatch: Any, tmp_path: Any) -> None:
    """``[WARN]`` entra, com a frase do dono — palavra por palavra.

    ESTE É O DEFEITO QUE A SPRINT FECHA: `check_snd_quirk` já chegava à aba
    **Sistema** (por `storm_report`), e a aba **Jogar** — a que fica aberta
    enquanto o jogo roda — dizia "nenhum aviso" sobre a mesma máquina.

    A FRASE NÃO É DIGITADA AQUI TAMPOUCO: ela é perguntada ao dono, no mesmo
    estado de máquina. Uma régua que digitasse a frase esperada passaria a
    medir a si mesma, que é o que se achou três vezes nesta leva.

    A MORDIDA: arranque o bloco da cura de `_avisos` e a coluna volta a dizer
    "nenhum aviso" com a cura AUSENTE — reprova na terceira asserção.
    """
    _so_a_cura(monkeypatch)
    selo, frase = _maquina(monkeypatch, "", tmp_path / "nao-existe.conf")
    assert selo == storm_doctor.WARN, "o estado montado não é o `[WARN]` do dono"

    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    selos, textos = _acesas(fora)
    assert textos == [frase], (
        f"a frase do dono não chegou inteira à coluna: {textos!r}")
    assert selos == [aba.SELO_DA_CURA], f"o selo não é o da cura: {selos!r}"
    assert fora["atencao-conta"] == painel.texto_da_conta(1)


def test_a_cura_agendada_tambem_e_trabalho_pendente(
        monkeypatch: Any, tmp_path: Any) -> None:
    """``[INFO]`` entra: *"desconecte e reconecte"* é gesto DELA, não estado bom.

    O `[INFO]` desta função diz que a cura está no `/etc/modprobe.d` e ainda
    não valeu — ela pega no replug de cada controle. É trabalho pendente com
    gesto nomeado, que é a definição de Atenção nesta casa; deixá-lo de fora
    esconderia da tela do jogo exatamente a máquina que está a um replug de
    ficar boa.

    A MORDIDA: troque o `if selo == storm_doctor.OK` por
    `if selo != storm_doctor.WARN` e o `[INFO]` some — reprova aqui, e
    `test_a_cura_ausente_chega_a_coluna` continua verde, que é o que faz esta
    régua valer a pena.
    """
    conf = tmp_path / "hefesto-dualsense-storm.conf"
    conf.write_text(f"options snd_usb_audio quirk_flags={QUIRK_DE_PE}",
                    encoding="utf-8")
    _so_a_cura(monkeypatch)
    selo, frase = _maquina(monkeypatch, "", conf)
    assert selo == storm_doctor.INFO, "o estado montado não é o `[INFO]` do dono"

    _, textos = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert textos == [frase], (
        f"a cura AGENDADA não chegou à coluna: {textos!r}")


def test_o_selo_novo_esta_na_escada(monkeypatch: Any, tmp_path: Any) -> None:
    """``CONTROLE`` está em `ORDEM_DA_GRAVIDADE` — senão a máquina cheia o some.

    O que não está na tupla vai para DEPOIS DE TUDO (`posto.get(..., fim)`), e
    com a coluna mostrando três de cada vez isso é o mesmo que esconder a linha
    atrás do ``+N``. Os três avisos de companhia são todos MENOS graves que a
    queda do controle, então na escada certa a cura vem em primeiro.

    A MORDIDA: tire ``"CONTROLE"`` de `ORDEM_DA_GRAVIDADE` e deixe a fonte no
    lugar — a linha da cura cai para o fim, some no ``+1`` e as duas asserções
    reprovam.
    """
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [
        {"selo": "RÁDIO", "texto": "frágil", "fonte": "x"},
        {"selo": "PERFIL", "texto": "cadeado", "fonte": "x"},
        {"selo": "PERFIL", "texto": "cego", "fonte": "x"},
    ])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    _, frase = _maquina(monkeypatch, "", tmp_path / "nao-existe.conf")

    fora = aba.pacote(_ctx(VIVO_NAVEGACAO))
    assert aba.SELO_DA_CURA in aba.ORDEM_DA_GRAVIDADE, (
        "o selo da cura saiu da escada — ele vai para depois de tudo")
    assert fora["aviso-selo"][0] == aba.SELO_DA_CURA, (
        f"a cura não subiu na escada: {fora['aviso-selo']!r}")
    assert frase in fora["aviso-texto"][:aba.AVISOS_NA_COLUNA], (
        f"a linha da cura sumiu atrás do `+N`: {fora['aviso-texto']!r}")


def test_o_selo_nao_e_o_do_radio(monkeypatch: Any, tmp_path: Any) -> None:
    """A cura é do CABO; quem já ocupa ``RÁDIO`` fala de Bluetooth.

    `texto_do_radio_fragil` (`painel.AVISOS_DA_TELA`) tem o selo ``RÁDIO`` e
    fala do transporte sem fio. Dois avisos com o mesmo selo, um do cabo e
    outro do rádio, é a coluna mandando ela procurar no lugar errado — e o selo
    deixa de dizer o que ele existe para dizer.

    A MORDIDA: troque `SELO_DA_CURA` para ``"RÁDIO"`` e as duas linhas nascem
    com o mesmo selo — reprova nas duas asserções.
    """
    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [
        {"selo": "RÁDIO", "texto": "o rádio está frágil", "fonte": "x"},
    ])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    _maquina(monkeypatch, "", tmp_path / "nao-existe.conf")

    selos, _ = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert aba.SELO_DA_CURA != "RÁDIO", "a cura do cabo pegou o selo do rádio"
    assert len(set(selos)) == len(selos) == 2, (
        f"o cabo e o rádio saíram com o mesmo selo: {selos!r}")


def test_a_fonte_que_levanta_vira_erro_e_nao_derruba_a_coluna(
        monkeypatch: Any) -> None:
    """A política do `try` próprio: a coluna sobrevive à fonte que quebra.

    É a mesma de `painel.avisos_do_estado`, do opt-out e do exame. Esta fonte
    é a PRIMEIRA desta coluna a tocar o disco a cada tique — um `/sys`
    remontado ou um `/etc` sem permissão não pode apagar as outras nove linhas.

    A MORDIDA: tire o `try/except` que embrulha a chamada em `_avisos` e o
    `pacote()` inteiro levanta — a coluna some, e com ela a mesa, os cartões e
    a faixa, porque `_avisos` é chamado no meio de `pacote()`.
    """
    def _explode() -> dict[str, str]:
        raise OSError("o /sys sumiu")

    monkeypatch.setattr(painel, "avisos_do_estado", lambda _s: [])
    monkeypatch.setattr(aba, "_do_exame", lambda: [])
    monkeypatch.setattr(aba, "_aviso_da_ponte", lambda _s: None)
    monkeypatch.setattr(
        home_actions, "aviso_de_opt_out_antigo", lambda *a, **k: None)
    monkeypatch.setattr(aba, "_aviso_da_cura_do_travamento", _explode)

    selos, textos = _acesas(aba.pacote(_ctx(VIVO_NAVEGACAO)))
    assert selos == ["ERRO"], f"a fonte que levantou não virou ERRO: {selos!r}"
    assert "OSError" in textos[0], (
        f"o aviso de erro não diz o que quebrou: {textos[0]!r}")


def test_a_frase_da_cura_nao_se_digita_nesta_aba(tmp_path: Any) -> None:
    """A frase tem DONO, e a aba a lê — não a redigita.

    É o defeito que `_do_exame` já custou a esta aba: as palavras "RÁDIO" e
    "AVISO" digitadas por cima de um selo que o produto emitia. Uma segunda
    cópia da frase aqui envelheceria no primeiro dia em que o dono a melhorasse
    — e o dono a melhorou duas vezes em 26/08 (o rótulo do botão e o gesto de
    atualizar por formato de instalação).

    O TRECHO PROCURADO É PERGUNTADO AO DONO, nunca digitado: uma régua que
    escrevesse a frase banida viraria a primeira ocorrência dela no arquivo —
    a armadilha de 05/09 desta casa, em que um aviso virou o defeito que
    descrevia.

    A VARREDURA PULA PROSA E COMENTÁRIO, como a régua irmã da palavra do
    transporte: o docstring que EXPLICA a cura não pode reprovar a cura que ele
    explica.

    A MORDIDA: cole a frase do `[WARN]` num literal de código de
    `a01_jogar.py` e esta régua a nomeia com o número da linha.
    """
    _, frase = storm_doctor.check_snd_quirk("", tmp_path / "nao-existe.conf")
    trecho = frase.split(" — ", 1)[0].strip()
    assert len(trecho) > 20, f"o trecho do dono ficou curto demais: {trecho!r}"

    caminho = "src/hefesto_dualsense4unix/interface/pacotes/a01_jogar.py"
    fonte = (RAIZ / caminho).read_text(encoding="utf-8")
    dentro_de_prosa = False
    acusados: list[str] = []
    for numero, linha in enumerate(fonte.splitlines(), start=1):
        nua = linha.strip()
        if nua.count('"""') == 1:
            dentro_de_prosa = not dentro_de_prosa
            continue
        if dentro_de_prosa or nua.startswith("#") or not nua:
            continue
        if trecho in nua.split("#", 1)[0]:
            acusados.append(f"{caminho}:{numero}: {nua}")
    assert not acusados, (
        "a frase da cura foi redigitada em código:\n  " + "\n  ".join(acusados)
        + "\nEla vem inteira de `storm_doctor.check_snd_quirk` e de mais lugar "
          "nenhum")
