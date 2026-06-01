from django.urls import path
from core.api.urls import api
from core.views.cards import add_colaborador, vencimento_proximo, renova_saldo_de_ferias, edit_colaborador, remove_colaborador
from core.views.solicitacao import add_solicitacao, reprovar_solicitacao, aprovar_solicitacao, verificar_fim_das_ferias, verificar_inicio_das_ferias
from core.views.index import historico_rh, index

urlpatterns = [
   path('add_colaborador/', add_colaborador, name='add_colaborador'),
   path('edit_colaborador/<str:id_colaborador>/', edit_colaborador, name='edit_colaborador'),
   path('remove_colaborador/<str:id_colaborador>/', remove_colaborador, name='remove_colaborador'),

   path('vencimento_proximo/', vencimento_proximo, name='vencimento_proximo'),

   path('add_solicitacao/', add_solicitacao, name='add_solicitacao'),
   path('reprovar_solicitacao/<str:id_solicitacao>/', reprovar_solicitacao, name='reprovar_solicitacao'),
   path('aprovar_solicitacao/<str:id_solicitacao>/', aprovar_solicitacao, name='aprovar_solicitacao'),

   path('verificar_fim_das_ferias/', verificar_fim_das_ferias, name='verificar_fim_das_ferias'),
   path('verificar_inicio_das_ferias/', verificar_inicio_das_ferias, name='verificar_inicio_das_ferias'),
   
   path('renova_saldo_de_ferias/', renova_saldo_de_ferias, name='renova_saldo_de_ferias'),

   path('historico_rh/', historico_rh, name='historico_rh'),
   path('', index, name='index'),

   path('api/', api.urls),
]