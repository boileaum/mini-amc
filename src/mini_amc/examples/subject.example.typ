// Example subject written in Typst with the mini-amc prelude.
//
// Generate the copies from this file instead of a YAML bank:
//   mini-amc generate --bank subject.example.typ --copies 30 --seed 42
// Preview it while you write (live re-render on save):
//   typst watch subject.example.typ subject.pdf
//
// `amc.typ` ships next to this file (copied by `mini-amc init`); the texts are
// markup strings, so `$…$` math and ``` code fences ``` work like in the YAML.

#import "amc.typ": exam, question, choice

#show: exam.with(
  title: "Demo exam",
  course: "Demo 101",
  date: "2026-11-12",
)

#question(id: "q1", text: "What is the capital of France?")[
  #choice("Paris", correct: true)
  #choice("Lyon")
  #choice("Marseille")
]

#question(id: "q2", text: "What is the largest ocean in the world?")[
  #choice("Atlantic")
  #choice("Indian")
  #choice("Pacific", correct: true)
]

#question(id: "q3", text: "What is $7 times 8$?")[
  #choice("$54$")
  #choice("$56$", correct: true)
  #choice("$63$")
]

#question(id: "q4", text: "In which year did the French Revolution take place?")[
  #choice("1492")
  #choice("1789", correct: true)
  #choice("1815")
]

#question(id: "q5", type: "open", max-points: 2, text: "Briefly explain the French Revolution.")[]
