// Second chapter of the example subject: its questions live in their own file
// and the subject joins them with `+`. Any number of chapters can be split
// this way (one file per part of the course, for instance).
//
// `read()` pulls in an external file (here a Python snippet) so the code shown
// on the copy is the real, runnable file: no copy-paste to keep in sync.

#import "../amc.typ": choice, question

#let questions = (
  question(
    id: "q4",
    text: "In which year did the French Revolution take place?",
    choices: (
      choice("1492"),
      choice("1789", correct: true),
      choice("1815"),
    ),
  ),
  question(
    id: "q5",
    type: "open",
    max-points: 2,
    text: "Briefly explain the French Revolution.",
  ),
  question(
    id: "q6",
    text: [
      What does this program print?

      #raw(read("../code/fizzbuzz.example.py", encoding: "utf8"), lang: "python")
    ],
    choices: (
      choice("1 2 3"),
      choice("1 2 Fizz", correct: true),
      choice("Fizz 2 3"),
    ),
  ),
)
