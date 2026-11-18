// One exam copy. The build directory is self-contained (main.typ, bank.typ,
// copy.json, qr-N.png): `typst compile main.typ out.pdf` works there as is.
//
// `bank` is the exam as the author wrote it (the subject, imported through the
// generated bank.typ); `copy.json` is the plan: which source question and
// which source choice go where on this copy. The statements therefore reach
// the PDF as the author's content, never as a re-parsed string.
#import "bank.typ": bank
#let copy = json("copy.json")

#let marker = 1.2cm
#let corner = 0.7cm
#let qr-size = 3cm

#set page(
  width: 21cm,
  height: 29.7cm,
  // top margin 4.5cm so the body never overlaps the QR/markers
  margin: (top: 4.5cm, right: 2.5cm, bottom: 2.5cm, left: 2.5cm),
  // drawn in the page background so they appear on every page, including
  // overflow pages; right/bottom corners need negative dx/dy (place() is
  // relative to the corner, the square must go inward)
  background: [
    #place(top + left, dx: corner, dy: corner, square(size: marker, fill: black))
    #place(top + right, dx: -corner, dy: corner, square(size: marker, fill: black))
    #place(bottom + left, dx: corner, dy: -corner, square(size: marker, fill: black))
    #place(bottom + right, dx: -corner, dy: -corner, square(size: marker, fill: black))
    #place(
      top + right,
      dx: -(corner + qr-size + marker + 0.3cm),
      dy: corner,
      context image("qr-" + str(here().page()) + ".png", width: qr-size),
    )
  ],
)
#set text(size: 11pt)

#v(0.8cm)

#align(center)[
  #text(16pt, weight: "bold")[#bank.at("title", default: "")]
  #linebreak()
  #text(12pt)[#bank.at("course", default: "") - #bank.at("date", default: "")]
  #linebreak()
  #text(12pt)[Copy no. #copy.copy_id]
  // with --students, also print the student name on the copy
  #if copy.at("student", default: none) != none [
    #linebreak()
    #text(12pt)[#copy.student]
  ]
]

#v(1cm)

#for p in copy.questions [
  #let q = bank.questions.at(p.src)
  #block(breakable: false)[
    #context [#metadata((kind: "question", copy: copy.copy_id, qid: q.id, page: here().page(), x: here().position().x, y: here().position().y))]
    #text(weight: "bold")[#q.id - #q.text]
    #if q.at("type", default: "mcq") == "open" [
      #block(width: 100%, height: 3cm, stroke: 0.5pt)
      #v(0.2cm)
      // grader area, AMC-style: gray background so the grade boxes are
      // visually distinct from the student bubbles; letter labels (A, B, …)
      // instead of numbers so they don't suggest a scale - the numeric value
      // stays in the #metadata, which is what the OMR reads
      #box(fill: luma(235), inset: 0.3em)[
        #for v in range(0, q.at("max-points", default: 1) + 1) [
          #context [#metadata((kind: "gradebox", copy: copy.copy_id, qid: q.id, value: v, page: here().page(), x: here().position().x, y: here().position().y))]
          #box(circle(radius: 4.5pt, stroke: 1pt))
          #h(0.3em)
          #"ABCDEFGHIJKLMNOPQRSTUVWXYZ".at(v)
          #h(0.8em)
        ]
      ]
    ] else [
      // multi-answer questions get square bubbles (single-answer: circles)
      #let multi = p.at("multi", default: false)
      #for c in p.choices [
        #let source = q.choices.at(c.src)
        #block[
          #context [#metadata((kind: "bubble", copy: copy.copy_id, qid: q.id, key: c.key, multi: multi, shape: if multi { "square" } else { "circle" }, page: here().page(), x: here().position().x, y: here().position().y))]
          #box(if multi { square(size: 9pt, stroke: 1pt) } else { circle(radius: 4.5pt, stroke: 1pt) })
          #h(0.4em)
          // no letter printed on the student copy: the key stays in the
          // #metadata (OMR) and in copy_XXXX.json / answers.json
          #source.text
        ]
      ]
    ]
  ]
  #v(0.4cm)
]
