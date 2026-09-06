"""STEAM-INPUT-01, entregas 1 e 9 — a frase falsa e os dois ponteiros errados.

Entrega 1: o produto ensinava a ir na Steam ligar a entrada do controle pela
janela da própria Steam. A frase só valia para um appid JÁ na allowlist; para
qualquer outro jogo o guarda desfaz o gesto (medido na DUPLO-REGISTRO-01, com o
Pragmata ligado no ``localconfig.vdf`` e ausente do ``steam_input_apps.txt``).
A frase saiu, e este arquivo impede que ela volte por qualquer texto de
interface — não só pelo toast onde ela morava.

Entrega 9: dois rótulos apontavam para lugar que não existe. Os testes daqui
NÃO comparam strings com uma constante: eles conferem que o alvo citado EXISTE
de fato (o botão está numa das dez páginas publicadas, a aba é a aba em que
esse botão mora, o arquivo citado está na árvore). Assim a próxima renomeação
de rótulo também reprova, em vez de passar calada.

**A TELA QUE ESTA RÉGUA LÊ MUDOU EM 06/09/2026, e a razão é um defeito vivo.**
Até aqui ela lia os ``GtkButton`` do ``gui/main.glade``. A frase do
``storm_doctor`` mandava clicar em *'Consertar problemas conhecidos'*, que é o
rótulo da janela — e na interface que ela usa aquele botão se chama **'Refazer
os consertos automáticos'** (``paginas/09-sistema.html``). A régua dava VERDE
sobre a frase falsa porque media a tela ERRADA: a que está saindo.

Achado pela ``GTK-2`` e pela ``SISTEMA-STEAM-01``, no mesmo dia e por dois
caminhos. A cura é um PAR — a frase e a régua —, e sem a segunda metade a
primeira reprova.

**O NOME DA ABA SAI DA PRÓPRIA PÁGINA**, do ``<a class="aba">`` da barra que
as dez compartilham, e não de uma tabela aqui: uma aba renomeada tem de mudar
esta régua junto, e não passar calada.
"""
from __future__ import annotations

import ast
import re
import xml.etree.ElementTree as ET
from typing import Any
from pathlib import Path

import pytest

from hefesto_dualsense4unix.app.actions.daemon_actions import (
    format_game_broken_result,
)
from hefesto_dualsense4unix.integrations import storm_doctor as sd

_RAIZ = Path(__file__).resolve().parents[2]
_PACOTE = _RAIZ / "src" / "hefesto_dualsense4unix"
_GLADE = _PACOTE / "gui" / "main.glade"
_DAEMON_ACTIONS = _PACOTE / "app" / "actions" / "daemon_actions.py"
_GUIA_MASCARAS = _RAIZ / "docs" / "usage" / "jogos-e-mascaras.md"

#: Rótulo entre aspas simples dentro de uma mensagem ("clique 'Assim'").
_ROTULO_CITADO = re.compile(r"'([^']{3,40})'")
#: "na aba Sistema" / "aba **Sistema**" — o nome da aba que a mensagem promete.
_ABA_CITADA = re.compile(r"aba \*{0,2}([A-ZÁÉÍÓÚÃÕÂÊÔÇ][a-záéíóúãõâêôç]+)")


# ---------------------------------------------------------------------------
# Leitura estrutural da janela
# ---------------------------------------------------------------------------
#: O BOTÃO NO HTML: `<button …>Texto</button>`, e o texto pode trazer filhos
#: (um `<span>` da dica vem logo DEPOIS do fecho, nunca dentro). O grupo é
#: preguiçoso para parar no primeiro `</button>`.
_BOTAO = re.compile(r"<button\b[^>]*>(.*?)</button>", re.S)
#: A BARRA DAS DEZ: `<a class="aba" href="NN-nome.html">Nome</a>`.
_ABA_NA_BARRA = re.compile(r'<a[^>]*class="aba"[^>]*href="([^"]+)"[^>]*>([^<]+)')
#: Marcação interna que sobra dentro do rótulo de um botão.
_TAGS = re.compile(r"<[^>]+>")


def _publicadas() -> list[Path]:
    """As dez páginas que o produto renderiza, na ordem do nome."""
    return sorted((_PACOTE / "interface" / "paginas").glob("[0-9][0-9]-*.html"))


def _nome_das_abas() -> dict[str, str]:
    """{arquivo: nome da aba}, lido da BARRA que as dez compartilham."""
    for arq in _publicadas():
        achados = _ABA_NA_BARRA.findall(arq.read_text(encoding="utf-8"))
        if achados:
            return {href: nome.strip() for href, nome in achados}
    raise AssertionError("nenhuma página publicada tem a barra das abas")


def _paginas() -> list[tuple[str, str]]:
    """[(nome da aba, HTML da página)] das dez publicadas."""
    nomes = _nome_das_abas()
    saida = []
    for arq in _publicadas():
        nome = nomes.get(arq.name)
        if nome:
            saida.append((nome, arq.read_text(encoding="utf-8")))
    assert saida, "as páginas publicadas sumiram da árvore"
    return saida


def _rotulo_do_botao(bruto: str) -> str | None:
    """O texto que a pessoa LÊ no botão, sem a marcação de dentro.

    **26/08/2026, e a razão sobrevive à troca de tela:** um botão tem o rótulo
    direto até o dia em que ele precisa de um `<span>` dentro. Quem vê a tela vê
    o mesmo texto nos dois casos, então a régua tem de ver os dois.
    """
    texto = _TAGS.sub("", bruto).strip()
    return texto or None


def _aba_do_botao(rotulo: str) -> str | None:
    """Nome da aba onde mora o botão de rótulo ``rotulo``, ou None."""
    for aba, html in _paginas():
        for bruto in _BOTAO.findall(html):
            if _rotulo_do_botao(bruto) == rotulo:
                return aba
    return _rotulos_do_cartao().get(rotulo)


#: OS BOTÕES QUE O PRODUTO CONSTRÓI NA HORA, e por isso não estão em página
#: nenhuma: o cartão da Steam da aba Lançadores só os oferece depois de ler a
#: biblioteca, e `cartoes(None)` — a primeira meia volta — não leu disco nenhum.
#: Um HTML estático não pode tê-los, e eles estão na tela dela do mesmo jeito.
#: O dono é `interface/desenho_dos_lancadores.py`, e o nome da aba sai da barra
#: das dez como o de qualquer outra.
_ROTULOS_QUE_NASCEM_NO_CARTAO = (
    "COPIAR_ROTULO", "DESLIGAR_STEAM_INPUT_ROTULO",
    "JOGO_NAO_FUNCIONA_ROTULO", "TUDO_PRONTO_ROTULO",
)


def _rotulos_do_cartao() -> dict[str, str]:
    """{rótulo: nome da aba} dos botões que o cartão da Steam monta na hora."""
    from hefesto_dualsense4unix.interface import desenho_dos_lancadores as dl

    aba = _nome_das_abas().get("07-lancadores.html", "Lançadores")
    return {getattr(dl, n): aba for n in _ROTULOS_QUE_NASCEM_NO_CARTAO
            if isinstance(getattr(dl, n, None), str)}


def _rotulos_de_botao() -> set[str]:
    """O universo dos alvos válidos: a tela que o LANÇADOR abre, e só ela.

    **A JANELA ESTÁVEL FICOU DE FORA, e a exclusão é medida — 06/09/2026.** A
    primeira versão desta cura punha os `GtkButton` do glade no universo, com o
    argumento de que a janela ainda existe. Com ela dentro, **a régua parou de
    morder**: devolvi a frase do `storm_doctor` ao rótulo velho
    (*'Consertar problemas conhecidos'*) e os dez testes passaram verdes — sobre
    exatamente o defeito que este arquivo existe para pegar.

    A razão é simples e vale como regra: quem lê a frase é quem abriu a tela que
    o lançador abre. Um rótulo que só existe na janela que está saindo é um
    rótulo que ela não vai encontrar.
    """
    achados = {
        _rotulo_do_botao(bruto)
        for _aba, html in _paginas()
        for bruto in _BOTAO.findall(html)
    }
    return {r for r in achados if r} | set(_rotulos_do_cartao())


def _corpo_de_funcao(caminho: Path, nome: str) -> str:
    """Texto-fonte de uma função/método, por AST (sem importar GTK)."""
    fonte = caminho.read_text(encoding="utf-8")
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        if isinstance(no, ast.FunctionDef) and no.name == nome:
            return ast.get_source_segment(fonte, no) or ""
    raise AssertionError(f"{nome}() não existe em {caminho.name}")


# ---------------------------------------------------------------------------
# Entrega 1 — a frase que ensinava o gesto na Steam não volta
# ---------------------------------------------------------------------------
#: O gesto proibido: "Propriedades -> Controle/Controlador" na janela da Steam.
#: "Propriedades -> Opções de inicialização" NÃO cai aqui de propósito — colar
#: a opção de inicialização é ação legítima e viva do produto.
_GESTO_NA_STEAM = re.compile(r"Propriedades\s*(?:→|->)\s*Control")


def _fontes_de_texto_de_interface() -> list[Path]:
    arquivos = sorted(_PACOTE.rglob("*.py"))
    arquivos.append(_GLADE)
    return arquivos


def test_nenhum_texto_da_janela_ensina_o_gesto_na_steam() -> None:
    """Entrega 1: a instrução de ir na Steam mexer no controle do jogo SAIU.

    Vale para o pacote inteiro, não só para o toast onde ela morava: a frase é
    falsa para todo jogo fora da allowlist, e o custo dela foi ela seguir o
    produto e cair na divergência entre os dois cadastros.
    """
    culpados = [
        f"{caminho.relative_to(_RAIZ)}:{n}"
        for caminho in _fontes_de_texto_de_interface()
        for n, linha in enumerate(
            caminho.read_text(encoding="utf-8").splitlines(), start=1
        )
        if _GESTO_NA_STEAM.search(linha)
    ]
    assert not culpados, (
        "texto de interface voltou a ensinar o gesto na Steam "
        f"(Propriedades -> Controle): {culpados}"
    )


@pytest.mark.parametrize("status", ["adicionado", "ja_estava"])
def test_toast_do_jogo_marcado_nao_manda_ninguem_a_steam(status: str) -> None:
    msg = format_game_broken_result(status=status, appid=2111190)
    assert "Propriedades" not in msg
    assert "Ativar" not in msg


@pytest.mark.parametrize("status", ["adicionado", "ja_estava"])
def test_toast_do_jogo_marcado_nao_deixa_vazio(status: str) -> None:
    """Tirar a frase falsa não pode virar silêncio.

    A pergunta legítima que ela respondia ("e se não funcionar?") continua
    respondida: o próximo passo concreto (fechar e abrir o jogo) e um destino
    que EXISTE na árvore para o caso de o jogo seguir mudo.
    """
    msg = format_game_broken_result(status=status, appid=2111190)
    assert "Feche e abra o jogo" in msg
    citados = re.findall(r"\bdocs/[\w./-]+\.md\b", msg)
    assert citados, f"o toast não aponta destino nenhum: {msg!r}"
    for rel in citados:
        assert (_RAIZ / rel).is_file(), f"o toast cita {rel}, que não existe"


def test_toast_do_jogo_marcado_nao_promete_o_que_o_clique_nao_faz() -> None:
    """O clique NÃO liga a entrada da Steam — só escreve na allowlist.

    Prova de que a promessa seria falsa: ``on_steam_game_broken`` chama
    ``add_appid_to_steam_input_allowlist`` e nada mais; quem mexe no
    ``localconfig.vdf`` é o ``scripts/disable_steam_input.sh``.
    """
    corpo = _corpo_de_funcao(_DAEMON_ACTIONS, "on_steam_game_broken")
    assert "add_appid_to_steam_input_allowlist" in corpo
    assert "UseSteamControllerConfig" not in corpo
    msg = format_game_broken_result(status="adicionado", appid=2111190)
    assert "respeita essa escolha" not in msg


# ---------------------------------------------------------------------------
# Entrega 9 — os ponteiros apontam para alvos que existem
# ---------------------------------------------------------------------------
def _warn_steam_input(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    """A mensagem de WARN do ``check_steam_input``, com fixtures no disco."""
    vdf = tmp_path / ".steam/steam/userdata/123/config/localconfig.vdf"
    vdf.parent.mkdir(parents=True)
    vdf.write_text('\t\t\t\t"SteamController_PSSupport"\t\t"2"\n', encoding="utf-8")
    # A allowlist real da máquina não pode decidir o resultado do teste.
    monkeypatch.setattr(sd, "_allowlist_path", lambda: tmp_path / "allowlist-vazia.txt")
    tag, msg = sd.check_steam_input(tmp_path)
    assert tag == sd.WARN
    return msg


def _warn_snd_quirk(tmp_path: Path) -> str:
    tag, msg = sd.check_snd_quirk(
        quirk_flags_text="", conf_path=tmp_path / "ausente.conf"
    )
    assert tag == sd.WARN
    return msg


def test_botao_citado_pelo_diagnostico_existe_na_janela(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Todo rótulo entre aspas nas mensagens do doctor é botão de verdade.

    Era aqui que morava o defeito: 'Reaplicar fixes seguros' não é o nome de
    widget nenhum. Conferir contra o glade — e não contra uma constante —
    também pega a próxima renomeação do botão.
    """
    rotulos = _rotulos_de_botao()
    for msg in (
        _warn_steam_input(tmp_path, monkeypatch),
        _warn_snd_quirk(tmp_path),
    ):
        for citado in _ROTULO_CITADO.findall(msg):
            assert citado in rotulos, (
                f"a mensagem {msg!r} manda procurar o botão {citado!r}, "
                "que não existe na janela"
            )


def test_aba_citada_e_a_aba_onde_o_botao_mora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Rótulo certo na aba errada continua sendo ponteiro errado."""
    msg = _warn_steam_input(tmp_path, monkeypatch)
    citados = _ROTULO_CITADO.findall(msg)
    assert citados, f"a mensagem parou de nomear o botão: {msg!r}"
    abas = _ABA_CITADA.findall(msg)
    assert abas, f"a mensagem parou de nomear a aba: {msg!r}"
    assert _aba_do_botao(citados[0]) == abas[0]


def test_guia_das_mascaras_aponta_o_botao_e_a_aba_que_existem() -> None:
    """``docs/usage/jogos-e-mascaras.md`` mandava usar um opt-in inexistente.

    O texto antigo era *"o opt-in em 'Steam Input' na aba Emulação"*: na aba
    Emulação existem só "Verificar" e "Desligar Steam Input" — nenhum opt-in
    por jogo. O opt-in é o botão "Este jogo não funciona".

    NOTA DATADA — 28/08/2026 (S4). Este caso pegava *o primeiro* parágrafo que
    contivesse "exceção por jogo" e exigia dele o par botão+aba. Isso amarrou a
    régua à ORDEM do texto: quando a S4 acrescentou, acima do parágrafo do
    gesto, a nota que CITA a instrução derrubada para dizer que ela morreu, o
    `next()` passou a cair na nota — que não cita botão nenhum, porque não
    manda fazer nada — e o caso reprovou a correção em vez do defeito.
    Agora a regra é a de verdade, e é mais forte: **todo** parágrafo que cite
    um botão existente tem de nomear a aba certa dele, e **algum** parágrafo
    tem de falar da exceção por jogo apontando um botão que exista.
    """
    texto = _GUIA_MASCARAS.read_text(encoding="utf-8")
    paragrafos = texto.split("\n\n")

    com_ponteiro: list[str] = []
    for trecho in paragrafos:
        citados = re.findall(r'"([^"]{3,40})"', trecho)
        botao = next((c for c in citados if c in _rotulos_de_botao()), None)
        if botao is None:
            continue
        com_ponteiro.append(trecho)
        abas = _ABA_CITADA.findall(trecho)
        assert abas, f"o guia cita {botao!r} e não diz em que aba ele mora: {trecho!r}"
        assert _aba_do_botao(botao) == abas[0], (
            f"o guia manda procurar {botao!r} na aba {abas[0]!r}, que não é "
            f"onde ele mora ({_aba_do_botao(botao)!r}): {trecho!r}"
        )

    assert any("exceção por jogo" in t or "marcar" in t for t in com_ponteiro), (
        "nenhum parágrafo do guia liga a exceção por jogo a um botão que "
        f"exista na janela — os que citam botão são {com_ponteiro!r}"
    )


def test_ponteiro_da_cura_do_usb_nao_manda_clicar_em_quem_nao_a_instala(
    tmp_path: Path,
) -> None:
    """Reenquadramento: aqui o nome do botão seria uma mentira NOVA.

    O "Aplicar correções" roda o ``scripts/disable_steam_input.sh`` e o
    ``scripts/fix_wireplumber_default_source.sh`` e deixa o quirk de fora de
    propósito (BUG-C). Quem instala a cura é o ``install.sh``. Se um dia o
    botão passar a instalá-la, este teste reprova — e a mensagem tem de mudar
    junto, porque a frase dela deixaria de ser verdade.
    """
    corpo = _corpo_de_funcao(_DAEMON_ACTIONS, "on_storm_fix_safe")
    assert "install_snd_quirk" not in corpo
    msg = _warn_snd_quirk(tmp_path)
    citados = re.findall(r"\./([\w./-]+\.sh)\b", msg)
    assert citados, f"a mensagem não diz o que rodar: {msg!r}"
    for rel in citados:
        alvo = _RAIZ / rel
        assert alvo.is_file(), f"a mensagem manda rodar {rel}, que não existe"
        assert "install_snd_quirk.sh" in alvo.read_text(encoding="utf-8"), (
            f"{rel} não instala a cura que a mensagem promete"
        )
