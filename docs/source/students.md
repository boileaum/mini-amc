# Students and grading

Two optional inputs turn anonymous copies into a nominative exam: a CSV of
students, read at generation time, and a grading scheme, read at grading time.
Both stay in the exam folder.

## A student list

The simplest form is two columns, `copy_id` and `name`:

```{literalinclude} ../../src/mini_amc/examples/students.example.csv
:language: text
```

```bash
mini-amc generate --bank subject.typ --students students.csv --copies 2 --seed 42
```

The link column provides the copy ids, and the number of rows must match
`--copies` - a mismatch is an error, never a silent truncation. Each copy is
then numbered after the student (`copy_21800001.pdf`), carries the student name
in its header, and the name lands in `students.json` and in the `student` column
of `notes.csv`.

## A Moodle export

A Moodle participant export works as is, with its own header names, its `;`
delimiter and its extra columns:

```{literalinclude} ../../src/mini_amc/examples/students.moodle.example.csv
:language: text
```

```bash
mini-amc generate --bank subject.typ \
  --students participants.csv \
  --students-id-column "Numéro étudiant" \
  --students-name-columns "Prénom,Nom"
```

| Option | Default | Role |
| --- | --- | --- |
| `--students` | none | CSV file; without it, copies are numbered `0001`, `0002`… |
| `--students-id-column` | `copy_id` | column that links a student to a copy |
| `--students-name-columns` | `name` | column(s) joined with a space for the display name |
| `--students-delimiter` | auto | `,` `;` tab or `\|`; detected on the first rows when empty |

Every other column is ignored, including Moodle's
`Dernier téléchargement depuis ce cours`. Quoting, a UTF-8 BOM and Windows line
endings are handled. The link column values must be unique and made of letters,
digits, `_`, `.` or `-` (they end up in file names and in the QR code); the name
must not be empty. Anything else fails before a single PDF is written:

- `participants.csv: missing column(s) ['Numéro étudiant'] (header: [...])`
- `participants.csv: line 4: duplicate copy id '21800001'`
- `participants.csv: line 7: empty name from column(s) ['Prénom', 'Nom']`

## Grading schemes

An MCQ scores under a named scheme; an open question always scores the value of
the blackened (or corrected) grade box, clamped to `[0, max-points]`, whatever
the scheme.

| Scheme | MCQ score |
| --- | --- |
| `v1` (default) | 1 pt when the checked set is exactly the expected set, else 0 |
| `amc` | +1 per correct box checked, -1 per wrong box checked, floored at 0 |

The scheme of an exam is recorded in `data/config.json` at generation time:

```json
{ "bareme": "amc" }
```

Edit that file to change the scheme for the whole exam, or pass `--bareme` to
override it for one run:

```bash
mini-amc grades --bareme amc
mini-amc web --bareme amc
```

`score_max` counts 1 pt per MCQ and `max-points` per open question, so a total
out of 20 is a division away.

## The CSV files

`mini-amc grades` writes two files in `data/`:

`notes.csv` - one row per copy:

```text
copy_id,student,status,bareme,score,score_max
21800001,Alice Martin,ok,v1,7,9
```

`notes_detail.csv` - one row per copy and question, to explain a score:

```text
copy_id,qid,type,page,checked,correction,expected,point,needs_review
21800001,q1,mcq,1,B,,B,1,False
21800001,q5,open,2,B,,open,1,False
```

`checked` and `expected` hold the choice keys joined with `+` (`A+C` for a
multi-answer question); `correction` is filled only when the review UI overrode
the reading; `needs_review` marks the rows worth a second look.
