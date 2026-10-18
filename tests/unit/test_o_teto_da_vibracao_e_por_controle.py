#!/usr/bin/env python3
"""A cadeia do teto de vibração por controle, do perfil ao motor (17/10/2026).

O CAMPO «Teto da vibração» e o gesto `teto-da-vibracao` da aba Conexões SAÍRAM:
nenhum elemento da página os chamava, e o dono único de
`controllers[chave].rumble.policy` é o gesto `forca` da aba Vibração. Os casos
do gesto e da pintura saíram com ele. Ficam os que medem o que a escolha
vira no caminho: o perfil, as escalas publicadas no backend e o fator que
chega ao motor, mais as contas de `conexoes.py` que o desenho ainda cita.

Todo `uniq` daqui vem da faixa sintética `aa:bb:cc:00:00:01`.
"""
from __future__ import annotations

import pathlib
import re
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src"))
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

UNIQ = "aa:bb:cc:00:00:01"
CHAVE = "aabbcc000001"


def _perfil(nome: str = "Bancada", **campos: Any) -> Any:
    """Um `Profile` DE VERDADE — o esquema é metade do que esta régua mede."""
    from hefesto_dualsense4unix.profiles.schema import Profile

    return Profile.model_validate(
        {"name": nome, "match": {"type": "criteria"}, **campos})


def _perfil_com_economia() -> Any:
    """O perfil que a escolha «30% da força» da aba Vibração deixa no disco."""
    return _perfil(controllers={CHAVE: {"rumble": {"policy": "economia"}}})


@pytest.fixture(autouse=True)
def _perfil_ativo_no_disco() -> None:
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    for nome in ("regua", "Bancada"):
        if not (profiles_dir() / f"{nome.lower()}.json").exists():
            loader.save_profile(Profile(name=nome, match=MatchManual()),
                                origem="regua")


@pytest.fixture
def a08():
    from pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture
def tela():
    from hefesto_dualsense4unix.interface import conexoes as aba_conexoes

    return aba_conexoes


def test_o_rotulo_nao_e_digitado(monkeypatch, tela) -> None:
    """A frase "30% da força" é REPRODUZIDA do produto, nunca digitada."""
    from hefesto_dualsense4unix.daemon.subsystems import rumble as subsistema

    antes = tela.opcoes_do_teto()
    assert "30% da força" in antes, f"o campo mudou de rótulo: {antes}"

    monkeypatch.setitem(subsistema.RUMBLE_POLICY_MULT, "economia", 0.25)
    depois = tela.opcoes_do_teto()

    assert "25% da força" in depois, (
        f"com `RUMBLE_POLICY_MULT['economia'] = 0.25` o campo continuou "
        f"oferecendo {depois}. Alguma camada tem a frase DIGITADA — é o mesmo "
        f"defeito que a dica desta aba tinha em 28/08, quando dizia 60% e o "
        f"produto cortava em 30.")
    assert "30% da força" not in depois, (
        f"o rótulo velho sobreviveu à troca do degrau: {depois}")
    with pytest.raises(ValueError):
        tela.politica_do_rotulo("30% da força")


def test_o_fator_que_chega_ao_hardware_e_zero_ponto_tres() -> None:
    """Do disco ao motor: `economia` sobre base `balanceado` vira `(200,200)→(60,60)`."""
    from hefesto_dualsense4unix.profiles.manager import _controllers_to_rumble_scales

    novo = _perfil_com_economia()

    escalas = _controllers_to_rumble_scales(novo.controllers, novo.rumble)
    assert escalas == {CHAVE: pytest.approx(0.3)}, (
        f"as escalas publicadas foram {escalas!r}. Sem opinião global, a base é "
        f"o `_RUMBLE_POLICY_PADRAO = 'balanceado'` (1,0), então o fator tem de "
        f"ser 0,3/1,0.")

    from hefesto_dualsense4unix.core.backend_pydualsense import PyDualSenseController

    motor = PyDualSenseController.__new__(PyDualSenseController)
    motor._rumble_scale_by_uniq = {}
    import threading

    motor._io_lock = threading.RLock()
    motor.set_rumble_scales(escalas)
    assert _no_motor(motor, CHAVE) == 60, (
        f"o motor receberia {_no_motor(motor, CHAVE)} em vez de 60 — o rótulo "
        f"promete 30% de 200.")
    assert _no_motor(motor, "aabbcc000002") == 200


def test_a_ativacao_do_perfil_publica_as_escalas_no_backend() -> None:
    """O elo que faz a escolha do usuário VALER AGORA — e que régua nenhuma cobria.

    `perfil.gravar_e_reaplicar` pede `profile.switch`; quem o atende chama
    `ProfileManager.apply`, e é ali (`profiles/manager.py:206-211`) que o mapa
    por-peça é publicado no backend. Sem esse elo o perfil muda no disco e o
    motor continua com a força velha até o próximo start do daemon.

    MEDIDO em 01/09/2026: nenhum teste desta casa cobria a chamada — o
    `test_por_unidade_01_todas_as_abas.py` mede as pontas
    (`_controllers_to_rumble_scales` e o fator no motor) e não o meio.

    MORDIDA: arranque o `escalar_rumble(escalas_rumble or None)` de
    `ProfileManager.apply` — este caso reprova dizendo que nada foi publicado.
    """
    from hefesto_dualsense4unix.profiles.manager import ProfileManager
    from hefesto_dualsense4unix.testing.fake_controller import FakeController

    class Espiao(FakeController):
        def __init__(self, **kw: Any) -> None:
            super().__init__(**kw)
            self.publicadas: list[Any] = []

        def set_rumble_scales(self, scales: Any = None) -> None:
            self.publicadas.append(None if scales is None else dict(scales))

    fc = Espiao(transport="usb")
    fc.connect()
    ProfileManager(controller=fc).apply(_perfil_com_economia())

    assert fc.publicadas == [{CHAVE: pytest.approx(0.3)}], (
        f"a ativação publicou {fc.publicadas!r} no backend. Sem o mapa, o "
        f"`escala_de` do funil não tem fator e o motor recebe a força inteira — o "
        f"perfil dela mudaria no disco e o aparelho não.")


def _pagina_publicada() -> str:
    import onde

    return (onde.PUBLICADO / "08-conexoes.html").read_text(encoding="utf-8")


def test_o_piloto_sabe_pintar_html() -> None:
    """O `BOOTSTRAP` tem o ramo `html` — sem ele a dica mostraria os marcadores."""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    assert "alvo === 'html'" in hefesto_vivo.BOOTSTRAP, (
        "o `escrever()` do piloto não tem o alvo `html`")
    ramo = hefesto_vivo.BOOTSTRAP.split("alvo === 'html'", 1)[1]
    ramo = ramo.split("if(alvo ===", 1)[0]
    assert re.search(r"el\.innerHTML\s*=", ramo), (
        "o alvo `html` existe e não escreve `innerHTML`")


def test_a_recusa_velha_saiu_dos_dois_lugares(a08, tela) -> None:
    """O fato errado sai de TODOS os lugares — regra, 11/08/2026.

    A afirmação *"o produto aplica `min` … sobrepor mudaria o daemon"* estava em
    DOIS: no `SEM_GESTO` deste pacote e no `SEM_FONTE` da camada de tela. Uma
    correção pela metade deixa as duas versões vivas, que é o defeito que a
    regra existe para matar.
    """
    enderecos = {linha[0] for linha in tela.SEM_FONTE}
    assert "controle.*.vibracao.teto" not in enderecos, (
        "a linha antiga continua em `SEM_FONTE` dizendo que a tela inteira não "
        "tem fonte — duas das três opções têm.")
    sobrou = [linha for linha in tela.SEM_FONTE
              if linha[0] == "controle.*.vibracao.sem-teto"]
    assert sobrou, "a recusa que SOBRA ('Sem teto') não está declarada"
    assert "MIGRA-CONEXOES-11" in sobrou[0][2], (
        f"a linha que sobrou não nomeia a dona: {sobrou[0][2]!r}")


_FOLHA = re.compile(r"<(style|script)\b.*?</\1>", re.S | re.I)
_COMENTARIO_HTML = re.compile(r"<!--.*?-->", re.S)
_TAG = re.compile(r"<[^>]+>")


def _texto_visivel(bruto: bytes) -> str:
    texto = _FOLHA.sub(" ", bruto.decode("utf-8"))
    texto = _COMENTARIO_HTML.sub(" ", texto)
    return " ".join(_TAG.sub(" ", texto).split())


def test_o_desenho_dela_so_mudou_no_que_esta_declarado() -> None:
    """A bancada e o publicado dizem as MESMAS PALAVRAS, byte a byte.

    **ESTE CASO ENCOLHEU EM 03/09/2026, e a razão é a sprint
    `IDENTIDADE-VEM-DE-CIMA-01`.** Ele exigia igualdade byte a byte entre a
    bancada e o publicado, descontada UMA cura nomeada (o quarto selo). A
    sprint da identidade mudou a FORMA de três coisas nesta aba — a cor do
    plástico saiu de um `--plastico` inline e virou a tinta de um `<i>` de 3px;
    a régua do rádio ganhou um recipiente com endereço; a lista de aparelhos
    ganhou o dela —, e nenhuma delas move um pixel.

    **UMA LISTA DE DESCONTOS QUE CRESCE A CADA SPRINT NÃO É RÉGUA, É DIÁRIO.**
    Ela ficaria verde por construção — cada leva acrescentaria a própria linha
    —, que é o defeito que esta casa chama de *régua que digita o que devia
    ler*. Então ele passou a medir o que continua sendo verdade e o que ele
    consegue ler sem lista nenhuma: **as palavras da tela.**

    O QUE ELE AINDA PEGA: uma palavra trocada, uma frase que sumiu, um número
    que mudou, uma dica reescrita — tudo o que chega aos olhos como TEXTO.

    O QUE ELE DEIXOU DE PEGAR, e está dito porque um buraco calado é pior que
    um buraco: uma COR mudada, uma medida de CSS, um bloco movido. Quem cobre
    isso são dois outros, e os dois estão ligados: o portão `desenho-aprovado`
    reprova QUALQUER divergência entre bancada e publicado que não esteja
    declarada em `mockup/DIVERGENCIAS.md` — e a declaração é o que ela lê antes
    de publicar —, e a `scripts/check_identidade_vem_de_cima.py` cobra que
    nenhuma cor de plástico fique congelada na página.

    **O NOME PROMETIA O QUE O CORPO NÃO FAZIA — corrigido em 03/09/2026.** Ele
    se chama *"só mudou no que está DECLARADO"* e nunca abriu a declaração:
    exigia igualdade de texto sempre, e por isso ficava vermelho no instante em
    que alguém fazia a coisa certa — adiantar a bancada e declarar a divergência
    em `mockup/DIVERGENCIAS.md`, que é o processo desta casa. Reprovava o
    processo, não o defeito.

    Em 03/09 a `08-conexoes` foi declarada duas vezes (o `MIGRA-08-01`, com dez
    endereços de pintura, e o desenho do controle que passou a vestir o
    aparelho), e a declaração diz o que ela vê hoje sem publicar. A régua passou
    a ler a MESMA fonte que o portão `desenho-aprovado` lê — `declaradas()`, do
    próprio script —, e a cobrar cada caso no seu estado:

    * **não declarada** → as palavras têm de bater. É a mordida original, e é a
      que pega a palavra trocada de fininho;
    * **declarada** → a bancada pode estar à frente, e o que se cobra é que a
      declaração exista de verdade. Some no dia do `--publicar`, e a igualdade
      volta a ser exigida sozinha.

    MORDIDAS (duas): mude uma palavra visível de um `<option>` no gerador,
    regere e tire a seção da `DIVERGENCIAS.md` — reprova com a palavra na
    mensagem; ou deixe a seção lá com o corpo vazio — reprova dizendo que
    declaração sem razão não é declaração.
    """
    import importlib.util

    import onde

    alvo = RAIZ / "scripts/check_o_desenho_aprovado.py"
    spec = importlib.util.spec_from_file_location("check_desenho_da_regua", alvo)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["check_desenho_da_regua"] = mod
    spec.loader.exec_module(mod)

    bancada = _texto_visivel(mod.o_que_se_ve(onde.BANCADA / "08-conexoes.html"))
    publicado = _texto_visivel(mod.o_que_se_ve(onde.PUBLICADO / "08-conexoes.html"))

    if "08-conexoes.html" not in mod.declaradas():
        assert bancada == publicado, (
            "a bancada da 08 passou a DIZER uma coisa que o publicado não diz — "
            "e palavra de tela é decisão dela, não de quem gera a página. Se "
            "isso é adiantamento com razão, declare em `mockup/DIVERGENCIAS.md`.")
        return

    texto = (RAIZ / "mockup/DIVERGENCIAS.md").read_text(encoding="utf-8")
    corpo = texto.split("\n---\n", 1)[-1]
    secao = corpo.split("## 08-conexoes.html", 1)[-1].split("\n## ", 1)[0]
    assert secao.strip(), (
        "a `08-conexoes.html` está declarada em `mockup/DIVERGENCIAS.md` com a "
        "seção VAZIA. Um título sem razão isenta a aba do portão sem contar a "
        "ninguém o que mudou — que é o oposto do que a declaração existe para "
        "fazer.")


def test_a_divergencia_do_quarto_selo_esta_declarada() -> None:
    """Bancada à frente do publicado só vale DECLARADA — é o portão do desenho."""
    bancada = (RAIZ / "mockup/08-conexoes.html").read_bytes()
    publicado = (
        RAIZ / "src/hefesto_dualsense4unix/interface/paginas/08-conexoes.html"
    ).read_bytes()
    texto = (RAIZ / "mockup/DIVERGENCIAS.md").read_text(encoding="utf-8")
    corpo = texto.split("\n---\n", 1)[-1]
    declarada = "## 08-conexoes.html" in corpo

    if bancada == publicado:
        assert not declarada, (
            "a bancada da 08 e o produto são byte-idênticos, e ainda há uma "
            "seção dizendo que a aba está EM TRABALHO — a lápide sobreviveu à "
            "publicação e vai enganar quem ler o arquivo")
        return
    assert declarada, (
        "a bancada da 08 andou à frente do publicado e ninguém declarou — o "
        "portão `desenho-aprovado` reprova, e com razão")


def _no_motor(motor: Any, uniq: str, viva: str = "balanceado", pedido: int = 200) -> int:
    """O que chega ao motor de ``uniq``: o funil `forca_do_controle`, com a peça
    lida do backend por `escala_de`, como os três caminhos de vibração a leem.
    """
    from hefesto_dualsense4unix.core.rumble import forca_do_controle
    from hefesto_dualsense4unix.daemon.lifecycle import DaemonConfig

    cfg = DaemonConfig()
    cfg.rumble_policy = viva
    forca = forca_do_controle(cfg, uniq, 100, {}, 0.0, escala=motor.escala_de(uniq))
    return max(0, min(255, round(pedido * forca)))


def test_o_global_do_perfil_nao_e_o_que_multiplica(tela) -> None:
    """`Profile.rumble.policy` é DENOMINADOR, e não o global que a tela reporta."""
    from hefesto_dualsense4unix.core.rumble import SEM_TETO

    segue = tela.teto_que_vale(tela.Vibracao(do_perfil="economia", a_viva="balanceado"))
    assert SEM_TETO not in segue[1], (
        f"a dica afirma {SEM_TETO!r} com a política viva em `balanceado`: {segue[1]!r}")
    assert "<b>100% da força</b>" in segue[1], (
        f"sem override, o motor recebe o que a viva deixa passar (1,0): {segue[1]!r}")

    sobre = tela.teto_que_vale(
        tela.Vibracao(do_controle="economia", do_perfil="economia", a_viva="balanceado"))
    assert "<b>100% da força</b>" in sobre[1], (
        f"o fator relativo ao próprio global do perfil é 1,0: {sobre[1]!r}")


def test_o_teto_do_orcamento_entra_por_cima_da_politica_viva(tela) -> None:
    """O `maquina.json` limita a viva com `min`, e a dica mostra o resultado."""
    sob_teto = tela.teto_que_vale(tela.Vibracao(a_viva="max", orcamento="economia"))[1]
    assert "<b>30% da força</b>" in sob_teto, (
        f"o orçamento `economia` não limitou o global `max`: {sob_teto!r}")
    sem_teto = tela.teto_que_vale(tela.Vibracao(a_viva="max", orcamento=None))[1]
    assert "<b>150% da força</b>" in sem_teto, (
        f"sem orçamento declarado o `max` passa inteiro: {sem_teto!r}")


@pytest.mark.parametrize("campos,porque", [
    ({"a_viva": None}, "o serviço não publicou o `rumble_policy`"),
    ({"a_viva": "auto"}, "o degrau do `auto` muda com a bateria a cada tique"),
    ({"a_viva": "balanceado", "a_mesa_respondeu": False},
     "o `maquina.json` não deu para ler"),
])
def test_o_que_nao_se_sabe_nao_vira_a_afirmacao_sem_teto(tela, campos, porque) -> None:
    """"Não sei" é uma resposta; "Sem teto" é uma AFIRMAÇÃO sobre um limite.

    Os três casos abaixo viravam a palavra em negrito **"Sem teto"** antes de
    01/09/2026 — a ausência de notícia lida como sucesso, no campo que ela
    clica. O dono da fonte proíbe a troca com todas as letras
    (`secao_orcamento.orcamento_em_vigor`: *"None aqui significa 'não sei',
    nunca 'sem teto'"*), e o `_orcamento_da_mesa` tinha um `except Exception:
    return None` que a fazia em silêncio.

    MORDIDA: em `forca_no_motor`, troque o `return None` do desvio do
    `a_mesa_respondeu` por `return 1.0` — o terceiro caso reprova, porque a tela
    passa a afirmar 100% sobre um arquivo que não foi lido.
    """
    from hefesto_dualsense4unix.core.rumble import SEM_TETO

    frase = tela.teto_que_vale(tela.Vibracao(**campos))[1]
    assert SEM_TETO not in frase, f"afirmou {SEM_TETO!r} quando {porque}: {frase!r}"
    assert "% da força" not in frase, (
        f"afirmou um percentual quando {porque}: {frase!r}")
    assert tela.NAO_SEI_A_FORCA in frase, (
        f"não disse que não sabe quando {porque}: {frase!r}")


def test_a_frase_do_orcamento_passa_pelo_dono_do_numero(tela, monkeypatch) -> None:
    """`fala_do_teto` deriva de `core.rumble.teto_do_orcamento`, o dono declarado.

    ERA A QUARTA GRAFIA da regra "chave de orçamento → frase do teto", e a única
    que não passava pelo dono: as outras três (`interface.sistema.forca_do_perfil`,
    `secao_orcamento.celula_do_teto` e `_dica_da_bateria_longa`) já o chamavam.
    Medido com o dono mordido para 0,5: a aba Sistema dizia "50% da força" e esta
    aba dizia "30%" — duas abas do mesmo produto, dois números para o mesmo fato.

    MORDIDA: esta é a mordida — o monkeypatch abaixo troca o DONO. Com a conta
    escrita à mão em `fala_do_teto` (o `if chave != _ORCAMENTO_COM_TETO` indo
    direto ao `RUMBLE_POLICY_MULT`), este caso reprova.
    """
    import hefesto_dualsense4unix.core.rumble as nucleo

    monkeypatch.setattr(nucleo, "teto_do_orcamento",
                        lambda o: 0.5 if o == "economia" else None)
    assert tela.fala_do_teto("economia") == "50% da força", (
        f"a frase não seguiu o dono do número: {tela.fala_do_teto('economia')!r}")


def test_o_numero_da_recusa_e_derivado_e_nao_digitado(tela, monkeypatch) -> None:
    """O `0,667` da recusa de "Sem teto" sai da tabela, não de três literais."""
    from hefesto_dualsense4unix.daemon.subsystems import rumble as subsistema

    monkeypatch.setitem(subsistema.RUMBLE_POLICY_MULT, "max", 2.0)
    with pytest.raises(ValueError) as erro:
        tela.politica_do_rotulo("Sem teto")
    assert "1/2 = 0,500" in str(erro.value), (
        f"a conta da recusa não acompanhou o degrau: {erro.value}")


def test_o_select_do_piloto_nao_conta_pintura_sobre_valor_que_nao_e_opcao() -> None:
    """Escrever `—` num `<select>` deixa `selectedIndex = -1` e mente para sempre."""
    from hefesto_dualsense4unix.interface import hefesto_vivo

    ramo = hefesto_vivo.BOOTSTRAP.split("if(alvo === 'valor')", 1)
    assert len(ramo) == 2, "o ramo `valor` do BOOTSTRAP mudou de forma"
    corpo = ramo[1].split("if(alvo === 'html')", 1)[0]
    assert "SELECT" in corpo and "el.options" in corpo, (
        "o ramo `valor` voltou a escrever em qualquer elemento sem conferir se um "
        "`<select>` oferece a opção — o contador de pinturas passa a mentir a cada "
        f"tique no lugar vazio da mesa. Corpo: {corpo!r}")


def test_a_camada_de_tela_desta_aba_continua_sem_gtk() -> None:
    """A linha 1 de `interface/conexoes.py` promete *"sem GTK"*, e o teto o quebrou."""
    import subprocess

    codigo = (
        "import sys\n"
        "from hefesto_dualsense4unix.interface import conexoes as t\n"  # noqa-acento: nome do módulo
        "t.opcoes_do_teto()\n"
        "t.fala_do_teto('economia')\n"
        "t.teto_que_vale(t.Vibracao(a_viva='balanceado'))\n"
        "c = t.Controle(uniq='aa:bb:cc:00:00:01', jogador=1, via='usb', bateria=50,\n"
        "               plastico='#fff', cor_nome='Branco', fabricante='Sony',\n"
        "               mic_ligado=False)\n"
        "t.texto_da_contagem([c])\n"
        "print('gi.repository.Gtk' in sys.modules)\n"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo], check=True, capture_output=True, text=True,
        env={"PYTHONPATH": str(RAIZ / "src"), "PATH": "/usr/bin:/bin",
             "HOME": "/nao-existe"},
    )
    assert saida.stdout.strip() == "False", (
        "o caminho do teto da vibração puxou `gi.repository.Gtk` para o processo, "
        "e a linha 1 deste módulo promete `sem GTK` — com três consequências "
        f"medidas escritas logo abaixo dela. Saída: {saida.stdout!r}")
