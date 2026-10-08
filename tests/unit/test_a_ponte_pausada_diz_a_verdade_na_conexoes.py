"""A-PONTE-PAUSADA-DIZ-A-VERDADE-NA-CONEXOES-01: a ponte pausada diz a verdade na Conexões.

Três furos que a conferência da O-SINAL-DE-CADA-CONTROLE-DIZ-SE-ELE-ESTA-LONGE-01 achou, uma
régua para cada um:

1. a caixa da ponte do controle longe dizia «94 Hz», a constante de projeto, com a ponte
   pausada: o campo ao vivo `hz-ponte` diz a taxa que a ponte escreve de verdade (vazio quando
   ela cede);
2. o governador contava a ponte `longe` (muda, não escreve) na vez da fila, e as vizinhas
   cediam por ela: `_a_vez` exclui a vaga longe da conta e do rodízio;
3. a proposta do Equilibrar não dizia que veio do sinal: a proposta leva `pelo_sinal` e os dois
   dBm, e o cartão e o balão dizem «sinal fraco».

A BANCADA do furo 2 é o governador real com o relógio e o diário de mentira, e o adaptador
de mentira que escoa até a capacidade de cada janela (o dublê das réguas da O-GOVERNADOR-NAO-
FAZ-UMA-PONTE-SO-CEDER-01), com o sinal na mão da régua. A MORDIDA de cada régua está no
docstring dela.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tests.conftest import exigir_gi_real

exigir_gi_real("importa `interface.pacotes.a08_conexoes`, que carrega o GTK")

from hefesto_dualsense4unix.daemon.subsystems import governador_do_radio as gov
from hefesto_dualsense4unix.integrations import radio_da_mesa as rm
from hefesto_dualsense4unix.interface.pacotes import a08_conexoes as a08
from tests.unit.test_o_governador_do_radio import (
    ADAPTADOR_A,
    CONTROLE_1,
    CONTROLE_2,
    CONTROLE_3,
    _AdaptadorQueEscoaDuas,
    _Diario,
    _Relogio,
)

POR_JANELA = 93.75 * gov.PERIODO_S
JANELAS_ANTES = 100
JANELAS_DEPOIS = 300


class _Sinal:
    """O leitor do sinal na mão da régua: o que ela põe em `dbm` é o que o governador lê."""

    def __init__(self) -> None:
        self.dbm: dict[str, int] = {}
        self._n = 0

    def talvez_ler(self, _amostra: object) -> None:
        return None

    def leitura(self) -> tuple[int, dict[str, int | None]]:
        self._n += 1
        return self._n, dict(self.dbm)


class _Bancada:
    """O governador real com `controles` (uma ponte de som cada) num adaptador que escoa
    `capacidade` pacotes por janela. `passo()` fecha uma janela; `fraco(uniq)` põe o sinal dele
    abaixo do que atrasa o botão (o tique seguinte o lê).
    """

    def __init__(self, controles: tuple[str, ...], capacidade: int) -> None:
        self.relogio, registro = _Relogio(), _Diario()
        self.medidor = _AdaptadorQueEscoaDuas(capacidade=capacidade)
        self.governador = gov.GovernadorDoRadio(
            medidor=self.medidor, adaptador_de=lambda _u: ADAPTADOR_A,
            registrar=registro, relogio=self.relogio, n_max=4,
        )
        self.sinal = _Sinal()
        self.governador.leitor_do_sinal = self.sinal  # type: ignore[assignment]
        self.governador.tique()
        self.vagas: dict[str, gov.Vaga] = {}
        for uniq in controles:
            vaga = self.governador.pedir_vaga(uniq, "som")
            assert isinstance(vaga, gov.Vaga), f"{uniq} não recebeu vaga: {vaga}"
            vaga.subiu("som")
            self.vagas[uniq] = vaga
        self.cedidas = dict.fromkeys(controles, 0)
        self.quadros = dict.fromkeys(controles, 0)
        self.parada = 0
        self._sobra = 0.0
        self.contando = False

    def fraco(self, uniq: str) -> None:
        self.sinal.dbm[gov._chave(uniq)] = rm.SINAL_QUE_ATRASA_DBM - 5

    def passo(self) -> int:
        """Uma janela: quem não cede escreve a sua parte. Devolve quantas pontes escreveram."""
        self._sobra += POR_JANELA
        por_ponte, self._sobra = int(self._sobra), self._sobra - int(self._sobra)
        escreveram = 0
        for uniq, vaga in self.vagas.items():
            if self.contando and vaga.cedendo:
                self.cedidas[uniq] += 1
            if vaga.cedendo:
                continue
            for _ in range(por_ponte):
                vaga.contar_escrita()
            if self.contando:
                self.quadros[uniq] += por_ponte
            escreveram += 1
        if self.contando and not escreveram:
            self.parada += 1
        self.medidor.janela(escreveram * por_ponte)
        self.relogio.agora += gov.PERIODO_S
        self.governador.tique()
        return escreveram


def _correr(
    controles: tuple[str, ...], capacidade: int, *, longe: str | None = None
) -> _Bancada:
    """`longe` fica com o sinal fraco a partir da janela `JANELAS_ANTES`; o que se conta é só o
    que acontece nas `JANELAS_DEPOIS` seguintes (janelas cedidas e quadros de cada controle).
    """
    bancada = _Bancada(controles, capacidade)
    for janela in range(JANELAS_ANTES + JANELAS_DEPOIS):
        if janela == JANELAS_ANTES:
            bancada.contando = True
            if longe is not None:
                bancada.fraco(longe)
        bancada.passo()
    return bancada


# ---------------------------------------------------------------------------------------------
# Furo 2: a ponte longe não gasta a vez das outras
# ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("capacidade", [47, 24])
def test_a_ponte_longe_nao_gasta_a_vez_das_vizinhas(capacidade: int) -> None:
    """Três pontes, a A longe: B e C escrevem tanto quanto se a A nem existisse.

    O controle é a corrida de B e C sozinhas no mesmo adaptador (nunca um número tirado da
    saída), medida depois de `ASSENTA` janelas, quando a fila que a A deixou já escoou. A A
    está pausada pelo sinal: não escreve, e a fila não tem o que cobrar dela. MEDIDO em
    08/10/2026: a diferença da conta errada é de uma ou duas janelas (o flag some quando o
    rodízio solta a A), e não as dezenas que o dossiê da sprint contava; por isso a régua
    também pega o instante em que a A vira longe, no teste do flag logo abaixo.

    Esta régua não morde sozinha (a conta errada some em duas janelas): quem morde é a do flag,
    logo abaixo. Ela guarda o desfecho, a taxa das vizinhas, contra uma regressão maior.
    """
    com_a = _correr((CONTROLE_1, CONTROLE_2, CONTROLE_3), capacidade, longe=CONTROLE_1)
    controle = _correr((CONTROLE_2, CONTROLE_3), capacidade)

    assert com_a.vagas[CONTROLE_1].longe, "premissa: a A ficou pausada pelo sinal"
    # o tique que lê o sinal vem depois da janela em que ele ficou fraco: uma janela escapa
    assert com_a.quadros[CONTROLE_1] <= int(POR_JANELA) + 1, "premissa: a A pausada não escreve"
    de_b_e_c = com_a.quadros[CONTROLE_2] + com_a.quadros[CONTROLE_3]
    do_controle = controle.quadros[CONTROLE_2] + controle.quadros[CONTROLE_3]
    assert de_b_e_c >= do_controle - 4 * int(POR_JANELA), (
        f"B e C puseram {de_b_e_c} quadros com a A longe, e {do_controle} sem a A: a ponte "
        "muda gastou a vez das outras")


def test_o_flag_da_fila_nao_fica_na_vaga_longe() -> None:
    """A vaga que a fila mandou ceder e depois ficou longe larga o «cedendo pela fila» na hora.

    O flag existe para a fila do adaptador; numa vaga longe ele a deixaria na conta da vez
    (as vizinhas cedendo por uma ponte muda) e, quando o sinal voltasse, cedendo por uma fila
    que não é dela. Na capacidade 24 a A é escolhida pelo rodízio quase toda janela.

    MORDIDA: tirar o `vaga.cedendo = False` de `_o_sinal_protege_o_botao`, ou o `not vaga.longe`
    do `_conceder`/`_a_vez`.
    """
    bancada = _Bancada((CONTROLE_1, CONTROLE_2, CONTROLE_3), 24)
    a = bancada.vagas[CONTROLE_1]
    na_vez_do_par_b_e_c = False
    for _ in range(JANELAS_ANTES):
        bancada.passo()
        estado = next(iter(bancada.governador._estados.values()))
        # a A com o flag e o rodízio na vez do par B+C: com a A na conta, as duas cedem juntas
        na_vez_do_par_b_e_c = a._cedendo_pela_fila and estado.vez % 3 == 1
        if na_vez_do_par_b_e_c:
            break
    assert na_vez_do_par_b_e_c, "premissa: a A leva o flag e a vez cai no par B+C"
    bancada.fraco(CONTROLE_1)
    bancada.contando = True
    bancada.passo()  # o tique que lê o sinal
    assert a.longe and a._cedendo_pela_fila is False
    for _ in range(40):
        bancada.passo()
        assert a._cedendo_pela_fila is False, "a fila voltou a pôr o flag na vaga longe"
    assert bancada.parada == 0, "janelas sem nenhuma ponte escrevendo: as duas vizinhas cederam"


def test_a_ponte_que_nasce_no_episodio_com_o_controle_longe_nao_leva_o_flag() -> None:
    """A vaga concedida enquanto a fila cede e o controle está longe nasce só `longe`.

    MORDIDA: o `_conceder` voltando a pôr `vaga.cedendo = True` sem olhar a pausa.
    """
    bancada = _Bancada((CONTROLE_1, CONTROLE_2, CONTROLE_3), 24)
    for _ in range(20):
        bancada.passo()
    estado = next(iter(bancada.governador._estados.values()))
    assert estado.cedendo, "premissa: o adaptador está num episódio de ceder"
    bancada.fraco(CONTROLE_2)
    bancada.passo()
    bancada.passo()
    vaga = bancada.governador.pedir_vaga(CONTROLE_2, "vibracao")
    assert isinstance(vaga, gov.Vaga)
    assert vaga.longe and vaga._cedendo_pela_fila is False


# ---------------------------------------------------------------------------------------------
# Furo 1: a caixa da ponte diz o que a ponte escreve, não o alvo de projeto
# ---------------------------------------------------------------------------------------------


def _cena(controles: dict[str, dict[str, Any]]) -> dict[str, Any]:
    aparelhos = [{"id": ident, "tipo": "controle", "lugar": "L1", "nome": "", "rotulo": "DualSense",
                  "cor": "", "mic": False, "ponte": "som", "alem": False, "esperando": False,
                  "fixo": False, "luz": True, **campos}
                 for ident, campos in controles.items()]
    return {"lugares": [{"id": "L1", "nome": "A"}, {"id": "L2", "nome": "B"}],
            "aparelhos": aparelhos, "evitados": [], "canais_medidos": {}, "vizinhos": [],
            "wifi": [], "portas": [], "procurando": a08.PROCURAR_DESLIGADO}


def test_a_caixa_da_ponte_diz_a_taxa_que_a_ponte_escreve() -> None:
    """O campo ao vivo leva o Hz medido da ponte; a sala não carrega o «94 Hz» de projeto.

    MORDIDA: a caixa voltando a imprimir `_hz(HZ_DA_PONTE)`, ou o `title` voltando a afirmar
    «94 por segundo»: a ponte pausada diz «94 Hz» e mente.
    """
    campos = a08.campos_da_secao(_cena({"a": {"hz_ponte": 91.4, "hz_mov": 80.0},
                                        "b": {"hz_ponte": 62.0, "hz_mov": 80.0}}))
    assert campos["hz-ponte"] == ["91 Hz", "62 Hz"]
    sala = campos["radio-sala"]
    assert 'data-campo="hz-ponte" data-alvo="a"' in sala
    assert 'data-campo="hz-ponte" data-alvo="b"' in sala
    assert "94 Hz" not in sala, "a sala carrega o Hz de projeto como se fosse medido"
    assert "Som: 94 por segundo" not in sala and "Som: até 94 por segundo" in sala


@pytest.mark.parametrize("campo", ["ponte_pausada", "ponte_cedendo"])
def test_a_ponte_que_cede_deixa_a_caixa_vazia_pelo_sinal_ou_pela_fila(campo: str) -> None:
    """Pausada pelo sinal e cedendo pela fila são dois motivos, e os dois esvaziam a caixa.

    MORDIDA: `_hz_da_ponte` sem o `ponte_pausada` (o sinal) ou sem o `ponte_cedendo` (a fila).
    """
    cena = _cena({"a": {"hz_ponte": 93.0, campo: True}, "b": {"hz_ponte": 93.0}})
    assert a08.campos_da_secao(cena)["hz-ponte"] == ["", "93 Hz"]


def test_o_rodizio_da_fila_nao_faz_a_caixa_piscar(monkeypatch: pytest.MonkeyPatch) -> None:
    """A caixa piora na hora e melhora devagar: o rodízio da fila não a faz piscar.

    O rodízio troca quem cede a cada janela de 0,25 s, e a tela lê o ``state_full`` mais
    depressa que isso: sem segurar, a mesma ponte alternaria «62 Hz» e vazio. Cedeu, a caixa
    esvazia na hora; o número só volta depois de `SEGURA_O_NIVEL_S` sem ceder.

    MORDIDA: `campos_da_secao` voltando a chamar `_hz_da_ponte` com `segurar` (sem a espera).
    """
    relogio = [1000.0]
    monkeypatch.setattr(a08, "_RELOGIO_DO_NIVEL", lambda: relogio[0])
    monkeypatch.setattr(a08, "_PONTE_CEDEU_EM", {})

    def caixa(cedendo: bool) -> str:
        cena = _cena({"a": {"hz_ponte": 62.0, "ponte_cedendo": cedendo}})
        return str(a08.campos_da_secao(cena, segurar=True)["hz-ponte"][0])

    assert caixa(False) == "62 Hz", "premissa: sem ceder, a caixa diz o número"
    vistas = []
    for janela in range(12):  # o rodízio: cede uma janela em cada três
        relogio[0] += 0.25
        vistas.append(caixa(janela % 3 == 0))
    assert vistas == [""] * 12, f"a caixa piscou no rodízio: {vistas}"
    relogio[0] += rm.SEGURA_O_NIVEL_S - 1.0  # a última cedida foi meio segundo antes
    assert caixa(False) == "", "o número voltou antes da espera"
    relogio[0] += 1.0
    assert caixa(False) == "62 Hz", "o número não voltou depois da espera"


def test_sem_medida_a_caixa_fica_vazia_e_no_cabo_o_campo_nao_existe() -> None:
    cena = _cena({"a": {"hz_ponte": None}, "b": {"ponte": None, "usb": True}})
    campos = a08.campos_da_secao(cena)
    assert campos["hz-ponte"] == [""], "o cabo (sem ponte) ganhou caixa, ou «não sei» virou número"
    sala = campos["radio-sala"]
    assert sala.count('data-campo="hz-ponte"') == 1


def test_o_desenho_mostra_a_taxa_de_projeto_e_o_mockup_tem_o_campo() -> None:
    """O desenho não tem governador: a cena dele não leva `hz_ponte`, e a caixa mostra o alvo."""
    desenho = _cena({"a": {}})
    assert a08._hz_da_ponte(desenho["aparelhos"][0]) == a08._hz(rm.HZ_DA_PONTE)
    assert "hz-ponte" in a08.campos_da_secao(desenho)
    mockup = (Path(__file__).resolve().parents[2] / "mockup" / "08-conexoes.html").read_text(
        encoding="utf-8")
    assert 'data-campo="hz-ponte"' in mockup


def test_o_governador_publica_a_taxa_e_o_ceder_de_cada_ponte() -> None:
    """Duas pontes que cabem escrevem ~93,75 por segundo; a longe publica `cedendo` e cai a ~0.

    A taxa é a de `Vaga.escritas` por janela do adaptador, suavizada: o que a ponte pôs no ar,
    nunca a constante. MORDIDA: `publicar` sem o `hz`/`cedendo` (a Conexões não tem o que ler).
    """
    bancada = _Bancada((CONTROLE_2, CONTROLE_3), 47)
    for _ in range(80):
        bancada.passo()
    pontes = {p["uniq"]: p for p in bancada.governador.publicar()[ADAPTADOR_A]["pontes"]}
    for uniq in (CONTROLE_2, CONTROLE_3):
        assert pontes[uniq]["cedendo"] is False
        assert abs(pontes[uniq]["hz"] - 93.75) < 8, pontes[uniq]

    bancada = _Bancada((CONTROLE_1, CONTROLE_2, CONTROLE_3), 47)
    for _ in range(40):
        bancada.passo()
    bancada.fraco(CONTROLE_1)
    for _ in range(40):
        bancada.passo()
    pontes = {p["uniq"]: p for p in bancada.governador.publicar()[ADAPTADOR_A]["pontes"]}
    assert pontes[CONTROLE_1]["pausada_pelo_sinal"] and pontes[CONTROLE_1]["cedendo"]
    assert pontes[CONTROLE_1]["hz"] < 5, "a ponte pausada ainda publica a taxa de antes"


def test_a_tela_le_a_taxa_e_o_ceder_que_o_governador_publica() -> None:
    controle = {"uniq": "aabbcc000011", "transport": "bt", "adaptador": ADAPTADOR_A,
                "hz_movimento": 80.0, "connected": True, "ponte_do_radio": "haptica"}
    ctx = a08.Contexto(state={"controllers": [controle]}, mesa=[], conectados=[], estados={})
    governador = {ADAPTADOR_A: {"pontes": [
        {"uniq": "aa:bb:cc:00:00:11", "tipo": "som", "hz": 90.0, "cedendo": False},
        {"uniq": "aa:bb:cc:00:00:11", "tipo": "vibracao", "hz": 41.5, "cedendo": True}]}}
    (ap,) = a08._aparelhos_da_cena(ctx, ctx.state, governador, [], (), {},
                                   [a08._mac(ADAPTADOR_A)])
    assert (ap["hz_ponte"], ap["ponte_cedendo"]) == (41.5, True), "leu a ponte do outro tipo"


def test_do_governador_a_caixa_da_tela_a_ponte_longe_fica_vazia_e_a_vizinha_diz_o_hz() -> None:
    """Ponta a ponta: o governador real publica, a Conexões lê, a caixa muda de «94» para vazio."""
    bancada = _Bancada((CONTROLE_1, CONTROLE_2), 47)
    for _ in range(60):
        bancada.passo()
    publicado = {ADAPTADOR_A: bancada.governador.publicar()[ADAPTADOR_A]}

    def caixas() -> list[str]:
        controles = [{"uniq": a08._so_hex(u), "transport": "bt", "adaptador": ADAPTADOR_A,
                      "hz_movimento": 80.0, "connected": True, "ponte_do_radio": "som"}
                     for u in (CONTROLE_1, CONTROLE_2)]
        ctx = a08.Contexto(state={"controllers": controles}, mesa=[], conectados=[], estados={})
        aparelhos = a08._aparelhos_da_cena(ctx, ctx.state, publicado, [], (), {},
                                           [a08._mac(ADAPTADOR_A)])
        cena = {**_cena({}), "aparelhos": [{**a, "lugar": "L1"} for a in aparelhos]}
        return a08.campos_da_secao(cena)["hz-ponte"]

    perto = caixas()
    assert all(c.endswith(" Hz") and 80 <= int(c.split()[0]) <= 105 for c in perto), perto

    bancada.fraco(CONTROLE_1)
    for _ in range(40):
        bancada.passo()
    publicado = {ADAPTADOR_A: bancada.governador.publicar()[ADAPTADOR_A]}
    longe = caixas()
    assert longe[0] == "" and longe[1].endswith(" Hz"), longe


# ---------------------------------------------------------------------------------------------
# Furo 3: a proposta do Equilibrar diz que veio do sinal
# ---------------------------------------------------------------------------------------------


def _proposta_pelo_sinal() -> Any:
    from tests.unit.test_o_sinal_de_cada_controle_diz_se_ele_esta_longe import (
        FRACO,
        QUARTO,
        _mesa_equilibrada,
        _ordem,
    )

    ordem = _ordem(_mesa_equilibrada(), {FRACO: {QUARTO.replace(":", ""): -40}})
    assert ordem is not None
    return ordem


def test_a_proposta_pelo_sinal_leva_a_marca_e_os_dois_dbm() -> None:
    """`publicar()` diz que veio do sinal, e o dBm de cada adaptador viaja junto.

    MORDIDA: `_ordem_pelo_sinal` sem o `pelo_sinal=True`, ou `publicar` sem as três chaves.
    """
    publicada = _proposta_pelo_sinal().publicar()
    assert (publicada["pelo_sinal"], publicada["sinal_aqui"], publicada["sinal_la"]) == (
        True, -55, -40)


def test_a_proposta_por_contagem_nao_diz_que_veio_do_sinal() -> None:
    from hefesto_dualsense4unix.integrations import plano_de_radio as plano
    from tests.unit.test_o_sinal_de_cada_controle_diz_se_ele_esta_longe import (
        ULTIMO,
        _controle,
        _mesa,
    )

    desequilibrada = _mesa((_controle("aabbcc000001", -55, None), _controle("aabbcc000002", -30,
                           None), _controle(ULTIMO, -30, None)), ())
    ordem = plano.ordem_de_redistribuicao(desequilibrada)
    assert ordem is not None
    publicada = ordem.publicar()
    assert (publicada["pelo_sinal"], publicada["sinal_aqui"], publicada["sinal_la"]) == (
        False, None, None)


def _cena_com_proposta(proposta: dict[str, Any]) -> dict[str, Any]:
    cena = _cena({"ap": {"lugar": "L1", "jogador": 2}})
    return {**cena, "proposta": proposta}


def test_o_cartao_do_equilibrar_diz_sinal_fraco_com_os_dois_numeros() -> None:
    """Por contagem o cartão diz «dividido em N»; pelo sinal, «com sinal fraco» e os dBm.

    MORDIDA: `dica_do_movimento` sem o ramo `pelo_sinal`, ou `_o_movimento_da_central` sem passar
    a marca: o cartão volta a falar em «dividido» para um controle que só está longe.
    """
    proposta = {"controle": "ap", "destino": "L2", "pelo_sinal": True,
                "sinal_aqui": -78, "sinal_la": -52}
    movimento = a08._o_movimento_da_central(_cena_com_proposta(proposta))
    assert movimento is not None and movimento.pelo_sinal
    from hefesto_dualsense4unix.integrations import dicas_da_conexao as dicas

    dica = dicas.dica_do_movimento(movimento)
    assert dica.titulo == "P2 com sinal fraco", (
        f"o sinal fraco é do controle, e o título diz {dica.titulo!r}")
    assert "-78 dBm" in dica.porque and "-52 dBm" in dica.porque
    assert "dividido" not in dica.titulo and "mesa" not in dica.porque.lower()
    por_contagem = a08._o_movimento_da_central(
        _cena_com_proposta({"controle": "ap", "destino": "L2"}))
    assert por_contagem is not None and not por_contagem.pelo_sinal
    assert "sinal" not in dicas.dica_do_movimento(por_contagem).titulo.lower()


def test_o_balao_ganha_so_o_atributo_e_a_cena_leva_a_marca_da_central() -> None:
    cena = _cena_com_proposta({"controle": "ap", "destino": "L2", "pelo_sinal": True,
                               "sinal_aqui": -78, "sinal_la": -52})
    balao = a08._molde_do_balao(cena)
    assert 'data-pelo-sinal="sim"' in balao and "funciona melhor" in balao
    assert balao.count("<button") == 1, "o balão ganhou um botão"
    sem = a08._molde_do_balao(_cena_com_proposta({"controle": "ap", "destino": "L2"}))
    assert "data-pelo-sinal" not in sem and "funciona melhor" in sem


def test_a_cena_leva_a_proposta_pelo_sinal_da_central_ate_o_cartao() -> None:
    """O caminho inteiro: `radio_central.proposta` (publicada) → cena → cartão «sinal fraco»."""
    publicada = _proposta_pelo_sinal().publicar()
    dono = {"id": "aa:bb:cc:00:00:01"}
    assert publicada["controle"] == "aabbcc000001"
    cena = a08._a_proposta_da_cena(publicada, [dono])
    assert cena is not None and cena["pelo_sinal"] is True
    assert (cena["sinal_aqui"], cena["sinal_la"]) == (-55, -40)
