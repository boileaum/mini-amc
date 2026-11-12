#let copy = json("copy.json")

#set page(width: 21cm, height: 29.7cm, margin: 2.5cm)
#set text(size: 11pt)

#let marker = 1.2cm

#place(top + left, dx: -1.9cm, dy: -1.9cm, square(size: marker, fill: black))
#place(top + right, dx: 1.9cm, dy: -1.9cm, square(size: marker, fill: black))
#place(bottom + left, dx: -1.9cm, dy: 1.9cm, square(size: marker, fill: black))
#place(bottom + right, dx: 1.9cm, dy: 1.9cm, square(size: marker, fill: black))

#place(top + right, dx: -3.6cm, dy: -1.9cm, image("qr.png", width: 3cm))

#align(center)[
  #text(16pt, weight: "bold")[#copy.meta.title]
  #linebreak()
  #text(12pt)[#copy.meta.course - #copy.meta.date]
  #linebreak()
  #text(12pt)[Copie n° #copy.copy_id]
]

#v(1cm)

#for q in copy.questions [
  #block[
    #text(weight: "bold")[#q.id - #q.text]
    #for c in q.choices [
      #block[
        #box(circle(radius: 4.5pt, stroke: 1pt))
        #h(0.4em)
        #c.key - #c.text
      ]
    ]
  ]
  #v(0.4cm)
]
