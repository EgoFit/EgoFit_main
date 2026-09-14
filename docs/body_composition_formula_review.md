# Body-composition formula review

Reviewed September 4, 2026. The calculator returns estimates from
anthropometric measurements; none of these equations replaces a clinical
assessment or indirect calorimetry.

## Implemented equations

- **BMI:** `weight_kg / height_m²`. The existing adult category labels remain
  the usual screening bands and are not a diagnosis.
- **WHR:** `waist / hip`. The displayed labels are screening bands. Cutoffs
  vary by population; the project uses `<0.90` / `0.90–<0.95` / `>=0.95` for
  men and `<0.80` / `0.80–<0.85` / `>=0.85` for women.
- **WHtR:** `waist / height`, both in the same units. The labels now follow
  NICE-style adult central-adiposity bands: `0.40–<0.50` healthy,
  `0.50–<0.60` increased, and `>=0.60` high. Values below `0.40` are marked
  outside the classified range.
- **Mifflin–St Jeor:** `10W + 6.25H - 5A + 5` for men and
  `10W + 6.25H - 5A - 161` for women, where `W` is kilograms, `H` is
  centimetres, and `A` is years. This is a resting-energy estimate; the
  historical project API name `BMR` is retained for compatibility.
- **TDEE:** estimated resting energy multiplied by the selected activity
  factor (`1.20`, `1.375`, `1.55`, `1.725`, or `1.90`). It is an estimate, not
  a measured expenditure.
- **Jackson–Pollock 3- and 7-site:** the existing density equations followed
  by Siri's `495 / density - 450` conversion.
- **Jackson–Pollock 4-site:** corrected to the four-site percent-fat
  equations. Men use abdomen, triceps, thigh, and suprailiac; women use
  triceps, suprailiac, thigh, and abdomen. Automatic selection is now
  seven-site, four-site, then three-site.
- **Navy circumference:** corrected to convert project centimetres to inches
  before applying the Hodgdon–Beckett logarithmic equations. Men use abdomen
  at the navel when available, falling back to waist; women use waist, hip,
  and neck. The Navy result has no body-density value, so it is represented
  as `None` rather than `0.0`.
- **Lean mass / fat mass:** `weight × (1 - body_fat / 100)` and
  `weight × body_fat / 100`. “Lean mass” here means fat-free mass, not
  muscle mass alone.
- **Protein:** profiles with unknown or sedentary activity receive
  `0.8–1.0 g/kg/day`; exercising
  profiles receive `1.4–2.0 g/kg/day`. The optional weight-loss context
  supports `1.8–2.7 g/kg/day`, or `2.3–3.1 g/kg fat-free mass` when FFM is
  supplied.
- **Weight targets:** the snapshot exposes a starting loss target of
  `TDEE - 600 kcal` and gain target of `TDEE + 300 kcal`. These are adjustable
  planning defaults, not universal prescriptions; targets must be reviewed
  for the person's age, health, training, and dietary history.

## Main references

1. Mifflin MD et al. *A new predictive equation for resting energy
   expenditure in healthy individuals*. American Journal of Clinical
   Nutrition (1990), PMID 2305711, DOI 10.1093/ajcn/51.2.241.
2. Frankenfield D et al. *Comparison of predictive equations for resting
   metabolic rate in healthy nonobese and obese adults*. Journal of the
   American Dietetic Association (2005), PMID 15883556.
3. Jackson AS, Pollock ML, Ward A. *Generalized equations for predicting body
   density of women*. Medicine & Science in Sports & Exercise (1980), PMID
   7402055.
4. Jackson–Pollock four-site equations as reproduced in the University of
   Michigan anthropometry reference and the peer-reviewed Iranian military
   anthropometry comparison (PMC articles).
5. NICE CG189 waist-to-height guidance: keep waist below half of height; the
   current NICE bands use `0.40–0.49`, `0.50–0.59`, and `>=0.60` for adults
   with BMI below 35.
6. U.S. Navy / Department of Defense body-composition guidance for the
   circumference method and inch-based circumference value.
7. International Society of Sports Nutrition position stand on protein and
   exercise (JISSN 2017), plus Morton et al. resistance-training meta-analysis
   (British Journal of Sports Medicine 2018, PMID 28698222).
8. NHS weight-management guidance commonly starts with an average
   `600 kcal/day` reduction; sports-nutrition weight-gain reviews commonly
   discuss a `300–500 kcal/day` surplus.
