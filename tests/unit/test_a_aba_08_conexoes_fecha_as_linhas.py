#!/usr/bin/env python3
"""As decisões do PO sobre a aba `08-conexoes`, medidas na SAÍDA do produto."""

from __future__ import annotations

import dataclasses
import re

import pytest


@pytest.fixture()
def pacote():
    """O pacote da aba, importado uma vez por teste."""
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    return a08_conexoes


@pytest.fixture()
def cena():
    """Uma cena de exame com as DUAS formas que a coluna da direita desenha."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import Item
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        DERIVADO_DA_CONTA,
        MEDIDO_AQUI,
        Linha,
        Ordem,
    )

    def ordem(chave: str) -> Ordem:
        return Ordem(
            chave=chave,
            acao=f"Mova o adaptador de {chave}",
            o_que_eu_vi=Linha(texto="dois rádios na mesma raiz", selo=MEDIDO_AQUI),
            por_que_importa=Linha(texto="USB 3.0 faz ruído em 2,4 GHz",
                                  selo=DERIVADO_DA_CONTA),
            ganho_esperado=Linha(texto="menos engasgo no rádio",
                                 selo=DERIVADO_DA_CONTA),
            arranjo="3-1|3-2",
        )

    from hefesto_dualsense4unix.integrations.exame_da_mesa import (
        ESTADO_ATENCAO,
        ESTADO_CERTO,
        ESTADO_NAO_SEI,
    )

    return [
        Item(chave="uma", rotulo="A", estado=ESTADO_ATENCAO, porque="vi isto",
             cura="mova o cabo", ordem=ordem("uma")),
        Item(chave="outra", rotulo="B", estado=ESTADO_ATENCAO, porque="vi aquilo",
             cura="tire o hub", ordem=ordem("outra")),
        Item(chave="conf-1", rotulo="C", estado=ESTADO_ATENCAO,
             porque="a economia de energia está ligada",
             cura="desligue a economia de energia"),
        Item(chave="conf-2", rotulo="D", estado=ESTADO_CERTO,
             porque="as entradas dão 500 mA", cura="não precisa fazer nada"),
        Item(chave="conf-3", rotulo="E", estado=ESTADO_NAO_SEI,
             porque="não consegui olhar", cura=None),
    ]


def _coluna(pacote, cena) -> str:
    """A coluna da direita como o produto a emite, com a cena na mão."""
    pacote._ORDENS_NA_TELA = tuple(i.ordem for i in cena)
    return pacote._html_das_dicas(cena, None)


def _com_destino(cena, destino: str):  # type: ignore[no-untyped-def]
    """A mesma cena, com toda ordem apontando para `destino`."""
    return [dataclasses.replace(i, ordem=dataclasses.replace(i.ordem, destino=destino))
            if i.ordem is not None else i for i in cena]


def test_a_coluna_nao_traz_procedencia_nem_ganho(pacote, cena) -> None:
    """A cena tem cura, ganho e frase derivada — a cura vai ao ⓘ, o resto não sai na coluna."""
    from hefesto_dualsense4unix.integrations.exame_da_mesa import ESTADO_CERTO
    from hefesto_dualsense4unix.integrations.ordens_da_mesa import (
        MEDIDO_AQUI,
        TEXTO_DO_SELO,
    )

    curas = [i.cura for i in cena
             if i.ordem is None and i.cura and i.estado != ESTADO_CERTO]
    ordens = [i.ordem for i in cena if i.ordem is not None]
    derivados = {linha.selo for o in ordens for linha in o.linhas} - {MEDIDO_AQUI}
    assert curas and ordens and derivados, (
        "a cena precisa ter cura, ordem e frase derivada, senão não mede nada")
    for destino in ("", "Entrada 9"):
        coluna = _coluna(pacote, _com_destino(cena, destino))
        assert 'class="ordem cura"' not in coluna and 'class="proc"' not in coluna
        assert all(c in coluna for c in curas), coluna
        proibidas = [*(TEXTO_DO_SELO[s] for s in derivados),
                     *(o.ganho_esperado.texto for o in ordens)]
        for frase in proibidas:
            assert frase not in coluna, (
                f"{frase!r} voltou à coluna da direita (destino {destino!r})")


def test_toda_ordem_aberta_tem_a_sua_linha(pacote, cena) -> None:
    """Decisão [07] — a segunda ordem de 03/09 deixa de sumir."""
    abertas = [i.ordem.acao for i in cena if i.ordem is not None]
    for destino in ("", "Entrada 9"):
        coluna = _coluna(pacote, _com_destino(cena, destino))
        assert all(acao in coluna for acao in abertas), coluna
        assert 'class="mais"' not in coluna


def test_o_mais_n_cala_quando_tudo_cabe(pacote, cena) -> None:
    """*"Só custa linha no dia em que sobra."* — com três cartões ou menos não há «mais N»."""
    tres = [i for i in cena if i.estado != "certo"][:3]
    assert "mais-dicas" not in _coluna(pacote, tres)


def test_os_quatro_que_mais_pesam_aparecem_e_o_resto_espera_sem_mais_n(pacote, cena) -> None:
    """Os quatro que mais pesam aparecem; o próximo entra quando ela ignora ou resolve um
    (desenho aprovado de 05/10/2026: sem «mais N»)."""
    nao_certos = [i for i in cena if i.estado != "certo"]
    assert len(nao_certos) == 4, "a cena precisa de quatro achados para medir a fileira"
    mais = [dataclasses.replace(i, chave=f"{i.chave}-2") for i in nao_certos]
    coluna = _coluna(pacote, [*nao_certos, *mais])
    assert coluna.count('<section class="cartao-dica') == 4
    assert "mais-dicas" not in coluna and "mais 4" not in coluna


def test_a_coluna_sem_a_lista_continua_sendo_so_o_card(pacote) -> None:
    """`_html_das_dicas()` sem cena é o que ela era: só as ordens que o tique pintou."""
    pacote._ORDENS_NA_TELA = ()
    assert "cd-cura" not in pacote._html_das_dicas()


def test_o_rodape_do_mapa_nao_manda_apertar_o_aplicar() -> None:
    """Decisão [08] — *"Trocar pela verdade."*"""
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert "mm-aplicar" in html, (
        "a linha do rodapé do Mapa sumiu — o teste não mede mais nada")
    assert "clicar em Aplicar" not in html


def test_o_rodape_do_mapa_diz_que_o_clique_ja_gravou() -> None:
    """E a frase nova é a do DONO desta aba, lida no ato."""
    from hefesto_dualsense4unix.interface.logica_do_mapa import GRAVA_NO_CLIQUE
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert GRAVA_NO_CLIQUE in html


def test_o_rodape_do_mapa_vem_do_dono() -> None:
    """A frase do rodapé tem UM dono, e o gerador não guarda uma segunda cópia."""
    import pathlib

    from hefesto_dualsense4unix.interface.logica_do_mapa import GRAVA_NO_CLIQUE
    from hefesto_dualsense4unix.interface import aba08, onde

    for publicado in (False, True):
        pagina = onde.pagina("08-conexoes.html", publicado=publicado)
        html = pagina.read_text(encoding="utf-8")
        no = re.findall(r'<div class="tn-frase mm-aplicar">(.*?)</div>', html)
        assert len(no) == 1, (
            f"{pagina.name} ({'publicada' if publicado else 'bancada'}) tem "
            f"{len(no)} rodapé(s) `.mm-aplicar` — seletor que casa zero é ERRO, "
            f"não silêncio")
        assert no[0] == GRAVA_NO_CLIQUE, (
            f"o rodapé da página {'publicada' if publicado else 'da bancada'} "
            f"não é o do dono:\n  página: {no[0]!r}\n  dono:   {GRAVA_NO_CLIQUE!r}")

    fonte = pathlib.Path(aba08.__file__).read_text(encoding="utf-8")
    assert GRAVA_NO_CLIQUE not in fonte, (
        "`aba08.py` voltou a DIGITAR a frase do rodapé — ela tem dono, e o "
        "gerador a lê por `MAPA[\"GRAVA_NO_CLIQUE\"]`")
    assert aba08.MAPA["GRAVA_NO_CLIQUE"] == GRAVA_NO_CLIQUE, (
        "o `MAPA` do gerador deixou de carregar a frase — sem ela no conjunto "
        "do `_constantes`, renomear no produto some da tela em silêncio")


def test_o_exame_nao_manda_procurar_um_botao_que_nao_existe() -> None:
    """*"Ver as ordens ignoradas"* saiu da tela em 31/08 e a frase ficou."""
    from hefesto_dualsense4unix.interface import aba08, onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    dicas = re.findall(r'title="([^"]*)"', html)
    dicas += re.findall(r'data-campo="achado-explica"[^>]*>(.*?)</span>', html)
    assert dicas, "a régua não achou dica nenhuma — seletor cego é ERRO, não silêncio"
    citam = [d for d in dicas if aba08.VER_IGNORADAS in d]
    assert not citam, f"{len(citam)} dica(s) ainda mandam procurar um botão que não existe"
    assert aba08.VER_IGNORADAS in html, (
        "a retrospectiva perdeu o nome do botão — a régua deixa de separar as "
        "duas metades e passaria por acidente")


def test_a_frase_nova_diz_o_que_o_produto_faz() -> None:
    """E o que entrou no lugar é o que `ordens_da_mesa.ordens_novas` faz."""
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert html.count(a08_conexoes.VOLTA_QUANDO) >= 2
    assert "A linha fica apagada aqui" not in html


def test_o_campo_do_nome_do_adaptador_tem_gesto(pacote) -> None:
    """Ela digita e o produto tem onde ouvir — o defeito da §3 desta aba.

    DESDE 23/09/2026 o campo é o `input.lugar-nome` do cartão de cada adaptador
    (TRANSPLANTE-DA-SECAO-01), e o gesto grava pelo dono do nome do adaptador
    (`grava="dar_nome_ao_adaptador"`, pelo endereço desde 26/09/2026). A RÉGUA
    LÊ O CARTÃO QUE O PRODUTO EMITE, não o gerador.
    """
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    assert ("08-conexoes.html", pacote.GESTO_DO_APELIDO) in GESTOS
    cartao = pacote.html_do_lugar(
        {"id": "E8473A000009", "lugar": "pci-0000:00:14.0-usb-0:1.2", "nome": "",
         "entrada": "Entrada 1.2"}, {"lugares": [], "aparelhos": []})
    campo = re.search(r'<input class="lugar-nome[^"]*"[^>]*>', cartao)
    assert campo, cartao[:300]
    assert f'data-gesto="{pacote.GESTO_DO_APELIDO}"' in campo.group(0)
    assert 'data-alvo="E8473A000009"' in campo.group(0)


def test_renomear_recusa_dizendo_sem_o_alvo(pacote) -> None:
    """*"Recusar dizendo é obrigatório."* — e o dublê tem de saber recusar."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    gesto = GESTOS[("08-conexoes.html", pacote.GESTO_DO_APELIDO)]
    with pytest.raises(ValueError):
        gesto(None, {"texto": "Sala"}, None)


def test_renomear_nao_escreve_quando_o_nome_nao_mudou(pacote, monkeypatch) -> None:
    """O mesmo nome não é gravado de novo — a regra é a da janela estável."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    chamou: list[tuple[str, str]] = []

    class _Feito:
        gravou = True

    def _escreveu(endereco: str, nome: str) -> _Feito:
        chamou.append((endereco, nome))
        return _Feito()

    monkeypatch.setattr(pacote, "_CENA_NA_TELA", {"lugares": [
        {"id": "E8473A000009", "lugar": "pci-0000:00:14.0-usb-0:1.2", "nome": "Sala"}]})
    monkeypatch.setattr(pacote, "_gravar_o_nome", _escreveu)
    gesto = GESTOS[("08-conexoes.html", pacote.GESTO_DO_APELIDO)]
    assert gesto(None, {"alvo": "E8473A000009", "valor": "Outro", "evento": "click"},
                 None) == {"armou": True}
    gesto(None, {"alvo": "E8473A000009", "valor": "Sala", "evento": "change"}, None)
    assert chamou == []
    gesto(None, {"alvo": "E8473A000009", "valor": "Sala do fundo", "evento": "change"}, None)
    assert chamou == [("E8473A000009", "Sala do fundo")]


def test_o_escritor_do_nome_chama_o_dono_com_a_assinatura_dele(
    pacote, monkeypatch
) -> None:
    """A ASSINATURA, e não só o nome — a cicatriz de 04/09/2026.

    *"Duas vezes em 04/09 um gesto passou VERDE sem gravar um byte: uma porque o
    dicionário ia como `timeout` posicional, outra porque `_run_blocking` não
    aceita keywords."* Aqui a régua fixa o contrato do escritor ÚNICO de
    23/09/2026, pelo endereço desde 26/09/2026:
    `entrada_a_entrada.dar_nome_ao_adaptador(endereco, nome)`, os dois posicionais.
    """
    from hefesto_dualsense4unix.integrations import entrada_a_entrada

    visto: dict[str, object] = {}

    def _falso(endereco, nome, **kw):
        visto.update(endereco=endereco, nome=nome, **kw)
        return entrada_a_entrada.NomeDado(endereco, nome, True, "")

    monkeypatch.setattr(entrada_a_entrada, "dar_nome_ao_adaptador", _falso)
    monkeypatch.setattr(pacote, "_reler_a_declaracao", lambda: None)
    feito = pacote._gravar_o_nome("E8:47:3A:00:00:09", "Sala do fundo")
    assert feito.gravou
    assert visto == {"endereco": "E8:47:3A:00:00:09", "nome": "Sala do fundo"}


@pytest.fixture()
def mesa(pacote):
    """Põe uma cena na tira e devolve a máquina ao que era. Sempre."""
    antes = (pacote._conferencias, pacote._EXTRAS, dict(pacote._DISPENSADAS),
             pacote._ORDENS_NA_TELA)

    def por(itens, dispensadas=None):
        pacote._conferencias = lambda: []
        pacote._EXTRAS = tuple(itens)
        pacote._DISPENSADAS = dict(dispensadas or {})
        pacote._ORDENS_NA_TELA = tuple(getattr(i, "ordem", None) for i in itens)

    yield por
    (pacote._conferencias, pacote._EXTRAS,
     pacote._DISPENSADAS, pacote._ORDENS_NA_TELA) = antes


def _dispensa_a_primeira(cena) -> dict[str, str]:
    """`{chave: arranjo}` da primeira ordem da cena — LIDO dela, não digitado."""
    ordem = next(i.ordem for i in cena if i.ordem is not None)
    return {ordem.chave: ordem.arranjo}


def test_a_ordem_calada_continua_na_tira(pacote, cena, mesa) -> None:
    """08-Q5 — a linha que ela calou **não sai da lista**."""
    mesa(cena, _dispensa_a_primeira(cena))
    tira = pacote._itens_da_tela()
    assert len(tira) == len(cena), (
        f"a tira perdeu itens: {[i.chave for i in tira]} — a ordem calada "
        "sumiu, que é a porta de mão única que a 08-Q5 fecha")
    caladas = [i.chave for i in tira if pacote._calada(i)]
    assert caladas == [next(i.chave for i in cena if i.ordem is not None)], (
        f"a marca da linha calada não caiu na linha certa: {caladas}")


def test_a_ordem_calada_com_arranjo_vazio_nao_cala(pacote, cena, mesa) -> None:
    """A borda do arranjo vazio, e ela é o preço do desfazer.

    O desfazer grava `arranjo=""` na mesma chave, e `Ordem.arranjo` tem `""` por
    PADRÃO. Sem o `and arranjo` da guarda, uma ordem viva sem assinatura casaria
    com o vazio guardado e nasceria calada — a tela apagando um achado que
    ninguém dispensou.

    MORDE: tire o `bool(arranjo) and` de `_ordem_calada` e este teste vê a linha
    nascer cinza.
    """
    import dataclasses

    item = next(i for i in cena if i.ordem is not None)
    sem_assinatura = dataclasses.replace(item.ordem, arranjo="")
    mesa([dataclasses.replace(item, ordem=sem_assinatura)],
         {sem_assinatura.chave: ""})
    tira = pacote._itens_da_tela()
    assert len(tira) == 1
    assert not pacote._calada(tira[0]), (
        "uma ordem VIVA sem assinatura de arranjo nasceu calada — o vazio "
        "guardado pelo desfazer casou com o vazio do padrão")


def test_a_aba_jogar_nao_recebe_a_ordem_calada(pacote, cena, mesa) -> None:
    """Passo 2 — `_exame()` é CONTRATO, e o consumidor é outra aba."""
    from hefesto_dualsense4unix.interface.pacotes import a01_jogar

    dispensada = _dispensa_a_primeira(cena)
    mesa(cena, dispensada)
    calada = next(iter(dispensada))
    assert calada in [i.chave for i in pacote._itens_da_tela()], (
        "a cena não tem a linha calada na tira — o teste não mede nada")
    assert calada not in [i["chave"] for i in a01_jogar._do_exame()], (
        "a aba Jogar recebeu a ordem que ela calou na Conexões")


def test_a_linha_que_voltou_apaga_a_tinta(pacote, cena, mesa) -> None:
    """Passo 3 — a chave `calada` vai em TODO tique, inclusive vazia."""
    dispensada = _dispensa_a_primeira(cena)
    mesa(cena, dispensada)
    antes = [pacote._linha(i)["calada"] for i in pacote._itens_da_tela()]
    assert antes.count("sim") == 1, f"a cena não calou uma linha só: {antes}"

    pacote._DISPENSADAS[next(iter(dispensada))] = ""
    depois = [pacote._linha(i)["calada"] for i in pacote._itens_da_tela()]
    assert len(depois) == len(antes), "a tira mudou de tamanho no desfazer"
    assert depois.count("sim") == 0, (
        f"a linha continuou marcada como calada depois do desfazer: {depois}")
    assert all(v == "" for v in depois), (
        "a chave sumiu em vez de vir VAZIA — o piloto não visitaria o elemento "
        f"e a tinta do tique anterior ficaria: {depois}")


def test_o_desenho_esmaece_a_dica_calada_e_o_botao_de_voltar_responde(pacote, cena, mesa) -> None:
    """A ordem calada FICA no fim, apagada, e o caminho de volta não esmaece.

    A folha tem de saber desenhar `.calada`, senão o cartão calado fica idêntico ao que fala; e o
    botão do cartão calado é o MESMO gesto `ignorar` (que desfaz), com a dica do dono.

    MORDE: tire a regra `.cartao-dica.calada` da folha e a primeira asserção reprova; tire o
    `calada=` do `dica_da_ordem` e a segunda reprova.
    """
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    assert re.search(r"\.cartao-dica\.calada[^{]*\{[^}]*opacity", html), (
        "a folha não ESMAECE a dica calada — ela ficaria igual à que fala")
    assert not re.search(r"\.cartao-dica\.calada[^{]*\{[^}]*display:none", html), (
        "a dica calada SOME em vez de esmaecer — a decisão dela diz que ela "
        "*continua no lugar dela*, e uma dica que some é a tela que esconde")
    mesa(cena, _dispensa_a_primeira(cena))
    coluna = _coluna(pacote, cena)
    calada = re.search(r'<section class="cartao-dica [^"]*calada.*?</section>', coluna, re.S)
    assert calada, "a ordem calada saiu da tela em vez de ficar apagada"
    assert 'data-gesto="ignorar"' in calada.group(0) and ">Mostrar</button>" in calada.group(0)
    assert f'title="{pacote.DICA_DO_DESFAZER}"' in calada.group(0)


def test_a_dica_do_ignorar_vem_do_produto() -> None:
    """O ignorar muda de sentido (cala/desfaz), e a dica do botão vem do dono do verbo."""
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as p

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    botoes = re.findall(r'<button class="btn cd-ignora"[^>]*>', html)
    assert botoes, "a régua não achou o «Ignorar» de nenhum cartão — seletor cego é ERRO"
    for b in botoes:
        assert 'data-gesto="ignorar"' in b, b
        assert f'title="{p.DICA_DO_IGNORAR}"' in b, (
            f"o `title` de partida não é o do dono: {b}")
    assert "sai desta lista" not in html, (
        "a frase que a 08-Q5 tornou falsa sobreviveu em algum lugar da tela — "
        "fato errado se SUBSTITUI, e sai de TODOS os lugares")


def test_o_mesmo_gesto_desfaz(pacote, cena, mesa) -> None:
    """Passo 5 — o ⊘ é um INTERRUPTOR, e o segundo clique traz de volta."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mesa(cena, {})
    gravado: list[dict] = []

    class _Ponte:
        """O que `ipc_bridge.machine_declare` devolve: `(ok, motivo)`.

        NÃO um `{"ok": True}`: `_resposta` faz `bool(r)` num objeto que não é
        tupla, e **todo dicionário não vazio é verdadeiro** — um dublê assim
        aprova a recusa junto com o sucesso. É o dublê mais frouxo que o real,
        que derrubou três réguas em 05/09.
        """

        def machine_declare(self, carga):
            gravado.append(carga["mesa"]["ordens_dispensadas"])
            return (True, "")

    gesto = GESTOS[("08-conexoes.html", "ignorar")]
    posicao = next(i for i, item in enumerate(cena) if item.ordem is not None)
    ordem = cena[posicao].ordem

    antes_reler = pacote._reler_a_declaracao
    pacote._reler_a_declaracao = lambda: None
    try:
        gesto(None, {"v": str(posicao)}, _Ponte())
        assert pacote._calada(cena[posicao]), "o primeiro clique não calou"
        assert gravado[-1][ordem.chave]["arranjo"] == ordem.arranjo
        assert gravado[-1][ordem.chave]["quando"], (
            "a dispensa foi gravada sem data — `quando` é o que diz quando ela "
            "decidiu")

        gesto(None, {"v": str(posicao)}, _Ponte())
        assert not pacote._calada(cena[posicao]), (
            "o segundo clique não desfez — o ⊘ continua sendo porta de mão única")
        assert gravado[-1][ordem.chave] == {"quando": "", "arranjo": ""}, (
            f"o desfazer não escreveu os dois vazios: {gravado[-1]}")
    finally:
        pacote._reler_a_declaracao = antes_reler


def test_o_desfazer_passa_no_esquema_do_disco() -> None:
    """E os dois vazios têm de sobreviver ao pydantic, senão o desfazer é teoria."""
    from hefesto_dualsense4unix.utils.maquina import MesaDeclarada

    mesa = MesaDeclarada.model_validate(
        {"ordens_dispensadas": {"dongle_atras_de_hub": {"quando": "", "arranjo": ""}}})
    assert mesa.ordens_dispensadas["dongle_atras_de_hub"].arranjo == ""


def test_a_recusa_do_disco_nao_cala_a_linha(pacote, cena, mesa) -> None:
    """Passo 5 — a ordem disco→memória não se inverte."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mesa(cena, {})

    class _PonteQueRecusa:
        def machine_declare(self, carga):
            return (False, "não consegui gravar agora")

    gesto = GESTOS[("08-conexoes.html", "ignorar")]
    posicao = next(i for i, item in enumerate(cena) if item.ordem is not None)
    with pytest.raises(RuntimeError):
        gesto(None, {"v": str(posicao)}, _PonteQueRecusa())
    assert not pacote._calada(cena[posicao]), (
        "a linha calou com o disco tendo RECUSADO — a tela num estado que o "
        "disco não tem, e a linha volta sozinha no tique seguinte")


def test_o_ignorar_numa_conferencia_continua_recusando_dizendo(pacote, cena, mesa) -> None:
    """Nada se perdeu: uma conferência não tem arranjo, e o ⊘ nela recusa."""
    from hefesto_dualsense4unix.interface.pacotes import GESTOS

    mesa(cena, {})
    posicao = next(i for i, item in enumerate(cena) if item.ordem is None)
    with pytest.raises(RuntimeError):
        GESTOS[("08-conexoes.html", "ignorar")](None, {"v": str(posicao)}, None)


def test_o_veredito_continua_cego_para_a_calada(pacote, cena, mesa) -> None:
    """Nada se perdeu: a linha cinza não pinta o topo."""
    mesa(cena, {})
    falando = pacote._veredito_do_exame(pacote._itens_da_tela())
    mesa(cena, _dispensa_a_primeira(cena))
    calada = pacote._veredito_do_exame(pacote._itens_da_tela())
    assert falando and calada, "o veredito veio vazio — o teste não mede nada"
    assert falando != calada, (
        "calar uma ordem não mudou o veredito do topo — o ⊘ deixou de fazer "
        "alguma coisa visível, que é a definição de botão morto")


def _ctx_de_alvo(pacote, indice, quantos=2):
    """Um `Contexto` com `quantos` controles e o alvo de saída em `indice`.

    A MESA É MONTADA PELO PRODUTO (`mesa_viva.mesa_do_estado`), e não à mão: é
    ele que decide qual `uniq` vira `p1` — e a conversão que este teste mede é
    exatamente a que atravessa as duas ordens. Uma mesa digitada aqui casaria
    com o que o teste espera e nunca com o que o produto faz.
    """
    from hefesto_dualsense4unix.interface import mesa_viva
    from hefesto_dualsense4unix.interface.pacotes import Contexto

    # O `player_slot` DESCE com a posição e o `index` SOBE: é o cruzamento que
    # errada. **O CAMPO É `player_slot`, e não `player`** — quem decide a
    controles = [
        {"uniq": f"aa:bb:cc:00:00:{n:02x}", "connected": True, "index": n,
         "transport": "usb", "player_slot": quantos - n}
        for n in range(quantos)
    ]
    estado = {"controllers": controles, "output_target_index": indice}
    mesa = mesa_viva.mesa_do_estado(estado, {})
    return Contexto(state=estado, mesa=mesa, conectados=controles), mesa


def test_o_alvo_de_saida_e_lido_de_volta_do_daemon(pacote) -> None:
    """Ela clica "só este" no P2 e a tela passa a apontar para ele.

    O DEFEITO QUE ISTO FECHA: o gesto `alvo` escrevia `controller.target.set`, o
    daemon obedecia, e no tique seguinte o acordeão continuava aberto no P1 — o
    `checked` do desenho. A fita do topo junto, porque o destaque dela vem das
    regras `body:has(#gc-pN:checked)` do gerador.

    MORDE: devolva a leitura ao índice CRU (`lugares[indice + 1]`, sem passar
    pelo `uniq`) e este teste reprova — o daemon numera por posição em
    `controllers` e o desenho por posição na mesa ORDENADA POR IDENTIDADE, e
    aqui as duas estão trocadas de propósito.
    """
    ctx, mesa = _ctx_de_alvo(pacote, indice=0)
    esperado = next(m["pref"] for m in mesa
                    if m["uniq"] == ctx.state["controllers"][0]["uniq"])
    assert pacote._pref_do_alvo(ctx) == esperado, (
        f"o alvo `index: 0` virou {pacote._pref_do_alvo(ctx)!r} e o produto põe "
        f"aquele controle em {esperado!r} — as duas ordens foram confundidas")
    marcado = pacote._alvo_de_saida(ctx)
    lugares = [pacote.TODOS_NA_TELA, *sorted(pacote.TODOS_OS_LUGARES)]
    assert len(marcado) == len(lugares), marcado
    acesos = [onde for onde, v in zip(lugares, marcado, strict=True) if v == "sim"]
    assert acesos == [esperado], marcado


def test_o_alvo_todos_marca_o_primeiro_radio(pacote) -> None:
    """`index: null` é o broadcast, e ele marca o "todos" — nunca um controle."""
    ctx, _ = _ctx_de_alvo(pacote, indice=None)
    marcado = pacote._alvo_de_saida(ctx)
    assert marcado[0] == "sim", marcado
    assert not any(marcado[1:]), marcado


def test_um_alvo_que_o_estado_nao_traduz_nao_marca_nada(pacote) -> None:
    """Índice fora da lista desmarca os cinco — e isso NÃO é o "todos"."""
    ctx, _ = _ctx_de_alvo(pacote, indice=97)
    assert pacote._pref_do_alvo(ctx) == ""
    assert not any(pacote._alvo_de_saida(ctx)), pacote._alvo_de_saida(ctx)


def test_a_lista_do_alvo_vai_em_todo_tique_inclusive_vazia(pacote) -> None:
    """Sem a chave `output_target_index` a lista sai VAZIA — e sai.

    É a regra do botão cinza da ONDA0-F: uma chave que só aparece quando há o
    que dizer deixa na tela a marca do tique anterior, e um acordeão preso no
    controle de antes é a tela mentindo sobre para onde a saída vai.

    A RÉGUA PASSA PELO `pacote()`, E NÃO PELO HELPER — 06/09/2026, e a primeira
    versão dela não provava nada: perguntar direto a `_alvo_de_saida` deixa a
    emissão de fora, que é justamente onde a chave pode sumir. A mordida que
    embrulhou a linha do `pacote()` num condicional passou VERDE por isso.

    MORDE: emita `alvo-aberto` só quando houver alvo e o `KeyError` aqui é a
    reprovação.
    """
    ctx, _ = _ctx_de_alvo(pacote, indice=0)
    ctx.state.pop("output_target_index")
    assert pacote._alvo_de_saida(ctx) == ["", "", "", "", ""]
    carga = pacote.pacote(ctx)
    assert "alvo-aberto" in carga, (
        "o pacote deixou de emitir `alvo-aberto` quando não há alvo — a tela "
        "fica com a marca do tique anterior, apontando o controle de antes")
    assert not any(carga["alvo-aberto"]), carga["alvo-aberto"]


def test_o_desenho_tem_um_endereco_por_radio_do_acordeao() -> None:
    """Os cinco `<input>` do acordeão têm o endereço, e só um nasce `checked`."""
    from hefesto_dualsense4unix.interface import onde
    from hefesto_dualsense4unix.interface.pacotes import TODOS_OS_LUGARES

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    quantos = html.count('data-campo="alvo-aberto" data-hef-alvo="marcado"')
    assert quantos == len(TODOS_OS_LUGARES) + 1, (
        f"são {quantos} rádios com endereço e a mesa tem "
        f"{len(TODOS_OS_LUGARES)} lugares mais o 'todos'")
    assert html.count('data-hef-alvo="marcado" checked') <= 1, (
        "o desenho afirma dois alvos de saída ao mesmo tempo")


def test_o_aviso_do_controle_nao_adotado_vem_do_dono(pacote) -> None:
    """A frase é `status_actions.texto_de_controle_nao_adotado`, palavra por palavra.

    MORDE: escreva a frase aqui no pacote e ela deixa de acompanhar o dono —
    que é quem sabe de quantos em quantos minutos o produto tenta sozinho
    (`MINUTOS_ENTRE_TENTATIVAS`, lido da unit do systemd).
    """
    from hefesto_dualsense4unix.app.actions.status_actions import (
        texto_de_controle_nao_adotado,
    )

    st = {"controles_sem_driver": {"quantidade": 2, "ids": ["x", "y"]}}
    assert pacote._frase_do_sem_driver(st) == texto_de_controle_nao_adotado(st)
    assert pacote._frase_do_sem_driver(st).strip(), "o dono não disse nada"


def test_sem_controle_orfao_a_linha_do_aviso_some(pacote) -> None:
    """Zero órfão vira `monta.NADA_A_DIZER`, e a folha esconde a linha."""
    nada = str(pacote._monta().NADA_A_DIZER)
    assert pacote._frase_do_sem_driver({}) == nada
    assert pacote._frase_do_sem_driver(
        {"controles_sem_driver": {"quantidade": 0, "ids": []}}) == nada


def test_o_aviso_do_radio_fragil_nomeia_os_controles(pacote) -> None:
    """O aviso do Bluetooth nativo frágil sai do dono, COM os números.

    A REGRA DOS DOIS DONOS É DELES: `controles_bt_frageis` lê a lista publicada
    e `texto_native_bt_fragil` a vira frase — e lista vazia com o booleano ACESO
    quer dizer *"não sei quais"*, não *"nenhum"*. O aviso acende sem nomes.

    MORDE: acenda a linha pelo tamanho da lista (`if not numeros: return nada`)
    e o segundo caso reprova — o aviso cala com o daemon dizendo que há frágil.
    """
    from hefesto_dualsense4unix.app.actions.home_actions import (
        NATIVE_BT_FRAGIL_TEXT,
        texto_native_bt_fragil,
    )

    st = {"native_bt_fragil": True, "native_bt_fragil_controles": [2, 3]}
    assert pacote._frase_do_radio_fragil(st) == texto_native_bt_fragil([2, 3])
    assert "2" in pacote._frase_do_radio_fragil(st)
    sem_nomes = {"native_bt_fragil": True, "native_bt_fragil_controles": []}
    assert pacote._frase_do_radio_fragil(sem_nomes) == NATIVE_BT_FRAGIL_TEXT


def test_sem_radio_fragil_a_linha_some(pacote) -> None:
    """Booleano apagado é silêncio — e o silêncio não ocupa pixel."""
    nada = str(pacote._monta().NADA_A_DIZER)
    assert pacote._frase_do_radio_fragil({}) == nada
    assert pacote._frase_do_radio_fragil({"native_bt_fragil": False}) == nada


def test_as_ressalvas_tem_endereco_na_pagina() -> None:
    """As linhas existem no desenho, com o alvo `html`."""
    from hefesto_dualsense4unix.interface import onde

    html = onde.pagina("08-conexoes.html").read_text(encoding="utf-8")
    for campo in ("sem-driver", "radio-fragil"):
        achado = re.search(rf'<div class="ressalva" data-campo="{campo}"[^>]*>', html)
        assert achado, f"o desenho não tem onde dizer o `{campo}`"
        assert 'data-hef-alvo="html"' in achado.group(0), achado.group(0)
    for saiu in ("hub-em-comum", "gabinete-contagens"):
        assert f'data-campo="{saiu}"' not in html, (
            f"`{saiu}` voltou à página sem dono no pacote")
