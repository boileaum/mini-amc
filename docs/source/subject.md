# Writing the subject

The subject is a Typst file: you write the exam as you want it to read, and
`mini-amc` reads the same value back to build the copies. No separate question
bank, no second source to keep in sync.

`mini-amc init` copies `amc.typ` next to your subject. It is a small prelude
(about 100 lines of Typst) with four functions:

| Function | Returns | Notes |
| --- | --- | --- |
| `choice(text, correct: false)` | one choice | `correct: true` marks the answer key; several correct choices make a multi-answer question |
| `question(id:, text:, type: "mcq", max-points: 1, choices: ())` | one question | `type: "open"` takes no `choices` |
| `exam(title:, course:, date:, questions:)` | the bank | header + array of questions |
| `render(bank)` | the draft | the statements and the bubbles, without OMR markers, QR code or shuffle |

## A complete subject

```typst
#import "amc.typ": choice, exam, question, render

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
      text: [What is $7 times 8$?],
      choices: (choice([$54$]), choice([$56$], correct: true), choice([$63$])),
    ),
    question(
      id: "q3",
      type: "open",
      max-points: 2,
      text: "Briefly explain the French Revolution.",
    ),
  ),
)

#render(bank)
```

```bash
typst compile subject.typ subject.pdf   # the draft
mini-amc generate --bank subject.typ --copies 30 --seed 42
```

The shipped example is
[`subject.typ`](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/subject.typ),
with its second chapter
[`q/chapter.example.typ`](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/q/chapter.example.typ)
and the external code file
[`code/fizzbuzz.example.py`](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/code/fizzbuzz.example.py),
next to
[`amc.typ`](https://github.com/boileaum/mini-amc/blob/main/src/mini_amc/examples/amc.typ).

## Strings and content

A statement is Typst content. A plain string is printed verbatim, so a content
block is needed as soon as the statement carries markup:

```typst
question(id: "q1", text: "What is 7 x 8?")          // verbatim
question(id: "q2", text: [What is $7 times 8$?])    // math
```

A content block also gives you emphasis, lists, tables and fenced code. Mind
Typst math syntax: single letters are variables, so write `m c^2`, not `mc^2`.

## Open questions

An open question is answered on the paper copy and graded by the teacher, on
paper, before the scan: the copy shows a free area and a gray grader area with
lettered boxes, and the teacher blackens one box (A = 0 pt, B = 1 pt, … up to
`max-points`). The OMR reads the blackened box; an ungraded one is flagged
`needs_review` and can still be corrected in the review UI.

```typst
question(
  id: "q5",
  type: "open",
  max-points: 2,   // boxes A, B, C
  text: "Briefly explain the French Revolution.",
)
```

## Multi-answer questions

Several `correct: true` choices make a multi-answer question: the copy renders
square bubbles instead of circles, and the score is 1 pt only when the checked
set is exactly the expected set (scheme `v1`).

```typst
question(
  id: "q2",
  text: "Which of these are prime numbers?",
  choices: (
    choice("2", correct: true),
    choice("4"),
    choice("7", correct: true),
  ),
)
```

## Several files

`#exam` takes an array, so chapters can live in their own files and be joined
with `+`:

```typst
#import "amc.typ": choice, exam, question, render
#import "q/chapter1.typ": questions as chapter1
#import "q/chapter2.typ": questions as chapter2

#let bank = exam(
  title: "Demo exam",
  questions: (
    question(id: "q1", text: "What is the capital of France?", choices: (...) ),
  ) + chapter1 + chapter2,
)

#render(bank)
```

and each chapter exports its own array:

```typst
#import "../amc.typ": choice, question

#let questions = (
  question(id: "q4", text: "In which year did the French Revolution take place?",
    choices: (choice("1492"), choice("1789", correct: true), choice("1815"))),
)
```

## External code

`read()` pulls a file in, so the code printed on the copy is the real, runnable
file - no copy-paste to keep in sync:

```typst
question(
  id: "q6",
  text: [
    What does this program print?

    #raw(read("code/fizzbuzz.py", encoding: "utf8"), lang: "python")
  ],
  choices: (choice("1 2 3"), choice("1 2 Fizz", correct: true), choice("Fizz 2 3")),
)
```

## Checking the layout

```bash
typst watch subject.typ subject.pdf   # draft, live re-render on save
mini-amc preview --png                # the real copy, in ./preview
```

The draft (`#render`) shows the statements and the bubbles as the students will
read them, without the OMR markers, the QR code and the per-copy shuffle. The
copies themselves are rendered by the template, which also emits the positions
the OMR relies on.

## Errors and checks

The prelude asserts while the subject is read, so a broken question fails before
any copy is generated, with the line and caret in your own file:

- `question: id is required`
- `question q1: at least 2 choices required`
- `question q1: at least 1 correct choice required`
- `question q5: an open question takes no choices`

`mini-amc` then checks the bank as a whole:

| Rule | Error |
| --- | --- |
| at least one question | `empty bank: no questions` |
| every question has an `id` | `every question needs an id` |
| ids are unique | `duplicate question ids: …` |
| every question has a `text` | `question q1: 'text' required` |
| 2 to 26 choices per MCQ | `question q1: 2 to 26 choices required` |
| open question: `max-points` between 1 and 20 | `question q5: open question needs max_points (int >= 1)` |
