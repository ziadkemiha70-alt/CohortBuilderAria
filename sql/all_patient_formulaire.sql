
SET NOCOUNT ON;


----------------------------------------------------------------------

-- Étape 1 : Colonnes Toxicité
DECLARE @cols_tox NVARCHAR(MAX) = ''; -- Déclaration d'une variable qui va contenir le code SQL de chaque colonne


-- Étape 1 : Récupération dynamique des noms de colonnes (noms des compétences)
SELECT @cols_tox = STRING_AGG(QUOTENAME(CAST(comp_names.tr_comp_name AS NVARCHAR(MAX))), ',')
FROM (
	SELECT DISTINCT tr.tr_comp_name 
	FROM tr_comp_culture tr
	JOIN tr_comp ON tr.tr_comp_id = tr_comp.tr_comp_id
	JOIN tr_asmt ON tr_asmt.tr_comp_name = tr_comp.tr_comp_name
				AND tr_asmt.gs_author = tr_comp.gs_author
				AND tr_asmt.eff_date = tr_comp.eff_date
				AND tr_asmt.tr_typ = tr_comp.tr_typ
	JOIN tr_asmt_hdr ON tr_asmt.tr_asmt_hdr_id = tr_asmt_hdr.tr_asmt_hdr_id
					AND tr_asmt.pt_id = tr_asmt_hdr.pt_id
					AND tr_asmt.pt_visit_id = tr_asmt_hdr.pt_visit_id
	JOIN pt ON tr_asmt.pt_id = pt.pt_id
	JOIN pt_visit ON pt_visit.pt_visit_id = tr_asmt.pt_visit_id
					AND pt_visit.pt_id = tr_asmt.pt_id
	JOIN Patient p ON p.PatientSer = pt.patient_ser
	WHERE tr.culture_cd = 'FRA'
		AND tr_asmt.valid_entry_ind = 'Y'
		AND tr_asmt_hdr.valid_entry_ind <> 'N'
) AS comp_names

-- Supprimer la ',' a la fin pour éviter l'erreur
IF RIGHT(@cols_tox, 3) = ',' + CHAR(13) + CHAR(10)
	SET @cols_tox = LEFT(@cols_tox, LEN(@cols_tox) - 3);

--PRINT @cols_tox;
----------------------------------------------------------------------

-- Étape 2 : Colonnes Questionnaire
DECLARE @cols_q NVARCHAR(MAX) = ''; -- Déclaration d'une variable qui va contenir le code SQL de chaque colonne

-- Objectif 1 : C'est d'avoir un seul resultat par jour
-- Objectif 2 : C'est de nettoyer la sortie en enlevant les espaces inutiles ou bien en remplacant les entités HTML par des caractères normaux pour éviter des erreurs SQL
SELECT @cols_q = ISNULL(@cols_q, '') +
	'MAX(CASE WHEN LTRIM(RTRIM(q.title)) = ''' + 
	REPLACE(q.title, '''', '''''') + 
	''' THEN pt.resp END) AS [' + 
	REPLACE(q.title, ']', '') + '],' + CHAR(13) + CHAR(10)
FROM (
	SELECT DISTINCT q.title
	FROM pt_resp pt
	LEFT JOIN qstr q ON q.qstr_name = pt.qstr_name
) q;

-- Supprimer la ',' a la fin pour éviter l'erreur
IF RIGHT(@cols_q, 3) = ',' + CHAR(13) + CHAR(10)
	SET @cols_q = LEFT(@cols_q, LEN(@cols_q) - 3);

----------------------------------------------------------------------

-- Étape 3 : Génération de la requête finale
DECLARE @sql NVARCHAR(MAX); -- Déclaration d'une variable final qui va contenir le code SQL de toute les colonnes

-- CTE 1 : RawData_Toxicity : Cette partie regroupe toutes les toxicités par date pour le patient sélectionné
-- CTE 2 : RawData_Questions : Cette partie regroupe toutes les Questions par date pour le patient sélectionné
-- CTE 3 : PerfoStatus : On récupère le score ECOG (performances status)
SET @sql = '
WITH RawData_Toxicity AS (
	SELECT pt_id, 
	CONVERT(DATE, date_time_asmt) AS date_event,
	' + @cols_tox + '
	FROM (
		SELECT 
			pt.pt_id,
			tr_asmt.date_time_asmt,
			tr.tr_comp_name,
			tr_asmt.tr_grade
		FROM tr_comp_culture tr
		JOIN tr_comp ON tr.tr_comp_id = tr_comp.tr_comp_id
		JOIN tr_asmt ON tr_asmt.tr_comp_name = tr_comp.tr_comp_name
					AND tr_asmt.gs_author = tr_comp.gs_author
					AND tr_asmt.eff_date = tr_comp.eff_date
					AND tr_asmt.tr_typ = tr_comp.tr_typ
		JOIN tr_asmt_hdr ON tr_asmt.tr_asmt_hdr_id = tr_asmt_hdr.tr_asmt_hdr_id
						AND tr_asmt.pt_id = tr_asmt_hdr.pt_id
						AND tr_asmt.pt_visit_id = tr_asmt_hdr.pt_visit_id
		JOIN pt ON tr_asmt.pt_id = pt.pt_id
		JOIN pt_visit ON pt_visit.pt_visit_id = tr_asmt.pt_visit_id
						AND pt_visit.pt_id = tr_asmt.pt_id
		JOIN Patient p ON p.PatientSer = pt.patient_ser
		WHERE tr.culture_cd = ''FRA''
			AND tr_asmt.valid_entry_ind = ''Y''
			AND tr_asmt_hdr.valid_entry_ind <> ''N''
			  
		
	) AS SourceTable
	PIVOT (
		MAX(tr_grade)
		FOR tr_comp_name IN (' + @cols_tox + ')
	) AS PivotTable
),

RawData_Questions AS (
	SELECT
		pt.pt_id,
		CONVERT(DATE, pt.trans_log_mtstamp) AS date_event,
		' + @cols_q + '
	FROM pt_resp pt
	LEFT JOIN qstr q ON q.qstr_name = pt.qstr_name
		
	GROUP BY pt.pt_id, CONVERT(DATE, pt.trans_log_mtstamp)
),

PerfoStatus AS (
	SELECT pt.pt_id, pt.perf_status_1 AS ECOG
	FROM pt_dx_status pt
		
)

SELECT 
	COALESCE(q.pt_id, t.pt_id) AS pt_id,
	COALESCE(q.date_event, t.date_event) AS date_event,
	p.ECOG, 
';

----------------------------------------------------------------------

-- Étape 4 : Ajout des colonnes dynamiques
DECLARE @cols_final NVARCHAR(MAX) = '';

-- Toxicité
SELECT @cols_final = ISNULL(@cols_final, '') +
	't.[' + REPLACE(REPLACE(REPLACE(tr_comp_name, '&amp;', '&'), '&lt;', '<'), '&gt;', '>') + '],' + CHAR(13) + CHAR(10)
FROM (
	SELECT DISTINCT tr.tr_comp_name 
	FROM tr_comp_culture tr
	JOIN tr_comp ON tr.tr_comp_id = tr_comp.tr_comp_id
	JOIN tr_asmt ON tr_asmt.tr_comp_name = tr_comp.tr_comp_name
				AND tr_asmt.gs_author = tr_comp.gs_author
				AND tr_asmt.eff_date = tr_comp.eff_date
				AND tr_asmt.tr_typ = tr_comp.tr_typ
	JOIN tr_asmt_hdr ON tr_asmt.tr_asmt_hdr_id = tr_asmt_hdr.tr_asmt_hdr_id
					AND tr_asmt.pt_id = tr_asmt_hdr.pt_id
					AND tr_asmt.pt_visit_id = tr_asmt_hdr.pt_visit_id
	JOIN pt ON tr_asmt.pt_id = pt.pt_id
	JOIN pt_visit ON pt_visit.pt_visit_id = tr_asmt.pt_visit_id
					AND pt_visit.pt_id = tr_asmt.pt_id
	JOIN Patient p ON p.PatientSer = pt.patient_ser
	WHERE tr.culture_cd = 'FRA'
		AND tr_asmt.valid_entry_ind = 'Y'
		AND tr_asmt_hdr.valid_entry_ind <> 'N'
) AS t;

-- Questionnaire
SELECT @cols_final = @cols_final + 
	'q.[' + REPLACE(title, ']', '') + '],' + CHAR(13) + CHAR(10)
FROM (
	SELECT DISTINCT q.title
	FROM pt_resp pt
	LEFT JOIN qstr q ON q.qstr_name = pt.qstr_name
) AS q;

IF RIGHT(@cols_final, 3) = ',' + CHAR(13) + CHAR(10)
	SET @cols_final = LEFT(@cols_final, LEN(@cols_final) - 3);

----------------------------------------------------------------------

-- Finalisation de la requête
SET @sql = @sql + @cols_final + '
FROM RawData_Questions q
FULL OUTER JOIN RawData_Toxicity t
	ON q.pt_id = t.pt_id AND q.date_event = t.date_event
LEFT JOIN PerfoStatus p
	ON p.pt_id = COALESCE(q.pt_id, t.pt_id)
ORDER BY date_event;
';

----------------------------------------------------------------------

-- Exécution
EXEC sp_executesql @sql;

