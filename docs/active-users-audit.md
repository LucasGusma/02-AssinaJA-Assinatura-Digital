# Usuários ativos e auditoria — 09/10/2026

A terceira aba é Usuários ativos; a quarta é Auditoria. Ambas são acessíveis a usuários autenticados e ativos. O Oracle define o master exclusivamente como ADMIN. Apenas ele pode alterar a permissão global de transferência, independentemente do setor. Os controles dos demais usuários são somente leitura; API e package também impedem alterações.

`database/migrations/003_access.sql` instala objetos próprios em APP_SCHEMA: AJA_PERMISSAO, AJA_AUDITORIA, sequência e PKG_ASSINAJA_ACESSO. Não altera tabelas clínicas nem substitui a package de documentos. `scripts/install_access.py` recusa sobrescrever uma instalação existente. DDL Oracle não é transacional: em falha, os objetos precisam ser inspecionados antes de repetir a instalação.

O diretório lê usuários ativos de DBASGU.USUARIOS e vínculos de setores ativos do MV. Inclui o grupo Sem setor ativo vinculado. Ordena pelo tipo de prestador (TIP_PRESTA.NM_TIP_PRESTA) e pelo nome; esse cadastro não fornece uma hierarquia de cargos. A busca por nome ou F0 funciona dentro do setor selecionado, ignorando acentos e maiúsculas. Um usuário com múltiplos vínculos aparece em todos os setores correspondentes, com a mesma permissão.

Mudanças de permissão e seus eventos são gravados na mesma transação; falhas geram rollback. Os eventos preservam nome e código do autor e do destinatário, estado anterior/novo, data/hora e identificador da requisição. A aba pagina o histórico inteiro, sem corte por período. A estrutura também contém documento, origem e destino para futura integração de transferência. Não recupera eventos anteriores à instalação nem mudanças feitas diretamente no MV.

## Transferência ainda não habilitada

A procedure fornecida atualiza apenas PW_DOCUMENTO_CLINICO.CD_PRESTADOR. Ela não muda CD_USUARIO, usado atualmente em Meus documentos, nem garante atualização das tabelas de origem. Os comentários do esquema exigem correspondência com essas tabelas; a trigger TRG_ATUALIZA_PREST_ATENDIME pode também afetar atendimento/faturamento. Por isso TRANSFERS_ENABLED permanece falso e nenhuma transferência clínica foi executada.

A próxima rotina de transferência precisa validar autor ativo e permissão; bloquear e revalidar documento fechado, pendente de assinatura; resolver o destinatário ativo e seu prestador; aplicar a operação suportada para o módulo de origem e o documento; registrar origem/destino com nomes e códigos, motivo, data/hora e autor; e confirmar tudo em uma única transação. Precisa também tratar repetição da requisição sem duplicar a operação. Apenas trocar CD_PRESTADOR não satisfaz o requisito de mover entre usuários MV.

Validação real: `scripts/verify_access.py` compara a cobertura do diretório com todos os usuários ativos, verifica recusa para não master e testa mudança de permissão com auditoria, revertendo ambas com rollback. Não imprime usuários nem altera documentos clínicos.
