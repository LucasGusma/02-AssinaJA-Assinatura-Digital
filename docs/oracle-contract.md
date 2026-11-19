# Contrato de integração Oracle — proposta v1

> Atualização de 09/10/2026: o modo ativo é `mv_refcursor`. Consulte [a integração da package recebida](mv-package-integration.md). As seções sobre JSON e integração pendente abaixo aplicam-se ao modo `json`.

Este é o contrato implementado pelo adaptador Python, não a declaração de uma package existente. A package será fornecida pelo responsável pelo banco. Nenhum objeto, grant ou dado Oracle foi criado nesta implementação. Se a package usar procedures separadas ou REF CURSOR, adaptar apenas `backend/app/infrastructure/oracle/gateway.py`; preservar os contratos HTTP.

## Ativação

`ORACLE_PACKAGE_ROUTINE` vazio mantém a API no estado `pending`, sem abrir conexões, autenticar usuários fictícios ou carregar SQLite. Após homologar o contrato, preencher com `SCHEMA.PACKAGE.PROCEDURE` (ou `PACKAGE.PROCEDURE`). O nome é configuração de servidor validada; nunca vem de parâmetros HTTP.

Assinatura proposta para dados JSON:

```sql
PROCEDURE executar(p_request IN CLOB, p_response OUT CLOB);
```

Assinatura proposta para arquivo PDF, configurada separadamente em `ORACLE_FILE_ROUTINE`:

```sql
PROCEDURE obter_pdf(
  p_session IN VARCHAR2,
  p_document_id IN NUMBER,
  p_request_id IN VARCHAR2,
  p_content OUT BLOB,
  p_status OUT VARCHAR2
);
```

A ordem dos parâmetros é parte do contrato. O BLOB deve conter bytes PDF originais, sem base64. A procedure deve validar sessão, escopo e documento antes de retornar conteúdo. `p_status` é `OK` ou um código da tabela de erros abaixo.

## Envelope JSON

Entrada:

```json
{
  "version": 1,
  "operation": "documents.list",
  "session": "token-opaco-da-sessao",
  "request_id": "identificador-de-correlacao",
  "payload": {
    "start": "2026-10-01",
    "end": "2026-10-08",
    "sector": null,
    "before": null,
    "limit": 50
  }
}
```

Sucesso: `{"ok":true,"data":{...}}`. Erro: `{"ok":false,"error":{"code":"FORBIDDEN"}}`.

`data` é sempre objeto JSON. Datas/horas devem ser ISO 8601 com offset explícito; a conversão do horário Oracle sem fuso deve seguir o fuso institucional. Início e fim do filtro são datas inclusivas. O Oracle pode implementar a condição com limite superior exclusivo no dia seguinte.

Limites de transporte: entrada HTTP de 8 KiB; resposta JSON da package até 2 Mi caracteres; PDF até 20 MiB. O limite de resposta é uma proteção adicional, não substitui paginação na package. Consultas de campos do Editor retornam no máximo 300 campos e sinalizam truncamento.

## Operações

| Operação | Payload | Data de sucesso |
|---|---|---|
| `health.ready` | `{}`; sem sessão | `{}`; confirmar disponibilidade dos objetos e contrato |
| `auth.login` | `username`, `password`, `ttl_seconds` | `user`, `token`, `expires_in` |
| `auth.session` | `{}` | `user` |
| `auth.logout` | `{}` | `{}`; revogar sessão |
| `directory.sectors` | `{}` | `sectors: [{id,name}]` |
| `directory.users` | `sector_id` | `users: [{username,name,profile,can_forward}]`; exclusivo master |
| `directory.recipients` | `document_id`, `search`, `limit:50` | `users` no mesmo formato; verificar direito de transferir |
| `documents.list` | `start`, `end`, `sector`, `before`, `limit:50` | `documents`, `next_cursor` |
| `documents.content` | `document_id` | `kind`, `title`, `fields`, `partial`, `message` |
| `permissions.update` | `username`, `sector_id`, `enabled` | `{}`; concessão e auditoria atômicas |
| `transfers.create` | `document_id`, `recipient`, `reason`, `idempotency_key` | `transfer_id`, `message` |
| `audit.list` | `before`, `limit:50` | `events`, `next_cursor` |

Não aceitar operações arbitrárias. Cada operação deve validar seus próprios parâmetros e autorização, mesmo após `auth.session`. A checagem da API é complementar e não elimina a necessidade de revalidar uma revogação concorrente dentro da operação final.

### Usuário e sessão

```json
{
  "user": {
    "username": "USUARIO_TESTE",
    "name": "Nome de exemplo",
    "is_master": false,
    "can_transfer": false,
    "all_sectors": true
  },
  "token": "token-aleatorio-criptograficamente-seguro-em-base64url",
  "expires_in": 3600
}
```

Somente `auth.login` retorna token. A API o coloca em cookie HttpOnly, nunca no JSON enviado ao React. O token deve possuir pelo menos 256 bits de entropia; o transporte aceita 32–512 caracteres `[A-Za-z0-9_-]`. Persistir seu hash, expiração e revogação no Oracle. Não armazenar senha institucional no AssinaJA. A expiração Oracle deve respeitar `ttl_seconds`; o limite do cookie não substitui a expiração no banco.

Usuário ativo, bloqueios, master, escopo e permissões devem vir do Oracle. Nenhum `actor`, perfil ou master fornecido pelo navegador é aceito. O login não aplica a transformação de credenciais da demonstração: ela deve ser encapsulada no mecanismo institucional confirmado pelo DBA.

### Lista de documentos

```json
{
  "documents": [{
    "id": 123,
    "title": "Documento de exemplo",
    "patient_name": "Nome de exemplo",
    "attendance_id": 456,
    "provider_name": "Profissional de exemplo",
    "mv_user": "USUARIO_TESTE",
    "sector_id": 1,
    "sector_name": "Setor de exemplo",
    "created": "2026-10-08T10:00:00-03:00",
    "status": "FECHADO",
    "can_transfer": false
  }],
  "next_cursor": null
}
```

Preservar a regra atual de documentos FECHADOS de objetos que exigem assinatura, salvo mudança deliberada no banco. A policy atual permite leitura global a usuários MV habilitados e reserva administração ao master. Não inferir master de leitura global. Filtrar antes de paginar. Ordenar pelo ID decrescente, buscar até `limit+1` e retornar como cursor o último ID exibido somente quando houver próxima página. Consultas são ao vivo, não um snapshot congelado.

### Conteúdo

- PDF disponível: `{"kind":"pdf","title":"Exemplo","fields":[],"partial":false}`. Consultar metadados, sem ler o BLOB inteiro nesta operação.
- Editor: `{"kind":"editor","fields":[{"label":"Campo","value":"Texto","truncated":false}],"partial":false}`.
- Indisponível: `{"kind":"unavailable","fields":[],"partial":false,"message":"Motivo seguro para exibição"}`.

Não retornar HTML executável. A interface renderiza os campos como texto. A visualização do Editor não reproduz o formulário oficial nem comprova assinatura. Metadados e PDF precisam validar o mesmo escopo de acesso.

### Auditoria

`{"events":[{"id":1,"created":"2026-10-08T10:00:00-03:00","actor":"USUARIO_TESTE","action":"Permissão alterada","detail":"Descrição segura do evento"}],"next_cursor":null}`.

Filtrar auditoria pelo usuário autenticado. Não incluir senhas, tokens ou conteúdo clínico desnecessário em `detail`.

### Erros

| Código | HTTP |
|---|---|
| `INVALID_CREDENTIALS`, `SESSION_EXPIRED` | 401 |
| `FORBIDDEN` | 403 |
| `NOT_FOUND` | 404 |
| `CONFLICT` | 409 |
| `INVALID_INPUT` | 422 |
| `RATE_LIMITED` | 429 |
| `UNAVAILABLE` | 503 |

Mensagens internas Oracle não são repassadas ao navegador. Erros de contrato retornam 502. O pacote pode registrar detalhes internamente usando `request_id`, sem registrar credenciais.

## Transações e concorrência

- Uma chamada de negócio usa uma conexão e uma transação. A API confirma a transação após envelope válido de sucesso; faz rollback em falhas. Não realizar `COMMIT`, DDL ou transações autônomas para alterações clínicas/permissões dentro dos packages.
- **Exceção explícita de autenticação:** respostas `INVALID_CREDENTIALS` ou `RATE_LIMITED` de `auth.login` confirmam apenas contadores e auditoria de tentativas. O pacote não pode alterar dados clínicos nessa operação. Isso permite bloqueios persistentes sem desfazer a contagem ao retornar erro HTTP.
- Sessões, bloqueios e autorização precisam funcionar entre múltiplos processos. O limitador local da API é apenas proteção complementar por IP; o bloqueio institucional pertence ao banco e limites globais de tráfego ao proxy.
- A operação de transferência deve revalidar estado, ator e destinatário dentro da transação e usar bloqueio/controle de concorrência adequado. Identificar a rotina MV homologada e todos os seus efeitos antes de habilitar `TRANSFERS_ENABLED`.
- Persistir a chave UUID de idempotência com ator, operação, hash do payload e resultado. Repetição da mesma chave e conteúdo retorna o resultado original; mesma chave com outro conteúdo deve resultar em conflito. A API não repete escritas automaticamente.
- Preservar autoria conforme a regra institucional e auditar os valores alterados. Não presumir que trocar apenas `CD_PRESTADOR` tem efeitos limitados ao documento.
- Não manter identidade ou permissões em variáveis globais de package ou contextos persistentes da conexão. O pool reutiliza sessões físicas: autenticar pelo token em cada chamada. Se sua package precisar de contexto Oracle, será necessário adicionar inicialização e limpeza específicas ao adaptador antes da ativação.

## Entrega da package

Fornecer nomes, assinaturas, exemplos de retorno, códigos de erro, grants necessários e semântica transacional. Com isso, ajustar o adaptador, executar integração em homologação e só então preencher as rotinas no `.env`. Se já houver outro contrato em construção, este documento não exige reescrever sua package: o adaptador é o ponto previsto para compatibilização.
