
SET NOCOUNT ON;

------------------------------------------------------------------------

-- Table contenant les fractions de traitement détaillées pour chaque patient
DECLARE @FractionsChamps TABLE (
	IdFractionChamp INT,
	DateSeance DATE,
	IdChamp INT,
	IdFractionSite INT,
	IdFractionSiteCorrected INT,
	IdSite INT,
	Prescrib FLOAT,
	IdTraitement INT,
	IdPatient INT,
	IdMachine INT,
	DateFractionChamp DATETIME,
	DoseFractionChamp FLOAT,
	NomChamp VARCHAR(100),
	DescriptionChamp VARCHAR(100),
	--RadiationNumber INT,
	RadiationType VARCHAR(50),
	FieldSetupNote VARCHAR(255),
	FractionNumber INT,
	TreatmentRecordSer INT,
	FractionNumero INT,
	NumeroDeFractionPourChamp INT,
	NumeroDeFractionPourASupprimer INT,
	FractionType VARCHAR(50)
);

-- Insérer les données dans @FractionsChamps en évitant les erreurs sur RadiationNumber
INSERT INTO @FractionsChamps
	SELECT 
		RefPointHstry.RefPointHstrySer AS IdFractionChamp,
		CONVERT(DATE, RefPointHstry.HstryDateTime) AS DateSeance, 
		RadiationHstry.RadiationSer AS IdChamp,
		TreatmentRecord.SeriesSer AS IdFractionSite,
		0 AS IdFractionSiteCorrected,
		TreatmentRecord.RTPlanSer AS IdSite,
		RTPlan.PrescribedDose AS Prescrib,
		PlanSetup.CourseSer AS IdTraitement,
		TreatmentRecord.PatientSer AS IdPatient,
		TreatmentRecord.ActualMachineSer AS IdMachine,
		RefPointHstry.HstryDateTime AS DateFractionChamp,
		RefPointHstry.ActualDose AS DoseFractionChamp,
		RadiationHstry.RadiationId AS NomChamp,
		RadiationHstry.RadiationName AS DescriptionChamp,
		--TRY_CAST(RadiationHstry.RadiationNumber AS INT) AS RadiationNumber,  -- Utilisation de TRY_CAST pour éviter les erreurs de conversion
		RadiationHstry.RadiationType,
		RadiationHstry.FieldSetupNote,
		RadiationHstry.FractionNumber,
		RadiationHstry.TreatmentRecordSer,
		TreatmentRecord.NoOfFractions AS FractionNumero,
		0 AS NumeroDeFractionPourChamp,
		ROW_NUMBER() OVER (PARTITION BY RadiationHstry.RadiationSer ORDER BY RefPointHstry.HstryDateTime) AS NumeroDeFractionPourASupprimer,
		TreatmentDeliveryType AS FractionType
	FROM RefPointHstry
	LEFT JOIN RadiationHstry ON RadiationHstry.RadiationHstrySer = RefPointHstry.RadiationHstrySer
	LEFT JOIN TreatmentRecord ON TreatmentRecord.TreatmentRecordSer = RadiationHstry.TreatmentRecordSer
	LEFT JOIN RTPlan ON RTPlan.RTPlanSer = TreatmentRecord.RTPlanSer
	LEFT JOIN PlanSetup ON PlanSetup.PlanSetupSer = RTPlan.PlanSetupSer
	LEFT JOIN Patient ON Patient.PatientSer = TreatmentRecord.PatientSer;


------------------------------------------------------------------------



-- Table de correction des sites de fractionnement (gestion des doublons ou erreurs)
DECLARE @CorrectedFractionSite TABLE (
	IdFractionChamp INT,
	IdFractionSiteCorrected INT
);

INSERT INTO @CorrectedFractionSite
SELECT 
	FC.IdFractionChamp,
	(
		SELECT MIN(TRY_CAST(SubFractionsChamps.IdFractionSite AS INT)) 
		FROM @FractionsChamps SubFractionsChamps
		WHERE SubFractionsChamps.IdPatient = FC.IdPatient
			AND SubFractionsChamps.IdSite = FC.IdSite
			AND SubFractionsChamps.DateFractionChamp BETWEEN DATEADD(HOUR, -4, FC.DateFractionChamp)
				AND DATEADD(HOUR, 4, FC.DateFractionChamp)
			AND TRY_CAST(SubFractionsChamps.IdFractionSite AS INT) IS NOT NULL
	) AS IdFractionSiteCorrected
FROM @FractionsChamps FC;



------------------------------------------------------------------------



-- Table pour numéroter les fractions par champ
DECLARE @FractionForField TABLE (
	NumeroDeFractionPourChamp INT,
	IdFractionSiteCorrected INT,
	IdChamp INT
);

INSERT INTO @FractionForField
SELECT 
	ROW_NUMBER() OVER (PARTITION BY IdChamp ORDER BY MIN(DateFractionChamp)) AS NumeroDeFractionPourChamp,
	IdFractionSiteCorrected,
	IdChamp
FROM @FractionsChamps
GROUP BY IdFractionSiteCorrected, IdChamp;



------------------------------------------------------------------------

-- Table des sites de traitement enrichie (technique, énergie, etc.)
DECLARE @ChampsSites TABLE (
	IdChamp INT,
	IdSite INT,
	IdPhaseSite INT,
	IdTraitement INT,
	IdPatient INT,
	PremiereFractionChamp DATETIME,
	DerniereFractionChamp DATETIME,

	DescriptionChamp VARCHAR(100),
	TechniqueId VARCHAR(50),
	RadiationType VARCHAR(50),
	Energy VARCHAR(50),
	NumeroDeChampPourSite INT,
	IdMachine INT  
);

-- Étape intermédiaire à ajouter
UPDATE FC
SET FC.IdFractionSiteCorrected = CFS.IdFractionSiteCorrected
FROM @FractionsChamps FC
JOIN @CorrectedFractionSite CFS ON FC.IdFractionChamp = CFS.IdFractionChamp;

-- Puis ta requête d'insertion dans @ChampsSites
INSERT INTO @ChampsSites
SELECT 
	IdChamp,
	IdSite,
	Radiation.PlanSetupSer AS IdPhaseSite,
	IdTraitement,
	IdPatient,
	PremiereFractionChamp,
	DerniereFractionChamp,
	RadiationName AS DescriptionChamp,
	Technique.TechniqueId,
	EnergyMode.RadiationType,
	Energy,
	ROW_NUMBER() OVER (PARTITION BY IdSite ORDER BY PremiereFractionChamp) AS NumeroDeChampPourSite,
	IdMachine
FROM (
	SELECT
		Fc.IdChamp,
		Fc.IdSite,
		MIN(Fc.IdTraitement) AS IdTraitement,
		MIN(Fc.IdPatient) AS IdPatient,
		MIN(Fc.DateFractionChamp) AS PremiereFractionChamp,
		MAX(Fc.DateFractionChamp) AS DerniereFractionChamp,
		SUM(Fc.DoseFractionChamp) AS DoseChamp,
		COUNT(DISTINCT Fc.IdFractionSiteCorrected) AS NombreFractionSite,
		MIN(Fc.IdMachine) AS IdMachine -- <-- ici on ajoute l'IdMachine
	FROM @FractionsChamps Fc
	GROUP BY Fc.IdChamp, Fc.IdSite
) AS sqChamps
LEFT JOIN Radiation ON Radiation.RadiationSer = sqChamps.IdChamp
LEFT JOIN ExternalFieldCommon ON ExternalFieldCommon.RadiationSer = sqChamps.IdChamp
LEFT JOIN Technique ON Technique.TechniqueSer = ExternalFieldCommon.TechniqueSer
LEFT JOIN EnergyMode ON EnergyMode.EnergyModeSer = ExternalFieldCommon.EnergyModeSer;


------------------------------------------------------------------------

	

-- Table de synthèse des plans et sessions de traitement
DECLARE @PlanSession TABLE (
    RTPlanSer INT,
    PlanSetupSer INT,
    ScheduledActivitySer INT,
    StartDateTime DATETIME,
    LastDateTime DATETIME,
    Doses FLOAT,
    DosesTotal INT,        
    PlannedFrac INT,
    NbFractionsEffectués INT,
    NbFractionsRestantes INT,
    DoseRestante FLOAT,
    DoseEffectuée FLOAT,
    DosePerFraction FLOAT,
    DosesTotal2 FLOAT,
    DoseEffectuée2 FLOAT,
    FirstName VARCHAR(MAX),
    LastName VARCHAR(MAX)
);
    
WITH FractionsEffectuees AS (
    SELECT
        srp.RTPlanSer,
        COUNT(DISTINCT srp.SessionSer) AS NbFractionsEffectuées,
        MIN(srp.HstryDateTime) AS StartDateTime,
        MAX(srp.HstryDateTime) AS LastDateTime,
        MAX(act.ScheduledActivitySer) AS ScheduledActivitySer
    FROM VARIAN.dbo.SessionRTPlan srp
    LEFT JOIN VARIAN.dbo.ActivitySession act ON act.SessionSer = srp.SessionSer
    WHERE srp.Status NOT IN ('TREAT')
    GROUP BY srp.RTPlanSer
),
DoseParPlan AS (
    SELECT 
        RTPlanSer,
        MAX(DosePerFraction) AS DosePerFraction
    FROM VARIAN.dbo.DoseContribution
    GROUP BY RTPlanSer
)
    
INSERT INTO @PlanSession
SELECT
    RTPlan.RTPlanSer,
    RTPlan.PlanSetupSer,
    fe.ScheduledActivitySer,
    fe.StartDateTime,
    fe.LastDateTime,
    RTPlan.PrescribedDose AS Doses,
    RTPlan.PrescribedDose * MAX(RTPlan.NoFractions) AS DosesTotal,
    MAX(RTPlan.NoFractions) AS PlannedFrac,
    fe.NbFractionsEffectuées,
    CASE 
        WHEN MAX(RTPlan.NoFractions) - fe.NbFractionsEffectuées < 0 THEN 0 
        ELSE MAX(RTPlan.NoFractions) - fe.NbFractionsEffectuées 
    END AS NbFractionsRestantes,
    CASE 
        WHEN RTPlan.PrescribedDose * (MAX(RTPlan.NoFractions) - fe.NbFractionsEffectuées) < 0 THEN 0 
        ELSE RTPlan.PrescribedDose * (MAX(RTPlan.NoFractions) - fe.NbFractionsEffectuées)
    END AS DoseRestante,
    RTPlan.PrescribedDose * fe.NbFractionsEffectuées AS DoseEffectuée,
    dc.DosePerFraction,
    dc.DosePerFraction * MAX(RTPlan.NoFractions) AS DosesTotal2,
    dc.DosePerFraction * fe.NbFractionsEffectuées AS DoseEffectuée2,
    p.FirstName,
    p.LastName
FROM VARIAN.dbo.RTPlan RTPlan
JOIN PlanSetup ps ON ps.PlanSetupSer = RTPlan.PlanSetupSer
JOIN Course c ON c.CourseSer = ps.CourseSer
JOIN Patient p ON p.PatientSer = c.PatientSer
LEFT JOIN FractionsEffectuees fe ON fe.RTPlanSer = RTPlan.RTPlanSer
LEFT JOIN DoseParPlan dc ON dc.RTPlanSer = RTPlan.RTPlanSer
GROUP BY 
    RTPlan.RTPlanSer,
    RTPlan.PlanSetupSer,
    fe.ScheduledActivitySer,
    fe.StartDateTime,
    fe.LastDateTime,
    RTPlan.PrescribedDose,
    fe.NbFractionsEffectuées,
    dc.DosePerFraction,
    p.FirstName,
    p.LastName
ORDER BY p.FirstName, p.LastName;





------------------------------------------------------------------------
	
	DECLARE @Prescriptions TABLE (
	PrescriptionSer INT,
	CreationDate date,
	PrescriptionName VARCHAR(255),
	TreatmentPhaseSer INT,
	PhaseType VARCHAR(50),
	Technique VARCHAR(100),
	Site VARCHAR(100),
	Status VARCHAR(50),
	Notes VARCHAR(MAX),
	PatientSer INT,
	PlanSetupSer INT,
	CourseSer INT,
	HstryUserName varchar(max),
	--PrescriptionPropertySer INT,
	--PropertyType INT,
	Modes VARCHAR(MAX),
	Energies VARCHAR(MAX),
	Frequences VARCHAR(MAX),
	PrescriptionTemplateName VARCHAR(MAX)
);

-- Étape 0 : Table temporaire avec les fréquences connues
DECLARE @Frequences TABLE (Valeur VARCHAR(100));
	
INSERT INTO @Frequences (Valeur)
VALUES ('Aucune'), ('1 fraction / semaine'), ('1 jour sur 2'), ('2 fractions / semaine'),
		('4 fractions / semaine'),('Bifractionné'), ('HDR: 1/semaine'), ('HDR: 2/semaine'), ('Hypofractionné'),
		('PDR: 1 pulse/h'), ('Quotidien');

-- Étape 1 : Numéroter les propriétés pour séparation
WITH NumberedProperties AS (
	SELECT
		pp.PrescriptionSer,
		pp.PropertyValue,
		RN = ROW_NUMBER() OVER (PARTITION BY pp.PrescriptionSer ORDER BY pp.PropertyValue)
	FROM PrescriptionProperty pp
),

-- Étape 2 : Séparer en 3 colonnes max
PropertiesExpanded AS (
	SELECT
		PrescriptionSer,
		MAX(CASE WHEN RN = 1 THEN PropertyValue END) AS PropertyValue1,
		MAX(CASE WHEN RN = 2 THEN PropertyValue END) AS PropertyValue2,
		MAX(CASE WHEN RN = 3 THEN PropertyValue END) AS PropertyValue3
	FROM NumberedProperties
	GROUP BY PrescriptionSer
),

-- Étape 3 : Trouver la fréquence correcte dynamiquement
FrequencesTrouvées AS (
	SELECT
		pp.PrescriptionSer,
		pp.PropertyValue AS Frequence,
		ROW_NUMBER() OVER (PARTITION BY pp.PrescriptionSer ORDER BY pp.PropertyValue) AS RN
	FROM PrescriptionProperty pp
	INNER JOIN @Frequences f
		ON TRIM(pp.PropertyValue) = f.Valeur
),

-- Étape 4 : Garder seulement la première fréquence par Prescription
FrequencesUnifiées AS (
	SELECT
		PrescriptionSer,
		Frequence
	FROM FrequencesTrouvées
	WHERE RN = 1
)

-- Étape 5 : Insertion finale avec intégration des propriétés
INSERT INTO @Prescriptions
SELECT 
	p.PrescriptionSer,
	p.CreationDate,
	p.PrescriptionName,
	p.TreatmentPhaseSer,
	p.PhaseType,
	p.Technique,
	p.Site,
	p.Status,
	p.Notes,
	c.PatientSer,
	ps.PlanSetupSer,
	c.CourseSer,
	p.HstryUserName,

	CASE 
		WHEN pe.PropertyValue1 IN ('N/A', 'Adaptatif', 'Compression abdominale', 'Inspiration bloquée', 'Spiro Dyn''R') THEN pe.PropertyValue1
		WHEN pe.PropertyValue2 IN ('N/A', 'Adaptatif', 'Compression abdominale', 'Inspiration bloquée', 'Spiro Dyn''R') THEN pe.PropertyValue2
		WHEN pe.PropertyValue3 IN ('N/A', 'Adaptatif', 'Compression abdominale', 'Inspiration bloquée', 'Spiro Dyn''R') THEN pe.PropertyValue3
		ELSE NULL
	END AS Modes,

	-- Energie (PropertyValue2) : valeur spécifique liée aux types d'énergie
	CASE 
		WHEN pe.PropertyValue1 IN ('Haute Energie', 'I 125', 'Ir 192') THEN pe.PropertyValue1
		WHEN pe.PropertyValue2 IN ('Haute Energie', 'I 125', 'Ir 192') THEN pe.PropertyValue2
		WHEN pe.PropertyValue3 IN ('Haute Energie', 'I 125', 'Ir 192') THEN pe.PropertyValue3
		ELSE NULL
	END AS Energies,

	-- Fréquence dynamique à partir de la jointure avec FrequencesUnifiées
	fu.Frequence,

	pt.PrescriptionTemplateName

FROM Prescription p
INNER JOIN TreatmentPhase tp ON p.TreatmentPhaseSer = tp.TreatmentPhaseSer
INNER JOIN Course c ON tp.CourseSer = c.CourseSer
LEFT JOIN PlanSetup ps ON ps.PrescriptionSer = p.PrescriptionSer
LEFT JOIN PropertiesExpanded pe ON pe.PrescriptionSer = p.PrescriptionSer
LEFT JOIN FrequencesUnifiées fu ON fu.PrescriptionSer = p.PrescriptionSer
LEFT JOIN PrescriptionTemplate pt ON pt.PrescriptionName = p.PrescriptionName
WHERE p.Status = 'Approved';

--select * from @Prescriptions where PatientSer = ''
--select * from @Prescriptions where PatientSer = ''
------------------------------------------------------------------------


DECLARE @Machines TABLE (
	idMachine INT,
	idcourse INT,
	NomMachine VARCHAR(100),
	Model VARCHAR(100)
);

INSERT INTO @Machines
SELECT 
	fr.IdMachine AS Machineid,
	fr.IdTraitement AS idcourse,
	m.MachineId AS NomMachine,
	m.MachineModel AS Model

FROM @FractionsChamps fr
LEFT JOIN Machine m ON m.ResourceSer = fr.IdMachine

	
	
------------------------------------------------------------------------

-- Table temporaire des médecins
DECLARE @Medecins TABLE (
	PersonSer INT,
	HstryUserName varchar(max),
	PrimaryFlag int,
	Nom NVARCHAR(255),
	Prenom NVARCHAR(255),
	Alias NVARCHAR(255)
);

-- Insertion des médecins liés au patient via PatientDoctor
INSERT INTO @Medecins
SELECT DISTINCT
	PD.PatientSer AS PersonSer,  -- Ici on prend l'ID du médecin (ResourceSer)
	P.HstryUserName,
	PD.PrimaryFlag,
	D.LastName AS Nom,
	D.FirstName AS Prenom,
	D.AliasName AS Alias
	
FROM Doctor D
	
INNER JOIN PatientDoctor PD ON PD.ResourceSer = D.ResourceSer
INNER JOIN @Prescriptions P ON P.HstryUserName = PD.HstryUserName
--WHERE PD.PatientSer = DPC.PatientId;

/*
select * 
from @Medecins
where PersonSer = ''
*/

------------------------------------------------------------------------

-- Table temporaire pour les volumes/doses des points de référence
DECLARE @Volumes TABLE (
	--Patientsid INT,
	--PatientVolumeid INT,
	Patientser INT,
	PatientVolumeSer INT,
	VolumeType NVARCHAR(MAX),
	DicomType NVARCHAR(MAX),
	PatientVolumeId NVARCHAR(MAX)

);



INSERT INTO @Volumes
SELECT DISTINCT
	PatientVolume.PatientSer,
	PatientVolume.PatientVolumeSer,
	ref.VolumeType,
	ref.DicomType,

	PatientVolume.PatientVolumeId

FROM PatientVolume
LEFT JOIN VolumeType ref ON ref.VolumeTypeSer = PatientVolume.VolumeTypeSer
--WHERE p.PatientId = ''
;
/*
select distinct * 
from @Volumes
where PatientSer = ''
*/
------------------------------------------------------------------------


-- Table principale
DECLARE @PatientInfo TABLE (
pt_id  VarChar(Max),
PatientId VarChar(Max),
FirstName VarChar(Max),
LastName VarChar(Max),
Naissance DATE,
PatientStatus VarChar(Max),
DeathDate DATE,
Age INT,
AgePrmFract INT,
Sex VarChar(Max),
CourseId VarChar(Max),
PlanSetupId VarChar(Max),
laterality_typ int,
laterality_desc VarChar(Max), 
PlannedFrac VarChar(Max),
DiagnosisCode VarChar(Max),
	
DiagPrimaire VarChar(Max),
	
DiagnosisType VarChar(Max),
ICD VarChar(Max),
cncr_stage VarChar(Max),
crit_desc VarChar(Max),

date_staged date,

Stade_Tumoral VARCHAR(100),
Stade_Nodal VARCHAR(100),
Stade_Metastase VARCHAR(100),
Facteur_HER2 VARCHAR(100),
Recepteur_Estrogene VARCHAR(100),
Recepteur_Progesterone VARCHAR(100),
Age_Diagnostic VARCHAR(100),
Grade_Histologique VARCHAR(100),
Niveau_PSA VARCHAR(100),
Score_Oncologique VARCHAR(100),
Autres VARCHAR(MAX),

morph_cd int,
tumor_size float,
necrosis_status_typ int,
ki67_status_typ int,
ki67_pct float,
varis_histology_cd VarChar(Max),

pt_dx_id int,
prmy_dx_id int,

invasive_ind varchar(max),
gleason_prmy varchar(max),
gleason_scndy varchar(max),
gleason_tertiary_typ varchar(max),
gleason_total varchar(max),
multifocal_ind varchar(max),

--necrosis_status_typ int,
cores_pos varchar(max),
cores_pos_left varchar(max),
cores_pos_right varchar(max),
cores_taken varchar(max),
cores_taken_left varchar(max),
cores_taken_right varchar(max),

stg_crit_desc varchar(max),
pathology_cmt varchar(max),
nodes_cytokeratin_pos varchar(max),
microcalc_status_typ varchar(max),
ece_status_typ varchar(max),

er_status VARCHAR(MAX),
pr_status VARCHAR(MAX),
nodes_examined INT,
nodes_pos INT,
her2neu_status2_typ INT,
in_situ_cncr_ind VARCHAR(MAX),
--TNM_Classification VARCHAR(100),


Description VarChar(Max),
PatientSer Int,
CourseSer Int,
PlanSetupSer Int,
RTPlanSer Int,
HistologyTableName VarChar(Max),
MobilePhone  nVarChar(Max),
Citizenship VarChar(Max)

)


;

WITH Tokens AS (
SELECT 
    pt_cncr_stg.crit_desc,
    LTRIM(RTRIM(value)) AS token
FROM pt_cncr_stg
CROSS APPLY STRING_SPLIT(pt_cncr_stg.crit_desc, ',')
WHERE pt_cncr_stg.crit_desc IS NOT NULL
), Classified AS (
SELECT
    crit_desc,
    token,
    CASE
        WHEN token LIKE 'DxAge%' THEN 'DxAge'
        WHEN token LIKE 'G%' THEN 'Grade'
        WHEN token LIKE 'P%' AND token NOT LIKE 'PR%' THEN 'PSA'
        WHEN token LIKE 'Onco%' THEN 'Score_Onco'
        WHEN token LIKE 'HER2%' THEN 'HER2'
        WHEN token LIKE 'ER%' THEN 'ER'
        WHEN token LIKE 'PR%' THEN 'PR'
        WHEN token LIKE '%T%' THEN 'T'
        WHEN token LIKE '%N%' THEN 'N'
        WHEN token LIKE '%M%' THEN 'M'
        ELSE 'AUTRE'
    END AS TypeChamp
FROM Tokens
), Pivote AS (
SELECT
    crit_desc,
    MAX(CASE WHEN TypeChamp = 'T' THEN token END) AS Stade_T,
    MAX(CASE WHEN TypeChamp = 'N' THEN token END) AS Stade_N,
    MAX(CASE WHEN TypeChamp = 'M' THEN token END) AS Stade_M,
    MAX(CASE WHEN TypeChamp = 'HER2' THEN token END) AS HER2,
    MAX(CASE WHEN TypeChamp = 'ER' THEN token END) AS Recepteur_Estrogene,
    MAX(CASE WHEN TypeChamp = 'PR' THEN token END) AS Recepteur_Progesterone,
    MAX(CASE WHEN TypeChamp = 'DxAge' THEN token END) AS Age_Diagnostic,
    MAX(CASE WHEN TypeChamp = 'Grade' THEN token END) AS Grade_Histologique,
    MAX(CASE WHEN TypeChamp = 'PSA' THEN token END) AS Niveau_PSA,
    MAX(CASE WHEN TypeChamp = 'Score_Onco' THEN token END) AS Score_Oncologique,
    STRING_AGG(CASE WHEN TypeChamp = 'AUTRE' THEN token END, ', ') AS Autre
FROM Classified
GROUP BY crit_desc
)



-- Insertion dans la table PatientInfo
INSERT INTO @PatientInfo
SELECT DISTINCT
	
pt_dx_cncr.pt_id,

PatientId,
Patient.FirstName AS FirstName,
Patient.LastName AS LastName,
CAST(DateOfBirth AS DATE) AS Naissance,
CASE 
	WHEN PP.DeathDate IS NULL THEN 'Alive' 
	ELSE 'Dead' 
END AS PatientStatus,
CAST( PP.DeathDate AS DATE) AS DeathDate,
FLOOR(DATEDIFF(DAY, DateOfBirth, GETDATE()) / 365.25) AS Age,
FLOOR(DATEDIFF(DAY, DateOfBirth, (SELECT MIN(DateFractionChamp) FROM @FractionsChamps WHERE IdPatient = Patient.PatientSer)) / 365.25) AS AgePrmFract,
Patient.Sex,
CourseId,
PlanSetupId,
pt_dx_cncr.laterality_typ,
laterality_typ.laterality_desc,
PlannedFrac,
Diagnosis.DiagnosisCode,
	
diag_primaire.DiagnosisCode AS DiagPrimaire,
	
Diagnosis.DiagnosisType,

cls_scheme.scheme_name AS TNM,
	
	


pt_cncr_stg.cncr_stage,
--pt_cncr_stg.crit_desc,
pt_dx.stg_crit_desc,
	
pt_cncr_stg.date_staged,
	
ISNULL(Stade_T, 'NA') AS Stade_Clinique_Tumoral,
ISNULL(Stade_N, 'NA') AS Stade_Clinique_Node,
ISNULL(Stade_M, 'NA') AS Stade_Clinique_Metastase,
ISNULL(HER2, 'NA') AS Facteur_Croissance_HER2,
ISNULL(Recepteur_Estrogene, 'NA') AS Recepteur_Estrogene,
ISNULL(Recepteur_Progesterone, 'NA') AS Recepteur_Progesterone,
ISNULL(Age_Diagnostic, 'NA') AS Age_Diagnostic,
ISNULL(Grade_Histologique, 'NA') AS Grade_Histologique,
ISNULL(Niveau_PSA, 'NA') AS Niveau_PSA,
ISNULL(Score_Oncologique, 'NA') AS Score_Oncologique,
ISNULL(Autre, '') AS Autre,

pt_dx_cncr.morph_cd,
pt_dx_cncr.tumor_size,
pt_dx_cncr.necrosis_status_typ,
pt_dx_cncr.ki67_status_typ,
pt_dx_cncr.ki67_pct,
icdo_morph_cd.varis_histology_cd,
	
pt_dx_cncr.pt_dx_id,
pt_dx_cncr.prmy_dx_id,

pt_dx_cncr.invasive_ind,
pt_dx_cncr.gleason_prmy,
pt_dx_cncr.gleason_scndy,
pt_dx_cncr.gleason_tertiary_typ,
pt_dx_cncr.gleason_total,
pt_dx_cncr.multifocal_ind,

--pt_dx_cncr.necrosis_status_typ,
pt_dx_cncr.cores_pos,
pt_dx_cncr.cores_pos_left,
pt_dx_cncr.cores_pos_right,
pt_dx_cncr.cores_taken,
pt_dx_cncr.cores_taken_left,
pt_dx_cncr.cores_taken_right,

pt_dx.stg_crit_desc,
pt_dx_cncr.pathology_cmt,
pt_dx_cncr.nodes_cytokeratin_pos,
pt_dx_cncr.microcalc_status_typ,
pt_dx_cncr.ece_status_typ,

pt_dx_cncr.er_status AS ER_Status,
pt_dx_cncr.pr_status AS PR_Status,  

pt_dx_cncr.nodes_examined,
pt_dx_cncr.nodes_pos,

pt_dx_cncr.her2neu_status2_typ,

pt_dx_cncr.in_situ_cncr_ind,

Diagnosis.Description,
Patient.PatientSer,
Course.CourseSer,
PlanSession.PlanSetupSer,
PlanSession.RTPlanSer,
Diagnosis.HistologyTableName,
Patient.MobilePhone,
Patient.Citizenship

	
FROM Patient Patient
JOIN Course Course ON Course.PatientSer = Patient.PatientSer
JOIN CourseDiagnosis CourseDiagnosis ON CourseDiagnosis.CourseSer = Course.CourseSer
JOIN Diagnosis Diagnosis ON Diagnosis.DiagnosisSer = CourseDiagnosis.DiagnosisSer
JOIN TreatmentPhase TreatmentPhase ON TreatmentPhase.CourseSer = Course.CourseSer
JOIN Prescription Prescription ON Prescription.TreatmentPhaseSer = TreatmentPhase.TreatmentPhaseSer
JOIN PlanSetup PlanSetup ON PlanSetup.CourseSer = Course.CourseSer
JOIN @PlanSession PlanSession ON PlanSession.PlanSetupSer = PlanSetup.PlanSetupSer
JOIN VARIAN.dbo.ScheduledActivity ScheduledActivity ON ScheduledActivity.ScheduledActivitySer = PlanSession.ScheduledActivitySer
JOIN VARIAN.dbo.ActivityCapture ActivityCapture ON ActivityCapture.ActivityInstanceSer = ScheduledActivity.ActivityInstanceSer
LEFT JOIN VARIAN.dbo.PatientParticular PP ON PP.PatientSer = Patient.PatientSer
LEFT JOIN pt_dx ON pt_dx.diagnosis_ser = Diagnosis.DiagnosisSer
LEFT JOIN pt_dx_cncr ON pt_dx_cncr.pt_dx_id = pt_dx.dx_id AND pt_dx_cncr.pt_id = pt_dx.pt_id
LEFT JOIN laterality_typ ON laterality_typ.laterality_typ = pt_dx_cncr.laterality_typ
LEFT JOIN icdo_morph_cd ON icdo_morph_cd.morph_cd = pt_dx_cncr.morph_cd AND icdo_morph_cd.morph_cd_seq = pt_dx_cncr.morph_cd_seq
                    AND icdo_morph_cd.behavior_cd  = pt_dx_cncr.behavior_cd 
                    AND icdo_morph_cd.cls_scheme_id = pt_dx_cncr.cls_scheme_id
LEFT JOIN pt_cncr_stg on pt_cncr_stg.crit_desc = pt_dx.stg_crit_desc
LEFT JOIN cls_scheme on cls_scheme.cls_scheme_id = pt_dx.cls_scheme_id
LEFT JOIN Pivote on Pivote.crit_desc = pt_dx.stg_crit_desc

LEFT JOIN (
SELECT 
    d.PatientSer, 
    MIN(d.DiagnosisCode) AS DiagnosisCode
FROM Diagnosis d
GROUP BY d.PatientSer
) diag_primaire ON diag_primaire.PatientSer = Patient.PatientSer


WHERE PlannedFrac > 0;

--select * from @PatientInfo p where p.PatientId = ''
------------------------------------------------------------------------

SELECT DISTINCT
	DPC.pt_id,
	DPC.PatientId,
	DPC.PatientSer,
	DPC.CourseSer,
	DPC.PlanSetupSer,
	DPC.RTPlanSer,
	P.TreatmentPhaseSer,
	P.PrescriptionSer,
	DPC.FirstName,
	DPC.LastName,
	DPC.Sex,
	DPC.Naissance,
	DPC.PatientStatus,
	DPC.DeathDate,
	DPC.MobilePhone,
	DPC.Citizenship,
	DPC.Age,
	DPC.AgePrmFract,
	DPC.CourseId,
	DPC.PlanSetupId,
	DPC.DiagnosisCode,

	DPC.DiagPrimaire,

	DPC.laterality_desc,
	DPC.DiagnosisType,
	DPC.ICD,
	DPC.cncr_stage,
	DPC.pt_dx_id,
	DPC.prmy_dx_id,
	DPC.stg_crit_desc,
	DPC.crit_desc,
	DPC.date_staged,
	DPC.Stade_Tumoral,
	DPC.Stade_Nodal,
	DPC.Stade_Metastase,
	DPC.Facteur_HER2,
	DPC.Recepteur_Estrogene,
	DPC.Recepteur_Progesterone,
	DPC.Score_Oncologique,
	DPC.Age_Diagnostic,
	DPC.Niveau_PSA,
	DPC.Grade_Histologique,
	DPC.Autres,
	DPC.morph_cd,
	DPC.tumor_size,
	DPC.necrosis_status_typ,
	DPC.ki67_status_typ,
	DPC.ki67_pct,
	DPC.varis_histology_cd,
	DPC.invasive_ind,
	DPC.gleason_prmy,
	DPC.gleason_scndy,
	DPC.gleason_tertiary_typ,
	DPC.gleason_total,
	DPC.multifocal_ind,
		
	DPC.pathology_cmt,
	DPC.microcalc_status_typ,
	DPC.ece_status_typ,
	DPC.nodes_cytokeratin_pos,
	DPC.pr_status,
	DPC.er_status,
	DPC.nodes_examined,
	DPC.her2neu_status2_typ,
	DPC.in_situ_cncr_ind,

	DPC.HistologyTableName,
	DPC.Description,
	P.Site,

	DPC.PlannedFrac,
	PS.NbFractionsEffectués,
	PS.NbFractionsRestantes,

	PS.DosePerFraction,
	PS.DosesTotal2,
	PS.DoseEffectuée2,

	CS.PremiereFractionChamp,
	CS.DerniereFractionChamp,

	CS.Energy,
	CS.RadiationType,
	CS.TechniqueId,

	P.HstryUserName,
	M.NomMachine,
	M.Model,

	P.PrescriptionName,

	v.VolumeType,
	v.DicomType,

	P.PrescriptionTemplateName,

	P.Modes,
	P.Frequences,
	P.Energies,
	P.Technique,

	P.PhaseType,
	P.Notes,
	P.Status

FROM @PatientInfo DPC

LEFT JOIN @PlanSession PS 
	ON DPC.RTPlanSer = PS.RTPlanSer

LEFT JOIN @ChampsSites CS 
	ON DPC.PatientSer = CS.IdPatient
	AND DPC.CourseSer = CS.IdTraitement
	AND DPC.PlanSetupSer = CS.IdPhaseSite
	AND DPC.RTPlanSer = CS.IdSite

LEFT JOIN @Volumes v ON v.Patientser = DPC.PatientSer

LEFT JOIN @Prescriptions P
	ON DPC.PatientSer = P.PatientSer
	AND DPC.CourseSer = P.CourseSer
	AND DPC.PlanSetupSer = P.PlanSetupSer

LEFT JOIN @Machines M
	ON M.idcourse = CS.IdTraitement

LEFT JOIN @Medecins Me
	ON Me.PersonSer = DPC.PatientSer




