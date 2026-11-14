#let copy = json("copy.json")

#let marker = 1.2cm
#let corner = 0.7cm
#let qr-size = 3cm

#set page(
  width: 21cm,
  height: 29.7cm,
  margin: (top: 4.5cm, right: 2.5cm, bottom: 2.5cm, left: 2.5cm),
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
  #text(16pt, weight: "bold")[#copy.meta.title]
  #linebreak()
  #text(12pt)[#copy.meta.course - #copy.meta.date]
  #linebreak()
  #text(12pt)[Copy no. #copy.copy_id]
]

#v(1cm)

#for q in copy.questions [
  #block(breakable: false)[
    #context [#metadata((kind: "question", copy: copy.copy_id, qid: q.id, page: here().page(), x: here().position().x, y: here().position().y))]
    #text(weight: "bold")[#q.id - #q.text]
    #if q.at("type", default: "mcq") == "open" [
      #block(width: 100%, height: 3cm, stroke: 0.5pt)
      #v(0.2cm)
      #text(9pt)[Grade:]
      #for v in range(0, q.max_points + 1) [
        #context [#metadata((kind: "gradebox", copy: copy.copy_id, qid: q.id, value: v, page: here().page(), x: here().position().x, y: here().position().y))]
        #box(circle(radius: 4.5pt, stroke: 1pt))
        #h(0.3em)
        #v
        #h(0.8em)
      ]
    ] else [
      #for c in q.choices [
        #block[
          #context [#metadata((kind: "bubble", copy: copy.copy_id, qid: q.id, key: c.key, page: here().page(), x: here().position().x, y: here().position().y))]
          #box(circle(radius: 4.5pt, stroke: 1pt))
          #h(0.4em)
          #c.key - #c.text
        ]
      ]
    ]
  ]
  #v(0.4cm)
]
