# Visão geral e Meus documentos — 09/10/2026

- **Visão geral:** qualquer usuário institucional autenticado consulta documentos de todos os usuários no período selecionado.
- **Meus documentos:** mesma apresentação, limitada a documentos cujo `CD_USUARIO` corresponde ao login autenticado.
- Ambas exibem exclusivamente `TP_STATUS='FECHADO'` e objetos com `SN_ASSINATURA='S'`. Abertos, assinados, cancelados e documentos sem exigência de assinatura não aparecem.
- Nenhuma terceira aba foi criada, conforme a orientação recebida.

## Oracle

Foi acrescentada `SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.LISTA_PENDENCIAS(p_usuario,p_dt_ini,p_dt_fim,p_escopo,p_antes,p_limite,documentos OUT SYS_REFCURSOR)`.

`p_escopo` aceita `TODOS` ou `MEUS`. O backend obtém `p_usuario` exclusivamente da sessão autenticada, revalida o cadastro ativo e passa o escopo selecionado. Não aceita um nome de usuário do navegador para consultar a aba pessoal.

Filtragem, ordenação decrescente pelo código e paginação são executadas no Oracle. A procedure retorna no máximo 51 registros: 50 para exibição e um para identificar a próxima página. Não existe mais a varredura de até 10.000 registros em Python. O período continua limitado a 31 dias inclusivos.

As procedures `LISTA_DOCUMENTOS` e `ATUALIZA_PRESTADOR` foram preservadas. A nova consulta usa LEFT JOIN nos dados complementares para não ocultar uma pendência quando um nome associado não estiver disponível.

DDL original e proposto estão em `database/migrations/002_prepared/`. Os fragmentos adicionados estão em `database/migrations/002_lista_pendencias_spec.sql` e `002_lista_pendencias_body.sql`. O script de aplicação verifica se a fonte original mudou, compila e restaura a versão original em caso de falha.

## Limitações que permanecem

Listar uma pendência não executa sua transferência. As operações de atualização permanecem bloqueadas até a homologação das validações e auditoria. O aplicativo continua sem assinar documentos.

Sessões permanecem temporárias em memória: usar um único worker. Reiniciar a API exige novo login. A definição anterior de listagem exclusivamente pessoal e sem filtro de estado foi substituída por esta alteração.

## Validação

30 testes Python, 8 testes React, build TypeScript/Vite e 2 cenários de navegador passaram. Package e corpo ficaram VALID. As consultas geral e pessoal foram conferidas em transação Oracle somente leitura, sem exibir dados clínicos; nenhuma atualização de documento foi executada.
