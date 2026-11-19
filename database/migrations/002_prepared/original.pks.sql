CREATE OR REPLACE PACKAGE SCHEMA_HOSPITAL.PKG_GERENCIADOR_ASSINATURA AS

    PROCEDURE lista_documentos(
        p_usuario  IN pw_documento_clinico.cd_usuario%TYPE,
        p_dt_ini   IN pw_documento_clinico.dh_criacao%TYPE,
        p_dt_fim   IN pw_documento_clinico.dh_criacao%TYPE,
        documentos OUT SYS_REFCURSOR
    );

    PROCEDURE atualiza_prestador(
        p_cd_documento_clinico IN pw_documento_clinico.cd_documento_clinico%TYPE,
        p_cd_prestador         IN prestador.cd_prestador%TYPE
    );

END PKG_GERENCIADOR_ASSINATURA;
