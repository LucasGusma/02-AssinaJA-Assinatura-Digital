# AssinaJA — Hospital de Referência Modelo

Primeira versão local de demonstração do gerenciador de pendências de assinaturas.

## Executar

Requer Python 3.10 ou superior. Não precisa instalar pacotes.

```powershell
python server.py
```

Abra http://127.0.0.1:8765. Também é possível executar `iniciar.bat`.

### Abertura automática e rede local

Execute `iniciar.bat`: o iniciador Python abre o navegador e mantém o servidor em segundo plano. Não depende de scripts PowerShell. Logs ficam em `data/server-output.log` e `data/server-error.log`. Se o app já responder, o iniciador reutiliza essa instância. O computador precisa permanecer ligado; não foi instalado serviço de inicialização automática do Windows.

Para iniciar manualmente com rede: `python server.py --lan`. O modo de rede escuta nas interfaces IPv4. Endereço identificado em 06/10/2026: `http://192.168.27.160:8765` (pode mudar conforme a rede).

A criação da regra do firewall foi bloqueada por falta de privilégios administrativos. Para permitir acesso de outros computadores, a TI pode executar `liberar-rede.bat` como administrador. A regra autoriza entrada TCP 8765 somente de `LocalSubnet`, no perfil de domínio. Nenhuma política de execução ou perfil de rede foi alterado. Conexões de outras sub-redes não estão incluídas. Validar o acesso a partir de outro computador após a liberação.

Esta liberação é para demonstração com dados fictícios e credenciais públicas. A integração com documentos reais exige autenticação e acesso adequados antes da ativação.

Usuário: `secretaria`. Senha: `Demo@2026`.
Outros usuários: `coordenador`, `superintendente`, `medico`, `enfermagem`, `cirurgia`, `tecnico`, `multi`, `admin`. Todos usam a mesma senha de demonstração.

## O que funciona

- Login com hash de senha PBKDF2 e sessão de uma hora em cookie HttpOnly/SameSite.
- Banco SQLite persistente, criado em `data/assinaja.db` na primeira execução.
- Listagem por setor e área, busca, filtros, indicadores e fila por destinatário.
- Encaminhamento pela secretaria para coordenador/superintendente do mesmo setor e área, validado no servidor.
- Autor original preservado; justificativa obrigatória; auditoria na mesma transação.
- Visão global para administrador, sem permissão adicional de encaminhamento.
- Consulta de acessos e página de estado da integração.

## Limites da demonstração

Não usar com dados reais de pacientes. O comando python server.py fica restrito a localhost; iniciar.bat habilita a rede local. Credenciais são públicas de demonstração. Sessões ficam em memória e são encerradas ao reiniciar. A versão não implementa provisionamento de usuários, identidade corporativa, limitação de tentativas, HTTPS, assinatura digital ou operação de produção. Os registros assinados são exemplos fictícios, não assinaturas produzidas pelo aplicativo. Os nomes são fictícios.

A logo original `FUNDO BRANCO.png` foi copiada com autorização para `static/logo-baleia.png` e aparece no cabeçalho do login. O arquivo original foi preservado; o CSS enquadra a marca, omitindo as margens externas, e a exibe sobre o cabeçalho verde. O carregamento não depende da unidade M:.

## Integração MV: pendente

`mv_adapter.py` prepara conexão Oracle de leitura e consulta de metadados. A conexão de produção foi testada em modo somente leitura em 06/10/2026. PW_DOCUMENTO_CLINICO foi localizada; PW_DOCUMENTO_ASSINADO não foi encontrada entre os objetos acessíveis. Não há sincronização de documentos ou instalação de trigger; o dashboard continua em demonstração.

### Diagnóstico local autorizado

O diagnóstico também aceita `.env`, com prioridade sobre `mv.local.json`. Modelo sem credenciais: `.env.example`. Campos: `MV_ENVIRONMENT`, `DB_USER`, `DB_PASSWORD`, `DB_DSN`, `DB_OWNER` e, opcionalmente, `ORACLE_CLIENT_DIR`. Com o diretório do cliente preenchido, usa Oracle Client (modo Thick). A senha do `.env` é usada somente pelo diagnóstico local, sem ser impressa; se estiver vazia, será solicitada no terminal. O `.env` está fora do Git e das rotas HTTP, mas é um arquivo local em texto simples e deve permanecer com acesso restrito.

Os campos `AUTH_SERVICE_URL` e `MV_LOGIN_URL` são referências ainda não utilizadas pelo aplicativo. Nenhum segredo TOTP de outro sistema é copiado. Criar o `.env` e consultar metadados não ativa documentos reais nem autenticação institucional no dashboard.

1. Copie `mv.example.json` para `mv.local.json` e preencha ambiente, host, porta, serviço, usuário de leitura e owner confirmado pela TI. O owner USUARIO_BANCO é uma sugestão baseada no SQL fornecido, a confirmar.
2. Prepare o ambiente Python e o driver:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements-mv.txt
.venv\Scripts\python diagnosticar_mv.py
```

A senha será solicitada no terminal sem ser exibida ou salva. Não a envie pelo chat. `mv.local.json`, `.venv` e `data` são ignorados pelo Git.

O diagnóstico inicia uma transação de leitura, consulta somente colunas e chaves das duas tabelas em `ALL_TAB_COLUMNS`, `ALL_CONSTRAINTS` e `ALL_CONS_COLUMNS`, e salva `data/mv-schema.json`. Nenhum dado de paciente é consultado. A ausência de uma tabela no resultado pode indicar owner incorreto ou falta de permissão. Use usuário com privilégios de leitura concedidos pela TI: a transação de leitura não substitui esse controle.

O conector usa o [driver oficial python-oracledb](https://python-oracledb.readthedocs.io/en/stable/user_guide/connection_handling.html). A compatibilidade com a versão Oracle do hospital deverá ser validada; não há configuração de Oracle Client/Thick nesta etapa.

Após validar o relatório, precisamos mapear estados, assinaturas múltiplas, setores e vínculos reais antes de carregar documentos no painel. As contas públicas de demonstração não podem acessar os registros reais. Um diagnóstico bem-sucedido não ativa o MV no site.

Precisamos confirmar em homologação:

1. Owner, colunas e chaves de `PW_DOCUMENTO_CLINICO` e `PW_DOCUMENTO_ASSINADO`, inclusive como identificar pendências e múltiplas assinaturas.
2. Relacionamentos de usuários, prestadores, setores, áreas e habilitações.
3. Host, porta, serviço Oracle e forma aprovada de armazenar credenciais de leitura; não enviar senhas pelo chat.
4. Mecanismo oficial do MV para abrir/assinar documentos e devolver o estado confirmado.
5. Regras institucionais de substituição/coassinatura por tipo documental.

A trigger apresentada pelo solicitante troca o prestador de um documento do modelo 624. Ela não assina. Não foi aplicada: o fluxo local registra um destinatário separadamente do autor. Fonoaudiologia, nutrição e psicologia poderão ter habilitações próprias no mapeamento real, sem assumir que todos os profissionais multi podem assinar qualquer documento.

Antes de ativar integração ou escrita no MV, apresentar operações/campos e solicitar autorização específica do solicitante.

## Testes

```powershell
python -m unittest discover -s tests -v
```

Desenvolvedores: Lucas Gusmão e Gabriel Soares.

## Consulta real de pendências (06/10/2026)

A aba Integração MV consulta `USUARIO_BANCO.PW_DOCUMENTO_CLINICO` com `USUARIO_BANCO.PAGU_OBJETO`, usando `TP_STATUS = FECHADO` e `SN_ASSINATURA = S`, conforme confirmação do hospital. Exclui documentos ABERTOS, ASSINADOS, CANCELADOS e IMPORTADOS. Limite de 31 dias por consulta e 50 registros por página; paginação por código decrescente. As datas filtram DH_CRIACAO. A API valida os vínculos no servidor antes de abrir a conexão. Não replica documentos reais no SQLite.

ADMIN foi confirmado ativo no MV e autorizado pelo solicitante como administrador master com consulta de todos os setores. `MV_MASTER_USER` identifica o cadastro inicial; não define senha. A entrada usa a senha institucional digitada pelo usuário e comparação no Oracle pelo mesmo mecanismo do aplicativo institucional instalado. Não há senha local alternativa nem armazenamento da senha MV do usuário. O teste de entrada com a senha pessoal deverá ser feito pelo próprio usuário. A inicialização cadastra a conta local e sua concessão master. Revogações futuras devem remover MV_MASTER_USER e desabilitar mv_accounts, pois a inicialização reaplica a concessão configurada.

O perfil master abre diretamente a consulta real, sem misturar registros fictícios. Conforme autorização de 07/10/2026, usuários institucionais ativos autenticados no MV são cadastrados localmente para leitura de todos os setores. Contas locais explicitamente desabilitadas não entram. Leitura global não concede administração: apenas is_master permite alterar permissões. As contas DEMO continuam bloqueadas, inclusive admin. Nenhuma permissão é obtida do cliente HTTP.

O endpoint `/api/mv/documents` recebe start/end, sector opcional e before opcional. A consulta é ao vivo e os resultados podem mudar entre páginas quando o MV é atualizado. Assinatura e encaminhamento de registros reais ainda não foram habilitados. A aba Documento lê PDF vinculado em DOCUMENTO_DIGITAL (quando disponível) ou campos reais do Editor MV. Campos não reproduzem o formulário oficial, não incluem imagens nem comprovam assinatura; documentos sem fonte compatível mostram indisponibilidade. Leituras têm limites de tamanho e avisos de conteúdo parcial.

## Setores e permissões (07/10/2026)

Diretório obtido de SETOR, USUARIO_SETOR e usuários ativos em DBASGU.USUARIOS, com perfil profissional de PRESTADOR/TIP_PRESTA. Não se infere cargo de coordenador a partir desse perfil. Somente o master altera mv_forward_permissions por usuário/setor, com auditoria em mv_permission_audit e revalidação do vínculo ativo. Essa permissão local ainda não executa transferência. Todas as conexões Oracle continuam em transação somente leitura. Para ativar escrita e assinatura, falta validar a API/rotina oficial, autenticação do signatário e regras de substituição por setor/área, preservando autoria e auditoria.

## Painel e escopo de transferência (07/10/2026)

Visão geral é a entrada dos usuários MV, com consulta automática dos últimos sete dias e cartões referentes à página carregada (não ao total do hospital). Somente o master vê Acessos e pode consultar /api/mv/users ou modificar permissões. Usuários ativos MV entram sem importação de senhas ou cadastro manual; contas locais desabilitadas permanecem bloqueadas.

O solicitante definiu que o AssinaJA será apenas para transferência, permitindo qualquer pessoa como destinatária, sem assinatura dentro do app. Esta orientação substitui a restrição anterior de destinatários coordenadores/superintendentes. A seleção e execução reais ainda dependem da rotina MV validada; não há transferência simulada apresentada como realizada no MV.

Investigação: os comentários oficiais de PW_DOCUMENTO_CLINICO.CD_USUARIO e CD_PRESTADOR exigem correspondência com as tabelas de origem (PRE_MED, PW_RECEITA etc.). PRC_FFCV_ALTERA_PRESTADOR atua em contas de faturamento e não deve ser usada para pendências clínicas. Não foi validada uma operação genérica de transferência. É necessário identificar a tela/rotina existente ou contrato de integração MV por módulo antes de propor campos de escrita. Nenhuma escrita Oracle executada.

A investigação de triggers identificou TRG_ATUALIZA_PREST_ATENDIME habilitada: em condições específicas de urgência e prestador geral, UPDATE em PW_DOCUMENTO_CLINICO pode alterar ATENDIME e ITREG_AMB e inserir MOV_PRESTADOR. A atualização isolada de CD_PRESTADOR não tem efeitos limitados necessariamente ao documento. Validar procedimento institucional e efeitos antes de ativar escrita.
## Filtros e navegação (08/10/2026)

O diretório apresenta setores com SETOR.SN_ATIVO = S e usuários com USUARIOS.SN_ATIVO = S vinculados a esses setores. A busca de usuários no setor aceita nome ou código MV, ignorando diferenças de acentuação. A lista de documentos oferece Anterior/Próxima e número da página; mantém os marcadores de consulta para voltar e reinicia a navegação ao consultar novos filtros. Falhas de consulta não avançam a página.

Validação: 22 testes Python e testes JavaScript de navegação e pesquisa em DOM simulado (`node tests/test_navigation.cjs`). Avanço visual conferido antes da interrupção; navegador de testes indisponível na retomada. Nenhuma escrita Oracle realizada.
