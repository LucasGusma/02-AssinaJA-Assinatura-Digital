# Validação da implementação — 08/10/2026

Validação local, sem conexão ao servidor Oracle e sem alteração dos dados MV.

| Verificação | Resultado |
|---|---|
| API FastAPI e adaptador Oracle, com doubles de teste | 19 testes |
| Componentes React em DOM de teste | 6 testes |
| Aplicação compilada em Edge headless | 2 cenários |
| Testes Python preservados da versão anterior | 22 testes |
| Navegação JavaScript legada | Cenários de paginação e pesquisa |
| TypeScript e build Vite | Build de produção gerado |
| Ruff | Sem violações |
| Auditoria npm | Zero vulnerabilidades reportadas após atualização do Vitest |
| Oracle Instant Client local | Thick carregado, versão 23.8.0.25.4; nenhuma conexão aberta |

Os cenários de navegador cobrem a tela inicial real com FastAPI em estado pendente, layout desktop/celular e painel/detalhes/acessos/logout com respostas fictícias interceptadas apenas pelo teste. Capturas locais ficam em `frontend/test-results/` e são regeneradas pelo Playwright. Os testes de navegador usam Microsoft Edge instalado na máquina.

Proteções verificadas incluem origem/CSRF, limite de corpo, não exposição de credenciais em erros, cookie HttpOnly, revogação de sessão, bloqueio de administração para não master, autorização do conteúdo/PDF, desativação de transferência, passagem da chave de idempotência, rejeição de resposta inválida antes de commit e rollback de erros de negócio.

Os testes não comprovam a futura implementação das regras na package. Ainda dependem do banco: autenticação institucional, grants, sessões persistidas, contadores distribuídos, transações reais, idempotência, migração do SQLite e efeitos da transferência no MV.

O ambiente emitiu aviso de depreciação do cliente httpx usado pelo TestClient do Starlette; os testes passaram. A migração do cliente de testes pode ser feita junto de uma futura atualização controlada das dependências.
