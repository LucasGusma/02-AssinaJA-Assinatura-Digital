-- Diagnostico somente leitura. Executar na conexao usada pelo PEP de simulacao.
-- Nao preenche empresa nem altera responsabilidades.
SELECT SYS_CONTEXT('USERENV','DB_NAME') banco,
       SYS_CONTEXT('USERENV','SERVICE_NAME') servico,
       SYS_CONTEXT('USERENV','SERVER_HOST') servidor
FROM dual;

SELECT dc.cd_documento_clinico, dc.cd_usuario, dc.cd_prestador,
       dc.tp_status, dc.cd_objeto, dc.cd_tipo_documento,
       dc.cd_documento_digital, dc.cd_multi_empresa empresa_documento,
       a.cd_multi_empresa empresa_atendimento,
       obj.sn_assinatura, t.sn_assinatura_digital, t.sn_ativo
FROM usuario_banco.pw_documento_clinico dc
LEFT JOIN usuario_banco.atendime a ON a.cd_atendimento=dc.cd_atendimento
LEFT JOIN usuario_banco.pagu_objeto obj ON obj.cd_objeto=dc.cd_objeto
LEFT JOIN usuario_banco.pw_tipo_documento t ON t.cd_tipo_documento=dc.cd_tipo_documento
WHERE dc.cd_documento_clinico=19701655;

SELECT u.cd_usuario,u.cd_prestador,u.sn_ativo,p.tp_situacao,p.cd_tip_presta
FROM dbasgu.usuarios u
LEFT JOIN usuario_banco.prestador p ON p.cd_prestador=u.cd_prestador
WHERE u.cd_usuario='ADMIN';

-- Solicitar ao DBA a consulta e os binds usados pela tela Pendencias de Assinatura.
-- Comparar banco/servico, usuario, prestador, empresa, datas e criterios de assinatura.
-- O usuario da aplicacao nao possui acesso a V$SQL para capturar essa consulta.
