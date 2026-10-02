"""O BOTÃO DE LIGAR O HEFESTO NA TELA NOVA: ele funciona, e ele se lembra.

Pedido dela, 31/08/2026, literal:

    *"Não sei se o botão de ativar ele na interface tá funcionando viu. não sei
    se segue desativado."*
    *"eu quero é que **ele funcione na interface e se lembre**."*

O QUE FOI MEDIDO ANTES DE UMA LINHA SER ESCRITA
-----------------------------------------------
Com o ``./interface`` aberto (que é o piloto da aba Controles dentro de um
``WebKit2.WebView``) e a tira navegada até a aba **Jogar**:

* ``[data-modo="gamepad"]`` — "Jogar pelo Hefesto" — aparecia **ACESO**;
* ``listeners=0`` nos QUATRO botões da fileira;
* um clique sintético (``el.click()``) produziu **zero** gestos;
* o ``gamepad_disabled.flag`` não se moveu;
* e o ``mode_of_state`` do daemon dizia ``desktop``.

Ou seja: a tela afirmava o estado do **desenho** enquanto o disco dizia o
contrário — o F7 desta casa (*estado velho como padrão*) na pergunta em que ele
mais dói, porque a resposta que ela precisa é justamente "segue desativado?".

**O QUE FALTAVA NÃO ERA MÉTODO DE IPC.** ``gamepad.emulation.set`` existe
(``daemon/ipc_server.py``), persiste (``utils/session.save_gamepad_emulation``
grava e apaga o ``gamepad_disabled.flag``) e é respeitado depois de reiniciar
(``gamepad_multiplos_controles_adiado estado=ignorado_gesto_dela``). Faltava a
metade **escritora** da tela nova: ``app/actions/jogar/painel`` dizia qual botão
acende e nunca dizia quem aplica o clique.

AS SEIS RÉGUAS, E ONDE CADA UMA MORDE
--------------------------------------
1. :func:`test_todo_botao_do_desenho_tem_linha_na_fileira` — a fileira é LIDA do
   ``src/hefesto_dualsense4unix/interface/paginas/01-jogar.html``, nunca digitada. **Morde**
   trocando um
   ``data-modo`` no mockup: o botão órfão aparece.
2. :func:`test_quem_aplica_e_o_dono_e_nao_uma_copia` — o plano é DELEGADO.
   **Morde** com a delegação arrancada (o teste troca o dono em tempo de
   execução e exige que a resposta acompanhe).
3. :func:`test_todo_passo_que_define_modo_declara_origem_manual` — sem
   ``origin="manual"`` o daemon lê o clique dela como reconciliação e o portão
   da allowlist do Steam Input o recusa (ORIGEM-QUE-MENTE-01). **Morde**
   tirando o campo.
4. :func:`test_o_desligado_nao_finge_ter_dono` — o quarto botão não tem
   escritor, e a tela diz isso em vez de oferecê-lo.
5. :func:`test_a_lembranca_tem_um_lugar_so_e_e_o_do_produto` — a memória vem do
   ``session.load_gamepad_preference`` e de mais lugar nenhum. **Morde** trocando
   o dono e exigindo que a resposta mude.
6. :func:`test_o_disco_lembra_o_desligar_e_o_ligar` — o ciclo inteiro no disco
   de mentira da suíte: desligou → o flag existe; ligou → o flag some.

E duas de forma, sobre o piloto que ela abre
(:func:`test_o_piloto_nao_digita_o_dono_do_modo` e
:func:`test_o_piloto_aplica_pelo_dono_e_nao_por_ipc_cru`), porque foi assim que
onze réguas desta casa reprovaram a melhora em vez do defeito, em 26/08:
**digitavam o que deviam LER**.
"""
from __future__ import annotations

from tests.conftest import exigir_gi_real

exigir_gi_real("test_o_botao_de_ligar_funciona_e_se_lembra: importa código da janela GTK")

import pathlib
import re

import pytest

from hefesto_dualsense4unix.app.actions import mode_transition
from hefesto_dualsense4unix.app.actions.jogar import painel

RAIZ = pathlib.Path(__file__).resolve().parents[2]
DESENHO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "paginas" / "01-jogar.html"  # noqa-acento (`paginas` e o nome da PASTA; caminho nao leva acento)
PILOTO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "controles_vivos.py"

_DATA_MODO = re.compile(r'data-modo="([a-z-]+)"')


def modos_do_desenho() -> set[str]:
    if not DESENHO.is_file():
        pytest.skip(f"o desenho da aba Jogar não está nesta árvore: {DESENHO}")
    return set(_DATA_MODO.findall(DESENHO.read_text(encoding="utf-8")))


def test_todo_botao_do_desenho_tem_linha_na_fileira() -> None:
    """Nenhum botão do desenho fica órfão, e nenhuma linha sobra sem botão."""
    do_desenho = modos_do_desenho()
    da_fileira = {modo.chave for modo in painel.MODOS_DA_TELA}
    assert do_desenho, "o desenho não tem um único [data-modo] — leia o arquivo certo"
    assert do_desenho == da_fileira, (
        f"o desenho e a fileira divergem — só no desenho: {do_desenho - da_fileira}; "
        f"só na fileira: {da_fileira - do_desenho}"
    )


def test_todo_botao_ou_tem_escritor_ou_tem_motivo() -> None:
    """Um botão sem escritor tem de dizer POR QUÊ, em português."""
    for chave in modos_do_desenho():
        tem_escritor = chave in painel.ESCRITOR_DOS_MODOS
        motivo = painel.porque_nao_aplica(chave)
        assert tem_escritor != bool(motivo), (
            f"{chave!r}: escritor={tem_escritor} e motivo={motivo!r} — "
            "um botão ou tem quem o atenda ou tem o porquê, nunca os dois nem nenhum"
        )
        assert painel.escritor_do_modo(chave), f"{chave!r} sem uma linha de dono"


def test_quem_aplica_e_o_dono_e_nao_uma_copia(monkeypatch: pytest.MonkeyPatch) -> None:
    """``plano_do_modo`` DELEGA a ``mode_transition.plan_mode_transition``."""
    for chave in painel.ESCRITOR_DOS_MODOS:
        assert painel.plano_do_modo(chave) == mode_transition.plan_mode_transition(chave)

    marca = [("passo.inventado", {"pelo": "dublê"})]
    monkeypatch.setattr(painel, "plan_mode_transition", lambda *_a, **_k: marca)
    assert painel.plano_do_modo(mode_transition.MODE_GAMEPAD) == marca, (
        "plano_do_modo não seguiu o dono — há uma segunda cópia da sequência"
    )


def test_todo_passo_que_define_modo_declara_origem_manual() -> None:
    """``origin="manual"`` em todo passo definidor — ORIGEM-QUE-MENTE-01."""
    definidores = {"native.mode.set", "gamepad.emulation.set"}
    for chave in painel.ESCRITOR_DOS_MODOS:
        plano = painel.plano_do_modo(chave)
        assert plano, f"{chave!r} tem escritor e plano vazio"
        for metodo, params in plano:
            if metodo in definidores:
                assert params.get("origin") == "manual", (
                    f"{chave!r} → {metodo}: sem origin=manual, o daemon lê o "
                    "clique dela como automático e pode recusá-lo"
                )


def test_o_desligado_virou_modo_nativo_e_saiu_da_fileira() -> None:
    """A LÁPIDE do quarto botão, e ela é uma régua — não um comentário.

    Esta régua nasceu (29/08) exigindo o contrário: que o botão ``desligado``
    estivesse na fileira **sem** dono, dizendo o porquê. Ele não tinha leitor —
    ``mode_of_state`` devolve TRÊS valores, nunca um quarto — e estava aberto
    como MIGRA-JOGAR-06.

    **31/08/2026, ela redesenhou o Modo de conexão e a resposta veio pela
    forma:** *Desligado = Modo Nativo, "o DualSense da forma como veio ao
    mundo"*. O botão órfão sumiu do desenho, e a posição Desligado do
    interruptor endereça ``MODE_NATIVE`` — que lê e escreve. A MIGRA-JOGAR-06
    fechou **sem uma linha de produto nova**.

    **A mordida:** devolva ``Modo(MODO_DESLIGADO, …)`` a ``MODOS_DA_TELA`` e as
    duas primeiras asserções caem; devolva o ``data-modo="desligado"`` ao
    desenho e a terceira cai junto com a régua da fileira.
    """
    fileira = {m.chave for m in painel.MODOS_DA_TELA}
    assert painel.MODO_DESLIGADO not in fileira, (
        "o botão órfão voltou à fileira — ele é uma lápide, não um endereço"
    )
    assert painel.MODO_DESLIGADO not in painel.ESCRITOR_DOS_MODOS
    assert painel.MODO_DESLIGADO not in modos_do_desenho()

    assert painel.plano_do_modo(painel.MODO_DESLIGADO) is None
    assert painel.porque_nao_aplica(painel.MODO_DESLIGADO)
    assert "SEM LINHA" in painel.escritor_do_modo(painel.MODO_DESLIGADO)

    assert mode_transition.MODE_NATIVE in fileira
    assert mode_transition.MODE_NATIVE in painel.ESCRITOR_DOS_MODOS
    assert painel.plano_do_modo(mode_transition.MODE_NATIVE)


def test_gesto_de_endereco_inventado_nao_derruba_nem_aplica() -> None:
    """Um ``data-modo`` que o gerador não escreve chega pelo DOM adulterado."""
    assert painel.plano_do_modo("modo-que-nao-existe") is None
    assert painel.porque_nao_aplica("modo-que-nao-existe")
    assert "SEM LINHA" in painel.escritor_do_modo("modo-que-nao-existe")


def test_a_tela_acende_o_modo_vivo_e_nao_o_do_desenho() -> None:
    """O caso DELA, de 30/08 às 21:15, congelado como fixture.

    O ``state_full`` do daemon dela dizia ``gamepad.enabled = False`` e
    ``native_mode = False``; o desenho traz ``class="on"`` chumbado no "Jogar
    pelo Hefesto". A tela tem de acender o que o daemon diz.
    """
    dela = {
        "native_mode": False,
        "gamepad_emulation": {"enabled": False, "flavor": "dualsense"},
        "paused": False,
    }
    assert painel.modo_vivo(dela) == mode_transition.MODE_DESKTOP
    assert painel.modo_vivo(dela) != mode_transition.MODE_GAMEPAD

    ligado = {"native_mode": False, "gamepad_emulation": {"enabled": True}}
    assert painel.modo_vivo(ligado) == mode_transition.MODE_GAMEPAD

    assert painel.modo_vivo(None) is None


def test_o_interruptor_le_dois_modos_como_ligado() -> None:
    """``hefesto_ligado`` — a leitura DERIVADA que o desenho de 31/08 encomendou."""
    navegando = {"native_mode": False, "gamepad_emulation": {"enabled": False}}
    jogando = {"native_mode": False, "gamepad_emulation": {"enabled": True}}
    nativo = {"native_mode": True, "gamepad_emulation": {"enabled": False}}

    assert painel.modo_vivo(navegando) == mode_transition.MODE_DESKTOP
    assert painel.hefesto_ligado(navegando) is True, (
        "a Navegação é o Hefesto LIGADO — quem emula teclado e mouse é ele"
    )
    assert painel.hefesto_ligado(jogando) is True
    assert painel.hefesto_ligado(nativo) is False
    assert painel.hefesto_ligado(None) is None

    for lado in (mode_transition.MODE_GAMEPAD, mode_transition.MODE_NATIVE):
        assert painel.modo_vivo(navegando) != lado, (
            "com o modo vivo em desktop, NENHUMA das duas posições do "
            "interruptor casa — é este o buraco que hefesto_ligado tapa"
        )


def test_o_algarismo_do_circulo_e_derivado_da_escada(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """O número do círculo sai da ``ESCADA``, e não de um literal."""
    from hefesto_dualsense4unix.integrations import ponte_escada

    antes = {c.chave: c.algarismo for c in painel.CHIPS_DA_ESCADA}
    assert antes["dualsense"] == "1", "a DualSense é o primeiro degrau da ESCADA"
    assert antes["navegacao"] == painel.SEM_ALGARISMO

    monkeypatch.setattr(ponte_escada, "ESCADA", tuple(reversed(ponte_escada.ESCADA)))
    depois = {c.chave: c.algarismo for c in painel.CHIPS_DA_ESCADA}
    assert depois != antes, "o algarismo não seguiu a ESCADA — ele está digitado"
    assert depois["dualsense"] == "4" and depois["steam"] == "1"
    assert depois["navegacao"] == painel.SEM_ALGARISMO


def _degraus_sem_lugar_na_tela(painel_: object) -> list[object]:
    """Os degraus da ``ESCADA`` que a tela não mostra em lugar nenhum."""
    from hefesto_dualsense4unix.integrations import ponte_escada

    nomeadas = {c.ponte for c in painel_.CHIPS_DA_ESCADA if c.ponte is not None}  # type: ignore[attr-defined]
    nomeadas |= set(painel_.PONTES_DO_INTERRUPTOR)  # type: ignore[attr-defined]
    return [d for d in ponte_escada.ESCADA if d.ponte not in nomeadas]


def test_a_escada_nao_deve_mais_nada_a_tela(monkeypatch: pytest.MonkeyPatch) -> None:
    """Todo degrau da escada tem onde aparecer — desde 31/08/2026."""
    from hefesto_dualsense4unix.integrations import ponte_escada

    assert _degraus_sem_lugar_na_tela(painel) == []

    monkeypatch.setattr(painel, "PONTES_DO_INTERRUPTOR", frozenset())
    orfaos = _degraus_sem_lugar_na_tela(painel)
    assert [d.ponte for d in orfaos] == [ponte_escada.Ponte(ponte_escada.KIND_NATIVE)], (
        "sem a linha do interruptor a régua acusa o Nativo — e a acusação é FALSA"
    )


def test_sem_degrau_e_sem_dono_sao_perguntas_diferentes() -> None:
    """A Navegação separa as duas, e pintar uma pela outra mente na tela."""
    sem_degrau = [c.chave for c in painel.CHIPS_DA_ESCADA
                  if c.ponte is not None and c.indice < 0]
    sem_dono = [c.chave for c in painel.CHIPS_DA_ESCADA
                if c.indice < 0 and (c.modo or "") not in painel.ESCRITOR_DOS_MODOS]
    assert sem_degrau == ["navegacao"]
    assert sem_dono == []

    navegacao = next(c for c in painel.CHIPS_DA_ESCADA if c.chave == "navegacao")
    assert navegacao.modo in painel.ESCRITOR_DOS_MODOS, (
        "a Navegação TEM escritor — é o que a tira dos sem dono"
    )
    assert "pointclick" not in {c.chave for c in painel.CHIPS_DA_ESCADA}, (
        "a linha fantasma voltou à tabela. Ela não tem `data-degrau` na página "
        "publicada, e o gerador (`aba01.py`) tem trava contra o quinto chip."
    )


def test_as_conferencias_sairam_do_produto() -> None:
    """As perguntas que nenhuma tela fazia não voltam ao ``painel``.

    A-TELA-PERGUNTA-AO-DONO-01, 28/09/2026: a conta que só a régua pergunta
    mora na régua, o leitor do chip aceso é um só (``caminho_vivo``, pelo
    pacote da aba) e o do perfil ativo também (``pacotes.perfil.nome_do_ativo``).
    **A mordida:** devolva qualquer uma ao módulo, e esta régua reprova antes
    de o ``casa-sabe`` voltar a acusá-la sem caminho.
    """
    for nome in ("indice_do_chip", "chips_sem_degrau", "chips_sem_dono",
                 "degraus_sem_chip", "degrau_vivo", "nome_do_perfil"):
        assert not hasattr(painel, nome), (
            f"`painel.{nome}` voltou ao produto sem tela que a pergunte")


def test_a_recusa_do_botao_sem_escritor_e_a_do_dono() -> None:
    """A frase com que o gesto recusa é a de ``escritor_do_modo`` — uma só."""
    for chave in (painel.MODO_DESLIGADO, "modo-que-nao-existe"):
        assert painel.porque_nao_aplica(chave) == painel.escritor_do_modo(chave)
    for chave in painel.ESCRITOR_DOS_MODOS:
        assert painel.porque_nao_aplica(chave) == ""


def test_a_lembranca_tem_um_lugar_so_e_e_o_do_produto(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A memória vem do ``session.load_gamepad_preference`` e de mais lugar nenhum."""
    from hefesto_dualsense4unix.utils import session

    for resposta, esperado in (
        ((True, "dualsense"), True),
        ((False, None), False),
        ((None, None), None),
    ):
        monkeypatch.setattr(session, "load_gamepad_preference", lambda r=resposta: r)
        lembra = painel.modo_lembrado()
        assert lembra.ligado is esperado, f"o dublê disse {resposta}, veio {lembra}"
        assert lembra.frase, "toda lembrança tem de vir com a frase que ela lê"

    monkeypatch.setattr(session, "load_gamepad_preference", lambda: (False, None))
    frase = painel.modo_lembrado().frase
    assert "DESLIGADO" in frase and "reiniciar" in frase


def test_o_disco_lembra_o_desligar_e_o_ligar(tmp_path: pathlib.Path) -> None:
    """O ciclo inteiro, no disco — o "se lembre" que ela pediu."""
    from hefesto_dualsense4unix.utils.session import save_gamepad_emulation
    from hefesto_dualsense4unix.utils.xdg_paths import config_dir

    flag = config_dir(ensure=True) / "gamepad_disabled.flag"

    save_gamepad_emulation(False)
    assert flag.exists(), "desligar tem de GRAVAR o opt-out, senão nada se lembra"
    assert painel.modo_lembrado().ligado is False

    save_gamepad_emulation(True, "dualsense")
    assert not flag.exists(), "ligar tem de APAGAR o opt-out"
    lembra = painel.modo_lembrado()
    assert lembra.ligado is True
    assert lembra.mascara == "dualsense"

    save_gamepad_emulation(False)
    assert flag.exists()
    assert painel.modo_lembrado().ligado is False


def _fonte_do_piloto() -> str:
    if not PILOTO.is_file():
        pytest.skip(f"o piloto não está nesta árvore: {PILOTO}")
    return PILOTO.read_text(encoding="utf-8")


def test_o_piloto_nao_digita_o_dono_do_modo() -> None:
    """A tabela de donos do piloto é LIDA do ``painel``, nunca digitada."""
    fonte = _fonte_do_piloto()
    assert "painel.escritor_do_modo(modo.chave)" in fonte, (
        "o DONOS_DOS_GESTOS do piloto deixou de derivar do painel"
    )
    assert "for modo in painel.MODOS_DA_TELA" in fonte


def test_o_piloto_aplica_pelo_dono_e_nao_por_ipc_cru() -> None:
    """O clique sai por ``mode_transition.apply_mode`` — nunca por IPC cru."""
    fonte = _fonte_do_piloto()
    assert "mode_transition.apply_mode(" in fonte, (
        "o piloto deixou de aplicar pelo dono da sequência"
    )
    corpo = fonte.split('"""', 2)[-1]
    for cru in ("gamepad.emulation.set", "native.mode.set", "mouse.emulation.restore"):
        assert f'"{cru}"' not in corpo and f"'{cru}'" not in corpo, (
            f"o piloto pronuncia {cru!r} cru — a sequência tem UM dono, e é o "
            "mode_transition"
        )


_CLIQUE_POR_ENDERECO = re.compile(r"""querySelector\('\[data-(modo|degrau)=\\"([a-z-]+)\\"\]'\)""")

_DATA_DEGRAU = re.compile(r'data-degrau="([a-z-]+)"')

JOGAR_VIVO = RAIZ / "src" / "hefesto_dualsense4unix" / "interface" / "jogar_vivo.py"


def test_o_roteiro_das_provas_clica_endereco_que_existe() -> None:
    """`.click()` sobre `null` levanta ``TypeError`` — e a régua morre calada."""
    texto = DESENHO.read_text(encoding="utf-8") if DESENHO.is_file() else ""
    if not texto:
        pytest.skip(f"o desenho da aba Jogar não está nesta árvore: {DESENHO}")
    do_desenho = {
        "modo": set(_DATA_MODO.findall(texto)),
        "degrau": set(_DATA_DEGRAU.findall(texto)),
    }
    assert do_desenho["degrau"], "o desenho não tem um único [data-degrau]"

    vistos = 0
    for tool in (PILOTO, JOGAR_VIVO):
        if not tool.is_file():
            continue
        for tipo, alvo in _CLIQUE_POR_ENDERECO.findall(tool.read_text(encoding="utf-8")):
            vistos += 1
            assert alvo in do_desenho[tipo], (
                f"{tool.name} clica [data-{tipo}=\"{alvo}\"], que NÃO existe no "
                f"{DESENHO.name} — `.click()` sobre null levanta TypeError e o "
                "roteiro morre no meio, calado"
            )
    assert vistos >= 4, (
        f"a régua só achou {vistos} cliques por endereço nos dois roteiros — "
        "ou a forma mudou, e então ela deixou de medir"
    )


def test_o_interruptor_da_tela_viva_segue_o_daemon_e_nao_o_clique() -> None:
    """A cura de 31/08, nos dois pilotos — e ela é LIDA, nunca digitada."""
    if not DESENHO.is_file():
        pytest.skip(f"o desenho da aba Jogar não está nesta árvore: {DESENHO}")
    html = DESENHO.read_text(encoding="utf-8")
    for lado in ("ligado", "desligado"):
        assert f'class="hef-pos {lado}"' in html, (
            f"o desenho perdeu o rótulo .hef-pos.{lado} — a pintura endereça por "
            "essa classe e o rádio sai do `for` dele"
        )

    for tool in (PILOTO, JOGAR_VIVO):
        if not tool.is_file():
            continue
        fonte = tool.read_text(encoding="utf-8")
        assert "painel.hefesto_ligado(state)" in fonte, (
            f"{tool.name} deixou de perguntar ao painel de que lado o "
            "interruptor está — a regra 'gamepad OU desktop' não pode viver no JS"
        )
        assert "htmlFor" in fonte, (
            f"{tool.name} deixou de derivar o rádio do `for` do rótulo"
        )
        for chumbado in ("hef-ligado", "hef-desligado"):
            assert chumbado not in fonte, (
                f"{tool.name} DIGITA o id {chumbado!r} — é o que se pode LER, e "
                "digitar o que se lê é a forma dos onze instrumentos falsos de 26/08"
            )


def test_a_aba_jogar_viva_nao_injeta_folha_por_cima_do_desenho() -> None:
    """Nenhuma regra de estilo injetada — o desenho é o dono do que a tela mostra."""
    if not JOGAR_VIVO.is_file():
        pytest.skip(f"a aba viva não está nesta árvore: {JOGAR_VIVO}")
    fonte = JOGAR_VIVO.read_text(encoding="utf-8")
    for ato in ("createElement('style')", "head.appendChild"):
        assert ato not in fonte, (
            f"a aba Jogar viva voltou a injetar folha de estilo ({ato}) — o "
            "estado que faltar se DESENHA no gerador, que é onde ela o vê"
        )


def test_o_piloto_nao_manda_mais_ninguem_para_um_botao_que_nao_existe() -> None:
    """A frase do daemon calado apontava para "Ligar o Hefesto" na aba Sistema."""
    assert 'aba Sistema e clique em "Ligar o Hefesto"' not in _fonte_do_piloto()
    if DESENHO.is_file():
        for html in sorted(DESENHO.parent.glob("*.html")):
            assert "Ligar o Hefesto" not in html.read_text(encoding="utf-8"), (
                f"{html.name} passou a ter o botão — atualize a frase do piloto, "
                "que hoje manda para o systemd"
            )
