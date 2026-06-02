from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from core.forms import SolicitacaoDeFeriasForm, VerificaSolicitacaoForm
from core.models.solicitacao import SolicitacaoDeFerias
from core.models.card import Card
from datetime import timedelta, datetime
import logging
import requests
from django.http import HttpResponseNotAllowed
from core.views.emails import email_nova_solicitacao, email_solicitacao_reprovada, email_solicitacao_aprovada
from core.services.sharepoint import criar_evento_sharepoint

logger = logging.getLogger(__name__)

def verifica_feriados(data_inicio_das_ferias):
    ano_atual = datetime.now().year
    proximo_ano = datetime.now().year + 1
    url_ano_atual = f'https://brasilapi.com.br/api/feriados/v1/{ano_atual}'
    url_proximo_ano = f'https://brasilapi.com.br/api/feriados/v1/{proximo_ano}'
    feriados_curitiba = [
        {
            "date":f"{ano_atual}-09-08",
            "nome":"Nossa Senhora da Luz",
        },
        {
            "date":f"{proximo_ano}-09-08",
            "nome":"Nossa Senhora da Luz",
        },
    ]

    try:
        response_atual = requests.get(url_ano_atual)
        feriados_atuais = response_atual.json()

        response_proximo_ano = requests.get(url_proximo_ano)
        feriados_proximo_ano = response_proximo_ano.json()
    except:
        erro = 'A API para verificação de datas está fora do ar. Tente novamente mais tarde, ou entre em contato com a Equipe de Desenvolvedores Macrosul.'
        return erro

    todos_os_feriados = feriados_atuais + feriados_proximo_ano + feriados_curitiba
    datas_feriados = [datetime.strptime(f["date"], "%Y-%m-%d").date() for f in todos_os_feriados]

    for feriado in datas_feriados:
            diferenca = (feriado - data_inicio_das_ferias).days
            if 0 <= diferenca <= 2:  # feriado no mesmo dia, ou 1 ou 2 dias depois
                return False  # Não pode iniciar férias nesse período
    return True  # OK: não é feriado nem até 48h antes


@login_required
def add_solicitacao(request):
    card_usuario = Card.objects.get(colaborador=request.user)
    solicitacoes_pendentes = SolicitacaoDeFerias.objects.filter(
        user=request.user, 
        solicitacao_aprovada=False,
        ferias_rejeitadas=False
    )

    solicitacoes_aprovadas_e_pendentes = SolicitacaoDeFerias.objects.filter(
        user = request.user,
        solicitacao_aprovada = True,
        ferias_finalizadas = False
    )


    dias_reservados = 0
    for s in solicitacoes_pendentes:
        dias_reservados += int(s.dias_de_descanso or 0) + int(s.dias_vendidos or 0)

    dias_vendidos_pendente = 0
    for s in solicitacoes_pendentes:
        dias_vendidos_pendente += int(s.dias_vendidos or 0)

    for s in solicitacoes_aprovadas_e_pendentes:
        dias_vendidos_pendente += int(s.dias_vendidos or 0)
    
    saldo_total = int(card_usuario.saldo_de_ferias or 0)
    saldo_disponivel = saldo_total - dias_reservados

    if saldo_disponivel <= 0:
        form = SolicitacaoDeFeriasForm()
        return render(request, 'core/index.html', {
            'ferias_em_aberto': True,
            'form': form 
        })
    
    if request.method == 'POST':
        form = SolicitacaoDeFeriasForm(request.POST, request.FILES)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            dias_pedidos = int(form.cleaned_data.get('dias_de_descanso') or 0)
            dias_vendidos = int(form.cleaned_data.get('dias_vendidos') or 0)
            
            if (dias_pedidos + dias_vendidos) > saldo_disponivel :
                return render(request, 'core/index.html', {
                    'saldo_de_ferias_insuficiente': True, 
                    'form': form 
                })
            elif dias_vendidos_pendente + dias_vendidos > 10:
                return render(request, 'core/index.html', {
                    'vender_10_dias': True, 
                    'form': form 
                })

            solicitacao.card = card_usuario
            solicitacao.user = request.user
            solicitacao.fim_do_descanso = form.cleaned_data['inicio_do_descanso'] + timedelta(days=dias_pedidos - 1)

            verificacao_de_feriado = verifica_feriados(solicitacao.inicio_do_descanso)

            if verificacao_de_feriado is True:
                solicitacao.save()
                email_nova_solicitacao(solicitacao)
                return render(request, 'core/index.html', {'form': form,'success': True })
            elif verificacao_de_feriado is False:
                return render(request, 'core/index.html', {'form': form, 'feriado': True})
            else:
                return render(request, 'core/index.html', {'form': form, 'erro_api': 'Erro na verificação.'})
        else:
            return render(request, 'core/index.html', {'form': form, 'form_errors': form.errors})
    else:
        form = SolicitacaoDeFeriasForm()
        return render(request, 'core/index.html', {'form': form})

@login_required
def reprovar_solicitacao(request, id_solicitacao):
    solicitacao = get_object_or_404(SolicitacaoDeFerias, pk=id_solicitacao)

    if request.method == 'POST':
        solicitacao.ferias_rejeitadas = True
        solicitacao.motivo_rejeicao = request.POST.get('motivo_rejeicao')
        solicitacao.save()
        email_solicitacao_reprovada(solicitacao)
        return redirect(reverse('index'))

    return HttpResponseNotAllowed(['POST'])

@login_required
def aprovar_solicitacao(request, id_solicitacao):
    solicitacao = SolicitacaoDeFerias.objects.get(pk=id_solicitacao)
    if request.method == 'POST':
        form = VerificaSolicitacaoForm(request.POST)
        if form.is_valid():
            #APROVANDO A SOLICITAÇÃO
            solicitacao.solicitacao_aprovada = True
            #ATUALIZANDO O SALDO DO CARD
            saldo = int( solicitacao.card.saldo_de_ferias)
            dias_descanso_solicitados = int(solicitacao.dias_de_descanso)
            dias_venda_solicitados = int(solicitacao.dias_vendidos)
            dias_totais_solicitados = dias_descanso_solicitados + dias_venda_solicitados
            solicitacao.card.saldo_de_ferias = saldo - dias_totais_solicitados
            #SALVANDO CARD E SOLICITACAO
            solicitacao.save()
            solicitacao.card.save()
            email_solicitacao_aprovada(solicitacao)
            try:
                criar_evento_sharepoint(solicitacao)
            except Exception as e:
                logger.error("Falha ao criar evento SharePoint para %s: %s", solicitacao.card.nome, e)
            return redirect(reverse('index'))
        else:
            return render(request, 'core/index.html', {'form': form, 'form_errors': form.errors})
    return redirect(reverse('index'))

def verificar_inicio_das_ferias():
    solicitacoes = SolicitacaoDeFerias.objects.filter(solicitacao_aprovada=True)
    for solicitacao in solicitacoes:
        if solicitacao.inicio_do_descanso <= datetime.now().date() and not solicitacao.ferias_iniciadas:
            solicitacao.ferias_iniciadas = True
            solicitacao.save()
    return redirect(reverse('index'))

def verificar_fim_das_ferias():
    solicitacoes = SolicitacaoDeFerias.objects.filter(ferias_iniciadas=True)
    for solicitacao in solicitacoes:
        if solicitacao.fim_do_descanso <= datetime.now().date():
            solicitacao.ferias_finalizadas = True
            solicitacao.save()
    return redirect(reverse('index'))    


