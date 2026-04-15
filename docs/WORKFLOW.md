# Workflow — PRD → Claude Code prompt → commit

> Workflow disciplinat pentru a evita stacking fixes pe cod neverificat.

## Roluri

- **Tu (developer)** — decizii, validări, code review
- **Chat A (Claude architect)** — generează prompturi pentru Claude Code, menține PRD-uri, ROADMAP
- **Claude Code** — execută prompturi, scrie cod, rulează teste, commit

## Flux standard

```
1. Idee/feature nou
       ↓
2. Discuție în Chat A (decizii arhitecturale, trade-offs)
       ↓
3. PRD draft generat (dacă e major) sau prompt direct (dacă e minor)
       ↓
4. Aprobare PRD/prompt
       ↓
5. Prompt Claude Code emis
       ↓
6. Claude Code:
   - Verifică context awareness (preconditions)
   - Implementează
   - Rulează teste
   - Commit + push
       ↓
7. Tu validezi rezultatul (output, plot, smoke test)
       ↓
8. La sfârșit de sesiune: checkout cu update ROADMAP/PRD
```

## Reguli non-negociabile

- Niciun prompt fără PRD aprobat (pentru features majore)
- Toate prompturile pe cod existent au secțiune **"Context awareness"** cu preconditions verificate (DEC D26)
- Decizii se iau în chat, nu în PRD-uri mid-session (DEC D19)
- Documentație consolidată la checkout, nu continuu (DEC D19)

## Ce e "minor" vs "major"

**Minor** (prompt direct, fără PRD):
- Renames, refactors mecanice
- Bug fixes localizate
- Update-uri docs, MAP.md
- Patches mici (logging, error handling)

**Major** (PRD obligatoriu):
- Feature nou (algoritm, layer)
- Decizie metodologică (alegere model, formula)
- Modificare arhitecturală (cum interacționează module)

## Anatomy unui prompt Claude Code corect

```
# PRD-XXX / CC-N — Short title

## CONTEXT
[Current state, what this CC adds, what NOT to touch]
[Context awareness preconditions — bash checks cu Expected outputs]

## TASK
[One-liner clear task]

## STACK
[Python version, key libraries]

## FILES
[Create / modify / delete lists]

## IMPLEMENTATION
[Step-by-step]

## CONSTRAINTS
[Limits, rules]

## DONE WHEN
[Verifiable conditions — grep counts, test pass, file exists]
```

Context awareness pattern (DEC D26):
> "Patch X assumes state Y — check Y. IF Y exists THEN apply. IF NOT return BLOCKER and halt."

## Anti-patterns de evitat

- ❌ "Fix-uri pe fix-uri" fără context awareness — duce la stacking
- ❌ Prompt vag ("îmbunătățește modulul X") — Claude Code ghicește
- ❌ Schimbări concomitente pe același fișier de la 2 sesiuni
- ❌ PRD-uri create mid-session ("o să documentez după") — uitate
- ❌ Commit fără teste — descoperire bug în production
- ❌ Fabricare de DEC/PRD IDs fără verificare în ROADMAP

## La sfârșit de sesiune (checkout)

Generează prompt Claude Code pentru:
1. Update `ROADMAP.md` cu PRD statuses noi
2. Add new DEC entries (next sequential number — verifică cu `grep`)
3. Update Technical Debt log dacă s-au descoperit TDs
4. Commit + push pe main

Vezi exemple în commit history: `0cb3493`, `d83156b` (checkout 2026-04-15).

## Test coverage rule (CLAUDE.md v1.4)

Orice PRD care introduce cod nou într-un modul fără test coverage existent include **obligatoriu** cel puțin un Claude Code prompt dedicat testelor. Un PRD nu poate fi marcat Done până când suita de teste pentru modulul respectiv nu trece.
