-- PROPOSTA PARA VALIDACAO. Nao executada pelo diagnostico.
-- Afeta todos os anexos elegiveis da simulacao, nao apenas um documento.
-- A consulta real do PEP (SQL_ID 8h3n1nxq0k4xw) exige este indicador.
-- Nao altera usuarios, prestadores, assinaturas ou packages.
DECLARE
  v_banco VARCHAR2(128);
BEGIN
  v_banco := SYS_CONTEXT('USERENV','DB_NAME');
  IF LOWER(v_banco) <> 'smlmv' THEN
    RAISE_APPLICATION_ERROR(-20001,'Executar somente na simulacao smlmv');
  END IF;
  UPDATE usuario_banco.pw_tipo_documento
     SET sn_pendencias_alertas = 'S'
   WHERE cd_tipo_documento = 19
     AND sn_pendencias_alertas = 'N';
END;
/
-- Conferir o resultado antes de decidir COMMIT ou ROLLBACK.
SELECT cd_tipo_documento, ds_tipo_documento, sn_pendencias_alertas,
       dh_pendencias_alertas
FROM usuario_banco.pw_tipo_documento
WHERE cd_tipo_documento = 19;
