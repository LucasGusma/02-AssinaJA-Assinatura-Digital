CREATE OR REPLACE PACKAGE BODY         PKG_GERENCIADOR_ASSINATURA AS

  -- LISTA DOS DOCUMENTOS
  PROCEDURE lista_documentos(p_usuario  IN pw_documento_clinico.cd_usuario%TYPE,
                             p_dt_ini   IN pw_documento_clinico.dh_criacao%TYPE,
                             p_dt_fim   IN pw_documento_clinico.dh_criacao%TYPE,
                             documentos OUT SYS_REFCURSOR) IS
  BEGIN
  
    OPEN documentos FOR
      SELECT dc.cd_documento_clinico,
             dc.cd_paciente,
             pac.nm_paciente,
             dc.cd_atendimento,
             dc.cd_usuario,
             usr.nm_usuario,
             dc.cd_prestador,
             pre.nm_prestador,
             dc.tp_status,
             dc.dh_criacao,
             obj.cd_objeto,
             obj.nm_objeto,
             obj.tp_objeto,
             obj.sn_assinatura
        FROM pw_documento_clinico dc
      
        JOIN paciente pac
          ON pac.cd_paciente = dc.cd_paciente
      
        JOIN usuario_banco.usuarios usr
          ON usr.cd_usuario = dc.cd_usuario
      
        JOIN prestador pre
          ON pre.cd_prestador = dc.cd_prestador
      
        JOIN pagu_objeto obj
          ON obj.cd_objeto = dc.cd_objeto
      
       WHERE obj.sn_assinatura = 'S'
         and dc.tp_status = 'FECHADO'
         AND usr.cd_usuario = p_usuario
         AND dc.dh_criacao BETWEEN p_dt_ini AND p_dt_fim;
  
  END lista_documentos;

  -- ATUALIZA O PRESTADOR NO DOCUMENTO CLÍNICO
  PROCEDURE atualiza_prestador(p_cd_documento_clinico IN pw_documento_clinico.cd_documento_clinico%TYPE,
                               p_cd_prestador         IN prestador.cd_prestador%TYPE) IS
  BEGIN
  
    IF p_cd_prestador IS NOT NULL THEN
    
      UPDATE usuario_banco.pw_documento_clinico
         SET cd_prestador = p_cd_prestador
       WHERE cd_documento_clinico = p_cd_documento_clinico;
    
    END IF;
  
  END atualiza_prestador;

  -- Read-only. Existing clinical update procedures are not called here.
  PROCEDURE lista_pendencias(p_usuario        IN pw_documento_clinico.cd_usuario%TYPE,
                             p_dt_ini         IN DATE,
                             p_dt_fim         IN DATE,
                             p_escopo         IN VARCHAR2,
                             p_antes          IN NUMBER,
                             p_limite         IN NUMBER,
                             documentos       OUT SYS_REFCURSOR,
                             p_prestador_nome IN VARCHAR2 DEFAULT NULL, p_tipo_documento IN NUMBER DEFAULT NULL) IS
  BEGIN
    IF p_usuario IS NULL OR p_escopo IS NULL OR
       p_escopo NOT IN ('TODOS', 'MEUS') THEN
      raise_application_error(-20001, 'Usuario e escopo obrigatorios.');
    END IF;
    IF p_dt_ini IS NULL OR p_dt_fim IS NULL OR
       TRUNC(p_dt_fim) < TRUNC(p_dt_ini) OR
       TRUNC(p_dt_ini) < ADD_MONTHS(TRUNC(p_dt_fim), -3) THEN
      raise_application_error(-20002, 'Periodo deve conter ate 3 meses.');
    END IF;
    IF p_limite IS NULL OR p_limite < 1 OR p_limite > 50 OR
       p_limite <> TRUNC(p_limite) OR
       (p_antes IS NOT NULL AND (p_antes < 1 OR p_antes <> TRUNC(p_antes))) THEN
      raise_application_error(-20003, 'Paginacao invalida.');
    END IF;
  
    OPEN documentos FOR
      SELECT *
        FROM (SELECT dc.cd_documento_clinico,
                     dc.cd_paciente,
                     pac.nm_paciente,
                     dc.cd_atendimento,
                     dc.cd_usuario,
                     usr.nm_usuario,
                     dc.cd_prestador,
                     pre.nm_prestador,
                     dc.tp_status,
                     dc.dh_criacao,
                     obj.cd_objeto,
                     obj.nm_objeto,
                     obj.tp_objeto,
                     obj.sn_assinatura
                FROM pw_documento_clinico dc
                JOIN pagu_objeto obj
                  ON obj.cd_objeto = dc.cd_objeto
                LEFT JOIN paciente pac
                  ON pac.cd_paciente = dc.cd_paciente
                LEFT JOIN usuario_banco.usuarios usr
                  ON usr.cd_usuario = dc.cd_usuario
                LEFT JOIN prestador pre
                  ON pre.cd_prestador = dc.cd_prestador
               WHERE dc.tp_status = 'FECHADO'
                 AND obj.sn_assinatura = 'S'
                 AND (p_escopo = 'TODOS' OR dc.cd_usuario = p_usuario)
                 AND dc.dh_criacao >= TRUNC(p_dt_ini)
                 AND dc.dh_criacao < TRUNC(p_dt_fim) + 1
                 AND (p_tipo_documento IS NULL OR dc.cd_objeto = p_tipo_documento) AND (p_antes IS NULL OR dc.cd_documento_clinico < p_antes)
                 AND (TRIM(p_prestador_nome) IS NULL OR
                     INSTR(TRANSLATE(UPPER(pre.nm_prestador),
                                      'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                                      'AAAAAEEEEIIIIOOOOOUUUUC'),
                            TRANSLATE(UPPER(TRIM(p_prestador_nome)),
                                      'ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ',
                                      'AAAAAEEEEIIIIOOOOOUUUUC')) > 0)
               ORDER BY dc.cd_documento_clinico DESC)
       WHERE ROWNUM <= p_limite + 1;
  END lista_pendencias;

  PROCEDURE validar_autor(p_autor VARCHAR2) IS
    n NUMBER;
  BEGIN
    SELECT COUNT(*)
      INTO n
      FROM DBASGU.USUARIOS u
      JOIN APP_SCHEMA.AJA_PERMISSAO a
        ON a.CD_USUARIO = u.CD_USUARIO
     WHERE u.CD_USUARIO = p_autor
       AND u.SN_ATIVO = 'S'
       AND a.SN_TRANSFERIR = 'S';
    IF n <> 1 THEN
      RAISE_APPLICATION_ERROR(-20010, 'Sem permissao de transferencia');
    END IF;
  END;
  PROCEDURE mapa(p_tipo VARCHAR2,
                 t      OUT VARCHAR2,
                 u      OUT VARCHAR2,
                 p      OUT VARCHAR2) IS
  BEGIN
    CASE p_tipo
      WHEN 'PRESCR' THEN
        t := 'PRE_MED';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'ENFERM' THEN
        t := 'PRE_MED';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'ANEXO' THEN
        t := 'ARQUIVO_ATENDIMENTO';
        u := NULL;
        p := NULL; -- NM_USUARIO records the uploader, not the current responsible user.
      WHEN 'ANOENF' THEN
        t := 'EVO_ENF';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'EVOMED' THEN
        t := 'PRE_MED';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'MEDICA' THEN
        t := 'PRE_MED';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'TRATMT' THEN
        t := 'PRE_MED';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'AFERIC' THEN
        t := 'COLETA_SINAL_VITAL';
        u := 'NM_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'ALTMED' THEN
        t := 'PW_REGISTRO_ALTA';
        u := 'CD_USUARIO';
        p := 'CD_PRESTADOR';
      WHEN 'AVALIA' THEN
        t := 'PAGU_AVALIACAO';
        u := 'NM_USUARIO';
        p := NULL;
      WHEN 'DIAEST' THEN
        t := 'DIAGNOSTICO_ATENDIME';
        u := 'NM_USUARIO';
        p := NULL;
      WHEN 'DIAENF' THEN
        t := 'SAE_DIAGNOSTICO_REALIZADO';
        u := NULL;
        p := 'CD_PRESTADOR';
      WHEN 'HISENF' THEN
        t := 'SAE_HISTORICO_ENFERMAGEM';
        u := NULL;
        p := 'CD_PRESTADOR';
      WHEN 'RESENF' THEN
        t := 'PW_SAE_RESULTADO_ENFERMG_RLZD';
        u := NULL;
        p := 'CD_PRESTADOR';
      WHEN 'DOCELE' THEN
        t := 'PW_EDITOR_CLINICO';
        u := NULL;
        p := NULL;
      ELSE
        t := NULL;
        u := NULL;
        p := NULL;
    END CASE;
  END;
  FUNCTION bloqueio(p_documento NUMBER) RETURN VARCHAR2 IS
    d          USUARIO_BANCO.PW_DOCUMENTO_CLINICO%ROWTYPE;
    assinatura VARCHAR2(1);
    tipo       VARCHAR2(30);
    t          VARCHAR2(40);
    u          VARCHAR2(40);
    p          VARCHAR2(40);
    n          NUMBER;
    ruins      NUMBER;
  BEGIN
    SELECT *
      INTO d
      FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO
     WHERE CD_DOCUMENTO_CLINICO = p_documento;
    IF d.TP_STATUS IS NULL OR d.TP_STATUS <> 'FECHADO' OR
       d.CD_DOCUMENTO_DIGITAL IS NOT NULL THEN
      RETURN 'Somente documentos fechados e sem assinatura digital podem ser transferidos.';
    END IF;
    IF d.CD_USUARIO IS NULL OR d.CD_PRESTADOR IS NULL THEN
      RETURN 'Responsavel atual nao identificado.';
    END IF;
    SELECT SN_ASSINATURA, TP_OBJETO
      INTO assinatura, tipo
      FROM USUARIO_BANCO.PAGU_OBJETO
     WHERE CD_OBJETO = d.CD_OBJETO;
    IF assinatura IS NULL OR assinatura <> 'S' THEN
      RETURN 'Documento nao exige assinatura.';
    END IF;
    mapa(tipo, t, u, p);
    IF t IS NULL THEN
      RETURN 'Tipo sem amostra homologada para transferencia.';
    END IF;
    SELECT COUNT(*)
      INTO n
      FROM USUARIO_BANCO.ATENDIME a
      JOIN USUARIO_BANCO.CONFIG_PAEU cfg
        ON cfg.CD_MULTI_EMPRESA = a.CD_MULTI_EMPRESA
     WHERE a.CD_ATENDIMENTO = d.CD_ATENDIMENTO
       AND a.TP_ATENDIMENTO = 'U'
       AND a.CD_PRESTADOR = cfg.CD_PRESTADOR_GERAL;
    IF n > 0 THEN
      RETURN 'Atendimento de urgencia com prestador geral: a trigger MV pode alterar faturamento.';
    END IF;
    EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM USUARIO_BANCO.' || t ||
                      ' WHERE CD_DOCUMENTO_CLINICO=:1'
      INTO n
      USING p_documento;
    IF n = 0 OR (tipo <> 'DOCELE' AND n <> 1) THEN
      RETURN 'Origem do documento nao identificada de forma unica.';
    END IF;
    IF u IS NOT NULL THEN
      EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM USUARIO_BANCO.' || t ||
                        ' WHERE CD_DOCUMENTO_CLINICO=:1 AND DECODE(' || u ||
                        ',:2,0,1)=1'
        INTO ruins
        USING p_documento, d.CD_USUARIO;
      IF ruins > 0 THEN
        RETURN 'Usuario da origem diverge do documento; revisar no MV.';
      END IF;
    END IF;
    IF p IS NOT NULL THEN
      EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM USUARIO_BANCO.' || t ||
                        ' WHERE CD_DOCUMENTO_CLINICO=:1 AND DECODE(' || p ||
                        ',:2,0,1)=1'
        INTO ruins
        USING p_documento, d.CD_PRESTADOR;
      IF ruins > 0 THEN
        RETURN 'Prestador da origem diverge do documento; revisar no MV.';
      END IF;
    END IF;
    IF tipo <> 'DOCELE' THEN
      EXECUTE IMMEDIATE 'SELECT COUNT(*) FROM USUARIO_BANCO.' || t ||
                        ' WHERE CD_DOCUMENTO_CLINICO=:1 AND DECODE(CD_ATENDIMENTO,:2,0,1)=1'
        INTO ruins
        USING p_documento, d.CD_ATENDIMENTO;
      IF ruins > 0 THEN
        RETURN 'Atendimento da origem diverge do documento; revisar no MV.';
      END IF;
    END IF;
    IF tipo = 'DOCELE' THEN
      SELECT COUNT(*)
        INTO ruins
        FROM USUARIO_BANCO.PW_EDITOR_CLINICO e
        LEFT JOIN USUARIO_BANCO.EDITOR_REGISTRO r
          ON r.CD_REGISTRO = e.CD_EDITOR_REGISTRO
       WHERE e.CD_DOCUMENTO_CLINICO = p_documento
         AND r.CD_REGISTRO IS NULL;
      IF ruins > 0 THEN
        RETURN 'Vinculo do documento com o editor inexistente.';
      END IF;
    END IF;
    RETURN NULL;
  EXCEPTION
    WHEN NO_DATA_FOUND OR TOO_MANY_ROWS THEN
      RETURN 'Origem do documento nao identificada de forma unica.';
  END;
  PROCEDURE sincronizar(p_documento NUMBER,
                        p_destino   VARCHAR2,
                        p_prestador NUMBER) IS
    tipo    VARCHAR2(30);
    t       VARCHAR2(40);
    u       VARCHAR2(40);
    p       VARCHAR2(40);
    comando VARCHAR2(500);
    linhas  SYS_REFCURSOR;
    rid     VARCHAR2(100);
  BEGIN
    SELECT o.TP_OBJETO
      INTO tipo
      FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO d
      JOIN USUARIO_BANCO.PAGU_OBJETO o
        ON o.CD_OBJETO = d.CD_OBJETO
     WHERE d.CD_DOCUMENTO_CLINICO = p_documento;
    mapa(tipo, t, u, p);
    IF t IS NULL THEN
      RAISE_APPLICATION_ERROR(-20011, 'Origem sem homologacao');
    END IF;
    OPEN linhas FOR 'SELECT ROWIDTOCHAR(ROWID) FROM USUARIO_BANCO.' || t || ' WHERE CD_DOCUMENTO_CLINICO=:1 FOR UPDATE WAIT 5'
      USING p_documento;
    LOOP
      FETCH linhas
        INTO rid;
      EXIT WHEN linhas%NOTFOUND;
    END LOOP;
    CLOSE linhas;
    IF bloqueio(p_documento) IS NOT NULL THEN
      RAISE_APPLICATION_ERROR(-20011, 'Origem mudou; atualize a consulta');
    END IF;
    IF u IS NOT NULL AND p IS NOT NULL THEN
      comando := 'UPDATE USUARIO_BANCO.' || t || ' SET ' || u || '=:1,' || p ||
                 '=:2 WHERE CD_DOCUMENTO_CLINICO=:3';
      EXECUTE IMMEDIATE comando
        USING p_destino, p_prestador, p_documento;
    ELSIF u IS NOT NULL THEN
      EXECUTE IMMEDIATE 'UPDATE USUARIO_BANCO.' || t || ' SET ' || u ||
                        '=:1 WHERE CD_DOCUMENTO_CLINICO=:2'
        USING p_destino, p_documento;
    ELSIF p IS NOT NULL THEN
      EXECUTE IMMEDIATE 'UPDATE USUARIO_BANCO.' || t || ' SET ' || p ||
                        '=:1 WHERE CD_DOCUMENTO_CLINICO=:2'
        USING p_prestador, p_documento;
    END IF;
  END;
  PROCEDURE destinatarios(p_autor     VARCHAR2,
                          p_documento NUMBER,
                          p_busca     VARCHAR2,
                          resultado   OUT SYS_REFCURSOR) IS
    motivo VARCHAR2(1000);
  BEGIN
    validar_autor(p_autor);
    motivo := bloqueio(p_documento);
    IF motivo IS NOT NULL THEN
      RAISE_APPLICATION_ERROR(-20011, motivo);
    END IF;
    OPEN resultado FOR
      SELECT *
        FROM (SELECT u.CD_USUARIO, u.NM_USUARIO, t.NM_TIP_PRESTA
                FROM DBASGU.USUARIOS u
                JOIN USUARIO_BANCO.PRESTADOR p
                  ON p.CD_PRESTADOR = u.CD_PRESTADOR
                LEFT JOIN USUARIO_BANCO.TIP_PRESTA t
                  ON t.CD_TIP_PRESTA = p.CD_TIP_PRESTA
               WHERE u.SN_ATIVO = 'S'
                 AND p.TP_SITUACAO = 'A'
                 AND u.CD_USUARIO <>
                     (SELECT CD_USUARIO
                        FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO
                       WHERE CD_DOCUMENTO_CLINICO = p_documento)
                 AND (p_busca IS NULL OR
                     INSTR(UPPER(u.CD_USUARIO), UPPER(p_busca)) > 0 OR
                     INSTR(UPPER(u.NM_USUARIO), UPPER(p_busca)) > 0)
               ORDER BY u.NM_USUARIO, u.CD_USUARIO)
       WHERE ROWNUM <= 50;
  END;
  PROCEDURE transferir(p_autor     VARCHAR2,
                       p_documento NUMBER,
                       p_origem    VARCHAR2,
                       p_destino   VARCHAR2,
                       p_motivo    VARCHAR2,
                       p_chave     VARCHAR2,
                       p_request   VARCHAR2,
                       p_evento    OUT NUMBER) IS
    d                  USUARIO_BANCO.PW_DOCUMENTO_CLINICO%ROWTYPE;
    depois             USUARIO_BANCO.PW_DOCUMENTO_CLINICO%ROWTYPE;
    snomed_antes       NUMBER;
    snomed_depois      NUMBER;
    atendimento_antes  NUMBER;
    atendimento_depois NUMBER;
    anterior           APP_SCHEMA.AJA_TRANSFERENCIA%ROWTYPE;
    prestador          NUMBER;
    autor_nome         VARCHAR2(400);
    origem_nome        VARCHAR2(400);
    destino_nome       VARCHAR2(400);
    permissao          CHAR(1);
    mensagem           VARCHAR2(1000);
    ver_usuario        VARCHAR2(128);
    ver_prestador      NUMBER;
  BEGIN
    SAVEPOINT aja_transferencia;
    IF SYS_CONTEXT('USERENV', 'DB_NAME') <> 'smlmv' THEN
      RAISE_APPLICATION_ERROR(-20011,
                              'Rotina homologada exclusivamente na base smlmv');
    END IF;
    validar_autor(p_autor);
    SELECT SN_TRANSFERIR
      INTO permissao
      FROM APP_SCHEMA.AJA_PERMISSAO
     WHERE CD_USUARIO = p_autor
       FOR UPDATE WAIT 5;
    validar_autor(p_autor);
    IF p_chave IS NULL OR NOT
        REGEXP_LIKE(p_chave,
                                       '^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$') OR
       p_origem IS NULL OR p_destino IS NULL OR LENGTH(TRIM(p_motivo)) < 10 OR
       p_motivo IS NULL OR LENGTH(p_motivo) > 1000 THEN
      RAISE_APPLICATION_ERROR(-20012, 'Dados de transferencia invalidos');
    END IF;
    BEGIN
      SELECT *
        INTO anterior
        FROM APP_SCHEMA.AJA_TRANSFERENCIA
       WHERE CHAVE = p_chave;
      IF anterior.CD_AUTOR <> p_autor OR
         anterior.CD_DOCUMENTO <> p_documento OR
         anterior.CD_ORIGEM <> p_origem OR anterior.CD_DESTINO <> p_destino OR
         anterior.MOTIVO <> p_motivo THEN
        RAISE_APPLICATION_ERROR(-20013,
                                'Chave reutilizada para outra transferencia');
      END IF;
      p_evento := anterior.ID_AUDITORIA;
      RETURN;
    EXCEPTION
      WHEN NO_DATA_FOUND THEN
        NULL;
    END;
    SELECT *
      INTO d
      FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO
     WHERE CD_DOCUMENTO_CLINICO = p_documento
       FOR UPDATE WAIT 5;
    IF d.CD_USUARIO <> p_origem OR d.CD_USUARIO IS NULL THEN
      RAISE_APPLICATION_ERROR(-20013,
                              'Responsavel mudou; atualize a consulta');
    END IF;
    IF p_destino = p_origem THEN
      RAISE_APPLICATION_ERROR(-20012, 'Destinatario ja responsavel');
    END IF;
    SELECT CD_PRESTADOR
      INTO atendimento_antes
      FROM USUARIO_BANCO.ATENDIME
     WHERE CD_ATENDIMENTO = d.CD_ATENDIMENTO
       FOR UPDATE WAIT 5;
    mensagem := bloqueio(p_documento);
    IF mensagem IS NOT NULL THEN
      RAISE_APPLICATION_ERROR(-20011, mensagem);
    END IF;
    SELECT u.NM_USUARIO, p.CD_PRESTADOR
      INTO destino_nome, prestador
      FROM DBASGU.USUARIOS u
      JOIN USUARIO_BANCO.PRESTADOR p
        ON p.CD_PRESTADOR = u.CD_PRESTADOR
     WHERE u.CD_USUARIO = p_destino
       AND u.SN_ATIVO = 'S'
       AND p.TP_SITUACAO = 'A';
    SELECT NM_USUARIO
      INTO autor_nome
      FROM DBASGU.USUARIOS
     WHERE CD_USUARIO = p_autor
       AND SN_ATIVO = 'S';
    SELECT NM_USUARIO
      INTO origem_nome
      FROM DBASGU.USUARIOS
     WHERE CD_USUARIO = p_origem;
    SELECT APP_SCHEMA.AJA_AUDITORIA_SEQ.NEXTVAL INTO p_evento FROM DUAL;
    INSERT INTO APP_SCHEMA.AJA_TRANSFERENCIA
    VALUES
      (p_chave,
       p_autor,
       p_documento,
       p_origem,
       p_destino,
       p_motivo,
       p_evento);
    SELECT COUNT(*)
      INTO snomed_antes
      FROM USUARIO_BANCO.SNOMEDCT_PACIENTE
     WHERE CD_DOCUMENTO_CLINICO = p_documento;
    sincronizar(p_documento, p_destino, prestador);
    SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA.ATUALIZA_PRESTADOR(p_documento,
                                                          prestador);
    UPDATE USUARIO_BANCO.PW_DOCUMENTO_CLINICO
       SET CD_USUARIO    = p_destino,
           DH_REFERENCIA = d.DH_REFERENCIA,
           DH_CRIACAO    = d.DH_CRIACAO,
           DH_FECHAMENTO = d.DH_FECHAMENTO,
           DH_IMPRESSO   = d.DH_IMPRESSO
     WHERE CD_DOCUMENTO_CLINICO = p_documento
       AND TP_STATUS = 'FECHADO'
       AND CD_USUARIO = p_origem;
    IF SQL%ROWCOUNT <> 1 THEN
      RAISE_APPLICATION_ERROR(-20013,
                              'Documento alterado durante transferencia');
    END IF;
    SELECT CD_USUARIO, CD_PRESTADOR
      INTO ver_usuario, ver_prestador
      FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO
     WHERE CD_DOCUMENTO_CLINICO = p_documento;
    IF ver_usuario <> p_destino OR ver_prestador <> prestador OR
       bloqueio(p_documento) IS NOT NULL THEN
      RAISE_APPLICATION_ERROR(-20013,
                              'Falha na consistencia apos transferencia');
    END IF;
    SELECT *
      INTO depois
      FROM USUARIO_BANCO.PW_DOCUMENTO_CLINICO
     WHERE CD_DOCUMENTO_CLINICO = p_documento;
    SELECT COUNT(*)
      INTO snomed_depois
      FROM USUARIO_BANCO.SNOMEDCT_PACIENTE
     WHERE CD_DOCUMENTO_CLINICO = p_documento;
    SELECT CD_PRESTADOR
      INTO atendimento_depois
      FROM USUARIO_BANCO.ATENDIME
     WHERE CD_ATENDIMENTO = d.CD_ATENDIMENTO;
    SELECT CASE
             WHEN DECODE(atendimento_antes, atendimento_depois, 0, 1) = 1 OR
                  snomed_antes <> snomed_depois OR
                  depois.TP_STATUS <> d.TP_STATUS OR
                  DECODE(depois.DH_CRIACAO, d.DH_CRIACAO, 0, 1) = 1 OR
                  DECODE(depois.DH_FECHAMENTO, d.DH_FECHAMENTO, 0, 1) = 1 OR
                  DECODE(depois.DH_REFERENCIA, d.DH_REFERENCIA, 0, 1) = 1 OR
                  DECODE(depois.CD_ATENDIMENTO, d.CD_ATENDIMENTO, 0, 1) = 1 OR
                  DECODE(depois.CD_PACIENTE, d.CD_PACIENTE, 0, 1) = 1 THEN
              1
             ELSE
              0
           END
      INTO snomed_depois
      FROM DUAL;
    IF snomed_depois = 1 THEN
      RAISE_APPLICATION_ERROR(-20011,
                              'Trigger alterou dados alem da responsabilidade; transferencia revertida');
    END IF;
    INSERT INTO APP_SCHEMA.AJA_AUDITORIA
      (ID,
       CD_AUTOR,
       NM_AUTOR,
       ACAO,
       DETALHE,
       CD_DOCUMENTO,
       CD_ORIGEM,
       NM_ORIGEM,
       CD_DESTINO,
       NM_DESTINO,
       REQUEST_ID)
    VALUES
      (p_evento,
       p_autor,
       autor_nome,
       'TRANSFERENCIA',
       p_motivo,
       p_documento,
       p_origem,
       origem_nome,
       p_destino,
       destino_nome,
       p_request);
  EXCEPTION
    WHEN OTHERS THEN
      ROLLBACK TO aja_transferencia;
      RAISE;
  END;


 PROCEDURE tipos_documento(resultado OUT SYS_REFCURSOR) IS BEGIN
  OPEN resultado FOR SELECT cd_objeto,nm_objeto FROM pagu_objeto WHERE sn_assinatura='S' ORDER BY UPPER(nm_objeto),cd_objeto;
 END;
 PROCEDURE resumo_pendencias(p_usuario VARCHAR2,p_escopo VARCHAR2,resultado OUT SYS_REFCURSOR) IS BEGIN
  IF p_usuario IS NULL OR p_escopo IS NULL OR p_escopo NOT IN ('TODOS','MEUS') THEN
   raise_application_error(-20001,'Usuario e escopo obrigatorios.');
  END IF;
  OPEN resultado FOR SELECT COUNT(*) total, ADD_MONTHS(TRUNC(SYSDATE),-3) inicio,TRUNC(SYSDATE) fim
   FROM pw_documento_clinico dc JOIN pagu_objeto obj ON obj.cd_objeto=dc.cd_objeto
   WHERE dc.tp_status='FECHADO' AND obj.sn_assinatura='S'
   AND dc.dh_criacao>=ADD_MONTHS(TRUNC(SYSDATE),-3) AND dc.dh_criacao<TRUNC(SYSDATE)+1
   AND (p_escopo='TODOS' OR dc.cd_usuario=p_usuario);
 END;

END PKG_GERENCIADOR_ASSINATURA;
/
