CREATE OR REPLACE PACKAGE BODY         PKG_GERENCIADOR_ASSINATURA AS

    -- LISTA DOS DOCUMENTOS
    PROCEDURE lista_documentos(
        p_usuario  IN pw_documento_clinico.cd_usuario%TYPE,
        p_dt_ini   IN pw_documento_clinico.dh_criacao%TYPE,
        p_dt_fim   IN pw_documento_clinico.dh_criacao%TYPE,
        documentos OUT SYS_REFCURSOR
    ) IS
    BEGIN

        OPEN documentos FOR
            SELECT
                dc.cd_documento_clinico,
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
    PROCEDURE atualiza_prestador(
        p_cd_documento_clinico IN pw_documento_clinico.cd_documento_clinico%TYPE,
        p_cd_prestador         IN prestador.cd_prestador%TYPE
    ) IS
    BEGIN

        IF p_cd_prestador IS NOT NULL THEN

            UPDATE usuario_banco.pw_documento_clinico
               SET cd_prestador = p_cd_prestador
             WHERE cd_documento_clinico = p_cd_documento_clinico;

        END IF;

    END atualiza_prestador;

    -- Read-only. Existing clinical update procedures are not called here.
    PROCEDURE lista_pendencias(
        p_usuario IN pw_documento_clinico.cd_usuario%TYPE,
        p_dt_ini IN DATE,
        p_dt_fim IN DATE,
        p_escopo IN VARCHAR2,
        p_antes IN NUMBER,
        p_limite IN NUMBER,
        documentos OUT SYS_REFCURSOR
    ) IS
    BEGIN
        IF p_usuario IS NULL OR p_escopo IS NULL OR p_escopo NOT IN ('TODOS', 'MEUS') THEN
            raise_application_error(-20001, 'Usuario e escopo obrigatorios.');
        END IF;
        IF p_dt_ini IS NULL OR p_dt_fim IS NULL OR TRUNC(p_dt_fim) < TRUNC(p_dt_ini)
           OR TRUNC(p_dt_fim) - TRUNC(p_dt_ini) > 30 THEN
            raise_application_error(-20002, 'Periodo deve conter ate 31 dias.');
        END IF;
        IF p_limite IS NULL OR p_limite < 1 OR p_limite > 50 OR p_limite <> TRUNC(p_limite)
           OR (p_antes IS NOT NULL AND (p_antes < 1 OR p_antes <> TRUNC(p_antes))) THEN
            raise_application_error(-20003, 'Paginacao invalida.');
        END IF;

        OPEN documentos FOR
            SELECT * FROM (
                SELECT dc.cd_documento_clinico, dc.cd_paciente, pac.nm_paciente,
                       dc.cd_atendimento, dc.cd_usuario, usr.nm_usuario,
                       dc.cd_prestador, pre.nm_prestador, dc.tp_status, dc.dh_criacao,
                       obj.cd_objeto, obj.nm_objeto, obj.tp_objeto, obj.sn_assinatura
                  FROM pw_documento_clinico dc
                  JOIN pagu_objeto obj ON obj.cd_objeto = dc.cd_objeto
                  LEFT JOIN paciente pac ON pac.cd_paciente = dc.cd_paciente
                  LEFT JOIN usuario_banco.usuarios usr ON usr.cd_usuario = dc.cd_usuario
                  LEFT JOIN prestador pre ON pre.cd_prestador = dc.cd_prestador
                 WHERE dc.tp_status = 'FECHADO'
                   AND obj.sn_assinatura = 'S'
                   AND (p_escopo = 'TODOS' OR dc.cd_usuario = p_usuario)
                   AND dc.dh_criacao >= TRUNC(p_dt_ini)
                   AND dc.dh_criacao < TRUNC(p_dt_fim) + 1
                   AND (p_antes IS NULL OR dc.cd_documento_clinico < p_antes)
                 ORDER BY dc.cd_documento_clinico DESC
            ) WHERE ROWNUM <= p_limite + 1;
    END lista_pendencias;

END pkg_gerenciador_assinatura;
