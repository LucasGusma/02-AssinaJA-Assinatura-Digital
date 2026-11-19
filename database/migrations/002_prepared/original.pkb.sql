CREATE OR REPLACE PACKAGE BODY SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA AS

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

END pkg_gerenciador_assinatura;
