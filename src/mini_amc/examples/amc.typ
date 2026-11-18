// mini-amc subject prelude: write the exam in Typst, mini-amc reads it back.
//
// The subject is the single source of truth. `#exam(...)` returns a plain
// value (a dictionary) and the template renders it, so what you write and what
// the students get cannot drift apart. `mini-amc generate --bank subject.typ`
// reads that same value back with `typst eval`.
//
// Why values instead of #metadata() + strings: a mistake in a question points
// at your own file (line and caret) instead of the template, and the texts
// stay real Typst content ($math$, `raw`, emphasis) instead of strings
// re-parsed by `eval()` at render time.

// One choice. `correct: true` marks the answer key; several correct choices
// make a multi-answer question (square bubbles on the copy).
#let choice(text, correct: false) = (text: text, correct: correct)

// One question, returned as a value: collect the questions in an array, split
// them over several files and join them with `+`.
//
// `text` takes a string (printed verbatim) or a content block `[...]` when the
// statement needs markup: `text: [What is $7 times 8$?]`. The assertions run
// while the subject is read, so a broken question fails before any copy is
// generated.
#let question(id: none, text: [], type: "mcq", max-points: 1, choices: ()) = {
  assert(id != none, message: "question: id is required")
  if type == "open" {
    assert(
      choices.len() == 0,
      message: "question " + str(id) + ": an open question takes no choices",
    )
  } else {
    assert(
      choices.len() >= 2,
      message: "question " + str(id) + ": at least 2 choices required",
    )
    assert(
      choices.any(c => c.correct),
      message: "question " + str(id) + ": at least 1 correct choice required",
    )
  }
  (id: id, text: text, type: type, max-points: max-points, choices: choices)
}

// The exam: header and questions. `questions` is an array of #question()
// values, so chapters can be written in separate files and concatenated.
#let exam(title: "", course: "", date: "", questions: ()) = (
  title: title,
  course: course,
  date: date,
  questions: questions,
)

// Draft rendering of a bank, for `typst compile subject.typ` (or `typst
// watch`) while writing: the statements and the bubbles as the students will
// read them, without the OMR markers, the QR code or the per-copy shuffle.
// The exam copies are rendered by the template (mini_amc/template/main.typ),
// which also emits the #metadata() the OMR relies on.
#let render(bank) = {
  align(center)[
    #text(16pt, weight: "bold")[#bank.at("title", default: "")]
    #linebreak()
    #text(12pt)[#bank.at("course", default: "") - #bank.at("date", default: "")]
  ]
  v(1cm)
  for q in bank.questions [
    #block(breakable: false)[
      #text(weight: "bold")[#q.id - #q.text]
      #if q.at("type", default: "mcq") == "open" [
        #block(width: 100%, height: 3cm, stroke: 0.5pt)
        #v(0.2cm)
        #box(fill: luma(235), inset: 0.3em)[
          #for v in range(0, q.at("max-points", default: 1) + 1) [
            #box(circle(radius: 4.5pt, stroke: 1pt))
            #h(0.3em)
            #"ABCDEFGHIJKLMNOPQRSTUVWXYZ".at(v)
            #h(0.8em)
          ]
        ]
      ] else [
        #let multi = q.choices.filter(c => c.correct).len() > 1
        #for c in q.choices [
          #block[
            #box(if multi {
              square(size: 9pt, stroke: 1pt)
            } else {
              circle(radius: 4.5pt, stroke: 1pt)
            })
            #h(0.4em)
            #c.text
          ]
        ]
      ]
    ]
    #v(0.4cm)
  ]
}
