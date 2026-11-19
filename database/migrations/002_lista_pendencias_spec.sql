    -- AssinaJA: authenticated global and personal pending-document views.
    PROCEDURE lista_pendencias(
        p_usuario IN pw_documento_clinico.cd_usuario%TYPE,
        p_dt_ini IN DATE,
        p_dt_fim IN DATE,
        p_escopo IN VARCHAR2,
        p_antes IN NUMBER,
        p_limite IN NUMBER,
        documentos OUT SYS_REFCURSOR
    );
