"""
BBA Mappers — convertesc output-ul fiecărui strat în Basic Belief Assignments.

Frame of discernment: Θ = {hawkish, dovish, neutral}
Power set: toate subseturile posibile + Θ (ignoranță totală)

Fiecare strat produce:
  m({hawkish})          = credință directă hawkish
  m({dovish})           = credință directă dovish
  m({neutral})          = credință directă neutral
  m({hawkish, dovish})  = semnal directional dar ambiguu
  m(Θ)                  = ignoranță — sursa nu contribuie semnal clar
  suma = 1.0

Reliability per strat calibrată empiric pe USMPD (TBD la activare PRD-500).
"""
