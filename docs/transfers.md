# Transferência na homologação smlmv

Atualização de 14/10/2026: as rotinas da migração 005 foram consolidadas na package existente pela migração 007, sem criar outra package. Foram testados 15 tipos: PRESCR, ENFERM, TRATMT, AFERIC, ALTMED, AVALIA, DIAEST, DIAENF, HISENF, RESENF, DOCELE, ANEXO, ANOENF, EVOMED e MEDICA. As regras abaixo sobre cobertura inicial da migração 004 foram substituídas por esta ampliação.

Os documentos solicitados 19701650 (Anexo Totem Termos) e 19701647 (Descrição Cirúrgica) passaram por transferência, auditoria, repetição e rollback. ARQUIVO_ATENDIMENTO.NM_USUARIO identifica quem anexou o arquivo, conforme comentário do schema; esse histórico permanece intacto. Um registro aberto no editor não é fechado nem assinado pela transferência: a condição de elegibilidade usa o documento clínico FECHADO e sem assinatura digital, preservando os vínculos e o estado do editor.

Exame físico (EXAFIS) e grupo de documentos (GRUDOC) não tiveram amostras fechadas encontradas e permanecem sem homologação. Urgências com prestador geral continuam bloqueadas porque podem alterar faturamento. Documentos assinados, sem necessidade de assinatura, sem origem identificável ou com vínculos inconsistentes não são liberados.

A migração 005 preserva as datas originais que triggers de sinais vitais, histórico e anotação recalculam durante updates. Os testes compararam os demais campos do documento e da origem, dados do atendimento, faturamento, movimentos de prestador, SNOMED e estado do editor. Nenhuma transferência de teste foi mantida.

As rotinas atuais estão em database/migrations/007_consolidated_transfers/current.pks.sql e current.pkb.sql. Os instaladores antigos estão desativados; os arquivos .backup são somente recuperação histórica, não fazem parte da instalação ativa. Não criar packages novas.


Transferências ativadas na configuração local após testes reais com rollback. O frontend permite selecionar um usuário ativo com prestador ativo e exige justificativa. O master ADMIN concede a permissão global na aba Usuários ativos, inclusive a si mesmo. Não há concessão automática de permissões aos usuários.

O backend chama SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.TRANSFERIR com o autor da sessão, o responsável visto na listagem e uma chave de idempotência. A package bloqueia documento/prescrição, revalida permissão e estado, sincroniza PRE_MED.NM_USUARIO/CD_PRESTADOR, chama a procedure fornecida SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.ATUALIZA_PRESTADOR e atualiza PW_DOCUMENTO_CLINICO.CD_USUARIO. O commit ocorre apenas depois da confirmação válida da package. Assim, o documento deixa o usuário anterior na consulta pessoal e passa para o destinatário.

Auditoria, atualização clínica e controle de repetição pertencem à mesma transação. São registrados nome e código do autor, origem e destino, documento, justificativa e data/hora. Uma falha de auditoria reverte a transferência. Uma requisição repetida com os mesmos dados retorna o evento original; responsável desatualizado ou reutilização de chave com outros dados gera conflito.

## Cobertura e restrições

A cobertura atual corresponde aos 15 tipos listados acima. As validações e restrições foram preservadas na consolidação. A liberação permanece restrita à base smlmv.

Nenhuma trigger MV foi desabilitada. A atualização fornecida foi preservada e chamada pela nova rotina. O teste real confirmou usuário/prestador na origem e no documento, auditoria, repetição, recusa por falta de permissão, conflito de responsável e rollback integral quando a inserção da auditoria falha. Os registros clínicos e permissões usados no teste voltaram ao estado anterior; sequências Oracle podem avançar mesmo com rollback. Não foi validada a interface do cliente MV com credenciais pessoais.

A consolidação foi validada por compilação Oracle, presença das cinco rotinas, ausência das packages de transferência antigas, 37 testes do backend e health ready. Nenhum documento clínico foi alterado nesta consolidação. A package de acesso existente permanece responsável pelo diretório, permissões e consulta da auditoria.
