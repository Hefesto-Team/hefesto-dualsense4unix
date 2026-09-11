"""SOM-BOTOES-01 — os botões do som fazem o que dizem? Medido, em 11/09/2026.

**A QUEIXA DELA NÃO ERA UM DEFEITO: ERA UMA DESCONFIANÇA.** *"tipo sobre o som
ta funcionando como deveria mas não sei se os botões funcionam lá como
deveriam. eu não sei explicar funciona mas sinto que tem algo errado."*
<!-- noqa-acento: citação literal dela -->
Ela estava certa duas vezes, e as duas viviam na fileira de três botões do
alto-falante.

## O PRIMEIRO — «Ouvir junto» NUNCA ACENDIA

`a02_controles.A_FILEIRA_TEM_TRES` valia `False` com a página publicada
trazendo o botão quatro vezes. Medido, com a mesma função, duas respostas::

    A_FILEIRA_TEM_TRES (do import)      False
    _a_pagina_tem_o_ouvir_junto() agora True

A causa são três defeitos empilhados na mesma linha, e a razão de cada um está
na docstring de `_a_pagina_tem_o_ouvir_junto`. O resumo: a atribuição rodava
**antes** de `PAGINA` existir, o `NameError` disso caía num `except Exception`
que o devolvia como *"a página não tem o botão"*, e a leitura ainda por cima
perguntava à BANCADA em vez do PUBLICADO.

O que ela via: clicava «Ouvir junto», o gesto gravava `fonte: mix` no perfil —
e a fileira continuava acesa no botão de antes. *Um botão que grava e não diz
nada*, que é a família de defeito que esta aba inteira veio matar.

**E NENHUMA RÉGUA VIA, porque a que existia mediu o próprio dublê.** As quatro de
leitura da `test_a02_a_fonte_do_som_ganha_gesto.py` passam por uma fixture que
faz `monkeypatch.setattr(a02, "A_FILEIRA_TEM_TRES", True)`. Ela nasceu em 10/09,
quando a página ainda não tinha o botão e o `False` era a verdade; o
`--publicar 02` de `5fdbf090` mudou o mundo e a fixture continuou afirmando o
mundo de ontem. **Esta régua não monkeypatcha essa constante em teste nenhum** —
é a diferença inteira entre as duas.

## O SEGUNDO — sair do «Todo o som do PC» deixava o firmware lá

O ramo do «Ouvir junto» devolvia a saída padrão do sistema (camada 1) e **não
tocava no byte da rota** (camada 2). Vindo de «Todo o som do PC» isso deixa o
firmware em `SAIDA_SO_NO_ALTO_FALANTE` com a camada 1 de volta na televisão —
o desacordo exato que `audio_saida.recado_da_rota` existe para denunciar. O
cartão acendia «Ouvir junto» e publicava, na mesma coluna, *"(…) Clique em
'Todo o som do PC' para mandá-lo para cá"*: a tela mandando desfazer o clique
que ela acabou de dar.

A cura é condicional de propósito — vindo de «Sons do jogo» o byte já é o certo
e mandá-lo de novo escreveria no aparelho uma escolha que ela não fez, que é o
contrato do `test_o_junto_nao_manda_byte_de_rota_ao_daemon` da régua irmã.

## O QUE ESTA RÉGUA NÃO MEDE

O ouvido. Som e microfone só fecham com ela ouvindo (§5 da sprint), e nenhuma
linha daqui toca o aparelho: a ponte é de papel, a camada 1 é dublê e o `HOME`
vai para um diretório temporário.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "src/hefesto_dualsense4unix/interface"))

#: Faixa sintética desta casa — há DOIS portões de anonimato nesta árvore.
P1 = "aa:bb:cc:00:00:01"
P2 = "aa:bb:cc:00:00:02"
CHAVE_P1 = P1.replace(":", "")
CHAVE_P2 = P2.replace(":", "")
NOME = "Regua-Dos-Botoes-Do-Som"

#: O sinal do terceiro botão na página. É o mesmo literal que o produto procura,
#: e ele está aqui porque a régua tem de saber o que perguntar ao arquivo — não
#: para repetir a resposta.
MARCA_DO_JUNTO = 'data-hef-quando="junto"'


class Ponte:
    """O daemon de papel. `recusa` faz `speaker_set` dizer não, uma vez."""

    def __init__(self, recusa: bool = False) -> None:
        self.chamadas: list[tuple[str, dict[str, Any]]] = []
        self.recusa = recusa

    def __getattr__(self, nome: str) -> Any:
        def registrar(*a: Any, **k: Any) -> Any:
            self.chamadas.append((nome, dict(k)))
            if nome == "speaker_set" and self.recusa:
                return False
            if nome.endswith("_detalhado"):
                return {"status": "ok", "por_uniq": True}
            return True

        return registrar

    @property
    def nomes(self) -> list[str]:
        return [c[0] for c in self.chamadas]

    def so(self, nome: str) -> list[dict[str, Any]]:
        return [p for n, p in self.chamadas if n == nome]


@pytest.fixture(autouse=True)
def _o_cache_da_camada_1_comeca_vazio() -> Any:
    """Esta régua mede o MÓDULO, então ela garante o estado do módulo.

    ACHADO NA COSTURA DE 11/09/2026, e o envenenador é ANTERIOR a esta leva:
    `test_a02_o_botao_do_mic_tem_tres_estados.py` (commit `79bde59e`, de 10/09)
    chama `a02.pacote(ctx)` de verdade, e o `pacote` preenche o cache de módulo
    `_CAMADA_1` com a leitura daquele contexto. Quem roda DEPOIS dele no mesmo
    processo lê o resto do vizinho: `aceso_da_rota` acha `_CAMADA_1[P1]` e
    devolve o `botao_aceso` de lá (`""`) em vez de ler o byte do `entry`.

    MEDIDO, e a bissecção dá o par exato:
        pytest test_a02_o_botao_do_mic_tem_tres_estados.py <este arquivo>
            → 1 failed — `assert '' == 'jogo'`
        pytest <este arquivo>
            → 19 passed

    A casa já nomeou esta família duas vezes — *um default de função média o
    mundo do import* e *o dublê mais POBRE que o produto*. A saída é a mesma das
    duas: **estado de módulo tem um dono, e quem mede o módulo o zera.** Zerar
    aqui não afrouxa nada: o que esta classe quer medir é `aceso_da_fileira`
    sobre o `entry` que ELA monta, e o cache vazio é exatamente o estado dos
    primeiros milissegundos da aba, que a docstring de `aceso_da_rota` descreve.
    """
    from pacotes import a02_controles as a02

    antes = dict(a02._CAMADA_1)
    a02._CAMADA_1.clear()
    quando, em_voo = a02._CAMADA_1_QUANDO[0], a02._CAMADA_1_EM_VOO[0]
    a02._CAMADA_1_QUANDO[0] = 0.0
    a02._CAMADA_1_EM_VOO[0] = False
    yield
    # E DEVOLVE O QUE ACHOU: um teste que limpa a casa do vizinho e não a
    # devolve troca um defeito de ordem por outro, na direção contrária.
    a02._CAMADA_1.clear()
    a02._CAMADA_1.update(antes)
    a02._CAMADA_1_QUANDO[0] = quando
    a02._CAMADA_1_EM_VOO[0] = em_voo


@pytest.fixture
def casa(tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> pathlib.Path:
    """Um lar de mentira com um perfil ativo. Nada dela é tocado."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from hefesto_dualsense4unix.profiles import loader
    from hefesto_dualsense4unix.profiles.schema import MatchManual, Profile
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    profiles_dir().mkdir(parents=True, exist_ok=True)
    loader.save_profile(Profile(name=NOME, match=MatchManual()), origem="regua")
    return profiles_dir()


@pytest.fixture
def sem_maquina_dela(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    """A camada 1 e o tocador viram dublê. NADA sai desta régua para o PipeWire.

    Sem isto o ramo do «Ouvir junto» rodaria `pactl` de verdade e mexeria na
    saída padrão do sistema DELA — a régua estragando a máquina que ela está
    usando para medir se o botão funciona.
    """
    from hefesto_dualsense4unix.app import audio_saida
    from pacotes import a02_controles as a02

    visto: dict[str, list[Any]] = {"mandou": [], "devolveu": []}
    monkeypatch.setattr(
        a02.audio_saida, "mandar_o_som_do_pc",
        lambda u, m=(), **k: (visto["mandou"].append(u)
                              or audio_saida.DesfechoDaRota(True, "", "sink-falso")))
    monkeypatch.setattr(
        a02.audio_saida, "devolver_o_som_do_pc",
        lambda **k: (visto["devolveu"].append(True)
                     or audio_saida.DesfechoDaRota(True)))
    monkeypatch.setattr(a02.audio_saida, "tocar_confirmacao",
                        lambda *a, **k: None)
    return visto


def _dele(uniq: str, *, rota: int | None = 2, fonte: str | None = None,
          volume: int = 100) -> dict[str, Any]:
    speaker: dict[str, Any] = {"volume": volume, "muted": False}
    if rota is not None:
        speaker["rota"] = rota
    if fonte is not None:
        speaker["fonte"] = fonte
    return {"uniq": uniq, "transport": "usb", "connected": True, "inputs": {},
            "audio": {"mic_mudo": False}, "speaker": speaker}


def _ctx(*entradas: dict[str, Any]) -> Any:
    import pacotes

    return pacotes.Contexto(state={"active_profile": NOME}, mesa=[],
                            conectados=list(entradas) or [_dele(P1)], estados={})


def _gesto(nome: str) -> Any:
    import pacotes
    import pacotes.a02_controles  # importar é registrar

    fn = pacotes.gesto_da_pagina("02-controles.html", nome)
    assert fn is not None, f"02-controles.html:{nome} não tem dono"
    return fn


def _do_controle(chave: str) -> dict[str, Any]:
    from hefesto_dualsense4unix.utils.xdg_paths import profiles_dir

    alvo = profiles_dir() / f"{NOME.lower().replace('-', '_')}.json"
    if not alvo.exists():
        return {}
    dos = json.loads(alvo.read_text(encoding="utf-8")).get("controllers") or {}
    bloco = dos.get(chave)
    return bloco if isinstance(bloco, dict) else {}


def _pagina_publicada() -> str:
    from hefesto_dualsense4unix.interface import onde
    from pacotes import a02_controles as a02

    return onde.pagina(a02.PAGINA, publicado=True).read_text(encoding="utf-8")


# ===========================================================================
# 1. O guarda da fileira responde sobre a PÁGINA, e responde certo
# ===========================================================================


class TestOGuardaDaFileira:
    def test_o_valor_do_import_bate_com_a_pagina_publicada(self) -> None:
        """A constante DE VERDADE, sem monkeypatch, contra o arquivo.

        MORDIDA: devolva `A_FILEIRA_TEM_TRES` para onde ela morava — acima de
        `PAGINA`, 400 linhas atrás. Com o `except` estreito de hoje o import
        REPROVA com `NameError`; com o `except Exception` de ontem ele responde
        `False` e este `assert` reprova nomeando a divergência. É o único teste
        desta casa que olha o valor real da constante: as quatro da régua irmã
        a monkeypatcham, e foi por isso que o defeito atravessou uma publicação
        inteira.
        """
        from pacotes import a02_controles as a02

        tem = MARCA_DO_JUNTO in _pagina_publicada()
        assert a02.A_FILEIRA_TEM_TRES is tem, (
            f"a página publicada {'TEM' if tem else 'NÃO tem'} o «Ouvir junto» "
            f"e o pacote acha que {a02.A_FILEIRA_TEM_TRES}")

    def test_ele_pergunta_ao_publicado_e_nao_a_bancada(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: tire o `publicado=True` da leitura.

        O padrão de `onde.pagina` é a BANCADA, e o produto renderiza o
        PUBLICADO — o piloto abre sempre a página do pacote. Uma bancada sem o
        botão apagaria o terceiro estado de uma tela que o tem.
        """
        from hefesto_dualsense4unix.interface import onde
        from pacotes import a02_controles as a02

        mentira = tmp_path / "mockup"
        mentira.mkdir()
        (mentira / a02.PAGINA).write_text(
            "<html><body>fileira de dois</body></html>", encoding="utf-8")
        monkeypatch.setattr(onde, "BANCADA", mentira)

        assert a02._a_pagina_tem_o_ouvir_junto() is (
            MARCA_DO_JUNTO in _pagina_publicada()), (
            "o guarda leu a bancada; quem o produto renderiza é o publicado")

    def test_um_erro_de_programacao_nao_vira_fato_sobre_o_desenho(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """MORDIDA: alargue o `except` de volta para `Exception`.

        Foi o `except Exception` que transformou um `NameError` em *"a página
        não tem o botão"* e escondeu o defeito por uma publicação inteira. Só
        arquivo que falta ou não abre pode ser engolido; o resto sobe.
        """
        from hefesto_dualsense4unix.interface import onde
        from pacotes import a02_controles as a02

        def _explode(*_a: Any, **_k: Any) -> Any:
            raise RuntimeError("o nome ainda não existe neste ponto do import")

        monkeypatch.setattr(onde, "pagina", _explode)  # noqa-acento: atributo
        with pytest.raises(RuntimeError):
            a02._a_pagina_tem_o_ouvir_junto()

    def test_arquivo_que_nao_abre_continua_sendo_um_nao(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A outra metade: `OSError` É engolido, e vira `False`.

        MORDIDA: tire o `except` inteiro. Uma árvore sem a página publicada
        (um wheel a meio caminho) derrubaria o import da aba, e a tela não
        abriria por causa de um botão.
        """
        from hefesto_dualsense4unix.interface import onde
        from pacotes import a02_controles as a02

        def _sem_arquivo(*_a: Any, **_k: Any) -> Any:
            raise OSError("a página publicada não está aqui")

        monkeypatch.setattr(onde, "pagina", _sem_arquivo)  # noqa-acento: atributo
        assert a02._a_pagina_tem_o_ouvir_junto() is False


# ===========================================================================
# 2. A fileira acende o do meio — com o valor REAL do módulo
# ===========================================================================


class TestOQueATelaAcende:
    def test_com_mix_a_fileira_acende_o_ouvir_junto(self) -> None:
        """O produto, sem dublê de constante nenhum.

        MORDIDA: qualquer um dos três defeitos do guarda faz `aceso_da_fileira`
        devolver `"jogo"` aqui — o botão de antes, sobre uma escolha nova. Era
        exatamente o que ela via.
        """
        from pacotes import a02_controles as a02

        if MARCA_DO_JUNTO not in _pagina_publicada():
            pytest.skip("a página publicada ainda tem dois botões")
        assert a02.aceso_da_fileira(P1, _dele(P1, fonte="mix")) == "junto"
        assert a02.aceso_da_fileira(P1, _dele(P1, fonte="sfx")) == "jogo"

    def test_a_pagina_e_o_pacote_falam_do_mesmo_botao(self) -> None:
        """O `data-hef-quando` que o pacote emite existe NA PÁGINA publicada.

        MORDIDA: troque `ROTA_OUVIR_JUNTO` por outra palavra. O pacote emitiria
        um valor que casa `data-hef-quando` nenhum, e a fileira apagaria
        INTEIRA — sem uma palavra, e sem régua que visse.
        """
        from pacotes import a02_controles as a02

        doc = _pagina_publicada()
        if MARCA_DO_JUNTO not in doc:
            pytest.skip("a página publicada ainda tem dois botões")
        assert f'data-hef-quando="{a02.ROTA_OUVIR_JUNTO}"' in doc


# ===========================================================================
# 3. Sair do «Todo o som do PC» devolve as DUAS camadas
# ===========================================================================


class TestSairDoTodoOSomDoPC:
    def test_o_junto_vindo_do_pc_devolve_o_byte_da_rota(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: apague o ramo que reenvia `rota` no «Ouvir junto».

        Sem ele o firmware fica em «só no alto-falante» com a camada 1 de volta
        na televisão, e o cartão publica a ressalva que manda desfazer o clique.
        """
        from pacotes import a02_controles as a02

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC])),
                       {"uniq": P1, "rota": "junto"}, p)

        pedidos = p.so("speaker_set")
        assert pedidos, "o «Ouvir junto» não devolveu o byte da rota ao daemon"
        assert pedidos[0]["rota"] == a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO]
        assert pedidos[0]["uniq"] == P1, "o byte foi para outro controle"
        assert sem_maquina_dela["devolveu"], "a camada 1 não foi devolvida"

    def test_o_cartao_para_de_mandar_desfazer_o_clique_dela(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """A ressalva do cartão some — é ela que ela LERIA depois do clique.

        MORDIDA: a mesma de cima. Com o byte em «todo o som do PC» e a saída
        padrão em outro lugar, `recado_da_rota` devolve
        `MOTIVO_ROTA_SO_NO_BYTE` — a tela mandando clicar no botão que ela
        acabou de largar.
        """
        from hefesto_dualsense4unix.app import audio_saida
        from pacotes import a02_controles as a02

        antes = a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC]
        assert audio_saida.recado_da_rota(antes, "sink-do-p1", "sink-da-tv"), (
            "a régua não reproduz o desacordo que ela veio medir")

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=antes)), {"uniq": P1, "rota": "junto"}, p)
        depois = p.so("speaker_set")[0]["rota"]
        assert audio_saida.recado_da_rota(depois, "sink-do-p1", "sink-da-tv") == ""

    def test_vindo_de_sons_do_jogo_ele_continua_calado(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: tire a condição e reenvie o byte sempre.

        A `fonte` é do NÓ; a rota é do FIRMWARE. Mandar um byte que já está no
        aparelho escreveria nele uma escolha que ela não fez — e é o contrato
        do `test_o_junto_nao_manda_byte_de_rota_ao_daemon` da régua irmã.
        """
        from pacotes import a02_controles as a02

        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO])),
                       {"uniq": P1, "rota": "junto"}, p)
        assert "speaker_set" not in p.nomes, (
            f"o «Ouvir junto» mexeu no firmware sem precisar: {p.nomes}")

    def test_sem_byte_publicado_ele_tambem_fica_calado(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: compare com `!= sons do jogo` em vez de `== todo o som`.

        O daemon só publica `speaker` depois da primeira escrita: sem bloco, o
        byte é `None`, e *"não sei"* não é *"está em todo o som do PC"*. Um
        reenvio aqui tomaria a posse do alto-falante num controle que ninguém
        mediu.
        """
        p = Ponte()
        _gesto("rota")(_ctx(_dele(P1, rota=None)), {"uniq": P1, "rota": "junto"}, p)
        assert "speaker_set" not in p.nomes, (
            f"reenviou a rota sobre um byte que o daemon nunca publicou: {p.nomes}")

    def test_o_perfil_lembra_as_duas_metades_e_so_do_dono(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: grave só a `fonte`, como antes.

        O perfil é o REGISTRO do que ficou de pé. Guardar `mix` sem a rota nova
        faria a ativação seguinte reimpor o byte de «todo o som do PC» debaixo
        de um botão que diz «Ouvir junto».
        """
        from pacotes import a02_controles as a02

        _gesto("rota")(_ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC]),
                            _dele(P2)),
                       {"uniq": P1, "rota": "junto"}, Ponte())

        dele = (_do_controle(CHAVE_P1).get("speaker") or {})
        assert dele.get("fonte") == "mix"
        assert dele.get("rota") == a02.ROTA_DO_CANAL[a02.CANAL_SONS_DO_JOGO]
        assert not _do_controle(CHAVE_P2), "a escolha de um chegou ao vizinho"

    def test_um_daemon_que_recusa_nao_deixa_o_perfil_a_meio_caminho(
        self, casa: pathlib.Path, sem_maquina_dela: dict[str, list[Any]]
    ) -> None:
        """MORDIDA: ignore o retorno de `speaker_set` no ramo do «junto».

        O perfil descreve o que FICOU DE PÉ. Gravar `mix` com o firmware ainda
        em «todo o som do PC» poria no disco um estado que este controle nunca
        teve — e a ativação seguinte o reimporia.
        """
        from pacotes import a02_controles as a02

        with pytest.raises(RuntimeError, match="não confirmou"):
            _gesto("rota")(
                _ctx(_dele(P1, rota=a02.ROTA_DO_CANAL[a02.CANAL_TODO_O_PC])),
                {"uniq": P1, "rota": "junto"}, Ponte(recusa=True))
        assert not _do_controle(CHAVE_P1), (
            "o perfil guardou uma escolha que o daemon recusou")


# ===========================================================================
# 4. A tabela dos botões — todo gesto de som da página tem dono, e é do dono
# ===========================================================================


class TestATabelaDosBotoes:
    #: O que a página tem na coluna de som, e o que cada um chama. A régua LÊ o
    #: primeiro da página e confere o segundo contra o registro — digitar os
    #: dois lados seria a régua medindo a própria aritmética.
    DA_COLUNA_DO_SOM = ("mudo", "volume", "rota", "mic-modo")

    def test_todo_gesto_de_som_da_pagina_tem_dono(self) -> None:
        """MORDIDA: apague um `@gesto` da coluna de som.

        Botão sem chamador é a `A-CASA-SABE-E-O-PRODUTO-NAO-FAZ` em miniatura:
        o piloto o registra como *"sem dono"*, devolve o botão ao normal, e
        quem clicou conclui que funcionou.
        """
        import pacotes
        import pacotes.a02_controles

        doc = _pagina_publicada()
        for nome in self.DA_COLUNA_DO_SOM:
            assert f'data-gesto="{nome}"' in doc, (
                f"a régua fala de um gesto que a página não tem: {nome}")
            assert pacotes.gesto_da_pagina("02-controles.html", nome) is not None, (
                f"a página tem `data-gesto={nome}` e ninguém o atende")

    @pytest.mark.parametrize(
        ("o", "metodo"),  # noqa-acento: nome de parametro
        [
            ({"mudo": "microfone"}, "mic_canal_set_detalhado"),
            ({"mudo": "alto-falante"}, "speaker_set"),
            ({"volume": "microfone", "valor": "42"}, "mic_volume_set_detalhado"),
            ({"volume": "alto-falante", "valor": "42"}, "speaker_set"),
            ({"rota": "jogo"}, "speaker_set"),
            ({"rota": "pc"}, "speaker_set"),
        ],
    )
    def test_cada_botao_do_som_so_mexe_no_controle_da_coluna(
        self, o: dict[str, Any], metodo: str, casa: pathlib.Path,
        sem_maquina_dela: dict[str, list[Any]],
    ) -> None:
        """Pergunta 3 da sprint, botão a botão: **vale só para aquele controle?**

        MORDIDA: tire o `uniq=` de qualquer uma das chamadas. O daemon cai na
        rota global, atende pelo PRIMEIRO controle da mesa e responde `ok` — a
        tela pinta o selo do cartão certo sobre um número que aquele controle
        nunca teve. É a decisão [08] de 04/09, e o defeito que ela já custou.
        """
        nome = next(k for k in ("mudo", "volume", "rota") if k in o)
        p = Ponte()
        _gesto(nome)(_ctx(_dele(P1), _dele(P2)), {"uniq": P1, **o}, p)

        pedidos = p.so(metodo)
        assert pedidos, f"{o} não chamou {metodo}: {p.nomes}"
        assert all(q.get("uniq") == P1 for q in pedidos), (
            f"{o} mexeu em outro controle: {pedidos}")
        assert not _do_controle(CHAVE_P2), "o perfil do vizinho foi tocado"
