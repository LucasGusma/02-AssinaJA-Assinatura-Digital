# Execução e implantação

> Atualização de 09/10/2026: o modo ativo é `mv_refcursor`. Consulte [a integração da package recebida](mv-package-integration.md). As seções sobre JSON e integração pendente abaixo aplicam-se ao modo `json`.

## Desenvolvimento local

1. Instalar Python compatível com as dependências e Oracle Instant Client da mesma arquitetura. Esta implementação foi validada localmente com Python 3.14; o modo Thick depende também da compatibilidade do cliente com a versão do servidor Oracle.
2. Instalar as dependências no ambiente virtual e executar `npm ci` em `frontend/`.
3. Compilar o React com `npm run build` em `frontend/`.
4. Executar `.venv\Scripts\python.exe server.py` na raiz. O endereço padrão é `http://127.0.0.1:8765`.
5. Para editar o frontend com recarga, executar também `npm run dev` em `frontend/` e abrir a URL indicada pelo Vite. `/api` é encaminhado para o backend local.

`iniciar.bat` usa o ambiente virtual e o iniciador atualizado. Ele não instala dependências nem compila o frontend. Uma instância antiga ocupando a porta precisa ser encerrada por seu responsável; o iniciador não a finaliza automaticamente.

`.env` é lido somente no backend; variáveis do processo têm prioridade. Credenciais não usam prefixo VITE e não entram no bundle. O modelo `.env.example` não contém credenciais reais.

## Integração pendente

Com `ORACLE_PACKAGE_ROUTINE` vazio, a aplicação mostra a integração pendente, `/api/health/live` retorna 200 e `/api/health/ready` retorna 503. Não há conexão com Oracle, login simulado ou fallback para SQLite. Esse comportamento é esperado até a entrega da package.

Ao preencher a rotina, o startup inicializa o Instant Client e o pool. Falha de cliente ou conexão impede a inicialização; não existe fallback Thin. `/api/health/ready` invoca `health.ready` na package e só retorna 200 se houver sucesso.

## Produção

- Compilar o frontend antes da publicação e executar a API como serviço com usuário dedicado. O lançador local não instala serviço Windows.
- Colocar proxy HTTPS na frente da API. Preservar `Host` e `Origin`, limitar tamanho e tempo de requisição e aplicar limitação global de tráfego/login.
- Configurar `APP_ENVIRONMENT=production`, `SESSION_COOKIE_SECURE=true`, `ALLOWED_HOSTS` com nomes explícitos e `ALLOWED_ORIGINS` com origens HTTPS exatas, sem barra final. As listas usam JSON no `.env`.
- O lançamento padrão desativa proxy headers para não confiar em cabeçalhos falsificados. Para usar IP real atrás de proxy, configurar explicitamente no Uvicorn somente os endereços confiáveis; não usar confiança irrestrita.
- O controle CSRF exige Origin autorizado, JSON e `X-CSRF-Protection: 1` em todas as mutações. Não há CORS habilitado; servir React e API na mesma origem.
- O cookie usa Path `/api`, HttpOnly e SameSite Strict. Sessões, revogação e bloqueio institucional precisam ser implementados no Oracle antes da operação real.
- Usuário da API precisa somente dos grants dos contratos homologados; não usar a conta de administração/migração como conta de execução. Conexões Oracle devem seguir a configuração de proteção de transporte aprovada pelo DBA.
- O pool é por processo: total máximo = processos × `ORACLE_POOL_MAX`. Inicialmente, usar um processo e ajustar somente após medir latência, espera por conexão e capacidade do Oracle.
- Não manter senhas, tokens, corpos de login ou dados clínicos em logs. Logs de acesso do lançador estão desativados para evitar URLs de pacientes/documentos em arquivos genéricos. A auditoria funcional deve ser feita pela package.
- Respostas da API usam `Cache-Control: no-store`. Arquivos PDF são limitados a 20 MiB e lidos dentro da conexão; dimensionar memória conforme concorrência. O frontend não guarda token ou dados clínicos em localStorage.
- Endpoint OpenAPI disponível em `/api/openapi.json` somente fora de produção. Docs interativas externas não são carregadas.

Não houve implantação em produção, configuração de TLS, criação de serviço, migração de dados SQLite ou ativação de transferências nesta entrega.

## Reversão

O servidor anterior está em `legacy/server.py`, os módulos `mv_*.py`, `static/` e o banco local foram preservados. O README anterior está em `docs/legacy-README.md`. O backend novo não importa esses módulos nem abre o SQLite.

Para consultar o comportamento antigo em desenvolvimento, o comando explícito é `python -m legacy.server`; requer revisão das configurações legadas e usa o banco local existente. Não executar versões diferentes na mesma porta. A reversão operacional após ativar escritas Oracle deverá ser planejada com a package e os dados migrados; trocar a versão HTTP não desfaz alterações de banco.

## Validações locais

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m ruff check backend
npm.cmd --prefix frontend test
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend audit
```

Os testes novos usam gateways simulados e verificam a fronteira de integração; não comprovam a implementação futura das regras Oracle. A homologação real deve incluir grants, revogação concorrente, estado do pool, PDF, idempotência, efeitos das rotinas MV e carga com volumes representativos.
