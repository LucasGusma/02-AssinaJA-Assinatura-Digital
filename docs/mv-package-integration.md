# Integração da package recebida — 09/10/2026

> Atualização: a consulta ativa agora é LISTA_PENDENCIAS, com escopos geral/pessoal, filtro FECHADO + assinatura obrigatória e paginação no Oracle. Veja [as regras atuais](pending-document-tabs.md). As limitações da listagem original abaixo foram superadas; as limitações de sessão, conteúdo e transferência permanecem.

Modo ativado no `.env`: `ORACLE_INTEGRATION_MODE=mv_refcursor` e `ORACLE_MV_PACKAGE=SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA`.

O adaptador `backend/app/infrastructure/oracle/mv_gateway.py` chama `LISTA_DOCUMENTOS(p_usuario,p_dt_ini,p_dt_fim,documentos OUT SYS_REFCURSOR)` usando o usuário autenticado, nunca um usuário arbitrário enviado pelo navegador. Preserva os estados retornados pelo banco. O fim da data é convertido para 23:59:59, pois a procedure usa `BETWEEN` sobre Oracle DATE.

A conexão real confirmou package e corpo VALID, assinaturas e colunas do REF CURSOR. A preparação da consulta de autenticação institucional também funcionou. O diagnóstico executou transação somente leitura e não buscou linhas clínicas.

## Limitações explícitas do contrato atual

- A procedure não filtra `TP_STATUS='FECHADO'`: a interface exibe o estado real e usa o termo documentos.
- Não há setor, cursor de paginação ou ORDER BY no contrato. O adaptador lê um resultado limitado a 10.000 linhas, ordena por ID decrescente e pagina em 50 registros. Acima desse limite, pede um período menor, sem exibir resultado parcial como completo. Para grandes volumes, acrescentar paginação e ordenação à procedure.
- PDF, campos do Editor, diretório, permissões e auditoria não estão implementados nessa package. As funcionalidades correspondentes ficam indisponíveis; não há fallback para SQLite.
- `ATUALIZA_PRESTADOR` não é chamada. A procedure precisa validar ator, destinatário, situação, concorrência e auditoria; seus efeitos de triggers também precisam ser homologados. `TRANSFERS_ENABLED=false` e bloqueio adicional no adaptador impedem a atualização mesmo por chamada HTTP direta.

## Autenticação e sessões nesta etapa

Mantida a comparação institucional já utilizada no projeto, em `DBASGU.USUARIOS` com a função `DBASGU.CRIPTO_DESCRIPTO`. Nenhuma senha é salva, devolvida ou registrada em log. O usuário deve testar a entrada com sua própria senha MV; o diagnóstico não testa nem conhece essa senha.

A package não fornece sessões. O adaptador usa tokens aleatórios, guardados apenas por hash em memória, com expiração, limite de quantidade, revogação no logout e revalidação do cadastro ativo em cada operação. **Executar somente um processo/worker. Reiniciar a API encerra as sessões.** A configuração padrão `server.py` já inicia um único processo.

Isso substitui temporariamente o contrato de sessões Oracle proposto anteriormente. Para múltiplos workers ou instâncias, fornecer procedimentos persistentes de sessão, revogação e bloqueio de tentativas na package; então remover o armazenamento temporário em memória. Não habilitar múltiplos workers com este adaptador.

Todas as chamadas Oracle deste modo iniciam transação somente leitura. Não foi criada nem alterada nenhuma package, grant ou tabela.

## Logos

Os arquivos enviados foram copiados sem alteração para `frontend/public`. O cabeçalho conserva a marca do hospital à esquerda, coloca o símbolo A seguido de `ssinaJA` no centro e BaleIA junto à frase à direita. O enquadramento das imagens e adaptação para celular são feitos por CSS.
