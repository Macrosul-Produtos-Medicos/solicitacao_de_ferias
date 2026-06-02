# Integração com SharePoint

## Visão geral

Quando uma solicitação de férias é **aprovada** por um gestor, o sistema cria automaticamente um evento na lista de calendário do SharePoint da organização via Microsoft Graph API. Isso mantém o calendário corporativo sincronizado sem intervenção manual.

---

## Fluxo de execução

```
Gestor aprova solicitação (POST /aprovar/<id>)
        │
        ▼
  aprovar_solicitacao() — core/views/solicitacao.py
        │  salva solicitação, atualiza saldo, envia e-mail
        │
        └──► criar_evento_sharepoint(solicitacao) — core/services/sharepoint.py
                    │
                    ├─ 1. _get_access_token()   → obtém token OAuth 2.0 (client_credentials)
                    ├─ 2. _get_site_id(token)   → resolve o ID interno do site (com cache)
                    └─ 3. POST /sites/{id}/lists/{list_id}/items  → cria o item na lista
```

> Falhas na criação do evento **não bloqueiam** a aprovação da solicitação. O erro é capturado e registrado em log (`logger.error`), garantindo que um problema no SharePoint não impeça o fluxo principal.

---

## Autenticação — OAuth 2.0 Client Credentials

A integração usa o fluxo **Client Credentials** do Azure AD (sem interação do usuário).

**Endpoint:**
```
POST https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token
```

**Parâmetros enviados:**

| Campo           | Valor                                    |
|-----------------|------------------------------------------|
| `grant_type`    | `client_credentials`                     |
| `client_id`     | `SHAREPOINT_CLIENT_ID`                   |
| `client_secret` | `SHAREPOINT_CLIENT_SECRET`               |
| `scope`         | `https://graph.microsoft.com/.default`   |

O token retornado (`access_token`) é usado como `Bearer` em todas as chamadas à Microsoft Graph API.

---

## Resolução do Site ID

O SharePoint identifica sites internamente por um ID (GUID), não pelo hostname. Por isso, antes de criar o evento, o serviço busca esse ID:

```
GET https://graph.microsoft.com/v1.0/sites/{SHAREPOINT_SITE_HOSTNAME}
Authorization: Bearer {token}
```

O resultado é **cacheado em memória** na variável `_site_id_cache` para evitar chamadas desnecessárias a cada aprovação.

---

## Criação do evento na lista

Com o `site_id` em mãos, o serviço faz um `POST` para adicionar um item na lista de eventos do SharePoint:

```
POST https://graph.microsoft.com/v1.0/sites/{site_id}/lists/{SHAREPOINT_EVENTS_LIST_ID}/items
```

**Payload enviado:**

```json
{
  "fields": {
    "Title": "Férias {nome do colaborador}",
    "EventDate": "{inicio_do_descanso}T12:00:00Z",
    "EndDate": "{fim_do_descanso}T12:00:00Z",
    "Category": "Holiday",
    "fAllDayEvent": true
  }
}
```

| Campo          | Origem no modelo                                   |
|----------------|----------------------------------------------------|
| `Title`        | `solicitacao.card.nome`                            |
| `EventDate`    | `solicitacao.inicio_do_descanso` (formato ISO)     |
| `EndDate`      | `solicitacao.fim_do_descanso` (formato ISO)        |
| `Category`     | Fixo: `"Holiday"`                                  |
| `fAllDayEvent` | Fixo: `true`                                       |

---

## Configuração — variáveis de ambiente

Adicione as seguintes variáveis ao arquivo `.env` do projeto:

```env
# SharePoint — preencha com seus valores do Entra (portal.azure.com)
SHAREPOINT_TENANT_ID=<id-do-tenant-azure>
SHAREPOINT_CLIENT_ID=<id-do-app-registration>
SHAREPOINT_CLIENT_SECRET=<secret-do-app-registration>
SHAREPOINT_SITE_HOSTNAME=<empresa>.sharepoint.com
SHAREPOINT_EVENTS_LIST_ID=<guid-da-lista-de-eventos>
```

Essas variáveis são lidas em `solicitacao_de_ferias/settings.py` e disponibilizadas via `django.conf.settings`.

---

## Como registrar o aplicativo no Azure

1. Acesse [portal.azure.com](https://portal.azure.com) → **Microsoft Entra ID** → **Registros de aplicativo** → **Novo registro**.
2. Dê um nome (ex.: `solicitacao-ferias`) e registre.
3. Em **Certificados e segredos**, crie um novo **segredo de cliente** e copie o valor — ele é exibido apenas uma vez.
4. Em **Permissões de API**, adicione a permissão de aplicativo (não delegada):
   - `Microsoft Graph` → `Sites.ReadWrite.All`
5. Clique em **Conceder consentimento de administrador**.
6. Copie o **ID do aplicativo (client_id)** e o **ID do diretório (tenant_id)** na tela de visão geral.

Para obter o `SHAREPOINT_EVENTS_LIST_ID`, acesse a lista de eventos no SharePoint → **Configurações da lista** → a GUID aparece na URL como `List=%7B...%7D` (decodifique o URL encoding).

---

## Arquivos relevantes

| Arquivo | Responsabilidade |
|---|---|
| [core/services/sharepoint.py](../core/services/sharepoint.py) | Toda a lógica de autenticação e criação do evento |
| [core/views/solicitacao.py](../core/views/solicitacao.py) | Chama `criar_evento_sharepoint` no fluxo de aprovação |
| [solicitacao_de_ferias/settings.py](../solicitacao_de_ferias/settings.py) | Lê as variáveis de ambiente e expõe via `settings.*` |
