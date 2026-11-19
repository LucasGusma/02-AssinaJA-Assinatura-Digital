-- Diagnostico SOMENTE LEITURA para o DBA/responsavel pelo MV.
-- Executar na conexao efetiva do PEP de simulacao e na do PEP de producao.
-- Nao cria packages, nao transfere documentos e nao altera configuracoes.
-- Compartilhar os resultados sem senhas, tokens ou dados de pacientes.

SELECT SYS_CONTEXT('USERENV','DB_NAME') banco,
       SYS_CONTEXT('USERENV','SERVICE_NAME') servico,
       SYS_CONTEXT('USERENV','SERVER_HOST') servidor,
       SYS_CONTEXT('USERENV','CURRENT_SCHEMA') esquema
FROM dual;

SELECT cd_configuracao_assinat_digit, cd_multi_empresa,
       sn_assinatura_digital, sn_pendencia_assinatura
FROM usuario_banco.configuracao_assinatura_digit
ORDER BY cd_multi_empresa;

SELECT cd_multi_empresa, sn_assinatura_digital
FROM usuario_banco.pw_configuracao_assinat_digit
ORDER BY cd_multi_empresa;

SELECT cd_configuracao_assinat_digit, cd_tipo_documento, dt_inicio, sn_ativo
FROM usuario_banco.excecao_config_assin_digit
ORDER BY cd_configuracao_assinat_digit, cd_tipo_documento;

-- Preencher :usuario_destino com o usuario utilizado no teste atual.
SELECT u.cd_usuario, u.cd_prestador, u.sn_ativo, p.tp_situacao,
       p.cd_tip_presta
FROM dbasgu.usuarios u
LEFT JOIN usuario_banco.prestador p ON p.cd_prestador=u.cd_prestador
WHERE u.cd_usuario=UPPER(:usuario_destino);

-- Contagem segundo os criterios basicos do AssinaJA, nao a consulta do PEP.
SELECT dc.cd_tipo_documento, dc.cd_objeto,
       dc.cd_multi_empresa empresa_documento,
       a.cd_multi_empresa empresa_atendimento, COUNT(*) quantidade
FROM usuario_banco.pw_documento_clinico dc
JOIN usuario_banco.pagu_objeto o ON o.cd_objeto=dc.cd_objeto
LEFT JOIN usuario_banco.atendime a ON a.cd_atendimento=dc.cd_atendimento
WHERE dc.cd_usuario=UPPER(:usuario_destino)
  AND dc.tp_status='FECHADO'
  AND dc.cd_documento_digital IS NULL
  AND o.sn_assinatura='S'
  AND dc.dh_criacao >= ADD_MONTHS(TRUNC(SYSDATE),-3)
  AND dc.dh_criacao < TRUNC(SYSDATE)+1
GROUP BY dc.cd_tipo_documento, dc.cd_objeto,
         dc.cd_multi_empresa, a.cd_multi_empresa;

-- Completar a comparacao com a consulta SQL e os parametros reais da tela
-- Pendencias de Assinatura, capturados pelo DBA durante uma consulta no PEP.
-- Comparar usuario/prestador, empresa, datas, status, origem e assinatura.
-- Nao inferir a conexao Oracle pelo endereco HTTP do navegador.
