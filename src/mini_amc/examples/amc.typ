// mini-amc subject prelude: author the exam in Typst, mini-amc reads it back.
//
// Every element emits a #metadata() entry; `mini-amc generate --bank subject.typ`
// runs `typst eval` on the file and rebuilds the question bank from those
// entries, so the subject you write and the copies the students get never
// drift apart. Texts are markup strings (like the YAML bank): `$…$` math and
// ``` code fences ``` are rendered by `eval(text, mode: "markup")`.

// Page header + document wrapper: `#show: exam.with(title: …, course: …, date: …)`
// `body` comes first because only defaulted parameters are named in Typst: a
// trailing `body` would be a named parameter and `#show` could not fill it.
#let exam(body, title: "", course: "", date: "") = {
  metadata((kind: "meta", title: title, course: course, date: date))
  align(center)[
    #text(16pt, weight: "bold")[#title]
    #linebreak()
    #text(12pt)[#course - #date]
  ]
  v(1cm)
  body
}

// One question, with its #choice() calls in the body. An open question takes
// `type: "open"` and `max-points: N`, and no choices.
#let question(body, id: none, text: "", type: "mcq", max-points: 1) = {
  assert(id != none, message: "question: id is required")
  metadata((
    kind: "question",
    id: id,
    text: text,
    type: type,
    max_points: max-points,
  ))
  block(breakable: false)[
    #strong[#id - #eval(text, mode: "markup")]
    #body
  ]
  v(0.4cm)
}

// One choice of the enclosing question. `correct: true` marks the answer key;
// several correct choices make a multi-answer question (square bubbles).
// `text` has no default on purpose: only defaulted parameters are named, so
// this makes `#choice("Paris")` valid and keeps `correct:` optional.
#let choice(text, correct: false) = {
  metadata((kind: "choice", text: text, correct: correct))
  block[
    #box(circle(radius: 4.5pt, stroke: 1pt))
    #h(0.4em)
    #eval(text, mode: "markup")
  ]
}
