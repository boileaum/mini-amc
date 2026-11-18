// YAML bank adapter: `main.typ` always imports `bank`, whether the exam was
// written as a Typst subject (then `bank.typ` is a one-line import of the
// subject) or as a YAML bank (then this file reads `bank.json`).
//
// eval(mode: "markup") is the price of YAML: the statements are strings, so
// they are parsed as markup here, which is what makes `$…$` math and
// ``` code fences ``` work in a YAML bank. A Typst subject needs no eval: its
// statements are already content.

#let data = json("bank.json")
#let meta = data.at("meta", default: (:))

#let bank = (
  title: meta.at("title", default: ""),
  course: meta.at("course", default: ""),
  date: meta.at("date", default: ""),
  questions: data.questions.map(q => (
    id: q.id,
    text: eval(str(q.text), mode: "markup"),
    type: q.at("type", default: "mcq"),
    max-points: q.at("max_points", default: 1),
    choices: q.at("choices", default: ()).map(c => (
      text: eval(str(c.text), mode: "markup"),
      correct: c.at("correct", default: false),
    )),
  )),
)
