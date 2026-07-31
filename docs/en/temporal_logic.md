# Temporal logic

## 1. Patient-level reference dates

For each retained patient, the application derives:

- `startD`: earliest retained radiotherapy date;
- `endD`: latest retained radiotherapy date.

Each form observation is assigned a day delay relative to the relevant reference date. These delays are then used to place values into enabled temporal phases.

## 2. Available phases

### Cumulative

Includes all available observations for the selected variable. Values, observation dates and delays may be retained in separate columns. Cumulative outputs preserve the chronological sequence rather than reducing the variable to a single window value.

### Before RT

Includes observations occurring before `startD`. The application can generate a complete pre-treatment cumulative representation and user-defined weekly windows.

### During RT / acute

Includes observations from `startD` during the acute period. Windows are expressed as treatment weeks.

### After RT / late

Includes observations after `endD`. The implementation can generate selected weekly windows and successive month intervals.

## 3. Default window configuration

The default code values are:

- weeks before RT: 71, 48, 41, 40, 37, 29, 13, 10, 8, 7, 6, 5, 4, 3, 2 and 1;
- weeks during RT: 1 through 7;
- weeks after RT: 1 and 8;
- monthly intervals: month 1, months 2-4, months 5-7, then successive intervals through 62 months and beyond.

These lists can be adjusted in expert mode. Changing the windows changes the generated schema and therefore requires export recalculation.

## 4. Output-column naming

For a variable exported as `Douleur`, the temporal schema may generate names such as:

```text
Douleur_Cumul
Douleur_Cumul_Date
Douleur_Cumul_Delai
Douleur_AvantRT_Semaine_001
Douleur_PendantRT_Semaines_001
Douleur_ApresRT_Semaine_001
Douleur_Mois 02 - 04
```

A value column may be accompanied by date and delay columns. Exact names depend on enabled phases and profile settings.

## 5. Aggregation rules

When several observations exist on the same day:

- an identical repeated value is retained once;
- numeric values are resolved by maximum;
- binary strings are merged using a logical OR by position;
- distinct text values are resolved using the last non-empty value.

For a non-cumulative temporal window, the first observation date inside the window is retained. For cumulative outputs, all valid observations are retained in chronological order.

## 6. Exact duplicates

An exact duplicate is defined by the same patient, variable, observation date and value. When duplicate removal is enabled, the duplicate is excluded from aggregation but remains counted and may be sampled in the evidence report.

## 7. Boundary validation

Temporal changes should be tested with dates positioned exactly on both sides of every boundary. Review:

- whether pre-treatment values remain strictly before `startD`;
- whether treatment-start observations enter the acute phase;
- whether post-treatment observations are referenced to `endD`;
- whether a date at a week or month boundary enters the intended interval;
- whether cumulative chronology and non-cumulative first-date rules remain consistent.
