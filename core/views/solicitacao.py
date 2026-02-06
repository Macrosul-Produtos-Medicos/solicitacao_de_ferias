from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from core.forms import SolicitacaoDeFeriasForm, VerificaSolicitacaoForm
from core.models.solicitacao import SolicitacaoDeFerias
from core.models.card import Card
from datetime import timedelta, datetime
import requests
from django.http import HttpResponseNotAllowed
from core.views.emails import email_nova_solicitacao, email_solicitacao_reprovada, email_solicitacao_aprovada

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
    solicitacao_em_aberto = SolicitacaoDeFerias.objects.filter(user = request.user, ferias_finalizadas = False, ferias_rejeitadas = False )

    #VERIFICA SE TEM SOLICITAÇÃO EM ABERTO
    if solicitacao_em_aberto:
        form = SolicitacaoDeFeriasForm() 
        return render(request, 'core/index.html', {'ferias_em_aberto': True, 'form':form })
    
    if request.method == 'POST':
        form = SolicitacaoDeFeriasForm(request.POST, request.FILES)
        if form.is_valid():
            solicitacao = form.save(commit=False)
            solicitacao.card = card_usuario
            solicitacao.user = request.user
            solicitacao.fim_do_descanso = form.cleaned_data['inicio_do_descanso'] + timedelta(days=int(form.cleaned_data['dias_de_descanso']) -1)

            # VERIFICA SE TEM SALDO DE FÉRIAS SUFICIENTE
            if int(card_usuario.saldo_de_ferias) < int(solicitacao.dias_de_descanso) + int(solicitacao.dias_vendidos):
                return render(request, 'core/index.html', {'saldo_de_ferias_insuficiente': True, 'form':form })
            
            #VERIFICA SE O DIA DE INICIO É FERIADO
            verificacao_de_feriado = verifica_feriados(solicitacao.inicio_do_descanso)

            if verificacao_de_feriado is True:
                solicitacao.save()
                email_nova_solicitacao(solicitacao)
                return render(request, 'core/index.html', {'form': form,'success': True })
            elif verificacao_de_feriado is False:
                return render(request, 'core/index.html', {'form': form, 'feriado': True})
            elif isinstance(verificacao_de_feriado, str):
                return render(request, 'core/index.html', {'form': form, 'erro_api': verificacao_de_feriado})
            else:
                # Fallback de segurança
                return render(request, 'core/index.html', {
                    'form': form,
                    'erro_api': f'Erro inesperado ao verificar feriados.'
                })
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


