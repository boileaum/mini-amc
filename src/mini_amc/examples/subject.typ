// Example subject written in Typst with the mini-amc prelude.
//
// Generate the copies from this file:
//   mini-amc generate --bank subject.typ --copies 30 --seed 42
// Check the layout while you write (live re-render on save):
//   typst watch subject.typ subject.pdf
//
// `amc.typ` ships next to this file (copied by `mini-amc init`). Questions are
// values: `#question(...)` returns one and `#exam(...)` takes the array. Split
// them over several files and join with `+` (see q/chapter.example.typ).
//
// A statement is Typst content: a plain string is printed verbatim, so use a
// content block `[...]` as soon as it needs markup, e.g. `$7 times 8$`.

#import "amc.typ": choice, exam, question, render
#import "q/chapter.example.typ": questions as chapter

#let bank = exam(
  title: "Demo exam",
  course: "Demo 101",
  date: "2026-11-12",
  questions: (
    question(
      id: "q1",
      text: "What is the capital of France?",
      choices: (
        choice("Paris", correct: true),
        choice("Lyon"),
        choice("Marseille"),
      ),
    ),
    question(
      id: "q2",
      text: "What is the largest ocean in the world?",
      choices: (
        choice("Atlantic"),
        choice("Indian"),
        choice("Pacific", correct: true),
      ),
    ),
    question(
      id: "q3",
      text: [What is $7 times 8$?],
      choices: (
        choice([$54$]),
        choice([$56$], correct: true),
        choice([$63$]),
      ),
    ),
  ) + chapter,
)

// Draft PDF of the subject: `typst compile subject.typ`
#render(bank)
