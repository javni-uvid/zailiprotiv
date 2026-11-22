# The family's data

What more than one project needs, kept once. A project reads it from its copy (`osnova/data/`) and never
corrects it there: a correction is a pull request in `javni-uvid/osnova`.

## municipalities.csv

Serbia's 168 municipalities, cities and city municipalities, as RIK's address book of local electoral
commissions lists them, and each one's web site.

| Column | What |
|---|---|
| `municipality_code` | the Statistical Office's code (five digits): **the key every project names a municipality by**, so that its page on one site can link its page on another. A municipality the Office has no code for has `r` and RIK's number (Vranjska Banja: `r162`), as izborna-analiza names it |
| `name` | as RIK writes it, in Cyrillic; a project turns it into Latin itself |
| `domain` | the site's domain, bare (`valjevo.rs`); empty where the commission's address is a webmail one and no site has been found |
| `note` | where the domain comes from (`rik-adresar`), and every change of it with the day and who made it |

The **sites** workflow asks for each site weekly; a domain that doesn't answer is replaced by a spelling of it
that does (`.rs`, `.org.rs`, `.ls.gov.rs`, `.gov.rs`), the old one named in the note (`tools/sites.py`). A site
found by hand goes in the same way, with the source in the note. What only one project needs about a
municipality (izborna-analiza's pages of its commission) stays in that project, under the same code.
