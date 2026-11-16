# Proposal: player-facing names and content handoff

The key distinction is between **what the theater sells** and **who supplies it**. Lead menus with the familiar food or action, and put supplier and procurement details below it.

## Concessions

| Current supply description | Customer-facing offer | Details beneath the offer |
| --- | --- | --- |
| A supplier's popping kernels | Plain popcorn | Kernel supplier, quality, yield and ingredient cost |
| Kernels + dairy butter | Buttered popcorn | Both suppliers and butter usage |
| Kernels + butter-flavored oil | Butter-flavored popcorn | Oil supplier, yield and shelf life |
| Kernels + savory seasoning | Savory popcorn | Seasoning profile and supplier |
| Kernels + butter-style spread | Butter-style popcorn | Spread supplier and cost |
| A supplier's cola syrup | Fountain cola | Syrup supplier, tank level and cost per serving |

This pass implements the short popcorn headings. It keeps supplier/product identifiers intact so saves and purchasing continue to refer to the correct goods. Broader renaming can be a presentation change, not an inventory migration.

For the next content pass, give each product structured fields such as `service_name`, `brand`, `producer`, `ingredient_kind` and `pitch`. Avoid deriving recipe identity from substrings of generated names. Generated prose should never be required to calculate a recipe or decide which machine it uses.

Keep a selected supplier until the player changes it. Show a persistent reserve target and exceptions such as “below target: monthly budget exhausted.” Do not ask players to reselect an unchanged recipe or manually refill every month. The new Keep counter stocked flow and refill automation provide this behavior now.

## Movie titles and employee pitches

Generate titles from compatible grammatical templates. For example, use `The Secret of {place}` only with a place phrase whose article is known; do not blindly combine `The Last` with `the Glass City`. Keep a template's casing and article rules with its vocabulary.

Separate a film's logline from employee observations and its production sheet:

1. **Logline:** protagonist, concrete objective and obstacle, in one or two sentences.
2. **Viewing notes:** observed performance, pacing, unusual structure and visible production quirks.
3. **Production sheet:** studio, director, genre/subgenre, runtime and public budget.

Employee notes should describe observations without exposing the hidden score or instructing the player to book/reject the film. Genre should constrain plot ingredients enough to avoid mismatched pitches. Production traits should affect descriptions through explicit fields rather than unstructured invented details.

## Suggested Gemini handoff

Ask for a small, structured content pack with familiar concession service names, supplier brands, genre-specific title templates and neutral viewing-note templates. Include valid and invalid example combinations. Keep gameplay numbers, supplier contracts and save identifiers outside this prose pass. Review a seeded sample of generated combinations before expanding the pack or adding historical vocabulary.
